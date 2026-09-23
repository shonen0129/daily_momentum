"""PIT fundamental-weakness extensions over the frozen T1 construction."""
import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_fixed_long_short import features as t1


FINS_COLUMNS = t1.FINS_COLUMNS + ["OperatingProfit", "OrdinaryProfit", "Profit"]
METRICS = {"op": "OperatingProfit", "ordinary": "OrdinaryProfit", "profit": "Profit",
           "equity": "Equity", "cash": "CashAndEquivalents"}


def load_inputs(directory, split="train"):
    inputs = t1.core.load_inputs(directory, split)
    inputs["fins_statements"] = pd.read_parquet(
        f"{directory}/fins_statements_{split}.parquet", columns=FINS_COLUMNS).sort_index()
    return inputs


def _current(store):
    return max(store.values(), key=lambda x: (x["end"], x["disclosed"], x["period"]), default=None)


def _comparable(current, old):
    return (current["period"] == old["period"] and current["basis"] == old["basis"]
            and abs((old["start"] - (current["start"] - pd.DateOffset(years=1))).days) <= 7
            and abs((old["end"] - (current["end"] - pd.DateOffset(years=1))).days) <= 7
            and abs(current["duration"] - old["duration"]) <= 7)


def extended_panel(index, fins):
    """Backward-only report state; missing values are not carried as alpha evidence."""
    dates = index.get_level_values("Date")
    base = index.to_frame(index=False)
    base["segment"] = np.asarray(t1.core.segment_keys(index)[1])
    raw = fins.reset_index().copy()
    raw["Date"] = pd.to_datetime(raw.Date).dt.tz_localize(None).dt.normalize()
    raw["Code"] = raw.Code.astype(str)
    for name in ["CurrentPeriodStartDate", "CurrentPeriodEndDate"]:
        raw[name] = pd.to_datetime(raw[name], errors="coerce")
    for name in ["TotalAssets", *METRICS.values()]:
        raw[name] = pd.to_numeric(raw[name], errors="coerce").replace([np.inf, -np.inf], np.nan)
    by_code = {key: value.sort_values(["Date", "DisclosureNumber"])
               for key, value in raw.groupby("Code", observed=True)}
    blocks, audit = [], {"accepted": 0, "invalid_period": 0, "metric_observations": 0}
    for (code, segment), daily in base.groupby(["Code", "segment"], sort=False):
        history = by_code.get(str(code), raw.iloc[:0])
        if segment > 0:
            history = history.loc[history.Date >= daily.Date.iloc[0]]
        history = history.loc[history.Date < daily.Date.iloc[-1]]
        stores = {name: {} for name in METRICS}
        snapshots = []
        for row in history.to_dict("records"):
            period, doc = str(row["TypeOfCurrentPeriod"]), str(row["TypeOfDocument"])
            start, end = row["CurrentPeriodStartDate"], row["CurrentPeriodEndDate"]
            if (period not in t1.PERIODS or "FinancialStatements_" not in doc
                    or pd.isna(start) or pd.isna(end)):
                audit["invalid_period"] += 1
                continue
            duration = (end - start).days
            if not t1.PERIODS[period][0] <= duration <= t1.PERIODS[period][1]:
                audit["invalid_period"] += 1
                continue
            audit["accepted"] += 1
            meta = {"start": start, "end": end, "period": period,
                    "basis": doc.split("FinancialStatements_", 1)[1], "duration": duration,
                    "disclosed": row["Date"]}
            assets = row["TotalAssets"]
            if not np.isfinite(assets) or assets <= 0:
                assets = np.nan
            for name, column in METRICS.items():
                value = row[column]
                if np.isfinite(assets) and np.isfinite(value):
                    stores[name][(start, end, period, meta["basis"])] = dict(meta, value=value / assets)
                    audit["metric_observations"] += 1
            snapshot = {"Date": row["Date"]}
            for name, store in stores.items():
                current = _current(store)
                prior = (max((item for item in store.values() if current and _comparable(current, item)),
                             key=lambda x: (x["end"], x["disclosed"]), default=None) if current else None)
                snapshot[name] = current["value"] if current else np.nan
                snapshot[name + "_yoy"] = current["value"] - prior["value"] if prior else np.nan
                snapshot[name + "_state_date"] = current["disclosed"] if current else pd.NaT
                snapshot[name + "_period"] = current["period"] if current else "missing"
            snapshots.append(snapshot)
        if snapshots:
            state = pd.DataFrame(snapshots).drop_duplicates("Date", keep="last").sort_values("Date")
            joined = pd.merge_asof(daily.sort_values("Date"), state, on="Date", direction="backward",
                                   allow_exact_matches=False)
        else:
            joined = daily.copy()
            for name in METRICS:
                for suffix in ["", "_yoy", "_state_date", "_period"]:
                    joined[name + suffix] = pd.NaT if suffix == "_state_date" else np.nan
        blocks.append(joined)
    out = pd.concat(blocks).set_index(["Date", "Code"]).reindex(index)
    for name in METRICS:
        age = (pd.Series(dates, index=index) - pd.to_datetime(out[name + "_state_date"])).dt.days
        out.loc[~age.between(0, 450), [name, name + "_yoy"]] = np.nan
        out[name + "_period"] = out[name + "_period"].fillna("missing").astype("string")
    out.attrs["extended_financial_audit"] = audit
    return out.drop(columns=["segment"])


def neutral_percentile(value, period=None):
    keys = [value.index.get_level_values("Date")]
    if period is not None:
        keys.append(period)
    return value.replace([np.inf, -np.inf], np.nan).groupby(keys, observed=True).rank(
        method="average", pct=True).fillna(0.5)


def build_features(inputs):
    base = t1.build_features(inputs)
    ext = extended_panel(base.index, inputs["fins_statements"])
    result = base.join(ext, validate="one_to_one")
    result["profit_risk"] = (
        neutral_percentile(-result.op_yoy, result.op_period)
        + neutral_percentile(-result.ordinary_yoy, result.ordinary_period)
        + neutral_percentile(-result.profit_yoy, result.profit_period)
    ) / 3.0
    result["balance_risk"] = (
        neutral_percentile(-result.equity) + neutral_percentile(-result.cash)
    ) / 2.0
    result["multi_risk"] = (result.fd_equal + result.profit_risk + result.balance_risk) / 3.0
    result.attrs.update(ext.attrs)
    return result


def _stitch_day(sub, risk):
    n = len(sub)
    long_rank = sub.L.rank(method="first").astype(int)
    neutral_max, short_max = int(np.floor(.6 * (n - 1) + 1)), int(np.floor(.4 * (n - 1) + 1))
    is_long = long_rank > neutral_max
    final_rank = pd.Series(index=sub.index, dtype=float)
    final_rank[is_long] = long_rank[is_long]
    rem = sub.loc[~is_long]
    order = np.lexsort((rem.index.get_level_values("Code").astype(str).to_numpy(),
                        long_rank.loc[~is_long].to_numpy(), -rem[risk].to_numpy()))
    final_rank[rem.index[order[:short_max]]] = np.arange(1, short_max + 1)
    final_rank[rem.index[order[short_max:]]] = np.arange(short_max + 1, neutral_max + 1)
    return (final_rank - 1.0) / (n - 1.0)


def predict_from_features(features, spec):
    trial = spec["trial_id"]
    if trial == "C0":
        return t1.predict_from_features(features, {"trial_id": "T1"})
    risk = {"C1": "profit_risk", "C2": "balance_risk", "C3": "multi_risk"}[trial]
    score = features.groupby(level="Date", group_keys=False).apply(_stitch_day, risk=risk)
    if not score.index.is_unique or not np.isfinite(score).all():
        raise ValueError("prediction contract failed")
    return score.rename("Return")
