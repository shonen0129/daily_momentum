"""One bounded Train-only retest using the pre-registered sqrt(L) duration."""
from __future__ import annotations

import argparse
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
from research.experiments import box_phase1_diagnostics as diag
from research.experiments.box_sqrt_duration_features import build_box_state
from research.experiments.slope_range_volume_ml import leg_account
from stock_comp_2026.strategies.dm_variable_box_breakout import features, models


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DM-20260925-01"
PRIOR_FEATURE_RUN = "artifacts/DM-20260924-10/run-20260924T081826Z"
PRIOR_PHASE1_RUN = "artifacts/DM-20260924-11/run-20260924T194237Z"
YEARS = models.YEARS
CUTOFFS = ("2010-12-30", "2012-12-28", "2015-12-30")


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False,
                               default=lambda x: x.item() if isinstance(x, np.generic) else str(x)) + "\n",
                    encoding="utf-8")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def future_mutation(prices, cutoff):
    changed = prices.copy()
    dates = changed.index.get_level_values("Date")
    future = dates > pd.Timestamp(cutoff)
    for column in ("High", "Low", "Close"):
        changed.loc[future, column] = changed.loc[future, column] * -3.14 + 888.0
    changed.loc[future, "AdjustmentFactor"] = 1.0
    if future.any():
        first = dates[future].min()
        changed.loc[future & (dates == first), "AdjustmentFactor"] = 0.25
    return changed


def prefix_audit(inputs, prices):
    records = []
    for cutoff in CUTOFFS:
        changed_inputs = dict(inputs)
        changed_inputs["prices_daily_quotes"] = future_mutation(prices, cutoff)
        original = build_box_state(inputs)
        mutated = build_box_state(changed_inputs)
        dates = original.index.get_level_values("Date")
        prefix = original.index[dates <= pd.Timestamp(cutoff)]
        columns = ["box_duration", "box_width_atr", "close_position", "box_cr_sqrt_l"]
        pd.testing.assert_frame_equal(original.loc[prefix, columns], mutated.loc[prefix, columns],
                                      check_exact=True)
        records.append({"cutoff": cutoff, "prefix_rows": int(len(prefix)),
                        "mutated_source": "prices_daily_quotes_train.parquet",
                        "columns": columns, "result": "bitwise exact"})
    return {"status": "PASS", "method": "future mutation after cutoff; changed OHLC and AdjustmentFactor",
            "cutoffs": records}


def matched_hac(events, x, b00_raw, outcomes, eval_index):
    box_a = events & x["box_duration"].gt(0)
    box_b = b00_raw.gt(0.0) & ~box_a
    rows = []
    for period in ["pooled_all_eval", *[str(y) for y in YEARS]]:
        idx = eval_index if period == "pooled_all_eval" else eval_index[
            eval_index.get_level_values("Date").year == int(period)]
        a_mask = box_a.reindex(idx).fillna(False)
        b_mask = box_b.reindex(idx).fillna(False)
        count_a = a_mask.groupby(level="Date").sum()
        count_b = b_mask.groupby(level="Date").sum()
        common = count_a.index[(count_a > 0) & (count_b > 0)]
        for label, value in outcomes.items():
            a = value.reindex(idx).where(a_mask).groupby(level="Date").mean().reindex(common).dropna()
            b = value.reindex(idx).where(b_mask).groupby(level="Date").mean().reindex(common).dropna()
            dates = a.index.intersection(b.index)
            diff = a.reindex(dates) - b.reindex(dates)
            rows.append({"period": period, "outcome": label, "common_dates": int(len(dates)),
                         "A_rows": int(count_a.reindex(dates).sum()),
                         "B_rows": int(count_b.reindex(dates).sum()),
                         "A_daily_mean": float(a.reindex(dates).mean()),
                         "B_daily_mean": float(b.reindex(dates).mean()),
                         "A_minus_B_daily_mean": float(diff.mean()),
                         "A_minus_B_annualized_arithmetic": float(diff.mean() * 252),
                         "A_minus_B_HAC5_t": evaluation.hac_t(diff)})
    return pd.DataFrame(rows)


def build_report(run_id, output, summary_rows, fold_rows, event_rows,
                 univariate_rows, duration_rows, matched_rows, timing_rows,
                 audit, replay, eval_span):
    report_dir = ROOT / "reports" / EXPERIMENT_ID
    report_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {EXPERIMENT_ID}: BOX sqrt(L) duration Phase 1 再診断", "",
        f"- Run: `{run_id}` (`{output.as_posix()}/run.json`)。初回Phase 1で成立ボックスの87.2%がL≤10、中央値5と判明した条件分岐により、案Aを一度だけ事前固定して再検証。",
        f"- Train only、既読期間の記述診断。評価期間 {eval_span[0]}〜{eval_span[1]}、2016 stubを分離、年末2 signal日purge。Valid・raw_target・未参照区間は未読。",
        "- 公式O2Oは t+1 Open → t+2 Open。モデルはannual expanding Ridge (lambda=1)、5特徴、同一target。BOX blend 0/50/100% × EWMA alpha .25/1.0の6通りだけ。",
        "- 変更はduration定義のみ: CR(L)=(prior High max−prior Low min)/(prior ATR20×sqrt(L))、L={5,10,…,120}でCR<3を満たす最大L。widthは選ばれた窓のATR比、close positionは同窓内t−1 Close。",
        "", "## 結論", "",
        "今回の表は記述的Train診断であり候補の再選択には使わない。下のevent-only予測、BOX 100%のweight差、Net/turnover/cost、年次符号を合わせて判断し、残る場合だけを明記する。", "",
        "## Blend / EWMA ablation", "",
        "全評価期間のpooled指標は年末purge後の2011–2016-03。2011–2015の年次pooledと2016 stubは下表に分離。各行のSharpeはその行の日次系列から算出。", "",
        "| Trial | Blend | α | Net SR | ΔNet SR vs same-α B00 | ΔGross ann | ΔNet ann | ΔTurnover/day | ΔCost ann | Mean |Δweight| | Changed weight rows | Corr(pred,weight) | Max DD |",
        "|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(f"| {row['trial_id']} | {row['blend']:.0%} | {row['alpha']:.2f} | {row['net_sharpe']:.3f} | {row['delta_net_sharpe_same_alpha_b00']:+.3f} | {row['delta_annual_gross_same_alpha_b00']:+.2%} | {row['delta_annual_net_same_alpha_b00']:+.2%} | {row['delta_turnover_same_alpha_b00']:+.5f} | {row['delta_cost_same_alpha_b00']:+.3%} | {row['mean_abs_weight_diff']:.6f} | {row['weight_changed_share']:.2%} | {row['raw_pred_final_weight_pearson']:+.3f} | {row['max_drawdown_additive']:+.2%} |")
    lines += ["", "## Annual stability and baseline differences", "",
              "| Trial | Period | Days | Gross SR | Net SR | Annual gross | Annual net | Cost | Turnover/day | RankIC | HAC5 t | Hit | Q mono | Long net | Short net | Max DD |",
              "|:---|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in fold_rows:
        lines.append(f"| {row['trial_id']} | {row['year']} | {row['days']} | {row['gross_sharpe']:.3f} | {row['net_sharpe']:.3f} | {row['annual_gross']:+.2%} | {row['annual_net']:+.2%} | {row['annual_cost']:.2%} | {row['turnover']:.5f} | {row['rankic']:+.4f} | {row['rankic_t_hac5']:+.2f} | {row['rankic_hit']:.3f} | {row['q_monotonicity']:+.2f} | {row['annual_long']:+.2%} | {row['annual_short']:+.2%} | {row['max_drawdown_additive']:+.2%} |")
    lines += ["", "## Event-only予測と単変量", "",
              "event内RankICは日次Spearman平均、HAC tはlag 5、hitは日次RankIC>0の比率。Q1〜Q5は日次5群の群別平均を等ウェイトし、monotonicityは群平均と順位のSpearman。2016はstub。", "",
              "| Feature | Period | Rows | RankIC | HAC5 t | Hit | Q1 | Q2 | Q3 | Q4 | Q5 | Q mono |",
              "|:---|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in [*event_rows, *univariate_rows]:
        label = row.get("feature", "BOX raw prediction")
        lines.append(f"| {label} | {row['period']} | {row['rows']} | {row['rankic']:+.4f} | {row['rankic_hac_t']:+.2f} | {row['rankic_hit']:.3f} | {row['q1_return']:+.5f} | {row['q2_return']:+.5f} | {row['q3_return']:+.5f} | {row['q4_return']:+.5f} | {row['q5_return']:+.5f} | {row['q_monotonicity']:+.2f} |")
    lines += ["", "## sqrt(L) duration distribution", "",
              "| Population | Rows | Mean | Median | P10 | P25 | P50 | P75 | P90 | L5 / qualified | L≤10 / qualified | Lmax / qualified | No box | Failure given history | Width-duration Spearman |",
              "|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in duration_rows:
        lines.append(f"| {row['population']} | {row['rows']} | {row['mean']:.2f} | {row['median']:.1f} | {row['p10']:.1f} | {row['p25']:.1f} | {row['p50']:.1f} | {row['p75']:.1f} | {row['p90']:.1f} | {row['L5_share_qualified']:.1%} | {row['L_le_10_share_qualified']:.1%} | {row['Lmax_share_qualified']:.1%} | {row['no_box_share_all']:.1%} | {row['condition_failure_share_given_history']:.1%} | {row['duration_width_spearman']:+.3f} |")
    lines += ["", "Histogram、年別分布、event数とduration別targetは `duration_histogram.csv` / `duration_by_year.csv` / `event_count_by_duration.csv`。", "",
              "## Matched overnight control", "",
              "A=新高値eventかつ修正duration>0、B=同日のB00高値eventからAを除いた集合。日別群平均を同じ日でpairedし、raw昼夜は市場調整前。HAC tはpaired日次A−B、lag 5。群のサイズ・構成は完全一致ではないので因果効果とは解釈しない。", "",
              "| Period | Outcome | Common dates | A rows | B rows | A−B/day | A−B annualized | HAC5 t |",
              "|:---|:---|---:|---:|---:|---:|---:|---:|"]
    for row in matched_rows:
        lines.append(f"| {row['period']} | {row['outcome']} | {row['common_dates']} | {row['A_rows']} | {row['B_rows']} | {row['A_minus_B_daily_mean']:+.5f} | {row['A_minus_B_annualized_arithmetic']:+.2%} | {row['A_minus_B_HAC5_t']:+.2f} |")
    lines += ["", "## 情報時点・監査", "",
              "| Stage | Time |", "|:---|:---|",
              "| sqrt(L) duration / width / close position | t−1 High/Low/Close + prior ATR20; available at t Close |",
              "| breakout event | t Close vs highs through t−1; available before entry |",
              "| entry / diagnostic day endpoint / exit | t+1 Open / t+1 Close / t+2 Open |",
              f"| sqrt(L) future-mutation prefix | **{audit['sqrt_duration_prefix']['status']}**, 3 cutoffs |",
              f"| Auxiliary volume/touch/t-close prefix | **{audit['auxiliary_prefix']['status']}** |",
              f"| Prior core builder audit | **{audit['prior_core_prefix_status']}** (unchanged columns reused) |",
              f"| B00 replay against prior Phase 1 | **{replay['b00_replay']}** |",
              f"| Deterministic Ridge prediction replay | **{replay['model_replay']}** |",
              f"| Source firewall / alignment / accounting | **{replay['firewall']} / {replay['alignment']} / {replay['accounting']}** |",
              "", "元の5特徴ボックス定義は実装コードに反映せず、今回のsqrt(L)定義も研究専用の単発診断である。Valid・raw_target・未参照区間は未読。", ""]
    path = report_dir / "REPORT.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run(config_path, output_path):
    started = time.monotonic()
    config_path, output = Path(config_path), Path(output_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    expected_trials = {"BLEND_0_A025", "BLEND_50_A025", "BLEND_100_A025",
                       "BLEND_0_A100", "BLEND_50_A100", "BLEND_100_A100"}
    if (config.get("experiment_id") != EXPERIMENT_ID or config.get("data_split") != "train"
            or config.get("valid_evaluation") is not False or config.get("selection_eligible") is not False
            or config.get("max_trials") != 6 or {x["trial_id"] for x in config.get("trials", [])} != expected_trials
            or config.get("parameters", {}).get("duration_definition") != "sqrt_l_normalized_max_qualifying"):
        raise ValueError("Run config differs from the single pre-registered sqrt(L) retest")
    for folder in ("models", "predictions", "metrics", "audit", "logs"):
        (output / folder).mkdir(parents=True, exist_ok=True)
    run_path = output / "run.json"
    meta = json.loads(run_path.read_text(encoding="utf-8"))
    expected_hashes = {key: digest(output / key) for key in ("plan.md", "config.json", "experiment.json")}
    if expected_hashes != meta["snapshot_sha256"]:
        raise AssertionError("Prepared plan/config snapshot hash mismatch")
    code_paths = [Path(__file__), Path(build_box_state.__code__.co_filename), Path(diag.__file__),
                  Path(features.__file__), Path(models.__file__), Path(evaluation.__file__), Path(firewall.__file__)]
    meta.update({"status": "running", "started_at_utc": utc_now(), "actual_trials": 0,
                 "command": sys.argv, "environment": {"python": sys.version,
                 "platform": platform.platform(), "numpy": np.__version__, "pandas": pd.__version__},
                 "code_sha256": {str(p.relative_to(ROOT)): digest(p) for p in code_paths}})
    dump(run_path, meta)
    try:
        data_dir = ROOT / "stock_comp_2026/input"
        prior_x_path = ROOT / PRIOR_FEATURE_RUN / "predictions/box_features.parquet"
        prior_stage_path = ROOT / PRIOR_PHASE1_RUN / "predictions/signal_stages.parquet"
        firewall.install(allowed_artifacts=[prior_x_path, prior_stage_path])
        input_names = ("prices_daily_quotes_train.parquet", "raw_return_1day_train.parquet",
                       "beta_1day_train.parquet", "topix_return_1day_train.parquet",
                       "target_1day_train.parquet")
        data_hashes = {name: digest(data_dir / name) for name in input_names}
        inputs = features.load_inputs(data_dir, split="train")
        prices = pd.read_parquet(data_dir / "prices_daily_quotes_train.parquet",
                                 columns=["Open", "High", "Low", "Close", "Volume", "AdjustmentFactor"]).sort_index()
        index = inputs["raw_return_1day"].index
        if not index.equals(prices.index):
            raise AssertionError("Train price and raw-return indexes differ")
        inputs["prices_daily_quotes"] = prices
        target = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index()
        if not index.equals(target.index):
            raise AssertionError("Train features and official target indexes differ")

        baseline_x = pd.read_parquet(prior_x_path).sort_index()
        x = features.build_features(inputs)
        if not x.index.equals(index) or not baseline_x.index.isin(x.index).all():
            raise AssertionError("Feature index differs from Train inputs or the saved baseline slice")
        prior_columns = list(features.FEATURE_COLUMNS)
        pd.testing.assert_frame_equal(
            x.loc[baseline_x.index, prior_columns],
            baseline_x.loc[:, prior_columns], check_exact=True)
        sqrt_state = build_box_state(inputs)
        if not sqrt_state.index.equals(index):
            raise AssertionError("sqrt(L) state index changed")
        for column in ("box_duration", "box_width_atr", "close_position"):
            x[column] = sqrt_state[column]
        x["box_cr_sqrt_l"] = sqrt_state["box_cr_sqrt_l"]
        unchanged = [c for c in baseline_x.columns
                     if c not in ("box_duration", "box_width_atr", "close_position", "box_cr_sqrt_l")]
        pd.testing.assert_frame_equal(x.loc[baseline_x.index, unchanged],
                                      baseline_x.loc[:, unchanged], check_exact=True)

        sqrt_prefix = prefix_audit(inputs, prices)
        prior_aux = diag.build_auxiliary(prices, index, x)
        auxiliary_prefix = diag.compute_aux_prefix_audit(prices, x, prior_aux, CUTOFFS)
        prior_audit = json.loads((ROOT / PRIOR_FEATURE_RUN / "audit/causality.json").read_text(encoding="utf-8"))
        dump(output / "audit/causality.json", {
            "status": "PASS", "sqrt_duration_prefix": sqrt_prefix,
            "auxiliary_feature_prefix_audit": auxiliary_prefix,
            "prior_core_feature_audit_reference": f"{PRIOR_FEATURE_RUN}/audit/causality.json",
            "prior_core_prefix_status": prior_audit["status"],
        })

        predictions, training_records = models.walk_forward_predictions(x, target, model_dir=output / "models")
        replay_predictions, replay_records = models.walk_forward_predictions(x, target, model_dir=None)
        pd.testing.assert_series_equal(predictions, replay_predictions, check_exact=True)
        if training_records != replay_records:
            raise AssertionError("Ridge model replay differs")

        b00_raw = models.raw_base_signal(x)
        b00_a025 = models.smooth_by_listing(b00_raw, alpha=.25).rename("B00_EWMA_A025")
        prior_stages = pd.read_parquet(prior_stage_path).sort_index()
        pd.testing.assert_series_equal(b00_a025.reindex(prior_stages.index),
                                       prior_stages["B00_EWMA_A025"].rename("B00_EWMA_A025"),
                                       check_exact=True)

        eval_dates = diag.evaluation_dates(pd.DatetimeIndex(index.get_level_values("Date").unique()))
        eval_mask = index.get_level_values("Date").isin(eval_dates)
        eval_index = index[eval_mask]
        events = x["high_available"] & x["new_high_excess"].gt(0.0)
        event_score = predictions.reindex(index)
        box_rank = models.active_percentile(event_score.where(events))
        score_by_trial, weight_by_trial, account_by_trial, legs_by_trial = {}, {}, {}, {}
        stage_columns = {"raw_box_prediction": event_score, "event_rank": box_rank,
                         "B00_raw": b00_raw, "B00_EWMA_A025": b00_a025,
                         "is_new_high_event": events.astype(bool), **{
                             name: x[name] for name in ("box_duration", "box_width_atr", "close_position",
                                                       "relative_strength_60", "distance_to_prior_high",
                                                       "box_cr_sqrt_l")}}
        for blend in (0.0, .5, 1.0):
            for alpha in (.25, 1.0):
                trial = f"BLEND_{int(blend * 100)}_A{int(alpha * 100):03d}"
                _, blended, final = diag.score_path(b00_raw, predictions, x, blend, alpha)
                weight = evaluation.weights(final)[0]
                account = evaluation.daily_account(final, target)
                legs = leg_account(final, target)
                error = (legs["net_sum"].reindex(account.index) - account["net"]).abs().max()
                if not np.isfinite(error) or error > 1e-10:
                    raise AssertionError(f"Official account mismatch in {trial}: {error}")
                score_by_trial[trial], weight_by_trial[trial] = final, weight
                account_by_trial[trial] = account.reindex(eval_dates)
                legs_by_trial[trial] = legs.reindex(eval_dates)
                account.to_csv(output / f"metrics/daily_account_{trial}.csv", index_label="Date")
                legs.to_csv(output / f"metrics/daily_legs_{trial}.csv", index_label="Date")
                stage_columns[f"{trial}_blend"] = blended
                stage_columns[f"{trial}_ewma"] = final
                stage_columns[f"{trial}_weight"] = weight

        all_events = eval_index[events.reindex(eval_index).fillna(False).to_numpy()
                                & target.reindex(eval_index).notna().to_numpy()
                                & event_score.reindex(eval_index).notna().to_numpy()]
        event_rows = [{"period": "pooled_all_eval", **diag.percentile_metrics(event_score, target, all_events)}]
        for year in YEARS:
            event_rows.append({"period": str(year), **diag.percentile_metrics(event_score, target, all_events, year)})
        pd.DataFrame(event_rows).to_csv(output / "metrics/event_only_metrics.csv", index=False)

        aux = diag.build_auxiliary(prices, index, x)
        duration_rows, duration_year_rows = diag.duration_tables(x, aux, target, eval_index, events, output / "metrics")
        features_to_check = [
            ("box_duration_sqrt_l", "box_duration", 1.0), ("tightness_prior", "box_width_atr", -1.0),
            ("close_position_prior", "close_position", 1.0),
            ("distance_to_prior_high", "distance_to_prior_high", 1.0),
            ("relative_strength_60", "relative_strength_60", 1.0),
            ("breakout_volume_ratio", "breakout_volume_ratio", 1.0),
            ("upper_touch_density", "upper_touch_density", 1.0),
            ("box_duration_through_t", "box_duration_through_t", 1.0),
            ("tightness_through_t", "box_width_atr_through_t", -1.0),
            ("close_position_through_t", "close_position_through_t", 1.0),
        ]
        univariate_rows, timing_rows = [], []
        for name, column, direction in features_to_check:
            value = (x[column] if column in x else aux[column]) * direction
            valid = value.reindex(all_events).replace([np.inf, -np.inf], np.nan).dropna().index
            for period in ["pooled_all_eval", *[str(year) for year in YEARS]]:
                year = None if period == "pooled_all_eval" else int(period)
                row = {"feature": name, "period": period,
                       **diag.percentile_metrics(value, target, valid, year)}
                univariate_rows.append(row)
                if name in ("box_duration_sqrt_l", "tightness_prior", "close_position_prior",
                            "box_duration_through_t", "tightness_through_t", "close_position_through_t"):
                    timing_rows.append(row)
        pd.DataFrame(univariate_rows).to_csv(output / "metrics/event_univariate.csv", index=False)
        pd.DataFrame(timing_rows).to_csv(output / "metrics/timing_diagnostics.csv", index=False)

        raw_return = inputs["raw_return_1day"]["Return"].sort_index()
        calendar = pd.DatetimeIndex(index.get_level_values("Date").unique()).sort_values()
        ordinal = pd.Series(np.arange(len(calendar)), index=calendar)
        positions = ordinal.reindex(index.get_level_values("Date")).to_numpy()
        entry_dates = pd.DatetimeIndex([calendar[p + 1] if p + 1 < len(calendar) else pd.NaT for p in positions])
        exit_dates = pd.DatetimeIndex([calendar[p + 2] if p + 2 < len(calendar) else pd.NaT for p in positions])
        codes = index.get_level_values("Code")
        entry_index = pd.MultiIndex.from_arrays([entry_dates, codes], names=index.names)
        exit_index = pd.MultiIndex.from_arrays([exit_dates, codes], names=index.names)
        day_return = prices["Close"].reindex(entry_index).to_numpy() / prices["Open"].reindex(entry_index).to_numpy() - 1.0
        o2o_return = raw_return.reindex(exit_index).to_numpy()
        night_return = (1.0 + o2o_return) / (1.0 + day_return) - 1.0
        day_s, night_s = pd.Series(day_return, index=index), pd.Series(night_return, index=index)
        matched = diag.matched_control(events, x, b00_raw, target, day_s, night_s, eval_index)
        paired = matched_hac(events, x, b00_raw,
                             {"official_o2o_residual": target, "raw_day": day_s, "raw_night": night_s},
                             eval_index)
        paired.to_csv(output / "metrics/matched_overnight_control.csv", index=False)

        summary_rows, fold_rows, transmission_rows = [], [], []
        full_dates = eval_dates[eval_dates.year < 2016]
        stub_dates = eval_dates[eval_dates.year == 2016]
        base_for_alpha = {.25: "BLEND_0_A025", 1.0: "BLEND_0_A100"}
        for blend in (0.0, .5, 1.0):
            for alpha in (.25, 1.0):
                trial = f"BLEND_{int(blend * 100)}_A{int(alpha * 100):03d}"
                baseline = base_for_alpha[alpha]
                account = account_by_trial[trial]
                base_account = account_by_trial[baseline]
                metric = evaluation.metrics(account)
                weight_delta = weight_by_trial[trial].reindex(eval_index) - weight_by_trial[baseline].reindex(eval_index)
                active = all_events
                corr = diag.safe_corr(event_score.reindex(active), weight_by_trial[trial].reindex(active))
                diff = account - base_account
                base_metric = evaluation.metrics(base_account)
                full_metric = evaluation.metrics(account.reindex(full_dates))
                stub_metric = evaluation.metrics(account.reindex(stub_dates))
                annual = [evaluation.metrics(account.reindex(eval_dates[eval_dates.year == year])) for year in range(2011, 2016)]
                summary_rows.append({"trial_id": trial, "blend": blend, "alpha": alpha, **metric,
                    "delta_net_sharpe_same_alpha_b00": metric["net_sharpe"] - base_metric["net_sharpe"],
                    "delta_annual_gross_same_alpha_b00": float(diff["gross"].mean() * 252),
                    "delta_annual_net_same_alpha_b00": float(diff["net"].mean() * 252),
                    "delta_turnover_same_alpha_b00": float(diff["turnover"].mean()),
                    "delta_cost_same_alpha_b00": float(diff["cost"].mean() * 252),
                    "mean_abs_weight_diff": float(weight_delta.abs().mean()),
                    "weight_changed_share": float(weight_delta.abs().gt(1e-15).mean()),
                    "raw_pred_final_weight_pearson": corr,
                    "full_years_net_sharpe": full_metric["net_sharpe"],
                    "full_years_annual_net": full_metric["annual_net"],
                    "full_years_median_annual_net_sr": float(np.median([a["net_sharpe"] for a in annual])),
                    "full_years_worst_annual_net_sr": float(np.min([a["net_sharpe"] for a in annual])),
                    "stub_2016_net_sharpe": stub_metric["net_sharpe"],
                    "stub_2016_annual_net": stub_metric["annual_net"]})
                for year in range(2011, 2016):
                    days = eval_dates[eval_dates.year == year]
                    m = evaluation.metrics(account.reindex(days))
                    bm = evaluation.metrics(base_account.reindex(days))
                    fold_rows.append({"trial_id": trial, "year": str(year), **m,
                        **{f"delta_{key}_vs_same_alpha_b00": m[key] - bm[key]
                           for key in ("rankic", "gross_sharpe", "net_sharpe", "turnover", "annual_cost")}})
                fold_rows.append({"trial_id": trial, "year": "2011-2015", **full_metric})
                fold_rows.append({"trial_id": trial, "year": "2016", **stub_metric})
                transmission_rows.append({"trial_id": trial,
                    "raw_pred_final_weight_pearson": corr,
                    "mean_abs_weight_diff": float(weight_delta.abs().mean()),
                    "max_abs_weight_diff": float(weight_delta.abs().max()),
                    "weight_changed_share": float(weight_delta.abs().gt(1e-15).mean()),
                    "delta_gross_annual": float(diff["gross"].mean() * 252),
                    "delta_turnover_daily": float(diff["turnover"].mean()),
                    "delta_cost_annual": float(diff["cost"].mean() * 252),
                    "delta_net_annual": float(diff["net"].mean() * 252)})

        stages = pd.DataFrame(stage_columns, index=index).loc[eval_mask].sort_index()
        stages.to_parquet(output / "predictions/signal_stages.parquet")
        weights_out = pd.DataFrame({trial: weight.reindex(index).loc[eval_mask]
                                    for trial, weight in weight_by_trial.items()}).sort_index()
        weights_out.to_parquet(output / "predictions/portfolio_weights.parquet")
        pd.DataFrame(summary_rows).to_csv(output / "metrics/ablation_summary.csv", index=False)
        pd.DataFrame(fold_rows).to_csv(output / "metrics/ablation_fold_metrics.csv", index=False)
        pd.DataFrame(transmission_rows).to_csv(output / "metrics/stage_transmission.csv", index=False)
        firewall.save(output / "audit/firewall.json")
        opened = json.loads((output / "audit/firewall.json").read_text(encoding="utf-8"))["opened_parquets"]
        if any("_valid" in Path(name).name.lower() or "raw_target" in Path(name).name.lower() for name in opened):
            raise AssertionError("Forbidden source appears in firewall audit")

        report_audit = {"sqrt_duration_prefix": sqrt_prefix,
                        "auxiliary_prefix": auxiliary_prefix,
                        "prior_core_prefix_status": prior_audit["status"]}
        replay = {"b00_replay": "PASS bitwise against DM-20260924-11",
                  "model_replay": "PASS bitwise walk-forward rerun",
                  "firewall": "PASS Train-only; raw_target/Valid unread",
                  "alignment": "PASS full feature/target index exact",
                  "accounting": "PASS daily Long+Short net reconciled for all six trials"}
        report = build_report(output.name, output, summary_rows, fold_rows, event_rows,
                              univariate_rows, duration_rows, paired.to_dict("records"), timing_rows,
                              report_audit, replay,
                              (str(eval_dates.min().date()), str(eval_dates.max().date())))
        summary = {"status": "PASS", "experiment_id": EXPERIMENT_ID, "run_id": output.name,
                   "actual_trials": 6, "valid_accessed": False, "raw_target_read": False,
                   "evaluation_days": int(len(eval_dates)),
                   "evaluation_span": [str(eval_dates.min().date()), str(eval_dates.max().date())],
                   "duration_definition": "max L in 5..120 step5 with Range/(ATR20*sqrt(L)) < 3",
                   "prefix_audit": sqrt_prefix, "auxiliary_prefix_audit": auxiliary_prefix,
                   "prior_core_prefix_status": prior_audit["status"], "input_data_sha256": data_hashes,
                   "opened_parquets": opened, "report": str(report.relative_to(ROOT))}
        dump(output / "audit/summary.json", summary)
        meta.update({"status": "completed", "completed_at_utc": utc_now(),
                     "elapsed_seconds": time.monotonic() - started, "actual_trials": 6,
                     "train_data_sha256": data_hashes, "valid_accessed": False,
                     "raw_target_read": False, "prefix_invariance": "PASS",
                     "source_firewall": "PASS", "deterministic_replay": "PASS",
                     "account_reconciliation": "PASS", "report": str(report.relative_to(ROOT))})
        dump(run_path, meta)
        print(f"[Done] {report}", flush=True)
    except BaseException as error:
        meta.update({"status": "failed", "completed_at_utc": utc_now(),
                     "failure": repr(error), "elapsed_seconds": time.monotonic() - started})
        try:
            firewall.save(output / "audit/firewall.json")
        except BaseException:
            pass
        dump(run_path, meta)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.config, args.output)
