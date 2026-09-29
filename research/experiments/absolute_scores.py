"""Train-only comparison of absolute B00 and channel-position scores."""
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
from research.evaluation import bootstrap_delta, daily_account
from research.experiments import channel_position_250 as base
from research.experiments.slope_range_volume_ml import (
    CUTOFFS, YEARS, dump, evaluation_dates, leg_account, metric_bundle, mutate_inputs,
)


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DM-20260924-08"
METHODS = ("H0", "B00", "B00_ABS", "CHANNEL_250_001", "CHANNEL_250_ABS")
CANDIDATES = ("B00_ABS", "CHANNEL_250_ABS")
SEED = 20260924
BOOTSTRAP_REPS = 1000
BOOTSTRAP_BLOCK = 20


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def make_signals(inputs, x):
    signed, _ = base.make_signals(inputs, x)
    signals = dict(signed)
    signals["B00_ABS"] = signed["B00"].abs().rename("B00_ABS")
    signals["CHANNEL_250_ABS"] = signed["CHANNEL_250_001"].abs().rename("CHANNEL_250_ABS")
    return signals


def source_scan():
    modules = (base.features, base.models, base.b00_features, base.b00_models)
    paths = []
    banned = (
        "AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose",
        "AdjustmentVolume", "raw_target", "target_1day_valid",
    )
    for module in modules:
        path = Path(module.__file__).resolve()
        source = path.read_text(encoding="utf-8")
        for token in banned:
            if token in source:
                raise AssertionError(f"Forbidden source token {token} in {path}")
        for node in ast.walk(ast.parse(source)):
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
        paths.append(str(path.relative_to(ROOT)))
    return paths


def audit_prefix(inputs, x):
    files = source_scan()
    dates = x.index.get_level_values("Date")
    records = []
    for label in CUTOFFS:
        cutoff = pd.Timestamp(label)
        prefix_index = x.index[dates <= cutoff]
        expected_x = x
        expected = make_signals(inputs, x)
        modes = {}
        for mode in ("mutation", "truncation"):
            changed_inputs = mutate_inputs(inputs, cutoff, truncate=(mode == "truncation"))
            changed_x = base.features.build_features(changed_inputs)
            actual = make_signals(changed_inputs, changed_x)
            pd.testing.assert_frame_equal(expected_x.loc[prefix_index], changed_x.loc[prefix_index], check_exact=True)
            for name in METHODS:
                pd.testing.assert_series_equal(expected[name].loc[prefix_index], actual[name].loc[prefix_index], check_exact=True)
            modes[mode] = "features and all signed/absolute scores bitwise exact"
        records.append({"cutoff": label, "prefix_rows": int(len(prefix_index)), "checks": modes})
    return {"status": "PASS", "source_files": files, "cutoffs": records}


def build_report(run_id, summaries, folds, audit, eval_span, eval_days):
    by_name = {item["strategy"]: item for item in summaries}
    lines = [
        f"# {EXPERIMENT_ID}: B00 / 52週位置スコアの絶対値化", "",
        f"- Run ID: {run_id}",
        "- Train only。Valid / Valid target / raw targetは未使用。全Trainは既知の記述評価。",
        f"- Evaluation: {eval_span[0]}〜{eval_span[1]} ({eval_days}日)。2016年は部分fold、各年境界と終端で2取引日をpurge。",
        "- 変換: 既存alpha=0.25 EWMA後のscoreにabsを適用。再平滑化なし。B00では高値/安値ブレイクをともに正値化、channelではレンジ上端/下端の両方を正値化。",
        "- Five-quantile weightと片道10bps costを共通使用。正の絶対スコア上位がLong、低い絶対スコア中央/ゼロ群がShortになり得る。",
        "", "## Pooled結果", "",
        "| Strategy | Gross SR | Net SR | ΔNet SR vs H0 | Annual Gross | Annual Net | Cost | Turnover/day | Long Net/SR | Short Net/SR | RankIC | Q mono | Max DD |",
        "|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    h0_sr = by_name["H0"]["pooled"]["net_sharpe"]
    for name in METHODS:
        p = by_name[name]["pooled"]
        legs = p["legs"]
        lines.append(
            f"| {name} | {p['gross_sharpe']:.4f} | {p['net_sharpe']:.4f} | {p['net_sharpe']-h0_sr:+.4f} | "
            f"{p['annual_gross']:+.2%} | {p['annual_net']:+.2%} | {p['annual_cost']:.2%} | {p['turnover']:.5f} | "
            f"{legs['long']['annual_net']:+.2%}/{legs['long']['net_sharpe']:.3f} | "
            f"{legs['short']['annual_net']:+.2%}/{legs['short']['net_sharpe']:.3f} | "
            f"{p['rankic']:+.4f} | {p['q_monotonicity']:+.2f} | {p['max_drawdown_additive']:+.2%} |"
        )
    lines += ["", "## 年別fold", "",
              "| Year | Strategy | Gross SR | Net SR | Δ vs signed source | Annual Net | Cost | Turnover | Long Net | Short Net | Max DD |",
              "|---:|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in folds:
        source = {"B00_ABS": "B00", "CHANNEL_250_ABS": "CHANNEL_250_001"}.get(row["strategy"], "H0")
        source_row = next(item for item in folds if item["strategy"] == source and item["year"] == row["year"])
        legs = row["legs"]
        lines.append(
            f"| {row['year']} | {row['strategy']} | {row['gross_sharpe']:.3f} | {row['net_sharpe']:.3f} | "
            f"{row['net_sharpe']-source_row['net_sharpe']:+.3f} | {row['annual_net']:+.2%} | {row['annual_cost']:.2%} | "
            f"{row['turnover']:.5f} | {legs['long']['annual_net']:+.2%} | {legs['short']['annual_net']:+.2%} | "
            f"{row['max_drawdown_additive']:+.2%} |"
        )
    lines += ["", "## Paired 20日 block bootstrap", "", "| Candidate | Baseline | Δ pooled Net SR | 95% CI | Positive fraction |", "|:---|:---|---:|:---|---:|"]
    for candidate in CANDIDATES:
        for baseline, comparison in by_name[candidate]["comparisons"].items():
            ci = comparison["bootstrap"]
            lines.append(f"| {candidate} | {baseline} | {comparison['delta_net_sharpe']:+.4f} | [{ci['low']:+.4f}, {ci['high']:+.4f}] | {ci['bootstrap_positive_fraction']:.3f} |")
    lines += ["", "## 監査と制約", "",
              f"- Source scan / Train firewall / feature and signed/absolute score prefix-invariance: **{audit['status']}**（3 cutoffs × mutation/truncation）。",
              "- Coverage、finite score、Long+Short会計一致: PASS。各methodの評価日とターゲットは同一。",
              "- 全期間は既知Train。結果は独立OOS・採用根拠ではなく、Validは未読。"]
    path = ROOT / "reports" / EXPERIMENT_ID / "REPORT.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run(config_path, output_path):
    started = time.monotonic()
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    expected_ids = ["B00_ABS", "CHANNEL_250_ABS"]
    if config.get("experiment_id") != EXPERIMENT_ID or config.get("data_split") != "train" or config.get("valid_evaluation") is not False:
        raise ValueError("Train-only experiment configuration required")
    if config.get("max_trials") != 2 or [trial["trial_id"] for trial in config["trials"]] != expected_ids:
        raise ValueError("Only the two preregistered absolute-score candidates are allowed")
    output = Path(output_path)
    for name in ("models", "predictions", "metrics", "audit"):
        (output / name).mkdir(parents=True, exist_ok=True)
    run_path = output / "run.json"
    metadata = json.loads(run_path.read_text(encoding="utf-8"))
    source_paths = [
        Path(__file__).resolve(), Path(base.__file__).resolve(),
        Path(dump.__globals__["__file__"]).resolve(),
        Path(base.features.__file__).resolve(), Path(base.models.__file__).resolve(),
        Path(base.b00_features.__file__).resolve(), Path(base.b00_models.__file__).resolve(),
    ]
    metadata.update({
        "status": "running", "started_at_utc": now_utc(), "command": sys.argv, "actual_trials": 0,
        "environment": {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__, "pandas": pd.__version__},
        "code_sha256": {str(path.relative_to(ROOT)): digest(path) for path in source_paths},
    })
    dump(run_path, metadata)
    try:
        firewall.install()
        data_dir = ROOT / "stock_comp_2026" / "input"
        data_hashes = {f"{name}_train.parquet": digest(data_dir / f"{name}_train.parquet") for name in base.features.INPUT_COLUMNS}
        data_hashes["target_1day_train.parquet"] = digest(data_dir / "target_1day_train.parquet")
        inputs = base.features.load_inputs(data_dir, split="train")
        target = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index()
        x = base.features.build_features(inputs)
        if not x.index.equals(target.index):
            raise AssertionError("Feature/target index mismatch")
        dates = x.index.get_level_values("Date")
        calendar = dates.unique().sort_values()
        if str(calendar.min().date()) != "2008-11-04" or str(calendar.max().date()) != "2016-03-31":
            raise AssertionError("Unexpected Train date span")

        print("[1/5] Prefix invariance audit...", flush=True)
        audit = audit_prefix(inputs, x)
        dump(output / "audit/causality.json", audit)
        firewall.save(output / "audit/firewall.json")

        print("[2/5] Generate fixed signed and absolute scores...", flush=True)
        signals = make_signals(inputs, x)
        if any(not signal.index.equals(target.index) for signal in signals.values()):
            raise AssertionError("Signal/target index mismatch")
        eval_dates = evaluation_dates(daily_account(signals["H0"], target).index)
        eval_set = set(eval_dates)
        required = dates.isin(eval_dates)
        coverage = {}
        for name, signal in signals.items():
            aligned = signal.reindex(target.index)
            values = aligned.to_numpy()[required]
            if not np.isfinite(values).all():
                raise AssertionError(f"Nonfinite evaluation score: {name}")
            signals[name] = aligned.rename(name)
            coverage[name] = int(len(values))
        pd.DataFrame(signals, index=target.index).sort_index().to_parquet(output / "predictions/signals.parquet")

        print("[3/5] Evaluate common-date portfolios...", flush=True)
        accounts, ledgers, summaries, folds = {}, {}, [], []
        for name in METHODS:
            account = daily_account(signals[name], target)
            legs = leg_account(signals[name], target)
            gap = (legs.net_sum.reindex(account.index) - account.net).abs().max()
            if not np.isfinite(gap) or gap > 1e-10:
                raise AssertionError(f"Long/Short reconciliation failed for {name}: {gap}")
            account.to_csv(output / f"metrics/daily_account_{name}.csv", index_label="Date")
            legs.to_csv(output / f"metrics/daily_legs_{name}.csv", index_label="Date")
            account = account.loc[account.index.isin(eval_set)]
            legs = legs.reindex(account.index)
            accounts[name], ledgers[name] = account, legs
            pooled = metric_bundle(account, legs)
            periods = []
            for year in YEARS:
                year_dates = [date for date in eval_dates if date.year == year]
                yearly_account = account.loc[account.index.isin(year_dates)]
                yearly_legs = legs.reindex(yearly_account.index)
                bundle = metric_bundle(yearly_account, yearly_legs)
                row = {"strategy": name, "year": year, **{key: val for key, val in bundle.items() if key != "legs"}, "legs": bundle["legs"]}
                folds.append(row)
                periods.append({"year": year, "metrics": bundle})
            summaries.append({"strategy": name, "pooled": pooled, "periods": periods})

        by_name = {item["strategy"]: item for item in summaries}
        comparison_map = {
            "B00_ABS": ("B00", "H0", "CHANNEL_250_ABS"),
            "CHANNEL_250_ABS": ("CHANNEL_250_001", "B00", "H0", "B00_ABS"),
        }
        for candidate, baselines in comparison_map.items():
            for baseline in baselines:
                delta_by_year = [
                    next(row["net_sharpe"] for row in folds if row["strategy"] == candidate and row["year"] == year)
                    - next(row["net_sharpe"] for row in folds if row["strategy"] == baseline and row["year"] == year)
                    for year in YEARS
                ]
                ci = bootstrap_delta(
                    accounts[baseline]["net"], accounts[candidate]["net"],
                    seed=SEED, reps=BOOTSTRAP_REPS, block=BOOTSTRAP_BLOCK,
                )
                by_name[candidate].setdefault("comparisons", {})[baseline] = {
                    "delta_net_sharpe": by_name[candidate]["pooled"]["net_sharpe"] - by_name[baseline]["pooled"]["net_sharpe"],
                    "fold_delta_net_sharpe": delta_by_year,
                    "improved_folds": int(sum(delta > 0 for delta in delta_by_year)),
                    "bootstrap": ci,
                }
        for row in folds:
            for baseline in ("H0", "B00"):
                base_row = next(item for item in folds if item["strategy"] == baseline and item["year"] == row["year"])
                row[f"delta_vs_{baseline}"] = row["net_sharpe"] - base_row["net_sharpe"]

        dump(output / "metrics/summary.json", summaries)
        fold_frame = pd.DataFrame([{key: val for key, val in row.items() if key != "legs"} for row in folds])
        fold_frame.to_csv(output / "metrics/fold_metrics.csv", index=False)
        report_dir = ROOT / "reports" / EXPERIMENT_ID
        report_dir.mkdir(parents=True, exist_ok=True)
        fold_frame.to_csv(report_dir / "fold_metrics.csv", index=False)
        comparison_rows = []
        for item in summaries:
            row = {"strategy": item["strategy"], **{key: val for key, val in item["pooled"].items() if key != "legs"}}
            for side in ("long", "short"):
                row[f"{side}_annual_net"] = item["pooled"]["legs"][side]["annual_net"]
                row[f"{side}_net_sharpe"] = item["pooled"]["legs"][side]["net_sharpe"]
            if item["strategy"] in CANDIDATES:
                for baseline, comparison in item["comparisons"].items():
                    row[f"delta_net_sharpe_vs_{baseline}"] = comparison["delta_net_sharpe"]
                    row[f"improved_folds_vs_{baseline}"] = comparison["improved_folds"]
                    row[f"bootstrap_low_vs_{baseline}"] = comparison["bootstrap"]["low"]
                    row[f"bootstrap_high_vs_{baseline}"] = comparison["bootstrap"]["high"]
            comparison_rows.append(row)
        pd.DataFrame(comparison_rows).to_csv(output / "metrics/model_comparison.csv", index=False)
        pd.DataFrame(comparison_rows).to_csv(report_dir / "model_comparison.csv", index=False)
        eval_span = (str(eval_dates.min().date()), str(eval_dates.max().date()))
        report = build_report(output.name, summaries, folds, audit, eval_span, len(eval_dates))
        firewall.save(output / "audit/firewall.json")
        access = json.loads((output / "audit/firewall.json").read_text(encoding="utf-8"))
        if any("_valid" in path or "raw_target" in path for path in access["opened_parquets"]):
            raise AssertionError("Firewall log includes prohibited data")
        metadata.update({
            "status": "completed", "completed_at_utc": now_utc(),
            "elapsed_seconds": time.monotonic() - started, "actual_trials": 2,
            "train_data_sha256": data_hashes, "valid_accessed": False,
            "source_scan": "PASS", "prefix_invariance": "PASS",
            "prediction_coverage": coverage, "account_reconciliation": "PASS",
            "evaluation_span": eval_span, "report": str(report.relative_to(ROOT)),
        })
        dump(run_path, metadata)
        print(f"[Done] {report}", flush=True)
    except BaseException as error:
        metadata.update({"status": "failed", "completed_at_utc": now_utc(), "failure": repr(error), "elapsed_seconds": time.monotonic() - started})
        try:
            firewall.save(output / "audit/firewall.json")
        except BaseException:
            pass
        dump(run_path, metadata)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.config, args.output)
