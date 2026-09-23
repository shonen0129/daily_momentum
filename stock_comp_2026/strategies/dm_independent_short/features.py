"""Causal V1/V2/V3 features over the unchanged C0/T1 Long construction."""
from pathlib import Path

import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_fixed_long_short import core
from stock_comp_2026.strategies.dm_fixed_long_short import features as champion


FINS_COLUMNS = champion.FINS_COLUMNS + [
    "Profit", "NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock",
]
PRICE_COLUMNS = ["Close"]
SHARES = "NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock"


def load_inputs(directory, split="train"):
    """Load only the causal inputs required by this strategy."""
    result = core.load_inputs(directory, split)
    root = Path(directory)
    result["fins_statements"] = pd.read_parquet(
        root / f"fins_statements_{split}.parquet", columns=FINS_COLUMNS).sort_index()
    result["prices_daily_quotes"] = pd.read_parquet(
        root / f"prices_daily_quotes_{split}.parquet", columns=PRICE_COLUMNS).sort_index()
    if not result["fins_statements"].index.is_unique or not result["prices_daily_quotes"].index.is_unique:
        raise ValueError("input index must be unique")
    return result


def neutral_percentile(value):
    """Daily cross-sectional rank; unavailable values are deliberately neutral."""
    key = value.index.get_level_values("Date")
    return value.replace([np.inf, -np.inf], np.nan).groupby(key).rank(
        method="average", pct=True).fillna(0.5)


def _latest(store):
    return max(store.values(), key=lambda x: (x["end"], x["disclosed"], x["period"]), default=None)


def financial_state(index, fins):
    """Build report states with only disclosures strictly before each signal date."""
    dates = index.get_level_values("Date")
    base = index.to_frame(index=False)
    base["segment"] = np.asarray(core.segment_keys(index)[1])
    raw = fins.reset_index().copy()
    raw["Date"] = pd.to_datetime(raw.Date).dt.tz_localize(None).dt.normalize()
    raw["Code"] = raw.Code.astype(str)
    for name in ["CurrentPeriodStartDate", "CurrentPeriodEndDate"]:
        raw[name] = pd.to_datetime(raw[name], errors="coerce")
    numeric = ["CashFlowsFromOperatingActivities", "Profit", "TotalAssets", SHARES]
    for name in numeric:
        raw[name] = pd.to_numeric(raw[name], errors="coerce").replace([np.inf, -np.inf], np.nan)
    by_code = {key: value.sort_values(["Date", "DisclosureNumber"])
               for key, value in raw.groupby("Code", observed=True)}
    blocks, audit = [], {"disclosures": int(len(raw)), "accepted": 0, "v1_usable_reports": 0,
                          "v2_usable_reports": 0, "invalid_period": 0}
    for (code, segment), daily in base.groupby(["Code", "segment"], sort=False):
        history = by_code.get(str(code), raw.iloc[:0])
        if segment > 0:
            history = history.loc[history.Date >= daily.Date.iloc[0]]
        history = history.loc[history.Date < daily.Date.iloc[-1]]
        yield_store, accrual_store, snapshots = {}, {}, []
        for row in history.to_dict("records"):
            period, doc = str(row["TypeOfCurrentPeriod"]), str(row["TypeOfDocument"])
            start, end = row["CurrentPeriodStartDate"], row["CurrentPeriodEndDate"]
            if (period not in champion.PERIODS or "FinancialStatements_" not in doc
                    or pd.isna(start) or pd.isna(end)):
                audit["invalid_period"] += 1
                continue
            days = (end - start).days
            if not champion.PERIODS[period][0] <= days <= champion.PERIODS[period][1]:
                audit["invalid_period"] += 1
                continue
            audit["accepted"] += 1
            meta = {"start": start, "end": end, "period": period,
                    "basis": doc.split("FinancialStatements_", 1)[1], "disclosed": row["Date"]}
            key = (start, end, period, meta["basis"])
            cfo, profit, assets, shares = (row["CashFlowsFromOperatingActivities"], row["Profit"],
                                            row["TotalAssets"], row[SHARES])
            if np.isfinite(cfo) and np.isfinite(shares) and shares > 0:
                yield_store[key] = dict(meta, annual_cfo=float(cfo * 365.0 / days), shares=float(shares))
                audit["v1_usable_reports"] += 1
            if np.isfinite(cfo) and np.isfinite(profit) and np.isfinite(assets) and assets > 0:
                accrual_store[key] = dict(meta, accrual=float((profit - cfo) / assets))
                audit["v2_usable_reports"] += 1
            current_yield, current_accrual = _latest(yield_store), _latest(accrual_store)
            snapshots.append({"Date": row["Date"],
                              "annual_cfo": current_yield["annual_cfo"] if current_yield else np.nan,
                              "shares": current_yield["shares"] if current_yield else np.nan,
                              "v1_date": current_yield["disclosed"] if current_yield else pd.NaT,
                              "accrual": current_accrual["accrual"] if current_accrual else np.nan,
                              "v2_date": current_accrual["disclosed"] if current_accrual else pd.NaT})
        if snapshots:
            state = pd.DataFrame(snapshots).drop_duplicates("Date", keep="last").sort_values("Date")
            joined = pd.merge_asof(daily.sort_values("Date"), state, on="Date", direction="backward",
                                   allow_exact_matches=False)
        else:
            joined = daily.copy()
            for name in ["annual_cfo", "shares", "accrual"]:
                joined[name] = np.nan
            joined["v1_date"], joined["v2_date"] = pd.NaT, pd.NaT
        blocks.append(joined)
    result = pd.concat(blocks).set_index(["Date", "Code"]).reindex(index)
    for column, date_column in [("annual_cfo", "v1_date"), ("shares", "v1_date"), ("accrual", "v2_date")]:
        age = (pd.Series(dates, index=index) - pd.to_datetime(result[date_column])).dt.days
        result.loc[~age.between(0, 450), column] = np.nan
    result.attrs["financial_state_audit"] = audit
    return result.drop(columns="segment")


def residual_features(inputs):
    r = inputs["raw_return_1day"]["Return"].sort_index().replace([np.inf, -np.inf], np.nan)
    index, groups = r.index, core.segment_keys(r.index)
    dates = index.get_level_values("Date")
    beta = inputs["beta_1day"]["Return"].reindex(index)
    market = pd.Series(inputs["topix_return_1day"]["Return"].reindex(dates).to_numpy(), index=index)
    residual = (r - beta * market).replace([np.inf, -np.inf], np.nan)
    lagged = residual.groupby(groups, sort=False).shift(1)
    return pd.DataFrame({"max20": lagged.groupby(groups, sort=False).transform(
        lambda value: value.rolling(20, min_periods=20).max()),
        "idio_vol20": lagged.groupby(groups, sort=False).transform(
        lambda value: value.rolling(20, min_periods=20).std())}, index=index)


def build_features(inputs):
    """Return Champion-compatible core data and the preregistered independent risks."""
    base = champion.build_features(inputs)
    state = financial_state(base.index, inputs["fins_statements"])
    result = base.join(state, validate="one_to_one").join(residual_features(inputs), validate="one_to_one")
    close = inputs["prices_daily_quotes"]["Close"].reindex(result.index)
    cap = close * result.shares
    result["cfo_yield"] = (result.annual_cfo / cap).where((close > 0) & (result.shares > 0))
    result["v1_risk"] = neutral_percentile(-result.cfo_yield)
    result["v2_risk"] = neutral_percentile(result.accrual)
    result["v3_risk"] = neutral_percentile(result.max20)
    result.attrs.update(state.attrs)
    return result


def _stitch_day(day, risk):
    n = len(day)
    long_rank = day.L.rank(method="first").astype(int)
    neutral_max, short_max = int(np.floor(.6 * (n - 1) + 1)), int(np.floor(.4 * (n - 1) + 1))
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
    else:
        risk = {"V1": "v1_risk", "V2": "v2_risk", "V3": "v3_risk"}[trial]
        score = features.groupby(level="Date", group_keys=False).apply(_stitch_day, risk=risk)
    if not score.index.is_unique or not np.isfinite(score).all():
        raise ValueError("prediction contract failed")
    return score.rename("Return")
