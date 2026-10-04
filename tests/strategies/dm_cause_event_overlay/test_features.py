import numpy as np
import pandas as pd
import pytest
from stock_comp_2026.strategies.dm_cause_event_overlay import features as fc, submission
from research.experiments.decline_causes import mutate
from research.experiments.sector_momentum import exact, account, fold_dates
from research import evaluation


def inputs(days=150,stocks=12):
    dates=pd.bdate_range('2011-01-03',periods=days,name='Date')
    codes=[f'{i:05d}' for i in range(stocks)]
    index=pd.MultiIndex.from_product([dates,codes],names=['Date','Code'])
    rng=np.random.default_rng(17)
    events=[];eindex=[]
    for day,forecast in [(0,100.),(15,80.),(40,90.),(75,95.)]:
        for j,code in enumerate(codes):
            eindex.append((dates[day],code))
            row={c:100. for c in fc.FINS_COLUMNS}
            row.update(ForecastOperatingProfit=forecast+j*3,TotalAssets=1000.+j*10,
                TypeOfDocument='1QFinancialStatements_Consolidated_JP',
                CurrentFiscalYearStartDate=pd.Timestamp('2010-04-01'),
                CurrentFiscalYearEndDate=pd.Timestamp('2011-03-31'))
            events.append(row)
    return {'raw_return_1day':pd.DataFrame({'Return':rng.normal(0,.01,len(index))},index=index),
        'beta_1day':pd.DataFrame({'Return':1.},index=index),
        'topix_return_1day':pd.DataFrame({'Return':rng.normal(0,.002,len(dates))},index=dates),
        'listed_info':pd.DataFrame({'Sector33Code':np.tile(['0050']*6+['1050']*(stocks-6),days),
                                  'Sector17Code':'1'},index=index),
        'prices_daily_quotes':pd.DataFrame({'Volume':rng.integers(1,1000,len(index)).astype(float),
            'Close':rng.uniform(10,100,len(index)),'TurnoverValue':rng.uniform(100,10000,len(index))},index=index),
        'fins_statements':pd.DataFrame(events,index=pd.MultiIndex.from_tuples(eindex,names=['Date','Code']))[fc.FINS_COLUMNS]}


@pytest.mark.parametrize('cut',[10,50,100])
@pytest.mark.parametrize('source',list(fc.INPUT_COLUMNS)+['ALL','TRUNCATION'])
def test_all_input_prefix_mutation_truncation_and_future_only_stocks(source,cut):
    data=inputs();f=fc.build_features(data);cutoff=data['topix_return_1day'].index[cut]
    changed={}
    for j,(n,v) in enumerate(data.items()):
        changed[n]=v.loc[v.index.get_level_values('Date')<=cutoff] if source=='TRUNCATION' else mutate(v,n,cutoff,81+j) if source in [n,'ALL'] else v
    got=fc.build_features(changed);prefix=f.index[f.index.get_level_values('Date')<=cutoff]
    exact(f.loc[prefix],got.loc[prefix])


def test_disclosure_fresh_one_session_weekend_unchanged_and_no_carry():
    data=inputs();dates=data['topix_return_1day'].index;code='00000'
    f=fc.build_features(data)
    assert np.isnan(f.loc[(dates[15],code),'FUND_EVENT_RAW'])
    assert f.loc[(dates[16],code),'FUND_EVENT_RAW']==pytest.approx(-.02)
    assert f.loc[(dates[16],code),'FreshFundEvent']==1
    assert f.loc[(dates[17],code),'FreshFundEvent']==0
    assert np.isnan(f.loc[(dates[17],code),'FundDelta'])
    assert f.loc[(dates[17],code),'FundOverlay']==0
    # A Friday revision moves to Saturday: still first available Monday.
    old=dates[40]; assert old.dayofweek==0
    fins=data['fins_statements']; row=fins.loc[[(old,code)]].copy()
    row.index=pd.MultiIndex.from_tuples([(old-pd.Timedelta(days=1),code)],names=['Date','Code'])
    data['fins_statements']=pd.concat([fins.drop((old,code)),row])
    f=fc.build_features(data)
    assert f.loc[(old,code),'FreshFundEvent']==1
    assert f.loc[(dates[41],code),'FreshFundEvent']==0
    data['fins_statements'].loc[(dates[75],code),'ForecastOperatingProfit']=90.
    f=fc.build_features(data)
    assert f.loc[(dates[76],code),'FreshFundEvent']==0
    assert f.loc[(dates[76],code),'FundOverlay']==0


def test_fiscal_basis_and_missing_scale_priority():
    data=inputs();dates=data['topix_return_1day'].index;code='00000';fins=data['fins_statements']
    fins.loc[(dates[15],code),'TypeOfDocument']='EarnForecastRevision'
    fins.loc[(dates[15],code),'TotalAssets']=np.nan
    assert fc.build_features(data).loc[(dates[16],code),'FUND_EVENT_RAW']==pytest.approx(-.02)
    fins.loc[(dates[40],code),fc.FISCAL]=[pd.Timestamp('2011-04-01'),pd.Timestamp('2012-03-31')]
    assert fc.build_features(data).loc[(dates[41],code),'FreshFundEvent']==0
    fins.loc[(dates[40],code),fc.FISCAL]=[pd.Timestamp('2010-04-01'),pd.Timestamp('2011-03-31')]
    fins.loc[(dates[40],code),'TypeOfDocument']='2QFinancialStatements_NonConsolidated_JP'
    assert fc.build_features(data).loc[(dates[41],code),'FreshFundEvent']==0
    # Known information event without a scale cannot become a Flow event.
    data=inputs();data['fins_statements'].loc[(slice(None),code),'TotalAssets']=np.nan
    data['prices_daily_quotes'].Volume=100.
    data['prices_daily_quotes'].loc[(dates[40],code),'Volume']=1000.
    data['raw_return_1day'].loc[(dates[40],code),'Return']=-.10
    f=fc.build_features(data)
    assert f.loc[(dates[41],code),'FreshFundEvent']==1
    assert f.loc[(dates[41],code),'FundOverlay']==0
    assert f.loc[(dates[41],code),'FlowActive']==0


def test_active_average_ranks_ties_missing_singletons():
    index=pd.MultiIndex.from_product([pd.to_datetime(['2011-01-03','2011-01-04']),list('abcdef')],names=['Date','Code'])
    raw=pd.Series([1,1,3,np.nan,0,np.inf,2,np.nan,np.nan,np.nan,np.nan,np.nan],index=index,dtype=float)
    active=pd.Series([True,True,True,True,False,True]+[True]*6,index=index)
    got=fc.event_rank(raw,active)
    np.testing.assert_array_equal(got.iloc[:6],[-1/3,-1/3,2/3,0,0,0])
    np.testing.assert_array_equal(got.iloc[6:],np.zeros(6))
    assert got.iloc[0]==got.iloc[1]
    np.testing.assert_array_equal(fc.event_rank(raw*0,active),np.zeros(12))


def test_fixed_flow_gating_sector_pit_volume_and_mutual_exclusion():
    data=inputs(days=90);dates=data['topix_return_1day'].index
    data['topix_return_1day'].Return=0.;data['raw_return_1day'].Return=0.
    data['prices_daily_quotes'].Volume=100.
    data['raw_return_1day'].loc[(dates[30],'00000'),'Return']=-.10
    data['prices_daily_quotes'].loc[(dates[30],'00000'),'Volume']=1000.
    f=fc.build_features(data)
    assert np.isnan(f.loc[(dates[20],'00000'),'AbnormalVolume'])
    assert f.loc[(dates[31],'00000'),'AbnormalVolume']==pytest.approx(np.log1p(1000)-np.log1p(100))
    assert f.loc[(dates[31],'00000'),'FLOW_EVENT_RAW']>0
    assert f.loc[(dates[32],'00000'),'FlowActive']==0
    assert not (f.FundActive.eq(1)&f.FlowActive.eq(1)).any()
    assert f.loc[f.FundActive.eq(0),'FundOverlay'].eq(0).all()
    assert f.loc[f.FlowActive.eq(0),'FlowOverlay'].eq(0).all()
    np.testing.assert_array_equal(f.SLOW_CAUSE_AWARE,f.SlowRank+f.FundOverlay+f.FlowOverlay)
    data['raw_return_1day'].Return=np.tile([.01]*6+[.03]*6,90)
    data['listed_info'].loc[(slice(dates[30],None),'00006'),'Sector33Code']='0050'
    f=fc.build_features(data)
    assert f.loc[(dates[30],'00006'),'SectorShock']==pytest.approx(.03)
    assert f.loc[(dates[31],'00006'),'SectorShock']==pytest.approx(.09/7)
    data['raw_return_1day']=data['raw_return_1day'].drop((dates[45],'00000'))
    assert np.isnan(fc.build_features(data).loc[(dates[46],'00000'),'WithinShock'])


def test_anchor_rank_portfolio_unchanged_shuffle_contract_adapter(tmp_path):
    from stock_comp_2026.strategies.dm_slow_multifactor import features as original
    data=inputs();f=fc.build_features(data)
    expected=original.build_features({n:data[n][cols] for n,cols in original.INPUT_COLUMNS.items()}).size_liquidity
    exact(f.SLOW_CONTROL,expected.rename('SLOW_CONTROL'))
    exact(evaluation.weights(f.SLOW_CONTROL)[0].rename('weight'),evaluation.weights(f.SlowRank)[0].rename('weight'))
    exact(f,fc.build_features({n:v.sample(frac=1,random_state=43) for n,v in data.items()}))
    for n,v in data.items():v.to_parquet(tmp_path/f'{n}_train.parquet')
    for n in fc.CANDIDATES:exact(fc.score(f,n).to_frame(),submission.predict(tmp_path,n))
    rng=np.random.default_rng(24);target=pd.Series(rng.normal(0,.01,len(f)),index=f.index,name='Return');target.iloc[0]=np.nan
    for n in fc.CANDIDATES:account(fc.score(f,n),target)
    dup=dict(data);dup['raw_return_1day']=pd.concat([data['raw_return_1day'],data['raw_return_1day'].iloc[:1]])
    with pytest.raises(ValueError):fc.build_features(dup)
    assert f.index.equals(data['raw_return_1day'].index)
    assert np.isfinite(f[list(fc.CANDIDATES)]).all().all()


def test_t_plus_two_maturity_purge():
    calendar=pd.bdate_range('2011-01-03','2016-03-31')
    days,audit=fold_dates(calendar,range(2011,2017))
    for date in days:assert calendar[calendar.get_loc(date)+2].year==date.year
    assert len(audit)==6


def test_fixed_cause_state_priority_and_missing():
    from research.experiments import cause_event_overlay as d
    f=fc.build_features(inputs()).iloc[:5].copy()
    f['StockRawReturn']=-.01
    f['FreshFundEvent']=[1.,1.,0.,0.,0.]
    f['FundDelta']=[-1.,1.,np.nan,np.nan,np.nan]
    f['SectorShock']=[-.02,-.02,-.02,0.,np.nan]
    f['WithinShock']=-.03;f['AbnormalVolume']=1.
    assert d.cause_states(f).tolist()==['PERSISTENT_INFO','OTHER','COMMON_INDUSTRY','TRANSIENT_PRESSURE','OTHER']


def test_cumulative_targets_consecutive_missing_and_maturity():
    from research.experiments import cause_event_overlay as d
    calendar=pd.bdate_range('2011-01-03','2016-03-31',name='Date')
    index=pd.MultiIndex.from_product([calendar,['a','b']],names=['Date','Code'])
    target=pd.Series(np.tile([.01,.02],len(calendar)),index=index,name='Return')
    target.loc[(calendar[2],'a')]=np.nan
    for h in [1,2,3,5]:
        got=d.cumulative_targets(target,calendar,h)
        assert got.loc[(calendar[0],'b')]==pytest.approx(.02*h)
        if h>=3:assert np.isnan(got.loc[(calendar[0],'a')])
        days,audit=d.diagnostic_dates(calendar,range(2011,2017),h)
        for date in days:assert calendar[calendar.get_loc(date)+h+1].year==date.year
        assert len(audit)==6
    # Absent stock row must not silently become an observed-row shift.
    target=target.drop((calendar[1],'b'))
    assert np.isnan(d.cumulative_targets(target,calendar,2).loc[(calendar[0],'b')])


def test_turnover_partitions_event_exit_and_rank_displacement():
    from research.experiments import cause_event_overlay as d
    data=inputs();f=fc.build_features(data)
    rng=np.random.default_rng(84);target=pd.Series(rng.normal(0,.01,len(f)),index=f.index,name='Return')
    base,bh,_=account(f.SLOW_CONTROL.rename('Return'),target)
    for n in fc.CANDIDATES:
        daily,h,_=account(fc.score(f,n),target)
        p=d.turnover_panel(f,h,bh,target,n)
        assert abs(p.turnover.sum()-daily.turnover.sum())<1e-12
        assert abs(p.cost.sum()-daily.cost.sum())<1e-12
        assert abs(p.delta_gross.sum()-(daily.gross-base.gross).sum())<1e-12
        assert abs(p.delta_net.sum()-(daily.net-base.net).sum())<1e-12
        active=f.FundActive.eq(1)|(f.FlowActive.eq(1) if n=='SLOW_CAUSE_AWARE' else False)
        previous=active.groupby('Code').shift(1).fillna(False).astype(bool)
        assert p.loc[previous&~active,'event_group'].eq('PRIOR_EVENT_ONLY').all()
        assert p.loc[~active&~previous,'event_group'].eq('NON_EVENT').all()
        assert p.loc[p.transition.eq('ENTRY'),'turnover'].gt(0).all()
    assert d.source_scan()['status']=='PASS'


def test_official_no_argument_adapter_uses_grader_working_directory(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    data=inputs(days=80)
    for n,v in data.items():v.to_parquet(tmp_path/f'{n}_train.parquet')
    root=Path(__file__).resolve().parents[3]
    strategy=root/'stock_comp_2026/strategies/dm_cause_event_overlay'
    script='\n'.join(['import sys',f'sys.path.insert(0,{str(root)!r})',
        'from pathlib import Path','from research import firewall; firewall.install()',
        'from stock_comp_2026 import evaluate_script as official',
        f'p=official.load_prediction(Path({str(strategy)!r}),Path({str(tmp_path)!r}))',
        f'assert len(p)=={len(data["raw_return_1day"])}','assert p.notna().all().all()',
        "assert not any('target' in x for x in firewall.ACCESSES)"])
    result=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
