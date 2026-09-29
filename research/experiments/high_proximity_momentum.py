"""Train-only High Proximity Momentum experiments."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from research import firewall
from research.evaluation import bootstrap_delta, daily_account, metrics
from stock_comp_2026.strategies.dm_high_proximity_momentum import features as strategy
from stock_comp_2026.strategies.dm_high_proximity_momentum import models

ROOT = Path(__file__).resolve().parents[2]
SUPPORTED_TRIALS = ["H0", "P60", "P250", "C1", "C2", "C3", "C3S", "C4", "C5", "C6"]


def now():
    return datetime.now(timezone.utc).isoformat()


def clean(x):
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return float(x) if np.isfinite(x) else None
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, (pd.Timestamp, pd.Period)):
        return str(x)
    return x


def dump(path, value):
    Path(path).write_text(json.dumps(clean(value), ensure_ascii=False, indent=2) + "\n")


def digest(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def source_scan():
    import ast
    paths = sorted(Path(strategy.__file__).parent.glob("*.py"))
    forbidden = [
        "AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose", "AdjustmentVolume",
        "raw_target", "target_1day_valid"
    ]
    for path in paths:
        text = path.read_text()
        for token in forbidden:
            if token in text:
                raise AssertionError(f"forbidden token {token} in {path}")
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("bfill", "backfill"):
                    raise AssertionError(f"backfill in {path}")
                if any(k.arg == "center" and isinstance(k.value, ast.Constant) and k.value.value for k in node.keywords):
                    raise AssertionError(f"center rolling in {path}")
                if any(k.arg == "direction" and isinstance(k.value, ast.Constant) and k.value.value == "forward" for k in node.keywords):
                    raise AssertionError(f"forward join in {path}")
    return [str(path.relative_to(ROOT)) for path in paths]


def mutate(inputs, cutoff, truncate=False):
    result = {}
    for name, frame in inputs.items():
        dates = frame.index.get_level_values("Date")
        if dates.tz is not None:
            dates = dates.tz_localize(None)
        future = dates > cutoff
        if truncate:
            result[name] = frame.loc[~future].copy()
            continue
        changed = frame.copy()
        for col in changed:
            if isinstance(changed[col].dtype, pd.CategoricalDtype):
                changed[col] = changed[col].astype(str)
            if pd.api.types.is_numeric_dtype(changed[col]):
                if name == "prices_daily_quotes" and col == "AdjustmentFactor":
                    changed.loc[future, col] = 1.0
                    future_dates = dates[future]
                    if len(future_dates):
                        first_future = future_dates.min()
                        changed.loc[future & (dates == first_future), col] = 0.25
                else:
                    changed.loc[future, col] = changed.loc[future, col] * -3.14 + 888.0
            elif pd.api.types.is_datetime64_any_dtype(changed[col]):
                changed.loc[future, col] = pd.Timestamp("1990-01-01")
            else:
                changed.loc[future, col] = "mutated_value"
        result[name] = changed
    return result


def audit_causality(inputs, original_features, trial_ids=None):
    if trial_ids is None:
        trial_ids = SUPPORTED_TRIALS
    records = []
    for label in ("2010-12-30", "2012-06-29", "2014-12-30"):
        cutoff = pd.Timestamp(label)
        prefix = original_features.index.get_level_values("Date") <= cutoff
        expected = original_features.loc[prefix]
        for mode in ("mutation", "truncation"):
            mutated_inputs = mutate(inputs, cutoff, truncate=(mode == "truncation"))
            actual = strategy.build_features(mutated_inputs)
            pd.testing.assert_frame_equal(expected, actual.loc[expected.index], check_exact=True)
            for trial_id in trial_ids:
                sig_exp = models.generate_signal(original_features, trial_id).loc[expected.index]
                sig_act = models.generate_signal(actual, trial_id).loc[expected.index]
                pd.testing.assert_series_equal(sig_exp, sig_act, check_exact=True)
        records.append({
            "cutoff": label,
            "rows": int(prefix.sum()),
            "features": int(original_features.shape[1]),
            "bitwise": True
        })
    return {
        "status": "PASS",
        "source_files": source_scan(),
        "prefix_tests": records
    }


def write_report(config, trial_summaries, output_dir, report_dir):
    report_file = report_dir / "REPORT.md"
    lines = [
        f"# {config['experiment_id']}: 高値近接度ファクターによるモメンタム戦略高度化 レポート",
        "",
        f"- 戦略名: `{config['strategy']}`",
        f"- Run ID: `{output_dir.name}`",
        f"- 実行日時 (UTC): `{now()}`",
        "- 検証種別: 完全Train-only（Validおよびraw_targetはファイアウォールでブロック）",
        f"- 主張範囲: {config.get('claim_scope', '探索的なTrain-only比較')}",
        "",
        "## 1. 総合評価サマリー (Pooled 2011–2014 開発期間)",
        "",
        "| Trial | 説明 | 採否判定 | Net Sharpe | Gross Sharpe | 年率Net損益 | 年率Gross損益 | 年率コスト | 日次Turnover | RankIC | 最大DD |",
        "|:---|:---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for item in trial_summaries:
        p = item["pooled_metrics"]
        d = item.get("decision", "—")
        lines.append(
            f"| **{item['trial_id']}** | {item['description']} | **{d}** | "
            f"{p['net_sharpe']:.4f} | {p['gross_sharpe']:.4f} | {p['annual_net']:.2%} | {p['annual_gross']:.2%} | "
            f"{p['annual_cost']:.2%} | {p['turnover']:.4f} | {p['rankic']:.4f} | {p['max_drawdown_additive']:.2%} |"
        )

    lines += [
        "",
        "## 2. Baseline (H0) に対する増分評価 (Incremental Evaluation)",
        "",
        "| Trial | ΔNet Sharpe (中央値) | Net SR改善Fold数 | 通算ΔNet Sharpe | ΔTurnover | ΔCost | Bootstrap 95% CI (ΔNet SR) | 一次選別通過 |",
        "|:---|---:|:---:|---:|---:|---:|:---:|:---:|",
    ]

    for item in trial_summaries:
        comp = item.get("comparison_vs_h0")
        if not comp:
            lines.append(f"| **{item['trial_id']}** (Baseline) | — | — | — | — | — | — | (基準) |")
            continue
        boot = comp["bootstrap"]
        ci_str = f"[{boot['low']:.4f}, {boot['high']:.4f}]"
        pass_str = "PASS" if comp["primary_passed"] else "FAIL"
        lines.append(
            f"| **{item['trial_id']}** | {comp['median_delta_net_sharpe']:+.4f} | "
            f"{comp['improved_net_sharpe_folds']}/4 | {comp['pooled_delta_net_sharpe']:+.4f} | "
            f"{comp['pooled_delta_turnover']:+.4f} | {comp['pooled_delta_cost']:+.2%} | {ci_str} | **{pass_str}** |"
        )

    lines += [
        "",
        "## 3. 年別・Fold別詳細 (Walk-Forward 2011–2014 & 確認期間 2015–2016-03)",
        "",
        "| Trial | 期間 (年) | 種別 | Net Sharpe | Gross Sharpe | 年率Net | Turnover | RankIC | Q1(Short) | Q5(Long) | 単調性 |",
        "|:---|:---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for item in trial_summaries:
        for f in item["folds"]:
            kind = "確認 (参考)" if f["year"] == "2015-2016-03" else "開発 Fold"
            lines.append(
                f"| {item['trial_id']} | {f['year']} | {kind} | {f['net_sharpe']:.4f} | {f['gross_sharpe']:.4f} | "
                f"{f['annual_net']:.2%} | {f['turnover']:.4f} | {f['rankic']:.4f} | "
                f"{f.get('q1_daily_return', 0.0):.5%} | {f.get('q5_daily_return', 0.0):.5%} | {f.get('q_monotonicity', 0.0):.4f} |"
            )

    lines += [
        "",
        "## 4. 経済的考察と結論",
        "",
    ]
    # Summary of findings
    best_candidate = None
    best_net_sr = -999.0
    for item in trial_summaries:
        if item["trial_id"] != "H0" and item["pooled_metrics"]["net_sharpe"] > best_net_sr:
            best_net_sr = item["pooled_metrics"]["net_sharpe"]
            best_candidate = item

    h0_sr = next(x["pooled_metrics"]["net_sharpe"] for x in trial_summaries if x["trial_id"] == "H0")
    if best_candidate and best_candidate.get("comparison_vs_h0", {}).get("primary_passed"):
        if config.get("selection_eligible", True):
            lines.append(
                f"- **最良候補**: `{best_candidate['trial_id']}` ({best_candidate['description']}) が "
                f"Net Sharpe {best_candidate['pooled_metrics']['net_sharpe']:.4f} (Baseline比 {best_candidate['comparison_vs_h0']['pooled_delta_net_sharpe']:+.4f}) "
                f"を達成し、一次選別基準（3/4 fold以上改善、中央値改善>0）をクリアしました。"
            )
        else:
            lines.append(
                f"- `{best_candidate['trial_id']}` は探索的スクリーニング基準を通過しました "
                f"(Net Sharpe {best_candidate['pooled_metrics']['net_sharpe']:.4f}, "
                f"Baseline比 {best_candidate['comparison_vs_h0']['pooled_delta_net_sharpe']:+.4f})。"
                "既知データでの事後探索のため、選択対象・採用候補にはしません。"
            )
    else:
        candidate_ids = [t["trial_id"] for t in config["trials"] if t["trial_id"] != "H0"]
        lines.append(
            f"- 事前固定した有限候補（{', '.join(candidate_ids)}）を評価した結果、H0 (Baseline Net Sharpe {h0_sr:.4f}) に対する "
            f"安定した増分改善（3/4 fold以上の改善かつ中央値改善>0）は得られませんでした。過学習防止原則に基づき候補を却下します。"
        )

    lines += [
        "",
        "### 監査・再現性記録",
        "- **ソースコード静的監査**: 遡及調整済みOHLCV水準（`AdjustmentOpen/High/Low/Close/Volume`）、`raw_target`、`target_1day_valid`、`bfill`、`center=True`、`forward join` なし (PASS)。`AdjustmentFactor`は日次イベント入力としてのみ使用。",
        "- **Prefix-Invarianceテスト**: 2010-12-30, 2012-06-29, 2014-12-30 の3カットオフでビット完全一致 (PASS)",
        f"- **探索予算**: 新規候補{config.get('new_candidate_budget', len(config['trials']) - 1)}件を事前固定し、結果後の追加試行なし",
        "- 全foldの必須指標とbaseline差分: `fold_metrics.csv` / `model_comparison.csv`。日次系列と全指標: run artifact `metrics/`。",
    ]

    report_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(config_path, output_path):
    started_time = time.monotonic()
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    assert config["data_split"] == "train" and config["valid_evaluation"] is False
    trial_ids = [x["trial_id"] for x in config["trials"]]
    assert trial_ids[0] == "H0" and len(set(trial_ids)) == len(trial_ids)
    assert all(trial_id in SUPPORTED_TRIALS for trial_id in trial_ids)
    assert config["max_trials"] == len(trial_ids)
    assert len(trial_ids) - 1 == config.get("new_candidate_budget", len(trial_ids) - 1)

    output_dir = Path(output_path)
    report_dir = ROOT / "reports" / config["experiment_id"]
    for d in (output_dir / "audit", output_dir / "metrics", output_dir / "predictions", report_dir):
        d.mkdir(parents=True, exist_ok=True)

    metadata = json.loads((output_dir / "run.json").read_text(encoding="utf-8"))
    metadata.update({
        "status": "running",
        "started_at_utc": now(),
        "command": sys.argv,
        "actual_trials": 0,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "code_sha256": {
            str(path.relative_to(ROOT)): digest(path)
            for path in (Path(__file__).resolve(), Path(strategy.__file__).resolve(), Path(models.__file__).resolve())
        },
    })
    dump(output_dir / "run.json", metadata)

    # Install Train-only firewall
    firewall.install()

    data_dir = ROOT / "stock_comp_2026/input"
    input_names = ["raw_return_1day", "beta_1day", "topix_return_1day", "prices_daily_quotes"]
    metadata["train_data_sha256"] = {
        f"{name}_train.parquet": digest(data_dir / f"{name}_train.parquet")
        for name in input_names
    }
    metadata["train_data_sha256"]["target_1day_train.parquet"] = digest(data_dir / "target_1day_train.parquet")

    # Load inputs
    print("[1/5] Loading Train inputs...")
    inputs = strategy.load_inputs(data_dir, "train")
    target_series = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index()

    # Build features
    print("[2/5] Building features...")
    features = strategy.build_features(inputs)

    # Causality & Prefix-invariance audit
    print("[3/5] Running causality and prefix-invariance audit...")
    audit_res = audit_causality(inputs, features, trial_ids=trial_ids)
    dump(output_dir / "audit/causality.json", audit_res)
    print("      Causality audit: PASS")

    # Evaluate trials
    print("[4/5] Generating signals and evaluating walk-forward performance...")
    trial_summaries = []
    h0_account = None

    # Define folds: 4 development folds (2011, 2012, 2013, 2014) + confirmation (2015-2016-03)
    dates = target_series.index.get_level_values("Date")
    dev_mask = (dates >= "2011-01-01") & (dates <= "2014-12-31")
    conf_mask = (dates >= "2015-01-01") & (dates <= "2016-03-31")

    for trial_info in config["trials"]:
        trial_id = trial_info["trial_id"]
        desc = trial_info["description"]
        print(f"      Evaluating {trial_id}: {desc}")

        signal = models.generate_signal(features, trial_id, alpha=config["parameters"]["ewma_alpha"])

        # Save predictions
        pred_df = signal.rename("Return").to_frame()
        pred_path = output_dir / f"predictions/{trial_id}.parquet"
        pred_df.to_parquet(pred_path)

        # Daily account
        account = daily_account(signal, target_series)
        account.to_csv(output_dir / f"metrics/daily_account_{trial_id}.csv")

        if trial_id == "H0":
            h0_account = account

        # Calculate metrics for each development fold
        fold_metrics_list = []
        for year in (2011, 2012, 2013, 2014):
            fold_acc = account.loc[str(year)]
            m = metrics(fold_acc)
            m["year"] = str(year)
            fold_metrics_list.append(m)

        # Pooled development metrics (2011-2014)
        pooled_acc = account.loc["2011":"2014"]
        pooled_m = metrics(pooled_acc)

        # Confirmation metrics (2015-2016-03)
        conf_acc = account.loc["2015":"2016-03"]
        conf_m = metrics(conf_acc)
        conf_m["year"] = "2015-2016-03"
        fold_metrics_list.append(conf_m)

        summary = {
            "trial_id": trial_id,
            "description": desc,
            "pooled_metrics": pooled_m,
            "folds": fold_metrics_list,
        }
        trial_summaries.append(summary)

    # Compute comparison vs Baseline (H0)
    print("[5/5] Computing incremental deltas vs H0...")
    h0_summary = trial_summaries[0]
    h0_dev_net = h0_account.loc["2011":"2014", "net"].dropna()

    for summary in trial_summaries:
        trial_id = summary["trial_id"]
        if trial_id == "H0":
            summary["decision"] = "Baseline"
            continue

        cand_acc = pd.read_csv(output_dir / f"metrics/daily_account_{trial_id}.csv", index_col="Date", parse_dates=True)
        cand_dev_net = cand_acc.loc["2011":"2014", "net"].dropna()

        # Delta per dev fold
        delta_net_sr_folds = []
        for year_idx, year in enumerate((2011, 2012, 2013, 2014)):
            h0_fold_sr = h0_summary["folds"][year_idx]["net_sharpe"]
            cand_fold_sr = summary["folds"][year_idx]["net_sharpe"]
            delta_net_sr_folds.append(cand_fold_sr - h0_fold_sr)

        improved_folds = sum(d > 0 for d in delta_net_sr_folds)
        median_delta = float(np.median(delta_net_sr_folds))
        pooled_delta_sr = summary["pooled_metrics"]["net_sharpe"] - h0_summary["pooled_metrics"]["net_sharpe"]
        pooled_delta_turn = summary["pooled_metrics"]["turnover"] - h0_summary["pooled_metrics"]["turnover"]
        pooled_delta_cost = summary["pooled_metrics"]["annual_cost"] - h0_summary["pooled_metrics"]["annual_cost"]

        # Bootstrap delta Net Sharpe (20-day block, 1000 reps)
        common_idx = h0_dev_net.index.intersection(cand_dev_net.index)
        boot = bootstrap_delta(h0_dev_net.loc[common_idx], cand_dev_net.loc[common_idx], seed=config["random_seed"])

        primary_passed = bool(
            improved_folds >= 3
            and median_delta > 0
            and pooled_delta_sr > 0
            and summary["pooled_metrics"]["turnover"] <= 1.5 * h0_summary["pooled_metrics"]["turnover"]
        )

        selection_eligible = config.get("selection_eligible", True)
        if selection_eligible:
            decision = "Candidate" if primary_passed else "Rejected"
        else:
            decision = "Exploratory screen pass" if primary_passed else "Exploratory screen fail"
        summary["decision"] = decision
        summary["comparison_vs_h0"] = {
            "delta_net_sharpe_per_fold": delta_net_sr_folds,
            "improved_net_sharpe_folds": improved_folds,
            "median_delta_net_sharpe": median_delta,
            "pooled_delta_net_sharpe": pooled_delta_sr,
            "pooled_delta_turnover": pooled_delta_turn,
            "pooled_delta_cost": pooled_delta_cost,
            "bootstrap": boot,
            "primary_passed": primary_passed,
        }

    # Save summary metrics
    dump(output_dir / "metrics/summary.json", trial_summaries)

    fold_rows = []
    comparison_rows = []
    for item in trial_summaries:
        for fold in item["folds"]:
            fold_rows.append({"trial_id": item["trial_id"], **fold})
        row = {"trial_id": item["trial_id"], "description": item["description"],
               "decision": item.get("decision"), **item["pooled_metrics"]}
        comparison = item.get("comparison_vs_h0")
        if comparison:
            row.update({
                "median_delta_net_sharpe": comparison["median_delta_net_sharpe"],
                "improved_net_sharpe_folds": comparison["improved_net_sharpe_folds"],
                "pooled_delta_net_sharpe": comparison["pooled_delta_net_sharpe"],
                "pooled_delta_turnover": comparison["pooled_delta_turnover"],
                "pooled_delta_cost": comparison["pooled_delta_cost"],
                "bootstrap_low": comparison["bootstrap"]["low"],
                "bootstrap_high": comparison["bootstrap"]["high"],
                "bootstrap_positive_fraction": comparison["bootstrap"]["bootstrap_positive_fraction"],
                "primary_screen_passed": comparison["primary_passed"],
            })
        comparison_rows.append(row)
    pd.DataFrame(fold_rows).to_csv(output_dir / "metrics/fold_metrics.csv", index=False)
    pd.DataFrame(comparison_rows).to_csv(output_dir / "metrics/model_comparison.csv", index=False)
    pd.DataFrame(fold_rows).to_csv(report_dir / "fold_metrics.csv", index=False)
    pd.DataFrame(comparison_rows).to_csv(report_dir / "model_comparison.csv", index=False)

    # Write REPORT.md
    write_report(config, trial_summaries, output_dir, report_dir)

    # Update decision.md
    decision_file = ROOT / "experiments" / config["experiment_id"] / "decision.md"
    decision_lines = [
        f"# {config['experiment_id']}: 採否判定記録",
        "",
        f"- 判定日: {now().split('T')[0]}",
        f"- 戦略名: `{config['strategy']}`",
        f"- Run ID: `{output_dir.name}`",
        "",
        "## 各候補の選別結果",
        "",
    ]
    for s in trial_summaries:
        t = s["trial_id"]
        d = s.get("decision", "—")
        sr = s["pooled_metrics"]["net_sharpe"]
        comp = s.get("comparison_vs_h0")
        if comp:
            decision_lines.append(
                f"- **{t}**: 判定=`{d}`, Pooled Net SR={sr:.4f} (Δ={comp['pooled_delta_net_sharpe']:+.4f}, "
                f"改善Fold={comp['improved_net_sharpe_folds']}/4, median Δ={comp['median_delta_net_sharpe']:+.4f})"
            )
        else:
            decision_lines.append(f"- **{t}**: Baseline, Pooled Net SR={sr:.4f}")

    decision_lines += [
        "",
        "## 結論",
        "",
    ]
    screen_passed = [
        s for s in trial_summaries
        if s.get("comparison_vs_h0", {}).get("primary_passed")
    ]
    selection_eligible = config.get("selection_eligible", True)
    passed_candidates = screen_passed if selection_eligible else []
    if passed_candidates:
        best = max(passed_candidates, key=lambda x: x["pooled_metrics"]["net_sharpe"])
        decision_lines.append(
            f"一次選別基準を満たした最良候補 `{best['trial_id']}` を Promising Candidate として記録。"
        )
    elif screen_passed:
        decision_lines.append(
            f"`{screen_passed[0]['trial_id']}` は事前定義した一次スクリーニングを通過。ただし既知データでの事後探索なので、"
            "選択対象・採用候補にはしない。独立データでの検証計画も本実験には含まない。"
        )
    else:
        decision_lines.append(
            "事前定義した全新候補が一次選別基準（3/4 fold以上改善、中央値改善>0）を満たさなかったため却下。"
        )
    decision_file.write_text("\n".join(decision_lines) + "\n", encoding="utf-8")

    # Update experiment.json and run.json
    exp_file = ROOT / "experiments" / config["experiment_id"] / "experiment.json"
    exp_meta = json.loads(exp_file.read_text(encoding="utf-8"))
    exp_meta["status"] = "completed" if (passed_candidates or not selection_eligible) else "rejected"
    dump(exp_file, exp_meta)

    metadata.update({
        "status": "completed",
        "finished_at_utc": now(),
        "elapsed_seconds": time.monotonic() - started_time,
        "actual_trials": len(trial_ids),
    })
    dump(output_dir / "run.json", metadata)
    print(f"\n[Done] Experiment finished in {metadata['elapsed_seconds']:.2f}s. Report written to {report_dir / 'REPORT.md'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.config, args.output)
