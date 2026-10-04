"""Exactly three preregistered literature-motivated Train-only trials."""
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
from research.experiments.sector_momentum import sha, dump, safe, exact, account, fold_dates, daily_corr, persistence, table
from research.experiments.hierarchical_momentum import scopes, rank_changes, sector_concentration
from stock_comp_2026.strategies.dm_industry_momentum_stock_reversal import features as im, primitives, submission
from stock_comp_2026.strategies.dm_trainonly import features as old


def source_scan():
    sources = sorted((ROOT / "stock_comp_2026/strategies/dm_industry_momentum_stock_reversal").glob("*.py"))
    findings = []
    for path in sources:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if any(t in node.value for t in ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose",
                        "AdjustmentVolume", "raw_target", "target_1day", "_valid.parquet", "Sector17"]):
                    findings.append([str(path), node.lineno, "forbidden input"])
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                bad = node.func.attr in ["bfill", "backfill"]
                if node.func.attr == "shift":
                    n = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == "periods"), None)
                    bad |= not isinstance(n, ast.Constant) or not isinstance(n.value, int) or n.value < 0
                for k in node.keywords:
                    bad |= k.arg == "center" and not (isinstance(k.value, ast.Constant) and k.value.value is False)
                    bad |= k.arg == "direction" and not (isinstance(k.value, ast.Constant) and k.value.value == "backward")
                if bad:
                    findings.append([str(path), node.lineno, "forbidden temporal operation"])
    assert not findings, findings
    return {"status": "PASS", "sources": [str(p.relative_to(ROOT)) for p in sources], "findings": findings,
            "manual_review": "Historical-date exact PIT33 membership, self-inclusive finite daily mean min5, residual20 lag1, same-date centered ranks, per-Code trailing EWMA. No LOO, fit, target or external input."}


def mutate(frame, name, cutoff, seed):
    out = frame.copy()
    future = out.index.get_level_values("Date") > cutoff
    rng = np.random.default_rng(seed)
    for col in out:
        if name == "listed_info":
            out.loc[future, col] = rng.choice(["NEW_FUTURE_SECTOR", "9999", "0050"], int(future.sum()))
        else:
            values = rng.normal(0, 1e6, int(future.sum()))
            values[::7] = np.nan
            out.loc[future, col] = values
    out = out.drop(out.index[future][::13])
    if isinstance(out.index, pd.MultiIndex):
        extra = frame.loc[future].iloc[::max(1, int(future.sum()) // 50)].copy()
        extra = extra.loc[~extra.index.get_level_values("Date").duplicated()]
        extra.index = pd.MultiIndex.from_arrays([extra.index.get_level_values("Date"), ["FUTURE_ONLY"]*len(extra)], names=["Date", "Code"])
        if name == "listed_info":
            extra.iloc[:, 0] = "NEW_FUTURE_SECTOR"
        out = pd.concat([out, extra])
    return out


def prefix_audit(inputs, f, history, config):
    cases = []
    for i, cutoff in enumerate(config["prefix_cutoffs"]):
        cutoff = pd.Timestamp(cutoff)
        idx = f.index[f.index.get_level_values("Date") <= cutoff]
        hi = history.index[history.index.get_level_values("Date") <= cutoff]
        for name in list(inputs) + ["ALL", "TRUNCATION"]:
            changed = dict(inputs)
            for j, (source, frame) in enumerate(inputs.items()):
                if name == "TRUNCATION":
                    changed[source] = frame.loc[frame.index.get_level_values("Date") <= cutoff]
                elif name in [source, "ALL"]:
                    changed[source] = mutate(frame, source, cutoff, config["random_seed"] + i*100+j)
            got, gh = im.build_features(changed, return_history=True)
            exact(f.loc[idx], got.loc[got.index.get_level_values("Date") <= cutoff])
            exact(history.loc[hi], gh.loc[gh.index.get_level_values("Date") <= cutoff])
            for candidate in im.CANDIDATES:
                exact(im.score(f.loc[idx], candidate), im.score(got.loc[idx], candidate))
            cases.append({"cutoff": str(cutoff.date()), "source": name, "status": "PASS", "bitwise": True,
                          "stock_rows": len(idx), "industry_rows": len(hi)})
        print(f"prefix {cutoff.date()}: all sources, full history, scores and truncation PASS", flush=True)
    for changed in [inputs, {n: x.sample(frac=1, random_state=91) for n, x in inputs.items()}]:
        got, gh = im.build_features(changed, return_history=True)
        exact(f, got)
        exact(history, gh)
    return {"status": "PASS", "cases": cases, "features": list(f), "industry_history": list(history),
            "row_shuffle": True, "deterministic_rebuild": True,
            "comparison": "Exact index/columns/dtype, numeric uint64 bits including NaN and signed zero; no tolerance",
            "mutation": "Suffix residual-source extremes/NaN; source row deletion; PIT classification changes/new industries, stock membership and future-only stocks; full truncation",
            "scope": "Full Train four input sources,3cutoffs; no fitted model. Empirical checks, not proof for every input."}


def primitive_parity(inputs, f):
    for name in ["smooth", "segment_keys", "centered_rank"]:
        assert inspect.getsource(getattr(primitives, name)) == inspect.getsource(getattr(old, name))
    exact(old.smooth(old.build_momentum(inputs), .25).rename("MOM60"), f.MOM60)
    with patch.object(old, "centered_rank", side_effect=lambda v: v):
        exact(old.build_momentum(inputs).rename("StockMom60_raw"), f.StockMom60_raw)
    return {"status": "PASS", "MOM60_bitwise": True, "raw60_bitwise": True,
            "unchanged_source": ["smooth", "segment_keys", "centered_rank"], "residual": "same provided raw_return-beta*TOPIX construction"}


def coverage(f, folder, dates):
    masks = {"StockMom20": f.StockMom20.notna(), "IndustryMom20": f.IndustryMom20.notna(),
             "Within33": f.Within33Rev20.notna()}
    rows, sector_rows = [], []
    for component, mask in masks.items():
        for scope, ds in [("ALL_TRAIN", f.index.get_level_values("Date").unique())] + scopes(dates):
            keep = f.index.get_level_values("Date").isin(ds)
            rows.append({"component": component, "scope": scope, "rows": int(keep.sum()), "raw_coverage": mask.loc[keep].mean(),
                "missing_sector": int((keep & f.Sector33Code.isna()).sum()),
                "daily_minimum_member_failure": int((keep & f.FiniteMembers.lt(5)).sum()),
                "industry_history_missing": int((keep & f.IndustryMom20.isna()).sum()),
                "stock_history_missing": int((keep & f.StockMom20.isna()).sum())})
            panel = pd.DataFrame({"finite": mask.loc[keep], "sector": f.Sector33Code.loc[keep].fillna("UNKNOWN"),
                     "min_fail": f.FiniteMembers.loc[keep].lt(5), "industry_missing": f.IndustryMom20.loc[keep].isna()})
            for code, block in panel.groupby("sector"):
                sector_rows.append({"component": component, "scope": scope, "sector": code, "rows": len(block),
                    "raw_coverage": block.finite.mean(), "daily_minimum_member_failure": int(block.min_fail.sum()),
                    "industry_history_missing": int(block.industry_missing.sum())})
    frame = pd.DataFrame(rows)
    frame.to_csv(folder / "coverage.csv", index=False)
    pd.DataFrame(sector_rows).to_csv(folder / "coverage_sector.csv", index=False)
    failure = pd.DataFrame({"rows": f.groupby("Date").size(),
        "stock_finite": masks["StockMom20"].groupby("Date").sum(),
        "industry_finite": masks["IndustryMom20"].groupby("Date").sum(),
        "within_finite": masks["Within33"].groupby("Date").sum(),
        "minimum_member_failure": f.FiniteMembers.lt(5).groupby("Date").sum()})
    failure.to_csv(folder / "coverage_daily.csv")
    return frame


def metrics(daily):
    result = evaluation.metrics(daily)
    result["q5_minus_q1_daily_return"] = daily.q5.mean()-daily.q1.mean()
    for side in ["long", "short"]:
        result[f"annual_{side}_gross"] = daily[side].mean()*252
        result[f"annual_{side}_net"] = daily[f"{side}_net"].mean()*252
        result[f"annual_{side}_cost"] = daily[f"{side}_cost"].mean()*252
        result[f"{side}_turnover"] = daily[f"{side}_turnover"].mean()
        result[f"{side}_gross_sharpe"] = evaluation.sharpe(daily[side])
        result[f"{side}_net_sharpe"] = evaluation.sharpe(daily[f"{side}_net"])
    return result


def component_diagnostics(f, target, dates, folder):
    rows, daily = [], []
    for name, raw in {"StockReversal": -f.StockMom20, "WithinReversal": f.Within33Rev20,
                      "IndustryMomentum": f.IndustryMom20}.items():
        ic = evaluation.rankic(raw, target)
        daily.append(ic.rename(name))
        for scope, ds in scopes(dates):
            x = ic.reindex(ds)
            rows.append({"component": name, "scope": scope, "rankic": x.mean(),
                         "HAC5_t": evaluation.hac_t(x), "hit": (x.dropna() > 0).mean(), "days": x.notna().sum()})
    pd.concat(daily, axis=1).to_csv(folder / "raw_component_rankic_daily.csv")
    pd.DataFrame(rows).to_csv(folder / "raw_component_rankic.csv", index=False)
    rows = []
    for a, b in [("StockMom20", "IndustryMom20"), ("Within33Rev20", "IndustryMom20"), ("StockMom20", "Within33Rev20")]:
        ic = daily_corr(f[a], f[b])
        for scope, ds in scopes(dates):
            rows.append({"pair": a+"/"+b, "scope": scope, "mean_daily_pearson": ic.reindex(ds).mean()})
    pd.DataFrame(rows).to_csv(folder / "component_correlations.csv", index=False)


def industry_diagnostics(f, history, target, dates, folder):
    keys = [f.index.get_level_values("Date"), f.Sector33Code]
    sector_target = target.groupby(keys).mean()
    sector_target.index.names = history.index.names
    panel = history.copy()
    panel["forward_target"] = sector_target.reindex(panel.index)
    panel["rank"] = panel.IndustryMom20.groupby("Date").rank(method="average", pct=True)
    panel["tercile"] = np.ceil(3*panel["rank"]).clip(1, 3)
    panel.to_csv(folder / "industry_momentum_daily.csv")
    cross = panel.rename_axis(index=["Date", "Code"])
    ic = evaluation.rankic(cross.IndustryMom20, cross.forward_target)
    ic.to_csv(folder / "industry_cross_rankic_daily.csv")
    # Rank movement is an industry-unweighted turnover proxy; no portfolio.
    cal = f.index.get_level_values("Date").unique().sort_values()
    ordinal = pd.Series(cal.get_indexer(panel.index.get_level_values("Date")), index=panel.index)
    adjacent = ordinal.groupby("Sector33Code").diff().eq(1)
    movement = panel["rank"].groupby("Sector33Code").diff().abs().where(adjacent)
    dispersion = panel.IndustryMom20.groupby("Date").std()
    summary = []
    buckets = []
    for scope, ds in scopes(dates):
        summary.append({"scope": scope, "rankic": ic.reindex(ds).mean(), "HAC5_t": evaluation.hac_t(ic.reindex(ds)),
            "hit": (ic.reindex(ds).dropna()>0).mean(), "dispersion": dispersion.reindex(ds).mean(),
            "industry_mean_abs_percentile_change_proxy": movement.groupby("Date").mean().reindex(ds).mean(),
            "industry_only_portfolio_evaluated": False})
        for bucket in [1, 2, 3]:
            x = panel.forward_target.where(panel.tercile.eq(bucket)).groupby("Date").mean().reindex(ds)
            buckets.append({"scope": scope, "tercile": bucket, "equal_sector_equal_date_target": x.mean(), "days": x.notna().sum()})
    pd.DataFrame(summary).to_csv(folder / "industry_momentum_diagnostics.csv", index=False)
    pd.DataFrame(buckets).to_csv(folder / "industry_tercile_target.csv", index=False)
    pd.DataFrame({"dispersion": dispersion, "rank_movement_proxy": movement.groupby("Date").mean()}).to_csv(folder / "industry_dispersion_turnover_proxy.csv")


def mechanism(f, target, holdings, dates, folder):
    valid = f.Within33Mom20.notna() & f.IndustryMom20.notna()
    state = pd.Series("ZERO_OR_MISSING", index=f.index)
    for label, inds, ins in [("A", 1, 1), ("B", 1, -1), ("C", -1, 1), ("D", -1, -1)]:
        state.loc[valid & (f.IndustryMom20*inds > 0) & (f.Within33Mom20*ins > 0)] = label
    within_sign = pd.Series("ZERO_OR_MISSING", index=f.index)
    within_sign.loc[f.Within33Mom20 > 0] = "WITHIN_POSITIVE"
    within_sign.loc[f.Within33Mom20 < 0] = "WITHIN_NEGATIVE"
    rows, contributions = [], []
    for grouping, group in [("FOUR_STATE", state), ("WITHIN_SIGN", within_sign)]:
        for scope, ds in scopes(dates):
            eligible = f.index.get_level_values("Date").isin(ds)
            for label in sorted(group.unique()):
                keep = eligible & group.eq(label)
                x = target.loc[keep]
                daily_target = x.groupby("Date").mean()
                rows.append({"grouping": grouping, "scope": scope, "state": label, "rows": int(keep.sum()),
                             "finite_targets": int(x.notna().sum()), "equal_row_target": x.mean(),
                             "equal_date_target": daily_target.mean(), "HAC5_t": evaluation.hac_t(daily_target)})
                for name, h in holdings.items():
                    block = h.loc[keep]
                    gross = block.gross.groupby("Date").sum().reindex(ds, fill_value=0)
                    net = block.net.groupby("Date").sum().reindex(ds, fill_value=0)
                    contributions.append({"grouping": grouping, "scope": scope, "state": label, "strategy": name,
                        "annual_gross": gross.mean()*252, "annual_net": net.mean()*252,
                        "annual_long_gross": block.gross.where(block.w>0, 0).sum()/len(ds)*252,
                        "annual_short_gross": block.gross.where(block.w<0, 0).sum()/len(ds)*252,
                        "annual_long_net": (block.gross.where(block.w>0, 0).fillna(0)-block.long_cost).sum()/len(ds)*252,
                        "annual_short_net": (block.gross.where(block.w<0, 0).fillna(0)-block.short_cost).sum()/len(ds)*252})
    pd.DataFrame(rows).to_csv(folder / "within_reversal_and_four_state_targets.csv", index=False)
    frame = pd.DataFrame(contributions)
    frame.to_csv(folder / "within_reversal_and_four_state_contributions.csv", index=False)
    for (grouping, name, scope), block in frame.groupby(["grouping", "strategy", "scope"]):
        ds = dict(scopes(dates))[scope]
        assert np.isclose(block.annual_net.sum(), holdings[name].loc[holdings[name].index.get_level_values("Date").isin(ds)].net.sum()/len(ds)*252, atol=1e-15, rtol=0)
    return {"status": "PASS", "original_book_partitions_reconcile": True, "new_candidates": 0, "filters": False}


def lead_lag(f, history, target, dates, folder):
    cal = f.index.get_level_values("Date").unique().sort_values()
    lag = im.long_series(history.IndustryResidualReturn.unstack("Sector33Code").reindex(cal).shift(1))
    key = pd.MultiIndex.from_arrays([f.index.get_level_values("Date"), f.Sector33Code], names=history.index.names)
    peer = pd.Series(lag.reindex(key).to_numpy(), index=f.index)
    own = f.ResidualReturn.groupby(primitives.segment_keys(f.index), sort=False).shift(1)
    rows, daily_rows = [], []
    keys = [f.index.get_level_values("Date"), f.Sector33Code]
    good = peer.notna() & target.notna()
    # Same-date/sector demeaned values expose the common-score identification limit.
    within_peer = peer.where(good) - peer.where(good).groupby(keys).transform("mean")
    within_target = target.where(good) - target.where(good).groupby(keys).transform("mean")
    for label, score, y in [("LAG1_INDUSTRY_SELF_INCLUSIVE", peer, target),
                             ("LAG1_OWN_RESIDUAL", own, target),
                             ("LAG1_INDUSTRY_WITHIN_SECTOR", within_peer, within_target)]:
        # The common lag1 value has zero within-sector variation by construction.
        if label.endswith("WITHIN_SECTOR"):
            ic = pd.Series(np.nan, index=cal)
        else:
            ic = evaluation.rankic(score, y)
        daily_rows.append(ic.rename(label))
        for scope, ds in scopes(dates):
            x = ic.reindex(ds)
            rows.append({"diagnostic": label, "scope": scope, "rankic": x.mean(), "HAC5_t": evaluation.hac_t(x),
                         "hit": (x.dropna()>0).mean(), "defined_days": x.notna().sum(),
                         "own_included": label.startswith("LAG1_INDUSTRY"), "lag": 1,
                         "limitation": "Common industry score has no within-sector rank variation; self-inclusive correlation cannot identify peer diffusion"})
    pd.concat(daily_rows, axis=1).to_csv(folder / "lead_lag_daily.csv")
    pd.DataFrame(rows).to_csv(folder / "lead_lag_descriptive.csv", index=False)


def tail_overlap(signals, holdings, dates, folder):
    rows = []
    base = holdings["MOM60"].q
    for name, h in holdings.items():
        for side, tail in [("long", 4), ("short", 0)]:
            a, b = h.q.eq(tail), base.eq(tail)
            inter = (a & b).groupby("Date").sum()
            union = (a | b).groupby("Date").sum()
            for scope, ds in scopes(dates):
                rows.append({"strategy": name, "side": side, "scope": scope,
                             "Q_tail_membership_Jaccard_vs_MOM60": (inter/union).reindex(ds).mean()})
    pd.DataFrame(rows).to_csv(folder / "membership_overlap.csv", index=False)


def timing_diagnostic(f, dates, folder):
    cal = f.index.get_level_values("Date").unique().sort_values()
    ordinal = pd.Series(cal.get_indexer(f.index.get_level_values("Date")), index=f.index, dtype=float)
    keys = primitives.segment_keys(f.index)
    start = ordinal.groupby(keys, sort=False).shift(20)
    end = ordinal.groupby(keys, sort=False).shift(1)
    mismatch = (start != ordinal-20) | (end != ordinal-1)
    rows = []
    for scope, ds in scopes(dates):
        keep = f.index.get_level_values("Date").isin(ds) & f.StockMom20.notna()
        rows.append({"scope": scope, "finite_stock_rows": int(keep.sum()),
                     "formation_calendar_mismatch_rows": int((keep & mismatch).sum()),
                     "mismatch_fraction": mismatch.loc[keep].mean()})
    pd.DataFrame(rows).to_csv(folder / "formation_timing_gaps.csv", index=False)


def decide(accounts, cover, boot):
    result = {}
    base = metrics(accounts["MOM60"])
    bx = metrics(accounts["MOM60"].loc[accounts["MOM60"].index.year != 2016])
    for name in im.CANDIDATES:
        m = metrics(accounts[name])
        ex = metrics(accounts[name].loc[accounts[name].index.year != 2016])
        gross_years = sum(evaluation.sharpe(accounts[name].loc[accounts[name].index.year == y].gross) > 0 for y in range(2011, 2016))
        component = "StockMom20" if name == "STOCK_REV20" else "Within33"
        raw = cover.loc[(cover.component==component)&(cover.scope=="POOLED"), "raw_coverage"].iloc[0]
        feasible = {"pooled_rankic_positive": m["rankic"]>0, "pooled_gross_positive": m["gross_sharpe"]>0,
            "ex2016_gross_positive": ex["gross_sharpe"]>0, "gross_positive_3of5": gross_years>=3,
            "raw_coverage_ge95pct": raw>=.95, "turnover_le008": m["turnover"]<=.08}
        extra = {}
        improvements = sum(evaluation.sharpe(accounts[name].loc[accounts[name].index.year==y].net) > evaluation.sharpe(accounts["MOM60"].loc[accounts["MOM60"].index.year==y].net) for y in range(2011, 2016))
        if name == "IND33_MOM_WITHIN_REV20":
            extra = {"pooled_netSR_beats_MOM60": m["net_sharpe"]>base["net_sharpe"],
                "ex2016_netSR_beats_MOM60": ex["net_sharpe"]>bx["net_sharpe"],
                "netSR_improvements_4of5": improvements>=4,
                "bootstrap_lower_positive": boot["POOLED:IND33_MOM_WITHIN_REV20-MOM60"]["low"]>0,
                "annual_net_beats_MOM60": m["annual_net"]>base["annual_net"],
                "turnover_le125_MOM60": m["turnover"]<=base["turnover"]*1.25,
                "long_net_positive": m["annual_long_net"]>0, "short_net_ge_MOM60": m["annual_short_net"]>=base["annual_short_net"],
                "Q_monotonicity_positive": m["q_monotonicity"]>0}
        failed = [k for k, v in {**feasible, **extra}.items() if not v]
        decision = "REJECT" if failed else ("NEXT_STAGE_ELIGIBLE" if extra else "FEASIBLE_COMPONENT_ONLY")
        result[name] = {"decision": decision, "feasibility": feasible, "combined_adoption": extra,
                        "failed_checks": failed, "raw_coverage": raw, "full_year_gross_positive": gross_years,
                        "full_year_netSR_improvements_vs_MOM60": improvements}
    return result


def standalone_smoke(stage, output, signals):
    smoke = output / "adapter_smoke"
    smoke.mkdir()
    (smoke / "input").symlink_to(stage, target_is_directory=True)
    pred = output / "predictions/standalone.parquet"
    result = output / "audit/standalone_smoke.json"
    script = "\n".join([
        "import sys,time,resource,json,os",
        f"sys.path.insert(0,{str(ROOT)!r})",
        "from research import firewall; firewall.install()",
        f"sys.path.insert(0,{str(ROOT/'stock_comp_2026/strategies/dm_industry_momentum_stock_reversal')!r})",
        "import submission",
        f"os.chdir({str(smoke)!r})",
        "t=time.monotonic(); p=submission.predict()",
        f"p.to_parquet({str(pred)!r})",
        "r={'status':'PASS','rows':len(p),'finite':bool(p.notna().all().all()),'seconds':time.monotonic()-t,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),'opened':sorted(firewall.ACCESSES),'no_argument_predict':True}",
        f"open({str(result)!r},'w').write(json.dumps(r,indent=2)+'\\n')"])
    (smoke / "script.py").write_text(script+"\n")
    completed = subprocess.run([sys.executable, str(smoke/"script.py")], capture_output=True, text=True, timeout=120)
    (output / "logs/standalone.log").write_text(completed.stdout+completed.stderr)
    assert completed.returncode==0, completed.stderr
    exact(signals["IND33_MOM_WITHIN_REV20"].to_frame(), pd.read_parquet(pred))
    record = json.loads(result.read_text())
    record["bitwise_research_parity"] = True
    dump(result, record)


def write_report(config, output, results, decisions, boot):
    destination = ROOT / config["report_dir"]
    destination.mkdir(exist_ok=False)
    for folder in ["metrics", "audit"]:
        shutil.copytree(output/folder, destination/folder)
    pooled = results.loc[results.scope=="POOLED"].set_index("strategy")
    text = f"# {config['experiment_id']} — Industry continuation / within-industry reversal\n\n"
    text += "Exactly3 fixed Train-only trials completed; known development evidence, not independent OOS. No Valid, rescue search, Freeze or submission.\n\n"
    text += f"Run `{output.relative_to(ROOT)}`. Plan/config/preregistration in experiments/{config['experiment_id']}. Prior06–09 remain unchanged.\n\n"
    text += table(results.loc[results.scope=="POOLED"], ["strategy", "rankic", "rankic_t_hac5", "gross_sharpe", "net_sharpe", "annual_net", "turnover", "annual_short_gross", "annual_short_net"])+"\n\n"
    s, w, c, b = [pooled.loc[n] for n in ["STOCK_REV20", "WITHIN33_REV20", "IND33_MOM_WITHIN_REV20", "MOM60"]]
    text += f"Q1: Stock reversal final-score RankIC {s.rankic:.6f}, HAC5 t {s.rankic_t_hac5:.3f}; Gross/Net SR {s.gross_sharpe:.4f}/{s.net_sharpe:.4f}. Raw signal diagnostics and all years are saved; this fixed competition test does not establish universal Japanese reversal.\n\n"
    text += f"Q2: Within minus stock ΔNet SR {w.net_sharpe-s.net_sharpe:+.4f}, ΔRankIC {w.rankic-s.rankic:+.6f}, ΔAnnualNet {(w.annual_net-s.annual_net)*100:+.3f}pp. Year and paired-CI evidence in incremental/bootstrap, with raw coverage kept separate.\n\n"
    text += f"Q3: Combined minus Within ΔNet SR {c.net_sharpe-w.net_sharpe:+.4f}; combined minus MOM60 {c.net_sharpe-b.net_sharpe:+.4f}. Industry-only has no performance portfolio by design, so a claim of better Net than industry-only is unidentified. Cross-industry IC/terciles/dispersion/proxy diagnose it without a fourth trial.\n\n"
    text += f"Q4: Combined annual Long gross/net {c.annual_long_gross*100:+.3f}%/{c.annual_long_net*100:+.3f}%, Short gross/net {c.annual_short_gross*100:+.3f}%/{c.annual_short_net*100:+.3f}%. Within Short gross/net {w.annual_short_gross*100:+.3f}%/{w.annual_short_net*100:+.3f}%, vs MOM60 {b.annual_short_gross*100:+.3f}%/{b.annual_short_net*100:+.3f}%. Side Sharpe/cost/turnover, tail overlap and sector concentration saved.\n\n"
    text += "Fixed criteria and decisions:\n\n```json\n"+json.dumps(safe(decisions),indent=2)+"\n```\n\n"
    text += "Bootstrap paired circular20 eligible sessions,2000reps,seed20261002,95%percentile ΔNetSR. PrimaryPOOLED combined-MOM60, EX2016 sensitivity, secondary within-stock/combined-within. Purged gaps are concatenated eligible sessions; no multiple-testing correction.\n\n```json\n"+json.dumps(safe(boot),indent=2)+"\n```\n\n"
    text += "Full-year chronology2011–2015;2016partial separated. All folds use expanding causal history without fit; final2 exchange sessions purged, t+2 maturity verified. Official full-panel daily accounting occurs before fold selection, retaining previous holdings. Official Code ties/five quintiles includingQ2/Q4,10bp one-way. Annual arithmetic mean×252 (2016 annualization is not a full-year realized return), sample-SD SR×sqrt252, RankIC HAC5 Bartlett and hit, Q1low/Q5high and monotonicity, additive/compound DD. Period sums saved. Missing-label cost omission follows official score; conservative all-position costs/net are also saved. Short residual P/L excludes borrow costs.\n\n"
    text += "Industry return uses historical-date PIT33 membership, self-inclusive equal finite residual mean min5; lag1 then20-calendar-observation sum, gaps/insufficient days stayNaN. Stock uses existing observed-row/relisting convention, same20/skip1; rare calendar-span differences saved in formation_timing_gaps.csv. Map today's sector only after historical industry construction. Raw Within=Stock-Industry, reversal sign registered from literature. Centered ranks before EWMA for all3; combined separately ranks both components, sums1:1, reranks then smooths. Missing raw is measured before neutral ranks and remains unavailable in raw diagnostics. No post-result sign/horizon/weight/alpha change.\n\n"
    text += "Mechanism: raw component IC, industry equal-sector terciles/cross-industry IC/year/dispersion/rank-change proxy, Within +/- and four Industry/Within sign states, original-book state contributions. Lead-lag is one fixed lag1 self-inclusive industry association versus own residual: it cannot separate peer information from own persistence/common shocks, and the common score has no within-sector variation. No LOO or causal diffusion claim. Sector33HHI/max/Q1Q5 distributions/top2 and LOSO subtract original-book contribution/cost without rerank; no sector exclusion. Spells follow contiguous observed sessions, reset on gaps, include boundary censoring; period means can include full spells intersecting the period.\n\n"
    text += "Audit: static scan, runtime Train firewall/pre-target score construction,3cutoff full-source mutations including future-only stocks/classifications/deletions, bitwise full industry-history/raw/final prefix, truncation/row shuffle/rebuild, exact index/finite outputs, unchanged primitive/MOM60 and saved control parity, research/adapter and isolated no-argument smoke, official weights/P/L reconciliation and target maturity. The Python firewall is best-effort; dynamic checks cover exercised inputs, not mathematical proof. Literature full-text replication, independent OOS, actual zip deployment and borrow costs are outside this research.\n"
    (destination / "REPORT.md").write_text(text)
    (destination / "literature_hypothesis.md").write_text(LITERATURE)
    (destination / "causality_audit.md").write_text("# Causality audit\n\nSee audit/source_scan.json, prefix_invariance.json (3cutoffs×6cases), primitive_parity, prior_control_parity, adapter_parity, standalone_smoke, prediction_source_firewall, firewall_denials, purge, official_accounting_parity, prior_evidence_unchanged and resources. Exact uint64-bit checks include IndustryResidualReturn/history, StockMom20, IndustryMom20, Within33Rev20, all scores; no tolerance. Mechanism partition reconciliation alone uses1e-15 floating tolerance. Four prediction inputs only; Train target loaded only after all feature and score audits. No fitting. Experimental checks cannot prove every possible input.\n")
    experiment = ROOT / "experiments" / config["experiment_id"]
    decision_text = f"# {config['experiment_id']} decision\n\nExactly3 fixed trials completed, known Train only.\n\n"
    for name, d in decisions.items():
        decision_text += f"- **{name}**: {d['decision']}. Failed checks: {', '.join(d['failed_checks']) or 'none'}.\n"
    decision_text += f"\n[Report](../../reports/{config['experiment_id']}/REPORT.md). Run `{output.relative_to(ROOT)}`. No rescue, extra trial, Valid, Freeze or submission. Prior06–09 decisions unchanged. Components have no standalone adoption criterion; passing combined means next-stage eligibility only.\n"
    (experiment / "decision.md").write_text(decision_text)
    meta = json.loads((experiment / "experiment.json").read_text())
    meta.update(status="rejected" if all(d["decision"]=="REJECT" for d in decisions.values()) else "completed",
                run_id=output.name, report=f"reports/{config['experiment_id']}/REPORT.md", actual_trials=3)
    dump(experiment / "experiment.json", meta)
    grave = ROOT / "experiments/GRAVEYARD.md"
    with grave.open("a") as stream:
        stream.write(f"\n## {config['experiment_id']}: Industry Momentum + Stock Reversal\n\n[Decision]({config['experiment_id']}/decision.md) / [Report](../reports/{config['experiment_id']}/REPORT.md). Exactly3 registered known-Train trials; no Valid/rescue/Freeze. Prior06–09 unchanged.\n\n")
        for name, d in decisions.items():
            stream.write(f"- **{name}** — {d['decision']}; failed: {', '.join(d['failed_checks']) or 'none'}.\n")


LITERATURE = """# Literature-motivated hypothesis test

Checked2026-10-02 JST before performance access. Primary-source search-indexed abstracts/author metadata were available; direct SSRN/publisher full-text access returned403. We do not claim full-text replication.

Gao, Cheng; Li, Sophia Zhengzi; Yuan, Peixuan; Zhou, Guofu (2026), [The Anatomy of Industry Momentum](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6371558), written2026-08-31, last revised2026-09-12,74-page **working paper**. Its abstract reports individual one-month reversal and short-horizon continuation in industry/characteristic/factor portfolios. It attributes industry momentum mainly to residual-industry dynamics and intra-industry lead-lag, with reversal exposure important in comparisons to factor momentum. This motivates preassigning positive Industry and negative Within signs; it is not an established universal fact and does not directly predict the competition target.

Iwanaga, Yasuhiro (2024), *Revisiting the residual momentum in Japan*, International Review of Financial Analysis93,103190, [DOI](https://doi.org/10.1016/j.irfa.2024.103190). [Author university bibliographic record](https://unitama.tamagawa.ac.jp/kg/japanese/researchersHtml/R240141/SBT_090/R240141_SBT_090_1.html) identifies peer review and May2024 publication. The [author preprint abstract](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4433572) reports Japanese residual momentum becoming insignificant after short/long reversal adjustment. This warns against assuming more residualization creates alpha; it motivates separating continuation from reversal, without importing fitted factor models.

This is a **competition-specific approximation**, not paper replication: selected Japanese498-stock universe and PIT33 daily membership, market beta/TOPIX residual primitive,20 observations as a fixed month, skip1 ending at prior observed return, daily open-to-open t+1→t+2 residual target, daily ranking/EWMA/quintiles and10bp one-way costs differ from the papers. No factor-spanning regressions or network model is reproduced. A fixed lag1 self-inclusive industry association cannot establish intra-industry information diffusion. No industry-only performance portfolio is constructed.

Past06–09 decisions remain REJECT where previously rejected. The user's new external hypothesis fixes reversal signs before results; this is not sign rescue of those old candidates. All Train has known development history; bootstrap uncertainty is not independent OOS or multiple-testing-adjusted evidence.
"""


def main_work(config, output, run):
    started = time.monotonic()
    experiment = ROOT / "experiments" / config["experiment_id"]
    prereg = json.loads((experiment / "preregistration.json").read_text())
    assert sha(output/"plan.md")==prereg["plan_sha256"] and sha(output/"config.json")==prereg["config_sha256"]
    prior_hashes = prereg["prior_evidence_sha256"]
    for path, expected in prior_hashes.items():
        assert sha(ROOT/path)==expected, path
    stage = output / "stage"
    stage.mkdir()
    data_hashes = {}
    for name in list(im.INPUT_COLUMNS) + ["target_1day"]:
        source = ROOT / config["input_dir"] / f"{name}_train.parquet"
        (stage/source.name).symlink_to(source)
        data_hashes[source.name] = sha(source)
    prior_id = config["prior_experiments"][1]
    prior_meta = json.loads((ROOT/"experiments"/prior_id/"experiment.json").read_text())
    prior_run = ROOT/"artifacts"/prior_id/prior_meta["run_id"]
    prior_score = prior_run/"predictions/scores.parquet"
    prior_record = json.loads((prior_run/"run.json").read_text())
    assert sha(prior_score)==prior_record["artifact_sha256"]["predictions/scores.parquet"]
    prediction_paths = [output/"predictions"/f"{n}.parquet" for n in ["features", "industry_history", "scores", "standalone"]]
    firewall.install(allowed_artifacts=prediction_paths+[prior_score]+[ROOT/p for p in prior_hashes if p.endswith(".parquet")])
    code_paths = [Path(__file__), ROOT/"research/evaluation.py", ROOT/"research/firewall.py",
        ROOT/"research/experiments/sector_momentum.py", ROOT/"research/experiments/hierarchical_momentum.py",
        ROOT/"stock_comp_2026/evaluate_script.py", ROOT/"stock_comp_2026/strategies/dm_trainonly/features.py"]
    code_paths += sorted((ROOT/"stock_comp_2026/strategies/dm_industry_momentum_stock_reversal").glob("*.py"))
    code_hashes = {str(p.relative_to(ROOT)): sha(p) for p in code_paths}
    for p in code_paths:
        dest = output/"code"/p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
    shutil.copyfile(experiment/"preregistration.json", output/"preregistration.json")
    run.update(status="running", command=sys.argv, code_sha256=code_hashes, train_data_sha256=data_hashes, actual_trials=0,
        environment={"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
                     "pyarrow": pyarrow.__version__, "scipy": scipy.__version__, "platform": platform.platform()})
    dump(output/"run.json", run)
    dump(output/"audit/pre_result_lock.json", {"at_utc": datetime.now(timezone.utc).isoformat(),
        "plan_sha256": sha(output/"plan.md"), "config_sha256": sha(output/"config.json"), "code_sha256": code_hashes,
        "target_loaded": False, "trials": list(im.CANDIDATES), "max_trials": 3})
    dump(output/"audit/source_scan.json", source_scan())
    inputs = im.load_train(stage)
    f, history = im.build_features(inputs, return_history=True)
    assert f.index.equals(im.canonical(inputs["raw_return_1day"]).index)
    assert np.isfinite(f[list(im.CANDIDATES)+["MOM60"]].to_numpy()).all()
    dump(output/"audit/primitive_parity.json", primitive_parity(inputs, f))
    exact(f.MOM60, pd.read_parquet(prior_score, columns=["MOM60"]).MOM60)
    dump(output/"audit/prior_control_parity.json", {"status": "PASS", "bitwise": True, "rows": len(f),
          "source": str(prior_score.relative_to(ROOT)), "source_sha256": sha(prior_score), "no_old_candidate_rerun": True})
    dump(output/"audit/prefix_invariance.json", prefix_audit(inputs, f, history, config))
    signals = {n: im.score(f, n) for n in im.CANDIDATES}
    signals["MOM60"] = f.MOM60.rename("Return")
    for name in im.CANDIDATES:
        exact(signals[name].to_frame(), submission.predict(stage, name))
    dump(output/"audit/adapter_parity.json", {"status": "PASS", "all3_bitwise": True, "rows": len(f)})
    standalone_smoke(stage, output, signals)
    denied = []
    for name in ["target_1day_valid.parquet", "raw_target_1day_train.parquet", "unknown.parquet"]:
        try:
            pd.read_parquet(stage/name)
        except PermissionError as e:
            denied.append({"path": name, "reason": str(e)})
        else:
            raise AssertionError("Forbidden path accepted")
    assert not any("target_1day" in p for p in firewall.ACCESSES)
    dump(output/"audit/firewall_denials.json", {"status": "PASS", "cases": denied})
    dump(output/"audit/prediction_source_firewall.json", {"status": "PASS", "opened": sorted(firewall.ACCESSES), "all_scores_before_Train_target_loaded": True})
    f.to_parquet(prediction_paths[0]); history.to_parquet(prediction_paths[1]); pd.DataFrame(signals).to_parquet(prediction_paths[2])
    calendar = f.index.get_level_values("Date").unique().sort_values()
    dates, purge = fold_dates(calendar, [x["year"] for x in config["walk_forward_folds"]])
    dump(output/"audit/purge.json", {"status": "PASS", "folds": purge})
    cover = coverage(f, output/"metrics", dates)
    timing_diagnostic(f, dates, output/"metrics")
    dump(output/"audit/coverage.json", {"status": "PASS", "exact_index": True, "finite_prediction": True, "rows": len(f), "raw_before_neutral": True})
    print("Features, history, full audits/adapter/smoke PASS. Now load Train target.", flush=True)
    target = im.canonical(pd.read_parquet(stage/"target_1day_train.parquet")).Return
    assert target.index.equals(f.index)
    daily, holdings, parity = {}, {}, {}
    for name, signal in signals.items():
        daily[name], holdings[name], parity[name] = account(signal, target)
        daily[name].to_csv(output/f"metrics/daily_{name}.csv")
        if name in im.CANDIDATES:
            run["actual_trials"] += 1
            dump(output/"run.json", run)
        print(f"Fixed trial/account {name} saved", flush=True)
    dump(output/"audit/official_accounting_parity.json", {"status": "PASS", "strategies": parity})
    accounts = {n: d.loc[dates] for n, d in daily.items()}
    results = pd.DataFrame([{"strategy": n, "scope": scope, **metrics(d.loc[ds])}
        for n, d in daily.items() for scope, ds in [("ALL_TRAIN", calendar)] + scopes(dates)])
    results.to_csv(output/"metrics/metrics.csv", index=False)
    results.loc[results.scope=="POOLED"].to_csv(output/"metrics/overall_metrics.csv", index=False)
    for name in ["fold_metrics", "year_metrics"]:
        results.loc[results.scope.isin([str(y) for y in range(2011,2017)])].to_csv(output/f"metrics/{name}.csv", index=False)
    results[["strategy", "scope"]+[k for k in results if "long" in k or "short" in k]].to_csv(output/"metrics/long_short.csv", index=False)
    results[["strategy", "scope"]+[k for k in results if k.startswith("q")]].to_csv(output/"metrics/quintiles.csv", index=False)
    pairs = [(n, "MOM60") for n in im.CANDIDATES]+[("WITHIN33_REV20", "STOCK_REV20"), ("IND33_MOM_WITHIN_REV20", "WITHIN33_REV20"), ("IND33_MOM_WITHIN_REV20", "STOCK_REV20")]
    increments = []
    for name, control in pairs:
        for scope in results.scope.unique():
            c = results.loc[(results.strategy==name)&(results.scope==scope)].iloc[0]
            b = results.loc[(results.strategy==control)&(results.scope==scope)].iloc[0]
            increments.append({"strategy": name, "control": control, "scope": scope,
                **{"delta_"+k: c[k]-b[k] for k in results if k not in ["strategy", "scope"]}})
    increment = pd.DataFrame(increments)
    assert np.allclose(increment.delta_annual_short_net, increment.delta_annual_short_gross-increment.delta_annual_short_cost, rtol=0, atol=1e-15)
    increment.to_csv(output/"metrics/incremental.csv", index=False)
    increment[["strategy", "control", "scope"]+[k for k in increment if "cost" in k or "long" in k or "short" in k or "turnover" in k]].to_csv(output/"metrics/side_cost_decomposition.csv", index=False)
    boot = {}
    for scope, ds in scopes(dates)[:2]:
        for name, control in config["bootstrap"]["pairs"]:
            key = f"{scope}:{name}-{control}"
            boot[key] = {**evaluation.bootstrap_delta(accounts[control].loc[ds].net, accounts[name].loc[ds].net,
                **{k: config["bootstrap"][k] for k in ["seed", "reps", "block"]}),
                "days": len(ds), "point_delta": evaluation.sharpe(accounts[name].loc[ds].net)-evaluation.sharpe(accounts[control].loc[ds].net),
                "primary": scope=="POOLED" and control=="MOM60"}
    dump(output/"metrics/bootstrap.json", boot)
    pd.DataFrame([{"contrast": key, **value} for key, value in boot.items()]).to_csv(output/"metrics/bootstrap.csv", index=False)
    decisions = decide(accounts, cover, boot)
    dump(output/"metrics/candidate_decision.json", decisions)
    print("All3 trials complete. Fixed mechanism diagnostics only.", flush=True)
    fe = f.loc[f.index.get_level_values("Date").isin(dates)]
    he = {n: h.loc[fe.index] for n, h in holdings.items()}
    component_diagnostics(f, target, dates, output/"metrics")
    industry_diagnostics(f, history, target, dates, output/"metrics")
    dump(output/"audit/mechanism_reconciliation.json", mechanism(fe, target.loc[fe.index], he, dates, output/"metrics"))
    lead_lag(f, history, target, dates, output/"metrics")
    persistence(signals, holdings, calendar, dates.rename("Date"), output/"metrics")
    rank_changes(signals, calendar, dates, output/"metrics")
    tail_overlap(signals, holdings, dates, output/"metrics")
    sector_concentration(fe, he, accounts, output/"metrics")
    for path, expected in prior_hashes.items():
        assert sha(ROOT/path)==expected, path
    dump(output/"audit/prior_evidence_unchanged.json", {"status": "PASS", "prior": config["prior_experiments"], "hashes": prior_hashes})
    firewall.save(output/"audit/firewall.json")
    resources = {"elapsed_seconds": time.monotonic()-started,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=="darwin" else 1024),
        "actual_trials": 3, "valid_evaluation": False}
    dump(output/"audit/resources.json", resources)
    write_report(config, output, results, decisions, boot)
    artifacts = {str(p.relative_to(output)): sha(p) for sub in ["audit", "metrics", "predictions", "code"] for p in (output/sub).rglob("*") if p.is_file()}
    run.update(resources)
    run.update(status="completed", exit_code=0, completed_at_utc=datetime.now(timezone.utc).isoformat(), artifact_sha256=artifacts, candidate_decisions=decisions)
    dump(output/"run.json", run)
    print(json.dumps(safe({"decisions": decisions, "resources": resources}),indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    config = json.loads(Path(args.config).read_text())
    assert Path(args.config).resolve()==output/"config.json"
    assert config["data_split"]=="train" and config["valid_evaluation"] is False and config["max_trials"]==3
    assert [t["trial_id"] for t in config["trials"]]==list(im.CANDIDATES)
    assert config["parameters"]=={"horizon":20,"skip":1,"min_periods":20,"sector33_min_finite_members":5,
        "alpha":.25,"ewm_adjust":False,"relisting_gap":20,"scale":"centered_rank","weights":[1,1]}
    assert config["bootstrap"]["block"]==20 and config["bootstrap"]["reps"]==2000 and config["bootstrap"]["seed"]==20261002
    run = json.loads((output/"run.json").read_text())
    assert run["status"]=="prepared"
    try:
        main_work(config, output, run)
    except BaseException as e:
        run.update(status="failed", exit_code=1, error=f"{type(e).__name__}: {e}", completed_at_utc=datetime.now(timezone.utc).isoformat())
        dump(output/"run.json", run)
        if firewall._PATCHED:
            firewall.save(output/"audit/firewall.json")
        raise


if __name__=="__main__":
    main()
