"""Fixed causal residual60 and same-date PIT leave-one-out peer components."""
from pathlib import Path

import numpy as np
import pandas as pd

INPUT_COLUMNS = {
    "raw_return_1day": ["Return"],
    "beta_1day": ["Return"],
    "topix_return_1day": ["Return"],
    "listed_info": ["Sector17Code", "Sector33Code"],
}
CANDIDATES = {
    "SECTOR17_MOM": "Sector17Mom",
    "SECTOR33_MOM": "Sector33Mom",
    "RELATIVE33_MOM": "Rel33Mom",
}


def canonical(frame, panel=True):
    expected = ["Date", "Code"] if panel else ["Date"]
    if frame.index.names != expected or not frame.index.is_unique:
        raise ValueError(f"Expected unique {expected} index")
    result = frame.copy()
    dates = pd.DatetimeIndex(frame.index.get_level_values("Date"))
    if dates.tz is not None:
        dates = dates.tz_convert("Asia/Tokyo").tz_localize(None)
    result.index = (pd.MultiIndex.from_arrays(
        [dates, frame.index.get_level_values("Code").astype(str)], names=expected)
        if panel else pd.DatetimeIndex(dates, name="Date"))
    if not result.index.is_unique:
        raise ValueError("Duplicate canonical index")
    return result.sort_index()


def load_train(directory):
    data = {name: pd.read_parquet(Path(directory) / f"{name}_train.parquet", columns=columns)
            for name, columns in INPUT_COLUMNS.items()}
    # Exact date/code projection, never add the broader listed-info universe.
    data["listed_info"] = canonical(data["listed_info"]).reindex(canonical(data["raw_return_1day"]).index)
    return data


def segment_keys(index):
    dates = index.get_level_values("Date")
    calendar = dates.unique().sort_values()
    ordinal = pd.Series(calendar.get_indexer(dates), index=index)
    code = index.get_level_values("Code")
    starts = ordinal.groupby(code, sort=False).diff().gt(20)
    segment = starts.groupby(code, sort=False).cumsum().astype(int)
    return [code, segment]


def peer_components(stock, sector, minimum):
    """Only finite, present peers with an observed classification contribute."""
    valid = stock.where(sector.notna())
    groups = valid.groupby([stock.index.get_level_values("Date"), sector], sort=False)
    total, count = groups.transform("sum"), groups.transform("count")
    own = valid.notna().astype(float)
    peers = count - own
    momentum = ((total - valid.fillna(0.0)) / peers.where(peers >= minimum))
    positive = valid.gt(0).astype(float).where(sector.notna())
    npositive = positive.groupby([stock.index.get_level_values("Date"), sector], sort=False).transform("sum")
    breadth = (npositive - valid.gt(0).astype(float)) / peers.where(peers >= minimum)
    return momentum.astype(float), peers.astype(float), breadth.astype(float)


def build_features(inputs):
    data = {name: canonical(inputs[name], panel=name != "topix_return_1day")
            for name in INPUT_COLUMNS}
    r = data["raw_return_1day"]["Return"].replace([np.inf, -np.inf], np.nan)
    index = r.index
    dates = index.get_level_values("Date")
    beta = data["beta_1day"]["Return"].reindex(index)
    market = pd.Series(data["topix_return_1day"]["Return"].reindex(dates).to_numpy(), index=index)
    residual = (r - beta * market).replace([np.inf, -np.inf], np.nan)
    groups = segment_keys(index)
    lagged = residual.groupby(groups, sort=False).shift(1)
    stock = lagged.groupby(groups, sort=False).transform(lambda v: v.rolling(60, min_periods=60).sum())
    listed = data["listed_info"].reindex(index)
    f = pd.DataFrame({"ResidualReturn": residual, "StockMom60": stock}, index=index)
    for level, minimum, unknown in [(17, 10, "99"), (33, 5, "9999")]:
        col = f"Sector{level}Code"
        sector = listed[col].astype("string")
        sector = sector.mask(sector.isin([unknown, "", "nan", "None"]))
        f[col] = sector
        mom, count, breadth = peer_components(stock, sector, minimum)
        f[f"Sector{level}Mom"] = mom
        f[f"Peer{level}Count"] = count
        f[f"Breadth{level}"] = breadth
        f[f"Rel{level}Mom"] = stock - mom
    return f


def score(features, candidate="SECTOR33_MOM"):
    if candidate not in CANDIDATES:
        raise ValueError(f"Unknown fixed candidate: {candidate}")
    return features[CANDIDATES[candidate]].fillna(0.0).rename("Return")
