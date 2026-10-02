"""Causal event-driven box lifecycle for one security's daily OHLC history."""
from __future__ import annotations

import numpy as np
import pandas as pd


SEARCH, BOX, EXTEND, ANCHOR = "SEARCH", "BOX", "EXTEND", "ANCHOR"
OUTPUT_COLUMNS = (
    "state", "box_id", "box_high", "box_low", "confirmed_at",
    "new_box", "bo_signal", "bo_strength", "bo_exit", "mr_signal", "close_position",
)


def run_state_machine(
    bars: pd.DataFrame,
    *,
    seed_window: int = 20,
    box_width_atr_min: float = 0.5,
    box_width_atr_max: float = 3.0,
    k_sl: float = 0.5,
    k_bo: float = 1.0,
    k_fail: float = 0.5,
    reversal_atr: float = 1.0,
    formation_timeout_sessions: int = 40,
    mr_entry_x: float = 0.8,
) -> pd.DataFrame:
    """Build as-of states from bars with a prior-only ``atr_prior`` column.

    The initial box is seeded from the preceding ``seed_window`` bars. After a
    breakout, the old boundaries are discarded and a new pair is confirmed by
    an ATR reversal from the breakout extreme and a second ATR reversal from
    the opposite anchor. No output row uses a future bar.
    """
    if not isinstance(bars, pd.DataFrame) or not bars.index.is_monotonic_increasing:
        raise ValueError("bars must be a chronologically sorted DataFrame")
    if not bars.index.is_unique:
        raise ValueError("bars index must be unique")
    required = {"Open", "High", "Low", "Close", "atr_prior"}
    if not required.issubset(bars.columns):
        raise ValueError(f"bars missing columns: {sorted(required - set(bars.columns))}")
    if seed_window < 2 or not (0 < box_width_atr_min < box_width_atr_max):
        raise ValueError("invalid seed window or box-width bounds")
    if not (0 <= k_sl < k_bo) or k_fail <= 0 or reversal_atr <= 0:
        raise ValueError("breakout thresholds must be ordered and positive")
    if formation_timeout_sessions < 1 or not 0 < mr_entry_x < 1:
        raise ValueError("invalid formation timeout or MR edge threshold")

    n = len(bars)
    states = np.full(n, SEARCH, dtype=object)
    box_ids = np.full(n, -1, dtype=np.int64)
    box_highs = np.full(n, np.nan)
    box_lows = np.full(n, np.nan)
    confirmed = np.full(n, pd.NaT, dtype=object)
    new_box = np.zeros(n, dtype=bool)
    bo_signal = np.zeros(n, dtype=np.int8)
    bo_strength = np.zeros(n, dtype=float)
    bo_exit = np.zeros(n, dtype=bool)
    mr_signal = np.zeros(n, dtype=np.int8)
    close_position = np.full(n, np.nan)

    high = pd.to_numeric(bars["High"], errors="coerce").to_numpy(dtype=float)
    low = pd.to_numeric(bars["Low"], errors="coerce").to_numpy(dtype=float)
    close = pd.to_numeric(bars["Close"], errors="coerce").to_numpy(dtype=float)
    atr = pd.to_numeric(bars["atr_prior"], errors="coerce").to_numpy(dtype=float)
    if not (np.isfinite(high).all() and np.isfinite(low).all() and np.isfinite(close).all()):
        raise ValueError("OHLC values must be finite")
    if (low <= 0).any() or (high < low).any() or (close < low).any() or (close > high).any():
        raise ValueError("invalid OHLC bounds")

    state = SEARCH
    upper = lower = np.nan
    box_id = -1
    confirmation_date = pd.NaT
    date_values = (bars.index.get_level_values("Date")
                   if isinstance(bars.index, pd.MultiIndex) and "Date" in bars.index.names
                   else bars.index)
    direction = 0
    extreme = np.nan
    anchor = np.nan
    life = 0
    mr_entered_long = False
    mr_entered_short = False

    for i in range(n):
        a = atr[i]
        if state == SEARCH:
            if i >= seed_window and np.isfinite(a) and a > 0:
                start = i - seed_window
                candidate_high = float(np.max(high[start:i]))
                candidate_low = float(np.min(low[start:i]))
                width_atr = (candidate_high - candidate_low) / a
                if (box_width_atr_min <= width_atr <= box_width_atr_max
                        and candidate_low <= close[i] <= candidate_high):
                    upper, lower = candidate_high, candidate_low
                    box_id += 1
                    confirmation_date = date_values[i]
                    state = BOX
                    new_box[i] = True
                    mr_entered_long = False
                    mr_entered_short = False
        elif state == BOX:
            width = upper - lower
            if width <= 0:
                state, upper, lower = SEARCH, np.nan, np.nan
            elif np.isfinite(a) and a > 0 and close[i] > upper + k_bo * a:
                direction = 1
                bo_signal[i] = 1
                bo_strength[i] = (close[i] - upper) / a
                extreme = max(upper, high[i])
                life = 0
                state = EXTEND
            elif np.isfinite(a) and a > 0 and close[i] < lower - k_bo * a:
                direction = -1
                bo_signal[i] = -1
                bo_strength[i] = (lower - close[i]) / a
                extreme = min(lower, low[i])
                life = 0
                state = EXTEND
            else:
                x = 2.0 * (close[i] - lower) / width - 1.0
                close_position[i] = x
                if x <= -mr_entry_x and not mr_entered_long:
                    mr_signal[i] = 1
                    mr_entered_long = True
                elif x >= mr_entry_x and not mr_entered_short:
                    mr_signal[i] = -1
                    mr_entered_short = True
        elif state == EXTEND:
            life += 1
            if life > formation_timeout_sessions:
                state, upper, lower = SEARCH, np.nan, np.nan
                bo_exit[i] = True
                direction = 0
            elif np.isfinite(a) and a > 0:
                if direction > 0 and close[i] < upper - k_fail * a:
                    state, upper, lower = SEARCH, np.nan, np.nan
                    bo_exit[i] = True
                    direction = 0
                elif direction < 0 and close[i] > lower + k_fail * a:
                    state, upper, lower = SEARCH, np.nan, np.nan
                    bo_exit[i] = True
                    direction = 0
                else:
                    extreme = max(extreme, high[i]) if direction > 0 else min(extreme, low[i])
                    reversal = (extreme - close[i]) if direction > 0 else (close[i] - extreme)
                    if reversal >= reversal_atr * a:
                        upper = extreme if direction > 0 else np.nan
                        lower = extreme if direction < 0 else np.nan
                        anchor = low[i] if direction > 0 else high[i]
                        state = ANCHOR
                        life = 0
        elif state == ANCHOR:
            life += 1
            if life > formation_timeout_sessions:
                state, upper, lower = SEARCH, np.nan, np.nan
                bo_exit[i] = True
                direction = 0
            elif np.isfinite(a) and a > 0:
                anchor = min(anchor, low[i]) if direction > 0 else max(anchor, high[i])
                reversal = (close[i] - anchor) if direction > 0 else (anchor - close[i])
                if reversal >= reversal_atr * a:
                    candidate_high = float(upper if direction > 0 else anchor)
                    candidate_low = float(anchor if direction > 0 else lower)
                    width_atr = (candidate_high - candidate_low) / a
                    if (candidate_high > candidate_low
                            and box_width_atr_min <= width_atr <= box_width_atr_max):
                        upper, lower = candidate_high, candidate_low
                        box_id += 1
                        confirmation_date = date_values[i]
                        state = BOX
                        new_box[i] = True
                        bo_exit[i] = True
                        direction = 0
                        mr_entered_long = False
                        mr_entered_short = False
                    else:
                        state, upper, lower = SEARCH, np.nan, np.nan
                        bo_exit[i] = True
                        direction = 0

        if state == BOX and new_box[i]:
            width = upper - lower
            x = 2.0 * (close[i] - lower) / width - 1.0
            close_position[i] = x
            if x <= -mr_entry_x:
                mr_signal[i] = 1
                mr_entered_long = True
            elif x >= mr_entry_x:
                mr_signal[i] = -1
                mr_entered_short = True

        states[i] = state
        if state == BOX:
            box_ids[i] = box_id
            box_highs[i] = upper
            box_lows[i] = lower
            confirmed[i] = confirmation_date

    result = pd.DataFrame({
        "state": states,
        "box_id": box_ids,
        "box_high": box_highs,
        "box_low": box_lows,
        "confirmed_at": pd.to_datetime(confirmed),
        "new_box": new_box,
        "bo_signal": bo_signal,
        "bo_strength": bo_strength,
        "bo_exit": bo_exit,
        "mr_signal": mr_signal,
        "close_position": close_position,
    }, index=bars.index)
    result.attrs["feature_columns"] = list(OUTPUT_COLUMNS)
    return result
