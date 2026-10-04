"""Raw Sector33 context operations, then one causal per-Code EWMA(.25)."""
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
CANDIDATES = {"SECTOR_CONFIRM": "Confirmed_ewm", "SHORT_DISAGREE_VETO": "ShortVeto_ewm"}


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


def context(stock, common):
    """Exact raw signs; missing context remains unavailable before neutralization."""
    finite = np.isfinite(stock) & np.isfinite(common)
    state = pd.Series("ZERO_OR_MISSING", index=stock.index, dtype="string")
    for name, condition in [("A", (stock > 0) & (common > 0)), ("B", (stock > 0) & (common < 0)),
                            ("C", (stock < 0) & (common > 0)), ("D", (stock < 0) & (common < 0))]:
        state.loc[finite & condition] = name
    confirmed = stock.where(state.isin(["A", "D"]), 0.)
    veto = stock.where(finite & ~((stock < 0) & (common > 0)), 0.)
    return state, confirmed, veto


def build_features(inputs):
    data = {n: canonical(inputs[n], panel=n != "topix_return_1day") for n in INPUT_COLUMNS}
    stock = raw_momentum(data)
    sector = data["listed_info"].reindex(stock.index).Sector33Code.astype("string")
    sector = sector.mask(sector.isin(["9999", "", "nan", "None"]))
    groups = stock.where(sector.notna()).groupby([stock.index.get_level_values("Date"), sector], sort=False)
    count = groups.transform("count").astype(float)
    common = groups.transform("mean").where(count >= 5)
    state, confirmed, veto = context(stock, common)
    f = pd.DataFrame({"StockMom60_raw": stock, "Sector33Code": sector, "FiniteMembers": count,
                      "Sector33Common_raw": common, "State": state,
                      "Confirmed_raw": confirmed, "ShortVeto_raw": veto}, index=stock.index)
    f["Confirmed_ewm"] = smooth(confirmed, .25)
    f["ShortVeto_ewm"] = smooth(veto, .25)
    f["MOM60"] = smooth(centered_rank(stock), .25)
    return f


def score(features, candidate="SHORT_DISAGREE_VETO"):
    if candidate not in CANDIDATES:
        raise ValueError(f"Unknown registered candidate: {candidate}")
    return features[CANDIDATES[candidate]].rename("Return")
