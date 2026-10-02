import numpy as np
import pandas as pd
import pytest
from stock_comp_2026.strategies.dm_nh_rev import features as f
from stock_comp_2026.strategies.dm_nh_rev.submission import predict
from research.experiments.nh_rev import event_daily, event_summary, evaluation_dates, source_scan


def fixture():
    dates=pd.bdate_range('2010-01-01',periods=330)
    codes=['10000','20000','30000','40000','50000','60000']
    ix=pd.MultiIndex.from_product([dates,codes],names=['Date','Code'])
    r=pd.DataFrame({'Return':np.tile(np.arange(6)*.001,len(dates))},index=ix)
    b=pd.DataFrame({'Return':0.},index=ix)
    m=pd.DataFrame({'Return':0.},index=pd.Index(dates,name='Date'))
    px=pd.DataFrame({'High':101.,'Low':99.,'Close':100.,'AdjustmentFactor':1.},index=ix)
    px.loc[(dates[-1],slice(None)),['High','Low','Close']]=[103.,100.,102.]
    return {'raw_return_1day':r,'beta_1day':b,'topix_return_1day':m,'prices_daily_quotes':px}


def test_direction_event_boundary_and_no_other_features():
    inputs=fixture(); x=f.build_features(inputs); s=f.signal_stages(x)
    assert not s.event.iloc[:-6].any() and s.event.iloc[-6:].all()
    assert s.relative_strength_60.iloc[-6:].is_monotonic_increasing
    assert s.event_rank.iloc[-6:].is_monotonic_decreasing
    assert s.combined_score.iloc[-6:].is_monotonic_decreasing
    assert s.ewma_score.iloc[-6:].is_monotonic_decreasing
    assert np.isfinite(s.ewma_score).all()
    assert not x.high_available.iloc[:250*6].any()
    inputs['prices_daily_quotes'].loc[(slice(None),'10000'),'Close']=101.
    # Equal to prior high is not an event.
    assert not f.signal_stages(f.build_features(inputs)).event.xs('10000',level='Code').any()
    source_scan()


def test_missing_inf_and_relisting_are_neutral_not_future_filled():
    inputs=fixture(); ix=inputs['raw_return_1day'].index
    inputs['raw_return_1day'].iloc[300,0]=np.inf
    inputs['prices_daily_quotes'].loc[ix[-1],'Close']=np.nan
    x=f.build_features(inputs); s=f.signal_stages(x)
    assert np.isfinite(s.ewma_score).all() and not s.event.iloc[-1]
    # Remove one stock for >20 market dates: its feature state must restart.
    dates=ix.get_level_values('Date').unique()
    for k in ['raw_return_1day','beta_1day','prices_daily_quotes']:
        frame=inputs[k]; drop=(frame.index.get_level_values('Code')=='10000') & frame.index.get_level_values('Date').isin(dates[260:300])
        inputs[k]=frame.loc[~drop]
    xx=f.build_features(inputs).xs('10000',level='Code')
    assert not xx.loc[dates[300]:].high_available.any()
    assert xx.loc[dates[300]:].relative_strength_60.eq(0).all()


@pytest.mark.parametrize('source',list(f.INPUT_COLUMNS))
def test_each_source_future_mutation_and_truncation(source):
    inputs=fixture(); original=f.signal_stages(f.build_features(inputs))
    dates=original.index.get_level_values('Date').unique(); cutoff=dates[275]
    changed={k:v.copy() for k,v in inputs.items()}
    frame=changed[source]; mask=frame.index.get_level_values('Date')>cutoff
    frame.loc[mask]=np.nan
    if source=='prices_daily_quotes': frame.loc[mask,'AdjustmentFactor']=.5
    got=f.signal_stages(f.build_features(changed)); prefix=original.index.get_level_values('Date')<=cutoff
    pd.testing.assert_frame_equal(original.loc[prefix],got.loc[prefix],check_exact=True)
    truncated={k:v.loc[v.index.get_level_values('Date')<=cutoff] for k,v in inputs.items()}
    pd.testing.assert_frame_equal(original.loc[prefix],f.signal_stages(f.build_features(truncated)),check_exact=True)


def test_submission_no_target_contract_determinism(tmp_path,monkeypatch):
    inputs=fixture()
    for name,frame in inputs.items(): frame.to_parquet(tmp_path/f'{name}_train.parquet')
    # A target must not be necessary or read.
    (tmp_path/'target_1day_train.parquet').write_text('poison')
    monkeypatch.chdir(tmp_path)
    a=predict(); b=predict()
    pd.testing.assert_frame_equal(a,b,check_exact=True)
    assert a.index.equals(inputs['raw_return_1day'].index)
    assert list(a.columns)==['Return'] and list(a.index.names)==['Date','Code']
    assert np.isfinite(a).all().all()


def test_primary_raw_and_score_signs_and_purge():
    inputs=fixture(); x=f.build_features(inputs); s=f.signal_stages(x)
    target=-s.relative_strength_60
    daily,_=event_daily(s,target,s.index.get_level_values('Date').unique())
    stats=event_summary(daily)
    assert stats['raw_rankic']==pytest.approx(-1.)
    assert stats['score_rankic']==pytest.approx(1.)
    assert stats['raw_q5_minus_q1']<0 and stats['score_q5_minus_q1']>0
    ds=evaluation_dates(s.index,True)
    original=s.index.get_level_values('Date').unique()
    for year in ds.year.unique():
        assert not ds.isin(original[original.year==year][-2:]).any()
