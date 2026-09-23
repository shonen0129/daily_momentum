"""Self-contained 21-day DRI vectors, matching dm_dri_long_short exactly."""
from pathlib import Path

import numpy as np
import pandas as pd

WINDOW = 21
INPUT_COLUMNS = {"raw_return_1day": ["Return"], "beta_1day": ["Return"],
                 "topix_return_1day": ["Return"]}


def load_inputs(directory, split="train"):
    if split not in ("train", "valid"):
        raise ValueError("Unknown feature split")
    result = {}
    for name, columns in INPUT_COLUMNS.items():
        frame = pd.read_parquet(Path(directory) / f"{name}_{split}.parquet", columns=columns).sort_index()
        if not frame.index.is_unique:
            raise ValueError(f"Duplicate index in {name}")
        result[name] = frame
    return result


def segment_keys(index):
    """Same >20 absent exchange-date reset as the existing DRI builder."""
    dates = index.get_level_values("Date")
    calendar = dates.unique().sort_values()
    ordinal = pd.Series(calendar.get_indexer(dates), index=index)
    code = index.get_level_values("Code")
    starts = ordinal.groupby(code, sort=False).diff().gt(20)
    segment = starts.groupby(code, sort=False).cumsum().astype(int)
    return [code, segment]


def residual_return(inputs):
    raw = inputs["raw_return_1day"]["Return"].sort_index().replace([np.inf, -np.inf], np.nan)
    index = raw.index
    dates = index.get_level_values("Date")
    beta = inputs["beta_1day"]["Return"].reindex(index)
    market = pd.Series(inputs["topix_return_1day"]["Return"].reindex(dates).to_numpy(), index=index)
    return (raw - beta * market).replace([np.inf, -np.inf], np.nan)


def dri_vector(values, prefix):
    values = values.sort_index().replace([np.inf, -np.inf], np.nan)
    groups = segment_keys(values.index)
    pieces, current = [], values
    for lag in range(WINDOW):
        pieces.append(current.rename(f"{prefix}_time_lag_{lag}"))
        current = current.groupby(groups, sort=False).shift()
    chronological = pd.concat(pieces, axis=1)
    available = chronological.notna().all(axis=1)
    ordered = np.full((len(chronological), WINDOW), np.nan, dtype=float)
    ordered[available.to_numpy()] = np.sort(chronological.loc[available].to_numpy(dtype=float), axis=1)
    sorted_vector = pd.DataFrame(ordered, index=chronological.index,
                                columns=[f"{prefix}_sorted_{rank}" for rank in range(1, WINDOW + 1)])
    return chronological.join(sorted_vector), available.rename(f"{prefix}_available")


def feature_columns(variant):
    if variant not in ("raw", "res"):
        raise ValueError("Unknown DRI variant")
    return [f"{variant}_time_lag_{lag}" for lag in range(WINDOW)] + [
        f"{variant}_sorted_{rank}" for rank in range(1, WINDOW + 1)]


def build_features(inputs):
    raw = inputs["raw_return_1day"]["Return"].sort_index().replace([np.inf, -np.inf], np.nan)
    rv, ra = dri_vector(raw, "raw")
    sv, sa = dri_vector(residual_return(inputs), "res")
    return rv.join(sv, validate="one_to_one").join(ra, validate="one_to_one").join(sa, validate="one_to_one")


def smooth_complete(score, available, alpha):
    source = score.where(available)
    smoothed = source.groupby(segment_keys(score.index), sort=False).transform(
        lambda value: value.ewm(alpha=alpha, adjust=False).mean())
    return smoothed.where(available, 0.0).fillna(0.0).rename("Return")
