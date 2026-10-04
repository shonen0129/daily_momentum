import numpy as np
import pandas as pd
import pytest
from stock_comp_2026.strategies.dm_decline_causes import features as fc, submission
from research.experiments import decline_causes as driver
from research import evaluation


def inputs(days=150,stocks=12):
    dates=pd.bdate_range('2011-01-03',periods=days,name='Date')
    codes=[f'{i:05d}' for i in range(stocks)]
    index=pd.MultiIndex.from_product([dates,codes],names=['Date','Code'])
    rng=np.random.default_rng(17)
    events=[];eindex=[]
    for day,forecast in [(0,100.),(15,80.),(40,90.),(75,95.)]:
        for j,code in enumerate(codes):
            eindex.append((dates[day],code));events.append([forecast+j*3,1000.+j*10,'1QFinancialStatements_Consolidated_JP',pd.Timestamp('2010-04-01'),pd.Timestamp('2011-03-31')])
    return {'raw_return_1day':pd.DataFrame({'Return':rng.normal(0,.01,len(index))},index=index),
        'beta_1day':pd.DataFrame({'Return':1.},index=index),
        'topix_return_1day':pd.DataFrame({'Return':rng.normal(0,.002,len(dates))},index=dates),
        'listed_info':pd.DataFrame({'Sector33Code':np.tile(['0050']*6+['1050']*(stocks-6),days)},index=index),
        'prices_daily_quotes':pd.DataFrame({'Volume':rng.integers(1,1000,len(index)).astype(float)},index=index),
        'fins_statements':pd.DataFrame(events,index=pd.MultiIndex.from_tuples(eindex,names=['Date','Code']),columns=fc.FINS_COLUMNS)}


@pytest.mark.parametrize('cut',[10,50,100])
@pytest.mark.parametrize('source',list(fc.INPUT_COLUMNS)+['ALL','TRUNCATION'])
def test_all_sources_future_mutation_truncation_and_future_only_stock(source,cut):
    data=inputs();f=fc.build_features(data);cutoff=data['topix_return_1day'].index[cut]
    changed={}
    for j,(n,v) in enumerate(data.items()):
        changed[n]=v.loc[v.index.get_level_values('Date')<=cutoff] if source=='TRUNCATION' else driver.mutate(v,n,cutoff,81+j) if source in [n,'ALL'] else v
    got=fc.build_features(changed);prefix=f.index[f.index.get_level_values('Date')<=cutoff]
    driver.exact(f.loc[prefix],got.loc[prefix])


def test_disclosure_before_after_same_period_and_fixed_state():
    data=inputs();dates=data['topix_return_1day'].index
    f=fc.build_features(data);code='00000'
    assert np.isnan(f.loc[(dates[15],code),'FUND_REV_raw'])
    assert f.loc[(dates[16],code),'FUND_REV_raw']==pytest.approx(-.02)
    assert f.loc[(dates[40],code),'FUND_REV_raw']==pytest.approx(-.02)
    assert f.loc[(dates[41],code),'FUND_REV_raw']==pytest.approx(.01)
    assert f.loc[(dates[16],code),'FundDisclosure']==dates[15]+pd.Timedelta('23:59:59')
    # Fiscal roll cannot compare 95 with90 from a different period.
    data['fins_statements'].loc[(dates[75],code),fc.FISCAL]=[pd.Timestamp('2011-04-01'),pd.Timestamp('2012-03-31')]
    assert np.isnan(fc.build_features(data).loc[(dates[76],code),'FUND_REV_raw'])


def test_basis_assets_revision_document_and_missing_disclosure_clear_state():
    data=inputs();dates=data['topix_return_1day'].index;fins=data['fins_statements'];code='00000'
    fins.loc[(dates[15],code),'TypeOfDocument']='EarnForecastRevision'
    fins.loc[(dates[15],code),'TotalAssets']=np.nan
    f=fc.build_features(data)
    assert f.loc[(dates[16],code),'FUND_REV_raw']==pytest.approx(-.02)
    assert f.loc[(dates[16],code),'PITAssets']==1000
    fins.loc[(dates[40],code),'TypeOfDocument']='2QFinancialStatements_NonConsolidated_JP'
    f=fc.build_features(data)
    assert np.isnan(f.loc[(dates[41],code),'FUND_REV_raw'])
    # A no-forecast disclosure clears the held state; no implicit holding extension.
    fins.loc[(dates[40],code),'TypeOfDocument']='DividendForecastRevision'
    fins.loc[(dates[40],code),'ForecastOperatingProfit']=np.nan
    f=fc.build_features(data)
    assert np.isnan(f.loc[(dates[41],code),'FUND_REV_raw'])
    assert f.loc[(dates[76],code),'FundDelta']==15.  # previous finite95-80 same period/basis


def test_pit_sector_at_tau_and_no_stale_stock_rows():
    data=inputs(days=80);dates=data['topix_return_1day'].index
    data['topix_return_1day'].Return=0.
    data['raw_return_1day'].Return=np.tile([.01]*6+[.03]*6,80)
    data['listed_info'].loc[(slice(dates[30],None),'00006'),'Sector33Code']='0050'
    f=fc.build_features(data)
    assert f.loc[(dates[30],'00006'),'SECTOR33_SHOCK_raw']==pytest.approx(.03)
    assert f.loc[(dates[31],'00006'),'SECTOR33_SHOCK_raw']==pytest.approx(.09/7)
    assert f.loc[(dates[31],'00006'),'WithinShock']==pytest.approx(.03-.09/7)
    missing=pd.MultiIndex.from_tuples([(dates[45],'00000')],names=['Date','Code'])
    data['raw_return_1day']=data['raw_return_1day'].drop(missing)
    f=fc.build_features(data)
    assert np.isnan(f.loc[(dates[46],'00000'),'StockResidualReturn'])
    assert np.isnan(f.loc[(dates[46],'00000'),'FLOW_REV_raw'])


def test_volume_exact_twenty_prior_excludes_today_zero_and_negative():
    data=inputs(days=80);dates=data['topix_return_1day'].index;index=data['raw_return_1day'].index
    data['prices_daily_quotes'].Volume=100.
    data['prices_daily_quotes'].loc[(dates[20],'00000'),'Volume']=1000.
    f=fc.build_features(data)
    assert np.isnan(f.loc[(dates[20],'00000'),'AbnormalVolume'])
    assert f.loc[(dates[21],'00000'),'AbnormalVolume']==pytest.approx(np.log1p(1000)-np.log1p(100))
    assert f.loc[(dates[22],'00000'),'AbnormalVolume']==pytest.approx(0)
    data['prices_daily_quotes'].loc[(dates[20],'00000'),'Volume']=0.
    assert fc.build_features(data).loc[(dates[21],'00000'),'AbnormalVolume']==pytest.approx(-np.log1p(100))
    data['prices_daily_quotes'].loc[(dates[20],'00000'),'Volume']=-1.
    assert np.isnan(fc.build_features(data).loc[(dates[21],'00000'),'AbnormalVolume'])


def test_flow_fixed_reversal_sign_and_composite_exact_weights():
    data=inputs(days=90);dates=data['topix_return_1day'].index
    data['topix_return_1day'].Return=0.;data['raw_return_1day'].Return=0.
    data['prices_daily_quotes'].Volume=100.
    data['raw_return_1day'].loc[(dates[30],'00000'),'Return']=-.10
    data['prices_daily_quotes'].loc[(dates[30],'00000'),'Volume']=1000.
    f=fc.build_features(data)
    assert f.loc[(dates[31],'00000'),'FLOW_REV_raw']>0
    assert f.loc[(dates[31],'00000'),'SECTOR33_SHOCK_raw']<0
    np.testing.assert_array_equal(f.CAUSE_COMPOSITE,f.FUND_REV_rank+f.SECTOR33_SHOCK_rank+f.FLOW_REV_rank)
    assert np.isfinite(f[list(fc.CANDIDATES)]).all().all()
    assert f.groupby('Date').FUND_REV.nunique().eq(12).all()
    assert f.groupby('Date').FLOW_REV.nunique().eq(12).all()


def test_shuffle_duplicate_index_parity_and_official_accounting(tmp_path):
    data=inputs();f=fc.build_features(data)
    driver.exact(f,fc.build_features({n:v.sample(frac=1,random_state=43) for n,v in data.items()}))
    for n,v in data.items():v.to_parquet(tmp_path/f'{n}_train.parquet')
    for n in fc.CANDIDATES:driver.exact(fc.score(f,n).to_frame(),submission.predict(tmp_path,n))
    rng=np.random.default_rng(24);target=pd.Series(rng.normal(0,.01,len(f)),index=f.index,name='Return');target.iloc[0]=np.nan
    for n in fc.CANDIDATES:driver.account(fc.score(f,n),target)
    dup=dict(data);dup['raw_return_1day']=pd.concat([data['raw_return_1day'],data['raw_return_1day'].iloc[:1]])
    with pytest.raises(ValueError):fc.build_features(dup)
    assert driver.source_scan()['status']=='PASS'


def test_session_purge_labels_end_inside_fold():
    calendar=pd.bdate_range('2011-01-03','2016-03-31')
    days,audit=driver.fold_dates(calendar,range(2011,2017))
    for date in days:assert calendar[calendar.get_loc(date)+2].year==date.year
    assert len(audit)==6


def test_official_no_argument_adapter_uses_grader_working_directory(tmp_path):
    import subprocess
    import sys
    import json
    from pathlib import Path
    data=inputs(days=80)
    for n,v in data.items():v.to_parquet(tmp_path/f'{n}_train.parquet')
    root=Path(__file__).resolve().parents[3]
    strategy=root/'stock_comp_2026/strategies/dm_decline_causes'
    script='\n'.join(['import sys',f'sys.path.insert(0,{str(root)!r})',
        'from pathlib import Path','from research import firewall; firewall.install()',
        'from stock_comp_2026 import evaluate_script as official',
        f'p=official.load_prediction(Path({str(strategy)!r}),Path({str(tmp_path)!r}))',
        f'assert len(p)=={len(data["raw_return_1day"])}','assert p.notna().all().all()',
        "assert not any('target' in x for x in firewall.ACCESSES)"])
    result=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
