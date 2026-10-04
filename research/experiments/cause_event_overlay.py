"""Pre-registered two-trial Train-only event-overlay research and diagnostics."""
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
import scipy
from research import evaluation, firewall
from research.experiments.sector_momentum import sha, dump, safe, exact, account, metrics, fold_dates, table
from research.experiments.hierarchical_momentum import scopes
from research.experiments.decline_causes import mutate, diagnostic_row
from stock_comp_2026.strategies.dm_cause_event_overlay import features as fc, submission
from stock_comp_2026.strategies.dm_trainonly import features as old


def source_scan():
    folder=ROOT/'stock_comp_2026/strategies/dm_cause_event_overlay'
    paths=sorted(folder.glob('*.py'));findings=[]
    assert sha(folder/'anchor.py')==sha(ROOT/'stock_comp_2026/strategies/dm_slow_multifactor/features.py')
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node,ast.Constant) and isinstance(node.value,str):
                if any(t in node.value for t in ['AdjustmentOpen','AdjustmentHigh','AdjustmentLow','AdjustmentClose',
                    'AdjustmentVolume','raw_target','target_1day','_valid.parquet','ForecastOrdinaryProfit','ForecastProfit']):
                    findings.append([str(path),node.lineno,'forbidden input'])
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                bad=node.func.attr in ['bfill','backfill']
                if node.func.attr=='shift':
                    n=node.args[0] if node.args else next((k.value for k in node.keywords if k.arg=='periods'),None)
                    bad |= not isinstance(n,ast.Constant) or not isinstance(n.value,int) or n.value<0
                for kw in node.keywords:
                    bad |= kw.arg=='center' and not (isinstance(kw.value,ast.Constant) and kw.value.value is False)
                    bad |= kw.arg=='direction' and not (isinstance(kw.value,ast.Constant) and kw.value.value=='backward')
                if bad:findings.append([str(path),node.lineno,'forbidden time operation'])
    assert not findings,findings
    return {'status':'PASS','sources':[str(p.relative_to(ROOT)) for p in paths],'findings':findings,
        'anchor_copy_bitwise':True,'manual_review':'Frozen global anchor only. Dormant original Sector17 loader/sector branch never used. New context only PIT33. Original anchor median allowed, no event imputation. Forecast delta only fresh first available signal, no held score. Price/volume prior session; causal20 prior observation median. Sector never added to score. No labels/fit.'}


def prefix_audit(inputs,f,config):
    cases=[]
    for i,text in enumerate(config['prefix_cutoffs']):
        cutoff=pd.Timestamp(text);index=f.index[f.index.get_level_values('Date')<=cutoff]
        for source in list(inputs)+['ALL','TRUNCATION']:
            changed={}
            for j,(key,frame) in enumerate(inputs.items()):
                changed[key]=(frame.loc[frame.index.get_level_values('Date')<=cutoff] if source=='TRUNCATION'
                    else mutate(frame,key,cutoff,config['random_seed']+i*100+j) if source in [key,'ALL'] else frame)
            got=fc.build_features(changed);exact(f.loc[index],got.loc[index])
            cases.append({'cutoff':text,'source':source,'status':'PASS','prefix_rows':len(index),'columns':len(f.columns),'bitwise':True})
        print(f'All-input future mutation/truncation {text}: PASS',flush=True)
    exact(f,fc.build_features(inputs))
    exact(f,fc.build_features({n:v.sample(frac=1,random_state=config['random_seed']) for n,v in inputs.items()}))
    return {'status':'PASS','cases':cases,'deterministic_rebuild_bitwise':True,'row_shuffle_bitwise':True,
        'method':'All intermediate features and both candidate scores; float64 uint64 exact incl NaNs, strings/index/dtypes exact. Each-source and joint extremes/NaN/zero, suffix deletion/date shifts, fiscal/basis/sector changes, future-only stocks, separate truncation.'}


def contract_audit(inputs,f):
    idx=fc.canonical(inputs['raw_return_1day']).index
    assert f.index.equals(idx)
    assert np.isfinite(f[list(fc.CANDIDATES)+['SLOW_CONTROL','SlowRank','MOM60']].to_numpy()).all()
    fresh=f.FreshFundEvent.eq(1);fund=f.FundActive.eq(1);flow=f.FlowActive.eq(1)
    assert not (fresh&flow).any()
    assert f.loc[~fund,'FundOverlay'].eq(0).all() and f.loc[~flow,'FlowOverlay'].eq(0).all()
    assert f.loc[~fresh,'FUND_EVENT_RAW'].isna().all()
    assert (f.loc[fresh,'FundDisclosure']<idx.get_level_values('Date')[fresh]).all()
    assert (f.loc[fund,'PITAssets']>0).all()
    assert (f.loc[flow,'WithinShock']<0).all() and (f.loc[flow,'AbnormalVolume']>0).all()
    exact(f.SLOW_FUND_EVENT,(f.SlowRank+f.FundOverlay).rename('SLOW_FUND_EVENT'))
    exact(f.SLOW_CAUSE_AWARE,(f.SlowRank+f.FundOverlay+f.FlowOverlay).rename('SLOW_CAUSE_AWARE'))
    exact(f.MOM60.rename('Return'),old.smooth(old.build_momentum(inputs),.25).rename('Return'))
    a,b=evaluation.weights(f.SLOW_CONTROL),evaluation.weights(f.SlowRank)
    exact(a[0].rename('weight'),b[0].rename('weight'));exact(a[1].rename('q'),b[1].rename('q'))
    events=fc.financial_events(inputs['fins_statements']);valid=events.ForecastPrevious.notna()
    assert events.loc[valid,fc.FISCAL+['Basis']].notna().all().all()
    return {'status':'PASS','rows':len(idx),'exact_index':True,'all_predictions_finite':True,
        'no_revision_carry':True,'event_support_mutually_exclusive':True,'inactive_overlay_exact_zero':True,
        'anchor_rank_weight_quintiles_bitwise':True,'MOM60_primitive_bitwise':True,
        'disclosure_available_before_signal':True,'same_fiscal_basis':True,'comparable_disclosures':int(valid.sum()),
        'fresh_known_revision_rows':int(fresh.sum()),'fund_active_rows':int(fund.sum()),'flow_active_rows':int(flow.sum())}


def standalone_smoke(stage,output,signal):
    folder=output/'adapter_smoke';folder.mkdir()
    pred=output/'predictions/standalone.parquet';result=output/'audit/standalone_smoke.json'
    script='\n'.join(['import sys,os,json,time,resource',f'sys.path.insert(0,{str(ROOT)!r})',
        'from research import firewall; firewall.install()',
        f'sys.path.insert(0,{str(ROOT/"stock_comp_2026/strategies/dm_cause_event_overlay")!r})','import submission',
        f'os.chdir({str(stage)!r})','t=time.monotonic();p=submission.predict()',f'p.to_parquet({str(pred)!r})',
        "r={'status':'PASS','rows':len(p),'elapsed_seconds':time.monotonic()-t,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),'opened':sorted(firewall.ACCESSES)}",
        f'open({str(result)!r},"w").write(json.dumps(r,indent=2)+"\\n")'])
    (folder/'script.py').write_text(script+'\n')
    process=subprocess.run([sys.executable,str(folder/'script.py')],capture_output=True,text=True,timeout=180)
    (output/'logs/standalone.log').write_text(process.stdout+process.stderr)
    assert process.returncode==0,process.stderr
    exact(signal.to_frame(),pd.read_parquet(pred))
    record=json.loads(result.read_text());record['bitwise_research_parity']=True;dump(result,record)


def coverage(f,dates,folder):
    rows=[];ties=[]
    masks={'FreshFundEvent':f.FreshFundEvent.eq(1),'FundActive':f.FundActive.eq(1),'FlowActive':f.FlowActive.eq(1),
        'FundOverlay_nonzero':f.FundOverlay.ne(0),'FlowOverlay_nonzero':f.FlowOverlay.ne(0),
        'SectorShock_finite':f.SectorShock.notna(),'AbnormalVolume_finite':f.AbnormalVolume.notna(),
        'StockResidualReturn_finite':f.StockResidualReturn.notna()}
    for scope,ds in [('ALL_TRAIN',f.index.get_level_values('Date').unique())]+scopes(dates):
        use=f.index.get_level_values('Date').isin(ds)
        for name,mask in masks.items():
            rows.append({'scope':scope,'component':name,'rows':int(use.sum()),'count':int((mask&use).sum()),'fraction':float(mask.loc[use].mean())})
    for day,g in f.groupby('Date',sort=True):
        for raw,active,overlay in [('FUND_EVENT_RAW','FundActive','FundOverlay'),('FLOW_EVENT_RAW','FlowActive','FlowOverlay')]:
            x=g.loc[g[active].eq(1),raw];counts=x.value_counts()
            ties.append({'Date':day,'event':raw,'active':len(x),'distinct':x.nunique(),
                'largest_tie':int(counts.max()) if len(counts) else 0,'nonzero_overlay':int(g[overlay].ne(0).sum()),
                'non_event_nonzero':int(g.loc[g[active].eq(0),overlay].ne(0).sum())})
    pd.DataFrame(rows).to_csv(folder/'event_coverage.csv',index=False)
    pd.DataFrame(ties).to_csv(folder/'event_ties_daily.csv',index=False)


def cause_states(f):
    fresh=f.FreshFundEvent.eq(1)
    state=pd.Series(np.select([fresh&f.FundDelta.lt(0),~fresh&f.SectorShock.lt(0),
        ~fresh&f.SectorShock.ge(0)&f.WithinShock.lt(0)&f.AbnormalVolume.gt(0)],
        ['PERSISTENT_INFO','COMMON_INDUSTRY','TRANSIENT_PRESSURE'],default='OTHER'),index=f.index,name='cause_state')
    return state.where(f.StockRawReturn.lt(0),'NON_NEGATIVE_OR_MISSING')


def cumulative_targets(target,calendar,horizon):
    """Diagnostics ONLY: forward official labels, consecutive calendar, no skips."""
    grid=target.unstack('Code').reindex(calendar)
    total=grid.copy();valid=grid.notna()
    for offset in range(1,horizon):
        # Negative shift confined to post-prediction diagnostic targets, never features.
        future=grid.shift(-offset)
        total=total+future;valid &= future.notna()
    return total.where(valid).stack(future_stack=True).reindex(target.index)


def diagnostic_dates(calendar,years,horizon):
    dates=[];audit=[]
    for year in years:
        sessions=calendar[calendar.year==year];keep=sessions[:-(horizon+1)]
        for day in keep:
            assert calendar[calendar.get_loc(day)+horizon+1].year==year
        dates.extend(keep)
        audit.append({'year':year,'horizon':horizon,'days':len(keep),'purged_sessions':horizon+1,
            'last_signal':str(keep[-1].date()),'last_maturity':str(sessions[-1].date()),'status':'PASS'})
    return pd.DatetimeIndex(dates),audit


def event_diagnostics(f,target,calendar,config,folder):
    fresh=f.FreshFundEvent.eq(1)
    masks={'FRESH_UP':fresh&f.FundDelta.gt(0),'FRESH_DOWN':fresh&f.FundDelta.lt(0),
        'NEG_MOVE_SECTOR_DOWN':f.StockRawReturn.lt(0)&f.SectorShock.lt(0),
        'NEG_MOVE_SECTOR_NONNEG':f.StockRawReturn.lt(0)&f.SectorShock.ge(0),
        'NEG_MOVE_SECTOR_MISSING':f.StockRawReturn.lt(0)&f.SectorShock.isna(),
        'NO_FUND_WITHIN_NEG_HIGH_VOL':~fresh&f.WithinShock.lt(0)&f.AbnormalVolume.gt(0),
        'NO_FUND_WITHIN_NEG_NORMAL_VOL':~fresh&f.WithinShock.lt(0)&f.AbnormalVolume.le(0),
        'NO_FUND_WITHIN_NEG_MISSING_VOL':~fresh&f.WithinShock.lt(0)&f.AbnormalVolume.isna()}
    summary=[];audits=[];panel=pd.DataFrame(index=f.index)
    for h in config['diagnostics']['horizons']:
        y=cumulative_targets(target,calendar,h);ds,records=diagnostic_dates(calendar,range(2011,2017),h)
        audits+=records;panel[f'cumulative_residual_{h}']=y.where(f.index.get_level_values('Date').isin(ds))
        for scope,dates in scopes(ds):
            use=f.index.get_level_values('Date').isin(dates)
            for name,mask in masks.items():
                samples=y.loc[use&mask];daily=samples.groupby('Date').mean().dropna()
                summary.append({'scope':scope,'cohort':name,'horizon':h,'event_count':len(samples),
                    'complete_target_count':int(samples.notna().sum()),'cumulative_residual_mean':float(samples.mean()),
                    'cumulative_residual_std':float(samples.std()),'mean_daily_event_return':float(daily.mean()),
                    'daily_event_return_t_hac5':evaluation.hac_t(daily),'event_days':len(daily)})
    for name,mask in masks.items():panel[name]=mask
    panel['FundDelta']=f.FundDelta;panel['FundDisclosure']=f.FundDisclosure
    keep=panel[list(masks)].any(axis=1)&panel.index.get_level_values('Date').year.isin(range(2011,2017))
    panel.loc[keep].to_parquet(folder/'event_study_panel.parquet')
    pd.DataFrame(summary).to_csv(folder/'event_study.csv',index=False)
    return {'status':'PASS','maturity_checks':audits,'cumulative_definition':'Arithmetic sum of official residual targets over1/2/3/5 consecutive calendar sessions; require all finite, horizon end within fold. Listing-boundary labels supplied missing by organizer. No optimization or strategy.'}


def state_diagnostics(f,target,signals,holdings,dates,folder):
    states=cause_states(f);rows=[];reconc=[]
    for scope,ds in scopes(dates):
        use=f.index.get_level_values('Date').isin(ds)&f.StockRawReturn.lt(0)
        local=f.loc[use];y=target.loc[use];st=states.loc[use]
        for n,s in signals.items():
            h=holdings[n].loc[local.index];parts=[]
            for state in ['PERSISTENT_INFO','COMMON_INDUSTRY','TRANSIENT_PRESSURE','OTHER']:
                mask=st.eq(state)
                row={'strategy':n,'scope':scope,'state':state,**diagnostic_row(s.loc[local.index],y,h,mask,len(ds)),
                    'long_membership_count':int((mask&h.w.gt(0)).sum()),'short_membership_count':int((mask&h.w.lt(0)).sum()),
                    'flat_membership_count':int((mask&h.w.eq(0)).sum()),'gross_contribution':float(h.gross.loc[mask].sum())}
                rows.append(row);parts.append(row)
            assert sum(x['count'] for x in parts)==len(local)
            assert abs(sum(x['gross_contribution'] for x in parts)-float(h.gross.sum()))<1e-12
            for side in ['long','short']:
                assert abs(sum(x[side+'_gross'] for x in parts)-float(h.gross.where(h.w.gt(0) if side=='long' else h.w.lt(0),0).sum()))<1e-12
            reconc.append({'scope':scope,'strategy':n,'status':'PASS','rows':len(local),'tolerance':1e-12})
    pd.DataFrame(rows).to_csv(folder/'cause_state_metrics.csv',index=False)
    states.to_frame().to_parquet(folder/'cause_states.parquet')
    return {'status':'PASS','cases':reconc,'classification':'Observed proxy classification, not true causal identification; fixed priority/no post-result filters.'}


def turnover_panel(f,h,anchor_h,target,candidate):
    active=f.FundActive.eq(1)|(f.FlowActive.eq(1) if candidate=='SLOW_CAUSE_AWARE' else False)
    prior_active=active.groupby('Code').shift(1).fillna(False).astype(bool)
    w=h.w;previous=w.groupby('Code').shift(1).fillna(0.)
    turn=(w-previous).abs();anchor_turn=anchor_h.w.groupby('Code').diff().abs().fillna(anchor_h.w.abs())
    displacement=h.q.ne(anchor_h.q)
    prior_displacement=displacement.groupby('Code').shift(1).fillna(False).astype(bool)
    event_group=np.select([active,prior_active],['CURRENT_EVENT','PRIOR_EVENT_ONLY'],default='NON_EVENT')
    transition=np.select([previous.eq(0)&w.ne(0),previous.ne(0)&w.eq(0),previous*w<0,turn.gt(0)],
        ['ENTRY','EXIT','SIGN_FLIP','RESIZE'],default='NO_CHANGE')
    rank_group=np.select([displacement,prior_displacement],['TODAY_DISPLACED','PRIOR_DISPLACED_ONLY'],default='ALWAYS_ALIGNED')
    out=pd.DataFrame({'event_group':event_group,'transition':transition,'rank_group':rank_group,
        'turnover':turn,'cost':.001*turn.where(target.notna(),0.),'cost_all':.001*turn,
        'gross':h.gross.fillna(0.),'net':h.net,'anchor_turnover':anchor_turn,
        'delta_turnover':turn-anchor_turn,'delta_cost':h.cost-anchor_h.cost,
        'delta_gross':h.gross.fillna(0.)-anchor_h.gross.fillna(0.),'delta_net':h.net-anchor_h.net,
        'event_current':active.astype(float),'event_current_or_prior':(active|prior_active).astype(float),
        'displaced_membership':displacement.astype(float),
        'non_event_displaced_membership':(displacement&~active).astype(float)},index=f.index)
    assert np.allclose(out.cost,h.cost,atol=1e-18,rtol=0)
    return out


def turnover_attribution(f,target,holdings,daily,dates,folder):
    summaries=[];daily_parts=[];checks=[];panels={}
    numeric=['turnover','cost','cost_all','gross','net','anchor_turnover','delta_turnover','delta_cost','delta_gross','delta_net',
        'event_current','event_current_or_prior','displaced_membership','non_event_displaced_membership']
    for n in fc.CANDIDATES:
        panel=turnover_panel(f,holdings[n],holdings['SLOW_CONTROL'],target,n);panels[n]=panel
        selected=panel.loc[panel.index.get_level_values('Date').isin(dates)]
        selected.to_parquet(folder/f'turnover_stock_panel_{n}.parquet')
        for scope,ds in scopes(dates):
            local=panel.loc[panel.index.get_level_values('Date').isin(ds)]
            for dimension in ['event_group','transition','rank_group']:
                grouped=local.groupby(dimension)[numeric].sum()
                for key,row in grouped.iterrows():
                    summaries.append({'strategy':n,'scope':scope,'dimension':dimension,'group':key,'stock_rows':int(local[dimension].eq(key).sum()),
                        **{k:float(v) for k,v in row.items()},'average_daily_turnover':float(row.turnover/len(ds)),
                        'annual_cost':float(row.cost/len(ds)*252),'annual_delta_gross':float(row.delta_gross/len(ds)*252),
                        'annual_delta_cost':float(row.delta_cost/len(ds)*252),'annual_delta_net':float(row.delta_net/len(ds)*252)})
                for metric in ['turnover','cost_all','gross','net']:
                    expected=float(daily[n].loc[ds,metric].sum())
                    assert abs(float(grouped[metric].sum())-expected)<1e-12,(n,scope,dimension,metric)
                # Official charged cost is gross minus net, within floating accumulation.
                assert abs(float(grouped.cost.sum())-float(daily[n].loc[ds,'cost'].sum()))<1e-12
                checks.append({'strategy':n,'scope':scope,'dimension':dimension,'status':'PASS','tolerance':1e-12})
        d=selected.reset_index().groupby(['Date','event_group','transition','rank_group'])[numeric].sum().reset_index()
        d['strategy']=n;daily_parts.append(d)
    pd.DataFrame(summaries).to_csv(folder/'turnover_attribution.csv',index=False)
    pd.concat(daily_parts,ignore_index=True).to_csv(folder/'turnover_attribution_daily.csv',index=False)
    # B-A decomposition by the same event support and transitions of B, no extra portfolio.
    ba=panels['SLOW_CAUSE_AWARE'].copy()
    for k in ['turnover','cost','gross','net']:
        ba['incremental_'+k]=panels['SLOW_CAUSE_AWARE'][k]-panels['SLOW_FUND_EVENT'][k]
    rows=[]
    for scope,ds in scopes(dates):
        local=ba.loc[ba.index.get_level_values('Date').isin(ds)]
        for dimension in ['event_group','transition','rank_group']:
            group=local.groupby(dimension)[['incremental_'+k for k in ['turnover','cost','gross','net']]].sum()
            for key,r in group.iterrows():rows.append({'scope':scope,'dimension':dimension,'group':key,
                **{k:float(v) for k,v in r.items()},**{'annual_'+k:float(r['incremental_'+k]/len(ds)*252) for k in ['cost','gross','net']}})
            for k in ['gross','net','turnover']:
                expected=float((daily['SLOW_CAUSE_AWARE'].loc[ds,k]-daily['SLOW_FUND_EVENT'].loc[ds,k]).sum())
                assert abs(float(group['incremental_'+k].sum())-expected)<1e-12
    pd.DataFrame(rows).to_csv(folder/'flow_incremental_attribution.csv',index=False)
    return {'status':'PASS','cases':checks,'B_minus_A_reconciled':True,
        'definition':'CURRENT_EVENT and PRIOR_EVENT_ONLY union assigns one-session event exits. NON_EVENT means neither current nor previous active event. ENTRY/EXIT/SIGN_FLIP/RESIZE disjoint. Rank membership displacement versus anchor is separate overlapping view, not added to transition turnover. No causal turnover identification claimed.'}


def decide(results,boot):
    result={}
    def get(n,scope):return results.loc[(results.strategy==n)&(results.scope==scope)].iloc[0]
    b=get('SLOW_CONTROL','POOLED');be=get('SLOW_CONTROL','EX2016')
    for n in fc.CANDIDATES:
        m=get(n,'POOLED');ex=get(n,'EX2016')
        improves=sum(get(n,str(y)).net_sharpe>get('SLOW_CONTROL',str(y)).net_sharpe for y in range(2011,2016))
        checks={'pooled_net_sharpe':m.net_sharpe>b.net_sharpe,'ex2016_net_sharpe':ex.net_sharpe>be.net_sharpe,
            'full_year_improvements_4_of_5':improves>=4,'bootstrap_lower_gt0':boot['POOLED:'+n+'-SLOW_CONTROL']['low']>0,
            'annual_net':m.annual_net>b.annual_net,'turnover_le_1_25x':m.turnover<=b.turnover*1.25,
            'long_net_ge0':m.annual_long_net>=0,'short_net_ge_control':m.annual_short_net>=b.annual_short_net}
        extra={}
        if n=='SLOW_CAUSE_AWARE':
            a=get('SLOW_FUND_EVENT','POOLED')
            extra={'B_net_sharpe_gt_A':m.net_sharpe>a.net_sharpe,'B_annual_net_gt_A':m.annual_net>a.annual_net,
                'Flow_incremental_cost_lt_gross':m.annual_cost-a.annual_cost<m.annual_gross-a.annual_gross}
            checks.update(extra)
        result[n]={'decision':'TRAIN_ONLY_NEXT_STAGE_ELIGIBLE' if all(checks.values()) else 'REJECT',
            'checks':checks,'failed_checks':[k for k,v in checks.items() if not v],
            'full_year_improvements':improves,'flow_additional_gates':extra}
    return result


def write_report(config,output,results,boot,decision):
    report=ROOT/config['report_dir'];report.mkdir(parents=True,exist_ok=False)
    for name in ['metrics','audit']:shutil.copytree(output/name,report/name)
    pooled=results.loc[results.scope=='POOLED']
    event=pd.read_csv(output/'metrics/event_study.csv');turn=pd.read_csv(output/'metrics/turnover_attribution.csv')
    flow=pd.read_csv(output/'metrics/incremental.csv')
    cols=['strategy','rankic','rankic_t_hac5','gross_sharpe','net_sharpe','annual_gross','annual_net','turnover','annual_cost','annual_long_net','annual_short_net']
    lines=[f'# {config["experiment_id"]} — Fresh information / industry context / transient pressure','',
        '採否: '+', '.join(n+'='+d['decision'] for n,d in decision.items())+'.',
        '2026-10-03 JST。指定2/2候補のみ。既知Trainの研究であり独立OOSではない。Historical Valid/Valid未使用、追加候補・window/weight/threshold変更なし。',
        f'Run: `{output.relative_to(ROOT)}`。計画/設定hashを実装前、code/input/environmentをtarget読込前に固定。',
        '', '## Pooled results','',table(pooled,cols),'',
        'P/Lはdecimal。年率=日次平均×252、Sharpe=sample SD×√252、IC t=Newey–West/Bartlett HAC5。Q1低score/Q5高score。Long/Shortは符号付き残差損益。SLOW_CONTROLは不変のglobal Size/Liquidity block、MOM60は記述参照。2016 partialは別集計。',
        '', '## Full years and 2016 partial','',table(results.loc[results.scope.isin([str(y) for y in range(2011,2017)])],['strategy','scope','net_sharpe','annual_net','turnover','annual_long_net','annual_short_net']),
        '', '## Incremental Flow: B minus A','',table(flow.loc[(flow.strategy=='SLOW_CAUSE_AWARE')&(flow.control=='SLOW_FUND_EVENT')&flow.scope.isin(['POOLED','EX2016'])],['scope','delta_rankic','delta_gross_sharpe','delta_net_sharpe','delta_annual_gross','delta_annual_net','delta_turnover','delta_annual_cost']),
        '', '## Bootstrap and adoption','',table(pd.DataFrame([{'contrast':k,**v} for k,v in boot.items()]),['contrast','point_delta','low','high']),
        '', 'Paired circular20 sessions/2000 reps/seed20261003/95% percentile。POOLED B−SLOW_CONTROL primary。A−control、B−A secondary、EX2016も保存。連結したeligible sessionsの年境界purge gapは連結。探索履歴の多重性は補正しておらず、既知Trainの標本不確実性。',
        '', *[f'- {n}: 改善{d["full_year_improvements"]}/5年。不通過: '+(', '.join(d['failed_checks']) or 'none')+'.' for n,d in decision.items()],
        '', '## Fixed mechanism diagnostics','',table(event.loc[(event.scope=='POOLED')&event.cohort.isin(['FRESH_UP','FRESH_DOWN','NO_FUND_WITHIN_NEG_HIGH_VOL','NO_FUND_WITHIN_NEG_NORMAL_VOL'])],['cohort','horizon','event_count','complete_target_count','cumulative_residual_mean','daily_event_return_t_hac5']),
        '', '1/2/3/5-sessionは固定event studyでholding候補ではない。累積はofficial residual targetの算術和、calendar連続、全ラベル有限、終点t+h+1をyear内にpurge。Industry negative move sector<0/>=0/missingもCSV。イベント重複と将来開示は自然経過を含み、因果識別やhalf-lifeの確定推定ではない。診断結果からcandidateを変更していない。',
        '', '## Turnover attribution','',table(turn.loc[(turn.scope=='POOLED')&(turn.dimension=='event_group')],['strategy','group','average_daily_turnover','annual_cost','annual_delta_gross','annual_delta_cost','annual_delta_net']),
        '', 'CURRENT_EVENT＋PRIOR_EVENT_ONLYがevent-active銘柄のturnover（当日または前日のevent support）。NON_EVENTはその両方に非該当。ENTRY/EXIT/SIGN_FLIP/RESIZEは別の排他的内訳。rank displacementはanchorのquintile membershipとの比較で、entry/exitと重なる別軸。非eventが押し出されるturnover、event翌日の退出も計測。これは観測会計であり真の因果attributionではない。B−Aのstock/daily gross/cost/netは別CSVで照合。',
        '', '## Definitions and limitations','',
        'Fresh fundは総額ForecastOperatingProfitの同一fiscal/basis revisionのみ。Date-only開示EODから最初のsignal sessionに一度だけactive、次日は0。scaled missingはoverlay0、既知fresh revisionならFlow排除。休日開示は次signalに利用可。複数開示は最新を優先。予想据置はno event。Assetsは開示時点既知値、過去へ遡及しない。',
        'Sector33はτのhistorical PIT membership/self-inclusive等weight residual mean、min1。SectorShockはcontextでscoreへ加算しない。raw-returnはopen-to-open、raw通日Volumeは終点open後の取引も含むため同時刻の純粋flow観測ではない。τは共通直前exchange session、株row欠落はmissing。Volume surpriseは固定20観測log1p中央値差。raw Volumeのsplit/単位変化は補正していない。',
        '非event/missing overlayはexact0。active有限のみaverage centered rank、Code ordinalを使わない。singleton/all tie=0、全fund符号を同じevent cross-sectionでrank。指定のcentered percentileのため小さいpositive Flow eventがnegative overlayにもなる。Final official quintile tieは公式Code-orderを保持。再EWMAなし。旧anchorのmedian normalizationと元入力は変更していない。',
        'Negative stock moveの固定4statesはobserved proxy classificationであり真の原因を識別したとは呼ばない。Fresh downward→no-fund sector<0→no-fund sector>=0/Within<0/high-volume→OTHERの順序。各state count/target/HAC5RankIC/LongShort membership/grossを保存しnegative subset損益へ照合。',
        '', '## Causality and artifacts','',
        '全入力個別/joint future mutationとtruncationを3cutoffで全中間特徴量/anchor/2scores bitwise検査。suffix値/NaN/zero/日付・fiscal・basis・sector変更/行削除/future-only stocks、row shuffle、deterministic rebuild、exact index/finite coverage、disclosure/fiscal/basis/Volume/PIT fixtures、adapter/standalone parity。動的検査は試した入力/cutoffの証拠。',
        '保存済みSLOW_CONTROLとMOM60をbitwise再現。SlowRank-only official weights/quintilesと日次P/Lは不変。全Train official weight/netP/L bitwise、LongShort会計1e−15、state/turnover内訳1e−12照合。公式missing-target cost脱落とall-position conservative cost/netを両方保存。全Train上で継続weight/costを計算後、年末2session purge。',
        '`metrics.csv`全指標、`fold_metrics.csv`/`year_metrics.csv`、`incremental.csv`、`long_short.csv`、`quintiles.csv`、`bootstrap.csv`、`event_study.csv`/panel、`cause_state_metrics.csv`/states、`event_coverage.csv`、`event_ties_daily.csv`、`turnover_attribution.csv`/daily/stock panel、`flow_incremental_attribution.csv`、`daily_*.csv`。audit/*、run予測/コードsnapshot/環境/hash/コマンドを保存。']
    (report/'REPORT.md').write_text('\n'.join(lines)+'\n')
    exp=ROOT/'experiments'/config['experiment_id']
    (exp/'decision.md').write_text('# '+config['experiment_id']+' decision\n\nExactly2/2 fixed performance trials, Train-only.\n\n'+'\n'.join('- **'+n+'** — '+d['decision']+'. Failed: '+(', '.join(d['failed_checks']) or 'none')+'.' for n,d in decision.items())+f'\n\n[Report](../../{config["report_dir"]}/REPORT.md). [All gates](../../{config["report_dir"]}/metrics/candidate_decision.json).\n\nImmutable SLOW_CONTROL preserved. No rescue/event-window/weight/threshold changes. Observed cause proxies only; no Valid/release/external submission.\n')
    meta=json.loads((exp/'experiment.json').read_text());meta.update(status='rejected' if all(d['decision']=='REJECT' for d in decision.values()) else 'completed',actual_trials=2,run_id=output.name,report=config['report_dir']+'/REPORT.md');dump(exp/'experiment.json',meta)
    rejected=[n for n,d in decision.items() if d['decision']=='REJECT']
    if rejected:
        with (ROOT/'experiments/GRAVEYARD.md').open('a') as stream:
            stream.write(f'\n## {config["experiment_id"]}: Fresh cause-aware event overlays\n\n[Decision]({config["experiment_id"]}/decision.md) / [Report](../{config["report_dir"]}/REPORT.md). Fixed2 trials; unchanged SLOW_CONTROL; Train-only/no Valid/no rescue.\n\n')
            for n in rejected:stream.write('- **'+n+'** — REJECT; failed: '+', '.join(decision[n]['failed_checks'])+'.\n')


def main_work(config,output,run):
    start=time.monotonic();exp=ROOT/'experiments'/config['experiment_id']
    prereg=json.loads((exp/'preregistration.json').read_text())
    assert sha(output/'plan.md')==prereg['plan_sha256'] and sha(output/'config.json')==prereg['config_sha256']
    stage=output/'stage';stage.mkdir();hashes={}
    for n in list(fc.INPUT_COLUMNS)+['target_1day']:
        path=ROOT/config['input_dir']/f'{n}_train.parquet';(stage/path.name).symlink_to(path);hashes[path.name]=sha(path)
    slow=ROOT/config['slow_control']['path'];assert sha(slow)==config['slow_control']['sha256']
    predictions=[output/'predictions'/f'{n}.parquet' for n in ['features','scores','standalone']]
    diagnostic_artifacts=[output/'metrics'/name for name in ['cause_states.parquet','event_study_panel.parquet',
        'turnover_stock_panel_SLOW_FUND_EVENT.parquet','turnover_stock_panel_SLOW_CAUSE_AWARE.parquet']]
    firewall.install(allowed_artifacts=predictions+diagnostic_artifacts+[slow])
    code=[Path(__file__),ROOT/'research/evaluation.py',ROOT/'research/firewall.py',ROOT/'research/experiments/sector_momentum.py',
        ROOT/'research/experiments/hierarchical_momentum.py',ROOT/'research/experiments/decline_causes.py',
        ROOT/'stock_comp_2026/evaluate_script.py',ROOT/'stock_comp_2026/strategies/dm_trainonly/features.py']
    for name in ['dm_cause_event_overlay','dm_slow_multifactor','dm_decline_causes','dm_sector_momentum','dm_hierarchical_momentum']:
        code+=sorted((ROOT/f'stock_comp_2026/strategies/{name}').glob('*.py'))
    code+=sorted((ROOT/'tests/strategies/dm_cause_event_overlay').glob('*.py'))
    codehash={str(p.relative_to(ROOT)):sha(p) for p in code}
    for p in code:
        dst=output/'code'/p.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
    shutil.copyfile(exp/'preregistration.json',output/'preregistration.json')
    for log in exp.glob('tests*.log'):shutil.copyfile(log,output/'logs'/log.name)
    run.update(status='running',actual_trials=0,command=sys.argv,code_sha256=codehash,train_data_sha256=hashes,
        environment={'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'pyarrow':pyarrow.__version__,'scipy':scipy.__version__,'platform':platform.platform()})
    dump(output/'run.json',run)
    dump(output/'audit/pre_result_lock.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'plan_sha256':sha(output/'plan.md'),'config_sha256':sha(output/'config.json'),'code_sha256':codehash,'targets_loaded':False,'max_trials':2})
    dump(output/'audit/source_scan.json',source_scan())
    inputs={n:fc.canonical(v,panel=n!='topix_return_1day') for n,v in fc.load_train(stage).items()}
    f=fc.build_features(inputs)
    dump(output/'audit/contract.json',contract_audit(inputs,f))
    dump(output/'audit/prefix_invariance.json',prefix_audit(inputs,f,config))
    saved=fc.canonical(pd.read_parquet(slow,columns=['SLOW_CONTROL','MOM60']))
    exact(f[['SLOW_CONTROL','MOM60']],saved[['SLOW_CONTROL','MOM60']])
    assert saved.index.equals(f.index)
    signals={n:fc.score(f,n) for n in fc.CANDIDATES}
    signals.update({n:f[n].rename('Return') for n in ['SLOW_CONTROL','MOM60']})
    for n in fc.CANDIDATES:exact(signals[n].to_frame(),submission.predict(stage,n))
    dump(output/'audit/adapter_parity.json',{'status':'PASS','both_candidates_bitwise':True,'prior_anchor_MOM60_bitwise':True,'anchor_sha256':sha(slow)})
    standalone_smoke(stage,output,signals['SLOW_CAUSE_AWARE'])
    for name in ['target_1day_valid.parquet','raw_target_1day_train.parquet','unknown.parquet']:
        try:pd.read_parquet(stage/name)
        except PermissionError:pass
        else:raise AssertionError('Forbidden path accepted')
    assert not any('target_1day' in p for p in firewall.ACCESSES)
    dump(output/'audit/prediction_source_firewall.json',{'status':'PASS','opened':sorted(firewall.ACCESSES),'no_target_in_prediction':True,'forbidden_denials':3})
    f.to_parquet(predictions[0]);pd.DataFrame(signals).to_parquet(predictions[1])
    calendar=f.index.get_level_values('Date').unique().sort_values();dates,purge=fold_dates(calendar,range(2011,2017))
    dump(output/'audit/purge.json',{'status':'PASS','folds':purge})
    coverage(f,dates,output/'metrics')
    print('Causality, unchanged anchor, rank portfolio and adapters PASS. First Train target read follows.',flush=True)
    target=fc.canonical(pd.read_parquet(stage/'target_1day_train.parquet')).Return
    assert target.index.equals(f.index)
    daily={};holdings={};parity={}
    for n,s in signals.items():
        daily[n],holdings[n],parity[n]=account(s,target);daily[n].to_csv(output/f'metrics/daily_{n}.csv')
        if n in fc.CANDIDATES:run['actual_trials']+=1;dump(output/'run.json',run)
        print(f'Fixed portfolio {n} complete',flush=True)
    ranked_daily,ranked_h,ranked_audit=account(f.SlowRank.rename('Return'),target)
    exact(daily['SLOW_CONTROL'],ranked_daily)
    exact(holdings['SLOW_CONTROL'],ranked_h)
    dump(output/'audit/anchor_rank_control_parity.json',{'status':'PASS','weights_quintiles_daily_PL_bitwise':True,'official':ranked_audit})
    dump(output/'audit/official_accounting_parity.json',{'status':'PASS','strategies':parity})
    results=pd.DataFrame([{'strategy':n,'scope':scope,**metrics(d.loc[ds])} for n,d in daily.items()
        for scope,ds in [('ALL_TRAIN',calendar[:-2])]+scopes(dates)])
    results.to_csv(output/'metrics/metrics.csv',index=False)
    for name,selection in [('overall_metrics',results.scope=='POOLED'),('fold_metrics',results.scope.isin([str(y) for y in range(2011,2017)])),('year_metrics',results.scope.isin([str(y) for y in range(2011,2017)]))]:
        results.loc[selection].to_csv(output/f'metrics/{name}.csv',index=False)
    results[['strategy','scope']+[k for k in results if 'long' in k or 'short' in k]].to_csv(output/'metrics/long_short.csv',index=False)
    results[['strategy','scope']+[k for k in results if k.startswith('q')]].to_csv(output/'metrics/quintiles.csv',index=False)
    increments=[]
    for n,control in [(n,c) for n in fc.CANDIDATES for c in ['SLOW_CONTROL','MOM60']]+[('SLOW_CAUSE_AWARE','SLOW_FUND_EVENT')]:
        for scope in results.scope.unique():
            a=results.loc[(results.strategy==n)&(results.scope==scope)].iloc[0];b=results.loc[(results.strategy==control)&(results.scope==scope)].iloc[0]
            increments.append({'strategy':n,'control':control,'scope':scope,**{'delta_'+k:a[k]-b[k] for k in results if k not in ['strategy','scope']}})
    pd.DataFrame(increments).to_csv(output/'metrics/incremental.csv',index=False)
    boot={}
    for scope,ds in scopes(dates)[:2]:
        for n,b in [('SLOW_CAUSE_AWARE','SLOW_CONTROL'),('SLOW_FUND_EVENT','SLOW_CONTROL'),('SLOW_CAUSE_AWARE','SLOW_FUND_EVENT')]:
            boot[scope+':'+n+'-'+b]={**evaluation.bootstrap_delta(daily[b].loc[ds].net,daily[n].loc[ds].net,**{k:config['bootstrap'][k] for k in ['block','reps','seed']}),
                'point_delta':evaluation.sharpe(daily[n].loc[ds].net)-evaluation.sharpe(daily[b].loc[ds].net),
                'days':len(ds),'primary':scope=='POOLED' and n=='SLOW_CAUSE_AWARE' and b=='SLOW_CONTROL'}
    dump(output/'metrics/bootstrap.json',boot);pd.DataFrame([{'contrast':k,**v} for k,v in boot.items()]).to_csv(output/'metrics/bootstrap.csv',index=False)
    print('2/2 fixed performance trials complete. Diagnostics and attribution only.',flush=True)
    dump(output/'audit/event_study_maturity.json',event_diagnostics(f,target,calendar,config,output/'metrics'))
    dump(output/'audit/cause_state_reconciliation.json',state_diagnostics(f,target,signals,holdings,dates,output/'metrics'))
    dump(output/'audit/turnover_reconciliation.json',turnover_attribution(f,target,holdings,daily,dates,output/'metrics'))
    decision=decide(results,boot);dump(output/'metrics/candidate_decision.json',decision)
    firewall.save(output/'audit/firewall.json')
    assert {Path(p).name for p in firewall.ACCESSES}==set(hashes)
    for p,h in codehash.items():assert sha(ROOT/p)==h,'Code changed after result lock'
    assert sha(slow)==config['slow_control']['sha256']
    assert sha(exp/'plan.md')==prereg['plan_sha256'] and sha(exp/'config.json')==prereg['config_sha256']
    resources={'elapsed_seconds':time.monotonic()-start,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),'actual_trials':2,'valid_evaluation':False}
    dump(output/'audit/resources.json',resources)
    write_report(config,output,results,boot,decision)
    run.update(resources);run.update(status='completed',exit_code=0,completed_at_utc=datetime.now(timezone.utc).isoformat(),candidate_decisions=decision,
        artifact_sha256={str(p.relative_to(output)):sha(p) for folder in ['code','metrics','audit','predictions'] for p in (output/folder).rglob('*') if p.is_file()})
    dump(output/'run.json',run)
    print(json.dumps(safe({'decisions':decision,'resources':resources}),indent=2),flush=True)


def complete_existing(config,output,run,source):
    """Recover report-only failure from immutable scientific results, no scoring."""
    start=time.monotonic();source=Path(source).resolve()
    origin=json.loads((source/'run.json').read_text())
    assert origin['status']=='failed' and origin['actual_trials']==2
    assert 'Train-only parquet guard denied' in origin['error']
    assert sha(source/'config.json')==sha(output/'config.json')
    assert sha(source/'plan.md')==sha(output/'plan.md')
    artifacts=[p for name in ['metrics','predictions'] for p in (source/name).rglob('*.parquet')]
    firewall.install(allowed_artifacts=artifacts)
    for p,h in origin['code_sha256'].items():
        assert sha(source/'code'/p)==h,'Scientific snapshot changed'
        if p.startswith('stock_comp_2026/strategies/'):
            assert sha(ROOT/p)==h,'Prediction code changed'
    required=['contract','prefix_invariance','adapter_parity','standalone_smoke','prediction_source_firewall',
        'purge','anchor_rank_control_parity','official_accounting_parity','event_study_maturity',
        'cause_state_reconciliation','turnover_reconciliation','source_scan']
    for name in required:assert json.loads((source/f'audit/{name}.json').read_text())['status']=='PASS'
    for folder in ['code','metrics','audit','predictions']:
        shutil.copytree(source/folder,output/folder,dirs_exist_ok=True)
    shutil.copyfile(source/'preregistration.json',output/'preregistration.json')
    shutil.copyfile(source/'logs/run.log',output/'logs/scientific_run_failure.log')
    for log in (source/'logs').glob('tests*.log'):shutil.copyfile(log,output/'logs'/log.name)
    completion_code=output/'report_completion_code';completion_code.mkdir()
    shutil.copyfile(Path(__file__),completion_code/Path(__file__).name)
    # Copying our generated parquets is explicit, finite allowlisting, not guard bypass.
    firewall.install(allowed_artifacts=[p for name in ['metrics','predictions'] for p in (output/name).rglob('*.parquet')])
    results=pd.read_csv(output/'metrics/metrics.csv')
    boot=json.loads((output/'metrics/bootstrap.json').read_text())
    decision=json.loads((output/'metrics/candidate_decision.json').read_text())
    assert safe(decide(results,boot))==decision
    dump(output/'audit/report_completion.json',{'status':'PASS','scientific_source_run':str(source.relative_to(ROOT)),
        'source_status':'failed_report_copy_only','prediction_source_unchanged':True,
        'new_performance_trials':0,'actual_unique_performance_trials':2,
        'correction':'Explicit allowlist for four generated diagnostic parquets, report completion from saved metrics. No rerun, no candidate/parameter/feature change.',
        'report_driver_sha256':sha(Path(__file__))})
    write_report(config,output,results,boot,decision)
    resources=json.loads((source/'audit/resources.json').read_text())
    run.update(status='completed',actual_trials=2,new_performance_trials=0,scientific_source_run=str(source.relative_to(ROOT)),
        source_run_manifest_sha256=sha(source/'run.json'),code_sha256=origin['code_sha256'],
        report_completion_code_sha256=sha(Path(__file__)),train_data_sha256=origin['train_data_sha256'],
        environment=origin['environment'],candidate_decisions=decision,command=sys.argv,
        completed_at_utc=datetime.now(timezone.utc).isoformat(),report_completion_seconds=time.monotonic()-start,
        scientific_resources=resources,
        artifact_sha256={str(p.relative_to(output)):sha(p) for folder in ['code','metrics','audit','predictions','report_completion_code']
            for p in (output/folder).rglob('*') if p.is_file()})
    dump(output/'run.json',run)
    print(json.dumps(safe({'decisions':decision,'resources':resources,'new_performance_trials':0}),indent=2),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--complete-from');args=parser.parse_args()
    output=Path(args.output).resolve();config=json.loads(Path(args.config).read_text())
    assert Path(args.config).resolve()==output/'config.json'
    assert config['data_split']=='train' and config['valid_evaluation'] is False and config['max_trials']==2
    assert tuple(x['trial_id'] for x in config['trials'])==fc.CANDIDATES
    assert config['parameters']=={'volume_window':20,'volume_min_periods':20,'sector33_min_finite_members':1,'relisting_gap':20,'weights':[1,1,1],'candidate_smoothing':None}
    assert config['bootstrap']['block']==20 and config['bootstrap']['reps']==2000 and config['bootstrap']['seed']==20261003
    run=json.loads((output/'run.json').read_text());assert run['status']=='prepared'
    try:
        if args.complete_from:complete_existing(config,output,run,args.complete_from)
        else:main_work(config,output,run)
    except BaseException as e:
        run.update(status='failed',exit_code=1,error=f'{type(e).__name__}: {e}',completed_at_utc=datetime.now(timezone.utc).isoformat());dump(output/'run.json',run)
        if firewall._PATCHED:firewall.save(output/'audit/firewall.json')
        raise


if __name__=='__main__':main()
