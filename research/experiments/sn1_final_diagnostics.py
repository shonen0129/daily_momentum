"""Fixed, predeclared source/risk/tie/cost/year diagnostics for SN1_H1."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from research import evaluation

EXP = ROOT / "experiments/DM-20260928-02"
PHASE1_TABLE = ROOT / "artifacts/DM-20260928-01/run-20260927T154814Z/audit/date_code_state.parquet"
REF_RUN = ROOT / "artifacts/DM-20260927-04/run-20260927T101500Z"
PRED_DIR = ROOT / "artifacts/DM-20260928-01/intervention-results-v2/predictions"
RECON_DIR_SUFFIX = Path("audit/full_reconstruction")
TRACE_DIR_SUFFIX = Path("audit/low_trace_preparation")
INPUT_DIR = ROOT / "stock_comp_2026/input"
ACCOUNT_DATES = {
    "train": (pd.Timestamp("2011-01-04"), pd.Timestamp("2016-03-29")),
    "historical_valid": (pd.Timestamp("2016-04-01"), pd.Timestamp("2026-07-29")),
}
ALIASES = {"train": "train", "historical_valid": "valid"}
ACCOUNTS = {"train": "daily_account_train_H1.csv", "historical_valid": "daily_account_valid_H1.csv"}
SECTORS = ("Sector17Code", "Sector33Code", "ScaleCategory")
SOURCES = {"low_state": "Low", "high_state": "High", "fallback": "D fallback"}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read_guard(run_dir: Path, extra=()):
    cfg = json.loads((EXP / "config.json").read_text(encoding="utf-8"))
    allowed = { (ROOT / p).resolve() for p in (cfg["allowed_inputs"] + cfg["full_reconstruction_inputs"]) }
    allowed.update(Path(p).resolve() for p in extra)
    original = pd.read_parquet
    accesses = []

    def guarded(path, *args, **kwargs):
        p = Path(path).resolve()
        if p not in allowed or "paper" in str(p).lower() or "raw_target" in p.name.lower():
            raise PermissionError(f"Final diagnostics firewall denied parquet: {p}")
        accesses.append(str(p.relative_to(ROOT)))
        return original(path, *args, **kwargs)

    pd.read_parquet = guarded
    return original, accesses


def load_target(split: str) -> pd.Series:
    path = REF_RUN / f"predictions/target_{ALIASES[split]}_H1.parquet"
    frame = pd.read_parquet(path)
    value = frame["Return"] if "Return" in frame else frame.iloc[:, 0]
    value.index = pd.MultiIndex.from_arrays(
        [pd.DatetimeIndex(value.index.get_level_values("Date")), value.index.get_level_values("Code").astype(str)],
        names=["Date", "Code"],
    )
    value = pd.to_numeric(value, errors="coerce").astype("float64").sort_index()
    if not value.index.is_unique:
        raise AssertionError(f"Duplicate H1 target index: {split}")
    return value


def load_full_reconstruction(run_dir: Path, split: str) -> pd.DataFrame:
    name = f"SN1_H1_RECONSTRUCTED_{split}.parquet"
    return pd.read_parquet(run_dir / RECON_DIR_SUFFIX / "predictions" / name).sort_index()


def load_state_table() -> pd.DataFrame:
    table = pd.read_parquet(PHASE1_TABLE).sort_index()
    if not table.index.is_unique:
        raise AssertionError("State table has duplicate Date×Code rows")
    return table


def load_account(split: str) -> pd.DataFrame:
    d = pd.read_csv(REF_RUN / "metrics" / ACCOUNTS[split], parse_dates=["Date"]).set_index("Date").sort_index()
    return d


def make_weights_in_order(score: pd.Series, ordered_codes: list[str]) -> tuple[pd.Series, pd.Series]:
    order = {code: i for i, code in enumerate(ordered_codes)}
    f = score.rename("score").rename_axis(index=["Date", "Code"]).reset_index()
    f["Code"] = f["Code"].astype(str)
    f["tie_order"] = f.Code.map(order)
    if f.tie_order.isna().any():
        raise AssertionError("Tie permutation does not cover every Code")
    f = f.sort_values(["Date", "tie_order"], kind="mergesort")
    f["rank"] = f.groupby("Date", sort=False).score.rank(method="first")
    n = f.groupby("Date", sort=False).Code.transform("count")
    f["q"] = (np.ceil(5 * (f["rank"] - 1) / (n - 1)) - 1).clip(0, 4)
    f["weight"] = (f["q"] - 2) / n / 1.2
    f = f.set_index(["Date", "Code"]).sort_index()
    return f.weight, f.q


def account_from_weights(score: pd.Series, weight: pd.Series, q: pd.Series, target: pd.Series, account_dates: pd.DatetimeIndex,
                         one_way_cost: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    score = score.reindex(target.index).fillna(0.0).sort_index()
    weight = weight.reindex(target.index).fillna(0.0).sort_index()
    q = q.reindex(target.index).fillna(2.0).sort_index()
    target = target.reindex(weight.index)
    turn = weight.groupby(level="Code", sort=False).diff().abs().fillna(weight.abs())
    gross_row = (weight * target).where(target.notna(), 0.0)
    cost_row = (one_way_cost * turn).where(target.notna(), 0.0)
    long_gross_row = (weight.clip(lower=0.0) * target).where(target.notna(), 0.0)
    short_gross_row = (weight.clip(upper=0.0) * target).where(target.notna(), 0.0)
    # Attribute turnover to changes in each sleeve's exposure. Looking only at
    # today's sign drops the exit cost when an old position becomes neutral and
    # misattributes sign flips. Since weight = long_weight + short_weight,
    # |Δweight| = |Δlong_weight| + |Δshort_weight| for these disjoint sleeves.
    long_weight = weight.clip(lower=0.0)
    short_weight = weight.clip(upper=0.0)
    long_turn = long_weight.groupby(level="Code", sort=False).diff().abs().fillna(long_weight.abs())
    short_turn = short_weight.groupby(level="Code", sort=False).diff().abs().fillna(short_weight.abs())
    long_cost_row = (one_way_cost * long_turn).where(target.notna(), 0.0)
    short_cost_row = (one_way_cost * short_turn).where(target.notna(), 0.0)
    if not np.allclose((long_cost_row + short_cost_row).to_numpy(), cost_row.to_numpy(), rtol=0.0, atol=1e-15):
        raise AssertionError("Long and Short sleeve costs do not reconcile to total turnover cost")
    dates = weight.index.get_level_values("Date")
    daily = pd.DataFrame(index=pd.DatetimeIndex(sorted(account_dates.unique()), name="Date"))
    for name, values in (
        ("gross", gross_row), ("cost", cost_row), ("long_gross", long_gross_row),
        ("short_gross", short_gross_row), ("long_cost", long_cost_row),
        ("short_cost", short_cost_row), ("turnover", turn),
    ):
        daily[name] = values.groupby(level="Date").sum().reindex(daily.index).fillna(0.0)
    daily["net"] = daily.gross - daily.cost
    daily["long_net"] = daily.long_gross - daily.long_cost
    daily["short_net"] = daily.short_gross - daily.short_cost
    ic = evaluation.rankic(score, target)
    daily["rankic"] = ic.reindex(daily.index)
    for k in range(5):
        daily[f"q{k+1}"] = target.where(q == k).groupby(level="Date").mean().reindex(daily.index)
    active = pd.DataFrame({"score": score, "weight": weight, "turnover": turn, "cost": cost_row,
                           "target": target, "gross": gross_row, "net": gross_row-cost_row,
                           "long_gross": long_gross_row, "short_gross": short_gross_row,
                           "long_cost": long_cost_row, "short_cost": short_cost_row, "q": q}, index=weight.index)
    active["long_net"] = long_gross_row - long_cost_row
    active["short_net"] = short_gross_row - short_cost_row
    if not np.allclose((active.long_net + active.short_net).to_numpy(), active.net.to_numpy(), rtol=0.0, atol=1e-15):
        raise AssertionError("Long and Short row P/L do not reconcile to total row P/L")
    return daily, active


def daily_metrics(d: pd.DataFrame) -> dict:
    return {
        "days": int(len(d)), "annual_gross": float(d.gross.mean() * 252),
        "annual_net": float(d.net.mean() * 252), "gross_sr": evaluation.sharpe(d.gross),
        "net_sr": evaluation.sharpe(d.net), "annual_cost": float(d.cost.mean() * 252),
        "turnover_per_day": float(d.turnover.mean()), "annual_long_gross": float(d.long_gross.mean()*252),
        "annual_long_net": float(d.long_net.mean()*252), "annual_short_gross": float(d.short_gross.mean()*252),
        "annual_short_net": float(d.short_net.mean()*252), "mean_rankic": float(d.rankic.mean()),
        "rankic_hac_t": evaluation.hac_t(d.rankic, lag=1),
        "rankic_hit_ratio": float((d.rankic.dropna() > 0).mean()),
        "q_monotonicity": float(spearmanr(range(1,6), [d[f"q{k}"].mean() for k in range(1,6)]).statistic),
        "max_drawdown_additive": float(np.min(np.r_[0.0, d.net.cumsum().to_numpy()] -
                                                   np.maximum.accumulate(np.r_[0.0, d.net.cumsum().to_numpy()]))),
    }


def weighted_group_summary(rows: pd.DataFrame, keys: list[str], account_dates: pd.DatetimeIndex) -> pd.DataFrame:
    records = []
    total_abs_weight = float(rows.weight.abs().sum())
    days_n = len(account_dates)
    if not keys:
        return pd.DataFrame()
    groups = rows.groupby(keys, dropna=False, sort=True)
    for group_key, g in groups:
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        daily_gross = g.groupby(level="Date").gross.sum().reindex(account_dates).fillna(0.0)
        daily_net = g.groupby(level="Date").net.sum().reindex(account_dates).fillna(0.0)
        daily_cost = g.groupby(level="Date").cost.sum().reindex(account_dates).fillna(0.0)
        daily_turn = g.groupby(level="Date").turnover.sum().reindex(account_dates).fillna(0.0)
        ic = []
        spread = []
        for _, gd in g.groupby(level="Date", sort=True):
            z = gd.loc[gd.target.notna() & np.isfinite(gd.score) & np.isfinite(gd.target)]
            if len(z) >= 3 and z.score.nunique() > 1 and z.target.nunique() > 1:
                ic.append(float(spearmanr(z.score, z.target).statistic))
            if len(z) >= 5 and z.score.nunique() > 1:
                r = z.score.rank(method="average", pct=True)
                qbin = np.minimum(4, np.floor(r * 5)).astype(int)
                if (qbin == 0).any() and (qbin == 4).any():
                    spread.append(float(z.target[qbin == 4].mean() - z.target[qbin == 0].mean()))
        rec = dict(zip(keys, group_key))
        gross_w = float(g.weight.abs().sum())
        rec.update({
            "stock_days": int(len(g)), "gross_exposure_sum": gross_w,
            "weight_share": gross_w / total_abs_weight if total_abs_weight else np.nan,
            "mean_weight_signed": float(g.weight.mean()), "mean_weight_abs": float(g.weight.abs().mean()),
            "annual_gross_contribution": float(daily_gross.mean() * 252),
            "annual_net_contribution": float(daily_net.mean() * 252),
            "annual_cost_contribution": float(daily_cost.mean() * 252),
            "annual_turnover_contribution": float(daily_turn.mean() * 252),
            "attributed_net_sr": evaluation.sharpe(daily_net),
            "mean_rankic": float(np.mean(ic)) if ic else np.nan,
            "rankic_hac_t": evaluation.hac_t(pd.Series(ic), lag=1) if len(ic) >= 3 else np.nan,
            "rankic_hit_ratio": float(np.mean(np.asarray(ic) > 0)) if ic else np.nan,
            "mean_h1_q5_q1_spread": float(np.mean(spread)) if spread else np.nan,
            "median_score_percentile": float(g.score_percentile.median()) if "score_percentile" in g else np.nan,
            "median_absolute_score": float(g.score.abs().median()),
            "near_zero_fraction": float(g.score.abs().lt(1e-12).mean()),
            "renewal_rate": float(g.renewal_bucket.isin(["single_same_side", "recurrent_same_side"]).mean()) if "renewal_bucket" in g else np.nan,
            "median_relevant_event_age": float(g.side_reinforcing_event_age_days.median()) if "side_reinforcing_event_age_days" in g else np.nan,
        })
        records.append(rec)
    return pd.DataFrame(records)


def trace_sample_lock(table: pd.DataFrame, events: pd.DataFrame, out: Path) -> pd.DataFrame:
    """Select boundary cases before reading any target/P&L values."""
    picked: dict[tuple[pd.Timestamp, str], set[str]] = {}
    context_by_split = {}
    eligible_events = events.copy()
    if not eligible_events.index.is_unique:
        raise AssertionError("Event feature table has duplicate rows")
    for split in ("train", "historical_valid"):
        st = table.loc[table.split.astype(str).eq(split)].copy()
        d = st.reset_index().sort_values(["Code", "Date"], kind="mergesort")
        calendar = pd.DatetimeIndex(sorted(pd.DatetimeIndex(st.index.get_level_values("Date")).unique()))
        ordinal = pd.Series(np.arange(len(calendar)), index=calendar)
        d["_ord"] = d.Date.map(ordinal)
        by_code = d.groupby("Code", sort=False)
        d["_gap"] = by_code["_ord"].diff()
        d["_prev_low_event"] = by_code["low_event"].shift().fillna(False).astype(bool)
        d["_prev_latest_side"] = by_code["latest_event_side"].shift().fillna("none")
        d["_prev_low_state"] = by_code["low_state"].shift()
        d["_prev_high_state"] = by_code["high_state"].shift()
        d["prior_low_state"] = d["_prev_low_state"].where(d["_gap"].le(20), 0.0).fillna(0.0)
        d["prior_high_state"] = d["_prev_high_state"].where(d["_gap"].le(20), 0.0).fillna(0.0)
        d["_next_gap"] = by_code["_gap"].shift(-1)
        d["_segment_start"] = d["_gap"].isna() | d["_gap"].gt(20)
        d["_segment"] = d.groupby("Code", sort=False)["_segment_start"].cumsum()
        d["_event"] = d.high_event | d.low_event
        d["_segment_event_count"] = d.groupby(["Code", "_segment"], sort=False)["_event"].cumsum()
        # Do not treat the split's first observed segment as a reset. Only a real
        # >20-market-date gap starts a post-reset segment for this boundary case.
        d["_reset_sequence"] = d["_gap"].gt(20).groupby(d["Code"], sort=False).cumsum()
        d["_events_since_real_reset"] = d.groupby(["Code", "_reset_sequence"], sort=False)["_event"].cumsum()
        d["_first_event_after_real_reset"] = (
            d["_event"] & d["_reset_sequence"].gt(0) & d["_events_since_real_reset"].eq(1)
        )
        d["_high_to_low"] = d.low_event & d["_prev_latest_side"].eq("high")
        d["_low_to_high"] = d.high_event & d["_prev_latest_side"].eq("low")
        d["_gap_missing"] = d["_event"] & ((d["_gap"].between(2,20)) | (d["_next_gap"].between(2,20)))
        d["_gap_20"] = d["_event"] & d["_gap"].eq(20)
        d["_gap_reset"] = d["_event"] & d["_gap"].gt(20)
        d["_consecutive_low"] = d.low_event & d["_prev_low_event"] & d["_gap"].eq(1)
        d["_low_nearzero"] = d.low_state.lt(0) & d.score.abs().lt(1e-12)
        d["_low_high"] = d.low_state.lt(0) & d.high_state.gt(0)
        d["_simultaneous"] = d.high_event & d.low_event
        d["_exact_zero"] = d.score.eq(0.0)
        # Pick the earliest deterministic member of each predeclared boundary class.
        cases = {
            "first_event_after_reset": d["_first_event_after_real_reset"],
            "consecutive_low_event": d["_consecutive_low"],
            "high_to_low": d["_high_to_low"],
            "low_to_high": d["_low_to_high"],
            "missing_panel_near_event": d["_gap_missing"],
            "gap_exactly_20_market_dates": d["_gap_20"],
            "reset_gap_over_20_market_dates": d["_gap_reset"],
            "negative_low_near_zero": d["_low_nearzero"],
            "low_negative_high_positive": d["_low_high"],
            "exact_zero_score": d["_exact_zero"],
            "simultaneous_high_low_if_any": d["_simultaneous"],
        }
        for label, mask in cases.items():
            candidates = d.loc[mask].sort_values(["Date", "Code"], kind="mergesort")
            if len(candidates):
                row = candidates.iloc[0]
                key = (pd.Timestamp(row.Date), str(row.Code))
                picked.setdefault(key, set()).add(label)
        # Keep exact gap/prior-state context with the selected source rows.
        context = d.set_index(["Date", "Code"])[["_gap", "prior_low_state", "prior_high_state", "_prev_latest_side"]]
        context_by_split[split] = context
        event_rows = d.loc[d["_event"]].copy()
        event_rows["_hash"] = [hashlib.blake2b(f"{r.Date.date()}|{r.Code}".encode(), digest_size=8, key=b"SN1trace20260928").hexdigest()
                                for r in event_rows.itertuples()]
        event_rows = event_rows.sort_values(["_hash", "Date", "Code"], kind="mergesort")
        split_event_n = sum(1 for (dt, _), _labels in picked.items() if (dt < pd.Timestamp("2016-04-01")) == (split == "train"))
        need = max(0, 100 - split_event_n)
        for r in event_rows.itertuples():
            key = (pd.Timestamp(r.Date), str(r.Code))
            if key not in picked:
                picked[key] = set()
                need -= 1
                if need <= 0:
                    break
    keys = pd.MultiIndex.from_tuples(sorted(picked), names=["Date", "Code"])
    selected = table.reindex(keys).copy()
    selected["split"] = selected["split"].astype(str)
    ev = eligible_events.reindex(keys)
    for split in ("train", "historical_valid"):
        mask = selected.split.astype(str).eq(split)
        add = context_by_split[split].reindex(selected.index[mask])
        selected.loc[mask, "gap_market_date_positions"] = add["_gap"].to_numpy()
        selected.loc[mask, "prior_low_state"] = add["prior_low_state"].to_numpy()
        selected.loc[mask, "prior_high_state"] = add["prior_high_state"].to_numpy()
        selected.loc[mask, "prior_latest_event_side"] = add["_prev_latest_side"].astype(str).to_numpy()
    selected["breakout_side"] = ev.breakout_side
    selected["ridge_prediction"] = ev.ridge_prediction
    selected["model_year"] = ev.model_year
    selected["raw_unsigned_event_score"] = ev.raw_unsigned_event_score
    selected["signed_raw_event_score"] = ev.signed_raw_event_score
    for col in ("box_duration", "box_width_atr", "oriented_close_position", "oriented_relative_strength_60", "distance_to_prior_extreme"):
        selected[col] = ev[col]
    selected["breakout_side"] = selected.breakout_side.fillna("none")
    selected["selected_boundary_cases"] = [";".join(sorted(picked[(pd.Timestamp(i[0]), str(i[1]))])) for i in selected.index]
    # Save source state before making a target read. This hash is the P/L-blind selection lock.
    out.parent.mkdir(parents=True, exist_ok=True)
    sample_path = out / "predictions/low_trace_sample_locked.parquet"
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    selected.to_parquet(sample_path, compression="zstd")
    lock = {
        "phase": "P/L-blind trace-row selection lock", "target_values_read": False, "pnl_calculated": False,
        "paper_data_accessed": False, "rows": int(len(selected)),
        "rows_by_split": {k: int((selected.split == k).sum()) for k in ("train", "historical_valid")},
        "boundary_case_counts": {label: int(sum(label in labels for labels in picked.values())) for label in sorted(set().union(*picked.values()))},
        "simultaneous_high_low_observed": bool((table.high_event & table.low_event).any()),
        "source_table_sha256": sha(PHASE1_TABLE), "event_features_sha256": sha(out / TRACE_DIR_SUFFIX / "predictions/event_predictions_and_features.parquet"),
        "sample_sha256": sha(sample_path),
    }
    write_json(out / "audit/low_trace_sample_lock.json", lock)
    return selected


def normalize_pair_index(frame: pd.DataFrame) -> pd.DataFrame:
    if isinstance(frame.index, pd.MultiIndex) and list(frame.index.names) == ["Date", "Code"]:
        frame.index = pd.MultiIndex.from_arrays(
            [pd.DatetimeIndex(frame.index.get_level_values("Date")), frame.index.get_level_values("Code").astype(str)],
            names=["Date", "Code"],
        )
        return frame.sort_index()
    if {"Date", "Code"}.issubset(frame.columns):
        frame = frame.set_index(["Date", "Code"])
        frame.index = pd.MultiIndex.from_arrays(
            [pd.DatetimeIndex(frame.index.get_level_values("Date")), frame.index.get_level_values("Code").astype(str)],
            names=["Date", "Code"],
        )
        return frame.sort_index()
    raise ValueError("Expected a (Date, Code) raw input index")


def load_raw_h1_sources(split: str) -> tuple[pd.Series, pd.Series, pd.Series]:
    alias = ALIASES[split]
    raw = pd.read_parquet(INPUT_DIR / f"raw_return_1day_{alias}.parquet", columns=["Return"])
    beta = pd.read_parquet(INPUT_DIR / f"beta_1day_{alias}.parquet", columns=["Return"])
    market = pd.read_parquet(INPUT_DIR / f"topix_return_1day_{alias}.parquet", columns=["Return"])
    raw = normalize_pair_index(raw)["Return"].astype("float64")
    beta = normalize_pair_index(beta)["Return"].astype("float64")
    if isinstance(market.index, pd.MultiIndex):
        market.index = pd.DatetimeIndex(market.index.get_level_values("Date"), name="Date")
    else:
        market.index = pd.DatetimeIndex(market.index, name="Date")
    market = market[~market.index.duplicated(keep="last")].sort_index()["Return"].astype("float64")
    return raw, beta, market


def portfolio_panel(split: str, table: pd.DataFrame, run_dir: Path, target: pd.Series,
                    account_dates: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    reconstructed = load_full_reconstruction(run_dir, split)
    score = reconstructed.score.reindex(target.index).fillna(0.0).sort_index()
    weight, q = evaluation.weights(score)
    daily, active = account_from_weights(score, weight, q, target, account_dates, 0.001)
    states = table.loc[table.split.astype(str).eq(split)].copy()
    states.index = states.index.set_names(["Date", "Code"])
    active = active.join(states.drop(columns=[c for c in ("score", "weight") if c in states]), how="left")
    account_mask = active.index.get_level_values("Date").isin(account_dates)
    active = active.loc[account_mask].copy()
    active["split"] = split
    active["portfolio_side"] = active.portfolio_side.astype(str)
    active["source_label"] = active.sn1_source.astype(str).map(SOURCES).fillna("D fallback")
    renewal_n = pd.to_numeric(active.side_reinforcing_events_last_60, errors="coerce").fillna(0)
    active["renewal_bucket"] = np.select(
        [renewal_n.ge(2), renewal_n.eq(1)], ["recurrent_same_side", "single_same_side"], default="no_recent_same_side"
    )
    active["sleeve_age_bucket"] = np.where(pd.to_numeric(active.sleeve_age, errors="coerce").fillna(0).lt(20), "under_20", "20_plus")
    active["event_age_bucket"] = active.portfolio_side_event_age_bucket.astype(str)
    rank_pct = score.groupby(level="Date").rank(method="average", pct=True)
    active["absolute_score_decile"] = np.minimum(9, np.floor(score.abs().groupby(level="Date").rank(method="average", pct=True) * 10)).astype("int8").reindex(active.index)
    active["rank_percentile"] = rank_pct.reindex(active.index)
    return daily, active, score, target


def rankic_and_spread(signal: pd.Series, target: pd.Series, dates: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series]:
    signal, target = signal.align(target, join="inner")
    good = signal.notna() & target.notna() & np.isfinite(signal) & np.isfinite(target)
    signal, target = signal.loc[good], target.loc[good]
    records_ic, records_spread = {}, {}
    frame = pd.DataFrame({"score": signal, "target": target})
    for date, g in frame.groupby(level="Date", sort=True):
        if len(g) >= 3 and g.score.nunique() > 1 and g.target.nunique() > 1:
            records_ic[pd.Timestamp(date)] = float(spearmanr(g.score, g.target).statistic)
        if len(g) >= 5 and g.score.nunique() > 1:
            pct = g.score.rank(method="average", pct=True)
            qb = np.minimum(4, np.floor(pct * 5)).astype(int)
            if (qb == 0).any() and (qb == 4).any():
                records_spread[pd.Timestamp(date)] = float(g.target[qb == 4].mean() - g.target[qb == 0].mean())
    ix = pd.DatetimeIndex(dates, name="Date")
    return pd.Series(records_ic).reindex(ix), pd.Series(records_spread).reindex(ix)


def event_quality(events: pd.DataFrame, target: pd.Series, split: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    e = events.loc[events.split.eq(split)].copy()
    y = target.reindex(e.index)
    e["target"] = y
    e = e.loc[e.target.notna()].copy()
    quality_rows, decile_rows = [], []
    dates = pd.DatetimeIndex(sorted(e.index.get_level_values("Date").unique()), name="Date")
    for side in ("high", "low"):
        g = e.loc[e.breakout_side.eq(side)].copy()
        if g.empty:
            continue
        score = g.signed_raw_event_score.astype("float64")
        ic, spread = rankic_and_spread(score, g.target, dates)
        quality_rows.append({
            "split": split, "breakout_side": side, "event_rows": int(len(g)),
            "signal_dates": int(g.index.get_level_values("Date").nunique()),
            "mean_h1_rankic": float(ic.mean()), "rankic_hac_t": evaluation.hac_t(ic, lag=1),
            "rankic_hit_ratio": float((ic.dropna() > 0).mean()), "mean_h1_q5_q1_spread": float(spread.mean()),
            "spread_hac_t": evaluation.hac_t(spread, lag=1), "target_coverage": float(g.target.notna().mean()),
            "orientation": "high score vs residual H1" if side == "high" else "signed negative Low score vs residual H1",
        })
        # The decile is based only on the existing signed event score and is descriptive.
        dates_for_rows = g.index.get_level_values("Date")
        decile = g.raw_unsigned_event_score.groupby(level="Date").rank(method="average", pct=True)
        g["event_score_decile"] = np.minimum(9, np.floor(decile * 10)).astype("int8")
        sign = 1.0 if side == "high" else -1.0
        out = g.groupby("event_score_decile").agg(
            event_rows=("target", "size"), mean_raw_residual_h1=("target", "mean"),
            mean_oriented_h1=("target", lambda v: float(sign * v.mean())),
            median_prediction=("ridge_prediction", "median"), median_unsigned_score=("raw_unsigned_event_score", "median"),
        ).reset_index()
        out.insert(0, "breakout_side", side); out.insert(0, "split", split); decile_rows.append(out)
    return pd.DataFrame(quality_rows), pd.concat(decile_rows, ignore_index=True) if decile_rows else pd.DataFrame()


def make_trace_outcomes(sample: pd.DataFrame, events: pd.DataFrame, table: pd.DataFrame, target: pd.Series,
                        active: pd.DataFrame, split: str, raw: pd.Series, beta: pd.Series, market: pd.Series) -> tuple[pd.DataFrame, float]:
    s = sample.loc[sample.split.eq(split)].copy()
    full_calendar = pd.DatetimeIndex(sorted(pd.DatetimeIndex(table.index.get_level_values("Date")).unique()))
    position = pd.Series(np.arange(len(full_calendar)), index=full_calendar)
    sig_dates = pd.DatetimeIndex(s.index.get_level_values("Date"))
    pos = sig_dates.map(position)
    d1 = [full_calendar[int(p)+1] if pd.notna(p) and int(p)+1 < len(full_calendar) else pd.NaT for p in pos]
    d2 = [full_calendar[int(p)+2] if pd.notna(p) and int(p)+2 < len(full_calendar) else pd.NaT for p in pos]
    s["prediction_asof"] = "after signal-date close"
    s["execution_start"] = d1
    s["execution_end"] = d2
    s["target_interval"] = [f"{a.date() if pd.notna(a) else 'NA'} Open -> {b.date() if pd.notna(b) else 'NA'} Open" for a,b in zip(d1,d2)]
    s["saved_h1_residual_target"] = target.reindex(s.index)
    exit_idx = pd.MultiIndex.from_arrays([pd.DatetimeIndex(d2), s.index.get_level_values("Code").astype(str)], names=["Date","Code"])
    s["raw_asset_return_at_exit"] = raw.reindex(exit_idx).to_numpy()
    s["beta_at_exit"] = beta.reindex(exit_idx).to_numpy()
    s["market_return_at_exit"] = pd.Series(d2, index=s.index).map(market)
    s["reconstructed_residual_target"] = s.raw_asset_return_at_exit - s.beta_at_exit * s.market_return_at_exit
    s["target_reconstruction_delta"] = s.reconstructed_residual_target - s.saved_h1_residual_target
    s["target_mature"] = s.saved_h1_residual_target.notna()
    s["realized_h1_residual_return"] = s.saved_h1_residual_target
    s["account_gross_contribution"] = s.weight * s.realized_h1_residual_return
    trace_turnover = active.turnover.reindex(s.index)
    s["one_way_cost_contribution_10bps"] = (0.001 * trace_turnover).where(s.target_mature, 0.0)
    s["account_net_contribution"] = s.account_gross_contribution - s.one_way_cost_contribution_10bps
    s["account_rank"] = s.score.groupby(level="Date").rank(method="first").reindex(s.index)
    s["residual_target_sign_times_weight"] = s.weight * s.realized_h1_residual_return
    # Add saved model maturity metadata; no target value enters model selection.
    from research.experiments import state_persistence_audit as state_audit
    for side in ("high", "low"):
        mask = s.breakout_side.eq(side)
        for year in pd.unique(s.loc[mask, "model_year"].dropna()):
            if int(year) == -1:
                path = REF_RUN / f"models/H1/valid/{side}_valid.json"
            else:
                path = REF_RUN / f"models/H1/train/{side}_{int(year)}.json"
            model = state_audit.load_model(path)
            use = mask & s.model_year.eq(year)
            s.loc[use, "model_max_training_signal"] = model.get("max_training_signal")
            s.loc[use, "model_max_label_maturity_date"] = model.get("max_label_maturity_date")
    finite_delta = s.target_reconstruction_delta.dropna().abs()
    max_delta = float(finite_delta.max()) if len(finite_delta) else np.nan
    return s, max_delta


def perf_row(name: str, score: pd.Series, q: pd.Series, w: pd.Series, target: pd.Series,
             account_dates: pd.DatetimeIndex, one_way_cost: float) -> dict:
    daily, _ = account_from_weights(score, w, q, target, account_dates, one_way_cost)
    return {"stress": name, **daily_metrics(daily)}


def tie_stress(split: str, run_dir: Path, score: pd.Series, target: pd.Series,
               account_dates: pd.DatetimeIndex, seed: int = 20260928) -> pd.DataFrame:
    base_w, base_q = evaluation.weights(score)
    base_daily, _ = account_from_weights(score, base_w, base_q, target, account_dates, 0.001)
    codes = sorted(score.index.get_level_values("Code").astype(str).unique())
    records = []

    def record(name: str, s: pd.Series, w: pd.Series, q: pd.Series, roundtrip_delta: float | None = None):
        daily, _ = account_from_weights(s, w, q, target, account_dates, 0.001)
        changed = q.reindex(base_q.index).ne(base_q)
        long_base, long_new = base_q.ge(3), q.reindex(base_q.index).ge(3)
        short_base, short_new = base_q.le(1), q.reindex(base_q.index).le(1)
        metrics = daily_metrics(daily)
        records.append({
            "split": split, "stress": name, "changed_quintile_rows": int(changed.sum()),
            "changed_long_membership_rows": int((long_base != long_new).sum()),
            "changed_short_membership_rows": int((short_base != short_new).sum()),
            "roundtrip_weight_max_abs_delta": roundtrip_delta,
            **metrics,
        })

    record("official_code_ascending", score, base_w, base_q, 0.0)
    w, q = make_weights_in_order(score, sorted(codes, reverse=True))
    record("code_descending", score, w, q)
    hashed = sorted(codes, key=lambda c: hashlib.blake2b(c.encode(), digest_size=16, key=b"SN1-20260928").digest())
    w, q = make_weights_in_order(score, hashed)
    record("blake2b_code_order", score, w, q)
    rng = np.random.default_rng(seed)
    random_order = [codes[i] for i in rng.permutation(len(codes))]
    w, q = make_weights_in_order(score, random_order)
    record("fixed_seed_code_permutation", score, w, q)

    code_perturb = {c: int.from_bytes(hashlib.blake2b(c.encode(), digest_size=8, key=b"SN1-20260928").digest(), "big") / (2**64) - 0.5 for c in codes}
    day_sd = score.groupby(level="Date").transform("std")
    u = pd.Series(score.index.get_level_values("Code").map(code_perturb).to_numpy(), index=score.index)
    perturbed = score + 1e-12 * day_sd * u
    pw, pq = evaluation.weights(perturbed)
    record("tiny_hash_perturbation_1e-12_daily_sd", perturbed, pw, pq)

    # Row shuffle plus Parquet roundtrip; ranking canonicalizes the Date×Code index.
    roundtrip_path = run_dir / "audit" / f"tie_roundtrip_{split}.parquet"
    roundtrip_path.parent.mkdir(parents=True, exist_ok=True)
    shuffled = score.rename("score").to_frame().sample(frac=1.0, random_state=seed)
    shuffled.to_parquet(roundtrip_path, compression="zstd")
    roundtrip = pd.read_parquet(roundtrip_path)["score"].sort_index()
    rw, rq = evaluation.weights(roundtrip)
    roundtrip_delta = max(float((rw - base_w).abs().max()), float((rq.astype(float) - base_q.astype(float)).abs().max()))
    record("row_shuffle_parquet_roundtrip", roundtrip, rw, rq, roundtrip_delta)
    if roundtrip_delta != 0.0:
        raise AssertionError("Row shuffle/Parquet roundtrip changed official assignments")
    return pd.DataFrame(records)


def cost_stress(split: str, score: pd.Series, target: pd.Series, account_dates: pd.DatetimeIndex) -> pd.DataFrame:
    w, q = evaluation.weights(score)
    rows = []
    for bps in (5, 10, 20, 30):
        daily, _ = account_from_weights(score, w, q, target, account_dates, bps / 10000.0)
        rows.append({"split": split, "one_way_bps": bps, **daily_metrics(daily)})
    return pd.DataFrame(rows)


def loyo_stress(split: str, daily: pd.DataFrame) -> pd.DataFrame:
    records = []
    years = sorted(daily.index.year.unique())
    partials = {2016, 2026}
    for year in years:
        keep = daily.index.year != year
        rest = daily.loc[keep]
        rec = {"split": split, "excluded_year": int(year), "remaining_days": int(len(rest)),
               "excluded_year_partial": bool(year in partials), "excluded_year_is_2026_partial": bool(year == 2026)}
        rec.update(daily_metrics(rest))
        records.append(rec)
    return pd.DataFrame(records)


def risk_exposure(rows: pd.DataFrame, split: str, account_dates: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = rows.loc[rows.portfolio_side.isin(["long", "short"])].copy()
    base["persistence_bucket"] = np.where(base.sleeve_age_bucket.eq("20_plus"), "persistent_20_plus", "under_20")
    exposure, annual = [], []
    for descriptor in SECTORS:
        if descriptor not in base:
            continue
        base["risk_descriptor"] = descriptor
        base["risk_bucket"] = base[descriptor].astype("string").fillna("Unknown")
        for (side, persistence, bucket), g in base.groupby(["portfolio_side", "persistence_bucket", "risk_bucket"], dropna=False, sort=True):
            dates = pd.DatetimeIndex(account_dates, name="Date")
            gross_w = g.weight.abs().groupby(level="Date").sum().reindex(dates).fillna(0.0)
            net_w = g.weight.groupby(level="Date").sum().reindex(dates).fillna(0.0)
            gross = g.gross.groupby(level="Date").sum().reindex(dates).fillna(0.0)
            net = g.net.groupby(level="Date").sum().reindex(dates).fillna(0.0)
            cost = g.cost.groupby(level="Date").sum().reindex(dates).fillna(0.0)
            tot = float(base.loc[(base.portfolio_side == side) & (base.persistence_bucket == persistence), "weight"].abs().sum())
            exposure.append({
                "split": split, "side": side, "persistence": persistence, "descriptor": descriptor, "bucket": str(bucket),
                "stock_days": int(len(g)), "mean_daily_gross_exposure": float(gross_w.mean()),
                "mean_daily_net_exposure": float(net_w.mean()), "gross_exposure_weight_share": float(g.weight.abs().sum()/tot) if tot else np.nan,
                "exposure_day_fraction": float((gross_w > 0).mean()), "annual_gross_contribution": float(gross.mean()*252),
                "annual_net_contribution": float(net.mean()*252), "annual_cost_contribution": float(cost.mean()*252),
                "attributed_net_sr": evaluation.sharpe(net),
            })
            ydf = pd.DataFrame({"gross_w": gross_w, "net_w": net_w, "gross": gross, "net": net, "cost": cost})
            ydf["year"] = ydf.index.year
            for year, yg in ydf.groupby("year"):
                annual.append({
                    "split": split, "side": side, "persistence": persistence, "descriptor": descriptor,
                    "bucket": str(bucket), "year": int(year), "partial_year": bool(year in {2016, 2026}),
                    "days": int(len(yg)), "mean_daily_gross_exposure": float(yg.gross_w.mean()),
                    "mean_daily_net_exposure": float(yg.net_w.mean()), "annual_gross_contribution": float(yg.gross.mean()*252),
                    "annual_net_contribution": float(yg.net.mean()*252), "annual_cost_contribution": float(yg.cost.mean()*252),
                })
    return pd.DataFrame(exposure), pd.DataFrame(annual)


def reset_audit(table: pd.DataFrame, split: str) -> dict:
    st = table.loc[table.split.astype(str).eq(split)].copy().reset_index()
    cal = pd.DatetimeIndex(sorted(pd.DatetimeIndex(st.Date.unique())))
    ordinal = pd.Series(np.arange(len(cal)), index=cal)
    st["market_ordinal"] = st.Date.map(ordinal)
    st = st.sort_values(["Code", "Date"], kind="mergesort")
    g = st.groupby("Code", sort=False)
    st["gap_market_dates"] = g.market_ordinal.diff()
    reset = st.gap_market_dates.gt(20)
    exact20 = st.gap_market_dates.eq(20)
    missing = st.gap_market_dates.gt(1) & st.gap_market_dates.le(20)
    # segment_keys starts a fresh adjust=False EWMA at first row after >20 market-date positions.
    reset_rows = st.loc[reset]
    high_delta = (reset_rows.high_state - reset_rows.high_raw_event_score).abs()
    low_delta = (reset_rows.low_state - reset_rows.low_raw_event_score).abs()
    return {
        "split": split, "stock_days": int(len(st)), "codes": int(st.Code.nunique()),
        "within_1_market_date_transitions": int(st.gap_market_dates.eq(1).sum()),
        "missing_panel_gaps_2_to_20": int(missing.sum()), "exact_20_market_date_gaps_no_reset": int(exact20.sum()),
        "reset_gaps_over_20": int(reset.sum()), "max_gap_market_dates": float(st.gap_market_dates.max()),
        "reset_state_equals_raw_max_abs_high": float(high_delta.max()) if len(high_delta) else 0.0,
        "reset_state_equals_raw_max_abs_low": float(low_delta.max()) if len(low_delta) else 0.0,
        "reset_rows_high_low_match_raw_within_2e_12": bool(max(float(high_delta.max()) if len(high_delta) else 0.0,
                                                                 float(low_delta.max()) if len(low_delta) else 0.0) <= 2e-12),
        "gap_rule": "reset iff consecutive observed Code rows differ by >20 market-date positions; exactly 20 carries",
        "missing_row_behavior": "no score/state row and no EWMA update while Code is absent; state carries until observed again or >20-position reset",
    }


def run_analysis(run_dir: Path) -> dict:
    baseline_path = run_dir / "audit/baseline_parity.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if not baseline.get("pass"):
        raise SystemExit("Analysis stopped: Phase 0 baseline parity has not passed")
    trace_path = run_dir / TRACE_DIR_SUFFIX / "predictions/event_predictions_and_features.parquet"
    extra = [trace_path,
             run_dir / RECON_DIR_SUFFIX / "predictions/SN1_H1_RECONSTRUCTED_train.parquet",
             run_dir / RECON_DIR_SUFFIX / "predictions/SN1_H1_RECONSTRUCTED_historical_valid.parquet",
             run_dir / "predictions/low_trace_sample_locked.parquet",
             run_dir / "audit/tie_roundtrip_train.parquet",
             run_dir / "audit/tie_roundtrip_historical_valid.parquet"]
    original_reader, accesses = read_guard(run_dir, extra)
    audit_dir, metrics_dir, pred_dir = (run_dir / "audit", run_dir / "metrics", run_dir / "predictions")
    for p in (audit_dir, metrics_dir, pred_dir):
        p.mkdir(parents=True, exist_ok=True)

    # P/L-blind boundary rows are chosen and hashed before the first target read.
    state_table = load_state_table()
    event_features = pd.read_parquet(trace_path).sort_index()
    sample = trace_sample_lock(state_table, event_features, run_dir)
    trace_lock = json.loads((audit_dir / "low_trace_sample_lock.json").read_text(encoding="utf-8"))
    if not trace_lock["rows"] >= 100 or any(v < 100 for v in trace_lock["rows_by_split"].values()):
        raise AssertionError(f"Trace sample did not reach 100 rows in each split: {trace_lock}")

    source_tables, matrix_tables, decile_tables = [], [], []
    event_quality_tables, event_decile_tables = [], []
    risk_tables, risk_year_tables = [], []
    tie_tables, cost_tables, loyo_tables, reset_rows, daily_rows = [], [], [], [], []
    trace_tables, input_targets = [], {}
    for split in ("train", "historical_valid"):
        target = load_target(split)
        input_targets[split] = target
        account = load_account(split)
        account_dates = pd.DatetimeIndex(account.index)
        daily, active, score, target = portfolio_panel(split, state_table, run_dir, target, account_dates)
        daily.to_csv(metrics_dir / f"daily_account_replay_{split}.csv", index_label="Date")
        daily_rows.append({"split": split, **daily_metrics(daily),
                           "account_date_count": int(len(account_dates)),
                           "target_coverage": float(target.groupby(level="Date").apply(lambda s: s.notna().mean()).reindex(account_dates).mean())})

        position_rows = active.loc[active.portfolio_side.isin(["long", "short", "neutral"])].copy()
        keys = ["portfolio_side", "source_label"]
        source_tables.append(weighted_group_summary(position_rows, keys, account_dates).assign(split=split))
        matrix_keys = ["portfolio_side", "source_label", "renewal_bucket", "sleeve_age_bucket", "event_age_bucket"]
        matrix_tables.append(weighted_group_summary(position_rows, matrix_keys, account_dates).assign(split=split))
        decile_tables.append(weighted_group_summary(position_rows, ["portfolio_side", "source_label", "absolute_score_decile"], account_dates).assign(split=split))
        # Source × side × age contribution by calendar year, with partial years explicit.
        year_rows = []
        for year in sorted(account_dates.year.unique()):
            dates_y = account_dates[account_dates.year == year]
            rows_y = position_rows.loc[position_rows.index.get_level_values("Date").isin(dates_y)]
            yy = weighted_group_summary(rows_y, matrix_keys, dates_y)
            if not yy.empty:
                yy["split"] = split; yy["year"] = int(year); yy["partial_year"] = bool(year in {2016, 2026})
                year_rows.append(yy)
        if year_rows:
            pd.concat(year_rows, ignore_index=True).to_csv(metrics_dir / f"source_side_by_year_{split}.csv", index=False)

        quality, event_deciles = event_quality(event_features, target, split)
        event_quality_tables.append(quality); event_decile_tables.append(event_deciles)
        tie_tables.append(tie_stress(split, run_dir, score, target, account_dates))
        cost_tables.append(cost_stress(split, score, target, account_dates))
        loyo_tables.append(loyo_stress(split, daily))
        reset_rows.append(reset_audit(state_table, split))
        risk, risk_year = risk_exposure(active, split, account_dates)
        risk_tables.append(risk); risk_year_tables.append(risk_year)

        raw, beta, market = load_raw_h1_sources(split)
        trace, target_delta = make_trace_outcomes(sample, event_features, state_table, target, active, split, raw, beta, market)
        trace["split"] = split
        trace_tables.append(trace)
        if np.isfinite(target_delta) and target_delta > 2e-12:
            raise AssertionError(f"H1 target raw-return/date alignment failed: {split} max delta={target_delta}")

    source_summary = pd.concat(source_tables, ignore_index=True)
    matrix = pd.concat(matrix_tables, ignore_index=True)
    decile = pd.concat(decile_tables, ignore_index=True)
    event_quality_frame = pd.concat(event_quality_tables, ignore_index=True)
    event_decile_frame = pd.concat(event_decile_tables, ignore_index=True)
    tie = pd.concat(tie_tables, ignore_index=True)
    cost = pd.concat(cost_tables, ignore_index=True)
    loyo = pd.concat(loyo_tables, ignore_index=True)
    risk = pd.concat(risk_tables, ignore_index=True)
    risk_year = pd.concat(risk_year_tables, ignore_index=True)
    trace_final = pd.concat(trace_tables).sort_index()

    source_summary.to_csv(metrics_dir / "source_side_attribution.csv", index=False)
    matrix.to_csv(metrics_dir / "source_side_renewal_age_matrix.csv", index=False)
    decile.to_csv(metrics_dir / "source_side_absolute_score_decile.csv", index=False)
    event_quality_frame.to_csv(metrics_dir / "event_only_h1_quality.csv", index=False)
    event_decile_frame.to_csv(metrics_dir / "event_only_h1_score_deciles.csv", index=False)
    tie.to_csv(metrics_dir / "tie_order_stress.csv", index=False)
    cost.to_csv(metrics_dir / "cost_stress.csv", index=False)
    loyo.to_csv(metrics_dir / "leave_one_year_out.csv", index=False)
    risk.to_csv(metrics_dir / "risk_exposure.csv", index=False)
    risk_year.to_csv(metrics_dir / "risk_exposure_by_year.csv", index=False)
    pd.DataFrame(reset_rows).to_csv(metrics_dir / "reset_missing_audit.csv", index=False)
    pd.DataFrame(daily_rows).to_csv(metrics_dir / "baseline_daily_summary.csv", index=False)
    trace_final.to_parquet(pred_dir / "low_branch_trace.parquet", compression="zstd")
    trace_final.to_csv(pred_dir / "low_branch_trace.csv", index=True)

    # Reconciliation and sensitivity summaries used in the final report.
    aggregate = {
        "phase": "fixed SN1_H1 development audit; no candidate evaluation",
        "candidate_count": 0, "paper_data_accessed": False, "raw_target_file_accessed": False,
        "train_and_historical_valid_are_development": True,
        "pnl_blind_sample_lock_sha256": sha(audit_dir / "low_trace_sample_lock.json"),
        "event_trace_preparation_sha256": sha(run_dir / TRACE_DIR_SUFFIX / "audit/trace_preparation_manifest.json"),
        "h1_target_reconstruction_max_abs_delta": {
            split: float(trace_final.loc[trace_final.split.eq(split), "target_reconstruction_delta"].dropna().abs().max())
            for split in ("train", "historical_valid")
        },
        "simultaneous_high_low_event_rows": int((state_table.high_event & state_table.low_event).sum()),
        "source_attribution_net_reconciliation_max_abs": None,
        "tie_stress_changed_quintile_rows_max_by_split": tie.groupby("split").changed_quintile_rows.max().astype(int).to_dict(),
        "row_shuffle_parquet_roundtrip_exact": bool(tie.loc[tie.stress.eq("row_shuffle_parquet_roundtrip"), "roundtrip_weight_max_abs_delta"].eq(0).all()),
        "reset_state_match_pass_by_split": {r["split"]: r["reset_rows_high_low_match_raw_within_2e_12"] for r in reset_rows},
        "input_hashes": {p: sha(ROOT / p) for p in sorted(set(accesses))},
        "accessed_parquets": sorted(set(accesses)),
        "code_sha256": {
            "research/experiments/sn1_final_diagnostics.py": sha(Path(__file__).resolve()),
            "research/experiments/sn1_low_branch_trace.py": sha(ROOT / "research/experiments/sn1_low_branch_trace.py"),
            "research/experiments/state_persistence_audit.py": sha(ROOT / "research/experiments/state_persistence_audit.py"),
            "research/evaluation.py": sha(ROOT / "research/evaluation.py"),
            "stock_comp_2026/strategies/dm_variable_box_breakout/features.py": sha(ROOT / "stock_comp_2026/strategies/dm_variable_box_breakout/features.py"),
            "stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py": sha(ROOT / "stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py"),
            "stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py": sha(ROOT / "stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py"),
        },
        "outputs": {},
    }
    # Contributions are an additive account attribution by current Date×Code side/source.
    for split in ("train", "historical_valid"):
        split_rows = matrix.loc[matrix.split.eq(split)]
        grouped = split_rows.annual_net_contribution.sum()
        total = next(r["annual_net"] for r in daily_rows if r["split"] == split)
        aggregate["source_attribution_net_reconciliation_max_abs"] = max(
            aggregate["source_attribution_net_reconciliation_max_abs"] or 0.0, abs(float(grouped - total)))
    outputs = [p for p in run_dir.rglob("*") if p.is_file() and p.name not in {"final_diagnostics_manifest.json", "run.json"}]
    aggregate["outputs"] = {str(p.relative_to(ROOT)): sha(p) for p in sorted(outputs)}
    write_json(audit_dir / "final_diagnostics_manifest.json", aggregate)
    return aggregate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run_analysis(args.run_dir.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
