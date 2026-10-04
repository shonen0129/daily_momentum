"""Self-contained explicit Train-only adapter; no later split is supported."""
from pathlib import Path
import pandas as pd

try:
    from .features import components, blend, sn_features, slow_features
except ImportError:
    from features import components, blend, sn_features, slow_features


def predict(data_dir="."):
    directory = Path(data_dir)
    sn_inputs = sn_features.load_inputs(directory, split="train")
    slow_inputs = slow_features.load_train(directory)
    target = pd.read_parquet(directory / "target_1day_train.parquet")["Return"].sort_index()
    scores, _, _, _ = components(sn_inputs, slow_inputs, target)
    return blend(scores.SN1_H1, scores.SLOW_CONTROL).rename("Return").to_frame()
