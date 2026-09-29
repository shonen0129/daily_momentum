"""Small expanding-window Ridge regression with mature-label purging."""
import json

import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_breakout_side_momentum.features import segment_keys


FEATURE_COLUMNS = (
    "res60s1",
    "new_high_rank",
    "new_low_rank",
    "relative_volume_change_rank",
)
RIDGE_LAMBDA = 1.0
YEARS = (2010, 2011, 2012, 2013, 2014)


def centered_target_rank(target):
    """Per-date average percentile target rank centered to [-1, 1]."""
    values = pd.to_numeric(target, errors="coerce").replace([np.inf, -np.inf], np.nan)
    ranks = values.groupby(level="Date").rank(method="average", pct=True)
    center = ranks.groupby(level="Date").transform("mean")
    return (2.0 * (ranks - center)).rename("target_rank")


def fit_arrays(x, y, ridge_lambda=RIDGE_LAMBDA):
    """Fit standardized Ridge using training-only imputation and scaling."""
    matrix = np.asarray(x, dtype=float)
    labels = np.asarray(y, dtype=float)
    if matrix.ndim != 2 or len(matrix) != len(labels) or len(labels) < 2:
        raise ValueError("Invalid linear training matrix")
    if not np.isfinite(labels).all() or ridge_lambda < 0:
        raise ValueError("Ridge labels must be finite and lambda nonnegative")
    finite = np.isfinite(matrix)
    count = finite.sum(axis=0)
    mean = np.divide(
        np.where(finite, matrix, 0.0).sum(axis=0),
        count,
        out=np.zeros(matrix.shape[1], dtype=float),
        where=count > 0,
    )
    filled = np.where(finite, matrix, mean)
    scale = filled.std(axis=0)
    scale[scale < 1e-8] = 1.0
    standardized = (filled - mean) / scale
    design = np.column_stack((np.ones(len(standardized)), standardized))
    penalty = np.eye(design.shape[1]) * ridge_lambda
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(
        design.T @ design + penalty,
        design.T @ labels,
    )
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
    filled = np.where(finite, matrix, mean)
    standardized = (filled - mean) / scale
    coefficients = np.asarray(model["coefficients"], dtype=float)
    result = np.full(len(x), coefficients[0], dtype=float)
    for column, coefficient in enumerate(coefficients[1:]):
        result += standardized[:, column] * coefficient
    return result


def fit_before(features, target, calendar, fold_start):
    if not features.index.equals(target.index):
        raise ValueError("Feature and target indexes must match exactly")
    if list(features.columns) != list(FEATURE_COLUMNS):
        raise ValueError("Unexpected feature contract")
    dates = features.index.get_level_values("Date")
    calendar = pd.DatetimeIndex(calendar).sort_values().unique()
    start_position = calendar.searchsorted(pd.Timestamp(fold_start))
    eligible_dates = calendar[: max(0, start_position - 2)]
    eligible_rows = dates.isin(eligible_dates)
    mature_target = target.where(eligible_rows)
    ranked_target = centered_target_rank(mature_target)
    available = ranked_target.notna()
    training_mask = eligible_rows & available.to_numpy()
    if training_mask.sum() < 10_000:
        raise ValueError(f"Too few mature training rows before {fold_start}")
    model = fit_arrays(
        features.loc[training_mask].to_numpy(),
        ranked_target.loc[training_mask].to_numpy(),
    )
    used_dates = dates[training_mask]
    last_signal = used_dates.max()
    position = calendar.get_indexer([last_signal])[0]
    model.update({
        "year": int(pd.Timestamp(fold_start).year),
        "training_dates": int(used_dates.nunique()),
        "min_training_signal": str(used_dates.min().date()),
        "max_training_signal": str(last_signal.date()),
        "max_label_maturity_date": str(calendar[min(position + 2, len(calendar) - 1)].date()),
    })
    return model, training_mask


def predict_year(features, target, year):
    dates = features.index.get_level_values("Date")
    calendar = dates.unique().sort_values()
    model, training_mask = fit_before(features, target, calendar, f"{year}-01-01")
    selected = dates.year == year
    prediction = pd.Series(
        predict_matrix(features.loc[selected], model),
        index=features.index[selected],
        name="LINEAR_001",
    )
    return prediction, model, training_mask


def walk_forward_predictions(features, target, years=YEARS, model_dir=None):
    pieces = []
    models = []
    for year in years:
        prediction, model, _ = predict_year(features, target, year)
        pieces.append(prediction)
        models.append(model)
        if model_dir is not None:
            model_dir.mkdir(parents=True, exist_ok=True)
            path = model_dir / f"RIDGE_{year}.json"
            path.write_text(
                json.dumps(model, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                encoding="utf-8",
            )
    combined = pd.concat(pieces).sort_index()
    if not combined.index.is_unique:
        raise AssertionError("Walk-forward prediction indexes overlap")
    return combined, models


def smooth_by_listing(signal, alpha=0.25):
    groups = segment_keys(signal.index)
    return signal.groupby(groups, sort=False).transform(
        lambda values: values.ewm(alpha=alpha, adjust=False).mean()
    ).rename(signal.name)
