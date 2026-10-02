"""Train-only attribution of unchanged SN1_H1 by source, magnitude and VOL20."""
from __future__ import annotations

import argparse
import gc
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
from research.experiments import sn1_volatility_diagnostic as vol_diag
from stock_comp_2026.strategies.dm_variable_box_breakout import bidirectional, features, sn1, submission


EXPERIMENT_ID = "DM-20261001-03"
YEARS = tuple(range(2011, 2017))
COMPLETE_YEARS = tuple(range(2011, 2016))
NEAR_ZERO = 1e-12
WINDOW = 20
ONE_WAY_COST = 0.001
ANNUALIZATION = 252
SOURCES = ("High", "Low", "D fallback")
MAGNITUDES = ("Near-zero", "Non-near-zero")
VOL_LABELS = tuple(f"V{i}" for i in range(1, 6)) + ("VOL_MISSING",)
SIDE_NAMES = ("Long", "Short")
EVENT_AGE_BUCKETS = ("event_day", "age_1_4", "age_5_plus", "no_prior_event_in_segment")
SLEEVE_AGE_BUCKETS = ("under_20", "20_plus", "not_held")
RENEWAL_BUCKETS = ("recurrent_same_side", "single_same_side", "no_recent_same_side")
SOURCE_PATHS = (
    "research/experiments/sn1_source_magnitude_volatility.py",
    "research/experiments/sn1_volatility_diagnostic.py",
    "research/evaluation.py",
    "research/firewall.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/features.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py",
    "stock_comp_2026/strategies/dm_variable_box_breakout/submission.py",
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
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.bool_):
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
    base_score = bidirectional.generate_signal(x, independent_predictions, alpha=sn1.HIGH_ALPHA)
    reconstructed = sn1.rebuild_from_base_score(base_score)
    _exact_series(current, reconstructed["SIDE_SOURCE_SEPARATION"].rename("Return"), "source reconstruction versus SN1_H1")
    if not np.isfinite(current.to_numpy(dtype="float64")).all():
        raise AssertionError("SN1_H1 score has nonfinite values")
    return x, current, base_score, reconstructed, {
        "status": "PASS",
        "rows": int(len(current)),
        "current_route": "submission.predict_from_features",
        "independent_route": "bidirectional.walk_forward_predictions + candidate_scores_from_predictions",
        "source_reconstruction_route": "generate_signal + sn1.rebuild_from_base_score",
        "saved_current_reference": str(vol_diag.BASELINE_SAVED.relative_to(ROOT)),
        "saved_prior_reference": str(vol_diag.BASELINE_PRIOR.relative_to(ROOT)),
        "current_vs_independent_bitwise_equal": True,
        "current_vs_saved_current_bitwise_equal": True,
        "current_vs_saved_prior_bitwise_equal": True,
        "source_reconstruction_vs_current_bitwise_equal": True,
        "max_abs_error_all_comparisons": 0.0,
        "candidate_fits": 0,
    }


def _state_frame(score: pd.Series, reconstructed: dict, vol: pd.Series) -> pd.DataFrame:
    high_state = reconstructed["high_state"].reindex(score.index).rename("high_state")
    low_state = reconstructed["low_state"].reindex(score.index).rename("low_state")
    low_selected = low_state.lt(0.0)
    high_selected = low_state.eq(0.0) & high_state.gt(0.0)
    source = pd.Series(np.select([low_selected, high_selected], ["Low", "High"], default="D fallback"),
                       index=score.index, name="selected_source", dtype="object")
    expected = low_state.where(low_selected, high_state.where(high_selected, reconstructed["D_LOW_FAST_ONLY"].reindex(score.index)))
    expected.name = "Return"
    _exact_series(score.rename("Return"), expected, "existing selected-source precedence reconstruction")

    weight, quintile = evaluation.weights(score)
    side = pd.Series(np.select([weight.gt(0.0), weight.lt(0.0)], ["Long", "Short"], default="Neutral"),
                     index=score.index, name="portfolio_side", dtype="object")
    vol_q = vol_diag._vol_quintile(vol).reindex(score.index)
    vol_name = vol_q.map({float(i): f"V{i+1}" for i in range(5)}).fillna("VOL_MISSING").rename("vol_quintile")
    magnitude = pd.Series(np.where(score.abs().lt(NEAR_ZERO), "Near-zero", "Non-near-zero"),
                          index=score.index, name="score_magnitude", dtype="object")
    dates = score.index.get_level_values("Date")
    score_pct = score.groupby(level="Date", sort=False).rank(method="average", pct=True).rename("score_percentile")

    frame = pd.DataFrame({
        "score": score,
        "score_abs": score.abs(),
        "score_percentile": score_pct,
        "high_state": high_state,
        "low_state": low_state,
        "d_score": reconstructed["D_LOW_FAST_ONLY"].reindex(score.index),
        "high_event": reconstructed["high_raw"].reindex(score.index).ne(0.0),
        "low_event": reconstructed["low_raw"].reindex(score.index).ne(0.0),
        "selected_source": source,
        "score_magnitude": magnitude,
        "vol20": vol.reindex(score.index),
        "vol_quintile": vol_name,
        "weight": weight,
        "official_quintile": quintile.astype("int8") + 1,
        "portfolio_side": side,
    }, index=score.index)
    _add_age_and_renewal(frame)
    return frame


def _add_age_and_renewal(frame: pd.DataFrame) -> None:
    """Reproduce the existing fixed event/sleeve/renewal buckets on Train rows."""
    idx = frame.index
    dates = pd.DatetimeIndex(idx.get_level_values("Date"))
    code = idx.get_level_values("Code")
    groups = features.segment_keys(idx)
    calendar = pd.DatetimeIndex(dates.unique().sort_values())
    ordinal_map = pd.Series(np.arange(len(calendar), dtype="int32"), index=calendar)
    ordinal = pd.Series(ordinal_map.reindex(dates).to_numpy(dtype="int32"), index=idx)
    row_in_segment = pd.Series(np.arange(len(frame), dtype="int64"), index=idx).groupby(groups, sort=False).cumcount()

    event_age_obs = {}
    event_age_days = {}
    event_counts = {}
    for label, event_col in (("high", "high_event"), ("low", "low_event")):
        event = frame[event_col].astype(bool)
        last_ord = ordinal.where(event).groupby(groups, sort=False).ffill()
        last_row = row_in_segment.where(event).groupby(groups, sort=False).ffill()
        event_age_days[label] = (ordinal - last_ord).astype("float64")
        event_age_obs[label] = (row_in_segment - last_row).astype("float64")
        event_counts[label] = {}
        for window in (20, 60, 120):
            event_counts[label][window] = event.astype("float64").groupby(groups, sort=False).transform(
                lambda values, w=window: values.rolling(w, min_periods=1).sum()
            )

    latest_event = frame.high_event | frame.low_event
    last_event_side = pd.Series(np.where(frame.high_event, "high", np.where(frame.low_event, "low", None)),
                                index=idx, dtype="object").where(latest_event).groupby(groups, sort=False).ffill()
    last_event_ord = ordinal.where(latest_event).groupby(groups, sort=False).ffill()
    latest_age = (ordinal - last_event_ord).astype("float64")

    high_n60 = event_counts["high"][60]
    low_n60 = event_counts["low"][60]
    reinforcing_n = pd.Series(np.select(
        [frame.portfolio_side.eq("Long"), frame.portfolio_side.eq("Short")],
        [high_n60, low_n60], default=0.0,
    ), index=idx, dtype="float64")
    reinforcing_age = pd.Series(np.select(
        [frame.portfolio_side.eq("Long"), frame.portfolio_side.eq("Short")],
        [event_age_days["high"], event_age_days["low"]], default=np.nan,
    ), index=idx, dtype="float64")
    reinforcing_age_obs = pd.Series(np.select(
        [frame.portfolio_side.eq("Long"), frame.portfolio_side.eq("Short")],
        [event_age_obs["high"], event_age_obs["low"]], default=np.nan,
    ), index=idx, dtype="float64")
    frame["latest_event_side"] = last_event_side.fillna("none")
    frame["latest_event_age_trading_days"] = latest_age
    frame["side_reinforcing_events_last_60"] = reinforcing_n
    frame["side_reinforcing_event_age_days"] = reinforcing_age
    frame["side_reinforcing_event_age_observations"] = reinforcing_age_obs
    frame["event_age_bucket"] = np.select(
        [reinforcing_age_obs.eq(0.0), reinforcing_age_obs.between(1, 4), reinforcing_age_obs.ge(5)],
        ["event_day", "age_1_4", "age_5_plus"], default="no_prior_event_in_segment",
    )
    frame["renewal_bucket"] = np.select(
        [reinforcing_n.ge(2), reinforcing_n.eq(1)],
        ["recurrent_same_side", "single_same_side"], default="no_recent_same_side",
    )

    # Same fixed sleeve-age rule as the existing Train state reconstruction.
    ordered = frame.sort_index(level=[1, 0])
    oidx = ordered.index
    ocode = oidx.get_level_values("Code")
    odates = pd.Series(pd.DatetimeIndex(oidx.get_level_values("Date")), index=oidx)
    oordinal = odates.map(ordinal_map).astype("int32")
    oside = ordered.portfolio_side.map({"Short": -1, "Neutral": 0, "Long": 1}).astype("int8")
    previous_ordinal = oordinal.groupby(ocode, sort=False).shift(1)
    previous_side = oside.groupby(ocode, sort=False).shift(1).fillna(0).astype("int8")
    adjacent = oordinal.sub(previous_ordinal).eq(1)
    starts = ~adjacent | oside.ne(previous_side)
    episode = starts.groupby(ocode, sort=False).cumsum().astype("int64")
    temp = pd.DataFrame({"code_key": ocode, "side_episode": episode}, index=oidx)
    age = temp.groupby(["code_key", "side_episode"], sort=False).cumcount().add(1).astype("int32")
    age = age.where(oside.ne(0), 0)
    ordered_age = pd.Series(age.to_numpy(), index=oidx).reindex(idx).astype("int32")
    frame["sleeve_age"] = ordered_age
    frame["sleeve_age_bucket"] = np.where(frame.sleeve_age.eq(0), "not_held",
                                         np.where(frame.sleeve_age.lt(20), "under_20", "20_plus"))


def _fixed_cell_keys(frame: pd.DataFrame) -> list[tuple[str, str, str]]:
    return [(source, magnitude, vol) for source in SOURCES for magnitude in MAGNITUDES for vol in VOL_LABELS]


def _period_dates(score: pd.Series, year: int | None) -> pd.DatetimeIndex:
    dates = score.index.get_level_values("Date")
    selected = dates.year.isin(YEARS) if year is None else dates.year == year
    return pd.DatetimeIndex(sorted(dates[selected].unique()), name="Date")


def _q_summary(score: pd.Series, target: pd.Series) -> tuple[dict, pd.Series]:
    result = {f"q{k}_mean_target": np.nan for k in range(1, 6)}
    spread = pd.Series(dtype="float64")
    if len(score) < 5 or score.nunique(dropna=True) < 2:
        result["q5_q1_monotonicity"] = np.nan
        return result, spread
    _, q = evaluation.weights(score)
    means = []
    q_daily = {}
    for k in range(5):
        value = target.where(q.eq(k)).groupby(level="Date", sort=False).mean()
        q_daily[k] = value
        result[f"q{k+1}_mean_target"] = float(value.mean()) if value.notna().any() else np.nan
        means.append(result[f"q{k+1}_mean_target"])
    spread = (q_daily[4] - q_daily[0]).replace([np.inf, -np.inf], np.nan).dropna()
    result["q5_q1_monotonicity"] = (
        float(spearmanr(range(1, 6), means).statistic)
        if np.isfinite(means).all() and len(set(means)) > 1 else np.nan
    )
    return result, spread


def _cell_metrics(frame: pd.DataFrame, target: pd.Series, centered_target: pd.Series,
                  cell_mask: pd.Series, period_dates: pd.DatetimeIndex, period: str, year):
    selected = frame.loc[cell_mask]
    score = selected.score
    y = target.reindex(selected.index)
    valid = y.notna() & np.isfinite(y.to_numpy(dtype="float64"))
    score = score.loc[valid]
    y = y.loc[valid]
    daily_ic = evaluation.rankic(score, y).replace([np.inf, -np.inf], np.nan).dropna() if len(score) else pd.Series(dtype=float)
    qstats, spread = _q_summary(score, y) if len(score) else ({}, pd.Series(dtype=float))
    return {
        "period": period,
        "year": "pooled" if year is None else year,
        "partial_year": bool(year == 2016),
        "stock_days": int(len(selected)),
        "target_stock_days": int(len(score)),
        "active_dates": int(selected.index.get_level_values("Date").nunique()),
        "rankic_days": int(len(daily_ic)),
        "mean_rankic": float(daily_ic.mean()) if len(daily_ic) else np.nan,
        "rankic_hac5_t": evaluation.hac_t(daily_ic, lag=5),
        "rankic_hit_ratio": float((daily_ic > 0).mean()) if len(daily_ic) else np.nan,
        "q5_q1_spread": float(spread.mean()) if len(spread) else np.nan,
        "q_spread_dates": int(len(spread)),
        "mean_centered_target_rank": float(centered_target.reindex(score.index).mean()) if len(score) else np.nan,
        "mean_h1_residual_target": float(y.mean()) if len(y) else np.nan,
        "target_sd": float(y.std(ddof=1)) if len(y) > 1 else np.nan,
        "mean_score": float(selected.score.mean()) if len(selected) else np.nan,
        "mean_abs_score": float(selected.score_abs.mean()) if len(selected) else np.nan,
        "mean_score_percentile": float(selected.score_percentile.mean()) if len(selected) else np.nan,
        "long_membership_share": float(selected.portfolio_side.eq("Long").mean()) if len(selected) else np.nan,
        "neutral_membership_share": float(selected.portfolio_side.eq("Neutral").mean()) if len(selected) else np.nan,
        "short_membership_share": float(selected.portfolio_side.eq("Short").mean()) if len(selected) else np.nan,
        **qstats,
    }


def _matrix(frame: pd.DataFrame, target: pd.Series, score: pd.Series, output: Path):
    centered_rank = target.groupby(level="Date", sort=False).rank(method="average", pct=True)
    centered_rank = (2.0 * (centered_rank - centered_rank.groupby(level="Date", sort=False).transform("mean"))).where(target.notna())
    dates = score.index.get_level_values("Date")
    years = dates.year
    weight_abs = frame.weight.abs().where(frame.weight.ne(0.0), 0.0)
    long_turn = frame.weight.clip(lower=0.0).groupby(level="Code", sort=False).diff().abs().fillna(frame.weight.clip(lower=0.0).abs())
    short_turn = frame.weight.clip(upper=0.0).groupby(level="Code", sort=False).diff().abs().fillna(frame.weight.clip(upper=0.0).abs())
    turnover = long_turn + short_turn
    label_ok = target.notna() & np.isfinite(target.to_numpy(dtype="float64"))
    gross = (frame.weight * target).where(label_ok, 0.0).fillna(0.0)
    cost_effective = (ONE_WAY_COST * turnover).where(label_ok, 0.0)
    cost_all = ONE_WAY_COST * turnover
    net = gross - cost_effective
    long_gross = (frame.weight.clip(lower=0.0) * target).where(label_ok, 0.0).fillna(0.0)
    short_gross = (frame.weight.clip(upper=0.0) * target).where(label_ok, 0.0).fillna(0.0)
    long_cost_effective = (ONE_WAY_COST * long_turn).where(label_ok, 0.0)
    short_cost_effective = (ONE_WAY_COST * short_turn).where(label_ok, 0.0)
    long_cost_all, short_cost_all = ONE_WAY_COST * long_turn, ONE_WAY_COST * short_turn
    row = frame.copy()
    row["turnover"] = turnover
    row["long_turnover"] = long_turn
    row["short_turnover"] = short_turn
    row["gross"] = gross
    row["net"] = net
    row["cost_effective"] = cost_effective
    row["cost_all"] = cost_all
    row["long_gross"] = long_gross
    row["short_gross"] = short_gross
    row["long_cost_effective"] = long_cost_effective
    row["short_cost_effective"] = short_cost_effective
    row["long_cost_all"] = long_cost_all
    row["short_cost_all"] = short_cost_all
    row["long_net"] = long_gross - long_cost_effective
    row["short_net"] = short_gross - short_cost_effective

    daily = evaluation.daily_account(score, target)
    audit_dates = daily.index[daily.index.year.isin(YEARS)]
    daily_year = daily.loc[daily.index.year.isin(YEARS)]
    account_reconciliation = {}
    for field, vals in (("gross", gross), ("net", net), ("cost", cost_effective), ("turnover", turnover)):
        reconstructed_daily = vals.groupby(level="Date", sort=False).sum().reindex(audit_dates).fillna(0.0)
        baseline_daily = daily_year[field].reindex(audit_dates).fillna(0.0)
        delta = float((reconstructed_daily - baseline_daily).abs().max()) if len(audit_dates) else 0.0
        if delta > 2e-15:
            raise AssertionError(f"Row-level {field} does not reconcile to official daily account: {delta}")
        account_reconciliation[field] = delta

    period_specs = [("pooled_2011_2016", None)] + [(str(y), y) for y in YEARS]
    records = []
    cells = _fixed_cell_keys(frame)
    for period, year in period_specs:
        period_mask = np.isin(years, YEARS if year is None else (year,))
        account_dates = _period_dates(score, year)
        base_denominator = float(weight_abs.loc[period_mask].sum())
        for source, magnitude, vol_name in cells:
            key_mask = (frame.selected_source.eq(source) & frame.score_magnitude.eq(magnitude) & frame.vol_quintile.eq(vol_name))
            mask = key_mask & pd.Series(period_mask, index=score.index)
            metrics = _cell_metrics(frame, target, centered_rank, mask, account_dates, period, year)
            selected_rows = row.loc[mask]
            gross_daily = selected_rows.gross.groupby(level="Date", sort=False).sum().reindex(account_dates).fillna(0.0)
            net_daily = selected_rows.net.groupby(level="Date", sort=False).sum().reindex(account_dates).fillna(0.0)
            cost_daily = selected_rows.cost_effective.groupby(level="Date", sort=False).sum().reindex(account_dates).fillna(0.0)
            cost_all_daily = selected_rows.cost_all.groupby(level="Date", sort=False).sum().reindex(account_dates).fillna(0.0)
            turnover_daily = selected_rows.turnover.groupby(level="Date", sort=False).sum().reindex(account_dates).fillna(0.0)
            cell_abs_weight = float(weight_abs.loc[mask].sum())
            cell_metrics = {
                **metrics,
                "selected_source": source,
                "score_magnitude": magnitude,
                "vol_quintile": vol_name,
                "gross_weight_share": cell_abs_weight / base_denominator if base_denominator else np.nan,
                "annual_gross_contribution": float(gross_daily.mean() * ANNUALIZATION) if len(gross_daily) else np.nan,
                "annual_net_contribution": float(net_daily.mean() * ANNUALIZATION) if len(net_daily) else np.nan,
                "net_contribution_sharpe": evaluation.sharpe(net_daily) if len(net_daily) > 1 else np.nan,
                "average_daily_turnover_attribution": float(turnover_daily.mean()) if len(turnover_daily) else np.nan,
                "turnover_attribution_sum": float(turnover_daily.sum()),
                "annual_cost_attribution_official": float(cost_daily.mean() * ANNUALIZATION) if len(cost_daily) else np.nan,
                "annual_cost_attribution_all_turnover": float(cost_all_daily.mean() * ANNUALIZATION) if len(cost_all_daily) else np.nan,
            }
            records.append(cell_metrics)
    matrix = pd.DataFrame(records)
    matrix.to_csv(output / "source_magnitude_vol_matrix.csv", index=False)
    matrix.loc[matrix.period.ne("pooled_2011_2016")].to_csv(output / "yearly_matrix.csv", index=False)

    # Side attribution uses unchanged sleeve membership; sleeve exits/costs are
    # assigned to the current signal-date source/magnitude/volatility cell.
    side_rows = []
    for period, year in period_specs:
        period_mask = np.isin(years, YEARS if year is None else (year,))
        account_dates = _period_dates(score, year)
        for source, magnitude, vol_name in cells:
            key_mask = (frame.selected_source.eq(source) & frame.score_magnitude.eq(magnitude) & frame.vol_quintile.eq(vol_name))
            mask = key_mask & pd.Series(period_mask, index=score.index)
            for side in SIDE_NAMES:
                g = row.loc[mask]
                gross_col = f"{side.lower()}_gross"
                net_col = f"{side.lower()}_net"
                cost_eff_col = f"{side.lower()}_cost_effective"
                cost_all_col = f"{side.lower()}_cost_all"
                turn_col = f"{side.lower()}_turnover"
                gross_daily = g[gross_col].groupby(level="Date", sort=False).sum().reindex(account_dates).fillna(0.0)
                net_daily = g[net_col].groupby(level="Date", sort=False).sum().reindex(account_dates).fillna(0.0)
                cost_daily = g[cost_eff_col].groupby(level="Date", sort=False).sum().reindex(account_dates).fillna(0.0)
                cost_all_daily = g[cost_all_col].groupby(level="Date", sort=False).sum().reindex(account_dates).fillna(0.0)
                turn_daily = g[turn_col].groupby(level="Date", sort=False).sum().reindex(account_dates).fillna(0.0)
                members = g.loc[g.portfolio_side.eq(side)]
                side_exposure = float(row.loc[period_mask & row.portfolio_side.eq(side), "weight"].abs().sum())
                member_exposure = float(members.weight.abs().sum())
                side_rows.append({
                    "period": period, "year": "pooled" if year is None else year,
                    "partial_year": bool(year == 2016), "side": side,
                    "selected_source": source, "score_magnitude": magnitude, "vol_quintile": vol_name,
                    "stock_days": int(len(members)), "active_dates": int(members.index.get_level_values("Date").nunique()),
                    "membership_rate_within_cell": float(len(members) / len(g)) if len(g) else np.nan,
                    "side_gross_weight_share": member_exposure / side_exposure if side_exposure else np.nan,
                    "annual_gross_contribution": float(gross_daily.mean() * ANNUALIZATION) if len(gross_daily) else np.nan,
                    "annual_net_contribution": float(net_daily.mean() * ANNUALIZATION) if len(net_daily) else np.nan,
                    "contribution_sharpe": evaluation.sharpe(net_daily) if len(net_daily) > 1 else np.nan,
                    "average_daily_turnover_attribution": float(turn_daily.mean()) if len(turn_daily) else np.nan,
                    "turnover_attribution_sum": float(turn_daily.sum()),
                    "annual_cost_attribution_official": float(cost_daily.mean() * ANNUALIZATION) if len(cost_daily) else np.nan,
                    "annual_cost_attribution_all_turnover": float(cost_all_daily.mean() * ANNUALIZATION) if len(cost_all_daily) else np.nan,
                    "mean_target_on_members": float(target.reindex(members.index).mean()) if len(members) else np.nan,
                })
    sides = pd.DataFrame(side_rows)
    sides.to_csv(output / "side_source_magnitude_vol_attribution.csv", index=False)
    return matrix, sides, row, daily_year, account_reconciliation


def _boundary_sensitivity(frame: pd.DataFrame, score: pd.Series, output: Path) -> pd.DataFrame:
    _, base_q = evaluation.weights(score)
    codes = score.index.get_level_values("Code").astype(str)
    perturbation = {
        code: int.from_bytes(hashlib.blake2b(code.encode(), digest_size=8, key=b"SN1-20260928").digest(), "big") / (2**64) - 0.5
        for code in pd.Index(codes).unique()
    }
    daily_sd = score.groupby(level="Date", sort=False).transform("std")
    u = pd.Series(codes.map(perturbation).to_numpy(dtype="float64"), index=score.index)
    perturbed_score = score + 1e-12 * daily_sd * u
    _, changed_q = evaluation.weights(perturbed_score)
    if not base_q.index.equals(changed_q.index):
        raise AssertionError("Boundary perturbation changed index")
    changed = base_q.ne(changed_q)
    q12 = base_q.le(1) != changed_q.le(1)
    q45 = base_q.ge(3) != changed_q.ge(3)
    date_values = score.index.get_level_values("Date")
    eval_mask = pd.Series(date_values.year.isin(YEARS), index=score.index)
    rows = []
    group_counts = {}
    group_endpoints = {}
    group_pairs = {}
    state = frame[["selected_source", "score_magnitude", "vol_quintile"]]
    for source in SOURCES:
        for magnitude in MAGNITUDES:
            for vol_name in ("V1", "V5"):
                key = (source, magnitude, vol_name)
                mask = eval_mask & state.selected_source.eq(source) & state.score_magnitude.eq(magnitude) & state.vol_quintile.eq(vol_name)
                group_counts[key] = int(mask.sum())
                group_endpoints[key] = {"all": 0, "tie": 0, "near": 0}
                group_pairs[key] = {"all": 0, "tie": 0, "near": 0}
    frame_q = pd.DataFrame({"score": score, "q": base_q}).reset_index()
    frame_q["Code"] = frame_q.Code.astype(str)
    frame_q["source"] = state.selected_source.to_numpy()
    frame_q["magnitude"] = state.score_magnitude.to_numpy()
    frame_q["vol"] = state.vol_quintile.to_numpy()
    frame_q["year"] = pd.DatetimeIndex(frame_q.Date).year
    for _, day in frame_q.loc[frame_q.year.isin(YEARS)].groupby("Date", sort=True):
        day = day.sort_values(["score", "Code"], kind="mergesort").reset_index(drop=True)
        boundary_ix = np.flatnonzero(day.q.to_numpy()[1:] != day.q.to_numpy()[:-1])
        day_sd = float(day.score.std(ddof=1))
        for left in boundary_ix:
            a, b = day.iloc[left], day.iloc[left + 1]
            gap = float(b.score - a.score)
            exact = gap == 0.0
            near = gap <= 1e-12 * day_sd
            for endpoint in (a, b):
                key = (endpoint.source, endpoint.magnitude, endpoint.vol)
                if key in group_endpoints:
                    group_endpoints[key]["all"] += 1
                    if exact:
                        group_endpoints[key]["tie"] += 1
                    if near:
                        group_endpoints[key]["near"] += 1
            touched = {
                (a.source, a.magnitude, a.vol),
                (b.source, b.magnitude, b.vol),
            }
            for key in touched:
                if key in group_pairs:
                    group_pairs[key]["all"] += 1
                    if exact:
                        group_pairs[key]["tie"] += 1
                    if near:
                        group_pairs[key]["near"] += 1

    for key, n in group_counts.items():
        source, magnitude, vol_name = key
        mask = eval_mask & state.selected_source.eq(source) & state.score_magnitude.eq(magnitude) & state.vol_quintile.eq(vol_name)
        endpoints = group_endpoints[key]
        pairs = group_pairs[key]
        rows.append({
            "period": "pooled_2011_2016", "year": "pooled",
            "selected_source": source, "score_magnitude": magnitude, "vol_quintile": vol_name,
            "stock_days": n,
            "changed_quintile_fraction": float(changed.loc[mask].mean()) if n else np.nan,
            "changed_q1_q2_membership_fraction": float(q12.loc[mask].mean()) if n else np.nan,
            "changed_q4_q5_membership_fraction": float(q45.loc[mask].mean()) if n else np.nan,
            "boundary_endpoints_in_cell": endpoints["all"],
            "tie_boundary_endpoint_fraction": endpoints["tie"] / endpoints["all"] if endpoints["all"] else np.nan,
            "near_tie_boundary_endpoint_fraction": endpoints["near"] / endpoints["all"] if endpoints["all"] else np.nan,
            "boundary_pairs_touching_cell": pairs["all"],
            "exact_tie_boundary_pair_fraction": pairs["tie"] / pairs["all"] if pairs["all"] else np.nan,
            "near_tie_boundary_pair_fraction": pairs["near"] / pairs["all"] if pairs["all"] else np.nan,
            "perturbation": "1e-12 × full daily score SD × fixed BLAKE2b(Code), key SN1-20260928",
        })
        for year in YEARS:
            year_mask = mask & pd.Series(date_values.year == year, index=score.index)
            rows.append({
                "period": str(year), "year": year, "selected_source": source,
                "score_magnitude": magnitude, "vol_quintile": vol_name,
                "stock_days": int(year_mask.sum()),
                "changed_quintile_fraction": float(changed.loc[year_mask].mean()) if year_mask.any() else np.nan,
                "changed_q1_q2_membership_fraction": float(q12.loc[year_mask].mean()) if year_mask.any() else np.nan,
                "changed_q4_q5_membership_fraction": float(q45.loc[year_mask].mean()) if year_mask.any() else np.nan,
                "boundary_endpoints_in_cell": np.nan,
                "tie_boundary_endpoint_fraction": np.nan,
                "near_tie_boundary_endpoint_fraction": np.nan,
                "boundary_pairs_touching_cell": np.nan,
                "exact_tie_boundary_pair_fraction": np.nan,
                "near_tie_boundary_pair_fraction": np.nan,
                "perturbation": "1e-12 × full daily score SD × fixed BLAKE2b(Code), key SN1-20260928",
            })
    result = pd.DataFrame(rows)
    result.to_csv(output / "boundary_sensitivity_matrix.csv", index=False)
    return result


def _age_renewal_matrix(row: pd.DataFrame, target: pd.Series, output: Path) -> pd.DataFrame:
    dates = row.index.get_level_values("Date")
    use = pd.Series(dates.year.isin(YEARS), index=row.index)
    selected = row.loc[use].copy()
    selected["target"] = target.reindex(selected.index)
    selected["gross_long"] = selected.long_gross
    selected["gross_short"] = selected.short_gross
    selected["date"] = selected.index.get_level_values("Date")
    keys = ["selected_source", "score_magnitude", "vol_quintile", "event_age_bucket", "sleeve_age_bucket", "renewal_bucket"]
    grouped = selected.groupby(keys, observed=True, sort=True, dropna=False)
    result = grouped.agg(
        stock_days=("score", "size"),
        active_dates=("date", "nunique"),
        mean_score=("score", "mean"),
        mean_abs_score=("score_abs", "mean"),
        mean_h1_residual_target=("target", "mean"),
        long_membership_share=("portfolio_side", lambda x: float(x.eq("Long").mean())),
        neutral_membership_share=("portfolio_side", lambda x: float(x.eq("Neutral").mean())),
        short_membership_share=("portfolio_side", lambda x: float(x.eq("Short").mean())),
        long_gross_sum=("gross_long", "sum"),
        short_gross_sum=("gross_short", "sum"),
        gross_sum=("gross", "sum"),
    ).reset_index()
    all_dates = _period_dates(row.score, None)
    result["annual_long_gross_contribution"] = result.long_gross_sum * ANNUALIZATION / len(all_dates)
    result["annual_short_gross_contribution"] = result.short_gross_sum * ANNUALIZATION / len(all_dates)
    result["annual_gross_contribution"] = result.gross_sum * ANNUALIZATION / len(all_dates)
    result.drop(columns=["long_gross_sum", "short_gross_sum", "gross_sum"], inplace=True)
    result.to_csv(output / "age_renewal_matrix.csv", index=False)
    return result


def _contrast_table(matrix: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows = []
    complete = matrix.loc[matrix.year.isin(COMPLETE_YEARS)]
    for source in ("High", "Low"):
        for magnitude in MAGNITUDES:
            for metric in ("mean_rankic", "q5_q1_spread"):
                pool = matrix.loc[(matrix.period == "pooled_2011_2016") & matrix.selected_source.eq(source) & matrix.score_magnitude.eq(magnitude)]
                v1 = pool.loc[pool.vol_quintile.eq("V1"), metric]
                v5 = pool.loc[pool.vol_quintile.eq("V5"), metric]
                direction = ("V5>=V1" if magnitude == "Near-zero" else "V1>V5")
                passed = bool(v5.iloc[0] >= v1.iloc[0]) if magnitude == "Near-zero" else bool(v1.iloc[0] > v5.iloc[0])
                yearly_pass = 0
                for year in COMPLETE_YEARS:
                    item = complete.loc[(complete.year == year) & complete.selected_source.eq(source) & complete.score_magnitude.eq(magnitude)]
                    a = item.loc[item.vol_quintile.eq("V1"), metric]
                    b = item.loc[item.vol_quintile.eq("V5"), metric]
                    if len(a) and len(b):
                        yearly_pass += int(bool(b.iloc[0] >= a.iloc[0]) if magnitude == "Near-zero" else bool(a.iloc[0] > b.iloc[0]))
                rows.append({
                    "selected_source": source, "score_magnitude": magnitude,
                    "metric": metric, "pooled_v1": float(v1.iloc[0]), "pooled_v5": float(v5.iloc[0]),
                    "preregistered_direction": direction, "pooled_direction_pass": passed,
                    "complete_year_direction_pass_count": yearly_pass,
                    "complete_years": len(COMPLETE_YEARS),
                })
    contrast = pd.DataFrame(rows)
    # SUPPORT requires one source to satisfy both paired orderings on both
    # metrics, with each ordering recurring in at least three complete years.
    supported_source = None
    for source in ("High", "Low"):
        subset = contrast.loc[contrast.selected_source.eq(source)].set_index(["score_magnitude", "metric"])
        paired = all(bool(subset.loc[(magnitude, metric), "pooled_direction_pass"])
                     and int(subset.loc[(magnitude, metric), "complete_year_direction_pass_count"]) >= 3
                     for magnitude in MAGNITUDES for metric in ("mean_rankic", "q5_q1_spread"))
        if paired:
            supported_source = source
            break
    any_pooled = bool(contrast.pooled_direction_pass.any())
    if supported_source:
        result = "SUPPORT"
    elif any_pooled:
        result = "MIXED"
    else:
        result = "NOT SUPPORTED"
    return contrast, {"result": result, "supporting_source": supported_source,
                      "any_pooled_preregistered_direction": any_pooled,
                      "support_rule": "At least one High/Low source must satisfy Non-near-zero V1>V5 and Near-zero V5>=V1 for pooled RankIC and Q5-Q1, with each of the four directional comparisons holding in at least 3/5 complete years.",
        "candidate_fits": 0, "strategy_changes": 0}


def _saved_account_parity(daily: pd.DataFrame, saved_path: Path) -> dict:
    saved = pd.read_csv(saved_path, parse_dates=["Date"]).set_index("Date").sort_index()
    selected = daily.loc[daily.index.year.isin(YEARS)].reindex(saved.index)
    fields = [name for name in ("gross", "net", "cost", "turnover", "rankic") if name in selected and name in saved]
    differences = {}
    tolerance = 2e-15
    for name in fields:
        left = selected[name].to_numpy(dtype="float64")
        right = saved[name].to_numpy(dtype="float64")
        finite = np.isfinite(left) & np.isfinite(right)
        delta = float(np.max(np.abs(left[finite] - right[finite]))) if finite.any() else 0.0
        if not np.array_equal(np.isnan(left), np.isnan(right)) or delta > tolerance:
            raise AssertionError(f"Official account differs from saved current baseline on {name}: {delta}")
        differences[name] = delta
    return {"status": "PASS", "daily_fields": differences, "numeric_tolerance": tolerance,
            "interpretation": "Baseline score identity is bitwise; serialized daily-account fields are checked at the fixed 2e-15 numeric tolerance."}


def _prefix_invariance(inputs, target, x, score, vol, state, audit_dir: Path):
    dates = score.index.get_level_values("Date")
    rows = []
    for cutoff in CUTOFFS:
        changed_inputs, changed_target, changes = vol_diag._mutate_future(inputs, target, cutoff)
        changed_x = features.build_features(changed_inputs)
        changed_vol = vol_diag._vol20(changed_inputs)
        if not changed_x.index.equals(x.index) or not changed_vol.index.equals(vol.index):
            raise AssertionError(f"Future mutation changed input index at {cutoff}")
        prefix_index = score.index[dates <= pd.Timestamp(cutoff)]
        pd.testing.assert_frame_equal(x.loc[prefix_index], changed_x.loc[prefix_index], check_exact=True, check_dtype=True)
        _exact_series(vol.loc[prefix_index], changed_vol.loc[prefix_index], f"VOL20 prefix {cutoff}")
        predictions, _ = bidirectional.walk_forward_predictions(changed_x, changed_target)
        changed_base = bidirectional.generate_signal(changed_x, predictions, alpha=sn1.HIGH_ALPHA)
        changed_reconstruction = sn1.rebuild_from_base_score(changed_base)
        changed_score = changed_reconstruction["SIDE_SOURCE_SEPARATION"].rename("Return").sort_index()
        _exact_series(score.loc[prefix_index], changed_score.loc[prefix_index], f"SN1_H1 prefix {cutoff}")
        changed_state = _state_frame(changed_score, changed_reconstruction, changed_vol)
        compare_columns = [
            "high_state", "low_state", "d_score", "selected_source", "score_magnitude",
            "vol_quintile", "high_event", "low_event", "latest_event_side",
            "latest_event_age_trading_days", "side_reinforcing_events_last_60",
            "side_reinforcing_event_age_days", "side_reinforcing_event_age_observations",
            "event_age_bucket", "renewal_bucket", "sleeve_age", "sleeve_age_bucket",
            "portfolio_side", "official_quintile", "weight",
        ]
        pd.testing.assert_frame_equal(state.loc[prefix_index, compare_columns], changed_state.loc[prefix_index, compare_columns],
                                      check_exact=True, check_dtype=True)
        if any(item["changed_cells"] <= 0 for item in changes.values()):
            raise AssertionError(f"Future mutation failed to change one or more staged Train sources after {cutoff}")
        rows.append({
            "cutoff": cutoff, "prefix_rows": int(len(prefix_index)), "changed_sources": changes,
            "features_prefix_bitwise_equal": True, "vol20_prefix_bitwise_equal": True,
            "baseline_score_prefix_bitwise_equal": True, "source_state_and_age_prefix_bitwise_equal": True,
        })
        del changed_inputs, changed_target, changed_x, changed_vol, predictions, changed_base, changed_reconstruction, changed_score, changed_state
        gc.collect()
    result = {
        "status": "PASS", "cutoffs": rows,
        "source_mutation": "All five staged Train sources after cutoff mutated using the fixed DM-20261001-02 procedure.",
        "comparison": "Exact index, dtype and values through cutoff for all baseline features, VOL20, SN1_H1, source/state, fixed event/sleeve age and renewal, official membership and weights.",
    }
    _write_json(audit_dir / "prefix_invariance.json", result)
    return result


def _boundary_code_scan() -> dict:
    return vol_diag._source_scan()


def _render_report(result: dict, base_audit: dict, source_audit: dict, prefix: dict,
                   matrix: pd.DataFrame, sides: pd.DataFrame, contrasts: pd.DataFrame,
                   reconciliation: dict, boundary: pd.DataFrame, run_id: str) -> None:
    pooled = matrix.loc[matrix.period.eq("pooled_2011_2016")]
    lines = [
        "# DM-20261001-03: SN1 source × magnitude × VOL20 diagnostic", "",
        "- **Baseline:** `SN1_H1`",
        "- **Trading strategy change:** **None**",
        "- **Fixed diagnostics:** existing selected source; frozen near-zero threshold `1e-12`; existing prior-only residual `VOL20`.",
        "- **Main question:** SN1のvolatility依存性は、sourceとscore magnitudeによって説明できるか？",
        f"- **Result:** **{result['result']}**",
        "- **Strategy candidate:** None. **OOS claim:** None.",
        f"- Run: `{run_id}`. Train development-history evidence only; Valid and raw-target inputs were not opened.", "",
        "## Baseline and audit", "",
        f"Current, independent, saved-current, saved-prior, and selected-source reconstruction paths matched bit for bit over {base_audit['rows']:,} rows. Source precedence audit: **{source_audit['status']}**.",
        f"Future mutation changed all five staged Train inputs after each frozen cutoff and preserved baseline features, VOL20, SN1_H1, source/state, official membership/weights, event/sleeve ages and renewal through cutoff: **{prefix['status']}**.",
        "The combined Train/Valid source-state artifact was not read. High/Low/fallback and fixed age buckets were reconstructed from Train baseline inputs and the existing SN1 contract.",
        "", "## Fixed source × magnitude × volatility matrix", "",
        "Near-zero is `abs(score) < 1e-12`; Non-near-zero is `>= 1e-12`. V1/V5 are endpoints of the exact prior-only residual VOL20 quintiles. Within-cell RankIC and score-ranked Q1–Q5 spreads describe ranking quality inside each fixed cell. P/L, turnover and cost rows are additive accounting attribution under unchanged weights. Turnover entries/exits are assigned to the current signal-date cell, including current neutral rows; these are not counterfactual sub-portfolios.",
        "", "### Pooled High and Low endpoint comparisons", "",
        "| Source | Magnitude | V1 RankIC | V5 RankIC | V1 Q5−Q1 (bp/day) | V5 Q5−Q1 (bp/day) | Annual gross contrib. V1/V5 | Long gross V1/V5 | Short gross V1/V5 |",
        "|:--|:--|--:|--:|--:|--:|:--|:--|:--|",
    ]
    for source in ("High", "Low"):
        for magnitude in MAGNITUDES:
            sub = pooled.loc[pooled.selected_source.eq(source) & pooled.score_magnitude.eq(magnitude)].set_index("vol_quintile")
            ssub = sides.loc[(sides.period == "pooled_2011_2016") & sides.selected_source.eq(source) & sides.score_magnitude.eq(magnitude)]
            side_lookup = ssub.set_index(["side", "vol_quintile"])
            v1, v5 = sub.loc["V1"], sub.loc["V5"]
            lines.append(
                f"| {source} | {magnitude} | {v1.mean_rankic:+.6f} | {v5.mean_rankic:+.6f} | {v1.q5_q1_spread*1e4:+.3f} | {v5.q5_q1_spread*1e4:+.3f} | {v1.annual_gross_contribution:+.3%} / {v5.annual_gross_contribution:+.3%} | {side_lookup.loc[('Long','V1'),'annual_gross_contribution']:+.3%} / {side_lookup.loc[('Long','V5'),'annual_gross_contribution']:+.3%} | {side_lookup.loc[('Short','V1'),'annual_gross_contribution']:+.3%} / {side_lookup.loc[('Short','V5'),'annual_gross_contribution']:+.3%} |"
            )
    lines += ["", "Complete pooled/yearly cells and the requested score, target, membership, weight, contribution, Sharpe, turnover, cost, and Q1–Q5 columns are in [`source_magnitude_vol_matrix.csv`](../../artifacts/" + EXPERIMENT_ID + f"/{run_id}/metrics/source_magnitude_vol_matrix.csv). Annual rows, with 2016 marked partial, are in [`yearly_matrix.csv`](../../artifacts/" + EXPERIMENT_ID + f"/{run_id}/metrics/yearly_matrix.csv). Long/Short detail is in [`side_source_magnitude_vol_attribution.csv`](../../artifacts/" + EXPERIMENT_ID + f"/{run_id}/metrics/side_source_magnitude_vol_attribution.csv).", "", "### Preregistered V1/V5 comparisons", "", "| Source | Magnitude | Metric | V1 | V5 | Direction | Pooled | Years in direction (2011–2015) |", "|:--|:--|:--|--:|--:|:--|:--:|--:|"]
    for r in contrasts.itertuples(index=False):
        scale = 1e4 if r.metric == "q5_q1_spread" else 1.0
        lines.append(f"| {r.selected_source} | {r.score_magnitude} | {r.metric} | {r.pooled_v1*scale:+.6f} | {r.pooled_v5*scale:+.6f} | {r.preregistered_direction} | {r.pooled_direction_pass} | {r.complete_year_direction_pass_count}/5 |")
    lines += ["", "The result rule was fixed before the run. It requires the paired Non-near-zero V1>V5 and Near-zero V5≥V1 ordering on both RankIC and Q5−Q1 for one source, with each direction recurring in at least three complete years. P/L concentration is descriptive evidence, not a rule for changing strategy.", "", "## Boundary sensitivity", "", "The original fixed tiny perturbation is reused without tuning. Source × magnitude × V1/V5 results (changed quintile/Q1-Q2/Q4-Q5 membership, exact/near-tie boundaries) are in [`boundary_sensitivity_matrix.csv`](../../artifacts/" + EXPERIMENT_ID + f"/{run_id}/metrics/boundary_sensitivity_matrix.csv).", "", "## Event age, sleeve age and renewal", "", "Existing fixed buckets are shown in [`age_renewal_matrix.csv`](../../artifacts/" + EXPERIMENT_ID + f"/{run_id}/metrics/age_renewal_matrix.csv). This is a composition description only; no age threshold was introduced.", "", "## Reconciliation and interpretation", "", f"Row-level baseline gross/net/cost/turnover reconciliation passed with maximum absolute daily differences: `{json.dumps(_safe(reconciliation['daily_account_max_abs_difference']), ensure_ascii=False)}`. Matrix gross-weight shares sum to 1 within each year/pooled period, including VOL_MISSING accounting rows.", "", "The evidence is observational attribution within unchanged baseline membership and weights. It does not establish that volatility causes predictive content, that source causes volatility dependence, or that changing cell exposure would improve performance. All dates are already seen Train development history; no independent OOS claim is made.", ""]
    report = ROOT / "reports" / EXPERIMENT_ID / "REPORT.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")


def run(data_dir: Path, output_dir: Path, run_json: Path):
    started = time.monotonic()
    data_dir, output_dir, run_json = Path(data_dir), Path(output_dir), Path(run_json)
    for name in ("audit", "metrics", "predictions"):
        (output_dir / name).mkdir(parents=True, exist_ok=True)
    _update_run(run_json, {"status": "running", "started_at_utc": _now(), "actual_trials": [],
                           "candidate_fits": 0, "max_trials": 1, "valid_evaluation": False})
    try:
        source_scan = _boundary_code_scan()
        _write_json(output_dir / "audit/source_scan.json", source_scan)
        if source_scan["status"] != "PASS":
            raise AssertionError(f"Static source/leak scan failed: {source_scan['findings']}")
        train_paths = sorted(data_dir.glob("*_train.parquet"))
        if {p.name for p in train_paths} != INPUT_NAMES:
            raise AssertionError(f"Unexpected Train-only stage: {sorted(p.name for p in train_paths)}")
        hashes = {p.name: _sha(p) for p in train_paths}
        source_hashes = {path: _sha(ROOT / path) for path in SOURCE_PATHS}
        _update_run(run_json, {
            "command": f".venv/bin/python -m research.experiments.sn1_source_magnitude_volatility --data-dir {data_dir} --output-dir {output_dir} --run-json {run_json}",
            "deadline_seconds": 1800, "code_sha256": source_hashes["research/experiments/sn1_source_magnitude_volatility.py"],
            "source_sha256": source_hashes, "train_data_sha256": hashes,
            "environment": {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__, "pandas": pd.__version__},
        })

        firewall.install(allowed_artifacts=[vol_diag.BASELINE_SAVED, vol_diag.BASELINE_PRIOR])
        if not vol_diag.BASELINE_SAVED.is_file() or not vol_diag.BASELINE_PRIOR.is_file() or not vol_diag.BASELINE_DAILY.is_file():
            raise FileNotFoundError("Required saved current/prior SN1_H1 references are missing")
        inputs = features.load_inputs(data_dir, split="train")
        target = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index().astype("float64")
        saved_current = pd.read_parquet(vol_diag.BASELINE_SAVED)["Return"].sort_index().rename("Return")
        saved_prior = pd.read_parquet(vol_diag.BASELINE_PRIOR)["Return"].sort_index().rename("Return")
        x, score, base_score, reconstructed, base_audit = _baseline_reproduction(inputs, target, saved_current, saved_prior)
        score.to_frame("Return").to_parquet(output_dir / "predictions/SN1_H1.parquet", compression="zstd")
        _write_json(output_dir / "audit/baseline_reproduction.json", base_audit)

        vol = vol_diag._vol20(inputs)
        vol_repeat = vol_diag._vol20(inputs)
        _exact_series(vol, vol_repeat, "deterministic VOL20 replay")
        if not vol.index.equals(score.index) or not target.index.equals(score.index) or not np.isfinite(score.to_numpy()).all():
            raise AssertionError("Baseline/VOL20/Train target index, coverage or finite-value contract failed")
        vol.to_frame("VOL20").to_parquet(output_dir / "predictions/VOL20.parquet", compression="zstd")
        state = _state_frame(score, reconstructed, vol)
        eval_rows = state.index.get_level_values("Date").year.isin(YEARS)
        source_counts = state.loc[eval_rows].groupby(["selected_source", "score_magnitude", "vol_quintile"], observed=True).size().rename("stock_days").reset_index()
        source_counts.to_csv(output_dir / "metrics/source_reconstruction_counts.csv", index=False)
        state_audit = {
            "status": "PASS", "source_precedence": "Low if low_state<0; else High if low_state==0 and high_state>0; else D fallback",
            "baseline_score_reconstruction_bitwise_equal": True,
            "source_derived_from_current_SN1_states_only": True,
            "combined_train_valid_state_artifact_opened": False,
            "valid_rows_in_reconstruction": 0,
            "full_train_rows": int(len(state)),
            "evaluation_rows_2011_2016": int(eval_rows.sum()),
            "evaluation_source_stock_days": {str(k): int(v) for k, v in state.loc[eval_rows, "selected_source"].value_counts().items()},
            "evaluation_magnitude_stock_days": {str(k): int(v) for k, v in state.loc[eval_rows, "score_magnitude"].value_counts().items()},
            "age_buckets": {"event_age": list(EVENT_AGE_BUCKETS), "sleeve_age": list(SLEEVE_AGE_BUCKETS), "renewal": list(RENEWAL_BUCKETS)},
            "age_buckets_reused_without_new_thresholds": True,
        }
        _write_json(output_dir / "audit/source_reconstruction.json", state_audit)
        # Compact Train-only states saved for review; no target column is included.
        state[["score", "high_state", "low_state", "d_score", "selected_source", "score_magnitude",
               "vol20", "vol_quintile", "score_percentile", "weight", "official_quintile",
               "portfolio_side", "high_event", "low_event", "event_age_bucket", "sleeve_age",
               "sleeve_age_bucket", "side_reinforcing_events_last_60", "renewal_bucket"]].to_parquet(
                   output_dir / "predictions/source_state_train.parquet", compression="zstd")

        prefix = _prefix_invariance(inputs, target, x, score, vol, state, output_dir / "audit")
        firewall.save(output_dir / "audit/firewall.json")

        # Recompute cell attributions from the exact unchanged score and target.
        matrix, sides, row, daily, reconciliation = _matrix(state, target, score, output_dir / "metrics")
        saved_account = _saved_account_parity(daily, vol_diag.BASELINE_DAILY)
        _write_json(output_dir / "audit/reconciliation.json", {
            "status": "PASS", "daily_account_max_abs_difference": reconciliation,
            "target_coverage_2011_2016": float(target.loc[target.index.get_level_values("Date").year.isin(YEARS)].notna().mean()),
            "score_coverage_2011_2016": int(score.loc[score.index.get_level_values("Date").year.isin(YEARS)].notna().sum()),
            "VOL_MISSING_rows_retained_for_accounting_reconciliation": int((state.vol_quintile.eq("VOL_MISSING") & state.index.get_level_values("Date").year.isin(YEARS)).sum()),
            "primary_matrix_includes_VOL_MISSING_accounting_row": True,
            "turnover_attribution": "Daily position/sleeve entry and exit turnover, plus related cost, is assigned to the current signal-date source × magnitude × VOL20 cell; rows with missing VOL20 are assigned VOL_MISSING.",
            "gross_weight_share_reconciles_including_VOL_MISSING": True,
            "counterfactual_portfolio": False,
        })
        baseline_daily = daily.loc[daily.index.year.isin(YEARS)]
        baseline_daily.to_csv(output_dir / "metrics/daily_account_SN1_H1.csv", index_label="Date")
        _write_json(output_dir / "audit/coverage_determinism.json", {
            "status": "PASS", "score_rows": int(len(score)), "index_exact": True,
            "score_finite": True, "vol20_deterministic_bitwise": True,
            "target_nonmissing_rows_2011_2016": int(target.loc[target.index.get_level_values("Date").year.isin(YEARS)].notna().sum()),
            "vol20_nonmissing_rows_2011_2016": int(vol.loc[vol.index.get_level_values("Date").year.isin(YEARS)].notna().sum()),
            "official_account_daily_parity_vs_saved_current": saved_account,
        })
        _write_json(output_dir / "audit/saved_account_parity.json", saved_account)

        boundary = _boundary_sensitivity(state, score, output_dir / "metrics")
        age_matrix = _age_renewal_matrix(row, target, output_dir / "metrics")
        contrasts, interpretation = _contrast_table(matrix)
        contrasts.to_csv(output_dir / "metrics/cell_contrasts.csv", index=False)
        _write_json(output_dir / "metrics/interpretation.json", interpretation)
        _render_report(interpretation, base_audit, state_audit, prefix, matrix, sides, contrasts,
                       {"daily_account_max_abs_difference": reconciliation}, boundary, run_json.parent.name)

        # Independent reconciliations: each fixed cell must sum to the base account,
        # and abs-weight shares must cover every active baseline row exactly.
        pooled = matrix.loc[matrix.period.eq("pooled_2011_2016")]
        for metric in ("annual_gross_contribution", "annual_net_contribution", "annual_cost_attribution_official", "average_daily_turnover_attribution"):
            total_cell = float(pooled[metric].sum())
            full_series = {"annual_gross_contribution": daily.gross,
                           "annual_net_contribution": daily.net,
                           "annual_cost_attribution_official": daily.cost,
                           "average_daily_turnover_attribution": daily.turnover}[metric]
            expected = float(full_series.loc[full_series.index.year.isin(YEARS)].mean() * (ANNUALIZATION if metric != "average_daily_turnover_attribution" else 1.0))
            if abs(total_cell - expected) > 2e-12:
                raise AssertionError(f"Cell {metric} does not reconcile: {total_cell} vs {expected}")
        if abs(float(pooled.gross_weight_share.sum()) - 1.0) > 2e-12:
            raise AssertionError("Gross weight share does not sum to 1 across the fixed matrix")
        _write_json(output_dir / "audit/attribution_reconciliation.json", {
            "status": "PASS", "daily_row_reconciliation": reconciliation,
            "pooled_cell_sum_reconciliation": "PASS",
            "pooled_gross_weight_share_sum": float(pooled.gross_weight_share.sum()),
            "side_table_policy": "Long/Short sleeve turnover costs include exits and are attributed to the current signal-date cell, including neutral current membership rows.",
            "age_renewal_rows": int(len(age_matrix)),
            "boundary_rows": int(len(boundary)),
        })
        status = "completed"
        _update_run(run_json, {
            "status": status, "completed_at_utc": _now(), "exit_code": 0,
            "actual_trials": ["SOURCE_MAGNITUDE_VOL20_ATTRIBUTION"], "candidate_fits": 0,
            "result": interpretation["result"], "source_scan_status": source_scan["status"],
            "baseline_reproduction_status": base_audit["status"], "source_reconstruction_status": state_audit["status"],
            "prefix_invariance_status": prefix["status"], "attribution_reconciliation_status": "PASS",
            "valid_evaluation": False, "raw_target_accessed": False,
            "opened_parquets": sorted(firewall.ACCESSES), "elapsed_seconds": time.monotonic() - started,
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
