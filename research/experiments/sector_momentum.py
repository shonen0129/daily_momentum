"""Bounded Train-only component identification, exactly three fixed trials."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import platform
import resource
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import pyarrow
import scipy

from research import evaluation, firewall
from stock_comp_2026 import evaluate_script as official
from stock_comp_2026.strategies.dm_sector_momentum import features as sm
from stock_comp_2026.strategies.dm_sector_momentum import submission as adapter
from stock_comp_2026.strategies.dm_trainonly import features as old


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe(value):
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.integer, np.bool_)):
        return value.item()
    return value


def dump(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(safe(value), indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def exact(a, b):
    if isinstance(a, pd.Series):
        a, b = a.to_frame(), b.to_frame()
    assert a.index.equals(b.index) and a.columns.equals(b.columns) and a.dtypes.equals(b.dtypes)
    for col in a:
        if pd.api.types.is_numeric_dtype(a[col]):
            assert np.array_equal(a[col].to_numpy().view(np.uint64), b[col].to_numpy().view(np.uint64)), col
        else:
            pd.testing.assert_series_equal(a[col], b[col], check_exact=True)


def source_scan():
    folder = ROOT / "stock_comp_2026/strategies/dm_sector_momentum"
    sources = {str(p.relative_to(ROOT)): p.read_text() for p in folder.glob("*.py")}
    for name in ["build_momentum", "segment_keys", "centered_rank", "smooth"]:
        sources[f"dm_trainonly.features.{name}"] = inspect.getsource(getattr(old, name))
    findings = []
    for path, source in sources.items():
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if any(token in node.value for token in ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow",
                       "AdjustmentClose", "AdjustmentVolume", "raw_target", "_valid.parquet", "target_1day"]):
                    findings.append((path, node.lineno, "forbidden input"))
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            bad = node.func.attr in ["bfill", "backfill"]
            if node.func.attr == "shift":
                n = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == "periods"), None)
                bad |= not isinstance(n, ast.Constant) or not isinstance(n.value, int) or n.value < 0
            for k in node.keywords:
                bad |= k.arg == "center" and not (isinstance(k.value, ast.Constant) and k.value.value is False)
                bad |= k.arg == "direction" and not (isinstance(k.value, ast.Constant) and k.value.value == "backward")
            if bad:
                findings.append((path, node.lineno, "forbidden temporal operation"))
    assert not findings, findings
    return {"status": "PASS", "sources": list(sources), "findings": findings,
            "manual_review": "Only same-date peer grouping, exact PIT joins, historical residual60 lag1. Full listed universe projected to present raw-return rows; no label dependency."}


def mutate(frame, name, cutoff, seed):
    out = frame.copy()
    mask = out.index.get_level_values("Date") > cutoff
    rng = np.random.default_rng(seed)
    for col in out:
        if name == "listed_info":
            out.loc[mask, col] = rng.choice(["new_sector", "99", "9999"], int(mask.sum()))
        else:
            values = rng.normal(0, 1e6, int(mask.sum()))
            values[::7] = np.nan
            out.loc[mask, col] = values
    out = out.drop(out.index[mask][::13])
    if isinstance(out.index, pd.MultiIndex):
        # Future-only code enters dataset/membership only after cutoff.
        future = frame.loc[mask].iloc[::max(1, int(mask.sum()) // 40)].copy()
        future = future.loc[~future.index.get_level_values("Date").duplicated()]
        future.index = pd.MultiIndex.from_arrays([future.index.get_level_values("Date"),
                           ["FUTURE_ONLY"] * len(future)], names=["Date", "Code"])
        out = pd.concat([out, future])
    return out


def prefix_audit(inputs, base, config):
    rows = []
    for i, text in enumerate(config["prefix_cutoffs"]):
        cutoff = pd.Timestamp(text)
        prefix = base.loc[base.index.get_level_values("Date") <= cutoff]
        for name in list(inputs) + ["ALL", "TRUNCATION"]:
            changed = dict(inputs)
            for j, (source, frame) in enumerate(inputs.items()):
                if name == "TRUNCATION":
                    changed[source] = frame.loc[frame.index.get_level_values("Date") <= cutoff]
                elif name in [source, "ALL"]:
                    changed[source] = mutate(frame, source, cutoff, config["random_seed"] + i * 100 + j)
            got = sm.build_features(changed).loc[prefix.index]
            exact(prefix, got)
            for candidate in sm.CANDIDATES:
                exact(sm.score(prefix, candidate), sm.score(got, candidate))
            rows.append({"cutoff": text, "source": name, "status": "PASS", "bitwise": True,
                         "prefix_rows": len(prefix), "features": list(base.columns), "scores": list(sm.CANDIDATES)})
        print(f"prefix {text}: all sources/membership/truncation PASS", flush=True)
    exact(base, sm.build_features(inputs))
    exact(base, sm.build_features({k: v.sample(frac=1, random_state=19) for k, v in inputs.items()}))
    return {"status": "PASS", "cases": rows, "deterministic_rebuild": True, "row_shuffle": True,
            "method": "numeric float64 uint64 bit patterns including NaN; string/dtype/index exact; suffix extreme/NaN, row deletion, changed sector and new future-only stocks"}


def fold_dates(calendar, years):
    dates, audit = [], []
    for year in years:
        now = calendar[calendar.year == year]
        keep = now[:-2]
        for date in keep:
            i = calendar.get_loc(date)
            assert i + 2 < len(calendar) and calendar[i + 2].year == year
        dates.extend(keep)
        audit.append({"year": year, "days": len(keep), "partial": year == 2016,
                      "purged": [str(d.date()) for d in now[-2:]], "last_signal": str(keep[-1].date()),
                      "last_label_end": str(now[-1].date()), "status": "PASS", "fitting": False})
    return pd.DatetimeIndex(dates), audit


def account(signal, target):
    daily = evaluation.daily_account(signal, target)
    w, q = evaluation.weights(signal)
    ow = official.compute_weight(signal.to_frame()).iloc[:, 0]
    exact(w, ow.rename(w.name))
    opl = official.compute_pl(signal.to_frame(), target.to_frame()).groupby("Date").sum()
    assert np.array_equal(opl.to_numpy(), daily.net.to_numpy())
    h = pd.DataFrame({"w": w, "q": q, "gross": w * target}, index=w.index)
    for side, positions in [("long", w.clip(lower=0)), ("short", (-w).clip(lower=0))]:
        turn = positions.groupby("Code").diff().abs().fillna(positions.abs())
        cost = .001 * turn.where(target.notna(), 0.)
        daily[f"{side}_turnover"] = turn.groupby("Date").sum()
        daily[f"{side}_cost"] = cost.groupby("Date").sum()
        daily[f"{side}_net"] = daily[side] - daily[f"{side}_cost"]
        h[f"{side}_cost"] = cost
    h["cost"] = h.long_cost + h.short_cost
    h["net"] = h.gross.fillna(0.) - h.cost
    assert np.allclose(daily.long_net + daily.short_net, daily.net, rtol=0, atol=1e-15)
    assert np.allclose(daily.long_turnover + daily.short_turnover, daily.turnover, rtol=0, atol=1e-15)
    return daily, h, {"status": "PASS", "weight_bitwise": True, "net_bitwise": True,
                      "long_short_tolerance": 1e-15, "full_panel_rows": len(signal)}


def metrics(daily):
    m = evaluation.metrics(daily)
    for side in ["long", "short"]:
        m[f"annual_{side}_gross"] = float(daily[side].mean() * 252)
        m[f"annual_{side}_net"] = float(daily[f"{side}_net"].mean() * 252)
        m[f"{side}_gross_sharpe"] = evaluation.sharpe(daily[side])
        m[f"{side}_net_sharpe"] = evaluation.sharpe(daily[f"{side}_net"])
        m[f"annual_{side}_cost"] = float(daily[f"{side}_cost"].mean() * 252)
    return m


def daily_corr(a, b):
    good = a.notna() & b.notna()
    x, y = a.where(good), b.where(good)
    x = x - x.groupby("Date").transform("mean")
    y = y - y.groupby("Date").transform("mean")
    return (x * y).groupby("Date").sum() / np.sqrt((x * x).groupby("Date").sum() * (y * y).groupby("Date").sum())


def correlations(f, folder):
    pairs = [("StockMom60", "Sector17Mom"), ("StockMom60", "Sector33Mom"),
             ("Sector17Mom", "Sector33Mom"), ("Rel17Mom", "Sector17Mom"), ("Rel33Mom", "Sector33Mom")]
    daily, pooled = [], []
    for left, right in pairs:
        a, b = f[left], f[right]
        pearson = daily_corr(a, b)
        pair_good = a.notna() & b.notna()
        rank_a, rank_b = a.where(pair_good).groupby("Date").rank(), b.where(pair_good).groupby("Date").rank()
        spearman = daily_corr(rank_a, rank_b)
        daily.append(pd.DataFrame({"pair": f"{left}/{right}", "pearson": pearson, "spearman": spearman}).reset_index())
        good = a.notna() & b.notna()
        x, y = a.where(good), b.where(good)
        x -= x.groupby("Date").transform("mean")
        y -= y.groupby("Date").transform("mean")
        pooled.append({"left": left, "right": right, "rows": int(good.sum()),
                       "pooled_pearson": a.corr(b), "pooled_spearman": a.corr(b, method="spearman"),
                       "pooled_date_demeaned_pearson": x.corr(y),
                       "mean_daily_pearson": pearson.mean(), "mean_daily_spearman": spearman.mean()})
    pd.concat(daily).to_csv(folder / "correlation_daily.csv", index=False)
    pd.DataFrame(pooled).to_csv(folder / "correlation_pooled.csv", index=False)
    f[["StockMom60", "Sector17Mom", "Sector33Mom", "Rel17Mom", "Rel33Mom"]].corr().to_csv(folder / "correlation_matrix.csv")
    good = f[["StockMom60", "Sector33Mom", "Rel33Mom"]].notna().all(axis=1)
    error = (f.StockMom60 - (f.Sector33Mom + f.Rel33Mom)).loc[good]
    diff = f.Sector33Mom - f.Sector17Mom
    mapping = f.groupby(["Sector33Code", "Sector17Code"]).size().rename("rows").reset_index()
    mapping.to_csv(folder / "hierarchy_mapping.csv", index=False)
    group = [f.index.get_level_values("Date"), f.Sector33Code]
    stock = f.StockMom60 - f.StockMom60.groupby(group).transform("mean")
    peer = f.Sector33Mom - f.Sector33Mom.groupby(group).transform("mean")
    dump(folder / "hierarchy.json", {"valid_rows": int(good.sum()), "max_identity_error": error.abs().max(),
         "industry_within_sector_mean": diff.mean(), "industry_within_sector_std": diff.std(),
         "sector33_sector17_corr": f.Sector33Mom.corr(f.Sector17Mom),
         "within_date_sector33_stock_peer_corr": stock.corr(peer),
         "interpretation": "Exact LOO algebra is sector_mean+(sector_mean-own)/(finite_count-1). It gives a negative within-sector stock coefficient; hierarchy difference is descriptive, not orthogonal extraction."})
    return pooled


def agreement_and_breadth(f, target, holdings, folder):
    agreement_rows, agreement_daily, breadth_rows, sector_breadth = [], [], [], []
    dates = f.index.get_level_values("Date").unique().sort_values()
    for level in [17, 33]:
        peer = f[f"Sector{level}Mom"]
        stock = f.StockMom60
        bucket = pd.Series("ZERO_OR_MISSING", index=f.index)
        for name, mask in [("A", (stock > 0) & (peer > 0)), ("B", (stock > 0) & (peer < 0)),
                           ("C", (stock < 0) & (peer > 0)), ("D", (stock < 0) & (peer < 0))]:
            bucket.loc[mask] = name
        for name in ["A", "B", "C", "D", "ZERO_OR_MISSING"]:
            mask = bucket == name
            mean_target = target.where(mask).groupby("Date").mean().reindex(dates)
            ic_stock = evaluation.rankic(stock.where(mask), target)
            ic_peer = evaluation.rankic(peer.where(mask), target)
            for strategy, h in holdings.items():
                short = h.w.where((h.w < 0) & mask, 0.) * target
                gross = short.groupby("Date").sum().reindex(dates, fill_value=0.)
                cost = h.short_cost.where(mask, 0.).groupby("Date").sum().reindex(dates, fill_value=0.)
                for scope, ds in [("POOLED", dates)] + [(str(y), dates[dates.year == y]) for y in range(2011, 2017)]:
                    row = {"level": level, "bucket": name, "strategy": strategy, "scope": scope,
                           "stock_days": int((mask & f.index.get_level_values("Date").isin(ds)).sum()),
                           "forward_target_mean": mean_target.reindex(ds).mean(),
                           "stock_rankic": ic_stock.reindex(ds).mean(), "stock_rankic_hac5": evaluation.hac_t(ic_stock.reindex(ds)),
                           "sector_rankic": ic_peer.reindex(ds).mean(), "sector_rankic_hac5": evaluation.hac_t(ic_peer.reindex(ds)),
                           "annual_short_gross_contribution": gross.reindex(ds).mean() * 252,
                           "annual_short_net_contribution": (gross - cost).reindex(ds).mean() * 252,
                           "short_gross_sharpe": evaluation.sharpe(gross.reindex(ds)),
                           "equal_short_mean_target": -mean_target.reindex(ds).mean()}
                    agreement_rows.append(row)
                agreement_daily.append(pd.DataFrame({"level": level, "bucket": name, "strategy": strategy,
                    "target_mean": mean_target, "stock_rankic": ic_stock, "sector_rankic": ic_peer,
                    "short_gross": gross, "short_cost": cost}).reset_index())
        breadth = f[f"Breadth{level}"]
        sector_keys = [f.index.get_level_values("Date"), f[f"Sector{level}Code"]]
        sector_panel = pd.DataFrame({"stock_mom": stock, "positive": stock.gt(0).astype(float).where(stock.notna()),
                                     "target": target}).groupby(sector_keys).agg(
            sector_mom=("stock_mom", "mean"), finite_count=("stock_mom", "count"),
            positive_count=("positive", "sum"), mean_forward_target=("target", "mean"))
        sector_panel.index.names = ["Date", "sector"]
        sector_panel["breadth"] = sector_panel.positive_count / sector_panel.finite_count.where(sector_panel.finite_count > 0)
        sector_panel["level"] = level
        sector_breadth.append(sector_panel.reset_index())
        equal_sector_median = sector_panel.sector_mom.groupby("Date").median()
        median = pd.Series(equal_sector_median.reindex(f.index.get_level_values("Date")).to_numpy(), index=f.index)
        partitions = {
            "HIGH_BROAD_POSITIVE": (peer >= median) & (peer > 0) & (breadth >= .5),
            "HIGH_NARROW_POSITIVE": (peer >= median) & (peer > 0) & (breadth < .5),
            "LOW_BROAD_WEAKNESS": (peer < median) & (peer < 0) & (breadth < .5),
        }
        partitions["OTHER_FINITE"] = peer.notna() & breadth.notna() & ~pd.concat(partitions, axis=1).any(axis=1)
        for name, mask in partitions.items():
            for scope, ds in [("POOLED", dates)] + [(str(y), dates[dates.year == y]) for y in range(2011, 2017)]:
                selected = mask & f.index.get_level_values("Date").isin(ds)
                daily_target = target.where(selected).groupby("Date").mean().reindex(ds)
                breadth_rows.append({"level": level, "bucket": name, "scope": scope, "rows": int(selected.sum()),
                                     "mean_sector_mom": peer.loc[selected].mean(), "mean_breadth": breadth.loc[selected].mean(),
                                     "forward_target_mean_equal_date": daily_target.mean()})
        breadth_rows.append({"level": level, "bucket": "CORRELATION", "scope": "POOLED",
                             "rows": int((peer.notna() & breadth.notna()).sum()),
                             "sector_breadth_pearson": peer.corr(breadth),
                             "mean_daily_sector_breadth_pearson": daily_corr(peer, breadth).mean()})
    pd.DataFrame(agreement_rows).to_csv(folder / "agreement.csv", index=False)
    pd.concat(agreement_daily).to_csv(folder / "agreement_daily.csv", index=False)
    pd.DataFrame(breadth_rows).to_csv(folder / "breadth.csv", index=False)
    pd.concat(sector_breadth).to_csv(folder / "sector_breadth_daily.csv", index=False)


def concentration(f, holdings, daily, folder):
    exposures, summaries, contributions, loso = [], [], [], []
    eval_dates = f.index.get_level_values("Date").unique().sort_values()
    for strategy, h in holdings.items():
        for level in [17, 33]:
            sector = f[f"Sector{level}Code"].fillna("UNKNOWN")
            keys = [h.index.get_level_values("Date"), sector]
            parts = pd.DataFrame({"long_weight": h.w.clip(lower=0), "short_weight": (-h.w).clip(lower=0),
                "gross_weight": h.w.abs(), "Q1_count": (h.q == 0).astype(int), "Q5_count": (h.q == 4).astype(int),
                "gross": h.gross.fillna(0.), "cost": h.cost, "net": h.net}, index=h.index)
            grouped = parts.groupby(keys).sum()
            grouped.index.names = ["Date", "sector"]
            exposure = grouped.copy()
            for col in ["long_weight", "short_weight", "gross_weight", "Q1_count", "Q5_count"]:
                total = grouped[col].groupby("Date").transform("sum")
                exposure[col + "_share"] = grouped[col] / total.where(total > 0)
            exposure["strategy"], exposure["level"] = strategy, level
            exposures.append(exposure.reset_index())
            for scope, ds in [("POOLED", eval_dates)] + [(str(y), eval_dates[eval_dates.year == y]) for y in range(2011, 2017)]:
                g = grouped.loc[grouped.index.get_level_values("Date").isin(ds)]
                for code, block in g.groupby("sector"):
                    contribution = {"strategy": strategy, "level": level, "sector": code, "scope": scope}
                    contribution.update({f"annual_{col}": block[col].sum() / len(ds) * 252 for col in ["gross", "net", "cost"]})
                    contributions.append(contribution)
            for col in ["gross_weight", "long_weight", "short_weight", "Q1_count", "Q5_count"]:
                shares = exposure[col + "_share"]
                max_daily = shares.groupby("Date").max()
                hhi = (shares * shares).groupby("Date").sum()
                average_share = shares.groupby("sector").sum() / len(eval_dates)
                for code, value in average_share.items():
                    summaries.append({"strategy": strategy, "level": level, "measure": col, "sector": code,
                                      "mean_daily_sector_share": value, "mean_daily_max_sector_share": max_daily.mean(),
                                      "daily_max_sector_concentration": max_daily.max(), "mean_daily_HHI": hhi.mean()})
            for code, block in grouped.groupby("sector"):
                removed = daily[strategy].loc[eval_dates].copy()
                for col in ["gross", "net"]:
                    removed[col] -= block[col].droplevel("sector").reindex(eval_dates, fill_value=0.)
                for scope, ds in [("POOLED", eval_dates), ("EX2016", eval_dates[eval_dates.year != 2016])]:
                    r = removed.loc[ds]
                    loso.append({"strategy": strategy, "level": level, "excluded_sector": code, "scope": scope,
                                 "gross_sharpe": evaluation.sharpe(r.gross), "net_sharpe": evaluation.sharpe(r.net),
                                 "annual_gross": r.gross.mean() * 252, "annual_net": r.net.mean() * 252,
                                 "method": "fixed positions minus attributed sector; no rerank/renormalization"})
            # Reconcile daily sector attribution against original daily accounts.
            totals = grouped[["gross", "net", "cost"]].groupby("Date").sum()
            assert np.allclose(totals.to_numpy(), daily[strategy].loc[eval_dates, ["gross", "net", "cost"]].to_numpy(), atol=1e-15, rtol=0)
    pd.concat(exposures).to_csv(folder / "sector_exposure_daily.csv", index=False)
    pd.DataFrame(summaries).to_csv(folder / "sector_concentration.csv", index=False)
    pd.DataFrame(contributions).to_csv(folder / "sector_contribution.csv", index=False)
    pd.DataFrame(loso).to_csv(folder / "leave_one_sector_out.csv", index=False)


def persistence(signals, holdings, calendar, eval_dates, folder):
    daily_rows, rows, spell_rows = [], [], []
    for strategy, score in signals.items():
        h = holdings[strategy]
        index = score.index
        ordinal = pd.Series(calendar.get_indexer(index.get_level_values("Date")), index=index)
        previous_ord = ordinal.groupby("Code").shift(1)
        adjacent = ordinal - previous_ord == 1
        rank = score.groupby("Date").rank(method="average", pct=True)
        previous_rank = rank.groupby("Code").shift(1).where(adjacent)
        rho = daily_corr(rank, previous_rank)
        previous_q = h.q.groupby("Code").shift(1).where(adjacent)
        retention = (h.q == previous_q).astype(float).where(previous_q.notna()).groupby("Date").mean()
        daily_rows.append(pd.DataFrame({"strategy": strategy, "rank_autocorrelation": rho,
                                       "quintile_retention": retention}).loc[eval_dates].reset_index())
        # Count contiguous tail membership spells, reset on missing exchange dates.
        block = pd.DataFrame({"q": h.q, "ordinal": ordinal}).reset_index().sort_values(["Code", "Date"])
        prev = block.groupby("Code").q.shift(1)
        prev_ord = block.groupby("Code").ordinal.shift(1)
        start = (block.q != prev) | (block.ordinal - prev_ord != 1)
        block["spell"] = start.cumsum()
        block["eligible"] = block.Date.isin(eval_dates)
        last_ordinal = block.groupby("Code").ordinal.transform("max")
        block["right_censored"] = block.ordinal == last_ordinal
        spells = block.groupby("spell").agg(Code=("Code", "first"), q=("q", "first"),
                  start=("Date", "min"), end=("Date", "max"), length=("Date", "size"),
                  eligible_days=("eligible", "sum"), right_censored=("right_censored", "max"))
        selected = spells.loc[spells.q.isin([0., 4.]) & (spells.eligible_days > 0)].copy()
        selected["strategy"] = strategy
        spell_rows.append(selected.reset_index(drop=True))
        for scope, ds in [("POOLED", eval_dates)] + [(str(y), eval_dates[eval_dates.year == y]) for y in range(2011, 2017)]:
            s = selected.loc[(selected.end >= ds.min()) & (selected.start <= ds.max())]
            rows.append({"strategy": strategy, "scope": scope, "mean_rank_autocorrelation": rho.reindex(ds).mean(),
                         "mean_quintile_retention": retention.reindex(ds).mean(),
                         "average_tail_holding_spell": s.length.mean(), "median_tail_holding_spell": s.length.median(),
                         "spells": len(s), "right_censored_spells": int(s.right_censored.sum())})
    pd.concat(daily_rows).to_csv(folder / "rank_persistence_daily.csv", index=False)
    pd.DataFrame(rows).to_csv(folder / "rank_persistence.csv", index=False)
    pd.concat(spell_rows).to_csv(folder / "holding_spells.csv", index=False)


def decisions(accounts, f, boot):
    result = {}
    control = metrics(accounts["MOM60"])
    for name, column in sm.CANDIDATES.items():
        d = accounts[name]
        m = metrics(d)
        ex = metrics(d.loc[d.index.year != 2016])
        yearly = [metrics(d.loc[d.index.year == y]) for y in range(2011, 2016)]
        feasibility = {"pooled_rankic_positive": m["rankic"] > 0,
            "pooled_grossSR_positive": m["gross_sharpe"] > 0,
            "ex2016_grossSR_positive": ex["gross_sharpe"] > 0,
            "positive_full_year_gross_3of5": sum(v["annual_gross"] > 0 for v in yearly) >= 3,
            "raw_finite_coverage_95pct": f[column].notna().mean() >= .95,
            "turnover_le_MOM60": m["turnover"] <= control["turnover"]}
        short = {"short_gross_positive": m["annual_short_gross"] > 0,
                 "short_gross_ge_MOM60": m["annual_short_gross"] >= control["annual_short_gross"],
                 "short_net_ge_MOM60": m["annual_short_net"] >= control["annual_short_net"]}
        next_stage = {"pooled_netSR_positive": m["net_sharpe"] > 0, "ex2016_netSR_positive": ex["net_sharpe"] > 0,
            "pooled_netSR_beats_MOM60": m["net_sharpe"] > control["net_sharpe"],
            "netSR_improvement_4of5": sum(v["net_sharpe"] > metrics(accounts["MOM60"].loc[accounts["MOM60"].index.year == y])["net_sharpe"] for y, v in zip(range(2011, 2016), yearly)) >= 4,
            "bootstrap_lower_positive": boot[name]["low"] > 0,
            "quintile_monotonicity_positive": m["q_monotonicity"] > 0}
        checks = {**feasibility, **short, **next_stage}
        result[name] = {"decision": "NEXT_EXPERIMENT_ELIGIBLE" if all(checks.values()) else "REJECT",
                        "feasibility": feasibility, "short_gate": short, "next_stage": next_stage,
                        "failed_checks": [k for k, v in checks.items() if not v], "no_release_adoption": True}
    return result


def table(frame, columns):
    selected = frame[columns].copy()
    for col in selected:
        if pd.api.types.is_float_dtype(selected[col]):
            selected[col] = selected[col].map(lambda x: f"{x:.6f}")
    return "| " + " | ".join(columns) + " |\n| " + " | ".join(["---"] * len(columns)) + " |\n" + "\n".join("| " + " | ".join(map(str, row)) + " |" for row in selected.itertuples(index=False, name=None))


def write_report(config, output, result, incremental, boot, decision):
    report = ROOT / config["report_dir"]
    report.mkdir(parents=True, exist_ok=True)
    for name in ["metrics", "audit"]:
        shutil.copytree(output / name, report / name, dirs_exist_ok=False)
    pooled = result.loc[result.scope == "POOLED"]
    lines = [f"# {config['experiment_id']} — PIT peer Momentum component identification", "",
        "Three fixed candidates completed; Train-only known development evidence, not independent OOS. No Valid, Freeze or external submission.", "",
        f"Run `{output.relative_to(ROOT)}`. Fixed60-observation residual sum, skip-one observation, raw pre-rank StockMom signs; equal-weight LOO peers,17 minimum10 /33 minimum5, exact PIT join. Candidate components have no smoothing; unchanged MOM60 control is centered rank+EWMA(.25). This comparison identifies components and their fixed operationalizations, and does not isolate only the aggregation transformation.", "",
        "## Overall matched2011–2016 partial", "",
        table(pooled, ["strategy", "rankic", "rankic_t_hac5", "gross_sharpe", "net_sharpe", "annual_gross", "annual_net", "turnover", "annual_cost", "annual_short_gross", "annual_short_net"]), "",
        "Decimal P/L; annual arithmetic mean×252, sample-SD Sharpe×sqrt252, HAC/Bartlett lag5, compound maximum DD. Both side Gross/Net Sharpe and all required Q1–Q5/hit/DD metrics are in metrics.csv. period_* fields are actual period sums; annual_* are annualized, including2016 partial. Official5-quintile weights includeQ2/Q4 and Code tie order. Full daily accounting precedes last2-date fold purge, retaining prior holdings.", "",
        "## Full-year folds and2016 partial", "",
        table(result.loc[result.scope.isin([str(y) for y in range(2011, 2017)])], ["strategy", "scope", "rankic", "gross_sharpe", "net_sharpe", "annual_gross", "annual_net", "annual_short_gross", "annual_short_net", "turnover"]), "",
        "## Fixed gates and decision", "", "```json", json.dumps(safe(decision), indent=2), "```", "",
        "Feasibility, Short-improvement claim and next-experiment eligibility are distinct. Failure is retained as rejection of this fixed candidate, not a theorem about industry information. No diagnostics create filters, exclusions, sign flips, smoothing or new candidates.", "",
        "## Paired20-session bootstrap ΔNet Sharpe vs MOM60", "", "```json", json.dumps(safe(boot), indent=2), "```", "",
        "2000 paired circular moving-block draws, seed20261002, percentile95% intervals. Concatenated eligible signal dates skip purged gaps; intervals are known-Train sampling variation and are not independent OOS or multiplicity-adjusted evidence.", "",
        "## Mechanism and robustness", "",
        "Agreement A(++),B(+-),C(-+),D(--) uses raw StockMom/peer signs. agreement.csv contains equal-date forward residual target means, Stock/sector within-bucket RankIC/HAC5 and official fixed Short-book contributions for every candidate/control, pooled/year. Equal-short target mean is descriptive only; no filtered portfolio is evaluated. Short net bucket attribution includes turnover costs on bucket rows, and must not be interpreted as the cost of a standalone bucket trading rule.", "",
        "Breadth is finite positive OTHER peers / finite peers. HIGH/LOW uses same-date equal-sector median of group StockMom means; broad-positive breadth>=.5, broad-weakness<.5. breadth.csv summarizes pre-fixed descriptive participation categories, while sector_breadth_daily.csv saves group-level common mean/count/positive breadth and target. Correlation files contain the requested5 pairs, daily Pearson/Spearman, pooled raw and same-date-demeaned Pearson, plus full matrix.", "",
        "StockMom=Sector33Mom+Rel33Mom holds up to recorded floating subtraction error. Sector33−Sector17 is a descriptive industry-within-sector component, not an orthogonal factor. Importantly, LOO sector score equals group mean+(group mean−own)/(n−1): within a fixed sector it carries a mechanically NEGATIVE own-StockMom ordering. Exact PIT33→17 mapping and within-date/sector correlation are recorded in hierarchy files; this can affect within-sector quintile ordering even when the common component varies little.", "",
        "Sector17/33 Q1/Q5 distributions, Long/Short normalized exposures, daily HHI/max concentration and gross/net/cost contributions are saved. LOSO subtracts one sector's original portfolio contribution and attributed costs without reranking/renormalization. Its Sharpe is descriptive; lower gross exposure after subtraction limits comparability. No good/bad sector selection results. rank_persistence.csv/daily and holding_spells.csv retain rank autocorrelation, quintile retention and complete tail spells intersecting evaluation (right-censored marked). This is quintile holding, not a trading-order holding time.", "",
        "## Coverage and causal audit", "",
        "Full-feature/score bitwise mutation/truncation at3 cutoffs, all4 sources individually/jointly, suffix membership/new stocks/sector/return changes; row shuffle/deterministic rebuild, exact index, raw finite coverage vs100% neutral adapter coverage, research/adapter parity and standalone top-level Train smoke passed. Source scan covers new builder/adapter plus unchanged control primitives. Runtime firewall rejects Valid/raw-target/unknown parquet paths; prediction is audited before any Train label read. Audit records limitations: Python-level guard is best-effort, tests are evidence on exercised cases rather than a mathematical proof.", "",
        "Missing-target rows remain in ranking; official scorer omits their cost, so all-position conservative cost/net are separate columns. Short residual P/L is signed target contribution, not a raw short-security return or borrow-cost estimate. Universe is the supplied498-stock dataset, not a reconstructed historical all-exchange universe: only date-present rows with PIT classifications enter peers, but provider universe survivorship cannot be independently removed here. Real Valid/zip/late-split runtime is untested by design.", "",
        "Artifacts: metrics.csv, fold_metrics.csv/year_metrics.csv, incremental.csv, long_short.csv, quintiles.csv, bootstrap.json/csv, daily_*.csv, agreement*.csv, breadth.csv, sector_exposure_daily.csv, sector_concentration.csv, sector_contribution.csv, leave_one_sector_out.csv, correlation*.csv, hierarchy.json/mapping.csv, rank_persistence*.csv, holding_spells.csv, coverage.csv, audit/*.json. Full features/scores, code snapshots/data/environment hashes and resource measurements are stored in the run."]
    (report / "REPORT.md").write_text("\n".join(lines) + "\n")
    exp = ROOT / "experiments" / config["experiment_id"]
    (exp / "decision.md").write_text(f"# {config['experiment_id']} decision\n\nThree fixed trials completed, known Train only.\n\n" +
        "\n".join(f"- **{name}**: {d['decision']}. Failed checks: {', '.join(d['failed_checks']) or 'none'}." for name, d in decision.items()) +
        f"\n\nNo additional trials, combination, Freeze, Valid or external submission. [Report](../../{config['report_dir']}/REPORT.md). [Gates](../../{config['report_dir']}/metrics/candidate_decision.json). Run `{output.relative_to(ROOT)}`.\n")
    meta = json.loads((exp / "experiment.json").read_text())
    meta.update(status="rejected" if all(d["decision"] == "REJECT" for d in decision.values()) else "completed",
                actual_trials=3, run_id=output.name, report=f"{config['report_dir']}/REPORT.md")
    dump(exp / "experiment.json", meta)
    with (ROOT / "experiments/GRAVEYARD.md").open("a") as stream:
        stream.write(f"\n## {config['experiment_id']}: Independent PIT Sector Momentum\n\n[Decision]({config['experiment_id']}/decision.md) / [Report](../{config['report_dir']}/REPORT.md). Fixed3 trials, known Train-only, no Valid/Freeze/combination.\n\n")
        for name, d in decision.items():
            if d["decision"] == "REJECT":
                m = pooled.loc[pooled.strategy == name].iloc[0]
                stream.write(f"- **{name}** — Gross/Net SR {m.gross_sharpe:.4f}/{m.net_sharpe:.4f}, turnover {m.turnover:.5f}/day, annual Short gross/net {m.annual_short_gross:+.3%}/{m.annual_short_net:+.3%}. Reject: {', '.join(d['failed_checks'])}.\n")
        stream.write("\nRejects fixed operationalizations; diagnostics do not authorize sector exclusion/breadth/agreement filters or rescue searches.\n")


def main_work(config, output, run):
    started = time.monotonic()
    stage = output / "stage"
    stage.mkdir()
    data_hashes = {}
    for name in list(sm.INPUT_COLUMNS) + ["target_1day"]:
        source = ROOT / config["input_dir"] / f"{name}_train.parquet"
        (stage / source.name).symlink_to(source)
        data_hashes[source.name] = sha(source)
    prediction_paths = [output / "predictions" / f"{name}.parquet" for name in ["features", "scores"]]
    firewall.install(allowed_artifacts=prediction_paths)
    code_paths = [Path(__file__), ROOT / "research/evaluation.py", ROOT / "research/firewall.py",
                  ROOT / "stock_comp_2026/evaluate_script.py", ROOT / "stock_comp_2026/strategies/dm_trainonly/features.py"]
    code_paths += list((ROOT / "stock_comp_2026/strategies/dm_sector_momentum").glob("*.py"))
    code_hashes = {str(p.relative_to(ROOT)): sha(p) for p in code_paths}
    for path in code_paths:
        destination = output / "code" / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    run.update(status="running", command=sys.argv, code_sha256=code_hashes, train_data_sha256=data_hashes,
               environment={"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
                            "scipy": scipy.__version__, "pyarrow": pyarrow.__version__, "platform": platform.platform()})
    dump(output / "run.json", run)
    dump(output / "audit/source_scan.json", source_scan())
    dump(output / "audit/pre_result_lock.json", {"at_utc": datetime.now(timezone.utc).isoformat(),
        "plan_sha256": sha(output / "plan.md"), "config_sha256": sha(output / "config.json"),
        "code_sha256": code_hashes, "target_read": False, "max_trials": 3, "trials": list(sm.CANDIDATES)})
    inputs = sm.load_train(stage)
    f = sm.build_features(inputs)
    assert f.index.equals(sm.canonical(inputs["raw_return_1day"]).index)
    signals = {name: sm.score(f, name) for name in sm.CANDIDATES}
    signals["MOM60"] = old.smooth(old.build_momentum(inputs), .25).rename("Return")
    exact(old.centered_rank(f.StockMom60).rename("res60s1"), old.build_momentum(inputs))
    print(f"built features/scores {len(f):,} rows; no labels read", flush=True)
    dump(output / "audit/prefix_invariance.json", prefix_audit(inputs, f, config))
    for name in sm.CANDIDATES:
        exact(signals[name].to_frame(), adapter.predict(stage, name))
    # Top-level standalone import: same API and input-stage, before label access.
    import importlib.util
    spec = importlib.util.spec_from_file_location("sector_standalone", ROOT / "stock_comp_2026/strategies/dm_sector_momentum/submission.py")
    top = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "stock_comp_2026/strategies/dm_sector_momentum"))
    spec.loader.exec_module(top)
    smoke_start = time.monotonic()
    exact(signals["SECTOR33_MOM"].to_frame(), top.predict(stage))
    dump(output / "audit/adapter_parity.json", {"status": "PASS", "candidates": list(sm.CANDIDATES),
         "rows": len(f), "bitwise": True, "top_level_default_parity": True,
         "standalone_seconds": time.monotonic() - smoke_start, "labels_read": False})
    denied = []
    for path in [stage / "target_1day_valid.parquet", stage / "raw_target_1day_train.parquet", stage / "unknown.parquet"]:
        try:
            pd.read_parquet(path)
        except PermissionError as error:
            denied.append({"path": path.name, "denial": str(error)})
        else:
            raise AssertionError("Forbidden path read succeeded")
    dump(output / "audit/firewall_denials.json", {"status": "PASS", "cases": denied})
    assert not any("target_1day" in p for p in firewall.ACCESSES)
    dump(output / "audit/prediction_source_firewall.json", {"status": "PASS", "opened_parquets": sorted(firewall.ACCESSES), "no_labels_before_predictions_and_audits": True})
    f.to_parquet(prediction_paths[0])
    pd.DataFrame(signals).to_parquet(prediction_paths[1])
    calendar = f.index.get_level_values("Date").unique().sort_values()
    eval_dates, purge = fold_dates(calendar, [v["year"] for v in config["walk_forward_folds"]])
    dump(output / "audit/purge.json", {"status": "PASS", "folds": purge})
    mask = f.index.get_level_values("Date").isin(eval_dates)
    fe = f.loc[mask]
    coverage_rows = []
    for name, col in sm.CANDIDATES.items():
        assert np.isfinite(signals[name]).all()
        for scope, ids in [("ALL_TRAIN", f.index), ("POOLED", fe.index)] + [(str(y), fe.index[fe.index.get_level_values("Date").year == y]) for y in range(2011, 2017)]:
            coverage_rows.append({"strategy": name, "scope": scope, "rows": len(ids),
                "raw_finite_coverage": f.loc[ids, col].notna().mean(), "adapter_finite_coverage": 1.,
                "exact_index": True, "PIT17_coverage": f.loc[ids, "Sector17Code"].notna().mean(),
                "PIT33_coverage": f.loc[ids, "Sector33Code"].notna().mean(),
                "mean_peer17_count": f.loc[ids, "Peer17Count"].mean(), "mean_peer33_count": f.loc[ids, "Peer33Count"].mean()})
    pd.DataFrame(coverage_rows).to_csv(output / "metrics/coverage.csv", index=False)
    dump(output / "audit/coverage.json", {"status": "PASS", "rows": len(f), "index_exact": True,
         "all_adapter_scores_finite": True, "coverage_gate_uses_raw_components": True})
    print("causality/adapter/firewall PASS; now read Train target", flush=True)
    target_frame = sm.canonical(pd.read_parquet(stage / "target_1day_train.parquet"))
    assert target_frame.index.equals(f.index)
    target = target_frame.Return
    daily, holdings, parity = {}, {}, {}
    for name, signal in signals.items():
        daily[name], holdings[name], parity[name] = account(signal, target)
        daily[name].to_csv(output / f"metrics/daily_{name}.csv")
        print(f"accounted fixed {name}", flush=True)
    dump(output / "audit/official_accounting_parity.json", {"status": "PASS", "strategies": parity})
    accounts = {k: v.loc[eval_dates] for k, v in daily.items()}
    metric_rows = []
    for name, d in daily.items():
        scopes = [("ALL_TRAIN", d), ("POOLED", d.loc[eval_dates]), ("EX2016", d.loc[eval_dates[eval_dates.year != 2016]])]
        scopes += [(str(y), d.loc[eval_dates[eval_dates.year == y]]) for y in range(2011, 2017)]
        for scope, frame in scopes:
            metric_rows.append({"strategy": name, "scope": scope, **metrics(frame)})
    result = pd.DataFrame(metric_rows)
    result.to_csv(output / "metrics/metrics.csv", index=False)
    result.loc[result.scope == "POOLED"].to_csv(output / "metrics/overall_metrics.csv", index=False)
    for fname in ["fold_metrics", "year_metrics"]:
        result.loc[result.scope.isin([str(y) for y in range(2011, 2017)])].to_csv(output / f"metrics/{fname}.csv", index=False)
    result[["strategy", "scope"] + [c for c in result if "long" in c or "short" in c]].to_csv(output / "metrics/long_short.csv", index=False)
    result[["strategy", "scope"] + [c for c in result if c.startswith("q")]].to_csv(output / "metrics/quintiles.csv", index=False)
    increments = []
    for name in sm.CANDIDATES:
        for scope in result.scope.unique():
            candidate = result.loc[(result.strategy == name) & (result.scope == scope)].iloc[0]
            baseline = result.loc[(result.strategy == "MOM60") & (result.scope == scope)].iloc[0]
            increments.append({"strategy": name, "control": "MOM60", "scope": scope,
                **{f"delta_{key}": candidate[key] - baseline[key] for key in ["rankic", "gross_sharpe", "net_sharpe", "turnover", "annual_cost", "annual_gross", "annual_net", "annual_short_gross", "annual_short_net"]}})
    incremental = pd.DataFrame(increments)
    incremental.to_csv(output / "metrics/incremental.csv", index=False)
    boot = {name: evaluation.bootstrap_delta(accounts["MOM60"].net, accounts[name].net,
             **{k: config["bootstrap"][k] for k in ["seed", "reps", "block"]}) for name in sm.CANDIDATES}
    dump(output / "metrics/bootstrap.json", boot)
    pd.DataFrame([{"strategy": k, "control": "MOM60", **v} for k, v in boot.items()]).to_csv(output / "metrics/bootstrap.csv", index=False)
    decision = decisions(accounts, fe, boot)
    dump(output / "metrics/candidate_decision.json", decision)
    print("three trials complete; descriptive diagnostics only", flush=True)
    he = {k: v.loc[fe.index] for k, v in holdings.items()}
    correlations(fe, output / "metrics")
    agreement_and_breadth(fe, target.loc[fe.index], he, output / "metrics")
    concentration(fe, he, accounts, output / "metrics")
    persistence(signals, holdings, calendar, eval_dates, output / "metrics")
    firewall.save(output / "audit/firewall.json")
    resource_audit = {"elapsed_seconds": time.monotonic() - started,
                      "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
                      "actual_trials": 3, "valid_evaluation": False, "status": "PASS"}
    dump(output / "audit/resources.json", resource_audit)
    write_report(config, output, result, incremental, boot, decision)
    artifacts = {str(p.relative_to(output)): sha(p) for subdir in ["audit", "metrics", "predictions", "code"] for p in (output / subdir).rglob("*") if p.is_file()}
    run.update(resource_audit)
    run.update(status="completed", exit_code=0, completed_at_utc=datetime.now(timezone.utc).isoformat(),
               artifact_sha256=artifacts, candidate_decisions=decision)
    dump(output / "run.json", run)
    print(json.dumps(safe({"decisions": decision, "resources": resource_audit}), indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    assert config["data_split"] == "train" and config["valid_evaluation"] is False
    assert config["max_trials"] == 3 and [t["trial_id"] for t in config["trials"]] == list(sm.CANDIDATES)
    assert config["parameters"] == {"horizon": 60, "skip_observations": 1, "min_periods": 60,
        "relisting_gap": 20, "sector17_min_peers": 10, "sector33_min_peers": 5, "weight": "equal",
        "candidate_smoothing": None, "control_alpha": .25}
    output = Path(args.output).resolve()
    assert Path(args.config).resolve() == output / "config.json"
    run = json.loads((output / "run.json").read_text())
    assert run["status"] == "prepared"
    try:
        main_work(config, output, run)
    except BaseException as error:
        run.update(status="failed", exit_code=1, error=f"{type(error).__name__}: {error}",
                   completed_at_utc=datetime.now(timezone.utc).isoformat())
        dump(output / "run.json", run)
        if firewall._PATCHED:
            firewall.save(output / "audit/firewall.json")
        raise


if __name__ == "__main__":
    main()
