"""Fixed Train-only VOL20 confidence diagnostic for the unchanged SN1_H1 baseline."""
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

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from research import evaluation, firewall
from stock_comp_2026.strategies.dm_variable_box_breakout import bidirectional
from stock_comp_2026.strategies.dm_variable_box_breakout import features, sn1, submission


EXPERIMENT_ID = "DM-20261001-02"
YEARS = tuple(range(2011, 2017))
COMPLETE_YEARS = tuple(range(2011, 2016))
WINDOW = 20
NEAR_ZERO = 1e-12
TINY_PERTURBATION = 1e-12
PERTURBATION_KEY = b"SN1-20260928"
ONE_WAY_COST = 0.001
BASELINE_SAVED = ROOT / "artifacts/DM-20261001-01/run-20261001T052315Z/predictions/SN1_H1.parquet"
BASELINE_PRIOR = ROOT / "artifacts/DM-20260930-02/run-20260930T081524Z/predictions/SN1_H1.parquet"
BASELINE_DAILY = ROOT / "artifacts/DM-20261001-01/run-20261001T052315Z/metrics/daily_account_SN1_H1.csv"
SOURCE_PATHS = (
    "research/experiments/sn1_volatility_diagnostic.py",
    "research/evaluation.py",
    "research/firewall.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/features.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/submission.py",
)
TOKEN_SCAN_PATHS = (
    "stock_comp_2026/strategies/dm_variable_box_breakout/features.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py",
)
AST_SCAN_PATHS = (
    "research/experiments/sn1_volatility_diagnostic.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/features.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py",
)
INPUT_NAMES = {
    "raw_return_1day_train.parquet",
    "beta_1day_train.parquet",
    "topix_return_1day_train.parquet",
    "prices_daily_quotes_train.parquet",
    "target_1day_train.parquet",
}
CUTOFFS = ("2012-06-29", "2014-06-30", "2015-06-30")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _safe(value):
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _update_run(path: Path, values) -> None:
    record = json.loads(path.read_text(encoding="utf-8"))
    record.update(_safe(values))
    _write_json(path, record)


def _exact_series(left: pd.Series, right: pd.Series, label: str) -> None:
    if not left.index.equals(right.index):
        raise AssertionError(f"{label}: index mismatch")
    pd.testing.assert_series_equal(left, right, check_exact=True, check_dtype=True, check_names=False)


def _source_scan() -> dict:
    banned = (
        "AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose",
        "AdjustmentVolume", "raw_" + "target", "target_1day_" + "valid", "_" + "valid.parquet",
    )
    findings = []
    for relative in TOKEN_SCAN_PATHS:
        source = (ROOT / relative).read_text(encoding="utf-8")
        for token in banned:
            if token in source:
                findings.append({"source": relative, "kind": "forbidden_source_token", "match": token})
    for relative in AST_SCAN_PATHS:
        source = (ROOT / relative).read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr in ("bfill", "backfill"):
                findings.append({"source": relative, "kind": "backfill_call"})
            if any(k.arg == "center" and isinstance(k.value, ast.Constant) and k.value.value
                   for k in node.keywords):
                findings.append({"source": relative, "kind": "centered_operation"})
            if node.func.attr == "shift":
                periods = node.args[0] if node.args else next(
                    (k.value for k in node.keywords if k.arg in ("period", "periods")), None)
                if isinstance(periods, ast.UnaryOp) and isinstance(periods.op, ast.USub):
                    findings.append({"source": relative, "kind": "negative_shift"})
    return {
        "status": "PASS" if not findings else "FAIL",
        "scanned_sources": list(TOKEN_SCAN_PATHS),
        "ast_scanned_sources": list(AST_SCAN_PATHS),
        "checks": ["adjusted OHLCV level references", "raw/Valid target references", "negative shift", "backfill", "centered operations"],
        "findings": findings,
        "interpretation": "Static scan supplements runtime Train-only firewall and mutation tests; it is not a proof of causality.",
    }


def _vol20(inputs: dict[str, pd.DataFrame]) -> pd.Series:
    raw = inputs["raw_return_1day"]["Return"].sort_index().astype("float64")
    index = raw.index
    beta = inputs["beta_1day"]["Return"].reindex(index).astype("float64")
    dates = index.get_level_values("Date")
    market = pd.Series(inputs["topix_return_1day"]["Return"].reindex(dates).to_numpy(dtype="float64"), index=index)
    residual = (raw - beta * market).replace([np.inf, -np.inf], np.nan)
    groups = features.segment_keys(index)
    return residual.groupby(groups, sort=False).transform(
        lambda block: block.shift(1).rolling(WINDOW, min_periods=WINDOW).std(ddof=1)
    ).rename("VOL20")


def _vol_quintile(vol: pd.Series) -> pd.Series:
    pct = vol.groupby(level="Date", sort=False).rank(method="average", pct=True)
    q = (np.ceil(pct * 5.0) - 1.0).clip(0, 4)
    return q.where(vol.notna()).rename("vol_quintile")


def _centered_target_rank(target: pd.Series) -> pd.Series:
    ranks = target.groupby(level="Date", sort=False).rank(method="average", pct=True)
    center = ranks.groupby(level="Date", sort=False).transform("mean")
    return (2.0 * (ranks - center)).where(target.notna()).rename("centered_target_rank")


def _mutate_future(inputs: dict[str, pd.DataFrame], target: pd.Series, cutoff: str):
    cutoff_date = pd.Timestamp(cutoff)
    changed = {key: frame.copy(deep=True) for key, frame in inputs.items()}
    changed_target = target.copy(deep=True)
    audit = {}
    for name, frame in changed.items():
        future = frame.index.get_level_values("Date") > cutoff_date
        before = frame.loc[future].copy(deep=True)
        if name == "topix_return_1day":
            future = frame.index > cutoff_date
            before = frame.loc[future].copy(deep=True)
            frame.loc[future, "Return"] = frame.loc[future, "Return"].fillna(0.0) * 7.0 - 1.0
        elif name in ("raw_return_1day", "beta_1day"):
            frame.loc[future, "Return"] = frame.loc[future, "Return"].fillna(0.0) * -11.0 + 3.0
        elif name == "prices_daily_quotes":
            frame.loc[future, ["High", "Low", "Close"]] = frame.loc[future, ["High", "Low", "Close"]] * 1.37 + 100.0
            frame.loc[future, "AdjustmentFactor"] = 0.25
        audit[name] = {
            "rows_after_cutoff": int(future.sum()),
            "changed_cells": int((before != frame.loc[future]).fillna(False).to_numpy().sum()),
        }
    future_target = changed_target.index.get_level_values("Date") > cutoff_date
    before_target = changed_target.loc[future_target].copy(deep=True)
    changed_target.loc[future_target] = 100.0 - 17.0 * changed_target.loc[future_target].fillna(0.0)
    audit["target_1day_train"] = {
        "rows_after_cutoff": int(future_target.sum()),
        "changed_cells": int((before_target != changed_target.loc[future_target]).fillna(False).sum()),
    }
    return changed, changed_target, audit


def _baseline_reproduction(inputs, target, saved_current: pd.Series, saved_prior: pd.Series):
    x = features.build_features(inputs)
    if not x.index.equals(target.index) or not x.index.is_unique:
        raise AssertionError("Current baseline features do not exactly align to Train target")
    current_frame, _ = submission.predict_from_features(x, target)
    current = current_frame["Return"].rename("Return").sort_index()
    independent_predictions, _ = bidirectional.walk_forward_predictions(x, target)
    independent = submission.candidate_scores_from_predictions(x, independent_predictions)[
        "SIDE_SOURCE_SEPARATION"
    ].rename("Return").sort_index()
    _exact_series(current, independent, "current versus independent SN1_H1")
    _exact_series(current, saved_current, "current versus saved current-run SN1_H1")
    _exact_series(current, saved_prior, "current versus DM-20260930-02 SN1_H1")
    if not np.isfinite(current.to_numpy(dtype="float64")).all():
        raise AssertionError("SN1_H1 score has nonfinite values")
    return x, current, {
        "status": "PASS",
        "rows": int(len(current)),
        "current_route": "dm_variable_box_breakout.submission.predict_from_features",
        "independent_route": "bidirectional.walk_forward_predictions + candidate_scores_from_predictions",
        "saved_current_reference": str(BASELINE_SAVED.relative_to(ROOT)),
        "saved_prior_reference": str(BASELINE_PRIOR.relative_to(ROOT)),
        "current_vs_independent_bitwise_equal": True,
        "current_vs_saved_current_bitwise_equal": True,
        "current_vs_saved_prior_bitwise_equal": True,
        "max_abs_error_all_comparisons": 0.0,
        "candidate_fits": 0,
    }


def _score_metrics(score: pd.Series, target: pd.Series, centered: pd.Series, mask: pd.Series, name: str, year):
    selected = mask & target.notna() & score.notna()
    s, y = score.loc[selected], target.loc[selected]
    cr = centered.reindex(s.index)
    date_count = int(s.index.get_level_values("Date").nunique())
    daily_ic = evaluation.rankic(s, y)
    daily_ic = daily_ic.replace([np.inf, -np.inf], np.nan).dropna()
    daily_unique = s.groupby(level="Date", sort=False).nunique(dropna=True)
    daily_count = s.groupby(level="Date", sort=False).size()
    daily_unique_ratio = (daily_unique / daily_count).replace([np.inf, -np.inf], np.nan)
    qmeans = {}
    q_dates = 0
    mono = np.nan
    if len(s):
        _, q = evaluation.weights(s)
        daily_qmeans = []
        for k in range(5):
            series = y.where(q.eq(k)).groupby(level="Date", sort=False).mean()
            qmeans[f"q{k+1}_target_mean"] = float(series.mean()) if series.notna().any() else np.nan
        spread = (y.where(q.eq(4)).groupby(level="Date", sort=False).mean()
                  - y.where(q.eq(0)).groupby(level="Date", sort=False).mean())
        spread = spread.replace([np.inf, -np.inf], np.nan).dropna()
        q_dates = int(len(spread))
        qspread = float(spread.mean()) if len(spread) else np.nan
        daily_qmeans = [qmeans[f"q{k}_target_mean"] for k in range(1, 6)]
        if np.isfinite(daily_qmeans).all() and len(set(daily_qmeans)) > 1:
            mono = float(spearmanr(range(1, 6), daily_qmeans).statistic)
    else:
        qspread = np.nan
        qmeans = {f"q{k}_target_mean": np.nan for k in range(1, 6)}
    record = {
        "period": name,
        "year": year,
        "stock_days": int(len(s)),
        "active_dates": date_count,
        "rankic_days": int(len(daily_ic)),
        "mean_rankic": float(daily_ic.mean()) if len(daily_ic) else np.nan,
        "rankic_hac5_t": evaluation.hac_t(daily_ic, lag=5),
        "rankic_hit_ratio": float((daily_ic > 0).mean()) if len(daily_ic) else np.nan,
        "q5_q1_spread": qspread,
        "q_spread_dates": q_dates,
        "q_monotonicity": mono,
        "mean_centered_target_rank": float(cr.mean()) if len(cr) else np.nan,
        "mean_residual_return": float(y.mean()) if len(y) else np.nan,
        "next_day_residual_std_pooled": float(y.std(ddof=1)) if len(y) > 1 else np.nan,
        "next_day_residual_std_mean_daily": float(y.groupby(level="Date", sort=False).std(ddof=1).mean()) if len(y) else np.nan,
        "sn1_score_mean": float(s.mean()) if len(s) else np.nan,
        "sn1_score_abs_mean": float(s.abs().mean()) if len(s) else np.nan,
        "exact_zero_rate": float(s.eq(0.0).mean()) if len(s) else np.nan,
        "near_zero_rate": float(s.abs().lt(NEAR_ZERO).mean()) if len(s) else np.nan,
        "unique_score_ratio_pooled": float(s.nunique(dropna=True) / len(s)) if len(s) else np.nan,
        "mean_daily_unique_score_ratio": float(daily_unique_ratio.mean()) if len(daily_unique_ratio) else np.nan,
        "unique_score_count_pooled": int(s.nunique(dropna=True)),
        **qmeans,
    }
    return record


def _volatility_tables(score, target, volq, output: Path):
    centered = _centered_target_rank(target)
    years = score.index.get_level_values("Date").year
    pooled_rows, yearly_rows = [], []
    qcodes = volq.reindex(score.index)
    base_eval = np.isin(years, YEARS) & target.notna().to_numpy() & score.notna().to_numpy()
    for q in range(5):
        qmask = qcodes.eq(float(q)) & pd.Series(base_eval, index=score.index)
        pooled_rows.append({"vol_quintile": f"V{q+1}", **_score_metrics(score, target, centered, qmask, "pooled_2011_2016", "pooled")})
        for year in YEARS:
            ymask = qmask & pd.Series(years == year, index=score.index)
            yearly_rows.append({"vol_quintile": f"V{q+1}", **_score_metrics(score, target, centered, ymask, str(year), int(year))})
    pd.DataFrame(pooled_rows).to_csv(output / "pooled_volatility_quintile.csv", index=False)
    pd.DataFrame(yearly_rows).to_csv(output / "yearly_volatility_quintile.csv", index=False)
    return pd.DataFrame(pooled_rows), pd.DataFrame(yearly_rows)


def _daily_sharpe(values: pd.Series) -> float:
    return evaluation.sharpe(values.to_numpy(dtype="float64"))


def _official_components(score: pd.Series, target: pd.Series):
    weight, q = evaluation.weights(score)
    label_ok = target.notna() & np.isfinite(target.to_numpy(dtype="float64"))
    gross_row = (weight * target).where(label_ok, 0.0).rename("gross")
    turn = weight.groupby(level="Code", sort=False).diff().abs().fillna(weight.abs())
    long_weight, short_weight = weight.clip(lower=0.0), weight.clip(upper=0.0)
    long_turn = long_weight.groupby(level="Code", sort=False).diff().abs().fillna(long_weight.abs())
    short_turn = short_weight.groupby(level="Code", sort=False).diff().abs().fillna(short_weight.abs())
    all_cost = (ONE_WAY_COST * turn).rename("cost_all")
    long_cost_all = (ONE_WAY_COST * long_turn).rename("long_cost_all")
    short_cost_all = (ONE_WAY_COST * short_turn).rename("short_cost_all")
    official_cost = all_cost.where(label_ok, 0.0).rename("cost_official")
    long_cost = long_cost_all.where(label_ok, 0.0).rename("long_cost_official")
    short_cost = short_cost_all.where(label_ok, 0.0).rename("short_cost_official")
    if not np.allclose((long_turn + short_turn).to_numpy(), turn.to_numpy(), rtol=0.0, atol=2e-15):
        raise AssertionError("Long/Short side turnover does not reconcile")
    return weight, q, gross_row, turn, all_cost, official_cost, long_turn, short_turn, long_cost, short_cost


def _attribution(score, target, volq, output: Path):
    (weight, quintile, gross, turnover, all_cost, effective_cost,
     long_turn, short_turn, long_cost, short_cost) = _official_components(score, target)
    dates = score.index.get_level_values("Date")
    vol_group = volq.reindex(score.index).map({float(i): f"V{i+1}" for i in range(5)}).fillna("VOL_MISSING")
    side = pd.Series("Neutral", index=score.index, dtype="object")
    side.loc[weight.gt(0.0)] = "Long"
    side.loc[weight.lt(0.0)] = "Short"
    label_ok = target.notna() & np.isfinite(target.to_numpy(dtype="float64"))
    row_data = pd.DataFrame({
        "weight": weight, "target": target, "gross": gross, "turnover": turnover,
        "all_cost": all_cost, "effective_cost": effective_cost,
        "long_turn": long_turn, "short_turn": short_turn,
        "long_cost_all": ONE_WAY_COST * long_turn, "short_cost_all": ONE_WAY_COST * short_turn,
        "long_cost_official": long_cost, "short_cost_official": short_cost,
        "vol_quintile": vol_group, "side": side,
        "label_ok": label_ok.astype(bool),
    }, index=score.index)
    row_data["net"] = row_data.gross - row_data.effective_cost
    row_data["long_gross"] = row_data.gross.where(row_data.side.eq("Long"), 0.0)
    row_data["short_gross"] = row_data.gross.where(row_data.side.eq("Short"), 0.0)
    row_data["long_net"] = row_data.long_gross - row_data.long_cost_official
    row_data["short_net"] = row_data.short_gross - row_data.short_cost_official
    row_data["position_abs"] = row_data.weight.abs().where(row_data.side.ne("Neutral"), 0.0)
    eval_days = pd.DatetimeIndex(sorted(pd.unique(dates[np.isin(dates.year, YEARS)])), name="Date")
    periods = [("pooled_2011_2016", None)] + [(str(y), y) for y in YEARS]
    records = []
    vol_names = [f"V{i+1}" for i in range(5)] + ["VOL_MISSING"]
    for period, year in periods:
        period_days = eval_days if year is None else eval_days[eval_days.year == year]
        period_mask = np.isin(dates.year, YEARS if year is None else (year,))
        for side_name in ("Long", "Short"):
            for vol_name in vol_names:
                side_turn_col = "long_turn" if side_name == "Long" else "short_turn"
                side_member = row_data.side.eq(side_name)
                mask = (side_member | row_data[side_turn_col].gt(0.0)) & row_data.vol_quintile.eq(vol_name) & pd.Series(period_mask, index=score.index)
                group = row_data.loc[mask]
                pnl_side = "long" if side_name == "Long" else "short"
                gross_daily = group[f"{pnl_side}_gross"].groupby(level="Date", sort=False).sum().reindex(period_days).fillna(0.0)
                net_daily = group[f"{pnl_side}_net"].groupby(level="Date", sort=False).sum().reindex(period_days).fillna(0.0)
                turn_daily = group[side_turn_col].groupby(level="Date", sort=False).sum().reindex(period_days).fillna(0.0)
                cost_official_col = "long_cost_official" if side_name == "Long" else "short_cost_official"
                cost_all_col = "long_cost_all" if side_name == "Long" else "short_cost_all"
                effective_daily = group[cost_official_col].groupby(level="Date", sort=False).sum().reindex(period_days).fillna(0.0)
                attributed_all_daily = group[cost_all_col].groupby(level="Date", sort=False).sum().reindex(period_days).fillna(0.0)
                member_rows = group.loc[group.side.eq(side_name)]
                exposure = float(member_rows.position_abs.sum())
                side_mask = row_data.side.eq(side_name) & pd.Series(period_mask, index=score.index)
                total_exposure = float(row_data.loc[period_mask & side_mask.to_numpy(), "position_abs"].sum())
                all_exposure = float(row_data.loc[period_mask & row_data.side.ne("Neutral").to_numpy(), "position_abs"].sum())
                valid_target = member_rows.loc[member_rows.label_ok, "target"]
                records.append({
                    "period": period, "year": year if year is not None else "pooled",
                    "side": side_name, "vol_quintile": vol_name,
                    "stock_days": int(len(member_rows)),
                    "active_dates": int(member_rows.index.get_level_values("Date").nunique()),
                    "gross_weight_share": exposure / all_exposure if all_exposure else np.nan,
                    "within_side_gross_weight_share": exposure / total_exposure if total_exposure else np.nan,
                    "annual_gross_contribution": float(gross_daily.mean() * 252) if len(gross_daily) else np.nan,
                    "annual_net_contribution": float(net_daily.mean() * 252) if len(net_daily) else np.nan,
                    "gross_contribution_sharpe": _daily_sharpe(gross_daily) if len(gross_daily) > 1 else np.nan,
                    "net_contribution_sharpe": _daily_sharpe(net_daily) if len(net_daily) > 1 else np.nan,
                    "mean_target": float(valid_target.mean()) if len(valid_target) else np.nan,
                    "average_daily_turnover_attribution": float(turn_daily.mean()) if len(turn_daily) else np.nan,
                    "turnover_attribution_sum": float(turn_daily.sum()),
                    "annual_cost_attribution_official": float(effective_daily.mean() * 252) if len(effective_daily) else np.nan,
                    "annual_cost_attribution_all_turnover": float(attributed_all_daily.mean() * 252) if len(attributed_all_daily) else np.nan,
                })
    attribution = pd.DataFrame(records)
    attribution.to_csv(output / "side_vol_attribution.csv", index=False)

    # Reconcile the fixed portfolio attribution to the ordinary baseline account.
    full_daily_gross = gross.where(pd.Series(np.isin(dates.year, YEARS), index=score.index)).groupby(level="Date").sum()
    full_daily_net = row_data.net.where(pd.Series(np.isin(dates.year, YEARS), index=score.index)).groupby(level="Date").sum()
    ordinary = evaluation.daily_account(score, target)
    selected_ordinary = ordinary.loc[ordinary.index.year.isin(YEARS)]
    gross_check = (full_daily_gross.reindex(selected_ordinary.index).fillna(0.0) - selected_ordinary.gross).abs()
    net_check = (full_daily_net.reindex(selected_ordinary.index).fillna(0.0) - selected_ordinary.net).abs()
    if float(gross_check.max()) > 2e-15 or float(net_check.max()) > 2e-15:
        raise AssertionError("Side × volatility attribution does not reconcile to fixed baseline account")
    totals = attribution.loc[attribution.period.eq("pooled_2011_2016")].groupby("side")[["annual_gross_contribution", "annual_net_contribution", "annual_cost_attribution_official", "annual_cost_attribution_all_turnover", "turnover_attribution_sum"]].sum()
    reconciliation = {
        "status": "PASS",
        "daily_gross_max_abs_difference": float(gross_check.max()),
        "daily_net_max_abs_difference": float(net_check.max()),
        "gross_weight_share_v1_v5_and_missing_covers_active_positions": True,
        "turnover_all_sides_reconciles": True,
        "turnover_attribution_method": "Split official weight into disjoint Long and Short sleeves; assign position-entry/exit turnover to that sleeve and current signal-date VOL bucket, including VOL_MISSING when unavailable.",
        "cost_method": "Report both official effective cost (only rows with an official H1 target, matching evaluation.daily_account net) and 10 bp all-turnover cost.",
        "annualized_using": "mean daily contribution over every baseline evaluation date in the period times 252",
    }
    _write_json(output / "side_vol_reconciliation.json", reconciliation)
    return attribution, reconciliation, row_data


def _score_magnitude_attribution(score, target, volq, row_data, output: Path):
    centered = _centered_target_rank(target)
    qseries = volq.reindex(score.index)
    dates = score.index.get_level_values("Date")
    years = dates.year
    # V1 and V5 are fixed endpoints; intermediate vol bins are already in the primary tables.
    rows = []
    for near_label, magnitude_mask in (
        ("near_zero_abs_lt_1e-12", score.abs().lt(NEAR_ZERO)),
        ("non_near_zero_abs_ge_1e-12", score.abs().ge(NEAR_ZERO)),
    ):
        for q, vol_label in ((0.0, "V1"), (4.0, "V5")):
            for period, year in [("pooled_2011_2016", None)] + [(str(y), y) for y in YEARS]:
                period_mask = np.isin(years, YEARS if year is None else (year,))
                mask = magnitude_mask & qseries.eq(q) & target.notna() & pd.Series(period_mask, index=score.index)
                s, y = score.loc[mask], target.loc[mask]
                daily_ic = evaluation.rankic(s, y).replace([np.inf, -np.inf], np.nan).dropna()
                uq = s.groupby(level="Date", sort=False).nunique()
                _, qbins = evaluation.weights(s) if len(s) else (pd.Series(dtype=float), pd.Series(dtype=float))
                if len(s):
                    top = y.where(qbins.eq(4)).groupby(level="Date").mean()
                    bottom = y.where(qbins.eq(0)).groupby(level="Date").mean()
                    spread = (top - bottom).dropna()
                else:
                    spread = pd.Series(dtype=float)
                selected_rows = row_data.loc[mask]
                long_rows = selected_rows.loc[selected_rows.side.eq("Long")]
                short_rows = selected_rows.loc[selected_rows.side.eq("Short")]
                account_dates = pd.DatetimeIndex(sorted(pd.unique(dates[np.isin(years, YEARS if year is None else (year,))])))
                side_contrib = {}
                for side_name, member in (("long", long_rows), ("short", short_rows)):
                    # Attribute side P/L to current score magnitude and VOL bucket; side-specific
                    # turnover costs include exits even when today's position is neutral/opposite.
                    daily_gross = selected_rows[f"{side_name}_gross"].groupby(level="Date").sum().reindex(account_dates).fillna(0.0)
                    daily_net = selected_rows[f"{side_name}_net"].groupby(level="Date").sum().reindex(account_dates).fillna(0.0)
                    turn_col = "long_turn" if side_name == "long" else "short_turn"
                    cost_all_col = f"{side_name}_cost_all"
                    cost_eff_col = f"{side_name}_cost_official"
                    daily_turn = selected_rows[turn_col].groupby(level="Date").sum().reindex(account_dates).fillna(0.0)
                    daily_cost_all = selected_rows[cost_all_col].groupby(level="Date").sum().reindex(account_dates).fillna(0.0)
                    daily_cost_eff = selected_rows[cost_eff_col].groupby(level="Date").sum().reindex(account_dates).fillna(0.0)
                    side_contrib[f"{side_name}_annual_gross_contribution"] = float(daily_gross.mean() * 252) if len(daily_gross) else np.nan
                    side_contrib[f"{side_name}_annual_net_contribution"] = float(daily_net.mean() * 252) if len(daily_net) else np.nan
                    side_contrib[f"{side_name}_annual_cost_attribution_official"] = float(daily_cost_eff.mean() * 252) if len(daily_cost_eff) else np.nan
                    side_contrib[f"{side_name}_annual_cost_attribution_all_turnover"] = float(daily_cost_all.mean() * 252) if len(daily_cost_all) else np.nan
                    side_contrib[f"{side_name}_average_daily_turnover_attribution"] = float(daily_turn.mean()) if len(daily_turn) else np.nan
                rows.append({
                    "period": period, "year": year if year is not None else "pooled",
                    "score_magnitude": near_label, "vol_quintile": vol_label,
                    "stock_days": int(len(s)), "active_dates": int(s.index.get_level_values("Date").nunique()),
                    "mean_rankic": float(daily_ic.mean()) if len(daily_ic) else np.nan,
                    "rankic_hac5_t": evaluation.hac_t(daily_ic, lag=5),
                    "rankic_hit_ratio": float((daily_ic > 0).mean()) if len(daily_ic) else np.nan,
                    "mean_target": float(y.mean()) if len(y) else np.nan,
                    "mean_centered_target_rank": float(centered.reindex(s.index).mean()) if len(s) else np.nan,
                    "q5_q1_spread": float(spread.mean()) if len(spread) else np.nan,
                    "q_spread_dates": int(len(spread)),
                    "unique_score_ratio": float(s.nunique() / len(s)) if len(s) else np.nan,
                    "long_membership_stock_days": int(len(long_rows)),
                    "short_membership_stock_days": int(len(short_rows)),
                    "long_membership_rate": float(len(long_rows) / len(s)) if len(s) else np.nan,
                    "short_membership_rate": float(len(short_rows) / len(s)) if len(s) else np.nan,
                    **side_contrib,
                })
    result = pd.DataFrame(rows)
    result.to_csv(output / "score_magnitude_vol_attribution.csv", index=False)
    return result


def _boundary_sensitivity(score, volq, output: Path):
    base_weight, base_q = evaluation.weights(score)
    codes = score.index.get_level_values("Code").astype(str)
    perturbation = {code: int.from_bytes(hashlib.blake2b(code.encode(), digest_size=8, key=PERTURBATION_KEY).digest(), "big") / (2**64) - 0.5 for code in pd.Index(codes).unique()}
    daily_sd = score.groupby(level="Date", sort=False).transform("std")
    u = pd.Series(codes.map(perturbation).to_numpy(dtype="float64"), index=score.index)
    changed_score = score + TINY_PERTURBATION * daily_sd * u
    _, changed_q = evaluation.weights(changed_score)
    if not changed_q.index.equals(base_q.index):
        raise AssertionError("Tiny-perturbation membership index changed")
    changed = base_q.ne(changed_q)
    qchg = {f"changed_q{k+1}_membership_fraction": (base_q.eq(k) != changed_q.eq(k)) for k in range(5)}
    qtail_short = base_q.le(1) != changed_q.le(1)
    qtail_long = base_q.ge(3) != changed_q.ge(3)
    rows = []
    vol_group = volq.reindex(score.index)
    dates = score.index.get_level_values("Date")
    for period, year in [("pooled_2011_2016", None)] + [(str(y), y) for y in YEARS]:
        period_mask = np.isin(dates.year, YEARS if year is None else (year,))
        for q in range(5):
            group_mask = period_mask & vol_group.eq(float(q)).to_numpy()
            ix = score.index[group_mask]
            q1 = base_q.reindex(ix)
            q2 = changed_q.reindex(ix)
            pert_changed = q1.ne(q2)
            d = score.loc[ix]
            boundary_endpoint = pd.Series(False, index=ix)
            tie_endpoint = pd.Series(False, index=ix)
            near_endpoint = pd.Series(False, index=ix)
            pair_count = 0
            tie_pairs = 0
            near_pairs = 0
            daily_sd_group = daily_sd.loc[ix]
            eps = TINY_PERTURBATION * daily_sd_group
            frame = pd.DataFrame({"score": d, "q": q1}).reset_index()
            frame["Code"] = frame["Code"].astype(str)
            for _, day in frame.groupby("Date", sort=True):
                day = day.sort_values(["score", "Code"], kind="mergesort").reset_index(drop=True)
                boundary_ix = np.flatnonzero(day.q.to_numpy()[1:] != day.q.to_numpy()[:-1])
                for left in boundary_ix:
                    pair_count += 1
                    a, b = day.iloc[left], day.iloc[left + 1]
                    pair_gap = float(b.score - a.score)
                    pair_codes = [(pd.Timestamp(a.Date), str(a.Code)), (pd.Timestamp(b.Date), str(b.Code))]
                    for key in pair_codes:
                        boundary_endpoint.loc[key] = True
                        if pair_gap == 0.0:
                            tie_endpoint.loc[key] = True
                        if pair_gap <= float(TINY_PERTURBATION * day.score.std()):
                            near_endpoint.loc[key] = True
                    if pair_gap == 0.0:
                        tie_pairs += 1
                    if pair_gap <= float(TINY_PERTURBATION * day.score.std()):
                        near_pairs += 1
            endpoint_n = int(boundary_endpoint.sum())
            rows.append({
                "period": period, "year": year if year is not None else "pooled",
                "vol_quintile": f"V{q+1}", "stock_days": int(len(ix)),
                "changed_quintile_fraction": float(pert_changed.mean()) if len(ix) else np.nan,
                "changed_q1_q2_membership_fraction": float(qtail_short.loc[ix].mean()) if len(ix) else np.nan,
                "changed_q4_q5_membership_fraction": float(qtail_long.loc[ix].mean()) if len(ix) else np.nan,
                **{key: float(value.loc[ix].mean()) if len(ix) else np.nan for key, value in qchg.items()},
                "boundary_pairs": pair_count,
                "boundary_endpoints_in_vol_group": endpoint_n,
                "tie_boundary_pair_fraction": tie_pairs / pair_count if pair_count else np.nan,
                "near_tie_boundary_pair_fraction": near_pairs / pair_count if pair_count else np.nan,
                "tie_boundary_endpoint_fraction": float(tie_endpoint.mean()) if len(ix) else np.nan,
                "near_tie_boundary_endpoint_fraction": float(near_endpoint.mean()) if len(ix) else np.nan,
                "perturbation": "1e-12 × full daily score SD × fixed BLAKE2b(Code) u; key SN1-20260928",
            })
    result = pd.DataFrame(rows)
    result.to_csv(output / "boundary_sensitivity.csv", index=False)
    return result


def _prefix_audit(inputs, target, x, baseline, original_vol, output: Path):
    dates = baseline.index.get_level_values("Date")
    rows = []
    for cutoff in CUTOFFS:
        mutated_inputs, mutated_target, changes = _mutate_future(inputs, target, cutoff)
        changed_x = features.build_features(mutated_inputs)
        changed_vol = _vol20(mutated_inputs)
        if not changed_x.index.equals(x.index) or not changed_vol.index.equals(original_vol.index):
            raise AssertionError(f"Future mutation changed a full input index at {cutoff}")
        prefix = dates <= pd.Timestamp(cutoff)
        prefix_index = baseline.index[prefix]
        pd.testing.assert_frame_equal(x.loc[prefix_index], changed_x.loc[prefix_index], check_exact=True, check_dtype=True)
        _exact_series(original_vol.loc[prefix_index], changed_vol.loc[prefix_index], f"VOL20 prefix {cutoff}")
        changed_frame, _ = submission.predict_from_features(changed_x, mutated_target)
        changed_baseline = changed_frame["Return"].rename("Return").sort_index()
        _exact_series(baseline.loc[prefix_index], changed_baseline.loc[prefix_index], f"SN1_H1 prefix {cutoff}")
        if any(item["changed_cells"] <= 0 for item in changes.values()):
            raise AssertionError(f"A Train input source did not change after {cutoff}")
        rows.append({
            "cutoff": cutoff, "prefix_rows": int(prefix.sum()),
            "changed_sources": changes,
            "feature_prefix_bitwise_equal": True,
            "vol20_prefix_bitwise_equal": True,
            "baseline_score_prefix_bitwise_equal": True,
        })
    result = {"status": "PASS", "cutoffs": rows,
              "source_mutation": "post-cutoff raw_return/beta * -11 + 3; TOPIX * 7 - 1; selected raw OHLC * 1.37 + 100 and AdjustmentFactor=0.25; H1 Train target=100 - 17*target",
              "comparison": "Exact index, dtype and bitwise values for all baseline feature columns, VOL20 and SN1_H1 score through each cutoff."}
    _write_json(output / "prefix_invariance.json", result)
    return result


def _coverage_audit(score, target, vol, vol_repeat, baseline_daily_path: Path, output: Path):
    if not score.index.equals(target.index) or not score.index.equals(vol.index):
        raise AssertionError("Score, target and VOL20 indexes are not exactly equal")
    if score.index.has_duplicates or target.index.has_duplicates or vol.index.has_duplicates:
        raise AssertionError("Duplicate Date×Code index")
    if not np.isfinite(score.to_numpy(dtype="float64")).all():
        raise AssertionError("Nonfinite baseline score")
    _exact_series(vol, vol_repeat, "deterministic VOL20 replay")
    daily = evaluation.daily_account(score, target)
    saved = pd.read_csv(baseline_daily_path, parse_dates=["Date"]).set_index("Date").sort_index()
    selected = daily.loc[daily.index.year.isin(YEARS)].reindex(saved.index)
    fields = [c for c in ("gross", "net", "cost", "turnover", "rankic") if c in selected and c in saved]
    deltas = {}
    account_tolerance = 2e-15
    for field in fields:
        left, right = selected[field].to_numpy(dtype="float64"), saved[field].to_numpy(dtype="float64")
        finite = np.isfinite(left) & np.isfinite(right)
        delta = float(np.max(np.abs(left[finite] - right[finite]))) if finite.any() else 0.0
        if not np.array_equal(np.isnan(left), np.isnan(right)) or delta > account_tolerance:
            raise AssertionError(f"Current official account differs from saved baseline on {field}")
        deltas[field] = delta
    years = score.index.get_level_values("Date").year
    eval_mask = np.isin(years, YEARS)
    _write_json(output / "coverage_determinism.json", {
        "status": "PASS", "score_rows": int(len(score)), "index_exact": True,
        "score_finite": True, "vol20_deterministic_bitwise": True,
        "target_nonmissing_rows_2011_2016": int((eval_mask & target.notna().to_numpy()).sum()),
        "vol20_nonmissing_rows_2011_2016": int((eval_mask & vol.notna().to_numpy()).sum()),
        "h1_target_coverage_2011_2016": float(target.loc[eval_mask].notna().mean()),
        "official_account_daily_max_abs_delta_vs_saved": deltas,
        "official_account_numeric_tolerance": account_tolerance,
        "official_account_parity": "PASS within serialization/numerical tolerance; baseline score parity itself is bitwise",
    })
    return daily


def _interpret(pooled: pd.DataFrame, yearly: pd.DataFrame, side: pd.DataFrame, magnitude: pd.DataFrame):
    p = pooled.set_index("vol_quintile")
    v1, v5 = p.loc["V1"], p.loc["V5"]
    ic_direction = bool(v1.mean_rankic > v5.mean_rankic)
    spread_direction = bool(v1.q5_q1_spread > v5.q5_q1_spread)
    full = yearly.loc[yearly.year.isin(COMPLETE_YEARS)].pivot(index="year", columns="vol_quintile", values=["mean_rankic", "q5_q1_spread"])
    stable_years = sum(bool(full.loc[y, ("mean_rankic", "V1")] > full.loc[y, ("mean_rankic", "V5")] and
                           full.loc[y, ("q5_q1_spread", "V1")] > full.loc[y, ("q5_q1_spread", "V5")]) for y in COMPLETE_YEARS)
    short = side.loc[(side.period == "pooled_2011_2016") & (side.side == "Short")].set_index("vol_quintile")
    short_loss_concentrated_high = bool(short.loc["V5", "annual_gross_contribution"] < short.loc["V1", "annual_gross_contribution"])
    m = magnitude.loc[(magnitude.period == "pooled_2011_2016") & (magnitude.score_magnitude == "near_zero_abs_lt_1e-12")].set_index("vol_quintile")
    nearzero_high_worse = bool(m.loc["V5", "mean_rankic"] < m.loc["V1", "mean_rankic"])
    if ic_direction and spread_direction and stable_years >= 3 and (short_loss_concentrated_high or nearzero_high_worse):
        result = "SUPPORT"
    elif ic_direction or spread_direction:
        result = "MIXED"
    else:
        result = "NOT SUPPORTED"
    return result, {
        "pooled_rankic_v1_gt_v5": ic_direction,
        "pooled_q5_q1_v1_gt_v5": spread_direction,
        "complete_years_both_directions_2011_2015": int(stable_years),
        "short_gross_contribution_v5_more_negative_than_v1": short_loss_concentrated_high,
        "nearzero_score_rankic_v5_below_v1": nearzero_high_worse,
        "rule": "Prerecorded qualitative gate in experiments/DM-20261001-02/config.json; no post-result thresholds.",
    }


def _render_report(result, checks, baseline_audit, feature_audit, prefix, coverage, pooled, yearly, side, magnitude, boundary, run_id, output: Path):
    idx = pooled.set_index("vol_quintile")
    lines = [
        f"# DM-20261001-02: SN1_H1 VOL20 confidence diagnostic", "",
        "- **Baseline:** `SN1_H1`", "- **Change to trading strategy:** **None**",
        "- **New variable:** prior-only market-residual `VOL20` (20 stock observations ending at `t-1`; sample SD, `ddof=1`) used for diagnostics only.",
        "- **Main question:** Does SN1 ranking quality deteriorate as idiosyncratic volatility rises?",
        f"- **Result:** **{result}**", "- **Limitation:** Train development-history diagnostic only; no candidate strategy evaluated; no OOS claim.",
        f"- Run: `{run_id}`. Valid and raw-target inputs were not opened.", "",
        "## Baseline reproduction and fixed setup", "",
        f"Current, independent and both saved SN1_H1 references matched bit for bit over {baseline_audit['rows']:,} rows. Official account daily parity was checked against the saved current baseline; result: **{coverage['status']}**.",
        "VOL20 uses the current PIT beta and TOPIX Train series with the existing listing-gap reset. Exactly 20 finite prior residual observations are required; missing VOL20 is not imputed. V1 is lowest daily percentile, V5 highest. The strategy's saved official weights and membership were held fixed.",
        f"Future mutation changed all five staged Train sources at three cutoffs and preserved features, VOL20 and SN1_H1 bitwise through each cutoff: **{prefix['status']}**.",
        "", "## Pooled V1–V5 prediction diagnostics", "",
        "RankIC is calculated cross-sectionally inside each volatility quintile and averaged across active dates. HAC t-stat uses lag 5. Q1–Q5 returns rank SN1 scores within that volatility bucket each date; Q5−Q1 and monotonicity are descriptive. Returns are official H1 Train residual targets.",
        "", "| Vol | Stock-days | Active dates | Mean RankIC | HAC-5 t | Hit ratio | Q5−Q1 (bp/day) | Centered target rank | Mean target (bp) | Target SD (bp) | Near-zero score | Unique score ratio |",
        "|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for q in range(1, 6):
        r = idx.loc[f"V{q}"]
        lines.append(f"| V{q} | {int(r.stock_days):,} | {int(r.active_dates):,} | {r.mean_rankic:+.6f} | {r.rankic_hac5_t:+.3f} | {r.rankic_hit_ratio:.3f} | {r.q5_q1_spread*1e4:+.3f} | {r.mean_centered_target_rank:+.5f} | {r.mean_residual_return*1e4:+.3f} | {r.next_day_residual_std_pooled*1e4:.2f} | {r.near_zero_rate:.3%} | {r.unique_score_ratio_pooled:.3%} |")
    lines += ["", "The full pooled table also records exact-zero rate, mean/absolute score, pooled and mean-daily unique ratios, each Q1–Q5 mean, and pooled/daily target dispersion in [`pooled_volatility_quintile.csv`](../../artifacts/" + EXPERIMENT_ID + f"/{run_id}/metrics/pooled_volatility_quintile.csv). Year/fold values for every V1–V5 bucket, including partial 2016, are in [`yearly_volatility_quintile.csv`](../../artifacts/" + EXPERIMENT_ID + f"/{run_id}/metrics/yearly_volatility_quintile.csv).", "", "### Year/fold RankIC and spread", "", "| Year | V1 RankIC | V5 RankIC | V1 Q5−Q1 bp/day | V5 Q5−Q1 bp/day |", "|---:|---:|---:|---:|---:|"]
    yearp = yearly.pivot(index="year", columns="vol_quintile", values=["mean_rankic", "q5_q1_spread"])
    for year in YEARS:
        lines.append(f"| {year}{' *' if year == 2016 else ''} | {yearp.loc[year, ('mean_rankic','V1')]:+.6f} | {yearp.loc[year, ('mean_rankic','V5')]:+.6f} | {yearp.loc[year, ('q5_q1_spread','V1')]*1e4:+.3f} | {yearp.loc[year, ('q5_q1_spread','V5')]*1e4:+.3f} |")
    lines += ["", "*2016 is a partial fold.*", "", "## Fixed official Side × Vol attribution", "", "This is accounting attribution of unchanged official memberships, weights and 10 bp one-way costs. It is not a counterfactual portfolio or a volatility-sorted portfolio. Trade turnover is attributed to the Long/Short sleeve and current day's VOL bucket (including `VOL_MISSING` for exits without a usable current bucket). Both official effective cost and all-turnover cost are saved. Pooled/year rows and reconciliation checks are in [`side_vol_attribution.csv`](../../artifacts/" + EXPERIMENT_ID + f"/{run_id}/metrics/side_vol_attribution.csv).", "", "| Side × Vol | Stock-days | Gross weight share | Annual gross contrib. | Annual net contrib. | Net contrib. SR | Mean H1 target (bp) | Daily turnover attrib. | Annual cost all-turnover |"]
    lines.append("|:--|--:|--:|--:|--:|--:|--:|--:|--:|")
    side_pool = side.loc[side.period.eq("pooled_2011_2016")].set_index(["side", "vol_quintile"])
    for side_name in ("Long", "Short"):
        for q in range(1, 6):
            r = side_pool.loc[(side_name, f"V{q}")]
            lines.append(f"| {side_name} × V{q} | {int(r.stock_days):,} | {r.gross_weight_share:.2%} | {r.annual_gross_contribution:+.3%} | {r.annual_net_contribution:+.3%} | {r.net_contribution_sharpe:+.3f} | {r.mean_target*1e4:+.3f} | {r.average_daily_turnover_attribution:.5f} | {r.annual_cost_attribution_all_turnover:.3%} |")
    lines += ["", "## Score magnitude and boundary sensitivity", "", "`abs(score) < 1e-12` is the frozen near-zero definition. Compare `near_zero_abs_lt_1e-12` with `non_near_zero_abs_ge_1e-12` for V1 and V5; RankIC, score-ranked spread, unchanged Long/Short membership, and side contribution are in [`score_magnitude_vol_attribution.csv`](../../artifacts/" + EXPERIMENT_ID + f"/{run_id}/metrics/score_magnitude_vol_attribution.csv). Near-zero score rows can have little or no within-group ranking variation; the saved unique-score ratio and valid RankIC days make that visible.", "", "Boundary sensitivity reuses the existing deterministic `1e-12 × daily score SD` BLAKE2b Code perturbation. No perturbation search or portfolio selection was run. Per-volatility changed quintile/Long/Short membership fractions and tie/near-tie boundary frequencies are in [`boundary_sensitivity.csv`](../../artifacts/" + EXPERIMENT_ID + f"/{run_id}/metrics/boundary_sensitivity.csv).", "", "## Interpretation", ""]
    lines.append(f"Predeclared checks: pooled V1>V5 RankIC = **{checks['pooled_rankic_v1_gt_v5']}**; pooled V1>V5 Q5−Q1 = **{checks['pooled_q5_q1_v1_gt_v5']}**; both directions in complete years 2011–2015 = **{checks['complete_years_both_directions_2011_2015']}/5**; high-vol Short gross loss more negative = **{checks['short_gross_contribution_v5_more_negative_than_v1']}**; near-zero RankIC worse in V5 = **{checks['nearzero_score_rankic_v5_below_v1']}**.")
    lines += ["", "The observed Train sample is development history. These descriptive associations do not establish that volatility causes ranking errors or that a confidence adjustment improves performance. Phase 1 evaluated no strategy candidate and made no OOS claim.", ""]
    (ROOT / "reports" / EXPERIMENT_ID / "REPORT.md").parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / EXPERIMENT_ID / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def run(data_dir: Path, output_dir: Path, run_json: Path):
    started = time.monotonic()
    data_dir, output_dir, run_json = Path(data_dir), Path(output_dir), Path(run_json)
    for name in ("audit", "metrics", "predictions"):
        (output_dir / name).mkdir(parents=True, exist_ok=True)
    _update_run(run_json, {"status": "running", "started_at_utc": _now(), "actual_trials": [], "candidate_fits": 0, "max_trials": 1, "valid_evaluation": False})
    status = "failed"
    try:
        scan = _source_scan()
        _write_json(output_dir / "audit/source_scan.json", scan)
        if scan["status"] != "PASS":
            raise AssertionError(f"Source/leak scan failed: {scan['findings']}")
        train_paths = sorted(data_dir.glob("*_train.parquet"))
        if {p.name for p in train_paths} != INPUT_NAMES:
            raise AssertionError(f"Unexpected Train-only stage: {sorted(p.name for p in train_paths)}")
        inputs_hashes = {p.name: _sha(p) for p in train_paths}
        source_hashes = {p: _sha(ROOT / p) for p in SOURCE_PATHS}
        _update_run(run_json, {
            "command": f".venv/bin/python -m research.experiments.sn1_volatility_diagnostic --data-dir {data_dir} --output-dir {output_dir} --run-json {run_json}",
            "deadline_seconds": 1800,
            "source_sha256": source_hashes,
            "code_sha256": source_hashes["research/experiments/sn1_volatility_diagnostic.py"],
            "train_data_sha256": inputs_hashes,
            "environment": {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__, "pandas": pd.__version__},
        })
        firewall.install(allowed_artifacts=[BASELINE_SAVED, BASELINE_PRIOR])
        if not BASELINE_SAVED.is_file() or not BASELINE_PRIOR.is_file() or not BASELINE_DAILY.is_file():
            raise FileNotFoundError("Required saved current baseline reference/account is missing")
        inputs = features.load_inputs(data_dir, split="train")
        target = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index().astype("float64")
        saved_current = pd.read_parquet(BASELINE_SAVED)["Return"].sort_index().rename("Return")
        saved_prior = pd.read_parquet(BASELINE_PRIOR)["Return"].sort_index().rename("Return")
        x, score, base_audit = _baseline_reproduction(inputs, target, saved_current, saved_prior)
        score.to_frame("Return").to_parquet(output_dir / "predictions/SN1_H1.parquet", compression="zstd")
        _write_json(output_dir / "audit/baseline_reproduction.json", base_audit)

        vol = _vol20(inputs)
        vol_repeat = _vol20(inputs)
        if not vol.index.equals(score.index) or not np.isfinite(score.to_numpy()).all():
            raise AssertionError("VOL20 or score index/coverage failed")
        pd.testing.assert_series_equal(vol, vol_repeat, check_exact=True, check_dtype=True)
        vol.to_frame().to_parquet(output_dir / "predictions/VOL20.parquet", compression="zstd")
        volq = _vol_quintile(vol)
        feat_audit = {
            "status": "PASS", "variable": "VOL20", "formula": "std(raw_return - PIT_beta * TOPIX, prior 20 stock observations)",
            "raw_return_source": "raw_return_1day_train.parquet / Return",
            "beta_source": "beta_1day_train.parquet / Return, reindexed by exact Date×Code",
            "market_source": "topix_return_1day_train.parquet / Return, aligned by signal date",
            "prior_only": True, "shift_observations": 1, "window_observations": WINDOW,
            "min_periods": WINDOW, "ddof": 1,
            "listing_gap_rule": "features.segment_keys, reset after >20 market-date positions",
            "missing_policy": "No imputation; NaN if fewer than 20 finite prior residual observations; excluded from V1-V5 and retained as VOL_MISSING in portfolio attribution.",
            "vol20_nonmissing_rows": int(vol.notna().sum()), "vol20_missing_rows": int(vol.isna().sum()),
            "daily_quintile_rule": "average percentile rank among finite VOL20, q=clip(ceil(5*pct)-1,0,4)",
            "same_day_or_future_return_used": False, "adjusted_ohlcv_levels_used": False,
        }
        _write_json(output_dir / "audit/volatility_feature.json", feat_audit)

        prefix = _prefix_audit(inputs, target, x, score, vol, output_dir / "audit")
        firewall.save(output_dir / "audit/firewall.json")
        daily = _coverage_audit(score, target, vol, vol_repeat, BASELINE_DAILY, output_dir / "audit")
        coverage = json.loads((output_dir / "audit/coverage_determinism.json").read_text(encoding="utf-8"))
        pooled, yearly = _volatility_tables(score, target, volq, output_dir / "metrics")
        side, reconciliation, row_data = _attribution(score, target, volq, output_dir / "metrics")
        magnitude = _score_magnitude_attribution(score, target, volq, row_data, output_dir / "metrics")
        boundary = _boundary_sensitivity(score, volq, output_dir / "metrics")
        official_daily = daily.loc[daily.index.year.isin(YEARS)]
        official_daily.to_csv(output_dir / "metrics/daily_account_SN1_H1.csv", index_label="Date")
        pd.DataFrame([evaluation.metrics(official_daily)]).to_csv(output_dir / "metrics/baseline_pooled_metrics.csv", index=False)
        result, checks = _interpret(pooled, yearly, side, magnitude)
        _write_json(output_dir / "audit/attribution_reconciliation.json", reconciliation)
        _write_json(output_dir / "metrics/interpretation.json", {"result": result, "checks": checks})
        _render_report(result, checks, base_audit, feat_audit, prefix, coverage, pooled, yearly, side, magnitude, boundary, run_json.parent.name, output_dir)
        status = "completed"
        _update_run(run_json, {
            "status": status, "completed_at_utc": _now(), "exit_code": 0,
            "actual_trials": ["VOL20_PHASE1_DIAGNOSTIC"], "candidate_fits": 0,
            "result": result, "source_scan_status": scan["status"],
            "baseline_reproduction_status": base_audit["status"], "prefix_invariance_status": prefix["status"],
            "volatility_feature_audit_status": feat_audit["status"], "attribution_reconciliation_status": reconciliation["status"],
            "valid_evaluation": False, "raw_target_accessed": False,
            "opened_parquets": sorted(firewall.ACCESSES),
            "elapsed_seconds": time.monotonic() - started,
        })
    except BaseException as error:
        try:
            firewall.save(output_dir / "audit/firewall.json")
        except Exception:
            pass
        _update_run(run_json, {"status": "failed", "completed_at_utc": _now(), "exit_code": 1,
                               "error": f"{type(error).__name__}: {error}",
                               "opened_parquets": sorted(firewall.ACCESSES),
                               "elapsed_seconds": time.monotonic() - started})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-json", type=Path, required=True)
    args = parser.parse_args()
    run(args.data_dir, args.output_dir, args.run_json)


if __name__ == "__main__":
    main()
