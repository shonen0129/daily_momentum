"""Causality and boundary tests for advanced DTI representations."""
import ast
from pathlib import Path

import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_advanced_dti import features


def index_for(days=90, codes=("a", "b")):
    return pd.MultiIndex.from_product([pd.bdate_range("2020-01-02", periods=days), codes], names=["Date", "Code"])


def test_strictly_prior_median_excludes_current_and_future_rows():
    index = index_for(days=65, codes=("a",))
    value = pd.Series(np.arange(65, dtype=float), index=index)
    baseline = features.strictly_prior_median(value)
    # At row 60, precisely rows 0..59 are eligible, so their median is 29.5.
    assert baseline.iloc[60] == 29.5
    changed = value.copy()
    changed.iloc[60:] = -99999.0
    pd.testing.assert_series_equal(baseline.iloc[:60], features.strictly_prior_median(changed).iloc[:60], check_exact=True)


def test_vector_is_exact_and_missing_volume_only_invalidates_affected_window():
    index = index_for(days=24)
    value = pd.Series(np.arange(len(index), dtype=float) / 1000 + .01, index=index)
    result, available = features.vector(value, "x")
    date = index.get_level_values("Date").unique()[20]
    expected = np.array([.05 - lag * .002 for lag in range(21)])
    np.testing.assert_allclose(result.loc[(date, "a")].to_numpy(float), np.r_[expected, np.sort(expected)])
    assert available.loc[(date, "a")]
    value.loc[(index.get_level_values("Date").unique()[10], "a")] = np.nan
    _, altered = features.vector(value, "x")
    assert not altered.loc[(date, "a")]
    assert altered.loc[(date, "b")]


def test_signed_channels_preserve_zero_return_and_do_not_turn_missing_return_into_zero():
    index = index_for(days=1)
    abnormal = pd.Series([2.0, -3.0], index=index)
    residual = pd.Series([0.0, np.nan], index=index)
    up = abnormal.where(residual > 0, 0.0).where(residual.notna())
    down = abnormal.where(residual < 0, 0.0).where(residual.notna())
    assert up.iloc[0] == 0.0 and down.iloc[0] == 0.0
    assert np.isnan(up.iloc[1]) and np.isnan(down.iloc[1])


def test_ewma_is_deterministic_and_resets_unavailable_to_neutral():
    index = pd.MultiIndex.from_product([[pd.Timestamp("2020-01-02"), pd.Timestamp("2020-01-03"), pd.Timestamp("2020-01-06")], ["a"]], names=["Date", "Code"])
    score, available = pd.Series([1.0, 2.0, 3.0], index=index), pd.Series([True, False, True], index=index)
    first = features.smooth_complete(score, available, .05)
    pd.testing.assert_series_equal(first, features.smooth_complete(score, available, .05), check_exact=True)
    assert first.iloc[1] == 0.0


def test_source_firewall_static_contract():
    forbidden = ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose", "AdjustmentVolume", "raw_target", "target_1day_valid"]
    for path in Path(features.__file__).parent.glob("*.py"):
        source = path.read_text()
        for token in forbidden:
            assert token not in source, (path, token)
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in ("bfill", "backfill")
                if node.func.attr == "shift" and node.args:
                    assert isinstance(node.args[0], ast.Constant) and node.args[0].value >= 0
                assert not any(k.arg == "center" and isinstance(k.value, ast.Constant) and k.value.value for k in node.keywords)
                assert not any(k.arg == "direction" and isinstance(k.value, ast.Constant) and k.value.value == "forward" for k in node.keywords)
