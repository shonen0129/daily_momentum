import numpy as np
import pandas as pd
import pytest
from stock_comp_2026.strategies.dm_raw_ewma_ablation import features as sc, primitives, submission
from stock_comp_2026.strategies.dm_sector_confirmation import features as prior
from research.experiments import raw_ewma_ablation as d


def inputs(days=180, stocks=12):
    dates=pd.bdate_range('2011-01-03',periods=days,name='Date')
    index=pd.MultiIndex.from_product([dates,[f'{i:05d}' for i in range(stocks)]],names=['Date','Code'])
    rng=np.random.default_rng(42)
    return {'raw_return_1day':pd.DataFrame({'Return':rng.normal(.001,.01,len(index))},index=index),
        'beta_1day':pd.DataFrame({'Return':1.},index=index),'topix_return_1day':pd.DataFrame({'Return':rng.normal(0,.002,len(dates))},index=dates),
        'listed_info':pd.DataFrame({'Sector33Code':'0050'},index=index)}


def test_states_missing_zero_and_prior_veto_exact():
    idx=inputs(days=1,stocks=11)['raw_return_1day'].index
    stock=pd.Series([1.,1.,-1.,-1.,0.,-1.,1.,np.nan,-1.,np.inf,1.],index=idx)
    common=pd.Series([1.,-1.,1.,-1.,1.,0.,0.,1.,np.nan,1.,np.inf],index=idx)
    state,veto=sc.context(stock,common)
    assert state.iloc[:4].tolist()==['A','B','C','D']
    np.testing.assert_array_equal(veto,[1.,1.,0.,-1.,0.,-1.,1.,0.,0.,0.,0.])
    ps,_,pv=prior.context(stock,common);d.exact(state,ps);d.exact(veto,pv)
    with pytest.raises(ValueError):sc.score(sc.build_features(inputs()),'EXTRA_CANDIDATE')
    with pytest.raises(ValueError):submission.predict('unused','EXTRA_CANDIDATE')


def test_raw_control_independent_no_sector_or_rank_and_single_ewma(monkeypatch):
    data=inputs();f=sc.build_features(data)
    assert d.primitive_parity(data,f)['prior08_veto_bitwise']
    d.exact(sc.score(f,'RAW_EWMA_CONTROL'),sc.build_control({k:v for k,v in data.items() if k!='listed_info'}))
    data['listed_info'].loc[:,'Sector33Code']='NEW'
    d.exact(f.RawControl_ewm,sc.build_features(data).RawControl_ewm)
    d.exact(f.RawControl_ewm,primitives.smooth(f.StockMom60_raw.fillna(0),.25).rename('RawControl_ewm'))
    assert not np.array_equal(f.RawControl_ewm,f.MOM60)
    d.exact(f.ShortVeto_ewm,primitives.smooth(f.ShortVeto_raw,.25).rename('ShortVeto_ewm'))
    monkeypatch.setattr(submission,'load_train',lambda _,use_context=True:inputs() if use_context else {k:v for k,v in inputs().items() if k!='listed_info'})
    for name in sc.CANDIDATES:d.exact(sc.score(f,name).to_frame(),submission.predict('unused',name))


@pytest.mark.parametrize('source',list(sc.INPUT_COLUMNS)+['ALL','TRUNCATION'])
def test_prefix_each_source(source):
    data=inputs();f=sc.build_features(data);cutoff=f.index.get_level_values('Date').unique()[95]
    changed=dict(data)
    for j,(name,frame) in enumerate(data.items()):
        if source=='TRUNCATION':changed[name]=frame.loc[frame.index.get_level_values('Date')<=cutoff]
        elif source in [name,'ALL']:changed[name]=d.mutate(frame,name,cutoff,42+j)
    idx=f.index[f.index.get_level_values('Date')<=cutoff]
    d.exact(f.loc[idx],sc.build_features(changed).loc[idx])


def test_full_audit_extra_suffix_cases_shuffle_determinism():
    data=inputs();f=sc.build_features(data)
    result=d.prefix_audit(data,f,{'prefix_cutoffs':['2011-05-16'],'random_seed':20261002})
    assert len(result['cases'])==9
    assert result['control_independent_of_all_history_sectors']
    assert d.source_scan()['status']=='PASS'


def test_min5_pit_self_inclusion_gap_and_delayed_c_veto(monkeypatch):
    data=inputs(days=1,stocks=6);raw=pd.Series([-2.,-1.,0.,1.,2.,6.],index=data['raw_return_1day'].index)
    monkeypatch.setattr(sc,'raw_momentum',lambda _:raw)
    f=sc.build_features(data);assert f.Sector33Common_raw.eq(1).all() and f.ShortVeto_raw.iloc[0]==0
    raw.iloc[-1]=np.nan;assert sc.build_features(data).Sector33Common_raw.eq(0).all()
    assert sc.build_features(data).ShortVeto_raw.iloc[0]==-2
    raw.iloc[-2]=np.nan;f=sc.build_features(data)
    assert f.Sector33Common_raw.isna().all() and f.ShortVeto_raw.eq(0).all()
    assert f.RawControl_raw.iloc[0]==-2
    monkeypatch.undo()
    idx=pd.MultiIndex.from_product([pd.bdate_range('2011-01-03',periods=3),['00000']],names=['Date','Code'])
    raw=pd.Series([-2.,-2.,-2.],index=idx);common=pd.Series([-1.,1.,1.],index=idx)
    _,v=sc.context(raw,common);sm=primitives.smooth(v,.25)
    np.testing.assert_array_equal(sm,[-2.,-1.5,-1.125])
    data=inputs(days=250);dates=data['raw_return_1day'].index.get_level_values('Date').unique()
    for key in ['raw_return_1day','beta_1day','listed_info']:
        frame=data[key];data[key]=frame.loc[~((frame.index.get_level_values('Code')=='00000')&frame.index.get_level_values('Date').isin(dates[100:130]))]
    f=sc.build_features(data)
    assert f.loc[(dates[130],'00000'),'RawControl_ewm']==0
    assert f.loc[(slice(dates[130],dates[189]),'00000'),'StockMom60_raw'].isna().all()
    assert np.isfinite(f.loc[(dates[190],'00000'),'StockMom60_raw'])
    data['raw_return_1day']=pd.concat([data['raw_return_1day'],data['raw_return_1day'].iloc[:1]])
    with pytest.raises(ValueError,match='unique'):sc.build_features(data)


def test_control_adapter_reads_only_three_sources(tmp_path, monkeypatch):
    data=inputs()
    opened=[]
    def read(path,columns):
        n=path.name.removesuffix('_train.parquet');opened.append(n)
        return data[n][columns]
    monkeypatch.setattr(pd,'read_parquet',read)
    result=submission.predict(tmp_path,'RAW_EWMA_CONTROL')
    assert opened==['raw_return_1day','beta_1day','topix_return_1day']
    d.exact(result,sc.build_control(data).to_frame())
    assert result.index.equals(data['raw_return_1day'].index) and np.isfinite(result.to_numpy()).all()


def test_official_account_all_mechanisms_and_matched_rows(tmp_path):
    data=inputs(days=300);f=sc.build_features(data);target=data['raw_return_1day'].Return.copy();target.iloc[1400]=np.nan
    signals={n:sc.score(f,n) for n in sc.CANDIDATES};signals['MOM60']=f.MOM60.rename('Return')
    daily,holdings={},{}
    for name,score in signals.items():
        daily[name],h,audit=d.account(score,target);holdings[name]=d.add_quintile_costs(d.enrich_holdings(h))
        assert audit['weight_bitwise'] and audit['net_bitwise']
    calendar=f.index.get_level_values('Date').unique();dates,purge=d.fold_dates(calendar,[2011,2012]);dates=dates.rename('Date')
    assert all(x['status']=='PASS' for x in purge)
    fe=f.loc[f.index.get_level_values('Date').isin(dates)];te=target.loc[fe.index]
    he={n:h.loc[fe.index] for n,h in holdings.items()};accounts={n:a.loc[dates] for n,a in daily.items()}
    cv=d.coverage(f,tmp_path,dates)
    assert cv.loc[(cv.scope=='ALL_TRAIN')&(cv.sector=='ALL'),'stock_finite'].iloc[0]<1
    tr=d.transitions(f,calendar,dates,tmp_path);d.turnover_attribution(f,tr,holdings,dates,tmp_path)
    assert d.agreement(fe,te,signals,he,accounts,tmp_path)['status']=='PASS'
    assert d.replacement(fe,te,he['RAW_EWMA_CONTROL'],he['RAW_EWMA_SHORT_VETO'],accounts,tmp_path)['status']=='PASS'
    assert d.turnover_difference(f,tr,holdings['RAW_EWMA_CONTROL'],holdings['RAW_EWMA_SHORT_VETO'],dates,tmp_path)['status']=='PASS'
    assert d.matched_rows(fe,te,signals,he,accounts,tmp_path)['status']=='PASS'
    d.long_protection(he,dates,tmp_path);d.concentration(fe,he,accounts,tmp_path)
    cohorts=pd.read_csv(tmp_path/'C_veto_short_cohorts.csv')
    assert {'annual_base_short_net','annual_candidate_short_net','average_base_weight'}<=set(cohorts)
    rep=pd.read_csv(tmp_path/'replacement_summary.csv');assert {'annual_delta_net','annual_weight_change_contribution'}<=set(rep)
    assert (tmp_path/'C_cohort_sector_distribution.csv').exists()
