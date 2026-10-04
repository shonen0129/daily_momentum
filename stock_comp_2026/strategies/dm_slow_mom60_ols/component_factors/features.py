"""Three independent immutable factors, equally ranked on each signal date."""
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from .component_slow import features as slow
    from . import component_momentum as momentum
except ImportError:
    from component_slow import features as slow
    import component_momentum as momentum

INPUT_COLUMNS = {**slow.INPUT_COLUMNS, "beta_1day": ["Return"],
                 "topix_return_1day": ["Return"]}
COMPONENTS = ["Size", "Illiquidity", "MOM60"]
SLOW, CANDIDATE = "SLOW_CONTROL", "SLOW_MOM60_EQUAL"


def load_train(directory):
    return {name: pd.read_parquet(Path(directory) / f"{name}_train.parquet", columns=cols)
            for name, cols in INPUT_COLUMNS.items()}


def components(inputs):
    """Preserve SLOW normalization and MOM60 rank-before-EWMA order exactly."""
    canonical = {}
    for name in INPUT_COLUMNS:
        frame = inputs[name]
        if name == "topix_return_1day":
            if frame.index.name != "Date" or not frame.index.is_unique:
                raise ValueError("Expected unique market Date index")
            canonical[name] = frame.sort_index()
        else:
            canonical[name] = slow.canonical(frame)
    f = slow.build_features({k: canonical[k] for k in slow.INPUT_COLUMNS}, sector=False)
    before_ewma = momentum.build_momentum(canonical)
    mom = momentum.smooth(before_ewma, .25)
    scores = pd.DataFrame({"Size": f.z_size, "Illiquidity": f.z_amihud,
                           SLOW: f.size_liquidity, "MOM60": mom}, index=f.index)
    if not np.isfinite(scores.to_numpy()).all():
        raise ValueError("Nonfinite immutable component")
    intermediates = f[["raw_size", "raw_amihud", "z_size", "z_amihud", "size_liquidity"]].copy()
    intermediates["MOM60_before_ewma"] = before_ewma
    return scores, intermediates


def factor_ranks(scores):
    if scores.index.names != ["Date", "Code"] or not scores.index.is_unique:
        raise ValueError("Expected unique Date/Code index")
    if not scores.index.is_monotonic_increasing:
        raise ValueError("Expected canonical sorted index")
    if not np.isfinite(scores[COMPONENTS].to_numpy()).all():
        raise ValueError("All three final components must be finite")
    return pd.DataFrame({name + "Rank": momentum.centered_rank(scores[name])
                         for name in COMPONENTS}, index=scores.index)


def score(scores):
    r = factor_ranks(scores)
    return ((r.SizeRank + r.IlliquidityRank + r.MOM60Rank) / 3).rename("Return")
