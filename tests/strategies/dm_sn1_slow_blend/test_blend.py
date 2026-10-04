"""Fixed scale, tie, contract, causal rank and accounting regressions."""
from pathlib import Path
import subprocess
import sys
import numpy as np
import pandas as pd
import pytest
from research.experiments.sn1_slow_diversification import exact, holdings_from_weight, account, attribution, source_scan, mutate, source_dates
from stock_comp_2026.strategies.dm_sn1_slow_blend import features as f
from stock_comp_2026 import evaluate_script as official


def panels():
    index=pd.MultiIndex.from_product([pd.bdate_range('2012-01-03',periods=5),[str(i) for i in range(10)]],names=['Date','Code'])
    return pd.Series(np.tile(np.arange(10,dtype=float),5),index=index,name='sn'),pd.Series(np.tile(np.arange(10,dtype=float)[::-1],5),index=index,name='slow')


def test_opposite_order_cancels_and_official_code_ties():
    a,b=panels();s=f.blend(a,b)
    assert s.abs().max()<1e-15
    # Complete cancellation uses deterministic official Code-order tie break.
    s[:]=0
    w=official.compute_weight(s.rename('Return').to_frame()).Return
    assert w.loc[(pd.Timestamp('2012-01-03'),'0')]<0
    assert w.loc[(pd.Timestamp('2012-01-03'),'9')]>0


def test_hand_tie_average_and_no_extra_smoothing():
    a,b=panels();a[:]=np.tile([0,1,1,3,4,5,6,7,8,9],5);b[:]=2.
    got=f.blend(a,b)
    np.testing.assert_allclose(got.iloc[:10],[-.9,-.6,-.6,-.3,-.1,.1,.3,.5,.7,.9],atol=1e-15,rtol=0)
    # Changes only today's score; no extra state survives to the next date.
    changed=a.copy();changed.iloc[:10]=changed.iloc[:10].to_numpy()[::-1]
    exact(got.iloc[10:],f.blend(changed,b).iloc[10:])


def test_future_scores_and_truncation_do_not_change_past_ranks():
    a,b=panels();got=f.blend(a,b);cutoff=pd.Timestamp('2012-01-05');keep=a.index.get_level_values('Date')<=cutoff
    aa=a.copy();bb=b.copy();aa.loc[~keep]=1e30;bb.loc[~keep]=-1e30
    exact(got.loc[keep],f.blend(aa,bb).loc[keep]);exact(got.loc[keep],f.blend(a.loc[keep],b.loc[keep]))


@pytest.mark.parametrize('invalid',['missing','misaligned','duplicate'])
def test_no_silent_missing_or_index_fallback(invalid):
    a,b=panels()
    if invalid=='missing':b.iloc[0]=np.nan
    elif invalid=='misaligned':b=b.iloc[::-1]
    else:a=pd.concat([a,a.iloc[:1]]);b=pd.concat([b,b.iloc[:1]])
    with pytest.raises(ValueError):f.blend(a,b)


def test_accounting_netting_and_attribution_retains_neutral_exit_costs(tmp_path):
    a,b=panels();target=pd.Series(.01,index=a.index,name='Return');target.iloc[0]=np.nan
    h={};d={}
    for name,s in [('SN1_H1',a),('SLOW_CONTROL',b),('SN1_SLOW_BLEND',f.blend(a,b))]:
        d[name],h[name],receipt=account(s,target);assert receipt['official_net_bits']
    average=.5*h['SN1_H1'].w+.5*h['SLOW_CONTROL'].w
    virtual=holdings_from_weight(average,target)
    assert (virtual.cost_all<=.5*h['SN1_H1'].cost_all+.5*h['SLOW_CONTROL'].cost_all+1e-15).all()
    receipt=attribution(h,target,a.index.get_level_values('Date').unique(),tmp_path)
    assert receipt['status']=='PASS'
    summary=pd.read_csv(tmp_path/'diversification_attribution.csv')
    assert 'SIGNAL_DISAGREEMENT' in summary.group.to_list()
    assert 'MARGINAL_OVERLAPPING' in summary.view.to_list()


def test_self_contained_source_parity_and_top_level_import():
    root=Path(__file__).resolve().parents[3];folder=root/'stock_comp_2026/strategies/dm_sn1_slow_blend'
    for part,original,names in [('component_sn1','dm_variable_box_breakout',['features','bidirectional','sn1']),('component_slow','dm_slow_multifactor',['features'])]:
        for name in names:assert (folder/part/(name+'.py')).read_bytes()==(root/'stock_comp_2026/strategies'/original/(name+'.py')).read_bytes()
    result=subprocess.run([sys.executable,'-c','import submission; assert callable(submission.predict)'],cwd=folder,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert source_scan(sorted(folder.rglob('*.py')))['status']=='PASS'


def test_financial_JST_cutoff_preserves_prefix_and_suffix_publication():
    dates=pd.date_range('2012-01-03',periods=20,tz='Asia/Tokyo')
    index=pd.MultiIndex.from_product([dates,['10000']],names=['Date','Code'])
    frame=pd.DataFrame({'TotalAssets':np.arange(20,dtype=float)},index=index)
    cutoff=pd.Timestamp('2012-01-10')
    got=mutate(frame,'fins_statements',cutoff,20261003)
    prefix=source_dates(frame)<=cutoff
    pd.testing.assert_frame_equal(frame.loc[prefix],got.loc[frame.index[prefix]],check_exact=True)
    assert (source_dates(got.loc[~got.index.isin(frame.index[prefix])])>cutoff).all()
