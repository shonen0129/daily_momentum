"""Causal I1/K1 features with the C0/T1 Long book held exactly fixed."""
from pathlib import Path

import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_fixed_long_short import core
from stock_comp_2026.strategies.dm_fixed_long_short import features as champion


PRICE_COLUMNS = ["Open", "Close"]


def load_inputs(directory, split="train"):
    """Load only Train-safe inputs; no labels are read here."""
    result = champion.load_inputs(directory, split)
    prices = pd.read_parquet(
        Path(directory) / f"prices_daily_quotes_{split}.parquet", columns=PRICE_COLUMNS
    ).sort_index()
    if not prices.index.is_unique:
        raise ValueError("duplicate prices index")
    result["prices_daily_quotes"] = prices
    return result


def _daily_percentile(value, neutral=0.5):
    return value.replace([np.inf, -np.inf], np.nan).groupby(level="Date").rank(
        method="average", pct=True
    ).fillna(neutral)


def _residual_return(inputs):
    raw = inputs["raw_return_1day"]["Return"].sort_index().replace([np.inf, -np.inf], np.nan)
    beta = inputs["beta_1day"]["Return"].reindex(raw.index)
    dates = raw.index.get_level_values("Date")
    market = pd.Series(inputs["topix_return_1day"]["Return"].reindex(dates).to_numpy(), index=raw.index)
    return (raw - beta * market).replace([np.inf, -np.inf], np.nan)


def intraday_features(inputs):
    """Use t's raw open/close and no future rows; unavailable observations are neutral."""
    price = inputs["prices_daily_quotes"].sort_index()
    opened, closed = price["Open"], price["Close"]
    intraday = (closed / opened - 1.0).where(
        opened.notna() & closed.notna() & (opened > 0) & (closed > 0)
    ).replace([np.inf, -np.inf], np.nan)
    groups = core.segment_keys(intraday.index)
    day_mom = intraday.groupby(groups, sort=False).transform(
        lambda x: x.rolling(60, min_periods=60).sum()
    )
    day_rank = 2.0 * _daily_percentile(day_mom) - 1.0
    # Missing history remains a neutral instantaneous rank before causal smoothing.
    day_rank = day_rank.where(day_mom.notna(), 0.0)
    smoothed = core.smooth(day_rank, .25)
    return pd.DataFrame(
        {"intraday_return": intraday, "daymom60": day_mom, "daymom60_rank": day_rank,
         "intraday_short_risk": (-smoothed).replace([np.inf, -np.inf], 0.0)},
        index=price.index,
    )


def _sample_skewness(values):
    values = np.asarray(values, dtype=float)
    if len(values) < 15:
        return np.nan
    centered = values - values.mean()
    scale = centered.std(ddof=1)
    return float(np.mean(centered ** 3) / scale ** 3) if np.isfinite(scale) and scale > 0 else np.nan


def _monthly_statistics(residual):
    """End-of-month characteristics, reset at a code-reuse segment boundary."""
    frame = residual.rename("residual").reset_index()
    frame["segment"] = np.asarray(core.segment_keys(residual.index)[1])
    frame["month"] = frame["Date"].dt.to_period("M")
    rows = []
    for (code, segment, month), block in frame.groupby(["Code", "segment", "month"], sort=True, observed=True):
        value = block.residual.dropna().to_numpy(dtype=float)
        rows.append({"Code": code, "segment": int(segment), "month": month,
                     "observations": int(len(value)), "realized_skewness": _sample_skewness(value),
                     "realized_volatility": float(np.std(value, ddof=1)) if len(value) >= 15 else np.nan,
                     "prior_month_residual_return": float(np.sum(value)) if len(value) >= 15 else np.nan,
                     "source_max_date": block.Date.max()})
    result = pd.DataFrame(rows).sort_values(["Code", "segment", "month"])
    grouped = result.groupby(["Code", "segment"], sort=False)["prior_month_residual_return"]
    # At month m use returns from m-12 through m-2 (eleven fixed calendar months).
    result["mom12_1"] = grouped.transform(
        lambda x: x.shift(2).rolling(11, min_periods=11).sum()
    )
    return result


PREDICTORS = ["realized_skewness", "realized_volatility", "prior_month_residual_return", "mom12_1"]


def expected_skewness(residual):
    """Forecast month m+1 from a regression estimated with data available by m end."""
    monthly = _monthly_statistics(residual)
    monthly = monthly.sort_values(["Code", "segment", "month"]).copy()
    shifted = monthly.groupby(["Code", "segment"], sort=False)[PREDICTORS].shift(1)
    shifted.columns = [f"lag_{name}" for name in PREDICTORS]
    monthly = pd.concat([monthly.reset_index(drop=True), shifted.reset_index(drop=True)], axis=1)
    forecasts, coeffs = [], []
    for month, current in monthly.groupby("month", sort=True, observed=True):
        fit_columns = ["realized_skewness", *[f"lag_{name}" for name in PREDICTORS]]
        fit = current.dropna(subset=fit_columns)
        forecast_month = month + 1
        forecast = current[["Code", "segment"]].copy()
        forecast["forecast_month"] = forecast_month
        forecast["expected_skewness"] = np.nan
        valid_fit = len(fit) >= 6
        if valid_fit:
            design = np.column_stack([np.ones(len(fit)), fit[[f"lag_{name}" for name in PREDICTORS]].to_numpy(float)])
            # Deterministic fallback: do not produce a forecast from rank-deficient data.
            valid_fit = np.linalg.matrix_rank(design) == design.shape[1]
        if valid_fit:
            beta, _, _, _ = np.linalg.lstsq(design, fit["realized_skewness"].to_numpy(float), rcond=None)
            current_x = current[PREDICTORS].to_numpy(float)
            usable = np.isfinite(current_x).all(axis=1)
            forecast.loc[usable, "expected_skewness"] = np.column_stack(
                [np.ones(usable.sum()), current_x[usable]]
            ) @ beta
            for name, value in zip(["intercept", *PREDICTORS], beta):
                coeffs.append({"estimation_month": str(month), "forecast_month": str(forecast_month),
                               "coefficient": name, "value": float(value), "fit_rows": int(len(fit)),
                               "rank_full": True})
        else:
            coeffs.append({"estimation_month": str(month), "forecast_month": str(forecast_month),
                           "coefficient": "intercept", "value": np.nan, "fit_rows": int(len(fit)),
                           "rank_full": False})
        source_max = current.source_max_date.max()
        forecast["estimation_month"] = month
        forecast["characteristic_max_date"] = source_max
        forecast["realized_skewness_target_max_date"] = source_max
        forecasts.append(forecast)
    return pd.concat(forecasts, ignore_index=True), monthly, pd.DataFrame(coeffs)


def build_features(inputs):
    """Champion features plus exactly the preregistered I1 and K1 columns."""
    base = champion.build_features(inputs)
    intra = intraday_features(inputs).reindex(base.index)
    residual = _residual_return(inputs).reindex(base.index)
    forecast, monthly, coefficients = expected_skewness(residual)
    dates = base.index.get_level_values("Date")
    lookup = base.index.to_frame(index=False)
    lookup["segment"] = np.asarray(core.segment_keys(base.index)[1])
    lookup["forecast_month"] = lookup.Date.dt.to_period("M")
    merged = lookup.merge(
        forecast[["Code", "segment", "forecast_month", "expected_skewness"]],
        on=["Code", "segment", "forecast_month"], how="left", validate="many_to_one", sort=False,
    )
    expected = pd.Series(merged.expected_skewness.to_numpy(), index=base.index)
    skew_rank = _daily_percentile(expected, neutral=np.nan)
    low_skew = (1.0 - skew_rank).where(expected.notna(), 0.5)
    fd_rank = _daily_percentile(base.fd_equal)
    result = base.join(intra, validate="one_to_one")
    result["residual_return"] = residual
    result["expected_skewness"] = expected
    result["expected_skew_rank"] = skew_rank.fillna(0.5)
    result["low_skew_preference"] = low_skew
    result["fd_rank"] = fd_rank
    result["k1_short_risk"] = fd_rank * low_skew
    result.attrs.update(base.attrs)
    result.attrs["monthly_statistics"] = monthly
    result.attrs["expected_skewness_forecasts"] = forecast
    result.attrs["skewness_coefficients"] = coefficients
    return result


def _stitch_day(day, risk):
    """Identical Long ordering/membership to C0/T1; only the residual 60% is reordered."""
    n = len(day)
    long_rank = day.L.rank(method="first").astype(int)
    neutral_max = int(np.floor(.6 * (n - 1) + 1))
    short_max = int(np.floor(.4 * (n - 1) + 1))
    long_mask = long_rank > neutral_max
    final_rank = pd.Series(index=day.index, dtype=float)
    final_rank[long_mask] = long_rank[long_mask]
    remainder = day.loc[~long_mask]
    order = np.lexsort((remainder.index.get_level_values("Code").astype(str).to_numpy(),
                        long_rank.loc[~long_mask].to_numpy(), -remainder[risk].to_numpy()))
    final_rank[remainder.index[order[:short_max]]] = np.arange(1, short_max + 1)
    final_rank[remainder.index[order[short_max:]]] = np.arange(short_max + 1, neutral_max + 1)
    return (final_rank - 1.0) / (n - 1.0)


def predict_from_features(features, spec):
    trial = spec["trial_id"]
    if trial == "H0":
        score = champion.predict_from_features(features, {"trial_id": "T1"})
    elif trial == "I1":
        score = features.groupby(level="Date", group_keys=False).apply(_stitch_day, risk="intraday_short_risk")
    elif trial == "K1":
        score = features.groupby(level="Date", group_keys=False).apply(_stitch_day, risk="k1_short_risk")
    else:
        raise ValueError(f"unknown trial: {trial}")
    if not score.index.is_unique or not np.isfinite(score).all():
        raise ValueError("prediction contract failure")
    # Feature attrs carry audit tables; a score is a plain, serializable contract object.
    score.attrs = {}
    return score.rename("Return")
