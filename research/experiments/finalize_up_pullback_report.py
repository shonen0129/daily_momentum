"""Recover UP_PULLBACK reporting from a completed metrics artifact without refitting."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from research.experiments import up_pullback_sn1 as driver


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DM-20261001-01"
RUN_ID = "run-20261001T052315Z"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               allow_nan=False) + "\n", encoding="utf-8")


def run():
    run_dir = ROOT / "artifacts" / EXPERIMENT_ID / RUN_ID
    report_dir = ROOT / "reports" / EXPERIMENT_ID
    audit_dir, metrics_dir = run_dir / "audit", run_dir / "metrics"
    source = read_json(audit_dir / "source_scan.json")
    feature = read_json(audit_dir / "feature_causality.json")
    baseline = read_json(audit_dir / "baseline_reproduction.json")
    prefix = read_json(audit_dir / "prefix_invariance.json")
    coverage = read_json(audit_dir / "coverage_determinism.json")
    maturity = read_json(audit_dir / "fold_maturity_and_candidate_model.json")
    firewall = read_json(audit_dir / "firewall.json")
    checks = {
        "source_scan": source["status"] == "PASS",
        "feature_causality": feature["status"] == "PASS",
        "baseline_reproduction": baseline["status"] == "PASS"
        and baseline["current_vs_independent_bitwise_equal"]
        and baseline["current_vs_saved_bitwise_equal"],
        "prefix_invariance": prefix["status"] == "PASS"
        and prefix["feature_prefix_bitwise_equal"]
        and prefix["baseline_score_prefix_bitwise_equal"]
        and prefix["candidate_score_prefix_bitwise_equal"],
        "coverage_determinism": coverage["status"] == "PASS"
        and coverage["deterministic_candidate_replay"],
        "fold_maturity": maturity["status"] == "PASS"
        and maturity["all_max_label_maturity_dates_precede_fold"],
        "firewall": firewall["valid_evaluation"] is False
        and firewall["raw_target_reads"] is False,
    }
    expected = {
        str((run_dir / "input_train" / name).resolve())
        for name in driver.EXPECTED_INPUTS
    }
    checks["firewall"] = checks["firewall"] and set(firewall["opened_parquets"]) == expected
    if not all(checks.values()):
        raise AssertionError(f"Refusing report recovery; audit failure: {checks}")
    baseline.pop("candidate_fitted", None)
    baseline["candidate_fitted_at_reproduction_check"] = False
    baseline["candidate_evaluated_after_passed_gate"] = True
    write_json(audit_dir / "baseline_reproduction.json", baseline)

    pooled = pd.read_csv(metrics_dir / "pooled_metrics.csv").set_index("strategy")
    annual = pd.read_csv(metrics_dir / "fold_year_metrics.csv")
    incremental = pd.read_csv(metrics_dir / "incremental_metrics.csv")
    incremental["period"] = incremental["period"].map(
        lambda value: int(value) if str(value).isdigit() else value
    )
    partial = read_json(metrics_dir / "partial_year_sensitivity.json")
    attribution = pd.read_csv(metrics_dir / "attribution_table.csv")
    decision = read_json(metrics_dir / "decision_gates.json")
    if decision["decision"] != "REJECT" or decision["primary_pass"]:
        raise AssertionError("Saved primary gates do not support the registered rejection")

    final_audit = {
        "baseline_reproduction": "PASS",
        "feature_causality": "PASS",
        "prefix_invariance": "PASS",
        "coverage_determinism": "PASS",
        "fold_maturity": "PASS",
        "firewall": "PASS",
        "valid_evaluation": False,
        "raw_target_accessed": False,
    }
    driver._write_report(report_dir, pooled, annual, incremental, partial,
                         attribution, decision, run_dir / "run.json", final_audit)
    write_json(audit_dir / "final_audit.json", final_audit)

    run_path = run_dir / "run.json"
    run_record = read_json(run_path)
    recovery_time = datetime.now(timezone.utc).isoformat()
    initial_error = run_record.get("initial_runner_error") or run_record.get("error")
    current_code_hash = hashlib.file_digest(
        (ROOT / "research/experiments/up_pullback_sn1.py").open("rb"), "sha256"
    ).hexdigest()
    recovery_code_hash = hashlib.file_digest(Path(__file__).open("rb"), "sha256").hexdigest()
    run_record.update({
        "status": "completed",
        "completed_at_utc": recovery_time,
        "exit_code": 0,
        "initial_runner_exit_code": 1,
        "initial_runner_status": "failed_at_report_render",
        "initial_runner_error": initial_error,
        "recovery": {
            "completed_at_utc": recovery_time,
            "action": "Report-only recovery using saved predictions, metrics, attribution, and completed audits.",
            "recovery_code_sha256": recovery_code_hash,
            "report_generator_code_sha256": current_code_hash,
            "new_candidate_fits": 0,
            "candidate_definition_or_metrics_changed": False,
        },
        "actual_trials": ["UP_PULLBACK_SN1_H1"],
        "max_trials": 1,
        "candidate_evaluated": True,
        "candidate_decision": decision,
        "opened_parquets": firewall["opened_parquets"],
        "valid_evaluation": False,
        "raw_target_accessed": False,
        "final_report": f"reports/{EXPERIMENT_ID}/REPORT.md",
        "command": ".venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.up_pullback_sn1 --data-dir artifacts/DM-20261001-01/run-20261001T052315Z/input_train --output-dir artifacts/DM-20261001-01/run-20261001T052315Z --run-json artifacts/DM-20261001-01/run-20261001T052315Z/run.json",
        "report_recovery_command": ".venv/bin/python -m research.experiments.finalize_up_pullback_report",
    })
    run_record.pop("error", None)
    write_json(run_path, run_record)

    experiment_path = ROOT / "experiments" / EXPERIMENT_ID / "experiment.json"
    experiment = read_json(experiment_path)
    experiment["status"] = "rejected"
    experiment["valid_evaluation"] = False
    write_json(experiment_path, experiment)

    base = pooled.loc["SN1_H1"]
    candidate = pooled.loc["UP_PULLBACK"]
    group = attribution.set_index("group").loc["UPSTATE=1,x<0"]
    d_rank = candidate["rankic"] - base["rankic"]
    d_gross = candidate["annual_gross"] - base["annual_gross"]
    d_spread = candidate["q5_q1_spread"] - base["q5_q1_spread"]
    part = partial["deltas"]
    decision_text = f"""# DM-20261001-01: decision record

Completed 2026-10-01 JST. **Decision: REJECT the fixed UP_PULLBACK feature addition.** The primary Mean RankIC gate was nonpositive; gross-return and Q5−Q1 gates were slightly positive.

- Final recovered run: [`{RUN_ID}`](../../artifacts/{EXPERIMENT_ID}/{RUN_ID}/run.json); report: [REPORT.md](../../reports/{EXPERIMENT_ID}/REPORT.md).
- Exactly one registered candidate was tested. Two prior technical attempts are retained as failed runs. Final report recovery used saved predictions, metrics, attribution, and passing audits; it performed zero additional candidate fits.
- Train inputs: 2008-11-04–2016-03-31; expanding folds 2011–2016; 2016 had 61 sessions and was partial. All dates and the motivating attribution bucket were previously inspected development history, not independent OOS evidence. Valid and raw target were not opened.

## Primary gates

- Mean RankIC: {base['rankic']:.9f} → {candidate['rankic']:.9f}; delta {d_rank:+.9f} — **{'PASS' if decision['primary_gates']['positive_mean_rankic_delta'] else 'FAIL'}**.
- Annualized gross return: {base['annual_gross']*100:.5f}% → {candidate['annual_gross']*100:.5f}%; delta {d_gross*10000:+.4f} bp/year — **{'PASS' if decision['primary_gates']['positive_annual_gross_return_delta'] else 'FAIL'}**.
- Q5−Q1: {base['q5_q1_spread']*10000:.5f} → {candidate['q5_q1_spread']*10000:.5f} bp/day; delta {d_spread*10000:+.5f} bp/day — **{'PASS' if decision['primary_gates']['positive_q5_q1_delta'] else 'FAIL'}**.

Mean RankIC is lower, so the strict three-gate rule rejects this candidate. Excluding partial 2016, the deltas are RankIC {part['rankic']:+.9f}, gross return {part['annual_gross']*10000:+.4f} bp/year, and Q5−Q1 {part['q5_q1_spread']*10000:+.5f} bp/day. The pooled gross lift depends on the partial year.

Long contribution changed {decision['delta_annual_long']*10000:+.4f} bp/year and Short contribution {decision['delta_annual_short']*10000:+.4f} bp/year. Turnover rose {candidate['turnover']-base['turnover']:+.8f} per day and full one-way annualized cost rose {(candidate['annual_cost_all']-base['annual_cost_all'])*10000:+.5f} bp/year. Gross return also rose, so the net change is not explained by lower trading cost.

In `UPSTATE=1, x<0`, mean score change was positive, but net Q4/Q5 migration was {int(group['net_q4_q5_migration_rows']):+d} rows (baseline 6,394; candidate 6,393). That bucket's annualized gross contribution changed {group['gross_contribution_change_annualized']*10000:+.4f} bp/year. The feature did not move additional bucket rows into Q4/Q5.

## Verification

- Current SN1_H1 matched an independent current-code rebuild and the saved DM-20260930-02 baseline bit for bit on 809,636 rows.
- Static source/leak scan, exact feature formula/column contract, 2014-06-30 future mutation of all five Train inputs including Train target, and feature/baseline/candidate prefix equality passed.
- Index coverage, 809,636 finite scores per strategy, deterministic candidate replay, two-position label maturity purge, and Train-only firewall passed.
- Model and metric generation finished in 115.0 seconds under the 1,800-second deadline. A report-render path error was recovered using saved artifacts with zero additional candidate fits.
- No new feature, parameter, threshold, horizon, Valid evaluation, or Freeze followed the result.

This rejects only this fixed `UP_PULLBACK` feature addition to SN1_H1. It does not reject Event Box generally, pullbacks generally, or trend following generally.
"""
    (ROOT / "experiments" / EXPERIMENT_ID / "decision.md").write_text(
        decision_text, encoding="utf-8"
    )
    print(json.dumps({
        "decision": decision["decision"],
        "primary_gates": decision["primary_gates"],
        "report": str((report_dir / "REPORT.md").relative_to(ROOT)),
        "run_status": "completed_after_report_recovery",
        "audits": checks,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
