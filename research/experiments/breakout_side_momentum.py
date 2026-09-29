"""Bounded Train-only backtest for independent Long/Short breakout toggles."""
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
from stock_comp_2026.strategies.dm_breakout_side_momentum import features, models
from stock_comp_2026.strategies.dm_high_proximity_momentum import features as reference_features
from stock_comp_2026.strategies.dm_high_proximity_momentum import models as reference_models

ROOT = Path(__file__).resolve().parents[2]
TRIALS = ("M00", "H10", "L01", "HL11")


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
    """Reject banned data paths and common noncausal source constructs."""
    source_root = Path(features.__file__).parent
    paths = sorted(source_root.glob("*.py"))
    forbidden = (
        "AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose",
        "AdjustmentVolume", "raw_target", "target_1day_valid",
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                raise AssertionError(f"Forbidden token {token} in {path}")
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("bfill", "backfill"):
                    raise AssertionError(f"Backfill call in {path}")
                if any(
                    key.arg == "center" and isinstance(key.value, ast.Constant) and key.value.value
                    for key in node.keywords
                ):
                    raise AssertionError(f"Centered rolling call in {path}")
                if any(
                    key.arg == "direction" and isinstance(key.value, ast.Constant)
                    and key.value.value == "forward" for key in node.keywords
                ):
                    raise AssertionError(f"Forward join in {path}")
    return [str(path.relative_to(ROOT)) for path in paths]


def mutate_after(inputs, cutoff, truncate=False):
    mutated = {}
    for name, frame in inputs.items():
        dates = frame.index.get_level_values("Date")
        if dates.tz is not None:
            dates = dates.tz_localize(None)
        future = dates > cutoff
        if truncate:
            mutated[name] = frame.loc[~future].copy()
            continue
        changed = frame.copy()
        for column in changed:
            if isinstance(changed[column].dtype, pd.CategoricalDtype):
                changed[column] = changed[column].astype(str)
            if pd.api.types.is_numeric_dtype(changed[column]):
                if name == "prices_daily_quotes" and column == "AdjustmentFactor":
                    changed.loc[future, column] = 1.0
                    future_dates = dates[future]
                    if len(future_dates):
                        first_future = future_dates.min()
                        changed.loc[future & (dates == first_future), column] = 0.25
                else:
                    changed.loc[future, column] = changed.loc[future, column] * -3.14 + 888.0
            elif pd.api.types.is_datetime64_any_dtype(changed[column]):
                changed.loc[future, column] = pd.Timestamp("1990-01-01")
            else:
                changed.loc[future, column] = "future_mutation"
        mutated[name] = changed
    return mutated


def audit_prefix_invariance(inputs, original_features):
    source_files = source_scan()
    records = []
    for label in ("2010-12-30", "2012-06-29", "2014-12-30"):
        cutoff = pd.Timestamp(label)
        dates = original_features.index.get_level_values("Date")
        prefix_index = original_features.index[dates <= cutoff]
        expected = original_features.loc[prefix_index]
        for mode in ("mutation", "truncation"):
            changed_inputs = mutate_after(inputs, cutoff, truncate=(mode == "truncation"))
            changed_features = features.build_features(changed_inputs)
            pd.testing.assert_frame_equal(
                expected, changed_features.loc[prefix_index], check_exact=True
            )
            for trial_id in TRIALS:
                expected_signal = models.generate_signal(original_features, trial_id).loc[prefix_index]
                actual_signal = models.generate_signal(changed_features, trial_id).loc[prefix_index]
                pd.testing.assert_series_equal(expected_signal, actual_signal, check_exact=True)
        records.append({"cutoff": label, "rows": len(prefix_index), "bitwise": True})
    return {"status": "PASS", "source_files": source_files, "prefix_tests": records}


def leg_account(signal, target):
    """Return long/short gross, net, side costs and turnover under shared weights."""
    signal = signal.reindex(target.index).sort_index().fillna(0.0)
    target = target.reindex(signal.index)
    portfolio_weights, _ = weights(signal)
    long_w = portfolio_weights.where(portfolio_weights > 0.0, 0.0)
    short_w = portfolio_weights.where(portfolio_weights < 0.0, 0.0)
    long_turn = long_w.groupby(level="Code").diff().abs().fillna(long_w.abs())
    short_turn = short_w.groupby(level="Code").diff().abs().fillna(short_w.abs())
    long_gross = long_w * target
    short_gross = short_w * target
    observed = target.notna()
    long_cost = (0.001 * long_turn).where(observed, 0.0)
    short_cost = (0.001 * short_turn).where(observed, 0.0)
    by_date = lambda values: values.groupby(level="Date").sum()
    result = pd.DataFrame({
        "long_gross": by_date(long_gross),
        "short_gross": by_date(short_gross),
        "long_cost": by_date(long_cost),
        "short_cost": by_date(short_cost),
        "long_turnover": by_date(long_turn),
        "short_turnover": by_date(short_turn),
    })
    result["long_net"] = result.long_gross - result.long_cost
    result["short_net"] = result.short_gross - result.short_cost
    result["net_sum"] = result.long_net + result.short_net
    return result


def side_metrics(account):
    def sharpe(values):
        values = np.asarray(values, dtype=float)
        std = np.std(values, ddof=1) if len(values) > 1 else 0.0
        return float(np.mean(values) / std * np.sqrt(252)) if std > 0 else 0.0

    def stats(prefix):
        net = account[f"{prefix}_net"]
        gross = account[f"{prefix}_gross"]
        cost = account[f"{prefix}_cost"]
        turnover = account[f"{prefix}_turnover"]
        cumulative = np.r_[0.0, net.cumsum().to_numpy()]
        drawdown = cumulative - np.maximum.accumulate(cumulative)
        return {
            "gross_sharpe": sharpe(gross),
            "net_sharpe": sharpe(net),
            "annual_gross": float(gross.mean() * 252),
            "annual_net": float(net.mean() * 252),
            "annual_cost": float(cost.mean() * 252),
            "turnover": float(turnover.mean()),
            "max_drawdown_additive": float(drawdown.min()),
        }
    return {"long": stats("long"), "short": stats("short")}


def select_window(account, start, end, purge_last=2):
    date_index = pd.DatetimeIndex(account.index)
    mask = (date_index >= pd.Timestamp(start)) & (date_index <= pd.Timestamp(end))
    chosen_dates = date_index[mask].unique().sort_values()
    if purge_last:
        chosen_dates = chosen_dates[:-purge_last]
    return account.loc[account.index.isin(chosen_dates)].copy()


def combined_years(account, years):
    pieces = [select_window(account, f"{year}-01-01", f"{year}-12-31") for year in years]
    return pd.concat(pieces).sort_index()


def metric_bundle(account, legs):
    total = metrics(account)
    sides = side_metrics(legs.reindex(account.index))
    return {**total, "legs": sides}


def build_report(config, run_id, summaries, audit, run_metadata):
    report = ROOT / "reports" / config["experiment_id"] / "REPORT.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    by_id = {item["trial_id"]: item for item in summaries}
    baseline = by_id["M00"]
    lines = [
        f"# {config['experiment_id']}: Long/Short別ブレイク・モメンタム比較",
        "",
        f"- Run ID: `{run_id}`",
        f"- 実行日時 (UTC): {run_metadata['completed_at_utc']}",
        "- 入力: Train splitのみ。Valid/Valid target/raw_targetは読まず、Valid評価なし。",
        "- 解釈範囲: 既知Trainを使い、既読Validの結果を見た後に立てた仮説の事後・記述的比較。独立な確認、採用根拠にはしない。",
        "- 期間: 2011〜2014年は開発fold。各期間末の2取引日をtarget horizon境界purge。2015-01〜2016-03は過去に見た参考期間のみ。",
        "",
        "## 固定した4パターン",
        "",
        "| ID | Long新高値 | Short新安値 | 定義 |",
        "|:---|:---:|:---:|:---|",
        "| M00 | off | off | res60s1のみ（H0基準） |",
        "| H10 | on | off | Long側だけMomentum rankと新高値rankを50/50合成 |",
        "| L01 | off | on | Short側だけMomentum rankと新安値rankを50/50合成 |",
        "| HL11 | on | on | Long/Shortを独立に両方有効 |",
        "",
        "新高値は`t`終値が`t-1`から遡る250有効観測のsplit-safe raw High最大値を上回る幅、新安値は`t`終値が同じく過去250観測のsplit-safe raw Low最小値を下回る幅。現在日High/Lowは障壁に入れず、250行未満は当該legのMomentumへ戻す。正のMomentum行だけLong合成、負のMomentum行だけShort合成し、EWMA alpha=0.25と公式5分位weight/costは全試行で共通。",
        "",
        "## Pooled 2011–2014",
        "",
        "| ID | Gross SR | Net SR | 年率Net | 年率Cost | turnover/日 | Long Net SR | Long 年率Net | Short Net SR | Short 年率Net | RankIC | HAC t | Hit率 | Q1→Q5単調性 | Max DD |",
        "|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summaries:
        pooled = item["pooled"]
        long = pooled["legs"]["long"]
        short = pooled["legs"]["short"]
        lines.append(
            f"| {item['trial_id']} | {pooled['gross_sharpe']:.4f} | {pooled['net_sharpe']:.4f} | "
            f"{pooled['annual_net']:.2%} | {pooled['annual_cost']:.2%} | {pooled['turnover']:.5f} | "
            f"{long['net_sharpe']:.4f} | {long['annual_net']:.2%} | {short['net_sharpe']:.4f} | "
            f"{short['annual_net']:.2%} | {pooled['rankic']:.4f} | {pooled['rankic_t_hac5']:.3f} | "
            f"{pooled['rankic_hit']:.3f} | {pooled['q_monotonicity']:.3f} | {pooled['max_drawdown_additive']:.2%} |"
        )
    lines += [
        "",
        "### M00との差分",
        "",
        "| ID | ΔGross SR | ΔNet SR | Net SR改善fold | ΔTurnover/日 | Δ年率Cost | Bootstrap 95% CI (ΔNet SR) |",
        "|:---|---:|---:|---:|---:|---:|:---|",
    ]
    for item in summaries:
        comparison = item.get("comparison")
        if not comparison:
            lines.append("| M00 | — | — | — | — | — | — |")
            continue
        boot = comparison["bootstrap"]
        lines.append(
            f"| {item['trial_id']} | {comparison['delta_gross_sharpe']:+.4f} | "
            f"{comparison['delta_net_sharpe']:+.4f} | {comparison['improved_folds']}/4 | "
            f"{comparison['delta_turnover']:+.5f} | {comparison['delta_annual_cost']:+.2%} | "
            f"[{boot['low']:.4f}, {boot['high']:.4f}] |"
        )
    lines += ["", "## Fold別・年別結果", "", "| ID | 年 | Net SR | Gross SR | Long Net SR | Short Net SR | 年率Long Net | 年率Short Net | Cost | Turnover | RankIC | Q1 | Q5 | monotonicity |", "|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for item in summaries:
        for period in item["periods"]:
            data = period["metrics"]
            legs = data["legs"]
            lines.append(
                f"| {item['trial_id']} | {period['name']} | {data['net_sharpe']:.4f} | "
                f"{data['gross_sharpe']:.4f} | {legs['long']['net_sharpe']:.4f} | "
                f"{legs['short']['net_sharpe']:.4f} | {legs['long']['annual_net']:.2%} | "
                f"{legs['short']['annual_net']:.2%} | {data['annual_cost']:.2%} | "
                f"{data['turnover']:.5f} | {data['rankic']:.4f} | {data['q1_daily_return']:.5%} | "
                f"{data['q5_daily_return']:.5%} | {data['q_monotonicity']:.3f} |"
            )
    lines += [
        "",
        "## 判断と制約",
        "",
        "- 4通りを事前固定した範囲だけ評価した。既知期間の事後分析なので、どの組合せも候補選定・戦略変更・Valid再評価の根拠にしない。結果を見て追加探索しない。",
        "- Long/ShortのNet Sharpeは、公式の全銘柄五分位weightを正weightと負weightに分解し、各legのturnover costを別々に割り当てて計算。2 legのnet日次損益和が全体netと一致することを検査した。",
        "- `AdjustmentFactor`累積を使うsplit-safe定義はC3Sと同様のイベント乗数解釈を前提とする。合併・上場区分の特殊事例を含む完全な企業行動データ品質検証ではない。",
        f"- Source scan: **{audit['status']}**。Future-mutation / truncation prefix-invariance: 3 cutoff × 2操作 × 4 signalでbitwise一致。",
        f"- 再現情報: run metadata `{run_id}/run.json`; 日次・全指標はartifacts run配下、比較表は`model_comparison.csv`と`fold_metrics.csv`。",
        "",
        "## 再計算上の注意",
        "",
        "Net Sharpeは全体・Long・Shortをそれぞれ日次Net損益から独立に算出する。Sharpeは加法的ではない。Long/Short寄与は同一スコアの正・負weight attributionであり、leg別に再正規化した2つの独立portfolioの成績ではない。",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def run(config_path, output_path):
    started = time.monotonic()
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if config.get("data_split") != "train" or config.get("valid_evaluation") is not False:
        raise ValueError("This runner only accepts a Train-only config")
    trial_ids = [trial["trial_id"] for trial in config["trials"]]
    if tuple(trial_ids) != TRIALS or config.get("max_trials") != 4:
        raise ValueError("The fixed four-pattern budget was modified")
    output = Path(output_path)
    report_dir = ROOT / "reports" / config["experiment_id"]
    for directory in (output / "audit", output / "metrics", output / "predictions", report_dir):
        directory.mkdir(parents=True, exist_ok=True)
    run_meta = json.loads((output / "run.json").read_text(encoding="utf-8"))
    code_files = [Path(__file__).resolve(), *sorted(Path(features.__file__).parent.glob("*.py")),
                  Path(reference_features.__file__).resolve(), Path(reference_models.__file__).resolve()]
    run_meta.update({
        "status": "running", "started_at_utc": utc_now(), "command": sys.argv,
        "actual_trials": 0,
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "numpy": np.__version__, "pandas": pd.__version__},
        "code_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in code_files},
    })
    dump(output / "run.json", run_meta)
    try:
        firewall.install()
        data_dir = ROOT / "stock_comp_2026" / "input"
        input_names = list(features.INPUT_COLUMNS)
        run_meta["train_data_sha256"] = {
            f"{name}_train.parquet": sha256(data_dir / f"{name}_train.parquet")
            for name in input_names
        }
        run_meta["train_data_sha256"]["target_1day_train.parquet"] = sha256(
            data_dir / "target_1day_train.parquet"
        )
        print("[1/5] Loading Train inputs and target only...", flush=True)
        inputs = features.load_inputs(data_dir, split="train")
        target = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index()
        print("[2/5] Building causal features...", flush=True)
        feature_frame = features.build_features(inputs)
        if not feature_frame.index.is_unique:
            raise AssertionError("Feature index is not unique")
        if not np.isfinite(feature_frame["res60s1"].to_numpy()).all():
            raise AssertionError("Non-finite momentum score")
        for rank_col, available_col in (("new_high_rank", "high_available"),
                                        ("new_low_rank", "low_available")):
            available_values = feature_frame.loc[feature_frame[available_col], rank_col]
            if not np.isfinite(available_values.to_numpy()).all():
                raise AssertionError(f"Non-finite available breakout rank: {rank_col}")
        print("      Verifying M00 exact H0 reproduction...", flush=True)
        reference_frame = reference_features.build_features(inputs)
        reference_h0 = reference_models.generate_signal(reference_frame, "H0", alpha=config["parameters"]["ewma_alpha"])
        candidate_m00 = models.generate_signal(feature_frame, "M00", alpha=config["parameters"]["ewma_alpha"])
        pd.testing.assert_series_equal(
            candidate_m00.rename("Return"), reference_h0.rename("Return"), check_exact=True
        )
        audit = audit_prefix_invariance(inputs, feature_frame)
        dump(output / "audit/causality.json", audit)
        print("[3/5] Source and future-mutation prefix audits: PASS", flush=True)

        dev_years = (2011, 2012, 2013, 2014)
        summaries = []
        accounts = {}
        leg_accounts = {}
        print("[4/5] Backtesting the four fixed combinations...", flush=True)
        for trial in config["trials"]:
            trial_id = trial["trial_id"]
            signal = models.generate_signal(feature_frame, trial_id, alpha=config["parameters"]["ewma_alpha"])
            if not signal.index.equals(feature_frame.index) or not np.isfinite(signal).all():
                raise AssertionError(f"Prediction index/coverage/finiteness failure for {trial_id}")
            pred = signal.rename("Return").to_frame()
            pred.to_parquet(output / f"predictions/{trial_id}.parquet")
            account = daily_account(signal, target)
            legs = leg_account(signal, target)
            difference = (legs["net_sum"].reindex(account.index) - account["net"]).abs().max()
            if not np.isfinite(difference) or difference > 1e-10:
                raise AssertionError(f"Leg net accounting does not reconcile for {trial_id}: {difference}")
            account.to_csv(output / f"metrics/daily_account_{trial_id}.csv", index_label="Date")
            legs.to_csv(output / f"metrics/daily_legs_{trial_id}.csv", index_label="Date")
            accounts[trial_id] = account
            leg_accounts[trial_id] = legs

            pooled = combined_years(account, dev_years)
            pooled_legs = leg_accounts[trial_id].reindex(pooled.index)
            periods = []
            for year in dev_years:
                part = select_window(account, f"{year}-01-01", f"{year}-12-31")
                part_legs = leg_accounts[trial_id].reindex(part.index)
                periods.append({"name": str(year), "metrics": metric_bundle(part, part_legs)})
            seen = select_window(account, "2015-01-01", "2016-03-31")
            periods.append({
                "name": "2015-2016-03 (known reference)",
                "metrics": metric_bundle(seen, leg_accounts[trial_id].reindex(seen.index)),
            })
            summaries.append({
                "trial_id": trial_id,
                "description": trial["description"],
                "pooled": metric_bundle(pooled, pooled_legs),
                "periods": periods,
            })

        print("[5/5] Writing paired comparisons and reports...", flush=True)
        base = accounts["M00"]
        base_pooled = combined_years(base, dev_years)
        for item in summaries:
            if item["trial_id"] == "M00":
                continue
            candidate = accounts[item["trial_id"]]
            candidate_pooled = combined_years(candidate, dev_years)
            common = base_pooled.index.intersection(candidate_pooled.index)
            base_common = base_pooled.loc[common]
            cand_common = candidate_pooled.loc[common]
            fold_delta = []
            for year in dev_years:
                base_period = next(row["metrics"] for row in by_trial(summaries, "M00")["periods"] if row["name"] == str(year))
                cand_period = next(row["metrics"] for row in item["periods"] if row["name"] == str(year))
                fold_delta.append(cand_period["net_sharpe"] - base_period["net_sharpe"])
            item["comparison"] = {
                "delta_gross_sharpe": item["pooled"]["gross_sharpe"] - by_trial(summaries, "M00")["pooled"]["gross_sharpe"],
                "delta_net_sharpe": item["pooled"]["net_sharpe"] - by_trial(summaries, "M00")["pooled"]["net_sharpe"],
                "fold_delta_net_sharpe": fold_delta,
                "improved_folds": sum(value > 0 for value in fold_delta),
                "delta_turnover": item["pooled"]["turnover"] - by_trial(summaries, "M00")["pooled"]["turnover"],
                "delta_annual_cost": item["pooled"]["annual_cost"] - by_trial(summaries, "M00")["pooled"]["annual_cost"],
                "bootstrap": bootstrap_delta(
                    base_common["net"], cand_common["net"],
                    seed=config["random_seed"],
                    reps=config["parameters"]["bootstrap_repetitions"],
                    block=config["parameters"]["bootstrap_block_days"],
                ),
            }

        dump(output / "metrics/summary.json", summaries)
        fold_rows, comparison_rows = [], []
        for item in summaries:
            for period in item["periods"]:
                data = period["metrics"]
                row = {"trial_id": item["trial_id"], "period": period["name"]}
                row.update({key: value for key, value in data.items() if key != "legs"})
                for side in ("long", "short"):
                    row.update({f"{side}_{key}": value for key, value in data["legs"][side].items()})
                fold_rows.append(row)
            row = {"trial_id": item["trial_id"], "description": item["description"]}
            row.update({key: value for key, value in item["pooled"].items() if key != "legs"})
            for side in ("long", "short"):
                row.update({f"{side}_{key}": value for key, value in item["pooled"]["legs"][side].items()})
            if "comparison" in item:
                comp = item["comparison"]
                row.update({key: value for key, value in comp.items() if key not in ("bootstrap", "fold_delta_net_sharpe")})
                row.update({"fold_delta_net_sharpe": json.dumps(comp["fold_delta_net_sharpe"]),
                            "bootstrap_low": comp["bootstrap"]["low"],
                            "bootstrap_high": comp["bootstrap"]["high"],
                            "bootstrap_positive_fraction": comp["bootstrap"]["bootstrap_positive_fraction"]})
            comparison_rows.append(row)
        pd.DataFrame(fold_rows).to_csv(output / "metrics/fold_metrics.csv", index=False)
        pd.DataFrame(comparison_rows).to_csv(output / "metrics/model_comparison.csv", index=False)
        pd.DataFrame(fold_rows).to_csv(report_dir / "fold_metrics.csv", index=False)
        pd.DataFrame(comparison_rows).to_csv(report_dir / "model_comparison.csv", index=False)
        run_meta.update({
            "status": "completed", "completed_at_utc": utc_now(),
            "elapsed_seconds": time.monotonic() - started,
            "actual_trials": len(trial_ids), "prefix_audit": "PASS",
            "valid_accessed": False, "baseline_m00_exact_h0_parity": True,
        })
        dump(output / "run.json", run_meta)
        report_path = build_report(config, output.name, summaries, audit, run_meta)
        print(f"[Done] Report: {report_path}", flush=True)
    except BaseException as error:
        run_meta.update({"status": "failed", "completed_at_utc": utc_now(), "failure": repr(error)})
        dump(output / "run.json", run_meta)
        raise


def by_trial(items, trial_id):
    return next(item for item in items if item["trial_id"] == trial_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    run(arguments.config, arguments.output)
