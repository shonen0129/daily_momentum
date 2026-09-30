"""Finite, preregistered Train-only research. Run as python -m research.run_trainonly."""
import hashlib
import json
import platform
import sys
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
STRATEGY=ROOT/'stock_comp_2026/strategies/dm_trainonly'
sys.path.insert(0,str(STRATEGY))
from features import load_inputs, build_features, smooth, centered_rank, MOMENTUM_NAMES
from models import fit_predict_family, PARAMETERS
from research.evaluation import daily_account, metrics, bootstrap_delta, dsr, rankic
from research import firewall

OUT=ROOT/'reports/DM-20260908'
DATA=ROOT/'stock_comp_2026/input'
SEED=20260908


def dump(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,ensure_ascii=False,default=str,allow_nan=False))


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def rank_choice(records):
    best=sorted(records,key=lambda r:(-r['positive_folds'],-r['median_fold_net'],-r['worst_fold_net'],r['metrics']['turnover'],r['id']))[0]
    near=[r for r in records if r['positive_folds']==best['positive_folds'] and r['median_fold_net']>=best['median_fold_net']-.05]
    return sorted(near,key=lambda r:(r['metrics']['turnover'],r.get('complexity',0),r['id']))[0]


def conditional_tests(f,m,target,inputs):
    rows=[]
    states={
        'all':pd.Series(True,index=f.index),
        'liquidity_down':f.liquidity_shock_value<0,
        'liquidity_up':f.liquidity_shock_value>0,
        'volume_low':f.volume_shock<-.333,
        'volume_high':f.volume_shock>.333,
        'pwv_high':f.pwv>.333,'pwv_low':f.pwv<0,
        'vwp_high':f.vwp>.333,'vwp_low':f.vwp<0,
        'historical_pwv_high':f.pwv_historical>.333,
        'historical_vwp_high':f.vwp_historical>.333,
        'vacuum':(f.liquidity_shock_value<0)&(f.pwv>.333),
        'am_down_pm_up':(f.am_value<0)&(f.pm_value>0),
        'am_up_pm_down':(f.am_value>0)&(f.pm_value<0),
    }
    dates=f.index.get_level_values('Date')
    for year in range(2011,2015):
        for state,mask in states.items():
            use=mask & (dates.year==year) & target.notna()
            ic=rankic(m.where(use),target.where(use)).dropna()
            rows.append({'year':year,'state':state,'rows':int(use.sum()),'days':len(ic),
                         'momentum_rankic':float(ic.mean()),
                         'signed_target':float((np.sign(m[use])*target[use]).mean())})
    pd.DataFrame(rows).to_csv(OUT/'conditional_states.csv',index=False)
    # Diagnostic outcomes only. Explicit next-date mapping; never a feature.
    calendar=dates.unique().sort_values()
    next_date=dict(zip(calendar[:-1],calendar[1:]))
    future_index=pd.MultiIndex.from_arrays([dates.map(next_date),f.index.get_level_values('Code')],names=['Date','Code'])
    next_r=inputs['raw_return_1day']['Return'].reindex(future_index).to_numpy()
    p=inputs['prices_daily_quotes'].reindex(f.index)
    overnight=pd.Series((1+next_r)*p.Open.to_numpy()/p.Close.to_numpy()-1,index=f.index)
    decay=[]
    for year in range(2011,2015):
        mask=dates.year==year
        for name in ['am','pm','volume_ratio','pwv','vwp']:
            for label,outcome in [('close_to_next_open',overnight),('competition_t1_t2',target)]:
                ic=rankic(f[name].where(mask),outcome.where(mask)).dropna()
                decay.append({'year':year,'feature':name,'outcome':label,'rankic':float(ic.mean()),'days':len(ic)})
    pd.DataFrame(decay).to_csv(OUT/'intraday_decay.csv',index=False)


def main():
    firewall.install()
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'daily').mkdir(exist_ok=True)
    print('Loading allowed Train features',flush=True)
    inputs=load_inputs(DATA,'train')
    f=build_features(inputs)
    dump(OUT/'impact_crossfit.json',f.attrs['impact_audit'])
    print(f'Features complete: {f.shape}',flush=True)
    # Read development labels only until the model-selection decision is saved.
    target=pd.read_parquet(DATA/'target_1day_train.parquet',filters=[('Date','<',pd.Timestamp('2015-01-01'))])['Return'].reindex(f.index)
    dates=f.index.get_level_values('Date')
    dev=(dates>=pd.Timestamp('2011-01-01'))&(dates<pd.Timestamp('2015-01-01'))
    records=[]; dailies={}; specs={}

    def evaluate(name,signal,spec,diagnostic=False,complexity=0):
        d=daily_account(signal.loc[dev],target.loc[dev])
        d.to_csv(OUT/'daily'/f'{name}.csv')
        fold=[{'year':int(y),**metrics(v)} for y,v in d.groupby(d.index.year)]
        record={'id':name,'date':'2026-09-08','parameters':spec,'diagnostic_only':diagnostic,
                'complexity':complexity,'metrics':metrics(d),'folds':fold,
                'positive_folds':sum(v['net_sharpe']>0 for v in fold),
                'median_fold_net':float(np.median([v['net_sharpe'] for v in fold])),
                'worst_fold_net':min(v['net_sharpe'] for v in fold),
                'train_window':'expanding 2008-11 onward, two-day boundary purge',
                'evaluation_window':'2011-01 through 2014-12',
                'hypothesis':spec.get('hypothesis','Causal momentum persistence with transaction-cost control')}
        records.append(record); dailies[name]=d; specs[name]=spec
        print(f"{name}: net={record['metrics']['net_sharpe']:.3f}, median={record['median_fold_net']:.3f}, positive={record['positive_folds']}/4, turnover={record['metrics']['turnover']:.4f}",flush=True)
        dump(OUT/'experiment_registry_inprogress.json',records)
        return record

    for name in MOMENTUM_NAMES:
        evaluate(f'M_{name}_a1',f[name],{'family':'Momentum','momentum':name,'alpha':1.})
    shape=rank_choice(records)['parameters']['momentum']
    for alpha in [.5,.25,.15]:
        evaluate(f'M_{shape}_a{alpha}',smooth(f[shape],alpha),{'family':'Momentum','momentum':shape,'alpha':alpha})
    baseline=rank_choice(records)
    momentum_name=baseline['parameters']['momentum']; alpha=baseline['parameters']['alpha']; m=f[momentum_name]
    baseline_id=baseline['id']
    baseline_signal=smooth(m,alpha)
    print(f'Momentum baseline locked: {baseline_id}; conditional tests before ML',flush=True)
    dump(OUT/'momentum_selection.json',baseline)
    conditional_tests(f,m,target,inputs)
    for a in sorted(set([max(.001,alpha*.8),min(1.,alpha*1.2)])-{alpha}):
        evaluate(f'SENS_alpha_{a:.3f}',smooth(m,a),{'family':'Momentum','momentum':momentum_name,'alpha':a},True)

    start_mask=dates>=pd.Timestamp('2011-01-01')
    vacuum=(f.liquidity_shock_value<0)&(f.pwv>.333)
    rule=m*np.where(vacuum,.5,1.)
    evaluate('C1_rule',smooth(rule,alpha),{'family':'C1_rule','momentum':momentum_name,'alpha':alpha,'gate_vacuum':.5,'pwv_threshold':.333},complexity=1)

    def fit(family,overrides=None,label=None):
        name=label or family
        print(f'Fitting {name}: fixed parameters, past -> future',flush=True)
        pred,audit=fit_predict_family(f,m,target,range(2011,2015),family,overrides,OUT/'models'/name)
        dump(OUT/f'fit_audit_{name}.json',audit)
        return pred

    p=fit('C1').clip(0,1)
    gate_signal=m.copy(); gate_signal.loc[start_mask]=(m*p).loc[start_mask]
    evaluate('C1_ml',smooth(gate_signal,alpha),{'family':'C1','momentum':momentum_name,'alpha':alpha,**PARAMETERS},complexity=2)
    correction=centered_rank(fit('B'))
    for lam in [.25,.5,1.]:
        evaluate(f'B_lambda{lam}',smooth(m+lam*correction,alpha),{'family':'B','momentum':momentum_name,'alpha':alpha,'lambda':lam,**PARAMETERS},complexity=3)
    c2=m.copy(); c2.loc[start_mask]=(m*(2*p-1)).loc[start_mask]
    evaluate('C2_ml',smooth(c2,alpha),{'family':'C2','momentum':momentum_name,'alpha':alpha,**PARAMETERS},complexity=4)
    for family in ['A_rank','A_raw']:
        pred=centered_rank(fit(family))
        direct=m.copy(); direct.loc[start_mask]=pred.loc[start_mask]
        evaluate(family,smooth(direct,alpha),{'family':family,'momentum':momentum_name,'alpha':alpha,**PARAMETERS},complexity=5)
    for lam in [.4,.6]:
        evaluate(f'SENS_B_lambda{lam}',smooth(m+lam*correction,alpha),{'family':'B','momentum':momentum_name,'alpha':alpha,'lambda':lam},True)
    for factor in [.8,1.2]:
        altered=m.copy(); altered.loc[start_mask]=(m*(p*factor).clip(0,1)).loc[start_mask]
        evaluate(f'SENS_C1_gate{factor}',smooth(altered,alpha),{'family':'C1','momentum':momentum_name,'alpha':alpha,'gate_factor':factor},True)
    for param,value in [('n_estimators',48),('n_estimators',72),('min_child_samples',400),('min_child_samples',600)]:
        label=f'SENS_C1_{param}{value}'
        prob=fit('C1',{param:value},label).clip(0,1)
        altered=m.copy(); altered.loc[start_mask]=(m*prob).loc[start_mask]
        evaluate(label,smooth(altered,alpha),{'family':'C1','momentum':momentum_name,'alpha':alpha,param:value},True)
    assert len(records)<=32
    variance=float(np.var([r['metrics']['net_sharpe']/np.sqrt(252) for r in records],ddof=1))
    accepted=[]
    increments=[]
    for record in records:
        name=record['id']
        record['dsr']=dsr(dailies[name].net,variance,len(records))
        record['dsr_100_trials']=dsr(dailies[name].net,variance,100)
        record['bootstrap_vs_baseline']=bootstrap_delta(dailies[baseline_id].net,dailies[name].net)
        improvements=[]
        for row,base in zip(record['folds'],baseline['folds']):
            delta={'model':name,'year':row['year']}
            for key in ['rankic','net_sharpe','gross_sharpe','turnover','annual_cost']:
                delta[f'delta_{key}']=row[key]-base[key]
            increments.append(delta); improvements.append(delta['delta_net_sharpe'])
        eligible=(not record['diagnostic_only'] and record['parameters']['family']!='Momentum' and
                  sum(x>0 for x in improvements)>=3 and np.median(improvements)>=.1 and
                  record['worst_fold_net']>=baseline['worst_fold_net']-.25 and
                  record['bootstrap_vs_baseline']['low']>0 and record['dsr']['dsr']>=.95)
        record['improved_folds']=sum(x>0 for x in improvements)
        record['median_increment_net']=float(np.median(improvements))
        record['eligible']=bool(eligible)
        if eligible: accepted.append(record)
    winner=rank_choice(accepted) if accepted else baseline
    for r in records:
        r['decision']='selected' if r['id']==winner['id'] else ('diagnostic only' if r['diagnostic_only'] else 'rejected')
        r['reason']=('Train development stability and preregistered acceptance rule' if r['id']==winner['id'] else
                     'Fixed sensitivity; not eligible for selection' if r['diagnostic_only'] else
                     'Momentum shape/smoothing stability rank' if r['parameters']['family']=='Momentum' else
                     f"Acceptance gate failed: improved folds={r['improved_folds']}/4; median delta={r['median_increment_net']:.3f}; bootstrap lower={r['bootstrap_vs_baseline']['low']:.3f}; DSR={r['dsr']['dsr']:.5f}")
    pd.DataFrame(increments).to_csv(OUT/'fold_incremental.csv',index=False)
    dump(OUT/'experiment_registry.json',records)
    selection={'strategy_id':'DM-20260908-v1','selected_id':winner['id'],'baseline_id':baseline_id,
               'selected_parameters':winner['parameters'],'selection_uses':'Train 2011-2014 only',
               'confirmation_seen':False,'valid_seen':False,'trials':len(records),
               'status':'research candidate; economic viability must be judged separately',
               'record':winner}
    dump(OUT/'selection_before_confirmation.json',selection)
    print(f"SELECTION SAVED BEFORE CONFIRMATION: {winner['id']}",flush=True)
    # Parameters and selection are fixed now. No loop back to model selection.
    full_target=pd.read_parquet(DATA/'target_1day_train.parquet')['Return'].reindex(f.index)
    calendar=dates.unique().sort_values()
    full_target.loc[dates.isin(calendar[-2:])]=np.nan
    confirmation=(dates>=pd.Timestamp('2015-01-01'))&(dates<=calendar[-3])
    confirm_signals={baseline_id:baseline_signal,'reference_res20s1_a1':f.res20s1}
    if winner['parameters']['family']=='Momentum':
        selected_signal=smooth(f[winner['parameters']['momentum']],winner['parameters']['alpha'])
    elif winner['parameters']['family']=='C1_rule':
        selected_signal=smooth(rule,alpha)
    else:
        family=winner['parameters']['family']
        pred,audit=fit_predict_family(f,m,full_target,[2015,2016], 'C1' if family=='C2' else family,model_dir=OUT/'models/confirmation')
        dump(OUT/'confirmation_fit_audit.json',audit)
        raw=m.copy(); now=dates>=pd.Timestamp('2015-01-01')
        if family=='B': raw.loc[now]=(m+winner['parameters']['lambda']*centered_rank(pred)).loc[now]
        elif family=='C1': raw.loc[now]=(m*pred.clip(0,1)).loc[now]
        elif family=='C2': raw.loc[now]=(m*(2*pred.clip(0,1)-1)).loc[now]
        else: raw.loc[now]=centered_rank(pred).loc[now]
        selected_signal=smooth(raw,alpha)
    confirm_signals[winner['id']]=selected_signal
    confirm={}
    for name,signal in confirm_signals.items():
        d=daily_account(signal.loc[confirmation],full_target.loc[confirmation])
        d.to_csv(OUT/'daily'/f'confirmation_{name}.csv')
        confirm[name]={'metrics':metrics(d),'years':[{'year':int(y),**metrics(v)} for y,v in d.groupby(d.index.year)]}
        print(f"Confirmation {name}: Net SR={metrics(d)['net_sharpe']:.3f}",flush=True)
    dump(OUT/'confirmation.json',confirm)
    # Every Train row, including unscored final two dates, must get finite output.
    assert selected_signal.index.equals(inputs['raw_return_1day'].index)
    assert np.isfinite(selected_signal).all() and len(selected_signal)==len(full_target)
    selected_signal.rename('Return').to_frame().to_parquet(OUT/'selected_train_predictions.parquet')
    dump(OUT/'coverage.json',{'rows':len(selected_signal),'dates':len(calendar),'codes':f.index.get_level_values('Code').nunique(),
                             'missing_predictions':int(selected_signal.isna().sum()),
                             'full_60day_momentum_history_fraction':float(f.momentum_available.mean()),
                             'last_two_train_signal_dates_excluded':list(map(str,calendar[-2:])),
                             'reason_last_two_excluded':'label t+2 crosses Train feature boundary even if supplied label is finite'})
    import scipy,pyarrow,lightgbm,sklearn
    versions={'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,
              'scipy':scipy.__version__,'pyarrow':pyarrow.__version__,'lightgbm':lightgbm.__version__,'scikit-learn':sklearn.__version__}
    dump(OUT/'environment.json',versions)
    manifest=json.loads((ROOT/'stock_comp_2026/input_manifest.json').read_text())['files']
    hashes={}
    for name in [*inputs.keys(),'target_1day']:
        filename=f'{name}_train.parquet'; actual=digest(DATA/filename)
        hashes[filename]={'sha256':actual,'matches_distribution':actual==manifest[filename]['sha256']}
    dump(OUT/'data_hashes.json',hashes)
    assert all(v['matches_distribution'] for v in hashes.values())
    firewall.save(OUT/'data_access_audit.json')
    print(f'Research finished. {len(records)} trials. Artifacts: {OUT}',flush=True)


if __name__=='__main__':
    main()
