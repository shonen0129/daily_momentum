"""Train-only standalone high/low variable-box breakout comparison."""
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

from research import evaluation, firewall
from research.evaluation import bootstrap_delta, daily_account
from research.experiments.slope_range_volume_ml import (
    BASELINE_NAMES, dump, leg_account, metric_bundle,
)
from stock_comp_2026.strategies.dm_variable_box_breakout import bidirectional, features, sn1, submission
from stock_comp_2026.strategies.dm_variable_box_breakout import models as b00_models
from stock_comp_2026.strategies.dm_breakout_side_momentum import features as reference_features
from stock_comp_2026.strategies.dm_breakout_base_momentum_overlay import models as reference_b00


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DM-20260925-03"
YEARS = tuple(range(2011, 2017))
METHODS = ("H0", "B00", bidirectional.TRIAL_ID)
SEED = 20260925
BOOTSTRAP_REPS = 1000
BOOTSTRAP_BLOCK = 20
ONE_WAY_COST = 0.001
CUTOFFS = ("2010-12-30", "2012-06-29", "2014-12-30")


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_scan():
    paths = [
        Path(features.__file__), Path(bidirectional.__file__),
        Path(sn1.__file__), Path(submission.__file__),
    ]
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


def baseline_signals(x):
    h0 = features.smooth_by_listing(x["relative_strength_60"].rename("H0"), alpha=0.25)
    b00 = b00_models.generate_base_signal(x, alpha=0.25).rename("B00")
    return {"H0": h0, "B00": b00}


def evaluation_dates(account_index):
    dates = pd.DatetimeIndex(account_index)
    selected = []
    for year in YEARS:
        year_dates = dates[dates.year == year].unique().sort_values()
        if len(year_dates) <= 2:
            raise AssertionError(f"Insufficient evaluation dates for {year}")
        selected.extend(year_dates[:-2].tolist())
    return pd.DatetimeIndex(selected).sort_values()


def predictions_through(x, target, cutoff):
    """Annual refits and event predictions needed to reproduce a signal prefix."""
    cutoff = pd.Timestamp(cutoff)
    dates = x.index.get_level_values("Date")
    calendar = pd.DatetimeIndex(dates.unique().sort_values())
    year_limit = min(cutoff.year, max(YEARS))
    years = [year for year in YEARS if year <= year_limit]
    result = {side: [] for side in bidirectional.SIDES}
    for year in years:
        for side in bidirectional.SIDES:
            model, _ = bidirectional.fit_before(x, target, calendar, f"{year}-01-01", side)
            selected = (
                (dates <= cutoff) & (dates.year == year)
                & bidirectional.event_mask(x, side).to_numpy()
            )
            matrix = bidirectional.directional_features(x.loc[selected], side)
            if len(matrix):
                result[side].append(pd.Series(
                    bidirectional.predict_matrix(matrix, model), index=matrix.index,
                    name=f"{bidirectional.TRIAL_ID}_{side}", dtype=float,
                ))
    combined = {}
    for side, pieces in result.items():
        combined[side] = (
            pd.concat(pieces).sort_index() if pieces else
            pd.Series(dtype=float, index=pd.MultiIndex.from_arrays(
                [[], []], names=x.index.names
            ), name=f"{bidirectional.TRIAL_ID}_{side}")
        )
    return combined


def build_signals(x, predictions):
    result = baseline_signals(x)
    result[bidirectional.TRIAL_ID] = bidirectional.generate_signal(x, predictions, alpha=0.25)
    return result


def audit_prefix(inputs, target, x, signals):
    files = source_scan()
    records = []
    dates = x.index.get_level_values("Date")
    for label in CUTOFFS:
        cutoff = pd.Timestamp(label)
        if cutoff not in dates:
            raise AssertionError(f"Missing prefix cutoff {label}")
        prefix_index = x.index[dates <= cutoff]
        modes = {}
        for mode in ("mutation", "truncation"):
            truncate = mode == "truncation"
            changed_inputs = mutate_inputs(inputs, cutoff, truncate=truncate)
            changed_x = features.build_features(changed_inputs)
            changed_target = mutate_target(target, cutoff, truncate=truncate)
            if truncate:
                changed_target = changed_target.reindex(changed_x.index)
            pd.testing.assert_frame_equal(
                x.loc[prefix_index], changed_x.loc[prefix_index], check_exact=True
            )
            changed_predictions = predictions_through(changed_x, changed_target, cutoff)
            changed_signals = build_signals(changed_x, changed_predictions)
            for name in METHODS:
                pd.testing.assert_series_equal(
                    signals[name].loc[prefix_index], changed_signals[name].loc[prefix_index],
                    check_exact=True,
                )
            modes[mode] = "features, baselines, side-specific mature-label refits and scores bitwise exact"
        records.append({"cutoff": label, "prefix_rows": int(len(prefix_index)), "checks": modes})
    return {"status": "PASS", "source_files": files, "cutoffs": records}


def make_report(run_id, summaries, folds, training_records, audit, eval_span, coverage, event_counts):
    report_dir = ROOT / "reports" / EXPERIMENT_ID
    report_dir.mkdir(parents=True, exist_ok=True)
    by_name = {item["strategy"]: item for item in summaries}
    lines = [
        f"# {EXPERIMENT_ID}: 可変長ボックスの高値・安値ブレイク独立スコア", "",
        f"- Run ID: `{run_id}`",
        "- Train split only。Valid / Valid target / raw targetは未使用。全Train期間は既読で記述診断のみ。",
        f"- 評価期間: {eval_span[0]}〜{eval_span[1]}。foldは2011〜2016（2016年は部分期間）、各年末2取引日をpurge。",
        "- 高値/安値イベントを別々のRidgeで学習し、side内順位を正/負scoreに変換。B00は比較だけに使い、候補scoreには混ぜない。",
        "- Box定義、raw価格のsplit整合、5特徴、λ=1.0、EWMA α=0.25、片道10bpsは計画時に固定。",
        "",
        "## Pooled結果", "",
        "| Strategy | Gross SR | Net SR | ΔNet SR vs H0 | ΔNet SR vs B00 | 年率Gross | 年率Net | 年率Cost | Turnover/日 | Long 年率Net / SR | Short 年率Net / SR | RankIC | HAC t | Hit | Q mono | Max DD |",
        "|:---|---:|---:|---:|---:|---:|---:|---:|---:|:---|:---|---:|---:|---:|---:|---:|",
    ]
    h0_sr = by_name["H0"]["pooled"]["net_sharpe"]
    b00_sr = by_name["B00"]["pooled"]["net_sharpe"]
    for item in summaries:
        p = item["pooled"]
        long, short = p["legs"]["long"], p["legs"]["short"]
        lines.append(
            f"| {item['strategy']} | {p['gross_sharpe']:.4f} | {p['net_sharpe']:.4f} | "
            f"{p['net_sharpe']-h0_sr:+.4f} | {p['net_sharpe']-b00_sr:+.4f} | "
            f"{p['annual_gross']:+.2%} | {p['annual_net']:+.2%} | {p['annual_cost']:.2%} | "
            f"{p['turnover']:.5f} | {long['annual_net']:+.2%} / {long['net_sharpe']:.3f} | "
            f"{short['annual_net']:+.2%} / {short['net_sharpe']:.3f} | {p['rankic']:+.4f} | "
            f"{p['rankic_t_hac5']:+.3f} | {p['rankic_hit']:.3f} | {p['q_monotonicity']:+.3f} | "
            f"{p['max_drawdown_additive']:+.2%} |"
        )
    candidate = by_name[bidirectional.TRIAL_ID]
    lines += [
        "", "## Baseline差分・bootstrap", "",
        "| Baseline | ΔRankIC | ΔGross SR | ΔNet SR | ΔTurnover/日 | ΔAnnual cost | ΔNet SR 95%区間 | 正差bootstrap比率 |", 
        "|:---|---:|---:|---:|---:|---:|:---|---:|",
    ]
    for baseline, comparison in candidate["comparisons"].items():
        delta, boot = comparison["delta_metrics"], comparison["bootstrap"]
        lines.append(
            f"| {baseline} | {delta['rankic']:+.5f} | {delta['gross_sharpe']:+.4f} | "
            f"{delta['net_sharpe']:+.4f} | {delta['turnover']:+.5f} | {delta['annual_cost']:+.3%} | "
            f"[{boot['low']:+.4f}, {boot['high']:+.4f}] | {boot['bootstrap_positive_fraction']:.3f} |"
        )
    lines += [
        "", "## 年別fold", "",
        "| Year | Strategy | Net SR | ΔNet SR vs B00 | 年率Net | Cost | Turnover | Long 年率Net | Short 年率Net | RankIC | RankIC t | Hit | Q1–Q5 mono | Max DD |",
        "|---:|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in folds:
        leg = row["legs"]
        base = next(r for r in folds if r["year"] == row["year"] and r["strategy"] == "B00")
        lines.append(
            f"| {row['year']} | {row['strategy']} | {row['net_sharpe']:.3f} | "
            f"{row['net_sharpe']-base['net_sharpe']:+.3f} | {row['annual_net']:+.2%} | "
            f"{row['annual_cost']:.2%} | {row['turnover']:.5f} | "
            f"{leg['long']['annual_net']:+.2%} | {leg['short']['annual_net']:+.2%} | "
            f"{row['rankic']:+.4f} | {row['rankic_t_hac5']:+.2f} | {row['rankic_hit']:.3f} | "
            f"{row['q_monotonicity']:+.2f} | {row['max_drawdown_additive']:+.2%} |"
        )
    lines += [
        "", "## 学習件数・スコア出力", "",
        "各sideの年次Ridgeは、その年より前に成熟したtargetを持つ同方向ブレイク行だけでfit。" 
        "予測はイベント行に限定し、方向別event内rankからsigned scoreを作る。B00とのblendは行わない。", "",
        "| Year | Side | Mature training rows | Training dates | Label matured through | Coefficients (intercept + 5) |",
        "|---:|:---|---:|---:|:---|:---|",
    ]
    for record in training_records:
        coefs = ", ".join(f"{v:+.4g}" for v in record["coefficients"])
        lines.append(
            f"| {record['year']} | {record['side']} | {record['training_rows']} | "
            f"{record['training_dates']} | {record['max_label_maturity_date']} | {coefs} |"
        )
    lines += [
        "", f"イベント件数: high={event_counts['high']:,}, low={event_counts['low']:,} (評価期間)",
        f"score coverage: {coverage[bidirectional.TRIAL_ID]:,}/{coverage['evaluation_rows']:,} 評価行が有限値。", "",
        "候補の全日次スコアはrun artifactの `predictions/signals.parquet`、年内side別イベント予測は "
        "`predictions/event_predictions.parquet` に保存。", "",
        "## 監査・制約", "",
        f"- Source scan / Train firewall / future-mutation prefix-invariance: **{audit['status']}**。",
        "- 3 cutoff × mutation/truncationで全特徴、H0/B00、両sideの成熟target refit、standalone score prefixをbitwise照合。",
        "- index alignment、全評価行finite coverage、決定性replay、Long+Short会計一致を実行。",
        "- 全Trainは既知。結果はこの固定候補の記述的比較で、独立OOS・採用・Freeze・Valid評価の根拠にしない。",
    ]
    report = report_dir / "REPORT.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def run(config_path, output_path):
    started = time.monotonic()
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if (config.get("experiment_id") != EXPERIMENT_ID or config.get("data_split") != "train"
            or config.get("valid_evaluation") is not False or config.get("selection_eligible") is not False
            or config.get("max_trials") != 1
            or [item["trial_id"] for item in config.get("trials", [])] != [bidirectional.TRIAL_ID]
            or config.get("selection_rule", {}).get("candidate_score_uses_baseline") is not False):
        raise ValueError("Unexpected experiment identity, eligibility, baseline use, or trial budget")
    output = Path(output_path)
    for folder in ("models", "predictions", "metrics", "audit"):
        (output / folder).mkdir(parents=True, exist_ok=True)
    run_path = output / "run.json"
    metadata = json.loads(run_path.read_text(encoding="utf-8"))
    sources = [
        Path(__file__).resolve(), Path(features.__file__).resolve(),
        Path(bidirectional.__file__).resolve(), Path(firewall.__file__).resolve(),
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

        print("[1/6] Load Train-only inputs and build causal high/low box features...", flush=True)
        inputs = features.load_inputs(data_dir, split="train")
        target = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index()
        x = features.build_features(inputs)
        if not x.index.equals(target.index):
            raise AssertionError("Feature and Train target indexes are not exactly aligned")
        dates = x.index.get_level_values("Date")
        calendar = pd.DatetimeIndex(dates.unique().sort_values())
        if str(calendar.min().date()) != "2008-11-04" or str(calendar.max().date()) != "2016-03-31":
            raise AssertionError("Unexpected Train date span")
        reference_x = reference_features.build_features(inputs)
        expected_b00 = reference_b00.generate_signal(reference_x, "B00", alpha=0.25)
        actual_b00 = b00_models.generate_base_signal(x, alpha=0.25)
        pd.testing.assert_series_equal(
            expected_b00, actual_b00, check_exact=True, check_names=False
        )

        print("[2/6] Fit separate annual high/low models and audit future prefixes...", flush=True)
        predictions, training_records = bidirectional.walk_forward_predictions(
            x, target, years=YEARS, model_dir=output / "models"
        )
        signals = build_signals(x, predictions)
        audit = audit_prefix(inputs, target, x, signals)
        dump(output / "audit/causality.json", audit)
        firewall.save(output / "audit/firewall.json")
        firewall_record = json.loads((output / "audit/firewall.json").read_text(encoding="utf-8"))
        if any("_valid" in path or "raw_target" in path for path in firewall_record.get("opened_parquets", [])):
            raise AssertionError("Train-only firewall opened a prohibited file")

        print("[3/6] Check full coverage, finite scores and deterministic model replay...", flush=True)
        seed_account = daily_account(signals["H0"], target)
        eval_dates = evaluation_dates(seed_account.index)
        eval_rows = dates.isin(eval_dates)
        eval_index = x.index[eval_rows]
        coverage = {}
        for name in METHODS:
            signal = signals[name].reindex(target.index)
            values = signal.loc[eval_index].to_numpy()
            if len(values) != len(eval_index) or not np.isfinite(values).all():
                raise AssertionError(f"Incomplete/nonfinite score for {name}")
            coverage[name] = int(len(values))
            signals[name] = signal
        event_predictions = pd.DataFrame(index=x.index)
        for side in bidirectional.SIDES:
            event_predictions[f"{side}_prediction"] = predictions[side].reindex(x.index)
            event_predictions[f"{side}_event"] = bidirectional.event_mask(x, side)
        pd.DataFrame(signals, index=target.index).sort_index().to_parquet(
            output / "predictions/signals.parquet"
        )
        event_predictions.loc[eval_rows].to_parquet(output / "predictions/event_predictions.parquet")
        x.loc[eval_rows].to_parquet(output / "predictions/box_features.parquet")
        replay, replay_records = bidirectional.walk_forward_predictions(
            x, target, years=YEARS, model_dir=None
        )
        for side in bidirectional.SIDES:
            pd.testing.assert_series_equal(predictions[side], replay[side], check_exact=True)
        if training_records != replay_records:
            raise AssertionError("Annual high/low model records changed on deterministic replay")

        print("[4/6] Evaluate standalone score, H0 and B00 with accounting reconciliation...", flush=True)
        eval_set = set(eval_dates)
        accounts, folds, summaries = {}, [], []
        for name in METHODS:
            account_all = daily_account(signals[name], target)
            legs_all = leg_account(signals[name], target)
            gap = (legs_all.net_sum.reindex(account_all.index) - account_all.net).abs().max()
            if not np.isfinite(gap) or gap > 1e-10:
                raise AssertionError(f"Long/Short accounting reconciliation failed for {name}: {gap}")
            account = account_all.loc[account_all.index.isin(eval_set)]
            legs = legs_all.reindex(account.index)
            account.to_csv(output / f"metrics/daily_account_{name}.csv", index_label="Date")
            legs.to_csv(output / f"metrics/daily_legs_{name}.csv", index_label="Date")
            accounts[name] = account
            pooled = metric_bundle(account, legs)
            summaries.append({"strategy": name, "pooled": pooled})
            for year in YEARS:
                year_account = account.loc[account.index.year == year]
                year_legs = legs.reindex(year_account.index)
                folds.append({
                    "strategy": name, "year": int(year),
                    **{key: value for key, value in metric_bundle(year_account, year_legs).items() if key != "legs"},
                    "legs": metric_bundle(year_account, year_legs)["legs"],
                })

        by_name = {item["strategy"]: item for item in summaries}
        candidate = by_name[bidirectional.TRIAL_ID]
        comparisons = {}
        for baseline in BASELINE_NAMES:
            common = accounts[baseline].index.intersection(accounts[bidirectional.TRIAL_ID].index)
            base, new = accounts[baseline].loc[common], accounts[bidirectional.TRIAL_ID].loc[common]
            boot = bootstrap_delta(
                base["net"], new["net"], seed=SEED, reps=BOOTSTRAP_REPS, block=BOOTSTRAP_BLOCK
            )
            comparisons[baseline] = {
                "bootstrap": boot,
                "delta_metrics": {
                    metric: float(candidate["pooled"][metric] - by_name[baseline]["pooled"][metric])
                    for metric in ("rankic", "gross_sharpe", "net_sharpe", "turnover", "annual_cost")
                },
                "improved_folds": int(sum(
                    next(row["net_sharpe"] for row in folds if row["strategy"] == bidirectional.TRIAL_ID and row["year"] == year)
                    > next(row["net_sharpe"] for row in folds if row["strategy"] == baseline and row["year"] == year)
                    for year in YEARS
                )),
            }
        candidate["comparisons"] = comparisons

        print("[5/6] Save scores, metrics, report and reproducibility metadata...", flush=True)
        summary_path = output / "metrics/summary.json"
        dump(summary_path, summaries)
        plain_folds = [{key: value for key, value in row.items() if key != "legs"} for row in folds]
        pd.DataFrame(plain_folds).to_csv(output / "metrics/fold_metrics.csv", index=False)
        comparison_rows = []
        for item in summaries:
            pooled = item["pooled"]
            row = {"strategy": item["strategy"], **{k: v for k, v in pooled.items() if k != "legs"}}
            for side in ("long", "short"):
                row[f"{side}_annual_net"] = pooled["legs"][side]["annual_net"]
                row[f"{side}_net_sharpe"] = pooled["legs"][side]["net_sharpe"]
            if item["strategy"] == bidirectional.TRIAL_ID:
                for baseline, comparison in comparisons.items():
                    row[f"delta_net_sharpe_vs_{baseline}"] = comparison["delta_metrics"]["net_sharpe"]
                    row[f"improved_folds_vs_{baseline}"] = comparison["improved_folds"]
                    row[f"bootstrap_low_vs_{baseline}"] = comparison["bootstrap"]["low"]
                    row[f"bootstrap_high_vs_{baseline}"] = comparison["bootstrap"]["high"]
                    for metric, value in comparison["delta_metrics"].items():
                        row[f"delta_{metric}_vs_{baseline}"] = value
            comparison_rows.append(row)
        pd.DataFrame(comparison_rows).to_csv(output / "metrics/model_comparison.csv", index=False)
        report_dir = ROOT / "reports" / EXPERIMENT_ID
        report_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(plain_folds).to_csv(report_dir / "fold_metrics.csv", index=False)
        pd.DataFrame(comparison_rows).to_csv(report_dir / "model_comparison.csv", index=False)
        event_counts = {
            side: int((bidirectional.event_mask(x, side) & dates.isin(eval_dates)).sum())
            for side in bidirectional.SIDES
        }
        span = (str(eval_dates.min().date()), str(eval_dates.max().date()))
        report = make_report(
            output.name, summaries, folds, training_records, audit, span,
            {**coverage, "evaluation_rows": int(eval_rows.sum())}, event_counts,
        )
        dump(report_dir / "audit_summary.json", {
            "status": "PASS", "source_scan": audit["source_files"],
            "cutoffs": audit["cutoffs"], "valid_accessed": False,
            "standalone_score_uses_b00": False,
        })
        metadata.update({
            "status": "completed", "completed_at_utc": now_utc(),
            "elapsed_seconds": time.monotonic() - started, "actual_trials": 1,
            "train_data_sha256": data_hashes, "valid_accessed": False,
            "source_scan": "PASS", "prefix_invariance": "PASS",
            "prediction_coverage": coverage, "account_reconciliation": "PASS",
            "evaluation_span": span, "report": str(report.relative_to(ROOT)),
            "standalone_score_uses_b00": False,
        })
        dump(run_path, metadata)
        print(f"[6/6] Complete: {report}", flush=True)
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
    args = parser.parse_args()
    run(args.config, args.output)
