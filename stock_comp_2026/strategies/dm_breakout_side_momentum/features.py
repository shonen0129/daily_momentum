"""Causal, split-safe feature builder for side-specific breakout research."""
from pathlib import Path

import numpy as np
import pandas as pd


INPUT_COLUMNS = {
    "raw_return_1day": ["Return"],
    "beta_1day": ["Return"],
    "topix_return_1day": ["Return"],
    "prices_daily_quotes": ["High", "Low", "Close", "AdjustmentFactor"],
}


def load_inputs(directory, split="train"):
    """Load one explicitly selected split; research driver requests Train only."""
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
    """Reset rolling state after a 20+ exchange-date listing gap."""
    dates = index.get_level_values("Date")
    calendar = dates.unique().sort_values()
    ordinal = pd.Series(calendar.get_indexer(dates), index=index)
    code = index.get_level_values("Code")
    starts = ordinal.groupby(code, sort=False).diff().gt(20)
    segment = starts.groupby(code, sort=False).cumsum().astype(int)
    return [code, segment]


def centered_rank(series):
    """Daily cross-sectional centered percentile rank in [-1, 1]."""
    values = series.replace([np.inf, -np.inf], np.nan)
    ranks = values.groupby(level="Date").rank(method="average", pct=True)
    mean_rank = ranks.groupby(level="Date").transform("mean")
    return (2.0 * (ranks - mean_rank)).fillna(0.0)


def smooth(series, alpha=0.25):
    """Causal EWMA along each listing segment."""
    groups = segment_keys(series.index)
    return series.groupby(groups, sort=False).transform(
        lambda values: values.ewm(alpha=alpha, adjust=False).mean()
    )


def build_momentum(inputs):
    """Champion res60s1, kept identical in definition to the active baseline."""
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
        lambda values: values.rolling(60, min_periods=60).sum()
    )
    return centered_rank(trailing).fillna(0.0).rename("res60s1")


def split_safe_prices(inputs):
    """Convert raw OHLC levels to a common within-listing-segment share unit."""
    index = inputs["raw_return_1day"].index
    prices = inputs["prices_daily_quotes"].reindex(index)
    groups = segment_keys(index)
    factor = pd.to_numeric(prices["AdjustmentFactor"], errors="coerce")
    invalid = factor.isna() | ~np.isfinite(factor) | (factor <= 0)
    if invalid.any():
        raise ValueError("AdjustmentFactor must be finite and positive for every row")
    event_factor = factor.where(~np.isclose(factor, 1.0, rtol=1e-12, atol=1e-12), 1.0)
    scale = event_factor.groupby(groups, sort=False).cumprod()
    result = pd.DataFrame(index=index)
    for column in ("High", "Low", "Close"):
        value = pd.to_numeric(prices[column], errors="coerce")
        value = value.where((value > 0) & np.isfinite(value))
        result[column.lower()] = value / scale
    return result


def build_features(inputs, window=250):
    """Build momentum and prior-only 250-observation breakout magnitudes/ranks."""
    index = inputs["raw_return_1day"].index
    prices = split_safe_prices(inputs)
    groups = segment_keys(index)
    prior_high = prices["high"].groupby(groups, sort=False).transform(
        lambda values: values.shift(1).rolling(window, min_periods=window).max()
    )
    prior_low = prices["low"].groupby(groups, sort=False).transform(
        lambda values: values.shift(1).rolling(window, min_periods=window).min()
    )
    high_excess = (prices["close"] / prior_high - 1.0).clip(lower=0.0)
    low_excess = (prior_low / prices["close"] - 1.0).clip(lower=0.0)
    high_excess = high_excess.where(prior_high.notna() & prices["close"].notna())
    low_excess = low_excess.where(prior_low.notna() & prices["close"].notna())

    return pd.DataFrame(
        {
            "res60s1": build_momentum(inputs),
            "new_high_excess": high_excess,
            "new_low_excess": low_excess,
            "new_high_rank": centered_rank(high_excess),
            "new_low_rank": centered_rank(low_excess),
            "high_available": high_excess.notna(),
            "low_available": low_excess.notna(),
        },
        index=index,
    )
