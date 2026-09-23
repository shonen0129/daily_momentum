"""Causal advanced-DTI representations; feature construction never reads labels."""
from pathlib import Path

import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_dti_long_short import features as base_dti
from stock_comp_2026.strategies.dm_fixed_long_short import core


WINDOW = 21
BASELINE_WINDOW = 60
EPSILON = 1e-12
REPRESENTATIONS = ("D0", "A1", "S1", "U1", "R1")


def load_inputs(directory, split="train"):
    """Load only raw volume, strictly-prior shares, and contemporaneous returns."""
    if split not in ("train", "valid"):
        raise ValueError("Unknown feature split")
    result = base_dti.load_inputs(directory, split)
    root = Path(directory)
    for name in ("raw_return_1day", "beta_1day", "topix_return_1day"):
        frame = pd.read_parquet(root / f"{name}_{split}.parquet", columns=["Return"]).sort_index()
        if not frame.index.is_unique:
            raise ValueError(f"Duplicate index in {name}")
        result[name] = frame
    return result


def residual_return(inputs):
    """Same-date residual return, available at signal date after that day's close."""
    raw = inputs["raw_return_1day"]["Return"].sort_index().replace([np.inf, -np.inf], np.nan)
    index = raw.index
    dates = index.get_level_values("Date")
    beta = inputs["beta_1day"]["Return"].reindex(index)
    market = pd.Series(inputs["topix_return_1day"]["Return"].reindex(dates).to_numpy(), index=index)
    return (raw - beta * market).replace([np.inf, -np.inf], np.nan).rename("residual_return")


def strictly_prior_median(value, window=BASELINE_WINDOW):
    """Median of exactly the prior observations in each listing segment, never current."""
    groups = core.segment_keys(value.index)
    prior = value.groupby(groups, sort=False).shift(1)
    return prior.groupby(groups, sort=False).transform(
        lambda block: block.rolling(window, min_periods=window).median()
    ).rename("baseline_log_turnover")


def vector(value, prefix):
    """Current-to-lagged chronological and ascending vectors without any future fill."""
    values = value.sort_index().replace([np.inf, -np.inf], np.nan)
    groups = core.segment_keys(values.index)
    blocks, current = [], values
    for lag in range(WINDOW):
        blocks.append(current.rename(f"{prefix}_time_lag_{lag}"))
        current = current.groupby(groups, sort=False).shift(1)
    chronological = pd.concat(blocks, axis=1)
    available = chronological.notna().all(axis=1)
    ordered = np.full((len(chronological), WINDOW), np.nan, dtype=float)
    ordered[available.to_numpy()] = np.sort(chronological.loc[available].to_numpy(dtype=float), axis=1)
    sorted_vector = pd.DataFrame(
        ordered, index=chronological.index,
        columns=[f"{prefix}_sorted_{rank}" for rank in range(1, WINDOW + 1)],
    )
    return chronological.join(sorted_vector), available.rename(f"{prefix}_available")


def feature_columns(representation):
    mapping = {
        "D0": ("to",), "A1": ("ato",), "S1": ("signed_ato",),
        "U1": ("up_ato", "down_ato"), "R1": ("ato", "rc_ato"),
    }
    if representation not in mapping:
        raise ValueError(f"Unknown representation: {representation}")
    return [f"{prefix}_time_lag_{lag}" for prefix in mapping[representation] for lag in range(WINDOW)] + [
        f"{prefix}_sorted_{rank}" for prefix in mapping[representation] for rank in range(1, WINDOW + 1)
    ]


def build_features(inputs):
    """Build D0/A1/S1/U1/R1 from strictly causal raw inputs."""
    turnover = base_dti.turnover_rate(inputs)
    log_turnover = np.log(turnover.turnover_rate + EPSILON).where(turnover.turnover_rate.notna()).rename("log_turnover")
    baseline = strictly_prior_median(log_turnover)
    abnormal = (log_turnover - baseline).replace([np.inf, -np.inf], np.nan).rename("abnormal_turnover")
    residual = residual_return(inputs)
    signed = (abnormal * np.sign(residual)).where(residual.notna()).rename("signed_abnormal_turnover")
    up = abnormal.where(residual > 0, 0.0).where(residual.notna()).rename("up_abnormal_turnover")
    down = abnormal.where(residual < 0, 0.0).where(residual.notna()).rename("down_abnormal_turnover")
    conditioned = (abnormal * residual).where(residual.notna()).rename("return_conditioned_abnormal_turnover")

    vectors, availability = [], []
    for value, prefix in ((turnover.turnover_rate, "to"), (abnormal, "ato"), (signed, "signed_ato"),
                          (up, "up_ato"), (down, "down_ato"), (conditioned, "rc_ato")):
        block, complete = vector(value, prefix)
        vectors.append(block)
        availability.append(complete)
    result = turnover.join(pd.concat([log_turnover, baseline, abnormal, residual, signed, up, down, conditioned], axis=1))
    result = result.join(pd.concat(vectors, axis=1)).join(pd.concat(availability, axis=1))
    result["D0_available"] = result.to_available
    result["A1_available"] = result.ato_available
    result["S1_available"] = result.signed_ato_available
    result["U1_available"] = result.up_ato_available & result.down_ato_available
    result["R1_available"] = result.ato_available & result.rc_ato_available
    # Compatibility field for the audited DTI denominator preflight; D0 is the
    # original complete raw-turnover vector.
    result["available"] = result["D0_available"]
    return result


def smooth_complete(score, available, alpha):
    """EWMA within listing segments; unavailable rows remain an exact neutral zero."""
    source = score.where(available)
    result = source.groupby(core.segment_keys(score.index), sort=False).transform(
        lambda block: block.ewm(alpha=alpha, adjust=False).mean()
    )
    return result.where(available, 0.0).fillna(0.0).rename("Return")
