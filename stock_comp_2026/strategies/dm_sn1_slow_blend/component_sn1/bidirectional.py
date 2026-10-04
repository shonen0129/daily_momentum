"""Standalone high- and low-breakout Ridge scores for variable-box research."""
import json

import numpy as np
import pandas as pd

try:
    from . import features
except ImportError:
    import features


SIDES = ("high", "low")
TRIAL_ID = "BOX_BIDIR_STANDALONE"
RIDGE_LAMBDA = 1.0
MIN_TRAINING_ROWS = 500
DIRECTIONAL_COLUMNS = (
    "box_duration",
    "box_width_atr",
    "oriented_close_position",
    "oriented_relative_strength_60",
    "distance_to_prior_extreme",
)


def event_mask(x, side):
    if side == "high":
        return x["high_available"] & x["new_high_excess"].gt(0.0)
    if side == "low":
        return x["low_available"] & x["new_low_excess"].gt(0.0)
    raise ValueError(f"Unknown breakout side: {side}")


def directional_features(x, side):
    """Orient common box/context inputs so larger means closer to continuation."""
    if side not in SIDES:
        raise ValueError(f"Unknown breakout side: {side}")
    if side == "high":
        close_position = x["close_position"]
        relative_strength = x["relative_strength_60"]
        distance = x["distance_to_prior_high"]
    else:
        close_position = 1.0 - x["close_position"]
        relative_strength = -x["relative_strength_60"]
        distance = x[features.LOW_DISTANCE_COLUMN]
    result = pd.DataFrame(
        {
            "box_duration": x["box_duration"],
            "box_width_atr": x["box_width_atr"],
            "oriented_close_position": close_position,
            "oriented_relative_strength_60": relative_strength,
            "distance_to_prior_extreme": distance,
        },
        index=x.index,
    )
    return result.replace([np.inf, -np.inf], np.nan)


def centered_target_rank(target):
    values = pd.to_numeric(target, errors="coerce").replace([np.inf, -np.inf], np.nan)
    ranks = values.groupby(level="Date").rank(method="average", pct=True)
    center = ranks.groupby(level="Date").transform("mean")
    return (2.0 * (ranks - center)).rename("target_rank")


def fit_arrays(x, y, ridge_lambda=RIDGE_LAMBDA):
    matrix = np.asarray(x, dtype=float)
    labels = np.asarray(y, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] != len(DIRECTIONAL_COLUMNS) or len(matrix) != len(labels):
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
        "columns": list(DIRECTIONAL_COLUMNS),
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
    result = coefficients[0] + standardized @ coefficients[1:]
    if not np.isfinite(result).all():
        raise ValueError("Nonfinite Ridge prediction")
    return result


def fit_before(x, target, calendar, fold_start, side):
    if side not in SIDES:
        raise ValueError(f"Unknown breakout side: {side}")
    if not x.index.equals(target.index):
        raise ValueError("Feature and target indexes must match")
    calendar = pd.DatetimeIndex(calendar).sort_values().unique()
    dates = x.index.get_level_values("Date")
    start_position = calendar.searchsorted(pd.Timestamp(fold_start))
    mature_dates = calendar[:max(0, start_position - 2)]
    mature = dates.isin(mature_dates)
    target_rank = centered_target_rank(target)
    oriented_target = target_rank if side == "high" else -target_rank
    training = mature & event_mask(x, side).to_numpy() & oriented_target.notna().to_numpy()
    rows = int(training.sum())
    if rows < MIN_TRAINING_ROWS:
        raise ValueError(
            f"Too few mature {side}-breakout observations before {fold_start}: {rows} "
            f"(minimum {MIN_TRAINING_ROWS})"
        )
    matrix = directional_features(x.loc[training], side)
    model = fit_arrays(matrix, oriented_target.loc[training])
    used_dates = dates[training]
    last_signal = pd.Timestamp(used_dates.max())
    position = calendar.get_indexer([last_signal])[0]
    model.update({
        "side": side,
        "year": int(pd.Timestamp(fold_start).year),
        "training_dates": int(used_dates.nunique()),
        "min_training_signal": str(pd.Timestamp(used_dates.min()).date()),
        "max_training_signal": str(last_signal.date()),
        "max_label_maturity_date": str(calendar[min(position + 2, len(calendar) - 1)].date()),
    })
    return model, training


def predict_year(x, target, year, side):
    dates = x.index.get_level_values("Date")
    calendar = pd.DatetimeIndex(dates.unique().sort_values())
    model, training = fit_before(x, target, calendar, f"{year}-01-01", side)
    selected = (dates.year == year) & event_mask(x, side).to_numpy()
    matrix = directional_features(x.loc[selected], side)
    prediction = pd.Series(
        predict_matrix(matrix, model), index=matrix.index,
        name=f"{TRIAL_ID}_{side}", dtype=float,
    )
    return prediction, model, training


def walk_forward_predictions(x, target, years=range(2011, 2017), model_dir=None):
    predictions = {side: [] for side in SIDES}
    records = []
    for year in years:
        for side in SIDES:
            pred, model, _ = predict_year(x, target, year, side)
            predictions[side].append(pred)
            records.append({key: model[key] for key in (
                "side", "year", "training_rows", "training_dates", "min_training_signal",
                "max_training_signal", "max_label_maturity_date", "coefficients",
            )})
            if model_dir is not None:
                model_dir.mkdir(parents=True, exist_ok=True)
                (model_dir / f"RIDGE_{side}_{year}.json").write_text(
                    json.dumps(model, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8",
                )
    combined = {}
    for side, pieces in predictions.items():
        combined[side] = pd.concat(pieces).sort_index()
        if not combined[side].index.is_unique:
            raise AssertionError(f"{side} prediction indexes overlap")
    if combined["high"].index.intersection(combined["low"].index).size:
        raise AssertionError("A row cannot be both a high and low breakout")
    return combined, records


def active_percentile(values):
    ranks = values.groupby(level="Date").rank(method="average", pct=True)
    return (0.5 + 0.5 * ranks).fillna(0.5)


def generate_raw_signal(x, predictions):
    """Create standalone signed event scores; B00 is intentionally absent."""
    if set(predictions) != set(SIDES):
        raise ValueError("Both independent direction prediction series are required")
    result = pd.Series(0.0, index=x.index, name=TRIAL_ID)
    masks = {side: event_mask(x, side) for side in SIDES}
    if (masks["high"] & masks["low"]).any():
        raise AssertionError("High and low event masks overlap")
    for side, sign in (("high", 1.0), ("low", -1.0)):
        pred = predictions[side].reindex(x.index)
        active = masks[side] & pred.notna()
        result.loc[active] = sign * active_percentile(pred.loc[active])
    return result


def smooth_by_listing(signal, alpha=0.25):
    groups = features.segment_keys(signal.index)
    return signal.groupby(groups, sort=False).transform(
        lambda values: values.ewm(alpha=alpha, adjust=False).mean()
    ).rename(signal.name)


def generate_signal(x, predictions, alpha=0.25):
    return smooth_by_listing(generate_raw_signal(x, predictions), alpha=alpha)
