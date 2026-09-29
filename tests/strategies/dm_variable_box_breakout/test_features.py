import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_variable_box_breakout import features
from stock_comp_2026.strategies.dm_variable_box_breakout import models
from stock_comp_2026.strategies.dm_breakout_side_momentum import features as reference_features
from stock_comp_2026.strategies.dm_breakout_base_momentum_overlay import models as reference_models


def synthetic_inputs(days=330, codes=("10000", "20000", "30000")):
    dates = pd.bdate_range("2009-01-05", periods=days)
    index = pd.MultiIndex.from_product([dates, codes], names=["Date", "Code"])
    day = np.repeat(np.arange(days, dtype=float), len(codes))
    close = np.full(len(index), 100.0)
    high = close * 1.01
    low = close * 0.99
    factor = np.ones(len(index))
    code_a = index.get_level_values("Code") == codes[0]
    date_values = index.get_level_values("Date")
    split_day = dates[280]
    split_rows = (date_values >= split_day) & code_a
    close[split_rows] *= 0.5
    high[split_rows] *= 0.5
    low[split_rows] *= 0.5
    factor[(date_values == split_day) & code_a] = 0.5
    final_rows = (date_values == dates[-1]) & code_a
    close[final_rows] = 120.0
    high[final_rows] = 121.0
    low[final_rows] = 119.0

    returns = pd.DataFrame({"Return": 0.001 + day * 0.0}, index=index)
    beta = pd.DataFrame({"Return": 0.0}, index=index)
    market = pd.DataFrame({"Return": 0.0}, index=pd.Index(dates, name="Date"))
    prices = pd.DataFrame(
        {"High": high, "Low": low, "Close": close, "AdjustmentFactor": factor},
        index=index,
    )
    return {
        "raw_return_1day": returns.sort_index(),
        "beta_1day": beta.sort_index(),
        "topix_return_1day": market.sort_index(),
        "prices_daily_quotes": prices.sort_index(),
    }


def mutate_after(inputs, cutoff, truncate=False):
    result = {}
    for name, frame in inputs.items():
        dates = frame.index.get_level_values("Date")
        future = dates > cutoff
        if truncate:
            result[name] = frame.loc[~future].copy()
            continue
        changed = frame.copy()
        for column in changed:
            if pd.api.types.is_numeric_dtype(changed[column]):
                if name == "prices_daily_quotes" and column == "AdjustmentFactor":
                    changed.loc[future, column] = 1.0
                else:
                    changed.loc[future, column] = changed.loc[future, column] * -3.14 + 888.0
        result[name] = changed
    return result


def test_variable_duration_and_split_unit_are_causal():
    inputs = synthetic_inputs()
    result = features.build_features(inputs)
    code = result.xs("10000", level="Code")
    # A quiet, constant-price history reaches the longest qualifying grid window.
    assert code.iloc[250]["box_duration"] == 120.0
    assert code.iloc[250]["box_width_atr"] < features.BOX_ATR_LIMIT
    assert np.isfinite(code.iloc[250]["close_position"])
    # The split at observation 280 does not create an artificial price range.
    prices = features.split_safe_prices(inputs).xs("10000", level="Code")
    assert prices.iloc[279]["close"] == prices.iloc[280]["close"]
    assert result["new_high_excess"].xs("10000", level="Code").iloc[-1] > 0.0
    assert result.index.equals(inputs["raw_return_1day"].index)


def test_feature_builder_is_invariant_to_equivalent_split_representations():
    split_inputs = synthetic_inputs()
    unsplit_inputs = {name: frame.copy() for name, frame in split_inputs.items()}

    prices = unsplit_inputs["prices_daily_quotes"]
    dates = prices.index.get_level_values("Date")
    codes = prices.index.get_level_values("Code")
    split_date = dates.unique().sort_values()[280]
    rows_after_split = (codes == "10000") & (dates >= split_date)
    prices.loc[rows_after_split, ["High", "Low", "Close"]] = (
        prices.loc[rows_after_split, ["High", "Low", "Close"]] * 2.0
    )
    split_day = (codes == "10000") & (dates == split_date)
    prices.loc[split_day, "AdjustmentFactor"] = 1.0

    expected = features.build_features(split_inputs)
    actual = features.build_features(unsplit_inputs)
    pd.testing.assert_frame_equal(actual, expected, check_exact=True)


def test_full_feature_builder_future_mutation_and_truncation_are_prefix_invariant():
    inputs = synthetic_inputs(days=390)
    original = features.build_features(inputs)
    cutoffs = (pd.Timestamp("2009-12-01"), pd.Timestamp("2010-01-29"))
    dates = original.index.get_level_values("Date")
    for cutoff in cutoffs:
        prefix = dates <= cutoff
        for truncate in (False, True):
            changed = features.build_features(mutate_after(inputs, cutoff, truncate=truncate))
            pd.testing.assert_frame_equal(
                original.loc[prefix],
                changed.loc[original.index[prefix]],
                check_exact=True,
            )


def test_features_are_prefix_invariant_under_future_mutation_and_truncation():
    inputs = synthetic_inputs()
    original = features.build_features(inputs)
    cutoff = pd.Timestamp("2009-12-01")
    prefix = original.index.get_level_values("Date") <= cutoff
    for truncate in (False, True):
        changed = features.build_features(mutate_after(inputs, cutoff, truncate=truncate))
        pd.testing.assert_frame_equal(original.loc[prefix], changed.loc[original.index[prefix]], check_exact=True)


def test_box_feature_schema_and_no_valid_price_levels():
    inputs = synthetic_inputs()
    result = features.build_features(inputs)
    assert tuple(result.attrs["feature_columns"]) == features.FEATURE_COLUMNS
    assert list(result.columns) == [
        "box_duration", "box_width_atr", "close_position", "relative_strength_60",
        "distance_to_prior_high", "distance_to_prior_low", "new_high_excess", "new_low_excess",
        "high_available", "low_available",
    ]
    assert not result["box_duration"].isna().any()
    assert np.isfinite(result.loc[result["low_available"], "distance_to_prior_low"]).any()
    expected = reference_models.generate_signal(reference_features.build_features(inputs), "B00")
    actual = models.generate_base_signal(result)
    pd.testing.assert_series_equal(expected, actual, check_exact=True)
