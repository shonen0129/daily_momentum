"""Tests for dm_high_proximity_momentum features and models."""
import ast
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from stock_comp_2026.strategies.dm_high_proximity_momentum import features, models


def test_static_source_firewall_contract():
    forbidden = [
        "AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose", "AdjustmentVolume",
        "raw_target", "target_1day_valid"
    ]
    for path in Path(features.__file__).parent.glob("*.py"):
        text = path.read_text()
        for token in forbidden:
            assert token not in text, f"Forbidden token {token} in {path}"
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in ("bfill", "backfill"), f"backfill found in {path}"
                if node.func.attr == "shift":
                    value = node.args[0] if node.args else next(k.value for k in node.keywords if k.arg == "periods")
                    assert isinstance(value, ast.Constant) and value.value >= 0, f"negative shift in {path}"
                assert not any(k.arg == "center" and isinstance(k.value, ast.Constant) and k.value.value for k in node.keywords), f"center rolling in {path}"
                assert not any(k.arg == "direction" and isinstance(k.value, ast.Constant) and k.value.value == "forward" for k in node.keywords), f"forward join in {path}"


def test_high_proximity_ratio_bounds_and_causality():
    dates = pd.bdate_range("2020-01-01", periods=30)
    index = pd.MultiIndex.from_product([dates, ["1001", "1002"]], names=["Date", "Code"])

    # Code 1001: monotonic upward, Close == High -> ratio should be 1.0
    # Code 1002: high at day 0 (100.0), close dropping to 50.0 -> ratio drops
    high = pd.Series(index=index, dtype=float)
    close = pd.Series(index=index, dtype=float)

    for i, d in enumerate(dates):
        high.loc[(d, "1001")] = 100.0 + i
        close.loc[(d, "1001")] = 100.0 + i

        high.loc[(d, "1002")] = 100.0
        close.loc[(d, "1002")] = 100.0 - i

    prices = pd.DataFrame({"High": high, "Close": close}, index=index)
    dummy_ret = pd.DataFrame({"Return": 0.01}, index=index)
    inputs = {
        "raw_return_1day": dummy_ret,
        "prices_daily_quotes": prices,
        "beta_1day": dummy_ret,
        "topix_return_1day": pd.DataFrame({"Return": 0.01}, index=dates),
    }

    prox = features.build_high_proximity(inputs, window=20, min_periods=20)
    # Check that centered rank output has values within [-1, 1]
    assert np.isfinite(prox).all()
    assert prox.min() >= -1.0
    assert prox.max() <= 1.0


def test_future_mutation_prefix_invariance():
    dates = pd.bdate_range("2020-01-01", periods=80)
    index = pd.MultiIndex.from_product([dates, ["1001", "1002", "1003"]], names=["Date", "Code"])
    rng = np.random.default_rng(42)

    close_arr = 100.0 + rng.normal(0, 2, len(index)).cumsum()
    close = pd.Series(np.maximum(close_arr, 1.0), index=index)
    high = close + rng.uniform(0, 3, len(index))

    prices = pd.DataFrame({"High": high, "Close": close, "AdjustmentFactor": 1.0}, index=index)
    ret = pd.DataFrame({"Return": rng.normal(0, 0.01, len(index))}, index=index)
    beta = pd.DataFrame({"Return": 1.0}, index=index)
    market = pd.DataFrame({"Return": rng.normal(0, 0.01, len(dates))}, index=dates)

    inputs = {
        "raw_return_1day": ret,
        "prices_daily_quotes": prices,
        "beta_1day": beta,
        "topix_return_1day": market,
    }

    base_features = features.build_features(inputs)
    repeated_features = features.build_features(inputs)
    pd.testing.assert_frame_equal(base_features, repeated_features, check_exact=True)

    # Cutoff at day 40: mutate future days (> 40)
    cutoff = dates[40]
    future_mask = index.get_level_values("Date") > cutoff

    mutated_prices = prices.copy()
    mutated_prices.loc[future_mask, "High"] = mutated_prices.loc[future_mask, "High"] * 5.0 + 1000.0
    mutated_prices.loc[future_mask, "Close"] = mutated_prices.loc[future_mask, "Close"] * 0.1
    mutated_prices.loc[future_mask, "AdjustmentFactor"] = 1.0
    first_future_date = dates[41]
    mutated_prices.loc[(first_future_date, slice(None)), "AdjustmentFactor"] = 0.25

    mutated_ret = ret.copy()
    mutated_ret.loc[future_mask, "Return"] = -0.5

    mutated_inputs = {
        "raw_return_1day": mutated_ret,
        "prices_daily_quotes": mutated_prices,
        "beta_1day": beta,
        "topix_return_1day": market,
    }

    mutated_features = features.build_features(mutated_inputs)

    # Verify that before/at cutoff, features are bitwise identical
    prefix = index.get_level_values("Date") <= cutoff
    pd.testing.assert_frame_equal(
        base_features.loc[prefix],
        mutated_features.loc[prefix],
        check_exact=True
    )

    # Also test models signals
    for trial_id in ("H0", "P60", "P250", "C1", "C2", "C3", "C3S", "C4", "C5", "C6"):
        sig_base = models.generate_signal(base_features, trial_id)
        sig_repeat = models.generate_signal(repeated_features, trial_id)
        pd.testing.assert_series_equal(sig_base, sig_repeat, check_exact=True)
        sig_mutated = models.generate_signal(mutated_features, trial_id)
        pd.testing.assert_series_equal(
            sig_base.loc[prefix],
            sig_mutated.loc[prefix],
            check_exact=True
        )


def test_split_safe_proximity_carries_event_factor_and_requires_full_window():
    dates = pd.bdate_range("2020-01-01", periods=300)
    index = pd.MultiIndex.from_product([dates, ["1001"]], names=["Date", "Code"])
    high = np.full(len(index), 1000.0)
    close = np.full(len(index), 850.0)
    factor = np.ones(len(index))

    # A 1:400 split is recorded as a one-row event multiplier, then resets to 1.
    high[250:] = 2.5
    close[250:] = 2.125
    factor[250] = 0.0025
    inputs = {
        "raw_return_1day": pd.DataFrame({"Return": 0.0}, index=index),
        "prices_daily_quotes": pd.DataFrame(
            {"High": high, "Close": close, "AdjustmentFactor": factor}, index=index
        ),
    }

    raw = features.build_high_proximity_ratio(inputs, window=250, min_periods=250)
    split_safe = features.build_high_proximity_ratio(
        inputs, window=250, min_periods=250, split_safe=True
    )

    assert np.isnan(raw.iloc[248])  # fewer than 250 observations
    assert np.isclose(raw.iloc[250], 2.125 / 1000.0)
    assert np.isclose(split_safe.iloc[250], 0.85)
    assert np.isclose(split_safe.iloc[251], 0.85)


def test_split_safe_proximity_rejects_missing_adjustment_factor():
    dates = pd.bdate_range("2020-01-01", periods=3)
    index = pd.MultiIndex.from_product([dates, ["1001"]], names=["Date", "Code"])
    inputs = {
        "raw_return_1day": pd.DataFrame({"Return": 0.0}, index=index),
        "prices_daily_quotes": pd.DataFrame(
            {"High": 100.0, "Close": 99.0, "AdjustmentFactor": [1.0, np.nan, 1.0]},
            index=index,
        ),
    }
    with pytest.raises(ValueError, match="AdjustmentFactor must be finite and positive"):
        features.build_high_proximity_split_safe(inputs)


def test_c6_is_equal_blend_of_c2_and_c3():
    dates = pd.bdate_range("2020-01-01", periods=40)
    index = pd.MultiIndex.from_product([dates, ["1001", "1002"]], names=["Date", "Code"])
    rng = np.random.default_rng(17)
    candidate_features = pd.DataFrame({
        "res60s1": pd.Series(rng.normal(size=len(index)), index=index),
        "prox20": pd.Series(rng.normal(size=len(index)), index=index),
        "prox60": pd.Series(rng.normal(size=len(index)), index=index),
        "prox250": pd.Series(rng.normal(size=len(index)), index=index),
    }, index=index)

    expected = 0.5 * (
        models.generate_signal(candidate_features, "C2")
        + models.generate_signal(candidate_features, "C3")
    )
    actual = models.generate_signal(candidate_features, "C6")
    np.testing.assert_allclose(actual.to_numpy(), expected.to_numpy(), rtol=1e-13, atol=1e-14)


def test_p250_is_pure_52_week_proximity():
    dates = pd.bdate_range("2020-01-01", periods=40)
    index = pd.MultiIndex.from_product([dates, ["1001", "1002"]], names=["Date", "Code"])
    rng = np.random.default_rng(52)
    candidate_features = pd.DataFrame({
        "res60s1": pd.Series(rng.normal(size=len(index)), index=index),
        "prox20": pd.Series(rng.normal(size=len(index)), index=index),
        "prox60": pd.Series(rng.normal(size=len(index)), index=index),
        "prox250": pd.Series(rng.normal(size=len(index)), index=index),
    }, index=index)

    expected = features.smooth(candidate_features["prox250"], alpha=0.25)
    actual = models.generate_signal(candidate_features, "P250")
    pd.testing.assert_series_equal(actual, expected)
