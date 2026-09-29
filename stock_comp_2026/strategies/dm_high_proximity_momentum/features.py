"""Causal High Proximity Momentum features.

Strictly Train-only / Point-in-time calculation.
No future leakage, no adjustment prices, no bfill, no center rolling.
"""
from pathlib import Path
import numpy as np
import pandas as pd

INPUT_COLUMNS = {
    'raw_return_1day': ['Return'],
    'beta_1day': ['Return'],
    'topix_return_1day': ['Return'],
    'prices_daily_quotes': ['High', 'Close', 'AdjustmentFactor'],
}


def load_inputs(directory, split='train'):
    """Load required inputs for feature generation. Denies valid split in research."""
    if split not in ('train', 'valid'):
        raise ValueError('Unknown split')
    result = {}
    for name, columns in INPUT_COLUMNS.items():
        path = Path(directory) / f'{name}_{split}.parquet'
        frame = pd.read_parquet(path, columns=columns)
        if not frame.index.is_unique:
            raise ValueError(f'Duplicate index in {name}')
        result[name] = frame.sort_index()
    return result


def segment_keys(index):
    """Reset state after >20 absent exchange dates (code reuse/relisting)."""
    dates = index.get_level_values('Date')
    calendar = dates.unique().sort_values()
    ordinal = pd.Series(calendar.get_indexer(dates), index=index)
    code = index.get_level_values('Code')
    starts = ordinal.groupby(code, sort=False).diff().gt(20)
    segment = starts.groupby(code, sort=False).cumsum().astype(int)
    return [code, segment]


def centered_rank(s):
    """Map daily cross-sectional distribution to centered rank in [-1, 1]."""
    s = s.replace([np.inf, -np.inf], np.nan)
    rank = s.groupby(level='Date').rank(method='average', pct=True)
    return (2.0 * (rank - rank.groupby(level='Date').transform('mean'))).fillna(0.0)


def smooth(s, alpha=0.25):
    """Causal exponential smoothing along listing segments."""
    groups = segment_keys(s.index)
    return s.groupby(groups, sort=False).transform(
        lambda v: v.ewm(alpha=alpha, adjust=False).mean()
    )


def build_momentum(inputs):
    """Champion res60s1 residual momentum feature."""
    r = inputs['raw_return_1day']['Return'].sort_index().replace([np.inf, -np.inf], np.nan)
    idx = r.index
    dates = idx.get_level_values('Date')
    beta = inputs['beta_1day']['Return'].reindex(idx)
    market = pd.Series(inputs['topix_return_1day']['Return'].reindex(dates).to_numpy(), index=idx)
    residual = (r - beta * market).replace([np.inf, -np.inf], np.nan)
    groups = segment_keys(idx)
    lagged = residual.groupby(groups, sort=False).shift(1)
    value = lagged.groupby(groups, sort=False).transform(
        lambda v: v.rolling(60, min_periods=60).sum()
    )
    return centered_rank(value).rename('res60s1')


def build_high_proximity_ratio(inputs, window=60, min_periods=None, split_safe=False):
    """Return Close / rolling max High; optionally carry observed split factors forward.

    AdjustmentFactor is an event multiplier in the supplied panel: non-1 values
    apply to earlier raw prices and reset to 1 on later rows. Its cumulative
    product defines a causal common share unit within each listing segment.
    This path uses raw High/Close plus observed event factors; it does not read
    retrospectively adjusted OHLC levels.
    """
    if min_periods is None:
        min_periods = window
    idx = inputs['raw_return_1day'].index
    p = inputs['prices_daily_quotes'].reindex(idx)
    high = p['High'].where((p['High'] > 0) & np.isfinite(p['High']))
    close = p['Close'].where((p['Close'] > 0) & np.isfinite(p['Close']))
    groups = segment_keys(idx)

    if split_safe:
        if 'AdjustmentFactor' not in p.columns:
            raise ValueError('AdjustmentFactor is required for split-safe proximity')
        factor = pd.to_numeric(p['AdjustmentFactor'], errors='coerce')
        invalid_factor = factor.isna() | ~np.isfinite(factor) | (factor <= 0)
        if invalid_factor.any():
            raise ValueError('AdjustmentFactor must be finite and positive for every row')
        event_factor = factor.where(~np.isclose(factor, 1.0, rtol=1e-12, atol=1e-12), 1.0)
        cumulative_factor = event_factor.groupby(groups, sort=False).cumprod()
        high = high / cumulative_factor
        close = close / cumulative_factor

    # Rolling maximum of High over the past `window` days (including current day t)
    roll_max_high = high.groupby(groups, sort=False).transform(
        lambda v: v.rolling(window, min_periods=min_periods).max()
    )
    # Proximity ratio: Close_t / max(High)
    ratio = (close / roll_max_high).where(roll_max_high.notna() & (roll_max_high > 0))
    return ratio


def build_high_proximity(inputs, window=60, min_periods=None):
    """Compute centered rank of raw Close / rolling max raw High."""
    ratio = build_high_proximity_ratio(inputs, window=window, min_periods=min_periods)
    return centered_rank(ratio)


def build_high_proximity_split_safe(inputs, window=250, min_periods=250):
    """Compute centered rank of split-safe 52-week proximity using full history."""
    ratio = build_high_proximity_ratio(
        inputs, window=window, min_periods=min_periods, split_safe=True
    )
    return centered_rank(ratio)


def build_features(inputs):
    """Build all candidate features for dm_high_proximity_momentum."""
    idx = inputs['raw_return_1day'].index
    df = pd.DataFrame(index=idx)
    df['res60s1'] = build_momentum(inputs)
    df['prox20'] = build_high_proximity(inputs, window=20, min_periods=20)
    df['prox60'] = build_high_proximity(inputs, window=60, min_periods=60)
    df['prox250'] = build_high_proximity(inputs, window=250, min_periods=120)
    df['prox250_split_safe'] = build_high_proximity_split_safe(
        inputs, window=250, min_periods=250
    )
    return df
