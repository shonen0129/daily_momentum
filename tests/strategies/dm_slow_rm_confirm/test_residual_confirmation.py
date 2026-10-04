import numpy as np
import pandas as pd
from research import evaluation
from research.experiments import slow_rm_descriptors as descriptors, slow_rm_statistics as statistics
from stock_comp_2026.strategies.dm_slow_rm_confirm import features as f


def sample():
    rng=np.random.default_rng(77)
    idx=pd.MultiIndex.from_product([pd.bdate_range('2010-01-01',periods=330),[f'{i:05d}' for i in range(60)]],names=['Date','Code'])
    size=rng.normal(size=len(idx));illiq=rng.normal(size=len(idx))
    scores=pd.DataFrame({'Size':size,'Illiquidity':illiq,'SLOW_CONTROL':size+illiq,'MOM60':rng.normal(size=len(idx))},index=idx)
    market=pd.DataFrame({'Return':rng.normal(0,.01,330)},index=pd.DatetimeIndex(idx.levels[0],name='Date'))
    return scores,market


def test_unregularized_residual_orthogonality_and_fixed_score():
    s,_=sample();p,c=f.construct(s)
    for _,g in p.groupby('Date'):
        residual=g.RESIDUAL_MOM_RAW.to_numpy()
        assert abs(residual.mean())<1e-14
        assert abs(residual@g.SizeRank.to_numpy())<1e-12
        assert abs(residual@g.IlliquidityRank.to_numpy())<1e-12
    pd.testing.assert_series_equal(f.score(p),(p.SLOW_RANK+p.SLOW_RANK.abs()*f.centered_rank(p.RM)).rename('Return'),check_exact=True)
    assert np.isfinite(f.score(p)).all()


def test_mutation_truncation_shuffle_and_regime_threshold_are_causal():
    s,m=sample();p,c,state=descriptors.describe(s,m);cut=s.index.levels[0][300]
    changed=s.copy();changed.loc[changed.index.get_level_values('Date')>cut]*=-1e4
    altered=m.copy();altered.loc[altered.index>cut,'Return']=1e3
    got,coeff,st=descriptors.describe(changed,altered)
    prefix=p.index.get_level_values('Date')<=cut
    pd.testing.assert_frame_equal(p.loc[prefix],got.loc[prefix],check_exact=True)
    got,_,_=descriptors.describe(s.loc[prefix],m.loc[m.index<=cut])
    pd.testing.assert_frame_equal(p.loc[prefix],got,check_exact=True)
    got,_,_=descriptors.describe(s.sample(frac=1,random_state=1),m.sample(frac=1,random_state=2))
    pd.testing.assert_frame_equal(p,got,check_exact=True)
    assert state.market_vol_past_median.loc[cut]==state.market_vol60.loc[state.index<cut].median()


def test_bins_before_missing_target_and_exact_spearman():
    x=np.arange(12,dtype=float);y=x/100;y[[1,7]]=np.nan
    spread,ic=statistics.batch_stat(x,y)
    assert np.isclose(spread[0],np.nanmean(y[8:])-np.nanmean(y[:4]))
    idx=pd.MultiIndex.from_product([[pd.Timestamp('2012-01-01')],list(range(12))],names=['Date','Code'])
    reference=evaluation.rankic(pd.Series(x,index=idx),pd.Series(y,index=idx)).iloc[0]
    assert np.isclose(ic[0],reference)
    tied=np.zeros(12);spread,ic=statistics.batch_stat(tied,y)
    assert np.isnan(spread[0]) and np.isnan(ic[0])


def test_transition_uses_previous_membership_and_lags_exchange_grid():
    s,m=sample();p,_,_=descriptors.describe(s,m)
    # Definition checked against an independent full date/code membership grid.
    side=np.sign(p.slow_w)
    previous=side.unstack('Code').shift(1).fillna(0).stack(future_stack=True).reindex(p.index)
    pd.testing.assert_series_equal(p.previous_side,previous.rename('previous_side'),check_exact=True)
    assert (p.loc[(side>0)&(previous<=0),'transition']==1).all()
    assert (p.loc[(side==0)&(previous>0),'transition']==3).all()
    assert (p.loc[(side<0)&(previous>=0),'transition']==4).all()


def test_hac_batch_matches_missing_aware_reference_and_bh():
    a=np.array([[.01,.02,np.nan,.03,.0],[-.01,-.02,.01,.02,.03]])
    expected=np.array([evaluation.hac_t(pd.Series(x)) for x in a])
    np.testing.assert_array_equal(statistics.hac_batch(a),expected)
    np.testing.assert_allclose(statistics.bh([.01,.04,.2,np.nan])[:3],[.03,.06,.2])


def test_undefined_observed_statistic_is_not_significant():
    from research.experiments.slow_rm_bundle import audited_permutation_table
    original=pd.DataFrame({'observed':[.1,np.nan],'p_positive':[.2,.0005],'p_two_sided':[.3,.0005]})
    corrected=audited_permutation_table(original)
    assert corrected.iloc[0].p_two_sided==.3
    assert corrected.iloc[1][['p_positive','p_two_sided']].isna().all()
    assert original.iloc[1].p_two_sided==.0005


def test_self_contained_submission_adapter_missing_labels_and_index(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    from stock_comp_2026.strategies.dm_slow_rm_confirm import submission
    dates=pd.bdate_range('2012-01-02',periods=95)
    codes=[str(10000+i) for i in range(15)]
    idx=pd.MultiIndex.from_product([dates,codes],names=['Date','Code'])
    raw=pd.DataFrame({'Return':np.sin(np.arange(len(idx)))*.01},index=idx)
    values=np.tile(np.arange(1.,16.),len(dates))
    inputs={'prices_daily_quotes':pd.DataFrame({'Close':100+values,'TurnoverValue':values*1e6},index=idx),
            'raw_return_1day':raw,'beta_1day':pd.DataFrame({'Return':1.},index=idx),
            'topix_return_1day':pd.DataFrame({'Return':np.cos(np.arange(len(dates)))*.002},index=dates.rename('Date')),
            'listed_info':pd.DataFrame({'Sector17Code':'A'},index=idx)}
    finsidx=pd.MultiIndex.from_product([dates[[0,60]],codes],names=['Date','Code'])
    inputs['fins_statements']=pd.DataFrame(1000.,index=finsidx,columns=f.factors.slow.INPUT_COLUMNS['fins_statements'])
    inputs['raw_return_1day'].iloc[::19]=np.nan
    inputs['prices_daily_quotes'].iloc[::29]=0.
    for name,frame in inputs.items():frame.to_parquet(tmp_path/(name+'_train.parquet'))
    expected=f.score(f.construct(f.components(inputs)[0])[0]).to_frame()
    got=submission.predict(tmp_path)
    pd.testing.assert_frame_equal(got,expected,check_exact=True)
    assert got.index.equals(raw.index) and np.isfinite(got.to_numpy()).all()
    folder=Path(submission.__file__).parent
    script='import submission,sys; p=submission.predict(sys.argv[1]); assert p.shape[1]==1 and p.notna().all().all()'
    result=subprocess.run([sys.executable,'-c',script,str(tmp_path)],cwd=folder,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
