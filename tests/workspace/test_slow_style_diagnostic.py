"""Causal fiscal matching, missing buckets and virtual accounting contracts."""
import numpy as np
import pandas as pd
from research.experiments import slow_style_descriptors as d
from research.experiments.slow_style_diagnostic import portfolio
from research.experiments.slow_style_diagnostic import characteristics, double_sort
from research import evaluation


def financials():
    rows=[]
    for disclosure,end,sales,op,profit,doc in [
        ('2010-05-10','2010-03-31',100.,10.,5.,'JP'),
        ('2011-05-10','2011-03-31',120.,15.,7.,'JP'),
        ('2011-06-01','2010-03-31',999.,99.,99.,'JP'),
        ('2012-05-10','2012-03-31',150.,17.,8.,'IFRS')]:
        e=pd.Timestamp(end);s=e-pd.DateOffset(years=1)+pd.Timedelta(days=1)
        row={c:np.nan for c in d.FIN_COLUMNS}
        row.update(Date=pd.Timestamp(disclosure),Code='A',TypeOfDocument='FYFinancialStatements_Consolidated_'+doc,
                   TypeOfCurrentPeriod='FY',CurrentPeriodStartDate=s,CurrentPeriodEndDate=e,
                   CurrentFiscalYearStartDate=s,CurrentFiscalYearEndDate=e,NetSales=sales,OperatingProfit=op,
                   Profit=profit,Equity=20.,TotalAssets=50.,CashFlowsFromOperatingActivities=3.,ForecastEarningsPerShare=2.)
        row[d.slow.SHARES]=10.;rows.append(row)
    return pd.DataFrame(rows).set_index(['Date','Code']).sort_index()


def test_growth_uses_disclosed_comparable_prior_and_invalidates_basis_change():
    f=financials();g,used,pairs=d.growth_events(f)
    assert np.isclose(g.loc[(pd.Timestamp('2011-05-10'),'A'),'sales_growth'],.2)
    assert not used.loc[(pd.Timestamp('2011-06-01'),'A')], 'late comparator restatement must not overwrite current growth'
    assert g.loc[(pd.Timestamp('2012-05-10'),'A')].isna().all()
    assert pairs.matched_previous_fiscal_period.sum()==1
    prefix=f.loc[f.index.get_level_values('Date')<=pd.Timestamp('2011-05-10')]
    gg,_,_=d.growth_events(prefix)
    pd.testing.assert_frame_equal(g.loc[prefix.index],gg,check_exact=True)


def test_pit_before_disclosure_missing_and_on_disclosure_available():
    dates=pd.to_datetime(['2011-05-09','2011-05-10','2011-06-02','2012-05-10'])
    idx=pd.MultiIndex.from_product([dates,['A']],names=['Date','Code'])
    price=pd.DataFrame({'Close':10.},index=idx)
    raw,z,ages,_=d.build(idx,price,financials())
    assert np.isnan(raw.sales_growth.iloc[0])
    assert np.isclose(raw.sales_growth.iloc[1],.2)
    assert raw.sales_growth.iloc[1]==raw.sales_growth.iloc[2]
    assert np.isnan(raw.sales_growth.iloc[3])
    assert ages.growth_age_days.iloc[1]==0


def test_missing_and_ties_not_artificially_ranked():
    idx=pd.MultiIndex.from_product([[pd.Timestamp('2011-01-01')],list('ABCDE')],names=['Date','Code'])
    s=pd.Series([1.,1.,1.,4.,np.nan],index=idx)
    z=d.standardize(s);b=d.terciles(z)
    assert z.iloc[-1]!=z.iloc[-1] and b.iloc[-1]!=b.iloc[-1]
    assert b.iloc[:3].nunique()==1
    assert not np.isinf(z.dropna()).any()


def test_empty_ols_is_missing_not_zero():
    idx=pd.MultiIndex.from_product([[pd.Timestamp('2009-03-31')],['A','B']],names=['Date','Code'])
    z=pd.DataFrame(np.nan,index=idx,columns=d.DESCRIPTORS)
    score=pd.Series([1.,-1.],index=idx)
    residual,coefficients=d.neutralize(score,z)
    assert residual.isna().all() and coefficients.empty
    assert coefficients.index.name=='Date'


def test_future_fiscal_actual_is_not_an_annual_report():
    f=financials().iloc[:1].copy()
    f.index=pd.MultiIndex.from_tuples([(pd.Timestamp('2009-12-01'),'A')],names=['Date','Code'])
    assert not d.annual_reports(f).any()


def test_matching_balances_cells_and_retains_book_mass():
    idx=pd.MultiIndex.from_product([[pd.Timestamp('2011-01-01')],list('ABCDEFGHIJKL')],names=['Date','Code'])
    w=pd.Series([.1,-.05,.1,-.05,.1,-.05,.1,-.05,.1,-.05,0.,0.],index=idx)
    value=pd.Series([1,1,2,2,3,3,4,4,5,5,6,6],index=idx,dtype=float)
    growth=pd.Series(0.,index=idx)
    m,c=d.matching_weights(w,value,growth)
    np.testing.assert_allclose(m.groupby(c).sum(),0.,atol=1e-16)
    assert np.isclose(m.clip(lower=0).sum(),.25)
    assert np.isclose((-m).clip(lower=0).sum(),.25)
    all_missing=d.matching_weights(w,value*float('nan'),growth)[0]
    assert all_missing.eq(0).all()


def test_zero_outside_support_preserves_exit_costs():
    idx=pd.MultiIndex.from_product([pd.date_range('2011-01-01',periods=3),['A','B']],names=['Date','Code'])
    w=pd.Series([.5,-.5,0.,0.,.5,-.5],index=idx)
    q=pd.Series([4.,0.,np.nan,np.nan,4.,0.],index=idx)
    score=q.copy();target=pd.Series(.01,index=idx)
    daily,h=portfolio(w,q,score,target)
    assert daily.turnover.iloc[1]==1. and daily.cost.iloc[1]==.001
    assert np.isclose(daily.long_net.sum()+daily.short_net.sum(),daily.net.sum())
    assert h.loc[(pd.Timestamp('2011-01-02'),'A'),'long_cost']>0


def test_characteristic_and_double_sort_smoke_preserves_date_column(tmp_path):
    dates=pd.date_range('2011-01-01',periods=5)  # Deliberately unnamed calendar.
    idx=pd.MultiIndex.from_product([dates,[str(k) for k in range(60)]],names=['Date','Code'])
    score=pd.Series(np.tile(np.arange(60,dtype=float),5),index=idx)
    raw=pd.DataFrame({c:score.copy() for c in d.DESCRIPTORS},index=idx)
    z=pd.DataFrame({c:d.standardize(raw[c]) for c in raw},index=idx)
    target=score*.001
    w,q=evaluation.weights(score);_,h=portfolio(w,q,score,target)
    daily,profile=characteristics(raw,z,h,dates,tmp_path)
    assert 'Date' in daily and len(daily)==5*8*2
    assert profile.loc[profile.scope.eq('POOLED'),'spread'].gt(0).all()
    result=double_sort(score,z,target,dates,tmp_path)
    assert result.loc[result.scope.eq('POOLED'),'mean_spread'].gt(0).all()
