"""Train-only adapter for reproducing the fixed Ridge experiment."""
from pathlib import Path

import pandas as pd

from . import features, models


def predict(data_dir=".", split="train"):
    """Return annual expanding-window Train predictions for research only."""
    if split != "train":
        raise ValueError("This research adapter only supports the Train split")
    inputs = features.load_inputs(data_dir, split="train")
    matrix = features.build_features(inputs)
    target = pd.read_parquet(Path(data_dir) / "target_1day_train.parquet")["Return"].sort_index()
    predictions, _, _ = models.walk_forward_predictions(matrix, target)
    signal = pd.Series(float("nan"), index=matrix.index, name="RIDGE_001")
    signal.loc[predictions.index] = predictions
    signal = models.smooth_by_listing(signal, alpha=0.25)
    return signal.rename("Return").to_frame()
