"""Fixed Train-only portfolio audit and BOX holding/gate diagnostics.

The current BOX and B00 signals are replayed from saved artifacts. Candidate A
changes only the two saved raw-score streams' carry rule. Candidate B uses the
existing causal feature builder and Ridge helpers with an eligibility mask.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from research import evaluation, firewall
from research.experiments.slope_range_volume_ml import dump
from stock_comp_2026.strategies.dm_variable_box_breakout import bidirectional, features
from stock_comp_2026.strategies.dm_variable_box_breakout import models as b00_models


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DM-20260926-01"
SOURCE_EXPERIMENT_ID = "DM-20260925-03"
SOURCE_RUN_ID = "run-20260926T063602Z"
ALPHA = 0.25
RIDGE_LAMBDA = 1.0
ONE_WAY_COST = 0.001
ANNUALIZATION = 252
YEARS = tuple(range(2011, 2017))
BOOTSTRAP_SEED = 20260925
BOOTSTRAP_REPS = 1000
BOOTSTRAP_BLOCK = 20
PREFIX_CUTOFFS = ("2011-12-30", "2012-06-29", "2014-12-30")
SOURCE_RUN = ROOT / "artifacts" / SOURCE_EXPERIMENT_ID / SOURCE_RUN_ID
SOURCE_SIGNALS = SOURCE_RUN / "predictions" / "signals.parquet"
SOURCE_EVENTS = SOURCE_RUN / "predictions" / "event_predictions.parquet"
SOURCE_BOX = SOURCE_RUN / "predictions" / "box_features.parquet"
CATEGORIES = (
    "high_event_day", "high_age_1_4", "high_age_5_plus",
    "low_event_day", "low_age_1_4", "low_age_5_plus",
    "score_zero_tail_tie_break", "score_zero_non_tail_tie_break", "other",
)
AGE_CATEGORIES = CATEGORIES[:6]
TRIAL_IDS = (
    "B00_BASE", "BOX_ORIGINAL", "A_LOW_NO_CARRY", "A_B00_LOW_NO_CARRY",
    "A_BOX_SHORT_GAMMA_050", "A_BOX_SHORT_GAMMA_025", "A_BOX_SHORT_GAMMA_000",
    "A_B00_SHORT_GAMMA_050", "A_B00_SHORT_GAMMA_025", "A_B00_SHORT_GAMMA_000",
    "B_BOX_GATE_B00_SCORE", "B_BOX_GATE_RIDGE",
)
GAMMAS = (1.0, 0.5, 0.25, 0.0)


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def grouped_sum(values):
    return values.groupby(level="Date").sum()


def segment_ewma(values, alpha=ALPHA):
    groups = features.segment_keys(values.index)
    return values.groupby(groups, sort=False).transform(
        lambda block: block.ewm(alpha=alpha, adjust=False).mean()
    ).rename(values.name)


def inverse_ewma(score, alpha=ALPHA):
    """Invert the known EWMA recurrence; clamp only floating-point zero noise."""
    groups = features.segment_keys(score.index)
    previous = score.groupby(groups, sort=False).shift(1)
    first = score.groupby(groups, sort=False).cumcount().eq(0)
    raw = ((score - (1.0 - alpha) * previous) / alpha).where(~first, score)
    raw = raw.where(raw.abs() >= 1e-12, 0.0).rename(f"{score.name}_raw")
    rebuilt = segment_ewma(raw, alpha=alpha)
    max_error = float((rebuilt - score).abs().max())
    if not np.isfinite(max_error) or max_error > 2e-12:
        raise AssertionError(f"EWMA inversion failed to reproduce saved score: {max_error}")
    return raw, max_error


def split_raw_sides(raw):
    """The saved event stream has disjoint positive High / negative Low rows."""
    high = raw.clip(lower=0.0).rename("high_raw")
    low = raw.clip(upper=0.0).rename("low_raw")
    if (high.ne(0.0) & low.ne(0.0)).any():
        raise AssertionError("High and Low raw streams overlap")
    return high, low


def asymmetric_score_from_raw(raw, alpha=ALPHA, name="A_LOW_NO_CARRY"):
    """Keep High EWMA and the EWMA-scaled Low event-day score only."""
    high_raw, low_raw = split_raw_sides(raw)
    groups = features.segment_keys(raw.index)
    first = raw.groupby(groups, sort=False).cumcount().eq(0)
    low_event_score = (alpha * low_raw).where(~first, low_raw)
    result = segment_ewma(high_raw, alpha=alpha) + low_event_score
    return result.rename(name)


def event_age_components(high_raw, low_raw, alpha=ALPHA):
    """Return additive, signed event-origin score components at each stock-day."""
    groups = features.segment_keys(high_raw.index)
    result = {}
    for side, raw in (("high", high_raw), ("low", low_raw)):
        total = segment_ewma(raw, alpha=alpha)
        first = raw.groupby(groups, sort=False).cumcount().eq(0)
        event_day = (alpha * raw).where(~first, raw).rename(f"{side}_event_day")
        age_1_4 = pd.Series(0.0, index=raw.index)
        for age in range(1, 5):
            lagged = raw.groupby(groups, sort=False).shift(age).fillna(0.0)
            age_1_4 = age_1_4 + alpha * (1.0 - alpha) ** age * lagged
        age_1_4 = age_1_4.rename(f"{side}_age_1_4")
        age_5 = (total - event_day - age_1_4).rename(f"{side}_age_5_plus")
        result[f"{side}_event_day"] = event_day
        result[f"{side}_age_1_4"] = age_1_4
        result[f"{side}_age_5_plus"] = age_5
    frame = pd.DataFrame(result, index=high_raw.index)
    return frame


def component_fractions(score, components, q):
    """Allocate a held score's weight across event-origin components by |score|."""
    raw_components = components.reindex(score.index).loc[:, list(AGE_CATEGORIES)]
    absolute = raw_components.abs()
    denominator = absolute.sum(axis=1)
    fractions = absolute.div(denominator.replace(0.0, np.nan), axis=0).fillna(0.0)
    zero = score.eq(0.0)
    tail_zero = zero & q.isin([0, 4])
    other = (~zero) & denominator.eq(0.0)
    fractions.loc[zero, :] = 0.0
    fractions.loc[other, :] = 0.0
    fractions["score_zero_tail_tie_break"] = tail_zero.astype(float)
    fractions["score_zero_non_tail_tie_break"] = (zero & ~tail_zero).astype(float)
    fractions["other"] = other.astype(float)
    if not np.allclose(fractions.sum(axis=1).to_numpy(), 1.0, rtol=0.0, atol=1e-12):
        raise AssertionError("Source attribution fractions must sum to one")
    return fractions.loc[:, list(CATEGORIES)]


def eligible_box_mask(x):
    width = pd.to_numeric(x["box_width_atr"], errors="coerce")
    return (
        x["box_duration"].gt(0.0)
        & width.notna()
        & np.isfinite(width)
        & width.lt(3.0)
    ).rename("eligible_box")


def zero_code_order_metrics(score, q):
    """Average within-date code-order/quintile rank relation among zero scores."""
    zeros = score.eq(0.0)
    positions = pd.DataFrame({"q": q.loc[zeros]}, index=q.index[zeros]).sort_index()
    positions["code_order"] = positions.groupby(level="Date", sort=False).cumcount()
    daily_rhos = []
    for _, part in positions.groupby(level="Date", sort=False):
        if len(part) >= 3 and part.q.nunique() > 1:
            from scipy.stats import spearmanr
            daily_rhos.append(float(spearmanr(part.code_order, part.q).statistic))
    return {
        "zero_code_order_spearman_q": float(np.mean(daily_rhos)) if daily_rhos else np.nan,
        "zero_code_order_spanning_days": int(len(daily_rhos)),
    }


def quintile_weights(signal):
    """Mirror evaluate_script: sort index, rank(method=first), then qcut into 5."""
    ordered = signal.sort_index().fillna(0.0)
    rank = ordered.groupby(level="Date").rank(method="first")
    n = rank.groupby(level="Date").transform("count")
    q = rank.groupby(level="Date").transform(
        lambda values: pd.qcut(values, 5, labels=False)
    ).astype("int8")
    if (n < 5).any():
        raise ValueError("The official five-quintile portfolio needs at least five names/day")
    weights = ((q.astype(float) - 2.0) / n / 1.2).rename("weight")
    # Confirm the repository's vectorized helper produces the same official assignment.
    helper_weights, helper_q = evaluation.weights(ordered)
    pd.testing.assert_series_equal(weights, helper_weights.rename("weight"), check_exact=True)
    pd.testing.assert_series_equal(q.astype(float), helper_q.astype(float), check_exact=True)
    return weights, q


def account_from_weights(signal, weights, q, target):
    """Compute daily official-compatible accounting for a supplied weight path."""
    signal = signal.sort_index().fillna(0.0)
    weights = weights.reindex(signal.index).fillna(0.0).rename("weight")
    target = target.reindex(signal.index)
    if not signal.index.equals(target.index) or not signal.index.equals(weights.index):
        raise ValueError("Score, weight, and target indexes must match exactly")
    turnover = weights.groupby(level="Code").diff().abs().fillna(weights.abs())
    valid = target.notna()
    cost_i = (ONE_WAY_COST * turnover).where(valid, 0.0)
    gross_i = weights * target
    net_i = gross_i - cost_i

    sides = {}
    for side, side_weight in (("long", weights.clip(lower=0.0)),
                              ("short", weights.clip(upper=0.0))):
        side_turn = side_weight.groupby(level="Code").diff().abs().fillna(side_weight.abs())
        side_cost = (ONE_WAY_COST * side_turn).where(valid, 0.0)
        side_gross_i = side_weight * target
        sides[f"{side}_gross"] = grouped_sum(side_gross_i)
        sides[f"{side}_cost"] = grouped_sum(side_cost)
        sides[f"{side}_net"] = grouped_sum(side_gross_i - side_cost)
        sides[f"{side}_turnover"] = grouped_sum(side_turn)

    gross = grouped_sum(gross_i)
    net = grouped_sum(net_i)
    daily = pd.DataFrame({
        "gross": gross,
        "net": net,
        "turnover": grouped_sum(turnover),
        "cost_all": grouped_sum(ONE_WAY_COST * turnover),
        "long": sides["long_gross"],
        "short": sides["short_gross"],
        "long_gross": sides["long_gross"],
        "short_gross": sides["short_gross"],
        "long_cost": sides["long_cost"],
        "short_cost": sides["short_cost"],
        "long_net": sides["long_net"],
        "short_net": sides["short_net"],
        "long_turnover": sides["long_turnover"],
        "short_turnover": sides["short_turnover"],
        "label_coverage": target.notna().groupby(level="Date").mean(),
        "gross_exposure": weights.abs().groupby(level="Date").sum(),
        "net_exposure": weights.groupby(level="Date").sum(),
        "long_exposure": weights.clip(lower=0.0).groupby(level="Date").sum(),
        "short_exposure": -weights.clip(upper=0.0).groupby(level="Date").sum(),
    })
    daily["cost"] = daily["gross"] - daily["net"]
    daily["net_all_cost"] = daily["gross"] - daily["cost_all"]
    daily["rankic"] = evaluation.rankic(signal, target)
    q = q.reindex(signal.index)
    for k in range(5):
        daily[f"q{k + 1}"] = target.where(q.eq(k)).groupby(level="Date").mean()

    # Decompose each sleeve using the same-date target-valid universe mean.
    universe_mean = target.groupby(level="Date").mean()
    for side in ("long", "short"):
        side_weight = weights.clip(lower=0.0) if side == "long" else weights.clip(upper=0.0)
        valid_weight = side_weight.where(valid, 0.0)
        label_exposure = valid_weight.groupby(level="Date").sum()
        common = label_exposure * universe_mean
        selection = daily[f"{side}_gross"] - common
        daily[f"{side}_label_valid_exposure"] = label_exposure
        daily[f"{side}_common"] = common
        daily[f"{side}_selection"] = selection
    daily["common"] = daily.long_common + daily.short_common
    daily["selection"] = daily.long_selection + daily.short_selection
    daily["universe_mean_residual"] = universe_mean

    if not np.allclose(
        (daily.long_net + daily.short_net).to_numpy(), daily.net.to_numpy(),
        rtol=0.0, atol=1e-12, equal_nan=True,
    ):
        raise AssertionError("Long plus Short net does not reconcile to total net")
    if not np.allclose(
        (daily.common + daily.selection).to_numpy(), daily.gross.to_numpy(),
        rtol=0.0, atol=1e-12, equal_nan=True,
    ):
        raise AssertionError("Common plus selection gross does not reconcile")
    return daily.sort_index(), turnover.rename("turnover"), cost_i.rename("cost_i")


def scale_short(weights, gamma):
    if gamma not in GAMMAS:
        raise ValueError(f"Unregistered gamma: {gamma}")
    return (weights.where(weights.ge(0.0), gamma * weights)).rename("weight")


def eligible_ridge_predictions(x, target, eligible, years=YEARS, model_dir=None):
    """Annual expanding Ridge fitted/predicted only on eligible event rows."""
    dates = x.index.get_level_values("Date")
    calendar = pd.DatetimeIndex(dates.unique().sort_values())
    target_rank = bidirectional.centered_target_rank(target)
    predictions = {side: [] for side in bidirectional.SIDES}
    records = []
    for year in years:
        start_pos = calendar.searchsorted(pd.Timestamp(f"{year}-01-01"))
        mature_dates = calendar[:max(0, start_pos - 2)]
        mature = dates.isin(mature_dates)
        for side in bidirectional.SIDES:
            event = bidirectional.event_mask(x, side) & eligible
            oriented_target = target_rank if side == "high" else -target_rank
            train = mature & event.to_numpy() & oriented_target.notna().to_numpy()
            rows = int(train.sum())
            if rows < bidirectional.MIN_TRAINING_ROWS:
                raise ValueError(
                    f"Only {rows} mature eligible {side} rows before {year}; "
                    f"existing Ridge contract requires {bidirectional.MIN_TRAINING_ROWS}"
                )
            matrix = bidirectional.directional_features(x.loc[train], side)
            model = bidirectional.fit_arrays(matrix, oriented_target.loc[train], RIDGE_LAMBDA)
            selected = (dates.year == year) & event.to_numpy()
            test_matrix = bidirectional.directional_features(x.loc[selected], side)
            pred = pd.Series(
                bidirectional.predict_matrix(test_matrix, model), index=test_matrix.index,
                name=f"B_BOX_GATE_RIDGE_{side}", dtype=float,
            )
            predictions[side].append(pred)
            used_dates = dates[train]
            last_signal = pd.Timestamp(used_dates.max())
            label_pos = calendar.get_indexer([last_signal])[0]
            model.update({
                "side": side,
                "year": int(year),
                "training_dates": int(used_dates.nunique()),
                "min_training_signal": str(pd.Timestamp(used_dates.min()).date()),
                "max_training_signal": str(last_signal.date()),
                "max_label_maturity_date": str(calendar[min(label_pos + 2, len(calendar) - 1)].date()),
                "eligibility": "box_duration > 0, finite box_width_atr < 3.0",
            })
            record = {key: model[key] for key in (
                "side", "year", "training_rows", "training_dates", "min_training_signal",
                "max_training_signal", "max_label_maturity_date", "coefficients",
            )}
            records.append(record)
            if model_dir is not None:
                (model_dir / f"RIDGE_eligible_{side}_{year}.json").write_text(
                    json.dumps(json_safe(model), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8",
                )
    combined = {}
    for side, pieces in predictions.items():
        combined[side] = pd.concat(pieces).sort_index()
        if not combined[side].index.is_unique:
            raise AssertionError(f"Duplicate eligible Ridge predictions for {side}")
    return combined, records


def score_from_side_values(x, high_mask, low_mask, high_value, low_value, name):
    raw = pd.Series(0.0, index=x.index, name=f"{name}_raw")
    for mask, values, sign in ((high_mask, high_value, 1.0), (low_mask, low_value, -1.0)):
        active_values = values.reindex(x.index).where(mask)
        rank = active_values.groupby(level="Date").rank(method="average", pct=True)
        raw.loc[mask] = sign * (0.5 + 0.5 * rank.loc[mask])
    if (high_mask & low_mask).any():
        raise AssertionError("High/Low event sets overlap")
    return raw


def build_gate_scores(x, eligible, target, model_dir=None):
    high = bidirectional.event_mask(x, "high")
    low = bidirectional.event_mask(x, "low")
    gate_high, gate_low = high & eligible, low & eligible
    # Reuse the existing B00 score implementation with only eligible events visible.
    gate_x = x.copy()
    gate_x["high_available"] = x["high_available"] & eligible
    gate_x["low_available"] = x["low_available"] & eligible
    b2_raw = b00_models.raw_base_signal(gate_x)
    b2 = segment_ewma(b2_raw.rename("B_BOX_GATE_B00_SCORE"), ALPHA)

    predictions, records = eligible_ridge_predictions(
        x, target, eligible, years=YEARS, model_dir=model_dir
    )
    b3_raw = score_from_side_values(
        x, gate_high, gate_low,
        predictions["high"], predictions["low"], "B_BOX_GATE_RIDGE",
    )
    b3 = segment_ewma(b3_raw, ALPHA).rename("B_BOX_GATE_RIDGE")
    return b2.rename("B_BOX_GATE_B00_SCORE"), b3, b2_raw, b3_raw, records, predictions


def mutate_inputs(inputs, cutoff, truncate=False):
    changed = {}
    cutoff = pd.Timestamp(cutoff)
    for name, frame in inputs.items():
        dates = frame.index.get_level_values("Date")
        future = dates > cutoff
        if truncate:
            changed[name] = frame.loc[~future].copy()
            continue
        values = frame.copy()
        for column in values:
            if pd.api.types.is_numeric_dtype(values[column]):
                if name == "prices_daily_quotes" and column == "AdjustmentFactor":
                    values.loc[future, column] = 1.0
                    if future.any():
                        values.loc[future & (dates == dates[future].min()), column] = 0.25
                else:
                    values.loc[future, column] = values.loc[future, column] * -3.14 + 888.0
            elif pd.api.types.is_datetime64_any_dtype(values[column]):
                values.loc[future, column] = pd.Timestamp("1990-01-01")
            else:
                values.loc[future, column] = "future_mutation"
        changed[name] = values
    return changed


def mutate_target(target, cutoff, truncate=False):
    cutoff = pd.Timestamp(cutoff)
    dates = target.index.get_level_values("Date")
    future = dates > cutoff
    if truncate:
        return target.loc[~future].copy()
    changed = target.copy()
    changed.loc[future] = changed.loc[future] * -3.14 + 888.0
    return changed


def gate_prefix_audit(inputs, target, x, eligible, b2, b3):
    records = []
    all_dates = x.index.get_level_values("Date")
    for label in PREFIX_CUTOFFS:
        cutoff = pd.Timestamp(label)
        if cutoff not in all_dates:
            raise AssertionError(f"Missing prefix cutoff: {label}")
        prefix_index = x.index[all_dates <= cutoff]
        mode_records = {}
        for mode, truncate in (("mutation", False), ("truncation", True)):
            changed_inputs = mutate_inputs(inputs, cutoff, truncate=truncate)
            changed_x = features.build_features(changed_inputs)
            changed_eligible = eligible_box_mask(changed_x)
            changed_target = mutate_target(target, cutoff, truncate=truncate)
            if truncate:
                changed_target = changed_target.reindex(changed_x.index)
            pd.testing.assert_frame_equal(
                x.loc[prefix_index], changed_x.loc[prefix_index], check_exact=True
            )
            pd.testing.assert_series_equal(
                eligible.loc[prefix_index], changed_eligible.loc[prefix_index], check_exact=True
            )
            changed_b2_raw = b00_models.raw_base_signal(
                changed_x.assign(
                    high_available=changed_x["high_available"] & changed_eligible,
                    low_available=changed_x["low_available"] & changed_eligible,
                )
            )
            changed_b2 = segment_ewma(changed_b2_raw, ALPHA).rename("B_BOX_GATE_B00_SCORE")
            changed_b3, *_ = build_b3_only(changed_x, changed_eligible, changed_target, cutoff)
            pd.testing.assert_series_equal(
                b2.loc[prefix_index], changed_b2.loc[prefix_index], check_exact=True
            )
            pd.testing.assert_series_equal(
                b3.loc[prefix_index], changed_b3.loc[prefix_index], check_exact=True
            )
            mode_records[mode] = "features, eligibility, B2, mature eligible Ridge refits, and B3 prefix bitwise exact"
        records.append({"cutoff": label, "prefix_rows": len(prefix_index), "checks": mode_records})
    return {"status": "PASS", "cutoffs": records}


def build_b3_only(x, eligible, target, cutoff):
    years = tuple(year for year in YEARS if year <= pd.Timestamp(cutoff).year)
    predictions, records = eligible_ridge_predictions(x, target, eligible, years=years)
    high = bidirectional.event_mask(x, "high") & eligible
    low = bidirectional.event_mask(x, "low") & eligible
    raw = score_from_side_values(x, high, low, predictions["high"], predictions["low"], "B3_prefix")
    return segment_ewma(raw, ALPHA).rename("B_BOX_GATE_RIDGE"), records, predictions


def static_source_scan():
    paths = [Path(features.__file__), Path(bidirectional.__file__), Path(b00_models.__file__)]
    banned = (
        "AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose",
        "AdjustmentVolume", "raw_target", "target_1day_valid",
    )
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
            if node.func.attr == "shift":
                periods = node.args[0] if node.args else next(
                    (arg.value for arg in node.keywords if arg.arg in ("periods", "period")), None
                )
                if isinstance(periods, ast.UnaryOp) and isinstance(periods.op, ast.USub):
                    raise AssertionError(f"Negative shift in {path}")
            if any(arg.arg == "center" and isinstance(arg.value, ast.Constant) and arg.value.value
                   for arg in node.keywords):
                raise AssertionError(f"Centered rolling call in {path}")
    return [str(path.relative_to(ROOT)) for path in paths]


def official_eval_dates(daily_index):
    dates = pd.DatetimeIndex(daily_index)
    chosen = []
    for year in YEARS:
        year_dates = dates[dates.year == year].unique().sort_values()
        if len(year_dates) <= 2:
            raise ValueError(f"Insufficient dates in {year}")
        chosen.extend(year_dates[:-2].tolist())
    return pd.DatetimeIndex(chosen).sort_values()


def stat_record(name, period, score, weights, q, daily, target, sector):
    selected_dates = daily.index
    a = daily.reindex(selected_dates)
    stats = evaluation.metrics(a)
    gross_vol = float(a.gross.std(ddof=1) * np.sqrt(ANNUALIZATION))
    net_vol = float(a.net.std(ddof=1) * np.sqrt(ANNUALIZATION))
    long_short_corr = float(a.long_net.corr(a.short_net)) if a.long_net.std() > 0 and a.short_net.std() > 0 else np.nan
    score_eval = score.loc[score.index.get_level_values("Date").isin(selected_dates)]
    weights_eval = weights.loc[weights.index.get_level_values("Date").isin(selected_dates)]
    q_eval = q.loc[q.index.get_level_values("Date").isin(selected_dates)]
    target_eval = target.reindex(score_eval.index)
    zero = score_eval.eq(0.0)
    zero_rows = int(zero.sum())
    short_mask = weights_eval.lt(0.0)
    long_mask = weights_eval.gt(0.0)
    q1, q5 = q_eval.eq(0), q_eval.eq(4)
    zero_q1, zero_q5 = zero & q1, zero & q5
    denom_short = float(weights_eval.where(short_mask).abs().sum())
    denom_long = float(weights_eval.where(long_mask).abs().sum())
    zero_q1_weight = float(weights_eval.where(zero_q1).abs().sum())
    zero_q5_weight = float(weights_eval.where(zero_q5).abs().sum())
    zero_q1_count = int(zero_q1.sum())
    zero_q5_count = int(zero_q5.sum())

    # This is a mechanical ordering diagnostic, not an alternative portfolio.
    code_order_metrics = zero_code_order_metrics(score_eval, q_eval)

    tail_stats = {}
    for side, mask, tail in (("short", q1, "Q1"), ("long", q5, "Q5")):
        part = pd.DataFrame({
            "sector": sector.reindex(q_eval.index)["Sector33CodeName"].fillna("Unknown").astype(str),
            "weight": weights_eval,
            "score": score_eval,
            "target": target_eval,
            "q": q_eval,
        }, index=q_eval.index).loc[mask]
        zero_tail = part.score.eq(0.0)
        gross_w = part.weight.abs()
        daily_sector = gross_w.groupby([part.index.get_level_values("Date"), part.sector]).sum()
        daily_sector_share = daily_sector / daily_sector.groupby(level=0).transform("sum").replace(0.0, np.nan)
        max_share = daily_sector_share.groupby(level=0).max()
        hhi = (daily_sector_share ** 2).groupby(level=0).sum()
        tail_stats[f"{tail.lower()}_zero_stock_share"] = float(zero_tail.mean()) if len(part) else np.nan
        tail_stats[f"{tail.lower()}_zero_gross_weight_share"] = (
            float(gross_w.where(zero_tail, 0.0).sum() / gross_w.sum()) if gross_w.sum() else np.nan
        )
        tail_stats[f"{tail.lower()}_mean_max_sector_share"] = float(max_share.mean()) if len(max_share) else np.nan
        tail_stats[f"{tail.lower()}_mean_sector_hhi"] = float(hhi.mean()) if len(hhi) else np.nan
        tail_stats[f"{tail.lower()}_zero_gross_pnl_annual"] = float(
            (part.weight * part.target).where(zero_tail).groupby(level="Date").sum().mean() * ANNUALIZATION
        )

    record = {
        "strategy": name,
        "period": period,
        "days": int(len(a)),
        "annual_gross_return": stats["annual_gross"],
        "annual_net_return": stats["annual_net"],
        "annualized_gross_volatility": gross_vol,
        "annualized_net_volatility": net_vol,
        "gross_sharpe": stats["gross_sharpe"],
        "net_sharpe": stats["net_sharpe"],
        "turnover_per_day": stats["turnover"],
        "annualized_cost": stats["annual_cost"],
        "max_drawdown_additive": stats["max_drawdown_additive"],
        "annual_long_gross": float(a.long_gross.mean() * ANNUALIZATION),
        "annual_long_net": float(a.long_net.mean() * ANNUALIZATION),
        "annual_short_gross": float(a.short_gross.mean() * ANNUALIZATION),
        "annual_short_net": float(a.short_net.mean() * ANNUALIZATION),
        "long_short_net_correlation": long_short_corr,
        "rankic": stats["rankic"],
        "rankic_hac_t_lag5": stats["rankic_t_hac5"],
        "rankic_hit_ratio": stats["rankic_hit"],
        "q1_q5_monotonicity": stats["q_monotonicity"],
        "average_gross_exposure": float(a.gross_exposure.mean()),
        "average_net_exposure": float(a.net_exposure.mean()),
        "average_long_exposure": float(a.long_exposure.mean()),
        "average_short_exposure": float(a.short_exposure.mean()),
        "active_signal_stock_days": int((score_eval != 0.0).sum()),
        "nonzero_score_ratio": float((score_eval != 0.0).mean()),
        "score_zero_stock_days": zero_rows,
        "score_zero_ratio": float(zero.mean()),
        "q1_zero_stock_count": zero_q1_count,
        "q1_zero_stock_share": float(zero_q1_count / q1.sum()) if q1.sum() else np.nan,
        "q1_zero_gross_weight_share": zero_q1_weight / denom_short if denom_short else np.nan,
        "q5_zero_stock_count": zero_q5_count,
        "q5_zero_stock_share": float(zero_q5_count / q5.sum()) if q5.sum() else np.nan,
        "q5_zero_gross_weight_share": zero_q5_weight / denom_long if denom_long else np.nan,
        **code_order_metrics,
        "q1_zero_tie_annual_gross_pnl": tail_stats["q1_zero_gross_pnl_annual"],
        "q5_zero_tie_annual_gross_pnl": tail_stats["q5_zero_gross_pnl_annual"],
        "q1_zero_tie_weight_share_of_short": zero_q1_weight / denom_short if denom_short else np.nan,
        "q5_zero_tie_weight_share_of_long": zero_q5_weight / denom_long if denom_long else np.nan,
        **tail_stats,
        **{f"q{k + 1}_daily_residual_return": stats[f"q{k + 1}_daily_return"] for k in range(5)},
        "mean_universe_residual_drift": float(a.universe_mean_residual.mean()),
        "annual_common_residual_component": float(a.common.mean() * ANNUALIZATION),
        "annual_selection_component": float(a.selection.mean() * ANNUALIZATION),
        "annual_long_common_component": float(a.long_common.mean() * ANNUALIZATION),
        "annual_long_selection_component": float(a.long_selection.mean() * ANNUALIZATION),
        "annual_short_common_component": float(a.short_common.mean() * ANNUALIZATION),
        "annual_short_selection_component": float(a.short_selection.mean() * ANNUALIZATION),
        "annual_net_exposure_common_proxy": float((a.net_exposure * a.universe_mean_residual).mean() * ANNUALIZATION),
    }
    return json_safe(record)


def category_turnover(weights, fractions):
    """Allocate turnover to old/new source categories; sum must equal total turnover."""
    groups = features.segment_keys(weights.index)
    previous = weights.groupby(groups, sort=False).shift(1).fillna(0.0)
    previous_fractions = fractions.groupby(groups, sort=False).shift(1).fillna(0.0)
    current = weights.fillna(0.0)
    prev_hold = previous.ne(0.0)
    curr_hold = current.ne(0.0)
    same_side = prev_hold & curr_hold & (np.sign(previous) == np.sign(current))
    old_only = prev_hold & ~curr_hold
    new_only = ~prev_hold & curr_hold
    cross = prev_hold & curr_hold & (np.sign(previous) != np.sign(current))
    result = {}
    for side in ("long", "short"):
        allocs = pd.DataFrame(0.0, index=weights.index, columns=CATEGORIES)
        for category in CATEGORIES:
            old_f = previous_fractions[category]
            new_f = fractions[category]
            col = pd.Series(0.0, index=weights.index)
            old_side = previous.gt(0.0) if side == "long" else previous.lt(0.0)
            new_side = current.gt(0.0) if side == "long" else current.lt(0.0)
            col.loc[same_side & old_side] = (
                (current - previous).abs() * 0.5 * (old_f + new_f)
            ).loc[same_side & old_side]
            col.loc[old_only & old_side] = (previous.abs() * old_f).loc[old_only & old_side]
            col.loc[new_only & new_side] = (current.abs() * new_f).loc[new_only & new_side]
            col.loc[cross & old_side] = (previous.abs() * old_f).loc[cross & old_side]
            col.loc[cross & new_side] = (current.abs() * new_f).loc[cross & new_side]
            allocs[category] = col
        result[side] = allocs
    turn = weights.groupby(level="Code").diff().abs().fillna(weights.abs())
    allocated = result["long"].sum(axis=1) + result["short"].sum(axis=1)
    if not np.allclose(turn.to_numpy(), allocated.to_numpy(), rtol=0.0, atol=1e-12):
        raise AssertionError("Category turnover allocation does not reconcile")
    return result


def attribution_tables(name, score, weights, q, components, target, eval_dates):
    fractions = component_fractions(score, components, q)
    turnover_alloc = category_turnover(weights, fractions)
    dates = score.index.get_level_values("Date")
    eval_mask = dates.isin(eval_dates)
    out = []
    daily_rows = []
    for side in ("long", "short"):
        side_mask = weights.gt(0.0) if side == "long" else weights.lt(0.0)
        side_weight = weights.where(side_mask, 0.0)
        side_turn_alloc = turnover_alloc[side]
        for category in CATEGORIES:
            frac = fractions[category]
            gross_i = side_weight * target.reindex(score.index) * frac
            turn_i = side_turn_alloc[category]
            cost_i = (ONE_WAY_COST * turn_i).where(target.reindex(score.index).notna(), 0.0)
            gross_day = gross_i.groupby(level="Date").sum()
            cost_day = cost_i.groupby(level="Date").sum()
            turn_day = turn_i.groupby(level="Date").sum()
            net_day = gross_day - cost_day
            held = side_mask & eval_mask
            denom_weight = float(weights.where(side_mask & eval_mask).abs().sum())
            fractional_weight = float((weights.abs() * frac).where(side_mask & eval_mask, 0.0).sum())
            stock_days_fractional = float(frac.where(held, 0.0).sum())
            max_idx = fractions.loc[held, list(CATEGORIES)].idxmax(axis=1)
            primary_count = int(max_idx.eq(category).sum())
            turnover_full = float(turn_i.loc[eval_mask].sum())
            total_turnover = float(side_turn_alloc.loc[eval_mask].sum().sum())
            annual_gross = float(gross_day.reindex(eval_dates).mean() * ANNUALIZATION)
            annual_cost = float(cost_day.reindex(eval_dates).mean() * ANNUALIZATION)
            annual_net = annual_gross - annual_cost
            row = {
                "strategy": name,
                "side": side,
                "category": category,
                "held_stock_days_primary": primary_count,
                "held_stock_days_fractional": stock_days_fractional,
                "fractional_stock_day_share_of_sleeve": stock_days_fractional / int((side_mask & eval_mask).sum()) if (side_mask & eval_mask).sum() else np.nan,
                "gross_weight_share_of_sleeve": fractional_weight / denom_weight if denom_weight else np.nan,
                "annual_gross_contribution": annual_gross,
                "annual_cost_attribution": annual_cost,
                "annual_net_contribution": annual_net,
                "turnover_share": turnover_full / total_turnover if total_turnover else np.nan,
            }
            out.append(row)
            for date in eval_dates:
                daily_rows.append({
                    "Date": date, "strategy": name, "side": side, "category": category,
                    "gross": gross_day.get(date, 0.0), "cost": cost_day.get(date, 0.0),
                    "net": net_day.get(date, 0.0), "turnover": turn_day.get(date, 0.0),
                })
    return pd.DataFrame(out), pd.DataFrame(daily_rows), fractions


def sector_outputs(name, score, weights, q, sector):
    data = pd.DataFrame({
        "q": q,
        "weight": weights,
        "score": score,
        "sector33_code": sector["Sector33Code"].fillna("Unknown").astype(str),
        "sector33_name": sector["Sector33CodeName"].fillna("Unknown").astype(str),
        "sector17_code": sector["Sector17Code"].fillna("Unknown").astype(str),
        "sector17_name": sector["Sector17CodeName"].fillna("Unknown").astype(str),
    }, index=score.index)
    date_values = data.index.get_level_values("Date")
    records = []
    for qvalue, tail in ((0, "Q1"), (4, "Q5")):
        part = data.loc[data.q.eq(qvalue)].copy()
        part["Date"] = date_values[data.q.eq(qvalue).to_numpy()]
        part["gross_weight"] = part.weight.abs()
        part["score_zero"] = part.score.eq(0.0)
        group = part.groupby(
            [part["Date"], part["sector33_code"], part["sector33_name"]], dropna=False
        )
        sector_daily = group.agg(
            stock_days=("weight", "size"),
            gross_weight=("gross_weight", "sum"),
            zero_stock_days=("score_zero", "sum"),
        ).reset_index()
        totals = sector_daily.groupby("Date")["gross_weight"].transform("sum")
        sector_daily["gross_weight_share"] = sector_daily.gross_weight.div(totals.replace(0.0, np.nan))
        sector_daily["tail"] = tail
        sector_daily["strategy"] = name
        records.extend(sector_daily.to_dict("records"))
    return records


def yearly_category_attribution(detail, daily_attribution):
    """Fold/year stock-days, gross-weight, P/L, cost, and turnover by source."""
    rows = []
    detail_frame = detail.reset_index()
    detail_frame["year"] = pd.to_datetime(detail_frame["Date"]).dt.year
    daily = daily_attribution.copy()
    daily["year"] = pd.to_datetime(daily["Date"]).dt.year
    held_frame = detail_frame.loc[detail_frame.weight.ne(0.0)]
    for (name, year, side), held in held_frame.groupby(
        ["strategy", "year", "portfolio_side"], sort=False
    ):
        if side not in ("Long", "Short"):
            continue
        side_daily = daily.loc[
            daily.strategy.eq(name) & daily.side.eq(side.lower()) & daily.year.eq(year)
        ]
        total_turn = float(side_daily.groupby("Date").turnover.sum().mean() * ANNUALIZATION) if len(side_daily) else 0.0
        total_weight = float(held.weight.abs().sum())
        primary_count = held.primary_source.value_counts()
        for category in CATEGORIES:
            cat_daily = daily.loc[
                daily.strategy.eq(name) & daily.side.eq(side.lower())
                & daily.category.eq(category) & daily.year.eq(year)
            ]
            fraction_col = f"fraction_{category}"
            fractional_days = float(held[fraction_col].sum())
            fractional_weight = float((held.weight.abs() * held[fraction_col]).sum())
            gross = float(cat_daily.gross.mean() * ANNUALIZATION) if len(cat_daily) else 0.0
            cost = float(cat_daily.cost.mean() * ANNUALIZATION) if len(cat_daily) else 0.0
            cat_turn = float(cat_daily.turnover.mean() * ANNUALIZATION) if len(cat_daily) else 0.0
            rows.append({
                "strategy": name, "year": int(year), "fold": int(year),
                "side": side.lower(), "category": category,
                "held_stock_days_primary": int(primary_count.get(category, 0)),
                "held_stock_days_fractional": fractional_days,
                "fractional_stock_day_share_of_sleeve": fractional_days / len(held) if len(held) else np.nan,
                "gross_weight_share_of_sleeve": fractional_weight / total_weight if total_weight else np.nan,
                "annual_gross_contribution": gross,
                "annual_cost_attribution": cost,
                "annual_net_contribution": gross - cost,
                "annual_turnover_contribution": cat_turn,
                "turnover_share_of_sleeve": cat_turn / total_turn if total_turn else np.nan,
            })
    return pd.DataFrame(rows)


def zero_sector_bias(detail, target):
    """Compare zero-score tail ties' PIT sectors with each same-day zero pool."""
    frame = detail.reset_index()
    frame["Date"] = pd.to_datetime(frame["Date"])
    frame["target"] = target.reindex(detail.index).to_numpy()
    frame["sector_code"] = frame["Sector33Code"].fillna("Unknown").astype(str)
    frame["sector_name"] = frame["Sector33CodeName"].fillna("Unknown").astype(str)
    frame["gross_weight"] = frame["weight"].abs()
    frame["gross_pnl"] = frame["weight"] * frame["target"]
    output = []
    for name, data in frame.groupby("strategy", sort=False):
        zeros = data.loc[data.score_zero]
        if zeros.empty:
            continue
        pool = zeros.groupby(["Date", "sector_code", "sector_name"], dropna=False).size().rename("zero_pool_count").reset_index()
        pool["daily_pool_share"] = pool.zero_pool_count / pool.groupby("Date").zero_pool_count.transform("sum")
        eval_day_count = int(data.Date.nunique())
        for q_value, tail in ((0, "Q1"), (4, "Q5")):
            tail_rows = zeros.loc[zeros.q.eq(q_value)]
            if tail_rows.empty:
                continue
            tie = tail_rows.groupby(["Date", "sector_code", "sector_name"], dropna=False).agg(
                tie_stock_days=("weight", "size"),
                tie_gross_weight=("gross_weight", "sum"),
                tie_gross_pnl=("gross_pnl", "sum"),
            ).reset_index()
            tie["daily_tail_share"] = tie.tie_stock_days / tie.groupby("Date").tie_stock_days.transform("sum")
            tail_weight = data.loc[data.q.eq(q_value)].groupby("Date").gross_weight.sum()
            tie["daily_tail_gross_weight_share"] = tie.apply(
                lambda row: row.tie_gross_weight / tail_weight.get(row.Date, np.nan), axis=1
            )
            tie["daily_tail_gross_pnl"] = tie.tie_gross_pnl
            active_dates = pd.Index(tie.Date.unique())
            # Include sector/date cells with no zero holdings so daily shares and
            # P/L use the same complete set of tail-zero dates.
            sectors = pool[["sector_code", "sector_name"]].drop_duplicates()
            grid = pd.DataFrame({"Date": active_dates}).merge(sectors, how="cross")
            merged = grid.merge(pool, on=["Date", "sector_code", "sector_name"], how="left")
            merged = merged.merge(tie, on=["Date", "sector_code", "sector_name"], how="left")
            merged[["zero_pool_count", "tie_stock_days", "tie_gross_weight", "tie_gross_pnl",
                    "daily_pool_share", "daily_tail_share", "daily_tail_gross_weight_share",
                    "daily_tail_gross_pnl"]] = merged[[
                        "zero_pool_count", "tie_stock_days", "tie_gross_weight", "tie_gross_pnl",
                        "daily_pool_share", "daily_tail_share", "daily_tail_gross_weight_share",
                        "daily_tail_gross_pnl",
                    ]].fillna(0.0)
            grouped = merged.groupby(["sector_code", "sector_name"], dropna=False)
            for (code, sector_name), part in grouped:
                output.append({
                    "strategy": name, "tail": tail, "Sector33Code": code,
                    "Sector33CodeName": sector_name,
                    "zero_pool_stock_days": int(part.zero_pool_count.sum()),
                    "tail_zero_stock_days": int(part.tie_stock_days.sum()),
                    "mean_daily_zero_pool_sector_share": float(part.daily_pool_share.mean()),
                    "mean_daily_tail_zero_sector_share": float(part.daily_tail_share.mean()),
                    "sector_share_delta_vs_zero_pool": float(part.daily_tail_share.mean() - part.daily_pool_share.mean()),
                    "mean_daily_tail_zero_gross_weight_share": float(part.daily_tail_gross_weight_share.mean()),
                    "annual_tail_zero_gross_pnl": float(part.daily_tail_gross_pnl.sum() * ANNUALIZATION / eval_day_count),
                })
    return pd.DataFrame(output)


def gamma_diagnostics(periods):
    names = [name for name in TRIAL_IDS if name in ("B00_BASE", "BOX_ORIGINAL") or "SHORT_GAMMA" in name]
    gamma_map = {"B00_BASE": 1.0, "BOX_ORIGINAL": 1.0}
    for name in names:
        if "SHORT_GAMMA" in name:
            gamma_map[name] = int(name.rsplit("_", 1)[1]) / 100.0
    result = periods.loc[
        periods.strategy.isin(names)
        & periods.period.isin(["full_train_eval", "ex_2016", *[str(year) for year in YEARS]])
    ].copy()
    result["gamma"] = result.strategy.map(gamma_map)
    result["official_five_quintile"] = result.gamma.eq(1.0)
    return result.sort_values(["gamma", "strategy", "period"], ascending=[False, True, True])


def trial_metric_sets(specs, target, sector, eval_dates):
    period_rows, daily_accounts, turnover_series, weights_store, quintiles_store = [], {}, {}, {}, {}
    for name in TRIAL_IDS:
        score, weights, q = specs[name]
        daily, turnover, _ = account_from_weights(score, weights, q, target)
        daily = daily.loc[daily.index.isin(eval_dates)].copy()
        daily_accounts[name] = daily
        turnover_series[name] = turnover
        weights_store[name] = weights
        quintiles_store[name] = q
        periods = [("full_train_eval", pd.DatetimeIndex(daily.index))]
        periods.append(("ex_2016", pd.DatetimeIndex(daily.index[daily.index.year != 2016])))
        periods.extend((str(year), pd.DatetimeIndex(daily.index[daily.index.year == year])) for year in YEARS)
        for period, dates in periods:
            if len(dates) == 0:
                continue
            period_rows.append(stat_record(
                name, period, score, weights, q, daily.loc[daily.index.isin(dates)],
                target, sector,
            ))
    return pd.DataFrame(period_rows), daily_accounts, turnover_series, weights_store, quintiles_store


def build_audit_detail(scores, weights, q, components, sector, eval_dates):
    score_eval = scores.loc[scores.index.get_level_values("Date").isin(eval_dates)]
    q_eval = q.reindex(score_eval.index)
    weight_eval = weights.reindex(score_eval.index)
    fractions = component_fractions(score_eval, components.reindex(score_eval.index), q_eval)
    result = pd.DataFrame({
        "score": score_eval,
        "score_zero": score_eval.eq(0.0),
        "q": q_eval,
        "weight": weight_eval,
        "portfolio_side": np.select([weight_eval.gt(0.0), weight_eval.lt(0.0)], ["Long", "Short"], default="Flat"),
        "tie_break_zero_tail": score_eval.eq(0.0) & q_eval.isin([0, 4]),
        "Sector33Code": sector.reindex(score_eval.index)["Sector33Code"],
        "Sector33CodeName": sector.reindex(score_eval.index)["Sector33CodeName"],
        "Sector17Code": sector.reindex(score_eval.index)["Sector17Code"],
        "Sector17CodeName": sector.reindex(score_eval.index)["Sector17CodeName"],
    }, index=score_eval.index)
    for col in components.columns:
        result[col] = components.loc[score_eval.index, col]
    for col in fractions.columns:
        result[f"fraction_{col}"] = fractions[col]
    result["primary_source"] = fractions.idxmax(axis=1)
    return result


def bootstrap_comparisons(daily_accounts, comparator):
    rows = []
    pairs = []
    for name, base in comparator.items():
        if name == base or name not in daily_accounts or base not in daily_accounts:
            continue
        pairs.append((name, base))
    pairs.append(("B_BOX_GATE_RIDGE", "B_BOX_GATE_B00_SCORE"))
    for candidate, baseline in pairs:
        lhs = daily_accounts[baseline]["net"]
        rhs = daily_accounts[candidate]["net"]
        common = lhs.index.intersection(rhs.index)
        result = evaluation.bootstrap_delta(
            lhs.loc[common], rhs.loc[common], seed=BOOTSTRAP_SEED,
            reps=BOOTSTRAP_REPS, block=BOOTSTRAP_BLOCK,
        )
        rows.append({
            "candidate": candidate, "baseline": baseline,
            "delta_net_sharpe": float(evaluation.sharpe(rhs.loc[common]) - evaluation.sharpe(lhs.loc[common])),
            "delta_annual_net_return": float((rhs.loc[common].mean() - lhs.loc[common].mean()) * ANNUALIZATION),
            "paired_delta_net_sharpe_ci_low": result["low"],
            "paired_delta_net_sharpe_ci_high": result["high"],
            "bootstrap_positive_fraction": result["bootstrap_positive_fraction"],
            "bootstrap_repetitions": BOOTSTRAP_REPS,
            "block_days": BOOTSTRAP_BLOCK,
            "seed": BOOTSTRAP_SEED,
        })
    return pd.DataFrame(rows)


def markdown_table(frame, columns, headers=None, digits=3):
    headers = headers or columns
    rows = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for _, row in frame[columns].iterrows():
        cells = []
        for column, value in row.items():
            if pd.isna(value):
                cells.append("—")
            elif isinstance(value, (float, np.floating)):
                percent = column in ("annual_long_net", "annual_short_net") or any(token in column for token in (
                    "_return", "_volatility", "_cost", "_contribution", "_share",
                    "_exposure", "_component", "_proxy", "gross_weight_share", "_pnl",
                ))
                if percent:
                    cells.append(f"{value * 100:+.{min(digits, 2)}f}%")
                else:
                    cells.append(f"{value:+.{digits}f}" if value != 0 else f"{0:.{digits}f}")
            else:
                cells.append(str(value))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def write_reports(report_dir, run_id, source_metadata, current_audit, summary, folds,
                  periods, comparisons, attribution, year_attribution, sector_bias,
                  gamma_diag, code_audit):
    report_dir.mkdir(parents=True, exist_ok=True)
    pooled = summary.loc[summary.period.eq("full_train_eval")].set_index("strategy")
    ex2016 = summary.loc[summary.period.eq("ex_2016")].set_index("strategy")
    worst = folds.sort_values("annual_net_return").groupby("strategy", as_index=False).first()
    brief = pooled.reset_index().copy()
    brief["ex_2016_net_sharpe"] = brief.strategy.map(ex2016.net_sharpe)
    brief["worst_year"] = brief.strategy.map(worst.set_index("strategy")["year"])
    brief["worst_year_net_return"] = brief.strategy.map(worst.set_index("strategy").annual_net_return)
    same_rule = {
        "B00_BASE": "B00_BASE", "BOX_ORIGINAL": "B00_BASE",
        "A_LOW_NO_CARRY": "A_B00_LOW_NO_CARRY", "A_B00_LOW_NO_CARRY": "B00_BASE",
        "A_BOX_SHORT_GAMMA_050": "A_B00_SHORT_GAMMA_050",
        "A_BOX_SHORT_GAMMA_025": "A_B00_SHORT_GAMMA_025",
        "A_BOX_SHORT_GAMMA_000": "A_B00_SHORT_GAMMA_000",
        "A_B00_SHORT_GAMMA_050": "B00_BASE",
        "A_B00_SHORT_GAMMA_025": "B00_BASE",
        "A_B00_SHORT_GAMMA_000": "B00_BASE",
        "B_BOX_GATE_B00_SCORE": "B00_BASE", "B_BOX_GATE_RIDGE": "B00_BASE",
    }
    brief["same_rule_b00"] = brief.strategy.map(same_rule)
    brief["delta_net_sharpe_vs_same_rule_b00"] = [
        float(pooled.loc[name, "net_sharpe"] - pooled.loc[base, "net_sharpe"])
        for name, base in zip(brief.strategy, brief.same_rule_b00)
    ]
    brief["delta_net_return_vs_same_rule_b00"] = [
        float(pooled.loc[name, "annual_net_return"] - pooled.loc[base, "annual_net_return"])
        for name, base in zip(brief.strategy, brief.same_rule_b00)
    ]
    brief.to_csv(report_dir / "candidate_summary.csv", index=False)
    year_attribution.to_csv(report_dir / "category_by_year.csv", index=False)
    sector_bias.to_csv(report_dir / "sector_zero_tail_bias.csv", index=False)
    gamma_diag.to_csv(report_dir / "gamma_diagnostics.csv", index=False)
    gamma_diag.loc[gamma_diag.period.isin([str(year) for year in YEARS])].to_csv(
        report_dir / "gamma_fold_metrics.csv", index=False
    )

    audit_lines = [
        f"# {EXPERIMENT_ID} 現行ポートフォリオ監査", "",
        f"- Run: `{run_id}`; source run: `{SOURCE_RUN_ID}`; Train only; Valid / raw target 未読。",
        f"- 評価日: {current_audit['eval_start']}〜{current_audit['eval_end']}（{current_audit['eval_days']}日）。2016部分期間: {current_audit['2016_start']}〜{current_audit['2016_end']}（{current_audit['2016_days']}日）。",
        "- Score・Box event・side predictionはDM-20260925-03の保存parquet、公式Train targetと同日PIT sectorはTrain入力から取得。保存daily accountとの差は照合済み。",
        "- 五分位は `(Date, Code)` 順にscoreを `rank(method='first')`、公式evaluate_scriptと同じ `qcut(..., 5)`。したがって厳密な同点はCodeの文字列順で決まる。Tie-break零点はQ1/Q5のscore=0保有として切り出した。",
        "- イベント年齢の保有weight/P&LはEWMA残存source score絶対値で分配。Stock-daysには最大sourceを1件割り当て、fractional stock-daysも併記。Event attributionは実際の5分位保有内の記述帰属で、独立取引結果ではない。",
        "",
        "## 現行BOX・B00のポートフォリオ内容", "",
    ]
    key = brief.loc[brief.strategy.isin(["BOX_ORIGINAL", "B00_BASE", "A_LOW_NO_CARRY", "A_B00_LOW_NO_CARRY"])]
    audit_lines.append(markdown_table(
        key, ["strategy", "annual_net_return", "net_sharpe", "turnover_per_day", "q1_zero_stock_share", "q1_zero_gross_weight_share", "q5_zero_stock_share", "q5_zero_gross_weight_share", "zero_code_order_spearman_q", "zero_code_order_spanning_days"],
        ["Strategy", "Net年率", "Net SR", "Turnover/日", "Q1零点stock比", "Q1零点weight比", "Q5零点stock比", "Q5零点weight比", "0点Code順rho", "0点が複数分位の日"], 4,
    ))
    audit_lines += [
        "", "公式weight式ではQ1/Q2がShort、Q3は中立でweight 0、Q4/Q5がLong。Q1はShort側の最下位quintile、Q5はLong側の最上位quintile。`q1_zero_*` と `q5_zero_*` はscore=0のうち当該tailへCode順tie-breakで割り当てられたstock-day / gross weight比。Long/Short表の `score_zero_tail_tie_break` と `score_zero_non_tail_tie_break` はscore=0の実保有で、後者のうち内側quintileに入った保有も同じ `rank(method='first')` のCode順で割り当てられる。`zero_code_order_spearman_q` は複数quintileにまたがる日ごとに0点group内の辞書順ordinalとq番号の相関を求め、その日次平均を取った診断である。", "",
        "## Long / Short実保有の構成", "",
        "以下は実weightのうち、High/Lowのイベント年齢、score=0、その他が占めた割合。スコアゼロ銘柄もQ1/Q5へ選ばれれば実保有として数える。", "",
    ]
    for side in ("long", "short"):
        selected_attr = attribution.loc[
            attribution.strategy.isin(["BOX_ORIGINAL", "A_LOW_NO_CARRY", "B00_BASE", "A_B00_LOW_NO_CARRY"])
            & attribution.side.eq(side)
        ]
        audit_lines += [f"### {side.title()} sleeve", ""]
        audit_lines.append(markdown_table(
            selected_attr,
            ["strategy", "category", "held_stock_days_primary", "held_stock_days_fractional", "gross_weight_share_of_sleeve", "annual_gross_contribution", "annual_net_contribution", "turnover_share"],
            ["Strategy", "分類", "実stock-days", "配賦stock-days", f"{side.title()} gross weight比", "年率Gross寄与", "年率Net寄与", "Turnover比"], 4,
        ))
    audit_lines += [
        "", "## Q1/Q5 score-zero tie-breakと業種", "",
        "詳細な日次・銘柄内訳は `holdings_audit.parquet` に保存。Sector33は各Date/Codeの `listed_info_train` PIT値を使用した。次表は、実際にtailへ入ったscore=0銘柄の業種構成を、その同日のscore=0全体の業種構成と比べる。Sector33の上位偏り・不足は `sector_zero_tail_bias.csv` に全件保存。", "",
    ]
    short_attribution = attribution.loc[attribution.side.eq("short")]
    def short_share(strategy, categories):
        rows = short_attribution.loc[
            short_attribution.strategy.eq(strategy) & short_attribution.category.isin(categories)
        ]
        return float(rows.gross_weight_share_of_sleeve.sum())
    box_aged_low_share = short_share("BOX_ORIGINAL", ["low_age_1_4", "low_age_5_plus"])
    a_aged_low_share = short_share("A_LOW_NO_CARRY", ["low_age_1_4", "low_age_5_plus"])
    box_aged_high_share = short_share("BOX_ORIGINAL", ["high_age_1_4", "high_age_5_plus"])
    a_aged_high_share = short_share("A_LOW_NO_CARRY", ["high_age_1_4", "high_age_5_plus"])
    box_zero_tie_share = short_share("BOX_ORIGINAL", ["score_zero_tail_tie_break", "score_zero_non_tail_tie_break"])
    a_zero_tie_share = short_share("A_LOW_NO_CARRY", ["score_zero_tail_tie_break", "score_zero_non_tail_tie_break"])
    audit_lines.extend([
        f"A_LOW_NO_CARRYではLow残存Short weightが {box_aged_low_share:.1%}→{a_aged_low_share:.1%} になり、代わりにaged Highは {box_aged_high_share:.1%}→{a_aged_high_share:.1%}、score=0のCode順tie保有は {box_zero_tie_share:.1%}→{a_zero_tie_share:.1%} を占めた。Short枠は消えず、Q1のscore=0比率も上表のとおり増加している。", "",
    ])
    bias = sector_bias.loc[sector_bias.strategy.isin(["BOX_ORIGINAL", "A_LOW_NO_CARRY", "B00_BASE", "A_B00_LOW_NO_CARRY"])]
    bias = bias.assign(abs_delta=bias.sector_share_delta_vs_zero_pool.abs()).sort_values(
        ["strategy", "tail", "abs_delta"], ascending=[True, True, False]
    ).groupby(["strategy", "tail"], as_index=False).head(3)
    audit_lines.append(markdown_table(
        bias,
        ["strategy", "tail", "Sector33CodeName", "mean_daily_zero_pool_sector_share", "mean_daily_tail_zero_sector_share", "sector_share_delta_vs_zero_pool", "mean_daily_tail_zero_gross_weight_share", "annual_tail_zero_gross_pnl"],
        ["Strategy", "Tail", "Sector33", "0点全体比", "Tail 0点比", "差", "Tail gross weight比", "年率Gross P/L"], 4,
    ))
    audit_lines += [
        "",
        "0点tailのticker順が偏りを作る場合、同点処理だけで個別銘柄・業種・P&Lが固定される。今回の監査は実現した順序依存とその寄与を計測し、別tie-breakでの再運用は候補化していない。", "",
        "## 共通残差ドリフトと銘柄選択", "",
        "各日の同じ評価universeにおける公式市場残差target平均を共通成分とし、`valid weight exposure × universe mean` を共通寄与、残差差分をcross-sectional selection寄与とした。Long、Short、合計の和はGross P/Lと一致する。これは会計分解であり、共通因子の因果推定ではない。", "",
    ]
    common_rows = brief.loc[brief.strategy.isin([
        "BOX_ORIGINAL", "B00_BASE", "A_LOW_NO_CARRY", "A_B00_LOW_NO_CARRY",
        "B_BOX_GATE_B00_SCORE", "B_BOX_GATE_RIDGE",
    ])]
    audit_lines.append(markdown_table(
        common_rows,
        ["strategy", "annual_common_residual_component", "annual_selection_component", "annual_long_common_component", "annual_long_selection_component", "annual_short_common_component", "annual_short_selection_component", "annual_net_exposure_common_proxy"],
        ["Strategy", "Common Gross寄与", "Selection Gross寄与", "Long共通", "Long選択", "Short共通", "Short選択", "Net exposure×μ proxy"], 4,
    ))
    audit_lines += [
        "## Box eligibility coverage", "",
        f"評価期間のHighイベントは適格 {current_audit['eligible_high_events']:,} / {current_audit['eligible_high_events'] + current_audit['ineligible_high_events']:,}（不適格 {current_audit['ineligible_high_events']:,}, {current_audit['ineligible_high_events'] / (current_audit['eligible_high_events'] + current_audit['ineligible_high_events']):.1%}）、Lowイベントは適格 {current_audit['eligible_low_events']:,} / {current_audit['eligible_low_events'] + current_audit['ineligible_low_events']:,}（不適格 {current_audit['ineligible_low_events']:,}, {current_audit['ineligible_low_events'] / (current_audit['eligible_low_events'] + current_audit['ineligible_low_events']):.1%}）。B2/B3は不適格イベントを通さず、両raw scoreの非ゼロ行が同一適格イベント集合に一致することを実行時確認した。", "",
        "", "## 年別・fold別", "",
        "`fold_metrics.csv` は各yearを独立行として全指標を保存し、`category_by_year.csv` はBOX/Low-no-carry/B00のcategory別stock-days、gross weight、P/L、Turnoverを年/fold別に保存する。`annual_category_attribution.csv` は同じ区分のpooled年率。2016は上記の部分期間であり、月数を推測していない。", "",
        "## 再現・制約", "",
        f"- Saved-account replay max absolute discrepancy: {current_audit['saved_account_max_abs_error']:.3g}。公式qcut weightsと既存evaluation.weightsは完全一致。",
        f"- PIT sector join coverage: {current_audit['sector_join_coverage']:.2%}; duplicate sector keys: {current_audit['sector_duplicate_keys']}.",
        f"- B00 / BOX saved score replay: {current_audit['b00_saved_score_max_abs_error']:.3g} / saved BOX EWMA inversion: {current_audit['box_ewma_inversion_max_abs_error']:.3g}.",
        f"- Eligible-event prefix mutation/truncation: **{code_audit['status']}** at {len(code_audit['cutoffs'])} cutoffs; full details: `../artifacts/{EXPERIMENT_ID}/{run_id}/audit/prefix_invariance.json`.",
        "- Train期間は既読。Score-age attribution・common drift splitはいずれも記述診断で、独立OOSや将来期待値ではない。",
    ]
    (report_dir / "AUDIT.md").write_text("\n".join(audit_lines) + "\n", encoding="utf-8")

    result_lines = [
        f"# {EXPERIMENT_ID} Candidate A/B results", "",
        f"- Run: `{run_id}`; Train only; all Train periods already known; no Valid, Freeze, or submission evaluation.",
        "- All candidates use official target, five quintiles, 10 bps one-way transaction cost, annualization 252, and exact 2011–2016 annual folds with the last two signal dates purged.",
        "- 2016 is 2016-01-04 through 2016-03-29. `ex_2016` recomputes pooled metrics on all 2011–2015 evaluation days.",
        "- Gamma rows preserve original quintile identities and scale negative weights only; turnover is recomputed from those scaled daily weights. Gamma < 1 rows are non-official operating rules, not official five-quintile strategies.",
        "- Full precision and all required year/fold diagnostics are in `candidate_summary.csv`, `period_metrics.csv`, and `fold_metrics.csv`. Candidate A/B score trials retain official five-quintile normalization; gamma<1 diagnostics do not.", "",
        "## Fixed-candidate comparison", "",
    ]
    result_lines.append(markdown_table(
        brief,
        ["strategy", "annual_gross_return", "annual_net_return", "annualized_net_volatility", "gross_sharpe", "net_sharpe", "turnover_per_day", "annualized_cost", "ex_2016_net_sharpe", "worst_year", "worst_year_net_return", "delta_net_sharpe_vs_same_rule_b00", "delta_net_return_vs_same_rule_b00"],
        ["Strategy", "Gross年率", "Net年率", "Vol", "Gross SR", "Net SR", "Turnover/日", "Cost年率", "ex-2016 SR", "worst year", "worst年Net", "ΔSR vs同ルールB00", "ΔNet vs同ルールB00"], 4,
    ))
    result_lines += ["", "## Fold / year performance", "", "全12条件の年別指標は `fold_metrics.csv` に保存。2016行は部分期間。以下はNet SR、Net年率、cost、turnoverの比較表。", ""]
    result_lines.append(markdown_table(
        folds,
        ["year", "strategy", "annual_net_return", "net_sharpe", "annualized_cost", "turnover_per_day", "annual_common_residual_component", "annual_selection_component"],
        ["Year", "Strategy", "Net年率", "Net SR", "Cost", "Turnover", "Common", "Selection"], 4,
    ))
    result_lines += ["", "## Same-rule B00 differences and paired bootstrap", "", "Bootstrapは既存実装の20日circular paired block、1,000回、seed 20260925を固定して再利用。区間は記述的で、既読Trainの不確実性評価である。", ""]
    result_lines.append(markdown_table(
        comparisons,
        ["candidate", "baseline", "delta_net_sharpe", "delta_annual_net_return", "paired_delta_net_sharpe_ci_low", "paired_delta_net_sharpe_ci_high", "bootstrap_positive_fraction"],
        ["Candidate", "Baseline", "ΔNet SR", "ΔNet年率", "Bootstrap CI low", "Bootstrap CI high", "正差比率"], 4,
    ))
    result_lines += ["", "## Candidate B interpretation", "", "B1→B2はeligible Box gate自体、B2→B3は同一イベント集合でのRidge順位付けを比較する。B2/B3は `box_duration > 0`、有限の `box_width_atr < 3.0` に限り、Box欠落イベントを平均補完して通していない。", ""]
    b_rows = brief.loc[brief.strategy.isin(["B00_BASE", "B_BOX_GATE_B00_SCORE", "B_BOX_GATE_RIDGE"])]
    result_lines.append(markdown_table(
        b_rows,
        ["strategy", "annual_net_return", "net_sharpe", "ex_2016_net_sharpe", "q1_zero_stock_share", "q5_zero_stock_share", "nonzero_score_ratio", "average_gross_exposure", "average_net_exposure"],
        ["Candidate", "Net年率", "Net SR", "ex-2016 SR", "Q1 0点比", "Q5 0点比", "Nonzero率", "Gross exposure", "Net exposure"], 4,
    ))
    result_lines += ["", "## Gamma exposure diagnosis", "", "同じgammaでのBOX/B00比較はすべてNon-official weight rule。gamma=1はB00_BASE / BOX_ORIGINALとして載せた。Net SR変化をnet long exposure、common residual drift、selection成分、分散、costに分けた。2016を含むfullと2016除外を以下に示し、年/fold全列は `gamma_fold_metrics.csv` に保存。", ""]
    gamma_brief = gamma_diag.loc[gamma_diag.period.isin(["full_train_eval", "ex_2016"])].copy()
    gamma_brief["rule"] = gamma_brief.strategy.map({"B00_BASE": "B00", "BOX_ORIGINAL": "BOX"})
    gamma_brief.loc[gamma_brief.strategy.str.startswith("A_BOX"), "rule"] = "BOX"
    gamma_brief.loc[gamma_brief.strategy.str.startswith("A_B00"), "rule"] = "B00"
    gamma_brief = gamma_brief.sort_values(["period", "gamma", "rule"], ascending=[True, False, True])
    result_lines.append(markdown_table(
        gamma_brief,
        ["rule", "gamma", "period", "annual_gross_return", "annual_net_return", "annualized_net_volatility", "gross_sharpe", "net_sharpe", "turnover_per_day", "annualized_cost", "average_gross_exposure", "average_net_exposure", "annual_common_residual_component", "annual_selection_component", "annual_long_net", "annual_short_net"],
        ["Rule", "γ", "Period", "Gross年率", "Net年率", "Vol", "Gross SR", "Net SR", "Turnover", "Cost", "Gross exp", "Net exp", "Common", "Selection", "Long Net", "Short Net"], 4,
    ))
    result_lines += ["", "GammaでSharpeが上がる場合も、BOX固有差と同じ倍率のB00差を区別する。", ""]
    result_lines += [
        "## Reproducibility", "",
        f"- Source report/run: `reports/{SOURCE_EXPERIMENT_ID}/REPORT.md`, `{SOURCE_RUN_ID}`.",
        f"- Git HEAD: `{source_metadata['git_commit_hash']}`; worktree dirty: `{source_metadata['git_worktree_dirty']}`.",
        f"- Config snapshot: `artifacts/{EXPERIMENT_ID}/{run_id}/config.json`; run metadata: `artifacts/{EXPERIMENT_ID}/{run_id}/run.json`.",
        f"- Score/weight outputs: `artifacts/{EXPERIMENT_ID}/{run_id}/predictions/`.",
    ]
    (report_dir / "EXPERIMENT_RESULTS.md").write_text("\n".join(result_lines) + "\n", encoding="utf-8")

    box = pooled.loc["BOX_ORIGINAL"]
    b00 = pooled.loc["B00_BASE"]
    a_box = pooled.loc["A_LOW_NO_CARRY"]
    a_b00 = pooled.loc["A_B00_LOW_NO_CARRY"]
    ex_box = ex2016.loc["BOX_ORIGINAL"]
    ex_a_box = ex2016.loc["A_LOW_NO_CARRY"]
    delta_a = float(a_box.net_sharpe - box.net_sharpe)
    delta_a_ex = float(ex_a_box.net_sharpe - ex_box.net_sharpe)
    delta_b00 = float(a_b00.net_sharpe - b00.net_sharpe)
    a_weak = folds.loc[
        folds.strategy.isin(["BOX_ORIGINAL", "A_LOW_NO_CARRY", "B00_BASE", "A_B00_LOW_NO_CARRY"])
        & folds.year.isin([2011, 2015])
    ]
    a_weak_idx = a_weak.set_index(["strategy", "year"])
    weak_ok = all(
        a_weak_idx.loc[(a, year), "annual_net_return"] >= a_weak_idx.loc[(b, year), "annual_net_return"]
        for a, b in (("A_LOW_NO_CARRY", "BOX_ORIGINAL"), ("A_B00_LOW_NO_CARRY", "B00_BASE"))
        for year in (2011, 2015)
    )
    selection_delta = float(a_box.annual_selection_component - box.annual_selection_component)
    common_delta = float(a_box.annual_common_residual_component - box.annual_common_residual_component)
    continue_a = (
        delta_a > 0.0 and delta_a_ex > 0.0 and delta_b00 > 0.0 and weak_ok
        and selection_delta > 0.0 and not (common_delta > 0.0 and selection_delta <= 0.0)
    )
    b2 = pooled.loc["B_BOX_GATE_B00_SCORE"]
    b3 = pooled.loc["B_BOX_GATE_RIDGE"]
    b2_ex = ex2016.loc["B_BOX_GATE_B00_SCORE"]
    b3_ex = ex2016.loc["B_BOX_GATE_RIDGE"]
    gate_value = bool(
        b2.net_sharpe > b00.net_sharpe and b2.annual_net_return > b00.annual_net_return
        and b2_ex.net_sharpe > ex2016.loc["B00_BASE", "net_sharpe"]
    )
    ridge_value = bool(
        b3.net_sharpe > b2.net_sharpe and b3.annual_net_return > b2.annual_net_return
        and b3_ex.net_sharpe > b2_ex.net_sharpe
    )
    gamma_box_0 = pooled.loc["A_BOX_SHORT_GAMMA_000"]
    gamma_b00_0 = pooled.loc["A_B00_SHORT_GAMMA_000"]
    gamma_box_0_ex = ex2016.loc["A_BOX_SHORT_GAMMA_000"]
    gamma_b00_0_ex = ex2016.loc["A_B00_SHORT_GAMMA_000"]
    gamma_common_delta = float(gamma_box_0.annual_common_residual_component - box.annual_common_residual_component)
    gamma_selection_delta = float(gamma_box_0.annual_selection_component - box.annual_selection_component)
    gamma_net_exposure_delta = float(gamma_box_0.average_net_exposure - box.average_net_exposure)
    gamma_box_050 = pooled.loc["A_BOX_SHORT_GAMMA_050"]
    gamma_box_025 = pooled.loc["A_BOX_SHORT_GAMMA_025"]
    gamma_exposure_rows = [gamma_box_050, gamma_box_025, gamma_box_0]
    a_cost_delta = float(a_box.annualized_cost - box.annualized_cost)
    a_turn_delta = float(a_box.turnover_per_day - box.turnover_per_day)
    decision_lines = [
        f"# {EXPERIMENT_ID} Decision", "",
        "All comparisons use Train periods already reviewed. These labels summarize fixed descriptive diagnostics and do not imply independent OOS validation.", "",
        "### 1. Current BOX", "",
        "- **Reject** as the current B00 alternative.",
        f"- BOX Net SR {box.net_sharpe:.4f}, annual Net {box.annual_net_return:+.2%}; B00 Net SR {b00.net_sharpe:.4f}, annual Net {b00.annual_net_return:+.2%}. The current candidate does not establish an incremental Box/Ridge advantage. Tie and Short attribution are in `AUDIT.md`.", "",
        "### 2. Candidate A", "",
        f"- **{'Continue' if continue_a else 'Stop'}** under the predeclared descriptive criteria.",
        f"- BOX Low-no-carry ΔNet SR vs current BOX: {delta_a:+.4f}; ex-2016 ΔNet SR: {delta_a_ex:+.4f}. Same rule on B00 ΔNet SR vs B00: {delta_b00:+.4f}.",
        f"- BOX annual selection-component change: {selection_delta:+.3%}; common-residual component change: {common_delta:+.3%}; weak-year nondegradation check (2011/2015, BOX and B00): {weak_ok}.",
        f"- Low carry stop raises turnover by {a_turn_delta:+.5f}/day and annual cost by {a_cost_delta:+.2%}; Q1 zero-score gross-weight share moves {box.q1_zero_gross_weight_share:.1%}→{a_box.q1_zero_gross_weight_share:.1%}. Total Short score-zero/code-order tie weight moves {box_zero_tie_share:.1%}→{a_zero_tie_share:.1%}; actual Short positions remain. This candidate worsens Net SR and is strongly exposed to code-order tie-breaks.",
        f"- Separate non-official gamma diagnostics reach BOX Net SR {pooled.loc['A_BOX_SHORT_GAMMA_050', 'net_sharpe']:.3f}/{pooled.loc['A_BOX_SHORT_GAMMA_025', 'net_sharpe']:.3f}/{gamma_box_0.net_sharpe:.3f} at γ=.50/.25/0; same-rule B00 is {pooled.loc['A_B00_SHORT_GAMMA_050', 'net_sharpe']:.3f}/{pooled.loc['A_B00_SHORT_GAMMA_025', 'net_sharpe']:.3f}/{gamma_b00_0.net_sharpe:.3f}. At γ=0, B00 is slightly better; both ex-2016 Sharpe are below 1 ({gamma_box_0_ex.net_sharpe:.3f} BOX, {gamma_b00_0_ex.net_sharpe:.3f} B00). BOX γ=0 net exposure change is {gamma_net_exposure_delta:+.2%}, common-component change {gamma_common_delta:+.2%}, and selection-component change {gamma_selection_delta:+.2%} vs BOX original. The apparent Sharpe gain is not Box-specific and includes greater net-long/common-drift exposure plus lower Short loss/cost.",
        f"- Cause split for BOX γ=.50/.25/0: net exposure {gamma_exposure_rows[0].average_net_exposure:+.1%}/{gamma_exposure_rows[1].average_net_exposure:+.1%}/{gamma_exposure_rows[2].average_net_exposure:+.1%}; common component {gamma_exposure_rows[0].annual_common_residual_component:+.2%}/{gamma_exposure_rows[1].annual_common_residual_component:+.2%}/{gamma_exposure_rows[2].annual_common_residual_component:+.2%}; selection {gamma_exposure_rows[0].annual_selection_component:+.2%}/{gamma_exposure_rows[1].annual_selection_component:+.2%}/{gamma_exposure_rows[2].annual_selection_component:+.2%}; Net vol {gamma_exposure_rows[0].annualized_net_volatility:.2%}/{gamma_exposure_rows[1].annualized_net_volatility:.2%}/{gamma_exposure_rows[2].annualized_net_volatility:.2%} vs BOX {box.annualized_net_volatility:.2%}; annual cost {gamma_exposure_rows[0].annualized_cost:.2%}/{gamma_exposure_rows[1].annualized_cost:.2%}/{gamma_exposure_rows[2].annualized_cost:.2%} vs BOX {box.annualized_cost:.2%}. At γ=0 the Short contribution falls from {box.annual_short_net:+.2%} to {gamma_box_0.annual_short_net:+.2%}; same-rule B00 has higher full-period Net SR at every gamma < 1.",
        "- Net SR >= 1 in a non-official gamma sleeve rule alone is not an adoption rule.",
        "- `A_LOW_NO_CARRY` and `A_B00_LOW_NO_CARRY` use official five-quintile weights. All gamma<1 descendants are separate non-official short-scaled operating rules.", "",
        "### 3. Candidate B", "",
        f"- Box condition: **{'Box condition adds a possible pooled point-estimate value' if gate_value else 'no evidence that the Box condition adds value'}**. B2−B1 Net SR {b2.net_sharpe-b00.net_sharpe:+.4f}; annual Net return difference {b2.annual_net_return-b00.annual_net_return:+.3%}; ex-2016 Sharpe difference {b2_ex.net_sharpe-ex2016.loc['B00_BASE', 'net_sharpe']:+.4f}. The net-return point difference is small, gross return is lower, only {int((folds.loc[folds.strategy.eq('B_BOX_GATE_B00_SCORE'), 'net_sharpe'].to_numpy() > folds.loc[folds.strategy.eq('B00_BASE'), 'net_sharpe'].to_numpy()).sum())}/6 yearly folds improve, and the paired bootstrap interval includes zero; treat it as weak, mixed Train evidence.",
        f"- Ridge ranking: **{'Ridge adds value (Train descriptive evidence)' if ridge_value else 'no evidence that Ridge adds value'}**. B3−B2 Net SR {b3.net_sharpe-b2.net_sharpe:+.4f}; ex-2016 difference {b3_ex.net_sharpe-b2_ex.net_sharpe:+.4f}.",
        "- These comparisons use the same eligible event set for B2/B3 and are not independent OOS proof.", "",
        "### 4. Next action", "",
    ]
    if continue_a:
        decision_lines.append("- One action: retain High/Low asymmetric holding as the sole future research hypothesis; stop Box threshold/window exploration. No Valid access or implementation change is authorized by this Train-only result.")
    elif gate_value:
        decision_lines.append("- One action: record eligible-Box gating as a possible hypothesis without adding windows/thresholds; stop this fixed Train series. No Valid access or parameter search.")
    else:
        decision_lines.append("- One action: end this BOX series and retain the audit/results; add no candidate or parameter search.")
    (report_dir / "DECISION.md").write_text("\n".join(decision_lines) + "\n", encoding="utf-8")
    return brief


def run(config_path, output_path):
    started = time.monotonic()
    config_path = Path(config_path)
    output = Path(output_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    expected_ids = [item["trial_id"] for item in config.get("trials", [])]
    if (config.get("experiment_id") != EXPERIMENT_ID or config.get("data_split") != "train"
            or config.get("valid_evaluation") is not False or config.get("selection_eligible") is not False
            or config.get("max_trials") != len(TRIAL_IDS) or tuple(expected_ids) != TRIAL_IDS
            or tuple(config.get("parameters", {}).get("short_scale_gamma", ())) != GAMMAS):
        raise ValueError("Run config differs from the pre-registered fixed experiment")
    for subdir in ("models", "predictions", "metrics", "audit", "logs"):
        (output / subdir).mkdir(parents=True, exist_ok=True)
    run_path = output / "run.json"
    metadata = json.loads(run_path.read_text(encoding="utf-8"))
    worktree = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, check=True, capture_output=True, text=True).stdout
    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    source_paths = [
        Path(__file__).resolve(), Path(features.__file__).resolve(), Path(bidirectional.__file__).resolve(),
        Path(b00_models.__file__).resolve(), Path(evaluation.__file__).resolve(), Path(firewall.__file__).resolve(),
    ]
    metadata.update({
        "status": "running", "started_at_utc": now_utc(), "command": sys.argv,
        "actual_trials": 0, "git_commit_hash": git_head, "git_worktree_dirty": bool(worktree),
        "source_run_id": SOURCE_RUN_ID,
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "numpy": np.__version__, "pandas": pd.__version__},
        "code_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in source_paths},
        "source_artifact_sha256": {str(path.relative_to(ROOT)): sha256(path)
                                    for path in (SOURCE_SIGNALS, SOURCE_EVENTS, SOURCE_BOX)},
        "cost_oneway": ONE_WAY_COST, "annualization": ANNUALIZATION,
        "parameter_values": config["parameters"],
    })
    dump(run_path, metadata)
    try:
        firewall.install(allowed_artifacts=(SOURCE_SIGNALS, SOURCE_EVENTS, SOURCE_BOX))
        data_dir = ROOT / "stock_comp_2026" / "input"
        data_hashes = {
            f"{name}_train.parquet": sha256(data_dir / f"{name}_train.parquet")
            for name in features.INPUT_COLUMNS
        }
        data_hashes["target_1day_train.parquet"] = sha256(data_dir / "target_1day_train.parquet")
        data_hashes["listed_info_train.parquet"] = sha256(data_dir / "listed_info_train.parquet")
        metadata["train_data_sha256"] = data_hashes
        dump(run_path, metadata)

        print("[1/7] Load saved score artifacts and Train-only inputs...", flush=True)
        saved = pd.read_parquet(SOURCE_SIGNALS).sort_index()
        saved_events = pd.read_parquet(SOURCE_EVENTS).sort_index()
        saved_box = pd.read_parquet(SOURCE_BOX).sort_index()
        inputs = features.load_inputs(data_dir, split="train")
        target = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index().rename("Return")
        x = features.build_features(inputs)
        if not x.index.equals(target.index) or not x.index.equals(saved.index):
            raise AssertionError("Saved score, feature, and official Train target indexes differ")
        dates = x.index.get_level_values("Date")
        calendar = pd.DatetimeIndex(dates.unique().sort_values())
        if str(calendar.min().date()) != "2008-11-04" or str(calendar.max().date()) != "2016-03-31":
            raise AssertionError("Unexpected Train date span")
        source_daily = {}
        source_accounts = {}
        for name in ("B00", "BOX_BIDIR_STANDALONE"):
            source_daily[name] = evaluation.daily_account(saved[name], target)
            source_accounts[name] = pd.read_csv(
                SOURCE_RUN / "metrics" / f"daily_account_{name}.csv", parse_dates=["Date"], index_col="Date"
            )
            common = source_daily[name].index.intersection(source_accounts[name].index)
            cols = [column for column in ("gross", "net", "turnover", "rankic")
                    if column in source_daily[name] and column in source_accounts[name]]
            for column in cols:
                err = float((source_daily[name].loc[common, column] - source_accounts[name].loc[common, column]).abs().max())
                if err > 1e-10:
                    raise AssertionError(f"Saved account replay mismatch for {name}.{column}: {err}")

        print("[2/7] Reconstruct exact quintiles, source components, and fixed signals...", flush=True)
        scan_files = static_source_scan()
        baseline_score = b00_models.generate_base_signal(x, alpha=ALPHA).rename("B00_BASE")
        b00_replay_err = float((baseline_score - saved["B00"]).abs().max())
        if b00_replay_err > 1e-12:
            raise AssertionError(f"Saved B00 score replay mismatch: {b00_replay_err}")
        box_raw, box_inverse_err = inverse_ewma(saved["BOX_BIDIR_STANDALONE"].rename("BOX"), ALPHA)
        box_high_raw, box_low_raw = split_raw_sides(box_raw)
        box_components = event_age_components(box_high_raw, box_low_raw, ALPHA)
        b00_raw = b00_models.raw_base_signal(x).rename("B00_raw")
        b00_high_raw, b00_low_raw = split_raw_sides(b00_raw)
        b00_components = event_age_components(b00_high_raw, b00_low_raw, ALPHA)
        a_box_score = asymmetric_score_from_raw(box_raw, ALPHA, "A_LOW_NO_CARRY")
        a_b00_score = asymmetric_score_from_raw(b00_raw, ALPHA, "A_B00_LOW_NO_CARRY")
        box_age_error = float((box_components.sum(axis=1) - saved["BOX_BIDIR_STANDALONE"]).abs().max())
        b00_age_error = float((b00_components.sum(axis=1) - saved["B00"]).abs().max())
        if max(box_age_error, b00_age_error) > 2e-12:
            raise AssertionError(f"Event-age sources do not reconstruct saved scores: {box_age_error}, {b00_age_error}")

        eligible = eligible_box_mask(x)
        high_event = bidirectional.event_mask(x, "high")
        low_event = bidirectional.event_mask(x, "low")
        b2_score, b3_score, b2_raw, b3_raw, ridge_records, ridge_predictions = build_gate_scores(
            x, eligible, target, model_dir=output / "models"
        )

        score_series = {
            "B00_BASE": saved["B00"].rename("B00_BASE"),
            "BOX_ORIGINAL": saved["BOX_BIDIR_STANDALONE"].rename("BOX_ORIGINAL"),
            "A_LOW_NO_CARRY": a_box_score,
            "A_B00_LOW_NO_CARRY": a_b00_score,
            "B_BOX_GATE_B00_SCORE": b2_score,
            "B_BOX_GATE_RIDGE": b3_score,
        }
        for name, score in score_series.items():
            if not score.index.equals(x.index) or not np.isfinite(score.to_numpy()).all():
                raise AssertionError(f"Invalid or incomplete scores for {name}")
        signals = pd.DataFrame(score_series, index=x.index)

        print("[3/7] Audit zero-score tie ordering and PIT sectors...", flush=True)
        index = x.index
        listed = pd.read_parquet(
            data_dir / "listed_info_train.parquet",
            columns=["Sector33Code", "Sector33CodeName", "Sector17Code", "Sector17CodeName"],
        ).sort_index()
        if not listed.index.is_unique:
            raise AssertionError("listed_info_train has duplicate PIT (Date, Code) keys")
        sector = listed.reindex(index)
        sector_coverage = float(sector["Sector33Code"].notna().mean())
        if sector_coverage < 0.95:
            raise AssertionError(f"Unexpectedly low same-day PIT sector coverage: {sector_coverage:.2%}")

        # Prove the five equal-sized score buckets equal evaluate_script's qcut result.
        specs = {}
        for name in ("B00_BASE", "BOX_ORIGINAL", "A_LOW_NO_CARRY", "A_B00_LOW_NO_CARRY"):
            score = score_series[name]
            weights, q = quintile_weights(score)
            specs[name] = (score, weights, q)
        gamma_specs = {}
        # Gamma 1.00 is already represented by the official BOX/B00 baselines.
        for base_name, prefix in (("BOX_ORIGINAL", "A_BOX"), ("B00_BASE", "A_B00")):
            for gamma in GAMMAS[1:]:
                suffix = f"{int(gamma * 100):03d}"
                score, base_weight, q = specs[base_name]
                gamma_name = f"{prefix}_SHORT_GAMMA_{suffix}"
                gamma_specs[gamma_name] = (score, scale_short(base_weight, gamma), q)
        specs.update(gamma_specs)
        specs["B_BOX_GATE_B00_SCORE"] = (b2_score, *quintile_weights(b2_score))
        specs["B_BOX_GATE_RIDGE"] = (b3_score, *quintile_weights(b3_score))
        if tuple(specs) != TRIAL_IDS:
            # Dict order is intentionally checked to keep output order and config auditable.
            raise AssertionError(f"Unexpected candidate order: {tuple(specs)}")

        eval_source = source_daily["B00"].index
        eval_dates = official_eval_dates(eval_source)
        expected_span = ("2011-01-04", "2016-03-29")
        if (str(eval_dates.min().date()), str(eval_dates.max().date())) != expected_span:
            raise AssertionError(f"Unexpected evaluation span: {eval_dates.min()} to {eval_dates.max()}")
        eval_2016 = eval_dates[eval_dates.year == 2016]
        if (str(eval_2016.min().date()), str(eval_2016.max().date())) != ("2016-01-04", "2016-03-29"):
            raise AssertionError("Unexpected exact 2016 partial fold span")
        eval_rows = dates.isin(eval_dates)
        expected_gate_events = ((high_event | low_event) & eligible).loc[eval_rows].to_numpy()
        if not np.array_equal(b2_raw.loc[eval_rows].ne(0.0).to_numpy(), expected_gate_events):
            raise AssertionError("B2 raw nonzero rows do not equal eligible High/Low event set")
        if not np.array_equal(b3_raw.loc[eval_rows].ne(0.0).to_numpy(), expected_gate_events):
            raise AssertionError("B3 raw nonzero rows do not equal the exact B2 eligible event set")
        pd.testing.assert_frame_equal(
            saved_box, x.loc[saved_box.index, saved_box.columns], check_exact=True
        )
        for side in bidirectional.SIDES:
            actual_event = bidirectional.event_mask(x, side).reindex(saved_events.index)
            pd.testing.assert_series_equal(
                saved_events[f"{side}_event"].astype(bool), actual_event.astype(bool), check_exact=True,
                check_names=False,
            )

        print("[4/7] Run eligible-event B3 mutation/truncation prefix checks...", flush=True)
        prefix = gate_prefix_audit(inputs, target, x, eligible, b2_score, b3_score)
        prefix["source_scan"] = scan_files
        dump(output / "audit/prefix_invariance.json", prefix)

        print("[5/7] Compute fixed 12-trial official and non-official accounts...", flush=True)
        summary, daily_accounts, turnovers, weight_store, q_store = trial_metric_sets(
            specs, target, sector, eval_dates
        )
        # The source report's exact saved-account values must remain reproducible.
        replay_max = 0.0
        for name, source_name in (("B00_BASE", "B00"), ("BOX_ORIGINAL", "BOX_BIDIR_STANDALONE")):
            current = daily_accounts[name]
            source = source_accounts[source_name].loc[source_accounts[source_name].index.isin(eval_dates)]
            for col in ("gross", "net", "turnover", "rankic"):
                if col in source:
                    err = float((current[col].reindex(source.index) - source[col]).abs().max())
                    replay_max = max(replay_max, err)
                    if err > 1e-10:
                        raise AssertionError(f"Current account no longer reproduces {source_name}.{col}: {err}")

        rows = []
        for name in TRIAL_IDS:
            daily = daily_accounts[name]
            periods = [("full_train_eval", daily.index),
                       ("ex_2016", daily.index[daily.index.year != 2016])]
            periods.extend((str(year), daily.index[daily.index.year == year]) for year in YEARS)
            for period, ix in periods:
                if len(ix):
                    rows.append(stat_record(
                        name, period, specs[name][0], specs[name][1], specs[name][2],
                        daily.loc[daily.index.isin(ix)], target, sector,
                    ))
        summary = pd.DataFrame(rows)
        full = summary.loc[summary.period.eq("full_train_eval")].copy()
        folds = summary.loc[summary.period.isin([str(y) for y in YEARS])].copy()
        folds["year"] = folds["period"].astype(int)
        gamma_diag = gamma_diagnostics(summary)
        comparisons = bootstrap_comparisons(daily_accounts, {
            "BOX_ORIGINAL": "B00_BASE",
            "A_LOW_NO_CARRY": "A_B00_LOW_NO_CARRY",
            "A_B00_LOW_NO_CARRY": "B00_BASE",
            "A_BOX_SHORT_GAMMA_050": "A_B00_SHORT_GAMMA_050",
            "A_BOX_SHORT_GAMMA_025": "A_B00_SHORT_GAMMA_025",
            "A_BOX_SHORT_GAMMA_000": "A_B00_SHORT_GAMMA_000",
            "A_B00_SHORT_GAMMA_050": "B00_BASE",
            "A_B00_SHORT_GAMMA_025": "B00_BASE",
            "A_B00_SHORT_GAMMA_000": "B00_BASE",
            "B_BOX_GATE_B00_SCORE": "B00_BASE",
            "B_BOX_GATE_RIDGE": "B00_BASE",
        })
        comparisons.to_csv(output / "metrics/paired_comparisons.csv", index=False)
        summary.to_csv(output / "metrics/period_metrics.csv", index=False)
        folds.to_csv(output / "metrics/fold_metrics.csv", index=False)
        full.to_csv(output / "metrics/candidate_summary.csv", index=False)

        print("[6/7] Build daily stock holdings and category attribution...", flush=True)
        audit_specs = {
            "BOX_ORIGINAL": (saved["BOX_BIDIR_STANDALONE"].rename("BOX_ORIGINAL"), specs["BOX_ORIGINAL"][1], specs["BOX_ORIGINAL"][2], box_components),
            "B00_BASE": (saved["B00"].rename("B00_BASE"), specs["B00_BASE"][1], specs["B00_BASE"][2], b00_components),
        }
        # Candidate A components retain all High ages and only the event-day Low component.
        a_box_components = pd.DataFrame({
                "high_event_day": box_components["high_event_day"],
                "high_age_1_4": box_components["high_age_1_4"],
                "high_age_5_plus": box_components["high_age_5_plus"],
                "low_event_day": box_components["low_event_day"],
                "low_age_1_4": pd.Series(0.0, index=index),
                "low_age_5_plus": pd.Series(0.0, index=index),
            }, index=index)
        a_b00_components = pd.DataFrame({
                "high_event_day": b00_components["high_event_day"],
                "high_age_1_4": b00_components["high_age_1_4"],
                "high_age_5_plus": b00_components["high_age_5_plus"],
                "low_event_day": b00_components["low_event_day"],
                "low_age_1_4": pd.Series(0.0, index=index),
                "low_age_5_plus": pd.Series(0.0, index=index),
            }, index=index)
        a_box_error = float((a_box_components.sum(axis=1) - a_box_score).abs().max())
        a_b00_error = float((a_b00_components.sum(axis=1) - a_b00_score).abs().max())
        if max(a_box_error, a_b00_error) > 2e-12:
            raise AssertionError(f"Candidate A event-age sources do not reconstruct score: {a_box_error}, {a_b00_error}")
        audit_specs["A_LOW_NO_CARRY"] = (
            a_box_score, specs["A_LOW_NO_CARRY"][1], specs["A_LOW_NO_CARRY"][2], a_box_components,
        )
        audit_specs["A_B00_LOW_NO_CARRY"] = (
            a_b00_score, specs["A_B00_LOW_NO_CARRY"][1], specs["A_B00_LOW_NO_CARRY"][2], a_b00_components,
        )
        attr_tables, daily_attr_tables, details = [], [], []
        sector_records = []
        for name, (score, weights, q, components) in audit_specs.items():
            table, daytable, _ = attribution_tables(name, score, weights, q, components, target, eval_dates)
            attr_tables.append(table)
            daily_attr_tables.append(daytable)
            details.append(build_audit_detail(score, weights, q, components, sector, eval_dates).assign(strategy=name))
            sector_records.extend(sector_outputs(name, score, weights, q, sector))
        attribution = pd.concat(attr_tables, ignore_index=True)
        daily_attribution = pd.concat(daily_attr_tables, ignore_index=True)
        detail = pd.concat(details).sort_index()
        sector_composition = pd.DataFrame(sector_records)
        year_attribution = yearly_category_attribution(detail, daily_attribution)
        sector_bias = zero_sector_bias(detail, target)
        attribution.to_csv(output / "metrics/annual_category_attribution.csv", index=False)
        daily_attribution.to_csv(output / "metrics/daily_category_attribution.csv", index=False)
        sector_composition.to_csv(output / "metrics/sector_tail_composition.csv", index=False)
        year_attribution.to_csv(output / "metrics/category_by_year.csv", index=False)
        sector_bias.to_csv(output / "metrics/sector_zero_tail_bias.csv", index=False)
        gamma_diag.to_csv(output / "metrics/gamma_diagnostics.csv", index=False)
        gamma_diag.loc[gamma_diag.period.isin([str(year) for year in YEARS])].to_csv(
            output / "metrics/gamma_fold_metrics.csv", index=False
        )
        detail.to_parquet(output / "predictions/holdings_audit.parquet")

        eval_mask = dates.isin(eval_dates)
        score_eval = signals.loc[eval_mask].copy()
        score_eval.to_parquet(output / "predictions/strategy_scores.parquet")
        weight_eval = pd.DataFrame({name: weights.reindex(score_eval.index) for name, weights in weight_store.items()})
        weight_eval.to_parquet(output / "predictions/portfolio_weights.parquet")
        event_eval = pd.DataFrame({
            "eligible_box": eligible.loc[eval_mask],
            "high_event": high_event.loc[eval_mask],
            "low_event": low_event.loc[eval_mask],
        }, index=x.index[eval_mask])
        event_eval.to_parquet(output / "predictions/event_masks.parquet")
        for name, daily in daily_accounts.items():
            daily.to_csv(output / f"metrics/daily_account_{name}.csv", index_label="Date")

        # Concise diagnostics for reports and metadata.
        current_zero_box = full.loc[full.strategy.eq("BOX_ORIGINAL")].iloc[0]
        current_audit = {
            "eval_start": str(eval_dates.min().date()),
            "eval_end": str(eval_dates.max().date()),
            "eval_days": int(len(eval_dates)),
            "2016_start": str(eval_2016.min().date()),
            "2016_end": str(eval_2016.max().date()),
            "2016_days": int(len(eval_2016)),
            "saved_account_max_abs_error": replay_max,
            "b00_saved_score_max_abs_error": b00_replay_err,
            "box_ewma_inversion_max_abs_error": box_inverse_err,
            "sector_join_coverage": sector_coverage,
            "sector_duplicate_keys": int(listed.index.duplicated().sum()),
            "box_zero_q1_stock_share": float(current_zero_box.q1_zero_stock_share),
            "box_zero_q5_stock_share": float(current_zero_box.q5_zero_stock_share),
            "eligible_high_events": int((high_event & eligible & dates.isin(eval_dates)).sum()),
            "eligible_low_events": int((low_event & eligible & dates.isin(eval_dates)).sum()),
            "ineligible_high_events": int((high_event & ~eligible & dates.isin(eval_dates)).sum()),
            "ineligible_low_events": int((low_event & ~eligible & dates.isin(eval_dates)).sum()),
            "saved_box_feature_replay": "PASS",
            "saved_event_mask_replay": "PASS",
        }
        dump(output / "audit/current_audit.json", current_audit)
        dump(output / "audit/firewall.json", {"status": "PASS", "opened_parquets": sorted(firewall.ACCESSES),
                                                "valid_evaluation": False, "raw_target_reads": False})
        source_metadata = {"git_commit_hash": git_head, "git_worktree_dirty": bool(worktree)}
        report_dir = ROOT / "reports" / EXPERIMENT_ID
        brief = write_reports(report_dir, output.name, source_metadata, current_audit, summary,
                              folds, summary, comparisons, attribution, year_attribution,
                              sector_bias, gamma_diag, prefix)
        # Duplicate year rows into reports for direct review from the report folder.
        summary.to_csv(report_dir / "period_metrics.csv", index=False)
        folds.to_csv(report_dir / "fold_metrics.csv", index=False)
        attribution.to_csv(report_dir / "annual_category_attribution.csv", index=False)
        year_attribution.to_csv(report_dir / "category_by_year.csv", index=False)
        daily_attribution.to_csv(report_dir / "daily_category_attribution.csv", index=False)
        comparisons.to_csv(report_dir / "paired_comparisons.csv", index=False)
        sector_composition.to_csv(report_dir / "sector_tail_composition.csv", index=False)
        sector_bias.to_csv(report_dir / "sector_zero_tail_bias.csv", index=False)
        gamma_diag.to_csv(report_dir / "gamma_diagnostics.csv", index=False)
        gamma_diag.loc[gamma_diag.period.isin([str(year) for year in YEARS])].to_csv(
            report_dir / "gamma_fold_metrics.csv", index=False
        )
        current_audit["status"] = "PASS"
        current_audit["prefix_invariance"] = prefix["status"]
        current_audit["source_scan_files"] = scan_files
        current_audit["run_id"] = output.name
        current_audit["source_run_id"] = SOURCE_RUN_ID
        current_audit["candidate_count"] = len(TRIAL_IDS)
        current_audit["actual_trials"] = len(TRIAL_IDS)
        current_audit["git_commit_hash"] = git_head
        current_audit["git_worktree_dirty"] = bool(worktree)
        current_audit["max_prefix_cutoffs"] = len(PREFIX_CUTOFFS)
        metadata.update({
            "status": "completed", "completed_at_utc": now_utc(),
            "elapsed_seconds": time.monotonic() - started, "actual_trials": len(TRIAL_IDS),
            "train_data_sha256": data_hashes, "valid_accessed": False,
            "source_scan": "PASS", "prefix_invariance": "PASS",
            "saved_score_replay": "PASS", "saved_account_replay": "PASS",
            "official_quintile_match": "PASS", "eligible_ridge_annual_purge": "PASS",
            "evaluation_span": [current_audit["eval_start"], current_audit["eval_end"]],
            "evaluation_days": len(eval_dates), "2016_partial_span": [current_audit["2016_start"], current_audit["2016_end"]],
            "prediction_coverage": {name: int(len(eval_dates) and score_eval[name].notna().sum()) for name in score_eval.columns},
            "outputs": {
                "audit": str((report_dir / "AUDIT.md").relative_to(ROOT)),
                "results": str((report_dir / "EXPERIMENT_RESULTS.md").relative_to(ROOT)),
                "decision": str((report_dir / "DECISION.md").relative_to(ROOT)),
                "metrics": str((report_dir / "candidate_summary.csv").relative_to(ROOT)),
                "category_by_year": str((report_dir / "category_by_year.csv").relative_to(ROOT)),
                "zero_sector_bias": str((report_dir / "sector_zero_tail_bias.csv").relative_to(ROOT)),
                "gamma_diagnostics": str((report_dir / "gamma_diagnostics.csv").relative_to(ROOT)),
            },
        })
        dump(run_path, metadata)
        dump(output / "audit/current_audit.json", current_audit)
        print(f"[7/7] Completed {len(TRIAL_IDS)} fixed results: {report_dir}", flush=True)
    except BaseException as error:
        metadata.update({"status": "failed", "completed_at_utc": now_utc(),
                         "failure": repr(error), "elapsed_seconds": time.monotonic() - started})
        try:
            firewall.save(output / "audit/firewall.json")
        except BaseException:
            pass
        dump(run_path, metadata)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.config, args.output)
