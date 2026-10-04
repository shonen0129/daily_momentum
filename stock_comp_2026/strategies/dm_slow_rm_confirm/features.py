"""Target-free same-date OLS residualization and fixed confirmation score."""
import numpy as np
import pandas as pd
try:
    from .component_factors import features as factors
except ImportError:
    from component_factors import features as factors

INPUT_COLUMNS = factors.INPUT_COLUMNS
load_train = factors.load_train
components = factors.components
centered_rank = factors.momentum.centered_rank


def bins(value, n, keys=None):
    keys = value.index.get_level_values('Date') if keys is None else keys
    p = value.groupby(keys, sort=False).rank(method='average', pct=True)
    return np.ceil(n * p).clip(1, n).astype(float)


def construct(scores):
    scores = scores.sort_index()
    if not scores.index.is_unique or scores.index.names != ['Date', 'Code']:
        raise ValueError('Unique Date/Code index required')
    if not np.isfinite(scores.to_numpy()).all():
        raise ValueError('Immutable components must be finite')
    ranks = factors.factor_ranks(scores)
    out = ranks.copy()
    out['SLOW_RANK'] = centered_rank(scores.SLOW_CONTROL)
    residual = pd.Series(index=scores.index, dtype=float)
    slow_residual = residual.copy()
    records = []
    for date, group in out.groupby('Date', sort=False):
        y = group.MOM60Rank.to_numpy()
        x = np.column_stack([np.ones(len(group)), group.SizeRank, group.IlliquidityRank])
        beta, _, rank, singular = np.linalg.lstsq(x, y, rcond=None)
        residual.loc[group.index] = y - x @ beta
        xs = np.column_stack([np.ones(len(group)), group.SLOW_RANK])
        bs, _, rs, _ = np.linalg.lstsq(xs, y, rcond=None)
        slow_residual.loc[group.index] = y - xs @ bs
        records.append({'Date': date, 'intercept': beta[0], 'size_beta': beta[1],
                        'illiq_beta': beta[2], 'design_rank': float(rank),
                        'condition': singular[0] / singular[-1] if singular[-1] > 0 else np.inf,
                        'slow_intercept': bs[0], 'slow_beta': bs[1], 'slow_rank': float(rs)})
    out['RESIDUAL_MOM_RAW'] = residual
    out['RM'] = centered_rank(residual)
    out['RM_SLOW'] = centered_rank(slow_residual)
    dates = out.index.get_level_values('Date')
    for n in (3, 5):
        out[f'size{n}'] = bins(scores.Size, n)
        out[f'illiq{n}'] = bins(scores.Illiquidity, n)
        out[f'cell{n}'] = (out[f'size{n}'] - 1) * n + out[f'illiq{n}']
        keys = [dates, out[f'cell{n}']]
        p = scores.MOM60.groupby(keys, sort=False).rank(method='average', pct=True)
        out[f'RM_CELL{n}'] = 2 * (p - p.groupby(keys, sort=False).transform('mean'))
    return out, pd.DataFrame(records).set_index('Date')


def score(panel):
    s = panel.SLOW_RANK
    m = centered_rank(panel.RM)
    return (s + s.abs() * m).rename('Return')
