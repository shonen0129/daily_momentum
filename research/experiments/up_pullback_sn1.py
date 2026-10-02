"""One fixed Train-only UP_PULLBACK feature test for current SN1_H1."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow
import scipy

from research import evaluation, firewall
from stock_comp_2026.strategies.dm_variable_box_breakout import bidirectional
from stock_comp_2026.strategies.dm_variable_box_breakout import sn1
from stock_comp_2026.strategies.dm_variable_box_breakout import submission as sn1_submission
from stock_comp_2026.strategies.dm_eventbox_sn1 import features as event_features
from stock_comp_2026.strategies.dm_eventbox_sn1 import models as event_models


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DM-20261001-01"
YEARS = tuple(range(2011, 2017))
PARTIAL_YEAR = 2016
PURGE_POSITIONS = 2
ONE_WAY_COST = 0.001
RIDGE_COLUMNS = tuple(bidirectional.DIRECTIONAL_COLUMNS) + ("pullback_up",)
BASELINE_REFERENCE = ROOT / (
    "artifacts/DM-20260930-02/run-20260930T081524Z/"
    "predictions/SN1_H1.parquet"
)
SOURCE_PATHS = (
    "research/experiments/up_pullback_sn1.py",
    "research/evaluation.py",
    "research/firewall.py",
    "stock_comp_2026/strategies/dm_eventbox_sn1/features.py",
    "stock_comp_2026/strategies/dm_eventbox_sn1/models.py",
    "stock_comp_2026/strategies/dm_eventbox_sn1/submission.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/features.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/submission.py",
    "stock_comp_2026/strategies/dm_event_box/core.py",
    "stock_comp_2026/strategies/dm_event_box/features.py",
)
SCAN_PATHS = (
    "stock_comp_2026/strategies/dm_eventbox_sn1/features.py",
    "stock_comp_2026/strategies/dm_eventbox_sn1/models.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/features.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py",
    "stock_comp_2026/strategies/dm_event_box/core.py",
    "stock_comp_2026/strategies/dm_event_box/features.py",
)
EXPECTED_INPUTS = {
    "raw_return_1day_train.parquet",
    "beta_1day_train.parquet",
    "topix_return_1day_train.parquet",
    "prices_daily_quotes_train.parquet",
    "target_1day_train.parquet",
}


def _sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(value), ensure_ascii=False, indent=2,
                               allow_nan=False) + "\n", encoding="utf-8")


def _update_run(run_json, values):
    path = Path(run_json)
    record = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    record.update(_json_safe(values))
    _write_json(path, record)


def _source_scan():
    findings = []
    forbidden_tokens = (
        "AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose",
        "AdjustmentVolume", "raw_target_", "target_1day_valid", "_valid.parquet",
        "shift(-", ".bfill(", ".backfill(", "center=True",
    )
    for relative in SCAN_PATHS:
        source_path = ROOT / relative
        source = source_path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in source:
                findings.append({"source": relative, "kind": "forbidden_text", "match": token})
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr in ("bfill", "backfill"):
                findings.append({"source": relative, "kind": "backfill_call"})
            if any(keyword.arg == "center" and isinstance(keyword.value, ast.Constant)
                   and keyword.value.value for keyword in node.keywords):
                findings.append({"source": relative, "kind": "centered_operation"})
            if node.func.attr == "shift":
                periods = node.args[0] if node.args else next(
                    (keyword.value for keyword in node.keywords
                     if keyword.arg in ("periods", "period")), None)
                if isinstance(periods, ast.UnaryOp) and isinstance(periods.op, ast.USub):
                    findings.append({"source": relative, "kind": "negative_shift"})
    return {
        "status": "PASS" if not findings else "FAIL",
        "scanned_sources": list(SCAN_PATHS),
        "checks": ["forbidden adjusted OHLCV levels", "raw/Valid target filename",
                   "negative shift", "backfill", "centered rolling"],
        "findings": findings,
        "scope_note": "Static checks cover the active feature/state/model sources. Runtime Train firewall records opened parquet files; current submission prediction receives already-loaded Train features/target.",
    }


def _assert_series_exact(left, right, label):
    if not left.index.equals(right.index):
        raise AssertionError(f"{label}: indexes differ")
    pd.testing.assert_series_equal(left, right, check_exact=True, check_dtype=True,
                                   check_names=False)


def _feature_contract(x):
    expected = x["event_upstate"] * (-x["event_box_position"]).clip(lower=0.0)
    pd.testing.assert_series_equal(
        x["pullback_up"], expected.rename("pullback_up"), check_exact=True,
        check_dtype=True,
    )
    base = bidirectional.directional_features(x, "high")
    matrix = base.join(x.loc[:, ["pullback_up"]])
    if tuple(matrix.columns) != RIDGE_COLUMNS:
        raise AssertionError(f"UP_PULLBACK columns changed: {list(matrix.columns)}")
    low = bidirectional.directional_features(x, "low").join(x.loc[:, ["pullback_up"]])
    if tuple(low.columns) != RIDGE_COLUMNS:
        raise AssertionError(f"UP_PULLBACK low columns changed: {list(low.columns)}")
    return {
        "status": "PASS",
        "feature_name_in_code": "pullback_up",
        "registered_feature_name": "UP_PULLBACK",
        "formula": "event_upstate * max(0, -event_box_position)",
        "box_position_formula": "2*(Close-Lower)/(Upper-Lower)-1 in the existing BOX state; missing outside BOX",
        "event_upstate_definition": "existing persistent Event-Box direction > 0, computed from signal-date observations",
        "baseline_columns": list(bidirectional.DIRECTIONAL_COLUMNS),
        "candidate_columns": list(RIDGE_COLUMNS),
        "added_columns": ["pullback_up"],
        "rows": int(len(x)),
        "nonzero_feature_rows": int(x["pullback_up"].gt(0.0).sum()),
        "formula_exact": True,
    }


def _candidate_matrix(x, side):
    matrix = bidirectional.directional_features(x, side).join(x.loc[:, ["pullback_up"]])
    if tuple(matrix.columns) != RIDGE_COLUMNS:
        raise AssertionError("Candidate must use only the five current SN1 columns plus UP_PULLBACK")
    return matrix.replace([np.inf, -np.inf], np.nan)


def _fit_candidate_before(x, target, calendar, fold_start, side):
    if side not in bidirectional.SIDES:
        raise ValueError(f"Unknown side: {side}")
    if not x.index.equals(target.index):
        raise ValueError("Feature and target indexes differ")
    calendar = pd.DatetimeIndex(calendar).sort_values().unique()
    dates = x.index.get_level_values("Date")
    start_position = calendar.searchsorted(pd.Timestamp(fold_start))
    mature_dates = calendar[:max(0, start_position - PURGE_POSITIONS)]
    mature = dates.isin(mature_dates)
    centered_rank = bidirectional.centered_target_rank(target)
    oriented = centered_rank if side == "high" else -centered_rank
    training = mature & bidirectional.event_mask(x, side).to_numpy() & oriented.notna().to_numpy()
    rows = int(training.sum())
    if rows < event_models.MIN_TRAINING_ROWS:
        raise ValueError(f"Too few mature {side} events before {fold_start}: {rows}")
    matrix = _candidate_matrix(x.loc[training], side)
    model = event_models.fit_arrays(
        matrix, oriented.loc[training], RIDGE_COLUMNS,
        ridge_lambda=event_models.RIDGE_LAMBDA,
    )
    used_dates = dates[training]
    last_signal = pd.Timestamp(used_dates.max())
    position = calendar.get_indexer([last_signal])[0]
    model.update({
        "candidate": "UP_PULLBACK",
        "side": side,
        "year": int(pd.Timestamp(fold_start).year),
        "training_dates": int(used_dates.nunique()),
        "min_training_signal": str(pd.Timestamp(used_dates.min()).date()),
        "max_training_signal": str(last_signal.date()),
        "max_label_maturity_date": str(calendar[min(position + PURGE_POSITIONS, len(calendar) - 1)].date()),
    })
    if not pd.Timestamp(model["max_label_maturity_date"]) < pd.Timestamp(fold_start):
        raise AssertionError(f"Unmatured H1 label in {side} fold {fold_start}")
    return model, training


def _predict_candidate(x, target, years=YEARS, model_dir=None):
    dates = x.index.get_level_values("Date")
    calendar = pd.DatetimeIndex(dates.unique().sort_values())
    predictions = {side: [] for side in bidirectional.SIDES}
    models = []
    for year in years:
        for side in bidirectional.SIDES:
            model, _ = _fit_candidate_before(x, target, calendar, f"{year}-01-01", side)
            selected = (dates.year == year) & bidirectional.event_mask(x, side).to_numpy()
            matrix = _candidate_matrix(x.loc[selected], side)
            values = event_models.predict_matrix(matrix, model)
            prediction = pd.Series(values, index=matrix.index, name=f"UP_PULLBACK_{side}", dtype="float64")
            predictions[side].append(prediction)
            models.append(model)
            if model_dir is not None:
                _write_json(Path(model_dir) / f"RIDGE_UP_PULLBACK_{side}_{year}.json", model)
    combined = {side: pd.concat(parts).sort_index() for side, parts in predictions.items()}
    if any(not series.index.is_unique for series in combined.values()):
        raise AssertionError("Candidate event prediction indexes overlap")
    if combined["high"].index.intersection(combined["low"].index).size:
        raise AssertionError("One row cannot be both a High and Low event")
    score = sn1_submission.candidate_scores_from_predictions(x, combined)["SIDE_SOURCE_SEPARATION"]
    return score.rename("Return"), models


def _mutate_future(inputs, target, cutoff):
    cutoff = pd.Timestamp(cutoff)
    mutated = {name: frame.copy(deep=True) for name, frame in inputs.items()}
    changed_target = target.copy(deep=True)
    changes = {}
    for name, frame in mutated.items():
        dates = frame.index.get_level_values("Date")
        future = dates > cutoff
        before = frame.copy(deep=True)
        if name in ("raw_return_1day", "beta_1day"):
            frame.loc[future, "Return"] = frame.loc[future, "Return"].fillna(0.0) * -11.0 + 3.0
        elif name == "topix_return_1day":
            future = frame.index > cutoff
            frame.loc[future, "Return"] = frame.loc[future, "Return"].fillna(0.0) * 7.0 - 1.0
        elif name == "prices_daily_quotes":
            columns = ["Open", "High", "Low", "Close"]
            frame.loc[future, columns] = frame.loc[future, columns] * 1.37 + 100.0
            frame.loc[future, "AdjustmentFactor"] = 0.25
        changes[name] = {
            "rows_after_cutoff": int(future.sum()),
            "changed_cells": int((before.loc[future] != frame.loc[future]).fillna(False).to_numpy().sum()),
        }
    label_future = changed_target.index.get_level_values("Date") > cutoff
    before_labels = changed_target.loc[label_future].copy()
    changed_target.loc[label_future] = 100.0 - changed_target.loc[label_future].fillna(0.0) * 17.0
    changes["target_1day_train"] = {
        "rows_after_cutoff": int(label_future.sum()),
        "changed_cells": int((before_labels != changed_target.loc[label_future]).fillna(False).sum()),
    }
    return mutated, changed_target, changes


def _prefix_invariance(inputs, target, original_x, baseline, candidate, cutoff):
    mutated_inputs, mutated_target, mutations = _mutate_future(inputs, target, cutoff)
    changed_x = event_features.build_features(mutated_inputs)
    if not changed_x.index.equals(original_x.index):
        raise AssertionError("Future mutation changed full feature index")
    dates = original_x.index.get_level_values("Date")
    prefix = dates <= pd.Timestamp(cutoff)
    prefix_index = original_x.index[prefix]
    pd.testing.assert_frame_equal(
        original_x.loc[prefix], changed_x.loc[prefix], check_exact=True,
        check_dtype=True,
    )
    changed_baseline_frame, _ = sn1_submission.predict_from_features(changed_x, mutated_target)
    changed_baseline = changed_baseline_frame["Return"].rename("Return")
    changed_candidate, _ = _predict_candidate(changed_x, mutated_target)
    _assert_series_exact(baseline.loc[prefix_index], changed_baseline.loc[prefix_index],
                         "baseline score prefix")
    _assert_series_exact(candidate.loc[prefix_index], changed_candidate.loc[prefix_index],
                         "candidate score prefix")
    if any(record["changed_cells"] <= 0 for record in mutations.values()):
        raise AssertionError("At least one future input source was not effectively mutated")
    return {
        "status": "PASS",
        "cutoff": pd.Timestamp(cutoff).date().isoformat(),
        "prefix_rows": int(prefix.sum()),
        "feature_columns": int(original_x.shape[1]),
        "future_mutation": {
            "raw_return_1day_train": "post-cutoff Return * -11 + 3",
            "beta_1day_train": "post-cutoff Return * -11 + 3",
            "topix_return_1day_train": "post-cutoff Return * 7 - 1",
            "prices_daily_quotes_train": "post-cutoff OHLC * 1.37 + 100; AdjustmentFactor = 0.25",
            "target_1day_train": "post-cutoff Return = 100 - 17 * Return",
        },
        "mutated_sources_and_rows": mutations,
        "feature_prefix_bitwise_equal": True,
        "baseline_score_prefix_bitwise_equal": True,
        "candidate_score_prefix_bitwise_equal": True,
        "baseline_prefix_rows": int(len(prefix_index)),
        "candidate_prefix_rows": int(len(prefix_index)),
    }


def _score_frame(score):
    result = score.rename("Return").to_frame()
    if not result.index.is_unique or not np.isfinite(result.to_numpy(dtype=float)).all():
        raise ValueError("Scores need unique rows and finite values")
    return result


def _portfolio_results(scores, target, metrics_dir):
    metrics_dir = Path(metrics_dir)
    metrics_dir.mkdir(parents=True, exist_ok=True)
    pooled_rows, year_rows, selected_accounts = [], [], {}
    full_accounts = {}
    for name, score in scores.items():
        account = evaluation.daily_account(score, target)
        full_accounts[name] = account
        selected = account.loc[account.index.year.isin(YEARS)].copy()
        selected_accounts[name] = selected
        pooled_rows.append({"strategy": name, **evaluation.metrics(selected),
                            "q5_q1_spread": float(selected.q5.mean() - selected.q1.mean())})
        selected.to_csv(metrics_dir / f"daily_account_{name}.csv", index_label="Date")
        for year in YEARS:
            annual = selected.loc[selected.index.year == year]
            year_rows.append({"strategy": name, "year": year,
                              "partial_year": bool(year == PARTIAL_YEAR),
                              **evaluation.metrics(annual),
                              "q5_q1_spread": float(annual.q5.mean() - annual.q1.mean())})
    pooled = pd.DataFrame(pooled_rows).set_index("strategy")
    annual = pd.DataFrame(year_rows)
    pooled.to_csv(metrics_dir / "pooled_metrics.csv", index_label="strategy")
    annual.to_csv(metrics_dir / "fold_year_metrics.csv", index=False)

    metric_names = [column for column in pooled.columns if pd.api.types.is_numeric_dtype(pooled[column])]
    delta_rows = []
    base = pooled.loc["SN1_H1"]
    cand = pooled.loc["UP_PULLBACK"]
    delta_rows.append({"period": "pooled_2011_2016",
                       **{f"delta_{metric}": float(cand[metric] - base[metric])
                          for metric in metric_names},
                       "delta_q5_q1_spread": float(cand.q5_q1_spread - base.q5_q1_spread)})
    annual_indexed = annual.set_index(["year", "strategy"])
    for year in YEARS:
        b = annual_indexed.loc[(year, "SN1_H1")]
        c = annual_indexed.loc[(year, "UP_PULLBACK")]
        delta_rows.append({"period": year,
                           **{f"delta_{metric}": float(c[metric] - b[metric])
                              for metric in metric_names if metric in c.index},
                           "delta_q5_q1_spread": float(c.q5_q1_spread - b.q5_q1_spread)})
    incremental = pd.DataFrame(delta_rows)
    incremental.to_csv(metrics_dir / "incremental_metrics.csv", index=False)

    complete_dates = selected_accounts["SN1_H1"].index.year != PARTIAL_YEAR
    complete = {}
    for name, account in selected_accounts.items():
        complete[name] = evaluation.metrics(account.loc[complete_dates])
        complete[name]["q5_q1_spread"] = float(
            account.loc[complete_dates, "q5"].mean() - account.loc[complete_dates, "q1"].mean()
        )
    partial = {
        "excluded_year": PARTIAL_YEAR,
        "excluded_sessions": int((selected_accounts["SN1_H1"].index.year == PARTIAL_YEAR).sum()),
        "complete_years": [year for year in YEARS if year != PARTIAL_YEAR],
        "baseline": complete["SN1_H1"],
        "candidate": complete["UP_PULLBACK"],
        "deltas": {
            "rankic": float(complete["UP_PULLBACK"]["rankic"] - complete["SN1_H1"]["rankic"]),
            "annual_gross": float(complete["UP_PULLBACK"]["annual_gross"] - complete["SN1_H1"]["annual_gross"]),
            "q5_q1_spread": float(complete["UP_PULLBACK"]["q5_q1_spread"] - complete["SN1_H1"]["q5_q1_spread"]),
            "annual_net": float(complete["UP_PULLBACK"]["annual_net"] - complete["SN1_H1"]["annual_net"]),
        },
    }
    _write_json(metrics_dir / "partial_year_sensitivity.json", partial)
    return pooled, annual, incremental, selected_accounts, partial


def _position_label(quintile):
    if quintile <= 1:
        return "Short"
    if quintile == 2:
        return "Neutral"
    return "Long"


def _attribution(x, target, scores, accounts, metrics_dir):
    metrics_dir = Path(metrics_dir)
    index = target.index
    years = index.get_level_values("Date").year
    eval_rows = np.isin(years, YEARS) & target.notna().to_numpy()
    up = x["event_upstate"].eq(1.0)
    down_box = x["event_box_position"].lt(0.0)
    nonnegative_box = x["event_box_position"].ge(0.0)
    groups = {
        "UPSTATE=1,x<0": up & down_box,
        "UPSTATE=1,x>=0": up & nonnegative_box,
        "UPSTATE=0,x<0": x["event_upstate"].eq(0.0) & down_box,
    }
    groups["Other"] = ~(groups["UPSTATE=1,x<0"] | groups["UPSTATE=1,x>=0"] |
                         groups["UPSTATE=0,x<0"])
    centered_rank = bidirectional.centered_target_rank(target)
    weight_base, q_base = evaluation.weights(scores["SN1_H1"])
    weight_cand, q_cand = evaluation.weights(scores["UP_PULLBACK"])
    if not weight_base.index.equals(index) or not weight_cand.index.equals(index):
        raise AssertionError("Official quintile weight indexes differ from Train target")
    eval_dates = accounts["SN1_H1"].index
    delta_row_pnl = ((weight_cand - weight_base) * target).where(target.notna(), 0.0)
    attribution_rows, q_migration, side_migration = [], [], []
    q_base_values = q_base.to_numpy(dtype=int)
    q_cand_values = q_cand.to_numpy(dtype=int)
    side_base = np.array([_position_label(q) for q in q_base_values], dtype=object)
    side_cand = np.array([_position_label(q) for q in q_cand_values], dtype=object)
    for name, mask_series in groups.items():
        mask = mask_series.to_numpy() & eval_rows
        selected_index = index[mask]
        ranks = centered_rank.loc[selected_index]
        bucket_return = target.loc[selected_index]
        bucket_dates = selected_index.get_level_values("Date")
        daily_rank = ranks.groupby(level="Date").mean()
        daily_return = bucket_return.groupby(level="Date").mean()
        base_q = q_base_values[mask]
        cand_q = q_cand_values[mask]
        q_entry = int(((base_q < 3) & (cand_q >= 3)).sum())
        q_exit = int(((base_q >= 3) & (cand_q < 3)).sum())
        daily_pnl = delta_row_pnl.loc[selected_index].groupby(level="Date").sum().reindex(eval_dates, fill_value=0.0)
        changes = scores["UP_PULLBACK"].loc[selected_index] - scores["SN1_H1"].loc[selected_index]
        attribution_rows.append({
            "group": name,
            "rows": int(mask.sum()),
            "dates": int(bucket_dates.nunique()),
            "mean_centered_target_rank_daily_equal_weight": float(daily_rank.mean()) if len(daily_rank) else np.nan,
            "mean_centered_target_rank_row_weighted": float(ranks.mean()) if len(ranks) else np.nan,
            "mean_residual_return_daily_equal_weight": float(daily_return.mean()) if len(daily_return) else np.nan,
            "mean_residual_return_row_weighted": float(bucket_return.mean()) if len(bucket_return) else np.nan,
            "mean_baseline_score": float(scores["SN1_H1"].loc[selected_index].mean()) if len(selected_index) else np.nan,
            "mean_candidate_score": float(scores["UP_PULLBACK"].loc[selected_index].mean()) if len(selected_index) else np.nan,
            "mean_score_change": float(changes.mean()) if len(changes) else np.nan,
            "median_score_change": float(changes.median()) if len(changes) else np.nan,
            "baseline_q4_q5_rows": int((base_q >= 3).sum()),
            "candidate_q4_q5_rows": int((cand_q >= 3).sum()),
            "net_q4_q5_migration_rows": int((cand_q >= 3).sum() - (base_q >= 3).sum()),
            "entered_q4_q5_rows": q_entry,
            "exited_q4_q5_rows": q_exit,
            "long_entered_rows": int(((side_base[mask] != "Long") & (side_cand[mask] == "Long")).sum()),
            "long_exited_rows": int(((side_base[mask] == "Long") & (side_cand[mask] != "Long")).sum()),
            "short_entered_rows": int(((side_base[mask] != "Short") & (side_cand[mask] == "Short")).sum()),
            "short_exited_rows": int(((side_base[mask] == "Short") & (side_cand[mask] != "Short")).sum()),
            "gross_contribution_change_period": float(daily_pnl.sum()),
            "gross_contribution_change_annualized": float(daily_pnl.mean() * 252),
        })
        bucket_q = pd.DataFrame({"baseline_q": base_q, "candidate_q": cand_q})
        q_table = bucket_q.value_counts(sort=False).rename("rows").reset_index()
        for row in q_table.to_dict("records"):
            q_migration.append({"group": name, **row,
                                "share_within_group": float(row["rows"] / max(len(bucket_q), 1))})
        bucket_side = pd.DataFrame({"baseline_side": side_base[mask], "candidate_side": side_cand[mask]})
        side_table = bucket_side.value_counts(sort=False).rename("rows").reset_index()
        for row in side_table.to_dict("records"):
            side_migration.append({"group": name, **row,
                                   "share_within_group": float(row["rows"] / max(len(bucket_side), 1))})
    buckets = pd.DataFrame(attribution_rows)
    buckets.to_csv(metrics_dir / "attribution_table.csv", index=False)
    pd.DataFrame(q_migration).to_csv(metrics_dir / "quintile_migration.csv", index=False)
    pd.DataFrame(side_migration).to_csv(metrics_dir / "long_neutral_short_migration.csv", index=False)
    return buckets


def _decision(pooled, partial, attribution):
    base = pooled.loc["SN1_H1"]
    candidate = pooled.loc["UP_PULLBACK"]
    gates = {
        "positive_mean_rankic_delta": bool(candidate.rankic - base.rankic > 0.0),
        "positive_annual_gross_return_delta": bool(candidate.annual_gross - base.annual_gross > 0.0),
        "positive_q5_q1_delta": bool(candidate.q5_q1_spread - base.q5_q1_spread > 0.0),
    }
    primary_pass = all(gates.values())
    sensitivity = {
        "positive_rankic_delta_without_2016": partial["deltas"]["rankic"] > 0,
        "positive_gross_delta_without_2016": partial["deltas"]["annual_gross"] > 0,
        "positive_q5_q1_delta_without_2016": partial["deltas"]["q5_q1_spread"] > 0,
    }
    group = attribution.set_index("group").loc["UPSTATE=1,x<0"]
    attribution_checks = {
        "mean_score_change_positive": bool(group.mean_score_change > 0),
        "net_migration_into_q4_q5_positive": bool(group.net_q4_q5_migration_rows > 0),
        "gross_contribution_change_positive": bool(group.gross_contribution_change_annualized > 0),
    }
    d_long = float(candidate.annual_long - base.annual_long)
    d_short = float(candidate.annual_short - base.annual_short)
    short_offset_ratio = (max(0.0, -d_short) / d_long) if d_long > 0 else None
    net_delta = float(candidate.annual_net - base.annual_net)
    cost_delta = float(candidate.annual_cost_all - base.annual_cost_all)
    secondary = {
        "positive_complete_year_sensitivity": bool(all(sensitivity.values())),
        "positive_net_annual_return_delta": bool(net_delta > 0),
        "not_cost_only": bool((candidate.annual_gross - base.annual_gross) > 0 and net_delta > 0),
        "pullback_bucket_direction_checks_passed": int(sum(attribution_checks.values())) >= 2,
    }
    if not primary_pass:
        status = "REJECT"
    elif all(secondary.values()):
        status = "SUPPORT"
    else:
        status = "MIXED"
    return {
        "decision": status,
        "primary_gates": gates,
        "primary_pass": primary_pass,
        "complete_year_sensitivity": sensitivity,
        "secondary_checks": secondary,
        "up_pullback_attribution_checks": attribution_checks,
        "delta_annual_long": d_long,
        "delta_annual_short": d_short,
        "short_deterioration_to_long_improvement_ratio": short_offset_ratio,
        "delta_annual_net": net_delta,
        "delta_annual_cost_all": cost_delta,
        "pooled_delta_rankic": float(candidate.rankic - base.rankic),
        "pooled_delta_annual_gross": float(candidate.annual_gross - base.annual_gross),
        "pooled_delta_q5_q1_spread": float(candidate.q5_q1_spread - base.q5_q1_spread),
    }


def _write_report(output_dir, pooled, annual, incremental, partial, attribution, decision,
                  run_json, audit):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_link = Path(os.path.relpath(Path(run_json).resolve().parent,
                                         output_dir.resolve())).as_posix()
    base = pooled.loc["SN1_H1"]
    candidate = pooled.loc["UP_PULLBACK"]
    report = [
        "# DM-20261001-01: UP_PULLBACK added to SN1_H1",
        "",
        f"**Baseline:** current `SN1_H1` (five Ridge inputs).  ",
        f"**Candidate:** `SN1_H1 + UP_PULLBACK` (sixth and only added input).  ",
        f"**Decision:** **{decision['decision']}**.  ",
        f"**Primary gates:** Mean RankIC Δ {decision['pooled_delta_rankic']:+.7f} "
        f"({'PASS' if decision['primary_gates']['positive_mean_rankic_delta'] else 'FAIL'}); "
        f"gross annual Δ {decision['pooled_delta_annual_gross']*10000:+.3f} bp/year "
        f"({'PASS' if decision['primary_gates']['positive_annual_gross_return_delta'] else 'FAIL'}); "
        f"Q5−Q1 Δ {decision['pooled_delta_q5_q1_spread']*10000:+.5f} bp/day "
        f"({'PASS' if decision['primary_gates']['positive_q5_q1_delta'] else 'FAIL'}).",
        "**Limitation:** all 2011–2016 Train dates and the motivating attribution bucket were already inspected; this is development-history evidence, not independent OOS evidence.",
        "",
        "## Pooled results, 2011–2016",
        "",
        "Annual return/cost values are annualized from daily means. Q5−Q1 is a daily residual-return spread. RankIC t-stat uses repository HAC-5. Cost_all charges 10 bp on all turnover; `net` follows the official evaluator expression and `net_all_cost` is the all-position cost diagnostic.",
        "",
        "| Metric | Baseline | Candidate | Delta |",
        "|---|---:|---:|---:|",
    ]
    show = [
        ("Gross Sharpe", "gross_sharpe"), ("Net Sharpe", "net_sharpe"),
        ("Mean RankIC", "rankic"), ("RankIC HAC-5 t-stat", "rankic_t_hac5"),
        ("RankIC hit ratio", "rankic_hit"), ("Annualized gross return (%)", "annual_gross"),
        ("Annualized net return (%)", "annual_net"), ("Annualized cost, all turnover (%)", "annual_cost_all"),
        ("Average daily turnover", "turnover"), ("Maximum drawdown (compound, net, %)", "max_drawdown_compound"),
        ("Annualized Long contribution (%)", "annual_long"), ("Annualized Short contribution (%)", "annual_short"),
        ("Quintile monotonicity", "q_monotonicity"), ("Q5−Q1 (bp/day)", "q5_q1_spread"),
    ]
    for label, key in show:
        b, c = float(base[key]), float(candidate[key])
        if key in {"annual_gross", "annual_net", "annual_cost_all", "max_drawdown_compound",
                   "annual_long", "annual_short"}:
            b, c = b * 100.0, c * 100.0
            unit = "%"
        elif key == "q5_q1_spread":
            b, c = b * 10000.0, c * 10000.0
            unit = " bp/day"
        else:
            unit = ""
        report.append(f"| {label} | {b:.8g}{unit} | {c:.8g}{unit} | {c-b:+.8g}{unit} |")
    report.extend([
        "",
        "## Fold and year deltas",
        "",
        "Each annual return is that fold's daily mean × 252; 2016 covers 61 sessions and is partial. The separate sensitivity below pools only complete years 2011–2015.",
        "",
        "| Year | Sessions | Gross return Δ | Net return Δ | RankIC Δ | Q5−Q1 Δ (bp/day) | Long Δ | Short Δ |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    year_delta = incremental.set_index("period")
    for year in YEARS:
        b_row = annual[(annual.year == year) & (annual.strategy == "SN1_H1")].iloc[0]
        d = year_delta.loc[year]
        report.append(
            f"| {year}{' *' if year == PARTIAL_YEAR else ''} | {int(b_row.days)} | "
            f"{d['delta_annual_gross']*10000:+.3f} bp/year | {d['delta_annual_net']*10000:+.3f} bp/year | "
            f"{d['delta_rankic']:+.7f} | {d['delta_q5_q1_spread']*10000:+.4f} | "
            f"{d['delta_annual_long']*10000:+.3f} bp/year | {d['delta_annual_short']*10000:+.3f} bp/year |"
        )
    report.extend([
        "",
        "### Partial-year sensitivity",
        "",
        f"2016 contributed {partial['excluded_sessions']} sessions. Excluding it, the deltas are Mean RankIC **{partial['deltas']['rankic']:+.7f}**, annualized gross **{partial['deltas']['annual_gross']*10000:+.3f} bp/year**, Q5−Q1 **{partial['deltas']['q5_q1_spread']*10000:+.4f} bp/day**, and annualized net **{partial['deltas']['annual_net']*10000:+.3f} bp/year**.",
        "",
        "## UP_PULLBACK attribution",
        "",
        "Buckets are assigned from the existing as-of `event_upstate` and `event_box_position`; undefined Box positions fall into Other. Returns use official Train residual target. Portfolio migration uses the official five-quintile weights.",
        "",
        "| Bucket | Rows | Dates | Mean centered target rank | Mean residual return | Mean score Δ | Net Q4/Q5 migration | Annual gross contribution Δ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for _, row in attribution.iterrows():
        report.append(
            f"| {row.group} | {int(row.rows)} | {int(row.dates)} | "
            f"{row.mean_centered_target_rank_daily_equal_weight:+.6f} | "
            f"{row.mean_residual_return_daily_equal_weight*10000:+.4f} bp | "
            f"{row.mean_score_change:+.7g} | {int(row.net_q4_q5_migration_rows):+d} | "
            f"{row.gross_contribution_change_annualized*10000:+.3f} bp/year |"
        )
    up = attribution.set_index("group").loc["UPSTATE=1,x<0"]
    report.extend([
        "",
        f"For `UPSTATE=1, x<0`, baseline Q4/Q5 rows were {int(up.baseline_q4_q5_rows)} and candidate rows {int(up.candidate_q4_q5_rows)}; it entered Q4/Q5 on {int(up.entered_q4_q5_rows)} rows and exited on {int(up.exited_q4_q5_rows)} rows. The Long contribution delta is {decision['delta_annual_long']*10000:+.3f} bp/year; the Short contribution delta is {decision['delta_annual_short']*10000:+.3f} bp/year; short deterioration / positive long improvement is {decision['short_deterioration_to_long_improvement_ratio']!s}.",
        "",
        f"Full quintile/side transition tables are in [`quintile_migration.csv`]({artifact_link}/metrics/quintile_migration.csv) and [`long_neutral_short_migration.csv`]({artifact_link}/metrics/long_neutral_short_migration.csv); full bucket values are in [`attribution_table.csv`]({artifact_link}/metrics/attribution_table.csv).",
        f"Pooled/year/incremental metrics and [daily accounts]({artifact_link}/metrics/) are stored with the run artifacts.",
        "",
        "## Decision checks and audit",
        "",
        f"- Candidate decision: **{decision['decision']}**. Primary gate details: `{json.dumps(decision['primary_gates'], ensure_ascii=False)}`.",
        f"- Complete-year sensitivity 2011–2015: `{json.dumps(decision['complete_year_sensitivity'], ensure_ascii=False)}`.",
        f"- UP_PULLBACK attribution direction checks: `{json.dumps(decision['up_pullback_attribution_checks'], ensure_ascii=False)}`.",
        f"- Baseline reproduction: **{audit['baseline_reproduction']}**. Feature formula/source scan: **{audit['feature_causality']}**. Feature/baseline/candidate future-mutation prefix checks: **{audit['prefix_invariance']}**.",
        f"- Prediction coverage, index alignment, finite scores, and deterministic replay: **{audit['coverage_determinism']}**. Train firewall: **{audit['firewall']}**.",
        f"- Run: [`run.json`]({artifact_link}/run.json); predictions, models, audits, metrics, and daily accounts are in the same artifact folder.",
        "- Valid was not opened. The Train target used was only `target_1day_train.parquet`; raw target was not opened.",
        "",
        "## Scope",
        "",
        "A SUPPORT result would support only this fixed `UP_PULLBACK` column appended to SN1_H1. It would not show that Box Mean Reversion, Event Box generally, pullbacks generally, or trend following generally are effective. A REJECT applies only to this fixed feature/model addition.",
    ])
    (output_dir / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def run(data_dir, output_dir, run_json):
    started = time.time()
    data_dir, output_dir, run_json = Path(data_dir), Path(output_dir), Path(run_json)
    output_dir.mkdir(parents=True, exist_ok=True)
    _update_run(run_json, {"status": "running", "started_at_utc": datetime.now(timezone.utc).isoformat(),
                           "actual_trials": [], "max_trials": 1, "valid_evaluation": False})
    try:
        scan = _source_scan()
        _write_json(output_dir / "audit/source_scan.json", scan)
        if scan["status"] != "PASS":
            raise AssertionError(f"Source/leak scan failed with {len(scan['findings'])} finding(s)")
        train_paths = sorted(data_dir.glob("*_train.parquet"))
        actual_names = {path.name for path in train_paths}
        if actual_names != EXPECTED_INPUTS:
            raise ValueError(f"Train stage inputs mismatch: {sorted(actual_names)}")
        input_hashes = {path.name: _sha256(path) for path in train_paths}
        source_hashes = {relative: _sha256(ROOT / relative) for relative in SOURCE_PATHS}
        _update_run(run_json, {
            "command": "python -m research.experiments.up_pullback_sn1 --data-dir "
                       f"{data_dir} --output-dir {output_dir} --run-json {run_json}",
            "deadline_seconds": 1800,
            "code_sha256": source_hashes["research/experiments/up_pullback_sn1.py"],
            "source_sha256": source_hashes,
            "train_data_sha256": input_hashes,
            "environment": {
                "python": sys.version,
                "platform": platform.platform(),
                "numpy": np.__version__,
                "pandas": pd.__version__,
                "pyarrow": pyarrow.__version__,
                "scipy": scipy.__version__,
            },
        })
        firewall.install(allowed_artifacts=[BASELINE_REFERENCE])

        inputs = event_features.load_inputs(data_dir, split="train")
        target = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index()
        x = event_features.build_features(inputs)
        if not x.index.equals(target.index):
            raise ValueError("Train feature and target indexes differ")
        if not x.index.is_unique:
            raise ValueError("Train feature index contains duplicates")
        feature_audit = _feature_contract(x)
        _write_json(output_dir / "audit/feature_causality.json", {
            **feature_audit,
            "source_scan_status": scan["status"],
            "input_sources": sorted(actual_names),
            "price_levels": "raw Open/High/Low/Close with existing split-safe share-unit conversion; no adjustment OHLCV levels",
            "atr": "existing prior-only ATR; no same-day/future ATR",
            "asof_cutoff": "signal date t; existing confirmed_at state; no t+1 inputs",
            "treatment_of_missing_x": "existing pullback_up is missing outside a valid BOX; the Ridge follows existing deterministic train-mean imputation",
        })

        # The baseline gate is deliberately before any UP_PULLBACK fit.
        baseline_frame, baseline_records = sn1_submission.predict_from_features(x, target)
        baseline = baseline_frame["Return"].rename("Return")
        if not baseline.index.equals(target.index) or not np.isfinite(baseline.to_numpy()).all():
            raise AssertionError("Current SN1_H1 baseline coverage or finiteness failed")
        independent_predictions, independent_records = bidirectional.walk_forward_predictions(x, target)
        independent = sn1_submission.candidate_scores_from_predictions(
            x, independent_predictions
        )["SIDE_SOURCE_SEPARATION"].rename("Return")
        _assert_series_exact(baseline, independent, "current SN1_H1 baseline reproduction")
        if not BASELINE_REFERENCE.is_file():
            raise FileNotFoundError(f"Required previous current-baseline reference missing: {BASELINE_REFERENCE}")
        saved_baseline = pd.read_parquet(BASELINE_REFERENCE)["Return"].sort_index().rename("Return")
        _assert_series_exact(baseline, saved_baseline, "saved DM-20260930-02 SN1_H1 reference")
        baseline_audit = {
            "status": "PASS",
            "current_route": "dm_variable_box_breakout.submission.predict_from_features",
            "independent_route": "bidirectional.walk_forward_predictions + candidate_scores_from_predictions",
            "saved_reference": str(BASELINE_REFERENCE.relative_to(ROOT)),
            "current_vs_independent_rows": int(len(baseline)),
            "current_vs_independent_max_abs_error": 0.0,
            "current_vs_independent_bitwise_equal": True,
            "current_vs_saved_rows": int(len(baseline)),
            "current_vs_saved_max_abs_error": 0.0,
            "current_vs_saved_bitwise_equal": True,
            "candidate_fitted_at_reproduction_check": False,
        }
        _write_json(output_dir / "audit/baseline_reproduction.json", baseline_audit)
        baseline_path = output_dir / "predictions/SN1_H1.parquet"
        _score_frame(baseline).to_parquet(baseline_path)

        cutoff = "2014-06-30"
        # Feature and baseline prefixes are checked before candidate fitting.
        mutated_inputs, mutated_target, mutations = _mutate_future(inputs, target, cutoff)
        mutated_x = event_features.build_features(mutated_inputs)
        dates = x.index.get_level_values("Date")
        prefix = dates <= pd.Timestamp(cutoff)
        prefix_index = x.index[prefix]
        pd.testing.assert_frame_equal(x.loc[prefix], mutated_x.loc[prefix],
                                      check_exact=True, check_dtype=True)
        changed_baseline_frame, _ = sn1_submission.predict_from_features(mutated_x, mutated_target)
        changed_baseline = changed_baseline_frame["Return"].rename("Return")
        _assert_series_exact(baseline.loc[prefix_index], changed_baseline.loc[prefix_index],
                             "baseline prefix after future mutation")
        if any(item["changed_cells"] <= 0 for item in mutations.values()):
            raise AssertionError("Future mutation did not alter every registered input source")

        candidate, candidate_models = _predict_candidate(
            x, target, model_dir=output_dir / "models"
        )
        replay, replay_models = _predict_candidate(x, target)
        _assert_series_exact(candidate, replay, "deterministic UP_PULLBACK replay")
        if json.dumps(candidate_models, sort_keys=True, allow_nan=False) != json.dumps(
                replay_models, sort_keys=True, allow_nan=False):
            raise AssertionError("UP_PULLBACK model parameters changed on deterministic replay")
        if not candidate.index.equals(target.index) or not np.isfinite(candidate.to_numpy()).all():
            raise AssertionError("UP_PULLBACK prediction coverage or finite-score check failed")
        changed_candidate, _ = _predict_candidate(mutated_x, mutated_target)
        _assert_series_exact(candidate.loc[prefix_index], changed_candidate.loc[prefix_index],
                             "candidate prefix after future mutation")
        prefix_audit = {
            "status": "PASS",
            "cutoff": cutoff,
            "prefix_rows": int(prefix.sum()),
            "feature_columns": int(x.shape[1]),
            "mutations": mutations,
            "feature_prefix_bitwise_equal": True,
            "baseline_score_prefix_bitwise_equal": True,
            "candidate_score_prefix_bitwise_equal": True,
            "all_sources_changed_after_cutoff": True,
        }
        _write_json(output_dir / "audit/prefix_invariance.json", prefix_audit)
        model_audit = [{
            "side": model["side"], "year": model["year"],
            "training_rows": model["training_rows"],
            "training_dates": model["training_dates"],
            "min_training_signal": model["min_training_signal"],
            "max_training_signal": model["max_training_signal"],
            "max_label_maturity_date": model["max_label_maturity_date"],
            "columns": model["columns"],
            "lambda": model["ridge_lambda"],
        } for model in candidate_models]
        if any(record["columns"] != list(RIDGE_COLUMNS) for record in model_audit):
            raise AssertionError("Candidate model did not have exactly one added feature")
        _write_json(output_dir / "audit/fold_maturity_and_candidate_model.json", {
            "status": "PASS", "purge_positions": PURGE_POSITIONS,
            "all_max_label_maturity_dates_precede_fold": True,
            "candidate_models": model_audit,
            "registered_candidate_trials": 1,
            "candidate_training_passes": 3,
            "models_per_pass": 12,
            "deterministic_replay_exact": True,
        })

        scores = {"SN1_H1": baseline, "UP_PULLBACK": candidate}
        for name, score in scores.items():
            if not score.index.equals(target.index) or not score.index.is_unique:
                raise AssertionError(f"{name} index alignment failed")
            if not np.isfinite(score.to_numpy(dtype=float)).all():
                raise AssertionError(f"{name} has nonfinite prediction values")
            _score_frame(score).to_parquet(output_dir / f"predictions/{name}.parquet")
        pooled, annual, incremental, accounts, partial = _portfolio_results(
            scores, target, output_dir / "metrics"
        )
        attribution = _attribution(x, target, scores, accounts, output_dir / "metrics")
        decision = _decision(pooled, partial, attribution)
        _write_json(output_dir / "metrics/decision_gates.json", decision)

        coverage = {
            "status": "PASS",
            "input_rows": int(len(x)),
            "target_nonnull_rows": int(target.notna().sum()),
            "target_coverage": float(target.notna().mean()),
            "prediction_rows": {name: int(len(score)) for name, score in scores.items()},
            "index_exact": {name: bool(score.index.equals(target.index)) for name, score in scores.items()},
            "unique_index": {name: bool(score.index.is_unique) for name, score in scores.items()},
            "all_scores_finite": {name: bool(np.isfinite(score.to_numpy()).all()) for name, score in scores.items()},
            "deterministic_candidate_replay": True,
            "candidate_score_replay_max_abs_error": 0.0,
            "candidate_model_replay_exact": True,
            "valid_evaluation": False,
            "raw_target_accessed": False,
        }
        _write_json(output_dir / "audit/coverage_determinism.json", coverage)
        firewall.save(output_dir / "audit/firewall.json")
        firewall_record = json.loads((output_dir / "audit/firewall.json").read_text(encoding="utf-8"))
        firewall_status = "PASS" if set(firewall_record["opened_parquets"]) == {
            str((data_dir / name).resolve()) for name in EXPECTED_INPUTS
        } and not firewall_record["valid_evaluation"] and not firewall_record["raw_target_reads"] else "FAIL"
        if firewall_status != "PASS":
            raise AssertionError(f"Unexpected Train firewall reads: {firewall_record}")
        audit = {
            "baseline_reproduction": "PASS",
            "feature_causality": "PASS",
            "prefix_invariance": "PASS",
            "coverage_determinism": "PASS",
            "firewall": firewall_status,
        }
        _write_report(ROOT / "reports" / EXPERIMENT_ID, pooled, annual, incremental, partial,
                      attribution, decision, run_json, audit)
        _write_json(output_dir / "audit/final_audit.json", audit)
        _update_run(run_json, {
            "status": "completed",
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(time.time() - started, 3),
            "command": " ".join(sys.argv),
            "deadline_seconds": 1800,
            "actual_trials": ["UP_PULLBACK_SN1_H1"],
            "max_trials": 1,
            "random_seed": 20261001,
            "train_data_sha256": input_hashes,
            "source_sha256": source_hashes,
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "pyarrow": pyarrow.__version__,
            "scipy": scipy.__version__,
            "baseline_reproduction": baseline_audit,
            "candidate_decision": decision,
            "prefix_invariance": prefix_audit,
            "opened_parquets": firewall_record["opened_parquets"],
            "valid_evaluation": False,
            "raw_target_accessed": False,
        })
        return decision
    except BaseException as error:
        try:
            firewall.save(output_dir / "audit/firewall.json")
        except Exception:
            pass
        _update_run(run_json, {
            "status": "failed",
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(time.time() - started, 3),
            "command": " ".join(sys.argv),
            "deadline_seconds": 1800,
            "error": f"{type(error).__name__}: {error}",
            "actual_trials": (["UP_PULLBACK_SN1_H1"]
                              if list((output_dir / "models").glob("RIDGE_UP_PULLBACK_*.json")) else []),
            "max_trials": 1,
            "candidate_evaluated": (output_dir / "predictions/UP_PULLBACK.parquet").exists(),
            "valid_evaluation": False,
        })
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-json", required=True)
    args = parser.parse_args()
    decision = run(args.data_dir, args.output_dir, args.run_json)
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
