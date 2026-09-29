"""Train-only adapter for the registered Ridge or LightGBM research candidate."""
from pathlib import Path

import pandas as pd

from . import features, models


def predict(data_dir=".", split="train", model_kind="ridge"):
    if split != "train":
        raise ValueError("This exploratory adapter only produces Train walk-forward scores")
    panels = features.load_inputs(data_dir, split="train")
    x = features.build_features(panels)
    target = pd.read_parquet(Path(data_dir) / "target_1day_train.parquet")["Return"].sort_index()
    predictions, _, _ = models.walk_forward_predictions(x, target, model_kind)
    signal = pd.Series(float("nan"), index=x.index, name=model_kind.upper())
    signal.loc[predictions.index] = predictions
    signal = models.smooth_by_listing(signal, alpha=0.25)
    return signal.rename("Return").to_frame()
