"""Fit from explicitly supplied past labels; inference never loads labels."""
import warnings

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.preprocessing import StandardScaler

try:
    from . import features
except ImportError:
    import features


def available_until(index, cutoff, calendar):
    calendar = pd.DatetimeIndex(calendar).sort_values().unique()
    end = calendar.searchsorted(pd.Timestamp(cutoff), side="right") - 1
    if end < 2:
        return np.zeros(len(index), dtype=bool)
    return index.get_level_values("Date") <= calendar[end - 2]


def fit_model(x, y, family, strength, settings):
    if not x.index.equals(y.index):
        raise ValueError("Training feature/label index mismatch")
    if len(x) < 2 or not np.isfinite(x.to_numpy()).all() or not np.isfinite(y).all():
        raise ValueError("Training requires finite complete rows")
    if family not in ("ridge", "elasticnet") or strength <= 0:
        raise ValueError("Invalid model specification")
    if family == "elasticnet" and strength >= 1:
        raise ValueError("Relative alpha must be below the all-zero boundary")
    scaler = StandardScaler()
    z = scaler.fit_transform(x)
    y_values = y.to_numpy(dtype=float)
    y_mean = float(y_values.mean())
    n = len(z)
    ratio = settings["l1_ratio"]
    alpha_max = float(np.max(np.abs((z - z.mean(axis=0)).T @ (y_values - y_mean))) / n / ratio)
    if family == "ridge":
        alpha = float(n * strength)
        estimator = Ridge(alpha=alpha, solver="cholesky", fit_intercept=True)
    else:
        alpha = float(strength * alpha_max)
        estimator = ElasticNet(alpha=alpha, l1_ratio=ratio, fit_intercept=True, precompute=True,
                               max_iter=settings["elasticnet_max_iter"], tol=settings["elasticnet_tol"],
                               selection="cyclic")
    if alpha_max == 0:
        coef, intercept, iterations, dual_gap = np.zeros(x.shape[1]), y_mean, 0, 0.0
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("error", ConvergenceWarning)
            estimator.fit(z, y_values)
        coef = estimator.coef_
        intercept = float(estimator.intercept_)
        iterations = int(getattr(estimator, "n_iter_", 0) or 0)
        dual_gap = float(getattr(estimator, "dual_gap_", 0.0))
    return {"family": family, "strength": float(strength), "alpha": alpha,
            "alpha_max": alpha_max, "l1_ratio": ratio, "n_train": n,
            "columns": list(x.columns), "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
            "coef": coef.tolist(), "intercept": intercept, "null_intercept": y_mean,
            "nonzero_count": int(np.count_nonzero(coef)), "iterations": iterations, "dual_gap": dual_gap}


def predict_matrix(x, model):
    """Fixed feature order avoids BLAS batch-size-dependent prefix rounding."""
    if list(x.columns) != model["columns"]:
        raise ValueError("Prediction feature order mismatch")
    values = x.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Prediction matrix must be finite")
    result = np.full(len(x), model["intercept"], dtype=float)
    for j, coefficient in enumerate(model["coef"]):
        result += ((values[:, j] - model["mean"][j]) / model["scale"][j]) * coefficient
    return result


def predict_from_features(frame, bundle, smooth=True):
    if not frame.index.is_unique or not frame.index.is_monotonic_increasing:
        raise ValueError("Expected sorted unique prediction index")
    variant = bundle["variant"]
    columns = features.feature_columns(variant)
    available = frame[f"{variant}_available"]
    year_values = frame.index.get_level_values("Date").year
    raw = pd.Series(0.0, index=frame.index, name="Return")
    years = {int(year): model for year, model in bundle["models"].items()}
    for year in sorted(set(year_values)):
        if year < min(years):
            continue
        if year not in years:
            raise ValueError(f"No causal trained model for year {year}")
        take = (year_values == year) & available.to_numpy()
        raw.loc[take] = predict_matrix(frame.loc[take, columns], years[year])
    if smooth:
        raw = features.smooth_complete(raw, available, bundle["ewma_alpha"])
    if not np.isfinite(raw).all():
        raise ValueError("Nonfinite prediction")
    return raw
