"""Causal Event-Box extensions to the fixed SN1 directional feature set."""
from pathlib import Path

import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_variable_box_breakout import features as sn1_features
from stock_comp_2026.strategies.dm_event_box import features as box_features
from stock_comp_2026.strategies.dm_event_box import core as box_core


INPUT_COLUMNS = {
    **sn1_features.INPUT_COLUMNS,
    "prices_daily_quotes": ["Open", "High", "Low", "Close", "AdjustmentFactor"],
}
EVENT_A_COLUMNS = (
    "event_upstate",
    "event_downstate",
    "event_bo_up_strength",
    "event_bo_down_strength",
    "event_box_width_atr",
    "event_box_age",
    "event_structure_age",
    "event_breakout_age",
    "event_breakout_failure",
    "event_box_position",
)
EVENT_B_COLUMNS = EVENT_A_COLUMNS + ("pullback_up",)
ATR_WINDOW = 20


def load_inputs(directory, split="train"):
    """Read the requested split; research runs pass a Train-only stage directory."""
    if split not in ("train", "valid"):
        raise ValueError(f"Unknown split: {split}")
    directory = Path(directory)
    result = {}
    for name, columns in INPUT_COLUMNS.items():
        path = directory / f"{name}_{split}.parquet"
        frame = pd.read_parquet(path, columns=columns)
        if not frame.index.is_unique:
            raise ValueError(f"Duplicate index in {name}")
        result[name] = frame.sort_index()
    reference = result["raw_return_1day"].index
    for name in ("beta_1day", "prices_daily_quotes"):
        if not result[name].index.equals(reference):
            raise ValueError(f"{name} index differs from raw_return_1day")
    market_index = result["topix_return_1day"].index
    dates = reference.get_level_values("Date").unique()
    if not market_index.is_unique or not dates.isin(market_index).all():
        raise ValueError("TOPIX date index is missing or duplicated")
    return result


def _prior_atr(inputs):
    index = inputs["raw_return_1day"].index
    quotes = inputs["prices_daily_quotes"]
    ohlc = box_features.split_safe_ohlc({
        "raw_return_1day": inputs["raw_return_1day"],
        "prices_daily_quotes": quotes,
    })
    groups = sn1_features.segment_keys(index)
    prior_close = ohlc["Close"].groupby(groups, sort=False).shift(1)
    true_range = pd.concat([
        ohlc["High"] - ohlc["Low"],
        (ohlc["High"] - prior_close).abs(),
        (ohlc["Low"] - prior_close).abs(),
    ], axis=1).max(axis=1, skipna=False)
    return true_range.groupby(groups, sort=False).transform(
        lambda values: values.shift(1).rolling(ATR_WINDOW, min_periods=ATR_WINDOW).mean()
    ).rename("atr_prior")


def _persistent_structure_features(state, atr):
    """Retain breakout direction through subsequent confirmed Boxes until failure."""
    index = state.index
    values = {name: np.full(len(state), np.nan, dtype=float) for name in EVENT_A_COLUMNS}
    codes = index.get_level_values("Code")
    for _, positions in state.groupby(level="Code", sort=False).indices.items():
        direction = 0
        structure_start = None
        breakout_position = None
        box_confirmation_position = None
        last_box_width = np.nan
        up_strength = 0.0
        down_strength = 0.0
        block = state.iloc[positions]
        atr_values = atr.iloc[positions].to_numpy(dtype=float)
        for local, global_position in enumerate(positions):
            row = block.iloc[local]
            state_name = row["state"]
            failed = False

            if state_name == box_core.SEARCH:
                direction = 0
                structure_start = None
                breakout_position = None
                box_confirmation_position = None
                last_box_width = np.nan
                up_strength = 0.0
                down_strength = 0.0

            signal_direction = int(row["bo_signal"])
            if signal_direction:
                if direction and signal_direction != direction:
                    failed = True
                if signal_direction != direction:
                    direction = signal_direction
                    structure_start = local
                elif structure_start is None:
                    structure_start = local
                breakout_position = local
                strength = float(row["bo_strength"])
                up_strength = strength if direction > 0 else 0.0
                down_strength = strength if direction < 0 else 0.0

            if bool(row["bo_exit"]) and not bool(row["new_box"]):
                failed = True
                direction = 0
                structure_start = None
                breakout_position = None
                box_confirmation_position = None
                last_box_width = np.nan
                up_strength = 0.0
                down_strength = 0.0

            if bool(row["new_box"]):
                box_confirmation_position = local
                high, low = row["box_high"], row["box_low"]
                if pd.notna(high) and pd.notna(low):
                    last_box_width = float(high - low)

            atr_value = atr_values[local]
            if state_name != box_core.SEARCH and np.isfinite(last_box_width) and np.isfinite(atr_value) and atr_value > 0:
                values["event_box_width_atr"][global_position] = last_box_width / atr_value
            if state_name != box_core.SEARCH and box_confirmation_position is not None:
                values["event_box_age"][global_position] = float(local - box_confirmation_position)
            if direction and structure_start is not None:
                values["event_structure_age"][global_position] = float(local - structure_start)
            if direction and breakout_position is not None:
                values["event_breakout_age"][global_position] = float(local - breakout_position)

            values["event_upstate"][global_position] = float(direction > 0)
            values["event_downstate"][global_position] = float(direction < 0)
            values["event_bo_up_strength"][global_position] = up_strength
            values["event_bo_down_strength"][global_position] = down_strength
            values["event_breakout_failure"][global_position] = float(failed)
            if state_name == box_core.BOX and pd.notna(row["close_position"]):
                values["event_box_position"][global_position] = float(row["close_position"])

    result = pd.DataFrame(values, index=index)
    result["pullback_up"] = result["event_upstate"] * (-result["event_box_position"]).clip(lower=0.0)
    return result.replace([np.inf, -np.inf], np.nan)


def build_features(inputs):
    """Return original SN1 features plus causal Event-Box features on the same index."""
    index = inputs["raw_return_1day"].index
    base = sn1_features.build_features(inputs)
    event_state = box_features.build_features({
        "raw_return_1day": inputs["raw_return_1day"],
        "prices_daily_quotes": inputs["prices_daily_quotes"],
    })
    if not event_state.index.equals(index):
        raise ValueError("Event-Box state index differs from SN1 feature index")
    event = _persistent_structure_features(event_state, _prior_atr(inputs))
    result = base.join(event)
    if not result.index.equals(index):
        raise ValueError("Combined feature index differs from the input panel")
    if not result.index.is_unique:
        raise ValueError("Combined feature index is not unique")
    result.attrs["base_feature_columns"] = list(sn1_features.FEATURE_COLUMNS)
    result.attrs["event_a_columns"] = list(EVENT_A_COLUMNS)
    result.attrs["event_b_columns"] = list(EVENT_B_COLUMNS)
    return result
