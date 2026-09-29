"""Fixed low-capacity Ridge and LightGBM models for Train-only research."""
import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_breakout_side_momentum.features import segment_keys


FEATURE_COLUMNS = (
    "log_price_slope_60_bps_day",
    "channel_position_250",
    "volume_zscore_60",
)
EVAL_YEARS = tuple(range(2010, 2017))
RIDGE_LAMBDA = 1.0
LGBM_PARAMETERS = {
    "objective": "regression",
    "max_depth": 2,
    "num_leaves": 4,
    "n_estimators": 60,
    "min_child_samples": 500,
    "learning_rate": 0.05,
    "reg_lambda": 10.0,
    "random_state": 20260924,
    "n_jobs": 2,
    "verbosity": -1,
    "deterministic": True,
    "force_col_wise": True,
}


def centered_target_rank(target):
    values = pd.to_numeric(target, errors="coerce").replace([np.inf, -np.inf], np.nan)
    ranks = values.groupby(level="Date").rank(method="average", pct=True)
    center = ranks.groupby(level="Date").transform("mean")
    return (2.0 * (ranks - center)).rename("target_rank")


def _prepare_arrays(features, training_mask):
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


def fit_before(features, target, calendar, fold_start, kind, model_path=None):
    """Fit one annual expanding model using only mature, complete-feature rows."""
    if not features.index.equals(target.index):
        raise ValueError("Feature and target indexes must match exactly")
    if list(features.columns) != list(FEATURE_COLUMNS):
        raise ValueError("Unexpected feature order")
    start_position = calendar.searchsorted(pd.Timestamp(fold_start))
    eligible_dates = calendar[: max(0, start_position - 2)]
    dates = features.index.get_level_values("Date")
    labels = centered_target_rank(target)
    complete = np.isfinite(features.to_numpy(dtype=float)).all(axis=1)
    finite_target = labels.notna() & np.isfinite(labels.to_numpy(dtype=float))
    training_mask = dates.isin(eligible_dates) & finite_target.to_numpy() & complete
    if int(training_mask.sum()) < 10000:
        raise ValueError(f"Too few complete mature rows before {fold_start}: {int(training_mask.sum())}")

    means, scales = _prepare_arrays(features, training_mask)
    transformed = _transform(features.loc[training_mask], means, scales)
    y = labels.loc[training_mask].to_numpy(dtype=float)
    model_dir = None if model_path is None else Path(model_path)

    if kind == "ridge":
        design = np.column_stack((np.ones(len(transformed)), transformed))
        penalty = np.eye(design.shape[1], dtype=float) * RIDGE_LAMBDA
        penalty[0, 0] = 0.0
        coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ y)
        model = {
            "kind": "ridge",
            "means": means.tolist(),
            "scales": scales.tolist(),
            "coefficients": coefficients.tolist(),
        }
        if model_dir is not None:
            model_dir.parent.mkdir(parents=True, exist_ok=True)
            model_dir.write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")
        importance = {name: float(value) for name, value in zip(FEATURE_COLUMNS, coefficients[1:])}
    elif kind == "lgbm":
        estimator = lgb.LGBMRegressor(**LGBM_PARAMETERS)
        estimator.fit(transformed, y, feature_name=list(FEATURE_COLUMNS))
        if model_dir is not None:
            model_dir.parent.mkdir(parents=True, exist_ok=True)
            estimator.booster_.save_model(str(model_dir))
        importance = {
            "gain": dict(zip(FEATURE_COLUMNS, map(float, estimator.booster_.feature_importance(importance_type="gain")))),
            "split": dict(zip(FEATURE_COLUMNS, map(int, estimator.booster_.feature_importance(importance_type="split")))),
        }
        model = {"kind": "lgbm", "estimator": estimator,
                 "means": means.tolist(), "scales": scales.tolist()}
    else:
        raise ValueError(f"Unknown model kind: {kind}")

    used_dates = dates[training_mask]
    last_signal = used_dates.max()
    maturity_position = calendar.get_indexer([last_signal])[0] + 2
    mature_through = calendar[min(maturity_position, len(calendar) - 1)]
    record = {
        "kind": kind,
        "fold_start": str(pd.Timestamp(fold_start).date()),
        "training_rows": int(training_mask.sum()),
        "training_dates": int(used_dates.nunique()),
        "min_training_signal": str(used_dates.min().date()),
        "max_training_signal": str(last_signal.date()),
        "max_training_label_maturity": str(mature_through.date()),
        "feature_complete_fraction_train": float(complete[dates.isin(eligible_dates)].mean()),
        "feature_importance_or_coefficients": importance,
        "means": means.tolist(),
        "scales": scales.tolist(),
        "parameters": {"ridge_lambda": RIDGE_LAMBDA} if kind == "ridge" else dict(LGBM_PARAMETERS),
    }
    return model, training_mask, record


def predict_matrix(features, model):
    means = np.asarray(model["means"], dtype=float)
    scales = np.asarray(model["scales"], dtype=float)
    transformed = _transform(features, means, scales)
    if model["kind"] == "ridge":
        coefficients = np.asarray(model["coefficients"], dtype=float)
        return coefficients[0] + transformed @ coefficients[1:]
    return model["estimator"].predict(transformed)


def predict_year(features, target, year, kind, model_dir=None):
    dates = features.index.get_level_values("Date")
    calendar = dates.unique().sort_values()
    fold_start = pd.Timestamp(f"{year}-01-01")
    path = None if model_dir is None else Path(model_dir) / f"{kind}_{year}"
    model, mask, record = fit_before(features, target, calendar, fold_start, kind, path)
    selected = dates.year == year
    result = pd.Series(
        predict_matrix(features.loc[selected], model),
        index=features.index[selected],
        name=kind.upper(),
    )
    record["year"] = int(year)
    record["prediction_rows"] = int(selected.sum())
    return result, model, mask, record


def walk_forward_predictions(features, target, kind, years=EVAL_YEARS, model_dir=None):
    predictions, records, model_by_year = [], [], {}
    for year in years:
        result, model, _, record = predict_year(features, target, year, kind, model_dir)
        predictions.append(result)
        records.append(record)
        model_by_year[int(year)] = model
    combined = pd.concat(predictions).sort_index()
    if not combined.index.is_unique:
        raise AssertionError("Annual prediction indexes overlap")
    return combined, records, model_by_year


def smooth_by_listing(signal, alpha=0.25):
    groups = segment_keys(signal.index)
    return signal.groupby(groups, sort=False).transform(
        lambda values: values.ewm(alpha=alpha, adjust=False).mean()
    ).rename(signal.name)
