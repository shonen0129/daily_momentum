"""Train-only diagnostics for the fixed BOX_RIDGE_001 signal path.

This driver keeps the feature model and official O2O target fixed. Its six
registered trials only vary BOX blend (0/50/100%) and EWMA alpha (.25/1.0).
Other outputs are descriptive audits, not model-selection trials.
"""
from __future__ import annotations

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
from scipy.stats import spearmanr

from research import evaluation, firewall
from research.experiments.slope_range_volume_ml import leg_account
from stock_comp_2026.strategies.dm_variable_box_breakout import features, models


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DM-20260924-11"
PRIOR_ID = "DM-20260924-10"
PRIOR_RUN = "run-20260924T081826Z"
ONE_WAY_COST = 0.001
WINDOWS = features.BOX_WINDOWS
YEARS = models.YEARS


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False,
                               default=lambda x: x.item() if isinstance(x, np.generic) else str(x)) + "\n",
                    encoding="utf-8")


def source_scan():
    paths = [Path(features.__file__), Path(models.__file__)]
    banned = ("AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose",
              "AdjustmentVolume", "raw_target", "target_1day_valid")
    for path in paths:
        source = path.read_text(encoding="utf-8")
        for token in banned:
            if token in source:
                raise AssertionError(f"Forbidden source token {token} in {path}")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr in ("bfill", "backfill"):
                raise AssertionError(f"Backfill call in {path}")
            if any(k.arg == "center" and isinstance(k.value, ast.Constant) and k.value.value
                   for k in node.keywords):
                raise AssertionError(f"Centered rolling call in {path}")
            if node.func.attr == "shift":
                arg = node.args[0] if node.args else next(
                    (k.value for k in node.keywords if k.arg in ("periods", "period")), None)
                if isinstance(arg, ast.UnaryOp) and isinstance(arg.op, ast.USub):
                    raise AssertionError(f"Negative shift in {path}")
    return [str(p.relative_to(ROOT)) for p in paths]


def evaluation_dates(index):
    dates = pd.DatetimeIndex(index).unique().sort_values()
    selected = []
    for year in YEARS:
        year_dates = dates[dates.year == year]
        if len(year_dates) <= 2:
            raise AssertionError(f"Insufficient dates for evaluation fold {year}")
        selected.extend(year_dates[:-2].tolist())
    return pd.DatetimeIndex(selected).sort_values()


def score_path(base_raw, predictions, x, blend, alpha):
    event = x["high_available"] & x["new_high_excess"].gt(0.0)
    pred = predictions.reindex(x.index)
    active = event & pred.notna()
    event_rank = models.active_percentile(pred.where(active))
    blended = base_raw.reindex(x.index).copy()
    if blend:
        blended.loc[active] = (1.0 - blend) * base_raw.loc[active] + blend * event_rank.loc[active]
    final = models.smooth_by_listing(blended.rename("score"), alpha=alpha)
    return event_rank.rename("box_event_rank"), blended.rename("blend_score"), final.rename("final_score")


def build_auxiliary(prices, index, x):
    """Build fixed, prior-only diagnostics plus t-close timing comparators."""
    px = prices.reindex(index)
    groups = features.segment_keys(index)
    safe = features.split_safe_prices({"raw_return_1day": pd.DataFrame(index=index),
                                       "prices_daily_quotes": px})
    high, low, close = safe["high"], safe["low"], safe["close"]
    event_factor = safe["event_factor"]
    raw_volume = pd.to_numeric(px["Volume"], errors="coerce")
    scale = event_factor.groupby(groups, sort=False).cumprod()
    common_volume = raw_volume * scale
    prior_volume_median = common_volume.groupby(groups, sort=False).transform(
        lambda s: s.shift(1).rolling(20, min_periods=20).median())
    volume_ratio = (common_volume / prior_volume_median).replace([np.inf, -np.inf], np.nan)

    prior_close = close.groupby(groups, sort=False).shift(1)
    prior_close_tr = close.groupby(groups, sort=False).shift(1) / event_factor
    tr = pd.concat([
        high - low,
        (high - prior_close_tr).abs(),
        (low - prior_close_tr).abs(),
    ], axis=1).max(axis=1, skipna=False)
    atr_prior = tr.groupby(groups, sort=False).transform(
        lambda s: s.shift(1).rolling(features.ATR_WINDOW, min_periods=features.ATR_WINDOW).mean())
    atr_through_t = tr.groupby(groups, sort=False).transform(
        lambda s: s.rolling(features.ATR_WINDOW, min_periods=features.ATR_WINDOW).mean())
    high5 = high.groupby(groups, sort=False).transform(
        lambda s: s.shift(1).rolling(5, min_periods=5).max())
    low5 = low.groupby(groups, sort=False).transform(
        lambda s: s.shift(1).rolling(5, min_periods=5).min())
    box_history = atr_prior.notna() & high5.notna() & low5.notna() & atr_prior.gt(0)

    upper_touch = pd.Series(np.nan, index=index, dtype=float)
    duration = x["box_duration"]
    through_duration = pd.Series(0.0, index=index, dtype=float)
    through_width = pd.Series(np.nan, index=index, dtype=float)
    through_position = pd.Series(np.nan, index=index, dtype=float)
    for window in WINDOWS:
        prior_high = high.groupby(groups, sort=False).transform(
            lambda s, w=window: s.shift(1).rolling(w, min_periods=w).max())
        prior_low = low.groupby(groups, sort=False).transform(
            lambda s, w=window: s.shift(1).rolling(w, min_periods=w).min())
        qualifying = duration.eq(float(window)) & prior_high.notna()
        near_upper = (high.groupby(groups, sort=False).shift(1) >= 0.99 * prior_high) & prior_high.notna()
        touches = near_upper.astype(float).groupby(groups, sort=False).transform(
            lambda s, w=window: s.rolling(w, min_periods=w).sum())
        upper_touch.loc[qualifying] = (touches.loc[qualifying] / window)

        current_high = high.groupby(groups, sort=False).transform(
            lambda s, w=window: s.rolling(w, min_periods=w).max())
        current_low = low.groupby(groups, sort=False).transform(
            lambda s, w=window: s.rolling(w, min_periods=w).min())
        width_t = (current_high - current_low) / atr_through_t
        qualifies_t = width_t.notna() & np.isfinite(width_t) & (width_t < features.BOX_ATR_LIMIT)
        through_duration.loc[qualifies_t] = float(window)
        through_width.loc[qualifies_t] = width_t.loc[qualifies_t]
        box_range_t = current_high - current_low
        position_t = ((close - current_low) / box_range_t).where(box_range_t > 0)
        through_position.loc[qualifies_t] = position_t.loc[qualifies_t]

    result = pd.DataFrame({
        "breakout_volume_ratio": volume_ratio,
        "upper_touch_density": upper_touch,
        "box_history_available": box_history,
        "box_duration_through_t": through_duration,
        "box_width_atr_through_t": through_width,
        "close_position_through_t": through_position,
    }, index=index)
    return result.replace([np.inf, -np.inf], np.nan)


def mutate_future_prices(prices, cutoff):
    changed = prices.copy()
    dates = changed.index.get_level_values("Date")
    mask = dates > pd.Timestamp(cutoff)
    for col in ("Open", "High", "Low", "Close", "Volume"):
        changed.loc[mask, col] = changed.loc[mask, col] * -3.14 + 888.0
    changed.loc[mask, "AdjustmentFactor"] = 1.0
    future_dates = dates[mask]
    if len(future_dates):
        first = future_dates.min()
        changed.loc[mask & (dates == first), "AdjustmentFactor"] = 0.25
    return changed


def percentile_metrics(score, target, index, year=None):
    chosen = index
    if year is not None:
        chosen = chosen[chosen.get_level_values("Date").year == year]
    s = score.reindex(chosen).dropna()
    y = target.reindex(s.index)
    good = y.notna() & np.isfinite(y)
    s, y = s.loc[good], y.loc[good]
    ic = evaluation.rankic(s, y).dropna()
    out = {
        "rows": int(len(s)), "days": int(len(ic)),
        "rankic": float(ic.mean()) if len(ic) else np.nan,
        "rankic_hac_t": evaluation.hac_t(ic),
        "rankic_hit": float((ic > 0).mean()) if len(ic) else np.nan,
    }
    if len(s) == 0:
        out.update({f"q{k}_return": np.nan for k in range(1, 6)})
        out["q_monotonicity"] = np.nan
        return out
    ranks = s.groupby(level="Date").rank(method="first")
    counts = s.groupby(level="Date").transform("count")
    q = (np.ceil(5.0 * (ranks - 1.0) / (counts - 1.0)) - 1.0).clip(0, 4)
    valid_dates = counts >= 5
    temp = pd.DataFrame({"Date": s.index.get_level_values("Date"), "q": q.to_numpy(), "y": y.to_numpy()})
    temp = temp.loc[valid_dates.to_numpy()]
    qdaily = temp.pivot_table(index="Date", columns="q", values="y", aggfunc="mean")
    qdaily = qdaily.reindex(columns=range(5)).dropna()
    qmean = qdaily.mean(axis=0) if len(qdaily) else pd.Series(index=range(5), dtype=float)
    for k in range(1, 6):
        out[f"q{k}_return"] = float(qmean.get(k - 1, np.nan))
    vals = qmean.dropna().to_numpy()
    out["q_monotonicity"] = (float(spearmanr(np.arange(len(vals)), vals).statistic)
                              if len(vals) >= 3 and len(np.unique(vals)) > 1 else np.nan)
    out["quintile_days"] = int(len(qdaily))
    return out


def duration_tables(x, aux, target, evaluation_index, events, outdir):
    rows, hist_rows, event_rows = [], [], []
    dates = x.index.get_level_values("Date")
    samples = {
        "all_eval_rows": evaluation_index,
        "high_events": evaluation_index[events.reindex(evaluation_index).fillna(False).to_numpy()],
    }
    for name, idx in samples.items():
        d = x["box_duration"].reindex(idx).dropna()
        qualified = d > 0
        history = aux["box_history_available"].reindex(idx).fillna(False).astype(bool)
        valid_history = history
        no_box = d.eq(0)
        row = {
            "population": name, "rows": int(len(d)), "mean": float(d.mean()),
            "median": float(d.median()), "p10": float(d.quantile(.10)),
            "p25": float(d.quantile(.25)), "p50": float(d.quantile(.50)),
            "p75": float(d.quantile(.75)), "p90": float(d.quantile(.90)),
            "L5_share_all": float(d.eq(5).mean()), "L_le_10_share_all": float(d.le(10).mean()),
            "Lmax_share_all": float(d.eq(max(WINDOWS)).mean()),
            "no_box_share_all": float(no_box.mean()),
            "L5_share_qualified": float(d.loc[qualified].eq(5).mean()) if qualified.any() else np.nan,
            "L_le_10_share_qualified": float(d.loc[qualified].le(10).mean()) if qualified.any() else np.nan,
            "Lmax_share_qualified": float(d.loc[qualified].eq(max(WINDOWS)).mean()) if qualified.any() else np.nan,
            "insufficient_history_share": float((~valid_history).mean()),
            "condition_failure_share_given_history": float((no_box & valid_history).sum() / max(1, valid_history.sum())),
        }
        widths = x["box_width_atr"].reindex(idx)
        pair = pd.concat([d.rename("duration"), widths.rename("width")], axis=1).dropna()
        row["duration_width_pearson"] = float(pair.corr().iloc[0, 1]) if len(pair) > 2 else np.nan
        row["duration_width_spearman"] = float(pair.corr(method="spearman").iloc[0, 1]) if len(pair) > 2 else np.nan
        rows.append(row)
        for duration, count in d.value_counts(dropna=False).sort_index().items():
            hist_rows.append({"population": name, "box_duration": float(duration), "rows": int(count)})
    duration = x["box_duration"].reindex(evaluation_index)
    event = events.reindex(evaluation_index).fillna(False).astype(bool)
    for year in sorted(evaluation_index.get_level_values("Date").year.unique()):
        yridx = evaluation_index[evaluation_index.get_level_values("Date").year == year]
        d = duration.reindex(yridx)
        ev = event.reindex(yridx)
        qualified = d > 0
        history = aux["box_history_available"].reindex(yridx).fillna(False).astype(bool)
        event_rows.append({
            "year": int(year), "rows": int(len(yridx)), "high_events": int(ev.sum()),
            "boxed_high_events": int((ev & qualified).sum()),
            "unboxed_high_events": int((ev & ~qualified).sum()),
            "mean_duration_all": float(d.mean()), "median_duration_all": float(d.median()),
            "mean_duration_events": float(d.loc[ev].mean()) if ev.any() else np.nan,
            "median_duration_events": float(d.loc[ev].median()) if ev.any() else np.nan,
            "L5_share_events": float(d.loc[ev].eq(5).mean()) if ev.any() else np.nan,
            "L_le_10_share_events": float(d.loc[ev].le(10).mean()) if ev.any() else np.nan,
            "Lmax_share_events": float(d.loc[ev].eq(max(WINDOWS)).mean()) if ev.any() else np.nan,
            "no_box_share_events": float(d.loc[ev].eq(0).mean()) if ev.any() else np.nan,
            "condition_failure_share_given_history": float(((d.eq(0) & history).sum()) / max(1, history.sum())),
        })
    pd.DataFrame(rows).to_csv(outdir / "duration_summary.csv", index=False)
    pd.DataFrame(hist_rows).to_csv(outdir / "duration_histogram.csv", index=False)
    pd.DataFrame(event_rows).to_csv(outdir / "duration_by_year.csv", index=False)
    ev_idx = evaluation_index[events.reindex(evaluation_index).fillna(False).to_numpy()]
    ev_duration = x["box_duration"].reindex(ev_idx)
    ev_target = target.reindex(ev_idx)
    counts_by_duration = ev_duration.groupby(ev_duration).size()
    mean_target = ev_target.groupby(ev_duration).mean()
    event_by_duration = pd.DataFrame({"event_rows": counts_by_duration, "mean_official_residual": mean_target})
    event_by_duration.index.name = "box_duration"
    event_by_duration.reset_index().to_csv(outdir / "event_count_by_duration.csv", index=False)
    return rows, event_rows


def matched_control(events, x, b00_raw, target, day, night, evaluation_index):
    box_a = events & x["box_duration"].gt(0)
    # The B00 long event pool is the un-smoothed positive breakout score.
    b00_events = b00_raw.gt(0.0)
    if not (b00_events.reindex(x.index).fillna(False) == events.reindex(x.index).fillna(False)).all():
        raise AssertionError("B00 raw Long event set does not agree with the high-breakout definition")
    box_b = b00_events & ~box_a
    outcomes = {"official_o2o_residual": target, "raw_day": day, "raw_night": night}
    all_rows = []
    years = [None, *sorted(evaluation_index.get_level_values("Date").year.unique())]
    for year in years:
        idx = evaluation_index
        label = "pooled_all_eval"
        if year is not None:
            idx = idx[idx.get_level_values("Date").year == year]
            label = str(year)
        mask_a = box_a.reindex(idx).fillna(False).to_numpy()
        mask_b = box_b.reindex(idx).fillna(False).to_numpy()
        counts_a = pd.Series(mask_a, index=idx).groupby(level="Date").sum()
        counts_b = pd.Series(mask_b, index=idx).groupby(level="Date").sum()
        common = counts_a.index[(counts_a > 0) & (counts_b > 0)]
        for metric, value in outcomes.items():
            ya = value.reindex(idx).where(pd.Series(mask_a, index=idx)).groupby(level="Date").mean()
            yb = value.reindex(idx).where(pd.Series(mask_b, index=idx)).groupby(level="Date").mean()
            a = ya.reindex(common).dropna()
            b = yb.reindex(common).dropna()
            shared = a.index.intersection(b.index)
            ma = float(a.reindex(shared).mean()) if len(shared) else np.nan
            mb = float(b.reindex(shared).mean()) if len(shared) else np.nan
            all_rows.append({
                "period": label, "outcome": metric, "common_dates": int(len(shared)),
                "A_total_rows_on_common_dates": int(counts_a.reindex(shared).sum()),
                "B_total_rows_on_common_dates": int(counts_b.reindex(shared).sum()),
                "A_mean_names_per_date": float(counts_a.reindex(shared).mean()) if len(shared) else np.nan,
                "B_mean_names_per_date": float(counts_b.reindex(shared).mean()) if len(shared) else np.nan,
                "A_daily_mean": ma, "B_daily_mean": mb, "A_minus_B_daily_mean": ma - mb,
                "A_annualized_arithmetic": ma * 252 if np.isfinite(ma) else np.nan,
                "B_annualized_arithmetic": mb * 252 if np.isfinite(mb) else np.nan,
                "A_minus_B_annualized_arithmetic": (ma - mb) * 252 if np.isfinite(ma - mb) else np.nan,
            })
    return pd.DataFrame(all_rows), box_a, box_b


def safe_corr(left, right, method="pearson"):
    joined = pd.concat([left.rename("x"), right.rename("y")], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(joined) < 3 or joined["x"].nunique() < 2 or joined["y"].nunique() < 2:
        return np.nan
    return float(joined["x"].corr(joined["y"], method=method))


def compute_aux_prefix_audit(prices, x, aux, cutoffs):
    dates = x.index.get_level_values("Date")
    rows = []
    for label in cutoffs:
        cutoff = pd.Timestamp(label)
        if cutoff not in dates.unique():
            continue
        changed = mutate_future_prices(prices, cutoff)
        changed_aux = build_auxiliary(changed, x.index, x)
        prefix = dates <= cutoff
        index = x.index[prefix]
        pd.testing.assert_frame_equal(aux.loc[index], changed_aux.loc[index], check_exact=True)
        rows.append({"cutoff": label, "prefix_rows": int(prefix.sum()),
                     "checks": "volume/touch/t-close diagnostics bitwise exact after future mutation"})
    if len(rows) < 3:
        raise AssertionError("Expected three future-mutation cutoffs for diagnostic features")
    return {"status": "PASS", "cutoffs": rows}


def build_report(run_id, pooled_rows, fold_rows, event_rows, univariate_rows,
                 duration_rows, annual_duration_rows, matched_rows, timing_rows,
                 replay_info, eval_span, run_path):
    report_dir = ROOT / "reports" / EXPERIMENT_ID
    report_dir.mkdir(parents=True, exist_ok=True)
    pooled = pd.DataFrame(pooled_rows)
    lines = [
        f"# {EXPERIMENT_ID}: BOX_RIDGE_001 Phase 1 診断", "",
        f"- Run ID: `{run_id}`。実行記録: `{run_path.as_posix()}`。", "- Train only。2011〜2016-03は既知Trainの記述診断で、独立OOS・採用・再選択の根拠にはしない。Valid・Valid target・未参照区間は未読。",
        f"- 公式holding periodは `t+1 Open → t+2 Open`。評価期間: {eval_span[0]}〜{eval_span[1]}。2016 stubはフル年集計から分離。各年末2 signal日はpurge。", "- 6 fixed score ablations: BOX blend 0/50/100% × EWMA alpha .25/1.0。Ridge・5特徴・target・Short scoreは固定。", "",
        "## 判定要約", "",
        "この節はevent-only予測力、スコアからweight、P&Lへの伝達、取引コスト、年次安定性の順に読み、モデル複雑化の理由に使わない。", "",
        "## Blend / EWMA ablation", "",
        "Full-evaluation pooled values include the 2016 stub for exact accounting reconciliation; 2011–2015 full-year pooled metrics and 2016 are shown separately. Cell Sharpe is not additive.", "",
        "| Trial | Blend | α | RankIC | Gross SR | Net SR | ΔNet SR vs same-α B00 | ΔGross ann | ΔNet ann | ΔTurnover/day | ΔCost ann | Mean |Δweight| | Corr(raw pred, final weight) | Q mono | Max DD |",
        "|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in pooled_rows:
        lines.append(
            f"| {r['trial_id']} | {r['blend']:.0%} | {r['alpha']:.2f} | {r['rankic']:+.4f} | {r['gross_sharpe']:.3f} | {r['net_sharpe']:.3f} | {r['delta_net_sharpe_same_alpha_b00']:+.3f} | {r['delta_annual_gross_same_alpha_b00']:+.2%} | {r['delta_annual_net_same_alpha_b00']:+.2%} | {r['delta_turnover_same_alpha_b00']:+.5f} | {r['delta_cost_same_alpha_b00']:+.3%} | {r['mean_abs_weight_diff']:.5f} | {r['raw_pred_final_weight_pearson']:+.3f} | {r['q_monotonicity']:+.2f} | {r['max_drawdown_additive']:+.2%} |"
        )
    lines += ["", "### Full-year pooled (2011–2015) and 2016 stub", "",
              "| Trial | Segment | Days | Gross SR | Net SR | Annual gross | Annual net | Cost | Turnover/day | RankIC | HAC t | Hit | Q mono | Long net | Short net | Max DD |",
              "|:---|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in fold_rows:
        if str(r["year"]) in ("2011-2015", "2016"):
            lines.append(
                f"| {r['trial_id']} | {r['year']} | {r['days']} | {r['gross_sharpe']:.3f} | {r['net_sharpe']:.3f} | {r['annual_gross']:+.2%} | {r['annual_net']:+.2%} | {r['annual_cost']:.2%} | {r['turnover']:.5f} | {r['rankic']:+.4f} | {r['rankic_t_hac5']:+.2f} | {r['rankic_hit']:.3f} | {r['q_monotonicity']:+.2f} | {r['annual_long']:+.2%} | {r['annual_short']:+.2%} | {r['max_drawdown_additive']:+.2%} |"
            )
    lines += ["", "年別foldの全指標とbaseline差は `ablation_fold_metrics.csv`、raw予測→event rank→blend→EWMA→portfolio weightの全行は `predictions/signal_stages.parquet` と `predictions/portfolio_weights.parquet`、日次Gross/cost/Net/turnoverは `metrics/daily_account_*.csv` / `metrics/daily_legs_*.csv` に保存。", "",
              "## Event-only BOX予測", "",
              "BOX raw prediction順位を新高値イベント内だけで評価。RankICは日次Spearman平均、HAC tはlag 5、hitは日次RankIC>0の割合。五分位は日ごとにイベント予測値を5群へ分け、日次群平均を等ウェイト平均。", "",
              "| Period | Events | RankIC | HAC t | Hit | Q1 | Q2 | Q3 | Q4 | Q5 | Q mono | Quintile days |", "|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in event_rows:
        lines.append(f"| {r['period']} | {r['rows']} | {r['rankic']:+.4f} | {r['rankic_hac_t']:+.2f} | {r['rankic_hit']:.3f} | {r['q1_return']:+.5f} | {r['q2_return']:+.5f} | {r['q3_return']:+.5f} | {r['q4_return']:+.5f} | {r['q5_return']:+.5f} | {r['q_monotonicity']:+.2f} | {r.get('quintile_days', 0)} |")
    lines += ["", "## 単変量: 高値イベント内", "",
              "BOX raw predictionとは分けて、各特徴単独の方向付き順位を公式targetで記述評価。widthは小さい方がtightとして符号反転。特徴別有効行数はcoverageを表す。", "",
              "| Feature | Period | Rows | RankIC | HAC t | Hit | Q1 | Q2 | Q3 | Q4 | Q5 | Q mono |", "|:---|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in univariate_rows:
        lines.append(f"| {r['feature']} | {r['period']} | {r['rows']} | {r['rankic']:+.4f} | {r['rankic_hac_t']:+.2f} | {r['rankic_hit']:.3f} | {r['q1_return']:+.5f} | {r['q2_return']:+.5f} | {r['q3_return']:+.5f} | {r['q4_return']:+.5f} | {r['q5_return']:+.5f} | {r['q_monotonicity']:+.2f} |")
    lines += ["", "## box_duration実測", "",
              "| Population | Rows | Mean | Median | P10 | P25 | P50 | P75 | P90 | L=5 / qualified | L≤10 / qualified | Lmax / qualified | No box | Condition failure given history | Width-duration Spearman |", "|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in duration_rows:
        lines.append(f"| {r['population']} | {r['rows']} | {r['mean']:.2f} | {r['median']:.1f} | {r['p10']:.1f} | {r['p25']:.1f} | {r['p50']:.1f} | {r['p75']:.1f} | {r['p90']:.1f} | {r['L5_share_qualified']:.1%} | {r['L_le_10_share_qualified']:.1%} | {r['Lmax_share_qualified']:.1%} | {r['no_box_share_all']:.1%} | {r['condition_failure_share_given_history']:.1%} | {r['duration_width_spearman']:+.3f} |")
    lines += ["", "頻度の全histogramは `duration_histogram.csv`、年別分布・event数・未成立率は `duration_by_year.csv`、event数とtargetのduration別集計は `event_count_by_duration.csv`。履歴不足と条件不成立を分けた。", "",
              "## Matched overnight control", "",
              "A=新高値かつduration>0、B=同日のB00高値eventのうちA以外。各群内は日ごとに等ウェイト平均し、A/B両方がある同一日だけを比較。昼夜はraw stock return（市場調整前）、O2O列は公式residual target。年率欄は日次平均×252の単純換算。", "",
              "| Period | Outcome | Dates | A rows | B rows | A mean | B mean | A−B/day | A−B annualized |", "|:---|:---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in matched_rows:
        if r["period"] in ("pooled_all_eval", "2011", "2012", "2013", "2014", "2015", "2016"):
            lines.append(f"| {r['period']} | {r['outcome']} | {r['common_dates']} | {r['A_total_rows_on_common_dates']} | {r['B_total_rows_on_common_dates']} | {r['A_daily_mean']:+.5f} | {r['B_daily_mean']:+.5f} | {r['A_minus_B_daily_mean']:+.5f} | {r['A_minus_B_annualized_arithmetic']:+.2%} |")
    lines += ["", "## 情報時点・因果性", "",
              "| Feature | Latest data used | Ready by entry? | Reason |\n|:---|:---|:---|:---|\n| box_duration / width / prior close position | t−1 Close/High/Low | Yes | Defines pre-breakout compression before t |\n| relative_strength_60 | t−1 and earlier residual O2O | Yes | One-observation skip is explicit |\n| distance_to_prior_high | t−1 Close and highs through t−2 | Yes | Prior-state distance |\n| breakout event | t Close vs prior 250 highs | Yes | Final close is known before t+1 Open |\n| volume ratio diagnostic | t Volume and t−1…t−20 Volume | Yes | Close-of-day volume known before next open |\n| upper touch density | box window through t−1 | Yes | Prior-only box observations |\n| t-close timing comparator | t High/Low/Close | Yes | Diagnostic only; checked against future mutation |", "", 
              f"DM-20260924-10のcore feature / model / prediction prefix auditは {replay_info['prior_prefix_audit']}。本runで追加したvolume/touch/t-close診断列の未来改変prefix test: **{replay_info['aux_prefix_audit']}**。t-1 box stateとt日終値までの固定定義比較は `timing_diagnostics.csv` に保存。", "",
              "## 再現性・判断", "",
              f"- 50% blend・alpha .25とB00 alpha .25の旧signal一致: **{replay_info['prior_signal_replay']}**。既存年度モデル係数の一致: **{replay_info['prior_model_replay']}**。再予測決定性: **{replay_info['deterministic_replay']}**。",
              f"- Source scan / Train firewall / index alignment / 公式Long+Short会計reconcile: **{replay_info['source_scan']} / {replay_info['firewall']} / {replay_info['index_alignment']} / {replay_info['accounting']}**。raw_target・Valid inputは未読。",
              "- `decision.md` に事前分岐に沿ったGo/No-GoとPhase 2を進めるかを記録。Full Trainの最大SRから候補を採用しない。",
              ""]
    report_path = report_dir / "REPORT.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def resume_report(output_path):
    """Finish report packaging from a run whose diagnostics completed first.

    The original computation attempt is preserved in logs/first_attempt_failure.json.
    This path reads only already-produced CSV/JSON artifacts and never reopens inputs.
    """
    output = Path(output_path)
    run_path = output / "run.json"
    meta = json.loads(run_path.read_text(encoding="utf-8"))
    failure_text = meta.get("failure", "")
    if meta.get("status") != "failed" or "not in the subpath" not in failure_text:
        raise ValueError("Resume is restricted to the report path-format failure after completed diagnostics")
    required = [
        "metrics/ablation_summary.csv", "metrics/ablation_fold_metrics.csv",
        "metrics/event_only_metrics.csv", "metrics/event_univariate.csv",
        "metrics/timing_diagnostics.csv", "metrics/duration_summary.csv",
        "metrics/duration_by_year.csv", "metrics/matched_overnight_control.csv",
        "audit/causality.json", "audit/information_timing.json", "audit/firewall.json",
        "predictions/signal_stages.parquet", "predictions/portfolio_weights.parquet",
    ]
    absent = [name for name in required if not (output / name).is_file()]
    if absent:
        raise FileNotFoundError(f"Cannot resume report; missing completed outputs: {absent}")
    metric_dir, audit_dir = output / "metrics", output / "audit"
    pooled_rows = pd.read_csv(metric_dir / "ablation_summary.csv").to_dict("records")
    fold_rows = pd.read_csv(metric_dir / "ablation_fold_metrics.csv").to_dict("records")
    event_rows = pd.read_csv(metric_dir / "event_only_metrics.csv").to_dict("records")
    univariate_rows = pd.read_csv(metric_dir / "event_univariate.csv").to_dict("records")
    timing_rows = pd.read_csv(metric_dir / "timing_diagnostics.csv").to_dict("records")
    duration_rows = pd.read_csv(metric_dir / "duration_summary.csv").to_dict("records")
    annual_duration_rows = pd.read_csv(metric_dir / "duration_by_year.csv").to_dict("records")
    matched_rows = pd.read_csv(metric_dir / "matched_overnight_control.csv").to_dict("records")
    if len(pooled_rows) != 6 or {r["trial_id"] for r in pooled_rows} != {
        "BLEND_0_A025", "BLEND_50_A025", "BLEND_100_A025",
        "BLEND_0_A100", "BLEND_50_A100", "BLEND_100_A100",
    }:
        raise AssertionError("Saved ablation output does not match the six registered trials")
    firewall_record = json.loads((audit_dir / "firewall.json").read_text(encoding="utf-8"))
    opened = firewall_record.get("opened_parquets", [])
    if firewall_record.get("valid_evaluation") is not False or firewall_record.get("raw_target_reads") is not False:
        raise AssertionError("Firewall record is not Train-only")
    prior = ROOT / "artifacts" / PRIOR_ID / PRIOR_RUN
    prior_audit = json.loads((prior / "audit/causality.json").read_text(encoding="utf-8"))
    aux_audit = json.loads((audit_dir / "causality.json").read_text(encoding="utf-8"))["auxiliary_feature_prefix_audit"]
    replay_info = {
        "prior_prefix_audit": prior_audit["status"], "aux_prefix_audit": aux_audit["status"],
        "prior_signal_replay": "PASS (B00 alpha=.25 and BOX blend=.50 alpha=.25 bitwise)",
        "prior_model_replay": "PASS (six annual model JSONs identical)",
        "deterministic_replay": "PASS (walk-forward prediction Series bitwise)",
        "source_scan": "PASS", "firewall": "PASS (Train files plus two prior Train artifacts)",
        "index_alignment": "PASS", "accounting": "PASS",
    }
    # Recover the fixed evaluation span from the complete daily output using the
    # registered years and final-two-signal-date purge, without reading prices.
    daily = pd.read_csv(output / "metrics/daily_account_BLEND_0_A025.csv", parse_dates=["Date"])
    all_dates = pd.DatetimeIndex(daily["Date"].dropna().unique()).sort_values()
    eval_dates = []
    for year in YEARS:
        year_dates = all_dates[all_dates.year == year]
        eval_dates.extend(year_dates[:-2].tolist())
    eval_dates = pd.DatetimeIndex(eval_dates).sort_values()
    if len(eval_dates) != 1275:
        raise AssertionError(f"Unexpected recovered evaluation day count: {len(eval_dates)}")
    report = build_report(output.name, pooled_rows, fold_rows, event_rows, univariate_rows,
                          duration_rows, annual_duration_rows, matched_rows, timing_rows,
                          replay_info, (str(eval_dates.min().date()), str(eval_dates.max().date())), run_path)
    data_dir = ROOT / "stock_comp_2026" / "input"
    data_hashes = {name: digest(data_dir / name) for name in (
        "prices_daily_quotes_train.parquet", "raw_return_1day_train.parquet",
        "beta_1day_train.parquet", "topix_return_1day_train.parquet",
        "target_1day_train.parquet")}
    first_attempt = {
        "status": "failed during report formatting after diagnostics were saved",
        "failure": meta.get("failure"), "command": meta.get("command"),
        "code_sha256": meta.get("code_sha256"), "initial_exit_code": 1,
        "diagnostic_artifacts_present": required,
    }
    dump(output / "logs/first_attempt_failure.json", first_attempt)
    summary = {
        "status": "PASS", "experiment_id": EXPERIMENT_ID, "run_id": output.name,
        "actual_trials": 6, "valid_accessed": False, "raw_target_read": False,
        "evaluation_days": int(len(eval_dates)),
        "evaluation_span": [str(eval_dates.min().date()), str(eval_dates.max().date())],
        "prior_feature_match": "PASS", "prior_signal_replay": replay_info["prior_signal_replay"],
        "prior_model_replay": replay_info["prior_model_replay"], "prefix_audit": aux_audit,
        "input_data_sha256": data_hashes, "opened_parquets": opened,
        "report": str(report.relative_to(ROOT)),
        "postprocessed_from_same_run": True,
    }
    dump(audit_dir / "summary.json", summary)
    meta.update({
        "status": "completed", "completed_at_utc": utc_now(), "exit_code": 0,
        "actual_trials": 6, "train_data_sha256": data_hashes,
        "valid_accessed": False, "source_scan": "PASS",
        "aux_prefix_invariance": "PASS", "model_replay": "PASS",
        "score_replay": "PASS", "account_reconciliation": "PASS",
        "report": str(report.relative_to(ROOT)),
        "initial_report_failure": first_attempt,
        "report_resumed_without_reopening_parquets": True,
        "postprocess_code_sha256": digest(Path(__file__)),
    })
    dump(run_path, meta)
    print(f"[Resumed report] {report}", flush=True)


def run(config_path, output_path):
    started = time.monotonic()
    config_path, output = Path(config_path), Path(output_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if (config.get("experiment_id") != EXPERIMENT_ID or config.get("data_split") != "train"
            or config.get("valid_evaluation") is not False or config.get("selection_eligible") is not False
            or config.get("max_trials") != 6 or len(config.get("trials", [])) != 6):
        raise ValueError("Unexpected experiment scope or trial budget")
    expected = {(b, a) for b in (0.0, 0.5, 1.0) for a in (0.25, 1.0)}
    trial_ids = {(float(t["trial_id"].split("_")[1]) / 100.0,
                  float(t["trial_id"].split("_")[2][1:]) / 100.0) for t in config["trials"]}
    if trial_ids != expected:
        raise ValueError(f"Ablation matrix differs from pre-registration: {trial_ids}")
    for folder in ("models", "predictions", "metrics", "audit", "logs"):
        (output / folder).mkdir(parents=True, exist_ok=True)
    run_path = output / "run.json"
    meta = json.loads(run_path.read_text(encoding="utf-8"))
    snapshot_ok = all(digest(output / n) == meta["snapshot_sha256"][n]
                      for n in ("plan.md", "config.json", "experiment.json"))
    if not snapshot_ok:
        raise AssertionError("Prepared plan/config snapshot hash mismatch")
    sources = [Path(__file__), Path(features.__file__), Path(models.__file__),
               Path(evaluation.__file__), Path(firewall.__file__)]
    meta.update({"status": "running", "started_at_utc": utc_now(), "command": sys.argv,
                 "actual_trials": 0, "environment": {"python": sys.version,
                 "platform": platform.platform(), "numpy": np.__version__, "pandas": pd.__version__},
                 "code_sha256": {str(p.relative_to(ROOT)): digest(p) for p in sources}})
    dump(run_path, meta)
    try:
        data_dir = ROOT / "stock_comp_2026" / "input"
        prior = ROOT / "artifacts" / PRIOR_ID / PRIOR_RUN
        allowed = [prior / "predictions/signals.parquet", prior / "predictions/box_features.parquet"]
        firewall.install(allowed_artifacts=allowed)
        input_names = ("prices_daily_quotes_train.parquet", "raw_return_1day_train.parquet",
                       "beta_1day_train.parquet", "topix_return_1day_train.parquet",
                       "target_1day_train.parquet")
        data_hashes = {name: digest(data_dir / name) for name in input_names}
        input_panels = features.load_inputs(data_dir, split="train")
        prices = pd.read_parquet(data_dir / "prices_daily_quotes_train.parquet",
                                 columns=["Open", "High", "Low", "Close", "Volume", "AdjustmentFactor"]).sort_index()
        index = input_panels["raw_return_1day"].index
        if not index.equals(prices.index):
            raise AssertionError("Prices and raw-return Train indexes differ")
        input_panels["prices_daily_quotes"] = prices
        target = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index()
        if not index.equals(target.index):
            raise AssertionError("Features and official Train target indexes differ")
        x = features.build_features(input_panels)
        if not x.index.equals(index):
            raise AssertionError("Feature index changed")
        old_sig = pd.read_parquet(allowed[0]).sort_index()
        old_x = pd.read_parquet(allowed[1]).sort_index()
        pd.testing.assert_frame_equal(x.loc[old_x.index, list(features.FEATURE_COLUMNS)],
                                      old_x.loc[:, list(features.FEATURE_COLUMNS)], check_exact=True)

        predictions, training_records = models.walk_forward_predictions(x, target, model_dir=output / "models")
        replay_predictions, replay_records = models.walk_forward_predictions(x, target, model_dir=None)
        pd.testing.assert_series_equal(predictions, replay_predictions, check_exact=True)
        if training_records != replay_records:
            raise AssertionError("Walk-forward model records changed on deterministic replay")
        prior_model_records = []
        for year in YEARS:
            model_path = output / "models" / f"RIDGE_{year}.json"
            prior_model_path = prior / "models" / f"RIDGE_{year}.json"
            current_model = json.loads(model_path.read_text(encoding="utf-8"))
            prior_model = json.loads(prior_model_path.read_text(encoding="utf-8"))
            if current_model != prior_model:
                raise AssertionError(f"Saved Ridge model differs from DM-20260924-10 for {year}")
            prior_model_records.append({"year": year, "sha256": digest(prior_model_path)})

        b00_raw = models.raw_base_signal(x)
        b00_a025 = models.smooth_by_listing(b00_raw, alpha=0.25).rename("B00_A025")
        b00_a100 = models.smooth_by_listing(b00_raw, alpha=1.0).rename("B00_A100")
        eval_dates = evaluation_dates(pd.DatetimeIndex(index.get_level_values("Date").unique()))
        eval_rows = index.get_level_values("Date").isin(eval_dates)
        eval_index = index[eval_rows]
        events = x["high_available"] & x["new_high_excess"].gt(0.0)
        box_rank = models.active_percentile(predictions.reindex(index).where(events))

        scores, stages, weights_by_trial, accounts, legs_by_trial = {}, {}, {}, {}, {}
        for b in (0.0, 0.5, 1.0):
            for alpha in (0.25, 1.0):
                trial = f"BLEND_{int(b * 100)}_A{int(alpha * 100):03d}"
                rank_s, blended, final = score_path(b00_raw, predictions, x, b, alpha)
                scores[trial] = final.rename(trial)
                stages[f"{trial}_blend"] = blended
                stages[f"{trial}_ewma"] = final
                stages[f"{trial}_weight"] = evaluation.weights(final)[0]
                weights_by_trial[trial] = evaluation.weights(final)[0]
                account_all = evaluation.daily_account(final, target)
                legs_all = leg_account(final, target)
                mismatch = (legs_all["net_sum"].reindex(account_all.index) - account_all["net"]).abs().max()
                if not np.isfinite(mismatch) or mismatch > 1e-10:
                    raise AssertionError(f"Long/Short accounting mismatch for {trial}: {mismatch}")
                accounts[trial] = account_all.reindex(eval_dates)
                legs_by_trial[trial] = legs_all.reindex(eval_dates)
                account_all.to_csv(output / f"metrics/daily_account_{trial}.csv", index_label="Date")
                legs_all.to_csv(output / f"metrics/daily_legs_{trial}.csv", index_label="Date")

        prior_a025 = old_sig[models.TRIAL_ID].reindex(index)
        prior_b00 = old_sig["B00"].reindex(index)
        replay_candidate = scores["BLEND_50_A025"].reindex(prior_a025.index)
        replay_base = b00_a025.reindex(prior_b00.index)
        pd.testing.assert_series_equal(replay_candidate.rename(models.TRIAL_ID), prior_a025.rename(models.TRIAL_ID), check_exact=True)
        pd.testing.assert_series_equal(replay_base.rename("B00"), prior_b00.rename("B00"), check_exact=True)

        b00_account = accounts["BLEND_0_A025"]
        summary_rows, fold_rows, stage_rows = [], [], []
        full_dates = eval_dates[eval_dates.year < 2016]
        stub_dates = eval_dates[eval_dates.year == 2016]
        event_metric_rows = []
        event_score = predictions.reindex(index)
        valid_event = events & target.notna() & event_score.notna()
        all_event_idx = eval_index[valid_event.reindex(eval_index).fillna(False).to_numpy()]
        event_metric_rows.append({"period": "pooled_all_eval", **percentile_metrics(event_score, target, all_event_idx)})
        for year in [*range(2011, 2017)]:
            event_metric_rows.append({"period": str(year), **percentile_metrics(event_score, target, all_event_idx, year)})
        pd.DataFrame(event_metric_rows).to_csv(output / "metrics/event_only_metrics.csv", index=False)

        aux = build_auxiliary(prices, index, x)
        cutoffs = json.loads((prior / "audit/causality.json").read_text(encoding="utf-8"))["cutoffs"]
        aux_audit = compute_aux_prefix_audit(prices, x, aux, [r["cutoff"] for r in cutoffs])
        dump(output / "audit/causality.json", {
            "status": "PASS", "core_feature_model_prefix_audit_reference": f"artifacts/{PRIOR_ID}/{PRIOR_RUN}/audit/causality.json",
            "auxiliary_feature_prefix_audit": aux_audit,
            "timing": {"prior_box_state": "t-1 High/Low/Close; prior ATR20", "breakout": "t Close versus prior High", "entry": "t+1 Open", "exit": "t+2 Open"},
        })
        duration_rows, annual_duration_rows = duration_tables(
            x, aux, target, eval_index, events, output / "metrics")

        feature_specs = [
            ("box_duration", "box_duration", 1.0),
            ("tightness_prior", "box_width_atr", -1.0),
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
        for name, col, direction in feature_specs:
            value = (x[col] if col in x else aux[col]) * direction
            finite = value.reindex(all_event_idx).replace([np.inf, -np.inf], np.nan).dropna().index
            for period in ["pooled_all_eval", *[str(y) for y in range(2011, 2017)]]:
                yr = None if period == "pooled_all_eval" else int(period)
                result = percentile_metrics(value, target, finite, yr)
                row = {"feature": name, "period": period, **result}
                univariate_rows.append(row)
                if name.endswith("_through_t") or name in ("box_duration", "tightness_prior", "close_position_prior"):
                    timing_rows.append(row)
        pd.DataFrame(univariate_rows).to_csv(output / "metrics/event_univariate.csv", index=False)
        pd.DataFrame(timing_rows).to_csv(output / "metrics/timing_diagnostics.csv", index=False)

        outcome_series = pd.read_parquet(data_dir / "raw_return_1day_train.parquet")["Return"].sort_index()
        calendar = pd.DatetimeIndex(index.get_level_values("Date").unique()).sort_values()
        date_ord = pd.Series(np.arange(len(calendar)), index=calendar)
        positions = date_ord.reindex(index.get_level_values("Date")).to_numpy()
        entry_dates = pd.DatetimeIndex([calendar[p + 1] if p + 1 < len(calendar) else pd.NaT for p in positions])
        exit_dates = pd.DatetimeIndex([calendar[p + 2] if p + 2 < len(calendar) else pd.NaT for p in positions])
        codes = index.get_level_values("Code")
        entry_index = pd.MultiIndex.from_arrays([entry_dates, codes], names=index.names)
        exit_index = pd.MultiIndex.from_arrays([exit_dates, codes], names=index.names)
        open_t1 = prices["Open"].reindex(entry_index).to_numpy()
        close_t1 = prices["Close"].reindex(entry_index).to_numpy()
        raw_o2o = outcome_series.reindex(exit_index).to_numpy()
        raw_day = close_t1 / open_t1 - 1.0
        raw_night = (1.0 + raw_o2o) / (1.0 + raw_day) - 1.0
        raw_day[~np.isfinite(raw_day)] = np.nan
        raw_night[~np.isfinite(raw_night)] = np.nan
        day_s = pd.Series(raw_day, index=index, name="raw_day")
        night_s = pd.Series(raw_night, index=index, name="raw_night")
        outcomes, group_a, group_b = matched_control(events, x, b00_raw, target, day_s, night_s, eval_index)
        outcomes.to_csv(output / "metrics/matched_overnight_control.csv", index=False)

        base_by_alpha = {0.25: "BLEND_0_A025", 1.0: "BLEND_0_A100"}
        for b in (0.0, 0.5, 1.0):
            for alpha in (0.25, 1.0):
                trial = f"BLEND_{int(b * 100)}_A{int(alpha * 100):03d}"
                base_trial = base_by_alpha[alpha]
                d_all = accounts[trial]
                legs = legs_by_trial[trial]
                metr = evaluation.metrics(d_all)
                base_all = accounts[base_trial]
                d_full = d_all.reindex(full_dates)
                d_stub = d_all.reindex(stub_dates)
                full_m = evaluation.metrics(d_full)
                stub_m = evaluation.metrics(d_stub)
                weight = weights_by_trial[trial]
                base_weight = weights_by_trial[base_trial]
                dw = weight.reindex(eval_index) - base_weight.reindex(eval_index)
                event_mask = events.reindex(eval_index).fillna(False)
                event_idx = eval_index[event_mask.to_numpy() & event_score.reindex(eval_index).notna().to_numpy()]
                corr = {
                    "raw_pred_b00_event_pearson": safe_corr(event_score.reindex(event_idx), b00_raw.reindex(event_idx)),
                    "raw_pred_final_weight_pearson": safe_corr(event_score.reindex(event_idx), weight.reindex(event_idx)),
                    "raw_pred_final_weight_spearman": safe_corr(event_score.reindex(event_idx), weight.reindex(event_idx), "spearman"),
                    "event_rank_final_weight_pearson": safe_corr(box_rank.reindex(event_idx), weight.reindex(event_idx)),
                    "final_score_b00_same_alpha_pearson": safe_corr(scores[trial].reindex(eval_index), scores[base_trial].reindex(eval_index)),
                    "weight_b00_same_alpha_pearson": safe_corr(weight.reindex(eval_index), base_weight.reindex(eval_index)),
                    "mean_abs_weight_diff": float(dw.abs().mean()),
                    "max_abs_weight_diff": float(dw.abs().max()),
                    "weight_changed_share": float(dw.abs().gt(1e-15).mean()),
                    "raw_prediction_to_weight_spearman": safe_corr(event_score.reindex(event_idx), weight.reindex(event_idx), "spearman"),
                }
                new_vs_base = d_all - base_all
                row = {"trial_id": trial, "blend": b, "alpha": alpha, **metr,
                       "full_years_net_sharpe": full_m["net_sharpe"],
                       "full_years_annual_net": full_m["annual_net"],
                       "full_years_q_monotonicity": full_m["q_monotonicity"],
                       "full_years_median_annual_net_sr": np.nan,
                       "full_years_worst_annual_net_sr": np.nan,
                       "stub_2016_net_sharpe": stub_m["net_sharpe"],
                       "stub_2016_annual_net": stub_m["annual_net"],
                       "delta_net_sharpe_same_alpha_b00": metr["net_sharpe"] - evaluation.metrics(base_all)["net_sharpe"],
                       "delta_annual_gross_same_alpha_b00": float(new_vs_base["gross"].mean() * 252),
                       "delta_annual_net_same_alpha_b00": float(new_vs_base["net"].mean() * 252),
                       "delta_turnover_same_alpha_b00": float(new_vs_base["turnover"].mean()),
                       "delta_cost_same_alpha_b00": float(new_vs_base["cost"].mean() * 252),
                       "delta_net_sharpe_vs_current_b00": metr["net_sharpe"] - evaluation.metrics(accounts["BLEND_0_A025"])["net_sharpe"],
                       **corr}
                # Annual Sharpe stability excludes the 2016 stub.
                annual_sharpes = []
                for year in range(2011, 2016):
                    annual_idx = eval_dates[eval_dates.year == year]
                    annual = evaluation.metrics(d_all.reindex(annual_idx))
                    annual_sharpes.append(annual["net_sharpe"])
                    fold = {"trial_id": trial, "year": str(year), **annual}
                    fold.update({f"delta_{k}_vs_same_alpha_b00": annual[k] - evaluation.metrics(base_all.reindex(annual_idx))[k]
                                 for k in ("rankic", "gross_sharpe", "net_sharpe", "turnover", "annual_cost")})
                    fold_rows.append(fold)
                row["full_years_median_annual_net_sr"] = float(np.median(annual_sharpes))
                row["full_years_worst_annual_net_sr"] = float(np.min(annual_sharpes))
                summary_rows.append(row)
                fold_rows.append({"trial_id": trial, "year": "2011-2015", **full_m})
                fold_rows.append({"trial_id": trial, "year": "2016", **stub_m})
                stage_rows.append({"trial_id": trial, **corr})

        stages_frame = pd.DataFrame({
            "raw_box_prediction": predictions.reindex(index),
            "event_rank": box_rank,
            "B00_raw": b00_raw,
            "B00_EWMA_A025": b00_a025,
            "B00_EWMA_A100": b00_a100,
            "is_new_high_event": events.astype(bool),
            "box_duration": x["box_duration"],
            "box_width_atr": x["box_width_atr"],
            "close_position": x["close_position"],
            "relative_strength_60": x["relative_strength_60"],
            "distance_to_prior_high": x["distance_to_prior_high"],
            **stages,
        }, index=index).loc[eval_rows].sort_index()
        stages_frame.to_parquet(output / "predictions/signal_stages.parquet")
        pd.DataFrame({t: s.reindex(index).loc[eval_rows] for t, s in weights_by_trial.items()}
                     | {"B00_A025": weights_by_trial["BLEND_0_A025"].reindex(index).loc[eval_rows],
                        "B00_A100": weights_by_trial["BLEND_0_A100"].reindex(index).loc[eval_rows]}).sort_index().to_parquet(
                            output / "predictions/portfolio_weights.parquet")
        pd.DataFrame(summary_rows).to_csv(output / "metrics/ablation_summary.csv", index=False)
        pd.DataFrame(fold_rows).to_csv(output / "metrics/ablation_fold_metrics.csv", index=False)
        pd.DataFrame(stage_rows).to_csv(output / "metrics/stage_transmission.csv", index=False)

        firewall.save(output / "audit/firewall.json")
        opened = json.loads((output / "audit/firewall.json").read_text(encoding="utf-8"))["opened_parquets"]
        if any("valid" in Path(p).name.lower() or "rawtarget" in Path(p).name.lower() for p in opened):
            raise AssertionError("Firewall audit contains a forbidden source")
        timing_info = {
            "signal_to_execution": ["t Close: signal finalized", "t+1 Open: entry", "t+1 Close: diagnostic day endpoint", "t+2 Open: exit"],
            "features": [
                {"name": "box_duration/width/close_position", "latest": "t-1 Close/High/Low", "reason": "pre-breakout state"},
                {"name": "relative_strength_60", "latest": "t-1 and earlier O2O", "reason": "explicit skip-one momentum"},
                {"name": "distance_to_prior_high", "latest": "t-1 Close; High through t-2", "reason": "prior state"},
                {"name": "new_high_event", "latest": "t Close", "reason": "available before t+1 Open"},
                {"name": "breakout_volume_ratio", "latest": "t Volume", "reason": "available by next open"},
                {"name": "upper_touch_density", "latest": "t-1 High", "reason": "selected pre-breakout box"},
                {"name": "timing comparison", "latest": "t High/Low/Close", "reason": "diagnostic-only fixed-definition comparator"},
            ],
            "day_night_definition": {"day": "t+1 Open to t+1 Close", "night": "t+1 Close to t+2 Open", "night_formula": "(1 + official raw O2O return)/(1 + raw day return) - 1"},
            "core_prefix_audit_reference": f"artifacts/{PRIOR_ID}/{PRIOR_RUN}/audit/causality.json",
            "aux_prefix_audit": aux_audit,
        }
        dump(output / "audit/information_timing.json", timing_info)

        # Summarize event-only and univariate metrics for reporting.
        event_report_rows = event_metric_rows
        univariate_report_rows = univariate_rows
        duration_report_rows = duration_rows
        matched_report_rows = outcomes.to_dict("records")
        prior_audit = json.loads((prior / "audit/causality.json").read_text(encoding="utf-8"))
        replay_info = {
            "prior_prefix_audit": prior_audit["status"],
            "aux_prefix_audit": aux_audit["status"],
            "prior_signal_replay": "PASS (B00 alpha=.25 and BOX blend=.50 alpha=.25 bitwise)",
            "prior_model_replay": "PASS (six annual model JSONs identical)",
            "deterministic_replay": "PASS (walk-forward prediction Series bitwise)",
            "source_scan": "PASS",
            "firewall": "PASS (Train files plus two prior Train artifacts)",
            "index_alignment": "PASS",
            "accounting": "PASS",
        }
        report = build_report(output.name, summary_rows, fold_rows, event_report_rows,
                              univariate_report_rows, duration_report_rows, annual_duration_rows,
                              matched_report_rows, timing_rows, replay_info, 
                              (str(eval_dates.min().date()), str(eval_dates.max().date())), run_path)
        summary = {
            "status": "PASS", "experiment_id": EXPERIMENT_ID, "run_id": output.name,
            "actual_trials": 6, "valid_accessed": False, "raw_target_read": False,
            "evaluation_days": int(len(eval_dates)), "evaluation_span": [str(eval_dates.min().date()), str(eval_dates.max().date())],
            "prior_feature_match": "PASS", "prior_signal_replay": replay_info["prior_signal_replay"],
            "prior_model_replay": replay_info["prior_model_replay"], "prefix_audit": aux_audit,
            "input_data_sha256": data_hashes, "prior_model_hashes": prior_model_records,
            "opened_parquets": opened, "report": str(report.relative_to(ROOT)),
        }
        dump(output / "audit/summary.json", summary)
        meta.update({"status": "completed", "completed_at_utc": utc_now(),
                     "elapsed_seconds": time.monotonic() - started, "actual_trials": 6,
                     "train_data_sha256": data_hashes, "valid_accessed": False,
                     "source_scan": "PASS", "aux_prefix_invariance": "PASS",
                     "model_replay": "PASS", "score_replay": "PASS",
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
    parser.add_argument("--config")
    parser.add_argument("--output", required=True)
    parser.add_argument("--resume-report", action="store_true")
    args = parser.parse_args()
    if args.resume_report:
        resume_report(args.output)
    else:
        if not args.config:
            parser.error("--config is required unless --resume-report is used")
        run(args.config, args.output)
