"""Rebuild SN1 score regulation statistics and audit numeric stability, Train artifacts only."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from research import firewall
from research.experiments import box_asymmetry_gate as prior
from research.experiments.box_bidirectional_standalone import source_scan
from research.experiments.short_night_root_cause import candidate_score_streams, prefix_mutation_audit
from stock_comp_2026.evaluate_script import align_prediction
from stock_comp_2026.strategies.dm_variable_box_breakout import bidirectional, features, sn1, submission


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "artifacts/DM-20260927-03/run-20260926T191539Z"
SOURCE_RUN = ROOT / "artifacts/DM-20260925-03/run-20260926T063602Z"
SCORES = RUN / "predictions/strategy_scores.parquet"
SAVED_WEIGHTS = RUN / "predictions/portfolio_weights.parquet"
SAVED_QUINTILES = RUN / "predictions/official_quintiles.parquet"
SOURCE_SIGNALS = SOURCE_RUN / "predictions/signals.parquet"
EVENT_PREDICTIONS = SOURCE_RUN / "predictions/event_predictions.parquet"
TRAIN_TARGET = ROOT / "stock_comp_2026/input/target_1day_train.parquet"
TRAIN_INPUT = ROOT / "stock_comp_2026/input"
AUDIT = RUN / "audit"
ROUNDTRIP = AUDIT / "sn1_numeric_roundtrip.tmp"
SEED = 20260927


def sha256(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def finite_float(value):
    value = float(value)
    return value if np.isfinite(value) else None


def stats_from_saved_score(score: pd.Series) -> tuple[dict, pd.Series, pd.Series]:
    """Calculate all score distribution and portfolio statistics from one saved score column."""
    score = score.sort_index().astype("float64")
    if not score.index.is_unique or not np.isfinite(score.to_numpy()).all():
        raise AssertionError("Saved score must have a unique index and finite values")
    weight, quintile = prior.quintile_weights(score)
    dates = score.index.get_level_values("Date")
    tied_size = score.groupby(level="Date", sort=False).transform(
        lambda day: day.groupby(day, sort=False).transform("size")
    )
    group_keys = [dates, score]
    q_min = quintile.groupby(group_keys, sort=False).transform("min")
    q_max = quintile.groupby(group_keys, sort=False).transform("max")
    daily_count = score.groupby(level="Date").size()
    daily_unique = score.groupby(level="Date").nunique()
    daily_ratio = daily_unique / daily_count
    bucket_sizes = quintile.groupby([dates, quintile], sort=False).size()
    bucket_spread = bucket_sizes.groupby(level=0).agg(lambda sizes: sizes.max() - sizes.min())
    long = weight.clip(lower=0.0).groupby(level="Date").sum()
    short = -weight.clip(upper=0.0).groupby(level="Date").sum()
    net = weight.groupby(level="Date").sum()
    gross = weight.abs().groupby(level="Date").sum()
    values = {
        "zero_score_rate": float(score.eq(0.0).mean()),
        "duplicate_score_stock_day_rate": float(tied_size.gt(1).mean()),
        "tie_crossing_quintile_boundary_stock_day_rate": float(
            (tied_size.gt(1) & q_min.ne(q_max)).mean()
        ),
        "unique_score_count_pooled": int(score.nunique()),
        "mean_daily_unique_score_count": float(daily_unique.mean()),
        "mean_daily_unique_score_ratio": float(daily_ratio.mean()),
        "min_daily_unique_score_ratio": float(daily_ratio.min()),
        "q_group_count_min": int(quintile.groupby(level="Date").nunique().min()),
        "q_group_count_max": int(quintile.groupby(level="Date").nunique().max()),
        "bucket_count_spread_max": int(bucket_spread.max()),
        "average_long_exposure": float(long.mean()),
        "average_short_exposure": float(short.mean()),
        "average_net_exposure": float(net.mean()),
        "average_gross_exposure": float(gross.mean()),
    }
    return values, weight, quintile


def explicit_float64_ewma(values: pd.Series, alpha: float) -> pd.Series:
    """Independent scalar float64 recurrence over the same listing segments."""
    series = values.sort_index().astype("float64")
    group_positions = series.groupby(features.segment_keys(series.index), sort=False).indices
    source = series.to_numpy(dtype=np.float64)
    output = np.empty_like(source)
    alpha64 = np.float64(alpha)
    decay64 = np.float64(1.0) - alpha64
    for positions in group_positions.values():
        previous = np.float64(0.0)
        for offset, position in enumerate(positions):
            current = source[position]
            state = current if offset == 0 else alpha64 * current + decay64 * previous
            output[position] = state
            previous = state
    return pd.Series(output, index=series.index, name=series.name, dtype="float64")


def assignment_diff(reference: pd.Series, alternative: pd.Series) -> dict:
    reference = reference.sort_index()
    alternative = alternative.reindex(reference.index)
    if alternative.isna().any():
        raise AssertionError("Stability comparison lost score rows")
    _, q_reference = prior.quintile_weights(reference)
    _, q_alternative = prior.quintile_weights(alternative)
    w_reference, _ = prior.quintile_weights(reference)
    w_alternative, _ = prior.quintile_weights(alternative)
    q_changed = q_reference.ne(q_alternative)
    w_changed = w_reference.ne(w_alternative)
    return {
        "score_rows": int(len(reference)),
        "score_values_bitwise_changed": int(np.count_nonzero(
            reference.to_numpy() != alternative.to_numpy()
        )),
        "score_max_abs_change": float((reference - alternative).abs().max()),
        "quintile_stock_days_changed": int(q_changed.sum()),
        "quintile_stock_day_rate_changed": float(q_changed.mean()),
        "weight_stock_days_changed": int(w_changed.sum()),
        "weight_stock_day_rate_changed": float(w_changed.mean()),
        "weight_max_abs_change": float((w_reference - w_alternative).abs().max()),
        "short_membership_stock_days_changed": int(
            (q_reference.lt(2) != q_alternative.lt(2)).sum()
        ),
    }


def run() -> dict:
    AUDIT.mkdir(parents=True, exist_ok=True)
    allowed = (SCORES, SAVED_WEIGHTS, SAVED_QUINTILES, SOURCE_SIGNALS,
               EVENT_PREDICTIONS, TRAIN_TARGET, ROUNDTRIP)
    firewall.install(allowed_artifacts=allowed)

    saved_scores = pd.read_parquet(SCORES).sort_index()
    saved_weights = pd.read_parquet(SAVED_WEIGHTS).sort_index()
    saved_quintiles = pd.read_parquet(SAVED_QUINTILES).sort_index()
    if not saved_scores.index.equals(saved_weights.index) or not saved_scores.index.equals(saved_quintiles.index):
        raise AssertionError("Saved score/weight/quintile artifacts do not share an index")

    target = pd.read_parquet(TRAIN_TARGET, columns=["Return"])["Return"].sort_index()
    eval_dates = saved_scores.index.get_level_values("Date").unique().sort_values()
    eval_target = target.loc[target.index.get_level_values("Date").isin(eval_dates)]
    rows = []
    recalculated = {}
    for name in saved_scores.columns:
        score = saved_scores[name].rename("Return")
        metrics, weight, quintile = stats_from_saved_score(score)
        saved_weight = saved_weights[name].rename("weight")
        saved_quintile = saved_quintiles[name].astype("int8").rename("quintile")
        if not weight.index.equals(saved_weight.index) or not quintile.index.equals(saved_quintile.index):
            raise AssertionError(f"Official assignment index mismatch for {name}")
        weight_error = float((weight - saved_weight).abs().max())
        quintile_changes = int(quintile.ne(saved_quintile).sum())
        prediction = score.to_frame("Return")
        aligned = align_prediction(prediction, eval_target.to_frame("Return"))
        contract_pass = (
            score.index.is_unique
            and np.isfinite(score.to_numpy()).all()
            and aligned.index.equals(eval_target.index)
            and quintile.groupby(level="Date").nunique().eq(5).all()
        )
        metrics.update({
            "strategy": name,
            "unique_index": bool(score.index.is_unique),
            "finite_numeric_score": bool(np.isfinite(score.to_numpy()).all()),
            "train_target_index_coverage": bool(aligned.index.equals(eval_target.index)),
            "one_numeric_column_contract": bool(prediction.shape[1] == 1 and
                                                  pd.api.types.is_numeric_dtype(prediction.dtypes.iloc[0])),
            "official_align_prediction_contract": "PASS" if aligned.index.equals(eval_target.index) else "FAIL",
            "five_quintile_daily_coverage": bool(quintile.groupby(level="Date").nunique().eq(5).all()),
            "quintile_bucket_count_spread_max": metrics["bucket_count_spread_max"],
            "official_weights_finite": bool(np.isfinite(weight.to_numpy()).all()),
            "saved_weight_max_abs_error": weight_error,
            "saved_quintile_rows_changed": quintile_changes,
            "score_contract_pass": bool(contract_pass),
        })
        rows.append(metrics)
        recalculated[name] = (score, weight, quintile)
    if not all(row["score_contract_pass"] for row in rows):
        raise AssertionError("At least one saved score fails the official score contract")

    score_hash = sha256(SCORES)
    pd.DataFrame(rows).to_csv(AUDIT / "regulation_checks.csv", index=False)
    regulation_summary_path = AUDIT / "regulation_summary.json"
    regulation_summary = json.loads(regulation_summary_path.read_text(encoding="utf-8"))
    regulation_summary.update({
        "checks": "audit/regulation_checks.csv",
        "statistics_source": "saved predictions/strategy_scores.parquet only",
        "statistics_source_sha256": score_hash,
        "regenerated_from_saved_score": True,
        "train_target_values_used_for_statistics": False,
        "valid_accessed": False,
        "pnl_calculated": False,
    })
    dump(regulation_summary_path, regulation_summary)
    regulation_source = {
        "source_scores": str(SCORES.relative_to(ROOT)),
        "source_scores_sha256": score_hash,
        "derived_statistics": "saved evaluation score columns only",
        "train_target_use": "index coverage check only; target values were not used in any score statistic or P/L calculation",
        "score_rows": int(len(saved_scores)),
        "date_count": int(saved_scores.index.get_level_values("Date").nunique()),
        "date_start": str(saved_scores.index.get_level_values("Date").min().date()),
        "date_end": str(saved_scores.index.get_level_values("Date").max().date()),
        "valid_accessed": False,
        "pnl_calculated": False,
        "regulation_checks_sha256": sha256(AUDIT / "regulation_checks.csv"),
        "stats": "research.experiments.sn1_saved_score_audit.stats_from_saved_score",
    }
    dump(AUDIT / "regulation_checks_source.json", regulation_source)

    source_signals = pd.read_parquet(SOURCE_SIGNALS).sort_index()
    event_predictions = pd.read_parquet(EVENT_PREDICTIONS).sort_index()
    base = source_signals["BOX_BIDIR_STANDALONE"].rename("BOX")
    canonical = sn1.rebuild_from_base_score(base)

    # Refit only the already-fixed annual Train models to recover the complete
    # raw event stream. The saved event_predictions artifact intentionally has
    # evaluation-date coverage only, so it omits non-evaluation events that can
    # carry EWMA state into the next evaluation date.
    train_panels = features.load_inputs(TRAIN_INPUT, split="train")
    x_train = features.build_features(train_panels)
    if not x_train.index.equals(target.index):
        raise AssertionError("Train feature and target indexes differ during raw replay")
    predictions, model_records = bidirectional.walk_forward_predictions(x_train, target)
    direct_raw = bidirectional.generate_raw_signal(x_train, predictions).rename("direct_raw")
    direct_base = bidirectional.smooth_by_listing(direct_raw, alpha=sn1.HIGH_ALPHA)
    base_replay_error = float((direct_base - base.reindex(direct_base.index)).abs().max())
    if not np.isfinite(base_replay_error) or base_replay_error > 2e-12:
        raise AssertionError(f"Direct raw stream does not replay saved BOX base: {base_replay_error}")
    for side in bidirectional.SIDES:
        saved_prediction = event_predictions[f"{side}_prediction"]
        replay_prediction = predictions[side].reindex(event_predictions.index)
        if not np.array_equal(saved_prediction.to_numpy(), replay_prediction.to_numpy(), equal_nan=True):
            raise AssertionError(f"Fixed annual {side} predictions differ from saved Train event artifact")
        replay_event = bidirectional.event_mask(x_train.reindex(event_predictions.index), side)
        if not np.array_equal(
            event_predictions[f"{side}_event"].fillna(False).to_numpy(),
            replay_event.to_numpy(),
        ):
            raise AssertionError(f"Rebuilt {side} event mask differs from saved Train artifact")
    submission_base, submission_score = submission.score_from_predictions(x_train, predictions)
    research_score_streams, _ = candidate_score_streams(submission_base)
    research_score = research_score_streams["SIDE_SOURCE_SEPARATION"]
    if not np.array_equal(submission_score.to_numpy(), research_score.to_numpy()):
        raise AssertionError("Submission and research SN1 outputs are not bit-for-bit identical")
    saved_research_score = saved_scores["SIDE_SOURCE_SEPARATION"]
    replay_on_eval = submission_score.reindex(saved_research_score.index)
    if replay_on_eval.isna().any() or not np.array_equal(
        replay_on_eval.to_numpy(), saved_research_score.to_numpy()
    ):
        raise AssertionError("Submission Train replay differs from the saved research SN1 score")
    formal_result = submission.predict(data_dir=TRAIN_INPUT, split="train")
    formal_score = formal_result["Return"]
    formal_aligned = align_prediction(formal_result, target.to_frame("Return"))
    if (not formal_aligned.index.equals(target.index)
            or not np.array_equal(formal_score.to_numpy(), submission_score.to_numpy())):
        raise AssertionError("Formal Train submission entry point differs from shared prediction replay")
    source_scan_paths = source_scan()
    prefix_results = prefix_mutation_audit(
        base,
        candidate_score_streams(base)[0],
        AUDIT,
    )
    direct = sn1.score_from_raw(direct_raw)
    evaluation_index = saved_scores.index

    high_explicit = explicit_float64_ewma(direct["high_raw"], sn1.HIGH_ALPHA)
    low_explicit = explicit_float64_ewma(direct["low_raw"], sn1.LOW_ALPHA)
    explicit_d = (high_explicit + low_explicit).rename("D_LOW_FAST_ONLY")
    explicit_sn1 = explicit_d.copy().rename("SIDE_SOURCE_SEPARATION")
    low_active = low_explicit.lt(0.0)
    explicit_sn1.loc[low_active] = low_explicit.loc[low_active]
    high_only = low_explicit.eq(0.0) & high_explicit.gt(0.0)
    explicit_sn1.loc[high_only] = high_explicit.loc[high_only]

    canonical_sn1 = canonical["SIDE_SOURCE_SEPARATION"].reindex(evaluation_index)
    direct_sn1 = direct["SIDE_SOURCE_SEPARATION"].reindex(evaluation_index)
    explicit_sn1 = explicit_sn1.reindex(evaluation_index)
    shuffled_raw = direct_raw.sample(frac=1.0, random_state=SEED)
    shuffled_sn1 = sn1.score_from_raw(shuffled_raw)["SIDE_SOURCE_SEPARATION"].reindex(evaluation_index)

    roundtrip_frame = pd.DataFrame({
        "canonical": canonical_sn1,
        "direct_raw": direct_sn1,
        "explicit_float64": explicit_sn1,
    })
    roundtrip_frame.to_parquet(ROUNDTRIP)
    loaded = pd.read_parquet(ROUNDTRIP).sort_index()
    save_reload = {}
    for column in roundtrip_frame.columns:
        before = roundtrip_frame[column].sort_index()
        after = loaded[column]
        save_reload[column] = {
            "score_values_bitwise_equal": bool(np.array_equal(before.to_numpy(), after.to_numpy())),
            **assignment_diff(before, after),
        }

    numerical = {
        "run_id": "run-20260926T191539Z",
        "source_scores_sha256": score_hash,
        "source_signal_sha256": sha256(SOURCE_SIGNALS),
        "source_event_predictions_sha256": sha256(EVENT_PREDICTIONS),
        "train_input_hashes": {
            f"{name}_train.parquet": sha256(TRAIN_INPUT / f"{name}_train.parquet")
            for name in features.INPUT_COLUMNS
        },
        "train_target_sha256": sha256(TRAIN_TARGET),
        "fixed_annual_model_records": model_records,
        "direct_base_replay_max_abs_error": base_replay_error,
        "submission_vs_research_sn1_bitwise_equal": True,
        "submission_vs_saved_research_eval_sn1_bitwise_equal": True,
        "formal_train_entrypoint_bitwise_equal": True,
        "source_scan": "PASS",
        "source_scan_paths": source_scan_paths,
        "future_prefix_invariance": prefix_results,
        "saved_event_predictions_scope": "evaluation dates only; full raw stream was refit from Train data",
        "strategy_code_sha256": sha256(ROOT / "stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py"),
        "research_driver_code_sha256": sha256(ROOT / "research/experiments/short_night_root_cause.py"),
        "train_window": [str(base.index.get_level_values("Date").min().date()),
                         str(base.index.get_level_values("Date").max().date())],
        "evaluation_window": [str(evaluation_index.get_level_values("Date").min().date()),
                              str(evaluation_index.get_level_values("Date").max().date())],
        "float_dtype": "float64",
        "zero_noise_floor_fixed_from_existing_research_code": sn1.ZERO_NOISE_FLOOR,
        "valid_accessed": False,
        "target_values_used": True,
        "target_use": "Train-only annual model fit and Train coverage alignment; never used as P/L",
        "pnl_calculated": False,
        "inversion_max_abs_error": canonical["inversion_max_abs_error"],
        "direct_raw_vs_inverse_recovery": {
            "raw_rows_bitwise_changed": int(np.count_nonzero(
                direct_raw.to_numpy() != canonical["raw"].reindex(direct_raw.index).to_numpy()
            )),
            "raw_max_abs_change": float((direct_raw - canonical["raw"].reindex(direct_raw.index)).abs().max()),
            **assignment_diff(canonical_sn1, direct_sn1),
        },
        "pandas_vs_independent_float64_recurrence": assignment_diff(canonical_sn1, explicit_sn1),
        "row_order_shuffle_then_canonical_sort": {
            "score_values_bitwise_equal": bool(np.array_equal(direct_sn1.to_numpy(), shuffled_sn1.to_numpy())),
            **assignment_diff(direct_sn1, shuffled_sn1),
        },
        "save_reload_round_trip": save_reload,
        "roundtrip_temp_artifact": str(ROUNDTRIP.relative_to(ROOT)),
        "regulation_checks": "audit/regulation_checks.csv regenerated from saved strategy_scores.parquet",
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "python": sys.version,
        "platform": platform.platform(),
        "opened_parquets": sorted(firewall.ACCESSES),
    }
    dump(AUDIT / "sn1_numeric_stability.json", numerical)
    return {"regulation_rows": rows, "numeric_stability": numerical}


if __name__ == "__main__":
    summary = run()
    print(json.dumps({
        "regulation_rows": len(summary["regulation_rows"]),
        "numeric_stability_file": "artifacts/DM-20260927-03/run-20260926T191539Z/audit/sn1_numeric_stability.json",
        "valid_accessed": False,
        "pnl_calculated": False,
    }, ensure_ascii=False, indent=2))
