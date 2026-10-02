"""Research adapter; candidate must be explicit and only Train is supported."""
from pathlib import Path

import pandas as pd

from stock_comp_2026.strategies.dm_variable_box_breakout import bidirectional
from stock_comp_2026.strategies.dm_variable_box_breakout import submission as sn1_submission
from stock_comp_2026.strategies.dm_variable_box_breakout import sn1
from . import features, models


def score_from_predictions(x, predictions):
    base_score = bidirectional.generate_signal(x, predictions, alpha=sn1.HIGH_ALPHA)
    return sn1.rebuild_from_base_score(base_score)["SIDE_SOURCE_SEPARATION"].rename("Return")


def predict_candidate_from_features(x, target, candidate, model_dir=None):
    if candidate == "baseline":
        result, records = sn1_submission.predict_from_features(x, target)
        return result["Return"].rename("Return"), records
    predictions, records = models.walk_forward_predictions(
        x, target, candidate=candidate, model_dir=model_dir
    )
    return score_from_predictions(x, predictions), records


def predict(data_dir=".", split="train", candidate=None):
    """Generate one selected research score; never reads Valid or raw-target labels."""
    if split != "train":
        raise ValueError("This research adapter supports Train only")
    if candidate not in ("baseline", "A", "B"):
        raise ValueError("candidate must be explicitly set to baseline, A, or B")
    directory = Path(data_dir)
    x = features.build_features(features.load_inputs(directory, split="train"))
    target = pd.read_parquet(directory / "target_1day_train.parquet")["Return"].sort_index()
    if not x.index.equals(target.index):
        raise ValueError("Train features and Train target indexes differ")
    score, _ = predict_candidate_from_features(x, target, candidate)
    if not score.index.equals(target.index):
        raise ValueError("Prediction index does not cover the Train panel")
    return score.to_frame("Return")
