"""Feature-only DRI implementation; this module never reads labels."""
from pathlib import Path

import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_fixed_long_short import core as champion_core


WINDOW = 21
INPUT_COLUMNS = {
    "raw_return_1day": ["Return"],
    "beta_1day": ["Return"],
    "topix_return_1day": ["Return"],
}


def load_inputs(directory, split="train"):
    """Load exactly the three causal inputs needed by DRI."""
    if split not in ("train", "valid"):
        raise ValueError("Unknown feature split")
    root = Path(directory)
    result = {}
    for name, columns in INPUT_COLUMNS.items():
        frame = pd.read_parquet(root / f"{name}_{split}.parquet", columns=columns).sort_index()
        if not frame.index.is_unique:
            raise ValueError(f"Duplicate index in {name}")
        result[name] = frame
    return result


def residual_return(inputs):
    """Return the causal same-day market residual using supplied return series."""
    raw = inputs["raw_return_1day"]["Return"].sort_index().replace([np.inf, -np.inf], np.nan)
    index = raw.index
    dates = index.get_level_values("Date")
    beta = inputs["beta_1day"]["Return"].reindex(index)
    market = pd.Series(inputs["topix_return_1day"]["Return"].reindex(dates).to_numpy(), index=index)
    return (raw - beta * market).replace([np.inf, -np.inf], np.nan)


def dri_vector(values, prefix):
    """Return chronological and ascending-sorted complete 21-observation vectors."""
    values = values.sort_index().replace([np.inf, -np.inf], np.nan)
    groups = champion_core.segment_keys(values.index)
    pieces, current = [], values
    for lag in range(WINDOW):
        pieces.append(current.rename(f"{prefix}_time_lag_{lag}"))
        current = current.groupby(groups, sort=False).shift()
    chronological = pd.concat(pieces, axis=1)
    available = chronological.notna().all(axis=1)
    ordered = np.full((len(chronological), WINDOW), np.nan, dtype=float)
    ordered[available.to_numpy()] = np.sort(chronological.loc[available].to_numpy(dtype=float), axis=1)
    sorted_vector = pd.DataFrame(
        ordered, index=chronological.index,
        columns=[f"{prefix}_sorted_{rank}" for rank in range(1, WINDOW + 1)],
    )
    return chronological.join(sorted_vector), available.rename(f"{prefix}_available")


def build_features(inputs):
    """Build RAW and RES DRI vectors without cross-date filling or normalization."""
    raw = inputs["raw_return_1day"]["Return"].sort_index().replace([np.inf, -np.inf], np.nan)
    raw_vector, raw_available = dri_vector(raw, "raw")
    res_vector, res_available = dri_vector(residual_return(inputs), "res")
    features = raw_vector.join(res_vector, validate="one_to_one")
    features = features.join(raw_available, validate="one_to_one").join(res_available, validate="one_to_one")
    return features


def feature_columns(variant):
    if variant not in ("raw", "res"):
        raise ValueError(f"Unknown DRI variant: {variant}")
    return [f"{variant}_time_lag_{lag}" for lag in range(WINDOW)] + [
        f"{variant}_sorted_{rank}" for rank in range(1, WINDOW + 1)
    ]


def smooth_complete(score, available, alpha):
    """EWMA only for complete current windows; incomplete rows stay precisely neutral."""
    source = score.where(available)
    smoothed = source.groupby(champion_core.segment_keys(score.index), sort=False).transform(
        lambda value: value.ewm(alpha=alpha, adjust=False).mean()
    )
    return smoothed.where(available, 0.0).fillna(0.0).rename("Return")
