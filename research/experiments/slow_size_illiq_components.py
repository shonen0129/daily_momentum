"""Fixed, target-free diagnostic transforms. No inference/submission API."""
import numpy as np
import pandas as pd
from stock_comp_2026.strategies.dm_slow_multifactor import features as slow

BOOKS = ['SIZE_ONLY', 'ILLIQ_ONLY', 'SLOW_CONTROL']
SIZE_NAMES = {1: 'Large', 2: 'Mid', 3: 'Small'}
ILLIQ_NAMES = {1: 'Liquid', 2: 'Mid', 3: 'Illiquid'}
GROUPS = ['BOTH_LONG', 'SIZE_ONLY_LONG', 'ILLIQ_ONLY_LONG', 'BOTH_SHORT',
          'SIZE_ONLY_SHORT', 'ILLIQ_ONLY_SHORT', 'SIGNAL_DISAGREEMENT', 'OTHER']


def bins(values, count=3, keys=None):
    """Average ties remain together; missing values retain missing bins."""
    if keys is None:
        keys = values.index.get_level_values('Date')
    rank = values.groupby(keys, sort=False).rank(method='average', pct=True)
    return np.ceil(count * rank).clip(1, count).astype('float64')


def centered_rank(values):
    p = values.groupby('Date', sort=False).rank(method='average', pct=True)
    return 2 * (p - p.groupby('Date', sort=False).transform('mean'))


def residualize(y, x):
    """Intercept OLS per signal date, analytic covariance/variance solution."""
    if not y.index.equals(x.index):
        raise ValueError('OLS index mismatch')
    if not np.isfinite(y.to_numpy()).all() or not np.isfinite(x.to_numpy()).all():
        raise ValueError('Original imputed components must be finite')
    dates = y.index.get_level_values('Date')
    ym, xm = y.groupby(dates, sort=False).transform('mean'), x.groupby(dates, sort=False).transform('mean')
    yc, xc = y - ym, x - xm
    xx = (xc * xc).groupby(dates, sort=False).sum()
    xy = (xc * yc).groupby(dates, sort=False).sum()
    slope = (xy / xx.where(xx > 0)).fillna(0.)
    b = slope.reindex(dates).to_numpy()
    a = ym - b * xm
    residual = y - (a + b * x)
    coeff = pd.DataFrame({'intercept': a.groupby(dates, sort=False).first(),
                          'slope': slope, 'regressor_ss': xx,
                          'n': y.groupby(dates, sort=False).size().astype('float64')})
    coeff.index.name = 'Date'
    return residual, coeff


def decompose(features):
    f = features.sort_index()
    if not f.index.is_unique or f.index.names != ['Date', 'Code']:
        raise ValueError('Expected unique Date/Code')
    out = pd.DataFrame({'SIZE_ONLY': f.z_size, 'ILLIQ_ONLY': f.z_amihud,
                        'SLOW_CONTROL': f.size_liquidity}, index=f.index)
    out['size_bin'] = bins(out.SIZE_ONLY)
    out['illiq_bin'] = bins(out.ILLIQ_ONLY)
    out['joint_cell'] = (out.size_bin - 1) * 3 + out.illiq_bin
    dates = out.index.get_level_values('Date')
    out['illiq_within_size_bin'] = bins(out.ILLIQ_ONLY, keys=[dates, out.size_bin])
    out['size_within_illiq_bin'] = bins(out.SIZE_ONLY, keys=[dates, out.illiq_bin])
    coefficients = []
    for name, y, x in [('RESIDUAL_SIZE', out.SIZE_ONLY, out.ILLIQ_ONLY),
                       ('RESIDUAL_ILLIQ', out.ILLIQ_ONLY, out.SIZE_ONLY)]:
        out[name], c = residualize(y, x)
        coefficients.append(c.add_prefix(name + '_'))
        out[name + '_q'] = bins(out[name], 5)
    out['SizeRank'], out['IlliquidityRank'] = centered_rank(out.SIZE_ONLY), centered_rank(out.ILLIQ_ONLY)
    out['COMMON'] = (out.SizeRank + out.IlliquidityRank) / 2
    out['DISAGREEMENT'] = (out.SizeRank - out.IlliquidityRank) / 2
    out['DISAGREEMENT_q'] = bins(out.DISAGREEMENT, 5)
    out['DISAGREEMENT_tercile'] = bins(out.DISAGREEMENT)
    return out, pd.concat(coefficients, axis=1)


def agreement_groups(size_w, illiq_w):
    if not size_w.index.equals(illiq_w.index):
        raise ValueError('Membership index mismatch')
    a, b = np.sign(size_w), np.sign(illiq_w)
    masks = [(a.eq(1) & b.eq(1)), (a.eq(1) & b.eq(0)), (a.eq(0) & b.eq(1)),
             (a.eq(-1) & b.eq(-1)), (a.eq(-1) & b.eq(0)), (a.eq(0) & b.eq(-1)),
             (a * b).eq(-1), (a.eq(0) & b.eq(0))]
    assert np.column_stack([m.to_numpy() for m in masks]).sum(axis=1).min() == 1
    assert np.column_stack([m.to_numpy() for m in masks]).sum(axis=1).max() == 1
    return pd.Series(np.select(masks, GROUPS, default='INVALID'), index=a.index, name='group')
