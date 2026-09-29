"""One-candidate Train-only Ridge comparison on audited breakout/momentum/volume features."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from research import firewall
from research.evaluation import bootstrap_delta, daily_account, metrics, weights
from stock_comp_2026.strategies.dm_breakout_base_momentum_overlay import features as breakout_features
from stock_comp_2026.strategies.dm_breakout_base_momentum_overlay import models as breakout_models
from stock_comp_2026.strategies.dm_breakout_momentum_volume_linear import features, models
from stock_comp_2026.strategies.dm_breakout_momentum_volume_lgbm import features as audited_features


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DM-20260924-05"
FIT_YEARS = (2010, 2011, 2012, 2013, 2014)
EVAL_YEARS = (2011, 2012, 2013, 2014)
METHODS = ("H0", "B00", "LINEAR_001")
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
    paths = sorted(Path(features.__file__).parent.glob("*.py"))
    paths += [Path(audited_features.__file__), Path(breakout_features.__file__)]
    paths = sorted({path.resolve() for path in paths})
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


def mutate_after(frame, cutoff, truncate=False, adjustment_factor=False):
    dates = frame.index.get_level_values("Date")
    future = dates > cutoff
    if truncate:
        return frame.loc[~future].copy()
    result = frame.copy()
    for column in result:
        if not pd.api.types.is_numeric_dtype(result[column]):
            continue
        if adjustment_factor and column == "AdjustmentFactor":
            result.loc[future, column] = 1.25
        else:
            result.loc[future, column] = result.loc[future, column] * -3.14 + 888.0
    return result


def mutate_panel(inputs, cutoff, truncate=False):
    return {
        name: mutate_after(
            frame, cutoff, truncate=truncate,
            adjustment_factor=(name == "prices_daily_quotes"),
        )
        for name, frame in inputs.items()
    }


def audit_prefix(inputs, target, x, bx):
    scanned = source_scan()
    all_dates = x.index.get_level_values("Date")
    calendar = all_dates.unique().sort_values()
    records = []
    for label in ("2010-12-30", "2012-06-29", "2014-12-30"):
        cutoff = pd.Timestamp(label)
        if cutoff not in calendar:
            raise AssertionError(f"Missing Train cutoff: {label}")
        prefix_mask = all_dates <= cutoff
        prefix_index = x.index[prefix_mask]
        probe_dates = calendar[max(0, calendar.get_loc(cutoff) - 2): calendar.get_loc(cutoff) + 1]
        original_probe = all_dates.isin(probe_dates)
        expected_model, _ = models.fit_before(x, target, calendar, cutoff)
        expected_prediction = pd.Series(
            models.predict_matrix(x.loc[original_probe], expected_model),
            index=x.index[original_probe],
            name="prediction",
        )
        last_fit = None
        for mode in ("mutation", "truncation"):
            truncate = mode == "truncation"
            changed_inputs = mutate_panel(inputs, cutoff, truncate=truncate)
            changed_target = mutate_after(
                target.to_frame("Return"), cutoff, truncate=truncate
            )["Return"]
            changed_x = features.build_features(changed_inputs)
            changed_bx = breakout_features.build_features(changed_inputs)
            pd.testing.assert_frame_equal(
                x.loc[prefix_index], changed_x.loc[prefix_index], check_exact=True
            )
            for source, rebuilt in (
                (x["res60s1"], changed_x["res60s1"]),
                (bx["res60s1"], changed_bx["res60s1"]),
            ):
                expected_h0 = models.smooth_by_listing(source)
                actual_h0 = models.smooth_by_listing(rebuilt)
                pd.testing.assert_series_equal(
                    expected_h0.loc[prefix_index], actual_h0.loc[prefix_index], check_exact=True
                )
            base_b00 = breakout_models.generate_signal(bx, "B00")
            changed_b00 = breakout_models.generate_signal(changed_bx, "B00")
            pd.testing.assert_series_equal(
                base_b00.loc[prefix_index], changed_b00.loc[prefix_index], check_exact=True
            )
            changed_model, training_mask = models.fit_before(
                changed_x, changed_target, calendar, cutoff
            )
            changed_dates = changed_x.index.get_level_values("Date")
            changed_probe = changed_dates.isin(probe_dates)
            actual_prediction = pd.Series(
                models.predict_matrix(changed_x.loc[changed_probe], changed_model),
                index=changed_x.index[changed_probe],
                name="prediction",
            )
            pd.testing.assert_series_equal(
                expected_prediction, actual_prediction, check_exact=True
            )
            last_fit = changed_dates[training_mask].max()
            if last_fit >= cutoff:
                raise AssertionError("Ridge trained on a label at/after its cutoff")
        mature_through = calendar[min(calendar.get_loc(last_fit) + 2, len(calendar) - 1)]
        records.append({
            "cutoff": label,
            "prefix_rows": int(prefix_mask.sum()),
            "prediction_probe_rows": int(len(probe_dates)),
            "max_training_signal": str(last_fit.date()),
            "max_training_label_maturity": str(mature_through.date()),
            "mutation_and_truncation_feature_signal_refit": "bitwise exact",
        })
    return {"status": "PASS", "source_files": scanned, "cutoffs": records}


def selected_eval_dates(account_index):
    dates = pd.DatetimeIndex(account_index)
    result = []
    for year in EVAL_YEARS:
        values = dates[dates.year == year].unique().sort_values()
        if len(values) <= 2:
            raise AssertionError(f"Insufficient signal dates for {year}")
        result.extend(values[:-2].tolist())
    return pd.DatetimeIndex(result).sort_values()


def leg_account(signal, target):
    signal = signal.reindex(target.index).sort_index().fillna(0.0)
    target = target.reindex(signal.index)
    portfolio_weights, _ = weights(signal)
    result = {}
    for side, side_weights in (
        ("long", portfolio_weights.clip(lower=0.0)),
        ("short", portfolio_weights.clip(upper=0.0)),
    ):
        turnover = side_weights.groupby(level="Code").diff().abs().fillna(side_weights.abs())
        gross = side_weights * target
        cost = (ONE_WAY_COST * turnover).where(target.notna(), 0.0)
        result[f"{side}_gross"] = gross.groupby(level="Date").sum()
        result[f"{side}_cost"] = cost.groupby(level="Date").sum()
        result[f"{side}_turnover"] = turnover.groupby(level="Date").sum()
        result[f"{side}_net"] = result[f"{side}_gross"] - result[f"{side}_cost"]
    out = pd.DataFrame(result)
    out["net_sum"] = out.long_net + out.short_net
    return out


def side_metrics(legs):
    result = {}
    for side in ("long", "short"):
        gross = legs[f"{side}_gross"]
        net = legs[f"{side}_net"]
        cost = legs[f"{side}_cost"]
        turnover = legs[f"{side}_turnover"]
        gross_std, net_std = gross.std(ddof=1), net.std(ddof=1)
        result[side] = {
            "gross_sharpe": float(gross.mean() / gross_std * np.sqrt(252)) if gross_std > 0 else 0.0,
            "net_sharpe": float(net.mean() / net_std * np.sqrt(252)) if net_std > 0 else 0.0,
            "annual_gross": float(gross.mean() * 252),
            "annual_net": float(net.mean() * 252),
            "annual_cost": float(cost.mean() * 252),
            "turnover": float(turnover.mean()),
        }
    return result


def metric_bundle(account, legs):
    return {**metrics(account), "legs": side_metrics(legs.reindex(account.index))}


def build_report(output, summaries, folds, models_audit, audit, completion_time):
    directory = ROOT / "reports" / EXPERIMENT_ID
    directory.mkdir(parents=True, exist_ok=True)
    lookup = {item["strategy"]: item for item in summaries}
    h0_sr = lookup["H0"]["pooled"]["net_sharpe"]
    b00_sr = lookup["B00"]["pooled"]["net_sharpe"]
    lines = [
        f"# {EXPERIMENT_ID}: ブレイク・モメンタム・出来高変化 Ridge",
        "",
        f"- Run ID: {output.name}",
        f"- 実行完了 UTC: {completion_time}",
        "- Train splitのみ。Valid / Valid target / raw_targetは未使用。",
        "- 仮説は前回LightGBMの結果を受けた事後設計。全Trainも既知なので独立確認や採用判断に使わない。",
        "- 開発期間は2011–2014、各年末2取引日をpurge。2010はturnover warm-up。",
        "",
        "## 固定モデル",
        "",
        "前実験と同じ4特徴量を使用し、予測対象だけを日次cross-sectional centered percentile rankに変換。Ridge lambda=1.0、intercept無罰則。imputation mean / feature mean・stdは各foldの過去Trainだけでfit。年次expanding refit、EWMA alpha=0.25。試行候補は1つのみ。",
        "",
        "## Pooled 2011–2014",
        "",
        "| Strategy | Gross SR | Net SR | ΔNet SR vs H0 | ΔNet SR vs B00 | 年率Gross | 年率Net | 年率Cost | Turnover/日 | Long 年率Net / SR | Short 年率Net / SR | RankIC | HAC t | Hit | Q1–Q5 monotonicity | Max DD |",
        "|:---|---:|---:|---:|---:|---:|---:|---:|---:|:---|:---|---:|---:|---:|---:|---:|",
    ]
    for name in METHODS:
        p = lookup[name]["pooled"]
        long, short = p["legs"]["long"], p["legs"]["short"]
        lines.append(
            f"| {name} | {p['gross_sharpe']:.4f} | {p['net_sharpe']:.4f} | "
            f"{p['net_sharpe'] - h0_sr:+.4f} | {p['net_sharpe'] - b00_sr:+.4f} | "
            f"{p['annual_gross']:.2%} | {p['annual_net']:.2%} | {p['annual_cost']:.2%} | "
            f"{p['turnover']:.5f} | {long['annual_net']:+.2%} / {long['net_sharpe']:.4f} | "
            f"{short['annual_net']:+.2%} / {short['net_sharpe']:.4f} | {p['rankic']:.4f} | "
            f"{p['rankic_t_hac5']:.3f} | {p['rankic_hit']:.3f} | "
            f"{p['q_monotonicity']:.3f} | {p['max_drawdown_additive']:.2%} |"
        )
    lines += [
        "",
        "## Fold結果",
        "",
        "| Year | Strategy | Net SR | ΔNet SR vs H0 | ΔNet SR vs B00 | Annual Net | Long Net | Short Net | RankIC | Turnover |",
        "|:---:|:---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in folds:
        lines.append(
            f"| {row['year']} | {row['strategy']} | {row['net_sharpe']:.4f} | "
            f"{row['delta_vs_H0']:+.4f} | {row['delta_vs_B00']:+.4f} | "
            f"{row['annual_net']:+.2%} | {row['long_annual_net']:+.2%} | "
            f"{row['short_annual_net']:+.2%} | {row['rankic']:.4f} | {row['turnover']:.5f} |"
        )
    lines += [
        "",
        "## Paired comparison",
        "",
        "| Baseline | ΔNet SR | Improved folds | Paired 20-day block bootstrap 95% CI |",
        "|:---|---:|:---:|:---|",
    ]
    for baseline in ("H0", "B00"):
        comparison = lookup["LINEAR_001"]["comparisons"][baseline]
        ci = comparison["bootstrap"]
        lines.append(
            f"| {baseline} | {comparison['delta_net_sharpe']:+.4f} | "
            f"{comparison['improved_folds']}/4 | [{ci['low']:+.4f}, {ci['high']:+.4f}] |"
        )
    lines += [
        "",
        "## Annual coefficients",
        "",
        "| Model year | Train rows | Mature label through | Intercept | res60s1 | new_high_rank | new_low_rank | relative_volume_change_rank |",
        "|:---:|---:|:---|---:|---:|---:|---:|---:|",
    ]
    for item in models_audit:
        coeff = item["coefficients"]
        lines.append(
            f"| {item['year']} | {item['training_rows']} | {item['max_label_maturity_date']} | "
            + " | ".join(f"{value:+.5f}" for value in coeff)
            + " |"
        )
    lines += [
        "",
        "## 結論・制約",
        "",
        "- H0、B00、LINEAR_001は同じ日付・official portfolio weight・costで比較した。Net Sharpe、fold安定性、turnover/cost、RankIC、Long/Shortを合わせて読む。",
        "- 特徴量は前実験で監査した同一定義。目的変数rankは学習に使う成熟Train日だけ計算し、fit mean/std/imputationもfold訓練行のみから推定。",
        f"- Source scan / Train firewall / prefix-invariance / fit replay: **{audit['status']}**。3 cutoffで将来mutationとtruncation後のfeature・baseline signal・成熟ラベル再fit・候補予測をbitwise照合。",
        "- 全期間・仮説は既知データ上で選ばれている。計算上のbootstrap区間は独立OOSの代替ではない。候補は結果後に変更しない。",
        "- 2015–2016-03の既知Train参考値も今回未使用。Validは再読していない。",
    ]
    report = directory / "REPORT.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def run(config_path, output_path):
    started = time.monotonic()
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("Unexpected experiment id")
    if config.get("data_split") != "train" or config.get("valid_evaluation") is not False:
        raise ValueError("Train-only configuration required")
    if config.get("max_trials") != 1 or [item["trial_id"] for item in config["trials"]] != ["LINEAR_001"]:
        raise ValueError("Only the fixed linear model candidate is allowed")
    if (
        config["parameters"].get("ridge_lambda") != models.RIDGE_LAMBDA
        or config["parameters"].get("ewma_alpha") != 0.25
    ):
        raise ValueError("The Ridge penalty or smoothing differs from the pre-registered model")
    output = Path(output_path)
    for name in ("models", "predictions", "metrics", "audit"):
        (output / name).mkdir(parents=True, exist_ok=True)
    metadata_path = output / "run.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    source_paths = [
        Path(__file__).resolve(),
        Path(features.__file__).resolve(),
        Path(models.__file__).resolve(),
        Path(audited_features.__file__).resolve(),
        Path(breakout_features.__file__).resolve(),
        Path(breakout_models.__file__).resolve(),
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
        metadata["train_data_sha256"] = {
            f"{name}_train.parquet": digest(data_dir / f"{name}_train.parquet")
            for name in features.INPUT_COLUMNS
        }
        metadata["train_data_sha256"]["target_1day_train.parquet"] = digest(
            data_dir / "target_1day_train.parquet"
        )
        print("[1/5] Load Train feature panel and target...", flush=True)
        inputs = features.load_inputs(data_dir, split="train")
        target = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index()
        x = features.build_features(inputs)
        bx = breakout_features.build_features(inputs)
        if not x.index.equals(target.index) or not bx.index.equals(target.index):
            raise AssertionError("Feature/target index alignment failed")
        if list(x.columns) != list(models.FEATURE_COLUMNS):
            raise AssertionError("Linear feature order differs from the frozen config")
        print("[2/5] Source and prefix-invariance audits...", flush=True)
        audit = audit_prefix(inputs, target, x, bx)
        dump(output / "audit/causality.json", audit)
        firewall.save(output / "audit/firewall.json")
        print("[3/5] Fit expanding-window Ridge models...", flush=True)
        raw_candidate, model_records = models.walk_forward_predictions(
            x, target, years=FIT_YEARS, model_dir=output / "models"
        )
        replay, replay_records = models.walk_forward_predictions(x, target, years=FIT_YEARS)
        pd.testing.assert_series_equal(raw_candidate, replay, check_exact=True)
        candidate = pd.Series(float("nan"), index=x.index, name="LINEAR_001")
        candidate.loc[raw_candidate.index] = raw_candidate
        candidate = models.smooth_by_listing(candidate, alpha=config["parameters"]["ewma_alpha"])
        h0 = models.smooth_by_listing(bx["res60s1"].rename("H0"))
        b00 = breakout_models.generate_signal(
            bx, "B00", alpha=config["parameters"]["ewma_alpha"]
        )
        signals = {"H0": h0, "B00": b00, "LINEAR_001": candidate}
        eval_seed = daily_account(h0, target)
        eval_dates = selected_eval_dates(eval_seed.index)
        required = target.index.get_level_values("Date").isin(eval_dates)
        coverage = {}
        for name, signal in signals.items():
            signal = signal.reindex(target.index)
            signals[name] = signal
            observed = signal.to_numpy()[required]
            if not np.isfinite(observed).all():
                raise AssertionError(f"Nonfinite signal coverage: {name}")
            coverage[name] = int(len(observed))
        pd.DataFrame(signals, index=target.index).sort_index().to_parquet(
            output / "predictions/three_way.parquet"
        )

        print("[4/5] Score same-date baselines and fold metrics...", flush=True)
        accounts, leg_books = {}, {}
        for name, signal in signals.items():
            account = daily_account(signal, target)
            legs = leg_account(signal, target)
            difference = (legs.net_sum.reindex(account.index) - account.net).abs().max()
            if not np.isfinite(difference) or difference > 1e-10:
                raise AssertionError(f"Long/Short account mismatch for {name}: {difference}")
            accounts[name], leg_books[name] = account, legs
            account.to_csv(output / f"metrics/daily_account_{name}.csv", index_label="Date")
            legs.to_csv(output / f"metrics/daily_legs_{name}.csv", index_label="Date")
        eval_set = set(eval_dates)
        summaries, folds, period_accounts = [], [], {}
        for name in METHODS:
            account = accounts[name].loc[accounts[name].index.isin(eval_set)].copy()
            legs = leg_books[name].reindex(account.index)
            period_accounts[name] = account
            pooled = metric_bundle(account, legs)
            years = []
            for year in EVAL_YEARS:
                year_dates = [date for date in eval_dates if date.year == year]
                year_account = account.loc[account.index.isin(year_dates)]
                bundle = metric_bundle(year_account, legs.reindex(year_account.index))
                years.append({"year": year, "metrics": bundle})
                row = {"strategy": name, "year": year}
                row.update({key: value for key, value in bundle.items() if key != "legs"})
                for side in ("long", "short"):
                    row[f"{side}_annual_net"] = bundle["legs"][side]["annual_net"]
                    row[f"{side}_net_sharpe"] = bundle["legs"][side]["net_sharpe"]
                folds.append(row)
            summaries.append({"strategy": name, "pooled": pooled, "periods": years})

        summary_by = {item["strategy"]: item for item in summaries}
        candidate_summary = summary_by["LINEAR_001"]
        comparisons = {}
        for baseline in ("H0", "B00"):
            base_account = period_accounts[baseline]
            candidate_account = period_accounts["LINEAR_001"]
            common = base_account.index.intersection(candidate_account.index)
            fold_deltas = []
            for year in EVAL_YEARS:
                candidate_sr = next(
                    part["metrics"]["net_sharpe"] for part in candidate_summary["periods"]
                    if part["year"] == year
                )
                base_sr = next(
                    part["metrics"]["net_sharpe"] for part in summary_by[baseline]["periods"]
                    if part["year"] == year
                )
                fold_deltas.append(candidate_sr - base_sr)
            comparisons[baseline] = {
                "delta_net_sharpe": (
                    candidate_summary["pooled"]["net_sharpe"]
                    - summary_by[baseline]["pooled"]["net_sharpe"]
                ),
                "fold_delta_net_sharpe": fold_deltas,
                "improved_folds": int(sum(value > 0 for value in fold_deltas)),
                "bootstrap": bootstrap_delta(
                    base_account.loc[common, "net"],
                    candidate_account.loc[common, "net"],
                    seed=config["random_seed"],
                    reps=config["parameters"]["bootstrap_repetitions"],
                    block=config["parameters"]["bootstrap_block_days"],
                ),
            }
        candidate_summary["comparisons"] = comparisons
        for row in folds:
            row["delta_vs_H0"] = row["net_sharpe"] - next(
                item["net_sharpe"] for item in folds
                if item["strategy"] == "H0" and item["year"] == row["year"]
            )
            row["delta_vs_B00"] = row["net_sharpe"] - next(
                item["net_sharpe"] for item in folds
                if item["strategy"] == "B00" and item["year"] == row["year"]
            )
        dump(output / "metrics/summary.json", summaries)
        pd.DataFrame(folds).to_csv(output / "metrics/fold_metrics.csv", index=False)
        report_dir = ROOT / "reports" / EXPERIMENT_ID
        report_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(folds).to_csv(report_dir / "fold_metrics.csv", index=False)
        comparison_rows = []
        for item in summaries:
            row = {"strategy": item["strategy"]}
            row.update({key: value for key, value in item["pooled"].items() if key != "legs"})
            for side in ("long", "short"):
                row[f"{side}_annual_net"] = item["pooled"]["legs"][side]["annual_net"]
                row[f"{side}_net_sharpe"] = item["pooled"]["legs"][side]["net_sharpe"]
            if item["strategy"] == "LINEAR_001":
                for baseline, comp in item["comparisons"].items():
                    row[f"delta_net_sharpe_vs_{baseline}"] = comp["delta_net_sharpe"]
                    row[f"improved_folds_vs_{baseline}"] = comp["improved_folds"]
                    row[f"bootstrap_low_vs_{baseline}"] = comp["bootstrap"]["low"]
                    row[f"bootstrap_high_vs_{baseline}"] = comp["bootstrap"]["high"]
            comparison_rows.append(row)
        pd.DataFrame(comparison_rows).to_csv(
            output / "metrics/model_comparison.csv", index=False
        )
        pd.DataFrame(comparison_rows).to_csv(
            report_dir / "model_comparison.csv", index=False
        )
        dump(output / "audit/model_training.json", {
            "models": model_records,
            "deterministic_replay_bitwise": True,
            "prediction_coverage": coverage,
            "evaluation_days": len(eval_dates),
            "purge_last_two_dates_per_year": True,
            "account_reconciliation": "PASS",
        })
        print("[5/5] Save report and run metadata...", flush=True)
        completed = now_utc()
        report = build_report(output, summaries, folds, model_records, audit, completed)
        metadata.update({
            "status": "completed",
            "completed_at_utc": completed,
            "elapsed_seconds": time.monotonic() - started,
            "actual_trials": 1,
            "valid_accessed": False,
            "source_scan": "PASS",
            "prefix_invariance": "PASS",
            "deterministic_replay": "PASS",
            "prediction_coverage": coverage,
            "account_reconciliation": "PASS",
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
    args = parser.parse_args()
    run(args.config, args.output)
