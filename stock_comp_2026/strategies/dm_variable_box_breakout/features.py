"""Causal, split-safe features for the variable-duration box hypothesis."""
from pathlib import Path

import numpy as np
import pandas as pd


INPUT_COLUMNS = {
    "raw_return_1day": ["Return"],
    "beta_1day": ["Return"],
    "topix_return_1day": ["Return"],
    "prices_daily_quotes": ["High", "Low", "Close", "AdjustmentFactor"],
}
BOX_WINDOWS = tuple(range(5, 121, 5))
BOX_ATR_LIMIT = 3.0
ATR_WINDOW = 20
BREAKOUT_WINDOW = 250
FEATURE_COLUMNS = (
    "box_duration",
    "box_width_atr",
    "close_position",
    "relative_strength_60",
    "distance_to_prior_high",
)
LOW_DISTANCE_COLUMN = "distance_to_prior_low"


def load_inputs(directory, split="train"):
    """Read only the requested feature split; research runs request Train."""
    if split not in ("train", "valid"):
        raise ValueError(f"Unknown split: {split}")
    result = {}
    for name, columns in INPUT_COLUMNS.items():
        frame = pd.read_parquet(Path(directory) / f"{name}_{split}.parquet", columns=columns)
        if not frame.index.is_unique:
            raise ValueError(f"Duplicate index in {name}")
        result[name] = frame.sort_index()
    return result


def segment_keys(index):
    """Reset rolling state after a long absence that may indicate relisting."""
    dates = index.get_level_values("Date")
    calendar = dates.unique().sort_values()
    ordinal = pd.Series(calendar.get_indexer(dates), index=index)
    code = index.get_level_values("Code")
    starts = ordinal.groupby(code, sort=False).diff().gt(20)
    segment = starts.groupby(code, sort=False).cumsum().astype(int)
    return [code, segment]


def centered_rank(values):
    values = values.replace([np.inf, -np.inf], np.nan)
    ranks = values.groupby(level="Date").rank(method="average", pct=True)
    center = ranks.groupby(level="Date").transform("mean")
    return (2.0 * (ranks - center)).fillna(0.0)


def smooth_by_listing(values, alpha=0.25):
    groups = segment_keys(values.index)
    return values.groupby(groups, sort=False).transform(
        lambda series: series.ewm(alpha=alpha, adjust=False).mean()
    )


def split_safe_prices(inputs):
    """Use raw OHLC plus only the observed corporate-action factors."""
    index = inputs["raw_return_1day"].index
    prices = inputs["prices_daily_quotes"].reindex(index)
    groups = segment_keys(index)
    factor = pd.to_numeric(prices["AdjustmentFactor"], errors="coerce")
    invalid = factor.isna() | ~np.isfinite(factor) | (factor <= 0.0)
    if invalid.any():
        raise ValueError("AdjustmentFactor must be finite and positive")
    event_factor = factor.where(~np.isclose(factor, 1.0, rtol=1e-12, atol=1e-12), 1.0)
    scale = event_factor.groupby(groups, sort=False).cumprod()
    output = pd.DataFrame(index=index)
    for column in ("High", "Low", "Close"):
        value = pd.to_numeric(prices[column], errors="coerce")
        value = value.where((value > 0.0) & np.isfinite(value))
        output[column.lower()] = value / scale
    output["event_factor"] = event_factor
    return output.replace([np.inf, -np.inf], np.nan)


def build_relative_strength(inputs):
    """Champion 60-observation market-residual momentum, skip one observation."""
    returns = inputs["raw_return_1day"]["Return"].sort_index().replace([np.inf, -np.inf], np.nan)
    index = returns.index
    dates = index.get_level_values("Date")
    beta = inputs["beta_1day"]["Return"].reindex(index)
    market = pd.Series(
        inputs["topix_return_1day"]["Return"].reindex(dates).to_numpy(), index=index
    )
    residual = (returns - beta * market).replace([np.inf, -np.inf], np.nan)
    groups = segment_keys(index)
    prior = residual.groupby(groups, sort=False).shift(1)
    trailing = prior.groupby(groups, sort=False).transform(
        lambda series: series.rolling(60, min_periods=60).sum()
    )
    return centered_rank(trailing).rename("relative_strength_60")


def build_features(inputs):
    """Build signal-date features, with box state ending at t-1 and breakout at t.

    Box duration is the longest qualifying lookback on a fixed 5-observation
    grid from 5 through 120. Its prior-only High-Low range must be below 3x
    the 20-observation ATR available at t-1. The t-1 close position is measured
    within that same box. Breakouts compare t Close with t-1's prior-only
    250-observation barrier.
    """
    index = inputs["raw_return_1day"].index
    prices = split_safe_prices(inputs).reindex(index)
    groups = segment_keys(index)
    high, low, close = prices["high"], prices["low"], prices["close"]

    prior_close = close.groupby(groups, sort=False).shift(1)
    # `close` has already been expressed in one common share unit by
    # split_safe_prices. Applying today's event factor again would distort the
    # split-day gap and depress ATR for the following ATR_WINDOW observations.
    prev_close_for_tr = prior_close
    true_range = pd.concat(
        [
            high - low,
            (high - prev_close_for_tr).abs(),
            (low - prev_close_for_tr).abs(),
        ],
        axis=1,
    ).max(axis=1, skipna=False)
    atr20 = true_range.groupby(groups, sort=False).transform(
        lambda series: series.shift(1).rolling(ATR_WINDOW, min_periods=ATR_WINDOW).mean()
    )

    duration = pd.Series(0.0, index=index, name="box_duration")
    chosen_width = pd.Series(np.nan, index=index, name="box_width_atr")
    chosen_upper = pd.Series(np.nan, index=index)
    chosen_lower = pd.Series(np.nan, index=index)
    for window in BOX_WINDOWS:
        rolling_high = high.groupby(groups, sort=False).transform(
            lambda series, w=window: series.shift(1).rolling(w, min_periods=w).max()
        )
        rolling_low = low.groupby(groups, sort=False).transform(
            lambda series, w=window: series.shift(1).rolling(w, min_periods=w).min()
        )
        width_atr = (rolling_high - rolling_low) / atr20
        qualifies = width_atr.notna() & np.isfinite(width_atr) & (width_atr < BOX_ATR_LIMIT)
        duration.loc[qualifies] = float(window)
        chosen_width.loc[qualifies] = width_atr.loc[qualifies]
        chosen_upper.loc[qualifies] = rolling_high.loc[qualifies]
        chosen_lower.loc[qualifies] = rolling_low.loc[qualifies]

    box_width = chosen_upper - chosen_lower
    close_position = ((prior_close - chosen_lower) / box_width).where(box_width > 0.0)

    prior_high_250 = high.groupby(groups, sort=False).transform(
        lambda series: series.shift(1).rolling(
            BREAKOUT_WINDOW, min_periods=BREAKOUT_WINDOW
        ).max()
    )
    prior_low_250 = low.groupby(groups, sort=False).transform(
        lambda series: series.shift(1).rolling(
            BREAKOUT_WINDOW, min_periods=BREAKOUT_WINDOW
        ).min()
    )
    high_excess = (close / prior_high_250 - 1.0).clip(lower=0.0)
    low_excess = (prior_low_250 / close - 1.0).clip(lower=0.0)
    high_available = prior_high_250.notna() & close.notna()
    low_available = prior_low_250.notna() & close.notna()

    # State before the breakout day, relative to the preceding 250 observations.
    prebreak_high = high.groupby(groups, sort=False).transform(
        lambda series: series.shift(2).rolling(
            BREAKOUT_WINDOW, min_periods=BREAKOUT_WINDOW
        ).max()
    )
    distance_to_prior_high = prior_close / prebreak_high - 1.0
    prebreak_low = low.groupby(groups, sort=False).transform(
        lambda series: series.shift(2).rolling(
            BREAKOUT_WINDOW, min_periods=BREAKOUT_WINDOW
        ).min()
    )
    distance_to_prior_low = prebreak_low / prior_close - 1.0

    result = pd.DataFrame(
        {
            "box_duration": duration,
            "box_width_atr": chosen_width,
            "close_position": close_position,
            "relative_strength_60": build_relative_strength(inputs),
            "distance_to_prior_high": distance_to_prior_high,
            LOW_DISTANCE_COLUMN: distance_to_prior_low,
            "new_high_excess": high_excess,
            "new_low_excess": low_excess,
            "high_available": high_available,
            "low_available": low_available,
        },
        index=index,
    ).replace([np.inf, -np.inf], np.nan)
    result.attrs["feature_columns"] = list(FEATURE_COLUMNS)
    return result
