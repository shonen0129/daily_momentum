"""Exact frozen MOM60 functions; only the unused general loaders are omitted."""
import numpy as np
import pandas as pd


def build_momentum(inputs):
    """Selected res60s1 only, exactly equivalent to build_features()['res60s1']."""
    r = inputs['raw_return_1day']['Return'].sort_index().replace([np.inf, -np.inf], np.nan)
    idx = r.index
    dates = idx.get_level_values('Date')
    beta = inputs['beta_1day']['Return'].reindex(idx)
    market = pd.Series(inputs['topix_return_1day']['Return'].reindex(dates).to_numpy(), index=idx)
    residual = (r-beta*market).replace([np.inf, -np.inf], np.nan)
    groups = segment_keys(idx)
    lagged = residual.groupby(groups, sort=False).shift(1)
    value = lagged.groupby(groups, sort=False).transform(
        lambda v: v.rolling(60, min_periods=60).sum())
    return centered_rank(value).rename('res60s1')


def centered_rank(s):
    s = s.replace([np.inf, -np.inf], np.nan)
    rank = s.groupby(level='Date').rank(method='average', pct=True)
    return (2 * (rank - rank.groupby(level='Date').transform('mean'))).fillna(0.)


def segment_keys(index):
    """Reset state after >20 absent exchange dates (code reuse/relisting)."""
    dates = index.get_level_values('Date')
    calendar = dates.unique().sort_values()
    ordinal = pd.Series(calendar.get_indexer(dates), index=index)
    code = index.get_level_values('Code')
    starts = ordinal.groupby(code, sort=False).diff().gt(20)
    segment = starts.groupby(code, sort=False).cumsum().astype(int)
    return [code, segment]


def smooth(s, alpha):
    return s.groupby(segment_keys(s.index), sort=False).transform(
        lambda v: v.ewm(alpha=alpha, adjust=False).mean())
