"""Annual expanding OLS on immutable ranks and strictly mature Train labels."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

RANK_COLUMNS = ["SizeRank", "IlliquidityRank", "MOM60Rank"]
FIRST_MODEL_YEAR = 2009


def validate(x):
    if x.index.names != ["Date", "Code"] or not x.index.is_unique or not x.index.is_monotonic_increasing:
        raise ValueError("Expected unique sorted Date/Code feature index")
    if list(x.columns) != RANK_COLUMNS or not np.isfinite(x.to_numpy()).all():
        raise ValueError("Expected three finite immutable ranks")


def fit_year(x, target, year):
    validate(x)
    if not target.index.equals(x.index):
        raise ValueError("Train label index must match features exactly")
    dates = x.index.get_level_values("Date")
    calendar = dates.unique().sort_values()
    fold_dates = calendar[calendar.year == year]
    if len(fold_dates) == 0:
        raise ValueError("No prediction sessions in model year")
    start = fold_dates[0]
    position = calendar.get_loc(start)
    # Strictly before the first prediction open: label ending at t+2.
    mature_signal_dates = calendar[:max(0, position - 2)]
    train = dates.isin(mature_signal_dates) & np.isfinite(target.to_numpy())
    if train.sum() < 4:
        raise ValueError("Insufficient mature Train labels")
    design = np.column_stack([np.ones(int(train.sum())), x.loc[train].to_numpy(dtype="float64")])
    y = target.loc[train].to_numpy(dtype="float64")
    coefficients, residuals, rank, singular = np.linalg.lstsq(design, y, rcond=None)
    used = dates[train].unique().sort_values()
    end = calendar[calendar.get_loc(used[-1]) + 2]
    if not end < start:
        raise AssertionError("Immature training label")
    return {"year": int(year), "fold_start": str(start.date()), "columns": RANK_COLUMNS,
            "coefficients": coefficients.tolist(), "rows": int(train.sum()),
            "training_sessions": len(used), "first_training_signal": str(used[0].date()),
            "last_training_signal": str(used[-1].date()), "max_label_maturity_date": str(end.date()),
            "maturity_strictly_before_prediction": True, "design_rank": int(rank),
            "singular_values": singular.tolist(),
            "condition_number": float(singular[0] / singular[-1]) if singular[-1] > 0 else None,
            "training_mse": float(np.mean((y - design @ coefficients) ** 2)),
            "estimator": "OLS numpy.linalg.lstsq(rcond=None), equal stock-day weights, intercept, raw residual target",
            "regularization": None, "fit_once_per_year": True}


def apply_year(x, model):
    validate(x)
    coef = np.asarray(model["coefficients"], dtype="float64")
    if model["columns"] != RANK_COLUMNS or coef.shape != (4,) or not np.isfinite(coef).all():
        raise ValueError("Invalid OLS artifact")
    if not pd.Timestamp(model["max_label_maturity_date"]) < pd.Timestamp(model["fold_start"]):
        raise ValueError("Immature model artifact")
    # Fixed arithmetic per row; invariant to the number/order of other years.
    return pd.Series(coef[0] + x.SizeRank.to_numpy() * coef[1]
                     + x.IlliquidityRank.to_numpy() * coef[2] + x.MOM60Rank.to_numpy() * coef[3],
                     index=x.index, name="Return")


def walk_forward(x, target, years=range(FIRST_MODEL_YEAR, 2017), model_dir=None):
    validate(x)
    output = pd.Series(0., index=x.index, name="Return")
    dates = x.index.get_level_values("Date")
    records = []
    for year in years:
        mask = dates.year == year
        if not mask.any():
            continue
        model = fit_year(x, target, year)
        output.loc[mask] = apply_year(x.loc[mask], model)
        records.append(model)
        if model_dir is not None:
            path = Path(model_dir)
            path.mkdir(parents=True, exist_ok=True)
            (path / f"OLS_{year}.json").write_text(json.dumps(model, indent=2, allow_nan=False) + "\n")
    return output, records


def predict_artifacts(x, model_dir):
    validate(x)
    output = pd.Series(0., index=x.index, name="Return")
    dates = x.index.get_level_values("Date")
    for year in sorted(set(dates.year)):
        if year < FIRST_MODEL_YEAR:
            continue  # Initial 2008 feature history has no available annual model.
        path = Path(model_dir) / f"OLS_{year}.json"
        if not path.is_file():
            raise ValueError(f"Missing annual model {year}")
        model = json.loads(path.read_text())
        if model["year"] != year:
            raise ValueError("Model-year mismatch")
        mask = dates.year == year
        if (dates[mask] < pd.Timestamp(model["fold_start"])).any():
            raise ValueError("Model not available at prediction date")
        output.loc[mask] = apply_year(x.loc[mask], model)
    return output
