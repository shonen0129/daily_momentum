"""Causal target-free descriptors for the fixed RM research bundle."""
import numpy as np
import pandas as pd
from research import evaluation
from stock_comp_2026.strategies.dm_slow_rm_confirm import features as f

TRANSITIONS = {1: 'newly_entered_Long', 2: 'continuing_Long', 3: 'exiting_Long',
               4: 'newly_entered_Short', 5: 'continuing_Short', 6: 'exiting_Short', 7: 'neutral'}


def describe(scores, market):
    p, coefficients = f.construct(scores)
    w, q = evaluation.weights(scores.SLOW_CONTROL)
    p['slow_w'], p['slow_q'] = w, q + 1
    pct = scores.SLOW_CONTROL.groupby('Date').rank(method='average', pct=True)
    p['slow_pct'] = pct
    for boundary in (.2, .4, .6, .8):
        p[f'distance_{int(100*boundary)}'] = (pct - boundary).abs()
    p['boundary_distance'] = p[[f'distance_{k}' for k in (20, 40, 60, 80)]].min(axis=1)
    wide = np.sign(w).unstack('Code').fillna(0.)
    prior = wide.shift(1).fillna(0.).stack(future_stack=True).reindex(p.index)
    side = np.sign(w)
    p['previous_side'] = prior
    p['side_flip'] = (side * prior < 0).astype(float)
    p['exit_long_flag'] = ((prior > 0) & (side <= 0)).astype(float)
    p['exit_short_flag'] = ((prior < 0) & (side >= 0)).astype(float)
    conditions = [(side > 0) & (prior <= 0), (side > 0) & (prior > 0),
                  (side == 0) & (prior > 0), (side < 0) & (prior >= 0),
                  (side < 0) & (prior < 0), (side == 0) & (prior < 0)]
    p['transition'] = np.select(conditions, [1, 2, 3, 4, 5, 6], default=7).astype(float)
    for name in ('RM', 'SLOW_RANK'):
        wide = p[name].unstack('Code')
        for lag in (1, 5, 10, 20):
            # Diagnostic lag on the exchange-date grid, never future reference.
            lagged = wide.shift(lag).stack(future_stack=True).reindex(p.index)
            p[f'{name}_lag{lag}'] = lagged
        p[f'{name}_abs_change'] = (p[name] - p[f'{name}_lag1']).abs()
    p['boundary_crossing'] = (side != prior).astype(float)
    previous_q = q.unstack('Code').shift(1).stack(future_stack=True).reindex(p.index)
    p['quintile_crossing'] = (q != previous_q).where(previous_q.notna()).astype(float)
    r = market.Return.sort_index().replace([np.inf, -np.inf], np.nan)
    vol = r.rolling(60, min_periods=40).std(ddof=1)
    threshold = vol.expanding(min_periods=252).median().shift(1)
    trend = r.rolling(60, min_periods=40).sum()
    state = pd.DataFrame({'market_vol60': vol, 'market_vol_past_median': threshold,
                          'market_trend60': trend,
                          'market_high_vol': (vol > threshold).where(threshold.notna()).astype(float),
                          'market_positive_trend': (trend > 0).where(trend.notna()).astype(float)})
    for col in state:
        p[col] = state[col].reindex(p.index.get_level_values('Date')).to_numpy()
    return p, coefficients, state
