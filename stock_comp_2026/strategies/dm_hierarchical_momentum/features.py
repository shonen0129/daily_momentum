"""PIT33 self-inclusive common/within decomposition with fixed causal EWMA."""
from pathlib import Path
import numpy as np
import pandas as pd

try:
    from .primitives import raw_momentum, smooth, centered_rank
except ImportError:
    from primitives import raw_momentum, smooth, centered_rank

INPUT_COLUMNS = {
    "raw_return_1day": ["Return"], "beta_1day": ["Return"],
    "topix_return_1day": ["Return"], "listed_info": ["Sector33Code"],
}
CANDIDATES = {
    "HIER33_SECTOR": "Sector33Common_ewm",
    "HIER33_WITHIN": "Within33_ewm",
    "HIER33_COMBINED": "Combined",
}


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


def zscore(s):
    group = s.groupby("Date", sort=False)
    scale = group.transform("std")
    return ((s - group.transform("mean")) / scale.where(scale > 0)).fillna(0.)


def build_features(inputs):
    data = {n: canonical(inputs[n], panel=n != "topix_return_1day") for n in INPUT_COLUMNS}
    stock = raw_momentum(data)
    sector = data["listed_info"].reindex(stock.index).Sector33Code.astype("string")
    sector = sector.mask(sector.isin(["9999", "", "nan", "None"]))
    keys = [stock.index.get_level_values("Date"), sector]
    groups = stock.where(sector.notna()).groupby(keys, sort=False)
    count = groups.transform("count").astype(float)
    common = groups.transform("mean").where(count >= 5)
    within = stock - common
    f = pd.DataFrame({"StockMom60_raw": stock, "Sector33Code": sector,
                      "FiniteMembers": count, "Sector33Common_raw": common, "Within33_raw": within}, index=stock.index)
    f["Sector33Common_ewm"] = smooth(common.fillna(0.), .25)
    f["Within33_ewm"] = smooth(within.fillna(0.), .25)
    f["Z_sector"] = zscore(f.Sector33Common_ewm)
    f["Z_within"] = zscore(f.Within33_ewm)
    f["Combined"] = f.Z_sector + f.Z_within
    f["StockMom60_ewm_diagnostic"] = smooth(stock.fillna(0.), .25)
    f["NeutralDefect_raw"] = stock.fillna(0.) - common.fillna(0.) - within.fillna(0.)
    f["NeutralDefect_ewm"] = smooth(f.NeutralDefect_raw, .25)
    f["MOM60"] = smooth(centered_rank(stock), .25)
    return f


def score(features, candidate="HIER33_COMBINED"):
    if candidate not in CANDIDATES:
        raise ValueError(f"Unknown registered candidate: {candidate}")
    return features[CANDIDATES[candidate]].rename("Return")
