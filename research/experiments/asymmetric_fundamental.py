"""Preregistered finite Train-only screening. No Valid evaluation or freeze."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import resource
import shutil
import signal
import sys
import time
import traceback
import warnings
import numpy as np
import pandas as pd
from stock_comp_2026.strategies.dm_asymmetric_fundamental import features as sf
from stock_comp_2026.strategies.dm_asymmetric_fundamental.submission import predict
from research import firewall
from research.evaluation import bootstrap_delta
from research.experiments import asymmetric_evaluation as ev
from research.experiments.asymmetric_audit import audit_inputs, coverage_tables

ROOT=Path(__file__).resolve().parents[2]


def clean(value):
    if isinstance(value,dict): return {k:clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [clean(v) for v in value]
    if isinstance(value,(float,np.floating)): return float(value) if np.isfinite(value) else None
    if isinstance(value,np.integer): return int(value)
    if isinstance(value,np.bool_): return bool(value)
    return value


def dump(path, obj):
    Path(path).write_text(json.dumps(clean(obj),indent=2,ensure_ascii=False,allow_nan=False,default=str)+'\n')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def now(): return datetime.now(timezone.utc).isoformat()


def validate_config(c):
    assert c['data_split']=='train' and c['valid_evaluation'] is False
    assert c['max_trials']==18 and len(c['trials'])==18
    assert [x['year'] for x in c['walk_forward_folds']]==[2011,2012,2013,2014]
    assert c['train_window']==['2008-11-04','2016-03-31']
    assert c['purge_trading_days']>=2 and c['parameters']['alpha']==.25
    assert c['feature_definitions']['freshness_calendar_days']==450
    assert c['feature_definitions']['yoy_tolerance_days']==7
    assert c['feature_definitions']['fiscal_periods']=={k:list(v) for k,v in sf.PERIODS.items()}
    assert c['transaction_cost_oneway']==.001 and c['annualization']==252
    assert c['parameters']['lambdas']==[.25,.5,.75,1.] and c['parameters']['gammas']==[.25,.5] and c['parameters']['deltas']==[.25,.5]
    assert c['random_seed']==20260909


def write_report(out,c,records,representatives,skipped,confirmation,manifest):
    lines=[f"# {c['experiment_id']}: 非対称Momentum / Fundamental Short 一次選別",'',
           f"Run: `{manifest['run_id']}`。Train-only。Valid/raw target未参照。提出用Freezeなし。",'',
           '## 判定','',
           '| 仮説 | 代表候補 | 判定 | 改善fold | median ΔNet SR | bootstrap 95% CI |',
           '|---|---|---|---:|---:|---|']
    for family,r in representatives.items():
        comp,ci=r['comparison'],r['bootstrap']
        lines.append(f"| {family} | {r['id']} | {r['decision']} | {comp['joint_folds']}/4 | {comp['median_delta_net_sr']:.4f} | [{ci['low']:.4f}, {ci['high']:.4f}] |")
    for family,reason in skipped.items(): lines.append(f'| {family} | 未実行 | {reason} | — | — | — |')
    lines += ['',f"実試行数 {len(records)}/18。旧研究30試行を含む既知の累積scoring試行数は{30+len(records)}。未実行枠の転用なし。",'',
              '一次基準の不通過は今回の定義を却下する判断であり、財務Short一般の無効果の証明ではない。',
              '基準通過でもbootstrap下限が0以下なら保留。CIは候補選択後の未補正の記述的区間で、独立な有意性検定ではない。','',
              '## 全候補の開発成績','',
              '| Trial | Gross SR | Net SR | RankIC | Turnover | 年率Cost | Short年率Net | Long年率Net |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in records:
        m=r['metrics']
        lines.append(f"| {r['id']} | {m['gross_sharpe']:.4f} | {m['net_sharpe']:.4f} | {m['rankic']:.5f} | {m['turnover']:.4f} | {m['annual_cost']:.2%} | {m['annual_short_net']:.2%} | {m['annual_long_net']:.2%} |")
    lines+=['','## Foldと増分','', '全候補のfold/年別・Q1–Q5・上下decile・Long/Short別・DD・RankIC/HAC5/hitは `fold_metrics.csv`。',
            'baseline差分と前段差分は `incremental.csv`。棄却した条件は `trial_registry.json` のchecks。','']
    for family,r in representatives.items():
        lines += [f"### {family}: {r['id']}",'',f"不通過条件: {', '.join(k for k,v in r['comparison']['checks'].items() if not v) or 'なし'}",'',
                  '| 年 | Net SR | ΔNet SR | ΔShort年率Net | ΔLong年率Net |','|---|---:|---:|---:|---:|']
        for m,d in zip(r['folds'],r['comparison']['fold_deltas']):
            lines.append(f"| {m['year']} | {m['net_sharpe']:.4f} | {d['net_sharpe']:.4f} | {d['annual_short_net']:.2%} | {d['annual_long_net']:.2%} |")
    lines+=['','## 既読Trainの再確認','',
            '2015–2016年3月は旧研究で既読。未使用holdoutではない。selection_before_confirmation.json保存後に代表だけを評価し、再選択していない。2016年は部分年。','',
            '| Trial | 再確認Net SR | Short年率Net | Long年率Net |','|---|---:|---:|---:|']
    for name, item in confirmation.items():
        m=item['metrics'];lines.append(f"| {name} | {m['net_sharpe']:.4f} | {m['annual_short_net']:.2%} | {m['annual_long_net']:.2%} |")
    lines += ['', '## 設計・診断・制約','',
              '- Long固定診断は `fixed_long_summary.csv` / `metrics/fixed_long_*.csv`。公式スコアとは別の配分実験。',
              '- 財務PIT利用率は `audit/coverage_*.csv`、財務条件付き集計は `metrics/conditional_financial.csv`、FD×WeakPriceは `metrics/fd_weak_3x3.csv`。',
              '- CFO系は当日×期間種別のrank。450日失効。Net CashはCash−(Assets−Equity)の代理値で、有利子負債控除後のNet Cashではない。',
              '- Tailは20/80%境界の同値を含む。Eventの多数のゼロも比較群に保持し、Short高群は正の証拠を要求する。',
              '- 開示時刻不明のため開示翌営業日から信号に利用。四半期CFO欠損、会計基準差、銘柄選択、既読Trainへの依存がある。',
              '- S0のrankは相対的な悪化・弱含み。絶対値負の追加Gateなし。L−λSはShortの完全置換ではなく、Long構成も変わる。',
              '- 固定式候補はラベル学習なし。Impactのみ前年までの入力でcross-fit。Label t+2が各年の境界を跨ぐ2営業日を損益集計から除く。',
              '- 公式5分位・片道0.1%・年率252・標本標準偏差。DDは加算と複利を併記。年境界で建玉は継続し初期costは1回。',
              '- 欠損labelで落ちる公式costと全建玉costを別計上。Long/Short正負weight変化に配賦して総額を照合。',
              '', '## 再現・監査','',
              f"コードsnapshot、SHA-256、環境、コマンド、データhash、実行時間・最大RSSはrun.json。runパス: `artifacts/{c['experiment_id']}/{manifest['run_id']}`。",
              'audit/causality.jsonに全入力のfuture-mutation/truncation、baseline bitwise一致を記録。audit/submission.jsonに全Train coverage・決定性・独立プロセス推論一致を記録。',
              '新規戦略の合成境界テストと既存Freeze検証も実行。全試行・不採用・未実行理由を保持する。','']
    (out/'REPORT.md').write_text('\n'.join(lines))


def run(config_path,out):
    c=json.loads(config_path.read_text()); validate_config(c)
    m=json.loads((out/'run.json').read_text())
    assert m['status']=='prepared' and config_path.resolve()==(out/'config.json').resolve()
    for name,h in m['snapshot_sha256'].items(): assert digest(out/name)==h
    t0=time.perf_counter(); m.update(status='running',started_at_utc=now(),command=sys.argv,actual_trials=0)
    dump(out/'run.json',m)
    def emit(msg):
        print(msg,flush=True)
        with (out/'logs/progress.log').open('a') as stream: stream.write(now()+' '+msg+'\n')
    records=[]
    try:
        own_predictions = [out/f'predictions/submission_{i}.parquet' for i in [1, 2]]
        firewall.install(allowed_artifacts=own_predictions)
        sources=list(Path(sf.__file__).parent.glob('*'))+[Path(__file__),Path(ev.__file__),
                 ROOT/'research/experiments/asymmetric_audit.py', ROOT/'research/evaluation.py',ROOT/'research/firewall.py',
                 ROOT/'tools/run_bounded.py',ROOT/'stock_comp_2026/evaluate_script.py',
                 ROOT/'stock_comp_2026/strategies/dm_trainonly/features.py',
                 ROOT/'AGENTS.md', ROOT/'docs/strategies/投資戦略仮説0909.md']
        sources += list((ROOT/'tests/strategies/dm_asymmetric_fundamental').glob('*.py'))
        m['code_sha256']={str(p.relative_to(ROOT)):digest(p) for p in sources if p.is_file()}
        for rel in m['code_sha256']:
            dest=out/'source'/rel; dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dest)
        import scipy, pyarrow, sklearn
        m['environment']=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,pyarrow=pyarrow.__version__,sklearn=sklearn.__version__,platform=platform.platform())
        stage=out/'train_stage';stage.mkdir()
        data=ROOT/c['data_directory']
        names=list(sf.core.INPUT_COLUMNS)+['fins_statements']
        m['train_data_sha256']={}
        for name in names:
            p=data/f'{name}_train.parquet'
            (stage/p.name).symlink_to(p.resolve())
            m['train_data_sha256'][p.name]=digest(p)
        dump(out/'run.json',m)
        emit('Loading only allowed Train features; labels remain unopened')
        inputs=sf.load_inputs(stage,'train'); f=sf.build_features(inputs)
        coverage_tables(f,out/'audit');dump(out/'audit/financial.json',f.attrs['financial_audit'])
        dump(out/'models/impact_crossfit.json',f.attrs['impact_audit'])
        emit(f'Features: {f.shape}; starting label-free causality audits')
        qa=audit_inputs(inputs,f,emit);dump(out/'audit/causality.json',qa)
        # Independent inference process, with only feature files staged.
        import subprocess
        for attempt in [1,2]:
            script = out/'audit/submission_smoke.py'
            if attempt==1:
                script.write_text('import sys\nfrom pathlib import Path\nsys.path.insert(0,'+repr(str(ROOT))+')\nfrom research.firewall import install\ninstall()\nfrom stock_comp_2026.strategies.dm_asymmetric_fundamental.submission import predict\np=predict(split="train")\np.to_parquet(sys.argv[1])\n')
            dest=out/f'predictions/submission_{attempt}.parquet'
            result=subprocess.run([sys.executable,str(script.resolve()),str(dest.resolve())],cwd=stage,capture_output=True,text=True,timeout=1800)
            (out/f'logs/submission_{attempt}.log').write_text(result.stdout+result.stderr)
            if result.returncode: raise RuntimeError(result.stderr)
        p1=pd.read_parquet(own_predictions[0]);p2=pd.read_parquet(own_predictions[1])
        default=json.loads(Path(sf.__file__).with_name('research_config.json').read_text())
        pd.testing.assert_frame_equal(p1,sf.predict_from_features(f,default).to_frame(),check_exact=True)
        pd.testing.assert_frame_equal(p1,p2,check_exact=True)
        assert p1.index.equals(f.index) and np.isfinite(p1.to_numpy()).all()
        dump(out/'audit/submission.json',dict(status='PASS',rows=len(p1),columns=1,coverage=1.,bitwise_research=True,deterministic=True,independent_processes=2))
        dates=f.index.get_level_values('Date');calendar=dates.unique().sort_values()
        assert str(calendar[0].date())==c['train_window'][0] and str(calendar[-1].date())==c['train_window'][1]
        dev_dates=ev.safe_dates(calendar,[2011,2012,2013,2014]); confirmation_dates=ev.safe_dates(calendar,[2015,2016])
        dump(out/'audit/purge.json',dict(purge_days=2,development_dates=[str(x.date()) for x in dev_dates],confirmation_dates=[str(x.date()) for x in confirmation_dates],prediction_coverage_includes_last_two=True,portfolio_continues_over_excluded_days=True))
        label=data/'target_1day_train.parquet';(stage/label.name).symlink_to(label.resolve())
        m['train_data_sha256'][label.name]=digest(label);dump(out/'run.json',m)
        emit('PIT/causality audits passed; reading development labels only')
        target=pd.read_parquet(stage/label.name,filters=[('Date','<',pd.Timestamp('2015-01-01'))])['Return']
        dev_index=f.index[(dates>=pd.Timestamp('2011-01-01'))&(dates<pd.Timestamp('2015-01-01'))].intersection(target.index)
        target_dev=target.reindex(dev_index)
        diagnostic_y=target.reindex(f.index).where(dates.isin(dev_dates))
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            ev.diagnostics(f,diagnostic_y,out/'metrics')
        emit('Preregistered financial diagnostics saved; scoring finite trials')
        population=f.financial_available & (f.momentum_available>0)
        base_signal=f.L.rename('Return');dailies={};specs={}
        def evaluate(spec,ref=None):
            if len(records)>=c['max_trials']: raise RuntimeError('Scoring budget exceeded')
            name=spec['trial_id'];signal=sf.predict_from_features(f,spec);short=sf.short_score(f,spec)
            score_daily=ev.account(signal.reindex(dev_index),target_dev,short,population,base_signal).loc[dev_dates]
            record=dict(id=name,spec=spec,metrics=ev.extended_metrics(score_daily),folds=ev.fold_metrics(score_daily),
                        complexity={'baseline':0,'A':1,'A_smooth':2,'B':3,'C':4,'Event':2}[spec['family']],
                        date=now(),feature_set='registered financial/PIT + fixed M60',train_window=c['train_window'],evaluation_window='2011-2014 purged annual folds')
            if ref:
                record['comparison']=ev.comparison(record,ref,c['selection_rule'])
                record['baseline_comparison']=ev.comparison(record,records[0],c['selection_rule'])
                record['bootstrap']=bootstrap_delta(dailies[ref['id']].net,score_daily.net,**c['selection_rule']['bootstrap'])
                record['decision']='継続研究' if record['comparison']['screen_pass'] and record['bootstrap']['low']>0 else ('保留' if record['comparison']['screen_pass'] else '却下')
            signal.to_frame().to_parquet(out/f'predictions/{name}.parquet')
            score_daily.to_csv(out/f'metrics/{name}.csv')
            records.append(record);dailies[name]=score_daily;specs[name]=spec
            dump(out/'trial_registry.json',records)
            m['actual_trials']=len(records);dump(out/'run.json',m)
            emit(f"{name}: NetSR={record['metrics']['net_sharpe']:.4f}, turnover={record['metrics']['turnover']:.4f}"+(f", {record['decision']}, joint={record['comparison']['joint_folds']}/4" if ref else ''))
            return record
        trials=c['trials'];baseline=evaluate(dict(trials[0]))
        raw_a=[evaluate(dict(t),baseline) for t in trials if t['family']=='A']
        selected_raw=ev.choose(raw_a)
        sm=dict(selected_raw['spec']);sm.update(trial_id='A_final_ewma',family='A_smooth',smoothing='final')
        final_a=evaluate(sm,baseline); a=ev.choose(raw_a+[final_a])
        representatives={'A':a};skipped={}
        if a['comparison']['screen_pass']:
            br=[]
            for t in trials:
                if t['family']=='B':
                    spec={**a['spec'],**t};spec.pop('inherits',None);br.append(evaluate(spec,a))
            b=ev.choose(br);representatives['B']=b
            if b['comparison']['screen_pass']:
                cr=[]
                for t in trials:
                    if t['family']=='C':
                        spec={**b['spec'],**t};spec.pop('inherits',None);cr.append(evaluate(spec,b))
                representatives['C']=ev.choose(cr)
            else: skipped['C']='Bが一次基準不通過'
        else: skipped.update(B='Aが一次基準不通過',C='B未実行のため停止')
        event=[evaluate(dict(t),baseline) for t in trials if t['family']=='Event']
        representatives['Event']=ev.choose(event)
        dump(out/'selection_before_confirmation.json',dict(saved_at=now(),representatives={k:r['id'] for k,r in representatives.items()},specs={k:r['spec'] for k,r in representatives.items()},decisions={k:r['decision'] for k,r in representatives.items()},skipped=skipped,actual_trials=len(records),confirmation_seen_this_run=False,confirmation_previously_seen=True,valid_seen=False))
        emit('Selection saved; computing fixed-Long diagnostics and previously seen Train confirmation')
        fixed_summary=[]
        for family,r in representatives.items():
            short=sf.short_score(f,r['spec'])
            fw=ev.fixed_long_weights(base_signal.reindex(dev_index),short.reindex(dev_index))
            fd=ev.side_account(fw,target_dev).loc[dev_dates]
            fd['net']=fd.long_net+fd.short_net
            fd.to_csv(out/f'metrics/fixed_long_{family}.csv')
            for year,z in fd.groupby(fd.index.year):
                fixed_summary.append(dict(family=family,id=r['id'],year=int(year),net_sharpe=ev.sharpe(z.net),annual_short_net=float(z.short_net.mean()*252),annual_long_net=float(z.long_net.mean()*252)))
        pd.DataFrame(fixed_summary).to_csv(out/'fixed_long_summary.csv',index=False)
        full_target=pd.read_parquet(stage/label.name)['Return']
        full_index=f.index[dates>=pd.Timestamp('2011-01-01')].intersection(full_target.index)
        confirmation={}
        for r in [baseline]+list(representatives.values()):
            signal=sf.predict_from_features(f,r['spec'])
            d=ev.account(signal.reindex(full_index),full_target.reindex(full_index),sf.short_score(f,r['spec']),population,base_signal).loc[confirmation_dates]
            confirmation[r['id']]=dict(metrics=ev.extended_metrics(d),years=ev.fold_metrics(d))
            d.to_csv(out/f"metrics/confirmation_{r['id']}.csv")
        dump(out/'confirmation.json',confirmation)
        fold_rows=[];delta_rows=[]
        for r in records:
            fold_rows.extend(dict(trial=r['id'],**v) for v in r['folds'])
            for kind in ['comparison','baseline_comparison']:
                if kind in r:
                    delta_rows.extend(dict(trial=r['id'],comparison=kind,reference=r[kind]['reference'],**v) for v in r[kind]['fold_deltas'])
        pd.DataFrame(fold_rows).to_csv(out/'fold_metrics.csv',index=False)
        pd.DataFrame(delta_rows).to_csv(out/'incremental.csv',index=False)
        write_report(out,c,records,representatives,skipped,confirmation,m)
        firewall.save(out/'audit/firewall.json')
        m.update(status='completed',completed_at_utc=now(),exit_code=0,actual_trials=len(records),elapsed_seconds=time.perf_counter()-t0,max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        dump(out/'run.json',m);emit('Completed Train-only screening; no Valid evaluation and no release freeze')
    except BaseException as error:
        m.update(status='failed',completed_at_utc=now(),exit_code=1,actual_trials=len(records),elapsed_seconds=time.perf_counter()-t0,error=repr(error))
        dump(out/'run.json',m);(out/'logs/error.log').write_text(traceback.format_exc())
        raise


def main():
    def timed_out(signum, frame):
        raise TimeoutError('Terminated by wall-clock supervisor')
    signal.signal(signal.SIGTERM, timed_out)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.config.resolve(),args.output.resolve())


if __name__=='__main__': main()
