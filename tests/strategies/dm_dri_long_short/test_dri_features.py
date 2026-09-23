"""Contract, causality primitives, and edge cases for DRI feature construction."""
import ast
from pathlib import Path

import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_dri_long_short import features


def synthetic_inputs(days=24):
    dates = pd.bdate_range("2020-01-02", periods=days)
    index = pd.MultiIndex.from_product([dates, ["a", "b"]], names=["Date", "Code"])
    raw = pd.Series(np.arange(len(index), dtype=float) / 1000.0, index=index)
    beta = pd.Series(1.0, index=index)
    topix = pd.Series(0.001, index=dates, name="Return")
    return {
        "raw_return_1day": raw.rename("Return").to_frame(),
        "beta_1day": beta.rename("Return").to_frame(),
        "topix_return_1day": topix.to_frame(),
    }


def test_complete_window_and_sorted_vector_are_exact():
    result = features.build_features(synthetic_inputs())
    date = pd.bdate_range("2020-01-02", periods=24)[20]
    row = result.loc[(date, "a")]
    expected = np.array([0.04 - lag * 0.002 for lag in range(21)])
    np.testing.assert_allclose(row[features.feature_columns("raw")[:21]].to_numpy(dtype=float), expected)
    np.testing.assert_allclose(row[features.feature_columns("raw")[21:]].to_numpy(dtype=float), np.sort(expected))
    assert not result.loc[(pd.bdate_range("2020-01-02", periods=24)[19], "a"), "raw_available"]
    assert row.raw_available


def test_missing_observation_makes_only_affected_window_neutral():
    inputs = synthetic_inputs()
    date = pd.bdate_range("2020-01-02", periods=24)[10]
    inputs["raw_return_1day"].loc[(date, "a"), "Return"] = np.nan
    result = features.build_features(inputs)
    assert not result.loc[(pd.bdate_range("2020-01-02", periods=24)[20], "a"), "raw_available"]
    assert result.loc[(pd.bdate_range("2020-01-02", periods=24)[20], "b"), "raw_available"]


def test_smoothing_preserves_current_missing_neutral_and_is_deterministic():
    index = pd.MultiIndex.from_product([[pd.Timestamp("2020-01-02"), pd.Timestamp("2020-01-03"), pd.Timestamp("2020-01-06")], ["a"]], names=["Date", "Code"])
    score = pd.Series([1.0, 2.0, 3.0], index=index)
    available = pd.Series([True, False, True], index=index)
    first = features.smooth_complete(score, available, .25)
    second = features.smooth_complete(score, available, .25)
    pd.testing.assert_series_equal(first, second, check_exact=True)
    assert first.iloc[1] == 0.0


def test_source_firewall_static_contract():
    folder = Path(features.__file__).parent
    forbidden = ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose", "AdjustmentVolume",
                 "raw_target", "target_1day_valid"]
    for path in folder.glob("*.py"):
        text = path.read_text()
        for token in forbidden:
            assert token not in text, (path, token)
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in ("bfill", "backfill")
                if node.func.attr == "shift" and node.args:
                    assert isinstance(node.args[0], ast.Constant) and node.args[0].value >= 0
                assert not any(k.arg == "center" and isinstance(k.value, ast.Constant) and k.value.value for k in node.keywords)
                assert not any(k.arg == "direction" and isinstance(k.value, ast.Constant) and k.value.value == "forward" for k in node.keywords)
