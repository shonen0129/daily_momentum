import ast
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from tests.legacy_dm_trainonly import load_modules
from research.evaluation import daily_account, weights
from stock_comp_2026.evaluate_script import compute_weight, compute_pl


with load_modules() as _dm:
    build_features = _dm.features.build_features
    build_momentum = _dm.features.build_momentum
    smooth = _dm.features.smooth
    segment_keys = _dm.features.segment_keys
    INPUT_COLUMNS = _dm.features.INPUT_COLUMNS
    centered_rank = _dm.features.centered_rank
    calibrated_oof = _dm.models.calibrated_oof
    training_mask = _dm.models.training_mask


def fixture_inputs(n=560, codes=6):
    rng=np.random.default_rng(123)
    dates=pd.bdate_range('2008-01-01',periods=n)
    idx=pd.MultiIndex.from_product([dates,[str(i) for i in range(codes)]],names=['Date','Code'])
    out={}
    for name,cols in INPUT_COLUMNS.items():
        if name=='topix_return_1day':
            out[name]=pd.DataFrame({'Return':rng.normal(0,.01,n)},index=dates.rename('Date'))
        elif name=='listed_info':
            out[name]=pd.DataFrame({'Sector17Code':np.tile(np.arange(codes)%2,n).astype(str),
                                   'ScaleCategory':'TOPIX Mid400'},index=idx)
        elif name=='prices_daily_quotes':
            out[name]=pd.DataFrame({c:rng.uniform(90,110,len(idx)) for c in cols},index=idx)
            for c in ['Volume','TurnoverValue','MorningVolume','AfternoonVolume']:
                out[name][c]*=10000
        else:
            out[name]=pd.DataFrame({'Return':rng.normal(0,.01,len(idx)) if 'raw_' in name else 1.},index=idx)
    return out


@pytest.mark.parametrize('cut', [110,310,510])
def test_all_features_future_mutation_bitwise(cut):
    data=fixture_inputs()
    before=build_features(data)
    cutoff=data['topix_return_1day'].index[cut]
    mutated={k:v.copy() for k,v in data.items()}
    for name,frame in mutated.items():
        mask=frame.index.get_level_values('Date')>cutoff
        for col in frame:
            frame.loc[mask,col]=('future_sector' if col=='Sector17Code' else 'TOPIX Core30') if name=='listed_info' else frame.loc[mask,col]*13+123
    after=build_features(mutated)
    pd.testing.assert_series_equal(before['res60s1'],build_momentum(data),check_exact=True)
    prefix=before.index.get_level_values('Date')<=cutoff
    pd.testing.assert_frame_equal(before.loc[prefix],after.loc[prefix],check_exact=True)
    pd.testing.assert_series_equal(smooth(build_momentum(data),.25).loc[prefix],
                                   smooth(build_momentum(mutated),.25).loc[prefix],check_exact=True)
    truncated={k:v.loc[v.index.get_level_values('Date')<=cutoff] for k,v in data.items()}
    pd.testing.assert_frame_equal(before.loc[prefix],build_features(truncated),check_exact=True)
    for col in ['res60s1','pwv','vwp','am','liquidity_shock']:
        pd.testing.assert_series_equal(smooth(before[col],.15).loc[prefix],smooth(after[col],.15).loc[prefix],check_exact=True)


def test_missing_inf_order_and_relisting():
    data=fixture_inputs(180)
    frame=data['prices_daily_quotes']
    frame.iloc[::7,:]=np.nan
    frame.iloc[::19,0]=0
    frame.iloc[::23,1]=np.inf
    baseline=build_features(data)
    shuffled={k:v.sample(frac=1,random_state=1) for k,v in data.items()}
    result=build_features(shuffled)
    pd.testing.assert_frame_equal(baseline,result,check_exact=True)
    assert np.isfinite(result.to_numpy()).all()
    idx=data['raw_return_1day'].index
    dates=idx.get_level_values('Date').unique()
    remove=(idx.get_level_values('Code')=='0') & (idx.get_level_values('Date').isin(dates[50:100]))
    short={k:(v.drop(index=idx[remove],errors='ignore') if isinstance(v.index,pd.MultiIndex) else v) for k,v in data.items()}
    f=build_features(short)
    # New listing has no 60-day momentum history; smoothing must reset too.
    assert f.loc[(dates[100],'0'),'momentum_available']==0
    s=pd.Series(1.,index=f.index)
    s.loc[(dates[100],'0')]=0
    assert smooth(s,.15).loc[(dates[100],'0')]==0


def test_scorer_matches_official_and_cost_identity():
    rng=np.random.default_rng(42)
    for n in [5,6,10,11,17,498]:
        idx=pd.MultiIndex.from_product([pd.bdate_range('2020-01-01',periods=5),list(map(str,range(n)))],names=['Date','Code'])
        s=pd.Series(rng.integers(0,5,len(idx)).astype(float),index=idx,name='Return').sort_index()
        target=pd.Series(rng.normal(0,.01,len(idx)),index=idx,name='Return').sort_index()
        target.iloc[1]=np.nan
        np.testing.assert_allclose(weights(s)[0],compute_weight(s.to_frame()).iloc[:,0],rtol=0,atol=1e-16)
        d=daily_account(s,target)
        np.testing.assert_allclose(d.net,compute_pl(s.to_frame(),target.to_frame()).groupby('Date').sum(),atol=1e-16)
        np.testing.assert_allclose(d.gross-d.cost,d.net,atol=1e-16)
        assert (d.cost_all>=d.cost-1e-16).all()


def test_calibration_future_target_mutation_and_purge():
    data=fixture_inputs()
    m=build_features(data)['res20s1']
    target=data['raw_return_1day']['Return'].copy()
    before,_,audit=calibrated_oof(m,target)
    cutoff=pd.Timestamp('2009-06-01')
    target.loc[target.index.get_level_values('Date')>cutoff]*=100
    after,_,_=calibrated_oof(m,target)
    pd.testing.assert_series_equal(before.loc[:cutoff],after.loc[:cutoff],check_exact=True)
    for row in audit:
        assert pd.Timestamp(row['max_label_available'])<pd.Timestamp(f"{row['year']}-01-01")


def test_source_firewall_ast():
    folder=Path(__file__).resolve().parents[1]/'stock_comp_2026/strategies/dm_trainonly'
    forbidden=['AdjustmentOpen','AdjustmentHigh','AdjustmentLow','AdjustmentClose','AdjustmentVolume','raw_target','target_1day_valid']
    for path in folder.glob('*.py'):
        source=path.read_text()
        for token in forbidden:
            assert token not in source,(path,token)
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Attribute):
                continue
            name=node.func.attr
            assert name not in ['bfill','backfill']
            if name=='shift':
                val=node.args[0] if node.args else next(k.value for k in node.keywords if k.arg=='periods')
                assert isinstance(val,ast.Constant) and isinstance(val.value,int) and val.value>=0
            for keyword in node.keywords:
                assert not (keyword.arg=='center' and not (isinstance(keyword.value,ast.Constant) and keyword.value.value is False))
                assert not (keyword.arg=='direction' and isinstance(keyword.value,ast.Constant) and keyword.value.value=='forward')


def test_runtime_firewall_denies_labels(tmp_path):
    # Isolate audit hook because Python audit hooks cannot be removed.
    import subprocess,sys
    script="from research.firewall import install; install(); import pandas as pd; pd.read_parquet('target_1day_valid.parquet')"
    result=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,timeout=30)
    assert result.returncode!=0 and 'Train-only parquet guard denied' in result.stderr


def test_runtime_firewall_guards_pyarrow_and_valid_symlinks(tmp_path):
    import subprocess
    import sys
    import pyarrow as pa
    import pyarrow.parquet as pq

    valid = tmp_path / "target_1day_valid.parquet"
    train = tmp_path / "target_1day_train.parquet"
    alias = tmp_path / "looks_like_train_train.parquet"
    artifact_dir = tmp_path / "CaseSensitiveArtifact"
    artifact_dir.mkdir()
    artifact = artifact_dir / "paired_scores.parquet"
    table = pa.table({"Return": [0.01, -0.02]})
    pq.write_table(table, valid)
    pq.write_table(table, train)
    pq.write_table(table, artifact)
    alias.symlink_to(valid)

    script = (
        "from research.firewall import install; install(); "
        "import pyarrow.parquet as pq; import sys; "
        "pq.read_table(sys.argv[1])"
    )
    denied_valid = subprocess.run(
        [sys.executable, "-c", script, str(valid)], capture_output=True, text=True, timeout=30
    )
    assert denied_valid.returncode != 0
    assert "Train-only parquet guard denied target_1day_valid.parquet" in denied_valid.stderr

    guarded_file_script = (
        "from research.firewall import install; install(); "
        "import pyarrow.parquet as pq; import sys; pq.ParquetFile(sys.argv[1])"
    )
    denied_alias = subprocess.run(
        [sys.executable, "-c", guarded_file_script, str(alias)],
        capture_output=True, text=True, timeout=30,
    )
    assert denied_alias.returncode != 0
    assert "Train-only parquet guard denied target_1day_valid.parquet" in denied_alias.stderr

    dataset_script = (
        "from research.firewall import install; install(); "
        "import pyarrow.dataset as ds; import sys; ds.dataset(sys.argv[1]).to_table()"
    )
    denied_dataset = subprocess.run(
        [sys.executable, "-c", dataset_script, str(valid)],
        capture_output=True, text=True, timeout=30,
    )
    assert denied_dataset.returncode != 0
    assert "Train-only parquet guard denied target_1day_valid.parquet" in denied_dataset.stderr

    allowed = subprocess.run(
        [sys.executable, "-c", script, str(train)], capture_output=True, text=True, timeout=30
    )
    assert allowed.returncode == 0, allowed.stderr

    allowed_dataset = subprocess.run(
        [sys.executable, "-c", dataset_script, str(train)],
        capture_output=True, text=True, timeout=30,
    )
    assert allowed_dataset.returncode == 0, allowed_dataset.stderr

    pandas_script = (
        "from research.firewall import install; install(); "
        "import pandas as pd; import sys; pd.read_parquet(sys.argv[1])"
    )
    allowed_pandas = subprocess.run(
        [sys.executable, "-c", pandas_script, str(train)],
        capture_output=True, text=True, timeout=30,
    )
    assert allowed_pandas.returncode == 0, allowed_pandas.stderr

    artifact_script = (
        "from research.firewall import install; import sys; install([sys.argv[1]]); "
        "import pyarrow.parquet as pq; pq.read_table(sys.argv[1])"
    )
    allowed_artifact = subprocess.run(
        [sys.executable, "-c", artifact_script, str(artifact)],
        capture_output=True, text=True, timeout=30,
    )
    assert allowed_artifact.returncode == 0, allowed_artifact.stderr

    file_like_script = (
        "from research.firewall import install; install(); "
        "import pyarrow as pa; import pyarrow.parquet as pq; import sys; "
        "source = pa.BufferReader(open(sys.argv[1], 'rb').read()); pq.read_table(source)"
    )
    denied_file_like = subprocess.run(
        [sys.executable, "-c", file_like_script, str(train)],
        capture_output=True, text=True, timeout=30,
    )
    assert denied_file_like.returncode != 0
    assert "rejects unverified file-like sources" in denied_file_like.stderr
