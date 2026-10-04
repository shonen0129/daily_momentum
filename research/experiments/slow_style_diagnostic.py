"""One frozen Train-only attribution bundle. No candidate/submission output."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import resource
import shutil
import sys
import time
import numpy as np
import pandas as pd
import pyarrow
import scipy
from scipy.stats import spearmanr
from research import evaluation, firewall
from research.experiments import slow_style_descriptors as desc
from research.experiments.slow_multifactor import sha, dump, exact, metrics, table, fold_dates, mutate
from stock_comp_2026.strategies.dm_slow_multifactor import features as slow
from stock_comp_2026 import evaluate_script as official

ROOT = Path(__file__).resolve().parents[2]


def now():
    return datetime.now(timezone.utc).isoformat()


def scopes(dates):
    return [('POOLED', dates), ('EX2016', dates[dates.year != 2016])] + [(str(y), dates[dates.year == y]) for y in range(2011, 2017)]


def source_scan():
    paths = [Path(desc.__file__), ROOT/'stock_comp_2026/strategies/dm_slow_multifactor/features.py']
    problems = []
    for path in paths:
        for n in ast.walk(ast.parse(path.read_text())):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                if any(s in n.value for s in ['target_1day', '_valid.parquet', 'AdjustmentClose', 'AdjustmentVolume', 'AdjustmentOpen']):
                    problems.append([str(path), n.lineno, n.value])
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                if n.func.attr in ['bfill', 'backfill']:
                    problems.append([str(path), n.lineno, n.func.attr])
                for k in n.keywords:
                    if k.arg == 'center' and isinstance(k.value, ast.Constant) and k.value.value is True:
                        problems.append([str(path), n.lineno, 'center'])
                    if k.arg == 'direction' and isinstance(k.value, ast.Constant) and k.value.value != 'backward':
                        problems.append([str(path), n.lineno, 'forward join'])
                if n.func.attr == 'shift':
                    period = n.args[0] if n.args else next((k.value for k in n.keywords if k.arg == 'periods'), None)
                    if not isinstance(period, ast.Constant) or period.value < 0:
                        problems.append([str(path), n.lineno, 'shift'])
    assert not problems, problems
    return {'status':'PASS', 'sources':[str(p.relative_to(ROOT)) for p in paths], 'findings':problems,
            'manual_review':'Targets appear only in return evaluation driver, after frozen target-free descriptors, OLS and matching. Backward joins at same-date EOD; exact annual fiscal intervals/document basis.'}


def descriptor_mutation(frame, cutoff, seed):
    out = frame.copy()
    future = out.index.get_level_values('Date') > cutoff
    rng = np.random.default_rng(seed)
    for col in out:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out.loc[future, col] = out.loc[future, col] + pd.Timedelta(days=100)
        elif pd.api.types.is_numeric_dtype(out[col]):
            val = rng.normal(0, 1e9, int(future.sum())); val[::5] = np.nan; val[1::7] = 0.
            out.loc[future, col] = val
        else:
            out[col] = out[col].astype(object)
            out.loc[future, col] = 'future_changed'
    out = out.drop(out.index[future][::11])
    if future.any():
        extra = out.iloc[-1:].copy()
        extra.index = pd.MultiIndex.from_tuples([(out.index.get_level_values('Date').max()+pd.Timedelta(days=3), '99999')], names=['Date','Code'])
        out = pd.concat([out, extra])
    return out


def audit(inputs, features, raw, z, config):
    idx = features.index
    score = features.size_liquidity.rename('SLOW_CONTROL')
    residual, _ = desc.neutralize(score, z)
    w, _ = evaluation.weights(score)
    matched, _ = desc.matching_weights(w, z.bp, z.sales_growth)
    rows = []
    for i, text in enumerate(config['prefix_cutoffs']):
        cutoff = pd.Timestamp(text); prefix = idx[idx.get_level_values('Date') <= cutoff]
        for source in list(inputs) + ['ALL','TRUNCATION']:
            changed = dict(inputs)
            for j, key in enumerate(inputs):
                if source == 'TRUNCATION':
                    changed[key] = inputs[key].loc[inputs[key].index.get_level_values('Date') <= cutoff]
                elif source in [key,'ALL']:
                    changed[key] = descriptor_mutation(inputs[key], cutoff, config['random_seed']+100*i+j)
            f = slow.build_features(changed, sector=False)
            r, zz, _, _ = desc.build(f.index, changed['prices_daily_quotes'], changed['fins_statements'])
            s = f.size_liquidity.rename('SLOW_CONTROL')
            rr, _ = desc.neutralize(s, zz)
            ww, _ = evaluation.weights(s)
            mm, _ = desc.matching_weights(ww, zz.bp, zz.sales_growth)
            for a,b in [(features,f),(raw,r),(z,zz),(score,s),(residual,rr),(matched,mm)]:
                exact(a.loc[prefix], b.loc[prefix])
            rows.append({'cutoff':text,'source':source,'rows':len(prefix),'status':'PASS','bitwise':True})
        print('causality cutoff',text,'PASS',flush=True)
    shuffled = {k:v.sample(frac=1,random_state=config['random_seed']) for k,v in inputs.items()}
    rebuilt = slow.build_features(shuffled, sector=False)
    rr,zz,_,_ = desc.build(idx,shuffled['prices_daily_quotes'],shuffled['fins_statements'])
    exact(features,rebuilt);exact(raw,rr);exact(z,zz)
    rr,zz,_,_ = desc.build(idx,inputs['prices_daily_quotes'],inputs['fins_statements'])
    exact(raw,rr);exact(z,zz)
    return {'status':'PASS','cases':rows,'row_shuffle':'PASS','deterministic_rebuild':'PASS',
            'exact_index':True,'comparison':'float64 uint64 bits including NaNs, index/columns/dtype',
            'tested_paths':['original SLOW feature/score','all raw/z descriptors','OLS residual score','primary matching weights'],
            'limitations':'Finite tested cutoffs, not universal proof; vendor financial vintage cannot be independently certified. Dates have no intraday disclosure clock.'}


def portfolio(w, q, score, target):
    """Zero weight outside eligible universe; full-panel turnover before purge."""
    gross = w * target
    turn = w.groupby('Code').diff().abs().fillna(w.abs())
    cost_all = .001*turn; cost = cost_all.where(target.notna(),0.)
    h = pd.DataFrame({'w':w,'q':q,'target':target,'gross':gross,'turnover':turn,'cost':cost,'cost_all':cost_all,'net':gross.fillna(0.)-cost})
    d = h[['gross','turnover','cost','cost_all','net']].groupby('Date').sum()
    d['net_all_cost'] = d.gross-d.cost_all
    for side,sleeve in [('long',w.clip(lower=0)),('short',(-w).clip(lower=0))]:
        h[side] = gross.where(w.gt(0) if side=='long' else w.lt(0),0.).fillna(0.)
        h[side+'_turnover'] = sleeve.groupby('Code').diff().abs().fillna(sleeve.abs())
        h[side+'_cost_all'] = .001*h[side+'_turnover']
        h[side+'_cost'] = h[side+'_cost_all'].where(target.notna(),0.)
        h[side+'_net'] = h[side]-h[side+'_cost']
        for suffix in ['', '_turnover','_cost_all','_cost','_net']:
            d[side+suffix] = h[side+suffix].groupby('Date').sum()
    d['rankic'] = evaluation.rankic(score,target)
    d['label_coverage'] = target.where(score.notna()).notna().groupby('Date').sum()/score.notna().groupby('Date').sum()
    for k in range(5):d[f'q{k+1}'] = target.where(q.eq(k)).groupby('Date').mean()
    assert np.allclose(d.long_net+d.short_net,d.net,rtol=0,atol=1e-15)
    return d,h


def score_portfolio(score, target):
    good = score.notna()
    ww,qq = evaluation.weights(score.loc[good])
    w = ww.reindex(target.index,fill_value=0.)
    q = qq.reindex(target.index)
    return portfolio(w,q,score,target)


def characteristics(raw, z, h, dates, folder):
    rows = []
    for scale, frame in [('raw',raw),('z',z)]:
        for c in desc.DESCRIPTORS:
            x = frame[c]; obs=x.notna(); row=pd.DataFrame(index=dates.rename('Date'))
            for side, sleeve in [('long',h.w.clip(lower=0)),('short',(-h.w).clip(lower=0))]:
                mass=sleeve.where(obs,0.).groupby('Date').sum()
                row[side+'_mean']=(sleeve*x).groupby('Date').sum()/mass.where(mass>0)
                row[side+'_weight_coverage']=mass/sleeve.groupby('Date').sum()
            row['spread']=row.long_mean-row.short_mean
            row['coverage']=obs.groupby('Date').mean()
            for q in range(5):row[f'q{q+1}']=x.where(h.q.eq(q)).groupby('Date').mean()
            row['descriptor']=c;row['scale']=scale;rows.append(row.reset_index())
    daily=pd.concat(rows,ignore_index=True)
    daily.to_csv(folder/'daily_characteristics.csv',index=False)
    summary=[]
    for scope,ds in scopes(dates):
        for (c,scale),f in daily.loc[daily.Date.isin(ds)].groupby(['descriptor','scale']):
            v=f.select_dtypes('number').mean().to_dict()
            qs=[v[f'q{k}'] for k in range(1,6)]
            summary.append({'scope':scope,'descriptor':c,'scale':scale,**v,'q_style_monotonicity':spearmanr(range(1,6),qs).statistic})
    result=pd.DataFrame(summary);result.to_csv(folder/'style_profile.csv',index=False)
    return daily,result


def double_sort(score,z,target,dates,folder):
    rows=[]
    for c in desc.DESCRIPTORS:
        bucket=desc.terciles(z[c]);keys=[score.index.get_level_values('Date'),bucket]
        rank=score.where(bucket.notna()).groupby(keys,sort=False).rank(method='average',pct=True)
        q=np.ceil(5*rank).clip(1,5)
        for b in [1,2,3]:
            d=pd.DataFrame(index=dates.rename('Date'))
            for k in range(1,6):
                m=bucket.eq(b)&q.eq(k)
                d[f'q{k}']=target.where(m).groupby('Date').mean()
                d[f'n{k}']=m.groupby('Date').sum()
            d['spread']=d.q5-d.q1;d['descriptor']=c;d['bucket']=b;rows.append(d.reset_index())
    daily=pd.concat(rows,ignore_index=True);daily.to_csv(folder/'daily_double_sort.csv',index=False)
    rows=[]
    for scope,ds in scopes(dates):
        for (c,b),f in daily.loc[daily.Date.isin(ds)].groupby(['descriptor','bucket']):
            sp=f.spread.dropna()
            rows.append({'scope':scope,'descriptor':c,'bucket':b,'days':len(f),'spread_days':len(sp),
                         'mean_spread':sp.mean(),'annual_spread':252*sp.mean(),'spread_t_hac5':evaluation.hac_t(sp),
                         'gross_sharpe_spread':evaluation.sharpe(sp) if len(sp)>1 else np.nan,
                         **{f'q{k}':f[f'q{k}'].mean() for k in range(1,6)}})
    result=pd.DataFrame(rows);result.to_csv(folder/'double_sort.csv',index=False);return result


def matched_value(w, bp):
    # Reuse exactly the fixed cell matcher with a single constant Growth cell.
    return desc.matching_weights(w,bp,pd.Series(0.,index=w.index))[0]


def cohort_attribution(raw,z,features,h,dates,folder):
    values=raw.copy();values['market_cap']=np.exp(-features.raw_size);values['amihud']=features.raw_amihud
    daily=[];distributions=[]
    for c in values:
        x=values[c];bucket=desc.terciles(z[c] if c in z else x).fillna(0.)
        keys=[x.index.get_level_values('Date'),bucket]
        for side,sleeve in [('long',h.w.clip(lower=0)),('short',(-h.w).clip(lower=0))]:
            panel=pd.DataFrame({'weight':sleeve,'stock_days':sleeve.gt(0).astype(int),
                                'gross':h[side],'net':h[side+'_net'],'cost':h[side+'_cost'],'cost_all':h[side+'_cost_all'],
                                'turnover':h[side+'_turnover']})
            f=panel.groupby(keys,sort=True).sum();f.index.names=['Date','bucket'];f=f.reset_index();f=f.loc[f.Date.isin(dates)]
            f['descriptor']=c;f['side']=side;daily.append(f)
            # Distribution over original active stock-days, with absolute book weights.
            for scope,ds in scopes(dates):
                keep=sleeve.gt(0)&x.notna()&x.index.get_level_values('Date').isin(ds)
                a=x.loc[keep].to_numpy();ww=sleeve.loc[keep].to_numpy();order=np.argsort(a,kind='stable')
                a,ww=a[order],ww[order];cum=np.cumsum(ww)
                quant={f'p{int(p*100)}':a[min(np.searchsorted(cum,p*cum[-1]),len(a)-1)] if len(a) else np.nan for p in [.1,.25,.5,.75,.9]}
                distributions.append({'scope':scope,'descriptor':c,'side':side,'observed_stock_days':int(keep.sum()),
                                      'weighted_mean':np.average(a,weights=ww) if len(a) else np.nan,**quant})
    daily=pd.concat(daily,ignore_index=True);daily.to_csv(folder/'daily_cohort_contribution.csv',index=False)
    result=[]
    for scope,ds in scopes(dates):
        for (c,side,b),f in daily.loc[daily.Date.isin(ds)].groupby(['descriptor','side','bucket']):
            result.append({'scope':scope,'descriptor':c,'side':side,'bucket':b,'stock_days':int(f.stock_days.sum()),
                           'average_weight':f.weight.sum()/len(ds),'period_gross':f.gross.sum(),'period_net':f.net.sum(),
                           'annual_gross':252*f.gross.sum()/len(ds),'annual_net':252*f.net.sum()/len(ds),
                           'annual_cost':252*f.cost.sum()/len(ds),'annual_cost_all':252*f.cost_all.sum()/len(ds)})
        for c in values:
            for side in ['long','short']:
                f=daily.loc[daily.Date.isin(ds)&daily.descriptor.eq(c)&daily.side.eq(side)]
                for key in ['gross','net']:
                    expected=h[side if key=='gross' else side+'_net'].loc[h.index.get_level_values('Date').isin(ds)].sum()
                    assert np.isclose(f[key].sum(),expected,atol=1e-12,rtol=0),(scope,c,side,key)
    result=pd.DataFrame(result);result.to_csv(folder/'cohort_contribution.csv',index=False)
    pd.DataFrame(distributions).to_csv(folder/'book_distributions.csv',index=False)
    return result


def regime(z,target,slow_daily,dates,folder):
    factors=pd.DataFrame(index=dates)
    for c,name in [('bp','Value'),('sales_growth','Growth')]:
        b=desc.terciles(z[c])
        factors[name]=target.where(b.eq(3)).groupby('Date').mean()-target.where(b.eq(1)).groupby('Date').mean()
    factors['Growth_minus_Value']=factors.Growth-factors.Value
    factors['SLOW_gross']=slow_daily.gross;factors.to_csv(folder/'daily_style_factors.csv')
    rows=[]
    for scope,ds in scopes(dates):
        for factor in ['Value','Growth','Growth_minus_Value']:
            f=factors.loc[ds,['SLOW_gross',factor]].dropna();xx=np.column_stack([np.ones(len(f)),f[factor]])
            coef,_,_,_=np.linalg.lstsq(xx,f.SLOW_gross,rcond=None)
            prediction=xx@coef
            rows.append({'scope':scope,'factor':factor,'days':len(f),'correlation':f.SLOW_gross.corr(f[factor]),
                         'beta':coef[1],'intercept_daily':coef[0],'intercept_annual':252*coef[0],
                         'r_squared':1-np.sum((f.SLOW_gross-prediction)**2)/np.sum((f.SLOW_gross-f.SLOW_gross.mean())**2),
                         'factor_annual_return':252*f[factor].mean()})
    result=pd.DataFrame(rows);result.to_csv(folder/'regime_factor_ols.csv',index=False);return result


def main_work(config,output,run):
    start=time.monotonic();stage=output/'stage';stage.mkdir()
    keys=list(slow.INPUT_COLUMNS)+['target_1day']
    for key in keys:(stage/(key+'_train.parquet')).symlink_to(ROOT/config['input_dir']/(key+'_train.parquet'))
    ref=ROOT/config['saved_scores']['path']
    own = [output/'metrics'/name for name in ['raw_descriptors.parquet','z_descriptors.parquet',
           'descriptor_ages.parquet','diagnostic_panel.parquet']]
    firewall.install(allowed_artifacts=[ref]+own)
    paths=[Path(__file__),Path(desc.__file__),ROOT/'research/experiments/slow_multifactor.py',ROOT/'research/evaluation.py',ROOT/'research/firewall.py',ROOT/'stock_comp_2026/strategies/dm_slow_multifactor/features.py',ROOT/'stock_comp_2026/evaluate_script.py']
    run.update(status='running',started_at_utc=now(),command=sys.argv,code_sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},
               train_data_sha256={k+'_train.parquet':sha(stage/(k+'_train.parquet')) for k in keys if k != 'target_1day'},
               environment={'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,'pyarrow':pyarrow.__version__,'scipy':scipy.__version__,'platform':platform.platform()},
               actual_trials=0,diagnostic_bundles=1)
    dump(output/'run.json',run)
    for path in paths:
        dest=output/'code_snapshot'/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
    assert sha(ref)==config['saved_scores']['sha256']
    dump(output/'audit/config_freeze.json',{'config_sha256':sha(output/'config.json'),'plan_sha256':sha(output/'plan.md'),
         'schema_sha256':config['schema_audit_sha256'],'code_sha256':run['code_sha256'],'target_read':False,'performance_candidates':0})
    dump(output/'audit/source_scan.json',source_scan())
    inputs={k:slow.canonical(pd.read_parquet(stage/(k+'_train.parquet'),columns=desc.FIN_COLUMNS if k=='fins_statements' else cols)) for k,cols in slow.INPUT_COLUMNS.items()}
    f=slow.build_features(inputs,sector=False);score=f.size_liquidity.rename('SLOW_CONTROL');idx=f.index
    saved=pd.read_parquet(ref,columns=config['saved_scores']['columns']).sort_index()
    exact(score,saved.SLOW_CONTROL)
    raw,z,ages,pairs=desc.build(idx,inputs['prices_daily_quotes'],inputs['fins_statements'])
    assert raw.index.equals(idx) and z.index.equals(idx)
    dump(output/'audit/slow_parity.json',{'status':'PASS','saved_score_bits':True,'rows':len(idx),'reference_sha256':sha(ref)})
    raw.to_parquet(output/'metrics/raw_descriptors.parquet');z.to_parquet(output/'metrics/z_descriptors.parquet')
    ages.to_parquet(output/'metrics/descriptor_ages.parquet');pairs.to_csv(output/'audit/annual_growth_pairs.csv',index=False)
    dump(output/'audit/prefix_invariance.json',audit(inputs,f,raw,z,config))
    residual,coefficients=desc.neutralize(score,z);coefficients.to_csv(output/'metrics/daily_neutralization_ols.csv')
    ww,qq=evaluation.weights(score)
    mw,cells=desc.matching_weights(ww,z.bp,z.sales_growth)
    vw=matched_value(ww,z.bp)
    # Exact cell-side equality is mathematical; summation tolerance is explicit.
    gap=(mw.clip(lower=0)-(-mw).clip(lower=0)).groupby([mw.index.get_level_values('Date'),cells]).sum().abs().max()
    assert gap<1e-14,gap
    dump(output/'audit/matching.json',{'status':'PASS','max_cell_side_weight_gap':gap,'tolerance':1e-14,'optimization':False,
         'daily_cash_days':int(mw.abs().groupby('Date').sum().eq(0).sum()),'bp_growth_grid':'3x3','primary_value':'bp','primary_growth':'sales_growth'})
    assert not any('target_1day' in p for p in firewall.ACCESSES),'target opened before descriptors frozen'
    dump(output/'audit/target_free_build.json',{'status':'PASS','opened_before_returns':sorted(firewall.ACCESSES),
         'descriptors_ols_and_matching_complete':True,'no_return_selection':True})
    target=slow.canonical(pd.read_parquet(stage/'target_1day_train.parquet')).Return
    run['train_data_sha256']['target_1day_train.parquet']=sha(stage/'target_1day_train.parquet')
    assert target.index.equals(idx)
    calendar=pd.DatetimeIndex(idx.get_level_values('Date').unique());dates,purge=fold_dates(calendar,range(2011,2017))
    dates=dates.rename('Date')
    dump(output/'audit/purge.json',purge)
    accounts={};holdings={}
    accounts['SLOW_CONTROL'],holdings['SLOW_CONTROL']=portfolio(ww,qq,score,target)
    ow=official.compute_weight(score.rename('Return').to_frame()).iloc[:,0];exact(ww.rename('w'),ow.rename('w'))
    onet=official.compute_pl(score.rename('Return').to_frame(),target.to_frame()).groupby('Date').sum()
    exact(accounts['SLOW_CONTROL'].net.rename('net'),onet.rename('net'))
    accounts['MOM60'],holdings['MOM60']=score_portfolio(saved.MOM60,target)
    common=score.where(residual.notna())
    accounts['SLOW_COMMON_SUPPORT'],holdings['SLOW_COMMON_SUPPORT']=score_portfolio(common,target)
    accounts['STYLE_NEUTRAL_RESIDUAL'],holdings['STYLE_NEUTRAL_RESIDUAL']=score_portfolio(residual,target)
    accounts['STYLE_MATCHED_SLOW'],holdings['STYLE_MATCHED_SLOW']=portfolio(mw,qq.where(mw.ne(0)),score.where(mw.ne(0)),target)
    accounts['VALUE_MATCHED_SLOW'],holdings['VALUE_MATCHED_SLOW']=portfolio(vw,qq.where(vw.ne(0)),score.where(vw.ne(0)),target)
    # Save target-free diagnostic scores/weights in metrics, never submission API.
    pd.DataFrame({'SLOW_CONTROL':score,'residual_score':residual,'matched_weight':mw,'value_matched_weight':vw,'common_support':common}).to_parquet(output/'metrics/diagnostic_panel.parquet')
    rows=[]
    for name,d in accounts.items():
        d.loc[dates].to_csv(output/f'metrics/daily_{name}.csv')
        for scope,ds in scopes(dates):rows.append({'diagnostic':name,'scope':scope,**metrics(d.loc[ds])})
    result=pd.DataFrame(rows);result.to_csv(output/'metrics/portfolio_metrics.csv',index=False)
    delta=[]
    for _,row in result.iterrows():
        for base in ['SLOW_CONTROL','MOM60']+(['SLOW_COMMON_SUPPORT'] if row.diagnostic=='STYLE_NEUTRAL_RESIDUAL' else []):
            b=result.loc[result.diagnostic.eq(base)&result.scope.eq(row.scope)].iloc[0]
            delta.append({'diagnostic':row.diagnostic,'baseline':base,'scope':row.scope,
                          **{'delta_'+k:row[k]-b[k] for k in ['rankic','net_sharpe','gross_sharpe','turnover','annual_cost']}})
    pd.DataFrame(delta).to_csv(output/'metrics/incremental.csv',index=False)
    daily,profile=characteristics(raw,z,holdings['SLOW_CONTROL'],dates,output/'metrics')
    ds=double_sort(score,z,target,dates,output/'metrics')
    cohorts=cohort_attribution(raw,z,f,holdings['SLOW_CONTROL'],dates,output/'metrics')
    reg=regime(z,target,accounts['SLOW_CONTROL'],dates,output/'metrics')
    coverage=[]
    for scope,days in scopes(dates):
        mask=idx.get_level_values('Date').isin(days)
        for c in desc.DESCRIPTORS:
            coverage.append({'scope':scope,'descriptor':c,'stock_days':int(mask.sum()),'finite_raw':int(raw.loc[mask,c].notna().sum()),
                             'finite_z':int(z.loc[mask,c].notna().sum()),'coverage':raw.loc[mask,c].notna().mean()})
        coverage.append({'scope':scope,'descriptor':'OLS_COMMON_SUPPORT','stock_days':int(mask.sum()),
                         'finite_raw':int(residual.loc[mask].notna().sum()),'finite_z':int(residual.loc[mask].notna().sum()),'coverage':residual.loc[mask].notna().mean()})
    pd.DataFrame(coverage).to_csv(output/'metrics/descriptor_coverage.csv',index=False)
    ages.loc[idx.get_level_values('Date').isin(dates)].describe().to_csv(output/'metrics/disclosure_age_summary.csv')
    fin=inputs['fins_statements'];pr=inputs['prices_daily_quotes']
    # Actions are diagnostic input only; never alter raw levels or frozen SLOW.
    actions=slow.canonical(pd.read_parquet(stage/'prices_daily_quotes_train.parquet',columns=['AdjustmentFactor'])).reindex(idx)
    split=actions.AdjustmentFactor.notna()&actions.AdjustmentFactor.ne(1)&actions.AdjustmentFactor.gt(0)
    split.reindex(idx).to_frame('corporate_action_observed').loc[split].to_csv(output/'audit/corporate_action_dates.csv')
    dump(output/'audit/corporate_action_limits.json',{'action_stock_days':int(split.sum()),'adjustments_to_SLOW_or_descriptors':False,
         'limitations':['last disclosed shares may lag splits/issuance; includes treasury stock','forecast EPS may use future/old share basis; no retrospective correction','Profit/Equity and CFO/Assets use FY reports only, not average capital or annual forecasts','B/P fields may have different disclosure vintages','annual growth covers positive prior denominators only; loss-to-profit transitions missing','sales growth is realized sales, not a market Growth classification','vendor revisions and historic coverage cannot be independently certified from Date-only rows']})
    dump(output/'audit/coverage.json',{'status':'PASS','full_index':len(idx),'SLOW_finite':int(score.notna().sum()),
         'original_score_weight_net_bitwise':True,'descriptors_missing_preserved':True,'common_support_saved':True,
         'cohort_account_reconciliation_atol':1e-12,'no_prediction_submission':True})
    firewall.save(output/'audit/firewall.json')
    resources={'elapsed_seconds':time.monotonic()-start,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    dump(output/'audit/resources.json',resources)
    report=ROOT/config['report_dir'];report.mkdir(exist_ok=False)
    shutil.copytree(output/'metrics',report/'metrics');shutil.copytree(output/'audit',report/'audit')
    # The interpretive report is written from this fixed bundle after completion.
    run.update(status='completed',completed_at_utc=now(),exit_code=0,actual_trials=0,diagnostic_bundles=1,resources=resources,
               artifact_sha256={str(p.relative_to(output)):sha(p) for p in list((output/'metrics').glob('*'))+list((output/'audit').glob('*')) if p.is_file()})
    dump(output/'run.json',run)
    print('DIAGNOSTIC COMPLETE',resources,flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    output=Path(args.output).resolve();config=json.loads(Path(args.config).read_text());run=json.loads((output/'run.json').read_text())
    assert config['diagnostic_only'] and config['data_split']=='train' and not config['valid_evaluation']
    assert config['parameters']['descriptors']==desc.DESCRIPTORS and config['performance_trial_budget']==0
    assert run['status']=='prepared' and sha(args.config)==run['snapshot_sha256']['config.json']
    try:main_work(config,output,run)
    except BaseException as error:
        run.update(status='failed',completed_at_utc=now(),exit_code=1,error=repr(error));dump(output/'run.json',run)
        if firewall._PATCHED:firewall.save(output/'audit/firewall.json')
        raise


if __name__=='__main__':main()
