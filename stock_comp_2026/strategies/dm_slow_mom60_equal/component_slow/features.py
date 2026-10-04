"""Label-free PIT factors; every cross-sectional operation uses one signal date."""
from pathlib import Path

import numpy as np
import pandas as pd

SHARES = "NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock"
FINS_COLUMNS = ["Equity", "TotalAssets", "Profit", "CashFlowsFromOperatingActivities",
                "ForecastEarningsPerShare", SHARES]
INPUT_COLUMNS = {
    "prices_daily_quotes": ["Close", "TurnoverValue"],
    "raw_return_1day": ["Return"],
    "fins_statements": FINS_COLUMNS,
    "listed_info": ["Sector17Code"],
}
FACTOR_NAMES = ["size", "amihud", "cf_assets", "roe", "equity_assets", "bp", "ey"]
BLOCK_NAMES = ["size_liquidity", "quality", "value"]
WINDOW, MIN_PERIODS, SECTOR_MIN = 60, 40, 20


def load_train(directory):
    return {name: pd.read_parquet(Path(directory) / f"{name}_train.parquet", columns=cols)
            for name, cols in INPUT_COLUMNS.items()}


def canonical(frame):
    if frame.index.names != ["Date", "Code"] or not frame.index.is_unique:
        raise ValueError("Expected unique Date/Code index")
    result = frame.copy()
    dates = pd.DatetimeIndex(result.index.get_level_values("Date"))
    if dates.tz is not None:
        dates = dates.tz_convert("Asia/Tokyo").tz_localize(None)
    result.index = pd.MultiIndex.from_arrays(
        [dates, result.index.get_level_values("Code").astype(str)], names=["Date", "Code"])
    if not result.index.is_unique:
        raise ValueError("Duplicate canonical Date/Code index")
    return result.sort_index()


def finite(values):
    return values.replace([np.inf, -np.inf], np.nan).astype("float64")


def zscore(values):
    values = finite(values)
    groups = values.groupby(level="Date", sort=False)
    mean, scale = groups.transform("mean"), groups.transform("std")
    return ((values - mean) / scale.where(scale > 0)).fillna(0.0)


def group_quantile_bounds(values, keys):
    """Vectorized NumPy linear quantiles with Series.quantile's exact lerp.

    NumPy chooses the upper-end interpolation formula for fractions >= .5.
    Keeping that choice also preserves its last-bit rounding, unlike pandas'
    Cython group quantile implementation. Empty groups remain missing.
    """
    groups = values.groupby(keys, sort=False)
    codes = groups.ngroup().to_numpy(dtype=int)
    good = values.notna().to_numpy()
    vals, valid_codes = values.to_numpy()[good], codes[good]
    if not len(vals):
        missing = pd.Series(np.nan, index=values.index)
        return missing, missing.copy()
    order = np.lexsort((vals, valid_codes))
    sorted_values = vals[order]
    counts = np.bincount(valid_codes, minlength=groups.ngroups)
    offset = np.cumsum(counts) - counts
    bounds = []
    for quantile in (.01, .99):
        virtual = (counts - 1) * quantile
        lower = np.maximum(0, np.floor(virtual).astype(int))
        fraction = virtual - lower
        left_index = np.minimum(offset + lower, len(vals) - 1)
        right_index = np.minimum(offset + np.minimum(lower + 1, np.maximum(0, counts - 1)), len(vals) - 1)
        left, right = sorted_values[left_index], sorted_values[right_index]
        difference = right - left
        result = left + difference * fraction
        np.subtract(right, difference * (1 - fraction), out=result, where=fraction >= .5)
        result[counts == 0] = np.nan
        bounds.append(pd.Series(result[codes], index=values.index))
    return bounds


def normalize(values, sectors=None):
    """Raw 1/99 winsorization, same-date median, then sample-standardization."""
    values = finite(values)

    def transform(keys):
        low, high = group_quantile_bounds(values, keys)
        clipped = values.clip(lower=low, upper=high)
        groups = clipped.groupby(keys, sort=False)
        filled = clipped.fillna(groups.transform("median")).fillna(0.0)
        groups = filled.groupby(keys, sort=False)
        scale = groups.transform("std")
        return ((filled - groups.transform("mean")) / scale.where(scale > 0)).fillna(0.0)

    global_result = transform(values.index.get_level_values("Date"))
    if sectors is None:
        return global_result
    keys = [values.index.get_level_values("Date"), sectors.fillna("unknown").astype(str)]
    count = values.groupby(keys, sort=False).transform("count")
    local_result = transform(keys)
    return local_result.where((count >= SECTOR_MIN) & sectors.notna(), global_result)


def asof_financials(index, fins):
    """Date-only disclosures become available at that day's end in JST.

    Per-field carry uses only previously disclosed finite observations. EPS
    revision uses the preceding actual observation, including unchanged values.
    """
    fins = canonical(fins)
    events = fins.reset_index()
    events["available_at"] = events["Date"].dt.normalize() + pd.Timedelta("23:59:59")
    events[FINS_COLUMNS] = events[FINS_COLUMNS].apply(pd.to_numeric, errors="coerce")
    events[FINS_COLUMNS] = events[FINS_COLUMNS].replace([np.inf, -np.inf], np.nan)
    events[SHARES] = events[SHARES].where(events[SHARES] > 0)
    eps = events.dropna(subset=["ForecastEarningsPerShare"])
    previous = eps.groupby("Code", sort=False)["ForecastEarningsPerShare"].shift(1)
    events["eps_revision"] = np.nan
    events.loc[eps.index, "eps_revision"] = eps["ForecastEarningsPerShare"] - previous
    columns = FINS_COLUMNS + ["eps_revision"]
    events[columns] = events.groupby("Code", sort=False)[columns].ffill()
    base = index.to_frame(index=False)
    base["signal_at"] = base["Date"].dt.normalize() + pd.Timedelta("23:59:59")
    base["position"] = np.arange(len(base))
    if events.empty:
        return pd.DataFrame(np.nan, index=index, columns=columns)
    joined = pd.merge_asof(
        base.sort_values("signal_at", kind="stable"),
        events.sort_values("available_at", kind="stable"),
        by="Code", left_on="signal_at", right_on="available_at",
        direction="backward", allow_exact_matches=True,
    ).sort_values("position")
    return pd.DataFrame(joined[columns].to_numpy(dtype=float), index=index, columns=columns)


def raw_factors(inputs):
    r = canonical(inputs["raw_return_1day"])
    index = r.index
    p = canonical(inputs["prices_daily_quotes"]).reindex(index)
    listed = canonical(inputs["listed_info"]).reindex(index)
    f = asof_financials(index, inputs["fins_statements"])
    close = finite(p["Close"]).where(p["Close"] > 0)
    shares = f[SHARES].where(f[SHARES] > 0)
    assets = f["TotalAssets"].where(f["TotalAssets"] > 0)
    equity = f["Equity"]
    turnover = finite(p["TurnoverValue"]).where(p["TurnoverValue"] > 0)
    ratio = finite(r["Return"]).abs() / turnover
    # Full exchange-date grid: an absent date is not silently skipped.
    grid = ratio.unstack("Code")
    illiq = grid.rolling(WINDOW, min_periods=MIN_PERIODS).mean()
    illiq = illiq.stack(future_stack=True).reindex(index)
    raw = pd.DataFrame({
        "size": -np.log(close * shares), "amihud": illiq,
        "cf_assets": f["CashFlowsFromOperatingActivities"] / assets,
        "roe": f["Profit"] / equity.where(equity > 0),
        "equity_assets": equity / assets,
        "bp": equity / shares / close,
        "ey": f["ForecastEarningsPerShare"] / close,
        "eps_revision_yield": f["eps_revision"] / close,
    }, index=index).replace([np.inf, -np.inf], np.nan)
    return raw, listed["Sector17Code"]


def build_features(inputs, sector=False):
    raw, sectors = raw_factors(inputs)
    normalized = {}
    for name in FACTOR_NAMES:
        by_sector = sectors if sector and name not in ("size", "amihud") else None
        normalized[name] = normalize(raw[name], by_sector)
    z = pd.DataFrame(normalized, index=raw.index)
    blocks = pd.DataFrame({
        "size_liquidity": zscore(z[["size", "amihud"]].mean(axis=1)),
        "quality": zscore(z[["cf_assets", "roe", "equity_assets"]].mean(axis=1)),
        "value": zscore(z[["bp", "ey"]].mean(axis=1)),
        "revision": zscore(normalize(raw["eps_revision_yield"])),
    }, index=raw.index)
    return pd.concat([raw.add_prefix("raw_"), z.add_prefix("z_"), blocks], axis=1)


def score(features, revision=False):
    columns = BLOCK_NAMES + (["revision"] if revision else [])
    return features[columns].sum(axis=1).rename("Return")
