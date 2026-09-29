"""Causal Train-only price-slope, 52-week channel and volume features."""
from pathlib import Path

import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_breakout_side_momentum.features import segment_keys


INPUT_COLUMNS = {
    "raw_return_1day": ["Return"],
    "beta_1day": ["Return"],
    "topix_return_1day": ["Return"],
    "prices_daily_quotes": ["High", "Low", "Close", "Volume", "AdjustmentFactor"],
}
FEATURE_COLUMNS = (
    "log_price_slope_60_bps_day",
    "channel_position_250",
    "volume_zscore_60",
)
SLOPE_WINDOW = 60
CHANNEL_WINDOW = 250
VOLUME_WINDOW = 60


def load_inputs(directory, split="train"):
    """Read only the explicitly allowed Train feature files."""
    if split != "train":
        raise ValueError("This research loader accepts Train only")
    result = {}
    for name, columns in INPUT_COLUMNS.items():
        frame = pd.read_parquet(Path(directory) / f"{name}_train.parquet", columns=columns)
        if not frame.index.is_unique:
            raise ValueError(f"Duplicate index in {name}")
        result[name] = frame.sort_index()
    return result


def split_safe_prices_and_volume(inputs):
    """Express raw prices and volume in a causal common unit across share events."""
    index = inputs["raw_return_1day"].index
    prices = inputs["prices_daily_quotes"].reindex(index)
    factor = pd.to_numeric(prices["AdjustmentFactor"], errors="coerce")
    invalid = factor.isna() | ~np.isfinite(factor) | (factor <= 0)
    if invalid.any():
        raise ValueError("AdjustmentFactor must be finite and positive")
    event = factor.where(~np.isclose(factor, 1.0, rtol=1e-12, atol=1e-12), 1.0)
    groups = segment_keys(index)
    scale = event.groupby(groups, sort=False).cumprod()
    result = pd.DataFrame(index=index)
    for column in ("High", "Low", "Close"):
        values = pd.to_numeric(prices[column], errors="coerce")
        values = values.where((values > 0) & np.isfinite(values))
        result[column.lower()] = values / scale
    volume = pd.to_numeric(prices["Volume"], errors="coerce")
    volume = volume.where((volume > 0) & np.isfinite(volume))
    result["volume"] = volume * scale
    result = result.replace([np.inf, -np.inf], np.nan)
    return result


def _ols_slope(values):
    """OLS slope for equally spaced log-price observations."""
    width = len(values)
    centered_time = np.arange(width, dtype=float) - (width - 1.0) / 2.0
    denominator = float(np.dot(centered_time, centered_time))
    return float(np.dot(centered_time, values) / denominator)


def build_features(inputs):
    """Build features for signal date t only from observations through t-1.

    Slope uses log Close for t-60 through t-1. Channel position uses Close
    at t-1 and High/Low from t-251 through t-2. Volume z-score compares
    Volume at t-1 with the mean and population standard deviation from t-61
    through t-2. Channel values outside the historical range remain outside
    [-1, 1], preserving the breakout distance.
    """
    index = inputs["raw_return_1day"].index
    values = split_safe_prices_and_volume(inputs)
    groups = segment_keys(index)

    log_close = np.log(values["close"].where(values["close"] > 0))
    slope = log_close.groupby(groups, sort=False).transform(
        lambda series: series.shift(1).rolling(
            SLOPE_WINDOW, min_periods=SLOPE_WINDOW
        ).apply(_ols_slope, raw=True)
    ) * 10000.0

    prior_close = values["close"].groupby(groups, sort=False).shift(1)
    barrier_high = values["high"].groupby(groups, sort=False).transform(
        lambda series: series.shift(2).rolling(
            CHANNEL_WINDOW, min_periods=CHANNEL_WINDOW
        ).max()
    )
    barrier_low = values["low"].groupby(groups, sort=False).transform(
        lambda series: series.shift(2).rolling(
            CHANNEL_WINDOW, min_periods=CHANNEL_WINDOW
        ).min()
    )
    width = barrier_high - barrier_low
    channel = (2.0 * (prior_close - barrier_low) / width - 1.0).where(
        prior_close.notna() & barrier_high.notna() & barrier_low.notna() & (width > 0)
    )

    volume = values["volume"]
    prior_volume = volume.groupby(groups, sort=False).shift(1)
    reference = volume.groupby(groups, sort=False).transform(
        lambda series: series.shift(2).rolling(
            VOLUME_WINDOW, min_periods=VOLUME_WINDOW
        ).mean()
    )
    reference_std = volume.groupby(groups, sort=False).transform(
        lambda series: series.shift(2).rolling(
            VOLUME_WINDOW, min_periods=VOLUME_WINDOW
        ).std(ddof=0)
    )
    zscore = ((prior_volume - reference) / reference_std).where(reference_std > 0)

    features = pd.DataFrame(
        {
            "log_price_slope_60_bps_day": slope,
            "channel_position_250": channel,
            "volume_zscore_60": zscore,
        },
        index=index,
    ).replace([np.inf, -np.inf], np.nan)
    features.attrs["feature_columns"] = list(FEATURE_COLUMNS)
    return features
