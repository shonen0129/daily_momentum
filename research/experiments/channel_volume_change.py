"""Fixed two-feature Ridge Train-only experiment."""
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
from research.experiments.slope_range_volume_ml import (
    CUTOFFS,
    YEARS,
    evaluation_dates,
    leg_account,
    metric_bundle,
    mutate_after,
    mutate_inputs,
)
from stock_comp_2026.strategies.dm_breakout_base_momentum_overlay import (
    features as b00_features,
    models as b00_models,
)
from stock_comp_2026.strategies.dm_breakout_side_momentum import features as breakout_features
from stock_comp_2026.strategies.dm_channel_volume_change import features, models
from stock_comp_2026.strategies.dm_slope_range_volume_ml import features as volume_feature_helpers


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DM-20260924-09"
METHODS = ("H0", "B00", "CHANNEL_250_001", "RIDGE_001")
BASELINES = ("H0", "B00", "CHANNEL_250_001")
SEED = 20260924
BOOTSTRAP_REPS = 1000
BOOTSTRAP_BLOCK = 20
ONE_WAY_COST = 0.001


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


def dump(path, value):
    Path(path).write_text(
        json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_scan():
    paths = [
        Path(features.__file__),
        Path(models.__file__),
        Path(volume_feature_helpers.__file__),
        Path(breakout_features.__file__),
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
            if any(
                key.arg == "center" and isinstance(key.value, ast.Constant) and key.value.value
                for key in node.keywords
            ):
                raise AssertionError(f"Centered rolling call in {path}")
            if node.func.attr == "shift":
                periods = node.args[0] if node.args else next(
                    (key.value for key in node.keywords if key.arg in ("periods", "period")),
                    None,
                )
                if isinstance(periods, ast.UnaryOp) and isinstance(periods.op, ast.USub):
                    raise AssertionError(f"Negative shift in {path}")
    return [str(path.relative_to(ROOT)) for path in paths]


def baseline_signals(inputs, channel_features):
    breakout = b00_features.build_features(inputs)
    h0 = models.smooth_by_listing(breakout["res60s1"].rename("H0"), alpha=0.25)
    b00 = b00_models.generate_signal(breakout, "B00", alpha=0.25)
    channel_raw = channel_features["channel_position_250"].fillna(0.0)
    channel = models.smooth_by_listing(channel_raw.rename("CHANNEL_250_001"), alpha=0.25)
    return {"H0": h0, "B00": b00, "CHANNEL_250_001": channel}, breakout


def audit_prefix(inputs, target, x, calendar):
    source_files = source_scan()
    dates = x.index.get_level_values("Date")
    records = []
    for label in CUTOFFS:
        cutoff = pd.Timestamp(label)
        if cutoff not in calendar:
            raise AssertionError(f"Train cutoff is absent: {label}")
        cutoff_position = calendar.get_loc(cutoff)
        fold_start = calendar[cutoff_position + 1]
        probes = calendar[max(0, cutoff_position - 1): cutoff_position + 1]
        prefix = dates <= cutoff
        prefix_index = x.index[prefix]
        expected_baselines, expected_bx = baseline_signals(inputs, x)
        expected_model, expected_mask, _ = models.fit_before(
            x, target, calendar, fold_start
        )
        expected_prediction = pd.Series(
            models.predict_matrix(x.loc[dates.isin(probes)], expected_model),
            index=x.index[dates.isin(probes)],
            name="RIDGE_001",
        )
        modes = {}
        for mode in ("mutation", "truncation"):
            truncate = mode == "truncation"
            changed_inputs = mutate_inputs(inputs, cutoff, truncate=truncate)
            changed_target = mutate_after(
                target.to_frame("Return"), cutoff, truncate=truncate
            )["Return"]
            changed_x = features.build_features(changed_inputs)
            changed_bx = b00_features.build_features(changed_inputs)
            pd.testing.assert_frame_equal(
                x.loc[prefix_index], changed_x.loc[prefix_index], check_exact=True
            )
            pd.testing.assert_frame_equal(
                expected_bx.loc[prefix_index], changed_bx.loc[prefix_index], check_exact=True
            )
            changed_baselines, _ = baseline_signals(changed_inputs, changed_x)
            for name in BASELINES:
                pd.testing.assert_series_equal(
                    expected_baselines[name].loc[prefix_index],
                    changed_baselines[name].loc[prefix_index],
                    check_exact=True,
                )
            changed_model, changed_mask, _ = models.fit_before(
                changed_x, changed_target, calendar, fold_start
            )
            if not x.index[expected_mask].equals(changed_x.index[changed_mask]):
                raise AssertionError(f"Training rows changed under {mode}: {label}")
            actual_dates = changed_x.index.get_level_values("Date")
            actual_probe = actual_dates.isin(probes)
            actual_prediction = pd.Series(
                models.predict_matrix(changed_x.loc[actual_probe], changed_model),
                index=changed_x.index[actual_probe],
                name="RIDGE_001",
            )
            pd.testing.assert_series_equal(
                expected_prediction, actual_prediction, check_exact=True
            )
            modes[mode] = "features, baselines, mature training rows and predictions bitwise exact"
        records.append({
            "cutoff": label,
            "fold_start": str(pd.Timestamp(fold_start).date()),
            "prefix_rows": int(prefix.sum()),
            "probe_dates": [str(value.date()) for value in probes],
            "checks": modes,
        })
    final_fold_start = pd.Timestamp("2016-01-01")
    replay, replay_mask, _ = models.fit_before(x, target, calendar, final_fold_start)
    selected = dates.year == 2016
    replay_prediction = pd.Series(
        models.predict_matrix(x.loc[selected], replay),
        index=x.index[selected],
        name="RIDGE_001",
    )
    expected_prediction = models.walk_forward_predictions(x, target, years=(2016,))[0]
    pd.testing.assert_series_equal(replay_prediction, expected_prediction, check_exact=True)
    return {
        "status": "PASS",
        "source_files": source_files,
        "cutoffs": records,
        "2016_deterministic_replay": {
            "bitwise_exact": True,
            "training_rows": int(replay_mask.sum()),
        },
    }


def build_report(run_id, summaries, folds, training_records, audit, eval_span):
    report_dir = ROOT / "reports" / EXPERIMENT_ID
    report_dir.mkdir(parents=True, exist_ok=True)
    lookup = {row["strategy"]: row for row in summaries}
    lines = [
        f"# {EXPERIMENT_ID}: 52週レンジ位置と前日出来高変化の2特徴Ridge",
        "",
        f"- Run ID: {run_id}",
        "- Train splitのみ。全Train期間は既知のため記述評価で、選択・採用根拠ではない。Valid/Valid target/raw targetは未使用。",
        f"- 評価期間: {eval_span[0]}〜{eval_span[1]}。2016年は部分fold。年境界・終端でt+2ラベルのため2取引日purge。",
        "- 特徴量: 前日終値のprior-only 250観測channel position、前日/2営業日前のsplit-safe raw Volume比から1を引いた変化率。",
        "- モデル: 日次centered percentile targetに対する年次expanding Ridge (lambda=1)、Train-only mean/std標準化・欠損補完、EWMA alpha=0.25。",
        "- 比較: H0、B00、および既存のchannel単独scoreを同じ日付・公式五分位weight・片道10bpsで比較。追加候補は1条件のみ。",
        "",
        "## Pooled結果",
        "",
        "| Strategy | Gross SR | Net SR | ΔNet SR vs H0 | ΔNet SR vs B00 | Annual Net | Cost | Turnover/day | RankIC | HAC t | Hit | Q monotonicity | Long Net | Short Net | Max DD |",
        "|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in METHODS:
        p = lookup[name]["pooled"]
        legs = p["legs"]
        lines.append(
            f"| {name} | {p['gross_sharpe']:.4f} | {p['net_sharpe']:.4f} | "
            f"{p['net_sharpe']-lookup['H0']['pooled']['net_sharpe']:+.4f} | "
            f"{p['net_sharpe']-lookup['B00']['pooled']['net_sharpe']:+.4f} | "
            f"{p['annual_net']:+.2%} | {p['annual_cost']:.2%} | {p['turnover']:.5f} | "
            f"{p['rankic']:+.4f} | {p['rankic_t_hac5']:+.3f} | {p['rankic_hit']:.3f} | "
            f"{p['q_monotonicity']:+.3f} | {legs['long']['annual_net']:+.2%} | "
            f"{legs['short']['annual_net']:+.2%} | {p['max_drawdown_additive']:+.2%} |"
        )
    lines += [
        "",
        "## 年別fold",
        "",
        "| Year | Strategy | Net SR | Δ vs H0 | Δ vs B00 | Annual Net | Cost | Turnover | RankIC | Q monotonicity | Long Net | Short Net | Max DD |",
        "|---:|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in folds:
        legs = row["legs"]
        lines.append(
            f"| {row['year']} | {row['strategy']} | {row['net_sharpe']:+.3f} | "
            f"{row['delta_net_sharpe_vs_H0']:+.3f} | {row['delta_net_sharpe_vs_B00']:+.3f} | "
            f"{row['annual_net']:+.2%} | {row['annual_cost']:.2%} | {row['turnover']:.5f} | "
            f"{row['rankic']:+.4f} | {row['q_monotonicity']:+.2f} | "
            f"{legs['long']['annual_net']:+.2%} | {legs['short']['annual_net']:+.2%} | "
            f"{row['max_drawdown_additive']:+.2%} |"
        )
    lines += [
        "",
        "## Paired 20日 block bootstrap",
        "",
        "| Baseline | Δ pooled Net SR | 95% CI | Positive fraction |",
        "|:---|---:|:---|---:|",
    ]
    for baseline, comparison in lookup["RIDGE_001"]["comparisons"].items():
        boot = comparison["bootstrap"]
        lines.append(
            f"| {baseline} | {comparison['delta_net_sharpe']:+.4f} | "
            f"[{boot['low']:+.4f}, {boot['high']:+.4f}] | "
            f"{boot['bootstrap_positive_fraction']:.3f} |"
        )
    lines += [
        "",
        "## 年次係数",
        "",
        "係数はfold内で標準化した特徴量に対する値。記述値であり因果効果や安定性の証明ではない。",
        "",
        "| Year | Training rows | Mature label through | Intercept | Channel coefficient | Volume-change coefficient |",
        "|---:|---:|:---|---:|---:|---:|",
    ]
    for record in training_records:
        coef = record["coefficients_intercept_channel_volume"]
        lines.append(
            f"| {record['year']} | {record['training_rows']} | "
            f"{record['max_training_label_maturity']} | {coef[0]:+.6g} | "
            f"{coef[1]:+.6g} | {coef[2]:+.6g} |"
        )
    lines += [
        "",
        "## 検証と制約",
        "",
        f"- Source scan / Train firewall / future-mutation・truncation prefix-invariance: **{audit['status']}**。",
        "- 全入力（raw_return、raw OHLCV、AdjustmentFactor、Train target）のcutoff後mutation/truncationで、特徴量、baseline、成熟training rows、直前予測がbitwise一致。",
        "- 年次foldのRidge再fitと予測再現、全評価行のcoverage、有限score、Long+Short会計照合を記録。",
        "- 全Trainは既知期間。成績は記述比較であり、独立OOS・採用・追加探索の根拠にしない。",
    ]
    report = report_dir / "REPORT.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def run(config_path, output_path):
    started = time.monotonic()
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if (
        config.get("experiment_id") != EXPERIMENT_ID
        or config.get("data_split") != "train"
        or config.get("valid_evaluation") is not False
        or config.get("selection_eligible") is not False
        or config.get("max_trials") != 1
        or [trial["trial_id"] for trial in config.get("trials", [])] != ["RIDGE_001"]
    ):
        raise ValueError("Unexpected scope or candidate budget")
    output = Path(output_path)
    for name in ("models", "predictions", "metrics", "audit"):
        (output / name).mkdir(parents=True, exist_ok=True)
    metadata_path = output / "run.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    source_paths = [
        Path(__file__).resolve(),
        Path(features.__file__).resolve(),
        Path(models.__file__).resolve(),
        Path(volume_feature_helpers.__file__).resolve(),
        Path(breakout_features.__file__).resolve(),
        Path(b00_features.__file__).resolve(),
        Path(b00_models.__file__).resolve(),
    ]
    metadata.update({
        "status": "running",
        "started_at_utc": now_utc(),
        "command": sys.argv,
        "actual_trials": 0,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "code_sha256": {str(path.relative_to(ROOT)): digest(path) for path in source_paths},
    })
    dump(metadata_path, metadata)
    try:
        firewall.install()
        data_dir = ROOT / "stock_comp_2026" / "input"
        data_hashes = {
            f"{name}_train.parquet": digest(data_dir / f"{name}_train.parquet")
            for name in features.INPUT_COLUMNS
        }
        data_hashes["target_1day_train.parquet"] = digest(
            data_dir / "target_1day_train.parquet"
        )
        metadata["train_data_sha256"] = data_hashes
        dump(metadata_path, metadata)

        print("[1/6] Load Train-only inputs and construct the fixed two-feature matrix...", flush=True)
        inputs = features.load_inputs(data_dir, split="train")
        target = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index()
        x = features.build_features(inputs)
        bx = b00_features.build_features(inputs)
        if not x.index.equals(target.index) or not bx.index.equals(target.index):
            raise AssertionError("Feature/target indexes are not exactly aligned")
        if tuple(x.columns) != models.FEATURE_COLUMNS:
            raise AssertionError("Unexpected feature names or order")
        calendar = x.index.get_level_values("Date").unique().sort_values()
        if str(calendar.min().date()) != "2008-11-04" or str(calendar.max().date()) != "2016-03-31":
            raise AssertionError("Unexpected Train date span")

        print("[2/6] Run source scan and causal prefix audits...", flush=True)
        audit = audit_prefix(inputs, target, x, calendar)
        dump(output / "audit/causality.json", audit)
        firewall.save(output / "audit/firewall.json")

        print("[3/6] Fit one annual expanding-window Ridge candidate...", flush=True)
        baselines, _ = baseline_signals(inputs, x)
        signals = {name: series.rename(name) for name, series in baselines.items()}
        raw_prediction, training_records, year_models = models.walk_forward_predictions(
            x, target, years=YEARS, model_dir=output / "models"
        )
        candidate = pd.Series(np.nan, index=x.index, name="RIDGE_001")
        candidate.loc[raw_prediction.index] = raw_prediction
        signals["RIDGE_001"] = models.smooth_by_listing(candidate, alpha=0.25)

        # Refit the final fold to confirm deterministic model and prediction output.
        final_model, final_mask, _ = models.fit_before(
            x, target, calendar, pd.Timestamp("2016-01-01")
        )
        final_dates = x.index.get_level_values("Date").year == 2016
        final_replay = pd.Series(
            models.predict_matrix(x.loc[final_dates], final_model),
            index=x.index[final_dates],
            name="RIDGE_001",
        )
        pd.testing.assert_series_equal(
            raw_prediction.loc[final_replay.index], final_replay, check_exact=True
        )

        account_seed = daily_account(signals["H0"], target)
        eval_dates = evaluation_dates(account_seed.index)
        date_values = target.index.get_level_values("Date")
        required_rows = date_values.isin(eval_dates)
        coverage = {}
        for name, signal in signals.items():
            aligned = signal.reindex(target.index)
            signals[name] = aligned
            observed = aligned.to_numpy()[required_rows]
            if len(observed) != int(required_rows.sum()) or not np.isfinite(observed).all():
                raise AssertionError(f"Incomplete or nonfinite evaluation signal: {name}")
            coverage[name] = int(len(observed))
        pd.DataFrame(signals, index=target.index).sort_index().to_parquet(
            output / "predictions/signals.parquet"
        )

        print("[4/6] Score same-date portfolios and reconcile Long/Short accounting...", flush=True)
        accounts, legs = {}, {}
        for name, signal in signals.items():
            account = daily_account(signal, target)
            split_legs = leg_account(signal, target)
            gap = (split_legs.net_sum.reindex(account.index) - account.net).abs().max()
            if not np.isfinite(gap) or gap > 1e-10:
                raise AssertionError(f"Long/Short accounting mismatch for {name}: {gap}")
            accounts[name], legs[name] = account, split_legs
            account.to_csv(output / f"metrics/daily_account_{name}.csv", index_label="Date")
            split_legs.to_csv(output / f"metrics/daily_legs_{name}.csv", index_label="Date")

        eval_set = set(eval_dates)
        summaries, folds, selected_accounts = [], [], {}
        for name in METHODS:
            selected = accounts[name].loc[accounts[name].index.isin(eval_set)]
            selected_legs = legs[name].reindex(selected.index)
            selected_accounts[name] = selected
            pooled = metric_bundle(selected, selected_legs)
            periods = []
            for year in YEARS:
                year_set = [date for date in eval_dates if date.year == year]
                year_account = selected.loc[selected.index.isin(year_set)]
                bundle = metric_bundle(year_account, selected_legs.reindex(year_account.index))
                row = {"strategy": name, "year": int(year)}
                row.update({key: value for key, value in bundle.items() if key != "legs"})
                row["legs"] = bundle["legs"]
                folds.append(row)
                periods.append({"year": int(year), "metrics": bundle})
            summaries.append({"strategy": name, "pooled": pooled, "periods": periods})

        summary_by = {row["strategy"]: row for row in summaries}
        candidate_row = summary_by["RIDGE_001"]
        candidate_comparisons = {}
        for baseline in BASELINES:
            base_account = selected_accounts[baseline]
            cand_account = selected_accounts["RIDGE_001"]
            common = base_account.index.intersection(cand_account.index)
            fold_deltas = []
            for year in YEARS:
                cand = next(row for row in folds if row["strategy"] == "RIDGE_001" and row["year"] == year)
                base = next(row for row in folds if row["strategy"] == baseline and row["year"] == year)
                fold_deltas.append(cand["net_sharpe"] - base["net_sharpe"])
            candidate_comparisons[baseline] = {
                "delta_net_sharpe": candidate_row["pooled"]["net_sharpe"] - summary_by[baseline]["pooled"]["net_sharpe"],
                "fold_delta_net_sharpe": fold_deltas,
                "improved_folds": int(sum(value > 0 for value in fold_deltas)),
                "bootstrap": bootstrap_delta(
                    base_account.loc[common, "net"],
                    cand_account.loc[common, "net"],
                    seed=SEED,
                    reps=BOOTSTRAP_REPS,
                    block=BOOTSTRAP_BLOCK,
                ),
            }
        candidate_row["comparisons"] = candidate_comparisons
        for row in folds:
            for baseline in ("H0", "B00"):
                base = next(
                    item for item in folds
                    if item["strategy"] == baseline and item["year"] == row["year"]
                )
                row[f"delta_net_sharpe_vs_{baseline}"] = row["net_sharpe"] - base["net_sharpe"]

        print("[5/6] Save full metrics, artifacts and report...", flush=True)
        dump(output / "metrics/summary.json", summaries)
        dump(output / "audit/model_training.json", {
            "records": training_records,
            "deterministic_replay": {
                "year": 2016,
                "bitwise_exact": True,
                "training_rows": int(final_mask.sum()),
            },
            "prediction_coverage": coverage,
            "evaluation_days": len(eval_dates),
            "purge_last_two_dates_per_year": True,
            "account_reconciliation": "PASS",
        })
        flat_folds = [{key: value for key, value in row.items() if key != "legs"} for row in folds]
        pd.DataFrame(flat_folds).to_csv(output / "metrics/fold_metrics.csv", index=False)
        report_dir = ROOT / "reports" / EXPERIMENT_ID
        report_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(flat_folds).to_csv(report_dir / "fold_metrics.csv", index=False)
        comparison_rows = []
        for row in summaries:
            item = {"strategy": row["strategy"]}
            item.update({key: value for key, value in row["pooled"].items() if key != "legs"})
            for side in ("long", "short"):
                item[f"{side}_annual_net"] = row["pooled"]["legs"][side]["annual_net"]
                item[f"{side}_net_sharpe"] = row["pooled"]["legs"][side]["net_sharpe"]
            if row["strategy"] == "RIDGE_001":
                for baseline, comparison in row["comparisons"].items():
                    item[f"delta_net_sharpe_vs_{baseline}"] = comparison["delta_net_sharpe"]
                    item[f"improved_folds_vs_{baseline}"] = comparison["improved_folds"]
                    item[f"bootstrap_low_vs_{baseline}"] = comparison["bootstrap"]["low"]
                    item[f"bootstrap_high_vs_{baseline}"] = comparison["bootstrap"]["high"]
            comparison_rows.append(item)
        pd.DataFrame(comparison_rows).to_csv(output / "metrics/model_comparison.csv", index=False)
        pd.DataFrame(comparison_rows).to_csv(report_dir / "model_comparison.csv", index=False)
        eval_span = (str(eval_dates.min().date()), str(eval_dates.max().date()))
        report = build_report(
            output.name, summaries, folds, training_records, audit, eval_span
        )

        print("[6/6] Finalize run metadata...", flush=True)
        firewall.save(output / "audit/firewall.json")
        accessed = json.loads((output / "audit/firewall.json").read_text(encoding="utf-8"))
        if any("_valid" in path or "raw_target" in path for path in accessed["opened_parquets"]):
            raise AssertionError("Firewall log contains a prohibited research input")
        metadata.update({
            "status": "completed",
            "completed_at_utc": now_utc(),
            "elapsed_seconds": time.monotonic() - started,
            "actual_trials": 1,
            "valid_accessed": False,
            "source_scan": "PASS",
            "prefix_invariance": "PASS",
            "deterministic_replay": "PASS",
            "prediction_coverage": coverage,
            "account_reconciliation": "PASS",
            "evaluation_span": eval_span,
            "report": str(report.relative_to(ROOT)),
        })
        dump(metadata_path, metadata)
        print(f"[Done] {report}", flush=True)
    except BaseException as error:
        metadata.update({
            "status": "failed",
            "completed_at_utc": now_utc(),
            "elapsed_seconds": time.monotonic() - started,
            "failure": repr(error),
        })
        try:
            firewall.save(output / "audit/firewall.json")
        except BaseException:
            pass
        dump(metadata_path, metadata)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    run(arguments.config, arguments.output)
