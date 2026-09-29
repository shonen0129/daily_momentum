"""Train-only comparison of a breakout-only base and optional momentum per side."""
import argparse
import ast
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np
import pandas as pd

from research import firewall
from research.evaluation import bootstrap_delta, daily_account
from research.experiments import breakout_side_momentum as shared
from stock_comp_2026.strategies.dm_breakout_base_momentum_overlay import features, models
from stock_comp_2026.strategies.dm_breakout_side_momentum import features as causal_features

ROOT = Path(__file__).resolve().parents[2]
TRIAL_IDS = ("B00", "M10", "M01", "M11")
DEV_YEARS = (2011, 2012, 2013, 2014)


def source_scan():
    paths = sorted(Path(features.__file__).parent.glob("*.py"))
    paths += sorted(Path(causal_features.__file__).parent.glob("*.py"))
    paths = sorted(set(path.resolve() for path in paths))
    banned = (
        "AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose",
        "AdjustmentVolume", "raw_target", "target_1day_valid",
    )
    for path in paths:
        source = path.read_text(encoding="utf-8")
        for token in banned:
            if token in source:
                raise AssertionError(f"Banned token {token} in {path}")
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("bfill", "backfill"):
                    raise AssertionError(f"Backfill in {path}")
                if any(k.arg == "center" and isinstance(k.value, ast.Constant) and k.value.value
                       for k in node.keywords):
                    raise AssertionError(f"Centered rolling in {path}")
    return [str(path.relative_to(ROOT)) for path in paths]


def audit_prefix(inputs, original):
    source_files = source_scan()
    records = []
    for label in ("2010-12-30", "2012-06-29", "2014-12-30"):
        cutoff = pd.Timestamp(label)
        dates = original.index.get_level_values("Date")
        prefix_index = original.index[dates <= cutoff]
        expected = original.loc[prefix_index]
        for mode in ("mutation", "truncation"):
            changed_inputs = shared.mutate_after(inputs, cutoff, truncate=(mode == "truncation"))
            changed_features = features.build_features(changed_inputs)
            pd.testing.assert_frame_equal(expected, changed_features.loc[prefix_index], check_exact=True)
            for trial_id in TRIAL_IDS:
                expected_signal = models.generate_signal(original, trial_id).loc[prefix_index]
                actual_signal = models.generate_signal(changed_features, trial_id).loc[prefix_index]
                pd.testing.assert_series_equal(expected_signal, actual_signal, check_exact=True)
        records.append({"cutoff": label, "rows": len(prefix_index), "bitwise": True})
    return {"status": "PASS", "source_files": source_files, "prefix_tests": records}


def breakout_contract(features_frame):
    raw = {trial_id: models.raw_signal(features_frame, trial_id) for trial_id in TRIAL_IDS}
    high_event = features_frame["high_available"] & (features_frame["new_high_excess"] > 0.0)
    low_event = features_frame["low_available"] & (features_frame["new_low_excess"] > 0.0)
    non_event = ~(high_event | low_event)
    if raw["B00"].loc[non_event].abs().max() != 0.0:
        raise AssertionError("B00 signal must be zero without a breakout event")
    if (raw["M10"].loc[high_event] < 0.0).any() or (raw["M01"].loc[low_event] > 0.0).any():
        raise AssertionError("Momentum overlay reversed a breakout leg")
    if (raw["M10"] - raw["B00"]).loc[~high_event].abs().max() != 0.0:
        raise AssertionError("Long-only momentum changed rows outside new-high events")
    if (raw["M01"] - raw["B00"]).loc[~low_event].abs().max() != 0.0:
        raise AssertionError("Short-only momentum changed rows outside new-low events")
    return {
        "status": "PASS",
        "rows": int(len(features_frame)),
        "new_high_rows": int(high_event.sum()),
        "new_low_rows": int(low_event.sum()),
        "no_event_b00_zero": True,
        "overlay_scope_and_sign": True,
    }


def build_report(config, output, summaries, audit, contract, metadata):
    report_dir = ROOT / "reports" / config["experiment_id"]
    report_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {config['experiment_id']}: ブレイク基準へのモメンタム追加比較",
        "",
        f"- Run ID: `{output.name}`",
        f"- 実行日時 (UTC): {metadata['completed_at_utc']}",
        "- 入力: Train splitのみ。Valid/Valid target/raw_targetは未使用。",
        "- この設計は既読Validの分析後に依頼された事後仮説で、Train期間も既知。結果は記述比較であり独立確認・採用根拠ではない。",
        "- 開発fold: 2011–2014（各年末のt+2越境2取引日をpurge）。2015-01–2016-03は既読Trainの参考値のみ。",
        "",
        "## 4パターン",
        "",
        "| ID | Longベース | Shortベース | モメンタム追加 |",
        "|:---|:---|:---|:---|",
        "| B00 | 新高値ブレイク | 新安値ブレイク | なし（基準） |",
        "| M10 | 新高値ブレイク | 新安値ブレイク | Longのみ |",
        "| M01 | 新高値ブレイク | 新安値ブレイク | Shortのみ |",
        "| M11 | 新高値ブレイク | 新安値ブレイク | Long/Short |",
        "",
        "新高値・新安値は、当日High/Lowを除くsplit-safe raw価格の過去250観測最大/最小を`t`終値で更新したイベント。イベント側だけで超過幅を日別percentile rankし、ブレイクstrengthを0.5〜1.0に変換。非イベントや250観測履歴不足は0。Momentum onでは該当するブレイクイベントのscoreだけを`0.5*breakout_signed_score + 0.5*res60s1`にし、Longは0以上、Shortは0以下へclip。イベント外にモメンタムだけで建玉を作らない。alpha=0.25のEWMA、公式5分位weight、片道10bps costは共通。",
        "",
        "## Pooled 2011–2014 (974評価日)",
        "",
        "| ID | Gross SR | Net SR | ΔNet SR vs B00 | 年率Gross | 年率Net | 年率Cost | Turnover/日 | Long 年率Net / Net SR | Short 年率Net / Net SR | RankIC | HAC t | Hit | Q1–Q5単調性 | Max DD |",
        "|:---|---:|---:|---:|---:|---:|---:|---:|:---|:---|---:|---:|---:|---:|---:|",
    ]
    base = next(item for item in summaries if item["trial_id"] == "B00")
    for item in summaries:
        p = item["pooled"]
        comp = item.get("comparison")
        l, s = p["legs"]["long"], p["legs"]["short"]
        delta = "—" if comp is None else f"{comp['delta_net_sharpe']:+.4f}"
        lines.append(
            f"| {item['trial_id']} | {p['gross_sharpe']:.4f} | {p['net_sharpe']:.4f} | "
            f"{delta} | {p['annual_gross']:.2%} | {p['annual_net']:.2%} | "
            f"{p['annual_cost']:.2%} | {p['turnover']:.5f} | "
            f"{l['annual_net']:+.2%} / {l['net_sharpe']:.4f} | "
            f"{s['annual_net']:+.2%} / {s['net_sharpe']:.4f} | {p['rankic']:.4f} | "
            f"{p['rankic_t_hac5']:.3f} | {p['rankic_hit']:.3f} | {p['q_monotonicity']:.3f} | "
            f"{p['max_drawdown_additive']:.2%} |"
        )
    lines += [
        "",
        "### B00差分のfold安定性",
        "",
        "| ID | 2011 ΔNet SR | 2012 | 2013 | 2014 | 改善fold | paired 20日bootstrap 95% CI |",
        "|:---|---:|---:|---:|---:|:---:|:---|",
    ]
    for item in summaries:
        comp = item.get("comparison")
        if not comp:
            lines.append("| B00 | — | — | — | — | — | — |")
            continue
        boot = comp["bootstrap"]
        deltas = comp["fold_delta_net_sharpe"]
        lines.append(
            f"| {item['trial_id']} | {deltas[0]:+.4f} | {deltas[1]:+.4f} | {deltas[2]:+.4f} | "
            f"{deltas[3]:+.4f} | {comp['improved_folds']}/4 | [{boot['low']:.4f}, {boot['high']:.4f}] |"
        )
    lines += ["", "## 年別結果", "", "| ID | 期間 | Gross SR | Net SR | 年率Net | 年率Cost | Turnover | Long Net SR | Short Net SR | RankIC | Q1 | Q5 | monotonicity | Max DD |", "|:---|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for item in summaries:
        for period in item["periods"]:
            p = period["metrics"]
            lines.append(
                f"| {item['trial_id']} | {period['name']} | {p['gross_sharpe']:.4f} | {p['net_sharpe']:.4f} | "
                f"{p['annual_net']:.2%} | {p['annual_cost']:.2%} | {p['turnover']:.5f} | "
                f"{p['legs']['long']['net_sharpe']:.4f} | {p['legs']['short']['net_sharpe']:.4f} | "
                f"{p['rankic']:.4f} | {p['q1_daily_return']:.5%} | {p['q5_daily_return']:.5%} | "
                f"{p['q_monotonicity']:.3f} | {p['max_drawdown_additive']:.2%} |"
            )
    lines += [
        "",
        "## 結論・制約",
        "",
        "- M10/M01/M11はB00を上回るかだけを固定比較する。試行後に定義・重み・窓を調整しない。既知Trainでの結果をもとにValidを再読しない。",
        "- Long/Shortは公式五分位weightの正負weightへの損益帰属。2 legのNet日次損益和が全体Netと一致することを確認したが、各legを別ポートフォリオとして再正規化したSharpeではない。Sharpeは加法的でない。",
        f"- Source scan: **{audit['status']}**。future-mutation/truncation prefix-invariance: 3 cutoff × 2操作 × 4 signalでbitwise一致。",
        f"- Breakout/momentum scope contract: **{contract['status']}**（breakout外のB00 score=0、overlayは対応側イベントだけ、方向反転なし）。",
        f"- 再現条件: seed={config['random_seed']}; paired bootstrap=1,000反復/20取引日block; run metadataは`{output.name}/run.json`。",
        "",
        "2015-01〜2016-03は既知Trainの参考値であり、未使用holdoutではない。すべての成績は既読データ上の事後的・記述的な比較として読む。",
    ]
    path = report_dir / "REPORT.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run(config_path, output_path):
    started = time.monotonic()
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if config.get("data_split") != "train" or config.get("valid_evaluation") is not False:
        raise ValueError("Train-only config required")
    trial_ids = [item["trial_id"] for item in config["trials"]]
    if tuple(trial_ids) != TRIAL_IDS or config.get("max_trials") != 4:
        raise ValueError("The four pre-registered variants were changed")
    output = Path(output_path)
    report_dir = ROOT / "reports" / config["experiment_id"]
    for directory in (output / "audit", output / "metrics", output / "predictions", report_dir):
        directory.mkdir(parents=True, exist_ok=True)
    metadata = json.loads((output / "run.json").read_text(encoding="utf-8"))
    code_paths = [Path(__file__).resolve(), Path(shared.__file__).resolve(),
                  Path(causal_features.__file__).resolve(),
                  *sorted(Path(features.__file__).parent.glob("*.py"))]
    metadata.update({
        "status": "running", "started_at_utc": shared.utc_now(), "command": sys.argv,
        "actual_trials": 0,
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "numpy": np.__version__, "pandas": pd.__version__},
        "code_sha256": {str(path.relative_to(ROOT)): shared.sha256(path) for path in code_paths},
    })
    shared.dump(output / "run.json", metadata)
    try:
        firewall.install()
        data_dir = ROOT / "stock_comp_2026" / "input"
        input_names = list(features.INPUT_COLUMNS)
        metadata["train_data_sha256"] = {
            f"{name}_train.parquet": shared.sha256(data_dir / f"{name}_train.parquet")
            for name in input_names
        }
        metadata["train_data_sha256"]["target_1day_train.parquet"] = shared.sha256(
            data_dir / "target_1day_train.parquet"
        )
        print("[1/5] Loading Train inputs and target...", flush=True)
        inputs = features.load_inputs(data_dir, split="train")
        target = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index()
        print("[2/5] Building breakout and momentum features...", flush=True)
        feature_frame = features.build_features(inputs)
        if not feature_frame.index.is_unique:
            raise AssertionError("Feature index is not unique")
        for column in ("res60s1", "new_high_excess", "new_low_excess"):
            available = feature_frame[column].dropna()
            if not np.isfinite(available.to_numpy()).all():
                raise AssertionError(f"Non-finite feature values in {column}")
        contract = breakout_contract(feature_frame)
        dump = shared.dump
        dump(output / "audit/breakout_contract.json", contract)
        audit = audit_prefix(inputs, feature_frame)
        dump(output / "audit/causality.json", audit)
        print("[3/5] Breakout contract and prefix-invariance audits: PASS", flush=True)

        summaries, accounts, leg_accounts = [], {}, {}
        print("[4/5] Evaluating B00/M10/M01/M11...", flush=True)
        for trial in config["trials"]:
            trial_id = trial["trial_id"]
            signal = models.generate_signal(feature_frame, trial_id, alpha=config["parameters"]["ewma_alpha"])
            replay = models.generate_signal(feature_frame, trial_id, alpha=config["parameters"]["ewma_alpha"])
            pd.testing.assert_series_equal(signal, replay, check_exact=True)
            if not signal.index.equals(feature_frame.index) or not np.isfinite(signal.to_numpy()).all():
                raise AssertionError(f"Prediction coverage/finiteness failure: {trial_id}")
            signal.rename("Return").to_frame().to_parquet(output / f"predictions/{trial_id}.parquet")
            account = daily_account(signal, target)
            legs = shared.leg_account(signal, target)
            reconcile = (legs["net_sum"].reindex(account.index) - account["net"]).abs().max()
            if not np.isfinite(reconcile) or reconcile > 1e-10:
                raise AssertionError(f"Long+Short net account mismatch: {trial_id} {reconcile}")
            account.to_csv(output / f"metrics/daily_account_{trial_id}.csv", index_label="Date")
            legs.to_csv(output / f"metrics/daily_legs_{trial_id}.csv", index_label="Date")
            accounts[trial_id], leg_accounts[trial_id] = account, legs
            pooled = shared.combined_years(account, DEV_YEARS)
            periods = []
            for year in DEV_YEARS:
                part = shared.select_window(account, f"{year}-01-01", f"{year}-12-31")
                periods.append({"name": str(year), "metrics": shared.metric_bundle(part, legs.reindex(part.index))})
            known = shared.select_window(account, "2015-01-01", "2016-03-31")
            periods.append({"name": "2015-2016-03 known reference",
                            "metrics": shared.metric_bundle(known, legs.reindex(known.index))})
            summaries.append({"trial_id": trial_id, "description": trial["description"],
                              "pooled": shared.metric_bundle(pooled, legs.reindex(pooled.index)),
                              "periods": periods})

        base_summary = shared.by_trial(summaries, "B00")
        base_account = shared.combined_years(accounts["B00"], DEV_YEARS)
        for item in summaries:
            if item["trial_id"] == "B00":
                continue
            account = shared.combined_years(accounts[item["trial_id"]], DEV_YEARS)
            common = base_account.index.intersection(account.index)
            fold_deltas = []
            for year in DEV_YEARS:
                base_period = next(p["metrics"] for p in base_summary["periods"] if p["name"] == str(year))
                candidate_period = next(p["metrics"] for p in item["periods"] if p["name"] == str(year))
                fold_deltas.append(candidate_period["net_sharpe"] - base_period["net_sharpe"])
            item["comparison"] = {
                "delta_gross_sharpe": item["pooled"]["gross_sharpe"] - base_summary["pooled"]["gross_sharpe"],
                "delta_net_sharpe": item["pooled"]["net_sharpe"] - base_summary["pooled"]["net_sharpe"],
                "delta_turnover": item["pooled"]["turnover"] - base_summary["pooled"]["turnover"],
                "delta_annual_cost": item["pooled"]["annual_cost"] - base_summary["pooled"]["annual_cost"],
                "fold_delta_net_sharpe": fold_deltas,
                "improved_folds": sum(x > 0 for x in fold_deltas),
                "bootstrap": bootstrap_delta(
                    base_account.loc[common, "net"], account.loc[common, "net"],
                    seed=config["random_seed"], reps=config["parameters"]["bootstrap_repetitions"],
                    block=config["parameters"]["bootstrap_block_days"],
                ),
            }

        dump(output / "metrics/summary.json", summaries)
        fold_rows, comparison_rows = [], []
        for item in summaries:
            for period in item["periods"]:
                values = period["metrics"]
                row = {"trial_id": item["trial_id"], "period": period["name"]}
                row.update({k: v for k, v in values.items() if k != "legs"})
                for side in ("long", "short"):
                    row.update({f"{side}_{k}": v for k, v in values["legs"][side].items()})
                fold_rows.append(row)
            row = {"trial_id": item["trial_id"], "description": item["description"]}
            row.update({k: v for k, v in item["pooled"].items() if k != "legs"})
            for side in ("long", "short"):
                row.update({f"{side}_{k}": v for k, v in item["pooled"]["legs"][side].items()})
            comp = item.get("comparison")
            if comp:
                row.update({k: v for k, v in comp.items() if k not in ("bootstrap", "fold_delta_net_sharpe")})
                row["fold_delta_net_sharpe"] = json.dumps(comp["fold_delta_net_sharpe"])
                row["bootstrap_low"], row["bootstrap_high"] = comp["bootstrap"]["low"], comp["bootstrap"]["high"]
                row["bootstrap_positive_fraction"] = comp["bootstrap"]["bootstrap_positive_fraction"]
            comparison_rows.append(row)
        pd.DataFrame(fold_rows).to_csv(output / "metrics/fold_metrics.csv", index=False)
        pd.DataFrame(comparison_rows).to_csv(output / "metrics/model_comparison.csv", index=False)
        pd.DataFrame(fold_rows).to_csv(report_dir / "fold_metrics.csv", index=False)
        pd.DataFrame(comparison_rows).to_csv(report_dir / "model_comparison.csv", index=False)
        metadata.update({"status": "completed", "completed_at_utc": shared.utc_now(),
                         "elapsed_seconds": time.monotonic() - started, "actual_trials": 4,
                         "valid_accessed": False, "breakout_contract": "PASS",
                         "prefix_invariance": "PASS", "long_short_account_reconciles": True})
        shared.dump(output / "run.json", metadata)
        report_path = build_report(config, output, summaries, audit, contract, metadata)
        print(f"[Done] Report: {report_path}", flush=True)
    except BaseException as error:
        metadata.update({"status": "failed", "completed_at_utc": shared.utc_now(),
                         "failure": repr(error)})
        shared.dump(output / "run.json", metadata)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.config, args.output)
