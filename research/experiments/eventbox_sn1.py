"""Fixed Train-only Event-Box feature augmentation to the SN1_H1 score."""
import argparse
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from research import evaluation, firewall
from stock_comp_2026.strategies.dm_variable_box_breakout import bidirectional, submission as sn1_submission
from stock_comp_2026.strategies.dm_eventbox_sn1 import features, models
from stock_comp_2026.strategies.dm_eventbox_sn1.submission import (
    predict_candidate_from_features,
)


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DM-20260930-02"
YEARS = tuple(range(2011, 2017))
ANNUALIZATION = 252
BASELINE_REFERENCE = ROOT / (
    "artifacts/DM-20260927-04/run-20260927T101500Z/"
    "predictions/SN1_H1_train.parquet"
)
SOURCE_PATHS = (
    "research/experiments/eventbox_sn1.py",
    "research/evaluation.py",
    "research/firewall.py",
    "stock_comp_2026/strategies/dm_eventbox_sn1/features.py",
    "stock_comp_2026/strategies/dm_eventbox_sn1/models.py",
    "stock_comp_2026/strategies/dm_eventbox_sn1/submission.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/features.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/submission.py",
    "stock_comp_2026/strategies/dm_event_box/core.py",
    "stock_comp_2026/strategies/dm_event_box/features.py",
)
SOURCE_SCAN_PATHS = (
    "stock_comp_2026/strategies/dm_eventbox_sn1/features.py",
    "stock_comp_2026/strategies/dm_eventbox_sn1/models.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/features.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py",
    "stock_comp_2026/strategies/dm_event_box/core.py",
    "stock_comp_2026/strategies/dm_event_box/features.py",
)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _source_scan():
    findings = []
    checks = {
        "negative_shift": "shift(-",
        "backfill": ".bfill(",
        "centered_rolling": "center=True",
        "valid_input_filename": "_valid.parquet",
        "raw_target_filename": "raw_target_",
    }
    for relative in SOURCE_SCAN_PATHS:
        text = (ROOT / relative).read_text(encoding="utf-8")
        for name, needle in checks.items():
            if needle in text:
                findings.append({"source": relative, "check": name, "match": needle})
    return {
        "sources": list(SOURCE_SCAN_PATHS),
        "checks": list(checks),
        "findings": findings,
        "passed": not findings,
        "scope_note": "Text scan for registered predictors and model route; runtime Train firewall and mutation tests are also recorded separately.",
    }


def _atomic_equal(left, right, label):
    if not left.index.equals(right.index) or list(left.columns) != list(right.columns):
        raise AssertionError(f"{label}: index or columns differ")
    pd.testing.assert_frame_equal(left, right, check_exact=True, check_dtype=True)


def _score_frame(score):
    if isinstance(score, pd.DataFrame):
        if score.shape[1] != 1:
            raise ValueError("Scores must have exactly one column")
        score = score.iloc[:, 0]
    score = score.astype("float64").rename("Return")
    if score.index.has_duplicates or not np.isfinite(score.to_numpy()).all():
        raise ValueError("Score index must be unique and values finite")
    return score.to_frame()


def _metrics_for_period(score, target, year=None):
    daily = evaluation.daily_account(score, target)
    if year is not None:
        daily = daily.loc[daily.index.year == year]
    return evaluation.metrics(daily), daily


def _quintile_spread(metrics_row):
    return float(metrics_row["q5_daily_return"] - metrics_row["q1_daily_return"])


def _portfolio_tables(scores, target, output):
    fold_rows = []
    summary_rows = []
    daily_accounts = {}
    for candidate, score in scores.items():
        summary, all_daily = _metrics_for_period(score, target)
        selected = all_daily.loc[all_daily.index.year.isin(YEARS)]
        summary = evaluation.metrics(selected)
        summary_rows.append({"candidate": candidate, **summary,
                             "q5_q1_spread": _quintile_spread(summary)})
        daily_accounts[candidate] = all_daily
        for year in YEARS:
            annual = all_daily.loc[all_daily.index.year == year]
            fold_rows.append({"candidate": candidate, "year": year,
                              **evaluation.metrics(annual),
                              "q5_q1_spread": _quintile_spread(evaluation.metrics(annual))})

    summary = pd.DataFrame(summary_rows).set_index("candidate")
    folds = pd.DataFrame(fold_rows)
    deltas = []
    reference = summary.loc["SN1_H1"]
    reference_annual = folds.loc[folds["candidate"] == "SN1_H1"].set_index("year")
    for candidate in summary.index:
        if candidate == "SN1_H1":
            continue
        row = summary.loc[candidate]
        record = {"candidate": candidate}
        for metric in (
            "rankic", "rankic_t_hac5", "rankic_hit", "gross_sharpe", "net_sharpe",
            "annual_gross", "annual_net", "annual_cost", "turnover",
            "max_drawdown_compound", "annual_long", "annual_short", "q5_q1_spread",
            "q_monotonicity",
        ):
            record[f"delta_{metric}"] = float(row[metric] - reference[metric])
        candidate_annual = folds.loc[folds["candidate"] == candidate].set_index("year")
        for year in YEARS:
            for metric in ("annual_gross", "annual_net", "net_sharpe", "rankic", "turnover", "annual_cost", "q5_q1_spread"):
                record[f"delta_{metric}_{year}"] = float(candidate_annual.loc[year, metric] - reference_annual.loc[year, metric])
        deltas.append(record)

    output.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output / "portfolio_summary.csv", index_label="candidate")
    folds.to_csv(output / "fold_metrics.csv", index=False)
    pd.DataFrame(deltas).to_csv(output / "incremental.csv", index=False)
    for candidate, account in daily_accounts.items():
        account.to_csv(output / f"daily_account_{candidate}.csv", index_label="Date")
    return summary, folds, pd.DataFrame(deltas), daily_accounts


def _attribution(features_frame, target, output):
    target_rank = bidirectional.centered_target_rank(target)
    years = features_frame.index.get_level_values("Date").year
    lower = features_frame["event_box_position"].lt(0.0)
    up = features_frame["event_upstate"].eq(1.0)
    down = features_frame["event_downstate"].eq(1.0)
    defined_position = features_frame["event_box_position"].notna()
    groups = {
        "UP_STRUCTURE": up,
        "DOWN_STRUCTURE": down,
        "NO_DIRECTIONAL_STRUCTURE": ~up & ~down,
        "UPSTATE_AND_LOWER_BOX": up & lower,
        "UPSTATE_AND_UPPER_BOX": up & defined_position & ~lower,
        "NO_UPSTATE_AND_LOWER_BOX": ~up & lower,
        "NO_UPSTATE_AND_UPPER_BOX": ~up & defined_position & ~lower,
    }
    records = []
    for name, mask in groups.items():
        for year in YEARS:
            selected = mask & (years == year) & target_rank.notna().to_numpy()
            values = target_rank.loc[selected]
            per_date = values.groupby(level="Date").mean()
            returns = target.loc[selected]
            records.append({
                "group": name,
                "year": year,
                "rows": int(selected.sum()),
                "dates": int(per_date.size),
                "mean_daily_centered_target_rank": float(per_date.mean()) if per_date.size else np.nan,
                "mean_row_centered_target_rank": float(values.mean()) if len(values) else np.nan,
                "mean_daily_official_residual_return": float(returns.groupby(level="Date").mean().mean()) if len(returns) else np.nan,
            })
        selected = mask & np.isin(years, YEARS) & target_rank.notna().to_numpy()
        values = target_rank.loc[selected]
        per_date = values.groupby(level="Date").mean()
        returns = target.loc[selected]
        records.append({
            "group": name,
            "year": "pooled_2011_2016",
            "rows": int(selected.sum()),
            "dates": int(per_date.size),
            "mean_daily_centered_target_rank": float(per_date.mean()) if per_date.size else np.nan,
            "mean_row_centered_target_rank": float(values.mean()) if len(values) else np.nan,
            "mean_daily_official_residual_return": float(returns.groupby(level="Date").mean().mean()) if len(returns) else np.nan,
        })
    result = pd.DataFrame(records)
    result.to_csv(output / "structural_attribution.csv", index=False)
    return result


def _gate_candidate_a(summary, folds):
    base = summary.loc["SN1_H1"]
    candidate = summary.loc["CANDIDATE_A"]
    annual = folds.pivot(index="year", columns="candidate", values="annual_gross")
    positive_years = int((annual["CANDIDATE_A"] - annual["SN1_H1"]).gt(0.0).sum())
    checks = {
        "positive_mean_rankic_delta": bool(candidate["rankic"] > base["rankic"]),
        "positive_mean_gross_delta": bool(candidate["annual_gross"] > base["annual_gross"]),
        "positive_mean_q5_q1_delta": bool(candidate["q5_q1_spread"] > base["q5_q1_spread"]),
        "gross_uplift_in_at_least_four_of_six_years": positive_years >= 4,
    }
    return {"checks": checks, "positive_gross_years": positive_years,
            "passed": bool(all(checks.values()))}


def _support_status(candidate_name, summary, folds, attribution):
    base = summary.loc["SN1_H1"]
    candidate = summary.loc[candidate_name]
    annual = folds.pivot(index="year", columns="candidate", values="annual_gross")
    positive_years = int((annual[candidate_name] - annual["SN1_H1"]).gt(0.0).sum())
    checks = {
        "positive_mean_rankic_delta": bool(candidate["rankic"] > base["rankic"]),
        "positive_mean_gross_delta": bool(candidate["annual_gross"] > base["annual_gross"]),
        "positive_mean_q5_q1_delta": bool(candidate["q5_q1_spread"] > base["q5_q1_spread"]),
        "gross_uplift_in_at_least_four_of_six_years": positive_years >= 4,
        "net_sharpe_not_lower": bool(candidate["net_sharpe"] >= base["net_sharpe"]),
    }
    if candidate_name == "CANDIDATE_B":
        pooled = attribution.loc[attribution["year"] == "pooled_2011_2016"].set_index("group")
        checks["upstate_lower_box_outperforms_no_upstate_lower_box"] = bool(
            pooled.loc["UPSTATE_AND_LOWER_BOX", "mean_daily_centered_target_rank"]
            > pooled.loc["NO_UPSTATE_AND_LOWER_BOX", "mean_daily_centered_target_rank"]
        )
    return {"checks": checks, "positive_gross_years": positive_years,
            "status": "SUPPORTED" if all(checks.values()) else "REJECTED"}


def _mutate_future(inputs, target, cutoff):
    mutated = {name: frame.copy(deep=True) for name, frame in inputs.items()}
    changed_target = target.copy(deep=True)
    for name in ("raw_return_1day", "beta_1day"):
        frame = mutated[name]
        mask = frame.index.get_level_values("Date") > cutoff
        frame.loc[mask, "Return"] = frame.loc[mask, "Return"].fillna(0.0) * -11.0 + 3.0
    market = mutated["topix_return_1day"]
    mask = market.index > cutoff
    market.loc[mask, "Return"] = market.loc[mask, "Return"].fillna(0.0) * 7.0 - 1.0
    quotes = mutated["prices_daily_quotes"]
    mask = quotes.index.get_level_values("Date") > cutoff
    for column in ("Open", "High", "Low", "Close"):
        quotes.loc[mask, column] = quotes.loc[mask, column] * 5.0
    quotes.loc[mask, "AdjustmentFactor"] = 0.5
    label_mask = changed_target.index.get_level_values("Date") > cutoff
    changed_target.loc[label_mask] = 100.0 - changed_target.loc[label_mask].fillna(0.0) * 17.0
    return mutated, changed_target


def _prefix_invariance(inputs, target, original_x, scores, output, cutoff):
    mutated_inputs, mutated_target = _mutate_future(inputs, target, pd.Timestamp(cutoff))
    mutated_x = features.build_features(mutated_inputs)
    dates = original_x.index.get_level_values("Date")
    prefix = dates <= pd.Timestamp(cutoff)
    original_prefix = original_x.loc[prefix]
    mutated_prefix = mutated_x.loc[prefix]
    _atomic_equal(original_prefix, mutated_prefix, "feature prefix")
    mutated_scores = {
        "SN1_H1": sn1_submission.predict_from_features(mutated_x, mutated_target)[0]["Return"],
        "CANDIDATE_A": predict_candidate_from_features(mutated_x, mutated_target, "A")[0],
    }
    if "CANDIDATE_B" in scores:
        mutated_scores["CANDIDATE_B"] = predict_candidate_from_features(mutated_x, mutated_target, "B")[0]
    prediction_records = {}
    for candidate, original_score in scores.items():
        left = original_score.loc[prefix]
        right = mutated_scores[candidate].loc[prefix]
        if not left.index.equals(right.index):
            raise AssertionError(f"{candidate} prefix prediction indexes differ")
        difference = float((left - right).abs().max()) if len(left) else 0.0
        if difference != 0.0:
            raise AssertionError(f"{candidate} prefix predictions changed by {difference}")
        prediction_records[candidate] = {
            "rows": int(len(left)),
            "bitwise_equal": bool(np.array_equal(left.to_numpy(), right.to_numpy())),
            "max_abs_difference": difference,
        }
    return {
        "cutoff": pd.Timestamp(cutoff).date().isoformat(),
        "future_mutation": {
            "raw_return_1day_train": "after-cutoff Return x -11 + 3",
            "beta_1day_train": "after-cutoff Return x -11 + 3",
            "topix_return_1day_train": "after-cutoff Return x 7 - 1",
            "prices_daily_quotes_train": "after-cutoff OHLC x 5; AdjustmentFactor set to 0.5",
            "target_1day_train": "after-cutoff Return transformed to 100 - 17 * Return",
        },
        "feature_rows": int(prefix.sum()),
        "feature_columns": int(original_x.shape[1]),
        "feature_prefix_bitwise_equal": True,
        "prediction_prefix": prediction_records,
        "all_checks_pass": True,
    }


def _write_run_record(run_json, updates):
    path = Path(run_json)
    current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    current.update(updates)
    write_json(path, current)


def run(data_dir, output_dir, run_json, baseline_reference=BASELINE_REFERENCE):
    started = time.time()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_json = Path(run_json)
    state = {"status": "running", "started_at_utc": datetime.now(timezone.utc).isoformat()}
    _write_run_record(run_json, state)
    try:
        scan = _source_scan()
        write_json(output_dir / "audit/source_scan.json", scan)
        if not scan["passed"]:
            raise AssertionError(f"Static leak scan found {len(scan['findings'])} issue(s)")

        input_paths = sorted(Path(data_dir).glob("*_train.parquet"))
        expected_names = {
            "raw_return_1day_train.parquet", "beta_1day_train.parquet",
            "topix_return_1day_train.parquet", "prices_daily_quotes_train.parquet",
            "target_1day_train.parquet",
        }
        actual_names = {path.name for path in input_paths}
        if actual_names != expected_names:
            raise ValueError(f"Train-only stage contents differ from registered inputs: {sorted(actual_names)}")
        input_hashes = {path.name: digest(path) for path in input_paths}
        source_hashes = {relative: digest(ROOT / relative) for relative in SOURCE_PATHS}

        allowed = [Path(baseline_reference)] if Path(baseline_reference).is_file() else []
        firewall.install(allowed_artifacts=allowed)
        inputs = features.load_inputs(data_dir, split="train")
        target = pd.read_parquet(Path(data_dir) / "target_1day_train.parquet")["Return"].sort_index()
        x = features.build_features(inputs)
        if not x.index.equals(target.index):
            raise ValueError("Combined Train feature/target indexes differ")
        required_finite = (
            "event_upstate", "event_downstate", "event_bo_up_strength",
            "event_bo_down_strength", "event_breakout_failure",
        )
        if not np.isfinite(x.loc[:, list(required_finite)].to_numpy(dtype=float)).all():
            raise ValueError("Required Event-Box state features contain nonfinite values")

        baseline, baseline_records = predict_candidate_from_features(x, target, "baseline")
        if not baseline.index.equals(target.index) or not np.isfinite(baseline.to_numpy()).all():
            raise ValueError("Baseline H1 score does not provide finite full-panel coverage")
        independent_predictions, _ = bidirectional.walk_forward_predictions(x, target)
        independent = sn1_submission.candidate_scores_from_predictions(
            x, independent_predictions
        )["SIDE_SOURCE_SEPARATION"]
        if not baseline.index.equals(independent.index):
            raise AssertionError("Current SN1_H1 baseline routes have different indexes")
        max_error = float((baseline - independent).abs().max())
        if max_error != 0.0:
            raise AssertionError(f"Current SN1_H1 baseline reproduction failed: max_abs_error={max_error}")

        archived_run_path = baseline_reference.parent.parent / "run.json"
        archived_run = json.loads(archived_run_path.read_text(encoding="utf-8"))
        archived_feature_hash = archived_run["source_sha256"][
            "stock_comp_2026/strategies/dm_variable_box_breakout/features.py"
        ]
        current_feature_hash = source_hashes[
            "stock_comp_2026/strategies/dm_variable_box_breakout/features.py"
        ]
        archive_comparable = archived_feature_hash == current_feature_hash
        archived_check = {
            "path": str(baseline_reference.relative_to(ROOT)),
            "archived_directional_feature_sha256": archived_feature_hash,
            "current_directional_feature_sha256": current_feature_hash,
            "same_feature_source": archive_comparable,
            "used_as_comparison": False,
        }
        if archive_comparable:
            historical_score = pd.read_parquet(baseline_reference)["Return"].sort_index()
            shared = baseline.index.intersection(historical_score.index)
            if not len(shared):
                raise AssertionError("Comparable archived H1 reference has no overlap")
            historical_error = float((baseline.loc[shared] - historical_score.loc[shared]).abs().max())
            archived_check.update({
                "matched_rows": int(len(shared)),
                "max_abs_error": historical_error,
                "bitwise_equal": historical_error == 0.0,
                "used_as_comparison": True,
            })
        else:
            archived_check["comparison_status"] = "not_comparable_pre_split_date_atr_correction"

        scores = {"SN1_H1": baseline}
        predictions = {"SN1_H1": _score_frame(baseline)}
        predictions["SN1_H1"].to_parquet(output_dir / "predictions/SN1_H1.parquet")
        models_dir = output_dir / "models"
        candidate_a, candidate_a_records = predict_candidate_from_features(
            x, target, "A", model_dir=models_dir
        )
        if not candidate_a.index.equals(target.index) or not np.isfinite(candidate_a.to_numpy()).all():
            raise ValueError("Candidate A score coverage or finiteness failure")
        scores["CANDIDATE_A"] = candidate_a
        predictions["CANDIDATE_A"] = _score_frame(candidate_a)
        predictions["CANDIDATE_A"].to_parquet(output_dir / "predictions/CANDIDATE_A.parquet")

        summary, folds, deltas, _ = _portfolio_tables(
            scores, target, output_dir / "metrics"
        )
        attribution = _attribution(x, target, output_dir / "metrics")
        gate_a = _gate_candidate_a(summary, folds)
        support_a = _support_status("CANDIDATE_A", summary, folds, attribution)
        actual_trials = ["EVENTBOX_SN1_A"]
        candidate_b_result = {"run": False, "reason": "Candidate A did not pass the pre-registered information gate"}

        if gate_a["passed"]:
            candidate_b, candidate_b_records = predict_candidate_from_features(
                x, target, "B", model_dir=models_dir
            )
            if not candidate_b.index.equals(target.index) or not np.isfinite(candidate_b.to_numpy()).all():
                raise ValueError("Candidate B score coverage or finiteness failure")
            scores["CANDIDATE_B"] = candidate_b
            predictions["CANDIDATE_B"] = _score_frame(candidate_b)
            predictions["CANDIDATE_B"].to_parquet(output_dir / "predictions/CANDIDATE_B.parquet")
            summary, folds, deltas, _ = _portfolio_tables(
                scores, target, output_dir / "metrics"
            )
            support_a = _support_status("CANDIDATE_A", summary, folds, attribution)
            support_b = _support_status("CANDIDATE_B", summary, folds, attribution)
            candidate_b_result = {
                "run": True,
                "records": candidate_b_records,
                "support": support_b,
            }
            actual_trials.append("EVENTBOX_SN1_B")

        # Prefix checks use a cutoff inside the 2014 annual prediction fold.
        cutoff = "2014-06-30"
        prefix = _prefix_invariance(inputs, target, x, scores, output_dir / "audit", cutoff)
        write_json(output_dir / "audit/prefix_invariance.json", prefix)
        write_json(output_dir / "audit/baseline_reproduction.json", {
            "passed": True,
            "current_code_route": "variable_box_breakout.submission.predict_from_features",
            "independent_rebuild_route": "bidirectional.walk_forward_predictions + candidate_scores_from_predictions",
            "matched_rows": int(len(baseline)),
            "max_abs_error": max_error,
            "bitwise_equal": True,
        })
        write_json(output_dir / "audit/historical_h1_comparability.json", archived_check)
        write_json(output_dir / "audit/coverage.json", {
            "input_rows": int(len(x)),
            "score_rows": {name: int(len(score)) for name, score in scores.items()},
            "index_exact": {name: bool(score.index.equals(target.index)) for name, score in scores.items()},
            "all_score_values_finite": {name: bool(np.isfinite(score.to_numpy()).all()) for name, score in scores.items()},
            "event_upstate_rows": int(x["event_upstate"].sum()),
            "event_downstate_rows": int(x["event_downstate"].sum()),
            "pullback_up_rows": int(x["pullback_up"].gt(0.0).sum()),
            "target_coverage": float(target.notna().mean()),
        })
        _write_run_record(run_json, {
            "status": "completed",
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(time.time() - started, 3),
            "command": " ".join(sys.argv),
            "actual_trials": actual_trials,
            "max_trials": 2,
            "random_seed": 20260930,
            "train_data_sha256": input_hashes,
            "source_sha256": source_hashes,
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "baseline_reproduction": {"matched_rows": int(len(baseline)), "max_abs_error": max_error},
            "historical_h1_comparability": archived_check,
            "candidate_a_gate": gate_a,
            "candidate_a_support": support_a,
            "candidate_b": candidate_b_result,
            "prefix_invariance": prefix,
        })
        firewall.save(output_dir / "audit/firewall.json")
        return {
            "summary": summary,
            "folds": folds,
            "deltas": deltas,
            "attribution": attribution,
            "gate_a": gate_a,
            "support_a": support_a,
            "candidate_b": candidate_b_result,
            "actual_trials": actual_trials,
            "baseline_records": baseline_records,
            "candidate_a_records": candidate_a_records,
        }
    except BaseException as error:
        try:
            firewall.save(output_dir / "audit/firewall.json")
        except Exception:
            pass
        _write_run_record(run_json, {
            "status": "failed",
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(time.time() - started, 3),
            "command": " ".join(sys.argv),
            "error": f"{type(error).__name__}: {error}",
        })
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-json", required=True)
    parser.add_argument("--baseline-reference", default=str(BASELINE_REFERENCE))
    args = parser.parse_args()
    result = run(args.data_dir, args.output_dir, args.run_json, Path(args.baseline_reference))
    print(json.dumps({
        "actual_trials": result["actual_trials"],
        "candidate_a_gate": result["gate_a"],
        "candidate_a_support": result["support_a"],
        "candidate_b": result["candidate_b"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
