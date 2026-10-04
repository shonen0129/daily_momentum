"""Checkpointed, preregistered conditional RM Train-only research bundle."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import time
import traceback
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pyarrow
import scipy
from scipy.stats import rankdata, ConstantInputWarning, norm

from research import evaluation, firewall
from research.experiments import slow_mom60_equal as prior, slow_multifactor as shared
from research.experiments import slow_rm_descriptors as descriptors, slow_rm_statistics as stats
from stock_comp_2026.strategies.dm_slow_rm_confirm import features as f
from stock_comp_2026 import evaluate_script as official

ROOT = Path(__file__).resolve().parents[2]
sha, dump, exact = shared.sha, shared.dump, shared.exact
CAND = 'SLOW_RM_CONFIRM'


def now():
    return datetime.now(timezone.utc).isoformat()


class Phases:
    def __init__(self, output, run):
        self.output, self.run = output, run
        self.records = run.setdefault('phases', [])

    def run_phase(self, name, function):
        if any(r['phase'] == name and r['status'] == 'PASS' for r in self.records):
            print('reuse verified phase '+name, flush=True)
            return
        started = time.monotonic()
        before = {str(p.relative_to(self.output)): sha(p) for folder in ('predictions','metrics','audit','models')
                  for p in (self.output/folder).rglob('*') if p.is_file()}
        function()
        # Register only artifacts generated in this run before hashing them.
        firewall.install(allowed_artifacts=[p for folder in ('predictions','metrics','models')
                                           for p in (self.output/folder).rglob('*.parquet')])
        after = {str(p.relative_to(self.output)): sha(p) for folder in ('predictions','metrics','audit','models')
                 for p in (self.output/folder).rglob('*') if p.is_file() and p.name != 'phases.json'}
        hashes = {k:v for k,v in after.items() if before.get(k) != v}
        self.records.append({'phase':name, 'status':'PASS', 'at_utc':now(),
                             'elapsed_seconds':time.monotonic()-started, 'sha256':hashes})
        dump(self.output/'audit/phases.json', self.records)
        dump(self.output/'run.json', self.run)
        print(f'phase {name} PASS {self.records[-1]["elapsed_seconds"]:.2f}s', flush=True)


def partition(panel, target, label, label_name, dates, folder, bins=3):
    """Within-date fixed group RM bins and full official SLOW contributions."""
    keys = [panel.index.get_level_values('Date'), label]
    rank_bin = f.bins(panel.RM, bins, keys)
    w = panel.slow_w
    turn = w.groupby('Code').diff().abs().fillna(w.abs())
    cost = (.001*turn).where(target.notna(), 0.)
    frame = pd.DataFrame({'group':label,'rm_bin':rank_bin,'target':target,'w':w,
                           'gross':(w*target).fillna(0.),'cost':cost,'turnover':turn},index=panel.index)
    frame['net'] = frame.gross - frame.cost
    frame.loc[frame.index.get_level_values('Date').isin(dates)].to_parquet(folder/f'{label_name}_stock_days.parquet')
    rows = []
    daily = frame.groupby(['Date','group','rm_bin']).agg(
        stock_days=('w','size'), active_stock_days=('w',lambda x:(x!=0).sum()),
        average_slow_weight=('w','mean'), forward_target=('target','mean'),
        gross=('gross','sum'),net=('net','sum'),cost=('cost','sum'),turnover=('turnover','sum'))
    daily.to_csv(folder/f'{label_name}_daily.csv')
    for scope, ds in stats.scopes(dates):
        sub = daily.loc[daily.index.get_level_values('Date').isin(ds)]
        for (group, rm_bin), g in sub.groupby(['group','rm_bin']):
            summed = g[['gross','net','cost','turnover']].groupby('Date').sum().reindex(ds,fill_value=0.)
            rows.append({'scope':scope,'group':group,'rm_bin':rm_bin,
                         'stock_days':g.stock_days.sum(),'active_stock_days':g.active_stock_days.sum(),
                         'average_slow_weight':np.average(g.average_slow_weight,weights=g.stock_days),
                         'forward_target':g.forward_target.mean(),
                         'annual_gross_contribution':summed.gross.mean()*252,
                         'annual_net_contribution':summed.net.mean()*252,
                         'annual_cost_contribution':summed.cost.mean()*252,
                         'turnover_contribution':summed.turnover.mean()})
    pd.DataFrame(rows).to_csv(folder/f'{label_name}_summary.csv',index=False)
    # Includes neutral exits; exact daily sums reconciled with all-position attribution.
    for measure in ('gross','net','cost','turnover'):
        assert np.allclose(daily[measure].groupby('Date').sum(),frame[measure].groupby('Date').sum(),atol=1e-15,rtol=0)


def boundary(panel, target, dates, folder):
    rows = []
    for date, g in panel.loc[panel.index.get_level_values('Date').isin(dates)].groupby('Date',sort=False):
        for boundary_name in ('nearest','20','40','60','80'):
            distance = g.boundary_distance if boundary_name=='nearest' else g['distance_'+boundary_name]
            for band in (.025,.05,.10):
                mask = distance <= band
                t=target.reindex(g.index).to_numpy()[mask]
                spread,ic=stats.batch_stat(g.RM.to_numpy()[mask],t)
                rows.append({'Date':date,'boundary':boundary_name,'band':band,'stocks':int(mask.sum()),
                             'spread':spread[0],'rankic':ic[0]})
    daily=pd.DataFrame(rows);daily.to_csv(folder/'boundary_daily.csv',index=False)
    result=[]
    for (bound,band),g in daily.groupby(['boundary','band']):
        for scope,ds in stats.scopes(dates):
            v=g.loc[g.Date.isin(ds)]
            result.append({'boundary':bound,'band':band,'scope':scope,'average_stocks':v.stocks.mean(),
                           'spread':v.spread.mean(),'spread_hac5_t':evaluation.hac_t(v.spread),
                           'rankic':v.rankic.mean(),'rankic_hac5_t':evaluation.hac_t(v.rankic)})
    pd.DataFrame(result).to_csv(folder/'boundary_summary.csv',index=False)


def persistence(panel,dates,folder):
    daily=pd.DataFrame(index=dates)
    for lag in (1,5,10,20):
        daily[f'rm_rank_autocorrelation_lag{lag}']=evaluation.rankic(panel.RM,panel[f'RM_lag{lag}']).reindex(dates)
    for col in ('RM_abs_change','SLOW_RANK_abs_change','boundary_crossing','quintile_crossing'):
        daily[col]=panel[col].groupby('Date').mean().reindex(dates)
    daily.to_csv(folder/'persistence_daily.csv',index_label='Date')
    rows=[]
    for scope,ds in stats.scopes(dates):
        g=daily.loc[ds]
        rows.append({'scope':scope,**g.mean().to_dict(),
                     'rm_change_slow_change_correlation':g.RM_abs_change.corr(g.SLOW_RANK_abs_change),
                     'rm_change_boundary_crossing_correlation':g.RM_abs_change.corr(g.boundary_crossing),
                     'rm_change_quintile_crossing_correlation':g.RM_abs_change.corr(g.quintile_crossing)})
    pd.DataFrame(rows).to_csv(folder/'persistence_summary.csv',index=False)
    stock=panel.loc[panel.index.get_level_values('Date').isin(dates),['RM_abs_change','SLOW_RANK_abs_change','boundary_crossing','quintile_crossing']].copy()
    stock['rm_change_bin']=f.bins(stock.RM_abs_change,5)
    stock.reset_index().groupby('rm_change_bin').agg(
        stock_days=('Code','size'),rm_abs_change=('RM_abs_change','mean'),
        slow_abs_change=('SLOW_RANK_abs_change','mean'),boundary_crossing=('boundary_crossing','mean'),
        quintile_crossing=('quintile_crossing','mean')).to_csv(folder/'persistence_change_relationship.csv')


def regime(daily,state,folder):
    primary=daily.loc[daily.variant=='RM'].copy()
    primary['half_year']=primary.Date.dt.year.astype(str)+'H'+np.where(primary.Date.dt.month<=6,'1','2')
    rows=[]
    for (group,half),g in primary.groupby(['group','half_year']):
        rows.append({'group':group,'regime':'half_year','state':half,'days':len(g),
                     'spread':g.spread.mean(),'rankic':g.rankic.mean(),'spread_hac5_t':evaluation.hac_t(g.spread)})
    for col in ('market_high_vol','market_positive_trend'):
        primary[col]=state[col].reindex(primary.Date).to_numpy()
        for (group,value),g in primary.groupby(['group',col]):
            rows.append({'group':group,'regime':col,'state':str(value),'days':len(g),
                         'spread':g.spread.mean(),'rankic':g.rankic.mean(),'spread_hac5_t':evaluation.hac_t(g.spread)})
    pd.DataFrame(rows).to_csv(folder/'regime_summary.csv',index=False)
    rolling=[]
    for group,g in primary.groupby('group',sort=False):
        v=g.set_index('Date')[['spread','rankic']].rolling(252,min_periods=252).mean()
        rolling.append(v.reset_index().assign(group=group))
    pd.concat(rolling).to_csv(folder/'rolling252.csv',index=False)


def permutations(panel,target,dates,output,config):
    """All 2000 draws shared across primary and complete3x3/5x5 surfaces."""
    folder=output/'metrics';reps=config['reps'];ng=len(stats.GROUPS)
    path=folder/'permutation_daily_draws.dat'
    progress=output/'audit/permutation_progress.json'
    done=0
    mode='w+'
    if progress.exists():
        receipt=json.loads(progress.read_text());done=receipt['completed_dates'];mode='r+'
        assert receipt['config']==config and receipt['shape']==[len(dates),reps,ng,2]
        assert path.stat().st_size==len(dates)*reps*ng*2*8
        assert sha(path)==receipt['partial_sha256']
    data=np.memmap(path,dtype='float64',mode=mode,shape=(len(dates),reps,ng,2))
    groups=dict(tuple(panel.loc[panel.index.get_level_values('Date').isin(dates)].groupby('Date',sort=False)))
    for i,date in enumerate(dates):
        if i<done:continue
        g=groups[date];x=g.RM.to_numpy();y=target.reindex(g.index).to_numpy()
        rng=np.random.default_rng(np.random.SeedSequence([config['seed'],i]))
        perm=np.broadcast_to(x,(reps,len(x))).copy()
        for cell in range(1,10):
            positions=np.flatnonzero(g.cell3.to_numpy()==cell)
            if len(positions):
                # Independent random keys yield uniform permutations inside each fixed cell.
                order=np.argsort(rng.random((reps,len(positions))),axis=1,kind='stable')
                perm[:,positions]=x[positions][order]
        for j,mask in enumerate(stats.group_masks(g)):
            spread,ic=stats.batch_stat(perm[:,mask],y[mask])
            data[i,:,j,0]=spread;data[i,:,j,1]=ic
        if (i+1)%100==0 or i+1==len(dates):
            data.flush()
            dump(progress,{'completed_dates':i+1,'total_dates':len(dates),'config':config,
                           'shape':list(data.shape),'partial_sha256':sha(path),
                           'seed_derivation':'SeedSequence([permutation seed, eligible date ordinal])'})
            print(f'permutation checkpoint {i+1}/{len(dates)} dates, reps{reps}',flush=True)
    observed=pd.read_csv(folder/'diagnostic_summary.csv')
    rows=[];surface=[];draw_tables=[]
    for scope,ds in stats.scopes(dates)[:2]:
        positions=dates.get_indexer(ds)
        for j,group in enumerate(stats.GROUPS):
            o=observed.loc[(observed.variant=='RM')&(observed.group==group)&(observed.scope==scope)].iloc[0]
            for k,metric in enumerate(('spread','rankic')):
                values=np.asarray(data[positions,:,j,k])
                means=np.nanmean(values,axis=0)
                rows.append({'scope':scope,'group':group,'metric':metric,'observed':o[metric],
                             'null_mean':np.nanmean(means),'null_low':np.nanquantile(means,.025),
                             'null_high':np.nanquantile(means,.975),
                             'p_positive':(1+np.sum(means>=o[metric]))/(1+reps),
                             'p_two_sided':(1+np.sum(np.abs(means)>=abs(o[metric])))/(1+reps),
                             'reps':reps,'seed':config['seed']})
                draw_tables.append(pd.DataFrame({'scope':scope,'group':group,'metric':metric,
                                                'draw':np.arange(reps),'statistic':means}))
        for n in (3,5):
            maxstat=np.zeros(reps)
            individual=[]
            for cell in range(1,n*n+1):
                group=f'CELL{n}_{cell}';j=stats.GROUPS.index(group)
                ts=stats.hac_batch(np.asarray(data[positions,:,j,0]).T)
                maxstat=np.maximum(maxstat,np.nan_to_num(np.abs(ts),nan=0.))
                individual.append((group,ts))
            pd.DataFrame({'draw':np.arange(reps),'max_abs_hac5_t':maxstat}).to_csv(folder/f'maxstat_{scope}_{n}x{n}_draws.csv',index=False)
            for group,ts in individual:
                t=float(observed.loc[(observed.variant=='RM')&(observed.group==group)&(observed.scope==scope),'spread_hac5_t'].iloc[0])
                surface.append({'scope':scope,'surface':f'{n}x{n}','group':group,'observed_hac5_t':t,
                                'maxstat_adjusted_p':(1+np.sum(maxstat>=abs(t)))/(1+reps) if np.isfinite(t) else np.nan,
                                'null_maxstat95':np.quantile(maxstat,.95),'reps':reps})
    pd.DataFrame(rows).to_csv(folder/'permutation_summary.csv',index=False)
    pd.concat(draw_tables).to_parquet(folder/'permutation_pooled_draws.parquet',index=False)
    pd.DataFrame(surface).to_csv(folder/'surface_maxstat.csv',index=False)
    del data


def circular(panel,target,dates,folder,config):
    rows=[];daily=[]
    for offset in config['circular_offsets']:
        shifted=panel.RM.groupby('Code',sort=False).transform(lambda x:np.roll(x.to_numpy(),offset))
        for date,g in panel.loc[panel.index.get_level_values('Date').isin(dates)].groupby('Date',sort=False):
            x=shifted.reindex(g.index).to_numpy();y=target.reindex(g.index).to_numpy()
            for group,mask in zip(stats.GROUPS,stats.group_masks(g)):
                spread,ic=stats.batch_stat(x[mask],y[mask])
                daily.append({'offset':offset,'Date':date,'group':group,'spread':spread[0],'rankic':ic[0]})
    d=pd.DataFrame(daily);d.to_csv(folder/'circular_placebo_daily.csv',index=False)
    for (offset,group),g in d.groupby(['offset','group']):
        for scope,ds in stats.scopes(dates):
            sub=g.loc[g.Date.isin(ds)]
            rows.append({'offset':offset,'group':group,'scope':scope,'spread':sub.spread.mean(),
                         'rankic':sub.rankic.mean(),'spread_hac5_t':evaluation.hac_t(sub.spread)})
    pd.DataFrame(rows).to_csv(folder/'circular_placebo_summary.csv',index=False)


def gate(summary,boot,config):
    checks={};evidence={}
    def value(group,scope,variant='RM'):
        return summary.loc[(summary.group==group)&(summary.scope==scope)&(summary.variant==variant)].iloc[0]
    for group in ('LONG','SHORT','CELL3_9'):
        for scope in ('POOLED','EX2016'):
            v=value(group,scope)
            checks[f'{group}_{scope}_positive']=bool(v.spread>0)
            evidence[f'{group}_{scope}_spread']=v.spread
        positives=int(value(group,'POOLED').positive_full_years)
        checks[f'{group}_positive_years_ge4']=positives>=4
        evidence[f'{group}_positive_full_years']=positives
        if group!='CELL3_9':
            low=float(boot.loc[(boot.scope=='POOLED')&(boot.estimand==group)&(boot.block==20),'low'].iloc[0])
            checks[f'{group}_bootstrap_lower_positive']=low>0
            evidence[f'{group}_bootstrap_lower']=low
        for variant in config['robustness_variants']:
            for scope in config['scopes']:
                checks[f'robustness_{group}_{variant}_{scope}']=bool(value(group,scope,variant).spread>0)
    return {'all_passed':all(checks.values()),'checks':checks,'evidence':evidence,
            'candidate_performance_trials_allowed':int(all(checks.values())),
            'primary_hypotheses':3,'rescue_trials':0,'no_secondary_cell_selection':True}


def causality(inputs,scores,mid,panel,coeff,state,config,folder):
    cases=[]
    for i,date in enumerate(config['prefix_cutoffs']):
        cutoff=pd.Timestamp(date);prefix=panel.index[panel.index.get_level_values('Date')<=cutoff]
        for source in list(inputs)+['ALL','TRUNCATION']:
            changed=dict(inputs)
            for j,(name,frame) in enumerate(inputs.items()):
                if source=='TRUNCATION':changed[name]=frame.loc[prior.source_dates(frame)<=cutoff]
                elif source in (name,'ALL'):changed[name]=prior.mutate(frame,name,cutoff,config['random_seed']+i*100+j)
            got,inter=f.components(changed)
            desc,c,st=descriptors.describe(got,changed['topix_return_1day'])
            exact(scores.loc[prefix],got.loc[prefix])
            prior.stored_raw_parity(mid.loc[prefix],inter.loc[prefix])
            exact(panel.loc[prefix],desc.loc[prefix])
            exact(coeff.loc[coeff.index<=cutoff],c.loc[c.index<=cutoff])
            exact(state.loc[state.index<=cutoff],st.loc[st.index<=cutoff])
            exact(f.score(panel).loc[prefix],f.score(desc).loc[prefix])
            cases.append({'cutoff':date,'source':source,'rows':len(prefix),'status':'PASS','bitwise':True})
        dump(folder/'prefix_progress.json',{'status':'running','cases':cases})
        print('RM causality '+date+' each input/ALL/truncation PASS',flush=True)
    for source,changed in [('ROW_SHUFFLE',{k:v.sample(frac=1,random_state=config['random_seed']) for k,v in inputs.items()}),('DETERMINISTIC_REBUILD',inputs)]:
        got,inter=f.components(changed);desc,c,st=descriptors.describe(got,changed['topix_return_1day'])
        exact(scores,got);prior.stored_raw_parity(mid,inter);exact(panel,desc);exact(coeff,c);exact(state,st);exact(f.score(panel),f.score(desc))
        cases.append({'source':source,'rows':len(panel),'status':'PASS','bitwise':True})
    return {'status':'PASS','cases':cases,'all_input_sources':list(inputs),'target_argument':False,
            'scope':'Components, all residual ranks/bins, transitions, boundaries, lag descriptors, past-only regimes, fixed score; exact index/dtype/finite bits and canonical missing positions.',
            'limitations':'Tests prove observed inputs/cutoffs only; stored raw NaN payload cannot survive parquet null serialization. No new return learning.'}


def candidate_work(panel,target,dates,output,config,run):
    if not json.loads((output/'audit/candidate_gate.json').read_text())['all_passed']:
        dump(output/'audit/candidate_accounting.json',{'status':'SKIPPED','reason':'Fixed diagnostic gate failed','candidate_trials':0,'rescue_trials':0})
        return
    run['actual_trials']=1;dump(output/'run.json',run)
    books={CAND:f.score(panel), 'SLOW_CONTROL':pd.read_parquet(output/'predictions/component_scores.parquet').SLOW_CONTROL}
    component=pd.read_parquet(output/'predictions/component_scores.parquet')
    books['MOM60']=component.MOM60;books['SLOW_MOM60_EQUAL']=f.factors.score(component)
    accounts={};holdings={};receipts={}
    for name,score in books.items():
        accounts[name],receipts[name]=prior.account(score.rename('Return'),target)
        holdings[name]=prior.holdings(score,target)
        accounts[name].to_csv(output/f'metrics/daily_{name}.csv',index_label='Date')
    result=pd.DataFrame([{'strategy':name,'scope':scope,**shared.metrics(d.loc[ds])} for name,d in accounts.items() for scope,ds in stats.scopes(dates)])
    result.to_csv(output/'metrics/candidate_metrics.csv',index=False)
    increments=[]
    for scope,_ in stats.scopes(dates):
        c=result.loc[(result.strategy==CAND)&(result.scope==scope)].iloc[0]
        for base in ('SLOW_CONTROL','MOM60','SLOW_MOM60_EQUAL'):
            b=result.loc[(result.strategy==base)&(result.scope==scope)].iloc[0]
            increments.append({'scope':scope,'comparison':CAND+'-'+base,**{'delta_'+col:c[col]-b[col] for col in result if col not in ('strategy','scope')}})
    pd.DataFrame(increments).to_csv(output/'metrics/candidate_incremental.csv',index=False)
    stress=[]
    for name,d in accounts.items():
        for bp in config['cost_stress_bps']:
            for scope,ds in stats.scopes(dates):
                z=d.loc[ds].copy();z['net']=z.gross-z.cost*bp/10
                stress.append({'strategy':name,'cost_bps':bp,'scope':scope,'net_sharpe':evaluation.sharpe(z.net),'annual_net':z.net.mean()*252,'annual_cost':z.cost.mean()*bp/10*252})
    pd.DataFrame(stress).to_csv(output/'metrics/cost_stress.csv',index=False)
    c,s=holdings[CAND],holdings['SLOW_CONTROL']
    masks=[(c.w*s.w>0),(c.w>0)&(s.w<=0),(s.w>0)&(c.w<=0),(c.w<0)&(s.w>=0),(s.w<0)&(c.w>=0)]
    # Flips need two signed sleeves; partition positive and negative delta separately.
    rows=[]
    for scope,ds in stats.scopes(dates):
        ix=c.index.get_level_values('Date').isin(ds)
        for side in ('long','short'):
            cw=c.w.clip(lower=0) if side=='long' else c.w.clip(upper=0)
            sw=s.w.clip(lower=0) if side=='long' else s.w.clip(upper=0)
            ct=cw.groupby('Code').diff().abs().fillna(cw.abs());st=sw.groupby('Code').diff().abs().fillna(sw.abs())
            gross=((cw-sw)*target).fillna(0.);cost=(.001*(ct-st)).where(target.notna(),0.)
            group=np.select([(cw!=0)&(sw!=0),(cw!=0)&(sw==0),(cw==0)&(sw!=0)],['common_holdings',side+'_additions',side+'_removals'],default='neutral_changes')
            for label in np.unique(group):
                mask=ix&(group==label)
                rows.append({'scope':scope,'group':label,'side':side,'stock_days':int(mask.sum()),
                             'annual_gross_delta':gross.loc[mask].sum()/len(ds)*252,
                             'annual_cost_delta':cost.loc[mask].sum()/len(ds)*252,
                             'annual_net_delta':(gross-cost).loc[mask].sum()/len(ds)*252})
    attr=pd.DataFrame(rows);attr.to_csv(output/'metrics/candidate_attribution.csv',index=False)
    for scope,ds in stats.scopes(dates):
        a=attr.loc[attr.scope==scope]
        for col in ('gross','cost','net'):
            assert np.isclose(a['annual_'+col+'_delta'].sum(),(accounts[CAND].loc[ds,col]-accounts['SLOW_CONTROL'].loc[ds,col]).mean()*252,atol=1e-13,rtol=0)
    bcfg=config['candidate_bootstrap'];brows=[];boot={}
    for scope,ds in stats.scopes(dates)[:2]:
        b,c=accounts['SLOW_CONTROL'].loc[ds],accounts[CAND].loc[ds]
        rng=np.random.default_rng(bcfg['seed']);block=bcfg['block'];reps=bcfg['reps']
        starts=rng.integers(0,len(ds),(reps,int(np.ceil(len(ds)/block))))
        ix=((starts[:,:,None]+np.arange(block))%len(ds)).reshape(reps,-1)[:,:len(ds)]
        draws={}
        for metric in ('net','gross'):
            cb,bb=c[metric].to_numpy()[ix],b[metric].to_numpy()[ix]
            draws['delta_'+metric+'_sharpe']=np.sqrt(252)*(cb.mean(1)/cb.std(1,ddof=1)-bb.mean(1)/bb.std(1,ddof=1))
            if metric=='net':draws['delta_annual_net']=(cb-bb).mean(1)*252
        def dd(a):
            w=np.cumprod(1+a,axis=1);peak=np.maximum.accumulate(np.column_stack([np.ones(len(a)),w]),axis=1)[:,1:]
            return (w/peak-1).min(1)
        draws['delta_maxdd_descriptive']=dd(c.net.to_numpy()[ix])-dd(b.net.to_numpy()[ix])
        pd.DataFrame(draws).to_parquet(output/f'metrics/candidate_bootstrap_{scope}_draws.parquet')
        for name,d in draws.items():
            brows.append({'scope':scope,'estimand':name,'low':np.quantile(d,.025),'high':np.quantile(d,.975),'seed':bcfg['seed'],'block':block,'reps':reps})
        boot[scope+':'+CAND+'-SLOW_CONTROL']={'low':np.quantile(draws['delta_net_sharpe'],.025)}
    pd.DataFrame(brows).to_csv(output/'metrics/candidate_bootstrap.csv',index=False)
    # Reuse existing exact adoption conjunction, passing fixed candidate identity.
    previous_candidate=prior.CAND
    try:
        prior.CAND=CAND;decision=prior.decision(result,boot)
    finally:prior.CAND=previous_candidate
    dump(output/'audit/candidate_adoption.json',decision)
    dump(output/'audit/candidate_accounting.json',{'status':'PASS','official_bitwise':receipts,'attribution_reconciled':True,'candidate_trials':1,'rescue_trials':0})


def audited_permutation_table(original):
    """An undefined observed statistic cannot have a numerical permutation p."""
    result=original.copy()
    undefined=~np.isfinite(result.observed)
    result.loc[undefined,['p_positive','p_two_sided']]=np.nan
    return result


def main_work(config,output,run):
    from research.experiments.slow_rm_report import report
    started=time.monotonic();phase=Phases(output,run)
    refs={k:ROOT/v['path'] for k,v in config['saved_components'].items()}
    for k,path in refs.items():assert sha(path)==config['saved_components'][k]['sha256'],k
    paths=sorted((ROOT/'stock_comp_2026/strategies'/config['strategy']).rglob('*.py'))
    code=paths+[Path(__file__),Path(descriptors.__file__),Path(stats.__file__),ROOT/'research/experiments/slow_rm_report.py',
                Path(prior.__file__),Path(shared.__file__),Path(evaluation.__file__),Path(firewall.__file__),ROOT/'stock_comp_2026/evaluate_script.py']
    code+=sorted((ROOT/'tests/strategies'/config['strategy']).rglob('*.py'))
    stage=output/'stage';stage.mkdir(exist_ok=True)
    for name in f.INPUT_COLUMNS:
        p=stage/(name+'_train.parquet')
        if not p.exists():p.symlink_to(ROOT/config['input_dir']/p.name)
    run.update(status='running',command=sys.argv,actual_trials=run.get('actual_trials') or 0,
               environment={'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__,'pyarrow':pyarrow.__version__,'platform':platform.platform()})
    def freeze():
        run['code_sha256']={str(p.relative_to(ROOT)):sha(p) for p in code}
        run['train_data_sha256']={name+'_train.parquet':sha(ROOT/config['input_dir']/(name+'_train.parquet')) for name in list(f.INPUT_COLUMNS)+['target_1day']}
        for p in code:
            dst=output/'code_snapshot'/p.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
        dump(output/'audit/pre_result_lock.json',{'at_utc':now(),'target_parsed':False,'config_sha256':sha(output/'config.json'),'plan_sha256':sha(output/'plan.md'),'code_sha256':run['code_sha256'],'input_sha256':run['train_data_sha256'],'primary_hypotheses':config['primary_hypotheses'],'max_candidate_trials':1,'rescue_trials':0})
    phase.run_phase('freeze',freeze)
    allowed=list(refs.values())+[output/f'predictions/{name}.parquet' for name in ('component_scores','intermediates','panel','coefficients','market_states','fixed_score')]
    allowed+=list((output/'metrics').glob('*.parquet'))
    firewall.install(allowed_artifacts=allowed)
    inputs=f.load_train(stage);inputs={k:v.sort_index() for k,v in inputs.items()}
    def component_parity():
        scores,mid=f.components(inputs)
        old=pd.read_parquet(refs['slow_features'],columns=config['saved_components']['slow_features']['columns'])
        raw=prior.stored_raw_parity(mid[['raw_size','raw_amihud']],old[['raw_size','raw_amihud']])
        exact(mid[['z_size','z_amihud','size_liquidity']],old[['z_size','z_amihud','size_liquidity']])
        exact(scores,pd.read_parquet(refs['component_scores']))
        prior.stored_raw_parity(mid,pd.read_parquet(refs['intermediates']))
        exact(scores.MOM60.rename('Return'),pd.read_parquet(refs['frozen_momentum']).Return)
        frozen_source=ROOT/'releases/DM-20260908-v1/snapshot/stock_comp_2026/strategies/dm_trainonly/features.py'
        functions=prior.function_sources(frozen_source);copied=prior.function_sources(Path(f.factors.momentum.__file__))
        for name in ('build_momentum','centered_rank','segment_keys','smooth'):assert functions[name]==copied[name]
        assert Path(f.factors.slow.__file__).read_bytes()==(ROOT/'stock_comp_2026/strategies/dm_slow_multifactor/features.py').read_bytes()
        assert scores.index.equals(inputs['raw_return_1day'].index) and np.isfinite(scores.to_numpy()).all()
        scores.to_parquet(output/'predictions/component_scores.parquet');mid.to_parquet(output/'predictions/intermediates.parquet')
        dump(output/'audit/component_parity.json',{'status':'PASS','rows':len(scores),'raw_storage':raw,'normalized_size_illiq_slow_bits':True,'mom_pre_and_final_bits':True,'frozen_mom_bits':True,'frozen_functions_identical':True,'slow_module_identical':True})
    phase.run_phase('component_parity',component_parity)
    scores=pd.read_parquet(output/'predictions/component_scores.parquet');mid=pd.read_parquet(output/'predictions/intermediates.parquet')
    def rm_build():
        panel,coeff,state=descriptors.describe(scores,inputs['topix_return_1day'])
        fixed=f.score(panel)
        assert panel.index.equals(scores.index) and np.isfinite(panel[['RM','RM_SLOW','RM_CELL3','RM_CELL5']].to_numpy()).all()
        assert np.isfinite(fixed.to_numpy()).all()
        panel.to_parquet(output/'predictions/panel.parquet');coeff.to_parquet(output/'predictions/coefficients.parquet');state.to_parquet(output/'predictions/market_states.parquet');fixed.to_frame().to_parquet(output/'predictions/fixed_score.parquet')
        dump(output/'audit/target_free_build.json',{'status':'PASS','feature_accesses':sorted(firewall.ACCESSES),'target_parsed_before_build':False,'rows':len(panel),'score_coverage':1.,'candidate_formula_constructed_without_performance_evaluation':True})
        assert not any('target_1day' in p for p in firewall.ACCESSES)
    phase.run_phase('RM_construction',rm_build)
    panel=pd.read_parquet(output/'predictions/panel.parquet');coeff=pd.read_parquet(output/'predictions/coefficients.parquet');state=pd.read_parquet(output/'predictions/market_states.parquet')
    p=stage/'target_1day_train.parquet'
    if not p.exists():p.symlink_to(ROOT/config['input_dir']/p.name)
    target=pd.read_parquet(p).Return.sort_index();assert target.index.equals(scores.index)
    calendar=scores.index.get_level_values('Date').unique().sort_values()
    dates=prior.maturity(inputs,target,calendar,output/'audit')
    def accounting_parity():
        receipts={}
        for name in ('SLOW_CONTROL','MOM60'):
            daily,receipts[name]=prior.account(scores[name].rename('Return'),target)
            previous=pd.read_csv(refs['daily_'+name],index_col='Date',parse_dates=True,float_precision='round_trip')
            exact(daily.net,previous.net)
            daily.to_csv(output/f'metrics/daily_{name}.csv',index_label='Date')
        dump(output/'audit/accounting_parity.json',{'status':'PASS','receipts':receipts,'saved_daily_net_bits':True,'official_weight_bits':True})
    phase.run_phase('official_component_accounting_parity',accounting_parity)
    def diagnostic_phase():
        daily=stats.observed(panel,target,dates);daily.to_parquet(output/'metrics/diagnostics_daily.parquet');daily.to_csv(output/'metrics/diagnostics_daily.csv',index=False)
        stats.summary(daily).to_csv(output/'metrics/diagnostic_summary.csv',index=False)
    phase.run_phase('unconditional_SLOW_conditional_surfaces',diagnostic_phase)
    firewall.install(allowed_artifacts=[output/'metrics/diagnostics_daily.parquet'])
    daily=pd.read_parquet(output/'metrics/diagnostics_daily.parquet')
    summary=pd.read_csv(output/'metrics/diagnostic_summary.csv')
    def surfaces():
        surfaces=summary.loc[(summary.variant=='RM')&summary.group.str.startswith('CELL')]
        surfaces.to_csv(output/'metrics/surface_summary.csv',index=False)
        rows=[]
        for n in (3,5):
            v=surfaces.loc[(surfaces.scope=='POOLED')&surfaces.group.str.startswith(f'CELL{n}_')].copy()
            v['cell']=v.group.str.split('_').str[-1].astype(int);v['size']=(v.cell-1)//n+1;v['illiq']=(v.cell-1)%n+1
            for metric in ('spread','rankic','average_stock_count','target_mean','slow_average_weight','annual_slow_gross_contribution'):
                grid=v.pivot(index='size',columns='illiq',values=metric)
                grid.to_csv(output/f'metrics/heatmap_{n}x{n}_{metric}.csv')
                if metric=='spread':
                    a=grid.to_numpy();rows.append({'surface':f'{n}x{n}','positive_cell_fraction':(a>0).mean(),
                                                   'size_adjacent_positive_fraction':(np.diff(a,axis=0)>0).mean(),
                                                   'illiq_adjacent_positive_fraction':(np.diff(a,axis=1)>0).mean(),
                                                   'size_edge_spread_delta':np.nanmean(a[-1]-a[0]),
                                                   'illiq_edge_spread_delta':np.nanmean(a[:,-1]-a[:,0])})
        pd.DataFrame(rows).to_csv(output/'metrics/surface_smoothness.csv',index=False)
    phase.run_phase('all3x3_5x5_heatmaps_support_sign_stability',surfaces)
    side=np.select([panel.slow_q>=4,panel.slow_q<=2],['Long','Short'],default='Neutral')
    phase.run_phase('Long_Short_asymmetry',lambda:partition(panel,target,pd.Series(side,index=panel.index),'side',dates,output/'metrics',5))
    transition=panel.transition.map(descriptors.TRANSITIONS)
    phase.run_phase('transition_boundary',lambda:(partition(panel,target,transition,'transition',dates,output/'metrics'),boundary(panel,target,dates,output/'metrics')))
    phase.run_phase('persistence',lambda:persistence(panel,dates,output/'metrics'))
    phase.run_phase('regime_stability',lambda:regime(daily,state,output/'metrics'))
    phase.run_phase('permutation2000_surface_maxstat',lambda:permutations(panel,target,dates,output,config['permutation']))
    phase.run_phase('circular_shift_placebo',lambda:circular(panel,target,dates,output/'metrics',config['permutation']))
    def bootstrap_fdr():
        boot=stats.bootstrap(daily,config['bootstrap'],output/'metrics');boot.to_csv(output/'metrics/bootstrap.csv',index=False)
        p=pd.read_csv(output/'metrics/permutation_summary.csv');selected=p.loc[p.group.str.startswith('CELL')].copy()
        selected['family']=selected.group.str.split('_').str[0]
        selected['bh_fdr']=selected.groupby(['scope','family','metric']).p_two_sided.transform(stats.bh)
        selected.to_csv(output/'metrics/FDR_permutation.csv',index=False)
        asymptotic=summary.loc[(summary.variant=='RM')&summary.group.str.startswith('CELL')].copy()
        asymptotic['p_two_sided_hac_normal']=2*norm.sf(asymptotic.spread_hac5_t.abs())
        asymptotic['family']=asymptotic.group.str.split('_').str[0]
        asymptotic['bh_fdr_hac']=asymptotic.groupby(['scope','family']).p_two_sided_hac_normal.transform(stats.bh)
        asymptotic.to_csv(output/'metrics/FDR_hac_descriptive.csv',index=False)
        dump(output/'audit/statistical_audit.json',{'primary_hypotheses':config['primary_hypotheses'],'number_primary':3,'number_group_descriptors':len(stats.GROUPS),'variants':stats.VARIANTS,'secondary_scope_families':'3x3/5x5 separately, each scope, each spread/IC metric; BH descriptive','permutation':config['permutation'],'bootstrap':config['bootstrap'],'draws_used_for_parameter_selection':False})
    phase.run_phase('bootstrap5000_FDR',bootstrap_fdr)
    boot=pd.read_csv(output/'metrics/bootstrap.csv')
    phase.run_phase('candidate_gate',lambda:dump(output/'audit/candidate_gate.json',gate(summary,boot,config['gate'])))
    phase.run_phase('conditional_one_candidate_cost_attribution_bootstrap',lambda:candidate_work(panel,target,dates,output,config,run))
    phase.run_phase('causality_audit',lambda:dump(output/'audit/prefix_invariance.json',causality(inputs,scores,mid,panel,coeff,state,config,output/'audit')))
    def verification():
        result=prior.source_scan(paths)
        result['descriptor_manual_review']='Fixed positive lags1/5/10/20 on exchange grid; prior-date transitions; expanding median lag1; same-day cross-sectional bins/ranks. No target argument.'
        result['descriptor_sha256']=sha(Path(descriptors.__file__))
        dump(output/'audit/source_scan.json',result)
        denied=[]
        for filename in ('target_1day_valid.parquet','raw_target_1day_train.parquet'):
            try:pd.read_parquet(ROOT/config['input_dir']/filename)
            except PermissionError:denied.append(filename)
        assert len(denied)==2;dump(output/'audit/firewall_denials.json',{'status':'PASS','denied':denied})
        result={}
        for name,cmd in [('related_tests',[str(ROOT/'.venv/bin/python'),'tools/run_bounded.py','--seconds','180',str(ROOT/'.venv/bin/python'),'-m','pytest','-q','tests/strategies/dm_slow_rm_confirm','tests/strategies/dm_slow_mom60_equal','tests/strategies/dm_slow_multifactor']),('make_check',['make','check'])]:
            proc=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=240)
            (output/f'logs/{name}.log').write_text(proc.stdout);result[name]={'exit_code':proc.returncode,'log':f'logs/{name}.log'}
            if name=='related_tests':assert proc.returncode==0,proc.stdout
        from tools import workspace
        workspace.validate_experiment(ROOT,ROOT/'experiments'/config['experiment_id'])
        result['new_metadata_valid']=True
        meta=json.loads((ROOT/'experiments/DM-20260908/experiment.json').read_text())
        frozen_root=ROOT/meta['freeze_root']
        manifest=ROOT/meta['freeze_manifest']
        assert sha(manifest)==meta['freeze_manifest_sha256']
        assert sha(frozen_root/meta['freeze_manifest'])==meta['freeze_manifest_sha256']
        frozen=json.loads(manifest.read_text());checked=0
        firewall.install(allowed_artifacts=[frozen_root/rel for section in ('code_sha256','artifact_sha256')
                                           for rel in frozen[section] if rel.endswith('.parquet')])
        for section in ('code_sha256','artifact_sha256'):
            for rel,h in frozen[section].items():
                assert sha(frozen_root/rel)==h,rel
                checked+=1
        result['existing_freeze_hashes_verified']=checked
        dump(output/'audit/verification.json',result)
    phase.run_phase('source_firewall_contract_regression',verification)
    def benchmark():
        featstage=output/'feature_stage';featstage.mkdir()
        for name in f.INPUT_COLUMNS:(featstage/(name+'_train.parquet')).symlink_to(ROOT/config['input_dir']/(name+'_train.parquet'))
        cmd=[str(ROOT/'.venv/bin/python'),'-m','research.experiments.slow_rm_bundle','--benchmark','--config',str(output/'config.json'),'--output',str(output)]
        proc=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=300)
        (output/'logs/submission_benchmark.log').write_text(proc.stdout+proc.stderr);assert proc.returncode==0,proc.stderr
    phase.run_phase('separate_submission_inference_benchmark',benchmark)
    def statistical_output_validation():
        original=pd.read_csv(output/'metrics/permutation_summary.csv')
        audited=audited_permutation_table(original)
        audited.to_csv(output/'metrics/permutation_summary_audited.csv',index=False)
        cells=audited.loc[audited.group.str.startswith('CELL')].copy()
        cells['family']=cells.group.str.split('_').str[0]
        cells['bh_fdr']=cells.groupby(['scope','family','metric']).p_two_sided.transform(stats.bh)
        cells.to_csv(output/'metrics/FDR_permutation_audited.csv',index=False)
        missing=audited.observed.isna()
        assert audited.loc[missing,['p_positive','p_two_sided']].isna().all().all()
        assert cells.loc[cells.observed.isna(),'bh_fdr'].isna().all()
        maxstat=pd.read_csv(output/'metrics/surface_maxstat.csv')
        assert maxstat.loc[maxstat.observed_hac5_t.isna(),'maxstat_adjusted_p'].isna().all()
        dump(output/'audit/statistical_output_validation.json',{
            'status':'PASS','undefined_observed_rows':int(missing.sum()),
            'corrected_rows':original.loc[missing,['scope','group','metric','observed','p_two_sided']].to_dict('records'),
            'original_outputs_preserved':True,
            'reason':'Support-insufficient cells without defined statistics must retain NaN p-values and be excluded from BH denominators',
            'strategy_or_config_changes':False,'permutation_bootstrap_or_performance_reruns':0,
            'use_audited_outputs':['permutation_summary_audited.csv','FDR_permutation_audited.csv']})
    phase.run_phase('statistical_output_validation',statistical_output_validation)
    firewall.save(output/'audit/firewall.json')
    run.update(status='completed',exit_code=0,completed_at_utc=now())
    report(config,output,run,started)
    run['output_sha256']={str(p.relative_to(output)):sha(p) for folder in ('predictions','metrics','audit','models') for p in (output/folder).rglob('*') if p.is_file()}
    dump(output/'run.json',run)
    print('FINAL '+str(ROOT/config['report_dir']/'REPORT.md'),flush=True)


def main():
    from research.experiments.slow_rm_report import report
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('--output',required=True);parser.add_argument('--resume-from');parser.add_argument('--benchmark',action='store_true')
    args=parser.parse_args();output=Path(args.output).resolve();config=json.loads(Path(args.config).read_text())
    if args.benchmark:
        firewall.install(allowed_artifacts=[output/'predictions/fixed_score.parquet'])
        from stock_comp_2026.strategies.dm_slow_rm_confirm import submission
        started=time.monotonic();got=submission.predict(output/'feature_stage');elapsed=time.monotonic()-started
        exact(got,pd.read_parquet(output/'predictions/fixed_score.parquet'))
        assert not any('target_1day' in x for x in firewall.ACCESSES)
        dump(output/'audit/submission_benchmark.json',{'status':'PASS','elapsed_seconds':elapsed,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'rows':len(got),'target_free_stage':True,'bitwise_research_inference':True,'candidate_performance_trial':False})
        return
    run=json.loads((output/'run.json').read_text())
    assert run['status']=='prepared' and config['data_split']=='train' and config['valid_evaluation'] is False
    assert config['max_trials']==1 and config['permutation']['reps']==2000 and config['bootstrap']['reps']==5000
    warnings.filterwarnings('ignore',category=ConstantInputWarning)
    started=time.monotonic()
    if args.resume_from:
        source=Path(args.resume_from).resolve();old=json.loads((source/'run.json').read_text())
        assert sha(output/'config.json')==sha(source/'config.json') and sha(output/'plan.md')==sha(source/'plan.md')
        for filename,h in old.get('train_data_sha256',{}).items():
            assert filename.endswith('_train.parquet') and 'raw_target' not in filename
            assert sha(ROOT/config['input_dir']/filename)==h,('resume input changed',filename)
        for record in old.get('phases',[]):
            for rel,h in record['sha256'].items():assert sha(source/rel)==h,(record['phase'],rel)
        for folder in ('predictions','metrics','audit','models'):
            shutil.copytree(source/folder,output/folder,dirs_exist_ok=True)
        # Keep original log paths reviewable without replacing this run's log.
        shutil.copytree(source/'logs',output/'logs'/source.name,dirs_exist_ok=False)
        run.update(phases=old.get('phases',[]),actual_trials=old.get('actual_trials',0),resume_source=str(source.relative_to(ROOT)),original_code_sha256=old.get('code_sha256'),technical_failure=old.get('failure'),code_sha256=old.get('code_sha256'),train_data_sha256=old.get('train_data_sha256'))
        dump(output/'audit/resume_provenance.json',{'source_run':str(source.relative_to(ROOT)),'source_run_sha256':sha(source/'run.json'),'same_config_plan':True,'completed_phase_hashes_verified':True,'outcomes_retained':True,'strategy_definition_unchanged':True})
        current={}
        for rel,h in old.get('code_sha256',{}).items():
            if (rel.startswith('stock_comp_2026/strategies/')
                    or rel.endswith(('slow_rm_statistics.py','slow_rm_descriptors.py','evaluation.py',
                                     'slow_multifactor.py','slow_mom60_equal.py','firewall.py','evaluate_script.py'))):
                assert sha(ROOT/rel)==h,('definition changed',rel)
            current[rel]=sha(ROOT/rel)
        run['completion_code_sha256']=current
        for rel in current:
            dst=output/'completion_code_snapshot'/rel
            dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/rel,dst)
        # The initial technical failure occurred after the diagnostic function
        # finished, while hashing. Preserve these fully saved outcomes.
        if old.get('failure')=="PermissionError('Train-only parquet guard denied diagnostics_daily.parquet')":
            recovered=['metrics/diagnostics_daily.parquet','metrics/diagnostics_daily.csv','metrics/diagnostic_summary.csv']
            assert all((source/p).is_file() for p in recovered)
            assert all(sha(source/p)==sha(output/p) for p in recovered)
            records=run['phases']
            records.append({'phase':'unconditional_SLOW_conditional_surfaces','status':'PASS',
                            'at_utc':now(),'elapsed_seconds':0.,
                            'sha256':{p:sha(output/p) for p in recovered},
                            'recovered_saved_results':True,'source_run':str(source.relative_to(ROOT)),
                            'reason':'Function completed and saved all outputs; traceback stopped only in post-function checkpoint hashing'})
            dump(output/'audit/recovered_diagnostic_phase.json',records[-1])
    try:main_work(config,output,run)
    except BaseException as error:
        run.update(status='failed',exit_code=1,completed_at_utc=now(),failure=repr(error),failure_traceback=traceback.format_exc(),peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        dump(output/'run.json',run)
        if firewall._PATCHED:firewall.save(output/'audit/firewall.json')
        report(config,output,run,started,failed=repr(error))
        raise


if __name__=='__main__':main()
