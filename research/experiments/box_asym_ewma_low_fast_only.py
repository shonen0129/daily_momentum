"""One fixed Low-fast-only EWMA diagnostic on saved Train score streams."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from research import evaluation, firewall
from research.experiments import box_asym_ewma as asym
from research.experiments import box_asymmetry_gate as prior
from stock_comp_2026.strategies.dm_variable_box_breakout import features


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DM-20260927-02"
SOURCE_SIGNALS = ROOT / "artifacts/DM-20260925-03/run-20260926T063602Z/predictions/signals.parquet"
PREVIOUS_RUN = ROOT / "artifacts/DM-20260927-01/run-20260926T165750Z-01"
PREVIOUS_SCORES = PREVIOUS_RUN / "predictions/strategy_scores.parquet"
PREVIOUS_WEIGHTS = PREVIOUS_RUN / "predictions/portfolio_weights.parquet"
DATA_DIR = ROOT / "stock_comp_2026/input"
BASE_ALPHA = 0.25
LOW_ALPHA = 0.50
ONE_WAY_COST = 0.001
ANNUALIZATION = 252
BOOTSTRAP_SEED = 20260925
BOOTSTRAP_REPS = 1000
BOOTSTRAP_BLOCK = 20
TRIALS = (
    "B00_BASE", "BOX_ORIGINAL", "A_LOW_NO_CARRY", "C_ASYM_EWMA",
    "C_B00_ASYM_EWMA", "D_LOW_FAST_ONLY", "D_B00_LOW_FAST_ONLY",
)


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def low_fast_score(raw, name):
    """Keep the original High EWMA; change only the Low EWMA alpha."""
    high_raw, low_raw = prior.split_raw_sides(raw)
    high_state = prior.segment_ewma(high_raw, BASE_ALPHA)
    low_state = prior.segment_ewma(low_raw, LOW_ALPHA)
    return (high_state + low_state).rename(name), high_state, low_state, high_raw, low_raw


def period_dates(daily):
    dates = pd.DatetimeIndex(daily.index)
    periods = [("full_train_eval", dates), ("ex_2016", dates[dates.year != 2016])]
    periods.extend((str(year), dates[dates.year == year]) for year in range(2011, 2017))
    return [(label, pd.DatetimeIndex(ix)) for label, ix in periods if len(ix)]


def paired_period_table(summary, pairs):
    rows = []
    for candidate, baseline in pairs:
        c = summary.loc[summary.strategy.eq(candidate)].set_index("period")
        b = summary.loc[summary.strategy.eq(baseline)].set_index("period")
        for period in c.index.intersection(b.index):
            x, y = c.loc[period], b.loc[period]
            rows.append({
                "candidate": candidate, "baseline": baseline, "period": period,
                "delta_annual_gross_return": x.annual_gross_return - y.annual_gross_return,
                "delta_annual_net_return": x.annual_net_return - y.annual_net_return,
                "delta_annual_cost": x.annualized_cost - y.annualized_cost,
                "delta_gross_volatility": x.annualized_gross_volatility - y.annualized_gross_volatility,
                "delta_gross_sharpe": x.gross_sharpe - y.gross_sharpe,
                "delta_net_sharpe": x.net_sharpe - y.net_sharpe,
                "delta_turnover_per_day": x.turnover_per_day - y.turnover_per_day,
                "delta_selection_component": x.annual_selection_component - y.annual_selection_component,
                "delta_rankic": x.rankic - y.rankic,
            })
    return pd.DataFrame(rows)


def bootstrap_table(accounts):
    pairs = (
        ("D_LOW_FAST_ONLY", "BOX_ORIGINAL"),
        ("D_B00_LOW_FAST_ONLY", "B00_BASE"),
        ("D_LOW_FAST_ONLY", "D_B00_LOW_FAST_ONLY"),
    )
    rows = []
    for candidate, baseline in pairs:
        c, b = accounts[candidate]["net"], accounts[baseline]["net"]
        common = c.index.intersection(b.index)
        if not c.index.equals(b.index):
            c, b = c.loc[common], b.loc[common]
        result = evaluation.bootstrap_delta(
            b, c, seed=BOOTSTRAP_SEED, reps=BOOTSTRAP_REPS, block=BOOTSTRAP_BLOCK,
        )
        rows.append({
            "candidate": candidate, "baseline": baseline,
            "delta_net_sharpe": evaluation.sharpe(c) - evaluation.sharpe(b),
            "paired_circular_block_ci_low": result["low"],
            "paired_circular_block_ci_high": result["high"],
            "positive_difference_ratio": result["bootstrap_positive_fraction"],
            "repetitions": result["reps"], "block_days": result["block"], "seed": result["seed"],
            "paired_days": len(common),
        })
    return pd.DataFrame(rows)


def run(config_path, output_path):
    started = time.monotonic()
    config_path, output = Path(config_path), Path(output_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    expected = [item["trial_id"] for item in config.get("trials", [])]
    p = config.get("parameters", {})
    if (config.get("experiment_id") != EXPERIMENT_ID or config.get("data_split") != "train"
            or config.get("valid_evaluation") is not False or config.get("selection_eligible") is not False
            or config.get("max_trials") != len(TRIALS) or tuple(expected) != TRIALS
            or p.get("candidate_d_alpha_high") != BASE_ALPHA or p.get("candidate_d_alpha_low") != LOW_ALPHA
            or p.get("bootstrap", {}).get("block_days") != BOOTSTRAP_BLOCK
            or p.get("bootstrap", {}).get("repetitions") != BOOTSTRAP_REPS
            or p.get("bootstrap", {}).get("seed") != BOOTSTRAP_SEED):
        raise ValueError("Config differs from the one pre-registered Low-fast-only diagnostic")
    for directory in ("models", "predictions", "metrics", "audit", "logs"):
        (output / directory).mkdir(parents=True, exist_ok=True)
    run_path = output / "run.json"
    metadata = json.loads(run_path.read_text(encoding="utf-8"))
    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, check=True,
                           capture_output=True, text=True).stdout.strip()
    sources = [Path(__file__).resolve(), Path(asym.__file__).resolve(), Path(prior.__file__).resolve(),
               Path(features.__file__).resolve(), Path(evaluation.__file__).resolve(), Path(firewall.__file__).resolve()]
    metadata.update({
        "status": "running", "started_at_utc": now_utc(), "command": sys.argv,
        "git_commit_hash": git_head, "git_worktree_dirty": bool(dirty),
        "source_run_id": "run-20260926T063602Z", "comparison_run_id": PREVIOUS_RUN.name,
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "numpy": np.__version__, "pandas": pd.__version__},
        "code_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in sources},
        "source_artifact_sha256": {str(path.relative_to(ROOT)): sha256(path)
                                    for path in (SOURCE_SIGNALS, PREVIOUS_SCORES, PREVIOUS_WEIGHTS)},
        "cost_oneway": ONE_WAY_COST, "annualization": ANNUALIZATION,
        "parameter_values": p, "actual_trials": 0, "valid_accessed": False,
    })
    dump(run_path, metadata)
    try:
        firewall.install(allowed_artifacts=(SOURCE_SIGNALS, PREVIOUS_SCORES, PREVIOUS_WEIGHTS))
        print("[1/6] Load saved signal stream, preceding diagnostic, and Train-only labels/sectors...", flush=True)
        saved = pd.read_parquet(SOURCE_SIGNALS).sort_index()
        previous_scores = pd.read_parquet(PREVIOUS_SCORES).sort_index()
        previous_weights = pd.read_parquet(PREVIOUS_WEIGHTS).sort_index()
        target = pd.read_parquet(DATA_DIR / "target_1day_train.parquet")["Return"].sort_index().rename("Return")
        listed = pd.read_parquet(DATA_DIR / "listed_info_train.parquet", columns=[
            "Sector33Code", "Sector33CodeName", "Sector17Code", "Sector17CodeName"
        ]).sort_index()
        if not saved.index.is_unique or not target.index.is_unique or not listed.index.is_unique:
            raise AssertionError("Expected unique (Date, Code) keys")
        index = saved.index
        if not index.equals(target.index):
            raise AssertionError("Saved signals and Train target indexes differ")
        sector = listed.reindex(index)
        sector_coverage = float(sector["Sector33Code"].notna().mean())
        if sector_coverage < 0.95:
            raise AssertionError(f"Unexpected PIT sector coverage {sector_coverage:.2%}")
        metadata["train_data_sha256"] = {
            name: sha256(DATA_DIR / name) for name in ("target_1day_train.parquet", "listed_info_train.parquet")
        }
        dump(run_path, metadata)

        print("[2/6] Reconstruct raw streams; apply D with High alpha fixed at 0.25...", flush=True)
        scores = {
            "B00_BASE": saved["B00"].rename("B00_BASE"),
            "BOX_ORIGINAL": saved["BOX_BIDIR_STANDALONE"].rename("BOX_ORIGINAL"),
        }
        raw_by_name, components, inverse_errors, high_state_errors = {}, {}, {}, {}
        for source_name, base_name, d_name, c_name in (
            ("B00", "B00_BASE", "D_B00_LOW_FAST_ONLY", "C_B00_ASYM_EWMA"),
            ("BOX_BIDIR_STANDALONE", "BOX_ORIGINAL", "D_LOW_FAST_ONLY", "C_ASYM_EWMA"),
        ):
            raw, inv_error = prior.inverse_ewma(saved[source_name].rename(source_name), BASE_ALPHA)
            inverse_errors[base_name] = inv_error
            raw_by_name[base_name] = raw
            high_raw, low_raw = prior.split_raw_sides(raw)
            high_base = prior.segment_ewma(high_raw, BASE_ALPHA)
            low_base = prior.segment_ewma(low_raw, BASE_ALPHA)
            rebuilt = high_base + low_base
            if float((rebuilt - saved[source_name]).abs().max()) > 2e-12:
                raise AssertionError(f"Baseline raw split does not reproduce {source_name}")
            scores[d_name], high_d, low_d, _, _ = low_fast_score(raw, d_name)
            if float((high_d - high_base).abs().max()) > 1e-14:
                raise AssertionError(f"D High state differs from {base_name} High state")
            high_state_errors[d_name] = float((high_d - high_base).abs().max())
            scores[c_name], _, _ = asym.asymmetric_score(raw, c_name)
            components[base_name] = asym.score_components(high_raw, low_raw, BASE_ALPHA, BASE_ALPHA)
            components[d_name] = asym.score_components(high_raw, low_raw, BASE_ALPHA, LOW_ALPHA)
            components[c_name] = asym.score_components(high_raw, low_raw, asym.ALPHA_HIGH, LOW_ALPHA)
            if base_name == "BOX_ORIGINAL":
                scores["A_LOW_NO_CARRY"] = prior.asymmetric_score_from_raw(raw, BASE_ALPHA, "A_LOW_NO_CARRY")
                components["A_LOW_NO_CARRY"] = asym.score_components(
                    high_raw, low_raw, BASE_ALPHA, BASE_ALPHA, low_no_carry=True)
        if float((scores["D_LOW_FAST_ONLY"] -
                  (components["D_LOW_FAST_ONLY"].iloc[:, :3].sum(axis=1)
                   + components["D_LOW_FAST_ONLY"].iloc[:, 3:].sum(axis=1))).abs().max()) > 2e-12:
            raise AssertionError("D source components fail additivity")
        for name in TRIALS:
            if name not in scores or not np.isfinite(scores[name].to_numpy()).all():
                raise AssertionError(f"Invalid or missing score {name}")
        # Verify the first five signals exactly reproduce DM-20260927-01.
        prior_score_errors = {}
        for name in TRIALS[:5]:
            prior_score_errors[name] = float((scores[name] - previous_scores[name]).abs().max())
            if prior_score_errors[name] > 2e-12:
                raise AssertionError(f"Prior full Train score mismatch: {name}")

        print("[3/6] Preserve prior eval dates, official weights/accounting, and prior replay...", flush=True)
        prior_daily_base = pd.read_csv(PREVIOUS_RUN / "metrics/daily_account_B00_BASE.csv",
                                      parse_dates=["Date"], index_col="Date")
        eval_dates = pd.DatetimeIndex(prior_daily_base.index)
        if (str(eval_dates.min().date()), str(eval_dates.max().date())) != ("2011-01-04", "2016-03-29") or len(eval_dates) != 1275:
            raise AssertionError("Prior purged 1,275-date evaluation span changed")
        eval_2016 = eval_dates[eval_dates.year == 2016]
        if (str(eval_2016.min().date()), str(eval_2016.max().date()), len(eval_2016)) != (
            "2016-01-04", "2016-03-29", 59):
            raise AssertionError("Registered 2016 partial span changed")
        specs = {}
        for name in TRIALS:
            weight, q = prior.quintile_weights(scores[name])
            specs[name] = (scores[name], weight, q)
        accounts, weights_store, q_store = {}, {}, {}
        prior_account_errors, prior_weight_errors = {}, {}
        for name, (score, weight, q) in specs.items():
            daily, _, _ = prior.account_from_weights(score, weight, q, target)
            daily = daily.loc[daily.index.isin(eval_dates)]
            accounts[name], weights_store[name], q_store[name] = daily, weight, q
            if name in TRIALS[:5]:
                old_daily = pd.read_csv(PREVIOUS_RUN / f"metrics/daily_account_{name}.csv",
                                        parse_dates=["Date"], index_col="Date").loc[eval_dates]
                err = max(float((daily[column] - old_daily[column]).abs().max())
                          for column in ("gross", "net", "turnover", "rankic"))
                prior_account_errors[name] = err
                if err > 1e-10:
                    raise AssertionError(f"Prior daily account mismatch {name}: {err}")
                prior_weight_errors[name] = float((weight - previous_weights[name]).abs().max())
                if prior_weight_errors[name] > 1e-12:
                    raise AssertionError(f"Prior official weights mismatch {name}")
        summary_rows = []
        for name in TRIALS:
            score, weight, q = specs[name]
            for period, dates in period_dates(accounts[name]):
                summary_rows.append(prior.stat_record(
                    name, period, score, weight, q,
                    accounts[name].loc[accounts[name].index.isin(dates)], target, sector,
                ))
        summary = pd.DataFrame(summary_rows)
        summary.to_csv(output / "metrics/period_metrics.csv", index=False)
        summary.loc[summary.period.eq("full_train_eval")].to_csv(
            output / "metrics/candidate_summary.csv", index=False)
        contrast_pairs = (
            ("D_LOW_FAST_ONLY", "BOX_ORIGINAL"),
            ("D_LOW_FAST_ONLY", "C_ASYM_EWMA"),
            ("D_LOW_FAST_ONLY", "A_LOW_NO_CARRY"),
            ("D_B00_LOW_FAST_ONLY", "B00_BASE"),
            ("D_LOW_FAST_ONLY", "D_B00_LOW_FAST_ONLY"),
        )
        paired_period_table(summary, contrast_pairs).to_csv(
            output / "metrics/paired_period_differences.csv", index=False)
        bootstrap = bootstrap_table(accounts)
        bootstrap.to_csv(output / "metrics/paired_circular_bootstrap.csv", index=False)

        print("[4/6] Compute rank stability and event-age portfolio attribution...", flush=True)
        rank_daily = pd.concat([
            asym.rank_turnover_diagnostics(name, specs[name][0], weights_store[name], q_store[name], accounts[name])
            for name in TRIALS
        ], ignore_index=True)
        rank_daily.to_csv(output / "metrics/rank_diagnostics_daily.csv", index=False)
        asym.aggregate_rank_diagnostics(rank_daily).to_csv(
            output / "metrics/rank_diagnostics_period.csv", index=False)
        attribution_rows, daily_attr_rows, detail_parts, sector_parts = [], [], [], []
        for name in TRIALS:
            score, weight, q = specs[name]
            table, daily_table, _ = prior.attribution_tables(
                name, score, weight, q, components[name], target, eval_dates)
            attribution_rows.append(table)
            daily_attr_rows.append(daily_table)
            detail = prior.build_audit_detail(score, weight, q, components[name], sector, eval_dates)
            detail_parts.append(detail.assign(strategy=name))
            sector_parts.extend(prior.sector_outputs(name, score, weight, q, sector))
        attribution = pd.concat(attribution_rows, ignore_index=True)
        daily_attribution = pd.concat(daily_attr_rows, ignore_index=True)
        details = pd.concat(detail_parts).sort_index()
        attribution.to_csv(output / "metrics/annual_category_attribution.csv", index=False)
        daily_attribution.to_csv(output / "metrics/daily_category_attribution.csv", index=False)
        prior.yearly_category_attribution(details, daily_attribution).to_csv(
            output / "metrics/category_by_year.csv", index=False)
        pd.DataFrame(sector_parts).to_csv(output / "metrics/sector_tail_composition.csv", index=False)
        prior.zero_sector_bias(details, target).to_csv(output / "metrics/sector_zero_tail_bias.csv", index=False)
        score_eval = pd.DataFrame({name: specs[name][0] for name in TRIALS}).loc[pd.IndexSlice[eval_dates, :], :]
        weight_eval = pd.DataFrame({name: weights_store[name] for name in TRIALS}).loc[pd.IndexSlice[eval_dates, :], :]
        score_eval.to_parquet(output / "predictions/strategy_scores.parquet")
        weight_eval.to_parquet(output / "predictions/portfolio_weights.parquet")
        details.to_parquet(output / "predictions/holdings_audit.parquet")
        for name, daily in accounts.items():
            daily.to_csv(output / f"metrics/daily_account_{name}.csv", index_label="Date")

        print("[5/6] Check source-age additivity, High-state identity, and Train firewall...", flush=True)
        component_errors = {}
        for name in TRIALS:
            error = float((components[name].sum(axis=1) - scores[name]).abs().max())
            component_errors[name] = error
            if error > 2e-12:
                raise AssertionError(f"Source components do not reconstruct {name}: {error}")
        firewall_state = {"status": "PASS", "opened_parquets": sorted(firewall.ACCESSES),
                          "valid_evaluation": False, "raw_target_reads": False}
        dump(output / "audit/firewall.json", firewall_state)
        audit = {
            "evaluation_span": [str(eval_dates.min().date()), str(eval_dates.max().date())],
            "evaluation_days": len(eval_dates),
            "partial_2016_span": [str(eval_2016.min().date()), str(eval_2016.max().date())],
            "partial_2016_days": len(eval_2016), "source_signal_rows": len(saved),
            "score_coverage_rows": {name: int(scores[name].notna().sum()) for name in TRIALS},
            "sector_join_coverage": sector_coverage, "ewma_inverse_max_abs_error": inverse_errors,
            "D_high_state_max_abs_error_vs_original": high_state_errors,
            "prior_score_max_abs_error": prior_score_errors,
            "prior_account_max_abs_error": prior_account_errors,
            "prior_weight_max_abs_error": prior_weight_errors,
            "source_component_max_abs_error": component_errors,
            "official_quintile_match": "PASS: prior.quintile_weights asserts exact match to evaluation.weights",
            "future_prefix_invariance": "PASS: tested on fixed side-wise adjust=False transform",
            "valid_accessed": False, "parquets_opened": sorted(firewall.ACCESSES),
        }
        dump(output / "audit/low_fast_only_audit.json", audit)
        print("[6/6] Finalize run metadata...", flush=True)
        metadata.update({
            "status": "completed", "completed_at_utc": now_utc(), "exit_code": 0,
            "actual_trials": len(TRIALS), "elapsed_seconds": time.monotonic() - started,
            "valid_accessed": False,
            "evaluation_span": [str(eval_dates.min().date()), str(eval_dates.max().date())],
            "partial_2016_span": [str(eval_2016.min().date()), str(eval_2016.max().date())],
            "outputs": {
                "period_metrics": "metrics/period_metrics.csv",
                "paired_period_differences": "metrics/paired_period_differences.csv",
                "paired_circular_bootstrap": "metrics/paired_circular_bootstrap.csv",
                "rank_diagnostics": "metrics/rank_diagnostics_period.csv",
                "category_attribution": "metrics/annual_category_attribution.csv",
                "category_by_year": "metrics/category_by_year.csv",
                "scores": "predictions/strategy_scores.parquet",
                "weights": "predictions/portfolio_weights.parquet",
                "audit": "audit/low_fast_only_audit.json", "firewall": "audit/firewall.json",
            },
        })
        dump(run_path, metadata)
    except BaseException as error:
        metadata.update({"status": "failed", "completed_at_utc": now_utc(), "exit_code": 1,
                         "error": f"{type(error).__name__}: {error}",
                         "elapsed_seconds": time.monotonic() - started})
        dump(run_path, metadata)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.config, args.output)


if __name__ == "__main__":
    main()
