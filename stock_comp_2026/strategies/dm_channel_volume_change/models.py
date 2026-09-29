"""Fixed, low-capacity Ridge model for the channel/volume experiment."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_breakout_side_momentum.features import segment_keys


FEATURE_COLUMNS = ("channel_position_250", "volume_change_1d")
EVAL_YEARS = tuple(range(2010, 2017))
RIDGE_LAMBDA = 1.0


def centered_target_rank(target):
    values = pd.to_numeric(target, errors="coerce").replace([np.inf, -np.inf], np.nan)
    ranks = values.groupby(level="Date").rank(method="average", pct=True)
    center = ranks.groupby(level="Date").transform("mean")
    return (2.0 * (ranks - center)).rename("target_rank")


def _fit_transform(features, training_mask):
    train = features.loc[training_mask].to_numpy(dtype=float)
    finite = np.isfinite(train)
    counts = finite.sum(axis=0)
    means = np.divide(
        np.where(finite, train, 0.0).sum(axis=0),
        counts,
        out=np.zeros(train.shape[1], dtype=float),
        where=counts > 0,
    )
    filled = np.where(finite, train, means)
    scales = filled.std(axis=0)
    scales[scales < 1e-8] = 1.0
    return means, scales


def _transform(features, means, scales):
    matrix = features.to_numpy(dtype=float)
    matrix = np.where(np.isfinite(matrix), matrix, means)
    return (matrix - means) / scales


def fit_before(features, target, calendar, fold_start, model_path=None):
    """Fit expanding-window Ridge on mature, complete-feature Train rows."""
    if not features.index.equals(target.index):
        raise ValueError("Feature and target indexes must match exactly")
    if tuple(features.columns) != FEATURE_COLUMNS:
        raise ValueError("Unexpected feature order")
    start_position = calendar.searchsorted(pd.Timestamp(fold_start))
    eligible_dates = calendar[: max(0, start_position - 2)]
    dates = features.index.get_level_values("Date")
    labels = centered_target_rank(target)
    complete = np.isfinite(features.to_numpy(dtype=float)).all(axis=1)
    finite_target = labels.notna() & np.isfinite(labels.to_numpy(dtype=float))
    training_mask = dates.isin(eligible_dates) & finite_target.to_numpy() & complete
    if int(training_mask.sum()) < 10000:
        raise ValueError(
            f"Too few complete mature rows before {fold_start}: {int(training_mask.sum())}"
        )

    means, scales = _fit_transform(features, training_mask)
    transformed = _transform(features.loc[training_mask], means, scales)
    y = labels.loc[training_mask].to_numpy(dtype=float)
    design = np.column_stack((np.ones(len(transformed)), transformed))
    penalty = np.eye(design.shape[1], dtype=float) * RIDGE_LAMBDA
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ y)
    model = {
        "means": means.tolist(),
        "scales": scales.tolist(),
        "coefficients": coefficients.tolist(),
    }
    if model_path is not None:
        path = Path(model_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")

    used_dates = dates[training_mask]
    last_signal = used_dates.max()
    maturity_position = calendar.get_indexer([last_signal])[0] + 2
    mature_through = calendar[min(maturity_position, len(calendar) - 1)]
    record = {
        "fold_start": str(pd.Timestamp(fold_start).date()),
        "training_rows": int(training_mask.sum()),
        "training_dates": int(used_dates.nunique()),
        "min_training_signal": str(used_dates.min().date()),
        "max_training_signal": str(last_signal.date()),
        "max_training_label_maturity": str(mature_through.date()),
        "feature_complete_fraction_train": float(
            complete[dates.isin(eligible_dates)].mean()
        ),
        "coefficients_intercept_channel_volume": coefficients.tolist(),
        "means": means.tolist(),
        "scales": scales.tolist(),
        "ridge_lambda": RIDGE_LAMBDA,
    }
    return model, training_mask, record


def predict_matrix(features, model):
    means = np.asarray(model["means"], dtype=float)
    scales = np.asarray(model["scales"], dtype=float)
    coefficients = np.asarray(model["coefficients"], dtype=float)
    return coefficients[0] + _transform(features, means, scales) @ coefficients[1:]


def walk_forward_predictions(features, target, years=EVAL_YEARS, model_dir=None):
    calendar = features.index.get_level_values("Date").unique().sort_values()
    dates = features.index.get_level_values("Date")
    predictions, records, models_by_year = [], [], {}
    for year in years:
        fold_start = pd.Timestamp(f"{year}-01-01")
        path = None if model_dir is None else Path(model_dir) / f"ridge_{year}.json"
        model, _, record = fit_before(
            features, target, calendar, fold_start, model_path=path
        )
        selected = dates.year == year
        prediction = pd.Series(
            predict_matrix(features.loc[selected], model),
            index=features.index[selected],
            name="RIDGE_001",
        )
        prediction.name = "RIDGE_001"
        record["year"] = int(year)
        record["prediction_rows"] = int(selected.sum())
        predictions.append(prediction)
        records.append(record)
        models_by_year[int(year)] = model
    combined = pd.concat(predictions).sort_index()
    if not combined.index.is_unique:
        raise AssertionError("Annual prediction indexes overlap")
    return combined, records, models_by_year


def smooth_by_listing(signal, alpha=0.25):
    groups = segment_keys(signal.index)
    return signal.groupby(groups, sort=False).transform(
        lambda values: values.ewm(alpha=alpha, adjust=False).mean()
    ).rename(signal.name)
