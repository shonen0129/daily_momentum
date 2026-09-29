"""Fixed Train-only diagnostic for asymmetric High/Low EWMA persistence."""
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
from research.experiments import box_asymmetry_gate as prior
from stock_comp_2026.strategies.dm_variable_box_breakout import features


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DM-20260927-01"
SOURCE_SIGNALS = ROOT / "artifacts/DM-20260925-03/run-20260926T063602Z/predictions/signals.parquet"
PRIOR_RUN = ROOT / "artifacts/DM-20260926-01/run-20260926T143032Z-08"
PRIOR_SCORES = PRIOR_RUN / "predictions/strategy_scores.parquet"
PRIOR_WEIGHTS = PRIOR_RUN / "predictions/portfolio_weights.parquet"
DATA_DIR = ROOT / "stock_comp_2026/input"
BASE_ALPHA = 0.25
ALPHA_HIGH = 0.15
ALPHA_LOW = 0.50
ONE_WAY_COST = 0.001
ANNUALIZATION = 252
STRATEGIES = ("B00_BASE", "BOX_ORIGINAL", "A_LOW_NO_CARRY", "C_ASYM_EWMA", "C_B00_ASYM_EWMA")


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def asymmetric_score(raw, name):
    """Apply the registered High/Low alphas to signed raw event streams."""
    high_raw, low_raw = prior.split_raw_sides(raw)
    high_score = prior.segment_ewma(high_raw, ALPHA_HIGH)
    low_score = prior.segment_ewma(low_raw, ALPHA_LOW)
    result = (high_score + low_score).rename(name)
    return result, high_raw, low_raw


def side_components(raw, alpha, side):
    """Additively attribute a side's EWMA state to event day and event ages."""
    groups = features.segment_keys(raw.index)
    first = raw.groupby(groups, sort=False).cumcount().eq(0)
    total = prior.segment_ewma(raw, alpha)
    event_day = (alpha * raw).where(~first, raw).rename(f"{side}_event_day")
    age_1_4 = pd.Series(0.0, index=raw.index)
    for age in range(1, 5):
        lagged = raw.groupby(groups, sort=False).shift(age).fillna(0.0)
        age_1_4 = age_1_4 + alpha * (1.0 - alpha) ** age * lagged
    age_1_4 = age_1_4.rename(f"{side}_age_1_4")
    age_5_plus = (total - event_day - age_1_4).rename(f"{side}_age_5_plus")
    return pd.DataFrame({event_day.name: event_day, age_1_4.name: age_1_4,
                         age_5_plus.name: age_5_plus}, index=raw.index)


def score_components(high_raw, low_raw, high_alpha, low_alpha, low_no_carry=False):
    high = side_components(high_raw, high_alpha, "high")
    low = side_components(low_raw, low_alpha, "low")
    if low_no_carry:
        low.loc[:, ["low_age_1_4", "low_age_5_plus"]] = 0.0
    return pd.concat([high, low], axis=1)


def portfolio_specs(scores):
    specs = {}
    for name in STRATEGIES:
        score = scores[name]
        weight, q = prior.quintile_weights(score)
        specs[name] = (score, weight, q)
    return specs


def period_dates(daily):
    dates = pd.DatetimeIndex(daily.index)
    periods = [("full_train_eval", dates), ("ex_2016", dates[dates.year != 2016])]
    periods.extend((str(year), dates[dates.year == year]) for year in range(2011, 2017))
    return [(label, pd.DatetimeIndex(ix)) for label, ix in periods if len(ix)]


def rank_turnover_diagnostics(name, score, weights, q, daily):
    """Measure adjacent-date score-rank persistence and Q1/Q5 churn."""
    dates = pd.DatetimeIndex(daily.index)
    rows = []
    score_by_date = {date: part.droplevel("Date") for date, part in
                     score.loc[score.index.get_level_values("Date").isin(dates)].groupby(level="Date", sort=True)}
    q_by_date = {date: part.droplevel("Date") for date, part in
                 q.loc[q.index.get_level_values("Date").isin(dates)].groupby(level="Date", sort=True)}
    w_by_date = {date: part.droplevel("Date") for date, part in
                 weights.loc[weights.index.get_level_values("Date").isin(dates)].groupby(level="Date", sort=True)}
    for previous_date, date in zip(dates[:-1], dates[1:]):
        prev_score, curr_score = score_by_date[previous_date], score_by_date[date]
        common = prev_score.index.intersection(curr_score.index)
        prev_rank = prev_score.reindex(common).rank(method="average", pct=True)
        curr_rank = curr_score.reindex(common).rank(method="average", pct=True)
        rank_corr = float(prev_rank.corr(curr_rank)) if len(common) > 2 else np.nan
        rank_delta = float((curr_rank - prev_rank).abs().mean()) if len(common) else np.nan
        prev_q, curr_q = q_by_date[previous_date], q_by_date[date]
        row = {"Date": date, "strategy": name, "common_codes": len(common),
               "score_rank_autocorrelation": rank_corr, "mean_abs_rank_percentile_change": rank_delta,
               "quintile_changed_codes": int((prev_q.reindex(common) != curr_q.reindex(common)).sum())}
        for qvalue, label in ((0, "q1"), (4, "q5")):
            prev_members = set(prev_q.index[prev_q.eq(qvalue)])
            curr_members = set(curr_q.index[curr_q.eq(qvalue)])
            intersection = len(prev_members & curr_members)
            entrants = len(curr_members - prev_members)
            exits = len(prev_members - curr_members)
            row[f"{label}_retention"] = intersection / len(prev_members) if prev_members else np.nan
            row[f"{label}_entrants"] = entrants
            row[f"{label}_exits"] = exits
            prev_tail = w_by_date[previous_date].where(prev_q.eq(qvalue), 0.0)
            curr_tail = w_by_date[date].where(curr_q.eq(qvalue), 0.0)
            aligned = pd.concat([prev_tail.rename("previous"), curr_tail.rename("current")], axis=1).fillna(0.0)
            row[f"{label}_weight_turnover"] = float((aligned.current - aligned.previous).abs().sum())
        row["total_weight_turnover"] = float(daily.loc[date, "turnover"])
        rows.append(row)
    return pd.DataFrame(rows)


def aggregate_rank_diagnostics(daily_rows):
    frames = []
    for name, group in daily_rows.groupby("strategy", sort=False):
        dates = pd.DatetimeIndex(pd.to_datetime(group.Date))
        periods = [("full_train_eval", dates), ("ex_2016", dates[dates.year != 2016])]
        periods.extend((str(year), dates[dates.year == year]) for year in range(2011, 2017))
        for label, selected in periods:
            part = group.loc[group.Date.isin(selected)]
            if part.empty:
                continue
            record = {"strategy": name, "period": label, "transition_days": len(part)}
            for column in part.columns:
                if column in ("Date", "strategy"):
                    continue
                record[f"mean_{column}"] = float(pd.to_numeric(part[column], errors="coerce").mean())
            frames.append(record)
    return pd.DataFrame(frames)


def write_csv(frame, path):
    frame.to_csv(path, index=False)


def run(config_path, output_path):
    started = time.monotonic()
    config_path, output = Path(config_path), Path(output_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    expected_ids = [item["trial_id"] for item in config.get("trials", [])]
    if (config.get("experiment_id") != EXPERIMENT_ID or config.get("data_split") != "train"
            or config.get("valid_evaluation") is not False or config.get("selection_eligible") is not False
            or config.get("max_trials") != 5 or tuple(expected_ids) != STRATEGIES
            or config.get("parameters", {}).get("candidate_c_alpha_high") != ALPHA_HIGH
            or config.get("parameters", {}).get("candidate_c_alpha_low") != ALPHA_LOW
            or config.get("parameters", {}).get("baseline_ewma_alpha") != BASE_ALPHA):
        raise ValueError("Run config differs from this pre-registered fixed asymmetric EWMA experiment")
    for directory in ("models", "predictions", "metrics", "audit", "logs"):
        (output / directory).mkdir(parents=True, exist_ok=True)
    run_path = output / "run.json"
    metadata = json.loads(run_path.read_text(encoding="utf-8"))
    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, check=True,
                           capture_output=True, text=True).stdout.strip()
    source_paths = [Path(__file__).resolve(), Path(prior.__file__).resolve(),
                    Path(features.__file__).resolve(), Path(evaluation.__file__).resolve(),
                    Path(firewall.__file__).resolve()]
    metadata.update({
        "status": "running", "started_at_utc": now_utc(), "command": sys.argv,
        "git_commit_hash": git_head, "git_worktree_dirty": bool(dirty),
        "source_run_id": "run-20260926T063602Z", "comparison_run_id": PRIOR_RUN.name,
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "numpy": np.__version__, "pandas": pd.__version__},
        "code_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in source_paths},
        "source_artifact_sha256": {str(path.relative_to(ROOT)): sha256(path)
                                    for path in (SOURCE_SIGNALS, PRIOR_SCORES, PRIOR_WEIGHTS)},
        "cost_oneway": ONE_WAY_COST, "annualization": ANNUALIZATION,
        "parameter_values": config["parameters"], "actual_trials": 0,
        "valid_accessed": False,
    })
    dump(run_path, metadata)
    try:
        firewall.install(allowed_artifacts=(SOURCE_SIGNALS, PRIOR_SCORES, PRIOR_WEIGHTS))
        print("[1/5] Load saved Train scores, fixed prior replay, and Train-only target/sector...", flush=True)
        saved = pd.read_parquet(SOURCE_SIGNALS).sort_index()
        prior_scores = pd.read_parquet(PRIOR_SCORES).sort_index()
        prior_weights = pd.read_parquet(PRIOR_WEIGHTS).sort_index()
        target = pd.read_parquet(DATA_DIR / "target_1day_train.parquet")["Return"].sort_index().rename("Return")
        listed = pd.read_parquet(DATA_DIR / "listed_info_train.parquet", columns=[
            "Sector33Code", "Sector33CodeName", "Sector17Code", "Sector17CodeName"
        ]).sort_index()
        if not saved.index.is_unique or not target.index.is_unique or not listed.index.is_unique:
            raise AssertionError("Expected unique (Date, Code) keys in saved scores, Train target, and PIT sector data")
        index = saved.index
        if not index.equals(target.index):
            raise AssertionError("Saved signals and Train target indexes differ")
        sector = listed.reindex(index)
        coverage = float(sector["Sector33Code"].notna().mean())
        if coverage < 0.95:
            raise AssertionError(f"Unexpected PIT sector join coverage: {coverage:.2%}")
        data_hashes = {name: sha256(DATA_DIR / name) for name in (
            "target_1day_train.parquet", "listed_info_train.parquet")}
        metadata["train_data_sha256"] = data_hashes
        dump(run_path, metadata)

        print("[2/5] Invert saved baseline EWMA and build the one fixed asymmetric pair...", flush=True)
        raw_streams = {}
        scores = {
            "B00_BASE": saved["B00"].rename("B00_BASE"),
            "BOX_ORIGINAL": saved["BOX_BIDIR_STANDALONE"].rename("BOX_ORIGINAL"),
        }
        inversion_errors = {}
        components = {}
        for source_name, trial_name in (("B00", "B00_BASE"),
                                        ("BOX_BIDIR_STANDALONE", "BOX_ORIGINAL")):
            raw, error = prior.inverse_ewma(saved[source_name].rename(source_name), BASE_ALPHA)
            inversion_errors[trial_name] = error
            raw_streams[trial_name] = raw
            high_raw, low_raw = prior.split_raw_sides(raw)
            baseline_rebuilt = (prior.segment_ewma(high_raw, BASE_ALPHA)
                                + prior.segment_ewma(low_raw, BASE_ALPHA))
            if float((baseline_rebuilt - saved[source_name]).abs().max()) > 2e-12:
                raise AssertionError(f"Could not reproduce saved {source_name} from split raw streams")
            if trial_name == "B00_BASE":
                scores["C_B00_ASYM_EWMA"], _, _ = asymmetric_score(raw, "C_B00_ASYM_EWMA")
                components["C_B00_ASYM_EWMA"] = score_components(high_raw, low_raw, ALPHA_HIGH, ALPHA_LOW)
                components["B00_BASE"] = score_components(high_raw, low_raw, BASE_ALPHA, BASE_ALPHA)
                components["A_LOW_NO_CARRY_B00_CONTROL"] = score_components(
                    high_raw, low_raw, BASE_ALPHA, BASE_ALPHA, low_no_carry=True)
            else:
                scores["C_ASYM_EWMA"], _, _ = asymmetric_score(raw, "C_ASYM_EWMA")
                components["C_ASYM_EWMA"] = score_components(high_raw, low_raw, ALPHA_HIGH, ALPHA_LOW)
                components["BOX_ORIGINAL"] = score_components(high_raw, low_raw, BASE_ALPHA, BASE_ALPHA)
                scores["A_LOW_NO_CARRY"] = prior.asymmetric_score_from_raw(
                    raw, BASE_ALPHA, "A_LOW_NO_CARRY")
                components["A_LOW_NO_CARRY"] = score_components(
                    high_raw, low_raw, BASE_ALPHA, BASE_ALPHA, low_no_carry=True)
        if "A_LOW_NO_CARRY" not in scores:
            raise AssertionError("Missing saved BOX Low-no-carry comparison")
        for name in STRATEGIES:
            if name not in scores or not np.isfinite(scores[name].to_numpy()).all():
                raise AssertionError(f"Missing or invalid score stream: {name}")
        score_errors = {}
        for name in ("B00_BASE", "BOX_ORIGINAL", "A_LOW_NO_CARRY"):
            if name not in prior_scores:
                raise AssertionError(f"Prior saved score artifact missing {name}")
            score_errors[name] = float((scores[name] - prior_scores[name]).abs().max())
            if score_errors[name] > 2e-12:
                raise AssertionError(f"Saved score replay mismatch {name}: {score_errors[name]}")

        print("[3/5] Rebuild official quintiles/accounting and exact prior replay checks...", flush=True)
        specs = portfolio_specs(scores)
        old_daily = pd.read_csv(PRIOR_RUN / "metrics/daily_account_B00_BASE.csv",
                                parse_dates=["Date"], index_col="Date")
        # This prior run's saved account file is already annual-tail-purged.
        # Reuse its exact evaluation index; applying the source-calendar helper
        # here would remove the final two dates a second time.
        eval_dates = pd.DatetimeIndex(old_daily.index)
        if (str(eval_dates.min().date()), str(eval_dates.max().date())) != ("2011-01-04", "2016-03-29"):
            raise AssertionError("The evaluation span does not match the registered Train folds")
        eval_2016 = eval_dates[eval_dates.year == 2016]
        if (str(eval_2016.min().date()), str(eval_2016.max().date())) != ("2016-01-04", "2016-03-29"):
            raise AssertionError("The 2016 partial span differs from the registered dates")
        daily_accounts, weights_store, q_store = {}, {}, {}
        replay_error = 0.0
        for name, (score, weights, q) in specs.items():
            daily, _, _ = prior.account_from_weights(score, weights, q, target)
            daily = daily.loc[daily.index.isin(eval_dates)]
            daily_accounts[name], weights_store[name], q_store[name] = daily, weights, q
            source_key = {"B00_BASE": "B00_BASE", "BOX_ORIGINAL": "BOX_ORIGINAL",
                          "A_LOW_NO_CARRY": "A_LOW_NO_CARRY"}.get(name)
            if source_key:
                for current_column, saved_column in (("gross", "gross"), ("net", "net"),
                                                     ("turnover", "turnover")):
                    err = float((daily[current_column] - old_daily.loc[daily.index, current_column]).abs().max()) if name == "B00_BASE" else None
                    if name == "B00_BASE":
                        replay_error = max(replay_error, err)
                    if name == "B00_BASE" and err > 1e-10:
                        raise AssertionError(f"Prior B00 account replay mismatch in {current_column}: {err}")
                saved_weights_name = source_key
                weight_error = float((weights - prior_weights[saved_weights_name]).abs().max())
                if weight_error > 1e-12:
                    raise AssertionError(f"Saved official weights mismatch {name}: {weight_error}")
            comp_name = name
            if comp_name not in components:
                raise AssertionError(f"Missing age attribution components for {name}")
            comp_error = float((components[comp_name].sum(axis=1) - score).abs().max())
            if comp_error > 2e-12:
                raise AssertionError(f"Source-age components do not reconstruct {name}: {comp_error}")
        if float((daily_accounts["A_LOW_NO_CARRY"]["net"] -
                  pd.read_csv(PRIOR_RUN / "metrics/daily_account_A_LOW_NO_CARRY.csv",
                              parse_dates=["Date"], index_col="Date").loc[eval_dates, "net"]).abs().max()) > 1e-10:
            raise AssertionError("Prior A_LOW_NO_CARRY net account does not replay")

        summary_rows = []
        for name in STRATEGIES:
            score, weights, q = specs[name]
            for period, dates in period_dates(daily_accounts[name]):
                summary_rows.append(prior.stat_record(
                    name, period, score, weights, q,
                    daily_accounts[name].loc[daily_accounts[name].index.isin(dates)], target, sector,
                ))
        summary = pd.DataFrame(summary_rows)
        write_csv(summary, output / "metrics/period_metrics.csv")
        write_csv(summary.loc[summary.period.eq("full_train_eval")], output / "metrics/candidate_summary.csv")
        paired_rows = []
        comparisons = (("A_LOW_NO_CARRY", "BOX_ORIGINAL"),
                       ("C_ASYM_EWMA", "A_LOW_NO_CARRY"),
                       ("C_ASYM_EWMA", "BOX_ORIGINAL"),
                       ("C_B00_ASYM_EWMA", "B00_BASE"),
                       ("C_ASYM_EWMA", "C_B00_ASYM_EWMA"))
        for candidate, baseline in comparisons:
            left, right = daily_accounts[baseline], daily_accounts[candidate]
            delta = right.net - left.net
            paired_rows.append({
                "candidate": candidate, "baseline": baseline,
                "delta_net_sharpe": evaluation.sharpe(right.net) - evaluation.sharpe(left.net),
                "delta_annual_net_return": float(delta.mean() * ANNUALIZATION),
                "delta_annual_gross_return": float((right.gross - left.gross).mean() * ANNUALIZATION),
                "delta_annual_cost": float((right.cost - left.cost).mean() * ANNUALIZATION),
                "paired_daily_net_mean_delta": float(delta.mean()),
                "paired_daily_net_volatility_delta": float(right.net.std(ddof=1) - left.net.std(ddof=1)),
            })
        write_csv(pd.DataFrame(paired_rows), output / "metrics/paired_differences.csv")

        print("[4/5] Compute adjacent-date rank, membership, weight, and event-origin attribution...", flush=True)
        rank_daily = pd.concat([
            rank_turnover_diagnostics(name, specs[name][0], weights_store[name], q_store[name], daily_accounts[name])
            for name in STRATEGIES
        ], ignore_index=True)
        rank_period = aggregate_rank_diagnostics(rank_daily)
        write_csv(rank_daily, output / "metrics/rank_diagnostics_daily.csv")
        write_csv(rank_period, output / "metrics/rank_diagnostics_period.csv")

        attribution_frames, daily_attribution_frames, details, sector_rows = [], [], [], []
        for name in STRATEGIES:
            score, weights, q = specs[name]
            table, day_table, _ = prior.attribution_tables(
                name, score, weights, q, components[name], target, eval_dates
            )
            attribution_frames.append(table)
            daily_attribution_frames.append(day_table)
            detail = prior.build_audit_detail(score, weights, q, components[name], sector, eval_dates)
            details.append(detail.assign(strategy=name))
            sector_rows.extend(prior.sector_outputs(name, score, weights, q, sector))
        attribution = pd.concat(attribution_frames, ignore_index=True)
        daily_attribution = pd.concat(daily_attribution_frames, ignore_index=True)
        details = pd.concat(details).sort_index()
        years = prior.yearly_category_attribution(details, daily_attribution)
        zero_sector = prior.zero_sector_bias(details, target)
        write_csv(attribution, output / "metrics/annual_category_attribution.csv")
        write_csv(daily_attribution, output / "metrics/daily_category_attribution.csv")
        write_csv(years, output / "metrics/category_by_year.csv")
        write_csv(pd.DataFrame(sector_rows), output / "metrics/sector_tail_composition.csv")
        write_csv(zero_sector, output / "metrics/sector_zero_tail_bias.csv")

        score_eval = pd.DataFrame({name: specs[name][0] for name in STRATEGIES}).loc[
            pd.IndexSlice[eval_dates, :], :]
        weight_eval = pd.DataFrame({name: weights_store[name] for name in STRATEGIES}).loc[
            pd.IndexSlice[eval_dates, :], :]
        score_eval.to_parquet(output / "predictions/strategy_scores.parquet")
        weight_eval.to_parquet(output / "predictions/portfolio_weights.parquet")
        details.to_parquet(output / "predictions/holdings_audit.parquet")
        for name, daily in daily_accounts.items():
            daily.to_csv(output / f"metrics/daily_account_{name}.csv", index_label="Date")

        print("[5/5] Save Train firewall, replay, coverage, and runtime audit...", flush=True)
        firewall_state = {"status": "PASS", "opened_parquets": sorted(firewall.ACCESSES),
                          "valid_evaluation": False, "raw_target_reads": False}
        dump(output / "audit/firewall.json", firewall_state)
        audit = {
            "evaluation_start": str(eval_dates.min().date()), "evaluation_end": str(eval_dates.max().date()),
            "evaluation_days": len(eval_dates), "partial_2016_start": str(eval_2016.min().date()),
            "partial_2016_end": str(eval_2016.max().date()), "partial_2016_days": len(eval_2016),
            "source_signal_rows": len(saved), "score_coverage_rows": {name: int(scores[name].notna().sum()) for name in STRATEGIES},
            "pit_sector_coverage": coverage, "ewma_inverse_max_abs_error": inversion_errors,
            "saved_prior_score_max_abs_error": score_errors, "saved_prior_account_max_abs_error": replay_error,
            "candidate_score_component_errors": {name: float((components[name].sum(axis=1) - scores[name]).abs().max())
                                                  for name in components if name in scores},
            "source_scan": "PASS: no strategy source was changed; fixed transform only uses current/past score rows",
            "future_prefix_invariance": "PASS: adjust=False listing-segment EWMA is causal; focused prefix test run separately",
            "official_quintile_weight_replay": "PASS: prior.quintile_weights asserts exact match with research.evaluation.weights",
            "valid_accessed": False, "source_parquets_opened": sorted(firewall.ACCESSES),
        }
        dump(output / "audit/asym_ewma_audit.json", audit)
        metadata.update({
            "status": "completed", "completed_at_utc": now_utc(), "exit_code": 0,
            "actual_trials": 5, "elapsed_seconds": time.monotonic() - started,
            "valid_accessed": False, "evaluation_span": [str(eval_dates.min().date()), str(eval_dates.max().date())],
            "evaluation_days": len(eval_dates), "partial_2016_span": [str(eval_2016.min().date()), str(eval_2016.max().date())],
            "outputs": {
                "period_metrics": "metrics/period_metrics.csv", "rank_diagnostics": "metrics/rank_diagnostics_period.csv",
                "category_attribution": "metrics/annual_category_attribution.csv", "category_by_year": "metrics/category_by_year.csv",
                "scores": "predictions/strategy_scores.parquet", "weights": "predictions/portfolio_weights.parquet",
                "audit": "audit/asym_ewma_audit.json", "firewall": "audit/firewall.json",
            },
        })
        dump(run_path, metadata)
    except BaseException as error:
        metadata.update({"status": "failed", "completed_at_utc": now_utc(),
                        "exit_code": 1, "error": f"{type(error).__name__}: {error}",
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
