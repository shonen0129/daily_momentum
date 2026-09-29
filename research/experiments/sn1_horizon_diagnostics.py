"""Post-fit holding persistence, turnover, concentration and attribution diagnostics."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research import evaluation


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "artifacts/DM-20260927-04/run-20260927T101500Z"
HORIZONS = (1, 5, 20)
SPLITS = ("train", "historical_valid")
YEARS = tuple(range(2011, 2017))


def read_panel(path, value_columns):
    frame = pd.read_parquet(path, columns=value_columns)
    if not isinstance(frame.index, pd.MultiIndex) or list(frame.index.names) != ["Date", "Code"]:
        if "Date" in frame.columns and "Code" in frame.columns:
            frame = frame.set_index(["Date", "Code"])
        else:
            raise ValueError(f"Expected a (Date, Code) index in {path}")
    frame.index = pd.MultiIndex.from_arrays(
        [pd.DatetimeIndex(frame.index.get_level_values("Date")),
         frame.index.get_level_values("Code").astype(str)],
        names=["Date", "Code"],
    )
    return frame.sort_index()


def score_decay(score, lags=(1, 5, 20, 40)):
    wide = score.unstack("Code").sort_index()
    base = wide.to_numpy(dtype="float64", copy=True)
    rows = []
    for lag in lags:
        future = wide.shift(-lag).to_numpy(dtype="float64", copy=False)
        ok = np.isfinite(base) & np.isfinite(future)
        a, b = base[ok], future[ok]
        rank_a = pd.Series(a).rank(method="average").to_numpy()
        rank_b = pd.Series(b).rank(method="average").to_numpy()
        pearson = float(np.corrcoef(a, b)[0, 1]) if len(a) > 2 else np.nan
        spearman_flat = float(np.corrcoef(rank_a, rank_b)[0, 1]) if len(a) > 2 else np.nan
        nonzero = ok & (base != 0.0)
        abs_base = np.abs(a)
        abs_future = np.abs(b)
        both_nonzero = nonzero & (future != 0.0)
        sign_flip = np.sign(base[both_nonzero]) != np.sign(future[both_nonzero])
        daily_corr = []
        for i in range(max(0, len(wide.index) - lag)):
            x, y = base[i], base[i + lag]
            pair = np.isfinite(x) & np.isfinite(y)
            if pair.sum() > 2:
                rx, ry = pd.Series(x[pair]).rank().to_numpy(), pd.Series(y[pair]).rank().to_numpy()
                if np.std(rx) > 0 and np.std(ry) > 0:
                    daily_corr.append(float(np.corrcoef(rx, ry)[0, 1]))
        rows.append({
            "lag_trading_days": lag,
            "score_pearson_flat": pearson,
            "score_spearman_flat": spearman_flat,
            "mean_daily_cross_sectional_rank_corr": float(np.mean(daily_corr)) if daily_corr else np.nan,
            "mean_abs_score_now": float(np.mean(abs_base)) if len(abs_base) else np.nan,
            "mean_abs_score_future": float(np.mean(abs_future)) if len(abs_future) else np.nan,
            "mean_abs_score_change": float(np.mean(np.abs(b - a))) if len(a) else np.nan,
            "ratio_of_mean_abs_future_to_now": float(np.mean(abs_future) / np.mean(abs_base)) if len(abs_base) and np.mean(abs_base) > 0 else np.nan,
            "nonzero_sign_flip_rate": float(np.mean(sign_flip)) if len(sign_flip) else np.nan,
            "matched_stock_days": int(ok.sum()),
            "nonzero_stock_days": int(nonzero.sum()),
        })
    return pd.DataFrame(rows)


def spell_age(quintile):
    dates = pd.DatetimeIndex(quintile.index.get_level_values("Date").unique().sort_values())
    ordinal = pd.Series(dates.get_indexer(quintile.index.get_level_values("Date")), index=quintile.index)
    side = pd.Series(np.where(quintile >= 3, 1, np.where(quintile <= 1, -1, 0)), index=quintile.index)
    frame = pd.DataFrame({"ordinal": ordinal, "side": side}, index=quintile.index)
    frame["code"] = frame.index.get_level_values("Code")
    frame = frame.sort_index(level=[1, 0])
    previous_date = frame.groupby("code", sort=False)["ordinal"].shift(1)
    previous_side = frame.groupby("code", sort=False)["side"].shift(1)
    continues = frame.side.eq(previous_side) & frame.ordinal.sub(previous_date).eq(1)
    start = ~continues
    frame["age"] = start.groupby(frame.code, sort=False).cumsum()
    frame.loc[frame.side.eq(0), "age"] = 0
    # Convert per-code spell id to current spell length.
    length = frame.groupby(["code", "side", "age"], sort=False).cumcount() + 1
    frame["spell_age"] = length.where(frame.side.ne(0), 0)
    frame = frame.sort_index()
    return frame["side"], frame["spell_age"]


def daily_turnover_counts(signal, quintile, weights):
    dates = pd.DatetimeIndex(signal.index.get_level_values("Date").unique().sort_values())
    rows = []
    for old_date, new_date in zip(dates[:-1], dates[1:]):
        old = quintile.xs(old_date, level="Date")
        new = quintile.xs(new_date, level="Date")
        common = old.index.intersection(new.index)
        a = old.reindex(common).to_numpy(dtype=int)
        b = new.reindex(common).to_numpy(dtype=int)
        record = {"date": new_date, "common_codes": len(common)}
        for q, name in ((0, "q1"), (1, "q2"), (3, "q4"), (4, "q5")):
            old_member, new_member = a == q, b == q
            record[f"{name}_entrants"] = int(np.sum(~old_member & new_member))
            record[f"{name}_exits"] = int(np.sum(old_member & ~new_member))
        record["long_entrants"] = int(np.sum((a < 3) & (b >= 3)))
        record["long_exits"] = int(np.sum((a >= 3) & (b < 3)))
        record["short_entrants"] = int(np.sum((a > 1) & (b <= 1)))
        record["short_exits"] = int(np.sum((a <= 1) & (b > 1)))
        rows.append(record)
    return pd.DataFrame(rows)


def concentration_by_category(frame, category):
    valid = frame.loc[frame[category].notna() & frame.abs_weight.gt(0.0)]
    if valid.empty:
        return pd.DataFrame(columns=["Date", "side", "hhi", "max_category_share", "missing_weight_share"])
    grouped = valid.groupby(["Date", "side", category], observed=True).abs_weight.sum().rename("weight").reset_index()
    total = grouped.groupby(["Date", "side"], observed=True).weight.transform("sum")
    grouped["share"] = grouped.weight / total
    result = grouped.groupby(["Date", "side"], observed=True).agg(
        hhi=("share", lambda x: float(np.square(x).sum())),
        max_category_share=("share", "max"),
    ).reset_index()
    all_weight = frame.loc[frame.abs_weight.gt(0.0)].groupby(["Date", "side"], observed=True).abs_weight.sum()
    known_weight = valid.groupby(["Date", "side"], observed=True).abs_weight.sum()
    missing_share = 1.0 - known_weight.div(all_weight).fillna(0.0)
    result["missing_weight_share"] = [float(missing_share.get((d, s), 1.0)) for d, s in zip(result.Date, result.side)]
    return result


def main():
    data_dir = ROOT / "stock_comp_2026/input"
    concentration, attribution, transitions = [], [], []
    for split in SPLITS:
        split_file = "train" if split == "train" else "valid"
        target = pd.read_parquet(data_dir / f"target_1day_{split_file}.parquet")["Return"].sort_index()
        listed = read_panel(data_dir / f"listed_info_{split_file}.parquet", ["Sector17Code", "Sector33Code", "ScaleCategory"])
        for horizon in HORIZONS:
            path = RUN / f"predictions/SN1_H{horizon}_{split}.parquet"
            signal = pd.read_parquet(path)["Return"].sort_index()
            signal.index = pd.MultiIndex.from_arrays(
                [pd.DatetimeIndex(signal.index.get_level_values("Date")), signal.index.get_level_values("Code").astype(str)],
                names=["Date", "Code"],
            )
            if split == "train":
                deploy = signal.index.get_level_values("Date").year.isin(YEARS)
                signal = signal.loc[deploy]
            weights, q = evaluation.weights(signal)
            decay = score_decay(signal)
            decay.insert(0, "split", split)
            decay.insert(0, "horizon", horizon)
            decay.to_csv(RUN / f"metrics/score_decay_{split}_H{horizon}.csv", index=False)

            changes = daily_turnover_counts(signal, q, weights)
            if not changes.empty:
                summary = {"horizon": horizon, "split": split}
                for col in changes.columns:
                    if col.endswith("entrants") or col.endswith("exits"):
                        summary[f"mean_{col}_daily"] = float(changes[col].mean())
                summary["mean_common_codes"] = float(changes.common_codes.mean())
                transitions.append(summary)
                changes.to_csv(RUN / f"metrics/entrants_exits_{split}_H{horizon}.csv", index=False)

            q_counts = q.groupby(level="Date").value_counts().unstack(fill_value=0)
            long_short = pd.Series(np.where(q >= 3, "long", np.where(q <= 1, "short", "neutral")), index=q.index)
            absolute = weights.abs()
            daily_gross = absolute.groupby(level="Date").sum()
            daily_hhi = (absolute.div(daily_gross.reindex(absolute.index.get_level_values("Date")).to_numpy(), axis=0) ** 2).groupby(level="Date").sum()
            concentration.append({
                "horizon": horizon, "split": split,
                "mean_daily_distinct_universe_codes": float(signal.groupby(level="Date").size().mean()),
                "mean_daily_long_codes": float((q >= 3).groupby(level="Date").sum().mean()),
                "mean_daily_short_codes": float((q <= 1).groupby(level="Date").sum().mean()),
                "mean_total_weight_hhi": float(daily_hhi.mean()),
                "mean_effective_weighted_holdings": float((1.0 / daily_hhi).mean()),
                "mean_daily_max_abs_weight": float(absolute.groupby(level="Date").max().mean()),
                "five_quintiles_all_days": bool((q_counts.reindex(columns=range(5), fill_value=0) > 0).all(axis=1).all()),
            })

            extra = pd.DataFrame(index=signal.index)
            extra["weight"] = weights
            extra["quintile"] = q
            extra["side"] = long_short
            extra["abs_weight"] = absolute
            extra = extra.join(listed, how="left")
            for category in ("Sector17Code", "Sector33Code", "ScaleCategory"):
                cc = concentration_by_category(extra, category)
                for side in ("long", "short"):
                    part = cc.loc[cc.side == side]
                    concentration.append({
                        "horizon": horizon, "split": split,
                        "category": category, "side": side,
                        "hhi_mean": float(part.hhi.mean()) if len(part) else np.nan,
                        "top_category_share_mean": float(part.max_category_share.mean()) if len(part) else np.nan,
                        "category_missing_weight_share_mean": float(part.missing_weight_share.mean()) if len(part) else np.nan,
                    })

            # At least 20 consecutive same-side days defines a persistent membership spell.
            side, age = spell_age(q)
            residual_target = target.reindex(signal.index)
            row_gross = weights * residual_target
            persistent = age.ge(20) & side.ne(0)
            for bucket, mask in (("persistent_20plus", persistent), ("newer_under20", side.ne(0) & ~persistent)):
                for sleeve in ("long", "short"):
                    select = mask & side.eq(1 if sleeve == "long" else -1)
                    contribution = row_gross.where(select, 0.0).groupby(level="Date").sum()
                    active_stock_days = int(select.sum())
                    attribution.append({
                        "horizon": horizon, "split": split, "holding_age_bucket": bucket,
                        "sleeve": sleeve, "stock_days": active_stock_days,
                        "annualized_gross_contribution": float(contribution.mean() * 252) if len(contribution) else np.nan,
                        "mean_daily_contribution": float(contribution.mean()) if len(contribution) else np.nan,
                    })

    pd.DataFrame(concentration).to_csv(RUN / "audit/holdings_concentration.csv", index=False)
    pd.DataFrame(attribution).to_csv(RUN / "metrics/persistent_holding_pnl.csv", index=False)
    pd.DataFrame(transitions).to_csv(RUN / "metrics/entrants_exits_summary.csv", index=False)
    manifest = {
        "script": str(Path(__file__).relative_to(ROOT)),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "inputs": ["saved fixed-candidate SN1 scores", "official one-day Train/Valid target for attribution", "PIT listed_info sector/scale"],
        "diagnostic_horizon": "20 consecutive trading days defines persistent membership; lag profile 1/5/20/40",
        "purpose": "descriptive only; no candidate or parameter selection",
    }
    (RUN / "audit/holdings_diagnostics_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
