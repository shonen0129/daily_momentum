"""NH_REV_001: only new-high/new-low baseline state and fixed RS60."""
from pathlib import Path
import numpy as np
import pandas as pd
INPUT_COLUMNS = {
    "raw_return_1day": ["Return"], "beta_1day": ["Return"],
    "topix_return_1day": ["Return"],
    "prices_daily_quotes": ["High", "Low", "Close", "AdjustmentFactor"],
}

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
    index = inputs["raw_return_1day"].index
    px = split_safe_prices(inputs)
    groups = segment_keys(index)
    high = px.high.groupby(groups, sort=False).transform(
        lambda s: s.shift(1).rolling(250, min_periods=250).max())
    low = px.low.groupby(groups, sort=False).transform(
        lambda s: s.shift(1).rolling(250, min_periods=250).min())
    return pd.DataFrame({
        "relative_strength_60": build_relative_strength(inputs),
        "new_high_excess": (px.close / high - 1).clip(lower=0),
        "new_low_excess": (low / px.close - 1).clip(lower=0),
        "high_available": high.notna() & px.close.notna(),
        "low_available": low.notna() & px.close.notna(),
    }, index=index).replace([np.inf, -np.inf], np.nan)


def active_rank(values):
    return values.groupby(level="Date").rank(method="average", pct=True)


def signal_stages(x):
    high = x.high_available & x.new_high_excess.gt(0)
    low = x.low_available & x.new_low_excess.gt(0)
    high_score = (0.5 + 0.5 * active_rank(x.new_high_excess.where(high))).where(high, 0.)
    low_score = (0.5 + 0.5 * active_rank(x.new_low_excess.where(low))).where(low, 0.)
    base = high_score - low_score
    score = -x.relative_strength_60
    rank = active_rank(score.where(high))
    # Fixed 100% event replacement, same map as the previous Phase 1.
    combined = base.where(~high, 0.5 + 0.5 * rank)
    result = pd.DataFrame({"event": high, "relative_strength_60": x.relative_strength_60,
        "score": score.where(high), "event_rank": rank, "b00_raw": base,
        "combined_score": combined, "b00_ewma": smooth_by_listing(base, alpha=0.25),
        "ewma_score": smooth_by_listing(combined, alpha=0.25)}, index=x.index)
    if not np.isfinite(result[["b00_ewma", "ewma_score"]]).all().all():
        raise ValueError("Nonfinite prediction")
    return result
