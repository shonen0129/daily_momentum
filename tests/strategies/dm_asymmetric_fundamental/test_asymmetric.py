import ast
from pathlib import Path
import importlib.util
import subprocess
import sys
import numpy as np
import pandas as pd
import pytest
from tests.test_causality import fixture_inputs
from stock_comp_2026.strategies.dm_asymmetric_fundamental import core, features as f, submission
from research.experiments import asymmetric_evaluation as ev
from evaluate_script import compute_weight, compute_pl


def report(date, code='0', end='2008-12-31', start='2008-01-01', cfo=10., assets=100., **kw):
    row = dict(Date=pd.Timestamp(date, tz='Asia/Tokyo'), Code=code, DisclosureNumber=1,
               TypeOfDocument='FYFinancialStatements_Consolidated_JP', TypeOfCurrentPeriod='FY',
               CurrentPeriodStartDate=start, CurrentPeriodEndDate=end,
               CurrentFiscalYearStartDate=start, CurrentFiscalYearEndDate=end,
               CashFlowsFromOperatingActivities=cfo, TotalAssets=assets, CashAndEquivalents=20., Equity=50.)
    row.update(kw)
    return row


def fins(rows):
    return pd.DataFrame(rows).set_index(['Date','Code']).sort_index()


def inputs(n=820, codes=6):
    d = fixture_inputs(n, codes)
    rows = []
    for c in range(codes):
        for year in [2008,2009,2010]:
            rows.append(report(f'{year+1}-02-02', str(c), f'{year}-12-31', f'{year}-01-01',
                               cfo=(10+c if year == 2008 else -10+c)))
    d['fins_statements'] = fins(rows)
    return d


def panel_index(start='2009-01-01', end='2012-01-01'):
    return pd.MultiIndex.from_product([pd.bdate_range(start,end), ['0']],names=['Date','Code'])


def test_availability_yoy_atomic_missing_freshness():
    idx = panel_index()
    rows = [report('2009-02-06'), report('2010-02-05', end='2009-12-31', start='2009-01-01', cfo=-10),
            report('2010-02-08', end='2010-03-31', start='2010-01-01', cfo=np.nan, assets=1000,
                   TypeOfDocument='1QFinancialStatements_Consolidated_JP', TypeOfCurrentPeriod='1Q'),
            report('2010-03-01', end='2009-12-31', start='2009-01-01', cfo=np.nan, assets=np.nan)]
    p = f.financial_panel(idx, fins(rows))
    assert pd.isna(p.loc[('2009-02-06','0'),'cfo_assets'])
    assert p.loc[('2009-02-09','0'),'cfo_assets'] == .1
    assert p.loc[('2010-02-05','0'),'cfo_assets'] == .1
    assert p.loc[('2010-02-08','0'),'cfo_assets'] == -.1
    assert p.loc[('2010-02-09','0'),'cfo_assets'] == -.1
    assert p.loc[('2010-02-08','0'),'cfo_yoy'] == -.2
    assert p.loc[('2010-02-08','0'),'event_age'] == 0
    assert p.loc[('2010-02-08','0'),'event'] == 1
    assert pd.isna(p.loc[('2011-05-02','0'),'cfo_assets'])


def test_holiday_and_revision_versions_do_not_renew_event():
    idx = panel_index()
    rows = [report('2009-02-07'), report('2010-02-05',end='2009-12-31',start='2009-01-01',cfo=-10),
            report('2010-02-10',end='2008-12-31',start='2008-01-01',cfo=30),
            report('2010-02-15',end='2009-12-31',start='2009-01-01',cfo=-20)]
    p = f.financial_panel(idx, fins(rows))
    assert p.loc[('2009-02-09','0'),'cfo_assets'] == .1
    assert p.loc[('2010-02-10','0'),'cfo_yoy'] == -.2
    assert p.loc[('2010-02-11','0'),'cfo_assets'] == -.1
    assert p.loc[('2010-02-11','0'),'cfo_yoy'] == -.4
    assert p.loc[('2010-02-16','0'),'event_date'] == pd.Timestamp('2010-02-05')
    assert p.loc[('2010-02-16','0'),'event_age'] == 6


@pytest.mark.parametrize('kind', ['period','basis','duration','negative_assets'])
def test_noncomparable_reports(kind):
    rows = [report('2009-02-01'),report('2010-02-01',end='2009-12-31',start='2009-01-01',cfo=-10)]
    if kind == 'period':
        rows[1].update(TypeOfCurrentPeriod='2Q',TypeOfDocument='2QFinancialStatements_Consolidated_JP',CurrentPeriodEndDate='2009-06-30')
    elif kind == 'basis':
        rows[1]['TypeOfDocument'] = 'FYFinancialStatements_Consolidated_IFRS'
    elif kind == 'duration':
        rows[1]['CurrentPeriodStartDate'] = '2009-10-01'
    else:
        rows[1]['TotalAssets'] = -1
    p = f.financial_panel(panel_index(),fins(rows))
    assert pd.isna(p.loc[('2010-02-02','0'),'cfo_yoy'])
    assert p.loc[('2010-02-02','0'),'event'] == 0


def test_event_decay_and_clear():
    np.testing.assert_array_equal(f.event_decay(np.array([-1,0,20,21,40,41,60,61,np.nan])),[0,1,1,.5,.5,.25,.25,0,0])
    rows=[report('2009-02-01'),report('2010-02-01',end='2009-12-31',start='2009-01-01',cfo=-10),
          report('2010-02-10',end='2009-12-31',start='2009-01-01',cfo=10)]
    p=f.financial_panel(panel_index(),fins(rows))
    assert p.loc[('2010-02-10','0'),'event'] == 1
    assert p.loc[('2010-02-11','0'),'event'] == 0


def mutate(data, cutoff):
    out={k:v.copy() for k,v in data.items()}
    for name, frame in out.items():
        dt=frame.index.get_level_values('Date')
        if dt.tz is not None: dt=dt.tz_localize(None)
        future=dt>cutoff
        for col in frame:
            if isinstance(frame[col].dtype, pd.CategoricalDtype): frame[col]=frame[col].astype(str)
            if pd.api.types.is_numeric_dtype(frame[col]):
                frame.loc[future,col]=frame.loc[future,col]*-13+999
            elif pd.api.types.is_datetime64_any_dtype(frame[col]):
                frame.loc[future,col]=pd.Timestamp('1990-01-01')
            else:
                frame.loc[future,col]='future_changed'
    return out


@pytest.mark.parametrize('cutoff',['2009-06-01','2010-06-01'])
def test_all_inputs_future_mutation_truncation_prediction(cutoff):
    d=inputs(); before=f.build_features(d); cutoff=pd.Timestamp(cutoff)
    changed=mutate(d,cutoff); after=f.build_features(changed)
    truncated={}
    for k,v in d.items():
        dt=v.index.get_level_values('Date')
        if dt.tz is not None: dt=dt.tz_localize(None)
        truncated[k]=v.loc[dt<=cutoff]
    short=f.build_features(truncated)
    prefix=before.index.get_level_values('Date')<=cutoff
    pd.testing.assert_frame_equal(before.loc[prefix],after.loc[prefix],check_exact=True)
    pd.testing.assert_frame_equal(before.loc[prefix],short,check_exact=True)
    for family in ['A','B','C','Event']:
        for sm in ['long','final']:
            spec=dict(family=family,weights='heavy',lambda_=.5,gamma=.5,delta=.5,smoothing=sm)
            pd.testing.assert_series_equal(f.predict_from_features(before,spec).loc[prefix],f.predict_from_features(after,spec).loc[prefix],check_exact=True)


def test_baseline_order_missing_relisting():
    from features import build_momentum, smooth
    d=inputs(820)
    before=f.build_features(d)
    pd.testing.assert_series_equal(before.L.rename('res60s1'),smooth(build_momentum(d),.25),check_exact=True)
    pd.testing.assert_frame_equal(before, f.build_features({k:v.sample(frac=1,random_state=3) for k,v in d.items()}),check_exact=True)
    idx=d['raw_return_1day'].index; dates=idx.get_level_values('Date').unique()
    remove=(idx.get_level_values('Code')=='0') & idx.get_level_values('Date').isin(dates[570:650])
    for k in list(d):
        if k!='fins_statements' and isinstance(d[k].index,pd.MultiIndex): d[k]=d[k].drop(idx[remove],errors='ignore')
    d['prices_daily_quotes'].iloc[::23,:]=0
    d['raw_return_1day'].iloc[::33,0]=np.inf
    ff=f.build_features(d)
    assert ff.loc[(dates[650],'0'),'L']==0
    assert not ff.loc[(dates[650],'0'),'financial_available']
    assert np.isfinite(f.predict_from_features(ff,dict(family='A',lambda_=.5,weights='heavy'))).all()


def test_official_costs_fixed_long_and_purge():
    rng=np.random.default_rng(12)
    idx=pd.MultiIndex.from_product([pd.bdate_range('2013-12-20',periods=20),list('abcdefghij')],names=['Date','Code'])
    s=pd.Series(rng.normal(size=len(idx)),index=idx,name='Return')
    y=pd.Series(rng.normal(0,.01,len(idx)),index=idx,name='Return'); y.iloc[11]=np.nan
    short=pd.Series(rng.uniform(size=len(idx)),index=idx)
    d=ev.account(s,y,short,pd.Series(True,index=idx),s)
    np.testing.assert_allclose(d.net,compute_pl(s.to_frame(),y.to_frame()).groupby('Date').sum(),atol=1e-16)
    np.testing.assert_allclose(d.long_net+d.short_net,d.net,atol=1e-16)
    bw=compute_weight(s.to_frame()).iloc[:,0]
    fw=ev.fixed_long_weights(s,short)
    np.testing.assert_array_equal(fw[bw>0],bw[bw>0])
    assert (fw.groupby('Date').apply(lambda v:int((v<0).sum()))==4).all()
    cal=idx.get_level_values('Date').unique()
    safe=ev.safe_dates(cal,[2013,2014])
    for date in safe:
        assert cal[cal.get_loc(date)+2].year==date.year


def test_submission_contract_and_default_import(tmp_path,monkeypatch):
    d=inputs(820)
    for k,v in d.items(): v.to_parquet(tmp_path/f'{k}_train.parquet')
    expected=f.predict_from_features(f.build_features(d),dict(family='A',weights='heavy',lambda_=.5,smoothing='long')).to_frame()
    actual=submission.predict(tmp_path,split='train')
    pd.testing.assert_frame_equal(actual,expected,check_exact=True)
    pd.testing.assert_frame_equal(actual,submission.predict(tmp_path,split='train'),check_exact=True)
    script=Path(submission.__file__).resolve()
    code=f"import importlib.util; s=importlib.util.spec_from_file_location('submission', {str(script)!r}); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); p=m.predict(); assert p.shape[1]==1; assert p.index.names==['Date','Code']"
    run=subprocess.run([sys.executable,'-c',code],cwd=tmp_path,capture_output=True,text=True,timeout=60)
    assert run.returncode==0,run.stderr


def test_source_scan_all_new_strategy_files():
    folder=Path(f.__file__).parent
    for path in folder.glob('*.py'):
        source=path.read_text()
        for token in ['AdjustmentOpen','AdjustmentHigh','AdjustmentLow','AdjustmentClose','AdjustmentVolume','raw_target','target_1day_valid']:
            assert token not in source,(path,token)
        for node in ast.walk(ast.parse(source)):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                assert node.func.attr not in ['bfill','backfill']
                if node.func.attr=='shift':
                    arg=node.args[0] if node.args else next(k.value for k in node.keywords if k.arg=='periods')
                    assert isinstance(arg,ast.Constant) and isinstance(arg.value,int) and arg.value>=0
                for kw in node.keywords:
                    assert not (kw.arg=='center' and not (isinstance(kw.value,ast.Constant) and kw.value.value is False))
                    assert not (kw.arg=='direction' and isinstance(kw.value,ast.Constant) and kw.value.value=='forward')
