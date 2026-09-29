"""One-candidate Train-only LightGBM experiment for breakout/momentum/volume."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
from datetime import datetime, timezone

import lightgbm
import numpy as np
import pandas as pd

from research import firewall
from research.evaluation import bootstrap_delta, daily_account, metrics
from research.experiments import breakout_side_momentum as side_helpers
from stock_comp_2026.strategies.dm_breakout_base_momentum_overlay import models as breakout_models
from stock_comp_2026.strategies.dm_breakout_base_momentum_overlay import features as breakout_features
from stock_comp_2026.strategies.dm_breakout_momentum_volume_lgbm import features, models


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DM-20260924-04"
EVAL_YEARS = (2011, 2012, 2013, 2014)
FIT_YEARS = (2010, 2011, 2012, 2013, 2014)
METHODS = ("H0", "B00", "LGBM_001")
COST_ONE_WAY = 0.001


def utc_now():
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


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_scan():
    strategy_dir = Path(features.__file__).parent
    paths = sorted(strategy_dir.glob("*.py"))
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
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("bfill", "backfill"):
                    raise AssertionError(f"Backfill call in {path}")
                if any(
                    key.arg == "center" and isinstance(key.value, ast.Constant)
                    and key.value.value for key in node.keywords
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
    changed = frame.copy()
    for column in changed:
        if not pd.api.types.is_numeric_dtype(changed[column]):
            continue
        if adjustment_factor and column == "AdjustmentFactor":
            changed.loc[future, column] = 1.25
        else:
            changed.loc[future, column] = changed.loc[future, column] * -3.14 + 888.0
    return changed


def mutate_panel_after(inputs, cutoff, truncate=False):
    result = {}
    for name, frame in inputs.items():
        result[name] = mutate_after(
            frame, cutoff, truncate=truncate,
            adjustment_factor=(name == "prices_daily_quotes"),
        )
    return result


def audit_prefix(inputs, target, original_features, original_breakout):
    paths = source_scan()
    dates = original_features.index.get_level_values("Date")
    calendar = dates.unique().sort_values()
    records = []
    for label in ("2010-12-30", "2012-06-29", "2014-12-30"):
        cutoff = pd.Timestamp(label)
        if cutoff not in calendar:
            raise AssertionError(f"Prefix cutoff absent from Train calendar: {label}")
        prefix = dates <= cutoff
        prefix_index = original_features.index[prefix]
        expected_features = original_features.loc[prefix_index]
        expected_breakout = original_breakout.loc[prefix_index]
        cutoff_position = calendar.get_loc(cutoff)
        probe_dates = calendar[max(0, cutoff_position - 2): cutoff_position + 1]
        probe = dates.isin(probe_dates)
        expected_model, _ = models.fit_before(
            original_features, target, calendar, cutoff
        )
        expected_prediction = pd.Series(
            expected_model.predict(original_features.loc[probe]),
            index=original_features.index[probe],
        )
        last_training_signal = None
        for mode in ("mutation", "truncation"):
            truncate = mode == "truncation"
            changed_inputs = mutate_panel_after(inputs, cutoff, truncate=truncate)
            changed_target = mutate_after(
                target.to_frame("Return"), cutoff, truncate=truncate
            )["Return"]
            changed_features = features.build_features(changed_inputs)
            changed_breakout = breakout_features.build_features(changed_inputs)
            pd.testing.assert_frame_equal(
                expected_features, changed_features.loc[prefix_index], check_exact=True
            )
            changed_h0 = models.smooth_by_listing(changed_features["res60s1"])
            original_h0 = models.smooth_by_listing(original_features["res60s1"])
            pd.testing.assert_series_equal(
                original_h0.loc[prefix_index], changed_h0.loc[prefix_index], check_exact=True
            )
            changed_b00 = breakout_models.generate_signal(changed_breakout, "B00")
            original_b00 = breakout_models.generate_signal(original_breakout, "B00")
            pd.testing.assert_series_equal(
                original_b00.loc[prefix_index], changed_b00.loc[prefix_index], check_exact=True
            )
            pd.testing.assert_frame_equal(
                expected_breakout.loc[:, ["res60s1", "new_high_excess", "new_low_excess"]],
                changed_breakout.loc[
                    prefix_index, ["res60s1", "new_high_excess", "new_low_excess"]
                ],
                check_exact=True,
            )
            actual_model, training_mask = models.fit_before(
                changed_features, changed_target, calendar, cutoff
            )
            changed_dates = changed_features.index.get_level_values("Date")
            changed_probe = changed_dates.isin(probe_dates)
            last_training_signal = changed_dates[training_mask].max()
            actual_prediction = pd.Series(
                actual_model.predict(changed_features.loc[changed_probe]),
                index=changed_features.index[changed_probe],
            )
            pd.testing.assert_series_equal(
                expected_prediction, actual_prediction, check_exact=True
            )
            if last_training_signal >= cutoff:
                raise AssertionError("A training label signal date reached the cutoff")
        last_position = calendar.get_loc(last_training_signal)
        records.append({
            "cutoff": label,
            "prefix_rows": int(prefix.sum()),
            "probe_rows": int(probe.sum()),
            "last_training_signal": str(last_training_signal.date()),
            "last_training_label_maturity": str(
                calendar[min(last_position + 2, len(calendar) - 1)].date()
            ),
            "mutation_and_truncation_features_signals_refits": "bitwise exact",
        })
    return {"status": "PASS", "source_files": paths, "prefix_tests": records}


def evaluation_dates(account_index):
    dates = pd.DatetimeIndex(account_index)
    selected = []
    for year in EVAL_YEARS:
        year_dates = dates[dates.year == year].unique().sort_values()
        if len(year_dates) <= 2:
            raise AssertionError(f"Insufficient dates for {year}")
        selected.extend(year_dates[:-2].tolist())
    return pd.DatetimeIndex(selected).sort_values()


def side_metrics(legs):
    result = {}
    for side in ("long", "short"):
        gross = legs[f"{side}_gross"]
        net = legs[f"{side}_net"]
        cost = legs[f"{side}_cost"]
        turnover = legs[f"{side}_turnover"]
        gross_std = gross.std(ddof=1)
        net_std = net.std(ddof=1)
        result[side] = {
            "gross_sharpe": float(gross.mean() / gross_std * np.sqrt(252))
            if gross_std > 0 else 0.0,
            "net_sharpe": float(net.mean() / net_std * np.sqrt(252))
            if net_std > 0 else 0.0,
            "annual_gross": float(gross.mean() * 252),
            "annual_net": float(net.mean() * 252),
            "annual_cost": float(cost.mean() * 252),
            "turnover": float(turnover.mean()),
        }
    return result


def leg_account(signal, target):
    from research.evaluation import weights

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
        cost = (COST_ONE_WAY * turnover).where(target.notna(), 0.0)
        result[f"{side}_gross"] = gross.groupby(level="Date").sum()
        result[f"{side}_cost"] = cost.groupby(level="Date").sum()
        result[f"{side}_turnover"] = turnover.groupby(level="Date").sum()
        result[f"{side}_net"] = result[f"{side}_gross"] - result[f"{side}_cost"]
    frame = pd.DataFrame(result)
    frame["net_sum"] = frame.long_net + frame.short_net
    return frame


def metric_bundle(account, legs):
    return {**metrics(account), "legs": side_metrics(legs.reindex(account.index))}


def build_report(output, summaries, fold_rows, model_audits, audit, metadata):
    report_dir = ROOT / "reports" / EXPERIMENT_ID
    report_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {EXPERIMENT_ID}: ブレイク・モメンタム・出来高変化 LightGBM",
        "",
        f"- Run ID: {output.name}",
        f"- 実行日時 (UTC): {metadata['completed_at_utc']}",
        "- Train splitのみ。Valid / Valid target / raw_targetは未使用。",
        "- 既読Valid分析後に着想した仮説で、Train期間も既知。候補選択・採用の根拠ではなく記述的なバックテスト。",
        "- 評価foldは2011–2014。各年末2取引日をtarget境界purge。2010は評価初年のturnover履歴を作るwarm-up。",
        "",
        "## 固定したモデル",
        "",
        "候補は一つだけ。特徴量はres60s1、prior-only split-safe 250観測新高値rank、新安値rank、split-safe raw Volumeの先行20観測median比rank。LightGBM回帰はmax_depth=2、num_leaves=4、60 trees、min_child_samples=500、learning_rate=0.05、reg_lambda=10、seed=20260924。毎年開始前に2営業日purgeした過去Train targetでexpanding-window fitし、出力へEWMA alpha=0.25を適用。特徴量・モデル・試行予算を結果後に変更しない。",
        "",
        "同日クロスセクションrankは、そのシグナル日の引け時点で利用可能な銘柄横断値。Long/Short損益は公式5分位weightの正負weightへの帰属。",
        "",
        "## Pooled 2011–2014",
        "",
        "| Strategy | Gross SR | Net SR | ΔNet SR vs H0 | ΔNet SR vs B00 | 年率Gross | 年率Net | 年率Cost | Turnover/日 | Long 年率Net / SR | Short 年率Net / SR | RankIC | HAC t | Hit | Q1–Q5 monotonicity | Max DD |",
        "|:---|---:|---:|---:|---:|---:|---:|---:|---:|:---|:---|---:|---:|---:|---:|---:|",
    ]
    lookup = {item["strategy"]: item for item in summaries}
    h0_sr = lookup["H0"]["pooled"]["net_sharpe"]
    b00_sr = lookup["B00"]["pooled"]["net_sharpe"]
    for name in METHODS:
        item = lookup[name]["pooled"]
        long, short = item["legs"]["long"], item["legs"]["short"]
        h0_delta = item["net_sharpe"] - h0_sr
        b00_delta = item["net_sharpe"] - b00_sr
        lines.append(
            f"| {name} | {item['gross_sharpe']:.4f} | {item['net_sharpe']:.4f} | "
            f"{h0_delta:+.4f} | {b00_delta:+.4f} | {item['annual_gross']:.2%} | "
            f"{item['annual_net']:.2%} | {item['annual_cost']:.2%} | {item['turnover']:.5f} | "
            f"{long['annual_net']:+.2%} / {long['net_sharpe']:.4f} | "
            f"{short['annual_net']:+.2%} / {short['net_sharpe']:.4f} | "
            f"{item['rankic']:.4f} | {item['rankic_t_hac5']:.3f} | "
            f"{item['rankic_hit']:.3f} | {item['q_monotonicity']:.3f} | "
            f"{item['max_drawdown_additive']:.2%} |"
        )
    lines += [
        "",
        "## 年別fold",
        "",
        "| Year | Strategy | Net SR | ΔNet SR vs H0 | ΔNet SR vs B00 | RankIC | Turnover | Annual Net | Long Net | Short Net |",
        "|:---:|:---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    baseline_by_year = {}
    for row in fold_rows:
        baseline_by_year.setdefault(row["year"], {})[row["strategy"]] = row
    for row in fold_rows:
        h0 = baseline_by_year[row["year"]]["H0"]["net_sharpe"]
        b00 = baseline_by_year[row["year"]]["B00"]["net_sharpe"]
        lines.append(
            f"| {row['year']} | {row['strategy']} | {row['net_sharpe']:.4f} | "
            f"{row['net_sharpe'] - h0:+.4f} | {row['net_sharpe'] - b00:+.4f} | "
            f"{row['rankic']:.4f} | {row['turnover']:.5f} | {row['annual_net']:+.2%} | "
            f"{row['long_annual_net']:+.2%} | {row['short_annual_net']:+.2%} |"
        )
    lines += [
        "",
        "## LGBM_001 paired comparison",
        "",
        "| Baseline | ΔNet SR | Fold improvement | Paired 20-day block-bootstrap 95% CI |",
        "|:---|---:|:---:|:---|",
    ]
    comp = lookup["LGBM_001"]["comparisons"]
    for baseline in ("H0", "B00"):
        stats = comp[baseline]
        lines.append(
            f"| {baseline} | {stats['delta_net_sharpe']:+.4f} | "
            f"{stats['improved_folds']}/4 | [{stats['bootstrap']['low']:+.4f}, "
            f"{stats['bootstrap']['high']:+.4f}] |"
        )
    lines += [
        "",
        "## 年次fit記録とgain importance",
        "",
        "| Model year | Train rows | Mature label through | Gain importance (features order: res60s1, new_high_rank, new_low_rank, relative_volume_change_rank) |",
        "|:---:|---:|:---|:---|",
    ]
    for item in model_audits:
        lines.append(
            f"| {item['year']} | {item['training_rows']} | {item['max_label_maturity_date']} | "
            f"{[round(v, 2) for v in item['importance_gain']]} |"
        )
    lines += [
        "",
        "## 結論と制約",
        "",
        "- 同じ評価日にH0、Breakout B00、LGBM_001を比較した。改善の一貫性、Long/Short別損益、cost・turnoverを合わせて判断する。全期間Train・既読期間なのでどの結果も独立確認ではない。",
        "- LightGBMの特徴量importanceは分岐利用の記述値で、経済的な寄与率や因果効果ではない。各featureの寄与をSharpe差から加法分解しない。",
        f"- Source scan / Train firewall / prefix-invariance: **{audit['status']}**。cutoffごとに特徴量・H0/B00信号・Train label再fit後の候補予測を、将来mutationとtruncationの双方でbitwise比較。",
        "- H0とB00との統計区間が0を含む場合は優越を主張しない。B00の既知結果には疎なscore同点がQ1/Q5へstable-index順に入る影響が含まれる。",
        "- run metadataにはコード/Train parquet hash、library version、seed、model parameters、firewall read list、年次fit上限を保存。",
        "",
        "2015–2016-03は以前に参照済みで、今回評価しなかった。Validも再読していない。結果を受けたモデル変更・追加探索・Valid閲覧は行わない。",
    ]
    path = report_dir / "REPORT.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run(config_path, output_path):
    started = time.monotonic()
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("Unexpected experiment id")
    if config.get("data_split") != "train" or config.get("valid_evaluation") is not False:
        raise ValueError("Train-only configuration required")
    if config.get("max_trials") != 1 or [trial["trial_id"] for trial in config["trials"]] != ["LGBM_001"]:
        raise ValueError("Only the one pre-registered candidate is allowed")
    output = Path(output_path)
    for path in (output / "models", output / "predictions", output / "metrics", output / "audit"):
        path.mkdir(parents=True, exist_ok=True)
    metadata_path = output / "run.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    code_paths = [
        Path(__file__).resolve(),
        Path(features.__file__).resolve(),
        Path(models.__file__).resolve(),
        Path(breakout_features.__file__).resolve(),
        Path(breakout_models.__file__).resolve(),
    ]
    metadata.update({
        "status": "running",
        "started_at_utc": utc_now(),
        "command": sys.argv,
        "actual_trials": 0,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "lightgbm": lightgbm.__version__,
        },
        "code_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in code_paths},
    })
    dump(metadata_path, metadata)
    try:
        firewall.install()
        data_dir = ROOT / "stock_comp_2026" / "input"
        input_names = list(features.INPUT_COLUMNS)
        metadata["train_data_sha256"] = {
            f"{name}_train.parquet": sha256(data_dir / f"{name}_train.parquet")
            for name in input_names
        }
        metadata["train_data_sha256"]["target_1day_train.parquet"] = sha256(
            data_dir / "target_1day_train.parquet"
        )
        print("[1/5] Loading Train features and target...", flush=True)
        inputs = features.load_inputs(data_dir, split="train")
        target = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index()
        if not target.index.is_unique:
            raise AssertionError("Target index is not unique")
        x = features.build_features(inputs)
        bx = breakout_features.build_features(inputs)
        if not x.index.equals(target.index) or not bx.index.equals(target.index):
            raise AssertionError("Feature/target index alignment failed")
        if tuple(x.columns) != features.FEATURE_COLUMNS:
            raise AssertionError("Feature contract changed")
        print("[2/5] Source firewall and prefix-invariance audit...", flush=True)
        causality = audit_prefix(inputs, target, x, bx)
        dump(output / "audit/causality.json", causality)
        firewall.save(output / "audit/firewall.json")
        print("[3/5] Fitting fixed annual walk-forward LightGBM models...", flush=True)
        raw_candidate, model_audits = models.walk_forward_predictions(
            x, target, years=FIT_YEARS, model_dir=output / "models"
        )
        candidate = pd.Series(float("nan"), index=x.index, name="LGBM_001")
        candidate.loc[raw_candidate.index] = raw_candidate
        candidate = models.smooth_by_listing(candidate, alpha=config["parameters"]["ewma_alpha"])
        h0 = models.smooth_by_listing(bx["res60s1"].rename("H0"))
        b00 = breakout_models.generate_signal(
            bx, "B00", alpha=config["parameters"]["ewma_alpha"],
        )
        signals = {"H0": h0, "B00": b00, "LGBM_001": candidate}
        eval_account_seed = daily_account(h0, target)
        dates = evaluation_dates(eval_account_seed.index)
        coverage = {}
        required_dates = target.index.get_level_values("Date").isin(dates)
        for name, signal in signals.items():
            signal = signal.reindex(target.index)
            signals[name] = signal
            values = signal.to_numpy()[required_dates]
            if not np.isfinite(values).all():
                raise AssertionError(f"Non-finite/missing signal coverage for {name}")
            coverage[name] = int(len(values))
        pred_frame = pd.DataFrame(signals, index=target.index).sort_index()
        pred_frame.to_parquet(output / "predictions/three_way.parquet")

        print("[4/5] Computing official-compatible daily accounts and fold metrics...", flush=True)
        accounts, legs_by_strategy = {}, {}
        for name, signal in signals.items():
            account = daily_account(signal, target)
            legs = side_helpers.leg_account(signal, target)
            legs_by_strategy[name] = legs
            discrepancy = (legs["net_sum"].reindex(account.index) - account["net"]).abs().max()
            if not np.isfinite(discrepancy) or discrepancy > 1e-10:
                raise AssertionError(f"Long+Short account does not reconcile for {name}: {discrepancy}")
            accounts[name] = account
            account.to_csv(output / f"metrics/daily_account_{name}.csv", index_label="Date")
            legs.to_csv(output / f"metrics/daily_legs_{name}.csv", index_label="Date")

        eval_set = set(dates)
        summaries = []
        fold_rows = []
        selected_accounts = {}
        for name in METHODS:
            account = accounts[name].loc[accounts[name].index.isin(eval_set)].copy()
            legs = legs_by_strategy[name].reindex(account.index)
            selected_accounts[name] = account
            pooled = metric_bundle(account, legs)
            periods = []
            for year in EVAL_YEARS:
                year_dates = [date for date in dates if date.year == year]
                part = account.loc[account.index.isin(year_dates)]
                part_legs = legs.reindex(part.index)
                bundle = metric_bundle(part, part_legs)
                periods.append({"year": year, "metrics": bundle})
                row = {"strategy": name, "year": year}
                row.update({key: value for key, value in bundle.items() if key != "legs"})
                for side in ("long", "short"):
                    row[f"{side}_annual_net"] = bundle["legs"][side]["annual_net"]
                    row[f"{side}_net_sharpe"] = bundle["legs"][side]["net_sharpe"]
                fold_rows.append(row)
            summaries.append({"strategy": name, "pooled": pooled, "periods": periods})

        summaries_by_name = {item["strategy"]: item for item in summaries}
        candidate_summary = summaries_by_name["LGBM_001"]
        candidate_account = selected_accounts["LGBM_001"]
        candidate_comparisons = {}
        for baseline in ("H0", "B00"):
            base = selected_accounts[baseline]
            common = base.index.intersection(candidate_account.index)
            deltas = []
            improved = 0
            for year in EVAL_YEARS:
                candidate_year = next(
                    item["metrics"]["net_sharpe"] for item in candidate_summary["periods"]
                    if item["year"] == year
                )
                baseline_year = next(
                    item["metrics"]["net_sharpe"] for item in summaries_by_name[baseline]["periods"]
                    if item["year"] == year
                )
                delta = candidate_year - baseline_year
                deltas.append(delta)
                improved += int(delta > 0)
            candidate_comparisons[baseline] = {
                "delta_net_sharpe": (
                    candidate_summary["pooled"]["net_sharpe"]
                    - summaries_by_name[baseline]["pooled"]["net_sharpe"]
                ),
                "fold_delta_net_sharpe": deltas,
                "improved_folds": improved,
                "bootstrap": bootstrap_delta(
                    base.loc[common, "net"], candidate_account.loc[common, "net"],
                    seed=config["random_seed"],
                    reps=config["parameters"]["bootstrap_repetitions"],
                    block=config["parameters"]["bootstrap_block_days"],
                ),
            }
        candidate_summary["comparisons"] = candidate_comparisons
        for item in summaries:
            if item["strategy"] != "LGBM_001":
                item["comparisons"] = {}
        for row in fold_rows:
            row["delta_net_sharpe_vs_H0"] = row["net_sharpe"] - next(
                item["net_sharpe"] for item in fold_rows
                if item["strategy"] == "H0" and item["year"] == row["year"]
            )
            row["delta_net_sharpe_vs_B00"] = row["net_sharpe"] - next(
                item["net_sharpe"] for item in fold_rows
                if item["strategy"] == "B00" and item["year"] == row["year"]
            )
        dump(output / "metrics/summary.json", summaries)
        pd.DataFrame(fold_rows).to_csv(output / "metrics/fold_metrics.csv", index=False)
        report_dir = ROOT / "reports" / EXPERIMENT_ID
        report_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(fold_rows).to_csv(report_dir / "fold_metrics.csv", index=False)
        comparison_rows = []
        for item in summaries:
            row = {"strategy": item["strategy"]}
            row.update({key: value for key, value in item["pooled"].items() if key != "legs"})
            for side in ("long", "short"):
                row[f"{side}_annual_net"] = item["pooled"]["legs"][side]["annual_net"]
                row[f"{side}_net_sharpe"] = item["pooled"]["legs"][side]["net_sharpe"]
            if item["strategy"] == "LGBM_001":
                for baseline, comp in item["comparisons"].items():
                    row[f"delta_net_sharpe_vs_{baseline}"] = comp["delta_net_sharpe"]
                    row[f"improved_folds_vs_{baseline}"] = comp["improved_folds"]
                    row[f"bootstrap_low_vs_{baseline}"] = comp["bootstrap"]["low"]
                    row[f"bootstrap_high_vs_{baseline}"] = comp["bootstrap"]["high"]
            comparison_rows.append(row)
        pd.DataFrame(comparison_rows).to_csv(output / "metrics/model_comparison.csv", index=False)
        pd.DataFrame(comparison_rows).to_csv(report_dir / "model_comparison.csv", index=False)
        dump(output / "audit/model_training.json", {
            "folds": model_audits,
            "prediction_coverage": coverage,
            "evaluation_days": len(dates),
            "purge_last_two_dates_per_year": True,
            "account_reconciliation": "PASS",
        })
        print("[5/5] Writing report and final run metadata...", flush=True)
        report_path = build_report(output, summaries, fold_rows, model_audits, causality, metadata)
        metadata.update({
            "status": "completed",
            "completed_at_utc": utc_now(),
            "elapsed_seconds": time.monotonic() - started,
            "actual_trials": 1,
            "valid_accessed": False,
            "source_scan": "PASS",
            "prefix_invariance": "PASS",
            "prediction_coverage": coverage,
            "account_reconciliation": "PASS",
            "report": str(report_path.relative_to(ROOT)),
        })
        dump(metadata_path, metadata)
        print(f"[Done] {report_path}", flush=True)
    except BaseException as error:
        metadata.update({
            "status": "failed",
            "completed_at_utc": utc_now(),
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
