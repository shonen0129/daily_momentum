"""P/L-blind structural screen, then one preregistered SN1 state intervention."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from research import evaluation  # noqa: E402

PHASE1 = ROOT / "artifacts/DM-20260928-01/run-20260927T154814Z"
REF = ROOT / "artifacts/DM-20260927-04/run-20260927T101500Z"
LOCK = ROOT / "experiments/DM-20260928-01/phase1_lock.json"
SPLITS = (("train", "train"), ("historical_valid", "valid"))
COST = 0.001
ANNUALIZATION = 252
EXPIRY_AGE = 60


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def score_with_low_expiry(g: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Expire only a negative Low state whose latest Low event is older than 60 sessions."""
    low = g.low_state.astype("float64").copy()
    expired = low.lt(0.0) & g.low_event_age_trading_days.gt(EXPIRY_AGE)
    low.loc[expired] = 0.0
    high = g.high_state.astype("float64")
    score = high + low
    score.loc[low.lt(0.0)] = low.loc[low.lt(0.0)]
    high_only = low.eq(0.0) & high.gt(0.0)
    score.loc[high_only] = high.loc[high_only]
    return score.rename("score"), expired.rename("expired_low_state")


def boundary_tie_rows(score: pd.Series, quintile: pd.Series) -> pd.Series:
    frame = pd.DataFrame({"score": score, "q": quintile}, index=score.index)
    return frame.groupby([frame.index.get_level_values("Date"), "score"], sort=False).q.transform("nunique").gt(1)


def structural_phase(out: Path) -> None:
    if out.exists():
        raise FileExistsError(out)
    lock_hash = Path(str(LOCK) + ".sha256").read_text().split()[0]
    if sha256(LOCK) != lock_hash:
        raise AssertionError("Phase 1 lock hash mismatch")
    manifest = json.loads((PHASE1 / "audit/phase1_manifest.json").read_text())
    table_path = PHASE1 / "audit/date_code_state.parquet"
    if sha256(table_path) != manifest["score_table_sha256"]:
        raise AssertionError("Phase 1 table hash mismatch")
    table = pd.read_parquet(table_path).sort_index()
    records = []
    for split, g in table.groupby("split", sort=False, observed=True):
        score, expired = score_with_low_expiry(g)
        baseline_score = g.score.astype("float64")
        w0, q0 = evaluation.weights(baseline_score)
        w1, q1 = evaluation.weights(score)
        n = score.groupby(level="Date").transform("count")
        unique = score.groupby(level="Date").transform("nunique")
        turnover = w1.groupby(level="Code").diff().abs().fillna(w1.abs()).groupby(level="Date").sum()
        daily_q = q1.groupby(level="Date").nunique()
        boundary = boundary_tie_rows(score, q1)
        stale_low_high_positive = g.low_state.lt(0) & g.low_event_age_trading_days.gt(EXPIRY_AGE) & g.high_state.gt(0)
        record = {
            "split": str(split), "stock_days": int(len(g)),
            "expired_negative_low_state_rate": float(expired.mean()),
            "expired_low_and_positive_high_rate": float(stale_low_high_positive.mean()),
            "score_changed_rate": float(score.ne(baseline_score).mean()),
            "quintile_changed_rate": float(q1.ne(q0).mean()),
            "weight_changed_rate": float(w1.ne(w0).mean()),
            "short_membership_changed_rate": float(q1.le(1).ne(q0.le(1)).mean()),
            "long_membership_changed_rate": float(q1.ge(3).ne(q0.ge(3)).mean()),
            "short_to_long_rate_within_stale_low_high_positive": float(q1.loc[stale_low_high_positive].ge(3).mean()),
            "short_rate_within_stale_low_high_positive": float(q1.loc[stale_low_high_positive].le(1).mean()),
            "exact_zero_rate": float(score.eq(0.0).mean()),
            "near_zero_abs_lt_1e_12_rate": float(score.abs().lt(1e-12).mean()),
            "mean_daily_unique_score_ratio": float((unique / n).groupby(level="Date").first().mean()),
            "boundary_tie_row_rate": float(boundary.mean()),
            "all_five_quintiles_populated_date_rate": float(daily_q.eq(5).mean()),
            "turnover_per_day": float(turnover.mean()),
            "mean_gross_exposure": float(w1.abs().groupby(level="Date").sum().mean()),
            "mean_net_exposure": float(w1.groupby(level="Date").sum().mean()),
        }
        records.append(record)
        # Candidate is a row-wise transform of information available at that date.
        dates = pd.DatetimeIndex(g.index.get_level_values("Date").unique().sort_values())
        cutoff = dates[int(len(dates) * 0.7)]
        full_prefix = score.loc[score.index.get_level_values("Date") <= cutoff]
        prefix_frame = g.loc[g.index.get_level_values("Date") <= cutoff]
        prefix_score, _ = score_with_low_expiry(prefix_frame)
        if not np.array_equal(full_prefix.to_numpy(), prefix_score.to_numpy()):
            raise AssertionError(f"Candidate transformation failed prefix invariance for {split}")
        mutated = g.copy()
        suffix = mutated.index.get_level_values("Date") > cutoff
        mutated.loc[suffix, "high_state"] = mutated.loc[suffix, "high_state"] * -777.0
        mutated.loc[suffix, "low_state"] = mutated.loc[suffix, "low_state"] * 333.0
        mutated.loc[suffix, "low_event_age_trading_days"] = 9999
        mutated_score, _ = score_with_low_expiry(mutated)
        if not np.array_equal(full_prefix.to_numpy(), mutated_score.loc[full_prefix.index].to_numpy()):
            raise AssertionError(f"Suffix mutation changed candidate prefix for {split}")
    out.mkdir(parents=True)
    pd.DataFrame(records).to_csv(out / "structural_screen.csv", index=False)
    write_json(out / "structural_manifest.json", {
        "phase": "P/L-blind intervention structure screen",
        "targets_or_PnL_read": False, "paper_data_read": False,
        "phase1_lock_sha256": lock_hash, "phase1_table_sha256": sha256(table_path),
        "driver_sha256": sha256(Path(__file__).resolve()),
        "candidate_id": "SN1_LOW_STATE_EXPIRY_60D",
        "rule": "if low_state < 0 and low_event_age_trading_days > 60, set low_state to exactly 0; apply unchanged SN1 precedence and official ranking/weights",
        "cutoff": "strictly greater than 60 market sessions since latest Low event; fixed once, no grid",
        "prefix_invariance": "pass for row-wise candidate transform under prefix truncation and suffix state/age mutation",
        "results_sha256": sha256(out / "structural_screen.csv"),
        "code_hashes": {"driver": sha256(Path(__file__).resolve()), "evaluation": sha256(ROOT / "research/evaluation.py")},
    })


def daily_exposure_table(score: pd.Series, target: pd.Series) -> tuple[pd.DataFrame, dict]:
    score = score.reindex(target.index).sort_index()
    target = target.reindex(score.index)
    weights, q = evaluation.weights(score)
    turn = weights.groupby(level="Code").diff().abs().fillna(weights.abs())
    cost = COST * turn
    row = pd.DataFrame({"weight": weights, "target": target, "turnover": turn, "cost": cost, "q": q}, index=score.index)
    row["gross"] = row.weight * row.target
    row["net"] = row.gross - row.cost
    row["long_gross"] = row.gross.where(row.weight.gt(0), 0.0)
    row["short_gross"] = row.gross.where(row.weight.lt(0), 0.0)
    row["long_net"] = (row.gross - row.cost).where(row.weight.gt(0), 0.0)
    row["short_net"] = (row.gross - row.cost).where(row.weight.lt(0), 0.0)
    official = evaluation.daily_account(score, target)
    sleeves = row.groupby(level="Date", sort=True).agg(
        long_gross=("long_gross", "sum"), short_gross=("short_gross", "sum"),
        long_net=("long_net", "sum"), short_net=("short_net", "sum"),
    )
    daily = official.join(sleeves, how="left").fillna(0.0)
    return daily, {"weights": weights, "quintile": q, "row": row}


def metrics_for(daily: pd.DataFrame) -> dict:
    base = evaluation.metrics(daily)
    for sleeve in ("long", "short"):
        series = daily[f"{sleeve}_net"]
        base[f"{sleeve}_gross_annual"] = float(daily[f"{sleeve}_gross"].mean() * ANNUALIZATION)
        base[f"{sleeve}_net_annual"] = float(series.mean() * ANNUALIZATION)
        base[f"{sleeve}_net_sr"] = evaluation.sharpe(series)
    base["gross_vol_annualized"] = float(daily.gross.std(ddof=1) * np.sqrt(ANNUALIZATION))
    base["net_vol_annualized"] = float(daily.net.std(ddof=1) * np.sqrt(ANNUALIZATION))
    return base


def evaluation_phase(out: Path, plan_path: Path) -> None:
    if out.exists():
        raise FileExistsError(out)
    plan_hash_path = Path(str(plan_path) + ".sha256")
    expected_plan_hash = plan_hash_path.read_text().split()[0]
    if sha256(plan_path) != expected_plan_hash:
        raise AssertionError("Intervention plan hash mismatch; evaluation stopped")
    plan = plan_path.read_text(encoding="utf-8")
    if "SN1_LOW_STATE_EXPIRY_60D" not in plan or "Candidate P/L" not in plan:
        raise AssertionError("Unexpected candidate set or missing locked P/L phase")
    phase1_manifest = json.loads((PHASE1 / "audit/phase1_manifest.json").read_text())
    phase1_lock_hash = Path(str(LOCK) + ".sha256").read_text().split()[0]
    if sha256(LOCK) != phase1_lock_hash or sha256(PHASE1 / "audit/date_code_state.parquet") != phase1_manifest["score_table_sha256"]:
        raise AssertionError("Phase 1 lock/table hash mismatch")
    allowed_parquets = {
        (PHASE1 / "audit/date_code_state.parquet").resolve(),
        (REF / "predictions/target_train_H1.parquet").resolve(),
        (REF / "predictions/target_valid_H1.parquet").resolve(),
    }
    read_parquet = pd.read_parquet
    accessed_parquets = []

    def guarded_read_parquet(path, *args, **kwargs):
        resolved = Path(path).resolve()
        if resolved not in allowed_parquets:
            raise PermissionError(f"P/L phase firewall denied parquet read: {resolved}")
        if "raw_target" in resolved.name.lower() or "paper" in str(resolved).lower():
            raise PermissionError(f"P/L phase firewall denied raw target/paper data: {resolved}")
        accessed_parquets.append(str(resolved.relative_to(ROOT)))
        return read_parquet(path, *args, **kwargs)

    pd.read_parquet = guarded_read_parquet
    out.mkdir(parents=True)
    (out / "metrics").mkdir()
    (out / "predictions").mkdir()
    table = pd.read_parquet(PHASE1 / "audit/date_code_state.parquet").sort_index()
    rows, summaries, annual_rows, regulation = [], [], [], []
    daily_store = {}
    input_hashes = {}
    for split, alias in SPLITS:
        g = table.loc[table.split.astype(str).eq(split)]
        candidate_score, expired = score_with_low_expiry(g)
        baseline_score = g.score.astype("float64")
        target_path = REF / f"predictions/target_{alias}_H1.parquet"
        target_frame = pd.read_parquet(target_path)
        if isinstance(target_frame, pd.Series):
            target = target_frame
        elif "Return" in target_frame:
            target = target_frame["Return"]
        else:
            target = target_frame.iloc[:, 0]
        target.index = pd.MultiIndex.from_arrays(
            [pd.DatetimeIndex(target.index.get_level_values("Date")), target.index.get_level_values("Code").astype(str)],
            names=["Date", "Code"],
        )
        target = pd.to_numeric(target, errors="coerce").astype("float64").sort_index()
        saved_path = REF / f"metrics/daily_account_{alias}_H1.csv"
        saved = pd.read_csv(saved_path, parse_dates=[0], index_col=0)
        saved.index = pd.DatetimeIndex(saved.index)
        eval_dates = saved.index
        eval_mask = baseline_score.index.get_level_values("Date").isin(eval_dates)
        # Replay the evaluator's target-index alignment over the full available target panel.
        # This preserves pre-evaluation turnover state in the Train replay.
        baseline_score = baseline_score.reindex(target.index).fillna(0.0).sort_index()
        candidate_score = candidate_score.reindex(target.index).fillna(0.0).sort_index()
        split_summaries = {}
        split_daily = {}
        split_aux = {}
        split_weights = {}
        for name, score in (("SN1_H1", baseline_score), ("SN1_LOW_STATE_EXPIRY_60D", candidate_score)):
            daily_full, aux = daily_exposure_table(score, target)
            daily = daily_full.reindex(eval_dates)
            required_daily = daily[["gross", "net", "cost", "turnover"]]
            if not daily.index.equals(eval_dates) or required_daily.isna().any().any():
                raise AssertionError(f"Daily account coverage mismatch for {split}/{name}")
            if name == "SN1_H1":
                maxdiff = {}
                for col in ("gross", "net", "cost", "turnover"):
                    maxdiff[col] = float((daily[col] - saved[col]).abs().max())
                if any(not np.isfinite(v) or v > 1e-12 for v in maxdiff.values()):
                    raise AssertionError(f"Saved baseline replay mismatch {split}: {maxdiff}")
            split_summaries[name] = metrics_for(daily)
            split_daily[name] = daily
            split_aux[name] = aux
            split_weights[name] = aux["weights"]
            daily_store[(split, name)] = daily
            row_eval = aux["weights"].index.get_level_values("Date").isin(eval_dates)
            score_eval = score.loc[row_eval]
            q = aux["quintile"].loc[row_eval]
            weight_eval = aux["weights"].loc[row_eval]
            size = q.groupby(level="Date").size()
            unique = score_eval.groupby(level="Date").nunique()
            ratio = unique / size
            tie_rows = boundary_tie_rows(score_eval, q)
            exposure = weight_eval.groupby(level="Date").agg(
                gross_exposure=lambda x: float(x.abs().sum()), net_exposure="sum"
            )
            daily_unique_ratio = (unique.groupby(level="Date").first() / size.groupby(level="Date").first())
            reg = {
                "split": split, "strategy": name,
                "finite_score": bool(np.isfinite(score_eval.to_numpy()).all()),
                "coverage_rows": int(score_eval.notna().sum()),
                "exact_zero_rate": float(score_eval.eq(0.0).mean()),
                "near_zero_abs_lt_1e_12_rate": float(score_eval.abs().lt(1e-12).mean()),
                "duplicate_row_rate": float((1.0 - daily_unique_ratio).mean()),
                "mean_daily_unique_score_ratio": float(ratio.mean()),
                "min_daily_unique_score_ratio": float(ratio.min()),
                "boundary_tie_row_rate": float(tie_rows.mean()),
                "all_five_quintiles_populated_date_rate": float(q.groupby(level="Date").nunique().eq(5).mean()),
                "gross_exposure_mean": float(exposure.gross_exposure.mean()),
                "net_exposure_mean": float(exposure.net_exposure.mean()),
                "code_order_tie_break": "official rank(method='first') after (Date, Code) ordering; unchanged",
            }
            regulation.append(reg)
            for year, year_daily in daily.groupby(daily.index.year):
                annual_rows.append({"split": split, "strategy": name, "year": int(year), **metrics_for(year_daily)})
            summaries.append({"split": split, "strategy": name, **split_summaries[name]})
            pd.DataFrame({"score": score_eval, "quintile": q, "weight": weight_eval}).to_parquet(
                out / "predictions" / f"{name}_{split}.parquet"
            )
            input_hashes[str(target_path.relative_to(ROOT))] = sha256(target_path)
            input_hashes[str(saved_path.relative_to(ROOT))] = sha256(saved_path)

        b = split_daily["SN1_H1"]
        c = split_daily["SN1_LOW_STATE_EXPIRY_60D"]
        base_w = split_weights["SN1_H1"]
        cand_w = split_weights["SN1_LOW_STATE_EXPIRY_60D"]
        signal_target = target
        delta_rows = pd.DataFrame({"baseline_weight": base_w, "candidate_weight": cand_w, "target": signal_target}, index=signal_target.index)
        same_side_common = (delta_rows.baseline_weight.ne(0) & delta_rows.candidate_weight.ne(0) &
                            (np.sign(delta_rows.baseline_weight) == np.sign(delta_rows.candidate_weight)))
        delta_rows["gross_delta"] = (delta_rows.candidate_weight - delta_rows.baseline_weight) * delta_rows.target
        delta_rows["gross_delta_common_names"] = delta_rows.gross_delta.where(same_side_common, 0.0)
        delta_rows["gross_delta_changed_membership_or_side"] = delta_rows.gross_delta.where(~same_side_common, 0.0)
        delta_daily = delta_rows.groupby(level="Date").agg(
            gross_delta=("gross_delta", "sum"), common_names=("gross_delta_common_names", "sum"),
            membership_or_side=("gross_delta_changed_membership_or_side", "sum"),
        ).reindex(eval_dates)
        cost_delta = (c.cost - b.cost)
        candidate_compare = {
            "split": split,
            "delta_annual_gross": float(delta_daily.gross_delta.mean() * ANNUALIZATION),
            "delta_annual_cost": float(cost_delta.mean() * ANNUALIZATION),
            "delta_annual_net": float((c.net - b.net).mean() * ANNUALIZATION),
            "delta_gross_common_names_annual": float(delta_daily.common_names.mean() * ANNUALIZATION),
            "delta_gross_membership_or_side_annual": float(delta_daily.membership_or_side.mean() * ANNUALIZATION),
            "delta_net_sr": float(evaluation.sharpe(c.net) - evaluation.sharpe(b.net)),
            "baseline_turnover_day": float(b.turnover.mean()),
            "candidate_turnover_day": float(c.turnover.mean()),
            "baseline_cost_annual": float(b.cost.mean() * ANNUALIZATION),
            "candidate_cost_annual": float(c.cost.mean() * ANNUALIZATION),
            "expired_state_rate_eval_rows": float(expired.loc[eval_mask].mean()),
            "paired_bootstrap_delta_net_sr": evaluation.bootstrap_delta(b.net.to_numpy(), c.net.to_numpy(), seed=20260908, reps=1000, block=20),
        }
        rows.append(candidate_compare)
        daily_store[(split, "delta")] = pd.concat([b.add_prefix("baseline_"), c.add_prefix("candidate_"), delta_daily], axis=1)
        # Save only daily accounts and the pre-specified delta terms.
        daily_store[(split, "delta")].to_csv(out / "metrics" / f"daily_comparison_{split}.csv")
    pd.DataFrame(summaries).to_csv(out / "metrics/overall_metrics.csv", index=False)
    pd.DataFrame(annual_rows).to_csv(out / "metrics/annual_metrics.csv", index=False)
    pd.DataFrame(regulation).to_csv(out / "metrics/regulation_checks.csv", index=False)
    pd.DataFrame(rows).to_csv(out / "metrics/decomposition.csv", index=False)
    code = Path(__file__).resolve()
    manifest = {
        "phase": "single preregistered candidate evaluation; Train and already-open historical Valid are development data",
        "candidate_id": "SN1_LOW_STATE_EXPIRY_60D", "candidate_count": 1,
        "plan_sha256": expected_plan_hash, "phase1_lock_sha256": phase1_lock_hash,
        "phase1_table_sha256": sha256(PHASE1 / "audit/date_code_state.parquet"),
        "targets_read_only_for_scoring": True, "target_used_for_model_fit_or_candidate_branching": False,
        "paper_data_accessed": False, "models_refit": False,
        "fixed_one_way_cost": COST, "cost_metric": "official daily_account: .001 * absolute weight change",
        "bootstrap": {"method": "research.evaluation.bootstrap_delta circular paired block", "block_days": 20, "repetitions": 1000, "seed": 20260908},
        "input_sha256": input_hashes,
        "accessed_parquets": accessed_parquets,
        "code_sha256": {str(code.relative_to(ROOT)): sha256(code), "research/evaluation.py": sha256(ROOT / "research/evaluation.py")},
        "outputs": {str(p.relative_to(out)): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()},
    }
    write_json(out / "audit_manifest.json", manifest)
    print(json.dumps({"candidate": "SN1_LOW_STATE_EXPIRY_60D", "plan_sha256": expected_plan_hash,
                      "summary": rows, "output": str(out.relative_to(ROOT))}, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["structure", "evaluate"])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--plan", type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if args.phase == "structure":
        structural_phase(out)
    else:
        if args.plan is None:
            raise SystemExit("--plan is required for evaluate phase")
        evaluation_phase(out, args.plan.resolve())


if __name__ == "__main__":
    main()
