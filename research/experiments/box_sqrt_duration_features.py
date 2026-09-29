"""Single pre-registered sqrt(L)-normalized box-duration correction.

Only prior-price box state is changed. Existing feature definitions and the
official strategy implementation remain untouched.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_variable_box_breakout import features


CR_LIMIT = 3.0
WINDOWS = tuple(range(5, 121, 5))


def build_box_state(inputs):
    """Return duration, ATR-scaled width, and prior-close position through t-1.

    For each L in {5, 10, ..., 120}, CR is
    `(prior_high_max - prior_low_min) / (ATR20_prior * sqrt(L))`.
    Duration is the largest qualifying L for CR < 3.0.
    """
    index = inputs["raw_return_1day"].index
    prices = features.split_safe_prices(inputs).reindex(index)
    groups = features.segment_keys(index)
    high, low, close = prices["high"], prices["low"], prices["close"]
    prev_close = close.groupby(groups, sort=False).shift(1)
    prev_close_for_tr = prev_close / prices["event_factor"]
    true_range = pd.concat([
        high - low,
        (high - prev_close_for_tr).abs(),
        (low - prev_close_for_tr).abs(),
    ], axis=1).max(axis=1, skipna=False)
    atr20 = true_range.groupby(groups, sort=False).transform(
        lambda s: s.shift(1).rolling(20, min_periods=20).mean()
    )

    duration = pd.Series(0.0, index=index, name="box_duration")
    width_atr = pd.Series(np.nan, index=index, name="box_width_atr")
    upper = pd.Series(np.nan, index=index, name="box_upper")
    lower = pd.Series(np.nan, index=index, name="box_lower")
    compression = pd.Series(np.nan, index=index, name="box_cr_sqrt_l")
    for window in WINDOWS:
        rolling_high = high.groupby(groups, sort=False).transform(
            lambda s, w=window: s.shift(1).rolling(w, min_periods=w).max()
        )
        rolling_low = low.groupby(groups, sort=False).transform(
            lambda s, w=window: s.shift(1).rolling(w, min_periods=w).min()
        )
        raw_width = rolling_high - rolling_low
        normalized_width = raw_width / atr20
        cr = normalized_width / np.sqrt(float(window))
        qualifies = cr.notna() & np.isfinite(cr) & (cr < CR_LIMIT)
        duration.loc[qualifies] = float(window)
        width_atr.loc[qualifies] = normalized_width.loc[qualifies]
        upper.loc[qualifies] = rolling_high.loc[qualifies]
        lower.loc[qualifies] = rolling_low.loc[qualifies]
        compression.loc[qualifies] = cr.loc[qualifies]

    box_range = upper - lower
    close_position = ((prev_close - lower) / box_range).where(box_range > 0.0)
    return pd.DataFrame({
        "box_duration": duration,
        "box_width_atr": width_atr,
        "close_position": close_position,
        "box_cr_sqrt_l": compression,
    }, index=index).replace([np.inf, -np.inf], np.nan)
