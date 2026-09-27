"""Fixed SIDE_SOURCE_SEPARATION transform shared by research and submission."""

import numpy as np
import pandas as pd

try:
    from . import features
except ImportError:
    import features


HIGH_ALPHA = 0.25
LOW_ALPHA = 0.50
ZERO_NOISE_FLOOR = 1e-12


def _ordered(values):
    if not isinstance(values.index, pd.MultiIndex) or list(values.index.names) != ["Date", "Code"]:
        raise ValueError("SN1 inputs must use a (Date, Code) index")
    if not values.index.is_unique:
        raise ValueError("SN1 inputs must have a unique (Date, Code) index")
    return values.sort_index().astype("float64")


def inverse_base_ewma(base_score, alpha=HIGH_ALPHA):
    """Recover the signed event stream from the fixed upstream EWMA score."""
    if not 0.0 < alpha <= 1.0:
        raise ValueError("EWMA alpha must be in (0, 1]")
    score = _ordered(base_score)
    groups = features.segment_keys(score.index)
    previous = score.groupby(groups, sort=False).shift(1)
    first = score.groupby(groups, sort=False).cumcount().eq(0)
    raw = ((score - (1.0 - alpha) * previous) / alpha).where(~first, score)
    raw = raw.where(raw.abs() >= ZERO_NOISE_FLOOR, 0.0).rename(f"{score.name}_raw")
    rebuilt = ewma_by_listing(raw, alpha)
    error = float((rebuilt - score).abs().max())
    if not np.isfinite(error) or error > 2e-12:
        raise AssertionError(f"EWMA inversion failed: maximum absolute error={error}")
    return raw, error


def ewma_by_listing(values, alpha):
    """Apply an adjust=False EWMA, resetting after a listing gap over 20 days."""
    series = _ordered(values)
    groups = features.segment_keys(series.index)
    return series.groupby(groups, sort=False).transform(
        lambda block: block.ewm(alpha=alpha, adjust=False).mean()
    ).rename(series.name)


def split_raw_sides(raw):
    """Separate the disjoint positive High and negative Low event streams."""
    raw = _ordered(raw)
    high = raw.clip(lower=0.0).rename("high_raw")
    low = raw.clip(upper=0.0).rename("low_raw")
    if (high.ne(0.0) & low.ne(0.0)).any():
        raise AssertionError("High and Low raw streams overlap")
    return high, low


def score_from_raw(raw):
    """Rebuild D and SN1 from an unsmoothed signed event stream."""
    high_raw, low_raw = split_raw_sides(raw)
    high_state = ewma_by_listing(high_raw, HIGH_ALPHA).rename("high_state")
    low_state = ewma_by_listing(low_raw, LOW_ALPHA).rename("low_state")
    d_score = (high_state + low_state).rename("D_LOW_FAST_ONLY")
    side_score = d_score.copy().rename("SIDE_SOURCE_SEPARATION")
    low_active = low_state.lt(0.0)
    side_score.loc[low_active] = low_state.loc[low_active]
    high_only = low_state.eq(0.0) & high_state.gt(0.0)
    side_score.loc[high_only] = high_state.loc[high_only]
    return {
        "raw": _ordered(raw),
        "high_raw": high_raw,
        "low_raw": low_raw,
        "high_state": high_state,
        "low_state": low_state,
        "D_LOW_FAST_ONLY": d_score,
        "SIDE_SOURCE_SEPARATION": side_score,
    }


def rebuild_from_base_score(base_score):
    """Replay the research route: invert saved BOX EWMA, then apply SN1 states."""
    raw, inversion_error = inverse_base_ewma(base_score, HIGH_ALPHA)
    result = score_from_raw(raw)
    result["inversion_max_abs_error"] = inversion_error
    return result
