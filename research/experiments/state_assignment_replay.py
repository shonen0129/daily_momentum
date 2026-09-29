"""P/L-free official quintile/weight replay from the locked state audit table."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from research import evaluation  # noqa: E402


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def compare(ref: pd.Series, alt: pd.Series) -> dict:
    wr, qr = evaluation.weights(ref)
    wa, qa = evaluation.weights(alt)
    q_changed = qr.ne(qa)
    w_changed = wr.ne(wa)
    return {
        "score_rows": int(len(ref)),
        "score_max_abs_change": float((ref - alt).abs().max()),
        "score_values_bitwise_changed": int(np.count_nonzero(ref.to_numpy() != alt.to_numpy())),
        "quintile_stock_days_changed": int(q_changed.sum()),
        "quintile_stock_day_rate_changed": float(q_changed.mean()),
        "weight_stock_days_changed": int(w_changed.sum()),
        "weight_stock_day_rate_changed": float(w_changed.mean()),
        "weight_max_abs_change": float((wr - wa).abs().max()),
        "reference_five_quintiles_every_date": bool(qr.groupby(level="Date").nunique().eq(5).all()),
        "alternative_five_quintiles_every_date": bool(qa.groupby(level="Date").nunique().eq(5).all()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    table = run_dir / "audit/date_code_state.parquet"
    phase1 = json.loads((run_dir / "audit/phase1_manifest.json").read_text(encoding="utf-8"))
    if sha256(table) != phase1["score_table_sha256"]:
        raise AssertionError("State audit table hash differs from phase 1 lock")
    frame = pd.read_parquet(table)
    saved = frame["score"].astype("float64")
    reconstructed = frame["high_state"].add(frame["low_state"])
    low = frame["low_state"].lt(0.0)
    high_only = frame["low_state"].eq(0.0) & frame["high_state"].gt(0.0)
    reconstructed = reconstructed.where(~low, frame["low_state"])
    reconstructed = reconstructed.where(~high_only, frame["high_state"])
    reconstructed.name = "reconstructed_from_HL_states"
    results = {}
    for split, group in frame.groupby("split", observed=True, sort=True):
        idx = group.index
        results[str(split)] = compare(saved.reindex(idx), reconstructed.reindex(idx))
    report = {
        "state_table_path": str(table.relative_to(ROOT)),
        "state_table_sha256": sha256(table),
        "state_table_matches_phase1_manifest": True,
        "source_code_sha256": sha256(Path(__file__).resolve()),
        "target_read": False, "pnl_calculated": False, "paper_data_accessed": False,
        "reconstruction": "D=high_state+low_state; choose low when low_state<0; choose high only when low_state==0 and high_state>0",
        "by_split": results,
    }
    # Fixed descriptive bins requested for auditing long holding spells; they
    # are not candidate cutoffs and have no P/L attached at this phase.
    labels = ["under_20", "20_59", "60_119", "120_299", "300_plus"]
    ages = pd.cut(frame["sleeve_age"], bins=[-1, 19, 59, 119, 299, np.inf], labels=labels)
    held = frame.loc[frame.portfolio_side.ne("neutral")].copy()
    held["sleeve_age_band"] = ages.loc[held.index]
    age_summary = held.groupby(["split", "portfolio_side", "sleeve_age_band"], observed=True, sort=True).agg(
        stock_days=("score", "size"), gross_weight_sum=("weight", lambda x: float(x.abs().sum())),
        mean_abs_score=("score_abs", "mean"), median_abs_score=("score_abs", "median"),
        p90_abs_score=("score_abs", lambda x: float(x.quantile(.9))),
        median_score_percentile=("score_percentile", "median"),
        mean_abs_score_over_daily_sd=("score_to_daily_sd", "mean"),
        near_zero_rate=("score_near_zero_1e12", "mean"),
        source_low_rate=("sn1_source", lambda x: float(x.eq("low_state").mean())),
        source_high_rate=("sn1_source", lambda x: float(x.eq("high_state").mean())),
        latest_event_age_median=("latest_event_age_trading_days", "median"),
        side_event_age_median=("side_reinforcing_event_age_days", "median"),
        same_side_renewal_60d_rate=("side_reinforcing_events_last_60", lambda x: float(x.gt(0).mean())),
        recurrent_same_side_60d_rate=("side_reinforcing_events_last_60", lambda x: float(x.ge(2).mean())),
    ).reset_index()
    age_summary.to_csv(run_dir / "metrics/phase1_sleeve_age_distribution.csv", index=False)
    report["age_distribution_path"] = str((run_dir / "metrics/phase1_sleeve_age_distribution.csv").relative_to(ROOT))
    report["age_distribution_sha256"] = sha256(run_dir / "metrics/phase1_sleeve_age_distribution.csv")

    ordered = frame.sort_index(level=[1, 0])
    code = ordered.index.get_level_values("Code")
    dates = pd.Series(pd.DatetimeIndex(ordered.index.get_level_values("Date")), index=ordered.index)
    calendar = pd.DatetimeIndex(frame.index.get_level_values("Date").unique().sort_values())
    ordinal_map = pd.Series(np.arange(len(calendar), dtype="int32"), index=calendar)
    ordinal = dates.map(ordinal_map)
    adjacent = ordinal.sub(ordinal.groupby(code, sort=False).shift(1)).eq(1)
    event_now = ordered.high_event | ordered.low_event
    event_prev = event_now.groupby(code, sort=False).shift(1).fillna(False)
    source_prev = ordered.sn1_source.groupby(code, sort=False).shift(1)
    percentile_prev = ordered.score_percentile.groupby(code, sort=False).shift(1)
    quintile_prev = ordered.official_quintile.groupby(code, sort=False).shift(1)
    no_event = adjacent & ~event_now & ~event_prev & ordered.sn1_source.eq(source_prev)
    recurrence_rows = []
    for source, state_col, alpha in (("low_state", "low_state", 0.50), ("high_state", "high_state", 0.25)):
        state = ordered[state_col]
        previous = state.groupby(code, sort=False).shift(1)
        expected = previous * (1.0 - alpha)
        valid = no_event & ordered.sn1_source.eq(source) & previous.ne(0.0)
        ratio = state.abs().div(previous.abs().replace(0.0, np.nan))
        close_to_expected = np.isclose(state.to_numpy(dtype="float64"), expected.to_numpy(dtype="float64"),
                                       rtol=2e-15, atol=0.0, equal_nan=False)
        recurrence_rows.append({
            "source": source, "alpha": alpha, "matched_no_event_stable_source_pairs": int(valid.sum()),
            "mean_abs_state_ratio_current_to_previous": float(ratio[valid].mean()),
            "median_abs_state_ratio_current_to_previous": float(ratio[valid].median()),
            "state_recurrence_within_2e_15_rate": float(close_to_expected[valid.to_numpy()].mean()),
            "median_abs_overall_rank_percentile_change": float((ordered.score_percentile[valid] - percentile_prev[valid]).abs().median()),
            "mean_abs_overall_rank_percentile_change": float((ordered.score_percentile[valid] - percentile_prev[valid]).abs().mean()),
            "official_quintile_retention": float((ordered.official_quintile[valid] == quintile_prev[valid]).mean()),
        })
    recurrence_path = run_dir / "metrics/phase1_no_event_state_recurrence.csv"
    pd.DataFrame(recurrence_rows).to_csv(recurrence_path, index=False)
    report["no_event_recurrence_path"] = str(recurrence_path.relative_to(ROOT))
    report["no_event_recurrence_sha256"] = sha256(recurrence_path)
    out = run_dir / "audit/phase1_official_assignment_replay.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
