"""PIT historical industry continuation and within-industry reversal."""
from pathlib import Path
import numpy as np
import pandas as pd
try:
    from .primitives import raw_momentum, centered_rank, smooth, segment_keys
except ImportError:
    from primitives import raw_momentum, centered_rank, smooth, segment_keys

INPUT_COLUMNS = {"raw_return_1day": ["Return"], "beta_1day": ["Return"],
                 "topix_return_1day": ["Return"], "listed_info": ["Sector17Code"]}
CANDIDATES = {"IND17_MOM_WITHIN_REV20": "IND17_MOM_WITHIN_REV20"}


def canonical(frame, panel=True):
    expected = ["Date", "Code"] if panel else ["Date"]
    if frame.index.names != expected or not frame.index.is_unique:
        raise ValueError(f"Expected unique {expected} index")
    result = frame.copy()
    dates = pd.DatetimeIndex(frame.index.get_level_values("Date"))
    if dates.tz is not None:
        dates = dates.tz_convert("Asia/Tokyo").tz_localize(None)
    result.index = (pd.MultiIndex.from_arrays([dates, frame.index.get_level_values("Code").astype(str)], names=expected)
                    if panel else pd.DatetimeIndex(dates, name="Date"))
    if not result.index.is_unique:
        raise ValueError("Duplicate canonical index")
    return result.sort_index()


def load_train(directory):
    data = {n: pd.read_parquet(Path(directory) / f"{n}_train.parquet", columns=c)
            for n, c in INPUT_COLUMNS.items()}
    data["listed_info"] = canonical(data["listed_info"]).reindex(canonical(data["raw_return_1day"]).index)
    return data


def residual_return(data):
    r = data["raw_return_1day"].Return.replace([np.inf, -np.inf], np.nan)
    dates = r.index.get_level_values("Date")
    beta = data["beta_1day"].Return.reindex(r.index)
    market = pd.Series(data["topix_return_1day"].Return.reindex(dates).to_numpy(), index=r.index)
    return (r - beta * market).replace([np.inf, -np.inf], np.nan).rename("ResidualReturn")


def long_series(wide):
    """Retain every value including NaN without version-dependent stack defaults."""
    index = pd.MultiIndex.from_product([wide.index, wide.columns], names=[wide.index.name, wide.columns.name])
    return pd.Series(wide.to_numpy().ravel(), index=index)


def industry_history(residual, sector):
    """Use membership on each historical date, retaining calendar gaps as NaN."""
    calendar = residual.index.get_level_values("Date").unique().sort_values()
    keys = [residual.index.get_level_values("Date"), sector]
    daily = residual.where(sector.notna()).groupby(keys, sort=True).agg(["mean", "count"])
    daily.index.names = ["Date", "Sector17Code"]
    daily["IndustryResidualReturn"] = daily["mean"].where(daily["count"] >= 5)
    wide = daily.IndustryResidualReturn.unstack("Sector17Code").reindex(calendar)
    momentum = wide.shift(1).rolling(20, min_periods=20).sum()
    daily["IndustryMom20"] = long_series(momentum).reindex(daily.index)
    return daily[["IndustryResidualReturn", "IndustryMom20", "count"]].rename(columns={"count": "FiniteMembers"})


def build_features(inputs, return_history=False):
    data = {n: canonical(inputs[n], panel=n != "topix_return_1day") for n in INPUT_COLUMNS}
    residual = residual_return(data)
    sector = data["listed_info"].reindex(residual.index).Sector17Code.astype("string").str.strip()
    sector = sector.mask(sector.isin(["9999", "", "nan", "None", "<NA>"]))
    history = industry_history(residual, sector)
    lookup = pd.MultiIndex.from_arrays([residual.index.get_level_values("Date"), sector], names=history.index.names)
    common = history.reindex(lookup)
    groups = segment_keys(residual.index)
    stock = residual.groupby(groups, sort=False).shift(1).groupby(groups, sort=False).transform(
        lambda v: v.rolling(20, min_periods=20).sum())
    f = pd.DataFrame({"ResidualReturn": residual, "Sector17Code": sector,
                      "StockMom20": stock}, index=residual.index)
    for name in common:
        f[name] = common[name].to_numpy(dtype=float)
    f["Within17Mom20"] = f.StockMom20 - f.IndustryMom20
    f["Within17Rev20"] = -f.Within17Mom20
    f["IndustryComponent"] = centered_rank(f.IndustryMom20)
    f["WithinReversalComponent"] = centered_rank(f.Within17Rev20)
    f["CombinedRaw"] = f.IndustryComponent + f.WithinReversalComponent
    f["IND17_MOM_WITHIN_REV20"] = smooth(centered_rank(f.CombinedRaw), .25)
    f["StockMom60_raw"] = raw_momentum(data)
    f["MOM60"] = smooth(centered_rank(f.StockMom60_raw), .25)
    return (f, history) if return_history else f


def score(features, candidate="IND17_MOM_WITHIN_REV20"):
    if candidate not in CANDIDATES:
        raise ValueError(f"Unknown registered candidate: {candidate}")
    return features[CANDIDATES[candidate]].rename("Return")
