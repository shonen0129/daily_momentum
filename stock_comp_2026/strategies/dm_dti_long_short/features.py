"""Causal Daily Turnover Information features; never reads labels."""
from pathlib import Path

import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_fixed_long_short import core
from stock_comp_2026.strategies.dm_independent_short import features as financial


WINDOW = 21
SHARES = "NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock"
INPUT_COLUMNS = {
    "prices_daily_quotes": ["Volume"],
    "fins_statements": financial.FINS_COLUMNS,
}


def load_inputs(directory, split="train"):
    """Load the raw-volume and disclosure inputs needed for a PIT denominator."""
    if split not in ("train", "valid"):
        raise ValueError("Unknown feature split")
    root = Path(directory)
    result = {}
    for name, columns in INPUT_COLUMNS.items():
        frame = pd.read_parquet(root / f"{name}_{split}.parquet", columns=columns).sort_index()
        if not frame.index.is_unique:
            raise ValueError(f"Duplicate index in {name}")
        result[name] = frame
    return result


def disclosed_shares(index, fins):
    """Latest strictly-prior valid filing's issued-share count, expiring after 450 days."""
    base = index.to_frame(index=False)
    base["segment"] = np.asarray(core.segment_keys(index)[1])
    raw = fins.reset_index().copy()
    raw["Date"] = pd.to_datetime(raw.Date).dt.tz_localize(None).dt.normalize()
    raw["Code"] = raw.Code.astype(str)
    raw[SHARES] = pd.to_numeric(raw[SHARES], errors="coerce")
    by_code = {key: value.sort_values(["Date", "DisclosureNumber"])
               for key, value in raw.groupby("Code", observed=True)}
    blocks, audit = [], {"disclosures": int(len(raw)), "valid_reports": 0, "share_updates": 0}
    for (code, segment), daily in base.groupby(["Code", "segment"], sort=False):
        history = by_code.get(str(code), raw.iloc[:0])
        if segment > 0:
            history = history.loc[history.Date >= daily.Date.iloc[0]]
        history = history.loc[history.Date < daily.Date.iloc[-1]]
        snapshots = []
        for row in history.to_dict("records"):
            period, document = str(row["TypeOfCurrentPeriod"]), str(row["TypeOfDocument"])
            shares = row[SHARES]
            if period not in financial.champion.PERIODS or "FinancialStatements_" not in document:
                continue
            audit["valid_reports"] += 1
            if np.isfinite(shares) and shares > 0:
                snapshots.append({"disclosed": row["Date"], "shares": float(shares)})
                audit["share_updates"] += 1
        if snapshots:
            state = pd.DataFrame(snapshots).drop_duplicates("disclosed", keep="last").sort_values("disclosed")
            joined = pd.merge_asof(daily.sort_values("Date"), state, left_on="Date", right_on="disclosed",
                                   direction="backward", allow_exact_matches=False)
        else:
            joined = daily.copy()
            joined["shares"], joined["disclosed"] = np.nan, pd.NaT
        blocks.append(joined)
    state = pd.concat(blocks).set_index(["Date", "Code"]).reindex(index)
    date = pd.Series(index.get_level_values("Date"), index=index)
    disclosure = pd.to_datetime(state["disclosed"])
    age = (date - disclosure).dt.days
    shares = state["shares"].where(age.between(0, 450) & state["shares"].gt(0))
    shares.attrs["share_audit"] = audit
    return shares.rename("shares"), disclosure.rename("shares_disclosure_date"), age.rename("shares_age_days")


def turnover_rate(inputs):
    """Raw daily traded shares divided by the last disclosed issued-share count."""
    price = inputs["prices_daily_quotes"]
    volume = pd.to_numeric(price["Volume"], errors="coerce").where(lambda x: x > 0)
    shares, disclosure, age = disclosed_shares(price.index, inputs["fins_statements"])
    turnover = (volume / shares).replace([np.inf, -np.inf], np.nan).rename("turnover_rate")
    data = pd.concat([turnover, volume.rename("volume"), shares, disclosure, age], axis=1)
    data.attrs["share_audit"] = getattr(shares, "attrs", {}).get("share_audit", {})
    return data


def dti_vector(turnover):
    """Chronological and ascending 21-observation vectors with no future fill."""
    values = turnover.sort_index().replace([np.inf, -np.inf], np.nan)
    groups = core.segment_keys(values.index)
    pieces, current = [], values
    for lag in range(WINDOW):
        pieces.append(current.rename(f"to_time_lag_{lag}"))
        current = current.groupby(groups, sort=False).shift()
    chronological = pd.concat(pieces, axis=1)
    available = chronological.notna().all(axis=1)
    ordered = np.full((len(chronological), WINDOW), np.nan, dtype=float)
    ordered[available.to_numpy()] = np.sort(chronological.loc[available].to_numpy(dtype=float), axis=1)
    sorted_vector = pd.DataFrame(ordered, index=chronological.index,
                                 columns=[f"to_sorted_{rank}" for rank in range(1, WINDOW + 1)])
    return chronological.join(sorted_vector), available.rename("available")


def feature_columns():
    return [f"to_time_lag_{lag}" for lag in range(WINDOW)] + [f"to_sorted_{rank}" for rank in range(1, WINDOW + 1)]


def build_features(inputs):
    turnover = turnover_rate(inputs)
    vector, available = dti_vector(turnover.turnover_rate)
    result = turnover.join(vector, validate="one_to_one").join(available, validate="one_to_one")
    result["mean_to21"] = result[feature_columns()[:WINDOW]].mean(axis=1).where(result.available)
    return result


def smooth_complete(score, available, alpha):
    """EWMA inside each listing segment; an incomplete current vector stays neutral."""
    source = score.where(available)
    output = source.groupby(core.segment_keys(score.index), sort=False).transform(
        lambda value: value.ewm(alpha=alpha, adjust=False).mean())
    return output.where(available, 0.0).fillna(0.0).rename("Return")
