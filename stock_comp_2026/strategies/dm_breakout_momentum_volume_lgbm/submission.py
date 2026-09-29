"""Train-only research adapter; this exploratory strategy is not submission-ready."""
from pathlib import Path

import pandas as pd

from . import features, models


def predict(data_dir=".", split="train"):
    if split != "train":
        raise ValueError("This exploratory strategy adapter only produces Train walk-forward scores")
    panels = features.load_inputs(data_dir, split="train")
    x = features.build_features(panels)
    target = pd.read_parquet(Path(data_dir) / "target_1day_train.parquet")["Return"].sort_index()
    prediction, _ = models.walk_forward_predictions(x, target)
    signal = pd.Series(float("nan"), index=x.index, name="LGBM_001")
    signal.loc[prediction.index] = prediction
    signal = models.smooth_by_listing(signal, alpha=0.25)
    return signal.rename("Return").to_frame()
