"""Fixed two-model Train-only experiment for slope/range/volume features."""
import argparse
import ast
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import lightgbm
import numpy as np
import pandas as pd

from research import firewall
from research.evaluation import bootstrap_delta, daily_account, metrics, weights
from stock_comp_2026.strategies.dm_breakout_base_momentum_overlay import features as b00_features
from stock_comp_2026.strategies.dm_breakout_base_momentum_overlay import models as b00_models
from stock_comp_2026.strategies.dm_slope_range_volume_ml import features, models


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DM-20260924-06"
YEARS = tuple(range(2010, 2017))
KINDS = ("ridge", "lgbm")
METHOD_NAMES = {"ridge": "RIDGE_001", "lgbm": "LGBM_001"}
BASELINE_NAMES = ("H0", "B00")
ONE_WAY_COST = 0.001
CUTOFFS = ("2010-12-30", "2012-12-28", "2015-12-30")


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
    paths = [Path(features.__file__), Path(models.__file__)]
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


def _dates_of(frame):
    if isinstance(frame.index, pd.MultiIndex):
        return pd.DatetimeIndex(frame.index.get_level_values("Date"))
    return pd.DatetimeIndex(frame.index)


def mutate_after(frame, cutoff, truncate=False, is_prices=False):
    dates = _dates_of(frame)
    future = dates > pd.Timestamp(cutoff)
    if truncate:
        return frame.loc[~future].copy()
    result = frame.copy()
    for column in result:
        if not pd.api.types.is_numeric_dtype(result[column]):
            continue
        if is_prices and column == "AdjustmentFactor":
            result.loc[future, column] = 1.25
        else:
            result.loc[future, column] = result.loc[future, column] * -3.14 + 888.0
    return result


def mutate_inputs(inputs, cutoff, truncate=False):
    return {
        name: mutate_after(
            frame, cutoff, truncate=truncate,
            is_prices=(name == "prices_daily_quotes"),
        )
        for name, frame in inputs.items()
    }


def audit_prefix(inputs, target, x, bx):
    paths = source_scan()
    dates = x.index.get_level_values("Date")
    calendar = dates.unique().sort_values()
    records = []
    for label in CUTOFFS:
        cutoff = pd.Timestamp(label)
        if cutoff not in calendar:
            raise AssertionError(f"Train cutoff is absent: {label}")
        cutoff_position = calendar.get_loc(cutoff)
        if cutoff_position + 1 >= len(calendar):
            raise AssertionError(f"No post-cutoff prediction dates for {label}")
        probe_dates = calendar[max(0, cutoff_position - 1): cutoff_position + 1]
        probe_mask = dates.isin(probe_dates)
        prefix_mask = dates <= cutoff
        prefix_index = x.index[prefix_mask]
        expected_h0 = models.smooth_by_listing(bx["res60s1"].rename("H0"))
        expected_b00 = b00_models.generate_signal(bx, "B00", alpha=0.25)
        fold_start = calendar[cutoff_position + 1]
        by_model = {}
        for kind in KINDS:
            expected_model, expected_train, _ = models.fit_before(
                x, target, calendar, fold_start, kind
            )
            expected_prediction = pd.Series(
                models.predict_matrix(x.loc[probe_mask], expected_model),
                index=x.index[probe_mask], name=kind,
            )
            mode_records = []
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
                pd.testing.assert_series_equal(
                    expected_h0.loc[prefix_index],
                    models.smooth_by_listing(changed_bx["res60s1"].rename("H0")).loc[prefix_index],
                    check_exact=True,
                )
                pd.testing.assert_series_equal(
                    expected_b00.loc[prefix_index],
                    b00_models.generate_signal(changed_bx, "B00", alpha=0.25).loc[prefix_index],
                    check_exact=True,
                )
                changed_model, changed_train, _ = models.fit_before(
                    changed_x, changed_target, calendar, fold_start, kind
                )
                expected_training_index = x.index[expected_train]
                changed_training_index = changed_x.index[changed_train]
                if not expected_training_index.equals(changed_training_index):
                    raise AssertionError(f"Training mask changed under {mode}: {kind}, {label}")
                changed_dates = changed_x.index.get_level_values("Date")
                changed_probe = changed_dates.isin(probe_dates)
                actual_prediction = pd.Series(
                    models.predict_matrix(changed_x.loc[changed_probe], changed_model),
                    index=changed_x.index[changed_probe], name=kind,
                )
                pd.testing.assert_series_equal(
                    expected_prediction, actual_prediction, check_exact=True
                )
                mode_records.append(f"{mode}: bitwise exact")
            if label == CUTOFFS[-1]:
                replay, replay_train, _ = models.fit_before(x, target, calendar, fold_start, kind)
                if not np.array_equal(expected_train, replay_train):
                    raise AssertionError(f"Deterministic replay training mask changed: {kind}")
                replay_prediction = pd.Series(
                    models.predict_matrix(x.loc[probe_mask], replay),
                    index=x.index[probe_mask], name=kind,
                )
                pd.testing.assert_series_equal(expected_prediction, replay_prediction, check_exact=True)
            by_model[kind] = mode_records
        records.append({
            "cutoff": label,
            "prefix_rows": int(prefix_mask.sum()),
            "probe_dates": [str(value.date()) for value in probe_dates],
            "refit_start": str(pd.Timestamp(fold_start).date()),
            "feature_prefix_and_refit_predictions": by_model,
            "replay_bitwise_exact_at_final_cutoff": label == CUTOFFS[-1],
        })
    return {"status": "PASS", "source_files": paths, "cutoffs": records}


def evaluation_dates(account_index):
    dates = pd.DatetimeIndex(account_index)
    selected = []
    for year in YEARS:
        year_dates = dates[dates.year == year].unique().sort_values()
        if len(year_dates) <= 2:
            raise AssertionError(f"Insufficient dates in year fold {year}")
        selected.extend(year_dates[:-2].tolist())
    return pd.DatetimeIndex(selected).sort_values()


def leg_account(signal, target):
    signal = signal.reindex(target.index).sort_index().fillna(0.0)
    target = target.reindex(signal.index)
    portfolio_weights, _ = weights(signal)
    results = {}
    for side, side_weights in (
        ("long", portfolio_weights.clip(lower=0.0)),
        ("short", portfolio_weights.clip(upper=0.0)),
    ):
        turnover = side_weights.groupby(level="Code").diff().abs().fillna(side_weights.abs())
        gross = side_weights * target
        cost = (ONE_WAY_COST * turnover).where(target.notna(), 0.0)
        results[f"{side}_gross"] = gross.groupby(level="Date").sum()
        results[f"{side}_cost"] = cost.groupby(level="Date").sum()
        results[f"{side}_turnover"] = turnover.groupby(level="Date").sum()
        results[f"{side}_net"] = results[f"{side}_gross"] - results[f"{side}_cost"]
    account = pd.DataFrame(results)
    account["net_sum"] = account.long_net + account.short_net
    return account


def side_metrics(legs):
    result = {}
    for side in ("long", "short"):
        gross = legs[f"{side}_gross"]
        net = legs[f"{side}_net"]
        cost = legs[f"{side}_cost"]
        turnover = legs[f"{side}_turnover"]
        result[side] = {
            "gross_sharpe": float(gross.mean() / gross.std(ddof=1) * np.sqrt(252)) if gross.std(ddof=1) > 0 else 0.0,
            "net_sharpe": float(net.mean() / net.std(ddof=1) * np.sqrt(252)) if net.std(ddof=1) > 0 else 0.0,
            "annual_gross": float(gross.mean() * 252),
            "annual_net": float(net.mean() * 252),
            "annual_cost": float(cost.mean() * 252),
            "turnover": float(turnover.mean()),
        }
    return result


def metric_bundle(account, legs):
    return {**metrics(account), "legs": side_metrics(legs.reindex(account.index))}


def build_report(run_id, summaries, folds, training_records, audit, eval_span):
    report_dir = ROOT / "reports" / EXPERIMENT_ID
    report_dir.mkdir(parents=True, exist_ok=True)
    by_name = {item["strategy"]: item for item in summaries}
    lines = [
        f"# {EXPERIMENT_ID}: 60日傾き・52週レンジ位置・出来高zスコア",
        "",
        f"- Run ID: {run_id}",
        "- Train split only。Valid / Valid target / raw targetは未使用。",
        "- 全Train期間は以前に参照済み。全結果は記述評価で、独立OOSや採否根拠ではない。",
        f"- 利用可能なデータは2008-11-04〜2016-03-31。評価は{eval_span[0]}〜{eval_span[1]}、2016年は部分fold。",
        "- 各fold開始前にt+2ラベル境界のため2取引日をpurge。fold最後の2日とTrain全体最後の2日は評価から除外。",
        "",
        "## 固定特徴量とモデル",
        "",
        "- 傾き: t-60〜t-1のsplit-safe対数終値に対する等間隔OLS傾き、10,000倍でbp/日。",
        "- レンジ位置: t-1終値をt-251〜t-2の250観測High最大/Low最小へ線形写像。High=+1、Low=-1、範囲外はclipしない。",
        "- 出来高: t-1のsplit-safe raw Volumeをt-61〜t-2の60観測平均・母標準偏差でzスコア化。",
        "- Ridge lambda=1と固定浅型LightGBMを各1条件。日次centered percentile target、fold内fitのmean補完・標準化、EWMA alpha=0.25を共通適用。",
        "- 既存H0残差MomentumとB00ブレイクを同日比較。公式五分位weight、片道10bps cost。",
        "",
        "## Pooled評価",
        "",
        "| Strategy | Gross SR | Net SR | ΔNet SR vs H0 | ΔNet SR vs B00 | Annual Gross | Annual Net | Annual Cost | Turnover/day | Long Net/SR | Short Net/SR | RankIC | HAC t | Hit | Q monotonicity | Max DD |",
        "|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    h0_sr = by_name["H0"]["pooled"]["net_sharpe"]
    b00_sr = by_name["B00"]["pooled"]["net_sharpe"]
    for name in ("H0", "B00", "RIDGE_001", "LGBM_001"):
        p = by_name[name]["pooled"]
        long, short = p["legs"]["long"], p["legs"]["short"]
        lines.append(
            f"| {name} | {p['gross_sharpe']:.4f} | {p['net_sharpe']:.4f} | "
            f"{p['net_sharpe']-h0_sr:+.4f} | {p['net_sharpe']-b00_sr:+.4f} | "
            f"{p['annual_gross']:+.2%} | {p['annual_net']:+.2%} | {p['annual_cost']:.2%} | "
            f"{p['turnover']:.5f} | {long['annual_net']:+.2%}/{long['net_sharpe']:.3f} | "
            f"{short['annual_net']:+.2%}/{short['net_sharpe']:.3f} | {p['rankic']:+.4f} | "
            f"{p['rankic_t_hac5']:+.3f} | {p['rankic_hit']:.3f} | "
            f"{p['q_monotonicity']:+.3f} | {p['max_drawdown_additive']:+.2%} |"
        )
    lines += [
        "",
        "## 年別foldとbaseline差",
        "",
        "| Year | Strategy | Gross SR | Net SR | Δ vs H0 | Δ vs B00 | Annual Gross | Annual Net | Cost | Turnover | RankIC | HAC t | Hit | Q mono | Long Net | Short Net | Max DD |",
        "|---:|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in folds:
        lines.append(
            f"| {row['year']} | {row['strategy']} | {row['gross_sharpe']:.3f} | {row['net_sharpe']:.3f} | "
            f"{row['delta_net_sharpe_vs_H0']:+.3f} | {row['delta_net_sharpe_vs_B00']:+.3f} | "
            f"{row['annual_gross']:+.2%} | {row['annual_net']:+.2%} | {row['annual_cost']:.2%} | "
            f"{row['turnover']:.5f} | {row['rankic']:+.4f} | {row['rankic_t_hac5']:+.2f} | "
            f"{row['rankic_hit']:.3f} | {row['q_monotonicity']:+.2f} | "
            f"{row['legs']['long']['annual_net']:+.2%} | {row['legs']['short']['annual_net']:+.2%} | "
            f"{row['max_drawdown_additive']:+.2%} |"
        )
    lines += [
        "",
        "## Paired 20日 block bootstrap",
        "",
        "| Candidate | Baseline | Δ pooled Net SR | 95% CI | bootstrap positive fraction |",
        "|:---|:---|---:|:---|---:|",
    ]
    for candidate in ("RIDGE_001", "LGBM_001"):
        for baseline in BASELINE_NAMES:
            comp = by_name[candidate]["comparisons"][baseline]
            ci = comp["bootstrap"]
            lines.append(
                f"| {candidate} | {baseline} | {comp['delta_net_sharpe']:+.4f} | "
                f"[{ci['low']:+.4f}, {ci['high']:+.4f}] | {ci['bootstrap_positive_fraction']:.3f} |"
            )
    lines += [
        "",
        "## 年次係数・gain importance",
        "",
        "各foldの係数/gainはモデル内部の記述値で、経済的寄与や因果効果を示さない。",
        "",
        "| Model | Year | Training rows | Mature label through | Feature coefficients or gain importance |",
        "|:---|---:|---:|:---|:---|",
    ]
    for record in training_records:
        lines.append(
            f"| {record['kind'].upper()} | {record['year']} | {record['training_rows']} | "
            f"{record['max_training_label_maturity']} | "
            f"{json.dumps(record['feature_importance_or_coefficients'], ensure_ascii=False, sort_keys=True)} |"
        )
    lines += [
        "",
        "## 監査と制約",
        "",
        f"- Feature source scan / Train firewall / prefix-invariance / label refit checks: **{audit['status']}**.",
        "- Cutoff後のraw returns、beta、TOPIX、raw OHLCV、AdjustmentFactor、targetをmutationまたはtruncationし、特徴量prefixと2モデルrefit・直後予測がbitwise一致することを確認。最終cutoffで固定入力refitも再現。",
        "- Evaluation accountとLong+Short別Net P/Lを照合。全評価日でprediction coverageと有限値を確認。",
        "- 2015〜2016-03も以前に参照したTrain期間。改善があっても独立OOS・採用根拠とはせず、特徴量・パラメータを追加探索しない。",
        "- 年次fold全詳細、五分位日次リターン、価格範囲・モデルartifactは対応するCSV/JSONとrun directoryに保存。",
    ]
    path = report_dir / "REPORT.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run(config_path, output_path):
    started = time.monotonic()
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID or config.get("data_split") != "train":
        raise ValueError("Unexpected experiment or split configuration")
    if config.get("valid_evaluation") is not False or config.get("max_trials") != 2:
        raise ValueError("This driver is fixed to two Train-only candidates")
    if [trial["trial_id"] for trial in config["trials"]] != ["RIDGE_001", "LGBM_001"]:
        raise ValueError("Candidate order/budget differs from the registered plan")
    output = Path(output_path)
    for name in ("models", "predictions", "metrics", "audit"):
        (output / name).mkdir(parents=True, exist_ok=True)
    metadata_path = output / "run.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    source_paths = [Path(__file__).resolve(), Path(features.__file__).resolve(), Path(models.__file__).resolve(),
                    Path(b00_features.__file__).resolve(), Path(b00_models.__file__).resolve()]
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
            "lightgbm": lightgbm.__version__,
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
        data_hashes["target_1day_train.parquet"] = digest(data_dir / "target_1day_train.parquet")
        metadata["train_data_sha256"] = data_hashes
        dump(metadata_path, metadata)
        print("[1/6] Load Train inputs and construct fixed features...", flush=True)
        inputs = features.load_inputs(data_dir, split="train")
        target = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index()
        x = features.build_features(inputs)
        bx = b00_features.build_features(inputs)
        if not x.index.equals(target.index) or not bx.index.equals(target.index):
            raise AssertionError("Feature/target indexes are not exactly aligned")
        if list(x.columns) != list(models.FEATURE_COLUMNS):
            raise AssertionError("Feature columns differ from fixed model order")
        train_calendar = x.index.get_level_values("Date").unique().sort_values()
        if str(train_calendar.min().date()) != "2008-11-04" or str(train_calendar.max().date()) != "2016-03-31":
            raise AssertionError("Unexpected Train date span")

        print("[2/6] Source scan and future-mutation/truncation audits...", flush=True)
        audit = audit_prefix(inputs, target, x, bx)
        dump(output / "audit/causality.json", audit)
        firewall.save(output / "audit/firewall.json")

        print("[3/6] Fit annual expanding Ridge and LightGBM models...", flush=True)
        baseline_h0 = models.smooth_by_listing(bx["res60s1"].rename("H0"), alpha=0.25)
        baseline_b00 = b00_models.generate_signal(bx, "B00", alpha=0.25)
        signals = {"H0": baseline_h0.rename("H0"), "B00": baseline_b00.rename("B00")}
        training_records = []
        raw_predictions = {}
        for kind in KINDS:
            pred, records, models_by_year = models.walk_forward_predictions(
                x, target, kind, years=YEARS, model_dir=output / "models" / kind
            )
            raw_predictions[kind] = pred
            training_records.extend(records)
            candidate_name = METHOD_NAMES[kind]
            signal = pd.Series(np.nan, index=x.index, name=candidate_name)
            signal.loc[pred.index] = pred
            signals[candidate_name] = models.smooth_by_listing(signal, alpha=0.25)

        # Replay one complete, already-scored fold for each model to verify deterministic refitting.
        replay_year = 2016
        replay_start = pd.Timestamp(f"{replay_year}-01-01")
        replay_kind_checks = {}
        for kind in KINDS:
            replay_model, replay_mask, _ = models.fit_before(x, target, train_calendar, replay_start, kind)
            dates = x.index.get_level_values("Date")
            probe = dates.year == replay_year
            replay_values = pd.Series(
                models.predict_matrix(x.loc[probe], replay_model), index=x.index[probe], name=kind
            )
            pd.testing.assert_series_equal(
                replay_values,
                raw_predictions[kind].loc[replay_values.index].rename(kind),
                check_exact=True,
            )
            replay_kind_checks[kind] = {"bitwise_exact": True, "training_rows": int(replay_mask.sum())}

        seed_account = daily_account(signals["H0"], target)
        eval_dates = evaluation_dates(seed_account.index)
        target_dates = target.index.get_level_values("Date")
        required_rows = target_dates.isin(eval_dates)
        coverage = {}
        for name, signal in signals.items():
            aligned = signal.reindex(target.index)
            signals[name] = aligned
            observed = aligned.to_numpy()[required_rows]
            if len(observed) != int(required_rows.sum()) or not np.isfinite(observed).all():
                raise AssertionError(f"Incomplete or nonfinite evaluation signal: {name}")
            coverage[name] = int(len(observed))
        prediction_frame = pd.DataFrame(signals, index=target.index).sort_index()
        prediction_frame.to_parquet(output / "predictions/four_way.parquet")

        print("[4/6] Score same-date baselines and reconcile accounts...", flush=True)
        accounts, legs, bundles = {}, {}, {}
        for name, signal in signals.items():
            account = daily_account(signal, target)
            split_legs = leg_account(signal, target)
            gap = (split_legs.net_sum.reindex(account.index) - account.net).abs().max()
            if not np.isfinite(gap) or gap > 1e-10:
                raise AssertionError(f"Long/Short account reconciliation failed for {name}: {gap}")
            accounts[name], legs[name] = account, split_legs
            account.to_csv(output / f"metrics/daily_account_{name}.csv", index_label="Date")
            split_legs.to_csv(output / f"metrics/daily_legs_{name}.csv", index_label="Date")

        eval_set = set(eval_dates)
        summaries, fold_rows, selected_accounts = [], [], {}
        for name in ("H0", "B00", "RIDGE_001", "LGBM_001"):
            selected = accounts[name].loc[accounts[name].index.isin(eval_set)]
            selected_legs = legs[name].reindex(selected.index)
            selected_accounts[name] = selected
            pooled = metric_bundle(selected, selected_legs)
            periods = []
            for year in YEARS:
                year_set = [date for date in eval_dates if date.year == year]
                year_account = selected.loc[selected.index.isin(year_set)]
                year_legs = selected_legs.reindex(year_account.index)
                bundle = metric_bundle(year_account, year_legs)
                row = {"strategy": name, "year": int(year)}
                row.update({key: value for key, value in bundle.items() if key != "legs"})
                row["legs"] = bundle["legs"]
                fold_rows.append(row)
                periods.append({"year": int(year), "metrics": bundle})
            summaries.append({"strategy": name, "pooled": pooled, "periods": periods})

        summary_by = {item["strategy"]: item for item in summaries}
        for candidate in ("RIDGE_001", "LGBM_001"):
            comparisons = {}
            for baseline in BASELINE_NAMES:
                base_account = selected_accounts[baseline]
                candidate_account = selected_accounts[candidate]
                common = base_account.index.intersection(candidate_account.index)
                fold_delta = []
                for year in YEARS:
                    candidate_row = next(r for r in fold_rows if r["strategy"] == candidate and r["year"] == year)
                    baseline_row = next(r for r in fold_rows if r["strategy"] == baseline and r["year"] == year)
                    fold_delta.append(candidate_row["net_sharpe"] - baseline_row["net_sharpe"])
                comparisons[baseline] = {
                    "delta_net_sharpe": summary_by[candidate]["pooled"]["net_sharpe"] - summary_by[baseline]["pooled"]["net_sharpe"],
                    "fold_delta_net_sharpe": fold_delta,
                    "improved_folds": int(sum(value > 0 for value in fold_delta)),
                    "bootstrap": bootstrap_delta(
                        base_account.loc[common, "net"], candidate_account.loc[common, "net"],
                        seed=config["random_seed"], reps=config["parameters"]["bootstrap_repetitions"],
                        block=config["parameters"]["bootstrap_block_days"],
                    ),
                }
            summary_by[candidate]["comparisons"] = comparisons
        for row in fold_rows:
            row["delta_net_sharpe_vs_H0"] = row["net_sharpe"] - next(
                item["net_sharpe"] for item in fold_rows if item["strategy"] == "H0" and item["year"] == row["year"]
            )
            row["delta_net_sharpe_vs_B00"] = row["net_sharpe"] - next(
                item["net_sharpe"] for item in fold_rows if item["strategy"] == "B00" and item["year"] == row["year"]
            )

        print("[5/6] Save fold metrics, models and report...", flush=True)
        dump(output / "metrics/summary.json", summaries)
        dump(output / "audit/model_training.json", {
            "records": training_records,
            "deterministic_replay": replay_kind_checks,
            "prediction_coverage": coverage,
            "evaluation_days": len(eval_dates),
            "purge_last_two_dates_per_year": True,
            "account_reconciliation": "PASS",
        })
        pd.DataFrame([{key: value for key, value in row.items() if key != "legs"} for row in fold_rows]).to_csv(
            output / "metrics/fold_metrics.csv", index=False
        )
        report_dir = ROOT / "reports" / EXPERIMENT_ID
        report_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([{key: value for key, value in row.items() if key != "legs"} for row in fold_rows]).to_csv(
            report_dir / "fold_metrics.csv", index=False
        )
        comparison_rows = []
        for item in summaries:
            row = {"strategy": item["strategy"]}
            row.update({key: value for key, value in item["pooled"].items() if key != "legs"})
            for side in ("long", "short"):
                row[f"{side}_annual_net"] = item["pooled"]["legs"][side]["annual_net"]
                row[f"{side}_net_sharpe"] = item["pooled"]["legs"][side]["net_sharpe"]
            if item["strategy"] in ("RIDGE_001", "LGBM_001"):
                for baseline, comp in item["comparisons"].items():
                    row[f"delta_net_sharpe_vs_{baseline}"] = comp["delta_net_sharpe"]
                    row[f"improved_folds_vs_{baseline}"] = comp["improved_folds"]
                    row[f"bootstrap_low_vs_{baseline}"] = comp["bootstrap"]["low"]
                    row[f"bootstrap_high_vs_{baseline}"] = comp["bootstrap"]["high"]
            comparison_rows.append(row)
        pd.DataFrame(comparison_rows).to_csv(output / "metrics/model_comparison.csv", index=False)
        pd.DataFrame(comparison_rows).to_csv(report_dir / "model_comparison.csv", index=False)
        eval_span = (str(eval_dates.min().date()), str(eval_dates.max().date()))
        report = build_report(output.name, summaries, fold_rows, training_records, audit, eval_span)

        print("[6/6] Finalize metadata...", flush=True)
        firewall.save(output / "audit/firewall.json")
        accessed = json.loads((output / "audit/firewall.json").read_text(encoding="utf-8"))
        if any("_valid" in path or "raw_target" in path for path in accessed["opened_parquets"]):
            raise AssertionError("Firewall log contains a prohibited Train research input")
        completed = now_utc()
        metadata.update({
            "status": "completed",
            "completed_at_utc": completed,
            "elapsed_seconds": time.monotonic() - started,
            "actual_trials": 2,
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
    args = parser.parse_args()
    run(args.config, args.output)
