"""Fixed H1 SN1 entry/state predictive and return-attribution diagnostics."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from research import evaluation  # noqa: E402

REF_RUN = ROOT / "artifacts/DM-20260927-04/run-20260927T101500Z"
PHASE1_RUN_NAME = "run-20260927T154814Z"
LAGS = (1, 5, 20, 40, 60)
SPLITS = ("train", "historical_valid")
HORIZONS = (1, 5)
ANNUALIZATION = 252
COST_RATE = 0.001
AGE_BANDS = ["under_20", "20_59", "60_119", "120_299", "300_plus"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def install_phase2_read_guard(phase1_table: Path, allowed_targets: list[Path], allowed_scores: list[Path]):
    original = pd.read_parquet
    allowed = {p.resolve() for p in [phase1_table, *allowed_targets, *allowed_scores]}
    accesses = []

    def guarded(path, *args, **kwargs):
        resolved = Path(path).resolve()
        if resolved not in allowed:
            raise PermissionError(f"Phase 2 firewall denied unexpected parquet: {resolved}")
        if "raw_target" in resolved.name.lower() or "paper" in str(resolved).lower():
            raise PermissionError(f"Phase 2 firewall denied raw target/paper data: {resolved}")
        accesses.append(str(resolved))
        return original(path, *args, **kwargs)

    pd.read_parquet = guarded
    return accesses


def load_return(path: Path) -> pd.Series:
    frame = pd.read_parquet(path)
    if isinstance(frame, pd.Series):
        out = frame
    elif "Return" in frame.columns:
        out = frame["Return"]
    else:
        if frame.shape[1] != 1:
            raise ValueError(f"Expected a single Return target column in {path}")
        out = frame.iloc[:, 0]
    if not isinstance(out.index, pd.MultiIndex) or list(out.index.names) != ["Date", "Code"]:
        raise ValueError(f"Target must have (Date, Code) index: {path}")
    out.index = pd.MultiIndex.from_arrays(
        [pd.DatetimeIndex(out.index.get_level_values("Date")), out.index.get_level_values("Code").astype(str)],
        names=["Date", "Code"],
    )
    out = pd.to_numeric(out, errors="coerce").astype("float64").sort_index()
    if not out.index.is_unique:
        raise ValueError(f"Duplicate target index: {path}")
    return out


def daily_rankic(signal: pd.Series, target: pd.Series) -> pd.Series:
    signal = signal.astype("float64")
    target = target.reindex(signal.index).astype("float64")
    good = signal.notna() & target.notna() & np.isfinite(signal) & np.isfinite(target)
    if not good.any():
        return pd.Series(dtype="float64", name="rankic")
    x = signal.where(good).groupby(level="Date", sort=True).rank(method="average")
    y = target.where(good).groupby(level="Date", sort=True).rank(method="average")
    x = x - x.groupby(level="Date", sort=True).transform("mean")
    y = y - y.groupby(level="Date", sort=True).transform("mean")
    numerator = (x * y).groupby(level="Date", sort=True).sum(min_count=2)
    xx = (x * x).groupby(level="Date", sort=True).sum(min_count=2)
    yy = (y * y).groupby(level="Date", sort=True).sum(min_count=2)
    return (numerator / np.sqrt(xx * yy)).replace([np.inf, -np.inf], np.nan).rename("rankic")


def daily_top_bottom_spread(signal: pd.Series, target: pd.Series) -> pd.Series:
    signal = signal.astype("float64")
    target = target.reindex(signal.index).astype("float64")
    good = signal.notna() & target.notna() & np.isfinite(signal) & np.isfinite(target)
    x = signal.where(good)
    y = target.where(good)
    count = x.groupby(level="Date", sort=True).transform("count")
    rank = x.groupby(level="Date", sort=True).rank(method="first")
    quintile = (np.ceil(5 * (rank - 1) / (count - 1)) - 1).clip(0, 4)
    q1 = y.where((quintile == 0) & count.ge(5)).groupby(level="Date", sort=True).mean()
    q5 = y.where((quintile == 4) & count.ge(5)).groupby(level="Date", sort=True).mean()
    return (q5 - q1).dropna().rename("q5_minus_q1")


def metric_record(signal: pd.Series, target: pd.Series, orientation: pd.Series | None, horizon: int,
                  split: str, side: str, score_role: str, lag: int) -> dict:
    target = target.reindex(signal.index)
    daily_ic = daily_rankic(signal, target)
    daily_spread = daily_top_bottom_spread(signal, target)
    valid = signal.notna() & target.notna() & np.isfinite(signal) & np.isfinite(target)
    t = target.loc[valid]
    rec = {
        "split": split, "event_side": side, "horizon": horizon, "fixed_lag": lag,
        "score_role": score_role, "stock_days": int(valid.sum()),
        "dates_with_observations": int(valid.index.get_level_values("Date")[valid].nunique()),
        "mean_daily_rankic": float(daily_ic.mean()) if len(daily_ic) else np.nan,
        "rankic_hac_t": float(evaluation.hac_t(daily_ic.dropna(), lag=max(1, horizon))) if len(daily_ic.dropna()) >= 3 else np.nan,
        "rankic_hit_rate": float((daily_ic.dropna() > 0).mean()) if len(daily_ic.dropna()) else np.nan,
        "rankic_days": int(daily_ic.notna().sum()),
        "oriented_return_sign_hit_rate": float((t > 0).mean()) if len(t) else np.nan,
        "daily_q5_minus_q1_oriented_residual": float(daily_spread.mean()) if len(daily_spread) else np.nan,
        "spread_hac_t": float(evaluation.hac_t(daily_spread.dropna(), lag=max(1, horizon))) if len(daily_spread.dropna()) >= 3 else np.nan,
        "spread_days": int(daily_spread.notna().sum()),
        "target_window": "existing saved H1 one-day target" if horizon == 1 else "existing saved H5 diagnostic target",
    }
    if orientation is not None:
        rec["score_target_sign_concordance"] = float((signal.loc[valid] * orientation.reindex(signal.index).loc[valid] > 0).mean()) if len(t) else np.nan
    return rec


def next_side_survival(frame: pd.DataFrame, split: str) -> pd.Series:
    sub = frame.loc[frame.split.astype(str).eq(split)]
    cal = pd.DatetimeIndex(sub.index.get_level_values("Date").unique().sort_values())
    codes = pd.Index(sub.index.get_level_values("Code").unique().sort_values())
    side_matrix = sub.portfolio_side_code.unstack("Code").reindex(index=cal, columns=codes).fillna(0).to_numpy(dtype="int8")
    dpos = cal.get_indexer(sub.index.get_level_values("Date"))
    cpos = codes.get_indexer(sub.index.get_level_values("Code"))
    current = sub.portfolio_side_code.to_numpy(dtype="int8")
    survival = {}
    for h in (5, 20, 60):
        future = np.zeros(len(sub), dtype="int8")
        ok = dpos + h < len(cal)
        future[ok] = side_matrix[dpos[ok] + h, cpos[ok]]
        survival[h] = pd.Series((current != 0) & (future == current), index=sub.index)
    return pd.DataFrame(survival, index=sub.index).rename(columns={5: "survival_5d", 20: "survival_20d", 60: "survival_60d"})


def account_replay(signal: pd.Series, target: pd.Series, saved_path: Path, split: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    signal = signal.reindex(target.index).sort_index().fillna(0.0)
    target = target.reindex(signal.index)
    weights, quintile = evaluation.weights(signal)
    turnover = weights.groupby(level="Code", sort=False).diff().abs().fillna(weights.abs())
    official = evaluation.daily_account(signal, target)
    saved = pd.read_csv(saved_path, parse_dates=[0], index_col=0)
    saved.index = pd.DatetimeIndex(saved.index)
    common = official.index.intersection(saved.index)
    diffs = {}
    for col in ("gross", "net", "cost", "turnover"):
        diffs[col] = float((official.loc[common, col] - saved.loc[common, col]).abs().max()) if len(common) else np.nan
    if len(common) != len(saved.index) or any((not np.isfinite(v)) or v > 1e-12 for v in diffs.values()):
        raise AssertionError(f"Saved official H1 daily account replay failed ({split}): {diffs}, days={len(common)} vs {len(saved)}")
    row = pd.DataFrame({"target": target, "weight": weights, "turnover": turnover}, index=weights.index)
    row["gross_contribution"] = row.weight * row.target
    row["cost_contribution"] = COST_RATE * row.turnover
    row["official_cost_contribution"] = row.cost_contribution.where(row.target.notna(), 0.0)
    # This exactly matches pandas' official daily_account expression: a missing target row drops both legs.
    row["net_contribution"] = row.gross_contribution - row.cost_contribution
    row["date"] = row.index.get_level_values("Date")
    row["split"] = split
    row["quintile"] = quintile.astype("int8") + 1
    return row, official, {"split": split, "saved_days": int(len(saved)), "replayed_days": int(len(common)),
                           "max_abs_difference": diffs, "pass": True}


def summarize_attribution(rows: pd.DataFrame, dims: list[str], account_dates_by_split: dict[str, pd.DatetimeIndex],
                          annual: bool = False) -> pd.DataFrame:
    frame = rows.copy()
    if annual:
        frame["year"] = pd.DatetimeIndex(frame.date).year.astype(str)
        group = ["split", "year", *dims]
    else:
        group = ["split", *dims]
    result = []
    for keys, part in frame.groupby(group, observed=True, sort=True, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        values = dict(zip(group, keys))
        split = str(values["split"])
        dates = pd.DatetimeIndex(account_dates_by_split[split])
        daily = part.groupby("date", sort=True).agg(
            gross=("gross_contribution", "sum"), net=("net_contribution", "sum"),
            cost=("official_cost_contribution", "sum"),
            turnover=("turnover", "sum"),
        ).reindex(dates, fill_value=0.0)
        if annual:
            year = str(values["year"])
            dates = dates[dates.year.astype(str) == year]
            daily = daily.reindex(dates, fill_value=0.0)
        n_days = len(daily)
        gross_series, net_series = daily.gross, daily.net
        gross_sd = gross_series.std(ddof=1) if len(gross_series) > 1 else np.nan
        net_sd = net_series.std(ddof=1) if len(net_series) > 1 else np.nan
        values.update({
            "stock_days": int(len(part)), "gross_weight_sum": float(part.weight.abs().sum()),
            "annual_gross_contribution": float(gross_series.mean() * ANNUALIZATION) if n_days else np.nan,
            "annual_net_contribution": float(net_series.mean() * ANNUALIZATION) if n_days else np.nan,
            "annual_cost_contribution": float(daily.cost.mean() * ANNUALIZATION) if n_days else np.nan,
            "mean_daily_turnover_contribution": float(daily.turnover.mean()) if n_days else np.nan,
            "attributed_gross_sr": float(gross_series.mean() / gross_sd * np.sqrt(ANNUALIZATION)) if n_days > 1 and gross_sd > 0 else np.nan,
            "attributed_net_sr": float(net_series.mean() / net_sd * np.sqrt(ANNUALIZATION)) if n_days > 1 and net_sd > 0 else np.nan,
            "active_dates": int(part.date.nunique()), "account_dates_in_period": n_days,
        })
        for h in (5, 20, 60):
            col = f"survival_{h}d"
            if col in part:
                values[col] = float(part[col].mean())
        result.append(values)
    return pd.DataFrame(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase1-run", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    phase1 = args.phase1_run.resolve()
    run_dir = args.run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    for name in ("audit", "metrics", "predictions"):
        (run_dir / name).mkdir()

    lock_path = ROOT / "experiments/DM-20260928-01/phase1_lock.json"
    lock_hash_path = Path(str(lock_path) + ".sha256")
    expected_lock_hash = lock_hash_path.read_text(encoding="utf-8").split()[0]
    if sha256(lock_path) != expected_lock_hash:
        raise AssertionError("Phase 1 lock hash mismatch; Phase 2 stopped before target reads")
    phase1_manifest = json.loads((phase1 / "audit/phase1_manifest.json").read_text(encoding="utf-8"))
    if sha256(phase1 / "audit/date_code_state.parquet") != phase1_manifest["score_table_sha256"]:
        raise AssertionError("Phase 1 state table hash mismatch; Phase 2 stopped before target reads")

    target_paths = []
    score_paths = []
    for split, alias in (("train", "train"), ("historical_valid", "valid")):
        for h in HORIZONS:
            target_paths.append(REF_RUN / f"predictions/target_{alias}_H{h}.parquet")
        score_paths.append(REF_RUN / f"predictions/SN1_H1_{split}.parquet")
    accesses = install_phase2_read_guard(phase1 / "audit/date_code_state.parquet", target_paths, score_paths)
    started = time.time()
    meta = {
        "experiment_id": "DM-20260928-01", "run_id": run_dir.name,
        "phase": "phase2_fixed_age_and_event_lag_descriptive_pnl",
        "state": "running", "git_head": None, "phase1_lock_sha256": expected_lock_hash,
        "phase1_table_sha256": phase1_manifest["score_table_sha256"],
        "experiment_plan_sha256": sha256(ROOT / "experiments/DM-20260928-01/plan.md"),
        "experiment_config_sha256": sha256(ROOT / "experiments/DM-20260928-01/config.json"),
        "driver_sha256": sha256(Path(__file__).resolve()),
        "started_unix": started, "python": sys.version, "platform": platform.platform(),
        "numpy": np.__version__, "pandas": pd.__version__, "target_used_for_model_fit": False,
        "candidate_pnl_run": False, "paper_data_accessed": False,
        "allowed_targets": [str(p.relative_to(ROOT)) for p in target_paths],
        "locked_lags": list(LAGS), "locked_diagnostic_horizons": list(HORIZONS),
    }
    import subprocess
    meta["git_head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    write_json(run_dir / "run.json", meta)

    table = pd.read_parquet(phase1 / "audit/date_code_state.parquet").sort_index()
    # Fixed saved labels: H1 official residual outcome plus already-existing H5 diagnostic target.
    targets = {}
    score_full = {}
    for split, alias in (("train", "train"), ("historical_valid", "valid")):
        targets[split] = {h: load_return(REF_RUN / f"predictions/target_{alias}_H{h}.parquet") for h in HORIZONS}
        score_full[split] = load_return(REF_RUN / f"predictions/SN1_H1_{split}.parquet")
    if not targets["train"][1].index.equals(score_full["train"].index):
        raise AssertionError("Train H1 target and saved score index mismatch")
    if not targets["historical_valid"][1].index.equals(score_full["historical_valid"].index):
        raise AssertionError("Historical-Valid H1 target and saved score index mismatch")

    # Event-date EntryScore and same-side state after exactly 1/5/20/40/60 market sessions.
    entry_rows, state_lag_rows = [], []
    for split in SPLITS:
        g = table.loc[table.split.astype(str).eq(split)]
        for side in ("high", "low"):
            is_high = side == "high"
            raw_col = "high_raw_event_score" if is_high else "low_raw_event_score"
            event_mask = g[raw_col].ne(0.0)
            entry_signal = g[raw_col] if is_high else -g[raw_col]
            side_sign = 1.0 if is_high else -1.0
            for h in HORIZONS:
                y_event = targets[split][h].reindex(g.index) * side_sign
                selected_entry = entry_signal.where(event_mask)
                entry_rows.append(metric_record(
                    selected_entry, y_event, None, h, split, side, "EntryScore on event date", 0
                ))
            # The first historical-Valid states may still descend from late-Train
            # events, so resolve origin scores against the continuous locked table.
            all_event_mask = table[raw_col].ne(0.0)
            all_event_signal = table[raw_col] if is_high else -table[raw_col]
            event_lookup = all_event_signal.loc[all_event_mask]
            for lag in LAGS:
                age_col = f"{side}_event_age_trading_days"
                age_mask = g[age_col].eq(lag)
                if is_high:
                    current_state = g.high_state
                    origin_date = g.last_high_event_date
                    opposite_age = g.low_event_age_trading_days
                else:
                    current_state = -g.low_state
                    origin_date = g.last_low_event_date
                    opposite_age = g.high_event_age_trading_days
                event_index = pd.MultiIndex.from_arrays(
                    [pd.DatetimeIndex(origin_date.loc[age_mask]), g.index.get_level_values("Code")[age_mask]],
                    names=["Date", "Code"],
                )
                origin_signal = pd.Series(event_lookup.reindex(event_index).to_numpy(dtype="float64"), index=g.index[age_mask], dtype="float64")
                if origin_signal.isna().any():
                    raise AssertionError(f"Missing origin EntryScore for {split}/{side}/lag={lag}")
                state_signal = current_state.loc[age_mask]
                opposite_since_event = opposite_age.loc[age_mask].lt(lag) & opposite_age.loc[age_mask].notna()
                opposite_rate = float(opposite_since_event.mean()) if len(opposite_since_event) else np.nan
                for h in HORIZONS:
                    y_now = targets[split][h].reindex(g.index[age_mask]) * side_sign
                    entry_rec = metric_record(
                        origin_signal, y_now, None, h, split, side,
                        "origin EntryScore evaluated at t+lag", lag,
                    )
                    state_rec = metric_record(
                        state_signal, y_now, None, h, split, side,
                        "same-side StateScore at t+lag", lag,
                    )
                    entry_rec["opposite_event_since_origin_rate"] = opposite_rate
                    state_rec["opposite_event_since_origin_rate"] = opposite_rate
                    state_lag_rows.extend([entry_rec, state_rec])

    pd.DataFrame(entry_rows).to_csv(run_dir / "metrics/entry_score_quality.csv", index=False)
    pd.DataFrame(state_lag_rows).to_csv(run_dir / "metrics/state_lag_quality.csv", index=False)

    # Build row-level official H1 account contributions and check against saved daily accounts.
    account_dates_by_split = {}
    pnl_rows = []
    account_replay_rows = []
    state_survival = pd.concat([next_side_survival(table, s) for s in SPLITS]).sort_index()
    for split, alias in (("train", "train"), ("historical_valid", "valid")):
        target = targets[split][1]
        score = score_full[split]
        saved_account_path = REF_RUN / f"metrics/daily_account_{alias}_H1.csv"
        row, official, check = account_replay(score, target, saved_account_path, split)
        saved_account = pd.read_csv(saved_account_path, parse_dates=[0], index_col=0)
        account_dates = pd.DatetimeIndex(saved_account.index)
        account_dates_by_split[split] = account_dates
        account_replay_rows.append(check)
        eval_mask = row.index.get_level_values("Date").isin(account_dates)
        row = row.loc[eval_mask].copy()
        attrs = table.loc[table.split.astype(str).eq(split)]
        row = row.join(attrs[["score", "score_abs", "score_percentile", "official_quintile", "weight",
                              "portfolio_side", "portfolio_side_code", "sleeve_age", "sleeve_age_bucket",
                              "portfolio_side_event_age_bucket", "side_reinforcing_events_last_60",
                              "side_opposite_events_last_60", "side_reinforcing_event_age_days", "sn1_source", "high_state", "low_state",
                              "Sector17Code", "Sector33Code", "ScaleCategory"]], how="left", rsuffix="_audit")
        if row.portfolio_side.isna().any():
            raise AssertionError(f"Missing locked phase1 attributes for {split} P/L rows")
        row["turnover_weight_delta"] = row.turnover
        row["abs_score_decile"] = np.floor(row.score_abs.groupby(level="Date").rank(method="average", pct=True) * 10).clip(0, 9).astype("int8")
        row["fixed_renewal_bucket_60d"] = np.select(
            [row.side_reinforcing_events_last_60.ge(2), row.side_reinforcing_events_last_60.eq(1),
             row.side_opposite_events_last_60.gt(0),
             row.side_reinforcing_event_age_days.gt(60)],
            ["recurrent_same_side_60d", "single_same_side_event_60d", "opposite_only_60d", "stale_same_side_60d_plus"],
            default="no_same_side_event_in_segment",
        )
        row["date"] = row.index.get_level_values("Date")
        row["split"] = split
        row = row.join(state_survival.loc[row.index], how="left")
        # Match the evaluator's account date set, excluding no dates based on performance.
        pnl_rows.append(row)
    pnl = pd.concat(pnl_rows).sort_index()
    pd.DataFrame(account_replay_rows).to_json(run_dir / "audit/daily_account_replay.json", orient="records", indent=2)
    if any(not x["pass"] for x in account_replay_rows):
        raise AssertionError("Official H1 daily account replay failed")

    dims = [
        (["portfolio_side", "sleeve_age_bucket"], "pnl_by_sleeve_age.csv"),
        (["portfolio_side", "portfolio_side_event_age_bucket"], "pnl_by_event_age.csv"),
        (["portfolio_side", "fixed_renewal_bucket_60d"], "pnl_by_event_renewal.csv"),
        (["portfolio_side", "abs_score_decile"], "pnl_by_absolute_score_decile.csv"),
        (["portfolio_side", "Sector17Code"], "pnl_by_sector17.csv"),
        (["portfolio_side", "ScaleCategory"], "pnl_by_scale_category.csv"),
    ]
    for columns, filename in dims:
        summarize_attribution(pnl, columns, account_dates_by_split, annual=False).to_csv(run_dir / "metrics" / filename, index=False)
        summarize_attribution(pnl, columns, account_dates_by_split, annual=True).to_csv(
            run_dir / "metrics" / filename.replace(".csv", "_annual.csv"), index=False
        )

    # Fixed age-band state survival curve, unweighted and distinct from P/L.
    age = pd.cut(table.sleeve_age, bins=[-1, 19, 59, 119, 299, np.inf], labels=AGE_BANDS)
    survival_table = table[["split", "portfolio_side", "sleeve_age", "score_abs", "score_percentile",
                            "score_to_daily_sd", "high_state_abs", "low_state_abs", "latest_event_age_trading_days",
                            "side_reinforcing_events_last_60", "high_events_last_60d", "low_events_last_60d"]].copy()
    survival_table["sleeve_age_band"] = age
    survival_table = survival_table.join(state_survival, how="left")
    survival_rows = []
    for (split, side, band), part in survival_table.loc[survival_table.portfolio_side.ne("neutral")].groupby(
        ["split", "portfolio_side", "sleeve_age_band"], observed=True, sort=True
    ):
        survival_rows.append({
            "split": str(split), "portfolio_side": str(side), "sleeve_age_band": str(band),
            "stock_days": int(len(part)), "mean_abs_final_score": float(part.score_abs.mean()),
            "median_abs_final_score": float(part.score_abs.median()),
            "median_score_percentile": float(part.score_percentile.median()),
            "mean_abs_score_over_daily_dispersion": float(part.score_to_daily_sd.mean()),
            "mean_abs_high_state": float(part.high_state_abs.mean()), "mean_abs_low_state": float(part.low_state_abs.mean()),
            "median_latest_event_age": float(part.latest_event_age_trading_days.median()),
            "recent_same_side_event_rate_60d": float(part.side_reinforcing_events_last_60.gt(0).mean()),
            "recurrent_same_side_event_rate_60d": float(part.side_reinforcing_events_last_60.ge(2).mean()),
            "survival_5d": float(part.survival_5d.mean()), "survival_20d": float(part.survival_20d.mean()),
            "survival_60d": float(part.survival_60d.mean()),
        })
    pd.DataFrame(survival_rows).to_csv(run_dir / "metrics/state_survival_by_sleeve_age.csv", index=False)

    inputs = sorted(set(accesses))
    code_paths = [Path(__file__).resolve(), ROOT / "research/evaluation.py"]
    manifest = {
        "phase": "Phase 2; descriptive fixed-state diagnostics only",
        "phase1_lock_sha256": expected_lock_hash,
        "phase1_table_sha256": phase1_manifest["score_table_sha256"],
        "candidate_pnl_run": False, "new_models_fit": False, "paper_data_accessed": False,
        "targets_used_for_model_fit_or_branching": False,
        "target_inputs": [str(p.relative_to(ROOT)) for p in target_paths],
        "account_inputs": [str((REF_RUN / f"metrics/daily_account_{x}_H1.csv").relative_to(ROOT)) for x in ("train", "valid")],
        "target_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in target_paths},
        "score_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in score_paths},
        "accessed_parquets": inputs,
        "code_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in code_paths},
        "daily_account_replay": account_replay_rows,
        "fixed_lags": list(LAGS), "diagnostic_horizons": list(HORIZONS),
        "one_way_cost": COST_RATE, "annualization": ANNUALIZATION,
        "HAC_lag": "fixed to outcome horizon H1=1, H5=5; no lag tuning",
        "metric_definitions": {
            "state_lag_sample": "rows where most recent same-side event age equals k market sessions, so no same-side renewal since the entry event",
            "entry_score_at_tk": "fixed entry percentile from that latest same-side event, evaluated against t+k H1/H5 target",
            "state_score_at_tk": "current separate High state or sign-oriented Low state, evaluated against t+k H1/H5 target",
            "spread": "daily within-sample five equal-count rank buckets, Q5 minus Q1 oriented residual; dates with fewer than 5 rows excluded",
            "absolute_score_decile": "within-date average-rank decile of abs(score); descriptive only",
            "attributed_sr": "Sharpe of daily weighted contribution with zero on dates absent from the attribution group; not standalone sleeve return",
            "survival": "same Long/Short membership after 5/20/60 subsequent market sessions, split-local, unweighted",
        },
    }
    write_json(run_dir / "audit/phase2_manifest.json", manifest)
    meta.update({"state": "phase2_complete", "finished_unix": time.time(),
                 "candidate_pnl_run": False, "target_values_read_after_phase1_lock": True,
                 "rankic_calculated": True,
                 "phase2_manifest_sha256": sha256(run_dir / "audit/phase2_manifest.json")})
    write_json(run_dir / "run.json", meta)
    print(json.dumps({"run_id": run_dir.name,
                      "entry_rows": len(entry_rows), "state_lag_rows": len(state_lag_rows),
                      "account_replay": account_replay_rows,
                      "output": str((run_dir / "metrics").relative_to(ROOT))}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
