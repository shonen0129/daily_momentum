#!/usr/bin/env python3
"""Fixed-current-graph NCMOM20 descriptive backtest for 2024.

This is deliberately a one-period research diagnostic, not a PIT feature builder
or submission route. It uses the current JP_Market_Vis graph as held fixed over
2024, and only the 2024 Valid target rows requested for this run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from research import evaluation
from stock_comp_2026.evaluate_script import compute_weight
from stock_comp_2026.strategies.dm_variable_box_breakout import features, submission

START = pd.Timestamp("2024-01-04")
END = pd.Timestamp("2024-12-30")
ONE_WAY_COST = 0.001
ANNUALIZATION = 252
GRAPH_EDGE = "major_customer"
VALID_INPUT_COLUMNS = features.INPUT_COLUMNS


def sha256(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def dump_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def date_index(frame: pd.DataFrame) -> pd.DatetimeIndex:
    if isinstance(frame.index, pd.MultiIndex) and "Date" in frame.index.names:
        return pd.DatetimeIndex(frame.index.get_level_values("Date"))
    return pd.DatetimeIndex(frame.index)


def stage_inputs(input_dir: Path, stage_dir: Path) -> dict:
    """Link full Train sources; project Valid feature inputs through END only."""
    stage_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"valid_date_filter_inclusive_end": str(END.date()), "files": {}}
    for name in VALID_INPUT_COLUMNS:
        train_src = input_dir / f"{name}_train.parquet"
        if not train_src.is_file():
            raise FileNotFoundError(train_src)
        (stage_dir / train_src.name).symlink_to(train_src.resolve())
        manifest["files"][train_src.name] = {
            "source": str(train_src.relative_to(ROOT)),
            "mode": "Train input; baseline fitting only",
            "sha256": sha256(train_src),
        }

        valid_src = input_dir / f"{name}_valid.parquet"
        if not valid_src.is_file():
            raise FileNotFoundError(valid_src)
        schema_names = set(pq.read_schema(valid_src).names)
        index_columns = [column for column in ("Date", "Code") if column in schema_names]
        projected = pq.read_table(
            valid_src,
            columns=VALID_INPUT_COLUMNS[name] + index_columns,
            filters=[("Date", "<=", END)],
        ).to_pandas().sort_index()
        if list(projected.index.names) != (["Date", "Code"] if "Code" in schema_names else ["Date"]):
            raise AssertionError(f"Projected {name}_valid index lost its competition keys: {projected.index.names}")
        valid_dst = stage_dir / valid_src.name
        projected.to_parquet(valid_dst)
        dates = date_index(projected)
        manifest["files"][valid_src.name] = {
            "source": str(valid_src.relative_to(ROOT)),
            "mode": "feature input, rows Date <= 2024-12-30",
            "rows": int(len(projected)),
            "max_date": str(dates.max().date()),
            "sha256_projected": sha256(valid_dst),
        }

    train_target = input_dir / "target_1day_train.parquet"
    if not train_target.is_file():
        raise FileNotFoundError(train_target)
    (stage_dir / train_target.name).symlink_to(train_target.resolve())
    manifest["train_target"] = {
        "source": str(train_target.relative_to(ROOT)),
        "mode": "Train-only labels for fixed baseline reproduction",
        "sha256": sha256(train_target),
    }
    if any("target_1day_valid.parquet" in p.name for p in stage_dir.iterdir()):
        raise AssertionError("Valid target must not enter baseline reconstruction staging")
    return manifest


def load_residual_series(stage_dir: Path) -> tuple[pd.Series, pd.DatetimeIndex]:
    returns = []
    betas = []
    markets = []
    for split in ("train", "valid"):
        path = stage_dir / f"raw_return_1day_{split}.parquet"
        returns.append(pd.read_parquet(path, columns=["Return"])["Return"].sort_index())
        path = stage_dir / f"beta_1day_{split}.parquet"
        betas.append(pd.read_parquet(path, columns=["Return"])["Return"].sort_index())
        path = stage_dir / f"topix_return_1day_{split}.parquet"
        markets.append(pd.read_parquet(path, columns=["Return"])["Return"].sort_index())

    raw = pd.concat(returns).sort_index()
    beta = pd.concat(betas).sort_index()
    if not raw.index.is_unique or not beta.index.is_unique or not raw.index.equals(beta.index):
        raise AssertionError("Raw return and beta panels are not one-to-one aligned")
    topix = pd.concat(markets).sort_index()
    if not topix.index.is_unique:
        raise AssertionError("TOPIX panel has duplicate dates")
    dates = pd.DatetimeIndex(raw.index.get_level_values("Date"))
    market_values = topix.reindex(dates).to_numpy(dtype=float)
    if not np.isfinite(market_values).all():
        raise AssertionError("TOPIX return is missing for a price-panel date")
    values = raw.to_numpy(dtype=float) - beta.to_numpy(dtype=float) * market_values
    residual = pd.Series(values, index=raw.index, name="residual_return").replace([np.inf, -np.inf], np.nan)
    return residual.sort_index(), pd.DatetimeIndex(dates.unique().sort_values())


def residual_history(residual: pd.Series, calendar: pd.DatetimeIndex) -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Store per-code return dates, residuals, and segment starts (gap >20 days)."""
    result = {}
    date_values = pd.DatetimeIndex(residual.index.get_level_values("Date"))
    ordinals = calendar.get_indexer(date_values)
    if (ordinals < 0).any():
        raise AssertionError("A return date is outside the market calendar")
    code_values = residual.index.get_level_values("Code").to_numpy()
    value_array = residual.to_numpy(dtype=float)
    for code, positions in pd.Series(np.arange(len(residual)), index=residual.index).groupby(level="Code", sort=False).indices.items():
        pos = np.asarray(positions, dtype=int)
        code_dates = date_values[pos].to_numpy(dtype="datetime64[ns]")
        code_values_resid = value_array[pos]
        code_ordinals = ordinals[pos]
        boundaries = np.r_[0, np.flatnonzero(np.diff(code_ordinals) > 20) + 1].astype(int)
        result[str(code)] = (code_dates, code_values_resid, boundaries)
    return result


def prior_sum(history, code: str, signal_date: pd.Timestamp, window: int) -> float:
    record = history.get(str(code))
    if record is None:
        return np.nan
    dates, values, starts = record
    pos = int(np.searchsorted(dates, np.datetime64(signal_date), side="left"))
    if pos < 1:
        return np.nan
    last = pos - 1
    segment_no = int(np.searchsorted(starts, last, side="right") - 1)
    start = int(starts[segment_no])
    if last + 1 - start < window:
        return np.nan
    window_values = values[last + 1 - window : last + 1]
    if len(window_values) != window or not np.isfinite(window_values).all():
        return np.nan
    return float(window_values.sum())


def current_graph_edges(m5_path: Path, m4_path: Path, price_codes: set[str]):
    m5 = json.loads(m5_path.read_text(encoding="utf-8"))
    m4 = json.loads(m4_path.read_text(encoding="utf-8"))
    companies = m4.get("companies", {})

    def map_key(key: str) -> str | None:
        company = companies.get(str(key))
        if not isinstance(company, dict):
            return None
        security_code = str(company.get("securities_code") or "")
        if len(security_code) != 4:
            return None
        return f"{security_code}0"

    major_customer = [r for r in m5.get("relations", []) if r.get("relation_type") == GRAPH_EDGE]
    eligible = [
        r for r in major_customer
        if r.get("status") == "confirmed"
        and r.get("source", {}).get("type") == "listed"
        and r.get("target", {}).get("type") == "listed"
    ]
    rows = []
    mapping_failures = []
    as_of_after_2024 = 0
    as_of_missing = 0
    for relation in eligible:
        source_key = str(relation["source"]["key"])
        target_key = str(relation["target"]["key"])
        supplier = map_key(source_key)
        customer = map_key(target_key)
        if supplier is None or customer is None:
            mapping_failures.append((source_key, target_key, supplier, customer))
            continue
        evidence_dates = [e.get("as_of") for e in relation.get("evidence", []) if e.get("as_of")]
        if not evidence_dates:
            as_of_missing += 1
        elif max(evidence_dates)[:4] > "2024":
            as_of_after_2024 += 1
        rows.append({
            "relation_id": relation.get("relation_id"),
            "source_key": source_key,
            "target_key": target_key,
            "supplier_code": supplier,
            "customer_code": customer,
            "as_of_latest": max(evidence_dates) if evidence_dates else None,
        })

    edge_df = pd.DataFrame(rows).drop_duplicates(["supplier_code", "customer_code"]).sort_values(
        ["supplier_code", "customer_code"]
    ).reset_index(drop=True)
    code_map = {}
    for key, company in companies.items():
        if isinstance(company, dict):
            mapped = map_key(str(key))
            if mapped:
                code_map[str(key)] = mapped
    code_collisions = Counter(code_map.values())
    diagnostics = {
        "m5_version": m5.get("version"),
        "m5_generated_at": m5.get("generated_at"),
        "m5_dataset_id": m5.get("dataset_id"),
        "m4_version": m4.get("version"),
        "m4_generated_at": m4.get("generated_at"),
        "total_relations": len(m5.get("relations", [])),
        "major_customer_all_status": len(major_customer),
        "major_customer_confirmed_listed_to_listed": len(eligible),
        "mapped_confirmed_listed_to_listed_edges_before_dedup": len(rows),
        "deduplicated_mapped_edges": len(edge_df),
        "unmapped_confirmed_listed_to_listed_edges": len(mapping_failures),
        "mapping_failure_examples": [list(row) for row in mapping_failures[:10]],
        "m4_security_code_collisions": int(sum(n > 1 for n in code_collisions.values())),
        "mapped_supplier_codes_present_in_2024_price_panel": int(
            edge_df.supplier_code.isin(price_codes).sum()
        ),
        "mapped_customer_codes_present_in_2024_price_panel": int(
            edge_df.customer_code.isin(price_codes).sum()
        ),
        "edges_with_as_of_after_2024": as_of_after_2024,
        "edges_with_no_as_of": as_of_missing,
        "edge_evidence_has_published_timestamp": any(
            "published" in evidence
            for relation in eligible
            for evidence in relation.get("evidence", [])
        ),
    }
    return edge_df, diagnostics


def build_network_features(target_index: pd.MultiIndex, edge_df: pd.DataFrame, history: dict) -> pd.DataFrame:
    target_dates = pd.DatetimeIndex(target_index.get_level_values("Date").unique().sort_values())
    supplier_to_customers = edge_df.groupby("supplier_code", sort=False).customer_code.apply(list).to_dict()
    customer_to_suppliers = edge_df.groupby("customer_code", sort=False).supplier_code.apply(list).to_dict()

    customer_codes = set(edge_df.customer_code.astype(str)) | set(edge_df.supplier_code.astype(str))
    lookup20 = {}
    lookup60 = {}
    for date in target_dates:
        for code in customer_codes:
            lookup20[(date, code)] = prior_sum(history, code, date, 20)
            lookup60[(date, code)] = prior_sum(history, code, date, 60)

    values = np.full((len(target_index), 5), np.nan, dtype=float)
    date_values = target_index.get_level_values("Date")
    code_values = target_index.get_level_values("Code").astype(str)
    for row_position, (date, supplier) in enumerate(zip(date_values, code_values)):
        customers = supplier_to_customers.get(supplier, [])
        customer_mom = [lookup20.get((date, str(code)), np.nan) for code in customers]
        finite_customer = [value for value in customer_mom if np.isfinite(value)]
        if finite_customer:
            values[row_position, 0] = float(np.mean(finite_customer))
        values[row_position, 1] = float(len(customers))
        values[row_position, 2] = float(len(finite_customer))
        values[row_position, 3] = lookup60.get((date, supplier), np.nan)

        upstream = customer_to_suppliers.get(supplier, [])
        supplier_mom = [lookup20.get((date, str(code)), np.nan) for code in upstream]
        finite_supplier = [value for value in supplier_mom if np.isfinite(value)]
        if finite_supplier:
            values[row_position, 4] = float(np.mean(finite_supplier))
    return pd.DataFrame(
        values,
        index=target_index,
        columns=["ncmom20", "n_customers_total", "n_customers_priced", "own_rs60", "reverse_supplier_mom20"],
    )


def future_return_mutation_check(
    target_index: pd.MultiIndex,
    edge_df: pd.DataFrame,
    history: dict,
    reference: pd.DataFrame,
    cutoff: pd.Timestamp,
) -> dict:
    """Confirm later customer/supplier return changes cannot alter earlier features."""
    mutated = {}
    changed_rows = 0
    for code, (dates, values, starts) in history.items():
        changed = dates > np.datetime64(cutoff)
        new_values = values.copy()
        finite = changed & np.isfinite(new_values)
        new_values[finite] += 0.123456789
        changed_rows += int(finite.sum())
        mutated[code] = (dates, new_values, starts)
    replay = build_network_features(target_index, edge_df, mutated)
    date_mask = target_index.get_level_values("Date") <= cutoff
    columns = ["ncmom20", "own_rs60", "reverse_supplier_mom20"]
    before = reference.loc[date_mask, columns].to_numpy(dtype=float)
    after = replay.loc[date_mask, columns].to_numpy(dtype=float)
    unchanged = bool(np.array_equal(before, after, equal_nan=True))
    return {
        "status": "PASS" if unchanged and changed_rows > 0 else "FAIL",
        "cutoff_inclusive": str(cutoff.date()),
        "future_residual_rows_mutated": changed_rows,
        "feature_rows_compared_through_cutoff": int(date_mask.sum()),
        "features_checked": columns,
        "max_abs_difference": float(np.nanmax(np.abs(before - after))) if before.size else 0.0,
        "prefix_unchanged": unchanged,
    }


def quintiles(signal: pd.Series) -> pd.Series:
    signal = signal.sort_index()
    ranking_input = signal.fillna(0.0)
    ranks = ranking_input.groupby(level="Date", sort=False).rank(method="first")
    q = ranks.groupby(level="Date", sort=False).transform(
        lambda day: pd.qcut(day, 5, labels=False)
    )
    return q.astype("Int64").rename("quintile")


def observed_quintiles(signal: pd.Series) -> pd.Series:
    """Quintiles among observed values only; missing network/RS values stay missing."""
    signal = signal.dropna().sort_index()
    if signal.empty:
        return pd.Series(dtype="Int64", index=signal.index, name="quintile")
    ranks = signal.groupby(level="Date", sort=False).rank(method="first")
    q = ranks.groupby(level="Date", sort=False).transform(
        lambda day: pd.qcut(day, 5, labels=False) if len(day) >= 5 else pd.Series(pd.NA, index=day.index)
    )
    return q.astype("Int64").rename("quintile")


def daily_rankic(signal: pd.Series, target: pd.Series) -> pd.Series:
    signal, target = signal.align(target, join="inner")
    valid = signal.notna() & target.notna()
    signal = signal.where(valid)
    target = target.where(valid)
    x = signal.groupby(level="Date", sort=False).rank(method="average")
    y = target.groupby(level="Date", sort=False).rank(method="average")
    x = x - x.groupby(level="Date", sort=False).transform("mean")
    y = y - y.groupby(level="Date", sort=False).transform("mean")
    num = (x * y).groupby(level="Date", sort=False).sum(min_count=1)
    den = np.sqrt(
        x.pow(2).groupby(level="Date", sort=False).sum(min_count=1)
        * y.pow(2).groupby(level="Date", sort=False).sum(min_count=1)
    )
    return (num / den).rename("rankic")


def eligible_weights(signal: pd.Series, target_index: pd.MultiIndex) -> tuple[pd.Series, pd.Series]:
    signal = signal.dropna().sort_index()
    if signal.empty:
        return pd.Series(0.0, index=target_index), pd.Series(dtype="Int64")
    if signal.groupby(level="Date").size().min() < 5:
        raise AssertionError("Fewer than five covered stocks on a portfolio date")
    frame = signal.to_frame("Return")
    weight_subset = compute_weight(frame).iloc[:, 0]
    quintile = quintiles(signal)
    weights = pd.Series(0.0, index=target_index, name="weight")
    weights.loc[weight_subset.index] = weight_subset
    return weights.sort_index(), quintile


def full_weights(signal: pd.Series, target_index: pd.MultiIndex) -> tuple[pd.Series, pd.Series]:
    signal = signal.reindex(target_index).sort_index()
    frame = signal.to_frame("Return")
    weight = compute_weight(frame).iloc[:, 0].rename("weight")
    return weight, quintiles(signal)


def account(signal: pd.Series, target: pd.Series, universe: str, *, restricted=False) -> tuple[dict, pd.DataFrame]:
    target = target.sort_index()
    signal = signal.reindex(target.index)
    if restricted:
        weight, q = eligible_weights(signal, target.index)
    else:
        weight, q = full_weights(signal, target.index)
    turnover = weight.groupby(level="Code", sort=False).diff().abs().fillna(weight.abs())
    gross_position = weight * target
    cost_position = ONE_WAY_COST * turnover
    # Match evaluate_script.compute_pl exactly: NaN target rows drop both gross
    # P/L and that row's cost from official daily net; keep all-position cost too.
    daily_gross = gross_position.groupby(level="Date", sort=False).sum(min_count=1)
    daily_net = (gross_position - cost_position).groupby(level="Date", sort=False).sum(min_count=1)
    daily_cost_all = cost_position.groupby(level="Date", sort=False).sum(min_count=1)
    daily_cost = daily_gross - daily_net
    long = (weight.clip(lower=0.0) * target).groupby(level="Date", sort=False).sum(min_count=1)
    short = (weight.clip(upper=0.0) * target).groupby(level="Date", sort=False).sum(min_count=1)
    rankic = daily_rankic(signal, target)
    q_frame = pd.DataFrame(index=daily_gross.index)
    for qid in range(5):
        selected = q.eq(qid).reindex(target.index, fill_value=False)
        q_frame[f"q{qid+1}"] = target.where(selected).groupby(level="Date", sort=False).mean()
    daily = pd.DataFrame({
        "gross": daily_gross,
        "net": daily_net,
        "turnover": turnover.groupby(level="Date", sort=False).sum(),
        "cost": daily_cost,
        "cost_all": daily_cost_all,
        "long": long,
        "short": short,
        "rankic": rankic,
    }).join(q_frame)
    q_mean = daily[[f"q{k}" for k in range(1, 6)]].mean()
    wealth = np.r_[1.0, (1.0 + daily.net.fillna(0.0).to_numpy()).cumprod()]
    additive = np.r_[0.0, daily.net.fillna(0.0).cumsum().to_numpy()]
    metric = {
        "universe": universe,
        "signal_days": int(daily.index.nunique()),
        "rankic_days": int(daily.rankic.notna().sum()),
        "covered_stock_days": int(signal.notna().sum()),
        "all_stock_days": int(len(target)),
        "coverage": float(signal.notna().mean()),
        "mean_rankic": float(daily.rankic.mean()),
        "rankic_hac5_t": evaluation.hac_t(daily.rankic),
        "rankic_hit_ratio": float((daily.rankic.dropna() > 0).mean()),
        "gross_sharpe": evaluation.sharpe(daily.gross),
        "net_sharpe": evaluation.sharpe(daily.net),
        "annual_gross_pl": float(daily.gross.mean() * ANNUALIZATION),
        "annual_net_pl": float(daily.net.mean() * ANNUALIZATION),
        "annual_cost": float(daily.cost.mean() * ANNUALIZATION),
        "annual_cost_all_positions": float(daily.cost_all.mean() * ANNUALIZATION),
        "average_daily_turnover": float(daily.turnover.mean()),
        "max_drawdown_compound": float(np.min(wealth / np.maximum.accumulate(wealth) - 1.0)),
        "max_drawdown_additive": float(np.min(additive - np.maximum.accumulate(additive))),
        "period_gross_pl": float(daily.gross.sum()),
        "period_net_pl": float(daily.net.sum()),
        "period_cost": float(daily.cost.sum()),
        "period_cost_all_positions": float(daily.cost_all.sum()),
        "period_long_pl": float(daily.long.sum()),
        "period_short_pl": float(daily.short.sum()),
        "annual_long_pl": float(daily.long.mean() * ANNUALIZATION),
        "annual_short_pl": float(daily.short.mean() * ANNUALIZATION),
        "q_monotonicity_spearman": float(spearmanr(np.arange(1, 6), q_mean.to_numpy()).statistic),
        **{f"q{k}_mean_return": float(q_mean[f"q{k}"]) for k in range(1, 6)},
        "q5_minus_q1": float(q_mean["q5"] - q_mean["q1"]),
    }
    daily.index.name = "Date"
    return metric, daily


def conditional_rankic(signal: pd.Series, target: pd.Series, bucket: pd.Series, name: str) -> pd.DataFrame:
    joined = pd.concat([signal.rename("signal"), target.rename("target"), bucket.rename("bucket")], axis=1)
    joined = joined.dropna(subset=["signal", "target", "bucket"])
    rows = []
    for group_id, frame in joined.groupby("bucket", sort=True):
        day_values = []
        for _, day in frame.groupby(level="Date", sort=True):
            if len(day) < 3 or day.signal.nunique() < 2 or day.target.nunique() < 2:
                continue
            day_values.append(float(spearmanr(day.signal, day.target).statistic))
        values = pd.Series(day_values, dtype=float)
        rows.append({
            "conditioning": name,
            "bucket": int(group_id) + 1,
            "stock_days": int(len(frame)),
            "rankic_days": int(values.notna().sum()),
            "mean_rankic": float(values.mean()) if len(values) else np.nan,
            "rankic_hac5_t": evaluation.hac_t(values),
            "rankic_hit_ratio": float((values > 0).mean()) if len(values) else np.nan,
        })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=ROOT / "stock_comp_2026/input")
    parser.add_argument("--m5", type=Path, required=True)
    parser.add_argument("--m4", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/DM-20261002-04/metrics")
    parser.add_argument("--audit-dir", type=Path, default=ROOT / "reports/DM-20261002-04/audit")
    args = parser.parse_args()
    started = time.monotonic()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.audit_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ncmom20-2024-") as temp_name:
        stage_dir = Path(temp_name) / "input"
        input_manifest = stage_inputs(args.input_dir, stage_dir)

        # Current baseline replay is fixed and Train-fitted; no Valid target is loaded here.
        baseline_candidates = submission.predict_candidates(data_dir=stage_dir, split="valid")
        baseline_all = baseline_candidates["SIDE_SOURCE_SEPARATION"]["Return"].sort_index()

        target_path = args.input_dir / "target_1day_valid.parquet"
        target_frame = pd.read_parquet(
            target_path,
            columns=["Return"],
            filters=[("Date", ">=", START), ("Date", "<=", END)],
        ).sort_index()
        target = target_frame["Return"].replace([np.inf, -np.inf], np.nan)
        if not isinstance(target.index, pd.MultiIndex) or list(target.index.names) != ["Date", "Code"]:
            raise AssertionError("Official target is not indexed by Date and Code")
        dates = pd.DatetimeIndex(target.index.get_level_values("Date").unique().sort_values())
        if dates.min() != START or dates.max() != END or len(dates) != 245:
            raise AssertionError(f"Unexpected 2024 target dates: {len(dates)}, {dates.min()}, {dates.max()}")
        if target.notna().sum() == 0:
            raise AssertionError("2024 official target has no finite values")
        target.index = target.index.set_names(["Date", "Code"])

        baseline = baseline_all.reindex(target.index)
        if baseline.isna().any() or not np.isfinite(baseline.to_numpy()).all():
            raise AssertionError("Current SN1_H1 score does not cover the full 2024 target panel")

        residual, market_calendar = load_residual_series(stage_dir)
        history = residual_history(residual, market_calendar)
        code_panel = set(target.index.get_level_values("Code").astype(str))
        edge_df, graph_meta = current_graph_edges(args.m5, args.m4, code_panel)
        features_2024 = build_network_features(target.index, edge_df, history)
        ncmom = features_2024["ncmom20"].replace([np.inf, -np.inf], np.nan)
        reverse = features_2024["reverse_supplier_mom20"].replace([np.inf, -np.inf], np.nan)
        own_rs = features_2024["own_rs60"].replace([np.inf, -np.inf], np.nan)

        # Official full-universe baseline and fixed, price-covered matched-universe accounts.
        full_baseline_metrics, full_baseline_daily = account(baseline, target, "SN1_H1_full_official_universe")
        covered = ncmom.notna()
        baseline_matched = baseline.where(covered)
        ncmom_metrics, ncmom_daily = account(ncmom, target, "NCMOM20_customer_to_supplier_covered_universe", restricted=True)
        baseline_matched_metrics, baseline_matched_daily = account(
            baseline_matched, target, "SN1_H1_matched_NCMOM20_covered_universe", restricted=True
        )
        reverse_metrics, reverse_daily = account(
            reverse, target, "reverse_supplier_to_customer_covered_universe", restricted=True
        )
        baseline_matched_metrics["comparison_to"] = "same NCMOM20-covered supplier rows"
        ncmom_metrics["comparison_to"] = "same NCMOM20-covered supplier rows"
        reverse_metrics["comparison_to"] = "reverse-direction covered rows"
        full_baseline_metrics["comparison_to"] = "all official 2024 target rows"

        summary_rows = [full_baseline_metrics, baseline_matched_metrics, ncmom_metrics, reverse_metrics]
        pd.DataFrame(summary_rows).to_csv(args.output_dir / "ncmom20_diagnostics.csv", index=False)
        daily_out = pd.concat({
            "SN1_H1_full": full_baseline_daily,
            "SN1_H1_matched": baseline_matched_daily,
            "NCMOM20": ncmom_daily,
            "reverse_supplier_mom20": reverse_daily,
        }, names=["strategy"])
        daily_out.to_csv(args.output_dir / "daily_account_2024.csv")

        # One calendar year was explicitly requested; it is reported as one partial-independent annual slice.
        yearly = pd.DataFrame(summary_rows)
        yearly.insert(0, "year", 2024)
        yearly.to_csv(args.output_dir / "ncmom20_yearly.csv", index=False)

        sn1_q = quintiles(baseline)
        rs_q = observed_quintiles(own_rs)
        cond_sn1 = conditional_rankic(ncmom, target, sn1_q, "SN1_H1 score quintile")
        cond_rs = conditional_rankic(ncmom, target, rs_q, "own RS60 quintile")
        cond_sn1.to_csv(args.output_dir / "ncmom20_conditional_sn1.csv", index=False)
        cond_rs.to_csv(args.output_dir / "ncmom20_conditional_rs60.csv", index=False)

        per_day_corr = []
        for day, positions in ncmom.groupby(level="Date", sort=True).groups.items():
            left = ncmom.loc[positions]
            pair_rs = pd.concat(
                [left.rename("ncmom20"), own_rs.reindex(left.index).rename("own_rs60")], axis=1
            ).dropna()
            pair_sn1 = pd.concat(
                [left.rename("ncmom20"), baseline.reindex(left.index).rename("SN1_H1")], axis=1
            ).dropna()
            per_day_corr.append({
                "Date": day,
                "corr_ncmom20_own_rs60_spearman": float(spearmanr(pair_rs.ncmom20, pair_rs.own_rs60).statistic)
                if len(pair_rs) >= 3 and pair_rs.ncmom20.nunique() > 1 and pair_rs.own_rs60.nunique() > 1 else np.nan,
                "corr_ncmom20_sn1_spearman": float(spearmanr(pair_sn1.ncmom20, pair_sn1.SN1_H1).statistic)
                if len(pair_sn1) >= 3 and pair_sn1.ncmom20.nunique() > 1 and pair_sn1.SN1_H1.nunique() > 1 else np.nan,
            })
        corr = pd.DataFrame(per_day_corr)
        corr.to_csv(args.output_dir / "ncmom20_daily_correlations.csv", index=False)
        correlation_summary = {
            "mean_daily_spearman_ncmom20_own_rs60": float(corr.corr_ncmom20_own_rs60_spearman.mean()),
            "mean_daily_spearman_ncmom20_sn1_h1": float(corr.corr_ncmom20_sn1_spearman.mean()),
            "median_daily_spearman_ncmom20_own_rs60": float(corr.corr_ncmom20_own_rs60_spearman.median()),
            "median_daily_spearman_ncmom20_sn1_h1": float(corr.corr_ncmom20_sn1_spearman.median()),
        }

        reverse_ic = daily_rankic(reverse, target)
        reverse_summary = {
            "direction": "reverse supplier-to-customer sanity check only",
            "mean_rankic": float(reverse_ic.mean()),
            "rankic_hac5_t": evaluation.hac_t(reverse_ic),
            "rankic_hit_ratio": float((reverse_ic.dropna() > 0).mean()),
            "covered_stock_days": int(reverse.notna().sum()),
            "coverage": float(reverse.notna().mean()),
            "q5_minus_q1": reverse_metrics["q5_minus_q1"],
            "net_sharpe": reverse_metrics["net_sharpe"],
            "annual_net_pl": reverse_metrics["annual_net_pl"],
        }
        customer_ic = daily_rankic(ncmom, target)
        directional_rows = [
            {
                "direction": "customer-to-supplier (specified)",
                "mean_rankic": float(customer_ic.mean()),
                "rankic_hac5_t": evaluation.hac_t(customer_ic),
                "rankic_hit_ratio": float((customer_ic.dropna() > 0).mean()),
                "covered_stock_days": int(ncmom.notna().sum()),
                "coverage": float(ncmom.notna().mean()),
                "q5_minus_q1": ncmom_metrics["q5_minus_q1"],
                "net_sharpe": ncmom_metrics["net_sharpe"],
                "annual_net_pl": ncmom_metrics["annual_net_pl"],
            },
            reverse_summary,
        ]
        pd.DataFrame(directional_rows).to_csv(args.output_dir / "direction_sanity_check.csv", index=False)

        coverage_by_day = pd.DataFrame({
            "target_stocks": target.groupby(level="Date").size(),
            "ncmom_covered": ncmom.notna().groupby(level="Date").sum(),
            "mean_graph_customers": features_2024.n_customers_total.groupby(level="Date").mean(),
            "mean_priced_customers": features_2024.n_customers_priced.groupby(level="Date").mean(),
        })
        coverage_by_day["coverage"] = coverage_by_day.ncmom_covered / coverage_by_day.target_stocks
        coverage_by_day.to_csv(args.output_dir / "network_coverage_daily.csv")

        panel = features_2024.copy()
        panel.insert(0, "SN1_H1", baseline)
        panel.to_parquet(args.output_dir / "prediction_panel_2024.parquet")
        graph_meta.update({
            "mapped_edges_with_supplier_in_target_panel": int(edge_df.supplier_code.isin(code_panel).sum()),
            "mapped_edges_with_customer_price_history": int(edge_df.customer_code.isin(history).sum()),
            "unique_mapped_graph_suppliers_in_target_panel": int(
                len(set(edge_df.supplier_code) & code_panel)
            ),
            "unique_target_suppliers_with_at_least_one_mapped_customer": int(
                len(set(edge_df.supplier_code) & code_panel)
            ),
            "customer_to_supplier_covered_stock_days": int(ncmom.notna().sum()),
            "official_target_stock_days": int(len(target)),
            "customer_to_supplier_stock_day_coverage": float(ncmom.notna().mean()),
            "covered_supplier_count_2024": int(
                features_2024.ncmom20.notna().groupby(level="Code").any().sum()
            ),
            "target_supplier_count_2024": int(target.index.get_level_values("Code").nunique()),
            "mean_customer_count_when_covered": float(
                features_2024.n_customers_priced.where(features_2024.ncmom20.notna()).mean()
            ),
            "mean_total_graph_customers_for_panel_suppliers": float(
                features_2024.n_customers_total.groupby(level="Code").first().mean()
            ),
        })
        # Deterministic replay plus future-return mutation. Relationship publication
        # causality remains intentionally unavailable for this user-requested run.
        deterministic_replay = build_network_features(target.index, edge_df, history)
        deterministic_ok = bool(
            np.array_equal(
                features_2024.to_numpy(dtype=float),
                deterministic_replay.to_numpy(dtype=float),
                equal_nan=True,
            )
        )
        return_prefix = future_return_mutation_check(
            target.index,
            edge_df,
            history,
            features_2024,
            pd.Timestamp("2024-06-28"),
        )
        prefix_audit = {
            "diagnostic_scope": "fixed M5 2026.09 graph and 2024 price/target window",
            "deterministic_network_feature_replay": "PASS" if deterministic_ok else "FAIL",
            "future_return_mutation_prefix_invariance": return_prefix,
            "relationship_publication_causality": "NOT_PIT_SAFE_BY_USER_REQUESTED_FIXED_GRAPH_ASSUMPTION",
            "relationship_reason": (
                "The 2026 snapshot is applied to 2024; edge evidence has as_of but no published timestamp, "
                "and the current source provides no 2024-vintage graph. No PIT relationship-mutation pass is claimed."
            ),
            "edges_with_as_of_after_2024": graph_meta["edges_with_as_of_after_2024"],
            "mapped_current_edges": int(len(edge_df)),
        }
        dump_json(args.audit_dir / "network_prefix_invariance.json", prefix_audit)
        mapping_metrics = [
            "major_customer_all_status",
            "major_customer_confirmed_listed_to_listed",
            "mapped_confirmed_listed_to_listed_edges_before_dedup",
            "deduplicated_mapped_edges",
            "unmapped_confirmed_listed_to_listed_edges",
            "m4_security_code_collisions",
            "mapped_supplier_codes_present_in_2024_price_panel",
            "mapped_customer_codes_present_in_2024_price_panel",
            "unique_mapped_graph_suppliers_in_target_panel",
            "covered_supplier_count_2024",
            "target_supplier_count_2024",
        ]
        pd.DataFrame(
            [{"metric": key, "value": graph_meta[key]} for key in mapping_metrics]
        ).to_csv(args.output_dir / "code_mapping_audit.csv", index=False)

        metrics_by_name = {row["universe"]: row for row in summary_rows}
        candidate_metrics = metrics_by_name["NCMOM20_customer_to_supplier_covered_universe"]
        matched_metrics = metrics_by_name["SN1_H1_matched_NCMOM20_covered_universe"]
        incremental_fields = [
            "mean_rankic",
            "rankic_hac5_t",
            "rankic_hit_ratio",
            "gross_sharpe",
            "net_sharpe",
            "annual_gross_pl",
            "annual_net_pl",
            "annual_cost",
            "average_daily_turnover",
            "max_drawdown_compound",
            "q5_minus_q1",
        ]
        pd.DataFrame([
            {
                "candidate": "NCMOM20_customer_to_supplier_covered_universe",
                "baseline": "SN1_H1_matched_NCMOM20_covered_universe",
                "metric": key,
                "NCMOM20": candidate_metrics[key],
                "SN1_H1_matched": matched_metrics[key],
                "delta_NCMOM20_minus_SN1_H1": candidate_metrics[key] - matched_metrics[key],
            }
            for key in incremental_fields
        ]).to_csv(args.output_dir / "incremental_vs_matched_sn1.csv", index=False)

        dump_json(args.audit_dir / "graph_and_coverage.json", graph_meta)
        dump_json(args.audit_dir / "correlation_summary.json", correlation_summary)

        code_hashes = {}
        for rel_path in [
            Path(__file__).relative_to(ROOT),
            Path("research/evaluation.py"),
            Path("stock_comp_2026/evaluate_script.py"),
            Path("stock_comp_2026/strategies/dm_variable_box_breakout/features.py"),
            Path("stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py"),
            Path("stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py"),
            Path("stock_comp_2026/strategies/dm_variable_box_breakout/submission.py"),
        ]:
            code_hashes[str(rel_path)] = sha256(ROOT / rel_path)
        run = {
            "experiment_id": "DM-20261002-04",
            "run_id": "current_graph_2024_descriptive",
            "state": "completed",
            "period": {"start_inclusive": str(START.date()), "end_inclusive": str(END.date()), "signal_dates": int(len(dates))},
            "valid_target_access": {
                "file": str(target_path.relative_to(ROOT)),
                "rows_read": int(len(target)),
                "date_filter": [str(START.date()), str(END.date())],
                "raw_target_read": False,
                "other_valid_target_dates_read": False,
            },
            "baseline": {
                "id": "SN1_H1",
                "code": "current dm_variable_box_breakout code after split-safe ATR correction",
                "model_fit_data": "Train target and Train feature rows only",
                "valid_prices_after_end_read": False,
                "prediction_rows": int(len(baseline)),
            "prediction_index_exactly_aligned": True,
            "target_nonmissing_stock_days": int(target.notna().sum()),
            "target_missing_stock_days": int(target.isna().sum()),
            "target_coverage": float(target.notna().mean()),
            },
            "network_assumption": "M5 2026.09 current major_customer graph held fixed through 2024; not PIT and not submission-usable evidence",
            "network_snapshot": {
                "m5_path": str(args.m5),
                "m4_path": str(args.m4),
                "m5_sha256": sha256(args.m5),
                "m4_sha256": sha256(args.m4),
            },
            "inputs": input_manifest,
            "code_sha256": code_hashes,
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "graph_and_coverage": graph_meta,
            "network_prefix_invariance": prefix_audit,
            "correlation_summary": correlation_summary,
            "output_sha256": {
                p.name: sha256(p)
                for p in sorted(args.output_dir.iterdir())
                if p.is_file()
            },
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
        dump_json(args.audit_dir / "run_manifest.json", run)
        print(json.dumps({
            "period_dates": len(dates),
            "target_rows": len(target),
            "graph_edges": len(edge_df),
            "coverage": graph_meta["customer_to_supplier_stock_day_coverage"],
            "metrics": summary_rows,
            "elapsed_seconds": run["elapsed_seconds"],
        }, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
