"""Causal competition inputs and core momentum primitives."""
from pathlib import Path
import numpy as np
import pandas as pd

INPUT_COLUMNS = {
    'raw_return_1day': ['Return'],
    'beta_1day': ['Return'],
    'topix_return_1day': ['Return'],
    'listed_info': ['Sector17Code', 'ScaleCategory'],
}


def load_inputs(directory, split='train', names=None):
    if split not in ('train', 'valid'):
        raise ValueError('Unknown feature split')
    result = {}
    for name, columns in INPUT_COLUMNS.items():
        if names is not None and name not in names:
            continue
        frame = pd.read_parquet(Path(directory) / f'{name}_{split}.parquet', columns=columns)
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
    s = s.replace([np.inf, -np.inf], np.nan)
    rank = s.groupby(level='Date').rank(method='average', pct=True)
    return (2 * (rank - rank.groupby(level='Date').transform('mean'))).fillna(0.)


def smooth(s, alpha):
    return s.groupby(segment_keys(s.index), sort=False).transform(
        lambda v: v.ewm(alpha=alpha, adjust=False).mean())


def build_momentum(inputs):
    """Selected res60s1 only, exactly equivalent to historical build_features()['res60s1']."""
    r = inputs['raw_return_1day']['Return'].sort_index().replace([np.inf, -np.inf], np.nan)
    idx = r.index
    dates = idx.get_level_values('Date')
    beta = inputs['beta_1day']['Return'].reindex(idx)
    market = pd.Series(inputs['topix_return_1day']['Return'].reindex(dates).to_numpy(), index=idx)
    residual = (r - beta * market).replace([np.inf, -np.inf], np.nan)
    groups = segment_keys(idx)
    lagged = residual.groupby(groups, sort=False).shift(1)
    value = lagged.groupby(groups, sort=False).transform(
        lambda v: v.rolling(60, min_periods=60).sum())
    return centered_rank(value).rename('res60s1')


def build_core_features(inputs):
    """Compute base residual returns and M60 / M5 windows."""
    r = inputs['raw_return_1day']['Return'].sort_index().replace([np.inf, -np.inf], np.nan)
    idx = r.index
    dates = idx.get_level_values('Date')
    groups = segment_keys(idx)
    beta = inputs['beta_1day']['Return'].reindex(idx)
    market = pd.Series(inputs['topix_return_1day']['Return'].reindex(dates).to_numpy(), index=idx)
    residual = (r - beta * market).replace([np.inf, -np.inf], np.nan)

    def lag1(s):
        return s.groupby(groups, sort=False).shift(1)

    def roll(s, window, method='sum'):
        return s.groupby(groups, sort=False).transform(
            lambda v: getattr(v.rolling(window, min_periods=window), method)())

    lagres = lag1(residual)
    m60_sum = roll(lagres, 60, 'sum')
    m5_sum = roll(lagres, 5, 'sum')

    f = pd.DataFrame(index=idx)
    f['res60s1'] = centered_rank(m60_sum)
    f['res5s1_sum'] = m5_sum
    f['momentum_available'] = m60_sum.notna().astype(float)
    return f
