"""Causal Train-only features for channel position and volume change."""
from pathlib import Path

import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_breakout_side_momentum.features import segment_keys
from stock_comp_2026.strategies.dm_slope_range_volume_ml.features import (
    split_safe_prices_and_volume,
)


INPUT_COLUMNS = {
    "raw_return_1day": ["Return"],
    "beta_1day": ["Return"],
    "topix_return_1day": ["Return"],
    "prices_daily_quotes": ["High", "Low", "Close", "Volume", "AdjustmentFactor"],
}
FEATURE_COLUMNS = ("channel_position_250", "volume_change_1d")
CHANNEL_WINDOW = 250


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


def build_features(inputs):
    """Build signal-date features using observations no later than t-1.

    At signal date t, channel position uses Close(t-1) against the split-safe
    High/Low range from t-251 through t-2. Volume change compares split-safe
    Volume(t-1) with Volume(t-2). The volume levels use raw Volume multiplied
    by cumulative, observed AdjustmentFactor events; no adjusted-volume level
    is read. Channel values outside [-1, 1] remain unclipped.
    """
    index = inputs["raw_return_1day"].index
    if not index.is_unique:
        raise ValueError("Feature input index must be unique")
    values = split_safe_prices_and_volume(inputs).reindex(index)
    groups = segment_keys(index)

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
    channel = (
        2.0 * (prior_close - barrier_low) / width - 1.0
    ).where(
        prior_close.notna() & barrier_high.notna() & barrier_low.notna() & (width > 0)
    )

    volume = values["volume"]
    prior_volume = volume.groupby(groups, sort=False).shift(1)
    two_days_prior_volume = volume.groupby(groups, sort=False).shift(2)
    volume_change = (
        prior_volume / two_days_prior_volume - 1.0
    ).where(
        prior_volume.notna()
        & two_days_prior_volume.notna()
        & (prior_volume > 0)
        & (two_days_prior_volume > 0)
    )

    features = pd.DataFrame(
        {"channel_position_250": channel, "volume_change_1d": volume_change},
        index=index,
    ).replace([np.inf, -np.inf], np.nan)
    features.attrs["feature_columns"] = list(FEATURE_COLUMNS)
    return features
