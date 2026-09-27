"""Train-only adapter for the descriptive variable-box experiment."""
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from . import bidirectional, features, sn1
except ImportError:
    # The competition evaluator imports submission.py as a top-level module
    # from the extracted strategy directory.
    import bidirectional
    import features
    import sn1


CANDIDATE_IDS = ("D_LOW_FAST_ONLY", "SIDE_SOURCE_SEPARATION")


def score_from_predictions(x, predictions):
    """Convert fixed annual event predictions through the shared research SN1 path."""
    base_score = bidirectional.generate_signal(x, predictions, alpha=sn1.HIGH_ALPHA)
    final_score = sn1.rebuild_from_base_score(base_score)["SIDE_SOURCE_SEPARATION"]
    return base_score, final_score


def candidate_scores_from_predictions(x, predictions):
    """Return the two preregistered comparison scores from one frozen prediction stream."""
    base_score = bidirectional.generate_signal(x, predictions, alpha=sn1.HIGH_ALPHA)
    replay = sn1.rebuild_from_base_score(base_score)
    return {
        "D_LOW_FAST_ONLY": replay["D_LOW_FAST_ONLY"],
        "SIDE_SOURCE_SEPARATION": replay["SIDE_SOURCE_SEPARATION"],
    }


def predict_from_features(x, target, years=range(2011, 2017)):
    """Fit fixed annual Train models and return the registered SN1 score."""
    if not x.index.equals(target.index):
        raise ValueError("Feature and Train target indexes are not exactly aligned")
    predictions, records = bidirectional.walk_forward_predictions(
        x, target, years=years, model_dir=None
    )
    _, result = score_from_predictions(x, predictions)
    return result.rename("Return").to_frame(), records


def predict_candidates_from_features(x, target, years=range(2011, 2017)):
    """Return only the preregistered D and SN1 Train scores."""
    if not x.index.equals(target.index):
        raise ValueError("Feature and Train target indexes are not exactly aligned")
    predictions, records = bidirectional.walk_forward_predictions(
        x, target, years=years, model_dir=None
    )
    scores = candidate_scores_from_predictions(x, predictions)
    return {
        name: score.rename("Return").to_frame()
        for name, score in scores.items()
    }, records


def _combine_panels(train_panels, later_panels):
    combined = {}
    for name in train_panels:
        train = train_panels[name]
        later = later_panels[name]
        joined = pd.concat([train, later]).sort_index()
        if not joined.index.is_unique:
            raise ValueError(f"Train and later inputs overlap for {name}")
        combined[name] = joined
    return combined


def _predict_later(x_train, target_train, x_later, full_calendar):
    """Fit one final model per side on mature Train and predict later events."""
    later_predictions = {}
    first_date = pd.Timestamp(x_later.index.get_level_values("Date").min())
    for side in bidirectional.SIDES:
        model, _ = bidirectional.fit_before(
            x_train, target_train, full_calendar, first_date, side
        )
        active = bidirectional.event_mask(x_later, side)
        matrix = bidirectional.directional_features(x_later.loc[active], side)
        later_predictions[side] = pd.Series(
            bidirectional.predict_matrix(matrix, model),
            index=matrix.index,
            name=f"{bidirectional.TRIAL_ID}_{side}",
            dtype="float64",
        )
    return later_predictions


def predict_candidates(data_dir=".", split=None):
    """Build the fixed D/SN1 comparison from one model fit and one signal stream."""
    data_dir = Path(data_dir)
    if split is None:
        split = "valid" if (data_dir / "raw_return_1day_valid.parquet").is_file() else "train"
    if split not in ("train", "valid"):
        raise ValueError(f"Unknown prediction split: {split}")

    train_panels = features.load_inputs(data_dir, split="train")
    target_train = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index()
    x_train = features.build_features(train_panels)
    if not x_train.index.equals(target_train.index):
        raise ValueError("Train features and Train target indexes are not exactly aligned")

    if split == "train":
        candidates, _ = predict_candidates_from_features(x_train, target_train)
        return candidates

    later_panels = features.load_inputs(data_dir, split="valid")
    full_panels = _combine_panels(train_panels, later_panels)
    x_full = features.build_features(full_panels)
    if not x_full.index.is_unique:
        raise ValueError("Combined feature index is not unique")
    x_later = x_full.loc[x_full.index.isin(later_panels["raw_return_1day"].index)]
    if not x_later.index.equals(later_panels["raw_return_1day"].index.sort_values()):
        raise ValueError("Later feature coverage or order differs from the requested split")

    train_predictions, _ = bidirectional.walk_forward_predictions(x_train, target_train)
    calendar = pd.DatetimeIndex(
        x_full.index.get_level_values("Date").unique().sort_values()
    )
    later_predictions = _predict_later(x_train, target_train, x_later, calendar)
    predictions = {
        side: pd.concat([train_predictions[side], later_predictions[side]]).sort_index()
        for side in bidirectional.SIDES
    }
    if any(not values.index.is_unique for values in predictions.values()):
        raise ValueError("Train and later event predictions overlap")
    scores = candidate_scores_from_predictions(x_full, predictions)
    candidates = {
        name: score.reindex(x_later.index).rename("Return").to_frame()
        for name, score in scores.items()
    }
    for name, result in candidates.items():
        if not result.index.equals(x_later.index) or not np.isfinite(result.to_numpy()).all():
            raise ValueError(f"Later {name} prediction coverage or finiteness failure")
    return candidates


def predict(data_dir=".", split=None):
    """Official one-column entry point; the registered strategy is SN1."""
    return predict_candidates(data_dir=data_dir, split=split)["SIDE_SOURCE_SEPARATION"]
