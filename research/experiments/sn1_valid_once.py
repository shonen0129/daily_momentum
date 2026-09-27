"""Single-use, hash-locked Valid comparison for D_LOW_FAST_ONLY vs SN1."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from research import evaluation
from stock_comp_2026.evaluate_script import compute_pl, compute_sr, compute_weight
from stock_comp_2026.strategies.dm_variable_box_breakout import submission


ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = ("D_LOW_FAST_ONLY", "SIDE_SOURCE_SEPARATION")
ONE_WAY_COST = 0.001
ANNUALIZATION = 252


def sha256(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def git_output(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def verify_freeze(lock_path: Path, manifest_path: Path, plan_path: Path, config_path: Path) -> dict:
    lock = read_json(lock_path)
    checks = {
        "manifest": (manifest_path, lock["manifest_sha256"]),
        "plan": (plan_path, lock["plan_sha256"]),
        "config": (config_path, lock["config_sha256"]),
    }
    for label, (path, expected) in checks.items():
        observed = sha256(path)
        if observed != expected:
            raise AssertionError(f"Frozen {label} hash mismatch: {observed} != {expected}")
    head = git_output("rev-parse", "HEAD")
    if head != lock["freeze_source_commit"]:
        raise AssertionError(f"Freeze source commit mismatch: {head} != {lock['freeze_source_commit']}")
    for relative, expected in lock["code_sha256"].items():
        observed = sha256(ROOT / relative)
        if observed != expected:
            raise AssertionError(f"Frozen code hash mismatch for {relative}: {observed} != {expected}")
    zip_path = ROOT / lock["submission_zip"]
    if sha256(zip_path) != lock["submission_zip_sha256"]:
        raise AssertionError("Frozen submission zip hash mismatch")
    input_manifest = ROOT / lock["input_manifest"]
    if sha256(input_manifest) != lock["input_manifest_sha256"]:
        raise AssertionError("Competition input manifest hash mismatch")
    if tuple(lock["candidate_ids"]) != CANDIDATES:
        raise AssertionError("Frozen candidate list differs from this runner")
    if lock["target_file"] != "target_1day_valid.parquet":
        raise AssertionError("Unexpected Valid target file in freeze lock")
    return lock


def exclusive_run_sentinel(path: Path, lock: dict) -> None:
    payload = {
        "status": "started",
        "stage": "pre_valid_inputs",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "freeze_source_commit": lock["freeze_source_commit"],
        "manifest_sha256": lock["manifest_sha256"],
        "plan_sha256": lock["plan_sha256"],
        "candidate_ids": list(CANDIDATES),
        "valid_target_read_count": 0,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def update_sentinel(path: Path, updates: dict) -> None:
    value = read_json(path)
    value.update(updates)
    temporary = path.with_suffix(path.suffix + ".tmp")
    write_json(temporary, value)
    os.replace(temporary, path)


def official_quintiles_and_weights(score_frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    ordered = score_frame.sort_index().fillna(0.0)
    rank = ordered.groupby("Date").rank(method="first")
    q = rank.groupby("Date").transform(
        lambda values: pd.qcut(values, 5, labels=False)
    ).iloc[:, 0].astype("int8")
    q.name = "quintile"
    official_weight = compute_weight(ordered).iloc[:, 0].rename("weight")
    return q.sort_index(), official_weight.sort_index()


def score_quality(name: str, score_frame: pd.DataFrame) -> tuple[dict, pd.Series, pd.Series]:
    if not isinstance(score_frame, pd.DataFrame) or score_frame.shape[1] != 1:
        raise TypeError(f"{name}: one-column DataFrame required")
    if list(score_frame.index.names) != ["Date", "Code"]:
        raise ValueError(f"{name}: prediction index must be (Date, Code)")
    if not score_frame.index.is_unique:
        raise ValueError(f"{name}: duplicate prediction index")
    if not pd.api.types.is_numeric_dtype(score_frame.iloc[:, 0]):
        raise TypeError(f"{name}: score must be numeric")
    score = score_frame.iloc[:, 0].sort_index().astype("float64").rename("Return")
    finite = np.isfinite(score.to_numpy())
    if not finite.all():
        raise ValueError(f"{name}: nonfinite score")

    q, weight = official_quintiles_and_weights(score.to_frame())
    research_weight, research_q = evaluation.weights(score)
    if not weight.index.equals(research_weight.index) or not np.array_equal(
        weight.to_numpy(), research_weight.to_numpy()
    ):
        raise AssertionError(f"{name}: official and research portfolio weights differ")
    if not np.array_equal(q.to_numpy(), research_q.reindex(q.index).to_numpy()):
        raise AssertionError(f"{name}: official and research quintile labels differ")

    dates = score.index.get_level_values("Date")
    table = pd.DataFrame({"date": dates, "score": score.to_numpy(), "q": q.to_numpy()})
    grouped = table.groupby(["date", "score"], sort=False, dropna=False)
    duplicate_rows = grouped["score"].transform("size").gt(1)
    crosses_boundary = duplicate_rows & grouped["q"].transform("min").ne(
        grouped["q"].transform("max")
    )
    per_day_unique_ratio = table.groupby("date", sort=True)["score"].nunique() / table.groupby(
        "date", sort=True
    )["score"].size()
    bucket_counts = q.groupby(level="Date").value_counts().unstack(fill_value=0)
    bucket_populated = bool((bucket_counts.reindex(columns=range(5), fill_value=0) > 0).all().all())
    if not bucket_populated:
        raise ValueError(f"{name}: official five quintiles are not populated every date")
    daily_spread = bucket_counts.max(axis=1) - bucket_counts.min(axis=1)

    long = weight.clip(lower=0.0)
    short = weight.clip(upper=0.0)
    daily_net = weight.groupby(level="Date").sum()
    daily_gross = weight.abs().groupby(level="Date").sum()
    metrics = {
        "candidate": name,
        "score_rows": int(len(score)),
        "date_count": int(dates.nunique()),
        "unique_index": True,
        "finite_score_rate": float(finite.mean()),
        "exact_zero_rate": float(score.eq(0.0).mean()),
        "duplicate_score_row_rate": float(duplicate_rows.mean()),
        "boundary_crossing_tie_row_rate": float(crosses_boundary.mean()),
        "pooled_unique_scores": int(score.nunique()),
        "mean_daily_unique_ratio": float(per_day_unique_ratio.mean()),
        "min_daily_unique_ratio": float(per_day_unique_ratio.min()),
        "quintiles_per_day": 5,
        "all_five_quintiles_populated": bucket_populated,
        "max_daily_bucket_size_spread": int(daily_spread.max()),
        "mean_long_exposure": float(long.groupby(level="Date").sum().mean()),
        "mean_short_exposure": float(-short.groupby(level="Date").sum().mean()),
        "mean_gross_exposure": float(daily_gross.mean()),
        "mean_net_exposure": float(daily_net.mean()),
        "max_abs_daily_net_exposure": float(daily_net.abs().max()),
    }
    return metrics, q, weight


def metric_record(name: str, score: pd.Series, weight: pd.Series, q: pd.Series,
                  target: pd.Series, period: str) -> tuple[dict, pd.DataFrame]:
    daily = evaluation.daily_account(score, target)
    expected_dates = pd.DatetimeIndex(target.index.get_level_values("Date").unique()).sort_values()
    if not daily.index.equals(expected_dates):
        raise AssertionError(f"{name}: research daily account dates differ from target")
    for side, side_weight in (("long", weight.clip(lower=0.0)),
                              ("short", weight.clip(upper=0.0))):
        side_turnover = side_weight.groupby(level="Code").diff().abs().fillna(side_weight.abs())
        side_cost_i = (ONE_WAY_COST * side_turnover).where(target.notna(), 0.0)
        side_gross_i = side_weight * target
        daily[f"{side}_gross"] = side_gross_i.groupby(level="Date").sum()
        daily[f"{side}_cost"] = side_cost_i.groupby(level="Date").sum()
        daily[f"{side}_net"] = (side_gross_i - side_cost_i).groupby(level="Date").sum()
        daily[f"{side}_turnover"] = side_turnover.groupby(level="Date").sum()
        daily[f"{side}_exposure"] = side_weight.groupby(level="Date").sum()
    if float((daily.long_net + daily.short_net - daily.net).abs().max()) > 1e-12:
        raise AssertionError(f"{name}: Long/Short accounting does not reconcile to total net")
    stats = evaluation.metrics(daily)
    gross_vol = float(daily.gross.std(ddof=1) * np.sqrt(ANNUALIZATION))
    net_vol = float(daily.net.std(ddof=1) * np.sqrt(ANNUALIZATION))
    official_frame = score.rename("Return").to_frame()
    official_target = target.rename("Return").to_frame()
    official_pl = compute_pl(official_frame, official_target)
    official_net = official_pl.groupby(level="Date").sum().sort_index()
    if not official_net.index.equals(daily.index):
        raise AssertionError(f"{name}: evaluator and research daily indexes differ")
    if float((official_net - daily.net).abs().max()) > 1e-12:
        raise AssertionError(f"{name}: evaluator and research net returns do not reconcile")

    row = {
        "candidate": name,
        "period": period,
        "signal_days": int(len(daily)),
        "label_days": int((daily.label_coverage > 0.0).sum()),
        "mean_daily_label_coverage": float(daily.label_coverage.mean()),
        "annual_gross_return": stats["annual_gross"],
        "annual_net_return": stats["annual_net"],
        "gross_sharpe": stats["gross_sharpe"],
        "net_sharpe": stats["net_sharpe"],
        "gross_volatility": gross_vol,
        "net_volatility": net_vol,
        "turnover_per_day": stats["turnover"],
        "annual_transaction_cost": stats["annual_cost"],
        "max_drawdown_additive": stats["max_drawdown_additive"],
        "max_drawdown_compound": stats["max_drawdown_compound"],
        "rankic": stats["rankic"],
        "rankic_t_hac5": stats["rankic_t_hac5"],
        "rankic_hit_ratio": stats["rankic_hit"],
        "q1_q5_monotonicity": stats["q_monotonicity"],
        "mean_long_exposure": float(daily.long_exposure.mean()),
        "mean_short_exposure": float(daily.short_exposure.mean()),
        "mean_gross_exposure": float(daily.gross_exposure.mean()),
        "mean_net_exposure": float(daily.net_exposure.mean()),
        "official_evaluator_net_sr_ddof0": compute_sr(official_pl),
        "research_net_sr_ddof1": evaluation.sharpe(daily.net),
    }
    for side in ("long", "short"):
        side_net = daily[f"{side}_net"]
        row[f"annual_{side}_gross"] = float(daily[f"{side}_gross"].mean() * ANNUALIZATION)
        row[f"annual_{side}_net"] = float(side_net.mean() * ANNUALIZATION)
        row[f"{side}_net_volatility"] = float(side_net.std(ddof=1) * np.sqrt(ANNUALIZATION))
        row[f"{side}_net_sharpe"] = evaluation.sharpe(side_net)
    row["long_short_net_correlation"] = float(
        daily.long_net.corr(daily.short_net)
    ) if daily.long_net.std() > 0.0 and daily.short_net.std() > 0.0 else np.nan
    return row, daily


def fixed_existing_paired_bootstrap(baseline: pd.Series, candidate: pd.Series) -> dict:
    """Use the existing circular-paired bootstrap definition and fixed seed."""
    base = np.asarray(baseline, dtype=float)
    cand = np.asarray(candidate, dtype=float)
    if len(base) != len(cand) or not len(base):
        raise ValueError("Paired bootstrap inputs must be nonempty and aligned")
    seed, repetitions, block_days = 20260925, 1000, 20
    sr = evaluation.bootstrap_delta(base, cand, seed=seed, reps=repetitions, block=block_days)
    rng = np.random.default_rng(seed)
    starts = rng.integers(
        0, len(base), size=(repetitions, int(np.ceil(len(base) / block_days)))
    )
    indices = ((starts[:, :, None] + np.arange(block_days)) % len(base)).reshape(
        repetitions, -1
    )[:, :len(base)]
    delta_annual = (cand[indices].mean(axis=1) - base[indices].mean(axis=1)) * ANNUALIZATION
    return {
        "delta_net_sharpe": float(evaluation.sharpe(cand) - evaluation.sharpe(base)),
        "delta_net_sharpe_ci_low": sr["low"],
        "delta_net_sharpe_ci_high": sr["high"],
        "delta_net_annual_return": float((cand.mean() - base.mean()) * ANNUALIZATION),
        "delta_net_annual_return_ci_low": float(np.quantile(delta_annual, 0.025)),
        "delta_net_annual_return_ci_high": float(np.quantile(delta_annual, 0.975)),
        "bootstrap_positive_net_sharpe_fraction": sr["bootstrap_positive_fraction"],
        "repetitions": repetitions,
        "block_days": block_days,
        "seed": seed,
    }


def evaluate_once(args) -> Path:
    manifest_path = (ROOT / args.manifest).resolve()
    plan_path = (ROOT / args.plan).resolve()
    config_path = (ROOT / args.config).resolve()
    lock_path = (ROOT / args.lock).resolve()
    output = (ROOT / args.output).resolve()
    sentinel = (ROOT / args.sentinel).resolve()

    # All fixed documents and source hashes are checked before opening any Valid input.
    lock = verify_freeze(lock_path, manifest_path, plan_path, config_path)
    data_dir = Path(args.data_dir).resolve()
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")
    if output.exists():
        raise FileExistsError(f"Single-use output already exists: {output}")
    exclusive_run_sentinel(sentinel, lock)
    output.mkdir(parents=True, exist_ok=False)
    for folder in ("predictions", "audit", "metrics", "logs"):
        (output / folder).mkdir()

    run = {
        "schema_version": 1,
        "experiment_id": "DM-20260927-03",
        "run_id": output.name,
        "status": "running",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": git_output("rev-parse", "HEAD"),
        "git_status_at_run": git_output("status", "--short"),
        "freeze_source_commit": lock["freeze_source_commit"],
        "freeze_manifest_sha256": sha256(manifest_path),
        "evaluation_plan_sha256": sha256(plan_path),
        "evaluation_config_sha256": sha256(config_path),
        "code_sha256": lock["code_sha256"],
        "submission_zip_sha256": lock["submission_zip_sha256"],
        "candidate_ids": list(CANDIDATES),
        "data_split": "valid",
        "target_file": "target_1day_valid.parquet",
        "input_manifest": lock["input_manifest"],
        "input_manifest_sha256": lock["input_manifest_sha256"],
        "target_valid_read_count": 0,
        "raw_target_accessed": False,
        "valid_pnl_accessed": False,
        "one_way_cost": ONE_WAY_COST,
        "annualization": ANNUALIZATION,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
    }
    write_json(output / "run.json", run)
    write_json(output / "config.json", read_json(config_path))
    (output / "VALID_EVALUATION_PLAN.md").write_text(
        plan_path.read_text(encoding="utf-8"), encoding="utf-8"
    )

    try:
        update_sentinel(sentinel, {"stage": "valid_feature_prediction_started"})
        scores = submission.predict_candidates(data_dir=data_dir, split="valid")
        if tuple(scores) != CANDIDATES:
            raise AssertionError(f"Candidate output changed: {tuple(scores)}")
        quality_rows = []
        quintiles = {}
        weights = {}
        ordered_scores = {}
        for name in CANDIDATES:
            frame = scores[name]
            score = frame.iloc[:, 0].sort_index().astype("float64").rename("Return")
            frame = score.to_frame()
            quality, q, weight = score_quality(name, frame)
            ordered_scores[name] = frame
            quintiles[name] = q
            weights[name] = weight
            quality_rows.append(quality)
            frame.to_parquet(output / "predictions" / f"{name}.parquet")
        pd.DataFrame(quality_rows).to_csv(output / "audit" / "score_regulation.csv", index=False)
        update_sentinel(sentinel, {"stage": "valid_scores_saved_target_not_read"})

        # This is the only read of target_1day_valid.parquet in this runner.
        target_path = data_dir / "target_1day_valid.parquet"
        update_sentinel(sentinel, {
            "stage": "valid_target_read_started",
            "valid_target_read_count": 1,
        })
        target_frame = pd.read_parquet(target_path, columns=["Return"]).sort_index()
        if not target_frame.index.is_unique:
            raise ValueError("Valid target index is not unique")
        target = target_frame["Return"].astype("float64").rename("Return")
        update_sentinel(sentinel, {
            "stage": "valid_target_read_once",
            "valid_target_read_count": 1,
            "valid_target_rows": int(len(target)),
        })
        run["target_valid_read_count"] = 1
        run["valid_pnl_accessed"] = True
        run["input_manifest"] = lock["input_manifest"]
        run["input_manifest_sha256"] = lock["input_manifest_sha256"]
        run["valid_target_rows"] = int(len(target))

        if not target.index.equals(ordered_scores[CANDIDATES[0]].index):
            raise ValueError("Valid prediction coverage does not exactly equal target index")
        if any(not ordered_scores[name].index.equals(target.index) for name in CANDIDATES):
            raise ValueError("D and SN1 prediction coverage differs from target")

        # Exercise the repository evaluator's alignment contract on each fixed candidate.
        from stock_comp_2026.evaluate_script import align_prediction

        daily_rows = []
        annual_rows = []
        daily_by_candidate = {}
        for name in CANDIDATES:
            aligned = align_prediction(ordered_scores[name], target_frame)
            if not aligned.index.equals(target.index):
                raise AssertionError(f"{name}: evaluator alignment changed index order")
            record, daily = metric_record(
                name, aligned.iloc[:, 0].rename("Return"), weights[name],
                quintiles[name], target, "full_valid",
            )
            daily_rows.append(record)
            daily_by_candidate[name] = daily
            for year in sorted(pd.Index(target.index.get_level_values("Date").year).unique()):
                selected = daily.loc[daily.index.year == int(year)]
                if selected.empty:
                    continue
                period_name = f"{year} partial" if year in {
                    int(target.index.get_level_values("Date").min().year),
                    int(target.index.get_level_values("Date").max().year),
                } and (target.index.get_level_values("Date").min().month != 1
                       or target.index.get_level_values("Date").max().month != 12) else str(year)
                local_row, _ = metric_record(
                    name, aligned.iloc[:, 0].loc[aligned.index.get_level_values("Date").year == int(year)].rename("Return"),
                    weights[name].loc[weights[name].index.get_level_values("Date").year == int(year)],
                    quintiles[name].loc[quintiles[name].index.get_level_values("Date").year == int(year)],
                    target.loc[target.index.get_level_values("Date").year == int(year)], period_name,
                )
                annual_rows.append(local_row)

        overall = pd.DataFrame(daily_rows)
        annual = pd.DataFrame(annual_rows)
        overall.to_csv(output / "metrics" / "overall_metrics.csv", index=False)
        annual.to_csv(output / "metrics" / "annual_metrics.csv", index=False)

        baseline = daily_by_candidate["D_LOW_FAST_ONLY"].sort_index()
        candidate = daily_by_candidate["SIDE_SOURCE_SEPARATION"].reindex(baseline.index)
        if candidate.isna().any().any():
            raise AssertionError("Paired daily accounts are not aligned")
        bootstrap = fixed_existing_paired_bootstrap(baseline["net"], candidate["net"])
        write_json(output / "metrics" / "paired_bootstrap.json", bootstrap)
        deltas = []
        metric_keys = (
            "annual_gross_return", "annual_net_return", "gross_sharpe", "net_sharpe",
            "gross_volatility", "net_volatility", "turnover_per_day",
            "annual_transaction_cost", "rankic", "annual_long_gross", "annual_long_net",
            "long_net_sharpe", "annual_short_gross", "annual_short_net", "short_net_sharpe",
        )
        base_row = overall.set_index("candidate").loc["D_LOW_FAST_ONLY"]
        sn1_row = overall.set_index("candidate").loc["SIDE_SOURCE_SEPARATION"]
        for key in metric_keys:
            deltas.append({"metric": key, "D": float(base_row[key]), "SN1": float(sn1_row[key]),
                           "SN1_minus_D": float(sn1_row[key] - base_row[key])})
        pd.DataFrame(deltas).to_csv(output / "metrics" / "overall_deltas.csv", index=False)

        annual_wide = annual.pivot(index="period", columns="candidate", values="annual_net_return")
        annual_wide["SN1_minus_D_annual_net_return"] = (
            annual_wide["SIDE_SOURCE_SEPARATION"] - annual_wide["D_LOW_FAST_ONLY"]
        )
        annual_wide.to_csv(output / "metrics" / "annual_net_return_deltas.csv")

        run.update({
            "status": "completed",
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "valid_target_read_count": 1,
            "raw_target_accessed": False,
            "valid_pnl_accessed": True,
            "valid_date_min": str(target.index.get_level_values("Date").min().date()),
            "valid_date_max": str(target.index.get_level_values("Date").max().date()),
            "valid_signal_dates": int(target.index.get_level_values("Date").nunique()),
            "valid_label_rows": int(target.notna().sum()),
            "valid_periods": list(annual.period.drop_duplicates()),
            "bootstrap": {"method": "existing paired circular block bootstrap", "block_days": 20,
                          "repetitions": 1000, "seed": 20260925},
            "score_quality_rows": quality_rows,
        })
        write_json(output / "run.json", run)
        update_sentinel(sentinel, {
            "status": "completed",
            "stage": "valid_evaluation_complete",
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "valid_target_read_count": 1,
            "valid_pnl_accessed": True,
            "output": str(output.relative_to(ROOT)),
        })
        return output
    except Exception as exc:
        run["status"] = "failed_after_single_use_lock"
        run["failure"] = f"{type(exc).__name__}: {exc}"
        run["failed_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(output / "run.json", run)
        update_sentinel(sentinel, {
            "status": "failed_no_retry",
            "failure": f"{type(exc).__name__}: {exc}",
            "failed_at_utc": datetime.now(timezone.utc).isoformat(),
            "valid_target_read_count": int(run.get("target_valid_read_count", 0)),
        })
        raise


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--lock", default="releases/DM-20260927-SN1-v1/valid_evaluation_lock.json")
    result.add_argument("--manifest", default="releases/DM-20260927-SN1-v1/SN1_FREEZE_MANIFEST.md")
    result.add_argument("--plan", default="experiments/DM-20260927-03/VALID_EVALUATION_PLAN.md")
    result.add_argument("--config", default="experiments/DM-20260927-03/valid_evaluation_config.json")
    result.add_argument("--data-dir", default="stock_comp_2026/input")
    result.add_argument("--output", default="artifacts/DM-20260927-03/valid-once-sn1-vs-d")
    result.add_argument("--sentinel", default="releases/DM-20260927-SN1-v1/valid_evaluation_run.lock")
    return result


if __name__ == "__main__":
    print(evaluate_once(parser().parse_args()))
