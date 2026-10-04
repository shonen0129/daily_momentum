"""Diagnostic OLS, causality, partition and official accounting regressions."""
import numpy as np
import pandas as pd
import pytest

from research.experiments import slow_size_illiq_components as dc
from research.experiments import slow_size_illiq_diagnostic as driver
from research.experiments.slow_multifactor import exact
from stock_comp_2026.strategies.dm_slow_multifactor import features as slow
from stock_comp_2026 import evaluate_script as official


def features():
    idx = pd.MultiIndex.from_product([pd.bdate_range('2012-01-02', periods=12),
                                      [str(10000+i) for i in range(30)]], names=['Date','Code'])
    rng = np.random.default_rng(123)
    size = pd.Series(rng.normal(size=len(idx)), index=idx)
    illiq = .7*size + pd.Series(rng.normal(size=len(idx)), index=idx)*.5
    f = pd.DataFrame({'z_size':size,'z_amihud':illiq})
    f['size_liquidity'] = slow.zscore(f.mean(axis=1))
    return f


def test_residual_ols_matches_independent_lstsq_and_is_orthogonal():
    f = features()
    residual, coeff = dc.residualize(f.z_size, f.z_amihud)
    for date, sub in f.groupby('Date'):
        x = np.column_stack([np.ones(len(sub)),sub.z_amihud])
        independent = np.linalg.lstsq(x, sub.z_size, rcond=None)[0]
        assert np.allclose(coeff.loc[date,['intercept','slope']], independent, rtol=0,atol=1e-14)
        r = residual.xs(date)
        assert abs(r.mean())<1e-14
        assert abs(np.dot(r,sub.z_amihud))<1e-13


def test_decomposition_future_mutation_truncation_and_shuffle_exact():
    f = features()
    base, c = dc.decompose(f)
    cutoff = f.index.get_level_values('Date').unique()[5]
    prefix = f.index[f.index.get_level_values('Date')<=cutoff]
    changed = f.copy()
    changed.loc[~changed.index.isin(prefix)] = 1e6
    for version in [changed, f.loc[prefix]]:
        got, gc = dc.decompose(version)
        exact(base.loc[prefix],got.loc[prefix])
        exact(c.loc[:cutoff],gc.loc[:cutoff])
    got, gc = dc.decompose(f.sample(frac=1,random_state=31))
    exact(base,got)
    exact(c,gc)


def test_zero_variance_regressor_and_missing_input_rejection():
    f = features()
    x = f.z_amihud*0+2
    r, c = dc.residualize(f.z_size,x)
    assert c.slope.eq(0).all()
    assert r.groupby('Date').mean().abs().max()<1e-14
    x.iloc[0]=np.nan
    with pytest.raises(ValueError,match='finite'):
        dc.residualize(f.z_size,x)


def test_bins_ties_not_split_and_no_cross_date_reference():
    idx = pd.MultiIndex.from_product([pd.to_datetime(['2012-01-02','2012-01-03']),
                                      list('abcdef')], names=['Date','Code'])
    v = pd.Series([1,1,2,2,3,3,9,9,9,9,9,9],index=idx,dtype=float)
    b = dc.bins(v)
    assert b.iloc[:6].tolist()==[1,1,2,2,3,3]
    assert b.iloc[6:].eq(2).all()
    assert dc.centered_rank(v).iloc[6:].eq(0).all()


def test_groups_exhaustive_exclusive_and_disagreement_priority():
    idx=pd.MultiIndex.from_product([pd.to_datetime(['2012-01-02']),range(9)],names=['Date','Code'])
    a=pd.Series([1,1,0,-1,-1,0,1,-1,0],index=idx,dtype=float)
    b=pd.Series([1,0,1,-1,0,-1,-1,1,0],index=idx,dtype=float)
    assert dc.agreement_groups(a,b).tolist()==dc.GROUPS[:6]+['SIGNAL_DISAGREEMENT','SIGNAL_DISAGREEMENT','OTHER']


def test_account_missing_target_and_exit_costs_reconcile_official():
    f=features();score=f.size_liquidity
    target=pd.Series(np.sin(np.arange(len(f)))*.01,index=f.index,name='Return')
    target.iloc[::11]=np.nan
    d,h,receipt=driver.account(score,target)
    net=official.compute_pl(score.rename('Return').to_frame(),target.to_frame()).groupby('Date').sum()
    exact(d.net.rename('net'),net.rename('net'))
    neutral=h.w.eq(0)&h.cost.gt(0)
    assert neutral.any()
    assert h.loc[neutral,'net'].eq(-h.loc[neutral,'cost']).all()
    assert h.loc[target.isna(),'cost'].eq(0).all()
    assert np.allclose(h.long_net+h.short_net,h.net,rtol=0,atol=1e-15)
    assert receipt['strict_uint64']


def test_partition_retains_empty_cells_and_neutral_costs():
    f=features();panel,_=dc.decompose(f)
    target=pd.Series(.01,index=f.index,name='Return')
    h=driver.holdings(panel.SLOW_CONTROL,target)
    dates=f.index.get_level_values('Date').unique()
    values=h[['gross','net','cost']]
    label=pd.Series(1.,index=f.index)
    daily,summary,error=driver.partition(label,[1.,2.,3.],values,target,dates)
    empty=daily.group.eq(3.)
    assert daily.loc[empty,'stock_count'].eq(0).all()
    assert daily.loc[empty,'forward_target_mean'].isna().all()
    assert error<1e-14
    assert np.isclose(summary.loc[summary.scope.eq('POOLED'),'period_net'].sum(),h.net.sum(),rtol=0,atol=1e-14)
