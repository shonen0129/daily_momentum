"""One fixed, annual expanding Ridge test for high-breakout box quality."""
import json

import numpy as np
import pandas as pd

from .features import FEATURE_COLUMNS, segment_keys


RIDGE_LAMBDA = 1.0
TRIAL_ID = "BOX_RIDGE_001"
# 2010 is a warm-up year: only 99 mature new-high rows precede its first fold.
YEARS = tuple(range(2011, 2017))


def centered_target_rank(target):
    values = pd.to_numeric(target, errors="coerce").replace([np.inf, -np.inf], np.nan)
    rank = values.groupby(level="Date").rank(method="average", pct=True)
    center = rank.groupby(level="Date").transform("mean")
    return (2.0 * (rank - center)).rename("target_rank")


def fit_arrays(x, y, ridge_lambda=RIDGE_LAMBDA):
    matrix = np.asarray(x, dtype=float)
    labels = np.asarray(y, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] != len(FEATURE_COLUMNS) or len(matrix) != len(labels):
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
        "columns": list(FEATURE_COLUMNS),
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
    return coefficients[0] + standardized @ coefficients[1:]


def fit_before(features, target, calendar, fold_start):
    if not features.index.equals(target.index):
        raise ValueError("Feature and target indexes must match")
    calendar = pd.DatetimeIndex(calendar).sort_values().unique()
    dates = features.index.get_level_values("Date")
    start_position = calendar.searchsorted(pd.Timestamp(fold_start))
    mature_dates = calendar[:max(0, start_position - 2)]
    mature = dates.isin(mature_dates)
    high_event = features["new_high_excess"].gt(0.0) & features["high_available"]
    target_rank = centered_target_rank(target)
    training = mature & high_event.to_numpy() & target_rank.notna().to_numpy()
    if int(training.sum()) < 500:
        raise ValueError(f"Too few mature new-high observations before {fold_start}: {int(training.sum())}")
    model = fit_arrays(features.loc[training, list(FEATURE_COLUMNS)], target_rank.loc[training])
    used_dates = dates[training]
    last_signal = pd.Timestamp(used_dates.max())
    position = calendar.get_indexer([last_signal])[0]
    model.update({
        "year": int(pd.Timestamp(fold_start).year),
        "training_dates": int(used_dates.nunique()),
        "min_training_signal": str(pd.Timestamp(used_dates.min()).date()),
        "max_training_signal": str(last_signal.date()),
        "max_label_maturity_date": str(calendar[min(position + 2, len(calendar) - 1)].date()),
    })
    return model, training


def predict_year(features, target, year):
    dates = features.index.get_level_values("Date")
    calendar = dates.unique().sort_values()
    model, training = fit_before(features, target, calendar, f"{year}-01-01")
    selected = dates.year == year
    x = features.loc[selected & features["new_high_excess"].gt(0.0).to_numpy(), list(FEATURE_COLUMNS)]
    prediction = pd.Series(predict_matrix(x, model), index=x.index, name=TRIAL_ID)
    return prediction, model, training


def walk_forward_predictions(features, target, years=YEARS, model_dir=None):
    predictions, records = [], []
    for year in years:
        pred, model, mask = predict_year(features, target, year)
        predictions.append(pred)
        records.append({key: model[key] for key in (
            "year", "training_rows", "training_dates", "min_training_signal",
            "max_training_signal", "max_label_maturity_date", "coefficients",
        )})
        if model_dir is not None:
            model_dir.mkdir(parents=True, exist_ok=True)
            (model_dir / f"RIDGE_{year}.json").write_text(
                json.dumps(model, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                encoding="utf-8",
            )
    combined = pd.concat(predictions).sort_index()
    if not combined.index.is_unique:
        raise AssertionError("Walk-forward prediction indexes overlap")
    return combined, records


def active_percentile(values):
    rank = values.groupby(level="Date").rank(method="average", pct=True)
    return (0.5 + 0.5 * rank).fillna(0.5)


def smooth_by_listing(signal, alpha=0.25):
    groups = segment_keys(signal.index)
    return signal.groupby(groups, sort=False).transform(
        lambda values: values.ewm(alpha=alpha, adjust=False).mean()
    ).rename(signal.name)


def generate_candidate(features, predictions, base_raw_signal, alpha=0.25):
    """Blend predicted box quality into raw Long events; preserve Short leg."""
    result = base_raw_signal.reindex(features.index).copy()
    high_event = features["high_available"] & features["new_high_excess"].gt(0.0)
    pred = predictions.reindex(features.index)
    available = high_event & pred.notna()
    # The base score on Long events lies in [0.5, 1]; the new forecast rank
    # has the same range, so equal blending keeps the breakout direction intact.
    result.loc[available] = (
        0.5 * result.loc[available] + 0.5 * active_percentile(pred.loc[available])
    )
    return smooth_by_listing(result.rename(TRIAL_ID), alpha=alpha)


def raw_base_signal(features):
    """Build the unsmoothed 250-observation breakout-only reference score."""
    high_active = features["high_available"] & features["new_high_excess"].gt(0.0)
    low_active = features["low_available"] & features["new_low_excess"].gt(0.0)
    high = active_percentile(features["new_high_excess"].where(high_active)).where(high_active, 0.0)
    low = active_percentile(features["new_low_excess"].where(low_active)).where(low_active, 0.0)
    return (high - low).rename("B00")


def generate_base_signal(features, alpha=0.25):
    """Return the fixed, smoothed 250-observation breakout-only reference."""
    return smooth_by_listing(raw_base_signal(features), alpha=alpha)
