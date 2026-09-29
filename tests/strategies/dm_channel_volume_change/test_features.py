import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_channel_volume_change.features import build_features


def make_inputs(rows=280):
    dates = pd.bdate_range("2010-01-04", periods=rows)
    index = pd.MultiIndex.from_product(
        [["TEST"], dates], names=["Code", "Date"]
    ).swaplevel().sort_values()
    position = np.arange(rows, dtype=float)
    close = 100.0 + position * 0.1
    high = close + 1.0
    low = close - 1.0
    volume = 1000.0 + position * 10.0
    prices = pd.DataFrame(
        {
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
            "AdjustmentFactor": np.ones(rows),
        },
        index=index,
    )
    return {
        "raw_return_1day": pd.DataFrame({"Return": np.zeros(rows)}, index=index),
        "prices_daily_quotes": prices,
    }, close, high, low, volume


def test_channel_uses_previous_close_and_250_earlier_high_low_rows():
    inputs, close, high, low, _ = make_inputs()
    result = build_features(inputs)
    signal_row = 270
    expected_high = high[signal_row - 251:signal_row - 1].max()
    expected_low = low[signal_row - 251:signal_row - 1].min()
    expected_close = close[signal_row - 1]
    expected = 2.0 * (expected_close - expected_low) / (expected_high - expected_low) - 1.0
    np.testing.assert_allclose(
        result.iloc[signal_row]["channel_position_250"], expected, rtol=0, atol=1e-12
    )


def test_volume_change_compares_previous_and_two_days_prior():
    inputs, _, _, _, volume = make_inputs()
    result = build_features(inputs)
    signal_row = 270
    expected = volume[signal_row - 1] / volume[signal_row - 2] - 1.0
    np.testing.assert_allclose(
        result.iloc[signal_row]["volume_change_1d"], expected, rtol=0, atol=1e-12
    )


def test_channel_and_volume_change_are_stable_across_split_event():
    original, close, high, low, volume = make_inputs()
    split = {
        name: frame.copy(deep=True) for name, frame in original.items()
    }
    quotes = split["prices_daily_quotes"]
    event_row = 260
    after = np.arange(len(close)) >= event_row
    for column, source in (("High", high), ("Low", low), ("Close", close)):
        quotes.loc[:, column] = source * np.where(after, 0.1, 1.0)
    quotes.loc[:, "Volume"] = volume * np.where(after, 10.0, 1.0)
    quotes.loc[:, "AdjustmentFactor"] = 1.0
    quotes.iloc[event_row, quotes.columns.get_loc("AdjustmentFactor")] = 0.1

    base_result = build_features(original)
    split_result = build_features(split)
    np.testing.assert_allclose(
        base_result.iloc[event_row + 1:].to_numpy(),
        split_result.iloc[event_row + 1:].to_numpy(),
        rtol=1e-12,
        atol=1e-12,
        equal_nan=True,
    )


def test_mutating_inputs_after_cutoff_does_not_change_feature_prefix():
    original, _, _, _, _ = make_inputs()
    expected = build_features(original)
    cutoff = expected.index.get_level_values("Date")[270]
    changed = {name: frame.copy(deep=True) for name, frame in original.items()}
    for name, frame in changed.items():
        future = frame.index.get_level_values("Date") > cutoff
        for column in frame.select_dtypes(include=[np.number]).columns:
            if name == "prices_daily_quotes" and column == "AdjustmentFactor":
                frame.loc[future, column] = 1.25
            else:
                frame.loc[future, column] = frame.loc[future, column] * -3.14 + 888.0
    actual = build_features(changed)
    prefix = expected.index.get_level_values("Date") <= cutoff
    pd.testing.assert_frame_equal(expected.loc[prefix], actual.loc[prefix], check_exact=True)
