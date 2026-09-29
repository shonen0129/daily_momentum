"""Fixed low-capacity annual LightGBM models with label-maturity purging."""
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_breakout_side_momentum.features import segment_keys


PARAMETERS = {
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
YEARS = (2010, 2011, 2012, 2013, 2014)


def fit_before(features, target, calendar, fold_start, parameters=None):
    """Fit only on labels whose signal dates precede the two-day purge."""
    if not features.index.equals(target.index):
        raise ValueError("Feature and target indexes must match exactly")
    dates = features.index.get_level_values("Date")
    start_position = calendar.searchsorted(pd.Timestamp(fold_start))
    eligible_dates = calendar[: max(0, start_position - 2)]
    target_values = pd.to_numeric(target, errors="coerce")
    available = target_values.notna() & np.isfinite(target_values.to_numpy())
    mask = dates.isin(eligible_dates) & available
    if mask.sum() < 10_000:
        raise ValueError(f"Too few mature Train labels before {fold_start}: {int(mask.sum())}")
    params = {**PARAMETERS, **(parameters or {})}
    model = lgb.LGBMRegressor(**params)
    model.fit(features.loc[mask], target_values.loc[mask])
    return model, mask


def predict_year(features, target, year, parameters=None, model_path=None):
    dates = features.index.get_level_values("Date")
    calendar = dates.unique().sort_values()
    start = f"{year}-01-01"
    model, training_mask = fit_before(features, target, calendar, start, parameters)
    if model_path is not None:
        model_path = Path(model_path)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model.booster_.save_model(str(model_path))
    selected = dates.year == year
    prediction = pd.Series(
        model.predict(features.loc[selected]), index=features.index[selected], name=f"LGBM_{year}"
    )
    used_dates = dates[training_mask]
    last_signal = used_dates.max()
    maturity_position = calendar.get_indexer([last_signal])[0] + 2
    max_label_maturity = calendar[min(maturity_position, len(calendar) - 1)]
    audit = {
        "year": int(year),
        "training_rows": int(training_mask.sum()),
        "training_dates": int(used_dates.nunique()),
        "min_training_signal": str(used_dates.min().date()),
        "max_training_signal": str(last_signal.date()),
        "max_label_maturity_date": str(max_label_maturity.date()),
        "fold_start": start,
        "feature_names": list(features.columns),
        "importance_gain": model.booster_.feature_importance(importance_type="gain").tolist(),
        "importance_split": model.booster_.feature_importance(importance_type="split").tolist(),
        "parameters": {key: value for key, value in PARAMETERS.items()},
    }
    return prediction, audit


def walk_forward_predictions(features, target, years=YEARS, model_dir=None):
    pieces, audits = [], []
    for year in years:
        path = None if model_dir is None else model_dir / f"LGBM_{year}.txt"
        prediction, audit = predict_year(features, target, year, model_path=path)
        pieces.append(prediction)
        audits.append(audit)
    combined = pd.concat(pieces).sort_index()
    if not combined.index.is_unique:
        raise AssertionError("Walk-forward predictions overlap")
    return combined, audits


def smooth_by_listing(signal, alpha=0.25):
    groups = segment_keys(signal.index)
    return signal.groupby(groups, sort=False).transform(
        lambda values: values.ewm(alpha=alpha, adjust=False).mean()
    ).rename(signal.name)
