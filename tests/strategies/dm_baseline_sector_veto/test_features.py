import numpy as np
import pandas as pd
import pytest
from stock_comp_2026.strategies.dm_baseline_sector_veto import features as sv, submission
from stock_comp_2026.strategies.dm_trainonly import features as old
from tests.strategies.dm_sector_momentum.test_features import fixture_inputs, assert_exact


@pytest.mark.parametrize("cut", [59, 95, 150])
@pytest.mark.parametrize("source", list(sv.INPUT_COLUMNS)+["ALL", "TRUNCATION"])
def test_all_inputs_future_changes_and_truncation(cut, source):
    from research.experiments.sector_momentum import mutate
    data = fixture_inputs()
    dates = data["raw_return_1day"].index.get_level_values("Date").unique()
    # Sector update exists before the final cutoff; chronology must remain exact.
    data["listed_info"].loc[(slice(dates[110], None), "00000"), "Sector33Code"] = "other"
    base = sv.build_features(data); cutoff = dates[cut]
    changed = dict(data)
    for name, frame in data.items():
        if source == "TRUNCATION":
            changed[name] = frame.loc[frame.index.get_level_values("Date") <= cutoff]
        elif source in [name, "ALL"]:
            changed[name] = mutate(frame, name, cutoff, 73)
    idx = base.index[base.index.get_level_values("Date") <= cutoff]
    assert_exact(base.loc[idx], sv.build_features(changed).loc[idx])


def test_inclusive_finite_minimum_and_pit_projection():
    data = fixture_inputs(days=1, stocks=10)
    idx = data["raw_return_1day"].index
    values = pd.Series(np.arange(10, dtype=float), index=idx)
    sector = pd.Series("test", index=idx, dtype="string")
    common, count = sv.sector_context(values, sector, 10)
    assert common.eq(4.5).all() and count.eq(10).all()
    changed = values.copy(); changed.iloc[0] = 100
    assert sv.sector_context(changed, sector, 10)[0].iloc[0] == 14.5  # own stock INCLUDED
    changed.iloc[0] = np.inf
    assert sv.sector_context(changed, sector, 10)[0].isna().all()
    sector.iloc[0] = pd.NA
    assert sv.sector_context(values, sector, 10)[0].isna().all()
    assert sv.sector_context(values, sector, 9)[1].iloc[1] == 9


def test_hierarchical_priority_unknown_and_missing_preserves_baseline():
    data = fixture_inputs()
    listed = data["listed_info"]
    codes = listed.index.get_level_values("Code")
    # 3-stock33 groups fail min5; their17 parent has24 finite members.
    listed["Sector33Code"] = [str(int(c)//3) for c in codes]
    f = sv.build_features(data)
    late = f.loc[f.index.get_level_values("Date") > f.index.get_level_values("Date").unique()[60]]
    assert late.ContextSource.eq("SECTOR17_FALLBACK").all()
    np.testing.assert_array_equal(late.HIER_SECTOR_MOM, late.SECTOR17_MOM)
    # A unavailable never neutralizes or otherwise changes the baseline.
    assert_exact(f.BASELINE.rename("Return").to_frame(), sv.score(f, sv.CANDIDATES[0]).to_frame())
    listed["Sector33Code"] = "0050"
    primary = sv.build_features(data)
    late = primary.loc[late.index]
    assert late.ContextSource.eq("SECTOR33").all()
    np.testing.assert_array_equal(late.HIER_SECTOR_MOM, late.SECTOR33_MOM)
    listed[["Sector33Code", "Sector17Code"]] = ["9999", "99"]
    missing = sv.build_features(data)
    assert missing.ContextSource.eq("UNAVAILABLE").all()
    for candidate in sv.CANDIDATES:
        assert_exact(missing.BASELINE.rename("Return").to_frame(), sv.score(missing, candidate).to_frame())


def test_final_score_veto_strict_sign_and_no_second_smoothing():
    idx = pd.MultiIndex.from_product([pd.bdate_range("2011-01-03", periods=5), ["A"]], names=["Date", "Code"])
    baseline = pd.Series([-1., -1., -1., 0., 1.], index=idx)
    context = pd.Series([1e-30, 0., np.nan, 1., 1.], index=idx)
    out = sv.apply_veto(baseline, context)
    np.testing.assert_array_equal(out, [0., -1., -1., 0., 1.])
    # A one-day veto ends immediately; the baseline EWMA remains independent.
    assert out.iloc[1] == baseline.iloc[1]
    data = fixture_inputs()
    f = sv.build_features(data)
    assert_exact(f.BASELINE.rename("res60s1").to_frame(), old.smooth(old.build_momentum(data), .25).to_frame())
    for candidate in sv.CANDIDATES:
        got = sv.score(f, candidate)
        keep = got.ne(0)
        assert np.array_equal(got.loc[keep].to_numpy().view(np.uint64), f.BASELINE.loc[keep].to_numpy().view(np.uint64))


def test_shuffle_relisting_nonfinite_exact_index_adapter(monkeypatch):
    data = fixture_inputs(days=230)
    dates = data["raw_return_1day"].index.get_level_values("Date").unique()
    for name in ["raw_return_1day", "beta_1day", "listed_info"]:
        frame = data[name]
        absent = frame.index.get_level_values("Code").eq("00000") if hasattr(frame.index.get_level_values("Code"), "eq") else frame.index.get_level_values("Code")=="00000"
        absent &= frame.index.get_level_values("Date").isin(dates[80:110])
        data[name] = frame.loc[~absent]
    data["raw_return_1day"].iloc[90, 0] = np.inf
    f = sv.build_features(data)
    assert f.loc[(slice(dates[110], dates[169]), "00000"), "StockMom60_raw"].isna().all()
    assert_exact(f, sv.build_features(data))
    assert_exact(f, sv.build_features({n:x.sample(frac=1, random_state=7) for n,x in data.items()}))
    monkeypatch.setattr(submission, "load_train", lambda unused: data)
    for candidate in sv.CANDIDATES:
        assert np.isfinite(sv.score(f, candidate)).all()
        assert_exact(sv.score(f, candidate).to_frame(), submission.predict("unused", candidate))
    assert f.index.equals(data["raw_return_1day"].index)
    with pytest.raises(ValueError):
        sv.score(f, "RESCUE")
    extra = data["listed_info"].iloc[:1].copy()
    extra.index = pd.MultiIndex.from_tuples([(dates[0], "LISTED_ONLY")], names=["Date", "Code"])
    changed = dict(data); changed["listed_info"] = pd.concat([data["listed_info"], extra])
    assert_exact(f, sv.build_features(changed))
    changed["listed_info"] = pd.concat([data["listed_info"], data["listed_info"].iloc[:1]])
    with pytest.raises(ValueError, match="unique"):
        sv.build_features(changed)


def test_accounting_diagnostics_reconcile_exit_costs(tmp_path):
    from research.experiments import baseline_sector_veto as driver
    from research.experiments.sector_momentum import account
    from research.experiments.sector_confirmation import enrich_holdings
    from research import evaluation
    assert driver.source_scan()["status"] == "PASS"
    data = fixture_inputs(days=540)
    f = sv.build_features(data)
    target = data["raw_return_1day"].Return.copy(); target.iloc[80] = np.nan
    accounts, holdings = {}, {}
    for name in ["BASELINE"]+list(sv.CANDIDATES):
        accounts[name], h, audit = account(f[name].rename("Return"), target)
        holdings[name] = enrich_holdings(h)
        assert audit["net_bitwise"] and audit["weight_bitwise"]
    dates, purge = driver.fold_dates(accounts["BASELINE"].index, [2011])
    assert purge[0]["status"]=="PASS"
    assert driver.replacement(f, target, holdings, accounts, dates, tmp_path)["status"]=="PASS"
    assert driver.fallback_attribution(f, target, holdings, dates, tmp_path)["status"]=="PASS"
    driver.long_impact(holdings, dates, tmp_path)
    cover = driver.coverage(f, dates, tmp_path)
    assert np.allclose(cover[[s.lower()+"_rate" for s in driver.SOURCES]].sum(axis=1), 1)
    assert evaluation.bootstrap_delta(accounts["BASELINE"].net, accounts["BASELINE"].net, seed=20261002, reps=50, block=20)["low"]==0


def test_firewall_allows_own_diagnostic_reads_and_report_copy(tmp_path):
    import subprocess
    import sys
    # The runtime audit hook also guards shutil/file hashing, not just pandas.
    script = """
import sys, shutil, hashlib
from pathlib import Path
import pandas as pd
from research import firewall
from research.experiments.baseline_sector_veto import saved_output_paths
output=Path(sys.argv[1])
paths=saved_output_paths(output)
for path in paths:
    path.parent.mkdir(parents=True,exist_ok=True)
    pd.DataFrame({'value':[1.]}).to_parquet(path)
firewall.install(allowed_artifacts=paths)
for path in paths:
    assert pd.read_parquet(path).value.iloc[0]==1.
    hashlib.sha256(path.read_bytes()).hexdigest()
    shutil.copyfile(path,path.with_suffix('.copied'))
try:
    pd.read_parquet(output/'target_1day_valid.parquet')
except PermissionError:
    pass
else:
    raise AssertionError('Valid guard bypassed')
"""
    done = subprocess.run([sys.executable, "-c", script, str(tmp_path)], capture_output=True, text=True, timeout=30)
    assert done.returncode==0, done.stderr
