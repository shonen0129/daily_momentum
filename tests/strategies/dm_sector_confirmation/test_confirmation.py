import inspect
import numpy as np
import pandas as pd
import pytest
from stock_comp_2026.strategies.dm_sector_confirmation import features as sc, primitives, submission
from stock_comp_2026.strategies.dm_hierarchical_momentum import features as hm
from stock_comp_2026.strategies.dm_trainonly import features as old
from research.experiments import sector_confirmation as d


def inputs(days=180, stocks=12):
    dates=pd.bdate_range('2011-01-03',periods=days,name='Date')
    index=pd.MultiIndex.from_product([dates,[f'{i:05d}' for i in range(stocks)]],names=['Date','Code'])
    rng=np.random.default_rng(42)
    return {'raw_return_1day':pd.DataFrame({'Return':rng.normal(.001,.01,len(index))},index=index),
        'beta_1day':pd.DataFrame({'Return':1.},index=index),'topix_return_1day':pd.DataFrame({'Return':rng.normal(0,.002,len(dates))},index=dates),
        'listed_info':pd.DataFrame({'Sector33Code':'0050'},index=index)}


def test_exact_states_veto_zeros_nonfinite_and_no_rescue():
    index=inputs(days=1,stocks=11)['raw_return_1day'].index
    stock=pd.Series([1.,1.,-1.,-1.,0.,-1.,1.,np.nan,-1.,np.inf,1.],index=index)
    common=pd.Series([1.,-1.,1.,-1.,1.,0.,0.,1.,np.nan,1.,np.inf],index=index)
    state,a,b=sc.context(stock,common)
    assert state.iloc[:4].tolist()==['A','B','C','D']
    assert state.iloc[4:].eq('ZERO_OR_MISSING').all()
    np.testing.assert_array_equal(a,[1.,0.,0.,-1.,0.,0.,0.,0.,0.,0.,0.])
    np.testing.assert_array_equal(b,[1.,1.,0.,-1.,0.,-1.,1.,0.,0.,0.,0.])
    with pytest.raises(ValueError):sc.score(sc.build_features(inputs()),'RESCUE')


@pytest.mark.parametrize('source',list(sc.INPUT_COLUMNS)+['ALL','TRUNCATION'])
def test_prefix_each_source_all_and_truncation(source):
    data=inputs();base=sc.build_features(data);cutoff=base.index.get_level_values('Date').unique()[95]
    changed=dict(data)
    for j,(name,frame) in enumerate(data.items()):
        if source=='TRUNCATION':changed[name]=frame.loc[frame.index.get_level_values('Date')<=cutoff]
        elif source in [name,'ALL']:changed[name]=d.mutate(frame,name,cutoff,42+j)
    idx=base.index[base.index.get_level_values('Date')<=cutoff]
    got=sc.build_features(changed).loc[idx]
    d.exact(base.loc[idx],got)
    for name in sc.CANDIDATES:d.exact(sc.score(base.loc[idx],name),sc.score(got,name))


def test_raw_common_min5_self_inclusion_and_missing_pit(monkeypatch):
    data=inputs(days=1,stocks=6);raw=pd.Series([-2.,-1.,0.,1.,2.,6.],index=data['raw_return_1day'].index)
    monkeypatch.setattr(sc,'raw_momentum',lambda _:raw)
    base=sc.build_features(data);assert base.Sector33Common_raw.eq(1.).all()
    assert base.State.iloc[0]=='C';assert base.ShortVeto_raw.iloc[0]==0
    raw.iloc[-1]=12.;assert sc.build_features(data).Sector33Common_raw.eq(2.).all()
    raw.iloc[-1]=np.nan;assert sc.build_features(data).Sector33Common_raw.eq(0.).all()
    assert sc.build_features(data).ShortVeto_raw.iloc[0]==-2
    raw.iloc[-2]=np.nan;got=sc.build_features(data)
    assert got.Sector33Common_raw.isna().all() and got.ShortVeto_raw.eq(0).all()
    raw.iloc[:]=[-2.,-1.,0.,1.,2.,6.]
    data['listed_info'].iloc[0,0]='9999';got=sc.build_features(data)
    assert pd.isna(got.Sector33Common_raw.iloc[0]) and got.Sector33Common_raw.iloc[1:].notna().all()
    extra=data['listed_info'].iloc[:1].copy();extra.index=pd.MultiIndex.from_tuples([(raw.index[0][0],'NOT_PRESENT')],names=['Date','Code'])
    data['listed_info']=pd.concat([data['listed_info'],extra]);d.exact(got,sc.build_features(data))


def test_primitives_common_baseline_adapter_transform_order(monkeypatch):
    data=inputs();f=sc.build_features(data)
    assert d.primitive_parity(data,f)['prior07_common_and_PIT_bitwise']
    monkeypatch.setattr(submission,'load_train',lambda _:data)
    for name,col in sc.CANDIDATES.items():
        raw=f['Confirmed_raw' if name=='SECTOR_CONFIRM' else 'ShortVeto_raw']
        d.exact(f[col],primitives.smooth(raw,.25).rename(col))
        assert not np.array_equal(f[col],primitives.smooth(primitives.centered_rank(raw),.25))
        d.exact(sc.score(f,name).to_frame(),submission.predict('unused',name))
    d.exact(f,sc.build_features(data));d.exact(f,sc.build_features({k:v.sample(frac=1,random_state=9) for k,v in data.items()}))
    assert np.isfinite(f[list(sc.CANDIDATES.values())].to_numpy()).all()
    assert f.index.equals(data['raw_return_1day'].index)


def test_gap_reset_sector_change_and_duplicate_rejection():
    data=inputs(days=250);dates=data['raw_return_1day'].index.get_level_values('Date').unique()
    for n in ['raw_return_1day','beta_1day','listed_info']:
        frame=data[n];mask=(frame.index.get_level_values('Code')=='00000')&frame.index.get_level_values('Date').isin(dates[100:130]);data[n]=frame.loc[~mask]
    f=sc.build_features(data)
    assert f.loc[(dates[130],'00000'),'ShortVeto_ewm']==0
    assert f.loc[(slice(dates[130],dates[189]),'00000'),'StockMom60_raw'].isna().all()
    assert np.isfinite(f.loc[(dates[190],'00000'),'StockMom60_raw'])
    data=inputs();f=sc.build_features(data);date=data['raw_return_1day'].index.get_level_values('Date').unique()[100]
    data['listed_info'].loc[(date,'00000'),'Sector33Code']='NEW_ALONE'
    got=sc.build_features(data)
    for col in sc.CANDIDATES.values():assert got.loc[(date,'00000'),col]==pytest.approx(.75*f.loc[(date-pd.offsets.BDay(),'00000'),col])
    data['listed_info']=pd.concat([data['listed_info'],data['listed_info'].iloc[:1]])
    with pytest.raises(ValueError,match='unique'):sc.build_features(data)


def test_official_account_mechanism_and_all_diagnostic_routes(tmp_path):
    assert d.source_scan()['status']=='PASS'
    data=inputs(days=300);f=sc.build_features(data);target=data['raw_return_1day'].Return.copy();target.iloc[1400]=np.nan
    signals={n:sc.score(f,n) for n in sc.CANDIDATES};signals['MOM60']=f.MOM60.rename('Return')
    daily,holdings={},{}
    for n,s in signals.items():
        daily[n],h,audit=d.account(s,target);holdings[n]=d.enrich_holdings(h)
        assert audit['net_bitwise'] and audit['weight_bitwise']
    calendar=f.index.get_level_values('Date').unique();dates,purge=d.fold_dates(calendar,[2011,2012]);dates=dates.rename('Date')
    fe=f.loc[f.index.get_level_values('Date').isin(dates)];te=target.loc[fe.index];he={n:h.loc[fe.index] for n,h in holdings.items()};accounts={n:a.loc[dates] for n,a in daily.items()}
    cover=d.coverage(f,tmp_path,dates)
    assert cover.loc[(cover.scope=='ALL_TRAIN')&(cover.sector=='ALL'),'agreement_finite'].iloc[0]<1
    tr=d.transitions(f,calendar,dates,tmp_path)
    d.turnover_attribution(f,tr,holdings,dates,tmp_path)
    d.persistence(signals,holdings,calendar,dates,tmp_path);d.rank_changes(signals,calendar,dates,tmp_path)
    assert d.agreement(fe,te,signals,he,accounts,tmp_path)['status']=='PASS'
    assert d.replacement(fe,te,he['MOM60'],he['SHORT_DISAGREE_VETO'],accounts,tmp_path)['status']=='PASS'
    d.long_protection(he,dates,tmp_path);d.concentration(fe,he,accounts,tmp_path)
    transition=pd.read_csv(tmp_path/'state_transitions.csv')
    probs=transition.groupby(['scope','from']).transition_probability.sum()
    assert np.allclose(probs.loc[probs>0],1.)
    duration=pd.read_csv(tmp_path/'state_duration_persistence.csv')
    assert ((duration.five_day_persistence<=duration.one_day_persistence)|duration.five_day_persistence.isna()).all()
    assert (tmp_path/'removed_added_unchanged_names.parquet').is_file()
