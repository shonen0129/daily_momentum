"""P/L-free structural reconstruction and audit of fixed SN1_H1 states."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from research import evaluation
from stock_comp_2026.strategies.dm_variable_box_breakout import bidirectional, features, sn1


REF_RUN = ROOT / "artifacts/DM-20260927-04/run-20260927T101500Z"
YEARS = tuple(range(2011, 2017))
FIRST_TRAIN_EVAL = pd.Timestamp("2011-01-04")
LAST_TRAIN_SIGNAL = pd.Timestamp("2016-03-31")
FIRST_VALID = pd.Timestamp("2016-04-01")
LAST_VALID = pd.Timestamp("2026-07-31")
PIT_COLUMNS_CANDIDATES = (
    "Sector17Code", "Sector33Code", "ScaleCategory", "MarketCapitalization",
    "MarketCap", "Size", "TOPIXSizeCategory",
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def safe(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return str(pd.Timestamp(value).date()) if pd.notna(value) else None
    return value


def install_phase1_read_guard():
    """Permit fixed H1 feature/scores/metadata only; deny all target/P&L reads."""
    original = pd.read_parquet
    accesses = []

    def guarded(path, *args, **kwargs):
        resolved = Path(path).resolve()
        name = resolved.name.lower()
        if "target" in name or "raw_target" in name or "paper" in str(resolved).lower():
            raise PermissionError(f"Phase 1 firewall denied target/paper parquet: {resolved}")
        permitted = (
            resolved.parent == (ROOT / "stock_comp_2026/input").resolve()
            and (name.startswith(("raw_return_1day_", "beta_1day_", "topix_return_1day_",
                                 "prices_daily_quotes_", "listed_info_")))
        ) or resolved in {
            (REF_RUN / "predictions/SN1_H1_train.parquet").resolve(),
            (REF_RUN / "predictions/SN1_H1_historical_valid.parquet").resolve(),
        }
        if not permitted:
            raise PermissionError(f"Phase 1 firewall denied unexpected parquet: {resolved}")
        accesses.append(str(resolved))
        return original(path, *args, **kwargs)

    pd.read_parquet = guarded
    return accesses


def load_model(path: Path) -> dict:
    model = json.loads(path.read_text(encoding="utf-8"))
    if model.get("horizon") != 1 or model.get("ridge_lambda") != 1.0:
        raise AssertionError(f"Not a fixed H1/lambda=1.0 model: {path}")
    return model


def fixed_event_predictions(x: pd.DataFrame, split: str) -> dict[str, pd.Series]:
    result = {side: [] for side in bidirectional.SIDES}
    dates = x.index.get_level_values("Date")
    if split == "train":
        for year in YEARS:
            year_rows = dates.year == year
            for side in bidirectional.SIDES:
                model = load_model(REF_RUN / f"models/H1/train/{side}_{year}.json")
                active = year_rows & bidirectional.event_mask(x, side).to_numpy()
                matrix = bidirectional.directional_features(x.loc[active], side)
                pred = pd.Series(
                    bidirectional.predict_matrix(matrix, model), index=matrix.index,
                    name=f"H1_{side}", dtype="float64",
                )
                result[side].append(pred)
    elif split == "historical_valid":
        for side in bidirectional.SIDES:
            model = load_model(REF_RUN / f"models/H1/valid/{side}_valid.json")
            active = bidirectional.event_mask(x, side)
            matrix = bidirectional.directional_features(x.loc[active], side)
            pred = pd.Series(
                bidirectional.predict_matrix(matrix, model), index=matrix.index,
                name=f"H1_{side}", dtype="float64",
            )
            result[side].append(pred)
    else:
        raise ValueError(f"Unknown split {split}")
    combined = {}
    for side, pieces in result.items():
        if not pieces:
            combined[side] = pd.Series(dtype="float64", index=pd.MultiIndex.from_arrays([[], []], names=["Date", "Code"]))
        else:
            combined[side] = pd.concat(pieces).sort_index()
            if not combined[side].index.is_unique:
                raise AssertionError(f"Duplicate {side} fixed H1 event predictions")
    return combined


def build_valid_features(train_panels, valid_panels):
    train_dates = pd.DatetimeIndex(train_panels["raw_return_1day"].index.get_level_values("Date").unique().sort_values())
    warm_dates = set(train_dates[-300:])
    warm = {}
    for name, train_panel in train_panels.items():
        if name == "topix_return_1day":
            keep = train_panel.index.isin(warm_dates)
        else:
            keep = train_panel.index.get_level_values("Date").isin(warm_dates)
        joined = pd.concat([train_panel.loc[keep], valid_panels[name]]).sort_index()
        if not joined.index.is_unique:
            raise ValueError(f"Duplicate Train warm-up/Valid rows: {name}")
        warm[name] = joined
    features_all = features.build_features(warm)
    valid_start = pd.DatetimeIndex(valid_panels["raw_return_1day"].index.get_level_values("Date").unique().sort_values()).min()
    return features_all.loc[features_all.index.get_level_values("Date") >= valid_start]


def load_pit(split: str) -> pd.DataFrame:
    path = ROOT / f"stock_comp_2026/input/listed_info_{'valid' if split == 'historical_valid' else 'train'}.parquet"
    import pyarrow.parquet as pq
    available = set(pq.ParquetFile(path).schema.names)
    use = [name for name in PIT_COLUMNS_CANDIDATES if name in available]
    if not use:
        return pd.DataFrame(index=pd.MultiIndex.from_arrays([[], []], names=["Date", "Code"]))
    panel = pd.read_parquet(path, columns=use)
    if not isinstance(panel.index, pd.MultiIndex) or list(panel.index.names) != ["Date", "Code"]:
        if not {"Date", "Code"}.issubset(panel.columns):
            raise ValueError(f"PIT listed info lacks a (Date, Code) key: {path}")
        panel = panel.set_index(["Date", "Code"])
    panel.index = pd.MultiIndex.from_arrays(
        [pd.DatetimeIndex(panel.index.get_level_values("Date")), panel.index.get_level_values("Code").astype(str)],
        names=["Date", "Code"],
    )
    return panel.sort_index()


def group_ffill(values: pd.Series, keys) -> pd.Series:
    return values.groupby(keys, sort=False).ffill()


def add_event_ages(frame: pd.DataFrame, keys, calendar: pd.DatetimeIndex) -> None:
    idx = frame.index
    date = pd.Series(pd.DatetimeIndex(idx.get_level_values("Date")), index=idx)
    ordinal_map = pd.Series(np.arange(len(calendar), dtype="int32"), index=calendar)
    ordinal = date.map(ordinal_map).astype("int32")
    row_in_segment = pd.Series(np.arange(len(frame), dtype="int64"), index=idx).groupby(keys, sort=False).cumcount()

    for prefix, event_col in (("high", "high_event"), ("low", "low_event")):
        event = frame[event_col].astype(bool)
        last_date = group_ffill(date.where(event), keys)
        last_ordinal = group_ffill(ordinal.where(event).astype("float64"), keys)
        last_row = group_ffill(row_in_segment.where(event).astype("float64"), keys)
        frame[f"last_{prefix}_event_date"] = last_date
        frame[f"{prefix}_event_age_trading_days"] = (ordinal - last_ordinal).astype("float64")
        frame[f"{prefix}_event_age_observations"] = (row_in_segment - last_row).astype("float64")
        for window in (20, 60, 120):
            count = frame[event_col].astype("float64").groupby(keys, sort=False).transform(
                lambda s, w=window: s.rolling(w, min_periods=1).sum()
            )
            frame[f"{prefix}_events_last_{window}d"] = count

    last_event_date = group_ffill(date.where(frame.high_event | frame.low_event), keys)
    last_event_side = group_ffill(
        pd.Series(np.where(frame.high_event, "high", np.where(frame.low_event, "low", None)), index=idx, dtype="object"),
        keys,
    )
    last_event_ordinal = group_ffill(ordinal.where(frame.high_event | frame.low_event).astype("float64"), keys)
    last_event_row = group_ffill(row_in_segment.where(frame.high_event | frame.low_event).astype("float64"), keys)
    frame["latest_event_side"] = last_event_side.fillna("none")
    frame["latest_event_date"] = last_event_date
    frame["latest_event_age_trading_days"] = (ordinal - last_event_ordinal).astype("float64")
    frame["latest_event_age_observations"] = (row_in_segment - last_event_row).astype("float64")


def add_membership_ages(frame: pd.DataFrame, calendar: pd.DatetimeIndex) -> None:
    """Compute consecutive holding/quintile ages; a missing stock date breaks a spell."""
    ordered = frame.sort_index(level=[1, 0])
    code = ordered.index.get_level_values("Code")
    date = pd.Series(pd.DatetimeIndex(ordered.index.get_level_values("Date")), index=ordered.index)
    ord_map = pd.Series(np.arange(len(calendar), dtype="int32"), index=calendar)
    ordinal = date.map(ord_map).astype("int32")
    q = ordered["official_quintile"].astype("int8")
    side = ordered["portfolio_side_code"].astype("int8")
    prev_ord = ordinal.groupby(code, sort=False).shift(1)
    prev_side = side.groupby(code, sort=False).shift(1)
    prev_q = q.groupby(code, sort=False).shift(1)
    adjacent = ordinal.sub(prev_ord).eq(1)
    starts = ~adjacent | side.ne(prev_side)
    switch = ~adjacent | side.ne(prev_side)
    side_episode = starts.groupby(code, sort=False).cumsum().astype("int64")
    exact_starts = ~adjacent | q.ne(prev_q)
    q_episode = exact_starts.groupby(code, sort=False).cumsum().astype("int64")
    temp = pd.DataFrame({"code_key": code, "side_episode": side_episode, "q_episode": q_episode}, index=ordered.index)
    sleeve_age = temp.groupby(["code_key", "side_episode"], sort=False).cumcount().add(1).astype("int32")
    sleeve_age = sleeve_age.where(side.ne(0), 0)
    quintile_age = temp.groupby(["code_key", "q_episode"], sort=False).cumcount().add(1).astype("int32")
    prev_side_nonnull = prev_side.fillna(0).astype("int8")
    entry = date.where(side.ne(0) & (~adjacent | side.ne(prev_side_nonnull)))
    last_entry = entry.groupby(code, sort=False).ffill().where(side.ne(0))
    last_switch = date.where(switch).groupby(code, sort=False).ffill()
    ordered["sleeve_age"] = sleeve_age
    ordered["exact_quintile_age"] = quintile_age
    ordered["last_sleeve_entry_date"] = last_entry
    ordered["last_side_switch_date"] = last_switch
    ordered["sleeve_age_bucket"] = pd.Categorical(
        np.where(side.eq(0), "not_held", np.where(sleeve_age < 20, "under_20", "20_plus")),
        categories=["not_held", "under_20", "20_plus"], ordered=True,
    )
    frame["sleeve_age"] = ordered["sleeve_age"].reindex(frame.index)
    frame["exact_quintile_age"] = ordered["exact_quintile_age"].reindex(frame.index)
    frame["last_sleeve_entry_date"] = ordered["last_sleeve_entry_date"].reindex(frame.index)
    frame["last_side_switch_date"] = ordered["last_side_switch_date"].reindex(frame.index)
    frame["sleeve_age_bucket"] = ordered["sleeve_age_bucket"].reindex(frame.index)


def summarize(frame: pd.DataFrame, run_dir: Path) -> dict:
    metrics_dir = run_dir / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    decay_rows = []
    for side, alpha in (("high", sn1.HIGH_ALPHA), ("low", sn1.LOW_ALPHA)):
        for days in (0, 1, 5, 20, 40, 60, 120):
            factor = float((1.0 - alpha) ** days)
            decay_rows.append({"source": side, "alpha": alpha, "days_without_same_side_event": days,
                               "remaining_fraction_of_event_state": factor,
                               "remaining_from_initial_raw_0_5": 0.5 * factor,
                               "remaining_from_initial_raw_1_0": factor})
    pd.DataFrame(decay_rows).to_csv(metrics_dir / "theoretical_ewma_decay.csv", index=False)

    rows = []
    for (split, side, age_bucket), g in frame.loc[frame.portfolio_side.ne("neutral")].groupby(
        ["split", "portfolio_side", "sleeve_age_bucket"], observed=True, sort=True
    ):
        rows.append({
            "split": split, "portfolio_side": side, "sleeve_age_bucket": str(age_bucket),
            "stock_days": int(len(g)), "gross_weight_sum": float(g.weight.abs().sum()),
            "mean_abs_score": float(g.score_abs.mean()), "median_abs_score": float(g.score_abs.median()),
            "p90_abs_score": float(g.score_abs.quantile(.90)),
            "median_score_percentile": float(g.score_percentile.median()),
            "mean_daily_dispersion_scaled_score": float(g.score_to_daily_sd.mean()),
            "exact_zero_rate": float(g.score_exact_zero.mean()), "near_zero_1e12_rate": float(g.score_near_zero_1e12.mean()),
            "low_state_negative_rate": float(g.low_state.lt(0).mean()),
            "high_state_positive_rate": float(g.high_state.gt(0).mean()),
            "low_priority_high_active_rate": float(g.low_priority_high_active.mean()),
            "low_priority_near_zero_rate": float(g.low_priority_near_zero.mean()),
            "source_low_rate": float(g.sn1_source.eq("low_state").mean()),
            "source_high_rate": float(g.sn1_source.eq("high_state").mean()),
            "latest_event_age_obs_median": safe(g.latest_event_age_observations.median()),
            "latest_event_age_days_median": safe(g.latest_event_age_trading_days.median()),
            "same_side_events_last_20_mean": float(g.side_reinforcing_events_last_20.mean()),
            "same_side_events_last_60_mean": float(g.side_reinforcing_events_last_60.mean()),
            "same_side_events_last_120_mean": float(g.side_reinforcing_events_last_120.mean()),
            "opposite_events_last_60_any_rate": float(g.side_opposite_events_last_60.gt(0).mean()),
            "same_side_renewal_60d_rate": float(g.side_reinforcing_events_last_60.gt(0).mean()),
            "recurrent_same_side_60d_rate": float(g.side_reinforcing_events_last_60.ge(2).mean()),
        })
    summary = pd.DataFrame(rows)
    summary.to_csv(metrics_dir / "phase1_sleeve_state_summary.csv", index=False)

    source_summary = frame.groupby(["split", "portfolio_side", "sn1_source"], observed=True, sort=True).agg(
        stock_days=("score", "size"), mean_abs_score=("score_abs", "mean"),
        median_abs_score=("score_abs", "median"), near_zero_rate=("score_near_zero_1e12", "mean"),
        mean_percentile=("score_percentile", "mean"), mean_score_sd_scaled=("score_to_daily_sd", "mean"),
        weight_abs_sum=("weight", lambda x: float(x.abs().sum())),
        high_active_rate=("high_state", lambda x: float(x.gt(0).mean())),
        low_active_rate=("low_state", lambda x: float(x.lt(0).mean())),
    ).reset_index()
    source_summary.to_csv(metrics_dir / "phase1_source_summary.csv", index=False)

    # Fixed observed-session renewal categories. These describe structure only.
    recent_bucket = np.select(
        [frame.side_reinforcing_events_last_60.ge(2), frame.side_reinforcing_events_last_60.eq(1),
         frame.side_opposite_events_last_60.gt(0), frame.side_reinforcing_event_age_days.gt(60)],
        ["recurrent_same_side_60d", "single_same_side_event_60d", "opposite_only_60d", "stale_same_side_60d_plus"],
        default="no_same_side_event_in_segment",
    )
    frame["fixed_renewal_bucket_60d"] = pd.Categorical(recent_bucket)
    renewal = frame.loc[frame.portfolio_side.ne("neutral")].groupby(
        ["split", "portfolio_side", "sleeve_age_bucket", "fixed_renewal_bucket_60d"],
        observed=True, sort=True,
    ).agg(stock_days=("score", "size"), mean_abs_score=("score_abs", "mean"),
          median_percentile=("score_percentile", "median"), gross_weight_sum=("weight", lambda x: float(x.abs().sum()))).reset_index()
    renewal.to_csv(metrics_dir / "phase1_event_renewal_composition.csv", index=False)

    # Exact no-event recurrence and rank/membership persistence, conditioned on stable source.
    ordered = frame.sort_index(level=[1, 0])
    code = ordered.index.get_level_values("Code")
    current_date = pd.Series(pd.DatetimeIndex(ordered.index.get_level_values("Date")), index=ordered.index)
    cal = pd.DatetimeIndex(frame.index.get_level_values("Date").unique().sort_values())
    ord_map = pd.Series(np.arange(len(cal), dtype="int32"), index=cal)
    ord_now = current_date.map(ord_map)
    ord_prev = ord_now.groupby(code, sort=False).shift(1)
    adjacent = ord_now.sub(ord_prev).eq(1)
    event_now = ordered.high_event | ordered.low_event
    event_prev = event_now.groupby(code, sort=False).shift(1).fillna(False)
    source_prev = ordered.sn1_source.groupby(code, sort=False).shift(1)
    score_prev = ordered.score.groupby(code, sort=False).shift(1)
    pct_prev = ordered.score_percentile.groupby(code, sort=False).shift(1)
    q_prev = ordered.official_quintile.groupby(code, sort=False).shift(1)
    mask = adjacent & ~event_now & ~event_prev & ordered.sn1_source.eq(source_prev)
    per_source = []
    for source in ("low_state", "high_state", "fallback"):
        selected = mask & ordered.sn1_source.eq(source)
        if not selected.any():
            continue
        abs_ratio = ordered.score.abs().div(score_prev.abs().replace(0.0, np.nan))
        per_source.append({
            "source": source, "matched_pairs_no_event_both_days_same_source": int(selected.sum()),
            "mean_abs_score_ratio_current_to_previous": float(abs_ratio[selected].mean()),
            "median_abs_percentile_change": float((ordered.score_percentile[selected] - pct_prev[selected]).abs().median()),
            "mean_abs_percentile_change": float((ordered.score_percentile[selected] - pct_prev[selected]).abs().mean()),
            "quintile_retention": float((ordered.official_quintile[selected] == q_prev[selected]).mean()),
            "exact_expected_geometric_decay_rate": float((abs_ratio[selected] == (1.0-sn1.LOW_ALPHA if source == "low_state" else 1.0-sn1.HIGH_ALPHA)).mean()),
        })
    pd.DataFrame(per_source).to_csv(metrics_dir / "phase1_no_event_rank_stability.csv", index=False)

    return {
        "rows": int(len(frame)),
        "dates": int(frame.index.get_level_values("Date").nunique()),
        "codes": int(frame.index.get_level_values("Code").nunique()),
        "date_start": str(frame.index.get_level_values("Date").min().date()),
        "date_end": str(frame.index.get_level_values("Date").max().date()),
        "train_rows": int(frame.split.eq("train").sum()),
        "historical_valid_rows": int(frame.split.eq("historical_valid").sum()),
        "near_zero_rate_all": float(frame.score_near_zero_1e12.mean()),
        "exact_zero_rate_all": float(frame.score_exact_zero.mean()),
        "low_state_nonzero_rate": float(frame.low_state.ne(0.0).mean()),
        "low_state_abs_below_1e12_rate": float(frame.low_state.abs().lt(1e-12).mean()),
        "negative_low_high_positive_rate": float(frame.low_priority_high_active.mean()),
        "negative_low_high_positive_but_selected_score_nearzero_rate": float(frame.low_priority_near_zero.mean()),
        "no_event_stable_source_pairs": int(mask.sum()),
        "no_event_stable_source_quintile_retention": float((ordered.official_quintile[mask] == q_prev[mask]).mean()) if mask.any() else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    for name in ("audit", "metrics", "predictions", "models"):
        (run_dir / name).mkdir(exist_ok=True)

    accesses = install_phase1_read_guard()
    run_meta = {
        "experiment_id": "DM-20260928-01", "run_id": run_dir.name, "phase": "phase1_structural_only",
        "state": "running", "git_head": None, "phase1_plan_sha256": sha256(ROOT / "experiments/DM-20260928-01/plan.md"),
        "config_sha256": sha256(ROOT / "experiments/DM-20260928-01/config.json"),
        "started_unix": time.time(), "python": sys.version, "platform": platform.platform(),
        "numpy": np.__version__, "pandas": pd.__version__, "target_read": False, "pnl_calculated": False,
        "valid_treated_as_historical_development": True, "paper_data_accessed": False,
    }
    try:
        import subprocess
        run_meta["git_head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        run_meta["git_head"] = "unavailable"
    write_json(run_dir / "run.json", run_meta)

    data_dir = ROOT / "stock_comp_2026/input"
    train_panels = features.load_inputs(data_dir, "train")
    valid_panels = features.load_inputs(data_dir, "valid")
    x_train = features.build_features(train_panels)
    x_valid = build_valid_features(train_panels, valid_panels)
    if x_valid.index.get_level_values("Date").min() != FIRST_VALID:
        raise AssertionError("Historical Valid feature start differs from fixed H1 artifact")
    train_predictions = fixed_event_predictions(x_train, "train")
    valid_predictions = fixed_event_predictions(x_valid, "historical_valid")
    raw_train = bidirectional.generate_raw_signal(x_train, train_predictions)
    raw_valid = bidirectional.generate_raw_signal(x_valid, valid_predictions)
    raw = pd.concat([raw_train, raw_valid]).sort_index()
    if not raw.index.is_unique:
        raise AssertionError("Train and historical Valid H1 signal indexes overlap")
    reconstructed = sn1.score_from_raw(raw)

    saved_paths = {
        "train": REF_RUN / "predictions/SN1_H1_train.parquet",
        "historical_valid": REF_RUN / "predictions/SN1_H1_historical_valid.parquet",
    }
    saved = {}
    reconstructed_by_split = {}
    replay = []
    for split, x in (("train", x_train), ("historical_valid", x_valid)):
        signal = pd.read_parquet(saved_paths[split])["Return"].sort_index().astype("float64")
        score = reconstructed["SIDE_SOURCE_SEPARATION"].reindex(signal.index)
        if score.isna().any():
            raise AssertionError(f"H1 reconstruction lost {split} saved-score rows")
        delta = (score - signal).abs()
        replay.append({
            "split": split, "rows": int(len(signal)), "max_abs_score_error": float(delta.max()),
            "bitwise_equal": bool(np.array_equal(score.to_numpy(), signal.to_numpy())),
            "equal_within_2e_12": bool(delta.max() <= 2e-12),
        })
        reconstructed_by_split[split] = score
        saved[split] = signal
    if not all(x["equal_within_2e_12"] for x in replay):
        raise AssertionError(f"Fixed H1 reconstruction failed saved-score parity: {replay}")

    # Preserve the independently reconstructed full signal and its official
    # assignment so a later parity check does not restart EWMA from a cropped
    # evaluation window and lose the zero-signal warm-up prefix.
    reconstructed_output_hashes = {}
    for split, reconstructed_score in reconstructed_by_split.items():
        reconstructed_weight, reconstructed_quintile = evaluation.weights(reconstructed_score)
        reconstructed_frame = pd.DataFrame({
            "score": reconstructed_score,
            "quintile": reconstructed_quintile.astype("int8"),
            "weight": reconstructed_weight,
        }, index=reconstructed_score.index)
        output_path = run_dir / "predictions" / f"SN1_H1_RECONSTRUCTED_{split}.parquet"
        reconstructed_frame.to_parquet(output_path, compression="zstd")
        reconstructed_output_hashes[str(output_path.relative_to(ROOT))] = sha256(output_path)

    score = pd.concat(saved.values()).sort_index()
    if not score.index.is_unique:
        raise AssertionError("Saved fixed H1 Train/old-Valid scores overlap")
    high_raw = reconstructed["high_raw"].reindex(score.index)
    low_raw = reconstructed["low_raw"].reindex(score.index)
    high_state = reconstructed["high_state"].reindex(score.index)
    low_state = reconstructed["low_state"].reindex(score.index)
    weights, quintile = evaluation.weights(score)
    date_values = score.index.get_level_values("Date")
    include = date_values >= FIRST_TRAIN_EVAL
    score = score.loc[include]
    high_raw, low_raw = high_raw.loc[include], low_raw.loc[include]
    high_state, low_state = high_state.loc[include], low_state.loc[include]
    weights, quintile = weights.loc[include], quintile.loc[include]
    idx = score.index
    frame = pd.DataFrame(index=idx)
    dates = pd.DatetimeIndex(idx.get_level_values("Date"))
    frame["split"] = pd.Categorical(np.where(dates < FIRST_VALID, "train", "historical_valid"),
                                    categories=["train", "historical_valid"])
    frame["score"] = score
    frame["score_abs"] = score.abs()
    frame["score_exact_zero"] = score.eq(0.0)
    frame["score_near_zero_1e12"] = score.abs().lt(1e-12)
    frame["high_raw_event_score"] = high_raw
    frame["low_raw_event_score"] = low_raw
    frame["high_event"] = high_raw.ne(0.0)
    frame["low_event"] = low_raw.ne(0.0)
    frame["high_state"] = high_state
    frame["low_state"] = low_state
    frame["high_state_abs"] = high_state.abs()
    frame["low_state_abs"] = low_state.abs()
    frame["official_quintile"] = quintile.astype("int8") + 1
    frame["weight"] = weights
    frame["portfolio_side_code"] = np.where(quintile.le(1), -1, np.where(quintile.ge(3), 1, 0)).astype("int8")
    frame["portfolio_side"] = pd.Categorical(
        np.where(frame.portfolio_side_code.gt(0), "long", np.where(frame.portfolio_side_code.lt(0), "short", "neutral")),
        categories=["short", "neutral", "long"], ordered=True,
    )
    frame["sn1_source"] = pd.Categorical(
        np.where(low_state.lt(0.0), "low_state", np.where((low_state.eq(0.0)) & high_state.gt(0.0), "high_state", "fallback")),
        categories=["low_state", "high_state", "fallback"],
    )
    frame["low_priority_high_active"] = low_state.lt(0.0) & high_state.gt(0.0)
    frame["low_priority_near_zero"] = frame.low_priority_high_active & score.abs().lt(1e-12)
    frame["score_percentile"] = score.groupby(level="Date", sort=False).rank(method="average", pct=True)
    frame["daily_score_dispersion"] = score.groupby(level="Date", sort=False).transform("std")
    frame["score_to_daily_sd"] = score.abs().div(frame.daily_score_dispersion.replace(0.0, np.nan))
    frame["absolute_state_sum"] = high_state.abs().add(low_state.abs())
    frame["low_share_of_absolute_state"] = low_state.abs().div(frame.absolute_state_sum.replace(0.0, np.nan))
    frame["high_share_of_absolute_state"] = high_state.abs().div(frame.absolute_state_sum.replace(0.0, np.nan))

    full_calendar = pd.DatetimeIndex(raw.index.get_level_values("Date").unique().sort_values())
    keys = features.segment_keys(idx)
    add_event_ages(frame, keys, full_calendar)
    # Side-matched event renewal versus opposite-side renewal.
    frame["side_reinforcing_events_last_20"] = np.where(frame.portfolio_side_code.gt(0), frame.high_events_last_20d,
                                                           np.where(frame.portfolio_side_code.lt(0), frame.low_events_last_20d, 0.0))
    frame["side_reinforcing_events_last_60"] = np.where(frame.portfolio_side_code.gt(0), frame.high_events_last_60d,
                                                           np.where(frame.portfolio_side_code.lt(0), frame.low_events_last_60d, 0.0))
    frame["side_reinforcing_events_last_120"] = np.where(frame.portfolio_side_code.gt(0), frame.high_events_last_120d,
                                                            np.where(frame.portfolio_side_code.lt(0), frame.low_events_last_120d, 0.0))
    frame["side_opposite_events_last_60"] = np.where(frame.portfolio_side_code.gt(0), frame.low_events_last_60d,
                                                        np.where(frame.portfolio_side_code.lt(0), frame.high_events_last_60d, 0.0))
    frame["side_reinforcing_event_age_days"] = np.where(frame.portfolio_side_code.gt(0), frame.high_event_age_trading_days,
                                                         np.where(frame.portfolio_side_code.lt(0), frame.low_event_age_trading_days, np.nan))
    frame["side_reinforcing_event_age_observations"] = np.where(frame.portfolio_side_code.gt(0), frame.high_event_age_observations,
                                                                 np.where(frame.portfolio_side_code.lt(0), frame.low_event_age_observations, np.nan))
    frame["portfolio_side_event_age_bucket"] = pd.Categorical(
        np.select([frame.side_reinforcing_event_age_observations.eq(0),
                   frame.side_reinforcing_event_age_observations.between(1, 4),
                   frame.side_reinforcing_event_age_observations.ge(5)],
                  ["event_day", "age_1_4", "age_5_plus"], default="no_prior_event_in_segment"),
        categories=["event_day", "age_1_4", "age_5_plus", "no_prior_event_in_segment"], ordered=True,
    )
    add_membership_ages(frame, full_calendar)

    # Code-to-size/sector fields are diagnostic PIT metadata only, never score inputs.
    pit_train, pit_valid = load_pit("train"), load_pit("historical_valid")
    pit = pd.concat([pit_train, pit_valid]).sort_index()
    if not pit.index.is_unique:
        # Boundary dates are disjoint; any remaining overlap is a data-contract issue.
        raise ValueError("PIT Train and historical Valid listed-info indexes overlap")
    pit_fields = [c for c in pit.columns if c in PIT_COLUMNS_CANDIDATES]
    frame = frame.join(pit[pit_fields], how="left")
    frame = frame.sort_index()
    frame.index = pd.MultiIndex.from_arrays(
        [pd.DatetimeIndex(frame.index.get_level_values("Date")), frame.index.get_level_values("Code").astype(str)],
        names=["Date", "Code"],
    )
    if not frame.index.is_unique:
        raise AssertionError("Audit Date×Code table is not unique")
    numeric = frame.select_dtypes(include=[np.number]).to_numpy(dtype="float64", copy=False)
    finite_columns = frame.select_dtypes(include=[np.number]).columns.tolist()
    # Age columns intentionally contain NaN before the first event; score/state/weights must be finite.
    required_finite = ["score", "weight", "high_raw_event_score", "low_raw_event_score", "high_state", "low_state"]
    if not np.isfinite(frame[required_finite].to_numpy(dtype="float64")).all():
        raise AssertionError("Fixed H1 score/state/weight has nonfinite values")

    structural_summary = summarize(frame, run_dir)
    table_path = run_dir / "audit/date_code_state.parquet"
    frame.to_parquet(table_path, compression="zstd")
    structure_manifest = {
        "phase": "P/L-free structural audit",
        "purpose": "separate H1 event entry stream, carried High/Low state, and official quintile/sleeve persistence",
        "target_read": False, "pnl_calculated": False, "rankic_calculated": False,
        "paper_data_accessed": False, "historical_valid_used_as_development": True,
        "reference_experiment": "DM-20260927-04", "reference_run": "run-20260927T101500Z",
        "alpha": {"high": sn1.HIGH_ALPHA, "low": sn1.LOW_ALPHA},
        "segment_reset": "existing features.segment_keys; reset when gap exceeds 20 market-date positions",
        "event_counts": "rolling event counts over per-code observations within the same listing segment",
        "near_zero_descriptive_flag": "abs(score)<1e-12 (uses the existing SN1 reconstruction cleanup scale; not an action threshold)",
        "official_quintile_and_weight": "research.evaluation.weights on the saved fixed SN1_H1 score",
        "fixed_model_replay": replay,
        "reconstructed_score_assignment_outputs": reconstructed_output_hashes,
        "rows": structural_summary["rows"], "score_table_path": str(table_path.relative_to(ROOT)),
        "score_table_sha256": sha256(table_path),
        "accessed_parquets": sorted(set(accesses)),
        "input_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in sorted({Path(x) for x in accesses})},
        "model_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in sorted((REF_RUN / "models/H1").rglob("*.json"))},
        "code_sha256": {
            "research/experiments/state_persistence_audit.py": sha256(Path(__file__).resolve()),
            "stock_comp_2026/strategies/dm_variable_box_breakout/features.py": sha256(ROOT / "stock_comp_2026/strategies/dm_variable_box_breakout/features.py"),
            "stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py": sha256(ROOT / "stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py"),
            "stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py": sha256(ROOT / "stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py"),
        },
        "finite_numeric_columns": finite_columns,
        "summary": structural_summary,
    }
    write_json(run_dir / "audit/phase1_manifest.json", structure_manifest)
    write_json(run_dir / "audit/phase1_structural_summary.json", structural_summary)
    run_meta.update({"state": "phase1_complete", "finished_unix": time.time(),
                     "target_read": False, "pnl_calculated": False,
                     "score_table_sha256": structure_manifest["score_table_sha256"],
                     "phase1_manifest_sha256": sha256(run_dir / "audit/phase1_manifest.json")})
    write_json(run_dir / "run.json", run_meta)
    print(json.dumps({"run_id": run_dir.name, "summary": structural_summary, "replay": replay,
                      "table_sha256": structure_manifest["score_table_sha256"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
