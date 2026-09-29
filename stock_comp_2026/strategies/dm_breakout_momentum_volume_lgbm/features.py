"""Causal features for the exploratory Train-only LightGBM."""
from pathlib import Path

import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_breakout_side_momentum import features as breakout


INPUT_COLUMNS = {
    "raw_return_1day": ["Return"],
    "beta_1day": ["Return"],
    "topix_return_1day": ["Return"],
    "prices_daily_quotes": ["High", "Low", "Close", "Volume", "AdjustmentFactor"],
}
FEATURE_COLUMNS = (
    "res60s1",
    "new_high_rank",
    "new_low_rank",
    "relative_volume_change_rank",
)


def load_inputs(directory, split="train"):
    """Load only the Train portion for this exploratory model."""
    if split != "train":
        raise ValueError("This research feature loader only accepts the Train split")
    result = {}
    for name, columns in INPUT_COLUMNS.items():
        frame = pd.read_parquet(Path(directory) / f"{name}_train.parquet", columns=columns)
        if not frame.index.is_unique:
            raise ValueError(f"Duplicate index in {name}")
        result[name] = frame.sort_index()
    return result


def split_safe_volume(inputs):
    """Express raw volume in a stable share unit across observed action factors."""
    index = inputs["raw_return_1day"].index
    prices = inputs["prices_daily_quotes"].reindex(index)
    factor = pd.to_numeric(prices["AdjustmentFactor"], errors="coerce")
    if factor.isna().any() or (~np.isfinite(factor)).any() or (factor <= 0).any():
        raise ValueError("AdjustmentFactor must be finite and positive")
    event_factor = factor.where(~np.isclose(factor, 1.0, rtol=1e-12, atol=1e-12), 1.0)
    scale = event_factor.groupby(breakout.segment_keys(index), sort=False).cumprod()
    volume = pd.to_numeric(prices["Volume"], errors="coerce")
    volume = volume.where((volume > 0) & np.isfinite(volume))
    return (volume * scale).rename("split_safe_volume")


def centered_rank_preserving_missing(series):
    """Daily centered percentile rank without turning unavailable history into zero."""
    values = series.replace([np.inf, -np.inf], np.nan)
    ranks = values.groupby(level="Date").rank(method="average", pct=True)
    center = ranks.groupby(level="Date").transform("mean")
    return (2.0 * (ranks - center)).rename(series.name)


def relative_volume_change(inputs, window=20):
    index = inputs["raw_return_1day"].index
    volume = split_safe_volume(inputs)
    groups = breakout.segment_keys(index)
    prior_median = volume.groupby(groups, sort=False).transform(
        lambda values: values.shift(1).rolling(window, min_periods=window).median()
    )
    ratio = np.log(volume.where(volume > 0) / prior_median.where(prior_median > 0))
    ratio.name = "relative_volume_change"
    return centered_rank_preserving_missing(ratio).rename("relative_volume_change_rank")


def build_features(inputs):
    """Build prior-only breakout, residual momentum and relative-volume ranks."""
    base = breakout.build_features(inputs, window=250)
    high = centered_rank_preserving_missing(base["new_high_excess"]).rename("new_high_rank")
    low = centered_rank_preserving_missing(base["new_low_excess"]).rename("new_low_rank")
    result = pd.DataFrame(
        {
            "res60s1": base["res60s1"],
            "new_high_rank": high,
            "new_low_rank": low,
            "relative_volume_change_rank": relative_volume_change(inputs),
        },
        index=base.index,
    )
    result = result.replace([np.inf, -np.inf], np.nan)
    result.attrs["feature_columns"] = list(FEATURE_COLUMNS)
    return result
