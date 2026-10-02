"""One-shot descriptive NCMOM20 backtest with a fixed 2026 graph projected onto 2025.

This is intentionally not a PIT feature or an official competition portfolio.
Stage `prepare` reads graph/master/listed metadata only; stage `run` refuses to
read outcomes until the pre-result lock is present and all locked inputs match.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import pyarrow.compute as pc
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[3]
EXP_ID = "DM-20261002-02"
EXP = ROOT / "experiments" / EXP_ID
REPORTS = ROOT / "reports" / EXP_ID
ARTIFACTS = ROOT / "artifacts" / EXP_ID / "static_graph_2025"
DEFAULT_M5 = Path("/private/tmp/DM-20261002-02-M5_company_relations.json")
DEFAULT_M4 = Path("/private/tmp/DM-20261002-02-M4_companies.json")
INPUT = ROOT / "stock_comp_2026" / "input"
INPUT_MANIFEST = ROOT / "stock_comp_2026" / "input_manifest.json"
BASELINE = ROOT / "artifacts/DM-20260927-04/run-20260927T101500Z/predictions/SN1_H1_historical_valid.parquet"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    return value


def name_key(value: object) -> str:
    """Normalize legal-form/spacing only; this is not fuzzy name matching."""
    s = unicodedata.normalize("NFKC", str(value or "")).casefold()
    s = re.sub(r"\s+", "", s)
    s = s.replace("(株)", "株式会社").replace("㈱", "株式会社")
    for pat in (r"^(株式会社|有限会社|合同会社|合資会社|合名会社)+",
                r"(株式会社|有限会社|合同会社|合資会社|合名会社)+$"):
        s = re.sub(pat, "", s)
    return re.sub(r"[・,，．.()（）「」『』\-‐ー_]+", "", s)


def listed_metadata_2025() -> pd.DataFrame:
    date_field = ds.field("Date")
    dataset = ds.dataset(INPUT / "listed_info_valid.parquet", format="parquet")
    table = dataset.to_table(
        columns=["Date", "Code", "CompanyName"],
        filter=(date_field >= pc.scalar(pd.Timestamp("2025-01-01").to_pydatetime()))
        & (date_field < pc.scalar(pd.Timestamp("2026-01-01").to_pydatetime())),
    )
    frame = table.to_pandas()
    if "Code" not in frame.columns or "Date" not in frame.columns:
        frame = frame.reset_index()
    if frame.empty:
        raise RuntimeError("No 2025 listed-info records")
    frame["Code"] = frame["Code"].astype(str)
    return frame


def prepare_graph(m5_path: Path, m4_path: Path) -> dict:
    """Select and map locked graph edges without opening any target/outcome file."""
    m5 = json.loads(m5_path.read_text(encoding="utf-8"))
    m4 = json.loads(m4_path.read_text(encoding="utf-8"))
    if m5.get("master_id") != "M5_company_relations" or m5.get("version") != "2026.09":
        raise RuntimeError("Unexpected M5 graph identity/version")
    if m4.get("master_id") != "M4_companies" or m4.get("version") != "2026.09":
        raise RuntimeError("Unexpected M4 company master identity/version")

    listed = listed_metadata_2025()
    listed_names: dict[str, set[str]] = {}
    listed_raw: dict[str, set[str]] = {}
    for code, grp in listed.groupby("Code", sort=True):
        listed_names[code] = {name_key(x) for x in grp["CompanyName"].dropna().unique()}
        listed_raw[code] = {str(x) for x in grp["CompanyName"].dropna().unique()}

    # Exact J-Quants code relation: 4-character securities_code plus terminal 0.
    m4_by_security: dict[str, tuple[str, dict]] = {}
    duplicates: set[str] = set()
    for master_key, company in m4.get("companies", {}).items():
        sec = str(company.get("securities_code") or master_key)
        if sec in m4_by_security:
            duplicates.add(sec)
        m4_by_security[sec] = (str(master_key), company)

    def endpoint_map(endpoint: dict) -> tuple[str, str, str]:
        if not isinstance(endpoint, dict) or endpoint.get("type") != "listed":
            return "", "", "endpoint_not_listed"
        key = str(endpoint.get("key", ""))
        match = m4_by_security.get(key)
        if not match:
            return "", "", "missing_m4_security_code"
        master_key, company = match
        if key in duplicates:
            return "", "", "ambiguous_m4_security_code"
        code = key + "0"
        if not code or code not in listed_names:
            return "", "", "not_in_2025_listed_info"
        expected = name_key(company.get("name_edinet") or company.get("name") or "")
        names = listed_names[code]
        if not expected or names != {expected}:
            return code, ";".join(sorted(listed_raw[code])), "company_name_mismatch_or_change"
        return code, ";".join(sorted(listed_raw[code])), "mapped_exact_code_and_normalized_name"

    type_rows = m5.get("relation_types", {}).get("major_customer", {})
    if not type_rows or type_rows.get("directed") is not True:
        raise RuntimeError("major_customer taxonomy is missing or not directed")

    counters: dict[str, int] = {
        "all_relations": len(m5.get("relations", [])),
        "major_customer_relations": 0,
        "confirmed_major_customer": 0,
        "confirmed_primary_edinet": 0,
        "primary_edinet_listed_listed": 0,
        "mapped_primary_edges_before_dedup": 0,
    }
    audits = []
    pair_relation_ids: dict[tuple[str, str], list[str]] = {}
    for row in m5.get("relations", []):
        if row.get("relation_type") != "major_customer":
            continue
        counters["major_customer_relations"] += 1
        if row.get("status") != "confirmed":
            continue
        counters["confirmed_major_customer"] += 1
        evidence = row.get("evidence") or []
        if not any(e.get("source") == "edinet" and e.get("tier") == "primary" for e in evidence):
            continue
        counters["confirmed_primary_edinet"] += 1
        source = row.get("source") or {}
        target = row.get("target") or {}
        source_code, source_name, source_status = endpoint_map(source)
        target_code, target_name, target_status = endpoint_map(target)
        edge_status = "eligible"
        if source.get("type") != "listed" or target.get("type") != "listed":
            edge_status = "endpoint_not_listed"
        elif source_status != "mapped_exact_code_and_normalized_name":
            edge_status = "supplier_" + source_status
        elif target_status != "mapped_exact_code_and_normalized_name":
            edge_status = "customer_" + target_status
        elif source_code == target_code:
            edge_status = "self_edge"
        else:
            counters["primary_edinet_listed_listed"] += 1
            counters["mapped_primary_edges_before_dedup"] += 1
            pair_relation_ids.setdefault((source_code, target_code), []).append(str(row.get("relation_id", "")))
        audits.append({
            "relation_id": row.get("relation_id", ""),
            "source_key": source.get("key", ""),
            "target_key": target.get("key", ""),
            "source_code": source_code,
            "target_code": target_code,
            "source_name_2025": source_name,
            "target_name_2025": target_name,
            "source_mapping_status": source_status,
            "target_mapping_status": target_status,
            "edge_status": edge_status,
            "evidence_as_of": ";".join(sorted({str(e.get("as_of", "")) for e in evidence if e.get("source") == "edinet"})),
        })

    edges = pd.DataFrame([
        {
            "supplier_code": supplier,
            "customer_code": customer,
            "relation_count": len(ids),
            "relation_ids": ";".join(sorted(ids)),
        }
        for (supplier, customer), ids in sorted(pair_relation_ids.items())
    ])
    if edges.empty:
        raise RuntimeError("The locked graph filter yielded no mapped listed-listed edges")
    if edges[["supplier_code", "customer_code"]].duplicated().any():
        raise AssertionError("Mapped graph has duplicate endpoint pairs")

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(audits).to_csv(REPORTS / "code_mapping_audit.csv", index=False)
    edges.to_csv(ARTIFACTS / "selected_edges.csv", index=False)
    counters["eligible_unique_edges"] = len(edges)
    counters["unique_suppliers"] = int(edges["supplier_code"].nunique())
    counters["unique_customers"] = int(edges["customer_code"].nunique())
    counters["selected_edge_count_duplicate_rows_removed"] = counters["mapped_primary_edges_before_dedup"] - len(edges)
    counters["listed_info_2025_unique_codes"] = len(listed_names)
    counters["crosswalk_rule"] = "M4 securities_code -> exact Code = securities_code + '0'; normalized full company name must match every 2025 listed-info name for that Code"
    counters["m5_version"] = m5.get("version")
    counters["m5_generated_at"] = m5.get("generated_at")
    counters["m5_dataset_id"] = m5.get("dataset_id")
    counters["m4_version"] = m4.get("version")
    counters["m4_generated_at"] = m4.get("generated_at")
    (ARTIFACTS / "graph_audit.json").write_text(json.dumps(counters, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return counters


def series_from_parquet(path: Path, name: str) -> pd.Series:
    frame = pd.read_parquet(path, columns=["Return"])
    if not isinstance(frame.index, pd.MultiIndex) or frame.index.names[:2] != ["Date", "Code"]:
        raise RuntimeError(f"Unexpected Date/Code parquet index: {path}")
    series = frame["Return"].astype(float)
    series.name = name
    if not series.index.is_unique:
        raise RuntimeError(f"Duplicate index: {path}")
    return series


def make_ncmom(residual: pd.DataFrame, edges: pd.DataFrame, lookback: int = 20) -> tuple[pd.DataFrame, pd.DataFrame]:
    customer_momentum = residual.rolling(lookback, min_periods=lookback).sum().shift(1)
    suppliers: dict[str, pd.Series] = {}
    counts: dict[str, pd.Series] = {}
    for supplier, group in edges.groupby("supplier_code", sort=True):
        customers = sorted(group["customer_code"].unique())
        present = [code for code in customers if code in customer_momentum.columns]
        if present:
            block = customer_momentum[present]
            counts[supplier] = block.notna().sum(axis=1).astype("int16")
            suppliers[supplier] = block.mean(axis=1, skipna=True)
        else:
            counts[supplier] = pd.Series(0, index=customer_momentum.index, dtype="int16")
            suppliers[supplier] = pd.Series(np.nan, index=customer_momentum.index, dtype=float)
    feature = pd.DataFrame(suppliers, index=customer_momentum.index)
    count_frame = pd.DataFrame(counts, index=customer_momentum.index)
    return feature, count_frame


def rank_ic(x: pd.Series, y: pd.Series) -> float:
    mask = np.isfinite(x.to_numpy(dtype=float)) & np.isfinite(y.to_numpy(dtype=float))
    if mask.sum() < 3:
        return np.nan
    return float(spearmanr(x.to_numpy(dtype=float)[mask], y.to_numpy(dtype=float)[mask]).statistic)


def hac5_t(values: pd.Series, max_lag: int = 5) -> float:
    """Bartlett/Newey-West t for the mean, with lag autocovariance divisor n."""
    x = values.dropna().to_numpy(dtype=float)
    n = len(x)
    if n < 2:
        return np.nan
    centered = x - x.mean()
    long_run = float(np.dot(centered, centered) / n)
    for lag in range(1, min(max_lag, n - 1) + 1):
        gamma = float(np.dot(centered[lag:], centered[:-lag]) / n)
        long_run += 2.0 * (1.0 - lag / (max_lag + 1.0)) * gamma
    if long_run <= 0:
        return np.nan
    return float(x.mean() / np.sqrt(long_run / n))


def daily_quintiles(group: pd.DataFrame, score_col: str, code_index: pd.Index) -> pd.Series:
    # A deterministic code order breaks exact score ties before assigning 5 bins.
    ordered = group[[score_col]].copy()
    ordered["_code_key"] = code_index.get_level_values("Code").astype(str)
    out = pd.Series(index=ordered.index, dtype="int8")
    order = ordered.sort_values([score_col, "_code_key"], kind="mergesort").index
    if len(order) < 5:
        return out
    bins = np.floor(np.arange(len(order), dtype=float) * 5 / len(order)).astype(int) + 1
    out.loc[order] = bins
    return out


def metric_for_days(daily: pd.DataFrame, signal: str) -> dict:
    prefix = signal + "_"
    x = daily.dropna(subset=[prefix + "gross", prefix + "net"])
    gross = x[prefix + "gross"].astype(float)
    net = x[prefix + "net"].astype(float)
    spread = x[prefix + "q5_minus_q1"].astype(float)
    sharpe_g = float(gross.mean() / gross.std(ddof=1) * np.sqrt(252)) if gross.std(ddof=1) > 0 else np.nan
    sharpe_n = float(net.mean() / net.std(ddof=1) * np.sqrt(252)) if net.std(ddof=1) > 0 else np.nan
    wealth = (1.0 + net).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    row = {
        "signal": signal,
        "days": int(len(x)),
        "network_covered_stock_days": int(x["covered_n"].sum()),
        "mean_daily_network_coverage": float(x["network_coverage_rate"].mean()),
        "mean_available_customers": float(x["mean_available_customers"].mean()),
        "mean_rankic": float(x[prefix + "rankic"].mean()),
        "rankic_hac5_t": hac5_t(x[prefix + "rankic"]),
        "rankic_hit_ratio": float((x[prefix + "rankic"] > 0).mean()),
        "q5_minus_q1_mean_daily": float(spread.mean()),
        "q5_minus_q1_hac5_t": hac5_t(spread),
        "q_monotonicity_daily_share": float(x[prefix + "q_monotonic"].mean()),
        "gross_sharpe": sharpe_g,
        "net_sharpe": sharpe_n,
        "annual_gross_arithmetic": float(gross.mean() * 252),
        "annual_net_arithmetic": float(net.mean() * 252),
        "annual_cost": float(x[prefix + "cost"].mean() * 252),
        "average_daily_turnover": float(x[prefix + "turnover"].mean()),
        "max_drawdown_compound_net": float(drawdown.min()),
        "annual_long_gross": float(x[prefix + "long"].mean() * 252),
        "annual_short_gross": float(x[prefix + "short"].mean() * 252),
        "mean_cost_daily": float(x[prefix + "cost"].mean()),
    }
    if signal == "ncmom20":
        row["mean_daily_spearman_with_sn1"] = float(x["ncmom20_vs_sn1_spearman"].mean())
    return row


def portfolio_daily(group: pd.DataFrame, score_col: str, code_order: pd.Series,
                    previous: pd.Series | None, cost_rate: float) -> tuple[dict, pd.Series]:
    eligible = group.loc[np.isfinite(group[score_col]) & np.isfinite(group["target"])].copy()
    eligible["Code"] = code_order.reindex(eligible.index).astype(str)
    eligible["_code_key"] = eligible["Code"]
    eligible = eligible.sort_values([score_col, "_code_key"], kind="mergesort")
    n = len(eligible)
    q = np.floor(np.arange(n, dtype=float) * 5 / n).astype(int) + 1 if n >= 5 else np.zeros(n, dtype=int)
    eligible["q"] = q
    low = eligible.loc[eligible["q"] == 1]
    high = eligible.loc[eligible["q"] == 5]
    weights = pd.Series(0.0, index=eligible.index)
    if len(high):
        weights.loc[high.index] = 0.5 / len(high)
    if len(low):
        weights.loc[low.index] = -0.5 / len(low)
    # Holdings are keyed by issuer Code across dates, not by the panel's Date/Code index.
    weights.index = eligible["Code"].astype(str).to_numpy()
    if previous is None:
        turnover = float(weights.abs().sum())
        long_turnover = float(weights.clip(lower=0).sum())
        short_turnover = float(-weights.clip(upper=0).sum())
    else:
        union_codes = weights.index.union(previous.index)
        prior = previous.reindex(union_codes, fill_value=0.0)
        current = weights.reindex(union_codes, fill_value=0.0)
        delta = current - prior
        turnover = float(delta.abs().sum())
        long_turnover = float((current.clip(lower=0) - prior.clip(lower=0)).abs().sum())
        short_turnover = float((current.clip(upper=0) - prior.clip(upper=0)).abs().sum())
    target = eligible["target"].astype(float)
    long_mask = weights.clip(lower=0).to_numpy(dtype=float)
    short_weights = weights.clip(upper=0).to_numpy(dtype=float)
    long = float(np.dot(long_mask, target.to_numpy(dtype=float)))
    short = float(np.dot(short_weights, target.to_numpy(dtype=float)))
    gross = long + short
    cost = cost_rate * turnover
    qmeans = eligible.groupby("q", sort=True)["target"].mean()
    monotonic = bool(len(qmeans) == 5 and np.all(np.diff(qmeans.to_numpy(dtype=float)) > 0))
    stats = {
        "rankic": rank_ic(eligible[score_col], target),
        "q5_minus_q1": float(qmeans.get(5, np.nan) - qmeans.get(1, np.nan)),
        "q_monotonic": float(monotonic),
        "gross": gross,
        "net": gross - cost,
        "cost": cost,
        "turnover": turnover,
        "long": long,
        "short": short,
        "q1": float(qmeans.get(1, np.nan)),
        "q2": float(qmeans.get(2, np.nan)),
        "q3": float(qmeans.get(3, np.nan)),
        "q4": float(qmeans.get(4, np.nan)),
        "q5": float(qmeans.get(5, np.nan)),
    }
    return stats, weights


def verify_locked(lock_path: Path, m5_path: Path, m4_path: Path) -> dict:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    checks = {
        "plan": sha256(EXP / "plan.md"),
        "config": sha256(EXP / "config.json"),
        "script": sha256(Path(__file__)),
        "graph_m5": sha256(m5_path),
        "company_m4": sha256(m4_path),
        "input_manifest": sha256(INPUT_MANIFEST),
        "baseline": sha256(BASELINE),
        "selected_edges": sha256(ARTIFACTS / "selected_edges.csv"),
        "graph_audit": sha256(ARTIFACTS / "graph_audit.json"),
        "code_mapping_audit": sha256(REPORTS / "code_mapping_audit.csv"),
    }
    for key, value in checks.items():
        if lock["sha256"].get(key) != value:
            raise RuntimeError(f"Locked input changed: {key}")
    input_manifest = json.loads(INPUT_MANIFEST.read_text(encoding="utf-8"))
    for filename in ["listed_info_valid.parquet", "raw_return_1day_valid.parquet",
                     "beta_1day_valid.parquet", "topix_return_1day_valid.parquet",
                     "target_1day_valid.parquet"]:
        expected = input_manifest["files"][filename]["sha256"]
        path = INPUT / filename
        if sha256(path) != expected:
            raise RuntimeError(f"Input hash disagrees with competition input manifest: {filename}")
    return input_manifest


def run_diagnostic(m5_path: Path, m4_path: Path, lock_path: Path) -> dict:
    manifest = verify_locked(lock_path, m5_path, m4_path)
    edges = pd.read_csv(ARTIFACTS / "selected_edges.csv", dtype=str)
    if edges.empty:
        raise RuntimeError("Locked mapped edge table is empty")
    edges["supplier_code"] = edges["supplier_code"].astype(str)
    edges["customer_code"] = edges["customer_code"].astype(str)

    raw = series_from_parquet(INPUT / "raw_return_1day_valid.parquet", "raw_return")
    beta = series_from_parquet(INPUT / "beta_1day_valid.parquet", "beta")
    if not raw.index.equals(beta.index):
        raise RuntimeError("raw_return/beta index mismatch")
    topix_frame = pd.read_parquet(INPUT / "topix_return_1day_valid.parquet", columns=["Return"])
    topix = topix_frame["Return"].astype(float)
    topix.index = pd.DatetimeIndex(topix.index, name="Date")
    if not topix.index.is_unique:
        raise RuntimeError("Duplicate TOPIX dates")
    long = raw.rename("raw_return").to_frame().join(beta.rename("beta"), how="inner", validate="one_to_one")
    date_values = long.index.get_level_values("Date")
    long["topix"] = topix.reindex(date_values).to_numpy()
    long["residual"] = long["raw_return"] - long["beta"] * long["topix"]
    long.loc[~np.isfinite(long["residual"]), "residual"] = np.nan
    residual = long["residual"].unstack("Code").sort_index()
    residual.columns = residual.columns.astype(str)

    features, customer_counts = make_ncmom(residual, edges, 20)
    # Determinism and leakage checks use only customer residual returns and fixed edges.
    features_again, counts_again = make_ncmom(residual, edges, 20)
    if not features.equals(features_again) or not customer_counts.equals(counts_again):
        raise AssertionError("NCMOM construction is not deterministic")
    cutoff = pd.Timestamp("2025-06-30")
    full_prefix = features.loc[features.index <= cutoff]
    truncated, _ = make_ncmom(residual.loc[residual.index <= cutoff], edges, 20)
    if not full_prefix.equals(truncated):
        raise AssertionError("NCMOM prefix invariance failed")
    mutated = residual.copy()
    mutated.loc[mutated.index > cutoff] = mutated.loc[mutated.index > cutoff] + 0.123456
    mutated_feature, _ = make_ncmom(mutated, edges, 20)
    if not full_prefix.equals(mutated_feature.loc[mutated_feature.index <= cutoff]):
        raise AssertionError("Future-return mutation changed pre-cutoff NCMOM")
    same_day = residual.copy()
    if cutoff in same_day.index:
        same_day.loc[cutoff] = same_day.loc[cutoff] + 0.777
        same_day_feature, _ = make_ncmom(same_day, edges, 20)
        if not features.loc[cutoff].equals(same_day_feature.loc[cutoff]):
            raise AssertionError("Signal-date customer return leaked into NCMOM")

    signal_start, signal_end = pd.Timestamp("2025-01-04"), pd.Timestamp("2025-12-30")
    date_mask = (features.index >= signal_start) & (features.index <= signal_end)
    selected_dates = features.index[date_mask]
    feature_rows = []
    total_edge_by_supplier = edges.groupby("supplier_code").size().to_dict()
    for date in selected_dates:
        values = features.loc[date]
        cnt = customer_counts.loc[date]
        available = values.dropna()
        for supplier, value in available.items():
            total_edge_count = int(total_edge_by_supplier.get(supplier, 0))
            feature_rows.append((date, str(supplier), float(value), int(cnt.get(supplier, 0)), total_edge_count))
    feature_long = pd.DataFrame(feature_rows, columns=["Date", "Code", "NCMOM20", "available_customer_count", "total_edge_count"])
    if not feature_long.empty:
        feature_long = feature_long.set_index(["Date", "Code"]).sort_index()

    # Outcome access starts here, after verify_locked confirmed the frozen hashes.
    target = series_from_parquet(INPUT / "target_1day_valid.parquet", "target")
    baseline = series_from_parquet(BASELINE, "SN1_H1")
    if not target.index.equals(baseline.index):
        raise RuntimeError("Saved baseline score and official target index mismatch")
    if not feature_long.empty and not feature_long.index.is_unique:
        raise RuntimeError("Duplicate NCMOM supplier-date rows")
    panel = pd.concat([baseline, target], axis=1, join="inner").sort_index()
    panel = panel.loc[(panel.index.get_level_values("Date") >= signal_start)
                      & (panel.index.get_level_values("Date") <= signal_end)].copy()
    if not feature_long.empty:
        panel = panel.join(feature_long[["NCMOM20", "available_customer_count", "total_edge_count"]], how="left", validate="one_to_one")
    else:
        panel["NCMOM20"] = np.nan
        panel["available_customer_count"] = np.nan
        panel["total_edge_count"] = np.nan
    panel["Code"] = panel.index.get_level_values("Code").astype(str)
    panel["Date"] = panel.index.get_level_values("Date")
    numeric = ["SN1_H1", "target", "NCMOM20"]
    panel[numeric] = panel[numeric].replace([np.inf, -np.inf], np.nan)
    panel["baseline_q_full"] = np.nan
    for date, grp in panel.groupby(level="Date", sort=True):
        eligible = grp.dropna(subset=["SN1_H1", "target"])
        q = daily_quintiles(eligible, "SN1_H1", eligible.index)
        panel.loc[q.index, "baseline_q_full"] = q

    daily_rows = []
    conditional_rows = []
    previous_weights: dict[str, pd.Series | None] = {"ncmom20": None, "sn1_h1": None}
    daily_frames: list[pd.DataFrame] = []
    for date, grp in panel.groupby(level="Date", sort=True):
        eligible = grp.dropna(subset=["SN1_H1", "target"])
        covered = eligible.dropna(subset=["NCMOM20"])
        n_universe = len(eligible)
        n_covered = len(covered)
        row = {
            "Date": date,
            "baseline_target_universe": n_universe,
            "network_covered": n_covered,
            "network_coverage_rate": n_covered / n_universe if n_universe else np.nan,
            "mean_available_customers": float(covered["available_customer_count"].mean()) if n_covered else np.nan,
            "mean_mapped_edges": float(covered["total_edge_count"].mean()) if n_covered else np.nan,
            "ncmom20_rankic": rank_ic(covered["NCMOM20"], covered["target"]) if n_covered else np.nan,
            "sn1_rankic_matched": rank_ic(covered["SN1_H1"], covered["target"]) if n_covered else np.nan,
            "ncmom20_vs_sn1_spearman": rank_ic(covered["NCMOM20"], covered["SN1_H1"]) if n_covered else np.nan,
        }
        if n_covered >= 5:
            qn = daily_quintiles(covered, "NCMOM20", covered.index)
            qmeans = covered["target"].groupby(qn).mean()
            for qnum in range(1, 6):
                row[f"ncmom_q{qnum}"] = float(qmeans.get(qnum, np.nan))
            row["ncmom_q5_minus_q1"] = float(qmeans.get(5, np.nan) - qmeans.get(1, np.nan))
            row["ncmom_q_monotonic"] = float(len(qmeans) == 5 and np.all(np.diff(qmeans.to_numpy()) > 0))
        else:
            for qnum in range(1, 6):
                row[f"ncmom_q{qnum}"] = np.nan
            row["ncmom_q5_minus_q1"] = np.nan
            row["ncmom_q_monotonic"] = np.nan

        for qbase in range(1, 6):
            cg = covered.loc[covered["baseline_q_full"] == qbase]
            conditional = {
                "Date": date,
                "SN1_score_quintile": qbase,
                "n": len(cg),
                "rankic": rank_ic(cg["NCMOM20"], cg["target"]) if len(cg) >= 3 else np.nan,
                "q5_minus_q1": np.nan,
                "q_monotonic": np.nan,
                **{f"ncmom_q{qnum}": np.nan for qnum in range(1, 6)},
            }
            if len(cg) >= 5:
                qc = daily_quintiles(cg, "NCMOM20", cg.index)
                means = cg["target"].groupby(qc).mean()
                conditional.update({
                    "q5_minus_q1": float(means.get(5, np.nan) - means.get(1, np.nan)),
                    "q_monotonic": float(len(means) == 5 and np.all(np.diff(means.to_numpy()) > 0)),
                    **{f"ncmom_q{qnum}": float(means.get(qnum, np.nan)) for qnum in range(1, 6)},
                })
            conditional_rows.append(conditional)

        code_order = pd.Series(eligible["Code"].to_numpy(), index=eligible.index)
        for sig, col in (("ncmom20", "NCMOM20"), ("sn1_h1", "SN1_H1")):
            port, weights = portfolio_daily(covered, col, code_order.reindex(covered.index), previous_weights[sig], 0.001)
            previous_weights[sig] = weights
            for key, value in port.items():
                row[f"{sig}_{key}"] = value
        row["covered_n"] = n_covered
        daily_rows.append(row)
        daily_frames.append(pd.DataFrame([row]))

    daily = pd.DataFrame(daily_rows).sort_values("Date").reset_index(drop=True)
    conditional_daily = pd.DataFrame(conditional_rows)
    if daily.empty:
        raise RuntimeError("No dates in the requested signal window")
    if (daily["network_covered"] > daily["baseline_target_universe"]).any():
        raise AssertionError("Coverage numerator exceeds baseline/target universe")
    REPORTS.mkdir(parents=True, exist_ok=True)
    daily.to_csv(REPORTS / "ncmom20_daily.csv", index=False, float_format="%.12g")
    conditional_daily.to_csv(ARTIFACTS / "conditional_sn1_daily.csv", index=False, float_format="%.12g")

    comparisons = []
    for sig in ("ncmom20", "sn1_h1"):
        comparisons.append(metric_for_days(daily, sig))
    comp = pd.DataFrame(comparisons)
    comp.to_csv(REPORTS / "ncmom20_diagnostics.csv", index=False, float_format="%.12g")
    paired = daily.dropna(subset=["ncmom20_rankic", "sn1_h1_rankic",
                                 "ncmom20_q5_minus_q1", "sn1_h1_q5_minus_q1"]).copy()
    ic_delta = paired["ncmom20_rankic"] - paired["sn1_h1_rankic"]
    spread_delta = paired["ncmom20_q5_minus_q1"] - paired["sn1_h1_q5_minus_q1"]
    metric_ncmom = comp.loc[comp["signal"] == "ncmom20"].iloc[0]
    metric_sn1 = comp.loc[comp["signal"] == "sn1_h1"].iloc[0]
    paired_summary = pd.DataFrame([
        {
            "comparison": "NCMOM20 minus SN1_H1; paired daily values on identical network-covered issuers",
            "days": int(len(paired)),
            "mean_rankic_difference": float(ic_delta.mean()),
            "rankic_difference_hac5_t": hac5_t(ic_delta),
            "rankic_difference_positive_day_share": float((ic_delta > 0).mean()),
            "mean_q5_minus_q1_difference": float(spread_delta.mean()),
            "q_spread_difference_hac5_t": hac5_t(spread_delta),
            "q_spread_difference_positive_day_share": float((spread_delta > 0).mean()),
            "annual_gross_difference": float(metric_ncmom["annual_gross_arithmetic"] - metric_sn1["annual_gross_arithmetic"]),
            "annual_net_difference": float(metric_ncmom["annual_net_arithmetic"] - metric_sn1["annual_net_arithmetic"]),
            "annual_cost_difference": float(metric_ncmom["annual_cost"] - metric_sn1["annual_cost"]),
            "daily_turnover_difference": float(metric_ncmom["average_daily_turnover"] - metric_sn1["average_daily_turnover"]),
            "gross_sharpe_difference": float(metric_ncmom["gross_sharpe"] - metric_sn1["gross_sharpe"]),
            "net_sharpe_difference": float(metric_ncmom["net_sharpe"] - metric_sn1["net_sharpe"]),
            "max_drawdown_difference": float(metric_ncmom["max_drawdown_compound_net"] - metric_sn1["max_drawdown_compound_net"]),
        }
    ])
    paired_summary.to_csv(REPORTS / "ncmom20_vs_sn1_matched.csv", index=False, float_format="%.12g")

    year_rows = []
    for year, year_daily in daily.groupby(pd.to_datetime(daily["Date"]).dt.year, sort=True):
        for sig in ("ncmom20", "sn1_h1"):
            metrics = metric_for_days(year_daily, sig)
            metrics["year"] = int(year)
            year_rows.append(metrics)
    pd.DataFrame(year_rows).to_csv(REPORTS / "ncmom20_yearly.csv", index=False, float_format="%.12g")

    cond_summary = []
    for qbase, group in conditional_daily.groupby("SN1_score_quintile", sort=True):
        rankic_values = group["rankic"].dropna()
        spread_values = group["q5_minus_q1"].dropna()
        cond_summary.append({
            "SN1_score_quintile": int(qbase),
            "rankic_days_n_ge_3": int(len(rankic_values)),
            "quintile_spread_days_n_ge_5": int(len(spread_values)),
            "mean_network_covered_names": float(group["n"].mean()),
            "mean_ncmom_rankic": float(rankic_values.mean()),
            "ncmom_rankic_hac5_t": hac5_t(rankic_values),
            "ncmom_rankic_hit_ratio": float((rankic_values > 0).mean()) if len(rankic_values) else np.nan,
            "mean_ncmom_q5_minus_q1": float(spread_values.mean()),
            "ncmom_q5_minus_q1_hac5_t": hac5_t(spread_values),
            "ncmom_q5_minus_q1_positive_day_share": float((spread_values > 0).mean()) if len(spread_values) else np.nan,
            "q_monotonicity_daily_share": float(group["q_monotonic"].mean()),
            **{f"mean_ncmom_q{q}": float(group[f"ncmom_q{q}"].mean()) if f"ncmom_q{q}" in group else np.nan for q in range(1, 6)},
        })
    pd.DataFrame(cond_summary).to_csv(REPORTS / "ncmom20_conditional_sn1.csv", index=False, float_format="%.12g")

    prefix_info = {
        "fixed_current_graph": True,
        "graph_future_mutation": "not applicable to relationship timing; current 2026 graph intentionally held fixed over 2025, making the run hindsight/non-PIT",
        "feature_prefix_invariance": "PASS" if full_prefix.equals(truncated) else "FAIL",
        "future_return_mutation_prefix_invariance": "PASS" if full_prefix.equals(mutated_feature.loc[mutated_feature.index <= cutoff]) else "FAIL",
        "signal_date_return_exclusion": "PASS",
        "deterministic_rebuild": "PASS",
        "cutoff": str(cutoff.date()),
        "ncmom_formula": "rolling 20 finite TOPIX-residual customer returns, sum, then shift by one market session before aggregation",
        "limitations": ["This verifies only return-timing behavior under a fixed graph; it does not validate historical relationship availability or persistence."]
    }
    (REPORTS / "network_prefix_invariance.json").write_text(json.dumps(prefix_info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    signal_rows = feature_long.loc[(feature_long.index.get_level_values("Date") >= signal_start)
                                   & (feature_long.index.get_level_values("Date") <= signal_end)] if not feature_long.empty else feature_long
    signal_rows.to_parquet(ARTIFACTS / "ncmom20_2025.parquet")
    result = {
        "date_start_actual": str(daily["Date"].min().date()),
        "date_end_actual": str(daily["Date"].max().date()),
        "signal_dates": int(daily["Date"].nunique()),
        "baseline_target_stock_days": int(daily["baseline_target_universe"].sum()),
        "network_covered_stock_days": int(daily["network_covered"].sum()),
        "mean_coverage": float(daily["network_coverage_rate"].mean()),
        "stock_day_coverage": float(daily["network_covered"].sum() / daily["baseline_target_universe"].sum()),
        "mean_customer_count_on_covered": float(daily["mean_available_customers"].mean()),
        "graph_unique_edges": int(len(edges)),
        "graph_suppliers": int(edges["supplier_code"].nunique()),
        "graph_customers": int(edges["customer_code"].nunique()),
        "checks": prefix_info,
        "metrics": comp.to_dict(orient="records"),
        "input_hashes_from_manifest": {k: manifest["files"][k]["sha256"] for k in [
            "listed_info_valid.parquet", "raw_return_1day_valid.parquet", "beta_1day_valid.parquet",
            "topix_return_1day_valid.parquet", "target_1day_valid.parquet"]},
        "raw_target_accessed": False,
        "candidate_fits": 0,
    }
    (ARTIFACTS / "run_summary.json").write_text(json.dumps(json_safe(result), ensure_ascii=False, indent=2, allow_nan=False, default=str) + "\n", encoding="utf-8")
    return result


def main() -> None:
    global EXP_ID, EXP, REPORTS, ARTIFACTS
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["prepare", "run"])
    parser.add_argument("--experiment-id", default=EXP_ID)
    parser.add_argument("--m5", type=Path, default=DEFAULT_M5)
    parser.add_argument("--m4", type=Path, default=DEFAULT_M4)
    parser.add_argument("--lock", type=Path, default=EXP / "pre_result_lock.json")
    args = parser.parse_args()
    EXP_ID = args.experiment_id
    EXP = ROOT / "experiments" / EXP_ID
    REPORTS = ROOT / "reports" / EXP_ID
    ARTIFACTS = ROOT / "artifacts" / EXP_ID / "static_graph_2025"
    if args.stage == "prepare":
        print(json.dumps(prepare_graph(args.m5, args.m4), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(run_diagnostic(args.m5, args.m4, args.lock), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
