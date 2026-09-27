"""Train-only structural audit and frozen-intervention evaluation for Short x Night."""
from __future__ import annotations

import argparse
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
from research.experiments import box_asym_ewma as asym
from research.experiments import box_asymmetry_gate as prior
from research.experiments import box_bidirectional_day_night as day_night
from stock_comp_2026.evaluate_script import align_prediction
from stock_comp_2026.strategies.dm_variable_box_breakout import features, sn1


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DM-20260927-03"
SOURCE = ROOT / "artifacts/DM-20260925-03/run-20260926T063602Z/predictions/signals.parquet"
BASE_RUN = ROOT / "artifacts/DM-20260927-02/run-20260926T174234Z"
SCORES = BASE_RUN / "predictions/strategy_scores.parquet"
WEIGHTS = BASE_RUN / "predictions/portfolio_weights.parquet"
EVENT_MASKS = ROOT / "artifacts/DM-20260926-01/run-20260926T143032Z-08/predictions/event_masks.parquet"
DATA_DIR = ROOT / "stock_comp_2026/input"
EVAL_START = "2011-01-04"
EVAL_END = "2016-03-29"
ALPHA_HIGH = 0.25
ALPHA_LOW = 0.50
ONE_WAY_COST = 0.001
BOOTSTRAP_SEED = 20260925
BOOTSTRAP_REPS = 1000
BOOTSTRAP_BLOCK = 20


def sha256(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def structural_audit(output: Path) -> dict:
    """Create a P/L-blind, stock-day audit of the stored D portfolio."""
    output.mkdir(parents=True, exist_ok=True)
    allowed = (SOURCE, SCORES, WEIGHTS, EVENT_MASKS)
    firewall.install(allowed_artifacts=allowed)

    saved = pd.read_parquet(SOURCE).sort_index()
    score_frame = pd.read_parquet(SCORES).sort_index()
    weight_frame = pd.read_parquet(WEIGHTS).sort_index()
    eligibility = pd.read_parquet(EVENT_MASKS, columns=["eligible_box"]).sort_index()
    listed = pd.read_parquet(DATA_DIR / "listed_info_train.parquet", columns=[
        "Sector33Code", "Sector33CodeName", "ScaleCategory"
    ]).sort_index()
    liquidity = pd.read_parquet(DATA_DIR / "prices_daily_quotes_train.parquet", columns=[
        "TurnoverValue", "Volume"
    ]).sort_index()

    score = score_frame["D_LOW_FAST_ONLY"].rename("score")
    weights_saved = weight_frame["D_LOW_FAST_ONLY"].rename("weight")
    if not score.index.equals(weights_saved.index) or not score.index.equals(eligibility.index):
        raise AssertionError("Stored score, weight, and eligibility indexes must match")
    if score.index.get_level_values("Date").min() != pd.Timestamp(EVAL_START):
        raise AssertionError("Unexpected first evaluation date")
    if score.index.get_level_values("Date").max() != pd.Timestamp(EVAL_END):
        raise AssertionError("Unexpected last evaluation date")

    # Replay D only from the saved causal score stream; do not read any target or P/L file.
    raw, inverse_error = prior.inverse_ewma(saved["BOX_BIDIR_STANDALONE"].rename("BOX"), ALPHA_HIGH)
    high_raw, low_raw = prior.split_raw_sides(raw)
    high_state = prior.segment_ewma(high_raw, ALPHA_HIGH).rename("high_state")
    low_state = prior.segment_ewma(low_raw, ALPHA_LOW).rename("low_state")
    rebuilt = (high_state + low_state).rename("score")
    if float((rebuilt.reindex(score.index) - score).abs().max()) > 2e-12:
        raise AssertionError("Reconstructed D state does not reproduce the saved D score")
    components = asym.score_components(high_raw, low_raw, ALPHA_HIGH, ALPHA_LOW).reindex(score.index)
    if float((components.sum(axis=1) - score).abs().max()) > 2e-12:
        raise AssertionError("D event-age components do not add to the saved score")

    computed_weight, quintile = prior.quintile_weights(score)
    weight_error = float((computed_weight - weights_saved).abs().max())
    if weight_error > 1e-12:
        raise AssertionError(f"Saved official weights do not replay: max error={weight_error}")
    score = score.sort_index()
    rank = score.groupby(level="Date", sort=False).rank(method="first").astype("int32")
    n_day = score.groupby(level="Date", sort=False).transform("count").astype("int32")
    rank_pct = rank / n_day
    q = quintile.reindex(score.index).astype("int8")

    abs_components = components.abs()
    dominant = abs_components.idxmax(axis=1).astype("string")
    dominant = dominant.where(score.ne(0.0), "score_zero")
    denominator = abs_components.sum(axis=1).replace(0.0, np.nan)
    component_fraction = abs_components.div(denominator, axis=0).fillna(0.0)

    # Duplicated scores are ties; a tie crosses a portfolio cut when its rows span Q bins.
    score_key = score.groupby(level="Date", sort=False).transform(lambda x: x.astype("float64"))
    tie_size = score_key.groupby([score.index.get_level_values("Date"), score_key], sort=False).transform("size")
    q_min = q.groupby([score.index.get_level_values("Date"), score_key], sort=False).transform("min")
    q_max = q.groupby([score.index.get_level_values("Date"), score_key], sort=False).transform("max")
    tie_break = tie_size.gt(1) & q_min.ne(q_max)

    columns = pd.DataFrame({
        "Date": score.index.get_level_values("Date"),
        "Code": score.index.get_level_values("Code").astype(str),
        "final_score": score.to_numpy(),
        "cross_sectional_rank": rank.to_numpy(),
        "cross_sectional_rank_pct": rank_pct.to_numpy(),
        "official_quintile": q.to_numpy(),
        "portfolio_weight": weights_saved.reindex(score.index).to_numpy(),
        "high_state": high_state.reindex(score.index).to_numpy(),
        "low_state": low_state.reindex(score.index).to_numpy(),
        "high_raw_score": high_raw.reindex(score.index).to_numpy(),
        "low_raw_score": low_raw.reindex(score.index).to_numpy(),
        "dominant_source": dominant.to_numpy(),
        "source_age": dominant.str.extract(r"age_(1_4|5_plus)$", expand=False).fillna("event_day").to_numpy(),
        "score_sign": np.sign(score.to_numpy()).astype("int8"),
        "score_abs": score.abs().to_numpy(),
        "zero_score_flag": score.eq(0.0).to_numpy(),
        "tie_break_flag": tie_break.to_numpy(),
        "box_eligible": eligibility["eligible_box"].reindex(score.index).fillna(False).to_numpy(),
        "Sector33Code": listed["Sector33Code"].reindex(score.index).to_numpy(),
        "Sector33CodeName": listed["Sector33CodeName"].reindex(score.index).to_numpy(),
        "ScaleCategory": listed["ScaleCategory"].reindex(score.index).to_numpy(),
        "TurnoverValue_t": liquidity["TurnoverValue"].reindex(score.index).to_numpy(),
        "Volume_t": liquidity["Volume"].reindex(score.index).to_numpy(),
        "high_age_5_plus_component": components["high_age_5_plus"].to_numpy(),
        "low_age_5_plus_component": components["low_age_5_plus"].to_numpy(),
        "high_age_5_plus_abs_share": component_fraction["high_age_5_plus"].to_numpy(),
        "low_age_5_plus_abs_share": component_fraction["low_age_5_plus"].to_numpy(),
    }, index=score.index)
    columns["high_state_sign"] = np.sign(columns["high_state"]).astype("int8")
    columns["low_state_sign"] = np.sign(columns["low_state"]).astype("int8")
    columns["weak_positive"] = False
    # Fixed descriptive definition: positive Short scores below the same day's median positive score.
    positive = columns["final_score"].gt(0.0)
    daily_positive_median = columns["final_score"].where(positive).groupby(level="Date").transform("median")
    columns["weak_positive"] = positive & columns["final_score"].le(daily_positive_median)
    columns["low_age_5_plus_component"] = components["low_age_5_plus"].to_numpy()
    short = columns.loc[columns["official_quintile"].isin([0, 1])].copy()
    if not short["portfolio_weight"].lt(0.0).all():
        raise AssertionError("Official Q1/Q2 rows are expected to carry short weights")
    short["short_quintile"] = np.where(short["official_quintile"].eq(0), "Q1", "Q2")
    short.to_parquet(output / "short_holdings_structure.parquet")
    short.to_csv(output / "short_holdings_structure.csv.gz", index=False, compression="gzip")

    q_rows = []
    source_rows = []
    mechanics_rows = []
    for label, part in short.groupby("short_quintile", sort=True):
        gross_weight = part["portfolio_weight"].abs()
        q_rows.append({
            "quintile": label,
            "stock_days": int(len(part)),
            "daily_mean_stock_count": float(part.groupby(level="Date").size().mean()),
            "gross_weight_sum": float(gross_weight.sum()),
            "gross_weight_share_short": float(gross_weight.sum() / short["portfolio_weight"].abs().sum()),
            "zero_score_stock_day_rate": float(part["zero_score_flag"].mean()),
            "zero_score_gross_weight_rate": float(gross_weight.where(part["zero_score_flag"], 0.0).sum() / gross_weight.sum()),
            "positive_score_rate": float(part["final_score"].gt(0.0).mean()),
            "weak_positive_rate": float(part["weak_positive"].mean()),
            "box_eligible_rate": float(part["box_eligible"].mean()),
            "tie_break_stock_day_rate": float(part["tie_break_flag"].mean()),
            "high_state_positive_rate": float(part["high_state"].gt(0.0).mean()),
            "low_state_negative_rate": float(part["low_state"].lt(0.0).mean()),
            "median_abs_score": float(part["score_abs"].median()),
            "p90_abs_score": float(part["score_abs"].quantile(0.90)),
            "median_turnover_value_t": float(part["TurnoverValue_t"].median()),
            "median_volume_t": float(part["Volume_t"].median()),
        })
        for source, group in part.groupby("dominant_source", dropna=False, sort=True):
            source_rows.append({
                "quintile": label, "dominant_source": str(source),
                "stock_days": int(len(group)), "stock_day_share": float(len(group) / len(part)),
                "gross_weight": float(group["portfolio_weight"].abs().sum()),
                "gross_weight_share": float(group["portfolio_weight"].abs().sum() / gross_weight.sum()),
                "zero_score_rate": float(group["zero_score_flag"].mean()),
                "positive_score_rate": float(group["final_score"].gt(0.0).mean()),
                "high_state_positive_rate": float(group["high_state"].gt(0.0).mean()),
                "low_state_negative_rate": float(group["low_state"].lt(0.0).mean()),
                "box_eligible_rate": float(group["box_eligible"].mean()),
                "median_abs_score": float(group["score_abs"].median()),
            })

    for source, mask_col in (("high_age_5_plus", "high_age_5_plus_abs_share"),
                             ("low_age_5_plus", "low_age_5_plus_abs_share")):
        active = short[mask_col].gt(0.0)
        for label, qpart in short.groupby("short_quintile", sort=True):
            group = qpart.loc[active.reindex(qpart.index).fillna(False)]
            if group.empty:
                mechanics_rows.append({"source": source, "quintile": label, "stock_days": 0})
                continue
            comp_name = f"{source}_component"
            comp = group[comp_name]
            low = group["low_state"]
            high = group["high_state"]
            mechanics_rows.append({
                "source": source, "quintile": label, "stock_days": int(len(group)),
                "stock_day_share_of_short_quintile": float(len(group) / len(qpart)),
                "gross_weight_share_of_short_quintile": float(group["portfolio_weight"].abs().sum() / qpart["portfolio_weight"].abs().sum()),
                "dominant_source_rate": float(group["dominant_source"].eq(source).mean()),
                "component_positive_rate": float(comp.gt(0.0).mean()),
                "component_negative_rate": float(comp.lt(0.0).mean()),
                "high_state_positive_rate": float(high.gt(0.0).mean()),
                "low_state_negative_rate": float(low.lt(0.0).mean()),
                "final_score_negative_rate": float(group["final_score"].lt(0.0).mean()),
                "final_score_zero_rate": float(group["final_score"].eq(0.0).mean()),
                "final_score_positive_rate": float(group["final_score"].gt(0.0).mean()),
                "median_abs_score": float(group["score_abs"].median()),
                "p10_abs_score": float(group["score_abs"].quantile(0.10)),
                "p90_abs_score": float(group["score_abs"].quantile(0.90)),
                "median_high_state": float(high.median()),
                "median_low_state": float(low.median()),
                "median_abs_high_low_ratio": float((high.abs() / low.abs().replace(0.0, np.nan)).median()),
                "box_eligible_rate": float(group["box_eligible"].mean()),
            })

    pd.DataFrame(q_rows).to_csv(output / "q1_q2_structure.csv", index=False)
    pd.DataFrame(source_rows).to_csv(output / "q1_q2_source_age.csv", index=False)
    pd.DataFrame(mechanics_rows).to_csv(output / "aged_source_short_mechanics.csv", index=False)

    sign_by_day = pd.DataFrame({
        "negative": score.lt(0.0).groupby(level="Date").mean(),
        "zero": score.eq(0.0).groupby(level="Date").mean(),
        "positive": score.gt(0.0).groupby(level="Date").mean(),
    })
    sign_by_day.to_csv(output / "cross_section_score_sign.csv", index_label="Date")
    zero_short = short.loc[short["zero_score_flag"]]
    sector_zero = (zero_short.groupby(["short_quintile", "Sector33CodeName"], dropna=False)
                   .agg(stock_days=("final_score", "size"), gross_weight=("portfolio_weight", lambda x: x.abs().sum()))
                   .reset_index())
    sector_zero["stock_day_share_within_zero"] = sector_zero["stock_days"] / sector_zero.groupby("short_quintile")["stock_days"].transform("sum")
    sector_zero["gross_weight_share_within_zero"] = sector_zero["gross_weight"] / sector_zero.groupby("short_quintile")["gross_weight"].transform("sum")
    sector_zero.to_csv(output / "zero_score_short_sector.csv", index=False)
    all_zero = pd.DataFrame({
        "Sector33CodeName": listed["Sector33CodeName"].reindex(score.index).fillna("Unknown").astype(str),
        "is_zero": score.eq(0.0), "is_short_zero": q.isin([0, 1]) & score.eq(0.0),
    }, index=score.index)
    sector_zero_bias = (all_zero.loc[all_zero.is_zero].groupby("Sector33CodeName", dropna=False)
                        .agg(all_zero_stock_days=("is_zero", "size"),
                             short_zero_stock_days=("is_short_zero", "sum")))
    sector_zero_bias["all_zero_share"] = sector_zero_bias["all_zero_stock_days"] / sector_zero_bias["all_zero_stock_days"].sum()
    sector_zero_bias["short_zero_share"] = sector_zero_bias["short_zero_stock_days"] / sector_zero_bias["short_zero_stock_days"].sum()
    sector_zero_bias["short_minus_all_zero_share"] = sector_zero_bias["short_zero_share"] - sector_zero_bias["all_zero_share"]
    sector_zero_bias.reset_index().to_csv(output / "zero_score_sector_bias.csv", index=False)
    code_order = prior.zero_code_order_metrics(score, q)

    overall = {
        "evaluation_start": EVAL_START, "evaluation_end": EVAL_END,
        "evaluation_days": int(score.index.get_level_values("Date").nunique()),
        "score_rows": int(len(score)), "short_stock_days": int(len(short)),
        "short_gross_weight": float(short["portfolio_weight"].abs().sum()),
        "short_positive_score_rate": float(short["final_score"].gt(0.0).mean()),
        "short_weak_positive_rate_daily_positive_median": float(short["weak_positive"].mean()),
        "short_zero_score_rate": float(short["zero_score_flag"].mean()),
        "short_zero_gross_weight_rate": float(short["portfolio_weight"].abs().where(short["zero_score_flag"], 0.0).sum() / short["portfolio_weight"].abs().sum()),
        "short_tie_break_stock_day_rate": float(short["tie_break_flag"].mean()),
        "short_code_order_zero_tie_days": int(short.loc[short["zero_score_flag"]].groupby(level="Date")["official_quintile"].nunique().gt(1).sum()),
        "high_state_positive_short_rate": float(short["high_state"].gt(0.0).mean()),
        "low_state_negative_short_rate": float(short["low_state"].lt(0.0).mean()),
        "eligible_box_short_rate": float(short["box_eligible"].mean()),
        "short_median_turnover_value_t": float(short["TurnoverValue_t"].median()),
        "short_median_volume_t": float(short["Volume_t"].median()),
        "high_age_5_plus_active_short_rate": float(short["high_age_5_plus_abs_share"].gt(0.0).mean()),
        "high_age_5_plus_dominant_short_rate": float(short["dominant_source"].eq("high_age_5_plus").mean()),
        "high_age_5_plus_short_high_positive_rate": float(short.loc[short["high_age_5_plus_abs_share"].gt(0.0), "high_state"].gt(0.0).mean()),
        "low_age_5_plus_active_short_rate": float(short["low_age_5_plus_abs_share"].gt(0.0).mean()),
        "low_age_5_plus_dominant_short_rate": float(short["dominant_source"].eq("low_age_5_plus").mean()),
        "low_age_5_plus_short_low_negative_rate": float(short.loc[short["low_age_5_plus_abs_share"].gt(0.0), "low_state"].lt(0.0).mean()),
        "high_state_ewma_alpha": ALPHA_HIGH, "low_state_ewma_alpha": ALPHA_LOW,
        "cross_section_negative_score_rate": float(score.lt(0.0).mean()),
        "cross_section_zero_score_rate": float(score.eq(0.0).mean()),
        "cross_section_positive_score_rate": float(score.gt(0.0).mean()),
        "days_nonpositive_score_coverage_below_40pct": int(sign_by_day["negative"].add(sign_by_day["zero"]).lt(0.40).sum()),
        "days_negative_score_coverage_below_40pct": int(sign_by_day["negative"].lt(0.40).sum()),
        "daily_median_nonpositive_score_coverage": float((sign_by_day["negative"] + sign_by_day["zero"]).median()),
        "q1_q2_zero_code_order_spearman_q": code_order["zero_code_order_spearman_q"],
        "q1_q2_zero_code_order_spanning_days": code_order["zero_code_order_spanning_days"],
        "short_fraction_abs_score_below_1e_12": float(short["score_abs"].lt(1e-12).mean()),
        "short_fraction_abs_score_below_1e_8": float(short["score_abs"].lt(1e-8).mean()),
        "short_fraction_abs_score_below_1e_4": float(short["score_abs"].lt(1e-4).mean()),
        "inverse_ewma_max_abs_error": inverse_error,
        "saved_weight_replay_max_abs_error": weight_error,
        "valid_accessed": False, "target_or_return_read": False, "pnl_calculated": False,
        "opened_parquets": sorted(firewall.ACCESSES),
    }
    write_json(output / "structural_audit.json", overall)
    return overall


def candidate_score_streams(box_score: pd.Series) -> tuple[dict[str, pd.Series], dict[str, pd.DataFrame]]:
    """Rebuild only the two frozen candidate score streams from saved BOX signal state."""
    rebuilt = sn1.rebuild_from_base_score(box_score.rename("BOX"))
    high_raw, low_raw = rebuilt["high_raw"], rebuilt["low_raw"]
    d_score = rebuilt["D_LOW_FAST_ONLY"]
    components = asym.score_components(high_raw, low_raw, ALPHA_HIGH, ALPHA_LOW)
    side_score = rebuilt["SIDE_SOURCE_SEPARATION"]

    high_dominant = components.abs().idxmax(axis=1).eq("high_age_5_plus")
    frame = pd.DataFrame({
        "Date": d_score.index.get_level_values("Date"),
        "Code": d_score.index.get_level_values("Code").astype(str),
        "veto": high_dominant.to_numpy(),
        "base_score": d_score.to_numpy(),
    }, index=d_score.index)
    ordered = frame.reset_index(drop=True).sort_values(
        ["Date", "veto", "base_score", "Code"], kind="mergesort"
    )
    ordered["ordinal"] = ordered.groupby("Date", sort=False).cumcount().add(1)
    veto_score = pd.Series(ordered["ordinal"].to_numpy(dtype=float),
                           index=pd.MultiIndex.from_arrays(
                               [ordered["Date"], ordered["Code"]], names=["Date", "Code"]
                           )).sort_index().rename("HIGH_AGE5_SHORT_VETO")
    if not veto_score.index.equals(d_score.index):
        raise AssertionError("High-age veto daily ordinal lost score index alignment")
    return {
        "D_LOW_FAST_ONLY": d_score,
        "SIDE_SOURCE_SEPARATION": side_score,
        "HIGH_AGE5_SHORT_VETO": veto_score,
    }, {
        "D_LOW_FAST_ONLY": components,
        "SIDE_SOURCE_SEPARATION": components,
        "HIGH_AGE5_SHORT_VETO": components,
    }


def prefix_mutation_audit(box_score: pd.Series, scores: dict[str, pd.Series], output: Path) -> dict:
    """Reverse each suffix cross-section and assert all earlier score/rank/weight outputs match."""
    records = []
    cutoffs = ("2012-12-28", "2014-12-30", "2015-12-30")
    for cutoff_text in cutoffs:
        cutoff = pd.Timestamp(cutoff_text)
        mutated = box_score.copy()
        suffix = mutated.index.get_level_values("Date") > cutoff
        suffix_values = mutated.loc[suffix].groupby(level="Date", sort=False).transform(
            lambda part: pd.Series(part.to_numpy()[::-1], index=part.index)
        )
        mutated.loc[suffix] = suffix_values
        changed = not np.array_equal(mutated.loc[suffix].to_numpy(), box_score.loc[suffix].to_numpy())
        if not changed:
            raise AssertionError(f"Suffix mutation did not change input after {cutoff.date()}")
        mutated_scores, _ = candidate_score_streams(mutated)
        prefix = scores["D_LOW_FAST_ONLY"].index.get_level_values("Date") <= cutoff
        for name in ("D_LOW_FAST_ONLY", "SIDE_SOURCE_SEPARATION", "HIGH_AGE5_SHORT_VETO"):
            left = scores[name].loc[prefix]
            right = mutated_scores[name].reindex(scores[name].index).loc[prefix]
            if not left.index.equals(right.index) or not np.array_equal(left.to_numpy(), right.to_numpy()):
                raise AssertionError(f"Future mutation changed {name} prefix at {cutoff.date()}")
            w_left, q_left = prior.quintile_weights(scores[name].loc[prefix])
            w_right, q_right = prior.quintile_weights(mutated_scores[name].reindex(scores[name].index).loc[prefix])
            if not w_left.equals(w_right) or not q_left.equals(q_right):
                raise AssertionError(f"Future mutation changed prefix portfolio for {name} at {cutoff.date()}")
        records.append({"cutoff": cutoff_text, "suffix_rows_mutated": int(suffix.sum()),
                        "changed_after_cutoff": True, "all_candidate_prefixes_exact": True,
                        "portfolio_prefix_exact": True})
    result = {"status": "PASS", "mutation": "reverse every per-date BOX score cross-section strictly after cutoff",
              "comparison": "exact index and values; candidate weights and quintiles exact",
              "cutoffs": records, "valid_accessed": False}
    write_json(output / "prefix_invariance.json", result)
    return result


def sign_tie_rate(score: pd.Series) -> dict:
    grouped = score.groupby(level="Date", sort=False)
    tie_size = grouped.transform(lambda x: x.groupby(x, sort=False).transform("size"))
    weight, q = prior.quintile_weights(score)
    q_min = q.groupby([score.index.get_level_values("Date"), score], sort=False).transform("min")
    q_max = q.groupby([score.index.get_level_values("Date"), score], sort=False).transform("max")
    return {
        "zero_score_rate": float(score.eq(0.0).mean()),
        "duplicate_score_stock_day_rate": float(tie_size.gt(1).mean()),
        "tie_crossing_quintile_boundary_stock_day_rate": float((tie_size.gt(1) & q_min.ne(q_max)).mean()),
        "unique_score_count_pooled": int(score.nunique()),
        "mean_daily_unique_score_count": float(score.groupby(level="Date").nunique().mean()),
        "mean_daily_unique_score_ratio": float((score.groupby(level="Date").nunique() /
                                                  score.groupby(level="Date").size()).mean()),
        "min_daily_unique_score_ratio": float((score.groupby(level="Date").nunique() /
                                                 score.groupby(level="Date").size()).min()),
        "q_group_count_min": int(q.groupby(level="Date").nunique().min()),
        "q_group_count_max": int(q.groupby(level="Date").nunique().max()),
        "bucket_count_spread_max": int(q.groupby([q.index.get_level_values("Date"), q]).size()
                                        .groupby(level=0).agg(lambda x: x.max() - x.min()).max()),
        "average_long_exposure": float(weight.clip(lower=0.0).groupby(level="Date").sum().mean()),
        "average_short_exposure": float(-weight.clip(upper=0.0).groupby(level="Date").sum().mean()),
        "average_net_exposure": float(weight.groupby(level="Date").sum().mean()),
        "average_gross_exposure": float(weight.abs().groupby(level="Date").sum().mean()),
        "quintile_weights": weight,
        "quintile_labels": q,
    }


def metric_periods(accounts: pd.DataFrame) -> list[tuple[str, pd.DatetimeIndex]]:
    dates = pd.DatetimeIndex(accounts.index)
    rows = [("full_train_eval", dates), ("ex_2016", dates[dates.year != 2016])]
    rows.extend((str(year), dates[dates.year == year]) for year in range(2011, 2017))
    return [(name, pd.DatetimeIndex(period_dates)) for name, period_dates in rows if len(period_dates)]


def all_metric_rows(scores, weights, quintiles, accounts, target, sector, names):
    rows = []
    period_rows = metric_periods(accounts[names[0]])
    for name in names:
        for period, dates in period_rows:
            daily = accounts[name].loc[accounts[name].index.isin(dates)]
            rows.append(prior.stat_record(name, period, scores[name], weights[name], quintiles[name],
                                          daily, target, sector))
    return pd.DataFrame(rows)


def source_night_attribution(name, score, weight, q, components, target, night_return,
                             eval_dates, accounts, output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    fractions = prior.component_fractions(score, components, q)
    turnover_allocation = prior.category_turnover(weight, fractions)["short"]
    short_weight = weight.clip(upper=0.0)
    rows, year_rows = [], []
    daily_sources = {}
    eval_mask = score.index.get_level_values("Date").isin(eval_dates)
    total_short_weight = float(weight.abs().where(weight.lt(0.0) & eval_mask, 0.0).sum())
    short_stock_days = int((weight.lt(0.0) & eval_mask).sum())
    for category in prior.CATEGORIES:
        frac = fractions[category]
        gross_i = short_weight * night_return.reindex(score.index) * frac
        gross = gross_i.groupby(level="Date").sum().reindex(eval_dates).fillna(0.0)
        turn_i = turnover_allocation[category]
        cost = (ONE_WAY_COST * turn_i).where(target.notna(), 0.0).groupby(level="Date").sum().reindex(eval_dates).fillna(0.0) * 0.5
        net = gross - cost
        daily_sources[category] = pd.DataFrame({"gross": gross, "cost": cost, "net": net})
        active = weight.lt(0.0) & eval_mask
        frac_weight = float((weight.abs() * frac).where(active, 0.0).sum())
        attributed_days = float(frac.where(active, 0.0).sum())
        row = {
            "strategy": name, "source": category,
            "annual_gross_contribution": float(gross.mean() * 252.0),
            "annual_cost_contribution": float(cost.mean() * 252.0),
            "annual_net_contribution": float(net.mean() * 252.0),
            "standalone_attributed_net_sharpe": evaluation.sharpe(net),
            "gross_weight_share_short": frac_weight / total_short_weight if total_short_weight else np.nan,
            "fractional_stock_days_share_short": attributed_days / short_stock_days if short_stock_days else np.nan,
            "primary_source_stock_days": int((active & fractions.idxmax(axis=1).eq(category)).sum()),
            "fractional_stock_days": attributed_days,
            "short_stock_days": short_stock_days,
        }
        rows.append(row)
        for year in range(2011, 2017):
            selected_dates = eval_dates[eval_dates.year == year]
            cell = daily_sources[category].reindex(selected_dates)
            if len(cell):
                year_rows.append({
                    "strategy": name, "year": year, "source": category,
                    "annual_gross_contribution": float(cell.gross.mean() * 252.0),
                    "annual_cost_contribution": float(cell.cost.mean() * 252.0),
                    "annual_net_contribution": float(cell.net.mean() * 252.0),
                    "standalone_attributed_net_sharpe": evaluation.sharpe(cell.net),
                })
    full = pd.DataFrame(rows)
    yearly = pd.DataFrame(year_rows)
    full.to_csv(output_dir / f"short_night_source_{name}.csv", index=False)
    return full, yearly


def paired_bootstrap(baseline: pd.Series, candidate: pd.Series) -> dict:
    base = np.asarray(baseline, dtype=float)
    cand = np.asarray(candidate, dtype=float)
    if len(base) != len(cand) or not len(base):
        raise ValueError("Paired bootstrap inputs must be nonempty and aligned")
    sr = evaluation.bootstrap_delta(base, cand, seed=BOOTSTRAP_SEED,
                                    reps=BOOTSTRAP_REPS, block=BOOTSTRAP_BLOCK)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    starts = rng.integers(0, len(base), size=(BOOTSTRAP_REPS, int(np.ceil(len(base) / BOOTSTRAP_BLOCK))))
    indices = ((starts[:, :, None] + np.arange(BOOTSTRAP_BLOCK)) % len(base)).reshape(BOOTSTRAP_REPS, -1)[:, :len(base)]
    delta_annual = (cand[indices].mean(axis=1) - base[indices].mean(axis=1)) * 252.0
    return {
        "delta_net_sharpe": float(evaluation.sharpe(cand) - evaluation.sharpe(base)),
        "delta_net_sharpe_ci_low": sr["low"], "delta_net_sharpe_ci_high": sr["high"],
        "delta_net_annual_return": float((cand.mean() - base.mean()) * 252.0),
        "delta_net_annual_return_ci_low": float(np.quantile(delta_annual, 0.025)),
        "delta_net_annual_return_ci_high": float(np.quantile(delta_annual, 0.975)),
        "bootstrap_positive_net_sharpe_fraction": sr["bootstrap_positive_fraction"],
        "repetitions": BOOTSTRAP_REPS, "block_days": BOOTSTRAP_BLOCK, "seed": BOOTSTRAP_SEED,
    }


def run_evaluation(config_path: Path, output: Path) -> dict:
    """Evaluate exactly the intervention plan's two candidates on Train labels."""
    started = time.monotonic()
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    plan_path = ROOT / config["intervention_plan"]
    plan_hash = sha256(plan_path)
    if plan_hash != config.get("intervention_plan_sha256"):
        raise AssertionError("Frozen intervention plan hash does not match config")
    expected_names = ("SIDE_SOURCE_SEPARATION", "HIGH_AGE5_SHORT_VETO")
    if tuple(row["trial_id"] for row in config.get("candidates", [])) != expected_names:
        raise AssertionError("Candidate list differs from the frozen plan")
    if config.get("data_split") != "train" or config.get("valid_evaluation") is not False or config.get("selection_eligible") is not False:
        raise AssertionError("Run config is not Train-only/non-selection")
    output.mkdir(parents=True, exist_ok=False)
    for name in ("predictions", "metrics", "audit", "logs"):
        (output / name).mkdir(parents=True, exist_ok=True)

    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    git_status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, check=True,
                                capture_output=True, text=True).stdout.strip()
    run = {
        "schema_version": 1, "experiment_id": EXPERIMENT_ID, "run_id": output.name,
        "status": "running", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit_hash": git_head, "git_worktree_dirty": bool(git_status),
        "config_sha256": sha256(config_path), "intervention_plan_sha256": plan_hash,
        "code_sha256": {str(Path(__file__).resolve().relative_to(ROOT)): sha256(Path(__file__).resolve()),
                        "research/evaluation.py": sha256(ROOT / "research/evaluation.py"),
                        "research/experiments/box_asymmetry_gate.py": sha256(ROOT / "research/experiments/box_asymmetry_gate.py"),
                        "research/experiments/box_asym_ewma.py": sha256(ROOT / "research/experiments/box_asym_ewma.py"),
                        "research/experiments/box_bidirectional_day_night.py": sha256(ROOT / "research/experiments/box_bidirectional_day_night.py"),
                        "stock_comp_2026/evaluate_script.py": sha256(ROOT / "stock_comp_2026/evaluate_script.py")},
        "source_artifact_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in (SOURCE, SCORES, WEIGHTS, EVENT_MASKS)},
        "environment": {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__, "pandas": pd.__version__},
        "source_run_id": "run-20260926T063602Z", "baseline_run_id": BASE_RUN.name,
        "period": [EVAL_START, EVAL_END], "cost_oneway": ONE_WAY_COST, "annualization": 252,
        "bootstrap": {"method": "research.evaluation.bootstrap_delta circular paired blocks",
                      "block_days": BOOTSTRAP_BLOCK, "repetitions": BOOTSTRAP_REPS, "seed": BOOTSTRAP_SEED},
        "candidate_trials": list(expected_names), "valid_accessed": False,
        "raw_target_accessed": False, "submission_evaluation": False,
    }
    write_json(output / "run.json", run)
    write_json(output / "config.json", config)
    (output / "plan.md").write_text(plan_path.read_text(encoding="utf-8"), encoding="utf-8")

    allowed = (SOURCE, SCORES, WEIGHTS, EVENT_MASKS)
    firewall.install(allowed_artifacts=allowed)
    saved = pd.read_parquet(SOURCE).sort_index()
    prior_scores = pd.read_parquet(SCORES).sort_index()
    prior_weights = pd.read_parquet(WEIGHTS).sort_index()
    target = pd.read_parquet(DATA_DIR / "target_1day_train.parquet", columns=["Return"])["Return"].sort_index()
    sector = pd.read_parquet(DATA_DIR / "listed_info_train.parquet", columns=[
        "Sector33Code", "Sector33CodeName", "Sector17Code", "Sector17CodeName", "ScaleCategory"
    ]).sort_index()
    prices = pd.read_parquet(DATA_DIR / "prices_daily_quotes_train.parquet", columns=["Open", "Close"]).sort_index()
    raw_returns = pd.read_parquet(DATA_DIR / "raw_return_1day_train.parquet", columns=["Return"]).sort_index()
    beta = pd.read_parquet(DATA_DIR / "beta_1day_train.parquet", columns=["Return"]).sort_index()
    topix = pd.read_parquet(DATA_DIR / "topix_return_1day_train.parquet", columns=["Return"]).sort_index()
    if not saved.index.equals(target.index):
        raise AssertionError("Saved signal and Train target indexes differ")
    if not sector.index.is_unique or not target.index.is_unique:
        raise AssertionError("Duplicate Train index")

    score_streams, components = candidate_score_streams(saved["BOX_BIDIR_STANDALONE"])
    if float((score_streams["D_LOW_FAST_ONLY"].reindex(prior_scores.index) - prior_scores["D_LOW_FAST_ONLY"]).abs().max()) > 2e-12:
        raise AssertionError("Rebuilt D baseline differs from saved D score")
    if float((score_streams["D_LOW_FAST_ONLY"].reindex(prior_weights.index) - prior_scores["D_LOW_FAST_ONLY"]).abs().max()) > 2e-12:
        raise AssertionError("D score/weight stored indexes differ")
    score_streams["BOX_ORIGINAL"] = saved["BOX_BIDIR_STANDALONE"].rename("BOX_ORIGINAL")
    box_raw, _ = prior.inverse_ewma(saved["BOX_BIDIR_STANDALONE"], ALPHA_HIGH)
    box_high_raw, box_low_raw = prior.split_raw_sides(box_raw)
    components["BOX_ORIGINAL"] = asym.score_components(
        box_high_raw, box_low_raw, ALPHA_HIGH, ALPHA_HIGH,
    )
    names = ("BOX_ORIGINAL", "D_LOW_FAST_ONLY", *expected_names)
    scores, weights, quintiles, regulation_rows = {}, {}, {}, []
    for name in names:
        score = score_streams[name].sort_index().rename(name)
        w, q = prior.quintile_weights(score)
        scores[name], weights[name], quintiles[name] = score, w, q
        if name in ("D_LOW_FAST_ONLY", "BOX_ORIGINAL"):
            reference = prior_weights[name] if name == "D_LOW_FAST_ONLY" else None
            if reference is not None and float((w - reference).abs().max()) > 1e-12:
                raise AssertionError("Official baseline weights fail saved replay")
        validation_input = score.rename("prediction").to_frame()
        aligned = align_prediction(validation_input, target.rename("Return").to_frame())
        if not aligned.index.equals(target.index):
            raise AssertionError(f"Train submission contract alignment failed for {name}")
        # The stored score artifact is the 2011-2016 evaluation window. Compute
        # regulation statistics on that same index; full in-memory scores begin
        # in 2008 and include pre-evaluation zeros that distort the distribution.
        regulatory_score = score.reindex(prior_scores.index)
        if regulatory_score.isna().any() or not regulatory_score.index.equals(prior_scores.index):
            raise AssertionError(f"Saved evaluation score coverage changed for {name}")
        info = sign_tie_rate(regulatory_score)
        q = info.pop("quintile_labels")
        w = info.pop("quintile_weights")
        # Keep the full-history arrays above for account construction. Only the
        # regulation record uses the saved evaluation window.
        unique_index = score.index.is_unique
        finite = bool(np.isfinite(score.to_numpy()).all())
        bucket_sizes = q.groupby([q.index.get_level_values("Date"), q]).size()
        counts_spread = bucket_sizes.groupby(level=0).agg(lambda x: x.max() - x.min())
        coverage = score.index.equals(target.index)
        info.update({
            "strategy": name, "unique_index": bool(unique_index), "finite_numeric_score": finite,
            "train_target_index_coverage": bool(coverage), "one_numeric_column_contract": True,
            "official_align_prediction_contract": "PASS",
            "five_quintile_daily_coverage": bool(q.groupby(level="Date").nunique().eq(5).all()),
            "quintile_bucket_count_spread_max": int(counts_spread.max()),
            "official_weights_finite": bool(np.isfinite(w.to_numpy()).all()),
            "score_contract_pass": bool(unique_index and finite and coverage and q.groupby(level="Date").nunique().eq(5).all()),
        })
        regulation_rows.append(info)

    prefix = prefix_mutation_audit(saved["BOX_BIDIR_STANDALONE"], score_streams, output / "audit")

    eval_accounts = {}
    full_daily = {}
    period_rows, ls_rows, cell_rows = [], [], []
    daynight_results = {}
    for name in names:
        daily, _, _ = prior.account_from_weights(scores[name], weights[name], quintiles[name], target)
        full_daily[name] = daily
        daynight_results[name] = day_night.calculate(
            scores[name], target, prices, raw_returns, beta, topix
        )
        eval_dates_for_name = daynight_results[name]["evaluation_dates"]
        eval_accounts[name] = daily.loc[daily.index.isin(eval_dates_for_name)].copy()
        if not daynight_results[name]["official_daily"].index.equals(eval_accounts[name].index):
            raise AssertionError(f"Day/night evaluation dates mismatch for {name}")
        for col in ("gross", "net", "cost", "turnover"):
            official = eval_accounts[name][col].reindex(daynight_results[name]["evaluation_dates"])
            split_col = col
            if col == "turnover":
                split = daynight_results[name]["daily"][["long_day_cost", "long_night_cost", "short_day_cost", "short_night_cost"]].sum(axis=1) * 0.0
                # Turnover itself is source-independent and checked through the official daily account.
                continue
            split_cols = [f"{side}_{session}_{split_col}" for side in day_night.SIDES for session in day_night.SESSIONS]
            split_value = daynight_results[name]["daily"][split_cols].sum(axis=1)
            if float((official - split_value).abs().max()) > 1e-10:
                raise AssertionError(f"Day/night {col} does not reconcile for {name}")

    eval_dates = daynight_results["D_LOW_FAST_ONLY"]["evaluation_dates"]
    if str(eval_dates.min().date()) != EVAL_START or str(eval_dates.max().date()) != EVAL_END or len(eval_dates) != 1275:
        raise AssertionError("Purged Train evaluation window changed")
    for name in names:
        account = full_daily[name].loc[eval_dates]
        for period, dates in metric_periods(account):
            period_rows.append(prior.stat_record(name, period, scores[name], weights[name], quintiles[name],
                                                 account.loc[account.index.isin(dates)], target, sector))
            selected = account.loc[account.index.isin(dates)]
            for side, column in (("long", "long_net"), ("short", "short_net")):
                series = selected[column]
                ls_rows.append({"strategy": name, "period": period, "side": side,
                                "annual_gross": float(selected[f"{side}_gross"].mean() * 252.0),
                                "annual_net": float(series.mean() * 252.0),
                                "net_volatility": float(series.std(ddof=1) * np.sqrt(252.0)),
                                "net_sharpe": evaluation.sharpe(series)})
            cells = daynight_results[name]["daily"]
            for side in day_night.SIDES:
                for session in day_night.SESSIONS:
                    gross = cells.loc[cells.index.isin(dates), f"{side}_{session}_gross"]
                    net = cells.loc[cells.index.isin(dates), f"{side}_{session}_net"]
                    cost = cells.loc[cells.index.isin(dates), f"{side}_{session}_cost"]
                    cell_rows.append({"strategy": name, "period": period, "side": side,
                                      "session": session, "days": len(net),
                                      "annual_gross": float(gross.mean() * 252.0),
                                      "annual_cost": float(cost.mean() * 252.0),
                                      "annual_net": float(net.mean() * 252.0),
                                      "gross_volatility": float(gross.std(ddof=1) * np.sqrt(252.0)),
                                      "net_volatility": float(net.std(ddof=1) * np.sqrt(252.0)),
                                      "gross_sharpe": evaluation.sharpe(gross),
                                      "net_sharpe": evaluation.sharpe(net)})

    periods = pd.DataFrame(period_rows)
    periods.to_csv(output / "metrics/period_metrics.csv", index=False)
    pd.DataFrame(ls_rows).to_csv(output / "metrics/long_short_metrics.csv", index=False)
    cells = pd.DataFrame(cell_rows)
    cells.to_csv(output / "metrics/day_night_metrics.csv", index=False)
    pd.concat([cells.loc[cells.strategy.eq(name) & cells.period.eq("full_train_eval")] for name in names], ignore_index=True).to_csv(
        output / "metrics/day_night_pooled.csv", index=False)
    pd.concat([cells.loc[cells.strategy.eq(name) & cells.period.isin(["ex_2016", "2011", "2012", "2013", "2014", "2015", "2016"])]
               for name in names], ignore_index=True).to_csv(output / "metrics/day_night_by_year.csv", index=False)

    comparison_rows = []
    for candidate in expected_names:
        for baseline in ("D_LOW_FAST_ONLY", "BOX_ORIGINAL"):
            c = periods.loc[periods.strategy.eq(candidate)].set_index("period")
            b = periods.loc[periods.strategy.eq(baseline)].set_index("period")
            for period in c.index.intersection(b.index):
                x, y = c.loc[period], b.loc[period]
                comparison_rows.append({
                    "candidate": candidate, "baseline": baseline, "period": period,
                    "delta_annual_gross_return": x.annual_gross_return - y.annual_gross_return,
                    "delta_annual_net_return": x.annual_net_return - y.annual_net_return,
                    "delta_annual_common": x.annual_common_residual_component - y.annual_common_residual_component,
                    "delta_annual_selection": x.annual_selection_component - y.annual_selection_component,
                    "delta_annual_cost": x.annualized_cost - y.annualized_cost,
                    "delta_gross_volatility": x.annualized_gross_volatility - y.annualized_gross_volatility,
                    "delta_net_volatility": x.annualized_net_volatility - y.annualized_net_volatility,
                    "delta_gross_sharpe": x.gross_sharpe - y.gross_sharpe,
                    "delta_net_sharpe": x.net_sharpe - y.net_sharpe,
                    "delta_turnover_per_day": x.turnover_per_day - y.turnover_per_day,
                    "delta_average_gross_exposure": x.average_gross_exposure - y.average_gross_exposure,
                    "delta_average_net_exposure": x.average_net_exposure - y.average_net_exposure,
                    "delta_net_exposure_common_proxy": x.annual_net_exposure_common_proxy - y.annual_net_exposure_common_proxy,
                    "delta_rankic": x.rankic - y.rankic,
                })
    differences = pd.DataFrame(comparison_rows)
    differences.to_csv(output / "metrics/paired_differences.csv", index=False)

    # Same residual overnight attribution as the existing day/night routine; Train raw target is not read.
    dates = pd.DatetimeIndex(target.index.get_level_values("Date").unique()).sort_values()
    entry_index, _ = day_night.future_index(target.index, dates, 1)
    exit_index, exit_dates = day_night.future_index(target.index, dates, 2)
    raw_day = (pd.to_numeric(prices["Close"].reindex(entry_index), errors="coerce").to_numpy() /
               pd.to_numeric(prices["Open"].reindex(entry_index), errors="coerce").to_numpy() - 1.0)
    raw_o2o = pd.to_numeric(raw_returns["Return"].reindex(exit_index), errors="coerce").to_numpy()
    beta_exit = pd.to_numeric(beta["Return"].reindex(exit_index), errors="coerce").to_numpy()
    topix_exit = pd.to_numeric(topix["Return"].reindex(exit_dates), errors="coerce").to_numpy()
    raw_night = (1.0 + raw_o2o) / (1.0 + raw_day) - 1.0
    night_return = pd.Series(
        raw_night + 0.5 * raw_day * raw_night - 0.5 * beta_exit * topix_exit,
        index=target.index, name="night_residual_component",
    )
    reconstructed = raw_o2o - beta_exit * topix_exit
    valid = target.notna().to_numpy() & target.index.get_level_values("Date").isin(eval_dates)
    target_reconstruction_error = float(np.nanmax(np.abs(reconstructed[valid] - target.to_numpy()[valid])))
    if target_reconstruction_error > 1e-12:
        raise AssertionError(f"Train target reconstruction mismatch: {target_reconstruction_error}")

    source_tables, source_year_tables, short_night_series = [], [], {}
    for name in names:
        full_attr, yearly_attr = source_night_attribution(
            name, scores[name], weights[name], quintiles[name], components[name], target,
            night_return, eval_dates, full_daily[name], output / "metrics",
        )
        source_tables.append(full_attr)
        source_year_tables.append(yearly_attr)
        # daily category net values are rebuilt with the same existing cost allocator for bootstrap.
        frac = prior.component_fractions(scores[name], components[name], quintiles[name])
        alloc = prior.category_turnover(weights[name], frac)["short"]
        nrows = {}
        for category in prior.CATEGORIES:
            gross = (weights[name].clip(upper=0.0) * night_return * frac[category]).groupby(level="Date").sum().reindex(eval_dates).fillna(0.0)
            cost = (ONE_WAY_COST * alloc[category]).where(target.notna(), 0.0).groupby(level="Date").sum().reindex(eval_dates).fillna(0.0) * 0.5
            nrows[category] = gross - cost
        short_night_series[name] = pd.DataFrame(nrows, index=eval_dates).sum(axis=1)
    source_all = pd.concat(source_tables, ignore_index=True)
    source_year = pd.concat(source_year_tables, ignore_index=True)
    source_all.to_csv(output / "metrics/short_night_source_attribution.csv", index=False)
    source_year.to_csv(output / "metrics/short_night_source_attribution_by_year.csv", index=False)

    bootstrap_rows = []
    base_name = "D_LOW_FAST_ONLY"
    for candidate in expected_names:
        base_daily = full_daily[base_name].loc[eval_dates, "net"]
        candidate_daily = full_daily[candidate].loc[eval_dates, "net"]
        result = paired_bootstrap(base_daily, candidate_daily)
        bn = short_night_series[base_name]
        cn = short_night_series[candidate]
        sn = paired_bootstrap(bn, cn)
        result.update({"candidate": candidate, "baseline": base_name,
                       "delta_short_night_net_contribution": float((cn.mean() - bn.mean()) * 252.0),
                       "delta_short_night_ci_low": float(sn["delta_net_annual_return_ci_low"]),
                       "delta_short_night_ci_high": float(sn["delta_net_annual_return_ci_high"])})
        bootstrap_rows.append(result)
    pd.DataFrame(bootstrap_rows).to_csv(output / "metrics/paired_circular_bootstrap.csv", index=False)

    # Store official-compatible score/weight/quintile evidence for all baselines and fixed candidates.
    eval_index = scores["D_LOW_FAST_ONLY"].index[scores["D_LOW_FAST_ONLY"].index.get_level_values("Date").isin(eval_dates)]
    pd.DataFrame({name: scores[name].reindex(eval_index) for name in names}).to_parquet(output / "predictions/strategy_scores.parquet")
    pd.DataFrame({name: weights[name].reindex(eval_index) for name in names}).to_parquet(output / "predictions/portfolio_weights.parquet")
    pd.DataFrame({name: quintiles[name].reindex(eval_index) for name in names}).to_parquet(output / "predictions/official_quintiles.parquet")
    for name in names:
        full_daily[name].loc[eval_dates].to_csv(output / f"metrics/daily_account_{name}.csv", index_label="Date")
        daynight_results[name]["daily"].to_csv(output / f"metrics/day_night_daily_{name}.csv", index_label="Date")
    pd.DataFrame(regulation_rows).to_csv(output / "audit/regulation_checks.csv", index=False)

    # Detailed source-specific holdings for every short row, including candidate re-ranking.
    details = []
    for name in names:
        w = weights[name].reindex(eval_index)
        q = quintiles[name].reindex(eval_index)
        s = scores[name].reindex(eval_index)
        comp = components[name].reindex(eval_index)
        held = w.lt(0.0)
        part = pd.DataFrame({"Date": eval_index.get_level_values("Date"),
                             "Code": eval_index.get_level_values("Code").astype(str),
                             "strategy": name, "score": s.to_numpy(), "weight": w.to_numpy(),
                             "quintile": q.to_numpy(), "primary_source": comp.abs().idxmax(axis=1).to_numpy()}, index=eval_index)
        for col in comp:
            part[col] = comp[col].to_numpy()
        part = part.loc[held]
        part["zero_score"] = part.score.eq(0.0)
        details.append(part.reset_index(drop=True))
    pd.concat(details, ignore_index=True).to_parquet(output / "predictions/short_holdings_audit.parquet")

    input_hashes = {name: sha256(DATA_DIR / name) for name in (
        "target_1day_train.parquet", "listed_info_train.parquet", "prices_daily_quotes_train.parquet",
        "raw_return_1day_train.parquet", "beta_1day_train.parquet", "topix_return_1day_train.parquet",
    )}
    firewall_result = {
        "status": "PASS" if not any("_valid" in Path(p).name or "raw_target" in Path(p).name for p in firewall.ACCESSES) else "FAIL",
        "opened_parquets": sorted(firewall.ACCESSES), "valid_accessed": False,
        "raw_target_accessed": False, "all_data_files_train": True,
    }
    write_json(output / "audit/firewall.json", firewall_result)
    write_json(output / "audit/pnl_reconciliation.json", {
        "target_reconstruction_max_abs_error": target_reconstruction_error,
        "day_night_four_cell_reconciled": True,
        "baseline_saved_D_score_max_abs_error": float((score_streams[base_name].reindex(prior_scores.index) - prior_scores[base_name]).abs().max()),
        "baseline_saved_D_weight_max_abs_error": float((weights[base_name].reindex(prior_weights.index) - prior_weights[base_name]).abs().max()),
        "valid_accessed": False,
    })
    write_json(output / "audit/regulation_summary.json", {
        "checks": "audit/regulation_checks.csv",
        "official_source": "stock_comp_2026/evaluate_script.py::align_prediction and repository official quintile helper",
        "separate_regulation_checker_found": False,
        "score_zero_or_uniqueness_minimum_in_repo": "not specified in README or evaluator contract; B00 remains diagnostic-only per user instruction",
        "submission_evaluation_run": False,
        "train_contract_validation": "evaluate_script.align_prediction invoked on in-memory Train-index predictions only",
        "valid_accessed": False,
    })
    write_json(output / "audit/train_data_hashes.json", input_hashes)
    run.update({
        "status": "completed", "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "exit_code": 0, "elapsed_seconds": time.monotonic() - started,
        "train_data_sha256": input_hashes, "evaluation_days": len(eval_dates),
        "evaluation_span": [str(eval_dates.min().date()), str(eval_dates.max().date())],
        "partial_2016_span": [str(eval_dates[eval_dates.year == 2016].min().date()),
                              str(eval_dates[eval_dates.year == 2016].max().date())],
        "valid_accessed": False, "raw_target_accessed": False, "submission_evaluation": False,
        "prefix_invariance": prefix, "outputs": {
            "period_metrics": "metrics/period_metrics.csv", "short_night_source": "metrics/short_night_source_attribution.csv",
            "short_night_source_by_year": "metrics/short_night_source_attribution_by_year.csv",
            "day_night_metrics": "metrics/day_night_metrics.csv", "regulation": "audit/regulation_checks.csv",
            "scores": "predictions/strategy_scores.parquet", "weights": "predictions/portfolio_weights.parquet",
        },
    })
    write_json(output / "run.json", run)
    return run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["structure", "evaluate"], required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--config")
    args = parser.parse_args()
    if args.phase == "structure":
        metadata = structural_audit(Path(args.output))
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
    elif args.phase == "evaluate":
        if not args.config:
            parser.error("--config is required for --phase evaluate")
        metadata = run_evaluation(Path(args.config), Path(args.output))
        print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
