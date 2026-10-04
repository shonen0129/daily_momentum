"""Two fixed transform-order matched Train-only rules and mechanism diagnostics."""
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
from stock_comp_2026.strategies.dm_raw_ewma_ablation import features as sc, primitives, submission
from stock_comp_2026.strategies.dm_hierarchical_momentum import features as hierarchy
from stock_comp_2026.strategies.dm_trainonly import features as old
from stock_comp_2026.strategies.dm_sector_confirmation import features as previous08
from research.experiments.sector_confirmation import scopes, enrich_holdings, agreement, transitions, turnover_attribution, concentration

STATES = ["A", "B", "C", "D", "ZERO_OR_MISSING"]


def source_scan():
    paths = sorted((ROOT / "stock_comp_2026/strategies/dm_raw_ewma_ablation").glob("*.py"))
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
            "manual_review": "Exact same-date PIT projection/self-inclusive finite common min5; residual60 shift1; raw signs/context before existing Code EWMA; raw-order matched, no labels or fitting."}


def prefix_audit(inputs, base, config):
    cases = []
    for i, cutoff in enumerate(config["prefix_cutoffs"]):
        date = pd.Timestamp(cutoff)
        idx = base.index[base.index.get_level_values("Date") <= date]
        for name in list(inputs) + ["ALL", "TRUNCATION", "FUTURE_STOCKS", "FUTURE_SECTORS", "SUFFIX_DELETION"]:
            changed = dict(inputs)
            for j, (source, frame) in enumerate(inputs.items()):
                if name == "TRUNCATION":
                    changed[source] = frame.loc[frame.index.get_level_values("Date") <= date]
                elif name in [source, "ALL"]:
                    changed[source] = mutate(frame, source, date, config["random_seed"] + i*100+j)
            if name == "FUTURE_STOCKS":
                for source, frame in inputs.items():
                    if not isinstance(frame.index, pd.MultiIndex):
                        continue
                    new = frame.loc[frame.index.get_level_values("Date") > date].iloc[::499].copy()
                    new = new.loc[~new.index.get_level_values("Date").duplicated()]
                    new.index = pd.MultiIndex.from_arrays([new.index.get_level_values("Date"), ["FUTURE_ONLY"]*len(new)], names=["Date", "Code"])
                    changed[source] = pd.concat([frame, new])
            elif name == "FUTURE_SECTORS":
                changed["listed_info"] = inputs["listed_info"].copy()
                mask = changed["listed_info"].index.get_level_values("Date") > date
                changed["listed_info"].loc[mask, "Sector33Code"] = "NEW_SUFFIX_SECTOR"
            elif name == "SUFFIX_DELETION":
                changed = {source: frame.drop(frame.index[frame.index.get_level_values("Date") > date][::2]) for source, frame in inputs.items()}
            got = sc.build_features(changed).loc[idx]
            exact(base.loc[idx], got)
            for candidate in sc.CANDIDATES:
                exact(sc.score(base.loc[idx], candidate), sc.score(got, candidate))
            cases.append({"cutoff": cutoff, "source": name, "status": "PASS", "bitwise": True,
                          "prefix_rows": len(idx), "features": list(base), "scores": list(sc.CANDIDATES)})
        print(f"context prefix {cutoff}: all sources/membership/truncation PASS", flush=True)
    exact(base, sc.build_features(inputs))
    exact(base, sc.build_features({n: x.sample(frac=1, random_state=9) for n, x in inputs.items()}))
    exact(sc.build_control(inputs), sc.score(base, "RAW_EWMA_CONTROL"))
    changed = dict(inputs)
    changed["listed_info"] = inputs["listed_info"].copy()
    changed["listed_info"].loc[:, "Sector33Code"] = "ALL_HISTORY_CHANGED"
    exact(sc.build_control({k:v for k,v in inputs.items() if k != "listed_info"}), sc.score(sc.build_features(changed), "RAW_EWMA_CONTROL"))
    return {"status": "PASS", "control_independent_of_all_history_sectors": True, "cases": cases, "row_shuffle": True, "deterministic_rebuild": True,
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
    prior = previous08.build_features(inputs)
    for col in ["StockMom60_raw", "Sector33Code", "FiniteMembers", "Sector33Common_raw", "State", "ShortVeto_raw", "ShortVeto_ewm", "MOM60"]:
        exact(f[col], prior[col])
    exact(f.RawControl_ewm, primitives.smooth(f.StockMom60_raw.where(np.isfinite(f.StockMom60_raw), 0.), .25).rename("RawControl_ewm"))
    return {"status": "PASS", "prior08_veto_bitwise": True, "StockMom_and_MOM60_bitwise": True, "prior07_common_and_PIT_bitwise": True,
            "unchanged_primitive_sources": ["smooth", "segment_keys", "centered_rank"]}


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
        base_cost = base.short_cost if book == "SHORT_Q1_Q2" else base[book+"_cost"]
        cand_cost = candidate.short_cost if book == "SHORT_Q1_Q2" else candidate[book+"_cost"]
        r["base_cost"], r["candidate_cost"] = base_cost, cand_cost
        r["base_net"], r["candidate_net"] = bg-base_cost, cg-cand_cost
        r["delta_net"] = r.candidate_net-r.base_net
        r["cost_effect"] = base_cost-cand_cost
        r["weight_change_contribution"] = r.delta_gross
        for clas in ["REMOVED", "ADDED", "UNCHANGED", "OTHER"]:
            mask = category == clas
            rd = r.loc[mask]
            rows.append(rd.loc[mask & ((category != "OTHER") | base_cost.ne(0) | cand_cost.ne(0))].reset_index())
            daily = r[["base_gross", "candidate_gross", "delta_gross", "base_cost", "candidate_cost", "base_net", "candidate_net", "delta_net", "cost_effect", "weight_change_contribution"]].where(mask, 0).groupby("Date").sum().reindex(dates)
            daily["book"], daily["class"] = book, clas
            daily["rows"] = mask.groupby("Date").sum()
            daily["target_mean"] = target.where(mask).groupby("Date").mean()
            decomposition.append(daily.reset_index())
            for scope, ds in scopes(dates):
                subset = rd.loc[rd.index.get_level_values("Date").isin(ds)]
                stats.append({"book": book, "class": clas, "scope": scope, "rows": len(subset), "target_mean": subset.target.mean(),
                    "target_equal_date_mean": daily.loc[ds,"target_mean"].mean(),
                    **{"annual_"+col: daily.loc[ds,col].mean()*252 for col in ["base_gross", "candidate_gross", "delta_gross", "base_net", "candidate_net", "delta_net", "base_cost", "candidate_cost", "cost_effect", "weight_change_contribution"]},
                    **{col+suffix: getattr(subset[col], method)() for col in ["stock_mom", "sector_common"] for suffix, method in [("_mean", "mean"),("_std", "std"),("_median", "median")]},
                    **{col+f"_q{q:g}": subset[col].quantile(q) for col in ["stock_mom", "sector_common"] for q in [.05,.25,.75,.95]}})
                stats[-1].update(base_average_weight=subset.base_weight.mean(), candidate_average_weight=subset.candidate_weight.mean())
                for sector, block in subset.groupby("sector"):
                    sector_stats.append({"book": book, "class": clas, "scope": scope, "sector": sector, "rows": len(block),
                        "row_share": len(block)/len(subset), "target_mean": block.target.mean(),
                        "annual_delta_gross": block.delta_gross.sum()/len(ds)*252, "annual_delta_net": block.delta_net.sum()/len(ds)*252})
    pd.concat(rows).to_parquet(folder/"removed_added_unchanged_names.parquet", index=False)
    pd.DataFrame(stats).to_csv(folder/"replacement_summary.csv", index=False)
    pd.DataFrame(sector_stats).to_csv(folder/"replacement_sector_distribution.csv", index=False)
    rd = pd.concat(decomposition)
    rd.to_csv(folder/"replacement_daily.csv", index=False)
    subset = rd.loc[rd.book=="SHORT_Q1_Q2"]
    pivot = subset.pivot(index="Date", columns="class", values="delta_gross").reindex(dates, fill_value=0.)
    b, c = accounts["RAW_EWMA_CONTROL"], accounts["RAW_EWMA_SHORT_VETO"]
    pivot["delta_short_gross"] = c.short - b.short
    pivot["cost_effect"] = b.short_cost - c.short_cost
    pivot["delta_short_net"] = c.short_net - b.short_net
    assert np.allclose(pivot[["REMOVED", "ADDED", "UNCHANGED"]].sum(axis=1), pivot.delta_short_gross, atol=1e-15, rtol=0)
    assert np.allclose(pivot.delta_short_gross + pivot.cost_effect, pivot.delta_short_net, atol=1e-15, rtol=0)
    pivot.to_csv(folder/"short_replacement_decomposition_daily.csv")
    summaries = [{"scope": scope, **{"annual_"+k: pivot.loc[ds,k].mean()*252 for k in pivot}} for scope, ds in scopes(dates)]
    pd.DataFrame(summaries).to_csv(folder/"short_replacement_decomposition.csv", index=False)
    netpivot = subset.pivot(index="Date", columns="class", values="delta_net").reindex(dates, fill_value=0.)
    assert np.allclose(netpivot.sum(axis=1), pivot.delta_short_net, atol=1e-15, rtol=0)
    netpivot.to_csv(folder/"short_replacement_net_by_class_daily.csv")
    cohorts, cohort_sectors = [], []
    C_short = f.State.eq("C") & base.w.lt(0)
    masks = {"C_ORIGINAL_SHORT_ALL": C_short, "C_ORIGINAL_SHORT_REMOVED": C_short & candidate.w.ge(0),
             "C_ORIGINAL_SHORT_RETAINED": C_short & candidate.w.lt(0), "ALL_SHORT_REPLACEMENTS": base.w.ge(0) & candidate.w.lt(0)}
    for name, mask in masks.items():
        for scope, ds in scopes(dates):
            keep = mask & f.index.get_level_values("Date").isin(ds)
            cohorts.append({"cohort": name, "scope": scope, "rows": int(keep.sum()), "target_mean": target.loc[keep].mean(),
                "annual_base_short_gross": base.gross.where(keep & base.w.lt(0),0).fillna(0).sum()/len(ds)*252,
                "annual_candidate_short_gross": candidate.gross.where(keep & candidate.w.lt(0),0).fillna(0).sum()/len(ds)*252,
                "annual_base_short_net": (base.gross.where(base.w.lt(0),0).fillna(0)-base.short_cost).loc[keep].sum()/len(ds)*252,
                "annual_candidate_short_net": (candidate.gross.where(candidate.w.lt(0),0).fillna(0)-candidate.short_cost).loc[keep].sum()/len(ds)*252,
                "average_base_weight": base.w.loc[keep].mean(), "average_candidate_weight": candidate.w.loc[keep].mean(),
                "average_base_short_weight": (-base.w).clip(lower=0).loc[keep].mean(), "average_candidate_short_weight": (-candidate.w).clip(lower=0).loc[keep].mean()})
            for sector, idx in f.loc[keep].groupby(f.Sector33Code.fillna("UNKNOWN")).groups.items():
                cohort_sectors.append({"cohort": name, "scope": scope, "sector": sector, "rows": len(idx), "target_mean": target.loc[idx].mean(),
                    "annual_base_short_gross": base.gross.where(base.w.lt(0),0).loc[idx].fillna(0).sum()/len(ds)*252,
                    "annual_candidate_short_gross": candidate.gross.where(candidate.w.lt(0),0).loc[idx].fillna(0).sum()/len(ds)*252,
                    "annual_base_short_net": (base.gross.where(base.w.lt(0),0).fillna(0)-base.short_cost).loc[idx].sum()/len(ds)*252,
                    "annual_candidate_short_net": (candidate.gross.where(candidate.w.lt(0),0).fillna(0)-candidate.short_cost).loc[idx].sum()/len(ds)*252,
                    "average_base_weight": base.w.loc[idx].mean(), "average_candidate_weight": candidate.w.loc[idx].mean()})
    pd.DataFrame(cohort_sectors).to_csv(folder/"C_cohort_sector_distribution.csv", index=False)
    pd.DataFrame(cohorts).to_csv(folder/"C_veto_short_cohorts.csv", index=False)
    pd.DataFrame({"target": target, "base_weight": base.w, "candidate_weight": candidate.w, "removed": candidate.w.ge(0)}).loc[C_short].to_parquet(folder/"C_original_short_names.parquet")
    return {"status": "PASS", "replacement_gross_reconciliation_atol": 1e-15, "net_equals_gross_minus_cost_atol": 1e-15,
            "interpretation": "REMOVED avoided signed old losses + ADDED signed new P/L + UNCHANGED weight effect; exact current-book difference, not isolated intervention causal effect."}


def long_protection(holdings, dates, folder):
    rows = []
    baseline = holdings["RAW_EWMA_CONTROL"].w.gt(0)
    for strategy, h in holdings.items():
        active = h.w.gt(0)
        intersection = (baseline & active).groupby("Date").sum()
        union = (baseline | active).groupby("Date").sum()
        overlap = intersection/baseline.groupby("Date").sum()
        r = pd.DataFrame({"strategy": strategy, "long_jaccard": intersection/union, "long_membership_overlap_vs_RAW_CONTROL": overlap,
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


def standalone_smoke(stage, output, signals):
    smoke=output/"adapter_smoke"; smoke.mkdir(); (smoke/"input").symlink_to(stage,target_is_directory=True)
    result=output/"audit/standalone_smoke.json"
    lines=["import sys,time,resource,json,os",f"sys.path.insert(0,{str(ROOT)!r})","from research import firewall; firewall.install()",
        f"sys.path.insert(0,{str(ROOT/'stock_comp_2026/strategies/dm_raw_ewma_ablation')!r})","import submission",f"os.chdir({str(smoke)!r})","t=time.monotonic()",
        "default=submission.predict()",f"default.to_parquet({str(output/'predictions/standalone.parquet')!r})"]
    for name in sc.CANDIDATES:
        lines += [f"p=submission.predict(candidate={name!r})",f"p.to_parquet({str(output/'predictions'/('standalone_'+name+'.parquet'))!r})"]
    lines += ["r={'status':'PASS','seconds':time.monotonic()-t,'rows':len(default),'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),'opened':sorted(firewall.ACCESSES),'no_argument_predict':True}",f"open({str(result)!r},'w').write(json.dumps(r,indent=2)+'\\n')"]
    (smoke/"script.py").write_text("\n".join(lines)+"\n")
    completed=subprocess.run([sys.executable,str(smoke/"script.py")],capture_output=True,text=True,timeout=120)
    (output/"logs/standalone.log").write_text(completed.stdout+completed.stderr)
    assert completed.returncode==0,completed.stderr
    exact(signals["RAW_EWMA_SHORT_VETO"].to_frame(),pd.read_parquet(output/"predictions/standalone.parquet"))
    for name in sc.CANDIDATES:
        exact(signals[name].to_frame(),pd.read_parquet(output/"predictions"/('standalone_'+name+'.parquet')))
    record=json.loads(result.read_text());record["bitwise_research_parity_all_candidates"]=True;dump(result,record)


def coverage(f, folder, dates):
    raw = pd.DataFrame({"stock_finite": np.isfinite(f.StockMom60_raw), "common_finite": np.isfinite(f.Sector33Common_raw)}, index=f.index)
    raw["C_state_evaluable"] = raw.stock_finite & raw.common_finite
    raw["agreement_finite"] = raw.C_state_evaluable
    raw["four_state_defined"] = f.State.isin(STATES[:4])
    raw["control_raw_available"] = raw.stock_finite
    raw["veto_raw_context_available"] = raw.C_state_evaluable
    raw["control_neutral"] = f.RawControl_raw.eq(0)
    raw["veto_neutral"] = f.ShortVeto_raw.eq(0)
    rows = []
    for scope, ds in [("ALL_TRAIN", f.index.get_level_values("Date").unique())]+scopes(dates):
        r = raw.loc[raw.index.get_level_values("Date").isin(ds)]
        for sector, block in [("ALL", r)]+list(r.groupby(f.Sector33Code.fillna("UNKNOWN").reindex(r.index))):
            rows.append({"scope": scope, "sector": sector, "rows": len(block), **block.mean().to_dict()})
    result = pd.DataFrame(rows)
    result.to_csv(folder/"coverage.csv", index=False)
    return result


def add_quintile_costs(h):
    """Allocate Short entry/rebalance to current Q; exits to preceding Q."""
    prior = h.q.groupby("Code").shift(1)
    destination = h.q.where(h.w.lt(0), prior)
    for q in [0, 1]:
        h[f"Q{q+1}_cost"] = h.short_cost.where(destination.eq(q), 0.)
    assert np.allclose(h.Q1_cost+h.Q2_cost, h.short_cost, atol=1e-15, rtol=0)
    return h


def turnover_difference(f, tr, base, veto, dates, folder):
    b, c = base.w.lt(0), veto.w.lt(0)
    cls = pd.Series("OTHER", index=f.index)
    cls.loc[b & ~c & f.State.eq("C")] = "C_STATE_EXIT"
    cls.loc[b & ~c & ~f.State.eq("C")] = "REMOVED_NON_C"
    cls.loc[~b & c] = "REPLACEMENT"
    cls.loc[b & c] = "UNCHANGED_WEIGHT"
    cols = ["turnover", "long_turnover", "short_turnover", "cost", "long_cost", "short_cost"]
    delta = veto[cols]-base[cols]
    all_rows, rows = [], []
    categories = {name: cls.eq(name) for name in ["C_STATE_EXIT", "REMOVED_NON_C", "REPLACEMENT", "UNCHANGED_WEIGHT", "OTHER"]}
    partition = []
    for name, mask in categories.items():
        d = delta.where(mask, 0).groupby("Date").sum().loc[dates]
        partition.append(d)
        d["class"] = name
        all_rows.append(d.reset_index())
        for scope, ds in scopes(dates):
            rows.append({"scope": scope, "class": name, **{("annual_delta_" if "cost" in col else "delta_")+col: d.loc[ds,col].mean()*(252 if "cost" in col else 1) for col in cols}})
    got = sum(p[cols] for p in partition)
    expected = delta.groupby("Date").sum().loc[dates]
    assert np.allclose(got, expected, atol=1e-15, rtol=0)
    pd.concat(all_rows).to_csv(folder/"turnover_difference_daily.csv", index=False)
    pd.DataFrame(rows).to_csv(folder/"turnover_difference.csv", index=False)
    # Actual raw C entry/exit events are a separate, potentially overlapping view.
    event = delta.where((tr.C_entry|tr.C_exit), 0).groupby("Date").sum().loc[dates]
    event.to_csv(folder/"C_temporal_transition_turnover_difference.csv")
    return {"status": "PASS", "disjoint_partition_atol": 1e-15,
            "C_STATE_EXIT": "Current raw C Short removed from portfolio, not necessarily a temporal raw-C exit",
            "limitation": "Descriptive current-row assignment; delayed EWMA/replacement causation is not uniquely identified"}


def matched_rows(f, target, signals, holdings, accounts, folder):
    dates = f.index.get_level_values("Date").unique().sort_values()
    available = np.isfinite(f.StockMom60_raw) & np.isfinite(f.Sector33Common_raw)
    rows, records = [], []
    for strategy, score in signals.items():
        score = score.reindex(f.index)
        subset = score.loc[available]
        _, q = evaluation.weights(subset)
        ic = evaluation.rankic(score.where(available), target).reindex(dates)
        d = pd.DataFrame({"rankic": ic, "matched_rows": available.groupby("Date").sum(),
                          "matched_label_rows": (available & target.notna()).groupby("Date").sum()}, index=dates)
        for k in range(5):
            d[f"q{k+1}"] = target.loc[available].where(q.eq(k)).groupby("Date").mean().reindex(dates)
        d["strategy"] = strategy
        records.append(d.reset_index())
        h = holdings[strategy]
        parts = pd.DataFrame({"gross": h.gross.fillna(0), "net": h.net, "cost": h.cost, "turnover": h.turnover,
            "long_gross": h.gross.where(h.w.gt(0),0).fillna(0), "short_gross": h.gross.where(h.w.lt(0),0).fillna(0),
            "long_net": h.gross.where(h.w.gt(0),0).fillna(0)-h.long_cost,
            "short_net": h.gross.where(h.w.lt(0),0).fillna(0)-h.short_cost}, index=f.index)
        for group, mask in [("MATCHED", available), ("UNAVAILABLE", ~available)]:
            contrib = parts.where(mask,0).groupby("Date").sum().reindex(dates, fill_value=0)
            for scope, ds in scopes(dates):
                block = d.loc[ds]
                qs = block[[f"q{k}" for k in range(1,6)]].mean()
                rows.append({"strategy":strategy,"scope":scope,"row_group":group,"rows":int((mask & f.index.get_level_values("Date").isin(ds)).sum()),
                    "matched_rankic":block.rankic.mean() if group=="MATCHED" else np.nan,
                    "matched_rankic_hac5":evaluation.hac_t(block.rankic) if group=="MATCHED" else np.nan,
                    "matched_rankic_hit":block.rankic.dropna().gt(0).mean() if group=="MATCHED" else np.nan,
                    "matched_rankic_days":block.rankic.notna().sum() if group=="MATCHED" else 0,
                    **{f"matched_q{k}_target":qs[f"q{k}"] if group=="MATCHED" else np.nan for k in range(1,6)},
                    **{("original_book_annual_" if col!="turnover" else "original_book_")+col:contrib.loc[ds,col].mean()*(252 if col!="turnover" else 1) for col in parts}})
        matched = parts.where(available,0).groupby("Date").sum()
        unavailable = parts.where(~available,0).groupby("Date").sum()
        assert np.allclose((matched+unavailable)[["gross","net","cost","turnover"]], accounts[strategy][["gross","net","cost","turnover"]], atol=1e-15, rtol=0)
    pd.concat(records).to_csv(folder/"matched_row_daily.csv", index=False)
    result=pd.DataFrame(rows); result.to_csv(folder/"matched_row_diagnostics.csv", index=False)
    m=result.loc[result.row_group=="MATCHED"]
    base=m.loc[m.strategy=="RAW_EWMA_CONTROL"].set_index("scope")
    candidate=m.loc[m.strategy=="RAW_EWMA_SHORT_VETO"].set_index("scope")
    keys=[k for k in m if k not in ["strategy","scope","row_group","rows"]]
    diff=candidate[keys]-base[keys];diff.to_csv(folder/"matched_row_primary_difference.csv")
    return {"status":"PASS","same_rows":True,"no_additional_strategy":True,"original_book_partition_atol":1e-15,
            "limitation":"Current raw availability cannot remove prior unavailable context's EWMA state; subset Q ranks are target diagnostics only"}


def comparisons(results, folder):
    keys=[k for k in results if k not in ["strategy","scope","days"]]
    rows=[]
    for candidate, control in [("RAW_EWMA_SHORT_VETO","RAW_EWMA_CONTROL"),("RAW_EWMA_CONTROL","MOM60"),("RAW_EWMA_SHORT_VETO","MOM60")]:
        for scope in results.scope.unique():
            c=results.loc[(results.strategy==candidate)&(results.scope==scope)].iloc[0]
            b=results.loc[(results.strategy==control)&(results.scope==scope)].iloc[0]
            r={"strategy":candidate,"control":control,"scope":scope,**{"delta_"+k:c[k]-b[k] for k in keys}}
            r["short_cost_effect"]=-r["delta_annual_short_cost"]
            assert np.isclose(r["delta_annual_short_net"],r["delta_annual_short_gross"]+r["short_cost_effect"],atol=1e-15,rtol=0)
            rows.append(r)
    inc=pd.DataFrame(rows)
    inc.to_csv(folder/"incremental.csv",index=False)
    inc.loc[inc.control=="RAW_EWMA_CONTROL"].to_csv(folder/"primary_ablation_comparison.csv",index=False)
    inc[["strategy","control","scope"]+[k for k in inc if "short" in k or "long" in k or "cost" in k or "turnover" in k]].to_csv(folder/"side_cost_decomposition.csv",index=False)
    return inc


def bootstrap(accounts, config, folder):
    result={}
    rows=[]
    for scope in ["EX2016","POOLED"]:
        for candidate,control in [("RAW_EWMA_SHORT_VETO","RAW_EWMA_CONTROL"),("RAW_EWMA_CONTROL","MOM60"),("RAW_EWMA_SHORT_VETO","MOM60")]:
            b=accounts[control];c=accounts[candidate]
            if scope=="EX2016":b=b.loc[b.index.year!=2016];c=c.loc[c.index.year!=2016]
            assert b.index.equals(c.index)
            r=evaluation.bootstrap_delta(b.net,c.net,**{k:config['bootstrap'][k] for k in ['seed','block','reps']})
            r.update(point_delta=evaluation.sharpe(c.net)-evaluation.sharpe(b.net),days=len(b),primary=(control=="RAW_EWMA_CONTROL" and scope=="EX2016"))
            key=f"{scope}:{candidate}-{control}";result[key]=r
            rows.append({"scope":scope,"strategy":candidate,"control":control,**r})
    dump(folder/"bootstrap.json",result);pd.DataFrame(rows).to_csv(folder/"bootstrap.csv",index=False)
    return result


def decide(accounts, cover, boot):
    b=accounts['RAW_EWMA_CONTROL'];c=accounts['RAW_EWMA_SHORT_VETO']
    bm=metrics(b);cm=metrics(c)
    bp=metrics(b.loc[b.index.year!=2016]);cp=metrics(c.loc[c.index.year!=2016])
    improvements=sum(metrics(c.loc[c.index.year==y])['net_sharpe']>metrics(b.loc[b.index.year==y])['net_sharpe'] for y in range(2011,2016))
    dg=cp['annual_short_gross']-bp['annual_short_gross'];dn=cp['annual_short_net']-bp['annual_short_net']
    share=dg/dn if dn>0 else np.nan
    checks={'pooled_NetSR_beats_RAW':cm['net_sharpe']>bm['net_sharpe'],'ex2016_NetSR_beats_RAW':cp['net_sharpe']>bp['net_sharpe'],
        'primary_annualNet_beats_RAW':cp['annual_net']>bp['annual_net'],'primary_Shortgross_ge_RAW':cp['annual_short_gross']>=bp['annual_short_gross'],
        'primary_Shortnet_ge_RAW':cp['annual_short_net']>=bp['annual_short_net'],'primary_turnover_le1p25_RAW':cp['turnover']<=1.25*bp['turnover'],
        'primary_Longnet_positive':cp['annual_long_net']>0,'primary_Qmonotonicity_positive':cp['q_monotonicity']>0,
        'NetSR_improvements_4of5':improvements>=4,'primary_bootstrap_lower_gt0':boot['EX2016:RAW_EWMA_SHORT_VETO-RAW_EWMA_CONTROL']['low']>0,
        'primary_deltaShortnet_positive':dn>0,'primary_gross_improvement_share_ge50pct':dn>0 and share>=.5}
    failed=[k for k,v in checks.items() if not v]
    raw=cover.loc[(cover.scope=='EX2016')&(cover.sector=='ALL')].iloc[0]
    return safe({'RAW_EWMA_CONTROL':{'decision':'DIAGNOSTIC_NEGATIVE_CONTROL','failed_checks':[]},
        'RAW_EWMA_SHORT_VETO':{'decision':'REJECT' if failed else 'NEXT_EXPERIMENT_ELIGIBLE_TRAIN_ONLY','checks':checks,'failed_checks':failed,
            'full_year_netSR_improvements':improvements,'primary_delta_short_gross':dg,'primary_delta_short_net':dn,
            'primary_short_cost_effect':dn-dg,'primary_gross_share_of_short_net_improvement':share,
            'control_raw_coverage':raw.stock_finite,'veto_raw_context_coverage':raw.agreement_finite,'coverage_gate':False}})


def report_results(config, output, results, decision, boot):
    report=ROOT/config['report_dir'];report.mkdir(parents=True,exist_ok=True)
    assert not (report/'REPORT.md').exists(),'Existing results must not be overwritten'
    # shutil may open source AND target; permit only these generated parquets.
    firewall.install(allowed_artifacts=list((output/'metrics').glob('*.parquet'))+[report/'metrics'/p.name for p in (output/'metrics').glob('*.parquet')])
    for sub in ['metrics','audit']:shutil.copytree(output/sub,report/sub,dirs_exist_ok=True)
    cols=['strategy','gross_sharpe','net_sharpe','annual_net','annual_short_gross','annual_short_net','annual_long_net','turnover','annual_cost']
    inc=pd.read_csv(output/'metrics/primary_ablation_comparison.csv',dtype={'scope':str},float_precision='round_trip')
    lines=[f"# {config['experiment_id']} — Transform-order matched Sector C-veto",'',
        f"Decision: RAW_EWMA_SHORT_VETO = {decision['RAW_EWMA_SHORT_VETO']['decision']}; RAW control is diagnostic only.",'',
        f"Run `{output.relative_to(ROOT)}`. Exactly2 fixed trials; known Train development evidence. Prior06/07/08 REJECT decisions and artifacts preserved. No Historical Valid, Freeze or external submission.",'',
        '## Primary 2011–2015 (EX2016)','',table(results.loc[results.scope=='EX2016'],cols),'',
        '## Primary VETO minus RAW_EWMA_CONTROL','',table(inc.loc[inc.scope=='EX2016'],['scope','delta_net_sharpe','delta_gross_sharpe','delta_annual_short_gross','delta_annual_short_net','short_cost_effect','delta_turnover','delta_annual_cost','delta_annual_long_net']),'',
        '## Pooled continuity including 2016 partial','',table(results.loc[results.scope=='POOLED'],cols),'',
        '## Year/fold results','',table(results.loc[results.scope.isin([str(y) for y in range(2011,2017)])],['strategy','scope','net_sharpe','annual_net','annual_short_gross','annual_short_net','annual_long_net','turnover']),'',
        '## Fixed gates','', '```json',json.dumps(decision,indent=2),'```','',
        '## Paired circular moving-block bootstrap','', '```json',json.dumps(boot,indent=2),'```','',
        'Primary inference is VETO minus RAW control within raw->EWMA(.25). MOM60 raw->centered rank->EWMA(.25) is secondary. This does not generalize automatically to rank->EWMA MOM60, other orders or general Sector context. Raw Common self-includes own StockMom, minimum5, same-date PIT33, equal weight. Exact prior08 Veto, thresholds/partial veto/alpha/horizon/ranking unchanged. RAW control does not read Sector input. Missing Stock neutral0 in control; unavailable raw context neutral0 in Veto exactly as08. Both predict every required row; raw coverage remains separate.','',
        'Primary2011–2015, 2016partial separate, pooled for continuity. Final2 exchange sessions each fold purged with t+2 maturity checked. No fitting; expanding history from2008. Continuous full required-row official weights and accounting before date selection. Official Code ties/five quintiles,10bp one-way,mean*252 annual P/L/cost,sample-SD Sharpe,HAC5 RankIC t/hit,compound/additive DD. Actual period sums and conservative all-position cost also saved. Official missing-label cost omission retained. Short residual signed P/L excludes borrow costs.','',
        'Bootstrap paired circular20 sessions/2000reps/seed20261002,95% percentile; concatenated eligible sessions include purge gaps. Only primary EX2016 Veto-vs-RAW lower bound is adoption gate. Known Train uncertainty, no independent OOS or multiplicity correction.','',
        'Replacement compares RAW control vs Veto official Q1/Q2 Shorts (and Q1,Q2 separately). Removed old signed losses, added signed P/L and unchanged weights reconcile deltaShortgross; all row costs including OTHER exit-only rows reconcile deltaShortnet=deltaShortgross+controlShortcost-vetoShortcost. Q-cost allocation: current Q on entry/rebalance, preceding Q on exits. C all/removed/retained cohorts preserve average weights/net/sector distribution. Raw veto can retain C Short positions because EWMA state decays gradually and global ranking determines membership.','',
        'State attribution is contribution to original globally ranked books, never standalone state strategies. Equal-row and equal-date targets/RankIC saved. Contiguous observed state spells intersect evaluation with gap/boundary censor flags;1/5day persistence conditional on available contiguous future diagnostic sessions. No duration filter. C entry/exit turnover share is turnover on event-date names, not complete delayed effect. Difference turnover buckets are disjoint current-row assignment: removed C (C_STATE_EXIT),removed non-C,replacement,unchanged weights,OTHER exits. Temporal raw-C exits are distinct and saved separately.','',
        'Long protection compares against RAW control; sector exposures side-normalized Short,HHI/max/top2, Q1/Q2 name distribution and original-book signed contributions. No exclusion. Matched-row RankIC/Q1-Q5 diagnostics use identical joint-finite raw rows; subset ranks never form another strategy. Original-book contributions on matched/unavailable rows sum to official result. Current matched availability cannot erase past missingness in EWMA.','',
        'Saved metrics: primary_ablation_comparison,overall/year/fold metrics,incremental,bootstrap,long_short,quintiles,side_cost_decomposition,state_attribution,state_transitions,state_duration_persistence,state_spells,C cohorts/replacement names and distributions,short_replacement_decomposition/Net classes,turnover_difference/state_triggered_turnover,long_protection,sector concentration/exposure/top2,coverage,matched_row_diagnostics and daily accounts.','',
        'Audit: source scan, runtime Train firewall/pre-target reads, full raw/context/state/veto/EWMA/control/final prefix mutations/truncation at3 cutoffs, future stocks/future sector changes/suffix deletion,row shuffle,deterministic rebuild,exact index/finite coverage,prior08 Veto and MOM60/raw/common parity,research-adapter and standalone parity,purge,official P/L bitwise reconciliation,mechanism/turnover/matched partition within1e-15,prior evidence hashes and resource usage. Python firewall is best-effort; mutation tests are evidence on exercised cases, not proof for every input. Independent OOS/survivorship/borrow costs/actual zip deployment are outside this research.']
    (report/'REPORT.md').write_text('\n'.join(lines)+'\n')
    exp=ROOT/'experiments'/config['experiment_id'];v=decision['RAW_EWMA_SHORT_VETO']
    (exp/'decision.md').write_text(f"# {config['experiment_id']} decision\n\nRAW_EWMA_CONTROL: DIAGNOSTIC_NEGATIVE_CONTROL.\nRAW_EWMA_SHORT_VETO: **{v['decision']}**.\n\nFailed checks: {', '.join(v['failed_checks']) or 'none'}. Full-year NetSR improvements {v['full_year_netSR_improvements']}/5.\n\nExactly2 fixed trials, raw->EWMA matched primary contrast. Prior08 decisions unchanged. Known Train, not independent OOS; no rescue/extra trial/Valid/Freeze/submission. [Report](../../{config['report_dir']}/REPORT.md). Run `{output.relative_to(ROOT)}`.\n")
    meta=json.loads((exp/'experiment.json').read_text());meta.update(status='rejected' if v['decision']=='REJECT' else 'completed',actual_trials=2,run_id=output.name,report=config['report_dir']+'/REPORT.md');dump(exp/'experiment.json',meta)
    if v['decision']=='REJECT':
        with (ROOT/'experiments/GRAVEYARD.md').open('a') as stream:
            stream.write(f"\n## {config['experiment_id']}: Transform-order matched C-veto ablation\n\n[Decision]({config['experiment_id']}/decision.md) / [Report](../{config['report_dir']}/REPORT.md). Exactly2 fixed Train-only trials. RAW control diagnostic only; Veto REJECT relative to RAW control: {', '.join(v['failed_checks'])}. Improvement {v['full_year_netSR_improvements']}/5 full years. Prior08 judgments unchanged. No rescue/Valid/Freeze or independent OOS claim.\n")

def control_only_smoke(stage, output, signal):
    smoke = output/"control_only_smoke"
    smoke.mkdir()
    script = smoke/"script.py"
    script.write_text("\n".join([
        "import sys,json", f"sys.path.insert(0,{str(ROOT)!r})",
        "from research import firewall; firewall.install()",
        f"sys.path.insert(0,{str(ROOT/'stock_comp_2026/strategies/dm_raw_ewma_ablation')!r})",
        "import submission", f"p=submission.predict({str(stage)!r}, 'RAW_EWMA_CONTROL')",
        f"p.to_parquet({str(output/'predictions/control_only.parquet')!r})",
        f"firewall.save({str(output/'audit/control_only_reads.json')!r})",
    ])+"\n")
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=120)
    (output/"logs/control_only.log").write_text(result.stdout+result.stderr)
    assert result.returncode == 0, result.stderr
    exact(signal.to_frame(), pd.read_parquet(output/"predictions/control_only.parquet"))
    reads = json.loads((output/"audit/control_only_reads.json").read_text())
    assert len(reads["opened_parquets"]) == 3
    assert all("listed_info" not in p for p in reads["opened_parquets"])
    dump(output/"audit/control_only_reads.json", {"status":"PASS", "bitwise_research_parity":True, **reads})


def main_work(config, output, run):
    graveyard_before=(ROOT/"experiments/GRAVEYARD.md").read_text()
    started=time.monotonic();stage=output/"stage";stage.mkdir()
    data_hashes={}
    for n in list(sc.INPUT_COLUMNS)+["target_1day"]:
        source=ROOT/config["input_dir"]/f"{n}_train.parquet";(stage/source.name).symlink_to(source);data_hashes[source.name]=sha(source)
    prior_files=[];prior_score=None;prior_runs={}
    for eid in config["prior_experiments"]:
        exp=ROOT/"experiments"/eid;meta=json.loads((exp/"experiment.json").read_text())
        assert meta["status"] in ["rejected","completed"]
        pr=ROOT/"artifacts"/eid/meta["run_id"];saved=json.loads((pr/"run.json").read_text());assert saved["status"] in ["completed", "failed"]
        recovery = None
        if saved["status"] == "failed":
            recovery_path = ROOT/"artifacts"/eid/meta["report_recovery_run_id"]
            recovery = json.loads((recovery_path/"audit/report_recovery.json").read_text())
            recovered = json.loads((recovery_path/"run.json").read_text())
            assert recovered["status"] == "completed" and recovered["actual_trials"] == 0
            assert recovery["status"] == "PASS" and recovery["source_run"] == str(pr.relative_to(ROOT))
            for path, expected in recovery["source_artifact_sha256"].items():
                assert sha(pr/path) == expected, path
            prior_files += list(recovery_path.glob("*.json"))+list((recovery_path/"audit").glob("*.json"))
        score=pr/"predictions/scores.parquet";assert sha(score)==(recovery["source_artifact_sha256"]["predictions/scores.parquet"] if recovery else saved["artifact_sha256"]["predictions/scores.parquet"])
        prior_runs[eid]={"path":str(pr.relative_to(ROOT)),"scores_sha256":sha(score)}
        prior_files += [pr/"run.json"]+list(exp.glob("*"))+list((ROOT/"reports"/eid).rglob("*"))+list((ROOT/"stock_comp_2026/strategies"/meta["strategy"]).glob("*.py"))
        if eid==config["prior_experiments"][-1]:prior_score=score
    prior_hashes={str(p.relative_to(ROOT)):sha(p) for p in prior_files if p.is_file()}
    prediction_paths=[output/"predictions"/(name+".parquet") for name in ["features","scores","standalone","control_only"]+["standalone_"+n for n in sc.CANDIDATES]]
    diagnostic_parquets=[output/"metrics"/name for name in ["removed_added_unchanged_names.parquet", "C_original_short_names.parquet"]]
    firewall.install(allowed_artifacts=prediction_paths+diagnostic_parquets+[prior_score]+[p for p in prior_files if p.suffix==".parquet"])
    code_paths=[Path(__file__),ROOT/"research/evaluation.py",ROOT/"research/firewall.py",ROOT/"research/experiments/sector_momentum.py",ROOT/"research/experiments/hierarchical_momentum.py",ROOT/"research/experiments/sector_confirmation.py",ROOT/"stock_comp_2026/evaluate_script.py",ROOT/"stock_comp_2026/strategies/dm_trainonly/features.py"]
    for slug in ["dm_raw_ewma_ablation","dm_sector_confirmation","dm_sector_momentum","dm_hierarchical_momentum"]:code_paths+=sorted((ROOT/"stock_comp_2026/strategies"/slug).glob("*.py"))
    code_paths+=sorted((ROOT/"tests/strategies/dm_raw_ewma_ablation").glob("*.py"))
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
    control_only_smoke(stage,output,signals["RAW_EWMA_CONTROL"])
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
        daily[n],h,parity[n]=account(s,target);holdings[n]=add_quintile_costs(enrich_holdings(h))
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
    comparisons(results,output/"metrics")
    boot=bootstrap(accounts,config,output/"metrics")
    decision=decide(accounts,cover,boot);dump(output/"metrics/candidate_decision.json",decision)
    print("2/2 trials complete; mechanism diagnostics only",flush=True)
    fe=f.loc[f.index.get_level_values("Date").isin(dates)];te=target.loc[fe.index];he={n:h.loc[fe.index] for n,h in holdings.items()}
    tr=transitions(f,calendar,dates,output/"metrics")
    turnover_attribution(f,tr,holdings,dates,output/"metrics")
    persistence(signals,holdings,calendar,dates,output/"metrics");rank_changes(signals,calendar,dates,output/"metrics")
    audits={"agreement":agreement(fe,te,signals,he,accounts,output/"metrics"),"replacement":replacement(fe,te,he["RAW_EWMA_CONTROL"],he["RAW_EWMA_SHORT_VETO"],accounts,output/"metrics")}
    long_protection(he,dates,output/"metrics");concentration(fe,he,accounts,output/"metrics")
    audits["turnover_difference"]=turnover_difference(f,tr,holdings["RAW_EWMA_CONTROL"],holdings["RAW_EWMA_SHORT_VETO"],dates,output/"metrics")
    audits["matched_rows"]=matched_rows(fe,te,signals,he,accounts,output/"metrics")
    dump(output/"audit/mechanism_reconciliation.json",{"status":"PASS",**audits})
    for p,expected in prior_hashes.items():assert sha(ROOT/p)==expected,p
    for p,expected in code_hashes.items():assert sha(ROOT/p)==expected,p
    dump(output/"audit/prior_evidence_unchanged.json",{"status":"PASS","prior":config["prior_experiments"],"files":len(prior_hashes),"hashes":prior_hashes})
    firewall.save(output/"audit/firewall.json")
    resources={"status":"PASS","elapsed_seconds":time.monotonic()-started,"peak_rss_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=="darwin" else 1024),"actual_trials":2,"valid_evaluation":False}
    dump(output/"audit/resources.json",resources);report_results(config,output,results,decision,boot)
    assert (ROOT/"experiments/GRAVEYARD.md").read_text().startswith(graveyard_before)
    for p,expected in prior_hashes.items():assert sha(ROOT/p)==expected,p
    artifacts={str(p.relative_to(output)):sha(p) for sub in ["audit","metrics","predictions","code"] for p in (output/sub).rglob("*") if p.is_file()}
    run.update(resources);run.update(status="completed",exit_code=0,completed_at_utc=datetime.now(timezone.utc).isoformat(),artifact_sha256=artifacts,candidate_decisions=decision)
    dump(output/"run.json",run);print(json.dumps(safe({"decisions":decision,"resources":resources}),indent=2),flush=True)



def main():
    p=argparse.ArgumentParser();p.add_argument("--config",required=True);p.add_argument("--output",required=True);args=p.parse_args()
    output=Path(args.output).resolve();config=json.loads(Path(args.config).read_text())
    assert Path(args.config).resolve()==output/"config.json"
    assert config["data_split"]=="train" and config["valid_evaluation"] is False and config["max_trials"]==2
    assert [x["trial_id"] for x in config["trials"]]==list(sc.CANDIDATES)
    assert config["parameters"]=={"horizon":60,"skip":1,"min_periods":60,"sector33_min_finite_members":5,"alpha":.25,"ewm_adjust":False,"relisting_gap":20,"neutral_before_ewma":0}
    assert config["purge_trading_days"]==2 and config["bootstrap"]["block"]==20 and config["bootstrap"]["reps"]==2000 and config["bootstrap"]["seed"]==20261002
    run=json.loads((output/"run.json").read_text());assert run["status"]=="prepared"
    try:
        main_work(config,output,run)
    except BaseException as error:
        run.update(status="failed",exit_code=1,error=f"{type(error).__name__}: {error}",completed_at_utc=datetime.now(timezone.utc).isoformat());dump(output/"run.json",run)
        if firewall._PATCHED:firewall.save(output/"audit/firewall.json")
        raise


if __name__=="__main__":main()
