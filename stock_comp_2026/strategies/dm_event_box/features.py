"""Split-safe OHLC preparation and point-in-time event-box features."""
from pathlib import Path

import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_variable_box_breakout.features import segment_keys
from . import core


INPUT_COLUMNS = {
    "raw_return_1day": ["Return"],
    "prices_daily_quotes": ["Open", "High", "Low", "Close", "AdjustmentFactor"],
}
ATR_WINDOW = 20


def load_inputs(directory, split="train"):
    if split not in ("train", "valid"):
        raise ValueError(f"Unknown split: {split}")
    result = {}
    for name, columns in INPUT_COLUMNS.items():
        frame = pd.read_parquet(Path(directory) / f"{name}_{split}.parquet", columns=columns)
        if not frame.index.is_unique:
            raise ValueError(f"Duplicate index in {name}")
        result[name] = frame.sort_index()
    return result


def split_safe_ohlc(inputs):
    index = inputs["raw_return_1day"].index
    quotes = inputs["prices_daily_quotes"].reindex(index)
    groups = segment_keys(index)
    factor = pd.to_numeric(quotes["AdjustmentFactor"], errors="coerce")
    if factor.isna().any() or (~np.isfinite(factor)).any() or factor.le(0).any():
        raise ValueError("AdjustmentFactor must be finite and positive")
    event_factor = factor.where(~np.isclose(factor, 1.0, rtol=1e-12, atol=1e-12), 1.0)
    scale = event_factor.groupby(groups, sort=False).cumprod()
    out = pd.DataFrame(index=index)
    for column in ("Open", "High", "Low", "Close"):
        value = pd.to_numeric(quotes[column], errors="coerce")
        value = value.where(value.gt(0) & np.isfinite(value))
        out[column] = value / scale
    return out.replace([np.inf, -np.inf], np.nan)


def _one_segment(bars):
    close = bars["Close"]
    prior_close = close.shift(1)
    true_range = pd.concat([
        bars["High"] - bars["Low"],
        (bars["High"] - prior_close).abs(),
        (bars["Low"] - prior_close).abs(),
    ], axis=1).max(axis=1, skipna=False)
    bars = bars.copy()
    # ATR used at t includes observations only through t-1.
    bars["atr_prior"] = true_range.shift(1).rolling(ATR_WINDOW, min_periods=ATR_WINDOW).mean()
    return core.run_state_machine(bars)


def _with_missing_bar_resets(segment):
    values = segment[["Open", "High", "Low", "Close"]].to_numpy(dtype=float)
    valid = np.isfinite(values).all(axis=1) & (values > 0.0).all(axis=1)
    valid &= (values[:, 2] <= values[:, 1]) & (values[:, 3] >= values[:, 2]) & (values[:, 3] <= values[:, 1])
    boundaries = np.flatnonzero(np.r_[True, valid[1:] != valid[:-1], True])
    pieces = []
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        if valid[left]:
            pieces.append(_one_segment(segment.iloc[left:right]))
    if pieces:
        state = pd.concat(pieces).sort_index().reindex(segment.index)
    else:
        state = pd.DataFrame(index=segment.index, columns=core.OUTPUT_COLUMNS)
    state["state"] = state["state"].fillna(core.SEARCH)
    state["box_id"] = state["box_id"].fillna(-1).astype("int64")
    state["new_box"] = state["new_box"].fillna(False).astype(bool)
    state["bo_signal"] = state["bo_signal"].fillna(0).astype("int8")
    state["bo_strength"] = state["bo_strength"].fillna(0.0).astype(float)
    state["bo_exit"] = state["bo_exit"].fillna(False).astype(bool)
    state["mr_signal"] = state["mr_signal"].fillna(0).astype("int8")
    return state.loc[:, list(core.OUTPUT_COLUMNS)]


def build_features(inputs):
    index = inputs["raw_return_1day"].index
    ohlc = split_safe_ohlc(inputs)
    frames = []
    codes = index.get_level_values("Code")
    for code in codes.unique():
        code_index = index[codes == code]
        prices = ohlc.loc[code_index]
        date_index = prices.index.get_level_values("Date")
        calendar = date_index.unique().sort_values()
        ordinal = calendar.get_indexer(date_index)
        boundaries = np.flatnonzero(np.r_[True, np.diff(ordinal) > 20, True])
        for left, right in zip(boundaries[:-1], boundaries[1:]):
            segment = prices.iloc[left:right]
            if len(segment):
                frames.append(_with_missing_bar_resets(segment))
    if not frames:
        return pd.DataFrame(index=index, columns=core.OUTPUT_COLUMNS)
    result = pd.concat(frames).sort_index()
    if not result.index.equals(index):
        raise ValueError("Feature output index does not match the input panel")
    if result["mr_signal"].isna().any() or result["bo_signal"].isna().any():
        raise ValueError("Signal coverage contains missing values")
    return result


def signal_from_features(features):
    """Signed event score: MR edge entries plus active BO lifecycle."""
    score = features["mr_signal"].astype(float)
    # During EXTEND/ANCHOR, retain the BO side. The first new BOX ends that leg.
    direction = np.zeros(len(features), dtype=float)
    for _, locs in features.groupby(level="Code", sort=False).indices.items():
        active = 0.0
        for i in locs:
            if features["state"].iloc[i] == core.SEARCH:
                active = 0.0
            if features["bo_signal"].iloc[i] != 0:
                active = float(features["bo_signal"].iloc[i])
            if features["bo_exit"].iloc[i]:
                active = 0.0
            direction[i] = active
    bo_score = pd.Series(direction, index=features.index)
    return (score + bo_score).rename("Return")
