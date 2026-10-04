"""Unchanged MOM60 final score with two fixed, unsmoothed Short-context vetoes."""
from pathlib import Path
import numpy as np
import pandas as pd
try:
    from .primitives import raw_momentum, centered_rank, smooth
except ImportError:
    from primitives import raw_momentum, centered_rank, smooth

INPUT_COLUMNS = {
    "raw_return_1day": ["Return"], "beta_1day": ["Return"],
    "topix_return_1day": ["Return"], "listed_info": ["Sector33Code", "Sector17Code"],
}
CANDIDATES = ("BASELINE_SECTOR33_VETO", "BASELINE_HIER_SECTOR_VETO")
MIN_MEMBERS = {33: 5, 17: 10}


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


def sector_context(momentum, sector, minimum):
    """Historical-date PIT members, inclusive equal mean of finite stock Momentum."""
    finite = momentum.replace([np.inf, -np.inf], np.nan).where(sector.notna())
    groups = finite.groupby([momentum.index.get_level_values("Date"), sector], sort=True)
    count = groups.transform("count").astype(float)
    return groups.transform("mean").where(count >= minimum), count


def apply_veto(baseline, context):
    # A missing context preserves the baseline, including its EWMA memory.
    return baseline.mask(baseline.lt(0) & np.isfinite(context) & context.gt(0), 0.)


def build_features(inputs):
    data = {n: canonical(inputs[n], panel=n != "topix_return_1day") for n in INPUT_COLUMNS}
    stock = raw_momentum(data)
    baseline = smooth(centered_rank(stock), .25)
    f = pd.DataFrame({"StockMom60_raw": stock, "BASELINE": baseline}, index=stock.index)
    listed = data["listed_info"].reindex(stock.index)
    for level in [33, 17]:
        key = f"Sector{level}Code"
        sector = listed[key].astype("string").str.strip()
        sector = sector.mask(sector.isin(["99", "9999", "", "nan", "None", "<NA>"]))
        f[key] = sector
        common, count = sector_context(stock, sector, MIN_MEMBERS[level])
        f[f"SECTOR{level}_MOM"] = common
        f[f"FiniteMembers{level}"] = count
    available33 = np.isfinite(f.SECTOR33_MOM)
    available17 = np.isfinite(f.SECTOR17_MOM)
    f["ContextSource"] = pd.Series("UNAVAILABLE", index=f.index, dtype="string")
    f.loc[available33, "ContextSource"] = "SECTOR33"
    f.loc[~available33 & available17, "ContextSource"] = "SECTOR17_FALLBACK"
    f["HIER_SECTOR_MOM"] = f.SECTOR33_MOM.where(available33, f.SECTOR17_MOM)
    f[CANDIDATES[0]] = apply_veto(baseline, f.SECTOR33_MOM)
    f[CANDIDATES[1]] = apply_veto(baseline, f.HIER_SECTOR_MOM)
    return f


def score(features, candidate="BASELINE_HIER_SECTOR_VETO"):
    if candidate not in CANDIDATES:
        raise ValueError(f"Unknown fixed candidate: {candidate}")
    return features[candidate].rename("Return")
