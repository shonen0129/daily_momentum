"""Finite Train-only cause-decomposition experiment; never searches after results."""
import argparse
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
import pyarrow
import pyarrow.parquet as pq
import scipy
from research import evaluation, firewall
from research.experiments.sector_momentum import sha, dump, safe, exact, account, metrics, fold_dates, table
from research.experiments.hierarchical_momentum import scopes
from stock_comp_2026.strategies.dm_decline_causes import features as fc, submission
from stock_comp_2026.strategies.dm_trainonly import features as old


def source_scan():
    paths = sorted((ROOT/'stock_comp_2026/strategies/dm_decline_causes').glob('*.py'))
    findings=[]
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node,ast.Constant) and isinstance(node.value,str):
                if any(t in node.value for t in ['AdjustmentOpen','AdjustmentHigh','AdjustmentLow','AdjustmentClose',
                    'AdjustmentVolume','raw_target','target_1day','_valid.parquet','Sector17','ForecastOrdinaryProfit','ForecastProfit','ForecastEarningsPerShare']):
                    findings.append([str(path),node.lineno,'forbidden input'])
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                bad=node.func.attr in ['bfill','backfill']
                if node.func.attr=='shift':
                    n=node.args[0] if node.args else next((k.value for k in node.keywords if k.arg=='periods'),None)
                    bad |= not isinstance(n,ast.Constant) or not isinstance(n.value,int) or n.value<0
                for kw in node.keywords:
                    bad |= kw.arg=='center' and not (isinstance(kw.value,ast.Constant) and kw.value.value is False)
                    bad |= kw.arg=='direction' and not (isinstance(kw.value,ast.Constant) and kw.value.value=='backward')
                if bad: findings.append([str(path),node.lineno,'forbidden time operation'])
    assert not findings,findings
    return {'status':'PASS','sources':[str(p.relative_to(ROOT)) for p in paths],'findings':findings,
        'manual_review':'No label fit. Fiscal/basis-key previous forecast; disclosure EOD backward asof <=prior session EOD. Raw20 volume excludes current. Exact historical PIT33 self-inclusive daily residual. Only same-date median/rank.'}


def mutate(frame,name,cutoff,seed):
    out=frame.copy()
    dates=out.index.get_level_values('Date')
    mask=dates>cutoff
    rng=np.random.default_rng(seed)
    for col in out:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out.loc[mask,col]=out.loc[mask,col]+pd.Timedelta(days=366)
        elif pd.api.types.is_numeric_dtype(out[col]):
            values=rng.normal(0,1e9,int(mask.sum()));values[::7]=np.nan;values[1::11]=0.
            out[col]=out[col].astype(float);out.loc[mask,col]=values
        else:
            out[col]=out[col].astype('string')
            out.loc[mask,col]='1QFinancialStatements_Consolidated_IFRS' if col=='TypeOfDocument' else '7777'
    future_index=out.index[mask]
    out=out.drop(future_index[::17])
    # Move suffix availability dates strictly within future, preserving unique keys.
    d=out.index.get_level_values('Date')
    moved=d+pd.to_timedelta((d>cutoff).astype(int)*3,unit='D')
    if name=='topix_return_1day':
        out.index=pd.DatetimeIndex(moved,name='Date')
    else:
        out.index=pd.MultiIndex.from_arrays([moved,out.index.get_level_values('Code')],names=['Date','Code'])
        extra=out.iloc[-1:].copy()
        extra.index=pd.MultiIndex.from_tuples([(d.max()+pd.Timedelta(days=10),'99999')],names=out.index.names)
        out=pd.concat([out,extra])
    return out


def prefix_audit(inputs,f,config):
    cases=[]
    for i,text in enumerate(config['prefix_cutoffs']):
        cutoff=pd.Timestamp(text)
        index=f.index[f.index.get_level_values('Date')<=cutoff]
        for source in list(inputs)+['ALL','TRUNCATION']:
            changed={}
            for j,(key,frame) in enumerate(inputs.items()):
                changed[key]=(frame.loc[frame.index.get_level_values('Date')<=cutoff] if source=='TRUNCATION'
                    else mutate(frame,key,cutoff,config['random_seed']+i*100+j) if source in [key,'ALL'] else frame)
            got=fc.build_features(changed)
            exact(f.loc[index],got.loc[index])
            cases.append({'cutoff':text,'source':source,'status':'PASS','prefix_rows':len(index),'columns':len(f.columns),'bitwise':True})
        print(f'All-source prefix mutation/truncation {text}: PASS',flush=True)
    exact(f,fc.build_features(inputs))
    shuffled={n:v.sample(frac=1,random_state=config['random_seed']) for n,v in inputs.items()}
    exact(f,fc.build_features(shuffled))
    return {'status':'PASS','cases':cases,'deterministic_rebuild_bitwise':True,'row_shuffle_bitwise':True,
        'method':'Float64 uint64 bits including NaNs; exact strings/datetimes/index/dtypes; each-source and joint extremes/NaN/zero, suffix deletion/date shifts, fiscal/basis/PIT changes, future-only stocks, separate truncation. All feature intermediates and all3 scores. No fit.'}


def contract_audit(inputs,f):
    idx=fc.canonical(inputs['raw_return_1day']).index
    assert f.index.equals(idx)
    assert np.isfinite(f[list(fc.CANDIDATES)+['MOM60']].to_numpy()).all()
    observed=f.FundDisclosure.notna()
    assert (f.loc[observed,'FundDisclosure']<=f.loc[observed,'Tau']+pd.Timedelta('23:59:59')).all()
    e=fc.financial_events(inputs['fins_statements'])
    valid=e.ForecastPrevious.notna()
    assert e.loc[valid,fc.FISCAL+['Basis']].notna().all().all()
    good=e.FUND_REV_raw.notna()
    assert (e.loc[good,'PITAssets']>0).all()
    exact(f.MOM60.rename('Return'),old.smooth(old.build_momentum(inputs),.25).rename('Return'))
    return {'status':'PASS','rows':len(idx),'all_prediction_finite':True,'exact_index':True,
        'financial_not_before_disclosure':True,'comparable_events':int(valid.sum()),'scaled_events':int(good.sum()),
        'same_fiscal_basis':True,'MOM60_primitive_bitwise':True,'tau_common_previous_exchange_session':True}


def coverage(f,dates,folder):
    masks={n:f[n].notna() for n in fc.RAW_COMPONENTS}
    masks.update(ALL3_RAW=f[list(fc.RAW_COMPONENTS)].notna().all(axis=1),StockResidualReturn=f.StockResidualReturn.notna(),
        AbnormalVolume=f.AbnormalVolume.notna(),Volume=f.Volume.notna(),MOM60=f.StockMom60_raw.notna())
    rows=[]
    for scope,ds in [('ALL_TRAIN',f.index.get_level_values('Date').unique())]+scopes(dates):
        use=f.index.get_level_values('Date').isin(ds)
        for name,mask in masks.items():
            rows.append({'scope':scope,'component':name,'rows':int(use.sum()),'finite':int((mask&use).sum()),'coverage':float(mask.loc[use].mean())})
    pd.DataFrame(rows).to_csv(folder/'raw_coverage.csv',index=False)
    tie=[]
    for day,g in f.groupby('Date',sort=True):
        for n in list(fc.RAW_COMPONENTS)+list(fc.CANDIDATES):
            x=g[n];v=x.value_counts(dropna=False)
            tie.append({'Date':day,'component':n,'n':len(x),'raw_missing':int(x.isna().sum()),
                'all_missing':bool(x.isna().all()),'zero_count':int(x.eq(0).sum()),'distinct':int(x.nunique()),
                'largest_tie_count':int(v.max()),'largest_tie_fraction':float(v.max()/len(x))})
    pd.DataFrame(tie).to_csv(folder/'ties_daily.csv',index=False)


def standalone_smoke(stage,output,signal):
    directory=output/'adapter_smoke';directory.mkdir()
    (directory/'input').symlink_to(stage,target_is_directory=True)
    pred=output/'predictions/standalone.parquet'
    result=output/'audit/standalone_smoke.json'
    script='\n'.join(['import sys,os,json,time,resource',f'sys.path.insert(0,{str(ROOT)!r})',
        'from research import firewall; firewall.install()',
        f'sys.path.insert(0,{str(ROOT/"stock_comp_2026/strategies/dm_decline_causes")!r})','import submission',
        f'os.chdir({str(stage)!r})','t=time.monotonic();p=submission.predict()',f'p.to_parquet({str(pred)!r})',
        "r={'status':'PASS','rows':len(p),'elapsed_seconds':time.monotonic()-t,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),'opened':sorted(firewall.ACCESSES)}",
        f'open({str(result)!r},"w").write(json.dumps(r,indent=2)+"\\n")'])
    (directory/'script.py').write_text(script+'\n')
    r=subprocess.run([sys.executable,str(directory/'script.py')],capture_output=True,text=True,timeout=180)
    (output/'logs/standalone.log').write_text(r.stdout+r.stderr)
    assert r.returncode==0,r.stderr
    exact(signal.to_frame(),pd.read_parquet(pred))
    record=json.loads(result.read_text());record['bitwise_research_parity']=True;dump(result,record)


def state_columns(f):
    out=pd.DataFrame(index=f.index)
    out['fundamental']=np.select([f.FUND_REV_raw.isna(),f.FUND_REV_raw<0],['MISSING','DOWN_REVISION'],default='NO_DOWN_REVISION')
    for name,col in [('sector','SECTOR33_SHOCK_raw'),('within','WithinShock')]:
        v=f[col];out[name]=np.select([v.isna(),v<0,v>0],['MISSING','DOWN' if name=='sector' else 'NEGATIVE','UP' if name=='sector' else 'POSITIVE'],default='ZERO')
    v=f.AbnormalVolume
    out['volume']=np.select([v.isna(),v>0],['MISSING','HIGH'],default='NORMAL')
    out['move']=np.select([f.StockRawReturn.isna(),f.StockRawReturn<0,f.StockRawReturn>0],['MISSING','NEGATIVE','POSITIVE'],default='ZERO')
    out['revision_event']=np.select([f.FUND_REV_raw.isna(),f.FundDisclosure.dt.normalize().eq(f.Tau)],['MISSING','NEW_DISCLOSURE'],default='HELD')
    return out


def diagnostic_row(signal,target,holding,mask,days):
    s=signal.loc[mask];y=target.loc[mask];h=holding.loc[mask]
    ic=evaluation.rankic(s,y)
    long=float(h.gross.where(h.w>0,0).sum())
    short=float(h.gross.where(h.w<0,0).sum())
    lc=float(h.long_cost.sum());sc=float(h.short_cost.sum())
    return {'count':len(y),'target_count':int(y.notna().sum()),'next_target_mean':float(y.mean()),
        'mean_daily_target':float(y.groupby('Date').mean().mean()),'rankic':float(ic.mean()),
        'rankic_t_hac5':evaluation.hac_t(ic),'rankic_days':int(ic.notna().sum()),
        'long_gross':long,'short_gross':short,'long_cost':lc,'short_cost':sc,
        'long_net':long-lc,'short_net':short-sc,
        'annual_long_gross_contribution':long/days*252,'annual_short_gross_contribution':short/days*252,
        'annual_long_net_contribution':(long-lc)/days*252,'annual_short_net_contribution':(short-sc)/days*252}


def diagnostics(f,target,signals,holdings,dates,folder):
    evaluation_index=f.index[f.index.get_level_values('Date').isin(dates)]
    f=f.loc[evaluation_index];target=target.loc[evaluation_index]
    states=state_columns(f)
    joint=[];marginal=[];raw=[];imputed=[];reconc=[]
    # Joint state contributions partition every book, including current flat rows with exit costs.
    for scope,ds in scopes(dates):
        use=f.index.get_level_values('Date').isin(ds)
        fs=f.loc[use];ts=target.loc[use];st=states.loc[use]
        for subset,subset_mask in [('ALL',pd.Series(True,index=fs.index)),('NEGATIVE_STOCK_MOVE',fs.StockRawReturn<0),('NEGATIVE_RESIDUAL',fs.StockResidualReturn<0)]:
            gs=st.loc[subset_mask]
            groups=gs.groupby(['fundamental','sector','volume','within'],sort=True).groups
            for name in fc.CANDIDATES+('MOM60',):
                local_signal=signals[name].loc[fs.index];h=holdings[name].loc[fs.index]
                book_rows=[]
                for key,ix in groups.items():
                    mask=pd.Series(fs.index.isin(ix),index=fs.index)
                    row={'strategy':name,'scope':scope,'subset':subset,**dict(zip(['fundamental','sector','volume','within'],key)),
                         **diagnostic_row(local_signal,ts,h,mask,len(ds))}
                    joint.append(row);book_rows.append(row)
                for side in ['long','short']:
                    expected=float(h.gross.where(h.w>0 if side=='long' else h.w<0,0).loc[subset_mask].sum())
                    got=sum(x[side+'_gross'] for x in book_rows)
                    assert abs(got-expected)<1e-12
                    net=expected-float(h.loc[subset_mask,side+'_cost'].sum())
                    assert abs(sum(x[side+'_net'] for x in book_rows)-net)<1e-12
                assert sum(x['count'] for x in book_rows)==int(subset_mask.sum())
                reconc.append({'strategy':name,'scope':scope,'subset':subset,'status':'PASS','atol':1e-12})
                for factor in ['fundamental','sector','volume','within','revision_event']:
                    for state,ix in gs.groupby(factor,sort=True).groups.items():
                        mask=pd.Series(fs.index.isin(ix),index=fs.index)
                        marginal.append({'strategy':name,'scope':scope,'subset':subset,'factor':factor,'state':state,
                            **diagnostic_row(local_signal,ts,h,mask,len(ds))})
        for name in fc.RAW_COMPONENTS:
            for subset,mask in [('ALL',pd.Series(True,index=fs.index)),('NEGATIVE_STOCK_MOVE',fs.StockRawReturn<0),('NEGATIVE_RESIDUAL',fs.StockResidualReturn<0)]:
                for state,sign in [('ALL',pd.Series(True,index=fs.index)),('NEGATIVE',fs[name]<0),('POSITIVE',fs[name]>0),('ZERO',fs[name]==0),('MISSING',fs[name].isna())]:
                    mask2=mask&sign;y=ts.loc[mask2];ic=evaluation.rankic(fs.loc[mask2,name],y)
                    raw.append({'scope':scope,'component':name,'subset':subset,'sign':state,'count':len(y),'target_count':int(y.notna().sum()),
                        'next_target_mean':float(y.mean()),'rankic':float(ic.mean()),'rankic_t_hac5':evaluation.hac_t(ic),'rankic_days':int(ic.notna().sum())})
        for name in fc.CANDIDATES:
            invalid=fs.FUND_REV_raw.isna() if name=='FUND_REV' else fs.FLOW_REV_raw.isna() if name=='FLOW_REV' else fs[list(fc.RAW_COMPONENTS)].isna().any(axis=1)
            h=holdings[name].loc[fs.index]
            for label,mask in [('COMPLETE_RAW',~invalid),('IMPUTED_RAW',invalid)]:
                imputed.append({'strategy':name,'scope':scope,'state':label,**diagnostic_row(signals[name].loc[fs.index],ts,h,mask,len(ds))})
    pd.DataFrame(joint).to_csv(folder/'mechanism_joint_states.csv',index=False)
    pd.DataFrame(marginal).to_csv(folder/'mechanism_marginal_states.csv',index=False)
    pd.DataFrame(raw).to_csv(folder/'raw_component_diagnostics.csv',index=False)
    pd.DataFrame(imputed).to_csv(folder/'imputed_attribution.csv',index=False)
    states.to_parquet(folder.parent/'predictions/mechanism_states.parquet')
    return {'status':'PASS','cases':reconc,'all_joint_books_reconcile':True,'negative_subsets_reconcile':True,'tolerance':1e-12,
        'meaning':'Fixed signed residual P/L attribution, not standalone state portfolios. Empty/undefined IC is NaN, not0. No diagnostic-derived filter.'}


def decide(results,boot):
    result={}
    def get(n,scope):return results.loc[(results.strategy==n)&(results.scope==scope)].iloc[0]
    b=get('MOM60','POOLED');be=get('MOM60','EX2016')
    for n in fc.CANDIDATES:
        m=get(n,'POOLED');ex=get(n,'EX2016')
        improves=sum(get(n,str(y)).net_sharpe>get('MOM60',str(y)).net_sharpe for y in range(2011,2016))
        checks={'pooled_net_sharpe':m.net_sharpe>b.net_sharpe,'ex2016_net_sharpe':ex.net_sharpe>be.net_sharpe,
            'full_year_improvements_4_of_5':improves>=4,'bootstrap_lower_gt0':boot['POOLED:'+n+'-MOM60']['low']>0,
            'annual_net':m.annual_net>b.annual_net,'turnover_le_1_25x':m.turnover<=b.turnover*1.25,
            'short_gross':m.annual_short_gross>=b.annual_short_gross,'short_net':m.annual_short_net>=b.annual_short_net,
            'long_net_positive':m.annual_long_net>0}
        result[n]={'decision':'TRAIN_ONLY_NEXT_STAGE_ELIGIBLE' if all(checks.values()) else 'REJECT',
            'checks':checks,'failed_checks':[k for k,v in checks.items() if not v],'full_year_improvements':improves}
    return result


def write_report(config,output,results,boot,decision):
    report=ROOT/config['report_dir'];report.mkdir(parents=True,exist_ok=False)
    for name in ['metrics','audit']:shutil.copytree(output/name,report/name)
    pooled=results.loc[results.scope=='POOLED']
    cols=['strategy','rankic','rankic_t_hac5','gross_sharpe','net_sharpe','annual_gross','annual_net','turnover','annual_cost','annual_long_net','annual_short_gross','annual_short_net']
    joint=pd.read_csv(output/'metrics/raw_component_diagnostics.csv')
    mechanism=joint.loc[(joint.scope=='POOLED')&(joint.subset=='NEGATIVE_STOCK_MOVE')&joint.sign.isin(['NEGATIVE','POSITIVE'])]
    lines=[f'# {config["experiment_id"]} — 株価下落の原因分解','',
        '固定3候補の採否: '+', '.join(n+'='+d['decision'] for n,d in decision.items())+'.',
        '2026-10-03 JST。全結果は既知Trainでの仮説検証。Historical Valid/Valid、符号反転、追加filter、救済候補、Freeze、外部提出は実施していない。',
        f'Run: `{output.relative_to(ROOT)}`。', '', '## Pooled comparison','',table(pooled,cols),'',
        'P/Lはdecimal fraction。年率=日次平均×252、Sharpe=sample SDで年率化、IC tはNewey–West/Bartlett HAC5。Q1=低score、Q5=高score。Long/Shortは符号付き市場残差寄与。SLOW_CONTROLは保存済みの記述参照のみで採用条件に不使用。',
        '', '## Full years and 2016 partial','',table(results.loc[results.scope.isin([str(y) for y in range(2011,2017)])],['strategy','scope','net_sharpe','annual_net','turnover','annual_long_net','annual_short_gross','annual_short_net']),
        '', '## Bootstrap and gates','',table(pd.DataFrame([{'contrast':k,**v} for k,v in boot.items()]),['contrast','point_delta','low','high']),
        '', 'Paired circular20-session/2000回/seed20261003/percentile95%。C−MOM60 pooledがprimary、A/Bはsecondary。EX2016も別保存。連結した適格営業日を再標本化し、年境界purgeのgapは連結する。既知Trainの標本不確実性であり、独立OOSや多重探索補正ではない。',
        '', *[f'- {n}: full-year改善{d["full_year_improvements"]}/5。不通過: '+(', '.join(d['failed_checks']) or 'none')+'.' for n,d in decision.items()],
        '', '## Mechanism: negative raw stock move','',table(mechanism,['component','sign','count','target_count','next_target_mean','rankic','rankic_t_hac5']),
        '', 'この表は各raw componentの状態別の関連。日次ICは状態内で定義できた日のみ。単なるtarget平均の符号だけでContinuation/Reversalの識別や経済原因の因果性を確定しない。joint/marginal全状態とLong/Short寄与はCSVに保存。ゼロと欠測を独立状態に保持し、診断を候補に変換していない。Sectorのみの追加performance trialは行っていない。',
        '', '## Definitions and limits','',
        'τは共通の直前営業日。株returnは配布open-to-open過去returnの市場残差でありclose-to-close下落ではない。Volumeはτの通日raw出来高で、return区間の終点openより後の取引を含む。したがってmechanismは価格下落の厳密な会計分解や観測された売買主体の識別ではなく、固定proxyの検証。翌寄付までの遅れ込みで評価した。',
        'FUNDは総額ForecastOperatingProfitのみ。同一fiscal start/end/過去のaccounting basisで比較し、開示時点のAssetsでscale。次開示まで状態を保持し、pair/scale不足やforecast欠測の開示でmissingへ更新。初回period forecastはmissing。NextYear予想は使わない。財務Dateにintraday clockが無いため当日23:59:59 JST availabilityで翌sessionから使用。各日時点の提供financial vintageが正しいというデータ契約に依存する。',
        'Sector33はhistorical-date exact PIT/self-inclusive finite mean、min1。小sectorも許容する固定仕様で、membership変更後を過去へ遡及しない。AbnormalVolumeはlog1p当日から直前20観測中央値を引き、max(surprise,0)を掛けてWithinの符号を反転。No smoothing。raw Volumeのsplit/取引単位変化を因果的に補正する情報は利用していない。',
        '欠測componentは同日medianで補完、Code順ordinal centered rank。これは経済情報ではなくcoverage契約。同値の予想据置・非高出来高Flow=0もCode順に分散し、合成にCode orderingが入り得る。raw coverage/大tie/補完行の損益は別保存。この実装上の分散を新alphaや原因識別の証拠と呼ばない。結果後のmissing/rank再設計はしていない。',
        '', '## Audit and artifacts','',
        '全中間特徴量/3scoresの全入力源future mutation・joint mutation・truncationを3cutoffでbitwise照合。suffix値/NaN/zero、日付/fiscal/basis/sector変更、行削除、future-only stocksを含む。row shuffle、deterministic rebuild、exact index、finite coverage、explicit disclosure-before/after/fiscal/basis fixtures、PIT33 switch、Volume history、research/adapter/standalone一致を検証。audit/*とtestログを参照。動的検査は試したcutoff/inputでの証拠。',
        '公式5分位weightと全Train日次Net P/Lはbitwise一致。Long+Short cost/netは1e−15以内で照合。joint状態寄与は全bookとnegative subsetを1e−12以内で照合。公式はmissing target行のcostを落とすためall-position conservative Net/Costも保存。毎年末2sessionをpurgeしてt+2終点をfold内へ固定。保持/costは完全Train系列上で算出してから評価日を選ぶ。',
        '`metrics/metrics.csv`全指標、`fold_metrics.csv`/`year_metrics.csv`、`incremental.csv`、`long_short.csv`、`quintiles.csv`、`bootstrap.csv`、`raw_coverage.csv`、`ties_daily.csv`、`raw_component_diagnostics.csv`、`mechanism_joint_states.csv`、`mechanism_marginal_states.csv`、`imputed_attribution.csv`、`daily_*.csv`。runにplan/config/code/data/environment hashesと予測、状態panelを保存。']
    (report/'REPORT.md').write_text('\n'.join(lines)+'\n')
    exp=ROOT/'experiments'/config['experiment_id']
    (exp/'decision.md').write_text('# '+config['experiment_id']+' decision\n\nExactly3/3 fixed performance trials, Train-only.\n\n'+'\n'.join('- **'+n+'** — '+d['decision']+'. Failed: '+(', '.join(d['failed_checks']) or 'none')+'.' for n,d in decision.items())+f'\n\n[Report](../../{config["report_dir"]}/REPORT.md). [Gates](../../{config["report_dir"]}/metrics/candidate_decision.json).\n\nNo rescue/window/sector/revision/sign/weight changes. Eligibility is next-stage research only; no Valid or release.\n')
    meta=json.loads((exp/'experiment.json').read_text());meta.update(status='rejected' if all(d['decision']=='REJECT' for d in decision.values()) else 'completed',actual_trials=3,run_id=output.name,report=config['report_dir']+'/REPORT.md')
    dump(exp/'experiment.json',meta)
    rejected=[n for n,d in decision.items() if d['decision']=='REJECT']
    if rejected:
        with (ROOT/'experiments/GRAVEYARD.md').open('a') as stream:
            stream.write(f'\n## {config["experiment_id"]}: 株価下落の原因分解\n\n[Decision]({config["experiment_id"]}/decision.md) / [Report](../{config["report_dir"]}/REPORT.md). Fixed3 trials; Train-only/no Valid/no rescue.\n\n')
            for n in rejected:stream.write('- **'+n+'** — REJECT; failed: '+', '.join(decision[n]['failed_checks'])+'.\n')


def main_work(config,output,run):
    start=time.monotonic();exp=ROOT/'experiments'/config['experiment_id']
    prereg=json.loads((exp/'preregistration.json').read_text())
    assert sha(output/'plan.md')==prereg['plan_sha256'] and sha(output/'config.json')==prereg['config_sha256']
    stage=output/'stage';stage.mkdir();hashes={}
    for n in list(fc.INPUT_COLUMNS)+['target_1day']:
        path=ROOT/config['input_dir']/f'{n}_train.parquet';(stage/path.name).symlink_to(path);hashes[path.name]=sha(path)
    slow=ROOT/config['slow_control']['path'];assert sha(slow)==config['slow_control']['sha256']
    predictions=[output/'predictions'/f'{n}.parquet' for n in ['features','scores','standalone','mechanism_states']]
    firewall.install(allowed_artifacts=predictions+[slow])
    code=[Path(__file__),ROOT/'research/evaluation.py',ROOT/'research/firewall.py',ROOT/'research/experiments/sector_momentum.py',
        ROOT/'research/experiments/hierarchical_momentum.py',ROOT/'stock_comp_2026/evaluate_script.py',ROOT/'stock_comp_2026/strategies/dm_trainonly/features.py']
    code+=sorted((ROOT/'stock_comp_2026/strategies/dm_decline_causes').glob('*.py'))
    code+=sorted((ROOT/'tests/strategies/dm_decline_causes').glob('*.py'))
    codehash={str(p.relative_to(ROOT)):sha(p) for p in code}
    for p in code:
        dst=output/'code'/p.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
    shutil.copyfile(exp/'preregistration.json',output/'preregistration.json')
    if (exp/'tests.log').exists():shutil.copyfile(exp/'tests.log',output/'logs/tests.log')
    run.update(status='running',actual_trials=0,command=sys.argv,code_sha256=codehash,train_data_sha256=hashes,
        environment={'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'pyarrow':pyarrow.__version__,'scipy':scipy.__version__,'platform':platform.platform()})
    dump(output/'run.json',run)
    dump(output/'audit/pre_result_lock.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'plan_sha256':sha(output/'plan.md'),'config_sha256':sha(output/'config.json'),'code_sha256':codehash,'targets_loaded':False,'max_trials':3})
    dump(output/'audit/source_scan.json',source_scan())
    dump(output/'audit/schema.json',{n:{'schema':str(pq.read_schema(stage/f'{n}_train.parquet')),'used_columns':c} for n,c in fc.INPUT_COLUMNS.items()})
    inputs={n:fc.canonical(v,panel=n!='topix_return_1day') for n,v in fc.load_train(stage).items()}
    f=fc.build_features(inputs)
    dump(output/'audit/contract.json',contract_audit(inputs,f))
    dump(output/'audit/prefix_invariance.json',prefix_audit(inputs,f,config))
    signals={n:fc.score(f,n) for n in fc.CANDIDATES};signals['MOM60']=f.MOM60.rename('Return')
    saved=fc.canonical(pd.read_parquet(slow,columns=['SLOW_CONTROL','MOM60']))
    exact(signals['MOM60'],saved.MOM60.rename('Return'))
    signals['SLOW_CONTROL']=saved.SLOW_CONTROL.rename('Return')
    assert saved.index.equals(f.index)
    for n in fc.CANDIDATES:exact(signals[n].to_frame(),submission.predict(stage,n))
    dump(output/'audit/adapter_parity.json',{'status':'PASS','all3_bitwise':True,'prior_MOM60_bitwise':True,'slow_descriptive_unchanged_sha256':sha(slow)})
    standalone_smoke(stage,output,signals['CAUSE_COMPOSITE'])
    for name in ['target_1day_valid.parquet','raw_target_1day_train.parquet','unknown.parquet']:
        try:pd.read_parquet(stage/name)
        except PermissionError:pass
        else:raise AssertionError('Forbidden path accepted')
    assert not any('target_1day' in p for p in firewall.ACCESSES)
    dump(output/'audit/prediction_source_firewall.json',{'status':'PASS','opened':sorted(firewall.ACCESSES),'no_target_in_prediction':True,'forbidden_denials':3})
    f.to_parquet(predictions[0]);pd.DataFrame(signals).to_parquet(predictions[1])
    calendar=f.index.get_level_values('Date').unique().sort_values();dates,purge=fold_dates(calendar,[x['year'] for x in config['walk_forward_folds']])
    dump(output/'audit/purge.json',{'status':'PASS','folds':purge})
    coverage(f,dates,output/'metrics')
    print('All causal features/audits/control/adapter PASS. First Train target read follows.',flush=True)
    target=fc.canonical(pd.read_parquet(stage/'target_1day_train.parquet')).Return
    assert target.index.equals(f.index)
    daily={};holdings={};parity={}
    for n,s in signals.items():
        daily[n],holdings[n],parity[n]=account(s,target);daily[n].to_csv(output/f'metrics/daily_{n}.csv')
        if n in fc.CANDIDATES:run['actual_trials']+=1;dump(output/'run.json',run)
        print(f'Fixed account {n} complete',flush=True)
    dump(output/'audit/official_accounting_parity.json',{'status':'PASS','strategies':parity})
    results=pd.DataFrame([{'strategy':n,'scope':scope,**metrics(d.loc[ds])} for n,d in daily.items()
        for scope,ds in [('ALL_TRAIN',calendar)]+scopes(dates)])
    results.to_csv(output/'metrics/metrics.csv',index=False)
    for name,selection in [('overall_metrics',results.scope=='POOLED'),('fold_metrics',results.scope.isin([str(y) for y in range(2011,2017)])),('year_metrics',results.scope.isin([str(y) for y in range(2011,2017)]))]:
        results.loc[selection].to_csv(output/f'metrics/{name}.csv',index=False)
    results[['strategy','scope']+[k for k in results if 'long' in k or 'short' in k]].to_csv(output/'metrics/long_short.csv',index=False)
    results[['strategy','scope']+[k for k in results if k.startswith('q')]].to_csv(output/'metrics/quintiles.csv',index=False)
    increments=[]
    for n in fc.CANDIDATES:
        for scope in results.scope.unique():
            a=results.loc[(results.strategy==n)&(results.scope==scope)].iloc[0];b=results.loc[(results.strategy=='MOM60')&(results.scope==scope)].iloc[0]
            increments.append({'strategy':n,'control':'MOM60','scope':scope,**{'delta_'+k:a[k]-b[k] for k in results if k not in ['strategy','scope']}})
    pd.DataFrame(increments).to_csv(output/'metrics/incremental.csv',index=False)
    boot={}
    for scope,ds in scopes(dates)[:2]:
        for n in fc.CANDIDATES:
            boot[scope+':'+n+'-MOM60']={**evaluation.bootstrap_delta(daily['MOM60'].loc[ds].net,daily[n].loc[ds].net,**{k:config['bootstrap'][k] for k in ['block','reps','seed']}),
                'point_delta':evaluation.sharpe(daily[n].loc[ds].net)-evaluation.sharpe(daily['MOM60'].loc[ds].net),'days':len(ds),'primary':scope=='POOLED' and n=='CAUSE_COMPOSITE'}
    dump(output/'metrics/bootstrap.json',boot);pd.DataFrame([{'contrast':k,**v} for k,v in boot.items()]).to_csv(output/'metrics/bootstrap.csv',index=False)
    print('3/3 performance trials complete; fixed mechanism diagnostics only.',flush=True)
    dump(output/'audit/mechanism_reconciliation.json',diagnostics(f,target,signals,holdings,dates,output/'metrics'))
    decision=decide(results,boot);dump(output/'metrics/candidate_decision.json',decision)
    firewall.save(output/'audit/firewall.json')
    assert {Path(p).name for p in firewall.ACCESSES}==set(hashes)
    for p,h in codehash.items():assert sha(ROOT/p)==h,'Code changed after result lock'
    assert sha(exp/'plan.md')==prereg['plan_sha256'] and sha(exp/'config.json')==prereg['config_sha256']
    resources={'elapsed_seconds':time.monotonic()-start,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),'actual_trials':3,'valid_evaluation':False}
    dump(output/'audit/resources.json',resources)
    write_report(config,output,results,boot,decision)
    run.update(resources);run.update(status='completed',exit_code=0,completed_at_utc=datetime.now(timezone.utc).isoformat(),candidate_decisions=decision,
        artifact_sha256={str(p.relative_to(output)):sha(p) for folder in ['code','metrics','audit','predictions'] for p in (output/folder).rglob('*') if p.is_file()})
    dump(output/'run.json',run)
    print(json.dumps(safe({'decisions':decision,'resources':resources}),indent=2),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    output=Path(args.output).resolve();config=json.loads(Path(args.config).read_text())
    assert Path(args.config).resolve()==output/'config.json'
    assert config['data_split']=='train' and config['valid_evaluation'] is False and config['max_trials']==3
    assert tuple(x['trial_id'] for x in config['trials'])==fc.CANDIDATES
    assert config['parameters']=={'volume_window':20,'volume_min_periods':20,'sector33_min_finite_members':1,'relisting_gap':20,'weights':[1,1,1],'candidate_smoothing':None}
    assert config['bootstrap']['block']==20 and config['bootstrap']['reps']==2000 and config['bootstrap']['seed']==20261003
    run=json.loads((output/'run.json').read_text());assert run['status']=='prepared'
    try:main_work(config,output,run)
    except BaseException as e:
        run.update(status='failed',exit_code=1,error=f'{type(e).__name__}: {e}',completed_at_utc=datetime.now(timezone.utc).isoformat());dump(output/'run.json',run)
        if firewall._PATCHED:firewall.save(output/'audit/firewall.json')
        raise


if __name__=='__main__':main()
