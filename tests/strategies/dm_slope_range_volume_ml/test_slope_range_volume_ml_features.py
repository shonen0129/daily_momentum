import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_slope_range_volume_ml.features import build_features


def make_inputs(rows=360):
    dates = pd.bdate_range("2010-01-04", periods=rows)
    index = pd.MultiIndex.from_product(
        [["TEST"], dates], names=["Code", "Date"]
    ).swaplevel().sort_values()
    step = np.arange(rows, dtype=float)
    close = 100.0 * np.exp(step * 0.001)
    volume = 1000.0 + (step % 7.0) * 100.0
    volume[299] = 5000.0
    prices = pd.DataFrame(
        {
            "High": close + 2.0,
            "Low": close - 2.0,
            "Close": close,
            "Volume": volume,
            "AdjustmentFactor": np.ones(rows),
        },
        index=index,
    )
    return {
        "raw_return_1day": pd.DataFrame({"Return": np.zeros(rows)}, index=index),
        "prices_daily_quotes": prices,
    }, close, volume


def test_slope_and_channel_use_previous_close_with_prior_only_windows():
    inputs, close, _ = make_inputs()
    features = build_features(inputs)
    signal_row = 300
    index = features.index

    expected_slope = np.polyfit(
        np.arange(60, dtype=float), np.log(close[signal_row - 60:signal_row]), 1
    )[0] * 10000.0
    np.testing.assert_allclose(
        features.iloc[signal_row]["log_price_slope_60_bps_day"],
        expected_slope,
        rtol=0,
        atol=1e-10,
    )

    previous_close = close[signal_row - 1]
    prior_high = np.max(close[signal_row - 251:signal_row - 1] + 2.0)
    prior_low = np.min(close[signal_row - 251:signal_row - 1] - 2.0)
    expected_position = 2.0 * (previous_close - prior_low) / (prior_high - prior_low) - 1.0
    np.testing.assert_allclose(
        features.iloc[signal_row]["channel_position_250"],
        expected_position,
        rtol=0,
        atol=1e-12,
    )
    assert features.index.equals(index)


def test_volume_zscore_compares_previous_day_with_strictly_earlier_60_rows():
    inputs, _, volume = make_inputs()
    features = build_features(inputs)
    signal_row = 300
    reference = volume[signal_row - 61:signal_row - 1]
    expected = (volume[signal_row - 1] - reference.mean()) / reference.std(ddof=0)
    np.testing.assert_allclose(
        features.iloc[signal_row]["volume_zscore_60"],
        expected,
        rtol=0,
        atol=1e-12,
    )


def test_split_safe_features_preserve_continuity_across_share_factor_event():
    base, close, volume = make_inputs()
    split = {
        key: value.copy(deep=True) if isinstance(value, pd.DataFrame) else value.copy()
        for key, value in base.items()
    }
    quotes = split["prices_daily_quotes"]
    row = 299
    after = np.arange(len(close)) >= row
    for column in ("High", "Low", "Close"):
        quotes.loc[:, column] = quotes[column].to_numpy() * np.where(after, 0.1, 1.0)
    quotes.loc[:, "Volume"] = volume * np.where(after, 10.0, 1.0)
    quotes.loc[:, "AdjustmentFactor"] = 1.0
    quotes.iloc[row, quotes.columns.get_loc("AdjustmentFactor")] = 0.1

    original_features = build_features(base)
    split_features = build_features(split)
    np.testing.assert_allclose(
        original_features.iloc[300:].to_numpy(),
        split_features.iloc[300:].to_numpy(),
        rtol=1e-12,
        atol=1e-12,
        equal_nan=True,
    )
