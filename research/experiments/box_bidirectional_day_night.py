"""Attribute the standalone BOX score into Long/Short x day/night Train P/L."""
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
ONE_WAY_COST = 0.001
ANNUALIZATION = 252
SIDES = ("long", "short")
SESSIONS = ("day", "night")


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def future_index(index, calendar, offset):
    dates = index.get_level_values("Date")
    codes = index.get_level_values("Code")
    positions = pd.Series(np.arange(len(calendar)), index=calendar).reindex(dates).to_numpy()
    shifted = pd.DatetimeIndex([
        calendar[position + offset] if position + offset < len(calendar) else pd.NaT
        for position in positions
    ])
    return pd.MultiIndex.from_arrays([shifted, codes], names=index.names), shifted


def evaluation_dates(account_index):
    dates = pd.DatetimeIndex(account_index)
    selected = []
    for year in range(2011, 2017):
        year_dates = dates[dates.year == year].unique().sort_values()
        if len(year_dates) <= 2:
            raise AssertionError(f"Insufficient evaluation dates for {year}")
        selected.extend(year_dates[:-2].tolist())
    return pd.DatetimeIndex(selected).sort_values()


def sharpe(values):
    values = pd.Series(values, dtype=float).dropna()
    if len(values) < 2:
        return np.nan
    std = values.std(ddof=1)
    return float(values.mean() / std * np.sqrt(ANNUALIZATION)) if std > 0 else np.nan


def metric_row(daily, side, session, year="pooled"):
    selected = daily
    if year != "pooled":
        selected = daily.loc[daily.index.year == int(year)]
    gross = selected[f"{side}_{session}_gross"]
    cost = selected[f"{side}_{session}_cost"]
    net = selected[f"{side}_{session}_net"]
    return {
        "period": year,
        "side": side,
        "session": session,
        "days": int(net.notna().sum()),
        "mean_daily_gross": float(gross.mean()),
        "annual_gross": float(gross.mean() * ANNUALIZATION),
        "annual_cost": float(cost.mean() * ANNUALIZATION),
        "mean_daily_net": float(net.mean()),
        "annual_net": float(net.mean() * ANNUALIZATION),
        "net_sharpe": sharpe(net),
        "period_net": float(net.sum()),
    }


def calculate(signal, target, prices, raw_returns, beta, topix):
    signal = signal.reindex(target.index).sort_index()
    target = target.reindex(signal.index).sort_index()
    if not signal.index.equals(target.index):
        raise AssertionError("Score and Train target index mismatch")

    dates = pd.DatetimeIndex(target.index.get_level_values("Date").unique()).sort_values()
    entry_index, entry_dates = future_index(target.index, dates, 1)
    exit_index, exit_dates = future_index(target.index, dates, 2)
    open_entry = pd.to_numeric(prices["Open"].reindex(entry_index), errors="coerce").to_numpy()
    close_entry = pd.to_numeric(prices["Close"].reindex(entry_index), errors="coerce").to_numpy()
    raw_o2o = pd.to_numeric(raw_returns["Return"].reindex(exit_index), errors="coerce").to_numpy()
    beta_exit = pd.to_numeric(beta["Return"].reindex(exit_index), errors="coerce").to_numpy()
    topix_exit = pd.to_numeric(topix["Return"].reindex(exit_dates), errors="coerce").to_numpy()
    official = target.to_numpy(dtype=float)

    raw_day = close_entry / open_entry - 1.0
    raw_night = (1.0 + raw_o2o) / (1.0 + raw_day) - 1.0
    market_adjustment = beta_exit * topix_exit
    reconstructed = raw_o2o - market_adjustment
    valid_target = np.isfinite(official)
    if not valid_target.any():
        raise AssertionError("No observed Train labels")
    official_daily = evaluation.daily_account(signal, target)
    eval_dates = evaluation_dates(official_daily.index)
    on_evaluation_date = target.index.get_level_values("Date").isin(eval_dates)
    eval_label = valid_target & on_evaluation_date
    unaligned = eval_label & ~np.isfinite(reconstructed)
    if unaligned.any():
        raise AssertionError(f"{int(unaligned.sum())} evaluation labels lack a finite raw O2O reconstruction")
    residual_error = np.abs(reconstructed[eval_label] - official[eval_label])
    max_residual_error = float(residual_error.max())
    if max_residual_error > 1e-12:
        raise AssertionError(f"Official target reconstruction mismatch: {max_residual_error}")

    cross_term = raw_day * raw_night
    base_component = {
        "day": raw_day + 0.5 * cross_term,
        "night": raw_night + 0.5 * cross_term,
    }
    for session in SESSIONS:
        base_component[session] = pd.Series(base_component[session], index=target.index)
    adjustment = pd.Series(market_adjustment, index=target.index)

    portfolio_weight, _ = evaluation.weights(signal)
    side_weight = {
        "long": portfolio_weight.clip(lower=0.0),
        "short": portfolio_weight.clip(upper=0.0),
    }
    side_turnover = {}
    side_cost = {}
    for side, weights in side_weight.items():
        turnover = weights.groupby(level="Code", sort=False).diff().abs().fillna(weights.abs())
        side_turnover[side] = turnover.groupby(level="Date").sum().reindex(dates).fillna(0.0)
        side_cost[side] = (
            (ONE_WAY_COST * turnover).where(target.notna(), 0.0)
            .groupby(level="Date").sum().reindex(dates).fillna(0.0)
        )

    component_returns = {}

    def build_for_adjustment(day_adjustment_share):
        components = {}
        day_return = pd.Series(
            base_component["day"].to_numpy() - day_adjustment_share * adjustment.to_numpy(),
            index=target.index,
        )
        night_return = pd.Series(
            base_component["night"].to_numpy() - (1.0 - day_adjustment_share) * adjustment.to_numpy(),
            index=target.index,
        )
        for side in SIDES:
            weights = side_weight[side]
            for session, returns in (("day", day_return), ("night", night_return)):
                gross = (weights * returns).groupby(level="Date").sum().reindex(dates).fillna(0.0)
                # Match official accounting: cost is dropped on each missing-target stock row.
                half_cost = side_cost[side] * 0.5
                components[f"{side}_{session}_gross"] = gross
                components[f"{side}_{session}_cost"] = half_cost
                components[f"{side}_{session}_net"] = gross - half_cost
        return pd.DataFrame(components).loc[eval_dates]

    # Primary attribution divides the market adjustment evenly across sessions.
    daily = build_for_adjustment(0.5)
    official_net = official_daily["net"].reindex(eval_dates)
    attributed_net = daily[[f"{s}_{q}_net" for s in SIDES for q in SESSIONS]].sum(axis=1)
    reconciliation = (attributed_net - official_net).abs()
    max_reconciliation_error = float(reconciliation.max())
    if max_reconciliation_error > 1e-10:
        attributed_gross = daily[[f"{s}_{q}_gross" for s in SIDES for q in SESSIONS]].sum(axis=1)
        attributed_cost = daily[[f"{s}_{q}_cost" for s in SIDES for q in SESSIONS]].sum(axis=1)
        gross_error = (attributed_gross - official_daily["gross"].reindex(eval_dates)).abs()
        cost_error = (attributed_cost - official_daily["cost"].reindex(eval_dates)).abs()
        turnover_gap = (
            side_turnover["long"] + side_turnover["short"]
            - official_daily["turnover"].reindex(dates)
        ).abs().loc[eval_dates]
        raise AssertionError(
            "Four-cell attribution does not reconcile: "
            f"net={max_reconciliation_error}, gross={float(gross_error.max())}, "
            f"cost={float(cost_error.max())}, turnover={float(turnover_gap.max())}, "
            f"bad day={str(reconciliation.idxmax().date())}"
        )

    pooled = [metric_row(daily, side, session) for side in SIDES for session in SESSIONS]
    annual = [
        metric_row(daily, side, session, year)
        for year in range(2011, 2017) for side in SIDES for session in SESSIONS
    ]
    sensitivity = []
    for share in (0.0, 0.5, 1.0):
        sens_daily = build_for_adjustment(share)
        for side in SIDES:
            for session in SESSIONS:
                row = metric_row(sens_daily, side, session)
                row["day_market_adjustment_share"] = share
                sensitivity.append(row)

    # Summed contribution over the four cells must reproduce the strategy's official total.
    for column in ("gross", "net", "cost"):
        key = f"{column}"
        if column == "gross":
            attributed = daily[[f"{s}_{q}_gross" for s in SIDES for q in SESSIONS]].sum(axis=1)
        elif column == "cost":
            attributed = daily[[f"{s}_{q}_cost" for s in SIDES for q in SESSIONS]].sum(axis=1)
        else:
            attributed = attributed_net
        official = official_daily[key].reindex(eval_dates)
        error = (attributed - official).abs()
        if float(error.max()) > 1e-10:
            raise AssertionError(f"Four-cell {column} does not reconcile: {float(error.max())}")

    return {
        "daily": daily,
        "pooled": pd.DataFrame(pooled),
        "annual": pd.DataFrame(annual),
        "sensitivity": pd.DataFrame(sensitivity),
        "evaluation_dates": eval_dates,
        "max_target_reconstruction_error": max_residual_error,
        "max_four_cell_reconciliation_error": max_reconciliation_error,
        "official_daily": official_daily.loc[eval_dates],
    }


def render_table(frame, columns, headers, row_labels=None):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join([":---"] * len(headers)) + "|"]
    for _, row in frame.iterrows():
        values = []
        for column, formatter in columns:
            values.append(formatter(row[column]))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def run(score_path, output_dir):
    score_path = Path(score_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = ROOT / "stock_comp_2026" / "input"
    allowed = [score_path]
    firewall.install(allowed_artifacts=allowed)

    saved = pd.read_parquet(score_path)
    if bidirectional.TRIAL_ID not in saved:
        raise ValueError(f"Missing {bidirectional.TRIAL_ID} in {score_path}")
    signal = saved[bidirectional.TRIAL_ID].sort_index()
    target = pd.read_parquet(data_dir / "target_1day_train.parquet")["Return"].sort_index()
    if not signal.index.equals(target.index):
        raise AssertionError("Saved standalone score and Train target indexes differ")
    prices = pd.read_parquet(
        data_dir / "prices_daily_quotes_train.parquet", columns=["Open", "Close"]
    ).sort_index()
    raw_returns = pd.read_parquet(data_dir / "raw_return_1day_train.parquet", columns=["Return"]).sort_index()
    beta = pd.read_parquet(data_dir / "beta_1day_train.parquet", columns=["Return"]).sort_index()
    topix = pd.read_parquet(data_dir / "topix_return_1day_train.parquet", columns=["Return"]).sort_index()

    result = calculate(signal, target, prices, raw_returns, beta, topix)
    result["pooled"].to_csv(output_dir / "ls_day_night_pooled.csv", index=False)
    result["annual"].to_csv(output_dir / "ls_day_night_by_year.csv", index=False)
    result["sensitivity"].to_csv(output_dir / "ls_day_night_market_adjustment_sensitivity.csv", index=False)
    result["daily"].to_csv(output_dir / "ls_day_night_daily.csv", index_label="Date")
    firewall.save(output_dir / "ls_day_night_firewall.json")

    pooled = result["pooled"].copy()
    pooled["cell"] = pooled["side"].str.title() + " × " + pooled["session"].str.title()
    pooled_table = render_table(
        pooled,
        [("cell", str), ("annual_gross", lambda x: f"{x:+.2%}"),
         ("annual_cost", lambda x: f"{x:.2%}"), ("annual_net", lambda x: f"{x:+.2%}"),
         ("net_sharpe", lambda x: "—" if not np.isfinite(x) else f"{x:+.3f}"),
         ("mean_daily_net", lambda x: f"{x*10000:+.3f} bp")],
        ["区分", "年率Gross寄与", "年率Cost配賦", "年率Net寄与", "単体Net Sharpe", "日次Net平均"],
    )

    annual = result["annual"].copy()
    annual["cell"] = annual["side"].str.title() + " × " + annual["session"].str.title()
    annual_table = render_table(
        annual,
        [("period", str), ("cell", str), ("annual_net", lambda x: f"{x:+.2%}"),
         ("net_sharpe", lambda x: "—" if not np.isfinite(x) else f"{x:+.3f}")],
        ["年", "区分", "年率Net寄与", "単体Net Sharpe"],
    )

    sensitivity = result["sensitivity"].copy()
    sensitivity = sensitivity.loc[
        (sensitivity["side"] == "short") & (sensitivity["session"] == "night")
    ].sort_values("day_market_adjustment_share")
    sensitivity_table = render_table(
        sensitivity,
        [("day_market_adjustment_share", lambda x: f"{x:.0%}"),
         ("annual_net", lambda x: f"{x:+.2%}"),
         ("net_sharpe", lambda x: "—" if not np.isfinite(x) else f"{x:+.3f}")],
        ["TOPIX調整の昼配分", "Short × 夜 年率Net", "単体Net Sharpe"],
    )

    period = result["evaluation_dates"]
    official = result["official_daily"]
    candidate_metrics = evaluation.metrics(official)
    section = "\n".join([
        "## L/S × 昼夜の2×2収益帰属", "",
        f"対象は `{bidirectional.TRIAL_ID}` の保存済みTrainスコア。評価期間は{period.min().date()}〜{period.max().date()}、"
        f"{len(period):,}営業日（各年の最後2シグナル日を除外）。売買weightは公式5分位、片道costは0.1%。", "",
        "昼は t+1 Open→t+1 Close、夜は t+1 Close→t+2 Open。raw O2Oリターンを昼・夜に分解し、"
        "複利交差項と `beta[t+2] × TOPIX[t+2]` 調整をそれぞれ半分ずつ配分した。"
        "CostはLong/Short別turnoverから計上し、昼夜に半分ずつ配賦。", "",
        pooled_table, "",
        f"4セルのNet日次損益合計は公式Netに一致（最大誤差 {result['max_four_cell_reconciliation_error']:.3g}）。"
        f"公式全体は年率Net {candidate_metrics['annual_net']:+.2%}、Net Sharpe {candidate_metrics['net_sharpe']:.3f}。"
        "各セルのSharpeはそのセルの日次寄与を単独系列として年率化した値で、セル間で加算できない。", "",
        "### 年別", "", annual_table, "",
        "### TOPIX調整配分感度: Short × 夜", "",
        "昼夜別の市場残差内訳は提供されないため、TOPIX調整を昼へ0%/50%/100%配分した感度を併記。"
        "4セル合計は各ケースで公式Netに一致する。", "", sensitivity_table, "",
        "この分解はコスト・市場調整の帰属ルールに依存する記述診断であり、"
        "各時間帯を独立して実際に売買したNet Sharpeや因果的な昼夜アルファではない。", "",
        "再現出力: `ls_day_night_pooled.csv`, `ls_day_night_by_year.csv`, "
        "`ls_day_night_market_adjustment_sensitivity.csv`, `ls_day_night_daily.csv`."
    ])
    report_path = ROOT / "reports" / EXPERIMENT_ID / "REPORT.md"
    text = report_path.read_text(encoding="utf-8")
    start = "## L/S × 昼夜の2×2収益帰属\n"
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
        "evaluation_span": [str(period.min().date()), str(period.max().date())],
        "evaluation_days": len(period),
        "metric_definition": {
            "day": "t+1 Open to t+1 Close",
            "night": "t+1 Close to t+2 Open",
            "raw_o2o_date": "signal date t+2",
            "market_adjustment": "beta[t+2] * TOPIX[t+2]; 50% assigned to each session in primary attribution",
            "cross_term": "raw_day * raw_night; 50% assigned to each session",
            "transaction_cost": "0.001 * side turnover; 50% assigned to each session",
        },
        "official_target_reconstruction_max_abs_error": result["max_target_reconstruction_error"],
        "four_cell_net_reconciliation_max_abs_error": result["max_four_cell_reconciliation_error"],
        "valid_accessed": False,
        "source_script_sha256": digest(Path(__file__)),
    }
    nonfinite_metadata = [
        key for key, value in metadata.items()
        if isinstance(value, (float, np.floating)) and not np.isfinite(value)
    ]
    if nonfinite_metadata:
        raise AssertionError(f"Unexpected nonfinite audit metadata: {nonfinite_metadata}")
    (output_dir / "ls_day_night_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Updated {report_path}")
    print(pooled_table)
    print(f"Official annual net={candidate_metrics['annual_net']:+.4%}; max reconciliation={result['max_four_cell_reconciliation_error']:.3g}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores", default="artifacts/DM-20260925-03/run-20260926T063602Z/predictions/signals.parquet")
    parser.add_argument("--output-dir", default="reports/DM-20260925-03")
    args = parser.parse_args()
    run(args.scores, args.output_dir)
