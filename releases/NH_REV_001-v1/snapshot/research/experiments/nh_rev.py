"""One fixed NH_REV experiment; Valid entry is gated by an immutable release."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import sys
import time
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import scipy
from scipy.stats import spearmanr
from research import evaluation, firewall
from stock_comp_2026.strategies.dm_nh_rev import features as f


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def clean(x):
    if isinstance(x, dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x, (list, tuple)): return [clean(v) for v in x]
    if isinstance(x, np.generic): return clean(x.item())
    if isinstance(x, float) and not math.isfinite(x): return None
    if isinstance(x, Path): return str(x)
    return x


def dump(path, x):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def evaluation_dates(index, train):
    dates=index.get_level_values('Date').unique().sort_values()
    years=range(2011,2017) if train else sorted(set(dates.year))
    return pd.DatetimeIndex([d for y in years for d in dates[dates.year==y][:-2]])


def event_daily(stages, target, dates):
    v=stages.loc[stages.event & stages.index.get_level_values('Date').isin(dates), ['relative_strength_60','score']].copy()
    v['target']=target.reindex(v.index)
    v=v.replace([np.inf,-np.inf],np.nan).dropna()
    count=v.groupby(level='Date').target.transform('size')
    v=v.loc[count>=5]
    daily=pd.DataFrame({'raw_rankic':evaluation.rankic(v.relative_strength_60,v.target),
                        'score_rankic':evaluation.rankic(v.score,v.target)})
    daily['event_rows']=v.groupby(level='Date').size()
    for col,label in [('relative_strength_60','raw'),('score','score')]:
        ranks=v[col].groupby(level='Date').rank(method='first')
        n=v[col].groupby(level='Date').transform('size')
        q=(np.ceil(5*(ranks-1)/(n-1))-1).clip(0,4)
        distinct=v[col].groupby(level='Date').transform('nunique')>=5
        frame=pd.DataFrame({'q':q,'target':v.target}).loc[distinct]
        qd=frame.reset_index().pivot_table(index='Date',columns='q',values='target',aggfunc='mean').reindex(columns=range(5)).dropna()
        for k in range(5): daily[f'{label}_q{k+1}']=qd[k]
        daily[f'{label}_spread']=qd[4]-qd[0]
    return daily.sort_index(),v


def event_summary(d):
    result={'days':len(d),'ic_days':int(d.raw_rankic.notna().sum()),'event_rows':int(d.event_rows.sum()),'quintile_days':int(d.raw_spread.notna().sum())}
    for prefix,direction in [('raw',-1),('score',1)]:
        ic=d[f'{prefix}_rankic'].dropna(); q=[d[f'{prefix}_q{k}'].mean() for k in range(1,6)]
        result.update({f'{prefix}_rankic':ic.mean(),f'{prefix}_hac_t':evaluation.hac_t(ic),
            f'{prefix}_positive_hit':(ic>0).mean(),f'{prefix}_hypothesis_hit':(direction*ic>0).mean(),
            f'{prefix}_q_monotonicity':spearmanr(range(5),q).statistic if np.isfinite(q).all() else np.nan,
            f'{prefix}_q5_minus_q1':d[f'{prefix}_spread'].mean(),
            **{f'{prefix}_q{k}':q[k-1] for k in range(1,6)}})
    return result


def signal_decision(d, train_summary, split_dates, rules):
    s=event_summary(d); ic=d.raw_rankic.dropna(); spread=d.raw_spread.dropna()
    trimmed_ic=ic.sort_values().iloc[max(1,math.ceil(.01*len(ic))):].mean()
    remove=spread.abs().nlargest(max(1,math.ceil(.01*len(spread)))).index
    trimmed_spread=spread.drop(remove).mean()
    first,last=split_dates.min(),split_dates.max()
    full_years=[y for y in sorted(set(split_dates.year)) if not ((y==first.year and first.month>1) or (y==last.year and last.month<12))]
    annual=[d.loc[d.index.year==y,'raw_rankic'].mean() for y in full_years]
    fraction=float(np.mean(np.array(annual)<0)) if annual else np.nan
    checks={'ic_magnitude':s['raw_rankic']<=rules['raw_rankic_max'],
            'hac_evidence':s['raw_hac_t']<=rules['raw_hac_t_max'],
            'quintile_direction':s['raw_q_monotonicity']<=rules['raw_quintile_monotonicity_max'],
            'spread_direction':s['raw_q5_minus_q1']<0,
            'enough_days':s['ic_days']>=rules['min_ic_days'],
            'annual_stability':fraction>=rules['minimum_negative_full_year_fraction'],
            'ic_not_few_days':trimmed_ic<=-.01,'spread_not_few_days':trimmed_spread<0,
            'train_direction':train_summary['raw_rankic']<0 and train_summary['raw_q5_minus_q1']<0}
    go=all(checks.values())
    return {'hypothesis_id':'NH_REV_001','decision':'GO' if go else 'NO-GO','status':'NEXT_PHASE_ELIGIBLE' if go else 'CLOSED',
        'checks':checks,'failed_criteria':[k for k,v in checks.items() if not v],
        'primary':s,'trimmed_raw_ic':trimmed_ic,'trimmed_raw_spread':trimmed_spread,
        'negative_full_year_fraction':fraction,'full_years':full_years,
        'independent_confirmation':False,'independence_reason':'Supplied Valid previously evaluated and used in prior research ideation.',
        'portfolio_interpretation_permitted':go,'next_phase_executed':False}


def source_scan():
    paths=[Path(f.__file__),Path(f.__file__).with_name('submission.py')]
    for p in paths:
        source=p.read_text(); tree=ast.parse(source)
        for token in ('AdjustmentOpen','AdjustmentHigh','AdjustmentLow','AdjustmentClose','AdjustmentVolume','raw_target','target_1day','box_duration','Ridge','LightGBM'):
            assert token not in source,(p,token)
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                assert node.func.attr not in ('bfill','backfill')
                assert not any(k.arg=='center' and isinstance(k.value,ast.Constant) and k.value.value for k in node.keywords)
                if node.func.attr=='shift':
                    assert node.args and isinstance(node.args[0],ast.Constant) and node.args[0].value>=0
    return {p.name:digest(p) for p in paths}


def mutation_audit(inputs, x, stages, cutoffs):
    results=[]
    # All four input sources are changed together. Prices include future share events.
    for cutoff in cutoffs:
        changed={k:v.copy() for k,v in inputs.items()}
        for name,frame in changed.items():
            mask=frame.index.get_level_values('Date')>pd.Timestamp(cutoff)
            for col in frame.columns:
                if col=='AdjustmentFactor': frame.loc[mask,col]=1.
                elif col=='Return': frame.loc[mask,col]=frame.loc[mask,col]*-7+1.234
                else: frame.loc[mask,col]=frame.loc[mask,col]*3.17+111
            if name=='prices_daily_quotes':
                future=frame.index.get_level_values('Date')[mask]
                if len(future): frame.loc[frame.index.get_level_values('Date')==future.min(),'AdjustmentFactor']=.25
        xx=f.build_features(changed); ss=f.signal_stages(xx)
        prefix=x.index.get_level_values('Date')<=pd.Timestamp(cutoff)
        pd.testing.assert_frame_equal(x.loc[prefix],xx.loc[prefix],check_exact=True)
        pd.testing.assert_frame_equal(stages.loc[prefix],ss.loc[prefix],check_exact=True)
        for col in ['b00_ewma','ewma_score']:
            w=evaluation.weights(stages[col])[0]; ww=evaluation.weights(ss[col])[0]
            pd.testing.assert_series_equal(w.loc[prefix],ww.loc[prefix],check_exact=True)
        results.append({'cutoff':cutoff,'sources':list(changed),'feature_score_weight_bitwise':'PASS','rows':int(prefix.sum())})
    return results


def legs(weights,target):
    out={}
    for label,w in [('long',weights.clip(lower=0)),('short',weights.clip(upper=0))]:
        turn=w.groupby(level='Code').diff().abs().fillna(w.abs())
        gross=w*target; cost=(.001*turn).where(target.notna(),0.)
        out[label+'_gross']=gross.groupby(level='Date').sum()
        out[label+'_net']=(gross-cost).groupby(level='Date').sum()
        out[label+'_cost']=cost.groupby(level='Date').sum()
    return pd.DataFrame(out)


def safe_corr(a,b,method='spearman'):
    z=pd.concat([a,b],axis=1).dropna()
    return z.iloc[:,0].corr(z.iloc[:,1],method=method) if len(z)>1 and z.nunique().min()>1 else np.nan


def write_report(output, cfg, pooled, annual, decision, portfolio, transmission, audit, is_valid):
    split='VALID' if is_valid else 'TRAIN'
    lines=[f'# NH_REV_001 — {split}', '', f'Run: `{output}`', '',
        '## 事実', '',
        'Validは過去に別リリースで評価済み。今回も独立・未使用holdoutではない。Trainは実装・方向・伝達経路の診断に限る。', '',
        'Primaryは元のRS60対targetのdaily Spearman平均。score=-RS60のICは逆符号。HAC lag=5。日別等ウェイト、5行以上、分位集計は5つ以上の異なる値がある日。', '',
        f"raw RS60 IC: **{pooled['raw_rankic']:.6f}**; HAC t: {pooled['raw_hac_t']:.3f}; 負方向Hit: {pooled['raw_hypothesis_hit']:.2%}。",
        f"score IC: **{pooled['score_rankic']:.6f}**; HAC t: {pooled['score_hac_t']:.3f}; 正方向Hit: {pooled['score_hypothesis_hit']:.2%}。",
        f"有効IC日数: {pooled['ic_days']}; event行数: {pooled['event_rows']}。",
        f"raw Q5-Q1: {pooled['raw_q5_minus_q1']:.6%}/日; monotonicity: {pooled['raw_q_monotonicity']:.3f}。",
        f"score Q5-Q1: {pooled['score_q5_minus_q1']:.6%}/日。", '',
        '| Period | raw IC | HAC t | negative hit | raw Q5-Q1/day | score IC |',
        '|---|---:|---:|---:|---:|---:|']
    for r in annual:
        lines.append(f"| {r['period']} | {r['raw_rankic']:.5f} | {r['raw_hac_t']:.2f} | {r['raw_hypothesis_hit']:.1%} | {r['raw_q5_minus_q1']:.5%} | {r['score_rankic']:.5f} |")
    lines+=['','Q1–Q5・日次IC・年別HAC/Hitの全数値は `annual_metrics.csv`, `event_daily.csv`, `event_summary.json`。年別は時系列foldであり学習なし。年末・split末の2 signal日を除外。2016 Train/Validと2026 Validは部分年。','']
    if portfolio:
        p=pd.DataFrame(portfolio); overall=p[p.period=='pooled']; lines+=['### Portfolio (official accounting)','', '| Metric | B00 | NH_REV_001 | Delta |','|---|---:|---:|---:|']
        b=overall[overall.strategy=='B00'].iloc[0]; c=overall[overall.strategy=='NH_REV_001'].iloc[0]
        for k in ['rankic','gross_sharpe','net_sharpe','annual_gross','annual_net','annual_cost','turnover','max_drawdown_compound','annual_long','annual_short']:
            lines.append(f'| {k} | {b[k]:.6f} | {c[k]:.6f} | {c[k]-b[k]:+.6f} |')
        lines+=['',f"平均|weight差|={transmission['mean_absolute_weight_difference']:.8f}; 変更銘柄日={transmission['changed_weight_fraction']:.2%}; event score対最終weight相関={transmission['event_score_final_weight_spearman']:.5f}。"]
    else:
        lines+=['Primary不合格のためValid portfolio集計・SR評価を実施しない。監査用weightsと日次Gross/Net/cost/turnover ledgerは保存し、救済選択には用いない。']
    lines+=['','## 解釈','',
        ('固定した負方向効果は、この既読Valid上の事前数値基準を満たした。ただし独立再現の証拠とは扱わない。' if is_valid and decision['decision']=='GO' else
         '固定した負方向効果は、このValid上の事前基準を満たさない。portfolio調整による救済は行わない。' if is_valid else
         'Train上の方向とパイプラインを確認する記述値。探索済みTrainの好成績から採用可能性を主張しない。'),
        '', '## 未確認事項','', '未使用区間での独立再現性、因果的な経済メカニズム、別の注入方式、Short再設計は未確認。今回のfuture-mutation PASSは試験した入力とcutoffの範囲での証拠。',
        '', '## 判定','',
        (f"**{decision['decision']} / {decision['status']}**。不合格基準: {', '.join(decision['failed_criteria']) or 'なし'}。次Phaseは実行しない。" if is_valid else 'TrainからはGo判定しない。固定仕様・基準をFreezeして一度だけValid評価する。'),
        '', '再現性・監査は `audit.json`, `run.json`。公式costは片道10bp、日次平均×252で年率化。Sharpeは標本標準偏差、DDは累積和・複利の両方。公式の欠損target行cost除外と全保有costを別保存。raw/score分位は同点のCode順配分により完全反転しない場合がある。']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n')


def run(args):
    start=time.monotonic(); output=Path(args.output).resolve(); cfg=json.loads(Path(args.config).read_text())
    root=Path(args.root).resolve(); data=root/'stock_comp_2026/input'
    assert cfg['hypothesis_id']=='NH_REV_001' and cfg['max_trials']==1
    assert cfg['parameters']['ewma_alpha']==.25 and cfg['parameters']['score_sign']==-1
    is_valid=args.valid
    output.mkdir(parents=True,exist_ok=True)
    meta_path=output/'run.json'
    if is_valid:
        assert not meta_path.exists(),'Valid evaluation already reserved; no reruns'
        release=Path(args.freeze).resolve(); manifest=json.loads((release/'manifest.json').read_text())
        assert digest(release/'manifest.json')==(release/'manifest.sha256').read_text().strip()
        for p,h in manifest['sha256'].items(): assert digest(release/p)==h,p
        assert (release/'TRAIN_FREEZE_VERIFICATION.json').exists()
        verification=json.loads((release/'TRAIN_FREEZE_VERIFICATION.json').read_text())
        assert verification['pass'] is True
        assert Path(__file__).resolve().is_relative_to(release/'snapshot')
        assert digest(args.config)==manifest['sha256']['snapshot/config.json']
        train_summary=json.loads((release/'snapshot/train_event_summary.json').read_text())
        meta={'status':'running','split':'valid','freeze_manifest_sha256':digest(release/'manifest.json')}
    else:
        meta=json.loads(meta_path.read_text()); assert meta['status']=='prepared'
        for p,h in meta['snapshot_sha256'].items(): assert digest(output/p)==h
        train_summary=None
    meta.update(started_at_utc=now(),command=sys.argv,actual_trials=1,environment={'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__,'platform':platform.platform()})
    dump(meta_path,meta)
    try:
        stage=output/'input_stage'; stage.mkdir()
        opened=[]; original_read=pd.read_parquet
        names=list(f.INPUT_COLUMNS)
        splits=['train','valid'] if is_valid else ['train']
        for split in splits:
            for name in names:
                (stage/f'{name}_{split}.parquet').symlink_to(data/f'{name}_{split}.parquet')
        if not is_valid:
            (stage/'target_1day_train.parquet').symlink_to(data/'target_1day_train.parquet')
            prior=root/'artifacts/DM-20260924-11/run-20260924T091842Z/predictions/signal_stages.parquet'
            # Discover the completed prior run from metadata; never load its target.
            candidates=sorted((root/'artifacts/DM-20260924-11').glob('*/predictions/signal_stages.parquet'))
            prior=candidates[-1] if candidates else None
            allow=[prior] if prior else []
            firewall.install(allowed_artifacts=allow)
        else:
            allowed={str((stage/f'{name}_{split}.parquet').resolve()) for split in splits for name in names}
            def guarded(path,*a,**kw):
                resolved=str(Path(path).resolve()); assert resolved in allowed,f'Not authorized input: {path}'
                opened.append(resolved); return original_read(path,*a,**kw)
            pd.read_parquet=guarded
        inputs=f.load_inputs(stage,'train'); train_index=inputs['raw_return_1day'].index
        if is_valid:
            later=f.load_inputs(stage,'valid'); out_index=later['raw_return_1day'].index
            inputs={k:pd.concat([inputs[k],later[k]]).sort_index() for k in inputs}
            assert all(v.index.is_unique for v in inputs.values())
        else: out_index=train_index
        source_hashes=source_scan()
        x=f.build_features(inputs); stages=f.signal_stages(x)
        assert x.index.equals(inputs['raw_return_1day'].index)
        audit={'source_scan':source_hashes,'coverage':len(stages.reindex(out_index)), 'nonfinite_predictions':int((~np.isfinite(stages.ewma_score)).sum()),'feature_sources':list(inputs)}
        print('predictions complete',len(stages),flush=True)
        if not is_valid:
            pd.testing.assert_frame_equal(stages,f.signal_stages(f.build_features(inputs)),check_exact=True)
            audit['determinism']='bitwise PASS'
            audit['future_mutation']=mutation_audit(inputs,x,stages,['2009-03-31','2012-12-28','2015-12-30'])
            if prior:
                old=pd.read_parquet(prior)
                # Exact previous B00 + alpha .25 score and unchanged RS60.
                bcol='BLEND_0_A025_ewma'
                pd.testing.assert_series_equal(stages.b00_ewma.reindex(old.index),old[bcol],check_names=False,check_exact=True)
                if 'relative_strength_60' in old:
                    pd.testing.assert_series_equal(stages.relative_strength_60.reindex(old.index),old.relative_strength_60,check_names=False,check_exact=True)
                audit['b00_prior_bitwise']='PASS'; audit['prior_artifact']=str(prior)
        else:
            # Labels remain unopened; verify a real later-period mutation cutoff as well.
            audit['future_mutation']=mutation_audit(inputs,x,stages,['2020-12-30'])
        scores=stages[['b00_ewma','ewma_score']].reindex(out_index).rename(columns={'b00_ewma':'B00','ewma_score':'NH_REV_001'})
        weights=pd.DataFrame({c:evaluation.weights(scores[c])[0] for c in scores})
        dates=evaluation_dates(out_index,not is_valid); selected=out_index.get_level_values('Date').isin(dates)
        saved=stages.reindex(out_index).copy(); saved['evaluated']=selected
        saved['final_weight']=weights.NH_REV_001; saved['b00_weight']=weights.B00
        saved.to_parquet(output/'signal_stages.parquet')
        scores.to_parquet(output/'predictions.parquet'); weights.to_parquet(output/'portfolio_weights.parquet')
        saved.loc[saved.event,['relative_strength_60','score','evaluated']].to_parquet(output/'event_predictions.parquet')
        saved.loc[saved.event,['event_rank','combined_score','ewma_score','final_weight','evaluated']].to_parquet(output/'event_ranks.parquet')
        dump(output/'prediction_seal.json',{'created_before_target_read':now(),'sha256':{p.name:digest(p) for p in output.glob('*.parquet')}})
        # Target access is permitted only after features/predictions and their seal exist.
        split='valid' if is_valid else 'train'
        target_path=data/f'target_1day_{split}.parquet'
        if is_valid:
            allowed.add(str(target_path.resolve()))
            target=pd.read_parquet(target_path)['Return'].sort_index()
        else: target=pd.read_parquet(stage/target_path.name)['Return'].sort_index()
        assert target.index.equals(out_index)
        daily,events=event_daily(saved,target,dates); pooled=event_summary(daily)
        annual=[{'period':str(y),**event_summary(daily.loc[daily.index.year==y])} for y in sorted(set(dates.year))]
        events.to_parquet(output/'event_labeled.parquet'); daily.to_csv(output/'event_daily.csv',index_label='Date')
        pd.DataFrame([{'period':'pooled',**pooled}]+annual).to_csv(output/'annual_metrics.csv',index=False)
        dump(output/'event_summary.json',pooled)
        decision=signal_decision(daily,train_summary,out_index.get_level_values('Date').unique(),cfg['selection_rule']) if is_valid else {'decision':'TRAIN_DIAGNOSTIC_ONLY','independent_confirmation':False}
        dump(output/'decision_result.json',decision)
        print('event primary',clean(decision if is_valid else pooled),flush=True)
        # Mechanical ledgers always saved. Portfolio summary/interpretation is primary-gated.
        accounts={}; legframes={}
        from stock_comp_2026 import evaluate_script as official
        for c in scores:
            account=evaluation.daily_account(scores[c],target); account['evaluated']=account.index.isin(dates)
            account.to_csv(output/f'daily_account_{c}.csv',index_label='Date'); accounts[c]=account
            legframes[c]=legs(weights[c],target)
            np.testing.assert_allclose(legframes[c].long_net+legframes[c].short_net,account.net,rtol=0,atol=1e-12)
            if not is_valid:
                official_w=official.compute_weight(scores[[c]]).iloc[:,0]
                pd.testing.assert_series_equal(official_w,weights[c],check_names=False,check_exact=True)
                official_net=official.compute_pl(scores[[c]],target.to_frame()).groupby(level='Date').sum()
                np.testing.assert_allclose(official_net,account.net,rtol=0,atol=1e-14)
        audit['accounting']='PASS'; audit['official_parity']='PASS' if not is_valid else 'frozen Train-verified accounting'
        pd.concat({k:v[['gross','net','evaluated']] for k,v in accounts.items()},axis=1).to_csv(output/'daily_pnl.csv')
        pd.concat({k:v[['cost','cost_all','evaluated']] for k,v in accounts.items()},axis=1).to_csv(output/'daily_cost.csv')
        pd.concat({k:v[['turnover','evaluated']] for k,v in accounts.items()},axis=1).to_csv(output/'daily_turnover.csv')
        portfolio=[]; transmission={}
        if not is_valid or decision['portfolio_interpretation_permitted']:
            for c in scores:
                legframes[c].to_csv(output/f'daily_legs_{c}.csv')
                for label,ds in [('pooled',dates)]+[(str(y),dates[dates.year==y]) for y in sorted(set(dates.year))]:
                    metric=evaluation.metrics(accounts[c].reindex(ds)); leg=legframes[c].reindex(ds)
                    metric.update({f'annual_{k}':float(leg[k].mean()*252) for k in leg})
                    portfolio.append({'strategy':c,'period':label,**metric})
            pp=pd.DataFrame(portfolio); pp.to_csv(output/'portfolio_metrics.csv',index=False)
            delta=pp[pp.strategy=='NH_REV_001'].set_index('period').drop(columns='strategy')-pp[pp.strategy=='B00'].set_index('period').drop(columns='strategy')
            delta.to_csv(output/'portfolio_deltas.csv')
            dw=(weights.NH_REV_001-weights.B00).loc[selected]; active=saved.event & saved.evaluated
            transmission={'mean_absolute_weight_difference':dw.abs().mean(),'changed_weight_fraction':dw.ne(0).mean(),
                'event_score_final_weight_spearman':safe_corr(saved.score.loc[active],saved.final_weight.loc[active]),
                'event_daily_score_weight_mean_rankic':evaluation.rankic(saved.score.loc[active],saved.final_weight.loc[active]).mean(),
                'short_mean_absolute_weight_difference':(weights.NH_REV_001.clip(upper=0)-weights.B00.clip(upper=0)).loc[selected].abs().mean(),
                'stage_daily_rankic':{col:evaluation.rankic(saved[col].loc[active],target.loc[active]).mean() for col in ['relative_strength_60','score','event_rank','combined_score','ewma_score','final_weight']}}
            dump(output/'signal_transmission.json',transmission)
        if not is_valid:
            firewall.save(output/'firewall.json'); audit['train_only_stage']='PASS'; audit['firewall']='PASS'
        else:
            dump(output/'access_log.json',{'opened_parquets':opened,'target_opened_after_predictions':True,'independent_valid':False})
        dump(output/'audit.json',audit)
        write_report(output,cfg,pooled,annual,decision,portfolio,transmission,audit,is_valid)
        meta.update(status='completed',completed_at_utc=now(),exit_code=0,elapsed_seconds=time.monotonic()-start,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            input_sha256={f'{name}_{split}.parquet':digest(data/f'{name}_{split}.parquet') for split in splits for name in names},target_sha256=digest(target_path),code_sha256={str(p):digest(p) for p in [Path(__file__),Path(f.__file__),Path(evaluation.__file__)]})
        dump(meta_path,meta); print('completed',meta['elapsed_seconds'],flush=True)
    except BaseException as exc:
        meta.update(status='failed',error=repr(exc),completed_at_utc=now(),exit_code=1)
        dump(meta_path,meta); raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True);p.add_argument('--root',default='.');p.add_argument('--valid',action='store_true');p.add_argument('--freeze')
    run(p.parse_args())
