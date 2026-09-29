"""Single-score Train-only test of the audited 250-observation channel position."""
import argparse
import ast
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from research import firewall
from research.evaluation import bootstrap_delta, daily_account, metrics
from research.experiments.slope_range_volume_ml import (
    BASELINE_NAMES, CUTOFFS, YEARS, dump, evaluation_dates, leg_account,
    metric_bundle, mutate_inputs,
)
from stock_comp_2026.strategies.dm_breakout_base_momentum_overlay import features as b00_features
from stock_comp_2026.strategies.dm_breakout_base_momentum_overlay import models as b00_models
from stock_comp_2026.strategies.dm_slope_range_volume_ml import features, models


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DM-20260924-07"
METHODS = ("H0", "B00", "CHANNEL_250_001")
SEED = 20260924
BOOTSTRAP_REPS = 1000
BOOTSTRAP_BLOCK = 20


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def clean(value):
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, pd.Period)):
        return str(value)
    return value


def save_json(path, value):
    Path(path).write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_scan():
    paths = [Path(features.__file__), Path(models.__file__)]
    banned = ("AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose", "AdjustmentVolume", "raw_target", "target_1day_valid")
    for path in paths:
        source = path.read_text(encoding="utf-8")
        scan_source = source
        for token in banned:
            if token in scan_source:
                raise AssertionError(f"Forbidden source token {token} in {path}")
        for node in ast.walk(ast.parse(scan_source)):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr in ("bfill", "backfill"):
                raise AssertionError(f"Backfill call in {path}")
            if any(k.arg == "center" and isinstance(k.value, ast.Constant) and k.value.value for k in node.keywords):
                raise AssertionError(f"Centered rolling call in {path}")
            if node.func.attr == "shift":
                periods = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg in ("periods", "period")), None)
                if isinstance(periods, ast.UnaryOp) and isinstance(periods.op, ast.USub):
                    raise AssertionError(f"Negative shift in {path}")
    return [str(path.relative_to(ROOT)) for path in paths]


def make_signals(inputs, features_frame):
    breakout = b00_features.build_features(inputs)
    h0 = models.smooth_by_listing(breakout["res60s1"].rename("H0"), alpha=0.25)
    b00 = b00_models.generate_signal(breakout, "B00", alpha=0.25)
    score = features_frame["channel_position_250"].fillna(0.0).rename("CHANNEL_250_001")
    channel = models.smooth_by_listing(score, alpha=0.25)
    return {"H0": h0, "B00": b00, "CHANNEL_250_001": channel}, breakout


def audit_prefix(inputs, x):
    source_files = source_scan()
    dates = x.index.get_level_values("Date")
    records = []
    for label in CUTOFFS:
        cutoff = pd.Timestamp(label)
        prefix = dates <= cutoff
        prefix_index = x.index[prefix]
        expected, _ = make_signals(inputs, x)
        modes = {}
        for mode in ("mutation", "truncation"):
            changed_inputs = mutate_inputs(inputs, cutoff, truncate=(mode == "truncation"))
            changed_x = features.build_features(changed_inputs)
            actual, _ = make_signals(changed_inputs, changed_x)
            pd.testing.assert_frame_equal(x.loc[prefix_index], changed_x.loc[prefix_index], check_exact=True)
            for name in METHODS:
                pd.testing.assert_series_equal(
                    expected[name].loc[prefix_index], actual[name].loc[prefix_index], check_exact=True
                )
            modes[mode] = "feature and H0/B00/channel signals bitwise exact"
        records.append({"cutoff": label, "prefix_rows": int(prefix.sum()), "checks": modes})
    return {"status": "PASS", "source_files": source_files, "cutoffs": records}


def make_report(run_id, summaries, folds, audit, eval_span):
    report_dir = ROOT / "reports" / EXPERIMENT_ID
    report_dir.mkdir(parents=True, exist_ok=True)
    lookup = {item["strategy"]: item for item in summaries}
    h0_sr, b00_sr = lookup["H0"]["pooled"]["net_sharpe"], lookup["B00"]["pooled"]["net_sharpe"]
    lines = [
        f"# {EXPERIMENT_ID}: 52週レンジ位置単独スコア", "",
        f"- Run ID: {run_id}",
        "- Train only。Valid / Valid target / raw targetは未使用。全Trainは既読の記述評価。",
        f"- Evaluation: {eval_span[0]}〜{eval_span[1]}。2016年は1〜3月の部分fold。各年境界と全体終端で2取引日をpurge。",
        "- Candidate: 前営業日終値を、前営業日を除いたprior-only 250観測High/Lowへ線形写像。高値=+1、安値=-1。範囲外はclipしない。履歴不足は0。EWMA alpha=0.25。",
        "- H0 / B00も同日比較し、公式五分位weight・片道10bps costを使用。",
        "",
        "## Pooled結果", "",
        "| Strategy | Gross SR | Net SR | ΔNet SR vs H0 | ΔNet SR vs B00 | Annual Gross | Annual Net | Annual Cost | Turnover/day | Long Net/SR | Short Net/SR | RankIC | HAC t | Hit | Q mono | Max DD |",
        "|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in METHODS:
        p = lookup[name]["pooled"]
        long, short = p["legs"]["long"], p["legs"]["short"]
        lines.append(
            f"| {name} | {p['gross_sharpe']:.4f} | {p['net_sharpe']:.4f} | "
            f"{p['net_sharpe']-h0_sr:+.4f} | {p['net_sharpe']-b00_sr:+.4f} | "
            f"{p['annual_gross']:+.2%} | {p['annual_net']:+.2%} | {p['annual_cost']:.2%} | "
            f"{p['turnover']:.5f} | {long['annual_net']:+.2%}/{long['net_sharpe']:.3f} | "
            f"{short['annual_net']:+.2%}/{short['net_sharpe']:.3f} | {p['rankic']:+.4f} | "
            f"{p['rankic_t_hac5']:+.3f} | {p['rankic_hit']:.3f} | {p['q_monotonicity']:+.3f} | "
            f"{p['max_drawdown_additive']:+.2%} |"
        )
    lines += ["", "## 年別fold", "",
              "| Year | Strategy | Gross SR | Net SR | Δ vs H0 | Δ vs B00 | Annual Net | Cost | Turnover | RankIC | Q mono | Long Net | Short Net | Max DD |",
              "|---:|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in folds:
        legs = row["legs"]
        lines.append(
            f"| {row['year']} | {row['strategy']} | {row['gross_sharpe']:.3f} | {row['net_sharpe']:.3f} | "
            f"{row['delta_vs_H0']:+.3f} | {row['delta_vs_B00']:+.3f} | {row['annual_net']:+.2%} | "
            f"{row['annual_cost']:.2%} | {row['turnover']:.5f} | {row['rankic']:+.4f} | "
            f"{row['q_monotonicity']:+.2f} | {legs['long']['annual_net']:+.2%} | "
            f"{legs['short']['annual_net']:+.2%} | {row['max_drawdown_additive']:+.2%} |"
        )
    candidate = lookup["CHANNEL_250_001"]
    lines += ["", "## Paired 20日 block bootstrap", "", "| Baseline | Δ pooled Net SR | 95% CI | Positive fraction |", "|:---|---:|:---|---:|"]
    for baseline, comp in candidate["comparisons"].items():
        ci = comp["bootstrap"]
        lines.append(f"| {baseline} | {comp['delta_net_sharpe']:+.4f} | [{ci['low']:+.4f}, {ci['high']:+.4f}] | {ci['bootstrap_positive_fraction']:.3f} |")
    lines += ["", "## 監査と制約", "",
              f"- Source scan / Train firewall / feature and signal prefix-invariance: **{audit['status']}**.",
              "- 3 cutoffで将来のOHLCV・AdjustmentFactor・baseline入力をmutation/truncationし、特徴量と全候補・baseline score prefixをbitwise照合。",
              "- Prediction coverage、finite score、Long+Short会計一致はPASS。既知Trainデータを使うため独立OOS・採用根拠ではない。Validは未読。"]
    path = report_dir / "REPORT.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run(config_path, output_path):
    started = time.monotonic()
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID or config.get("data_split") != "train" or config.get("valid_evaluation") is not False:
        raise ValueError("Train-only experiment configuration required")
    if config.get("max_trials") != 1 or [x["trial_id"] for x in config["trials"]] != ["CHANNEL_250_001"]:
        raise ValueError("Only the registered candidate is allowed")
    output = Path(output_path)
    for name in ("models", "predictions", "metrics", "audit"):
        (output / name).mkdir(parents=True, exist_ok=True)
    run_path = output / "run.json"
    metadata = json.loads(run_path.read_text(encoding="utf-8"))
    source_paths = [Path(__file__).resolve(), Path(dump.__globals__["__file__"]).resolve(), Path(features.__file__).resolve(), Path(models.__file__).resolve(),
                    Path(b00_features.__file__).resolve(), Path(b00_models.__file__).resolve()]
    metadata.update({
        "status": "running", "started_at_utc": now_utc(), "command": sys.argv, "actual_trials": 0,
        "environment": {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__, "pandas": pd.__version__},
        "code_sha256": {str(path.relative_to(ROOT)): digest(path) for path in source_paths},
    })
    save_json(run_path, metadata)
    try:
        firewall.install()
        data_dir = ROOT / "stock_comp_2026" / "input"
        data_hashes = {f"{name}_train.parquet": digest(data_dir / f"{name}_train.parquet") for name in features.INPUT_COLUMNS}
        data_hashes["target_1day_train.parquet"] = digest(data_dir / "target_1day_train.parquet")
        inputs = features.load_inputs(data_dir, split="train")
        target = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index()
        x = features.build_features(inputs)
        if not x.index.equals(target.index):
            raise AssertionError("Feature/target index mismatch")
        dates = x.index.get_level_values("Date")
        calendar = dates.unique().sort_values()
        print("[1/5] Prefix invariance audit...", flush=True)
        audit = audit_prefix(inputs, x)
        save_json(output / "audit/causality.json", audit)
        firewall.save(output / "audit/firewall.json")

        print("[2/5] Generate fixed signals...", flush=True)
        signals, breakout = make_signals(inputs, x)
        if not signals["CHANNEL_250_001"].index.equals(target.index):
            raise AssertionError("Candidate signal index mismatch")
        seed = daily_account(signals["H0"], target)
        eval_dates = evaluation_dates(seed.index)
        required = dates.isin(eval_dates)
        coverage = {}
        for name, signal in signals.items():
            signal = signal.reindex(target.index)
            signals[name] = signal
            values = signal.to_numpy()[required]
            if not np.isfinite(values).all():
                raise AssertionError(f"Nonfinite evaluation scores: {name}")
            coverage[name] = int(len(values))
        pd.DataFrame(signals, index=target.index).sort_index().to_parquet(output / "predictions/signals.parquet")

        print("[3/5] Evaluate same-date portfolios...", flush=True)
        eval_set = set(eval_dates)
        accounts, ledgers, summaries, folds = {}, {}, [], []
        for name in METHODS:
            all_account = daily_account(signals[name], target)
            all_legs = leg_account(signals[name], target)
            gap = (all_legs.net_sum.reindex(all_account.index) - all_account.net).abs().max()
            if not np.isfinite(gap) or gap > 1e-10:
                raise AssertionError(f"Account reconciliation failed for {name}: {gap}")
            all_account.to_csv(output / f"metrics/daily_account_{name}.csv", index_label="Date")
            all_legs.to_csv(output / f"metrics/daily_legs_{name}.csv", index_label="Date")
            account = all_account.loc[all_account.index.isin(eval_set)]
            legs = all_legs.reindex(account.index)
            accounts[name], ledgers[name] = account, legs
            pooled = metric_bundle(account, legs)
            periods = []
            for year in YEARS:
                year_dates = [date for date in eval_dates if date.year == year]
                yaccount = account.loc[account.index.isin(year_dates)]
                ylegs = legs.reindex(yaccount.index)
                bundle = metric_bundle(yaccount, ylegs)
                row = {"strategy": name, "year": year, **{k: v for k, v in bundle.items() if k != "legs"}, "legs": bundle["legs"]}
                folds.append(row)
                periods.append({"year": year, "metrics": bundle})
            summaries.append({"strategy": name, "pooled": pooled, "periods": periods})
        summary_by = {item["strategy"]: item for item in summaries}
        candidate = summary_by["CHANNEL_250_001"]
        comparisons = {}
        for baseline in BASELINE_NAMES:
            deltas = []
            for year in YEARS:
                cand = next(row for row in folds if row["strategy"] == "CHANNEL_250_001" and row["year"] == year)
                base = next(row for row in folds if row["strategy"] == baseline and row["year"] == year)
                deltas.append(cand["net_sharpe"] - base["net_sharpe"])
            comparisons[baseline] = {
                "delta_net_sharpe": candidate["pooled"]["net_sharpe"] - summary_by[baseline]["pooled"]["net_sharpe"],
                "fold_delta_net_sharpe": deltas,
                "improved_folds": int(sum(value > 0 for value in deltas)),
                "bootstrap": bootstrap_delta(
                    accounts[baseline]["net"], accounts["CHANNEL_250_001"]["net"],
                    seed=SEED, reps=BOOTSTRAP_REPS, block=BOOTSTRAP_BLOCK,
                ),
            }
        candidate["comparisons"] = comparisons
        for row in folds:
            row["delta_vs_H0"] = row["net_sharpe"] - next(x["net_sharpe"] for x in folds if x["strategy"] == "H0" and x["year"] == row["year"])
            row["delta_vs_B00"] = row["net_sharpe"] - next(x["net_sharpe"] for x in folds if x["strategy"] == "B00" and x["year"] == row["year"])
        save_json(output / "metrics/summary.json", summaries)
        save_json(output / "audit/coverage.json", {"coverage": coverage, "evaluation_days": len(eval_dates), "account_reconciliation": "PASS"})
        fold_frame = pd.DataFrame([{k: v for k, v in row.items() if k != "legs"} for row in folds])
        fold_frame.to_csv(output / "metrics/fold_metrics.csv", index=False)
        report_dir = ROOT / "reports" / EXPERIMENT_ID
        report_dir.mkdir(parents=True, exist_ok=True)
        fold_frame.to_csv(report_dir / "fold_metrics.csv", index=False)
        comparison_rows = []
        for item in summaries:
            row = {"strategy": item["strategy"], **{k: v for k, v in item["pooled"].items() if k != "legs"}}
            for side in ("long", "short"):
                row[f"{side}_annual_net"] = item["pooled"]["legs"][side]["annual_net"]
                row[f"{side}_net_sharpe"] = item["pooled"]["legs"][side]["net_sharpe"]
            if item["strategy"] == "CHANNEL_250_001":
                for baseline, comp in item["comparisons"].items():
                    row[f"delta_net_sharpe_vs_{baseline}"] = comp["delta_net_sharpe"]
                    row[f"improved_folds_vs_{baseline}"] = comp["improved_folds"]
                    row[f"bootstrap_low_vs_{baseline}"] = comp["bootstrap"]["low"]
                    row[f"bootstrap_high_vs_{baseline}"] = comp["bootstrap"]["high"]
            comparison_rows.append(row)
        pd.DataFrame(comparison_rows).to_csv(report_dir / "model_comparison.csv", index=False)
        eval_span = (str(eval_dates.min().date()), str(eval_dates.max().date()))
        report = make_report(output.name, summaries, folds, audit, eval_span)
        firewall.save(output / "audit/firewall.json")
        access = json.loads((output / "audit/firewall.json").read_text(encoding="utf-8"))
        if any("_valid" in path or "raw_target" in path for path in access["opened_parquets"]):
            raise AssertionError("Firewall log includes prohibited data")
        completed = now_utc()
        metadata.update({
            "status": "completed", "completed_at_utc": completed,
            "elapsed_seconds": time.monotonic() - started, "actual_trials": 1,
            "train_data_sha256": data_hashes, "valid_accessed": False,
            "source_scan": "PASS", "prefix_invariance": "PASS",
            "prediction_coverage": coverage, "account_reconciliation": "PASS",
            "evaluation_span": eval_span, "report": str(report.relative_to(ROOT)),
        })
        save_json(run_path, metadata)
        print(f"[Done] {report}", flush=True)
    except BaseException as error:
        metadata.update({"status": "failed", "completed_at_utc": now_utc(), "failure": repr(error), "elapsed_seconds": time.monotonic()-started})
        try:
            firewall.save(output / "audit/firewall.json")
        except BaseException:
            pass
        save_json(run_path, metadata)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.config, args.output)
