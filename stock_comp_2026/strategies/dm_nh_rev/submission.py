"""Self-contained fixed NH_REV_001 predictor; no target access or fitting."""
from pathlib import Path
import pandas as pd
try:
    from .features import load_inputs, build_features, signal_stages
except ImportError:
    from features import load_inputs, build_features, signal_stages


def predict(data_dir=".", split=None):
    if split is None:
        split = "valid" if (Path(data_dir)/"raw_return_1day_valid.parquet").exists() else "train"
    inputs = load_inputs(data_dir, "train")
    index = inputs["raw_return_1day"].index
    if split == "valid":
        later = load_inputs(data_dir, "valid")
        index = later["raw_return_1day"].index
        inputs = {k: pd.concat([inputs[k], later[k]]).sort_index() for k in inputs}
    elif split != "train":
        raise ValueError(split)
    if any(not v.index.is_unique for v in inputs.values()):
        raise ValueError("Duplicate input index")
    return signal_stages(build_features(inputs)).ewma_score.reindex(index).rename("Return").to_frame()
