"""Decompose BOX_BIDIR_STANDALONE EWMA score by originating event age."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research import evaluation, firewall
from stock_comp_2026.strategies.dm_variable_box_breakout import bidirectional, features


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DM-20260925-03"
RUN_ID = "run-20260926T063602Z"
ALPHA = 0.25
ANNUALIZATION = 252
FOLDS = tuple(range(2011, 2017))
AGE_BINS = ("event_day", "age_1_4", "age_5_plus")
SIDE_SPECS = (("long", "high", 1.0), ("short", "low", -1.0))


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def side_impulse(x, predictions, side):
    sign = 1.0 if side == "high" else -1.0
    pred = predictions[side].reindex(x.index)
    active = bidirectional.event_mask(x, side) & pred.notna()
    result = pd.Series(0.0, index=x.index, name=f"{side}_event_impulse")
    if active.any():
        result.loc[active] = sign * bidirectional.active_percentile(pred.loc[active])
    return result


def evaluation_calendar(account_index):
    dates = pd.DatetimeIndex(account_index)
    selected = []
    for year in FOLDS:
        year_dates = dates[dates.year == year].unique().sort_values()
        if len(year_dates) <= 2:
            raise AssertionError(f"Insufficient evaluation dates for {year}")
        selected.extend(year_dates[:-2].tolist())
    return pd.DatetimeIndex(selected).sort_values()


def age_components(raw, side_ewma, groups):
    lagged = {}
    for age in range(5):
        lagged[age] = raw.groupby(groups, sort=False).shift(age).fillna(0.0)
    recent = {
        "event_day": ALPHA * lagged[0],
        "age_1_4": sum(
            ALPHA * (1.0 - ALPHA) ** age * lagged[age]
            for age in range(1, 5)
        ),
    }
    recent_sum = recent["event_day"] + recent["age_1_4"]
    recent["age_5_plus"] = side_ewma - recent_sum
    return recent


def event_counts(raw, groups):
    event = raw.ne(0.0).astype(np.int64)
    lagged = {
        age: event.groupby(groups, sort=False).shift(age).fillna(0).astype(np.int64)
        for age in range(5)
    }
    prior_total = event.groupby(groups, sort=False).cumsum() - event
    return {
        "event_day": lagged[0],
        "age_1_4": sum(lagged[age] for age in range(1, 5)),
        "age_5_plus": prior_total - sum(lagged[age] for age in range(1, 5)),
    }


def build_components(index, x, predictions):
    groups = features.segment_keys(index)
    components = {}
    counts = {}
    side_ewma = {}
    impulses = {}
    for position_side, event_side, sign in SIDE_SPECS:
        raw = side_impulse(x, predictions, event_side).reindex(index).fillna(0.0)
        smooth = bidirectional.smooth_by_listing(raw, alpha=ALPHA).reindex(index)
        impulses[position_side] = raw
        side_ewma[position_side] = smooth
        by_age = age_components(raw, smooth, groups)
        by_count = event_counts(raw, groups)
        for age_bin in AGE_BINS:
            key = (position_side, age_bin)
            components[key] = by_age[age_bin]
            counts[key] = by_count[age_bin]
    return components, counts, side_ewma, impulses


def summarize(signal, target, components, counts, weights, eval_dates, official_daily):
    index = signal.index
    row_dates = index.get_level_values("Date")
    eligible = row_dates.isin(eval_dates) & target.notna().to_numpy()
    score_abs = pd.DataFrame(
        {f"{side}:{age}": components[(side, age)].abs() for side, _event, _sign in SIDE_SPECS for age in AGE_BINS},
        index=index,
    )
    denominator = score_abs.sum(axis=1)
    gross_row = (weights * target).where(target.notna(), 0.0)
    long_row = (weights.clip(lower=0.0) * target).where(target.notna(), 0.0)
    short_row = (weights.clip(upper=0.0) * target).where(target.notna(), 0.0)
    allocation_fraction = score_abs.div(denominator.replace(0.0, np.nan), axis=0).fillna(0.0)

    allocations = {}
    daily_parts = {}
    for side, _event_side, _sign in SIDE_SPECS:
        for age_bin in AGE_BINS:
            key = (side, age_bin)
            column = f"{side}:{age_bin}"
            fraction = allocation_fraction[column]
            allocations[key] = {
                "long": long_row * fraction,
                "short": short_row * fraction,
                "total": gross_row * fraction,
            }
            for actual_side in ("long", "short", "total"):
                pnl = allocations[key][actual_side]
                daily_parts[f"{side}_{age_bin}_{actual_side}"] = pnl.groupby(level="Date").sum()

    no_residual = denominator.eq(0.0)
    daily_parts["no_event_residual_total"] = gross_row.where(no_residual, 0.0).groupby(level="Date").sum()
    daily_parts["no_event_residual_long"] = long_row.where(no_residual, 0.0).groupby(level="Date").sum()
    daily_parts["no_event_residual_short"] = short_row.where(no_residual, 0.0).groupby(level="Date").sum()
    daily = pd.DataFrame(daily_parts).reindex(official_daily.index).fillna(0.0)
    daily["official_gross"] = official_daily["gross"]
    daily["official_long_gross"] = official_daily["long"]
    daily["official_short_gross"] = official_daily["short"]

    pnl_columns = [
        column for column in daily.columns
        if column.endswith("_total") or column.endswith("_long") or column.endswith("_short")
    ]
    age_total_cols = [f"{side}_{age}_total" for side, _event, _sign in SIDE_SPECS for age in AGE_BINS]
    long_total_cols = [f"{side}_{age}_long" for side, _event, _sign in SIDE_SPECS for age in AGE_BINS]
    short_total_cols = [f"{side}_{age}_short" for side, _event, _sign in SIDE_SPECS for age in AGE_BINS]
    total_check = daily[age_total_cols].sum(axis=1) + daily["no_event_residual_total"]
    long_check = daily[long_total_cols].sum(axis=1) + daily["no_event_residual_long"]
    short_check = daily[short_total_cols].sum(axis=1) + daily["no_event_residual_short"]
    errors = {
        "gross": float((total_check - daily["official_gross"]).abs().max()),
        "long": float((long_check - daily["official_long_gross"]).abs().max()),
        "short": float((short_check - daily["official_short_gross"]).abs().max()),
    }
    if max(errors.values()) > 1e-10:
        raise AssertionError(f"Holding contribution allocation failed to reconcile: {errors}")

    target_sign = target.copy()
    rows = []

    def one_group(label, date_mask, fold_dates):
        row_mask = eligible & date_mask
        labeled_rows = int(row_mask.sum())
        period_days = len(fold_dates)
        for side, event_side, direction in SIDE_SPECS:
            for age_bin in AGE_BINS:
                key = (side, age_bin)
                component = components[key]
                active = row_mask & component.ne(0.0).to_numpy()
                active_count = int(active.sum())
                magnitude = component.abs().where(row_mask, 0.0)
                magnitude_sum = float(magnitude.sum())
                aligned = target_sign * direction
                weighted_return = (
                    float((magnitude * aligned).sum()) / magnitude_sum
                    if magnitude_sum > 0 else np.nan
                )
                active_aligned = aligned.loc[active]
                held = allocations[key]
                held_long_sum = float(held["long"].loc[row_mask].sum())
                held_short_sum = float(held["short"].loc[row_mask].sum())
                held_total_sum = float(held["total"].loc[row_mask].sum())
                rows.append({
                    "fold": label,
                    "side": side,
                    "event_side": event_side,
                    "age_bin": age_bin,
                    "evaluation_days": period_days,
                    "labeled_stock_days": labeled_rows,
                    "component_stock_days": active_count,
                    "event_residual_instances": int(counts[key].where(row_mask, 0).sum()),
                    "direction_aligned_o2o_weighted_mean": weighted_return,
                    "direction_aligned_o2o_active_mean": float(active_aligned.mean()) if active_count else np.nan,
                    "score_residual_abs_sum": magnitude_sum,
                    "score_residual_abs_mean_active": magnitude_sum / active_count if active_count else np.nan,
                    "score_residual_abs_mean_all_labeled": magnitude_sum / labeled_rows if labeled_rows else np.nan,
                    "held_long_gross_contribution_sum": held_long_sum,
                    "held_short_gross_contribution_sum": held_short_sum,
                    "held_gross_contribution_sum": held_total_sum,
                    "held_long_gross_contribution_annualized": held_long_sum / period_days * ANNUALIZATION if period_days else np.nan,
                    "held_short_gross_contribution_annualized": held_short_sum / period_days * ANNUALIZATION if period_days else np.nan,
                    "held_gross_contribution_annualized": held_total_sum / period_days * ANNUALIZATION if period_days else np.nan,
                })

    pooled_dates = pd.DatetimeIndex(eval_dates)
    one_group("pooled", row_dates.isin(pooled_dates), pooled_dates)
    for year in FOLDS:
        fold_dates = pd.DatetimeIndex(eval_dates[eval_dates.year == year])
        one_group(str(year), row_dates.year == year, fold_dates)

    no_residual_rows = []
    for label in ("pooled", *(str(year) for year in FOLDS)):
        fold_dates = pooled_dates if label == "pooled" else pd.DatetimeIndex(eval_dates[eval_dates.year == int(label)])
        row_mask = eligible & (row_dates.isin(fold_dates))
        period_days = len(fold_dates)
        for actual_side in ("long", "short", "total"):
            pnl = gross_row if actual_side == "total" else long_row if actual_side == "long" else short_row
            pnl_sum = float(pnl.where(row_mask & no_residual, 0.0).sum())
            no_residual_rows.append({
                "fold": label,
                "actual_side": actual_side,
                "gross_contribution_sum": pnl_sum,
                "gross_contribution_annualized": pnl_sum / period_days * ANNUALIZATION if period_days else np.nan,
            })

    daily = daily.loc[eval_dates]
    return pd.DataFrame(rows), pd.DataFrame(no_residual_rows), daily, errors


def fmt_bp(value):
    return "—" if not np.isfinite(value) else f"{value * 10000:+.2f} bp"


def build_table(frame, fold=None):
    if fold is not None:
        frame = frame.loc[frame["fold"] == str(fold)]
    lines = [
        "| Fold | Side | Event age | Stock-days | Residual instances | Residual score total | Mean residual score | Direction-aligned O2O (score-weighted) | Held gross contribution (annualized) |",
        "|:---|:---|:---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in frame.iterrows():
        lines.append(
            f"| {row['fold']} | {row['side'].title()} | {row['age_bin']} | "
            f"{int(row['component_stock_days']):,} | {int(row['event_residual_instances']):,} | "
            f"{row['score_residual_abs_sum']:.2f} | "
            f"{row['score_residual_abs_mean_active']:.6f} | "
            f"{fmt_bp(row['direction_aligned_o2o_weighted_mean'])} | "
            f"{row['held_gross_contribution_annualized']:+.2%} |"
        )
    return "\n".join(lines)


def run(score_path, output_dir):
    score_path = Path(score_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = ROOT / "stock_comp_2026" / "input"
    firewall.install(allowed_artifacts=[score_path])

    saved = pd.read_parquet(score_path)
    signal = saved[bidirectional.TRIAL_ID].sort_index().astype(float)
    target = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index()
    if not signal.index.equals(target.index):
        raise AssertionError("Saved standalone score and Train target indexes differ")

    # Recreate the fixed, already evaluated annual expanding models to recover
    # event impulses on the two purged signal dates, omitted from saved event rows.
    inputs = features.load_inputs(data_dir, split="train")
    x = features.build_features(inputs)
    if not x.index.equals(signal.index):
        raise AssertionError("Rebuilt Train features and saved signal indexes differ")
    predictions, _training_records = bidirectional.walk_forward_predictions(
        x, target, years=FOLDS, model_dir=None
    )
    components, counts, side_ewma, impulses = build_components(signal.index, x, predictions)
    reconstructed = side_ewma["long"] + side_ewma["short"]
    reconstruction_error = float((reconstructed - signal).abs().max())
    if reconstruction_error > 1e-12:
        raise AssertionError(f"Rebuilt event impulses do not reproduce saved EWMA score: {reconstruction_error}")
    component_sum = sum(components.values())
    component_error = float((component_sum - signal).abs().max())
    if component_error > 1e-12:
        raise AssertionError(f"Age components do not sum to saved score: {component_error}")

    official_daily = evaluation.daily_account(signal, target)
    eval_dates = evaluation_calendar(official_daily.index)
    portfolio_weight, _quintile = evaluation.weights(signal)
    fold_summary, no_residual, daily, holding_errors = summarize(
        signal, target, components, counts, portfolio_weight, eval_dates, official_daily
    )
    pooled = fold_summary.loc[fold_summary["fold"] == "pooled"].copy()
    by_fold = fold_summary.loc[fold_summary["fold"] != "pooled"].copy()
    pooled.to_csv(output_dir / "ewma_event_age_pooled.csv", index=False)
    by_fold.to_csv(output_dir / "ewma_event_age_by_fold.csv", index=False)
    no_residual.to_csv(output_dir / "ewma_event_age_no_residual_holdings.csv", index=False)
    daily.to_csv(output_dir / "ewma_event_age_daily.csv", index_label="Date")
    firewall.save(output_dir / "ewma_event_age_firewall.json")

    main_table = build_table(pooled)
    fold_table = build_table(by_fold)
    no_residual_pooled = no_residual.loc[no_residual["fold"] == "pooled"]
    no_residual_text = "; ".join(
        f"{row.actual_side.title()} {row.gross_contribution_annualized:+.2%}"
        for row in no_residual_pooled.itertuples(index=False)
    )
    section = "\n".join([
        "## EWMAに残るイベント年齢成分", "",
        "対象は保存済み `BOX_BIDIR_STANDALONE` のTrainスコア。イベント当日の成分は "
        "`alpha × raw_event_score`、年齢k日の成分は `alpha × (1-alpha)^k × raw_event_score[t-k]` "
        "（alpha=0.25）として、高値イベント由来Longと安値イベント由来Shortに分けた。",
        "各年の最後2シグナル日を除外する既存fold定義を使用。purge日のイベントも翌foldへ残るEWMAに含めるため、"
        "保存済みTrain feature/targetから固定済みannual expandingモデルを再現し、保存scoreとの一致を監査した。", "",
        "公式O2Oはsignal dateの市場残差target。方向整合は高値/Longを+、安値/Shortを−として算出。"
        "表示リターンは残存score絶対値で加重した平均。Residual instancesはイベント起点×評価signal-dateの組数、"
        "Stock-daysは残存成分のある銘柄日数。どちらも独立標本数ではない。", "",
        main_table, "",
        "### Fold別", "", fold_table, "",
        "### 保有寄与の定義", "",
        "公式5分位weightは全EWMAスコアからそのまま計算。各日の実際のLong/Short gross P/Lを、"
        "6つのside×age成分の絶対残存score比で配分し、残存成分がないweightは別枠にした。"
        "これは加算可能な記述的帰属で、age別に独立して売買した成績ではない。コストはage別に配賦していない。", "",
        f"残存成分なしの保有寄与（年率Gross）は {no_residual_text}。"
        f"保存score再構成誤差={reconstruction_error:.3g}、age成分合計誤差={component_error:.3g}、"
        f"保有P/L照合誤差（Long/Short/Gross）={holding_errors['long']:.3g}/{holding_errors['short']:.3g}/{holding_errors['gross']:.3g}。", "",
        "出力: `ewma_event_age_pooled.csv`, `ewma_event_age_by_fold.csv`, "
        "`ewma_event_age_no_residual_holdings.csv`, `ewma_event_age_daily.csv`."
    ])
    report_path = ROOT / "reports" / EXPERIMENT_ID / "REPORT.md"
    text = report_path.read_text(encoding="utf-8")
    start = "## EWMAに残るイベント年齢成分\n"
    end = "## 監査・制約\n"
    if start in text:
        prefix, rest = text.split(start, 1)
        if end not in rest:
            raise ValueError("Cannot find report insertion boundary")
        _, suffix = rest.split(end, 1)
        text = prefix + section + "\n\n" + end + suffix
    elif end in text:
        prefix, suffix = text.split(end, 1)
        text = prefix + section + "\n\n" + end + suffix
    else:
        raise ValueError("Cannot find report insertion boundary")
    report_path.write_text(text, encoding="utf-8")

    metadata = {
        "experiment_id": EXPERIMENT_ID,
        "source_run_id": RUN_ID,
        "score_path": str(score_path.relative_to(ROOT)),
        "score_sha256": digest(score_path),
        "evaluation_span": [str(eval_dates.min().date()), str(eval_dates.max().date())],
        "evaluation_days": int(len(eval_dates)),
        "alpha": ALPHA,
        "age_bins_trading_rows": {"event_day": [0, 0], "age_1_4": [1, 4], "age_5_plus": [5, None]},
        "holding_pnl_allocation": "actual full-score long/short gross PnL allocated by absolute component-score share; zero-residual holdings separate",
        "score_reconstruction_max_abs_error": reconstruction_error,
        "age_component_sum_max_abs_error": component_error,
        "holding_contribution_reconciliation_max_abs_error": holding_errors,
        "valid_accessed": False,
        "source_script_sha256": digest(Path(__file__)),
    }
    (output_dir / "ewma_event_age_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Updated {report_path}")
    print(main_table)
    print(f"Score reconstruction max error={reconstruction_error:.3g}; holding reconciliation={holding_errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scores",
        default="artifacts/DM-20260925-03/run-20260926T063602Z/predictions/signals.parquet",
    )
    parser.add_argument("--output-dir", default="reports/DM-20260925-03")
    args = parser.parse_args()
    run(args.scores, args.output_dir)
