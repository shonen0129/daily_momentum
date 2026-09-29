"""Fixed H1/H5/H20 target-horizon study for the frozen SN1 signal architecture."""
import argparse
import hashlib
import json
import math
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from research import evaluation
from stock_comp_2026.strategies.dm_variable_box_breakout import bidirectional, features, sn1, submission


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DM-20260927-04"
HORIZONS = (1, 5, 20)
YEARS = tuple(range(2011, 2017))
ANNUALIZATION = 252
COST_RATE = 0.001
BOOTSTRAP = {"block": 20, "reps": 1000, "seed": 20260908}
SIDE_NAMES = ("high", "low")
EVAL_DIR = ROOT / "artifacts/DM-20260927-03/run-20260926T191539Z/predictions"
VALID_REF = ROOT / "artifacts/DM-20260927-03/valid-once-sn1-vs-d/predictions/SIDE_SOURCE_SEPARATION.parquet"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dump_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def daily_residual(raw, beta, market):
    if not raw.index.equals(beta.index):
        raise ValueError("raw return and beta indexes differ")
    date_index = raw.index.get_level_values("Date")
    market_by_row = pd.Series(market["Return"].reindex(date_index).to_numpy(), index=raw.index)
    residual = raw["Return"].astype("float64") - beta["Return"].astype("float64") * market_by_row
    return residual.replace([np.inf, -np.inf], np.nan).rename("daily_market_residual")


def forward_window(residual, width, first_offset=2):
    """Compound absolute future calendar rows, matching official raw_return[t+2] indexing."""
    index = residual.index
    wide = residual.unstack(level="Code").sort_index()
    values = wide.to_numpy(dtype="float64", copy=True)
    n_dates = values.shape[0]
    result = np.ones(values.shape, dtype="float64")
    valid = np.ones(values.shape, dtype=bool)
    for offset in range(first_offset, first_offset + width):
        if offset >= n_dates:
            valid[:] = False
            break
        future = values[offset:, :]
        step_valid = np.isfinite(future) & ((1.0 + future) > 0.0)
        valid[:-offset, :] &= step_valid
        result[:-offset, :] *= np.where(step_valid, 1.0 + future, 1.0)
        valid[-offset:, :] = False
    result -= 1.0
    result[~valid] = np.nan
    row_positions = wide.index.get_indexer(index.get_level_values("Date"))
    column_positions = wide.columns.get_indexer(index.get_level_values("Code"))
    if (row_positions < 0).any() or (column_positions < 0).any():
        raise AssertionError("Could not map panel labels to absolute date/code positions")
    selected = result[row_positions, column_positions]
    return pd.Series(selected, index=index, name=f"forward_{width}d_residual")


def make_horizon_target(residual, official_h1, horizon):
    if horizon == 1:
        target = (official_h1["Return"] if isinstance(official_h1, pd.DataFrame) else official_h1)
        target = target.sort_index().astype("float64").rename("Return")
        if not target.index.equals(residual.index):
            raise ValueError("Official H1 target does not align with feature panel")
        return target
    return forward_window(residual, horizon).rename("Return")


def maturity_mask(calendar, index, fold_start, horizon):
    calendar = pd.DatetimeIndex(calendar).sort_values().unique()
    start = int(calendar.searchsorted(pd.Timestamp(fold_start)))
    # Target endpoint is signal-position + H + 1; it must be before fold start.
    mature_dates = calendar[:max(0, start - (horizon + 1))]
    return index.get_level_values("Date").isin(mature_dates), mature_dates


def fit_before_horizon(x, target, calendar, fold_start, side, horizon):
    if not x.index.equals(target.index):
        raise ValueError("Feature and target indexes must match")
    if side not in bidirectional.SIDES:
        raise ValueError(f"Unknown side: {side}")
    dates = x.index.get_level_values("Date")
    mature, mature_dates = maturity_mask(calendar, x.index, fold_start, horizon)
    labels = bidirectional.centered_target_rank(target)
    oriented = labels if side == "high" else -labels
    training = mature & bidirectional.event_mask(x, side).to_numpy() & oriented.notna().to_numpy()
    rows = int(training.sum())
    if rows < bidirectional.MIN_TRAINING_ROWS:
        raise ValueError(f"Too few mature {side} rows for H{horizon} before {fold_start}: {rows}")
    matrix = bidirectional.directional_features(x.loc[training], side)
    model = bidirectional.fit_arrays(matrix, oriented.loc[training], ridge_lambda=1.0)
    used_dates = dates[training]
    last_signal = pd.Timestamp(used_dates.max())
    position = int(pd.DatetimeIndex(calendar).get_indexer([last_signal])[0])
    end_position = position + horizon + 1
    if end_position >= len(calendar) or pd.Timestamp(calendar[end_position]) >= pd.Timestamp(fold_start):
        raise AssertionError("Training label maturity reaches or crosses prediction fold")
    model.update({
        "side": side,
        "horizon": int(horizon),
        "year": int(pd.Timestamp(fold_start).year),
        "training_dates": int(used_dates.nunique()),
        "min_training_signal": str(pd.Timestamp(used_dates.min()).date()),
        "max_training_signal": str(last_signal.date()),
        "max_label_maturity_date": str(pd.Timestamp(calendar[end_position]).date()),
        "mature_signal_dates": int(len(mature_dates)),
    })
    return model, training


def predict_with_model(x, model, side):
    active = bidirectional.event_mask(x, side)
    matrix = bidirectional.directional_features(x.loc[active], side)
    return pd.Series(
        bidirectional.predict_matrix(matrix, model), index=matrix.index,
        name=f"H{model['horizon']}_{side}", dtype="float64",
    )


def train_walk_forward(x, target, horizon, model_dir):
    calendar = pd.DatetimeIndex(x.index.get_level_values("Date").unique().sort_values())
    preds = {side: [] for side in SIDE_NAMES}
    records = []
    for year in YEARS:
        for side in SIDE_NAMES:
            model, _ = fit_before_horizon(x, target, calendar, f"{year}-01-01", side, horizon)
            dates = x.index.get_level_values("Date")
            select = (dates.year == year) & bidirectional.event_mask(x, side).to_numpy()
            matrix = bidirectional.directional_features(x.loc[select], side)
            pred = pd.Series(bidirectional.predict_matrix(matrix, model), index=matrix.index,
                             name=f"H{horizon}_{side}", dtype="float64")
            preds[side].append(pred)
            model_dir.mkdir(parents=True, exist_ok=True)
            (model_dir / f"{side}_{year}.json").write_text(
                json.dumps(model, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
            )
            records.append(model)
    combined = {side: pd.concat(pieces).sort_index() for side, pieces in preds.items()}
    return combined, records


def valid_predictions(x_train, target_train, x_valid, full_calendar, horizon, model_dir):
    preds = {}
    records = []
    first_date = pd.Timestamp(x_valid.index.get_level_values("Date").min())
    for side in SIDE_NAMES:
        model, _ = fit_before_horizon(x_train, target_train, full_calendar, first_date, side, horizon)
        preds[side] = predict_with_model(x_valid, model, side)
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / f"{side}_valid.json").write_text(
            json.dumps(model, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        records.append(model)
    return preds, records


def score_from_split_predictions(x_train, x_valid, train_preds, valid_preds):
    """Build the same continuous SN1 stream without retaining a full duplicate feature panel."""
    train_raw = bidirectional.generate_raw_signal(x_train, train_preds)
    valid_raw = bidirectional.generate_raw_signal(x_valid, valid_preds)
    raw = pd.concat([train_raw, valid_raw]).sort_index()
    if not raw.index.is_unique:
        raise ValueError("Train and historical Valid raw score indexes overlap")
    base = bidirectional.smooth_by_listing(raw, alpha=sn1.HIGH_ALPHA)
    replay = sn1.rebuild_from_base_score(base)
    return {
        "D_LOW_FAST_ONLY": replay["D_LOW_FAST_ONLY"],
        "SIDE_SOURCE_SEPARATION": replay["SIDE_SOURCE_SEPARATION"],
    }


def _rankic(a, b):
    good = a.notna() & b.notna()
    if int(good.sum()) < 2:
        return pd.Series(dtype="float64")
    ar = a.where(good).groupby(level="Date").rank(method="average")
    br = b.where(good).groupby(level="Date").rank(method="average")
    ar = ar - ar.groupby(level="Date").transform("mean")
    br = br - br.groupby(level="Date").transform("mean")
    numerator = (ar * br).groupby(level="Date").sum()
    denominator = np.sqrt((ar * ar).groupby(level="Date").sum() * (br * br).groupby(level="Date").sum())
    return (numerator / denominator).replace([np.inf, -np.inf], np.nan)


def series_metrics(values, lag):
    vals = values.dropna()
    return {
        "mean": float(vals.mean()) if len(vals) else np.nan,
        "hac_t": float(evaluation.hac_t(vals, lag=lag)) if len(vals) else np.nan,
        "hit_rate": float((vals > 0).mean()) if len(vals) else np.nan,
        "observations": int(len(vals)),
    }


def prediction_quality(horizon, split, x, preds, score, targets, model_records, outdir):
    rows = []
    daily_rows = []
    if split == "train":
        deploy = score.index.get_level_values("Date").year.isin(YEARS)
        score = score.loc[deploy]
    for target_h, target in targets.items():
        daily = _rankic(score, target)
        item = series_metrics(daily, lag=max(horizon, 1))
        daily_rows.append({"horizon": horizon, "split": split, "target_window": target_h,
                           "scope": "full_cross_section_SN1_score", **item})
    for side in SIDE_NAMES:
        pred = preds[side]
        for target_h, target in targets.items():
            oriented = bidirectional.centered_target_rank(target)
            if side == "low":
                oriented = -oriented
            ic = _rankic(pred, oriented.reindex(pred.index))
            item = series_metrics(ic, lag=max(horizon, 1))
            rows.append({"horizon": horizon, "split": split, "side": side,
                         "target_window": target_h, **item,
                         "event_rows": int(pred.notna().sum())})
        counts = pred.groupby(level="Date").size()
        dispersions = pred.groupby(level="Date").std(ddof=1)
        daily_rows.append({
            "horizon": horizon, "split": split, "target_window": "prediction_dispersion",
            "scope": side, "mean_daily_event_count": float(counts.mean()),
            "median_daily_event_count": float(counts.median()),
            "median_daily_prediction_sd": float(dispersions.median()),
            "mean_daily_prediction_sd": float(dispersions.mean()),
            "pooled_prediction_sd": float(pred.std(ddof=1)),
        })
    for rec in model_records:
        for column, coef in zip(bidirectional.DIRECTIONAL_COLUMNS, rec["coefficients"][1:]):
            rows.append({"horizon": horizon, "split": split, "side": rec["side"],
                         "target_window": "coefficient", "feature": column,
                         "fold_year": rec["year"], "coefficient": float(coef),
                         "training_rows": rec["training_rows"],
                         "training_dates": rec["training_dates"],
                         "maturity_date": rec["max_label_maturity_date"]})
    pd.DataFrame(rows).to_csv(outdir / f"prediction_quality_{split}_H{horizon}.csv", index=False)
    pd.DataFrame(daily_rows).to_csv(outdir / f"prediction_daily_{split}_H{horizon}.csv", index=False)
    return rows, daily_rows


def side_account(score, target):
    signal = score.reindex(target.index).sort_index().fillna(0.0)
    weights, quintile = evaluation.weights(signal)
    prior = weights.groupby(level="Code", sort=False).shift(1).fillna(0.0)
    long_turn = (weights.clip(lower=0) - prior.clip(lower=0)).abs()
    short_turn = (weights.clip(upper=0) - prior.clip(upper=0)).abs()
    aligned_target = target.reindex(weights.index)
    long = weights.clip(lower=0) * aligned_target
    short = weights.clip(upper=0) * aligned_target
    official = evaluation.daily_account(signal, aligned_target)
    idx = weights.index
    daily = pd.DataFrame({
        "long_gross": long.groupby(level="Date").sum(),
        "short_gross": short.groupby(level="Date").sum(),
        "long_cost": (COST_RATE * long_turn).where(aligned_target.notna(), 0.0).groupby(level="Date").sum(),
        "short_cost": (COST_RATE * short_turn).where(aligned_target.notna(), 0.0).groupby(level="Date").sum(),
        "long_turnover": long_turn.groupby(level="Date").sum(),
        "short_turnover": short_turn.groupby(level="Date").sum(),
        "gross_exposure": weights.abs().groupby(level="Date").sum(),
        "net_exposure": weights.groupby(level="Date").sum(),
    })
    daily["long_net"] = daily["long_gross"] - daily["long_cost"]
    daily["short_net"] = daily["short_gross"] - daily["short_cost"]
    daily["gross"] = official["gross"]
    daily["net"] = official["net"]
    daily["net_all_cost"] = official["net_all_cost"]
    daily["turnover"] = official["turnover"]
    daily["cost"] = official["cost"]
    daily["cost_all"] = official["cost_all"]
    daily["rankic"] = official["rankic"]
    daily["label_coverage"] = official["label_coverage"]
    daily["long"] = official["long"]
    daily["short"] = official["short"]
    for i in range(1, 6):
        daily[f"q{i}"] = official[f"q{i}"]
    if float((daily.long_gross + daily.short_gross - daily.gross).abs().max()) > 1e-10:
        raise AssertionError("Long/Short gross does not reconcile to official gross")
    if float((daily.long_net + daily.short_net - daily.net).abs().max()) > 1e-10:
        raise AssertionError("Long/Short net does not reconcile to official net")
    return daily, quintile, weights


def score_regulation(score, split, horizon, outdir):
    signal = score.sort_index().astype("float64")
    if not signal.index.is_unique or not np.isfinite(signal.to_numpy()).all():
        raise AssertionError(f"H{horizon} {split}: score index/finite failure")
    w, q = evaluation.weights(signal)
    dates = signal.index.get_level_values("Date")
    rows = []
    for date, group in signal.groupby(level="Date", sort=True):
        vals = group.to_numpy(dtype="float64")
        qday = q.reindex(group.index).to_numpy(dtype=int)
        unique = int(pd.Series(vals).nunique(dropna=False))
        n = len(vals)
        # Boundary ties: equal adjacent scores crossing the official rank-defined quintile.
        order = np.argsort(vals, kind="stable")
        sorted_v, sorted_q = vals[order], qday[order]
        cross = (sorted_q[1:] != sorted_q[:-1]) & (sorted_v[1:] == sorted_v[:-1]) if n > 1 else np.array([], bool)
        counts = np.bincount(qday, minlength=5)
        rows.append({
            "date": date, "n": n, "zero_rate": float(np.mean(vals == 0.0)),
            "unique_scores": unique, "unique_ratio": unique / n if n else np.nan,
            "duplicate_row_rate": 1.0 - unique / n if n else np.nan,
            "boundary_tie_count": int(cross.sum()),
            "boundary_tie_rate": float(cross.sum() / 4.0),
            "any_boundary_tie": bool(cross.any()),
            "q1_count": int(counts[0]), "q2_count": int(counts[1]),
            "q3_count": int(counts[2]), "q4_count": int(counts[3]),
            "q5_count": int(counts[4]),
            "gross_exposure": float(w.loc[group.index].abs().sum()),
            "net_exposure": float(w.loc[group.index].sum()),
            "score_mean": float(np.mean(vals)), "score_sd": float(np.std(vals, ddof=1)),
            "score_min": float(np.min(vals)), "score_max": float(np.max(vals)),
        })
    result = pd.DataFrame(rows)
    result.to_csv(outdir / f"regulation_{split}_H{horizon}.csv", index=False)
    summary = {
        "horizon": horizon, "split": split,
        "zero_rate_mean": float(result.zero_rate.mean()),
        "duplicate_rate_mean": float(result.duplicate_row_rate.mean()),
        "unique_ratio_mean": float(result.unique_ratio.mean()),
        "unique_ratio_min": float(result.unique_ratio.min()),
        "boundary_tie_rate_mean": float(result.boundary_tie_rate.mean()),
        "days_with_boundary_ties": float(result.any_boundary_tie.mean()),
        "five_quintiles_populated_days": int(((result[[f"q{i}_count" for i in range(1, 6)]] > 0).all(axis=1)).sum()),
        "days": int(len(result)),
        "mean_gross_exposure": float(result.gross_exposure.mean()),
        "mean_net_exposure": float(result.net_exposure.mean()),
        "finite": bool(np.isfinite(result.select_dtypes(include=[np.number]).to_numpy()).all()),
    }
    return summary


def consecutive_persistence(signal, split, horizon, outdir):
    _, q = evaluation.weights(signal)
    dates = pd.DatetimeIndex(signal.index.get_level_values("Date").unique().sort_values())
    codes = signal.index.get_level_values("Code")
    rank = signal.groupby(level="Date").rank(method="average", pct=True)
    pair_rows = []
    for previous_date, current_date in zip(dates[:-1], dates[1:]):
        old = q.xs(previous_date, level="Date")
        new = q.xs(current_date, level="Date")
        common = old.index.intersection(new.index)
        if not len(common):
            continue
        a = old.reindex(common).astype(int)
        b = new.reindex(common).astype(int)
        old_rank = rank.xs(previous_date, level="Date").reindex(common)
        new_rank = rank.xs(current_date, level="Date").reindex(common)
        pair_rows.append({
            "date": current_date,
            "rank_autocorr": float(old_rank.corr(new_rank, method="spearman")) if old_rank.nunique() > 1 and new_rank.nunique() > 1 else np.nan,
            "common_codes": int(len(common)),
            "q1_retention": float((b[a == 0] == 0).mean()) if (a == 0).any() else np.nan,
            "q2_retention": float((b[a == 1] == 1).mean()) if (a == 1).any() else np.nan,
            "q4_retention": float((b[a == 3] == 3).mean()) if (a == 3).any() else np.nan,
            "q5_retention": float((b[a == 4] == 4).mean()) if (a == 4).any() else np.nan,
            "transition_count": int(len(common)),
        })
    pairs = pd.DataFrame(pair_rows)
    transition_array = np.zeros((5, 5), dtype="int64")
    if not pairs.empty:
        # Reconstruct transition matrix in bounded date pairs.
        for previous_date, current_date in zip(dates[:-1], dates[1:]):
            old = q.xs(previous_date, level="Date")
            new = q.xs(current_date, level="Date")
            common = old.index.intersection(new.index)
            old_q = old.reindex(common).to_numpy(dtype=int)
            new_q = new.reindex(common).to_numpy(dtype=int)
            np.add.at(transition_array, (old_q, new_q), 1)
    transitions = pd.DataFrame(transition_array, index=range(5), columns=range(5))
    transitions.to_csv(outdir / f"quintile_transitions_{split}_H{horizon}.csv")
    pair_summary = {
        "horizon": horizon, "split": split,
        "mean_score_rank_autocorr": float(pairs.rank_autocorr.mean()),
        "mean_q1_retention": float(pairs.q1_retention.mean()),
        "mean_q2_retention": float(pairs.q2_retention.mean()),
        "mean_q4_retention": float(pairs.q4_retention.mean()),
        "mean_q5_retention": float(pairs.q5_retention.mean()),
        "daily_pairs": int(len(pairs)),
        "mean_common_codes": float(pairs.common_codes.mean()),
        "mean_quintile_transition_probability": (transitions / transitions.sum(axis=1).replace(0, np.nan).to_numpy()[:, None]).to_numpy().tolist(),
    }
    pairs.to_csv(outdir / f"persistence_daily_{split}_H{horizon}.csv", index=False)

    # Membership spells in contiguous trading-calendar time; opposite-side and missing-date gaps start new spells.
    d = signal.index.get_level_values("Date")
    ord_map = {date: i for i, date in enumerate(dates)}
    ords = pd.Series(d.map(ord_map).to_numpy(), index=signal.index)
    membership = pd.Series(np.where(q >= 3, 1, np.where(q <= 1, -1, 0)), index=signal.index)
    frame = pd.DataFrame({"ord": ords, "side": membership}, index=signal.index)
    frame["code"] = frame.index.get_level_values("Code")
    frame = frame.sort_index(level=[1, 0])
    previous_ord = frame.groupby("code", sort=False)["ord"].shift(1)
    previous_side = frame.groupby("code", sort=False)["side"].shift(1)
    new_spell = frame.side.ne(previous_side) | frame.ord.sub(previous_ord).ne(1)
    frame["spell"] = new_spell.groupby(frame.code, sort=False).cumsum()
    held = frame[frame.side.ne(0)]
    spells = held.groupby(["code", "side", "spell"], sort=False).size()
    for side, label in ((1, "long"), (-1, "short")):
        values = spells.loc[spells.index.get_level_values("side") == side] if len(spells) else pd.Series(dtype=float)
        pair_summary[f"{label}_spell_mean_days"] = float(values.mean()) if len(values) else np.nan
        pair_summary[f"{label}_spell_median_days"] = float(values.median()) if len(values) else np.nan
        pair_summary[f"{label}_spell_5plus_share"] = float((values >= 5).mean()) if len(values) else np.nan
        pair_summary[f"{label}_spell_10plus_share"] = float((values >= 10).mean()) if len(values) else np.nan
        pair_summary[f"{label}_spell_20plus_share"] = float((values >= 20).mean()) if len(values) else np.nan
    return pair_summary


def account_period_metrics(daily, split):
    rows = []
    dates = pd.DatetimeIndex(daily.index)
    windows = [("full", dates), ("ex2016", dates[dates.year != 2016])]
    if split == "train":
        windows.extend((str(year), dates[dates.year == year]) for year in YEARS)
    else:
        windows.extend((str(year), dates[dates.year == year]) for year in sorted(set(dates.year)))
    for label, use_dates in windows:
        use_dates = pd.DatetimeIndex(use_dates).intersection(daily.index)
        if not len(use_dates):
            continue
        d = daily.loc[use_dates]
        row = evaluation.metrics(d[["gross", "net", "net_all_cost", "cost", "cost_all", "turnover",
                                   "rankic", "long", "short", "label_coverage",
                                   "q1", "q2", "q3", "q4", "q5"]].copy())
        for col in ("gross", "net", "long_gross", "long_net", "short_gross", "short_net"):
            row[f"{col}_vol_annual"] = float(d[col].std(ddof=1) * np.sqrt(ANNUALIZATION))
        row.update({
            "period": label, "split": split,
            "annual_long_gross": float(d.long_gross.mean() * ANNUALIZATION),
            "annual_long_net": float(d.long_net.mean() * ANNUALIZATION),
            "long_net_sharpe": evaluation.sharpe(d.long_net),
            "annual_short_gross": float(d.short_gross.mean() * ANNUALIZATION),
            "annual_short_net": float(d.short_net.mean() * ANNUALIZATION),
            "short_net_sharpe": evaluation.sharpe(d.short_net),
            "long_short_gross_correlation": float(d.long_gross.corr(d.short_gross)),
            "mean_gross_exposure": float(d.gross_exposure.mean()),
            "mean_net_exposure": float(d.net_exposure.mean()),
            "mean_cost": float(d.cost.mean() * ANNUALIZATION),
        })
        rows.append(row)
    return rows


def annual_return_decomposition(base_score, candidate_score, target, base_daily, candidate_daily):
    b = base_score.reindex(target.index).sort_index().fillna(0.0)
    c = candidate_score.reindex(target.index).sort_index().fillna(0.0)
    wb, _ = evaluation.weights(b)
    wc, _ = evaluation.weights(c)
    common_weight = pd.Series(np.sign(wb) * np.minimum(wb.abs(), wc.abs()), index=wb.index)
    daily_common = (common_weight * target).groupby(level="Date").sum()
    base_unique = (wb - common_weight)
    candidate_unique = (wc - common_weight)
    daily_base_unique = (base_unique * target).groupby(level="Date").sum()
    daily_candidate_unique = (candidate_unique * target).groupby(level="Date").sum()
    daily_selection = daily_candidate_unique - daily_base_unique
    check = daily_selection
    realized_delta = candidate_daily.gross.reindex(check.index) - base_daily.gross.reindex(check.index)
    if float((check - realized_delta).abs().max()) > 1e-10:
        raise AssertionError("common/selection gross-delta decomposition does not reconcile")
    return {
        "delta_annual_gross": float(realized_delta.mean() * ANNUALIZATION),
        "selection_annual": float(daily_selection.mean() * ANNUALIZATION),
        "shared_holdings_annual_pnl_baseline": float(daily_common.mean() * ANNUALIZATION),
        "shared_holdings_delta": 0.0,
        "baseline_only_annual_pnl": float(daily_base_unique.mean() * ANNUALIZATION),
        "candidate_only_annual_pnl": float(daily_candidate_unique.mean() * ANNUALIZATION),
        "delta_annual_cost": float((candidate_daily.cost - base_daily.cost).mean() * ANNUALIZATION),
        "delta_annual_net": float((candidate_daily.net - base_daily.net).mean() * ANNUALIZATION),
        "identity_error": float((candidate_daily.net - base_daily.net - (realized_delta - (candidate_daily.cost - base_daily.cost))).abs().max()),
        "delta_turnover": float((candidate_daily.turnover - base_daily.turnover).mean()),
        "delta_net_exposure": float((candidate_daily.net_exposure - base_daily.net_exposure).mean()),
        "delta_gross_vol_annual": float(candidate_daily.gross.std(ddof=1) * np.sqrt(ANNUALIZATION) - base_daily.gross.std(ddof=1) * np.sqrt(ANNUALIZATION)),
    }


def bootstrap_pair(base, candidate):
    base = np.asarray(base, dtype=float)
    candidate = np.asarray(candidate, dtype=float)
    if len(base) != len(candidate) or not len(base):
        return {"error": "unaligned daily series"}
    rng = np.random.default_rng(BOOTSTRAP["seed"])
    blocks = int(np.ceil(len(base) / BOOTSTRAP["block"]))
    starts = rng.integers(0, len(base), size=(BOOTSTRAP["reps"], blocks))
    indexes = ((starts[:, :, None] + np.arange(BOOTSTRAP["block"])) % len(base)).reshape(BOOTSTRAP["reps"], -1)[:, :len(base)]
    b, c = base[indexes], candidate[indexes]
    sr_b = np.sqrt(ANNUALIZATION) * b.mean(axis=1) / b.std(axis=1, ddof=1)
    sr_c = np.sqrt(ANNUALIZATION) * c.mean(axis=1) / c.std(axis=1, ddof=1)
    ann_delta = (c.mean(axis=1) - b.mean(axis=1)) * ANNUALIZATION
    delta_sr = sr_c - sr_b
    return {
        "delta_net_sr_low": float(np.quantile(delta_sr, .025)),
        "delta_net_sr_median": float(np.quantile(delta_sr, .5)),
        "delta_net_sr_high": float(np.quantile(delta_sr, .975)),
        "delta_net_sr_positive_fraction": float(np.mean(delta_sr > 0)),
        "delta_annual_net_low": float(np.quantile(ann_delta, .025)),
        "delta_annual_net_median": float(np.quantile(ann_delta, .5)),
        "delta_annual_net_high": float(np.quantile(ann_delta, .975)),
        **BOOTSTRAP,
    }


def make_consistency_targets(residual, horizon, horizon_target):
    result = {"day1": forward_window(residual, 1, first_offset=2)}
    if horizon == 1:
        return result
    if horizon == 5:
        result["days1_5"] = horizon_target
        result["days6_20"] = forward_window(residual, 15, first_offset=7)
        return result
    result["days1_5"] = forward_window(residual, 5, first_offset=2)
    result["days1_20"] = horizon_target
    result["days21_40"] = forward_window(residual, 20, first_offset=22)
    return result


def target_integrity(residual, official_h1, horizon):
    reconstructed = forward_window(residual, 1, first_offset=2)
    official = (official_h1["Return"] if isinstance(official_h1, pd.DataFrame) else official_h1)
    official = official.sort_index().astype(float)
    common = reconstructed.notna() & official.notna()
    delta = (reconstructed[common] - official[common]).abs()
    return {
        "horizon": horizon,
        "reconstruction_rows": int(common.sum()),
        "official_coverage_rows": int(official.notna().sum()),
        "max_abs_h1_reconstruction_error": float(delta.max()) if len(delta) else np.nan,
        "mean_abs_h1_reconstruction_error": float(delta.mean()) if len(delta) else np.nan,
        "h1_reconstruction_exact_1e12": bool(len(delta) and delta.max() <= 1e-12),
    }


def run_prefix_invariance(train_panels, x_train, targets, run_dir):
    cutoff = pd.Timestamp("2014-06-30")
    available_codes = sorted(set(x_train.index.get_level_values("Code")))
    codes = set(available_codes[:48])
    sample = {}
    for name, frame in train_panels.items():
        if name == "topix_return_1day":
            sample[name] = frame.copy()
        else:
            sample[name] = frame.loc[frame.index.get_level_values("Code").isin(codes)].copy()
    before = features.build_features(sample)
    changed = {name: frame.copy() for name, frame in sample.items()}
    for name, frame in changed.items():
        dates = frame.index.get_level_values("Date")
        future = dates > cutoff
        if name == "raw_return_1day":
            frame.loc[future, "Return"] += 0.013
        elif name == "beta_1day":
            frame.loc[future, "Return"] *= 1.17
        elif name == "topix_return_1day":
            frame.loc[future, "Return"] += 0.006
        elif name == "prices_daily_quotes":
            for col in ("High", "Low", "Close"):
                frame.loc[future, col] *= 1.009
            frame.loc[future, "AdjustmentFactor"] *= 1.001
    after = features.build_features(changed)
    prefix = before.index.get_level_values("Date") <= cutoff
    x_equal = before.loc[prefix].equals(after.loc[prefix])

    # Alter only post-cutoff outcome inputs; safe mature labels and fitted models must remain identical.
    raw, beta, market = train_panels["raw_return_1day"], train_panels["beta_1day"], train_panels["topix_return_1day"]
    residual = daily_residual(raw, beta, market)
    mutated = raw.copy()
    future_raw = mutated.index.get_level_values("Date") > cutoff
    mutated.loc[future_raw, "Return"] += 0.013
    changed_resid = daily_residual(mutated, beta, market)
    safe_label_checks = []
    model_checks = []
    calendar = pd.DatetimeIndex(x_train.index.get_level_values("Date").unique().sort_values())
    next_day = calendar[calendar.searchsorted(cutoff)]
    for h in HORIZONS:
        if h == 1:
            a = forward_window(residual, 1, 2)
            b = forward_window(changed_resid, 1, 2)
        else:
            a = forward_window(residual, h, 2)
            b = forward_window(changed_resid, h, 2)
        maturity = pd.Series(calendar.get_indexer(a.index.get_level_values("Date")), index=a.index) + h + 1
        cutoff_pos = int(calendar.get_indexer([cutoff])[0]) if cutoff in calendar else int(calendar.searchsorted(cutoff))
        safe = a.notna() & b.notna() & (maturity < cutoff_pos)
        label_equal = np.array_equal(a[safe].to_numpy(), b[safe].to_numpy())
        safe_label_checks.append({"horizon": h, "safe_labels": int(safe.sum()), "equal": bool(label_equal)})
        official_like = a.rename("Return") if h == 1 else a.rename("Return")
        changed_target = b.rename("Return")
        for side in SIDE_NAMES:
            model_a, _ = fit_before_horizon(x_train, official_like, calendar, next_day, side, h)
            model_b, _ = fit_before_horizon(x_train, changed_target, calendar, next_day, side, h)
            coef_equal = np.array_equal(np.asarray(model_a["coefficients"]), np.asarray(model_b["coefficients"]))
            model_checks.append({"horizon": h, "side": side, "coefficients_equal": bool(coef_equal),
                                 "training_rows": model_a["training_rows"]})
    summary = {
        "cutoff": str(cutoff.date()), "sample_codes": len(codes),
        "feature_prefix_bitwise_equal": bool(x_equal),
        "safe_target_labels": safe_label_checks,
        "future_outcome_mutation_fit_checks": model_checks,
        "all_checks_pass": bool(x_equal and all(x["equal"] for x in safe_label_checks)
                                 and all(x["coefficients_equal"] for x in model_checks)),
        "limitations": "Feature prefix check uses 48 sorted Train codes; target maturity and fit checks use full Train features.",
    }
    dump_json(run_dir / "audit/prefix_invariance.json", summary)
    return summary


def save_scores(score, path):
    frame = score.rename("Return").to_frame()
    frame.to_parquet(path, compression="zstd")


def compare_h1_reference(train_score, valid_score):
    rows = []
    ref_train_path = EVAL_DIR / "strategy_scores.parquet"
    if ref_train_path.is_file():
        frame = pd.read_parquet(ref_train_path)
        if not isinstance(frame.index, pd.MultiIndex) or list(frame.index.names) != ["Date", "Code"]:
            frame = frame.set_index(["Date", "Code"])
        ref = frame.sort_index()["SIDE_SOURCE_SEPARATION"]
        common = ref.index.intersection(train_score.index)
        delta = (ref.reindex(common) - train_score.reindex(common)).abs()
        rows.append({"reference": "previous_train_saved_score", "matched_rows": len(common),
                     "max_abs_error": float(delta.max()) if len(delta) else np.nan,
                     "bitwise_equal": bool(len(delta) and np.array_equal(ref.reindex(common).to_numpy(), train_score.reindex(common).to_numpy()))})
    if VALID_REF.is_file():
        frame = pd.read_parquet(VALID_REF)
        if not isinstance(frame.index, pd.MultiIndex) or list(frame.index.names) != ["Date", "Code"]:
            frame = frame.set_index(["Date", "Code"])
        ref = frame.sort_index()["Return"]
        common = ref.index.intersection(valid_score.index)
        delta = (ref.reindex(common) - valid_score.reindex(common)).abs()
        rows.append({"reference": "previous_valid_once_saved_score", "matched_rows": len(common),
                     "max_abs_error": float(delta.max()) if len(delta) else np.nan,
                     "bitwise_equal": bool(len(delta) and np.array_equal(ref.reindex(common).to_numpy(), valid_score.reindex(common).to_numpy()))})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=ROOT / "stock_comp_2026/input")
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    data_dir, run_dir = args.data_dir.resolve(), args.run_dir.resolve()
    for name in ("metrics", "predictions", "models", "audit"):
        (run_dir / name).mkdir(parents=True, exist_ok=True)
    lock = json.loads((ROOT / f"experiments/{EXPERIMENT_ID}/pre_result_lock.json").read_text())
    if digest(ROOT / f"experiments/{EXPERIMENT_ID}/plan.md") != lock["plan_sha256"]:
        raise AssertionError("Pre-result plan hash changed")
    if digest(ROOT / f"experiments/{EXPERIMENT_ID}/config.json") != lock["config_sha256"]:
        raise AssertionError("Pre-result config hash changed")
    status = {"experiment_id": EXPERIMENT_ID, "run_id": run_dir.name, "state": "running",
              "git_head": lock["git_head"], "plan_sha256": lock["plan_sha256"],
              "config_sha256": lock["config_sha256"], "started_unix": time.time(),
              "python": sys.version, "platform": platform.platform(),
              "numpy": np.__version__, "pandas": pd.__version__, "source_sha256": lock["source_sha256"]}
    dump_json(run_dir / "run.json", status)

    # The historical Valid period is development data here, as explicitly instructed.
    train_panels = features.load_inputs(data_dir, "train")
    valid_panels = features.load_inputs(data_dir, "valid")
    train_target = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index()
    valid_target = pd.read_parquet(data_dir / "target_1day_valid.parquet")["Return"].sort_index()
    train_residual = daily_residual(train_panels["raw_return_1day"], train_panels["beta_1day"], train_panels["topix_return_1day"])
    valid_residual = daily_residual(valid_panels["raw_return_1day"], valid_panels["beta_1day"], valid_panels["topix_return_1day"])
    if not train_residual.index.equals(train_target.index) or not valid_residual.index.equals(valid_target.index):
        raise ValueError("Daily input and official target indexes are not aligned")
    dump_json(run_dir / "audit/target_integrity.json", [
        target_integrity(train_residual, train_target, 1), target_integrity(valid_residual, valid_target, 1)
    ])

    x_train = features.build_features(train_panels)
    if not x_train.index.equals(train_target.index):
        raise ValueError("Train features and target are not aligned")
    prefix = run_prefix_invariance(train_panels, x_train, {}, run_dir)
    if not prefix["all_checks_pass"]:
        raise AssertionError("Prefix invariance audit failed before horizon comparison")

    # The last 300 Train trading dates warm the fixed 250-observation Valid feature builder.
    train_calendar = pd.DatetimeIndex(train_residual.index.get_level_values("Date").unique().sort_values())
    valid_calendar = pd.DatetimeIndex(valid_residual.index.get_level_values("Date").unique().sort_values())
    full_calendar = train_calendar.append(valid_calendar).unique().sort_values()
    valid_first = valid_calendar.min()
    warm_dates = set(train_calendar[-300:])
    valid_warm_panels = {}
    for name, train_panel in train_panels.items():
        if name == "topix_return_1day":
            keep = train_panel.index.isin(warm_dates)
        else:
            keep = train_panel.index.get_level_values("Date").isin(warm_dates)
        joined = pd.concat([train_panel.loc[keep], valid_panels[name]]).sort_index()
        if not joined.index.is_unique:
            raise ValueError(f"Duplicate warm-up/Valid index in {name}")
        valid_warm_panels[name] = joined
    warm_features = features.build_features(valid_warm_panels)
    x_valid = warm_features.loc[warm_features.index.get_level_values("Date") >= valid_first]
    del warm_features, valid_warm_panels
    if not x_valid.index.equals(valid_target.index):
        raise ValueError("Historical Valid feature/target indexes are not aligned")

    # Existing H1 reference path, checked before any H5/H20 candidate is evaluated.
    ref_train_pred, _ = bidirectional.walk_forward_predictions(x_train, train_target, years=YEARS)
    ref_train_score = submission.candidate_scores_from_predictions(x_train, ref_train_pred)["SIDE_SOURCE_SEPARATION"]
    ref_valid_pred = submission._predict_later(x_train, train_target, x_valid, full_calendar)

    daily_accounts = {"train": {}, "valid": {}}
    h1_scores, h1_accounts = {}, {}
    portfolio_rows, quality_rows, persistence_rows, regulation_rows = [], [], [], []
    decomposition_rows, bootstrap_rows = [], []
    h1_gate = None

    for horizon in HORIZONS:
        print(f"starting fixed H{horizon}", flush=True)
        target_train = make_horizon_target(train_residual, train_target, horizon)
        target_valid = make_horizon_target(valid_residual, valid_target, horizon)
        if not target_train.index.equals(x_train.index) or not target_valid.index.equals(x_valid.index):
            raise ValueError(f"H{horizon} target coverage/index mismatch")
        target_train.to_frame().to_parquet(run_dir / f"predictions/target_train_H{horizon}.parquet", compression="zstd")
        target_valid.to_frame().to_parquet(run_dir / f"predictions/target_valid_H{horizon}.parquet", compression="zstd")

        train_pred, train_records = train_walk_forward(x_train, target_train, horizon, run_dir / f"models/H{horizon}/train")
        valid_pred, valid_records = valid_predictions(x_train, target_train, x_valid, full_calendar, horizon, run_dir / f"models/H{horizon}/valid")
        if horizon == 1:
            prediction_deltas = []
            for side in SIDE_NAMES:
                prediction_deltas.extend([
                    (train_pred[side].reindex(ref_train_pred[side].index) - ref_train_pred[side]).abs(),
                    (valid_pred[side].reindex(ref_valid_pred[side].index) - ref_valid_pred[side]).abs(),
                ])
            prediction_error = max(float(delta.max()) for delta in prediction_deltas)
            if prediction_error != 0.0:
                dump_json(run_dir / "audit/h1_reproduction_gate.json", {"passed": False, "event_prediction_max_abs_error": prediction_error})
                raise AssertionError("H1 event predictions differ from existing functions; H5/H20 stopped")

        candidates = score_from_split_predictions(x_train, x_valid, train_pred, valid_pred)
        train_score = candidates["SIDE_SOURCE_SEPARATION"].reindex(x_train.index)
        valid_score = candidates["SIDE_SOURCE_SEPARATION"].reindex(x_valid.index)
        if not np.isfinite(train_score.to_numpy()).all() or not np.isfinite(valid_score.to_numpy()).all():
            raise AssertionError(f"H{horizon} SN1 score contains nonfinite values")
        save_scores(train_score, run_dir / f"predictions/SN1_H{horizon}_train.parquet")
        save_scores(valid_score, run_dir / f"predictions/SN1_H{horizon}_historical_valid.parquet")

        if horizon == 1:
            train_delta = (train_score - ref_train_score.reindex(train_score.index)).abs()
            saved_refs = compare_h1_reference(train_score, valid_score)
            matched = [item for item in saved_refs if item["matched_rows"] > 0]
            archive_equal = bool(matched) and all(item["bitwise_equal"] for item in matched)
            h1_pass = bool(train_delta.max() == 0.0 and archive_equal)
            h1_gate = {"passed": h1_pass,
                       "train_research_score_max_abs_error": float(train_delta.max()),
                       "event_prediction_max_abs_error": prediction_error,
                       "saved_score_intersections": saved_refs,
                       "historical_valid_treated_as_development": True}
            dump_json(run_dir / "audit/h1_reproduction_gate.json", h1_gate)
            if not h1_pass:
                raise AssertionError("H1 did not reproduce saved scores; H5/H20 stopped")
            h1_scores = {"train": train_score.copy(), "valid": valid_score.copy()}

        # Actual daily P/L uses the official one-day target and official quintile/cost accounting.
        train_account, _, _ = side_account(train_score, train_target)
        valid_account, _, _ = side_account(valid_score, valid_target)
        eval_dates = []
        for year in YEARS:
            dates = pd.DatetimeIndex(train_account.index)
            dates = dates[dates.year == year]
            eval_dates.extend(dates[:-2].tolist())
        train_account = train_account.loc[pd.DatetimeIndex(eval_dates).sort_values()]
        valid_labeled = valid_target.notna().groupby(level="Date").any()
        valid_account = valid_account.loc[pd.DatetimeIndex(valid_labeled[valid_labeled].index)]
        daily_accounts["train"][horizon] = train_account
        daily_accounts["valid"][horizon] = valid_account
        train_account.to_csv(run_dir / f"metrics/daily_account_train_H{horizon}.csv", index_label="Date")
        valid_account.to_csv(run_dir / f"metrics/daily_account_valid_H{horizon}.csv", index_label="Date")
        portfolio_rows.extend(account_period_metrics(train_account, "train") + account_period_metrics(valid_account, "valid"))

        train_deploy = train_score.loc[train_score.index.get_level_values("Date").year.isin(YEARS)]
        regulation_rows.extend([
            score_regulation(train_deploy, "train", horizon, run_dir / "audit"),
            score_regulation(valid_score, "valid", horizon, run_dir / "audit"),
        ])
        persistence_rows.extend([
            consecutive_persistence(train_deploy, "train", horizon, run_dir / "metrics"),
            consecutive_persistence(valid_score, "valid", horizon, run_dir / "metrics"),
        ])

        train_windows = make_consistency_targets(train_residual, horizon, target_train)
        valid_windows = make_consistency_targets(valid_residual, horizon, target_valid)
        _, train_daily_quality = prediction_quality(horizon, "train", x_train, train_pred, train_score,
                                                    train_windows, train_records, run_dir / "metrics")
        _, valid_daily_quality = prediction_quality(horizon, "valid", x_valid, valid_pred, valid_score,
                                                    valid_windows, valid_records, run_dir / "metrics")
        quality_rows.extend(train_daily_quality + valid_daily_quality)
        for split, pred_by_side, windows in (("train", train_pred, train_windows), ("valid", valid_pred, valid_windows)):
            for side in SIDE_NAMES:
                for window_name, window_target in windows.items():
                    oriented = bidirectional.centered_target_rank(window_target).reindex(pred_by_side[side].index)
                    if side == "low":
                        oriented = -oriented
                    result = series_metrics(_rankic(pred_by_side[side], oriented), lag=horizon)
                    quality_rows.append({"horizon": horizon, "split": split, "target_window": window_name,
                                         "scope": f"event_{side}", **result})

        if horizon == 1:
            h1_accounts = {"train": train_account.copy(), "valid": valid_account.copy()}
        else:
            for split, daily_candidate, score_candidate, target_daily in (
                ("train", train_account, train_score, train_target),
                ("valid", valid_account, valid_score, valid_target),
            ):
                daily_base = h1_accounts[split]
                common_dates = daily_base.index.intersection(daily_candidate.index)
                decomposition = annual_return_decomposition(
                    h1_scores[split], score_candidate,
                    target_daily.loc[target_daily.index.get_level_values("Date").isin(common_dates)],
                    daily_base.loc[common_dates], daily_candidate.loc[common_dates],
                )
                decomposition.update({"split": split, "candidate": f"H{horizon}"})
                decomposition_rows.append(decomposition)
                bootstrap = bootstrap_pair(daily_base.loc[common_dates, "net"], daily_candidate.loc[common_dates, "net"])
                bootstrap.update({"split": split, "candidate": f"H{horizon}"})
                bootstrap_rows.append(bootstrap)

        print(f"finished H{horizon}; Train={len(train_score):,} rows; historical Valid={len(valid_score):,} rows", flush=True)

    pd.DataFrame(portfolio_rows).to_csv(run_dir / "metrics/portfolio_period_metrics.csv", index=False)
    pd.DataFrame(quality_rows).to_csv(run_dir / "metrics/prediction_quality_summary.csv", index=False)
    pd.DataFrame(persistence_rows).to_csv(run_dir / "metrics/persistence_summary.csv", index=False)
    pd.DataFrame(regulation_rows).to_csv(run_dir / "audit/regulation_summary.csv", index=False)
    pd.DataFrame(decomposition_rows).to_csv(run_dir / "metrics/horizon_decomposition.csv", index=False)
    pd.DataFrame(bootstrap_rows).to_csv(run_dir / "metrics/paired_circular_bootstrap.csv", index=False)

    data_files = (
        "raw_return_1day_train.parquet", "beta_1day_train.parquet", "topix_return_1day_train.parquet", "target_1day_train.parquet",
        "raw_return_1day_valid.parquet", "beta_1day_valid.parquet", "topix_return_1day_valid.parquet", "target_1day_valid.parquet",
        "prices_daily_quotes_train.parquet", "prices_daily_quotes_valid.parquet",
    )
    input_hashes = {name: digest(data_dir / name) for name in data_files}
    dump_json(run_dir / "audit/data_hashes.json", {"files": input_hashes,
              "manifest_sha256": digest(ROOT / "stock_comp_2026/input_manifest.json")})
    status.update({"state": "completed", "finished_unix": time.time(),
                   "elapsed_seconds": time.time() - status["started_unix"],
                   "candidates": ["SN1_H1", "SN1_H5", "SN1_H20"],
                   "h1_reproduction_gate": "PASS", "prefix_invariance": "PASS",
                   "valid_treated_as_development": True, "valid_used_for_model_fit": False,
                   "raw_target_file_read": False, "historical_sharpe_selection": False,
                   "input_hashes": input_hashes, "driver_sha256": digest(Path(__file__))})
    dump_json(run_dir / "run.json", status)


if __name__ == "__main__":
    main()
