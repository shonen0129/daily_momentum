"""Make degenerate-feature and no-control outputs explicit in the final report."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def feature_source_scan(path):
    source = Path(path).read_text(encoding="utf-8")
    for token in ("AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose",
                  "AdjustmentVolume", "raw_target", "target_1day_valid"):
        if token in source:
            raise AssertionError(f"Forbidden feature-source token: {token}")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr in ("bfill", "backfill"):
            raise AssertionError("Backfill call in corrected feature source")
        if any(key.arg == "center" and isinstance(key.value, ast.Constant) and key.value.value
               for key in node.keywords):
            raise AssertionError("Centered rolling call in corrected feature source")
        if node.func.attr == "shift":
            period = node.args[0] if node.args else next(
                (key.value for key in node.keywords if key.arg in ("period", "periods")), None)
            if isinstance(period, ast.UnaryOp) and isinstance(period.op, ast.USub):
                raise AssertionError("Negative shift in corrected feature source")
    return {"status": "PASS", "source": str(Path(path).relative_to(ROOT)), "sha256": digest(path)}


def finalize(run_path):
    run = Path(run_path)
    source_audit = feature_source_scan(ROOT / "research/experiments/box_sqrt_duration_features.py")
    report_path = ROOT / "reports/DM-20260925-01/REPORT.md"
    metric_path = run / "metrics/event_univariate.csv"
    uni = pd.read_csv(metric_path)
    duration_mask = uni["feature"].eq("box_duration_sqrt_l")
    for column in ["q1_return", "q2_return", "q3_return", "q4_return", "q5_return", "q_monotonicity"]:
        uni.loc[duration_mask, column] = np.nan
    uni.loc[duration_mask, "quintile_days"] = 0
    uni.to_csv(metric_path, index=False)

    duration = pd.read_csv(run / "metrics/duration_summary.csv")
    event_duration = duration.loc[duration.population.eq("high_events")].iloc[0]
    lmax_share = float(event_duration.Lmax_share_qualified)
    if lmax_share < .99:
        raise AssertionError("Duration is not sufficiently concentrated at the upper cap")
    event = pd.read_csv(run / "metrics/event_only_metrics.csv").set_index("period")
    pooled_event = event.loc["pooled_all_eval"]
    annual_events = event.drop(index="pooled_all_eval")
    positive_event_years = [str(year) for year, row in annual_events.iterrows() if row.rankic > 0]
    negative_event_years = [str(year) for year, row in annual_events.iterrows() if row.rankic < 0]
    ablation = pd.read_csv(run / "metrics/ablation_summary.csv").set_index("trial_id")
    full = ablation.loc["BLEND_100_A025"]
    baseline = ablation.loc["BLEND_0_A025"]
    no_smoothing_baseline_sr = float(ablation.loc["BLEND_0_A100"].net_sharpe)
    matched = pd.read_csv(run / "metrics/matched_overnight_control.csv")
    if int(matched.loc[matched.period.eq("pooled_all_eval"), "common_dates"].max()) != 0:
        raise AssertionError("Corrected duration unexpectedly has a matched B control")

    prior = ROOT / "artifacts/DM-20260924-11/run-20260924T194237Z/metrics/matched_overnight_control.csv"
    prior_matched = pd.read_csv(prior)
    prior_night = prior_matched.query("period == 'pooled_all_eval' and outcome == 'raw_night'").iloc[0]
    prior_o2o = prior_matched.query("period == 'pooled_all_eval' and outcome == 'official_o2o_residual'").iloc[0]
    full_year_rows = prior_matched.loc[
        prior_matched.outcome.eq("raw_night") & prior_matched.period.isin(["2011", "2012", "2013", "2014", "2015"])
    ]
    pos_years = int((full_year_rows.A_minus_B_daily_mean > 0).sum())
    neg_years = int((full_year_rows.A_minus_B_daily_mean < 0).sum())

    conclusion = (
        f"**No-Go。sqrt(L)補正後も1日BOX予測は残らず、Phase 2へ進まない。** "
        f"event-only raw予測はRankIC {pooled_event.rankic:+.4f}、HAC5 t {pooled_event.rankic_hac_t:+.2f}、"
        f"hit {pooled_event.rankic_hit:.1%}、Q monotonicity {pooled_event.q_monotonicity:+.2f}。年別RankIC符号は正が{','.join(positive_event_years)}、負が{','.join(negative_event_years)}。 "
        f"BOX 100%・alpha .25はB00に対しNet SR {baseline.net_sharpe:.3f}→{full.net_sharpe:.3f} "
        f"(Δ{full.delta_net_sharpe_same_alpha_b00:+.4f})、年率Net {full.delta_annual_net_same_alpha_b00:+.3%}、"
        f"Gross {full.delta_annual_gross_same_alpha_b00:+.3%}、annual cost差 {full.delta_cost_same_alpha_b00:+.3%}、"
        f"turnover差 {full.delta_turnover_same_alpha_b00:+.5f}/日。平均|weight差| {full.mean_abs_weight_diff:.6f}、"
        f"変化した銘柄日 {full.weight_changed_share:.2%}。alpha=1はB00自体がNet SR {no_smoothing_baseline_sr:.3f}となり、EWMAを外す経路は不良。 "
        f"補正durationは高値eventの{lmax_share:.2%}がLmax=120に達し、期間分散を下限集中から上限集中へ移しただけだった。"
        "対照群もゼロとなり修正版のmatched comparisonは推定不能。追加閾値調整・interaction・Short policy等の救済試行を行わず、BOX_RIDGE_001の1日O2O研究を停止する。Valid未読。"
    )
    report = report_path.read_text(encoding="utf-8")
    left = report.index("## 結論\n\n") + len("## 結論\n\n")
    right = report.index("\n## Blend / EWMA ablation", left)
    report = report[:left] + conclusion + report[right:]

    start = report.index("## Matched overnight control\n")
    end = report.index("\n## 情報時点・監査", start)
    matched_text = (
        "## Matched overnight control\n\n"
        "A=新高値eventかつ修正duration>0、B=同日のB00高値eventからAを除いた集合。sqrt(L)定義では高値eventのほぼ全てがAとなり、"
        "Bは全期間0行、共通日は0日だったため、群間差は推定不能。これは夜間効果の不在を意味せず、このduration定義で対照群を作れないことを示す。\n\n"
        f"元定義のDM-20260924-11ではraw夜間平均がA {prior_night.A_daily_mean:+.5f}/日、B {prior_night.B_daily_mean:+.5f}/日、"
        f"A−B {prior_night.A_minus_B_daily_mean:+.5f}/日（単純年率 {prior_night.A_minus_B_annualized_arithmetic:+.2%}）、"
        f"公式O2O残差のA−Bは {prior_o2o.A_minus_B_daily_mean:+.5f}/日。双方に正のraw夜間平均があり、"
        f"A−Bの2011–2015年別符号は{pos_years}年正・{neg_years}年負で安定しないため、BOX固有overnight alphaとは結論しない。"
        "このcontrolは日付だけを合わせた記述比較で、銘柄属性を揃えた因果推定ではない。"
    )
    report = report[:start] + matched_text + report[end:]
    report = report.replace(
        "| Source firewall / alignment / accounting |",
        "| Corrected feature static leak scan | **PASS** |\n| Source firewall / alignment / accounting |",
    )
    lines = []
    for line in report.splitlines():
        if line.startswith("| box_duration_sqrt_l |"):
            cells = line.split("|")
            if len(cells) > 12:
                for pos in range(7, 13):
                    cells[pos] = " — "
                for pos in (4, 5, 6):
                    if "nan" in cells[pos].lower():
                        cells[pos] = " — "
                line = "|".join(cells)
        lines.append(line)
    report = "\n".join(lines) + "\n"
    distribution_marker = "Histogram、年別分布、event数とduration別targetは"
    report_lines = []
    for line in report.splitlines():
        if distribution_marker in line:
            suffix = line[line.index(distribution_marker):]
            line = (f"高値eventの{lmax_share:.2%}がLmax=120でdurationの断面分散がないため、"
                    f"`box_duration_sqrt_l` のQ1–Q5は欠測扱いとした。{suffix}")
        report_lines.append(line)
    report = "\n".join(report_lines) + "\n"
    report_path.write_text(report, encoding="utf-8")

    audit = {
        "status": "PASS",
        "purpose": "Finalize decision and represent non-identifiable quintiles/matched groups as unavailable.",
        "corrected_feature_static_scan": source_audit,
        "source_metrics_modified": True,
        "event_univariate_change": "Only Q1-Q5, monotonicity, and quintile day count are nulled for box_duration_sqrt_l due to >99% Lmax saturation; event-level RankIC/HAC/hit remain unchanged.",
        "matched_control": "Corrected-definition B group empty; rendered as not estimable, not zero return.",
        "original_definition_control_reference": "DM-20260924-11 matched_overnight_control.csv",
        "decision": "No-Go; stop one-day BOX_RIDGE_001; no Phase 2, no threshold adjustment.",
        "valid_accessed": False,
        "raw_target_read": False,
        "code_sha256": digest(Path(__file__)),
    }
    (run / "audit/report_finalization.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_json = run / "run.json"
    meta = json.loads(run_json.read_text(encoding="utf-8"))
    meta["exit_code"] = 0
    meta["report_postprocessing"] = "Decision plus non-estimable degenerate quintiles and matched groups; see audit/report_finalization.json"
    meta["report_postprocess_code_sha256"] = audit["code_sha256"]
    run_json.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    finalize(parser.parse_args().run)
