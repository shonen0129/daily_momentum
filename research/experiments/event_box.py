"""Fixed Train-only event study for the first event-driven box operationalization."""
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from research import evaluation, firewall
from stock_comp_2026.strategies.dm_event_box import core, features
from stock_comp_2026.strategies.dm_variable_box_breakout.features import segment_keys


EXPERIMENT_ID = "DM-20260930-01"
YEARS = tuple(range(2011, 2017))
TRAIN_FILES = ("raw_return_1day_train.parquet", "prices_daily_quotes_train.parquet",
               "target_1day_train.parquet")
ONE_WAY_COST = 0.001
BOOTSTRAP_SEED = 20260930
BOOTSTRAP_REPS = 1000
BOOTSTRAP_BLOCK = 20


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe(value):
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def dump(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(safe(value), ensure_ascii=False, indent=2,
                                     allow_nan=False) + "\n", encoding="utf-8")


def source_scan():
    paths = [Path(core.__file__), Path(features.__file__),
             ROOT / "stock_comp_2026/strategies/dm_event_box/submission.py"]
    forbidden = ("AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose",
                 "AdjustmentVolume", "raw_target", "target_1day_valid")
    for path in paths:
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in source:
                raise AssertionError(f"Forbidden source token {token} in {path}")
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr in ("bfill", "backfill"):
                raise AssertionError(f"Backfill call in {path}")
            if any(key.arg == "center" and isinstance(key.value, ast.Constant) and key.value.value
                   for key in node.keywords):
                raise AssertionError(f"Centered rolling call in {path}")
            if node.func.attr == "shift":
                periods = node.args[0] if node.args else next(
                    (key.value for key in node.keywords if key.arg in ("periods", "period")), None)
                if isinstance(periods, ast.UnaryOp) and isinstance(periods.op, ast.USub):
                    raise AssertionError(f"Negative shift in {path}")
    return [str(path.relative_to(ROOT)) for path in paths]


def mutate_inputs(inputs, cutoff, truncate=False):
    cutoff = pd.Timestamp(cutoff)
    changed = {}
    for name, frame in inputs.items():
        dates = frame.index.get_level_values("Date")
        future = dates > cutoff
        if truncate:
            changed[name] = frame.loc[~future].copy()
            continue
        values = frame.copy()
        if name == "prices_daily_quotes":
            # A common future-only price translation preserves OHLC ordering.
            values.loc[future, ["Open", "High", "Low", "Close"]] = (
                values.loc[future, ["Open", "High", "Low", "Close"]] * 1.37 + 100.0)
            values.loc[future, "AdjustmentFactor"] = 1.0
            future_dates = dates[future]
            if len(future_dates):
                first = future_dates.min()
                values.loc[future & (dates == first), "AdjustmentFactor"] = 0.25
        else:
            values.loc[future, "Return"] = values.loc[future, "Return"] * -3.14 + 8.88
        changed[name] = values
    return changed


def prefix_audit(inputs, original, cutoff):
    cutoff = pd.Timestamp(cutoff)
    dates = original.index.get_level_values("Date")
    prefix_index = original.index[dates <= cutoff]
    expected = original.loc[prefix_index]
    records = {}
    for mode in ("mutation", "truncation"):
        changed = features.build_features(mutate_inputs(inputs, cutoff, truncate=(mode == "truncation")))
        pd.testing.assert_frame_equal(expected, changed.loc[prefix_index], check_exact=True)
        records[mode] = {"status": "PASS", "cutoff": str(cutoff.date()),
                         "prefix_rows": len(prefix_index), "all_input_sources_mutated_or_truncated": True}
    return records


def active_event_account(score, target):
    """Cash-aware long/short event portfolio; each available side has 0.5 gross."""
    score = score.reindex(target.index)
    active = score.notna() & score.ne(0.0)
    positive = active & score.gt(0)
    negative = active & score.lt(0)
    w = pd.Series(0.0, index=target.index, dtype=float)
    long_count = positive.groupby(level="Date").transform("sum").replace(0, np.nan)
    short_count = negative.groupby(level="Date").transform("sum").replace(0, np.nan)
    w.loc[positive] = (0.5 / long_count.loc[positive]).astype(float)
    w.loc[negative] = (-0.5 / short_count.loc[negative]).astype(float)
    turn = w.groupby(level="Code", sort=False).diff().abs()
    first = w.groupby(level="Code", sort=False).cumcount().eq(0)
    turn.loc[first] = w.loc[first].abs()
    turn = turn.fillna(0.0)
    gross_row = w * target
    rankic = evaluation.rankic(score.where(active), target)
    daily = pd.DataFrame({
        "gross": gross_row.groupby(level="Date").sum(),
        "turnover": turn.groupby(level="Date").sum(),
        "long": gross_row.where(w.gt(0), 0.0).groupby(level="Date").sum(),
        "short": gross_row.where(w.lt(0), 0.0).groupby(level="Date").sum(),
        "rankic": rankic,
    })
    daily["cost"] = ONE_WAY_COST * daily.turnover
    daily["cost_all"] = daily["cost"]
    daily["net"] = daily.gross - daily.cost
    daily["net_all_cost"] = daily["net"]
    daily["label_coverage"] = target.notna().groupby(level="Date").mean()
    dates = score.index.get_level_values("Date")
    qrows = {f"q{i}": [] for i in range(1, 6)}
    # Quantiles are defined only over active event names, never over flat names.
    for date, ids in score.loc[active].groupby(level="Date", sort=False).groups.items():
        ids = pd.Index(ids)
        sig = score.loc[ids].sort_index()
        lab = target.reindex(sig.index)
        if len(sig) < 5:
            continue
        rank = sig.groupby(level="Date").rank(method="first")
        n = rank.groupby(level="Date").transform("count")
        q = np.floor(5 * (rank - 1) / n).clip(0, 4).astype(int)
        for i in range(5):
            qrows[f"q{i+1}"].append((date, float(lab.loc[q.eq(i)].mean())))
    for column, rows in qrows.items():
        daily[column] = np.nan
        for date, value in rows:
            daily.loc[date, column] = value
    daily = daily.sort_index()
    return w, daily


def one_day_metrics(daily):
    return evaluation.metrics(daily)


def trade_first_passage(group, signal_positions, max_hold=5, cost=ONE_WAY_COST):
    """Simulate next-open MR entries, conservative same-day TP/SL ordering."""
    records = []
    signals = group["mr_signal"].to_numpy(dtype=int)
    opens = group["Open"].to_numpy(dtype=float)
    highs = group["High"].to_numpy(dtype=float)
    lows = group["Low"].to_numpy(dtype=float)
    uppers = group["box_high"].to_numpy(dtype=float)
    lowers = group["box_low"].to_numpy(dtype=float)
    box_ids = group["box_id"].to_numpy(dtype=int)
    dates = group.index.get_level_values("Date")
    gap_canceled = 0
    for i in signal_positions:
        side = int(signals[i])
        if side == 0 or box_ids[i] < 0 or i + max_hold + 1 >= len(group):
            continue
        entry_i = i + 1
        upper, lower = uppers[i], lowers[i]
        width = upper - lower
        if not (np.isfinite(width) and width > 0 and np.isfinite(opens[entry_i]) and opens[entry_i] > 0):
            continue
        target = (upper + lower) / 2.0
        stop = lower - 0.1 * width if side > 0 else upper + 0.1 * width
        entry = opens[entry_i]
        x0 = 2 * (entry - lower) / width - 1.0
        # If the next open has already passed either boundary, do not chase a stale signal.
        if (side > 0 and (entry <= stop or entry >= target)) or (side < 0 and (entry >= stop or entry <= target)):
            if dates[i].year in YEARS:
                gap_canceled += 1
            continue
        if side > 0:
            p0 = (x0 + 1.2) / 1.2
        else:
            p0 = (1.2 - x0) / 1.2
        p0 = float(np.clip(p0, 0.0, 1.0))
        outcome = "timeout"
        exit_price = np.nan
        exit_i = entry_i + max_hold
        for j in range(entry_i, entry_i + max_hold):
            o, h, l = opens[j], highs[j], lows[j]
            if side > 0:
                if o <= stop:
                    outcome, exit_price, exit_i = "stop_gap", o, j
                    break
                if o >= target:
                    outcome, exit_price, exit_i = "tp_gap", o, j
                    break
                stop_hit, target_hit = l <= stop, h >= target
            else:
                if o >= stop:
                    outcome, exit_price, exit_i = "stop_gap", o, j
                    break
                if o <= target:
                    outcome, exit_price, exit_i = "tp_gap", o, j
                    break
                stop_hit, target_hit = h >= stop, l <= target
            if stop_hit:
                outcome, exit_price, exit_i = "stop", stop, j
                break
            if target_hit:
                outcome, exit_price, exit_i = "take_profit", target, j
                break
        if outcome == "timeout":
            exit_price = opens[exit_i]
        if not np.isfinite(exit_price) or exit_price <= 0:
            continue
        gross = side * (exit_price / entry - 1.0)
        is_tp = outcome in ("take_profit", "tp_gap")
        is_sl = outcome in ("stop", "stop_gap")
        records.append({
            "signal_date": dates[i], "entry_date": dates[entry_i], "exit_date": dates[exit_i],
            "Code": group.index.get_level_values("Code")[i], "box_id": box_ids[i],
            "side": "long" if side > 0 else "short", "entry_price": entry,
            "exit_price": exit_price, "gross_return": gross, "net_return": gross - 2 * cost,
            "outcome": outcome, "take_profit_first": int(is_tp), "stop_first": int(is_sl),
            "resolved": bool(is_tp or is_sl), "p0": p0, "edge_p_minus_p0": (int(is_tp) - p0) if (is_tp or is_sl) else np.nan,
            "holding_sessions": int(exit_i - entry_i),
        })
    return records, gap_canceled


def fixed_horizon_trades(group, event_col, side_value=1, max_hold=5, cost=ONE_WAY_COST):
    signals = np.flatnonzero(group[event_col].to_numpy(dtype=float) == side_value)
    opens = group["Open"].to_numpy(dtype=float)
    dates = group.index.get_level_values("Date")
    code = group.index.get_level_values("Code")[0]
    rows = []
    for i in signals:
        entry_i, exit_i = i + 1, i + max_hold + 1
        if exit_i >= len(group) or not (opens[entry_i] > 0 and opens[exit_i] > 0):
            continue
        gross = opens[exit_i] / opens[entry_i] - 1.0
        rows.append({"signal_date": dates[i], "entry_date": dates[entry_i], "exit_date": dates[exit_i],
                     "Code": code, "gross_return": gross, "net_return": gross - 2 * cost,
                     "holding_sessions": max_hold, "outcome": "fixed_5_session_exit"})
    return rows


def clustered_bootstrap_edge(trades, evaluation_calendar=None):
    resolved = trades.loc[trades.resolved].copy()
    if resolved.empty:
        return {"trades": 0, "low": None, "high": None, "positive_fraction": None}
    daily = resolved.groupby("entry_date").edge_p_minus_p0.agg(["sum", "count"])
    calendar = (pd.DatetimeIndex(sorted(daily.index.unique())) if evaluation_calendar is None
                else pd.DatetimeIndex(evaluation_calendar).unique().sort_values())
    sums = daily["sum"].reindex(calendar, fill_value=0.0).to_numpy()
    counts = daily["count"].reindex(calendar, fill_value=0).to_numpy(dtype=float)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    nblocks = int(np.ceil(len(calendar) / BOOTSTRAP_BLOCK))
    samples = np.empty(BOOTSTRAP_REPS, dtype=float)
    for k in range(BOOTSTRAP_REPS):
        starts = rng.integers(0, len(calendar), size=nblocks)
        ix = ((starts[:, None] + np.arange(BOOTSTRAP_BLOCK)) % len(calendar)).ravel()[:len(calendar)]
        total_n = counts[ix].sum()
        samples[k] = sums[ix].sum() / total_n if total_n > 0 else np.nan
    samples = samples[np.isfinite(samples)]
    return {"trades": int(len(resolved)), "low": float(np.quantile(samples, .025)),
            "high": float(np.quantile(samples, .975)),
            "positive_fraction": float((samples > 0).mean()), "seed": BOOTSTRAP_SEED,
            "repetitions": BOOTSTRAP_REPS, "block_days": BOOTSTRAP_BLOCK}


def annual_trade_summary(trades, name):
    if trades.empty:
        return pd.DataFrame(columns=["year", "strategy", "trades"])
    part = trades.copy()
    part["year"] = pd.DatetimeIndex(part.entry_date).year
    rows = []
    for year, frame in part.groupby("year", sort=True):
        row = {"year": int(year), "strategy": name, "trades": len(frame),
               "mean_gross_return": frame.gross_return.mean(),
               "mean_net_return": frame.net_return.mean(),
               "net_win_rate": (frame.net_return > 0).mean(),
               "median_net_return": frame.net_return.median(),
               "mean_holding_sessions": frame.holding_sessions.mean()}
        if "resolved" in frame:
            resolved = frame.loc[frame.resolved]
            row.update({"resolved_trades": len(resolved),
                        "p_take_profit_first": resolved.take_profit_first.mean() if len(resolved) else np.nan,
                        "mean_p0": resolved.p0.mean() if len(resolved) else np.nan,
                        "mean_p_minus_p0": resolved.edge_p_minus_p0.mean() if len(resolved) else np.nan,
                        "timeout_rate": (frame.outcome == "timeout").mean()})
        rows.append(row)
    return pd.DataFrame(rows)


def make_donchian(inputs, prices):
    index = prices.index
    groups = segment_keys(index)
    high, low, close = prices["High"], prices["Low"], prices["Close"]
    prior_close = close.groupby(groups, sort=False).shift(1)
    tr = pd.concat([high - low, (high - prior_close).abs(), (low - prior_close).abs()], axis=1).max(axis=1, skipna=False)
    atr = tr.groupby(groups, sort=False).transform(lambda x: x.shift(1).rolling(20, min_periods=20).mean())
    upper = high.groupby(groups, sort=False).transform(lambda x: x.shift(1).rolling(20, min_periods=20).max())
    previous_close = close.groupby(groups, sort=False).shift(1)
    previous_upper = upper.groupby(groups, sort=False).shift(1)
    event = close.gt(upper) & previous_close.le(previous_upper)
    strength = ((close - upper) / atr).where(event, 0.0).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    return pd.DataFrame({"signal": event.fillna(False).astype(int),
                         "strength": strength.rename("donchian_strength")}, index=index)


def event_date_metrics(scores, target, cutoff_dates):
    rows, daily_by_name = [], {}
    for name, score in scores.items():
        w, daily = active_event_account(score, target)
        daily = daily.reindex(cutoff_dates).fillna({"gross": 0.0, "turnover": 0.0, "long": 0.0,
                                                   "short": 0.0, "cost": 0.0, "net": 0.0})
        daily_by_name[name] = daily
        for year in YEARS:
            year_dates = cutoff_dates[cutoff_dates.year == year]
            year_daily = daily.loc[year_dates]
            rows.append({"strategy": name, "year": year, **one_day_metrics(year_daily)})
        rows.append({"strategy": name, "year": "pooled", **one_day_metrics(daily)})
    return pd.DataFrame(rows), daily_by_name


def make_report(metrics, mr_trades, bo_trades, donchian_trades, bootstrap, audit):
    mr = mr_trades
    resolved = mr.loc[mr.resolved]
    p = resolved.take_profit_first.mean() if len(resolved) else np.nan
    p0 = resolved.p0.mean() if len(resolved) else np.nan
    net_ev = mr.net_return.mean() if len(mr) else np.nan
    lines = [
        "# DM-20260930-01: Event-driven box first trial", "",
        "Train-only descriptive result. No Valid file/label was opened; all Train years were previously inspected and are not an independent holdout.", "",
        "## Fixed design", "",
        "Seed the initial BOX from the prior 20 sessions when width is 0.5–3.0 prior ATR20 and the current close remains within the fixed bounds. Use one ATR reversal for the post-breakout swing high/low. Fixed MR entry/target/stop/timeout are |x|≥0.8 / x=0 / |x|=1.2 / 5 sessions; `kSL=0.5`, `kBO=1.0`, `kfail=0.5`, formation timeout 40 sessions. Same-bar TP and SL resolves to SL; entries and timeouts execute at the next Open.", "",
        "## Causal and execution audits", "",
        f"- Static source scan: {', '.join(audit['source_scan'])}",
        f"- Future mutation/truncation prefix audit: {audit['prefix_invariance']['mutation']['status']} / {audit['prefix_invariance']['truncation']['status']} at {audit['prefix_invariance']['mutation']['cutoff']}.",
        f"- Train firewall: {audit['firewall']['status']}; opened inputs: {', '.join(Path(p).name for p in audit['firewall']['opened_parquets'])}",
        f"- Prediction coverage: {audit['prediction_rows']:,}/{audit['target_rows']:,}; deterministic replay: {audit['determinism']}; index alignment: {audit['index_alignment']}.", "",
        "## MR first-passage diagnostic", "",
        f"- Eligible episodes: {len(mr):,}; TP/SL-resolved: {len(resolved):,}; timeouts: {int((mr.outcome == 'timeout').sum()) if len(mr) else 0:,}; gap-canceled entries: {audit['gap_canceled_mr']:,}.",
        f"- Resolved TP-first rate p={p:.4f}; mean analytic driftless p0={p0:.4f}; p-p0={p-p0:+.4f}.",
        f"- Date-clustered 20-session bootstrap 95% interval for p-p0: [{bootstrap.get('low')}, {bootstrap.get('high')}], positive fraction={bootstrap.get('positive_fraction')}.",
        f"- Mean episode return: gross={mr.gross_return.mean():+.5%}, net after 10bp each way={net_ev:+.5%}; the strategy continuation gate also requires a bootstrap lower bound above zero and multi-year consistency.", "",
        "## BO event comparison", "",
        f"- Event-box upward breakouts: {len(bo_trades):,}; prior-20 Donchian upward breakouts: {len(donchian_trades):,}.",
        "- Both are entered at next Open and held for the same five-session horizon for this entry-timing comparison; this does not test the eventual BOX lifecycle exit.", "",
        "## One-day event-entry portfolio", "",
        "Daily long and short event names share 0.5 gross per available side; inactive names remain cash. Returns use the official Train `target_1day` (next Open to following Open) and 10bp one-way turnover cost. Q1–Q5 are ranked only among active events. This is an entry-day diagnostic, not a submission-equivalent portfolio.", "",
        "| Signal | Entry year | Net Sharpe | Gross Sharpe | Annual net P/L | Annual cost | Turnover/day | RankIC | HAC5 t | Q monotonicity | Max DD |",
        "|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in metrics.to_dict("records"):
        lines.append(f"| {row['strategy']} | {row['year']} | {row.get('net_sharpe', np.nan):+.3f} | {row.get('gross_sharpe', np.nan):+.3f} | {row.get('annual_net', np.nan):+.3%} | {row.get('annual_cost', np.nan):.3%} | {row.get('turnover', np.nan):.4f} | {row.get('rankic', np.nan):+.4f} | {row.get('rankic_t_hac5', np.nan):+.2f} | {row.get('q_monotonicity', np.nan):+.3f} | {row.get('max_drawdown_additive', np.nan):+.3%} |")
    lines.extend(["", "## Annual episode outcomes", "", "See `metrics/annual_episode_metrics.csv` for MR TP rate, p0, p-p0, net expectancy, timeout rate, and matched-horizon BO / Donchian returns.", "",
                  "## Decision", "",
                  "One fixed operationalization only. No post-result parameter changes are permitted. If MR first-passage and net-expectancy gates fail, reject this operationalization and stop. Even if descriptive gates pass, do not call this independent OOS or freeze it; a separate null-process and integrated lifecycle phase is still required.", ""])
    return "\n".join(lines)


def run(config_path, output_path):
    started = time.monotonic()
    output = Path(output_path).resolve()
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if (config.get("experiment_id") != EXPERIMENT_ID or config.get("data_split") != "train"
            or config.get("valid_evaluation") is not False or config.get("max_trials") != 1
            or len(config.get("trials", [])) != 1):
        raise ValueError("Unexpected run scope; only the registered fixed Train trial is allowed")
    metadata_path = output / "run.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    source_paths = [Path(__file__).resolve(), Path(core.__file__).resolve(), Path(features.__file__).resolve(),
                    ROOT / "stock_comp_2026/strategies/dm_event_box/submission.py",
                    ROOT / "stock_comp_2026/strategies/dm_variable_box_breakout/features.py",
                    Path(evaluation.__file__).resolve(), Path(firewall.__file__).resolve(), config_path]
    metadata.update({"status": "running", "started_at_utc": datetime.now(timezone.utc).isoformat(),
                     "command": sys.argv, "actual_trials": 1, "valid_accessed": False,
                     "environment": {"python": sys.version, "platform": platform.platform(),
                                     "numpy": np.__version__, "pandas": pd.__version__},
                     "code_sha256": {str(path.relative_to(ROOT)): digest(path) for path in source_paths}})
    dump(metadata_path, metadata)
    try:
        data_root = ROOT / "stock_comp_2026/input"
        stage = output / "train_stage"
        stage.mkdir(exist_ok=True)
        staged_paths = []
        for name in TRAIN_FILES:
            source = data_root / name
            destination = stage / name
            if not destination.exists():
                destination.symlink_to(source.resolve())
            staged_paths.append(str(source.resolve()))
        firewall.install()
        inputs = features.load_inputs(stage, split="train")
        target = pd.read_parquet(stage / "target_1day_train.parquet")["Return"].sort_index()
        index = inputs["raw_return_1day"].index
        if not target.index.equals(index):
            raise AssertionError("Train target and feature index do not align exactly")
        dates = pd.DatetimeIndex(index.get_level_values("Date").unique().sort_values())
        if str(dates.min().date()) != "2008-11-04" or str(dates.max().date()) != "2016-03-31":
            raise AssertionError("Unexpected Train data range")

        scanned = source_scan()
        state = features.build_features(inputs)
        replay = features.build_features(inputs)
        pd.testing.assert_frame_equal(state, replay, check_exact=True)
        if not state.index.equals(target.index) or not np.isfinite(state["mr_signal"].to_numpy()).all():
            raise AssertionError("Output coverage, index, or finite-signal check failed")
        audit_prefix = prefix_audit(inputs, state, "2014-12-30")
        prices = features.split_safe_ohlc(inputs)
        pd.testing.assert_series_equal(features.signal_from_features(state),
                                       features.signal_from_features(replay), check_exact=True)

        panel = prices.join(state, how="left")
        if not panel.index.equals(target.index):
            raise AssertionError("Price, state and Train target index alignment failed")
        panel["mr_event_score"] = np.nan
        active_mr = panel["mr_signal"].ne(0)
        panel.loc[active_mr, "mr_event_score"] = -panel.loc[active_mr, "close_position"]
        panel["box_bo_event_score"] = np.nan
        upper_events = panel["bo_signal"].eq(1)
        panel.loc[upper_events, "box_bo_event_score"] = panel.loc[upper_events, "bo_strength"]
        donchian = make_donchian(inputs, prices)
        panel["donchian_signal"] = donchian["signal"]
        panel["donchian_event_score"] = donchian["strength"].where(donchian["signal"].eq(1))

        mr_records, bo_records, donchian_records = [], [], []
        gap_canceled_mr = 0
        for _, group in panel.groupby(level="Code", sort=False):
            mr_positions = np.flatnonzero(group["mr_signal"].to_numpy(dtype=int) != 0)
            rows, canceled = trade_first_passage(group, mr_positions, max_hold=5)
            mr_records.extend(rows)
            gap_canceled_mr += canceled
            bo_records.extend(fixed_horizon_trades(group, "bo_signal", side_value=1, max_hold=5))
            donchian_records.extend(fixed_horizon_trades(group, "donchian_signal", side_value=1, max_hold=5))
        mr = pd.DataFrame(mr_records)
        bo = pd.DataFrame(bo_records)
        donchian_trades = pd.DataFrame(donchian_records)
        if mr.empty:
            mr = pd.DataFrame(columns=["signal_date", "entry_date", "exit_date", "Code", "box_id", "side",
                                       "entry_price", "exit_price", "gross_return", "net_return", "outcome",
                                       "take_profit_first", "stop_first", "resolved", "p0", "edge_p_minus_p0",
                                       "holding_sessions"])
        if bo.empty:
            bo = pd.DataFrame(columns=["signal_date", "entry_date", "exit_date", "Code", "gross_return",
                                       "net_return", "holding_sessions", "outcome"])
        if donchian_trades.empty:
            donchian_trades = bo.iloc[:0].copy()
        for frame in (mr, bo, donchian_trades):
            if not frame.empty:
                entry_year = pd.DatetimeIndex(frame.entry_date).year
                frame.drop(frame.index[~pd.Index(entry_year).isin(YEARS)], inplace=True)
        mr_keys = set(zip(mr.signal_date, mr.Code))
        bo_keys = set(zip(bo.signal_date, bo.Code))
        donchian_keys = set(zip(donchian_trades.signal_date, donchian_trades.Code))
        score_keys = list(panel.index)
        mr_mask = pd.Series([key in mr_keys for key in score_keys], index=panel.index)
        bo_mask = pd.Series([key in bo_keys for key in score_keys], index=panel.index)
        donchian_mask = pd.Series([key in donchian_keys for key in score_keys], index=panel.index)
        scores = {
            "MR_entry": panel["mr_event_score"].where(mr_mask),
            "BOX_BO_entry": panel["box_bo_event_score"].where(bo_mask),
            "Donchian20_entry": panel["donchian_event_score"].where(donchian_mask),
        }
        evaluation_dates = dates[dates.year.isin(YEARS)]
        daily_metrics, daily = event_date_metrics(scores, target, evaluation_dates)
        eval_index = index[index.get_level_values("Date").year.isin(YEARS)]
        pd.DataFrame({name: score.reindex(eval_index) for name, score in scores.items()},
                     index=eval_index).sort_index().to_parquet(output / "predictions/event_entry_scores.parquet")
        mr.to_csv(output / "metrics/mr_episodes.csv", index=False)
        bo.to_csv(output / "metrics/box_bo_5day_trades.csv", index=False)
        donchian_trades.to_csv(output / "metrics/donchian_5day_trades.csv", index=False)
        annual_mr = annual_trade_summary(mr, "MR")
        annual_bo = annual_trade_summary(bo, "BOX_BO_5day")
        annual_donchian = annual_trade_summary(donchian_trades, "Donchian20_5day")
        pd.concat([annual_mr, annual_bo, annual_donchian], ignore_index=True).to_csv(
            output / "metrics/annual_episode_metrics.csv", index=False)
        bootstrap = clustered_bootstrap_edge(mr, evaluation_dates) if not mr.empty else {
            "trades": 0, "low": None, "high": None, "positive_fraction": None}
        dump(output / "metrics/mr_first_passage_bootstrap.json", bootstrap)
        daily_frame = pd.concat({name: frame for name, frame in daily.items()}, axis=1)
        daily_frame.to_csv(output / "metrics/daily_event_portfolios.csv")
        audit = {
            "source_scan": scanned,
            "prefix_invariance": audit_prefix,
            "firewall": {"status": "PASS", "opened_parquets": sorted(firewall.ACCESSES),
                         "guarded_reader_apis": sorted(firewall.GUARDED_READS),
                         "valid_evaluation": False, "raw_target_reads": False},
            "prediction_rows": int(len(state)), "target_rows": int(len(target)),
            "index_alignment": "PASS", "determinism": "PASS",
            "finite_event_signals": int(np.isfinite(state["mr_signal"].to_numpy()).sum()),
            "gap_canceled_mr": int(gap_canceled_mr),
            "seed": BOOTSTRAP_SEED,
            "trial_count": 1,
            "stage_inputs": staged_paths,
        }
        dump(output / "audit/audit.json", audit)
        firewall.save(output / "audit/firewall.json")
        report = make_report(daily_metrics, mr, bo, donchian_trades, bootstrap, audit)
        (output / "report_draft.md").write_text(report, encoding="utf-8")
        for path in staged_paths:
            if not path.endswith("_train.parquet") and not path.endswith("target_1day_train.parquet"):
                raise AssertionError(f"Non-Train file staged: {path}")
        metadata.update({"status": "completed", "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                         "exit_code": 0, "actual_trials": 1,
                         "train_data_sha256": {Path(path).name: digest(path) for path in staged_paths},
                         "run_seconds": time.monotonic() - started,
                         "valid_accessed": False, "firewall_audit": "audit/firewall.json"})
        dump(metadata_path, metadata)
        print(json.dumps({"status": "completed", "run_seconds": metadata["run_seconds"],
                          "mr_episodes": len(mr), "mr_resolved": int(mr.resolved.sum()) if len(mr) else 0,
                          "mr_mean_net": float(mr.net_return.mean()) if len(mr) else None,
                          "mr_p_minus_p0": float(mr.loc[mr.resolved, "edge_p_minus_p0"].mean()) if len(mr) and mr.resolved.any() else None,
                          "box_bo_5day": len(bo), "donchian_5day": len(donchian_trades)}, ensure_ascii=False), flush=True)
    except BaseException as error:
        metadata.update({"status": "failed", "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                         "exit_code": 1, "failure": f"{type(error).__name__}: {error}",
                         "run_seconds": time.monotonic() - started})
        dump(metadata_path, metadata)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.config, args.output)


if __name__ == "__main__":
    main()
