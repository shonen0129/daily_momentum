"""Fixed annual expanding Ridge fits for Candidate A and Candidate B."""
import json

import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_variable_box_breakout import bidirectional
from . import features as event_features


RIDGE_LAMBDA = 1.0
MIN_TRAINING_ROWS = 500
YEARS = tuple(range(2011, 2017))
CANDIDATES = ("A", "B")


def feature_columns(candidate):
    if candidate == "A":
        return tuple(bidirectional.DIRECTIONAL_COLUMNS) + event_features.EVENT_A_COLUMNS
    if candidate == "B":
        return tuple(bidirectional.DIRECTIONAL_COLUMNS) + event_features.EVENT_B_COLUMNS
    raise ValueError(f"Unknown candidate: {candidate}")


def _directional_matrix(x, side, candidate):
    base = bidirectional.directional_features(x, side)
    added = list(event_features.EVENT_A_COLUMNS)
    if candidate == "B":
        added.append("pullback_up")
    return base.join(x.loc[:, added]).replace([np.inf, -np.inf], np.nan)


def fit_arrays(x, y, columns, ridge_lambda=RIDGE_LAMBDA):
    matrix = np.asarray(x, dtype=float)
    labels = np.asarray(y, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] != len(columns) or len(matrix) != len(labels):
        raise ValueError("Invalid Ridge input shape")
    if len(labels) < 2 or not np.isfinite(labels).all() or ridge_lambda < 0:
        raise ValueError("Invalid Ridge training data")
    finite = np.isfinite(matrix)
    count = finite.sum(axis=0)
    mean = np.divide(
        np.where(finite, matrix, 0.0).sum(axis=0), count,
        out=np.zeros(matrix.shape[1], dtype=float), where=count > 0,
    )
    filled = np.where(finite, matrix, mean)
    scale = filled.std(axis=0)
    scale[scale < 1e-8] = 1.0
    standardized = (filled - mean) / scale
    design = np.column_stack((np.ones(len(standardized)), standardized))
    penalty = np.eye(design.shape[1]) * ridge_lambda
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ labels)
    return {
        "columns": list(columns),
        "mean": mean.tolist(),
        "scale": scale.tolist(),
        "coefficients": coefficients.tolist(),
        "ridge_lambda": float(ridge_lambda),
        "training_rows": int(len(labels)),
    }


def predict_matrix(x, model):
    if list(x.columns) != model["columns"]:
        raise ValueError("Prediction feature order mismatch")
    matrix = x.to_numpy(dtype=float)
    finite = np.isfinite(matrix)
    mean = np.asarray(model["mean"], dtype=float)
    scale = np.asarray(model["scale"], dtype=float)
    standardized = (np.where(finite, matrix, mean) - mean) / scale
    coefficients = np.asarray(model["coefficients"], dtype=float)
    prediction = coefficients[0] + standardized @ coefficients[1:]
    if not np.isfinite(prediction).all():
        raise ValueError("Nonfinite Ridge prediction")
    return prediction


def fit_before(x, target, calendar, fold_start, side, candidate):
    if side not in bidirectional.SIDES:
        raise ValueError(f"Unknown breakout side: {side}")
    if not x.index.equals(target.index):
        raise ValueError("Feature and target indexes must match exactly")
    calendar = pd.DatetimeIndex(calendar).sort_values().unique()
    dates = x.index.get_level_values("Date")
    start_position = calendar.searchsorted(pd.Timestamp(fold_start))
    mature_dates = calendar[:max(0, start_position - 2)]
    mature = dates.isin(mature_dates)
    target_rank = bidirectional.centered_target_rank(target)
    oriented_target = target_rank if side == "high" else -target_rank
    training = mature & bidirectional.event_mask(x, side).to_numpy() & oriented_target.notna().to_numpy()
    rows = int(training.sum())
    if rows < MIN_TRAINING_ROWS:
        raise ValueError(f"Too few mature {side} events before {fold_start}: {rows}")
    columns = feature_columns(candidate)
    matrix = _directional_matrix(x.loc[training], side, candidate)
    model = fit_arrays(matrix, oriented_target.loc[training], columns)
    used_dates = dates[training]
    last_signal = pd.Timestamp(used_dates.max())
    position = calendar.get_indexer([last_signal])[0]
    model.update({
        "candidate": candidate,
        "side": side,
        "year": int(pd.Timestamp(fold_start).year),
        "training_dates": int(used_dates.nunique()),
        "min_training_signal": str(pd.Timestamp(used_dates.min()).date()),
        "max_training_signal": str(last_signal.date()),
        "max_label_maturity_date": str(calendar[min(position + 2, len(calendar) - 1)].date()),
    })
    return model, training


def predict_year(x, target, year, side, candidate):
    dates = x.index.get_level_values("Date")
    calendar = pd.DatetimeIndex(dates.unique().sort_values())
    model, training = fit_before(x, target, calendar, f"{year}-01-01", side, candidate)
    selected = (dates.year == year) & bidirectional.event_mask(x, side).to_numpy()
    matrix = _directional_matrix(x.loc[selected], side, candidate)
    prediction = pd.Series(
        predict_matrix(matrix, model), index=matrix.index,
        name=f"EVENTBOX_SN1_{candidate}_{side}", dtype="float64",
    )
    return prediction, model, training


def walk_forward_predictions(x, target, candidate, years=YEARS, model_dir=None):
    if candidate not in CANDIDATES:
        raise ValueError(f"Unknown candidate: {candidate}")
    predictions = {side: [] for side in bidirectional.SIDES}
    records = []
    for year in years:
        for side in bidirectional.SIDES:
            prediction, model, _ = predict_year(x, target, year, side, candidate)
            predictions[side].append(prediction)
            records.append({key: model[key] for key in (
                "candidate", "side", "year", "training_rows", "training_dates",
                "min_training_signal", "max_training_signal", "max_label_maturity_date",
                "columns", "coefficients", "mean", "scale",
            )})
            if model_dir is not None:
                model_dir.mkdir(parents=True, exist_ok=True)
                path = model_dir / f"RIDGE_{candidate}_{side}_{year}.json"
                path.write_text(
                    json.dumps(model, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8",
                )
    combined = {side: pd.concat(pieces).sort_index() for side, pieces in predictions.items()}
    if any(not values.index.is_unique for values in combined.values()):
        raise AssertionError("Walk-forward prediction indexes overlap")
    if combined["high"].index.intersection(combined["low"].index).size:
        raise AssertionError("A row cannot be both a high and a low breakout")
    return combined, records
