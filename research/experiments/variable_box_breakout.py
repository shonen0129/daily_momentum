"""Train-only, single-candidate variable box breakout experiment."""
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
from research import evaluation
from research.evaluation import bootstrap_delta, daily_account
from research.experiments.slope_range_volume_ml import (
    BASELINE_NAMES, CUTOFFS, dump, leg_account, metric_bundle,
)
from stock_comp_2026.strategies.dm_variable_box_breakout import features, models, submission as adapter


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DM-20260924-10"
METHODS = ("H0", "B00", models.TRIAL_ID)
SEED = 20260924
BOOTSTRAP_REPS = 1000
BOOTSTRAP_BLOCK = 20
ONE_WAY_COST = 0.001


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_scan():
    paths = [Path(features.__file__), Path(models.__file__), Path(adapter.__file__)]
    banned = (
        "AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose",
        "AdjustmentVolume", "raw_target", "target_1day_valid",
    )
    for path in paths:
        source = path.read_text(encoding="utf-8")
        for token in banned:
            if token in source:
                raise AssertionError(f"Forbidden source token {token} in {path}")
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr in ("bfill", "backfill"):
                raise AssertionError(f"Backfill call in {path}")
            if any(key.arg == "center" and isinstance(key.value, ast.Constant) and key.value.value
                   for key in node.keywords):
                raise AssertionError(f"Centered rolling call in {path}")
            if node.func.attr == "shift":
                periods = node.args[0] if node.args else next(
                    (key.value for key in node.keywords if key.arg in ("periods", "period")), None
                )
                if isinstance(periods, ast.UnaryOp) and isinstance(periods.op, ast.USub):
                    raise AssertionError(f"Negative shift in {path}")
    return [str(path.relative_to(ROOT)) for path in paths]


def mutate_inputs(inputs, cutoff, truncate=False):
    changed = {}
    cutoff = pd.Timestamp(cutoff)
    for name, frame in inputs.items():
        dates = frame.index.get_level_values("Date")
        if dates.tz is not None:
            dates = dates.tz_localize(None)
        future = dates > cutoff
        if truncate:
            changed[name] = frame.loc[~future].copy()
            continue
        values = frame.copy()
        for column in values:
            if isinstance(values[column].dtype, pd.CategoricalDtype):
                values[column] = values[column].astype(str)
            if pd.api.types.is_numeric_dtype(values[column]):
                if name == "prices_daily_quotes" and column == "AdjustmentFactor":
                    values.loc[future, column] = 1.0
                    if future.any():
                        first = dates[future].min()
                        values.loc[future & (dates == first), column] = 0.25
                else:
                    values.loc[future, column] = values.loc[future, column] * -3.14 + 888.0
            elif pd.api.types.is_datetime64_any_dtype(values[column]):
                values.loc[future, column] = pd.Timestamp("1990-01-01")
            else:
                values.loc[future, column] = "future_mutation"
        changed[name] = values
    return changed


def mutate_target(target, cutoff, truncate=False):
    cutoff = pd.Timestamp(cutoff)
    dates = target.index.get_level_values("Date")
    future = dates > cutoff
    if truncate:
        return target.loc[~future].copy()
    changed = target.copy()
    changed.loc[future] = changed.loc[future] * -3.14 + 888.0
    return changed


def evaluation_dates(account_index):
    dates = pd.DatetimeIndex(account_index)
    selected = []
    for year in models.YEARS:
        year_dates = dates[dates.year == year].unique().sort_values()
        if len(year_dates) <= 2:
            raise AssertionError(f"Insufficient evaluation dates for {year}")
        selected.extend(year_dates[:-2].tolist())
    return pd.DatetimeIndex(selected).sort_values()


def candidate_predictions_through(x, target, cutoff):
    """Refit only annual models needed to reproduce the prefix through cutoff."""
    cutoff = pd.Timestamp(cutoff)
    dates = x.index.get_level_values("Date")
    calendar = pd.DatetimeIndex(dates.unique().sort_values())
    pieces = []
    years = sorted(year for year in set(dates[dates <= cutoff].year) if year in models.YEARS)
    for year in years:
        model, _ = models.fit_before(x, target, calendar, f"{year}-01-01")
        selected = (dates <= cutoff) & (dates.year == year) & x["new_high_excess"].gt(0.0).to_numpy()
        if selected.any():
            rows = x.loc[selected, list(features.FEATURE_COLUMNS)]
            pieces.append(pd.Series(models.predict_matrix(rows, model), index=rows.index, name=models.TRIAL_ID))
    if not pieces:
        return pd.Series(dtype=float, index=pd.MultiIndex.from_arrays([[], []], names=x.index.names))
    return pd.concat(pieces).sort_index()


def build_signals(x, target, candidate_predictions=None):
    h0 = features.smooth_by_listing(x["relative_strength_60"].rename("H0"), alpha=0.25)
    b00_raw = models.raw_base_signal(x)
    b00 = models.smooth_by_listing(b00_raw, alpha=0.25).rename("B00")
    if candidate_predictions is None:
        candidate_predictions, records = models.walk_forward_predictions(x, target, model_dir=None)
    else:
        records = []
    candidate = models.generate_candidate(x, candidate_predictions, b00_raw, alpha=0.25)
    return {"H0": h0, "B00": b00, models.TRIAL_ID: candidate}, records


def audit_prefix(inputs, target, x, signals):
    source_files = source_scan()
    records = []
    calendar = pd.DatetimeIndex(x.index.get_level_values("Date").unique().sort_values())
    for label in CUTOFFS:
        cutoff = pd.Timestamp(label)
        prefix = x.index.get_level_values("Date") <= cutoff
        prefix_index = x.index[prefix]
        check_modes = {}
        for mode in ("mutation", "truncation"):
            truncated = mode == "truncation"
            changed_inputs = mutate_inputs(inputs, cutoff, truncate=truncated)
            changed_x = features.build_features(changed_inputs)
            changed_target = mutate_target(target, cutoff, truncate=truncated)
            if truncated:
                changed_target = changed_target.reindex(changed_x.index)
            pd.testing.assert_frame_equal(x.loc[prefix_index], changed_x.loc[prefix_index], check_exact=True)
            changed_signals = build_signals(
                changed_x,
                changed_target,
                candidate_predictions_through(changed_x, changed_target, cutoff),
            )[0]
            for name in METHODS:
                pd.testing.assert_series_equal(
                    signals[name].loc[prefix_index], changed_signals[name].loc[prefix_index],
                    check_exact=True,
                )
            check_modes[mode] = "features, H0/B00, mature-label refit and candidate prefix bitwise exact"
        records.append({"cutoff": label, "prefix_rows": int(prefix.sum()), "checks": check_modes})
    return {"status": "PASS", "source_files": source_files, "cutoffs": records}


def make_report(run_id, summaries, folds, audit, training_records, coverage, evaluation_span):
    report_dir = ROOT / "reports" / EXPERIMENT_ID
    report_dir.mkdir(parents=True, exist_ok=True)
    lookup = {item["strategy"]: item for item in summaries}
    h0 = lookup["H0"]["pooled"]["net_sharpe"]
    b00 = lookup["B00"]["pooled"]["net_sharpe"]
    lines = [
        f"# {EXPERIMENT_ID}: 可変長ボックス後の新高値ブレイク", "",
        f"- Run ID: `{run_id}`",
        "- Train splitのみ。Valid / Valid target / raw targetは未使用。全Trainは既読の記述評価で、候補選択・採用には使わない。",
        f"- 評価期間: {evaluation_span[0]}〜{evaluation_span[1]}。2010年は学習warm-up、2016年は部分fold。各評価年末で2取引日をpurge。",
        "- Official target: t+1 Open → t+2 Open の1日市場残差リターン。",
        "- Box duration: t-1までの5観測刻み5〜120日窓から、prior ATR20の3倍未満となる最長期間。Close positionはt-1終値。",
        "- BOX_RIDGE_001: 新高値イベント行のみのannual expanding Ridge(lambda=1.0)。5特徴のTrain fit、Longイベント順位をB00と50/50、ShortはB00維持、EWMA alpha=0.25。",
        "- H0 / B00と同じ公式5分位weight・片道10bps costで比較。追加候補は1本。",
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
            f"{p['net_sharpe']-h0:+.4f} | {p['net_sharpe']-b00:+.4f} | "
            f"{p['annual_gross']:+.2%} | {p['annual_net']:+.2%} | {p['annual_cost']:.2%} | "
            f"{p['turnover']:.5f} | {long['annual_net']:+.2%}/{long['net_sharpe']:.3f} | "
            f"{short['annual_net']:+.2%}/{short['net_sharpe']:.3f} | {p['rankic']:+.4f} | "
            f"{p['rankic_t_hac5']:+.3f} | {p['rankic_hit']:.3f} | {p['q_monotonicity']:+.3f} | "
            f"{p['max_drawdown_additive']:+.2%} |"
        )
    lines += [
        "", "## 年別fold", "",
        "| Year | Strategy | Gross SR | Net SR | ΔNetSR H0 | ΔNetSR B00 | Annual Net | Cost | Turnover | RankIC | Q mono | Long Net | Short Net | Max DD |",
        "|---:|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in folds:
        legs = row["legs"]
        lines.append(
            f"| {row['year']} | {row['strategy']} | {row['gross_sharpe']:.3f} | {row['net_sharpe']:.3f} | "
            f"{row['delta_vs_H0']:+.3f} | {row['delta_vs_B00']:+.3f} | {row['annual_net']:+.2%} | "
            f"{row['annual_cost']:.2%} | {row['turnover']:.5f} | {row['rankic']:+.4f} | "
            f"{row['q_monotonicity']:+.2f} | {legs['long']['annual_net']:+.2%} | "
            f"{legs['short']['annual_net']:+.2%} | {row['max_drawdown_additive']:+.2%} |"
        )
    candidate = lookup[models.TRIAL_ID]
    lines += [
        "", "## 増分指標", "",
        "各foldのΔRankIC・ΔGross/Net Sharpe・Δturnover・Δcost対H0/B00は `fold_metrics.csv` に保存。pooled差分:", "",
        "| Baseline | ΔRankIC | ΔGross SR | ΔNet SR | ΔTurnover/day | ΔAnnual cost |", "|:---|---:|---:|---:|---:|---:|",
    ]
    for baseline, comparison in candidate["comparisons"].items():
        delta = comparison["delta_metrics"]
        lines.append(
            f"| {baseline} | {delta['rankic']:+.5f} | {delta['gross_sharpe']:+.4f} | "
            f"{delta['net_sharpe']:+.4f} | {delta['turnover']:+.5f} | {delta['annual_cost']:+.3%} |"
        )
    lines += [
        "", "## Paired 20日 block bootstrap", "",
        "| Baseline | Δ pooled Net SR | 95% CI | Positive fraction |", "|:---|---:|:---|---:|",
    ]
    for baseline, result in candidate["comparisons"].items():
        boot = result["bootstrap"]
        lines.append(
            f"| {baseline} | {result['delta_net_sharpe']:+.4f} | "
            f"[{boot['low']:+.4f}, {boot['high']:+.4f}] | {boot['bootstrap_positive_fraction']:.3f} |"
        )
    lines += [
        "", "## 年次モデルとデータcoverage", "",
        "係数はfold内標準化後の値。将来の因果効果や係数安定性の証明ではない。", "",
        "| Year | Training breakout rows | Mature label through | Coefficients (intercept + five features) |", "|---:|---:|:---|:---|",
    ]
    for record in training_records:
        coefs = ", ".join(f"{value:+.4g}" for value in record["coefficients"])
        lines.append(
            f"| {record['year']} | {record['training_rows']} | {record['max_label_maturity_date']} | {coefs} |"
        )
    lines += [
        "", "## 監査・制約", "",
        f"- Prefix invariance / source scan / Train firewall: **{audit['status']}**.",
        "- 3 cutoffでOHLC・raw returns・beta・TOPIX・AdjustmentFactor・Train targetを将来mutation/truncationし、特徴・baseline・成熟target refit・予測prefixをbitwise照合。",
        f"- Candidate signal finite coverage: {coverage[models.TRIAL_ID]}/{coverage['evaluation_rows']} evaluation rows; box model predictions are limited to new-high events.",
        "- Signal coverage、Long+Short日次Net会計照合、fold再fit再現をPASS。",
        "- 全Train期間は過去実験で既知。数値は今回の記述診断に限り、独立OOS・採用・Freeze・Valid評価の根拠にはしない。",
    ]
    path = report_dir / "REPORT.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run(config_path, output_path):
    started = time.monotonic()
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if (config.get("experiment_id") != EXPERIMENT_ID or config.get("data_split") != "train"
            or config.get("valid_evaluation") is not False or config.get("selection_eligible") is not False
            or config.get("max_trials") != 1
            or [item["trial_id"] for item in config.get("trials", [])] != [models.TRIAL_ID]):
        raise ValueError("Unexpected experiment scope or trial budget")
    output = Path(output_path)
    for folder in ("models", "predictions", "metrics", "audit"):
        (output / folder).mkdir(parents=True, exist_ok=True)
    run_path = output / "run.json"
    metadata = json.loads(run_path.read_text(encoding="utf-8"))
    sources = [
        Path(__file__).resolve(), Path(features.__file__).resolve(), Path(models.__file__).resolve(),
        Path(adapter.__file__).resolve(), Path(firewall.__file__).resolve(),
        Path(evaluation.__file__).resolve(), Path(dump.__globals__["__file__"]).resolve(),
    ]
    metadata.update({
        "status": "running", "started_at_utc": now_utc(), "command": sys.argv,
        "actual_trials": 0,
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "numpy": np.__version__, "pandas": pd.__version__},
        "code_sha256": {str(path.relative_to(ROOT)): digest(path) for path in sources},
    })
    dump(run_path, metadata)
    try:
        firewall.install()
        data_dir = ROOT / "stock_comp_2026" / "input"
        data_hashes = {
            f"{name}_train.parquet": digest(data_dir / f"{name}_train.parquet")
            for name in features.INPUT_COLUMNS
        }
        data_hashes["target_1day_train.parquet"] = digest(data_dir / "target_1day_train.parquet")
        metadata["train_data_sha256"] = data_hashes
        dump(run_path, metadata)

        print("[1/6] Load Train-only inputs and compute the fixed feature matrix...", flush=True)
        inputs = features.load_inputs(data_dir, split="train")
        target = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index()
        x = features.build_features(inputs)
        if not x.index.equals(target.index):
            raise AssertionError("Feature and Train target indexes are not exactly aligned")
        dates = x.index.get_level_values("Date")
        calendar = pd.DatetimeIndex(dates.unique().sort_values())
        if str(calendar.min().date()) != "2008-11-04" or str(calendar.max().date()) != "2016-03-31":
            raise AssertionError("Unexpected Train date span")

        print("[2/6] Run source, firewall and full future-mutation/truncation audits...", flush=True)
        predictions, training_records = models.walk_forward_predictions(
            x, target, model_dir=output / "models"
        )
        signals, _ = build_signals(x, target, predictions)
        audit = audit_prefix(inputs, target, x, signals)
        dump(output / "audit/causality.json", audit)
        firewall.save(output / "audit/firewall.json")
        audit = {**audit, "firewall": json.loads((output / "audit/firewall.json").read_text(encoding="utf-8"))}
        opened = audit["firewall"].get("opened_parquets", [])
        if any("_valid" in path or "raw_target" in path for path in opened):
            raise AssertionError("Train-only firewall opened a prohibited file")

        print("[3/6] Check coverage, deterministic annual refits and score files...", flush=True)
        seed = daily_account(signals["H0"], target)
        eval_dates = evaluation_dates(seed.index)
        eval_rows = dates.isin(eval_dates)
        coverage = {}
        for name, signal in signals.items():
            signals[name] = signal.reindex(target.index)
            values = signals[name].to_numpy()[eval_rows]
            if len(values) != int(eval_rows.sum()) or not np.isfinite(values).all():
                raise AssertionError(f"Incomplete/nonfinite score for {name}")
            coverage[name] = int(len(values))
        pd.DataFrame(signals, index=target.index).sort_index().to_parquet(
            output / "predictions/signals.parquet"
        )
        x.loc[eval_rows, list(features.FEATURE_COLUMNS)].to_parquet(
            output / "predictions/box_features.parquet"
        )
        replay, replay_records = models.walk_forward_predictions(x, target, model_dir=None)
        pd.testing.assert_series_equal(predictions, replay, check_exact=True)
        if training_records != replay_records:
            raise AssertionError("Annual model records differ on deterministic replay")

        print("[4/6] Evaluate H0/B00/candidate on identical dates and reconcile legs...", flush=True)
        eval_set = set(eval_dates)
        accounts, legs, summaries, fold_rows = {}, {}, [], []
        for name in METHODS:
            account_all = daily_account(signals[name], target)
            legs_all = leg_account(signals[name], target)
            gap = (legs_all.net_sum.reindex(account_all.index) - account_all.net).abs().max()
            if not np.isfinite(gap) or gap > 1e-10:
                raise AssertionError(f"Long/Short account reconciliation failed for {name}: {gap}")
            account_all.to_csv(output / f"metrics/daily_account_{name}.csv", index_label="Date")
            legs_all.to_csv(output / f"metrics/daily_legs_{name}.csv", index_label="Date")
            account = account_all.loc[account_all.index.isin(eval_set)]
            split_legs = legs_all.reindex(account.index)
            accounts[name], legs[name] = account, split_legs
            pooled = metric_bundle(account, split_legs)
            periods = []
            for year in models.YEARS:
                yearly_dates = [date for date in eval_dates if date.year == year]
                y_account = account.loc[account.index.isin(yearly_dates)]
                y_legs = split_legs.reindex(y_account.index)
                bundle = metric_bundle(y_account, y_legs)
                row = {"strategy": name, "year": int(year), **{k: v for k, v in bundle.items() if k != "legs"},
                       "legs": bundle["legs"]}
                fold_rows.append(row)
                periods.append({"year": int(year), "metrics": bundle})
            summaries.append({"strategy": name, "pooled": pooled, "periods": periods})

        lookup = {item["strategy"]: item for item in summaries}
        candidate = lookup[models.TRIAL_ID]
        common_comparisons = {}
        for baseline in BASELINE_NAMES:
            common = accounts[baseline].index.intersection(accounts[models.TRIAL_ID].index)
            deltas = []
            for year in models.YEARS:
                new = next(row for row in fold_rows if row["strategy"] == models.TRIAL_ID and row["year"] == year)
                old = next(row for row in fold_rows if row["strategy"] == baseline and row["year"] == year)
                deltas.append(new["net_sharpe"] - old["net_sharpe"])
            common_comparisons[baseline] = {
                "delta_net_sharpe": candidate["pooled"]["net_sharpe"] - lookup[baseline]["pooled"]["net_sharpe"],
                "fold_delta_net_sharpe": deltas,
                "improved_folds": int(sum(value > 0 for value in deltas)),
                "bootstrap": bootstrap_delta(
                    accounts[baseline].loc[common, "net"],
                    accounts[models.TRIAL_ID].loc[common, "net"],
                    seed=SEED, reps=BOOTSTRAP_REPS, block=BOOTSTRAP_BLOCK,
                ),
            }
        candidate["comparisons"] = common_comparisons
        for row in fold_rows:
            row["delta_vs_H0"] = row["net_sharpe"] - next(
                item["net_sharpe"] for item in fold_rows if item["strategy"] == "H0" and item["year"] == row["year"]
            )
            row["delta_vs_B00"] = row["net_sharpe"] - next(
                item["net_sharpe"] for item in fold_rows if item["strategy"] == "B00" and item["year"] == row["year"]
            )
            for baseline in BASELINE_NAMES:
                base_row = next(
                    item for item in fold_rows
                    if item["strategy"] == baseline and item["year"] == row["year"]
                )
                for metric in ("rankic", "gross_sharpe", "net_sharpe", "turnover", "annual_cost"):
                    row[f"delta_{metric}_vs_{baseline}"] = row[metric] - base_row[metric]
        for baseline, comparison in common_comparisons.items():
            comparison["delta_metrics"] = {
                metric: candidate["pooled"][metric] - lookup[baseline]["pooled"][metric]
                for metric in ("rankic", "gross_sharpe", "net_sharpe", "turnover", "annual_cost")
            }

        print("[5/6] Save metrics, model training records and report...", flush=True)
        dump(output / "metrics/summary.json", summaries)
        dump(output / "audit/model_training.json", {
            "records": training_records, "deterministic_replay": "bitwise exact",
            "prediction_coverage": coverage, "evaluation_days": len(eval_dates),
            "purge_last_two_dates_per_year": True, "account_reconciliation": "PASS",
        })
        pd.DataFrame([{key: value for key, value in row.items() if key != "legs"} for row in fold_rows]).to_csv(
            output / "metrics/fold_metrics.csv", index=False
        )
        comp_rows = []
        for item in summaries:
            row = {"strategy": item["strategy"]}
            row.update({key: value for key, value in item["pooled"].items() if key != "legs"})
            for side in ("long", "short"):
                row[f"{side}_annual_net"] = item["pooled"]["legs"][side]["annual_net"]
                row[f"{side}_net_sharpe"] = item["pooled"]["legs"][side]["net_sharpe"]
            if item["strategy"] == models.TRIAL_ID:
                for baseline, result in common_comparisons.items():
                    row[f"delta_net_sharpe_vs_{baseline}"] = result["delta_net_sharpe"]
                    row[f"improved_folds_vs_{baseline}"] = result["improved_folds"]
                    row[f"bootstrap_low_vs_{baseline}"] = result["bootstrap"]["low"]
                    row[f"bootstrap_high_vs_{baseline}"] = result["bootstrap"]["high"]
                    for metric, value in result["delta_metrics"].items():
                        row[f"delta_{metric}_vs_{baseline}"] = value
            comp_rows.append(row)
        pd.DataFrame(comp_rows).to_csv(output / "metrics/model_comparison.csv", index=False)
        report_dir = ROOT / "reports" / EXPERIMENT_ID
        report_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([{key: value for key, value in row.items() if key != "legs"} for row in fold_rows]).to_csv(
            report_dir / "fold_metrics.csv", index=False
        )
        pd.DataFrame(comp_rows).to_csv(report_dir / "model_comparison.csv", index=False)
        span = (str(eval_dates.min().date()), str(eval_dates.max().date()))
        report = make_report(
            output.name, summaries, fold_rows, audit, training_records,
            {**coverage, "evaluation_rows": int(eval_rows.sum())}, span,
        )
        dump(report_dir / "audit_summary.json", {
            "status": "PASS", "source_scan": audit["source_files"],
            "cutoffs": audit["cutoffs"], "valid_accessed": False,
        })
        metadata.update({
            "status": "completed", "completed_at_utc": now_utc(),
            "elapsed_seconds": time.monotonic() - started, "actual_trials": 1,
            "train_data_sha256": data_hashes, "valid_accessed": False,
            "source_scan": "PASS", "prefix_invariance": "PASS",
            "prediction_coverage": coverage, "account_reconciliation": "PASS",
            "evaluation_span": span, "report": str(report.relative_to(ROOT)),
        })
        dump(run_path, metadata)
        print(f"[Done] {report}", flush=True)
    except BaseException as error:
        metadata.update({"status": "failed", "completed_at_utc": now_utc(),
                         "failure": repr(error), "elapsed_seconds": time.monotonic() - started})
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
    arguments = parser.parse_args()
    run(arguments.config, arguments.output)
