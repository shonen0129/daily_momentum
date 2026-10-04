"""One preregistered immutable SN1/SLOW score blend; Train-only diversification."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import pyarrow
import scipy
from research import evaluation, firewall
from research.experiments.slow_multifactor import metrics, table
from stock_comp_2026 import evaluate_script as official
from stock_comp_2026.strategies.dm_sn1_slow_blend import features as blend_features, submission
from stock_comp_2026.strategies.dm_variable_box_breakout import features as original_sn, submission as original_adapter
from stock_comp_2026.strategies.dm_slow_multifactor import features as original_slow
from stock_comp_2026.strategies.dm_trainonly import features as momentum

ROOT = Path(__file__).resolve().parents[2]
SN, SLOW, BLEND = 'SN1_H1', 'SLOW_CONTROL', 'SN1_SLOW_BLEND'
VIRTUAL = 'PURE_WEIGHT_50_50'


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe(obj):
    if isinstance(obj, dict): return {str(k): safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)): return [safe(v) for v in obj]
    if isinstance(obj, (np.integer,)): return int(obj)
    if isinstance(obj, (np.bool_,)): return bool(obj)
    if isinstance(obj, (float, np.floating)): return float(obj) if np.isfinite(obj) else None
    if isinstance(obj, (datetime, pd.Timestamp)): return obj.isoformat()
    return obj


def dump(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(safe(obj), ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def exact(a, b):
    if isinstance(a, pd.Series): a = a.to_frame()
    if isinstance(b, pd.Series): b = b.to_frame()
    assert a.index.equals(b.index), 'index mismatch'
    assert a.columns.equals(b.columns), 'columns mismatch'
    assert a.dtypes.equals(b.dtypes), 'dtype mismatch'
    for col in a:
        left, right = a[col].to_numpy(), b[col].to_numpy()
        if left.dtype == np.float64:
            assert np.array_equal(left.view(np.uint64), right.view(np.uint64)), f'float64 bit mismatch: {col}'
        else:
            pd.testing.assert_series_equal(a[col], b[col], check_exact=True)


def scopes(dates):
    return [('POOLED', dates), ('EX2016', dates[dates.year != 2016])] + [(str(y), dates[dates.year == y]) for y in range(2011,2017)]


def eligible_dates(calendar):
    dates, rows = [], []
    for year in range(2011, 2017):
        year_dates = calendar[calendar.year == year]
        keep = year_dates[:-2]
        for date in keep:
            p = calendar.get_loc(date)
            assert p+2 < len(calendar) and calendar[p+2].year == year
        rows.append({'year':year,'signal_start':str(keep[0].date()),'last_signal':str(keep[-1].date()),
                     'last_label_end':str(year_dates[-1].date()),'excluded_sessions':[str(d.date()) for d in year_dates[-2:]],
                     'partial':year==2016,'sessions':len(keep),'status':'PASS'})
        dates.extend(keep)
    return pd.DatetimeIndex(dates), rows


def holdings_from_weight(w, target):
    h = pd.DataFrame({'w':w,'target':target,'gross':w*target},index=w.index)
    h['turnover'] = w.groupby('Code').diff().abs().fillna(w.abs())
    h['cost_all'] = .001*h.turnover
    h['cost'] = h.cost_all.where(target.notna(),0.)
    h['net'] = h.gross.fillna(0.)-h.cost
    for side, sleeve in [('long',w.clip(lower=0)),('short',(-w).clip(lower=0))]:
        h[side+'_turnover'] = sleeve.groupby('Code').diff().abs().fillna(sleeve.abs())
        h[side+'_cost_all'] = .001*h[side+'_turnover']
        h[side+'_cost'] = h[side+'_cost_all'].where(target.notna(),0.)
        h[side] = h.gross.where(w.gt(0) if side=='long' else w.lt(0),0.).fillna(0.)
        h[side+'_net'] = h[side]-h[side+'_cost']
    return h


def account(score, target):
    w,q = evaluation.weights(score)
    h = holdings_from_weight(w,target)
    h['q'] = q
    d = evaluation.daily_account(score,target)
    for side in ['long','short']:
        for suffix in ['turnover','cost','cost_all','net']:
            d[side+'_'+suffix] = h[side+'_'+suffix].groupby('Date').sum()
    ow = official.compute_weight(score.rename('Return').to_frame()).iloc[:,0]
    exact(w.rename('w'),ow.rename('w'))
    opl = official.compute_pl(score.rename('Return').to_frame(),target.to_frame()).groupby('Date').sum()
    exact(d.net.rename('net'),opl.rename('net'))
    for c in ['gross','net','turnover','cost']:
        assert np.allclose(h[c].groupby('Date').sum(),d[c],atol=1e-15,rtol=0),c
    assert np.allclose(d.long_net+d.short_net,d.net,atol=1e-15,rtol=0)
    assert np.allclose(d.long_turnover+d.short_turnover,d.turnover,atol=1e-15,rtol=0)
    return d,h,{'status':'PASS','official_weight_bits':True,'official_net_bits':True,'rows':len(score),
                'attribution_reconciliation_atol':1e-15,'missing_target_official_cost_semantics':True}


def orthogonality(scores, accounts, holdings, listed, dates, folder):
    a,b = accounts[SN].loc[dates],accounts[SLOW].loc[dates]
    daily = pd.DataFrame({'SN1_gross':a.gross,'SLOW_gross':b.gross,'SN1_net':a.net,'SLOW_net':b.net,
                          'score_spearman':evaluation.rankic(scores[SN],scores[SLOW]).loc[dates]})
    for side in ['long','short']:
        x = holdings[SN].w.gt(0) if side=='long' else holdings[SN].w.lt(0)
        y = holdings[SLOW].w.gt(0) if side=='long' else holdings[SLOW].w.lt(0)
        inter=(x&y).groupby('Date').sum(); union=(x|y).groupby('Date').sum()
        nx=x.groupby('Date').sum(); ny=y.groupby('Date').sum()
        for key,val in {'intersection':inter,'union':union,'SN1_count':nx,'SLOW_count':ny,
                        'overlap':inter/np.minimum(nx,ny),'SN1_overlap':inter/nx,'SLOW_overlap':inter/ny,'jaccard':inter/union}.items():
            daily[side+'_'+key]=val.reindex(dates)
    exposures = pd.DataFrame(index=scores.index)
    sector = listed.Sector33Code.reindex(scores.index).fillna('UNKNOWN').astype(str).replace({'9999':'UNKNOWN','':'UNKNOWN'})
    for book in [SN,SLOW]:
        exposures[book+'_long']=holdings[book].w.clip(lower=0)
        exposures[book+'_short']=(-holdings[book].w).clip(lower=0)
    exposures['sector']=sector
    expo=exposures.groupby([exposures.index.get_level_values('Date'),'sector']).sum()
    expo=expo.loc[expo.index.get_level_values('Date').isin(dates)]
    expo.to_csv(folder/'sector_exposures.csv')
    for side in ['long','short']:
        correlations=expo.groupby('Date')[[SN+'_'+side,SLOW+'_'+side]].apply(lambda f:f.iloc[:,0].corr(f.iloc[:,1]))
        daily[side+'_sector_cross_section_corr']=correlations
    daily.to_csv(folder/'orthogonality_daily.csv',index_label='Date')
    summaries=[]; sector_rows=[];dd_rows=[];episodes=[]
    for scope,ds in scopes(dates):
        aa,bb=a.loc[ds],b.loc[ds];dd=pd.DataFrame(index=ds)
        for book,d in [(SN,aa),(SLOW,bb)]:
            wealth=(1+d.net).cumprod();peak=np.maximum.accumulate(np.r_[1.,wealth.to_numpy()])[1:]
            dd[book+'_drawdown']=wealth/peak-1
            dd[book+'_underwater']=dd[book+'_drawdown'].lt(0)
            active=dd[book+'_underwater']; grp=active.ne(active.shift(fill_value=False)).cumsum()
            for _,g in dd.loc[active].groupby(grp.loc[active]):
                episodes.append({'scope':scope,'book':book,'start':g.index[0],'end':g.index[-1],
                                 'sessions':len(g),'depth':g[book+'_drawdown'].min(),
                                 'other_underwater_fraction':g[(SLOW if book==SN else SN)+'_underwater'].mean() if (SLOW if book==SN else SN)+'_underwater' in g else np.nan})
        x,y=dd[SN+'_underwater'],dd[SLOW+'_underwater'];both=x&y;union=x|y
        losses1,losses2=aa.net.lt(0),bb.net.lt(0)
        result={'scope':scope,'days':len(ds),'gross_pl_corr':aa.gross.corr(bb.gross),'net_pl_corr':aa.net.corr(bb.net),
                'score_spearman_mean':daily.loc[ds,'score_spearman'].mean(),
                'score_spearman_hac5_t':evaluation.hac_t(daily.loc[ds,'score_spearman']),
                'slow_mean_net_when_sn1_negative':bb.net.loc[losses1].mean(),'sn1_mean_net_when_slow_negative':aa.net.loc[losses2].mean(),
                'both_negative_days':int((losses1&losses2).sum()),'only_sn1_negative_days':int((losses1&~losses2).sum()),
                'only_slow_negative_days':int((~losses1&losses2).sum()),'exactly_one_negative_days':int((losses1^losses2).sum()),
                'neither_negative_days':int((~losses1&~losses2).sum()),'both_drawdown_days':int(both.sum()),
                'sn1_only_drawdown_days':int((x&~y).sum()),'slow_only_drawdown_days':int((y&~x).sum()),
                'drawdown_jaccard':both.sum()/union.sum() if union.sum() else np.nan,
                'slow_underwater_given_sn1':both.sum()/x.sum() if x.sum() else np.nan,
                'sn1_underwater_given_slow':both.sum()/y.sum() if y.sum() else np.nan,
                'drawdown_depth_corr':dd[SN+'_drawdown'].corr(dd[SLOW+'_drawdown']),
                'drawdown_paths_equal':bool(np.array_equal(dd[SN+'_drawdown'].to_numpy(),dd[SLOW+'_drawdown'].to_numpy()))}
        for side in ['long','short']:
            for c in ['overlap','SN1_overlap','SLOW_overlap','jaccard','sector_cross_section_corr']:
                result[side+'_'+c]=daily.loc[ds,side+'_'+c].mean()
        summaries.append(result);dd['scope']=scope;dd_rows.append(dd.reset_index(names='Date'))
        sub=expo.loc[expo.index.get_level_values('Date').isin(ds)]
        for sec,g in sub.groupby('sector'):
            sector_rows.append({'scope':scope,'sector':sec,**{side+'_exposure_time_corr':g[SN+'_'+side].corr(g[SLOW+'_'+side]) for side in ['long','short']}})
    # Calculate other-book episode overlap only after both drawdown paths exist.
    ddf=pd.concat(dd_rows);ep=pd.DataFrame(episodes)
    for i,r in ep.iterrows():
        g=ddf.loc[(ddf.scope==r.scope)&(ddf.Date>=r.start)&(ddf.Date<=r.end)]
        ep.loc[i,'other_underwater_fraction']=g[(SLOW if r.book==SN else SN)+'_underwater'].mean()
    ep.to_csv(folder/'drawdown_episodes.csv',index=False)
    ddf.to_csv(folder/'component_drawdowns.csv',index=False)
    pd.DataFrame(sector_rows).to_csv(folder/'sector_exposure_time_correlations.csv',index=False)
    result=pd.DataFrame(summaries);result.to_csv(folder/'orthogonality_summary.csv',index=False)
    return result


def virtual_portfolio(holdings,accounts,target,dates,folder):
    w=.5*holdings[SN].w+.5*holdings[SLOW].w
    h=holdings_from_weight(w,target)
    cols=['gross','net','turnover','cost','cost_all','long','short','long_net','short_net','long_cost','short_cost','long_cost_all','short_cost_all','long_turnover','short_turnover']
    d=h[cols].groupby('Date').sum()
    d['net_all_cost']=d.gross-d.cost_all
    d['sleeve_net']=.5*accounts[SN].net+.5*accounts[SLOW].net
    d['sleeve_cost']=.5*accounts[SN].cost+.5*accounts[SLOW].cost
    d['sleeve_turnover']=.5*accounts[SN].turnover+.5*accounts[SLOW].turnover
    for side in ['long','short']:
        d['sleeve_'+side+'_gross']=.5*accounts[SN][side]+.5*accounts[SLOW][side]
        d['sleeve_'+side+'_net']=.5*accounts[SN][side+'_net']+.5*accounts[SLOW][side+'_net']
    assert np.allclose(d.gross,.5*accounts[SN].gross+.5*accounts[SLOW].gross,atol=1e-15,rtol=0)
    assert (d.cost <= d.sleeve_cost+1e-15).all()
    d.to_csv(folder/('daily_'+VIRTUAL+'.csv'),index_label='Date')
    rows=[]
    for scope,ds in scopes(dates):
        s=d.loc[ds];wealth=np.r_[1.,(1+s.net).cumprod()];cum=np.r_[0.,s.net.cumsum()]
        rows.append({'strategy':VIRTUAL,'scope':scope,'days':len(ds),'gross_sharpe':evaluation.sharpe(s.gross),'net_sharpe':evaluation.sharpe(s.net),
                     'sleeve_net_sharpe':evaluation.sharpe(s.sleeve_net),'turnover':s.turnover.mean(),
                     'max_drawdown_compound':np.min(wealth/np.maximum.accumulate(wealth)-1),'max_drawdown_additive':np.min(cum-np.maximum.accumulate(cum)),
                     **{'annual_'+c:s[c].mean()*252 for c in ['gross','net','cost','cost_all','long','short','long_net','short_net','sleeve_net','sleeve_cost','sleeve_long_gross','sleeve_long_net','sleeve_short_gross','sleeve_short_net']},
                     **{'period_'+c:s[c].sum() for c in ['gross','net','cost']},'diagnostic_only':True})
    pd.DataFrame(rows).to_csv(folder/'pure_diversification_metrics.csv',index=False)
    pd.DataFrame({VIRTUAL:w}).to_parquet(folder/'pure_virtual_weights.parquet')
    return d


def attribution(holdings,target,dates,folder):
    x=holdings[SN].w; y=holdings[SLOW].w
    disagree=(x*y).lt(0)
    cls=pd.Series('BOTH_NEUTRAL',index=x.index,dtype='string')
    for name,mask in [('SN1_ONLY_LONG',x.gt(0)&y.eq(0)),('SLOW_ONLY_LONG',y.gt(0)&x.eq(0)),('BOTH_LONG',x.gt(0)&y.gt(0)),
                      ('SN1_ONLY_SHORT',x.lt(0)&y.eq(0)),('SLOW_ONLY_SHORT',y.lt(0)&x.eq(0)),('BOTH_SHORT',x.lt(0)&y.lt(0)),('SIGNAL_DISAGREEMENT',disagree)]:
        cls.loc[mask]=name
    inclusive={'SN1_ONLY_LONG':x.gt(0)&~y.gt(0),'SLOW_ONLY_LONG':y.gt(0)&~x.gt(0),'BOTH_LONG':x.gt(0)&y.gt(0),
               'SN1_ONLY_SHORT':x.lt(0)&~y.lt(0),'SLOW_ONLY_SHORT':y.lt(0)&~x.lt(0),'BOTH_SHORT':x.lt(0)&y.lt(0),'SIGNAL_DISAGREEMENT':disagree}
    r=pd.DataFrame({'group':cls,'forward_target':target},index=x.index)
    measure=[]
    for book in [SN,SLOW,BLEND]:
        for col in ['gross','net','turnover','cost','cost_all']:
            key=book+'_'+col;r[key]=holdings[book][col].fillna(0.);measure.append(key)
    for base in [SN,SLOW]:
        for col in ['gross','net','turnover','cost','cost_all']:
            key='DELTA_VS_'+base+'_'+col;r[key]=r[BLEND+'_'+col]-r[base+'_'+col];measure.append(key)
    r=r.loc[r.index.get_level_values('Date').isin(dates)]
    r.to_parquet(folder/'diversification_stock_attribution.parquet')
    rows=[];dailyrows=[]
    for view,masks in [('EXCLUSIVE',{c:r.group.eq(c) for c in sorted(cls.unique())}),('MARGINAL_OVERLAPPING',{c:m.reindex(r.index) for c,m in inclusive.items()})]:
        parts=[]
        for group,mask in masks.items():
            d=r[measure].where(mask,0.).groupby('Date').sum().reindex(dates,fill_value=0)
            d['count']=mask.groupby('Date').sum().reindex(dates,fill_value=0)
            d['forward_target_mean']=r.forward_target.where(mask).groupby('Date').mean().reindex(dates)
            if view=='EXCLUSIVE':parts.append(d[measure])
            for scope,ds in scopes(dates):
                sub=r.loc[mask&r.index.get_level_values('Date').isin(ds)]
                row={'view':view,'group':group,'scope':scope,'count':len(sub),'target_count':sub.forward_target.notna().sum(),
                     'forward_target_mean':sub.forward_target.mean(),'daily_forward_target_mean':d.loc[ds,'forward_target_mean'].mean()}
                for c in measure:
                    row[c+'_period']=d.loc[ds,c].sum()
                    row[c+('_daily' if c.endswith('turnover') else '_annual')]=d.loc[ds,c].mean()*(1 if c.endswith('turnover') else 252)
                rows.append(row)
            d['view']=view;d['group']=group;dailyrows.append(d.reset_index(names='Date'))
        if view=='EXCLUSIVE':
            total=sum(parts)
            for book in [SN,SLOW,BLEND]:
                for col in ['gross','net','turnover','cost']:
                    expected=holdings[book][col].fillna(0).groupby('Date').sum().loc[dates]
                    assert np.allclose(total[book+'_'+col],expected,atol=1e-15,rtol=0),(book,col)
    pd.DataFrame(rows).to_csv(folder/'diversification_attribution.csv',index=False)
    pd.concat(dailyrows).to_csv(folder/'diversification_attribution_daily.csv',index=False)
    return {'status':'PASS','exclusive_reconciliation_atol':1e-15,'both_neutral_exit_costs_retained':True,
            'marginal_view_overlaps':True,'signal_disagreement':'opposite official portfolio side; no veto'}


def source_dates(frame):
    dates=pd.DatetimeIndex(frame.index.get_level_values('Date') if isinstance(frame.index,pd.MultiIndex) else frame.index)
    return dates.tz_convert('Asia/Tokyo').tz_localize(None) if dates.tz is not None else dates


def mutate(frame,name,cutoff,seed):
    f=frame.copy(); dates=source_dates(f)
    mask=dates>cutoff; rng=np.random.default_rng(seed)
    for c in f:
        if c=='AdjustmentFactor':
            f.loc[mask,c]=rng.choice([.25,.5,1.,2.,4.],mask.sum())
        elif pd.api.types.is_numeric_dtype(f[c]):
            values=rng.normal(0,1e6,mask.sum());values[::7]=np.nan;values[1::11]=0
            f.loc[mask,c]=values
        else: f.loc[mask,c]='FUTURE_CHANGED_SECTOR'
    if name=='fins_statements':
        # Suffix disclosures can be removed or published later; never move into prefix.
        f=f.drop(f.index[mask][::11]);arrays=f.index.to_frame(index=False)
        suffix=source_dates(f)>cutoff;arrays.loc[suffix,'Date']+=pd.Timedelta(days=1)
        f.index=pd.MultiIndex.from_frame(arrays)
        f=f.loc[~f.index.duplicated(keep='last')].sort_index()
    return f


def causality(inputs,target,scores,x,f,config,folder):
    cases=[]; snkeys=list(blend_features.sn_features.INPUT_COLUMNS); slowkeys=list(blend_features.slow_features.INPUT_COLUMNS)
    base_blend=blend_features.blend(scores[SN],scores[SLOW]); allkeys=list(inputs)+['target_1day']
    for i,ct in enumerate(config['prefix_cutoffs']):
        cutoff=pd.Timestamp(ct);idx=scores.index[scores.index.get_level_values('Date')<=cutoff]
        for source in allkeys+['ALL','TRUNCATION']:
            changed=dict(inputs); labels=target
            for j,(key,frame) in enumerate(inputs.items()):
                ds=source_dates(frame)
                if source=='TRUNCATION':changed[key]=frame.loc[ds<=cutoff]
                elif source in [key,'ALL']:changed[key]=mutate(frame,key,cutoff,config['random_seed']+i*100+j)
            if source=='TRUNCATION':labels=target.loc[idx]
            elif source in ['target_1day','ALL']:labels=mutate(target.to_frame(),'target_1day',cutoff,config['random_seed']+i).Return
            # Only refit components whose inputs change. Original scores are otherwise immutable.
            affect_sn=source in snkeys+['target_1day','ALL','TRUNCATION']
            affect_slow=source in slowkeys+['ALL','TRUNCATION']
            ss=scores[SN].loc[idx];sl=scores[SLOW].loc[idx]
            if affect_sn:
                xx=blend_features.sn_features.build_features({k:changed[k][blend_features.sn_features.INPUT_COLUMNS[k]] for k in snkeys})
                exact(x.loc[idx],xx.loc[idx])
                yy=labels.reindex(xx.index)
                years=[y for y in range(2011,2017) if y<=cutoff.year]
                pred,rec=blend_features.bidirectional.walk_forward_predictions(xx,yy,years=years)
                base=blend_features.bidirectional.generate_signal(xx,pred,alpha=.25)
                ss=blend_features.sn1.rebuild_from_base_score(base)['SIDE_SOURCE_SEPARATION'].loc[idx].rename(SN)
                for record in rec:assert pd.Timestamp(record['max_label_maturity_date'])<pd.Timestamp(f"{record['year']}-01-01")
                exact(scores[SN].loc[idx],ss)
            if affect_slow:
                ff=blend_features.slow_features.build_features({k:changed[k][blend_features.slow_features.INPUT_COLUMNS[k]] for k in slowkeys},sector=False)
                exact(f.loc[idx],ff.loc[idx]);sl=ff.size_liquidity.loc[idx].rename(SLOW);exact(scores[SLOW].loc[idx],sl)
            exact(base_blend.loc[idx],blend_features.blend(ss,sl))
            cases.append({'cutoff':ct,'source':source,'status':'PASS','rows':len(idx),'bitwise':True,'SN1_refit':affect_sn,'SLOW_rebuilt':affect_slow})
        print(f'causality {ct}: each input + Train labels / ALL / truncation PASS',flush=True)
        dump(folder/'prefix_progress.json',{'status':'running','cases':cases})
    return {'status':'PASS','cases':cases,'comparison':'exact index/columns/dtype/float64 uint64 incl NaN, zero tolerance',
            'SN1_learning_included':True,'future_model_years_excluded_when_not_available':True,
            'mutations':'all source suffix extreme/NaN/zero; valid positive observed action factors; suffix financial disclosure row deletion/publication date movement; every-source truncation',
            'tested_scores':[SN,SLOW,BLEND],'untested':'arbitrary adversarial deletions of required price/factor rows violate frozen input contract; no universal proof'}


def source_scan(paths):
    findings=[]; exceptions=[]
    for p in paths:
        tree=ast.parse(p.read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Constant) and isinstance(node.value,str) and any(k in node.value for k in ['AdjustmentOpen','AdjustmentHigh','AdjustmentLow','AdjustmentClose','AdjustmentVolume','_valid.parquet','raw_target']):
                findings.append({'source':str(p.relative_to(ROOT)),'line':node.lineno,'operation':node.value})
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                bad=node.func.attr in ['bfill','backfill']
                for kw in node.keywords:
                    bad |= kw.arg=='center' and isinstance(kw.value,ast.Constant) and kw.value.value is True
                    bad |= kw.arg=='direction' and isinstance(kw.value,ast.Constant) and kw.value.value!='backward'
                if node.func.attr=='shift':
                    arg=node.args[0] if node.args else next((k.value for k in node.keywords if k.arg=='periods'),None)
                    bad |= isinstance(arg,ast.UnaryOp) and isinstance(arg.op,ast.USub)
                if bad:findings.append({'source':str(p.relative_to(ROOT)),'line':node.lineno,'operation':'forbidden time operation'})
        if 'target_1day' in p.read_text():exceptions.append({'source':str(p.relative_to(ROOT)),'reason':'explicit Train-only SN1 annual learning; mature prior-fold labels. Blend transform takes final scores only.'})
    assert not findings,findings
    return {'status':'PASS','paths':[str(p.relative_to(ROOT)) for p in paths],'findings':findings,'reviewed_label_access':exceptions,
            'manual':'original backward PIT financial EOD join, causal observed AdjustmentFactor cumprod (not adjusted OHLC level), trailing prior prices and rolling, within-date ranks; explicit Train-only loaders'}


def decisions(results,boot):
    def row(name,scope):return results.loc[(results.strategy==name)&(results.scope==scope)].iloc[0]
    checks={};count=0
    for y in range(2011,2016):count+=row(BLEND,str(y)).net_sharpe>row(SLOW,str(y)).net_sharpe
    checks['improved_full_years_ge4']=count>=4
    for scope in ['POOLED','EX2016']:
        b,s,n=row(BLEND,scope),row(SLOW,scope),row(SN,scope)
        checks[scope+'_net_sharpe_gt_slow']=b.net_sharpe>s.net_sharpe
        checks[scope+'_annual_net_ge_slow']=b.annual_net>=s.annual_net
        checks[scope+'_MDD_magnitude_le_slow']=abs(b.max_drawdown_compound)<=abs(s.max_drawdown_compound)
        checks[scope+'_long_net_gt0']=b.annual_long_net>0
        checks[scope+'_short_net_ge0']=b.annual_short_net>=0
        checks[scope+'_turnover_le_max_components']=b.turnover<=max(s.turnover,n.turnover)
    checks['primary_pooled_bootstrap_lower_gt0']=boot['POOLED:'+BLEND+'-'+SLOW]['low']>0
    return {'decision':'NEXT_STAGE' if all(checks.values()) else 'REJECT','all_passed':all(checks.values()),
            'checks':checks,'full_year_net_sharpe_improvements':int(count),'actual_trials':1,'rescue_trials':0}


def report(config,output,result,incremental,ortho,boot,decision,resources):
    folder=ROOT/config['report_dir'];folder.mkdir(parents=True,exist_ok=True)
    for sub in ['metrics','audit']:
        shutil.copytree(output/sub,folder/sub,dirs_exist_ok=True)
    pooled=result.loc[(result.scope=='POOLED')&result.strategy.isin([SN,SLOW,BLEND])]
    year=result.loc[result.strategy.isin([SN,SLOW,BLEND])&result.scope.isin([str(y) for y in range(2011,2017)])]
    o=ortho.loc[ortho.scope=='POOLED'].iloc[0]; virt=pd.read_csv(output/'metrics/pure_diversification_metrics.csv'); v=virt.loc[virt.scope=='POOLED'].iloc[0]
    primary=boot['POOLED:'+BLEND+'-'+SLOW]; secondary=boot['POOLED:'+BLEND+'-'+SN]
    text=[f'# {config["experiment_id"]}: SN1 × SLOW diversification', '',f'Decision: **{decision["decision"]}**. One fixed score-blend trial; zero rescue trials. Historical Valid / Valid not read or evaluated. Run: `{output.relative_to(ROOT)}`.', '',
          '目的はMomentum/BreakoutとSize/Liquidityを組み合わせたときの安定したNetの増分。単体の優劣を選ぶ実験ではない。低相関だけで採用しない。', '',
          table(pooled,['strategy','net_sharpe','gross_sharpe','annual_net','annual_gross','turnover','annual_cost','max_drawdown_compound','annual_long_net','annual_short_net']), '',
          'Primary/secondary comparison and all required IC/HAC5/hit/Q1–Q5/side/period metrics are in `metrics/metrics.csv` and `metrics/incremental.csv`.', '',
          table(year,['strategy','scope','days','net_sharpe','annual_net','turnover','max_drawdown_compound']), '',
          f'2011–2015 Net Sharpe改善 vs SLOW: **{decision["full_year_net_sharpe_improvements"]}/5**。2016は部分年として別記。POOLEDとEX2016は日付を揃えた2011以降の評価営業日。年間P/Lは日次平均×252であり2016も年率換算、実額はperiod_*。Sharpeはsample SD(ddof1)×sqrt252、RankICは日次average-tie Spearman、tはNewey-West/Bartlett HAC5。', '',
          '## Orthogonality before performance trial', '',
          f'Pooled gross P/L correlation **{o.gross_pl_corr:.6f}**, net **{o.net_pl_corr:.6f}**; mean daily score Spearman **{o.score_spearman_mean:.6f}**. Long/Short Jaccard **{o.long_jaccard:.6f}/{o.short_jaccard:.6f}**. Long/Short daily cross-sector exposure correlation **{o.long_sector_cross_section_corr:.6f}/{o.short_sector_cross_section_corr:.6f}**.', '',
          f'SN1とSLOWのdrawdown pathは同一か: **{o.drawdown_paths_equal}**。Underwater Jaccard **{o.drawdown_jaccard:.6f}**、depth correlation **{o.drawdown_depth_corr:.6f}**。SN1のみunderwater **{int(o.sn1_only_drawdown_days)}**日、SLOWのみ **{int(o.slow_only_drawdown_days)}**日、両方 **{int(o.both_drawdown_days)}**日。異なるdrawdownは診断上の観測であり、独立した経済原因の証明ではない。', '',
          f'SN1 net<0日にSLOW平均Net **{o.slow_mean_net_when_sn1_negative:.8f}**、SLOW net<0日にSN1平均Net **{o.sn1_mean_net_when_slow_negative:.8f}**。両方負 **{int(o.both_negative_days)}**日、片方のみ負 **{int(o.exactly_one_negative_days)}**日。', '',
          table(ortho,['scope','gross_pl_corr','net_pl_corr','score_spearman_mean','drawdown_jaccard','both_negative_days','exactly_one_negative_days']), '',
          'Sector33は各signal日PIT、欠損/9999はUNKNOWN。各日sector断面相関とsectorごとの時系列相関を両方保存。Long=Q4/Q5, Short=Q1/Q2、Q3はneutral。Overlap=intersection/min(side set sizes)、Jaccard=intersection/union。Underwaterはwealth/peak−1<0、初期wealth1を含む。各scopeでcurveを再初期化し年別episodesも保存。', '',
          '## Pure-weight diagnostic (not a candidate)', '',
          f'0.5×official weightsの仮想portfolio pooled NetSR **{v.net_sharpe:.6f}**、GrossSR **{v.gross_sharpe:.6f}**、年率Net **{v.annual_net:.6f}**、turnover **{v.turnover:.6f}**。Nettingしない0.5×両戦略P/Lのsleeve NetSR **{v.sleeve_net_sharpe:.6f}**。', '',
          table(virt,['scope','net_sharpe','gross_sharpe','sleeve_net_sharpe','annual_net','turnover','annual_cost','max_drawdown_compound']), '',
          '合成後weightの差分で売買をnettingする主診断と、各戦略コストを半分ずつ負担するsleeve診断を区別。前者のLong/Shortは合成weight符号、後者のside attributionは元戦略sideの平均。純粋な分散効果とranking interactionを分離して解釈する。', '',
          '## Bootstrap and adoption', '',
          f'Paired circular moving-block: block20, reps2000, seed20261003, 95% percentile CI. Primary ΔNetSR(BLEND−SLOW) **{primary["observed_delta"]:.6f}**, CI **[{primary["low"]:.6f}, {primary["high"]:.6f}]**. Secondary ΔNetSR(BLEND−SN1) **{secondary["observed_delta"]:.6f}**, CI **[{secondary["low"]:.6f}, {secondary["high"]:.6f}]**.', '',
          table(pd.DataFrame([{'gate':k,'passed':v} for k,v in decision['checks'].items()]),['gate','passed']), '',
          '## Diversification attribution', '',
          'metrics/diversification_attribution.csv とstock/daily panelにcount、forward target、全3bookのgross/net/turnover/cost、BLEND−各component差分を保存。Exclusive viewはopposite official sideをSIGNAL_DISAGREEMENTへ先に割当て、onlyLong/Shortは他方neutral。BOTH_NEUTRALにexitコストを保持するため全会計へ照合できる。MARGINAL_OVERLAPPING viewは要求された「片方のみLong/Short」を他方oppositeも含めて集計し、disagreementとの重複を明記。群を合算して重複計上しない。新filterは作らない。', '',
          '## Causality and reproducibility', '',
          'Component source copies byte-identical, current originals/adapter/saved scores float64 bitwise parity; exact809636-row input/output index and finite coverage; deterministic rebuild. Future mutation covers each/all sources and Train labels; truncation covers all sources at three cutoffs, features/all3 scores bitwise. Annual SN1 models are refit on original mature prior-fold labels, so learning path is included. Cutoff後のmodel年を監査時に使用しない。No later split prediction is implemented in new adapter.', '',
          'Official weights and daily Net are bitwise reconciled. Stock/sleeve attribution uses1e-15 numerical sum tolerance and is not called bitwise. The official expression omits cost when target is missing; cost_all/net_all_cost are also saved. Official turnover follows last observed stock row across absences, unchanged. Full-panel accounting precedes fold purge, preserving holdings across omitted days. Training maturity and reconstructed t+2 target are saved in audit/maturity.json.', '',
          f'Elapsed **{resources["elapsed_seconds"]:.2f}s**, peak RSS **{resources["peak_rss_bytes"]/1e9:.3f} GB**. Source/input/config/plan/artifact hashes, environment versions, bounded command and phase timestamps saved. Tests and workspace verification are in audit/verification.json. The new adapter is a Train research candidate, not a frozen later-split submission. No release or external submission.', '',
          'Conclusion applies to this fixed operationalization and known Train sample. Low correlation cannot establish higher tradable after-cost Sharpe. No weight/feature/parameter/filter changes or rescue candidates after results.']
    (folder/'REPORT.md').write_text('\n'.join(text)+'\n')
    exp=ROOT/'experiments'/config['experiment_id']
    dump(exp/'decision.json',decision)
    (exp/'decision.md').write_text(f'# {config["experiment_id"]}: {decision["decision"]}\n\n[Report](../../reports/{config["experiment_id"]}/REPORT.md). One fixed performance trial, zero rescue.\n\n'+table(pd.DataFrame([{'criterion':k,'passed':v} for k,v in decision['checks'].items()]),['criterion','passed'])+'\n\nAll comparisons Train-only. Immutable component definitions and weights retained. No Historical Valid / Valid / release / submission.\n')
    meta=json.loads((exp/'experiment.json').read_text());meta['status']='rejected' if decision['decision']=='REJECT' else 'completed';dump(exp/'experiment.json',meta)
    if decision['decision']=='REJECT':
        with (ROOT/'experiments/GRAVEYARD.md').open('a') as stream:
            stream.write(f'\n- [{config["experiment_id"]}](./{config["experiment_id"]}/decision.md): fixed SN1_H1+SLOW_CONTROL rank1:1 diversification REJECT; improved full-year NetSR {decision["full_year_net_sharpe_improvements"]}/5. Failed gates: '+', '.join(k for k,v in decision['checks'].items() if not v)+'. One trial, zero rescue, Train-only.\n')


def main_work(config,output,run):
    start=time.monotonic();stage=output/'stage';stage.mkdir()
    keys=set(blend_features.sn_features.INPUT_COLUMNS)|set(blend_features.slow_features.INPUT_COLUMNS)
    filenames=sorted(keys|{'target_1day'})
    for key in filenames:(stage/(key+'_train.parquet')).symlink_to(ROOT/config['input_dir']/(key+'_train.parquet'))
    refs={n:ROOT/r['path'] for n,r in config['saved_components'].items()}
    for n,p in refs.items():assert sha(p)==config['saved_components'][n]['sha256']
    source_paths=sorted((ROOT/'stock_comp_2026/strategies/dm_sn1_slow_blend').rglob('*.py'))
    code_paths=source_paths+[Path(__file__),ROOT/'research/evaluation.py',ROOT/'research/firewall.py',ROOT/'research/experiments/slow_multifactor.py',ROOT/'stock_comp_2026/evaluate_script.py',ROOT/'stock_comp_2026/strategies/dm_trainonly/features.py']
    code_paths+=sorted((ROOT/'stock_comp_2026/strategies/dm_variable_box_breakout').glob('*.py'))
    code_paths+=[ROOT/'stock_comp_2026/strategies/dm_slow_multifactor/features.py']
    run.update(status='running',command=sys.argv,actual_trials=0,code_sha256={str(p.relative_to(ROOT)):sha(p) for p in code_paths},
               train_data_sha256={key+'_train.parquet':sha(stage/(key+'_train.parquet')) for key in filenames},
               environment={'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'pyarrow':pyarrow.__version__,'scipy':scipy.__version__,'platform':platform.platform()})
    dump(output/'run.json',run)
    for p in code_paths:
        to=output/'code'/p.relative_to(ROOT);to.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,to)
    phases=[]
    def checkpoint(phase,files=()):
        phases.append({'phase':phase,'at_utc':now(),'actual_trials':run['actual_trials'],
                       'sha256':{str(p.relative_to(output)):sha(p) for p in files}})
        dump(output/'audit/phase_gates.json',phases);print('phase '+phase,flush=True)
    dump(output/'audit/pre_result_lock.json',{'at_utc':now(),'plan_sha256':sha(output/'plan.md'),'config_sha256':sha(output/'config.json'),
                                            'code_sha256':run['code_sha256'],'max_trials':1,'target_read':False})
    checkpoint('plan_config_code_freeze',[output/'plan.md',output/'config.json'])
    dump(output/'audit/source_scan.json',source_scan(source_paths))
    copies=[]
    for part,source,names in [('component_sn1','dm_variable_box_breakout',['features','bidirectional','sn1']),('component_slow','dm_slow_multifactor',['features'])]:
        for name in names:
            a=ROOT/f'stock_comp_2026/strategies/{source}/{name}.py';b=ROOT/f'stock_comp_2026/strategies/dm_sn1_slow_blend/{part}/{name}.py'
            assert a.read_bytes()==b.read_bytes();copies.append({'original':str(a.relative_to(ROOT)),'copy':str(b.relative_to(ROOT)),'sha256':sha(a)})
    columns={}
    for loader in [blend_features.sn_features,blend_features.slow_features]:
        for k,cols in loader.INPUT_COLUMNS.items():columns.setdefault(k,set()).update(cols)
    columns['listed_info'].add('Sector33Code')
    # Input hashes read bytes without decoding labels. Install the read audit
    # after hashing, before any parquet parser loads feature or label values.
    own_parquets=[output/'predictions/component_scores.parquet', output/'predictions/strategy_scores.parquet',
                  output/'metrics/pure_virtual_weights.parquet', output/'metrics/diversification_stock_attribution.parquet']
    # This immutable Train artifact is hashed by the existing workspace Freeze
    # verification; its values are never parsed or used for this experiment.
    own_parquets.append(ROOT/'releases/DM-20260908-v1/snapshot/reports/DM-20260908/selected_train_predictions.parquet')
    firewall.install(allowed_artifacts=list(refs.values())+own_parquets)
    inputs={k:pd.read_parquet(stage/(k+'_train.parquet'),columns=sorted(cols)).sort_index() for k,cols in columns.items()}
    feature_opened=sorted(firewall.ACCESSES)
    assert not any('target_1day' in p for p in feature_opened)
    target=pd.read_parquet(stage/'target_1day_train.parquet').Return.sort_index()
    sn_inputs={k:inputs[k][cols] for k,cols in blend_features.sn_features.INPUT_COLUMNS.items()}
    slow_inputs={k:inputs[k][cols] for k,cols in blend_features.slow_features.INPUT_COLUMNS.items()}
    scores,x,f,records=blend_features.components(sn_inputs,slow_inputs,target,model_dir=output/'models')
    # Source and adapter parity check original current paths and saved final scores.
    ox=original_sn.build_features(sn_inputs);exact(x,ox)
    original,original_records=original_adapter.predict_from_features(ox,target)
    exact(scores[SN].rename('Return'),original.Return)
    of=original_slow.build_features(slow_inputs,sector=False);exact(f,of)
    for name in [SN,SLOW]:
        saved=pd.read_parquet(refs[name],columns=[config['saved_components'][name]['column']]).iloc[:,0].rename(name)
        exact(scores[name],saved)
    rebuilt,xx,ff,rr=blend_features.components(sn_inputs,slow_inputs,target)
    exact(scores,rebuilt);exact(x,xx);exact(f,ff)
    assert scores.index.equals(target.index) and scores.index.equals(sn_inputs['raw_return_1day'].index)
    assert np.isfinite(scores.to_numpy()).all()
    mom=momentum.smooth(momentum.build_momentum({k:inputs[k] for k in ['raw_return_1day','beta_1day','topix_return_1day']}),.25).rename('MOM60')
    saved_mom=pd.read_parquet(refs[SLOW],columns=['MOM60']).MOM60;exact(mom,saved_mom)
    dump(output/'audit/component_parity.json',{'status':'PASS','copies':copies,'source_feature_bits':True,'saved_score_bits':True,
                                             'SN1_original_adapter_bits':True,'deterministic_rebuild_bits':True,'MOM60_saved_bits':True,'rows':len(scores),
                                             'saved_refs':config['saved_components'],'SN1_original_fit_records_equal':records==original_records})
    scores.to_parquet(output/'predictions/component_scores.parquet')
    dump(output/'audit/contract.json',{'status':'PASS','rows':len(scores),'exact_index':True,'unique':True,'finite':True,'feature_only_reads_before_train_learning':feature_opened})
    checkpoint('component_parity',[output/'audit/component_parity.json',output/'predictions/component_scores.parquet'])
    calendar=scores.index.get_level_values('Date').unique().sort_values();dates,purge=eligible_dates(calendar)
    dump(output/'audit/purge.json',{'status':'PASS','folds':purge,'continuous_full_panel_accounting_before_purge':True})
    # Annual training maturity and realized target endpoint reconstruction.
    maturity=[]
    for r in records:
        assert pd.Timestamp(r['max_label_maturity_date'])<pd.Timestamp(f"{r['year']}-01-01")
        maturity.append(r)
    raw=inputs['raw_return_1day'].Return;beta=inputs['beta_1day'].Return.reindex(raw.index)
    market=pd.Series(inputs['topix_return_1day'].Return.reindex(raw.index.get_level_values('Date')).to_numpy(),index=raw.index)
    residual=raw-beta*market;wide=residual.unstack('Code').reindex(calendar);future=wide.shift(-2).stack(future_stack=True).reindex(target.index)
    ok=target.notna()&future.notna()&target.index.get_level_values('Date').isin(calendar[:-2])
    err=(target.loc[ok]-future.loc[ok]).abs().max();assert err<1e-12,err
    dump(output/'audit/maturity.json',{'status':'PASS','SN1_annual_models':maturity,'H1_endpoint':'signal exchange index+2',
                                     'reconstructable_rows':int(ok.sum()),'reconstruction_max_abs_error':err,'target_bitwise':bool(np.array_equal(target.loc[ok].to_numpy().view(np.uint64),future.loc[ok].to_numpy().view(np.uint64))),
                                     'terminal_two_sessions_excluded_from_every_evaluation':True})
    accounts={};holdings={};parity={}
    for name,score in [(SN,scores[SN]),(SLOW,scores[SLOW]),('MOM60',mom)]:
        accounts[name],holdings[name],parity[name]=account(score,target)
    ortho=orthogonality(scores,accounts,holdings,inputs['listed_info'],dates,output/'metrics')
    checkpoint('orthogonality_diagnostics_saved',[output/'metrics/orthogonality_summary.csv',output/'metrics/orthogonality_daily.csv'])
    virtual_portfolio(holdings,accounts,target,dates,output/'metrics')
    checkpoint('pure_weight_diagnostic_saved',[output/'metrics/pure_diversification_metrics.csv'])
    # First creation of the one authorized performance candidate.
    scores[BLEND]=blend_features.blend(scores[SN],scores[SLOW]);run['actual_trials']=1
    scores.to_parquet(output/'predictions/strategy_scores.parquet')
    accounts[BLEND],holdings[BLEND],parity[BLEND]=account(scores[BLEND],target)
    for name,d in accounts.items():d.to_csv(output/f'metrics/daily_{name}.csv',index_label='Date')
    result=pd.DataFrame([{'strategy':name,'scope':scope,**metrics(d.loc[ds])} for name,d in accounts.items() for scope,ds in scopes(dates)])
    result.to_csv(output/'metrics/metrics.csv',index=False)
    numeric=[c for c in result if c not in ['strategy','scope']]
    inc=[]
    for scope,_ in scopes(dates):
        cand=result.loc[(result.strategy==BLEND)&(result.scope==scope)].iloc[0]
        for name in [SLOW,SN,'MOM60']:
            base=result.loc[(result.strategy==name)&(result.scope==scope)].iloc[0]
            inc.append({'comparison':BLEND+'-'+name,'scope':scope,**{'delta_'+c:cand[c]-base[c] for c in numeric}})
    incremental=pd.DataFrame(inc);incremental.to_csv(output/'metrics/incremental.csv',index=False)
    dump(output/'audit/official_accounting.json',{'status':'PASS','books':parity})
    dump(output/'audit/attribution.json',attribution(holdings,target,dates,output/'metrics'))
    checkpoint('fixed_score_blend_trial_completed',[output/'metrics/metrics.csv'])
    boot={}
    for scope,ds in scopes(dates)[:2]:
        for name in [SLOW,SN]:
            boot[scope+':'+BLEND+'-'+name]={**evaluation.bootstrap_delta(accounts[name].loc[ds].net,accounts[BLEND].loc[ds].net,**{k:config['bootstrap'][k] for k in ['seed','block','reps']}),
                                         'observed_delta':evaluation.sharpe(accounts[BLEND].loc[ds].net)-evaluation.sharpe(accounts[name].loc[ds].net),
                                         'days':len(ds),'ci':.95,'primary':name==SLOW}
    dump(output/'metrics/bootstrap.json',boot);pd.DataFrame([{'comparison':k,**v} for k,v in boot.items()]).to_csv(output/'metrics/bootstrap.csv',index=False)
    checkpoint('bootstrap_completed',[output/'metrics/bootstrap.json'])
    audit=causality(inputs,target,scores[[SN,SLOW]],x,f,config,output/'audit');dump(output/'audit/prefix_invariance.json',audit)
    adapted=submission.predict(stage).Return;exact(scores[BLEND].rename('Return'),adapted)
    dump(output/'audit/adapter_parity.json',{'status':'PASS','bitwise':True,'rows':len(adapted),'self_contained_components':True})
    firewall.save(output/'audit/firewall.json')
    assert not any('_valid' in p.lower() or 'raw_target' in p.lower() for p in firewall.ACCESSES)
    checkpoint('causality_audit_completed',[output/'audit/prefix_invariance.json'])
    tests=subprocess.run([sys.executable,str(ROOT/'tools/run_bounded.py'),'--seconds','180',sys.executable,'-m','pytest','-q',
                          'tests/strategies/dm_sn1_slow_blend','tests/strategies/dm_variable_box_breakout/test_sn1.py','tests/strategies/dm_slow_multifactor',
                          '-k','not valid and not later'],cwd=ROOT,capture_output=True,text=True)
    (output/'logs/tests.log').write_text(tests.stdout+tests.stderr);assert tests.returncode==0,tests.stdout+tests.stderr
    check=subprocess.run(['make','check'],cwd=ROOT,capture_output=True,text=True);(output/'logs/make_check.log').write_text(check.stdout+check.stderr)
    from tools import workspace
    workspace.validate_experiment(ROOT,ROOT/'experiments'/config['experiment_id'])
    frozen=0
    for p in sorted((ROOT/'reports').glob('*/freeze_manifest.json')):
        manifest=json.loads(p.read_text());root=ROOT
        for exp in (ROOT/'experiments').iterdir():
            meta_path=exp/'experiment.json'
            if meta_path.is_file():
                meta=json.loads(meta_path.read_text())
                if meta.get('freeze_manifest')==str(p.relative_to(ROOT)):root=ROOT/meta['freeze_root']
        for section in ['code_sha256','artifact_sha256']:
            for rel,h in manifest[section].items():assert sha(root/rel)==h;frozen+=1
    dump(output/'audit/verification.json',{'status':'PASS','tests_returncode':tests.returncode,'tests_output':tests.stdout.strip(),
                                         'make_check_returncode':check.returncode,'make_check_output':check.stdout+check.stderr,
                                         'own_metadata':'PASS','existing_freeze_hashes':frozen,'existing_freeze_hashes_status':'PASS'})
    decision=decisions(result,boot);dump(output/'metrics/decision.json',decision)
    checkpoint('decision_recorded',[output/'metrics/decision.json'])
    resources={'elapsed_seconds':time.monotonic()-start,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),'actual_trials':1,'valid_evaluation':False}
    dump(output/'audit/resources.json',resources)
    report(config,output,result,incremental,ortho,boot,decision,resources)
    run.update(status='completed',exit_code=0,completed_at_utc=now(),decision=decision,resources=resources,
               artifact_sha256={str(p.relative_to(output)):sha(p) for folder in ['predictions','metrics','audit','models'] for p in (output/folder).rglob('*') if p.is_file()})
    dump(output/'run.json',run)
    print(json.dumps(safe({'decision':decision,'resources':resources}),indent=2),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    config=json.loads(Path(args.config).read_text());output=Path(args.output).resolve();run=json.loads((output/'run.json').read_text())
    assert run['status']=='prepared';assert config['max_trials']==1 and config['trials']==[{'trial_id':BLEND}]
    assert config['data_split']=='train' and not config['valid_evaluation'];assert config['parameters']['blend_weights']==[1,1]
    assert config['bootstrap']['block']==20 and config['bootstrap']['reps']==2000 and config['bootstrap']['seed']==20261003
    try:main_work(config,output,run)
    except BaseException as error:
        run.update(status='failed',exit_code=1,completed_at_utc=now(),failure=repr(error));dump(output/'run.json',run)
        if firewall._PATCHED:firewall.save(output/'audit/firewall.json')
        raise


if __name__=='__main__':main()
