"""Two preregistered Train-only sector-context strategies and book diagnostics."""
import argparse
import ast
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
import pyarrow
import scipy
from research import evaluation, firewall
from research.experiments.sector_momentum import sha, safe, dump, exact, mutate, account, metrics, fold_dates, persistence, table
from research.experiments.hierarchical_momentum import rank_changes
from stock_comp_2026.strategies.dm_sector_confirmation import features as sc, primitives, submission
from stock_comp_2026.strategies.dm_hierarchical_momentum import features as hierarchy
from stock_comp_2026.strategies.dm_trainonly import features as old

STATES = ["A", "B", "C", "D", "ZERO_OR_MISSING"]


def scopes(dates):
    return [("POOLED", dates), ("EX2016", dates[dates.year != 2016])] + [(str(y), dates[dates.year == y]) for y in sorted(set(dates.year))]


def source_scan():
    paths = sorted((ROOT / "stock_comp_2026/strategies/dm_sector_confirmation").glob("*.py"))
    findings = []
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if any(t in node.value for t in ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose", "AdjustmentVolume", "raw_target", "target_1day", "_valid.parquet", "Sector17"]):
                    findings.append((str(path), node.lineno, "forbidden input"))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                bad = node.func.attr in ["bfill", "backfill"]
                if node.func.attr == "shift":
                    n = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == "periods"), None)
                    bad |= not isinstance(n, ast.Constant) or not isinstance(n.value, int) or n.value < 0
                for kw in node.keywords:
                    bad |= kw.arg == "center" and not (isinstance(kw.value, ast.Constant) and kw.value.value is False)
                    bad |= kw.arg == "direction" and not (isinstance(kw.value, ast.Constant) and kw.value.value == "backward")
                if bad:
                    findings.append((str(path), node.lineno, "forbidden temporal operation"))
    assert not findings, findings
    return {"status": "PASS", "sources": [str(p.relative_to(ROOT)) for p in paths], "findings": findings,
            "manual_review": "Exact same-date PIT projection/self-inclusive finite common min5; residual60 shift1; raw signs/context before existing Code EWMA; no label/fitted/order-matched path."}


def prefix_audit(inputs, base, config):
    cases = []
    for i, cutoff in enumerate(config["prefix_cutoffs"]):
        date = pd.Timestamp(cutoff)
        idx = base.index[base.index.get_level_values("Date") <= date]
        for name in list(inputs) + ["ALL", "TRUNCATION"]:
            changed = dict(inputs)
            for j, (source, frame) in enumerate(inputs.items()):
                if name == "TRUNCATION":
                    changed[source] = frame.loc[frame.index.get_level_values("Date") <= date]
                elif name in [source, "ALL"]:
                    changed[source] = mutate(frame, source, date, config["random_seed"] + i*100+j)
            got = sc.build_features(changed).loc[idx]
            exact(base.loc[idx], got)
            for candidate in sc.CANDIDATES:
                exact(sc.score(base.loc[idx], candidate), sc.score(got, candidate))
            cases.append({"cutoff": cutoff, "source": name, "status": "PASS", "bitwise": True,
                          "prefix_rows": len(idx), "features": list(base), "scores": list(sc.CANDIDATES)})
        print(f"context prefix {cutoff}: all sources/membership/truncation PASS", flush=True)
    exact(base, sc.build_features(inputs))
    exact(base, sc.build_features({n: x.sample(frac=1, random_state=9) for n, x in inputs.items()}))
    return {"status": "PASS", "cases": cases, "row_shuffle": True, "deterministic_rebuild": True,
            "comparison": "Exact index/columns/dtypes/string values; numeric uint64 bits including NaN, zero tolerance",
            "mutation": "Each/joint suffix return,beta,TOPIX extreme/NaN; PIT changes; deletion; future-only codes; truncation"}


def primitive_parity(inputs, f):
    for name in ["smooth", "segment_keys", "centered_rank"]:
        assert inspect.getsource(getattr(primitives, name)) == inspect.getsource(getattr(old, name))
    exact(f.MOM60, old.smooth(old.build_momentum(inputs), .25).rename("MOM60"))
    with patch.object(old, "centered_rank", side_effect=lambda v: v):
        raw = old.build_momentum(inputs).rename("StockMom60_raw")
    exact(f.StockMom60_raw, raw)
    previous = hierarchy.build_features(inputs)
    for col in ["StockMom60_raw", "Sector33Code", "FiniteMembers", "Sector33Common_raw", "MOM60"]:
        exact(f[col], previous[col])
    return {"status": "PASS", "StockMom_and_MOM60_bitwise": True, "prior07_common_and_PIT_bitwise": True,
            "unchanged_primitive_sources": ["smooth", "segment_keys", "centered_rank"]}


def enrich_holdings(h):
    h = h.copy()
    for side, positions in [("long", h.w.clip(lower=0)), ("short", (-h.w).clip(lower=0))]:
        h[side+"_turnover"] = positions.groupby("Code").diff().abs().fillna(positions.abs())
    h["turnover"] = h.long_turnover + h.short_turnover
    return h


def coverage(f, folder, dates):
    frame = pd.DataFrame({"stock_finite": np.isfinite(f.StockMom60_raw), "common_finite": np.isfinite(f.Sector33Common_raw)}, index=f.index)
    frame["agreement_finite"] = frame.stock_finite & frame.common_finite
    frame["four_state_defined"] = f.State.isin(["A", "B", "C", "D"])
    frame["missing_sector"] = f.Sector33Code.isna()
    frame["below_min_members"] = f.FiniteMembers.lt(5)
    frame["neutral_confirmation"] = f.Confirmed_raw.eq(0)
    frame["neutral_short_veto"] = f.ShortVeto_raw.eq(0)
    rows = []
    for scope, ds in [("ALL_TRAIN", f.index.get_level_values("Date").unique())] + scopes(dates):
        selected = frame.loc[frame.index.get_level_values("Date").isin(ds)]
        groups = [("ALL", selected)] + list(selected.groupby(f.Sector33Code.fillna("UNKNOWN").reindex(selected.index)))
        for sector, block in groups:
            rows.append({"scope": scope, "sector": sector, "rows": len(block), **{k: block[k].mean() for k in frame}})
    result = pd.DataFrame(rows)
    result.to_csv(folder/"coverage.csv", index=False)
    return result


def agreement(f, target, signals, holdings, accounts, folder):
    dates = f.index.get_level_values("Date").unique().sort_values()
    summary, daily = [], []
    for state in STATES:
        mask = f.State == state
        mean_target = target.where(mask).groupby("Date").mean().reindex(dates)
        raw_ic = evaluation.rankic(f.StockMom60_raw.where(mask), target)
        for strategy, h in holdings.items():
            parts = pd.DataFrame(index=f.index)
            for side in ["long", "short"]:
                active = h.w.gt(0) if side == "long" else h.w.lt(0)
                parts[side+"_gross"] = h.gross.where(mask & active, 0).fillna(0)
                parts[side+"_cost"] = h[side+"_cost"].where(mask, 0)
                parts[side+"_net"] = parts[side+"_gross"] - parts[side+"_cost"]
                parts[side+"_turnover"] = h[side+"_turnover"].where(mask, 0)
            d = parts.groupby("Date").sum().reindex(dates, fill_value=0.)
            d["state"], d["strategy"], d["target_mean"] = state, strategy, mean_target
            d["rows"] = mask.groupby("Date").sum()
            ic = evaluation.rankic(signals[strategy].reindex(f.index).where(mask), target)
            d["rankic"], d["raw_stock_rankic"] = ic, raw_ic
            daily.append(d.reset_index())
            for scope, ds in scopes(dates):
                keep = mask & f.index.get_level_values("Date").isin(ds)
                block = d.loc[ds]
                summary.append({"strategy": strategy, "scope": scope, "state": state, "rows": int(keep.sum()),
                    "forward_target_row_mean": target.loc[keep].mean(), "forward_target_equal_date_mean": block.target_mean.mean(),
                    "rankic": block.rankic.mean(), "rankic_hac5": evaluation.hac_t(block.rankic),
                    "raw_stock_rankic": block.raw_stock_rankic.mean(), "raw_stock_rankic_hac5": evaluation.hac_t(block.raw_stock_rankic),
                    **{"annual_"+c: block[c].mean()*252 for c in parts if "turnover" not in c},
                    **{c: block[c].mean() for c in parts if "turnover" in c}})
    daily = pd.concat(daily)
    pd.DataFrame(summary).to_csv(folder/"state_attribution.csv", index=False)
    daily.to_csv(folder/"state_attribution_daily.csv", index=False)
    for name, d in accounts.items():
        sums = daily.loc[daily.strategy==name].groupby("Date").sum(numeric_only=True).reindex(d.index)
        for side in ["long", "short"]:
            for column, account_col in [(side+"_gross", side), (side+"_net", side+"_net"), (side+"_cost", side+"_cost"), (side+"_turnover", side+"_turnover")]:
                assert np.allclose(sums[column], d[account_col], rtol=0, atol=1e-15), column
    return {"status": "PASS", "state_book_reconciliation_atol": 1e-15, "standalone_state_strategy": False}


def transitions(f, calendar, dates, folder):
    state = f.State
    ordinal = pd.Series(calendar.get_indexer(f.index.get_level_values("Date")), index=f.index)
    previous = state.groupby("Code").shift(1)
    adjacent = (ordinal - ordinal.groupby("Code").shift(1)) == 1
    tr = pd.DataFrame({"previous": previous.where(adjacent), "current": state}, index=f.index)
    tr["C_entry"] = adjacent & state.eq("C") & ~previous.eq("C").fillna(False)
    tr["C_exit"] = adjacent & ~state.eq("C") & previous.eq("C").fillna(False)
    transition_daily = tr.loc[tr.previous.notna()].groupby([pd.Grouper(level="Date"), "previous", "current"]).size().rename("rows").reset_index()
    transition_daily = transition_daily.loc[transition_daily.Date.isin(dates)]
    transition_daily.to_csv(folder/"state_transitions_daily.csv", index=False)
    rows = []
    for scope, ds in scopes(dates):
        grouped = transition_daily.loc[transition_daily.Date.isin(ds)].groupby(["previous", "current"]).rows.sum().reindex(pd.MultiIndex.from_product([STATES, STATES]), fill_value=0)
        totals = grouped.groupby(level=0).sum()
        for (a, b), count in grouped.items():
            rows.append({"scope": scope, "from": a, "to": b, "rows": count, "transition_probability": count/totals[a] if totals[a] else np.nan})
    pd.DataFrame(rows).to_csv(folder/"state_transitions.csv", index=False)
    block = pd.DataFrame({"state": state, "ordinal": ordinal}, index=f.index).reset_index().sort_values(["Code", "Date"])
    before = block.groupby("Code").state.shift(1)
    prev_ord = block.groupby("Code").ordinal.shift(1)
    start = block.state.ne(before).fillna(True) | block.ordinal.sub(prev_ord).ne(1)
    block["spell"] = start.astype("int64").cumsum()
    block["eligible"] = block.Date.isin(dates)
    after_ord = block.groupby("Code").ordinal.shift(-1)
    block["left_censored"] = block.ordinal.sub(prev_ord).ne(1)
    block["right_censored"] = after_ord.sub(block.ordinal).ne(1)
    spells = block.groupby("spell").agg(Code=("Code", "first"), state=("state", "first"), start=("Date", "min"), end=("Date", "max"),
        length=("Date", "size"), eligible_days=("eligible", "sum"), left_censored=("left_censored", "max"), right_censored=("right_censored", "max"))
    selected = spells.loc[spells.eligible_days>0]
    selected.to_csv(folder/"state_spells.csv", index=False)
    selected.loc[selected.state=="C"].to_csv(folder/"C_state_duration_distribution.csv", index=False)
    persistence_values = {}
    for horizon in [1, 5]:
        observable = pd.Series(True, index=f.index)
        persist = pd.Series(True, index=f.index)
        for k in range(1, horizon+1):
            future_ord = ordinal.groupby("Code").shift(-k)
            observable &= future_ord.sub(ordinal).eq(k)
            persist &= state.groupby("Code").shift(-k).eq(state).fillna(False)
        persistence_values[horizon] = persist.astype(float).where(observable)
    rows = []
    for scope, ds in scopes(dates):
        for s in STATES:
            sp = selected.loc[(selected.state==s)&(selected.end>=ds.min())&(selected.start<=ds.max())]
            keep = state.eq(s) & f.index.get_level_values("Date").isin(ds)
            rows.append({"scope": scope, "state": s, "spells": len(sp), "mean_duration": sp.length.mean(), "median_duration": sp.length.median(),
                "p10_duration": sp.length.quantile(.1), "p90_duration": sp.length.quantile(.9), "max_duration": sp.length.max(),
                "one_day_persistence": persistence_values[1].loc[keep].mean(), "five_day_persistence": persistence_values[5].loc[keep].mean(),
                "one_day_observable_rows": persistence_values[1].loc[keep].notna().sum(), "five_day_observable_rows": persistence_values[5].loc[keep].notna().sum(),
                "left_censored": sp.left_censored.sum(), "right_censored": sp.right_censored.sum()})
    pd.DataFrame(rows).to_csv(folder/"state_duration_persistence.csv", index=False)
    return tr


def turnover_attribution(f, tr, holdings, dates, folder):
    rows, daily_rows = [], []
    for strategy, h in holdings.items():
        categories = {"C_ENTRY": tr.C_entry, "C_EXIT": tr.C_exit, "C_ENTRY_OR_EXIT": tr.C_entry|tr.C_exit,
                      "ANY_STATE_CHANGE": tr.previous.notna() & tr.current.ne(tr.previous)}
        for name, mask in categories.items():
            cols = ["turnover", "long_turnover", "short_turnover", "cost", "long_cost", "short_cost"]
            d = h[cols].where(mask, 0).groupby("Date").sum().loc[dates]
            total = h[cols].groupby("Date").sum().loc[dates]
            d["strategy"], d["event"] = strategy, name
            daily_rows.append(d.reset_index())
            for scope, ds in scopes(dates):
                rows.append({"strategy": strategy, "scope": scope, "event": name,
                    **{c+"_share": d.loc[ds,c].sum()/total.loc[ds,c].sum() if total.loc[ds,c].sum()>0 else np.nan for c in cols},
                    "mean_daily_turnover": d.loc[ds,"turnover"].mean(), "annual_cost": d.loc[ds,"cost"].mean()*252})
    pd.DataFrame(rows).to_csv(folder/"state_triggered_turnover.csv", index=False)
    pd.concat(daily_rows).to_csv(folder/"state_triggered_turnover_daily.csv", index=False)


def replacement(f, target, base, candidate, accounts, folder):
    dates = f.index.get_level_values("Date").unique().sort_values()
    rows, stats, sector_stats, decomposition = [], [], [], []
    for book, bmask, cmask in [("SHORT_Q1_Q2", base.w<0, candidate.w<0), ("Q1", base.q==0, candidate.q==0), ("Q2", base.q==1, candidate.q==1)]:
        category = pd.Series("OTHER", index=f.index)
        category.loc[bmask & ~cmask] = "REMOVED"
        category.loc[~bmask & cmask] = "ADDED"
        category.loc[bmask & cmask] = "UNCHANGED"
        bg = base.gross.where(bmask, 0).fillna(0)
        cg = candidate.gross.where(cmask, 0).fillna(0)
        r = pd.DataFrame({"book": book, "class": category, "target": target, "state": f.State,
                          "sector": f.Sector33Code.fillna("UNKNOWN"), "stock_mom": f.StockMom60_raw,
                          "sector_common": f.Sector33Common_raw, "base_weight": base.w.where(bmask, 0),
                          "candidate_weight": candidate.w.where(cmask, 0), "base_gross": bg, "candidate_gross": cg,
                          "delta_gross": cg-bg}, index=f.index)
        for clas in ["REMOVED", "ADDED", "UNCHANGED"]:
            mask = category == clas
            rd = r.loc[mask]
            rows.append(rd.reset_index())
            daily = r[["base_gross", "candidate_gross", "delta_gross"]].where(mask, 0).groupby("Date").sum().reindex(dates)
            daily["book"], daily["class"] = book, clas
            daily["rows"] = mask.groupby("Date").sum()
            daily["target_mean"] = target.where(mask).groupby("Date").mean()
            decomposition.append(daily.reset_index())
            for scope, ds in scopes(dates):
                subset = rd.loc[rd.index.get_level_values("Date").isin(ds)]
                stats.append({"book": book, "class": clas, "scope": scope, "rows": len(subset), "target_mean": subset.target.mean(),
                    "target_equal_date_mean": daily.loc[ds,"target_mean"].mean(),
                    **{"annual_"+col: daily.loc[ds,col].mean()*252 for col in ["base_gross", "candidate_gross", "delta_gross"]},
                    **{col+suffix: getattr(subset[col], method)() for col in ["stock_mom", "sector_common"] for suffix, method in [("_mean", "mean"),("_std", "std"),("_median", "median")]},
                    **{col+f"_q{q:g}": subset[col].quantile(q) for col in ["stock_mom", "sector_common"] for q in [.05,.25,.75,.95]}})
                for sector, block in subset.groupby("sector"):
                    sector_stats.append({"book": book, "class": clas, "scope": scope, "sector": sector, "rows": len(block),
                        "row_share": len(block)/len(subset), "target_mean": block.target.mean(),
                        "annual_delta_gross": block.delta_gross.sum()/len(ds)*252})
    pd.concat(rows).to_parquet(folder/"removed_added_unchanged_names.parquet", index=False)
    pd.DataFrame(stats).to_csv(folder/"replacement_summary.csv", index=False)
    pd.DataFrame(sector_stats).to_csv(folder/"replacement_sector_distribution.csv", index=False)
    rd = pd.concat(decomposition)
    rd.to_csv(folder/"replacement_daily.csv", index=False)
    subset = rd.loc[rd.book=="SHORT_Q1_Q2"]
    pivot = subset.pivot(index="Date", columns="class", values="delta_gross").reindex(dates, fill_value=0.)
    b, c = accounts["MOM60"], accounts["SHORT_DISAGREE_VETO"]
    pivot["delta_short_gross"] = c.short - b.short
    pivot["cost_effect"] = b.short_cost - c.short_cost
    pivot["delta_short_net"] = c.short_net - b.short_net
    assert np.allclose(pivot[["REMOVED", "ADDED", "UNCHANGED"]].sum(axis=1), pivot.delta_short_gross, atol=1e-15, rtol=0)
    assert np.allclose(pivot.delta_short_gross + pivot.cost_effect, pivot.delta_short_net, atol=1e-15, rtol=0)
    pivot.to_csv(folder/"short_replacement_decomposition_daily.csv")
    summaries = [{"scope": scope, **{"annual_"+k: pivot.loc[ds,k].mean()*252 for k in pivot}} for scope, ds in scopes(dates)]
    pd.DataFrame(summaries).to_csv(folder/"short_replacement_decomposition.csv", index=False)
    cohorts = []
    C_short = f.State.eq("C") & base.w.lt(0)
    masks = {"C_ORIGINAL_SHORT_ALL": C_short, "C_ORIGINAL_SHORT_REMOVED": C_short & candidate.w.ge(0),
             "C_ORIGINAL_SHORT_RETAINED": C_short & candidate.w.lt(0), "ALL_SHORT_REPLACEMENTS": base.w.ge(0) & candidate.w.lt(0)}
    for name, mask in masks.items():
        for scope, ds in scopes(dates):
            keep = mask & f.index.get_level_values("Date").isin(ds)
            cohorts.append({"cohort": name, "scope": scope, "rows": int(keep.sum()), "target_mean": target.loc[keep].mean(),
                "annual_base_short_gross": base.gross.where(keep & base.w.lt(0),0).fillna(0).sum()/len(ds)*252,
                "annual_candidate_short_gross": candidate.gross.where(keep & candidate.w.lt(0),0).fillna(0).sum()/len(ds)*252})
    pd.DataFrame(cohorts).to_csv(folder/"C_veto_short_cohorts.csv", index=False)
    pd.DataFrame({"target": target, "base_weight": base.w, "candidate_weight": candidate.w, "removed": candidate.w.ge(0)}).loc[C_short].to_parquet(folder/"C_original_short_names.parquet")
    return {"status": "PASS", "replacement_gross_reconciliation_atol": 1e-15, "net_equals_gross_minus_cost_atol": 1e-15,
            "interpretation": "REMOVED avoided signed old losses + ADDED signed new P/L + UNCHANGED weight effect; exact current-book difference, not isolated intervention causal effect."}


def long_protection(holdings, dates, folder):
    rows = []
    baseline = holdings["MOM60"].w.gt(0)
    for strategy, h in holdings.items():
        active = h.w.gt(0)
        intersection = (baseline & active).groupby("Date").sum()
        union = (baseline | active).groupby("Date").sum()
        overlap = intersection/baseline.groupby("Date").sum()
        r = pd.DataFrame({"strategy": strategy, "long_jaccard": intersection/union, "long_membership_overlap_vs_MOM60": overlap,
            "long_gross": h.gross.where(active,0).groupby("Date").sum(),
            "long_cost": h.long_cost.groupby("Date").sum(), "long_turnover": h.long_turnover.groupby("Date").sum()}).loc[dates]
        r["long_net"] = r.long_gross-r.long_cost
        rows.append(r.reset_index())
    daily = pd.concat(rows)
    daily.to_csv(folder/"long_protection_daily.csv", index=False)
    rows = []
    for strategy, d in daily.groupby("strategy"):
        d = d.set_index("Date")
        for scope, ds in scopes(dates):
            rows.append({"strategy": strategy, "scope": scope, **{k:d.loc[ds,k].mean()*(252 if k in ["long_gross","long_net","long_cost"] else 1) for k in d if k!="strategy"}})
    pd.DataFrame(rows).to_csv(folder/"long_protection.csv", index=False)


def concentration(f, holdings, accounts, folder):
    dates = f.index.get_level_values("Date").unique().sort_values()
    keys = [f.index.get_level_values("Date"), f.Sector33Code.fillna("UNKNOWN")]
    exposures, daily_stats, contributions, top2 = [], [], [], []
    for strategy, h in holdings.items():
        parts = pd.DataFrame({"short_weight": (-h.w).clip(lower=0), "Q1_count": h.q.eq(0).astype(float), "Q2_count": h.q.eq(1).astype(float),
            "gross": h.gross.fillna(0), "net": h.net, "cost": h.cost,
            "short_gross": h.gross.where(h.w<0,0).fillna(0), "short_cost": h.short_cost,
            "short_net": h.gross.where(h.w<0,0).fillna(0)-h.short_cost}, index=f.index).groupby(keys).sum()
        parts.index.names = ["Date", "sector"]
        e = parts.copy()
        for col in ["short_weight", "Q1_count", "Q2_count"]:
            shares = parts[col]/parts[col].groupby("Date").transform("sum")
            e[col+"_share"] = shares
            stats = pd.DataFrame({"strategy": strategy, "measure": col, "HHI": shares.pow(2).groupby("Date").sum(), "max_sector_weight": shares.groupby("Date").max()})
            daily_stats.append(stats.reset_index())
        e["strategy"] = strategy
        exposures.append(e.reset_index())
        for scope, ds in scopes(dates):
            now = parts.loc[parts.index.get_level_values("Date").isin(ds)].groupby("sector").sum()/len(ds)*252
            for sector, r in now.iterrows():
                contributions.append({"strategy": strategy, "scope": scope, "sector": sector, **{"annual_"+k:r[k] for k in ["gross","net","cost","short_gross","short_net","short_cost"]}})
            for measure in ["gross", "short_gross", "short_weight"]:
                leaders = now.nlargest(2, measure)
                top2.append({"strategy": strategy, "scope": scope, "selection": measure, "sectors": ",".join(leaders.index.astype(str)),
                    "annual_gross": leaders.gross.sum(), "annual_net": leaders.net.sum(), "annual_short_gross": leaders.short_gross.sum(),
                    "annual_short_net": leaders.short_net.sum(), "short_exposure_share": leaders.short_weight.sum()/now.short_weight.sum(),
                    "share_of_total_gross": leaders.gross.sum()/now.gross.sum() if now.gross.sum()!=0 else np.nan})
        totals = parts[["gross","net","cost"]].groupby("Date").sum()
        assert np.allclose(totals, accounts[strategy][["gross","net","cost"]], atol=1e-15, rtol=0)
    pd.concat(exposures).to_csv(folder/"sector_exposure_daily.csv", index=False)
    ds = pd.concat(daily_stats)
    ds.to_csv(folder/"sector_concentration_daily.csv", index=False)
    rows=[]
    for (strategy, measure), block in ds.groupby(["strategy", "measure"]):
        for scope, dateset in scopes(dates):
            b = block.loc[block.Date.isin(dateset)]
            rows.append({"strategy":strategy,"measure":measure,"scope":scope,"mean_HHI":b.HHI.mean(),"mean_max_sector_weight":b.max_sector_weight.mean(),"max_sector_weight":b.max_sector_weight.max()})
    pd.DataFrame(rows).to_csv(folder/"sector_concentration.csv", index=False)
    pd.DataFrame(contributions).to_csv(folder/"sector_contribution.csv", index=False)
    pd.DataFrame(top2).to_csv(folder/"top2_sector_contribution.csv", index=False)


def decide(accounts, cover, boot):
    result = {}
    b = metrics(accounts["MOM60"])
    bex = metrics(accounts["MOM60"].loc[accounts["MOM60"].index.year!=2016])
    raw = cover.loc[(cover.scope=="POOLED")&(cover.sector=="ALL"),"agreement_finite"].iloc[0]
    for name in sc.CANDIDATES:
        d=accounts[name]; m=metrics(d); ex=metrics(d.loc[d.index.year!=2016])
        full=[metrics(d.loc[d.index.year==y]) for y in range(2011,2016)]
        baseline_full=[metrics(accounts["MOM60"].loc[accounts["MOM60"].index.year==y]) for y in range(2011,2016)]
        n_improvements=sum(c["net_sharpe"]>a["net_sharpe"] for c,a in zip(full,baseline_full))
        feasibility={"pooled_RankIC_positive":m["rankic"]>0,"pooled_GrossSR_positive":m["gross_sharpe"]>0,"ex2016_GrossSR_positive":ex["gross_sharpe"]>0,
            "gross_positive_3of5":sum(c["annual_gross"]>0 for c in full)>=3,"raw_context_coverage_ge95pct":raw>=.95,"turnover_le1p25_MOM60":m["turnover"]<=1.25*b["turnover"]}
        adoption={"pooled_NetSR_beats_MOM60":m["net_sharpe"]>b["net_sharpe"],"ex2016_NetSR_beats_MOM60":ex["net_sharpe"]>bex["net_sharpe"],
            "NetSR_improvement_4of5":n_improvements>=4,"bootstrap_lower_gt0":boot[name]["low"]>0,"annualNet_beats_MOM60":m["annual_net"]>b["annual_net"],
            "turnover_le1p25_MOM60":m["turnover"]<=1.25*b["turnover"],"Shortgross_ge_MOM60":m["annual_short_gross"]>=b["annual_short_gross"],
            "Shortnet_ge_MOM60":m["annual_short_net"]>=b["annual_short_net"],"Longnet_positive":m["annual_long_net"]>0,"Qmonotonicity_positive":m["q_monotonicity"]>0}
        dg=m["annual_short_gross"]-b["annual_short_gross"]; dn=m["annual_short_net"]-b["annual_short_net"]
        ratio=dg/dn if dn>0 else np.nan
        if name=="SHORT_DISAGREE_VETO": adoption["Shortnet_improvement_positive_gross_share_ge50pct"]=dn>0 and ratio>=.5
        failed=[k for k,v in {**feasibility,**adoption}.items() if not v]
        result[name]={"decision":"ELIGIBLE_TRAIN_ONLY" if not failed else "REJECT","feasibility":feasibility,"adoption":adoption,"failed_checks":failed,
            "full_year_netSR_improvements":n_improvements,"raw_context_coverage":raw,"delta_annual_short_gross":dg,"delta_annual_short_net":dn,"gross_share_of_short_net_improvement":ratio}
    return safe(result)


def standalone_smoke(stage, output, signals):
    smoke=output/"adapter_smoke"; smoke.mkdir(); (smoke/"input").symlink_to(stage,target_is_directory=True)
    result=output/"audit/standalone_smoke.json"
    lines=["import sys,time,resource,json,os",f"sys.path.insert(0,{str(ROOT)!r})","from research import firewall; firewall.install()",
        f"sys.path.insert(0,{str(ROOT/'stock_comp_2026/strategies/dm_sector_confirmation')!r})","import submission",f"os.chdir({str(smoke)!r})","t=time.monotonic()",
        "default=submission.predict()",f"default.to_parquet({str(output/'predictions/standalone.parquet')!r})"]
    for name in sc.CANDIDATES:
        lines += [f"p=submission.predict(candidate={name!r})",f"p.to_parquet({str(output/'predictions'/('standalone_'+name+'.parquet'))!r})"]
    lines += ["r={'status':'PASS','seconds':time.monotonic()-t,'rows':len(default),'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),'opened':sorted(firewall.ACCESSES),'no_argument_predict':True}",f"open({str(result)!r},'w').write(json.dumps(r,indent=2)+'\\n')"]
    (smoke/"script.py").write_text("\n".join(lines)+"\n")
    completed=subprocess.run([sys.executable,str(smoke/"script.py")],capture_output=True,text=True,timeout=120)
    (output/"logs/standalone.log").write_text(completed.stdout+completed.stderr)
    assert completed.returncode==0,completed.stderr
    exact(signals["SHORT_DISAGREE_VETO"].to_frame(),pd.read_parquet(output/"predictions/standalone.parquet"))
    for name in sc.CANDIDATES:
        exact(signals[name].to_frame(),pd.read_parquet(output/"predictions"/('standalone_'+name+'.parquet')))
    record=json.loads(result.read_text());record["bitwise_research_parity_all_candidates"]=True;dump(result,record)


def report_results(config, output, results, decision, boot):
    report=ROOT/config["report_dir"];report.mkdir(parents=True,exist_ok=True)
    assert not (report/"REPORT.md").exists(),"Existing results must not be overwritten"
    for sub in ["metrics","audit"]: shutil.copytree(output/sub,report/sub,dirs_exist_ok=True)
    columns=["strategy","rankic","gross_sharpe","net_sharpe","annual_net","turnover","annual_cost","annual_short_gross","annual_short_net","annual_long_net"]
    lines=[f"# {config['experiment_id']} — Sector Momentum as context", "",
        "**Decision: " + ", ".join(n+"="+d["decision"] for n,d in decision.items())+".**", "",
        f"Run `{output.relative_to(ROOT)}`. Exactly two pre-registered performance trials, no rescue. Known Train development evidence; no independent OOS, Historical Valid, release, Freeze or submission. Prior06/07 definitions, decisions and hashes remain unchanged.","",
        "Primary2011–2015 follows below. POOLED additionally includes2016 partial for continuity with preceding experiments and fixed pooled gates.2016 is shown separately and never counted in4/5 full-year improvement. Each fold's final2 exchange dates purged; t+2 maturity verified. No fitted model; expanding causal history. Same dates/accounts for all strategies.","",
        "## Primary2011–2015 (EX2016)","",table(results.loc[results.scope=="EX2016"],columns),"",
        "## Pooled including2016 partial", "",table(results.loc[results.scope=="POOLED"],columns),"",
        "## Fold/year metrics", "",table(results.loc[results.scope.isin([str(y) for y in range(2011,2017)])],["strategy","scope","gross_sharpe","net_sharpe","annual_net","turnover","annual_short_gross","annual_short_net","annual_long_net"]),"",
        "Control: residual60 skip1 -> same-date centered rank -> unchanged EWMA(.25). Candidates: fixed raw Stock/sector context operation -> unchanged EWMA(.25), once. Sector common includes own StockMom, PIT33 exact Date/Code membership, minimum5 finite. This operational strategy comparison also changes transform order; it cannot identify a pure isolated sector-context causal effect. No order-matched third candidate was evaluated.","",
        "A(++), B(+-), C(-+), D(--), ZERO_OR_MISSING use raw signs. A keeps A/D only. B neutralizes C only; exact common zero retains negative stock. Missing/nonfinite context neutral0, raw coverage computed before neutralization. No thresholds/weights/alpha/horizon search.","",
        "## Fixed gates", "", "```json",json.dumps(safe(decision),indent=2),"```","",
        "## Paired circular20-session bootstrap ΔNet Sharpe vs MOM60", "", "```json",json.dumps(safe(boot),indent=2),"```","",
        "2000 paired draws, seed20261002,95% percentile interval; blocks over concatenated matched eligible sessions including purge gaps. Describes known-Train sampling uncertainty, not independent OOS or multiplicity-adjusted proof.","",
        "## Accounting and mechanism definitions", "",
        "P/L values are decimal fractions. Annual P/L/cost=daily arithmetic mean×252, Sharpe=sample-SD daily mean/SD×sqrt252. HAC5 RankIC t and hit ratio, additive/compound DD and Q1-Q5/monotonicity saved for every scope. Official Code-order5 quintiles and10bp one-way cost, computed continuously before date filtering. Official missing-target cost omission matches scorer; conservative all-position cost/net also saved. Short uses signed market-residual P/L, not borrow-cost-adjusted raw short security returns. Side gross/net/cost reconcile within1e-15.","",
        "State attribution is original-book contribution, NOT standalone state performance. Exit cost is assigned to the current row/state even if its current position is zero. State gross/net/cost and side turnover sum to full accounts. Equal-row and equal-date target means are both saved; RankIC is equal-date with raw Stock and each strategy score.","",
        "State transitions count adjacent exchange-date observations; missing-row gaps reset. Full observed spell lengths intersecting evaluation are retained, left/right gaps and sample boundaries marked censored (no survival adjustment).1/5-day persistence is uninterrupted same-state across next1/5 contiguous observed sessions; denominator excludes unavailable future horizons. This future-looking diagnostic never enters signals. C entry/exit turnover share is turnover on the transitioning names on the event date, not a causal estimate of all delayed EWMA or replacement turnover.","",
        "Short replacement memberships are official Q1+Q2; Q1 and Q2 membership also classified separately. REMOVED=base short only, ADDED=candidate short only, UNCHANGED=both. Exact ΔShortgross=−old removed signed P/L+new added signed P/L+unchanged weight difference. Cost effect=old Short cost−new Short cost includes every row, including exits; ΔShortnet=ΔShortgross+cost effect. C original-Short all/removed/retained cohorts and subsequent residual targets saved. Raw C veto does not guarantee immediate portfolio exit after EWMA/global reranking. Replacement effects cannot be uniquely attributed to C because transform order differs.","",
        "Rank autocorrelation uses adjacent-date average percentile ranks. Quintile retention uses official Code ties; tail spells use original full contiguous Q1/Q5 lengths. Long protection saves gross/net/turnover and membership Jaccard/base retention. Sector concentration uses side-normalized Short weights and Q1/Q2 name shares, daily HHI/max, side contributions and top2 selected by totalgross/Shortgross/Shortexposure; signed contribution shares may exceed100% with offsetting losses. No reranking/exclusion/filter derives from diagnostics.","",
        "## Saved evidence", "",
        "metrics/overall_metrics.csv,fold_metrics.csv,year_metrics.csv,incremental.csv,long_short.csv,quintiles.csv,bootstrap.{json,csv},candidate_decision.json,side_cost_decomposition.csv; state_attribution*.csv,state_transitions*.csv,state_duration_persistence.csv,state_spells.csv,C_state_duration_distribution.csv; daily_* accounts,rank_persistence*.csv,holding_spells.csv,rank_change*.csv,state_triggered_turnover*.csv; replacement_summary.csv,replacement_daily.csv,replacement_sector_distribution.csv,removed_added_unchanged_names.parquet,C_veto_short_cohorts.csv,C_original_short_names.parquet,short_replacement_decomposition*.csv; long_protection*.csv; sector_exposure_daily.csv,sector_concentration*.csv,sector_contribution.csv,top2_sector_contribution.csv; coverage.csv.","",
        "audit/ includes source scan, full raw/context/state/veto/EWMA/final/control bitwise prefix/truncation audit at3 cutoffs, raw/common/control parity, prior artifact/hash preservation, firewall denials and pre-target prediction reads, exact index/finite coverage, standalone research/adapter parity, official weight/net parity, purge, mechanism reconciliation and runtime resources. All four input sources individually/jointly mutated, future-only stocks, sector changes and source-row deletions; shuffle/rebuild exact. No target influences feature construction; no training path exists.","",
        "Runtime firewall is a best-effort Python guard. Exercised mutations provide evidence, not a proof for every possible input. Dataset survivorship, independent OOS, borrow costs and later deployment/zip execution remain outside this research. Neutralization does not remedy raw availability. Technical failures, if any, stay in artifacts; no additional candidate after results."]
    (report/"REPORT.md").write_text("\n".join(lines)+"\n")
    exp=ROOT/"experiments"/config["experiment_id"]
    (exp/"decision.md").write_text(f"# {config['experiment_id']} decision\n\nExactly2 fixed Train-only trials, previous REJECT evidence unchanged.\n\n"+"\n".join(f"- **{n}**: {d['decision']}. Failed checks: {', '.join(d['failed_checks']) or 'none'}." for n,d in decision.items())+f"\n\nNo rescue, extra trial, Valid, Freeze or submission. Known Train evidence, not independent OOS. [Report](../../{config['report_dir']}/REPORT.md). Run `{output.relative_to(ROOT)}`.\n")
    meta=json.loads((exp/"experiment.json").read_text());meta.update(status="rejected" if all(d["decision"]=="REJECT" for d in decision.values()) else "completed",actual_trials=2,run_id=output.name,report=f"{config['report_dir']}/REPORT.md");dump(exp/"experiment.json",meta)
    with (ROOT/"experiments/GRAVEYARD.md").open("a") as stream:
        rejected=[n for n,d in decision.items() if d["decision"]=="REJECT"]
        if rejected:
            stream.write(f"\n## {config['experiment_id']}: Sector context confirmation\n\n[Decision]({config['experiment_id']}/decision.md) / [Report](../{config['report_dir']}/REPORT.md). Exactly2 fixed context-before-EWMA trials, known Train, no Valid/Freeze/rescue. Prior06/07 remain unchanged.\n\n")
            pooled=results.loc[results.scope=="POOLED"].set_index("strategy")
            for n in rejected:
                m=pooled.loc[n];stream.write(f"- **{n}** — Gross/Net SR{m.gross_sharpe:.4f}/{m.net_sharpe:.4f}, turnover{m.turnover:.5f}, Shortgross/net{m.annual_short_gross:+.3%}/{m.annual_short_net:+.3%}. REJECT: {', '.join(decision[n]['failed_checks'])}.\n")
            stream.write("\nRejects these fixed operational strategies; no tuning/filters or independent OOS claim.\n")


def main_work(config, output, run):
    started=time.monotonic();stage=output/"stage";stage.mkdir()
    data_hashes={}
    for n in list(sc.INPUT_COLUMNS)+["target_1day"]:
        source=ROOT/config["input_dir"]/f"{n}_train.parquet";(stage/source.name).symlink_to(source);data_hashes[source.name]=sha(source)
    prior_files=[];prior_score=None;prior_runs={}
    for eid in config["prior_experiments"]:
        exp=ROOT/"experiments"/eid;meta=json.loads((exp/"experiment.json").read_text())
        assert meta["status"] in ["rejected","completed"]
        pr=ROOT/"artifacts"/eid/meta["run_id"];saved=json.loads((pr/"run.json").read_text());assert saved["status"]=="completed"
        score=pr/"predictions/scores.parquet";assert sha(score)==saved["artifact_sha256"]["predictions/scores.parquet"]
        prior_runs[eid]={"path":str(pr.relative_to(ROOT)),"scores_sha256":sha(score)}
        prior_files += list(exp.glob("*"))+list((ROOT/"reports"/eid).rglob("*"))+list((ROOT/"stock_comp_2026/strategies"/meta["strategy"]).glob("*.py"))
        if eid==config["prior_experiments"][-1]:prior_score=score
    prior_hashes={str(p.relative_to(ROOT)):sha(p) for p in prior_files if p.is_file()}
    prediction_paths=[output/"predictions"/(name+".parquet") for name in ["features","scores","standalone"]+["standalone_"+n for n in sc.CANDIDATES]]
    diagnostic_parquets=[output/"metrics"/name for name in ["removed_added_unchanged_names.parquet", "C_original_short_names.parquet"]]
    firewall.install(allowed_artifacts=prediction_paths+diagnostic_parquets+[prior_score])
    code_paths=[Path(__file__),ROOT/"research/evaluation.py",ROOT/"research/firewall.py",ROOT/"research/experiments/sector_momentum.py",ROOT/"research/experiments/hierarchical_momentum.py",ROOT/"stock_comp_2026/evaluate_script.py",ROOT/"stock_comp_2026/strategies/dm_trainonly/features.py"]
    for slug in ["dm_sector_confirmation","dm_sector_momentum","dm_hierarchical_momentum"]:code_paths+=sorted((ROOT/"stock_comp_2026/strategies"/slug).glob("*.py"))
    code_paths+=sorted((ROOT/"tests/strategies/dm_sector_confirmation").glob("*.py"))
    code_hashes={str(p.relative_to(ROOT)):sha(p) for p in code_paths}
    for p in code_paths:
        dest=output/"code"/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    run.update(status="running",command=sys.argv,code_sha256=code_hashes,train_data_sha256=data_hashes,prior_evidence_sha256=prior_hashes,prior_runs=prior_runs,actual_trials=0,
        environment={"python":platform.python_version(),"pandas":pd.__version__,"numpy":np.__version__,"scipy":scipy.__version__,"pyarrow":pyarrow.__version__,"platform":platform.platform()})
    dump(output/"run.json",run)
    exp=ROOT/"experiments"/config["experiment_id"]
    prereg=json.loads((exp/"preregistration.json").read_text())
    assert prereg["plan_sha256"]==sha(output/"plan.md") and prereg["config_sha256"]==sha(output/"config.json")
    dump(output/"audit/pre_result_lock.json",{"at_utc":datetime.now(timezone.utc).isoformat(),"plan_sha256":sha(output/"plan.md"),"config_sha256":sha(output/"config.json"),"code_sha256":code_hashes,"prior_evidence_sha256":prior_hashes,"target_read":False,"trials":list(sc.CANDIDATES),"max_trials":2,"preregistration":prereg})
    dump(output/"audit/source_scan.json",source_scan())
    inputs=sc.load_train(stage);f=sc.build_features(inputs)
    assert f.index.equals(sc.canonical(inputs["raw_return_1day"]).index)
    assert np.isfinite(f[list(sc.CANDIDATES.values())+["MOM60"]].to_numpy()).all()
    dump(output/"audit/primitive_parity.json",primitive_parity(inputs,f))
    exact(f.MOM60,pd.read_parquet(prior_score,columns=["MOM60"]).MOM60)
    dump(output/"audit/prior_control_parity.json",{"status":"PASS","rows":len(f),"bitwise":True,"source":str(prior_score.relative_to(ROOT)),"no_prior_candidate_performance_rerun":True})
    dump(output/"audit/prefix_invariance.json",prefix_audit(inputs,f,config))
    signals={n:sc.score(f,n) for n in sc.CANDIDATES};signals["MOM60"]=f.MOM60.rename("Return")
    for n in sc.CANDIDATES:exact(signals[n].to_frame(),submission.predict(stage,n))
    dump(output/"audit/adapter_parity.json",{"status":"PASS","rows":len(f),"all_candidates_bitwise":True})
    standalone_smoke(stage,output,signals)
    denied=[]
    for name in ["target_1day_valid.parquet","raw_target_1day_train.parquet","unknown.parquet"]:
        try:pd.read_parquet(stage/name)
        except PermissionError as err:denied.append({"path":name,"denial":str(err)})
        else:raise AssertionError("Forbidden input accepted")
    assert not any("target_1day" in p for p in firewall.ACCESSES)
    dump(output/"audit/firewall_denials.json",{"status":"PASS","cases":denied})
    dump(output/"audit/prediction_source_firewall.json",{"status":"PASS","opened":sorted(firewall.ACCESSES),"prediction_and_audit_before_Train_target":True})
    f.to_parquet(prediction_paths[0]);pd.DataFrame(signals).to_parquet(prediction_paths[1])
    calendar=f.index.get_level_values("Date").unique().sort_values();dates,purge=fold_dates(calendar,[x["year"] for x in config["walk_forward_folds"]]);dates=dates.rename("Date")
    dump(output/"audit/purge.json",{"status":"PASS","folds":purge})
    cover=coverage(f,output/"metrics",dates)
    dump(output/"audit/coverage.json",{"status":"PASS","rows":len(f),"exact_index":True,"finite_prediction":True,"raw_context_before_neutral":True})
    print("Raw/context/score/adapter prefix audit PASS; now read Train target",flush=True)
    tf=sc.canonical(pd.read_parquet(stage/"target_1day_train.parquet"));assert tf.index.equals(f.index);target=tf.Return
    daily,holdings,parity={},{},{}
    for n,s in signals.items():
        daily[n],h,parity[n]=account(s,target);holdings[n]=enrich_holdings(h)
        daily[n].to_csv(output/f"metrics/daily_{n}.csv")
        if n in sc.CANDIDATES:run["actual_trials"]+=1;dump(output/"run.json",run)
        print(f"fixed trial/account {n}: saved",flush=True)
    dump(output/"audit/official_accounting_parity.json",{"status":"PASS","strategies":parity})
    accounts={n:d.loc[dates] for n,d in daily.items()};rows=[]
    for n,d in daily.items():
        for scope,ds in [("ALL_TRAIN",calendar)]+scopes(dates):
            rows.append({"strategy":n,"scope":scope,**metrics(d.loc[ds]),"long_turnover":d.loc[ds,"long_turnover"].mean(),"short_turnover":d.loc[ds,"short_turnover"].mean()})
    results=pd.DataFrame(rows);results.to_csv(output/"metrics/metrics.csv",index=False)
    results.loc[results.scope.isin(["POOLED","EX2016"])].to_csv(output/"metrics/overall_metrics.csv",index=False)
    for name in ["fold_metrics","year_metrics"]:results.loc[results.scope.isin([str(y) for y in range(2011,2017)])].to_csv(output/f"metrics/{name}.csv",index=False)
    results[["strategy","scope"]+[k for k in results if "long" in k or "short" in k]].to_csv(output/"metrics/long_short.csv",index=False)
    results[["strategy","scope"]+[k for k in results if k.startswith("q")]].to_csv(output/"metrics/quintiles.csv",index=False)
    increments=[]
    for n in sc.CANDIDATES:
        for scope in results.scope.unique():
            c=results.loc[(results.strategy==n)&(results.scope==scope)].iloc[0];b=results.loc[(results.strategy=="MOM60")&(results.scope==scope)].iloc[0]
            keys=["rankic","gross_sharpe","net_sharpe","turnover","annual_cost","annual_gross","annual_net","annual_short_gross","annual_short_net","annual_short_cost","annual_long_gross","annual_long_net","annual_long_cost","long_turnover","short_turnover"]
            increments.append({"strategy":n,"scope":scope,"control":"MOM60",**{"delta_"+k:c[k]-b[k] for k in keys}})
    increment=pd.DataFrame(increments)
    assert np.allclose(increment.delta_annual_short_net,increment.delta_annual_short_gross-increment.delta_annual_short_cost,atol=1e-15,rtol=0)
    increment.to_csv(output/"metrics/incremental.csv",index=False)
    increment[["strategy","scope","control"]+[k for k in increment if "cost" in k or "turnover" in k or "short" in k or "long" in k]].to_csv(output/"metrics/side_cost_decomposition.csv",index=False)
    boot={n:evaluation.bootstrap_delta(accounts["MOM60"].net,accounts[n].net,**{k:config["bootstrap"][k] for k in ["seed","block","reps"]}) for n in sc.CANDIDATES}
    dump(output/"metrics/bootstrap.json",boot);pd.DataFrame([{"strategy":k,"control":"MOM60",**v} for k,v in boot.items()]).to_csv(output/"metrics/bootstrap.csv",index=False)
    decision=decide(accounts,cover,boot);dump(output/"metrics/candidate_decision.json",decision)
    print("2/2 trials complete; mechanism diagnostics only",flush=True)
    fe=f.loc[f.index.get_level_values("Date").isin(dates)];te=target.loc[fe.index];he={n:h.loc[fe.index] for n,h in holdings.items()}
    tr=transitions(f,calendar,dates,output/"metrics")
    turnover_attribution(f,tr,holdings,dates,output/"metrics")
    persistence(signals,holdings,calendar,dates,output/"metrics");rank_changes(signals,calendar,dates,output/"metrics")
    audits={"agreement":agreement(fe,te,signals,he,accounts,output/"metrics"),"replacement":replacement(fe,te,he["MOM60"],he["SHORT_DISAGREE_VETO"],accounts,output/"metrics")}
    long_protection(he,dates,output/"metrics");concentration(fe,he,accounts,output/"metrics")
    dump(output/"audit/mechanism_reconciliation.json",{"status":"PASS",**audits})
    for p,expected in prior_hashes.items():assert sha(ROOT/p)==expected,p
    for p,expected in code_hashes.items():assert sha(ROOT/p)==expected,p
    dump(output/"audit/prior_evidence_unchanged.json",{"status":"PASS","prior":config["prior_experiments"],"files":len(prior_hashes),"hashes":prior_hashes})
    firewall.save(output/"audit/firewall.json")
    resources={"status":"PASS","elapsed_seconds":time.monotonic()-started,"peak_rss_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=="darwin" else 1024),"actual_trials":2,"valid_evaluation":False}
    dump(output/"audit/resources.json",resources);report_results(config,output,results,decision,boot)
    artifacts={str(p.relative_to(output)):sha(p) for sub in ["audit","metrics","predictions","code"] for p in (output/sub).rglob("*") if p.is_file()}
    run.update(resources);run.update(status="completed",exit_code=0,completed_at_utc=datetime.now(timezone.utc).isoformat(),artifact_sha256=artifacts,candidate_decisions=decision)
    dump(output/"run.json",run);print(json.dumps(safe({"decisions":decision,"resources":resources}),indent=2),flush=True)


def recover_report(config, output, run, source):
    """Complete publication from a failed copy step, with zero new performance trials."""
    saved=json.loads((source/"run.json").read_text())
    assert saved["status"]=="failed" and saved["actual_trials"]==2
    assert saved["error"].startswith("Error: ") and "Train-only parquet guard denied" in saved["error"]
    assert sha(source/"config.json")==sha(output/"config.json") and sha(source/"plan.md")==sha(output/"plan.md")
    allowed=list((source/"predictions").glob("*.parquet"))+list((source/"metrics").glob("*.parquet"))
    allowed += [ROOT/config["report_dir"]/"metrics"/name for name in ["removed_added_unchanged_names.parquet", "C_original_short_names.parquet"]]
    firewall.install(allowed_artifacts=allowed)
    source_hashes={str(p.relative_to(source)):sha(p) for sub in ["code","audit","metrics","predictions","logs"] for p in (source/sub).rglob("*") if p.is_file()}
    source_hashes["run.json"]=sha(source/"run.json")
    for path,expected in saved["code_sha256"].items():
        assert sha(source/"code"/path)==expected,path
        if path.startswith("stock_comp_2026/strategies/"):
            assert sha(ROOT/path)==expected,path
    for path,expected in saved["prior_evidence_sha256"].items():assert sha(ROOT/path)==expected,path
    required=["source_scan","primitive_parity","prefix_invariance","adapter_parity","standalone_smoke","firewall_denials","prediction_source_firewall","purge","coverage","official_accounting_parity","mechanism_reconciliation","prior_evidence_unchanged","resources"]
    for name in required:assert json.loads((source/"audit"/(name+".json")).read_text())["status"]=="PASS",name
    run.update(status="running",actual_trials=0,source_actual_trials=2,mode="report_only",source_run=str(source.relative_to(ROOT)),source_artifact_sha256=source_hashes,
        command=sys.argv,code_sha256={str(Path(__file__).relative_to(ROOT)):sha(Path(__file__))},valid_evaluation=False)
    dump(output/"run.json",run)
    destination=output/"code"/Path(__file__).relative_to(ROOT);destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(Path(__file__),destination)
    results=pd.read_csv(source/"metrics/metrics.csv",dtype={"scope":str},float_precision="round_trip")
    cover=pd.read_csv(source/"metrics/coverage.csv",dtype={"scope":str,"sector":str},float_precision="round_trip")
    boot=json.loads((source/"metrics/bootstrap.json").read_text());decision=json.loads((source/"metrics/candidate_decision.json").read_text())
    accounts={n:pd.read_csv(source/"metrics"/("daily_"+n+".csv"),index_col="Date",parse_dates=["Date"],float_precision="round_trip") for n in list(sc.CANDIDATES)+["MOM60"]}
    calendar=accounts["MOM60"].index;dates,_=fold_dates(calendar,[x["year"] for x in config["walk_forward_folds"]]);accounts={n:d.loc[dates] for n,d in accounts.items()}
    assert decide(accounts,cover,boot)==decision
    report_results(config,source,results,decision,boot)
    report=ROOT/config["report_dir"]
    with (report/"REPORT.md").open("a") as stream:
        stream.write(f"\nInitial research run completed2/2 trials and all scientific audits, then failed copying its generated diagnostic parquet because explicit artifact allowlisting was missing. Failed run unchanged. This report was recovered in `{output.relative_to(ROOT)}` using hash-checked saved metrics/predictions/audits only:0 new performance trials, no inference/backtest/bootstrap rerun. Float CSV round_trip reload preserves saved values. Allowlist fix changes artifact publication only.\n")
    for path,expected in source_hashes.items():assert sha(source/path)==expected,path
    report_hashes={str(p.relative_to(report)):sha(p) for p in report.rglob("*") if p.is_file()}
    verification={"status":"PASS","source_run":str(source.relative_to(ROOT)),"source_artifact_sha256":source_hashes,"source_unchanged":True,"new_performance_trials":0,"total_performance_trials":2,"report_sha256":report_hashes,"cached_decision_reproduced":True}
    dump(output/"audit/report_recovery.json",verification);firewall.save(output/"audit/firewall.json")
    exp=ROOT/"experiments"/config["experiment_id"];meta=json.loads((exp/"experiment.json").read_text());meta["report_recovery_run_id"]=output.name;dump(exp/"experiment.json",meta)
    run.update(status="completed",exit_code=0,completed_at_utc=datetime.now(timezone.utc).isoformat(),candidate_decisions=decision,
        artifact_sha256={str(p.relative_to(output)):sha(p) for sub in ["audit","code"] for p in (output/sub).rglob("*") if p.is_file()})
    dump(output/"run.json",run);print(json.dumps({"status":"PASS","report_only":True,"actual_trials":0,"total_performance_trials":2,"decisions":decision},indent=2),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument("--config",required=True);p.add_argument("--output",required=True);p.add_argument("--report-only-source");args=p.parse_args()
    output=Path(args.output).resolve();config=json.loads(Path(args.config).read_text())
    assert Path(args.config).resolve()==output/"config.json"
    assert config["data_split"]=="train" and config["valid_evaluation"] is False and config["max_trials"]==2
    assert [x["trial_id"] for x in config["trials"]]==list(sc.CANDIDATES)
    assert config["parameters"]=={"horizon":60,"skip":1,"min_periods":60,"sector33_min_finite_members":5,"alpha":.25,"ewm_adjust":False,"relisting_gap":20,"neutral_before_ewma":0}
    assert config["purge_trading_days"]==2 and config["bootstrap"]["block"]==20 and config["bootstrap"]["reps"]==2000 and config["bootstrap"]["seed"]==20261002
    run=json.loads((output/"run.json").read_text());assert run["status"]=="prepared"
    try:
        if args.report_only_source:recover_report(config,output,run,Path(args.report_only_source).resolve())
        else:main_work(config,output,run)
    except BaseException as error:
        run.update(status="failed",exit_code=1,error=f"{type(error).__name__}: {error}",completed_at_utc=datetime.now(timezone.utc).isoformat());dump(output/"run.json",run)
        if firewall._PATCHED:firewall.save(output/"audit/firewall.json")
        raise


if __name__=="__main__":main()
