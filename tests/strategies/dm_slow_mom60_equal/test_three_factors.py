"""Three independent ranks, immutable component order, causal and accounting contracts."""
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from stock_comp_2026.strategies.dm_slow_mom60_equal import features as f, submission
from stock_comp_2026.strategies.dm_slow_multifactor import features as old_slow
from stock_comp_2026.strategies.dm_trainonly import features as old_mom
from research.experiments.slow_mom60_equal import (exact, source_scan, function_sources, mutate,
    source_dates, holdings, agreement_groups, attribution, stored_raw_parity, SLOW, MOM, CAND)


def inputs_fixture():
    dates = pd.bdate_range("2012-01-02", periods=95)
    codes = [str(10000 + i) for i in range(15)]
    index = pd.MultiIndex.from_product([dates, codes], names=["Date", "Code"])
    v = np.tile(np.arange(1, 16, dtype=float), len(dates))
    prices = pd.DataFrame({"Close": 90 + v, "TurnoverValue": v * 1e6}, index=index)
    raw = pd.DataFrame({"Return": np.sin(np.arange(len(index))) * .015}, index=index)
    listed = pd.DataFrame({"Sector17Code": "A"}, index=index)
    fi = pd.MultiIndex.from_product([dates[[4, 50, 80]], codes], names=["Date", "Code"])
    q = np.tile(np.arange(1, 16, dtype=float), 3)
    fins = pd.DataFrame({"Equity": q * 30, "TotalAssets": q * 100,
                         "Profit": q, "CashFlowsFromOperatingActivities": q * 2,
                         "ForecastEarningsPerShare": q, old_slow.SHARES: q * 1000}, index=fi)
    return {"prices_daily_quotes": prices, "raw_return_1day": raw, "listed_info": listed,
            "fins_statements": fins, "beta_1day": pd.DataFrame({"Return": v / 10}, index=index),
            "topix_return_1day": pd.DataFrame({"Return": np.cos(np.arange(len(dates))) * .002}, index=dates.rename("Date"))}


def test_original_factor_and_rank_before_ewma_parity():
    inputs = inputs_fixture()
    scores, mid = f.components(inputs)
    original = old_slow.build_features({k: inputs[k] for k in old_slow.INPUT_COLUMNS})
    exact(scores.Size, original.z_size.rename("Size"))
    exact(scores.Illiquidity, original.z_amihud.rename("Illiquidity"))
    exact(scores[SLOW], original.size_liquidity.rename(SLOW))
    before = old_mom.build_momentum(inputs)
    exact(mid.MOM60_before_ewma, before.rename("MOM60_before_ewma"))
    exact(scores[MOM], old_mom.smooth(before, .25).rename(MOM))
    exact(scores[SLOW], old_slow.zscore(scores[["Size", "Illiquidity"]].mean(axis=1)).rename(SLOW))
    assert scores.index.equals(inputs["raw_return_1day"].index)
    assert np.isfinite(scores.to_numpy()).all()


def test_hand_computed_average_ties_and_independent_equal_weights():
    index = pd.MultiIndex.from_product([[pd.Timestamp("2012-01-02")], list("abcd")], names=["Date", "Code"])
    scores = pd.DataFrame({"Size": [0., 1., 1., 3.], "Illiquidity": [4., 3., 2., 1.],
                           "MOM60": [0., 0., 0., 0.]}, index=index)
    got = f.factor_ranks(scores)
    # Average percentile ranks .25,.625,.625,1 center around .625.
    np.testing.assert_array_equal(got.SizeRank, [-.75, 0., 0., .75])
    np.testing.assert_array_equal(got.IlliquidityRank, [.75, .25, -.25, -.75])
    np.testing.assert_array_equal(got.MOM60Rank, [0., 0., 0., 0.])
    np.testing.assert_array_equal(f.score(scores), [0., 1/12, -1/12, 0.])
    # Each factor's numeric units have no effect on its independent rank.
    transformed = scores.copy()
    transformed.Size *= 100
    transformed.Illiquidity *= .001
    exact(f.score(scores), f.score(transformed))


def test_three_factor_score_is_different_from_two_score_blend():
    inputs = inputs_fixture()
    scores, _ = f.components(inputs)
    two = (old_mom.centered_rank(scores[SLOW]) + old_mom.centered_rank(scores[MOM])) / 2
    assert not np.array_equal(f.score(scores).to_numpy().view(np.uint64), two.to_numpy().view(np.uint64))
    # The combination has no additional temporal smoothing.
    cut = scores.index.get_level_values("Date").unique()[70]
    changed = scores.copy()
    mask = changed.index.get_level_values("Date") == cut
    changed.loc[mask, "Size"] *= -1
    other = ~mask
    exact(f.score(scores).loc[other], f.score(changed).loc[other])


@pytest.mark.parametrize("source", list(f.INPUT_COLUMNS) + ["ALL", "TRUNCATION"])
def test_each_input_future_mutation_and_truncation(source):
    inputs = inputs_fixture()
    scores, mid = f.components(inputs)
    cutoff = pd.Timestamp("2012-03-01")
    prefix = scores.index[scores.index.get_level_values("Date") <= cutoff]
    changed = dict(inputs)
    for i, (name, frame) in enumerate(inputs.items()):
        if source == "TRUNCATION":
            changed[name] = frame.loc[source_dates(frame) <= cutoff]
        elif source in [name, "ALL"]:
            changed[name] = mutate(frame, name, cutoff, 20261003 + i)
    got, mm = f.components(changed)
    exact(scores.loc[prefix], got.loc[prefix])
    exact(mid.loc[prefix], mm.loc[prefix])
    exact(f.score(scores).loc[prefix], f.score(got).loc[prefix])


def test_row_shuffle_missing_inf_relisting_and_zero_denominators():
    inputs = inputs_fixture()
    dates = inputs["raw_return_1day"].index.get_level_values("Date").unique()
    # A gap longer than20 retains frozen MOM state reset semantics.
    index = inputs["raw_return_1day"].index
    missing = (index.get_level_values("Code") == "10000") & index.get_level_values("Date").isin(dates[20:60])
    inputs["raw_return_1day"] = inputs["raw_return_1day"].loc[~missing]
    inputs["raw_return_1day"].iloc[::19] = np.nan
    inputs["prices_daily_quotes"].iloc[::23] = 0.
    inputs["fins_statements"].iloc[::7] = np.inf
    scores, mid = f.components(inputs)
    shuffled = {k: v.sample(frac=1, random_state=42) for k, v in inputs.items()}
    got, mm = f.components(shuffled)
    exact(scores, got)
    exact(mid, mm)
    assert np.isfinite(f.score(scores)).all()
    assert scores.index.equals(inputs["raw_return_1day"].index)


@pytest.mark.parametrize("bad", ["duplicate", "missing", "unsorted"])
def test_rank_contract_rejects_invalid_components(bad):
    scores, _ = f.components(inputs_fixture())
    if bad == "duplicate":
        scores = pd.concat([scores, scores.iloc[:1]])
    elif bad == "missing":
        scores.iloc[0, 0] = np.nan
    else:
        scores = scores.iloc[::-1]
    with pytest.raises(ValueError):
        f.score(scores)


def test_adapter_is_label_free_self_contained_and_deterministic(tmp_path):
    inputs = inputs_fixture()
    for name, frame in inputs.items():
        frame.to_parquet(tmp_path / f"{name}_train.parquet")
    expected = f.score(f.components(inputs)[0]).to_frame()
    exact(expected, submission.predict(tmp_path))
    exact(expected, submission.predict(tmp_path))
    folder = Path(__file__).resolve().parents[3] / "stock_comp_2026/strategies/dm_slow_mom60_equal"
    script = 'import submission; import sys; p=submission.predict(sys.argv[1]); assert p.shape[1]==1; assert p.notna().all().all()'
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)], cwd=folder, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert source_scan(sorted(folder.rglob("*.py")))["status"] == "PASS"


def test_source_copy_and_reachable_momentum_functions_are_exact():
    root = Path(__file__).resolve().parents[3]
    folder = root / "stock_comp_2026/strategies/dm_slow_mom60_equal"
    original = root / "stock_comp_2026/strategies/dm_slow_multifactor/features.py"
    assert (folder / "component_slow/features.py").read_bytes() == original.read_bytes()
    copy = function_sources(folder / "component_momentum.py")
    frozen = function_sources(root / "releases/DM-20260908-v1/snapshot/stock_comp_2026/strategies/dm_trainonly/features.py")
    assert all(copy[k] == frozen[k] for k in ["build_momentum", "centered_rank", "segment_keys", "smooth"])


def test_parquet_null_payload_is_distinct_from_finite_component_bit_parity(tmp_path):
    index = pd.MultiIndex.from_product([[pd.Timestamp("2011-01-03")], list("ab")], names=["Date", "Code"])
    raw = pd.DataFrame({"raw_size": [-np.nan, 1.]}, index=index)
    raw.to_parquet(tmp_path / "raw.parquet")
    stored = pd.read_parquet(tmp_path / "raw.parquet")
    receipt = stored_raw_parity(raw, stored)
    assert receipt["columns"][0]["nan_payload_bit_differences"] == 1
    changed = stored.copy()
    changed.iloc[1, 0] = np.nextafter(1., 2.)
    with pytest.raises(AssertionError):
        stored_raw_parity(raw, changed)


def test_future_new_rows_preserve_input_timezone_and_prefix():
    inputs = inputs_fixture()
    for name in ["prices_daily_quotes", "fins_statements", "listed_info"]:
        frame = inputs[name].copy()
        arrays = frame.index.to_frame(index=False)
        arrays.Date = arrays.Date.dt.tz_localize("Asia/Tokyo")
        frame.index = pd.MultiIndex.from_frame(arrays)
        inputs[name] = frame
    scores, mid = f.components(inputs)
    cutoff = pd.Timestamp("2012-03-01")
    changed = {k: mutate(v, k, cutoff, 20261003) for k, v in inputs.items()}
    for name in ["prices_daily_quotes", "fins_statements", "listed_info"]:
        assert pd.DatetimeIndex(changed[name].index.get_level_values("Date")).tz is not None
    got, mm = f.components(changed)
    prefix = scores.index[scores.index.get_level_values("Date") <= cutoff]
    exact(scores.loc[prefix], got.loc[prefix])
    exact(mid.loc[prefix], mm.loc[prefix])
    exact(f.score(scores).loc[prefix], f.score(got).loc[prefix])


def test_official_membership_groups_and_attribution_missing_target_exit_costs(tmp_path):
    dates = pd.bdate_range("2011-01-03", periods=3)
    index = pd.MultiIndex.from_product([dates, [str(i) for i in range(10)]], names=["Date", "Code"])
    slow = pd.Series(np.tile(np.arange(10, dtype=float), 3), index=index)
    mom = pd.Series(np.tile(np.arange(10, dtype=float)[::-1], 3), index=index)
    candidate = slow.copy()
    candidate.loc[dates[1]] = candidate.loc[dates[1]].to_numpy()[::-1]
    target = pd.Series(.01, index=index, name="Return")
    target.iloc[0] = np.nan
    h = {name: holdings(s, target) for name, s in [(SLOW, slow), (MOM, mom), (CAND, candidate)]}
    groups = agreement_groups(h[SLOW].w, h[MOM].w)
    assert groups.loc[(dates[0], "0")] == "SLOW_LOW_MOM_HIGH"
    assert groups.loc[(dates[0], "9")] == "SLOW_HIGH_MOM_LOW"
    assert groups.loc[(dates[0], "4")] == "OTHER"
    assert h[CAND].cost.iloc[0] == 0 and h[CAND].cost_all.iloc[0] > 0
    assert attribution(h, target, dates, tmp_path)["status"] == "PASS"
    d = pd.read_csv(tmp_path / "momentum_contribution_daily.csv")
    assert d.groupby("Date").stock_days.sum().eq(10).all()
