"""Exactly two preregistered post-baseline Sector context candidates, Train only."""
import argparse
import ast
from datetime import datetime, timezone
import importlib.util
import inspect
import json
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
import pyarrow
import scipy
from research import evaluation, firewall
from research.experiments.sector_momentum import sha, safe, dump, exact, mutate, account, fold_dates, table
from research.experiments.industry_momentum_stock_reversal import metrics
from research.experiments.sector_confirmation import enrich_holdings, concentration
from stock_comp_2026.strategies.dm_baseline_sector_veto import features as sv, primitives, submission
from stock_comp_2026.strategies.dm_trainonly import features as old

A, B = sv.CANDIDATES
SOURCES = ["SECTOR33", "SECTOR17_FALLBACK", "UNAVAILABLE"]


def saved_output_paths(output):
    predictions = [output / "predictions" / (n+".parquet") for n in ["features", "scores", "standalone", "standalone_"+A, "standalone_"+B]]
    diagnostics = [output / "metrics" / (n+".parquet") for n in ["removed_added_"+A, "removed_added_"+B, "fallback_attribution_rows_vs_BASELINE", "fallback_attribution_rows_vs_"+A]]
    return predictions+diagnostics


def scopes(dates):
    return [("POOLED", dates), ("EX2016", dates[dates.year != 2016])] + [(str(y), dates[dates.year == y]) for y in sorted(set(dates.year))]


def source_scan():
    paths = sorted((ROOT / "stock_comp_2026/strategies/dm_baseline_sector_veto").glob("*.py"))
    findings = []
    for p in paths:
        for node in ast.walk(ast.parse(p.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if any(t in node.value for t in ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose", "AdjustmentVolume", "raw_target", "target_1day", "_valid.parquet"]):
                    findings.append((str(p), node.lineno, "forbidden input"))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                bad = node.func.attr in ["bfill", "backfill"]
                if node.func.attr == "shift":
                    n = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == "periods"), None)
                    bad |= not isinstance(n, ast.Constant) or not isinstance(n.value, int) or n.value < 0
                for k in node.keywords:
                    bad |= k.arg == "center" and not (isinstance(k.value, ast.Constant) and k.value.value is False)
                    bad |= k.arg == "direction" and not (isinstance(k.value, ast.Constant) and k.value.value == "backward")
                if bad:
                    findings.append((str(p), node.lineno, "forbidden temporal operation"))
    assert not findings, findings
    return {"status": "PASS", "sources": [str(p.relative_to(ROOT)) for p in paths], "findings": findings,
            "manual_review": "All4 input sources exact PIT/date joins; finite inclusive historical-date stock residual60 means; unchanged centered rank/EWMA baseline, finite33 priority then17, strict sign-only veto on final score. No target or fit."}


def prefix_audit(inputs, f, config):
    cases = []
    for i, text in enumerate(config["prefix_cutoffs"]):
        cutoff = pd.Timestamp(text)
        idx = f.index[f.index.get_level_values("Date") <= cutoff]
        for name in list(inputs) + ["ALL", "TRUNCATION"]:
            changed = dict(inputs)
            for j, (source, frame) in enumerate(inputs.items()):
                if name == "TRUNCATION":
                    changed[source] = frame.loc[frame.index.get_level_values("Date") <= cutoff]
                elif name in [source, "ALL"]:
                    changed[source] = mutate(frame, source, cutoff, config["random_seed"] + i * 100 + j)
            got = sv.build_features(changed).loc[idx]
            exact(f.loc[idx], got)
            for candidate in sv.CANDIDATES:
                exact(sv.score(f.loc[idx], candidate), sv.score(got, candidate))
            cases.append({"cutoff": text, "source": name, "status": "PASS", "prefix_rows": len(idx), "bitwise": True})
        print(f"prefix {text}: all input/PIT/future stocks/truncation PASS", flush=True)
    exact(f, sv.build_features(inputs))
    exact(f, sv.build_features({n: x.sample(frac=1, random_state=19) for n, x in inputs.items()}))
    return {"status": "PASS", "cases": cases, "features": list(f), "scores": list(sv.CANDIDATES),
            "deterministic_rebuild": True, "row_shuffle": True, "comparison": "Exact index/columns/dtypes/strings; numeric uint64 bits including NaN, zero tolerance",
            "mutations": "Each/joint suffix extreme/NaN, row deletion, future-only stocks and PIT changes on33/17; whole-source truncation at3cutoffs"}


def baseline_parity(inputs, f, prior_score):
    for name in ["smooth", "segment_keys", "centered_rank"]:
        assert inspect.getsource(getattr(primitives, name)) == inspect.getsource(getattr(old, name))
    frozen_path = ROOT / "releases/DM-20260908-v1/snapshot/stock_comp_2026/strategies/dm_trainonly/features.py"
    spec = importlib.util.spec_from_file_location("frozen_baseline_features", frozen_path)
    frozen = importlib.util.module_from_spec(spec); spec.loader.exec_module(frozen)
    exact(f.BASELINE, old.smooth(old.build_momentum(inputs), .25).rename("BASELINE"))
    exact(f.BASELINE, frozen.smooth(frozen.build_momentum(inputs), .25).rename("BASELINE"))
    exact(f.BASELINE, pd.read_parquet(prior_score, columns=["MOM60"]).MOM60.rename("BASELINE"))
    # Historical same-horizon inclusive33 context is unchanged.
    from stock_comp_2026.strategies.dm_sector_confirmation import features as previous
    pf = previous.build_features(inputs)
    exact(f.SECTOR33_MOM, pf.Sector33Common_raw.rename("SECTOR33_MOM"))
    exact(f.StockMom60_raw, pf.StockMom60_raw)
    return {"status": "PASS", "frozen_and_current_baseline_bitwise": True, "saved_baseline_bitwise": True,
            "saved_source": str(prior_score.relative_to(ROOT)), "saved_sha256": sha(prior_score),
            "same_horizon_sector33_bitwise": True, "baseline_parameters": json.loads((frozen_path.parent / "frozen_config.json").read_text())}


def coverage(f, dates, folder):
    all_dates = f.index.get_level_values("Date").unique().sort_values()
    rows, sectors = [], []
    for scope, ds in [("ALL_TRAIN", all_dates)] + scopes(dates):
        block = f.loc[f.index.get_level_values("Date").isin(ds)]
        rows.append({"scope": scope, "rows": len(block), "sector33_available": np.isfinite(block.SECTOR33_MOM).mean(),
            "sector17_available": np.isfinite(block.SECTOR17_MOM).mean(), "context_available": np.isfinite(block.HIER_SECTOR_MOM).mean(),
            "stock_raw_available": np.isfinite(block.StockMom60_raw).mean(),
            **{s.lower()+"_rows": int(block.ContextSource.eq(s).sum()) for s in SOURCES},
            **{s.lower()+"_rate": block.ContextSource.eq(s).mean() for s in SOURCES},
            **{name+"_veto_rows": int((block.BASELINE.lt(0) & block[name].eq(0)).sum()) for name in sv.CANDIDATES}})
        for level in [33, 17]:
            for sector, sub in block.groupby(block[f"Sector{level}Code"].fillna("UNKNOWN")):
                sectors.append({"scope": scope, "partition": level, "sector": sector, "rows": len(sub),
                    "sector33_available": np.isfinite(sub.SECTOR33_MOM).mean(), "sector17_available": np.isfinite(sub.SECTOR17_MOM).mean(),
                    "context_available": np.isfinite(sub.HIER_SECTOR_MOM).mean(),
                    **{s.lower()+"_rate": sub.ContextSource.eq(s).mean() for s in SOURCES}})
    result = pd.DataFrame(rows); result.to_csv(folder / "coverage.csv", index=False)
    pd.DataFrame(sectors).to_csv(folder / "coverage_by_sector.csv", index=False)
    assert np.allclose(result[[s.lower()+"_rate" for s in SOURCES]].sum(axis=1), 1, atol=1e-15, rtol=0)
    return result


def replacement(f, target, holdings, accounts, dates, folder):
    """Partition full side accounting, keeping exit-only OTHER costs explicit."""
    idx = f.index[f.index.get_level_values("Date").isin(dates)]
    f, target = f.loc[idx], target.loc[idx]
    base = holdings["BASELINE"].loc[idx]
    summaries, distributions, decomposition = [], [], []
    for name in sv.CANDIDATES:
        cand = holdings[name].loc[idx]
        saved_rows = []
        for book, bm, cm in [("SHORT_Q1_Q2", base.w.lt(0), cand.w.lt(0)), ("Q1", base.q.eq(0), cand.q.eq(0)), ("Q2", base.q.eq(1), cand.q.eq(1))]:
            category = pd.Series("OTHER", index=idx, dtype="string")
            category.loc[bm & ~cm] = "REMOVED"; category.loc[~bm & cm] = "ADDED"; category.loc[bm & cm] = "UNCHANGED"
            r = pd.DataFrame({"book": book, "class": category, "forward_target": target, "baseline_score": f.BASELINE,
                "Sector33Code": f.Sector33Code.fillna("UNKNOWN"), "Sector17Code": f.Sector17Code.fillna("UNKNOWN"),
                "Sector33Momentum": f.SECTOR33_MOM, "Sector17Momentum": f.SECTOR17_MOM,
                "ContextSource": f.ContextSource, "candidate_score": f[name],
                "base_weight": base.w.where(bm, 0), "candidate_weight": cand.w.where(cm, 0),
                "base_gross": base.gross.where(bm, 0).fillna(0), "candidate_gross": cand.gross.where(cm, 0).fillna(0)}, index=idx)
            if book == "SHORT_Q1_Q2":
                # Include all costs for this side, even after current positions disappear.
                r["base_cost"], r["candidate_cost"] = base.short_cost, cand.short_cost
                r["base_turnover"], r["candidate_turnover"] = base.short_turnover, cand.short_turnover
            else:
                r["base_cost"] = base.short_cost.where(bm, 0); r["candidate_cost"] = cand.short_cost.where(cm, 0)
                r["base_turnover"] = base.short_turnover.where(bm, 0); r["candidate_turnover"] = cand.short_turnover.where(cm, 0)
            for prefix in ["base", "candidate"]:
                r[prefix+"_net"] = r[prefix+"_gross"] - r[prefix+"_cost"]
            for col in ["gross", "cost", "net", "turnover"]:
                r["delta_"+col] = r["candidate_"+col] - r["base_"+col]
            saved_rows.append(r.loc[category.ne("OTHER") | r.base_cost.ne(0) | r.candidate_cost.ne(0)].reset_index())
            measure = [c for c in r if c.startswith(("base_", "candidate_", "delta_")) and c not in ["baseline_score", "candidate_score"]]
            for clas in ["REMOVED", "ADDED", "UNCHANGED", "OTHER"]:
                mask = category.eq(clas)
                daily = r[measure].where(mask, 0).groupby("Date").sum().reindex(dates, fill_value=0)
                daily["candidate"], daily["book"], daily["class"] = name, book, clas
                decomposition.append(daily.reset_index())
                for scope, ds in scopes(dates):
                    sub = r.loc[mask & idx.get_level_values("Date").isin(ds)]
                    summaries.append({"candidate": name, "book": book, "class": clas, "scope": scope, "rows": len(sub),
                        "forward_target_mean": sub.forward_target.mean(), "sector33_mom_mean": sub.Sector33Momentum.mean(),
                        "sector17_mom_mean": sub.Sector17Momentum.mean(), "baseline_score_mean": sub.baseline_score.mean(),
                        **{"annual_"+c: daily.loc[ds, c].mean()*252 for c in measure if "weight" not in c and "turnover" not in c},
                        **{c: daily.loc[ds, c].mean() for c in measure if "turnover" in c}})
                    for level in [33, 17]:
                        for sector, block in sub.groupby(f"Sector{level}Code"):
                            distributions.append({"candidate": name, "book": book, "class": clas, "scope": scope, "partition": level,
                                "sector": sector, "rows": len(block), "row_share": len(block)/len(sub), "forward_target_mean": block.forward_target.mean(),
                                "annual_base_gross": block.base_gross.sum()/len(ds)*252, "annual_candidate_gross": block.candidate_gross.sum()/len(ds)*252,
                                "annual_delta_net": block.delta_net.sum()/len(ds)*252})
            if book == "SHORT_Q1_Q2":
                now = r[["delta_gross", "delta_net", "delta_cost", "delta_turnover"]].groupby("Date").sum()
                delta = accounts[name].loc[dates] - accounts["BASELINE"].loc[dates]
                for col, expected in [("delta_gross", "short"), ("delta_net", "short_net"), ("delta_cost", "short_cost"), ("delta_turnover", "short_turnover")]:
                    assert np.allclose(now[col], delta[expected], atol=1e-15, rtol=0), (name, col)
        pd.concat(saved_rows).to_parquet(folder / f"removed_added_{name}.parquet", index=False)
    pd.DataFrame(summaries).to_csv(folder / "removed_added_summary.csv", index=False)
    pd.DataFrame(distributions).to_csv(folder / "removed_added_sector_distribution.csv", index=False)
    pd.concat(decomposition).to_csv(folder / "removed_added_daily.csv", index=False)
    return {"status": "PASS", "Short_gross_net_cost_turnover_reconciliation_atol": 1e-15,
            "definition": "Current membership REMOVED/ADDED/UNCHANGED; unchanged includes weight effects. OTHER retains exit-only costs for exact Short reconciliation; Q1/Q2 costs are current-quintile allocation, not standalone quintile strategies."}


def fallback_attribution(f, target, holdings, dates, folder):
    idx = f.index[f.index.get_level_values("Date").isin(dates)]
    ff, cand = f.loc[idx], holdings[B].loc[idx]
    summaries, daily_rows = [], []
    for control in ["BASELINE", A]:
        base = holdings[control].loc[idx]
        r = pd.DataFrame({"ContextSource": ff.ContextSource, "forward_target": target.loc[idx],
            "base_short": base.w.lt(0), "candidate_short": cand.w.lt(0),
            "direct_veto": ff.BASELINE.lt(0) & ff.HIER_SECTOR_MOM.gt(0),
            "gross": cand.gross.fillna(0), "net": cand.net, "turnover": cand.turnover,
            "short_gross": cand.gross.where(cand.w.lt(0), 0).fillna(0), "short_cost": cand.short_cost,
            "short_turnover": cand.short_turnover,
            "delta_gross": cand.gross.fillna(0)-base.gross.fillna(0), "delta_net": cand.net-base.net,
            "delta_turnover": cand.turnover-base.turnover,
            "delta_short_gross": cand.gross.where(cand.w.lt(0), 0).fillna(0)-base.gross.where(base.w.lt(0), 0).fillna(0),
            "delta_short_cost": cand.short_cost-base.short_cost, "delta_short_turnover": cand.short_turnover-base.short_turnover}, index=idx)
        r["short_removed"] = r.base_short & ~r.candidate_short
        r["short_net"] = r.short_gross-r.short_cost
        r["delta_short_net"] = r.delta_short_gross-r.delta_short_cost
        measure = [c for c in r if c not in ["ContextSource", "forward_target"]]
        parts = []
        for source in SOURCES:
            mask = r.ContextSource.eq(source)
            d = r[measure].astype(float).where(mask, 0).groupby("Date").sum().reindex(dates, fill_value=0)
            d["rows"] = mask.groupby("Date").sum().reindex(dates, fill_value=0)
            parts.append(d.copy())
            daily_rows.append(d.assign(control=control, source=source).reset_index())
            for scope, ds in scopes(dates):
                sub = d.loc[ds]
                summaries.append({"control": control, "source": source, "scope": scope, "row_count": int(sub.rows.sum()),
                    "short_removed_count": int(sub.short_removed.sum()), "direct_veto_count": int(sub.direct_veto.sum()),
                    **{"annual_"+c: sub[c].mean()*252 for c in measure if c not in ["base_short", "candidate_short", "direct_veto", "short_removed"] and "turnover" not in c},
                    **{c: sub[c].mean() for c in measure if "turnover" in c}})
        totals = sum(parts)
        original = r[measure].groupby("Date").sum()
        assert np.allclose(totals[measure], original, atol=1e-15, rtol=0)
        r.to_parquet(folder / f"fallback_attribution_rows_vs_{control}.parquet")
    pd.DataFrame(summaries).to_csv(folder / "fallback_attribution.csv", index=False)
    pd.concat(daily_rows).to_csv(folder / "fallback_attribution_daily.csv", index=False)
    return {"status": "PASS", "disjoint_source_accounting_atol": 1e-15,
            "limitation": "Source assigned at each current row, including cost-only exits and global-ranking spillovers. B-minus-A source allocation is descriptive; not a separately optimized17 strategy or isolated causal attribution."}


def long_impact(holdings, dates, folder):
    baseline = holdings["BASELINE"].w.gt(0)
    rows = []
    for name, h in holdings.items():
        active = h.w.gt(0)
        intersection = (baseline & active).groupby("Date").sum()
        union = (baseline | active).groupby("Date").sum()
        d = pd.DataFrame({"membership_overlap": intersection/baseline.groupby("Date").sum(), "jaccard": intersection/union,
            "long_gross": h.gross.where(active, 0).fillna(0).groupby("Date").sum(),
            "long_cost": h.long_cost.groupby("Date").sum(), "long_turnover": h.long_turnover.groupby("Date").sum()}).loc[dates]
        d["long_net"] = d.long_gross-d.long_cost
        d.to_csv(folder / f"long_daily_{name}.csv")
        for scope, ds in scopes(dates):
            rows.append({"strategy": name, "scope": scope, **{c: d.loc[ds, c].mean()*(252 if c in ["long_gross", "long_net", "long_cost"] else 1) for c in d}})
    pd.DataFrame(rows).to_csv(folder / "long_impact.csv", index=False)


def decisions(results, boot, cover, config):
    def row(name, scope="POOLED"):
        return results.loc[(results.strategy==name) & (results.scope==scope)].iloc[0]
    base, exbase = row("BASELINE"), row("BASELINE", "EX2016")
    decisions = {}
    for name in sv.CANDIDATES:
        c, ex = row(name), row(name, "EX2016")
        year_count = sum(row(name, str(y)).net_sharpe > row("BASELINE", str(y)).net_sharpe for y in range(2011, 2016))
        dg = c.annual_short_gross-base.annual_short_gross; dn = c.annual_short_net-base.annual_short_net
        gross_fraction = dg/dn if dn>0 else np.nan
        checks = {
            "pooled_net_sharpe": c.net_sharpe>base.net_sharpe,
            "ex2016_net_sharpe": ex.net_sharpe>exbase.net_sharpe,
            "full_year_improvements_4_of_5": year_count>=4,
            "bootstrap_lower_gt0": boot[f"POOLED:{name}-BASELINE"]["low"]>0,
            "annual_net": c.annual_net>base.annual_net,
            "short_gross": c.annual_short_gross>=base.annual_short_gross,
            "short_net": c.annual_short_net>=base.annual_short_net,
            "long_net_positive": c.annual_long_net>0,
            "turnover_le_1_25x": c.turnover<=base.turnover*1.25,
            "q_monotonicity_no_large_decline": c.q_monotonicity>=base.q_monotonicity-.1-1e-15 and c.q5_minus_q1_daily_return>0,
            "short_net_positive_increment": dn>0,
            "short_gross_share_ge50pct": dn>0 and gross_fraction>=.5,
        }
        decisions[name] = {"decision": "TRAIN_ONLY_NEXT_STAGE_ELIGIBLE" if all(checks.values()) else "REJECT", "checks": checks,
            "failed_checks": [k for k,v in checks.items() if not v], "full_year_improvements": year_count,
            "delta_short_gross": dg, "short_cost_effect": base.annual_short_cost-c.annual_short_cost,
            "delta_short_net": dn, "gross_fraction_of_short_net_improvement": gross_fraction}
    ca, cb = row(A), row(B)
    cv = cover.loc[cover.scope=="POOLED"].iloc[0]
    checks = {"net_sharpe": cb.net_sharpe>ca.net_sharpe, "annual_net": cb.annual_net>ca.annual_net,
              "coverage": cv.context_available>cv.sector33_available, "short_net": cb.annual_short_net>=ca.annual_short_net}
    decisions["fallback"] = {"checks": checks, "alpha_increment_confirmed": all(checks.values()),
        "conclusion": "17 fallback has incremental Train evidence under fixed criteria" if all(checks.values()) else
        "17 fallbackはoperational coverageを改善するがalpha改善は未確認" if checks["coverage"] else "17 fallback coverage increment absent"}
    return decisions


def standalone_smoke(stage, output, signals):
    smoke = output / "adapter_smoke"; smoke.mkdir()
    (smoke / "input").symlink_to(stage, target_is_directory=True)
    for p in (ROOT / "stock_comp_2026/strategies/dm_baseline_sector_veto").glob("*.py"):
        shutil.copyfile(p, smoke / p.name)
    lines = ["import sys,time,resource,json,os", f"sys.path.insert(0,{str(ROOT)!r})", "from research import firewall; firewall.install()",
             f"os.chdir({str(smoke)!r})", "import submission", "started=time.monotonic()", "default=submission.predict()",
             f"default.to_parquet({str(output/'predictions/standalone.parquet')!r})"]
    for name in sv.CANDIDATES:
        lines += [f"submission.predict(candidate={name!r}).to_parquet({str(output/'predictions'/('standalone_'+name+'.parquet'))!r})"]
    lines += ["r={'status':'PASS','seconds':time.monotonic()-started,'rows':len(default),'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),'opened':sorted(firewall.ACCESSES),'no_argument_predict':True}",
              f"open({str(output/'audit/standalone_smoke.json')!r},'w').write(json.dumps(r,indent=2)+'\\n')"]
    (smoke / "script.py").write_text("\n".join(lines)+"\n")
    done = subprocess.run([sys.executable, str(smoke / "script.py")], capture_output=True, text=True, timeout=120)
    (output / "logs/standalone.log").write_text(done.stdout+done.stderr)
    assert done.returncode==0, done.stderr
    exact(signals[B].to_frame(), pd.read_parquet(output / "predictions/standalone.parquet"))
    for name in sv.CANDIDATES:
        exact(signals[name].to_frame(), pd.read_parquet(output / "predictions" / ("standalone_"+name+".parquet")))
    r = json.loads((output / "audit/standalone_smoke.json").read_text()); r["bitwise_research_parity"] = True
    dump(output / "audit/standalone_smoke.json", r)


def report(config, output, results, decision, boot, cover):
    destination = ROOT / config["report_dir"]; destination.mkdir(exist_ok=True)
    shutil.copytree(output / "metrics", destination, dirs_exist_ok=True)
    shutil.copytree(output / "audit", destination / "audit", dirs_exist_ok=True)
    p = results.loc[results.scope=="POOLED"].set_index("strategy")
    cb, base = p.loc[B], p.loc["BASELINE"]
    cv = cover.loc[cover.scope=="POOLED"].iloc[0]
    text = f"# {config['experiment_id']} — baseline Sector Short-context veto\n\n"
    text += f"**A: {decision[A]['decision']}。B（本命）: {decision[B]['decision']}。** 固定2候補のTrain-only実験を終了。旧Sector実験の採否・証拠は変更していない。追加探索・Historical Valid/Valid・Freeze・外部提出なし。\n\n"
    text += "正式baselineはDM-20260908-v1のresidual60/skip1→centered rank→EWMA(.25)。既存実装・凍結snapshot・前回保存MOM60 scoreとbitwise一致。Vetoはその最終scoreの負値かつ正Sector contextのときだけexact0へ置換し、他はbaselineを保持。Candidate後の再平滑化はない。公式global rankingでzero scoreがShortに残る場合やLong側への波及がある。\n\n"
    text += "Sectorは各historical dateのPIT銘柄のfinite残差60Momentumをself-inclusive equal mean。33min5、17min10は同じ60観測DM06の値を固定（直近Industry20のmin5とは別定義）。未回答のclarificationには事前告知したsame-horizon defaultを使用。33優先、33 unavailable時だけ17。No LOO/blend/weight/threshold search。\n\n"
    text += table(results.loc[results.scope.isin(["POOLED", "EX2016"])], ["strategy", "scope", "net_sharpe", "annual_net", "annual_short_gross", "annual_short_net", "annual_long_net", "turnover", "q_monotonicity"])+"\n\n"
    text += f"Pooled context33使用{cv.sector33_rate*100:.3f}%、17fallback{cv.sector17_fallback_rate*100:.3f}%、unavailable{cv.unavailable_rate*100:.3f}%。Coverageは元のNaNを保持したcontext availabilityであり、全Trainのfinite予測100%とは別。\n\n"
    for name in sv.CANDIDATES:
        d = decision[name]
        text += f"{name} Short年率ΔNet {d['delta_short_net']*100:+.4f}pp = ΔGross {d['delta_short_gross']*100:+.4f}pp + cost effect {d['short_cost_effect']*100:+.4f}pp。Gross share={d['gross_fraction_of_short_net_improvement']:.4f}（ΔNet>0の場合）。full-year NetSR改善{d['full_year_improvements']}/5。未達: {', '.join(d['failed_checks']) or 'なし'}。\n\n"
    text += f"Fallback B−A判定: **{decision['fallback']['conclusion']}**。判定チェックをcandidate_decision.jsonに保存。B−A source寄与はcurrent-row attributionであり、global rank spilloverやexit costsを含む。17単独portfolioを作っていない。\n\n"
    text += "年別（2011–2015 full-year、2016 partialは改善年数から除外）:\n\n"
    text += table(results.loc[results.scope.isin([str(y) for y in range(2011, 2017)])], ["strategy", "scope", "net_sharpe", "annual_net", "annual_short_gross", "annual_short_net", "turnover"])+"\n\n"
    text += "Paired circular moving-block20eligible sessions/2000reps/seed20261002/95%percentile、同一session vector。Primary pooled B−BASELINE、secondary A−BASELINE/B−A。EX2016はrobustness別表示。purge gapsを除いたeligible sessionsを連結。既知Train・多重比較補正なし・独立OOSの保証なし。\n\n"
    text += table(pd.DataFrame([{"contrast":k, **v} for k,v in boot.items()]), ["contrast", "point_delta", "low", "high"])+"\n\n"
    text += "removed_added_*にはShortQ1+Q2/Q1/Q2ごとのREMOVED/ADDED/UNCHANGEDのforward target、signed gross/net、両Sector Momentum、baseline score、両sector分布を保存。UNCHANGEDはweight差を含み、OTHERのexit-only costsも保存。Short差分はgross/net/cost/turnover全て1e-15内で日次reconcile。Loss avoidanceの解釈はremoved cohortの旧signed grossとreplacementの新signed grossを併せて判断し、cost削減だけをalpha改善と呼ばない。\n\n"
    text += "long_impact.csvにLonggross/net/turnover/overlap/Jaccard、sector17/sector33に同じPIT partitionでの全3bookのShortHHI/max/Q1Q2分布/top2 exposure/contribution。Unknown sectorを除去せず保持し、rerankやexclusionなし。fallback_attribution.csvはB vs baseline/B vs Aを33/fallback/unavailableで分離し、全行・Short除去・gross/net/turnoverを保存。\n\n"
    text += "公式5quintiles/Q2Q4 half-weight/Code tie order、one-way0.1%cost、Sharpe sampleSD×sqrt252、annual arithmetic mean×252、RankIC HAC5 Bartlett、Q1low/Q5high Spearman単調性、additive/compound DD、period sums。全Trainbook/cost計算後にfold選択し、過去保有を維持。各fold末2sessions purge/t+2 maturity監査。Missing targetのcost除外は公式互換、保守的all-position costも別保存。Shortはborrowcost未控除の市場残差signed P/L。2016年率値は実現full-year returnではない。\n\n"
    text += "Auditは全4Train入力、3cutoffs×6mutation/truncation、future-only stocks、future PIT33/17 changes、全intermediate/final score bits、row shuffle、決定性、exact index/coverage、研究/adapter/isolated no-argument smoke、公式accounting、source firewall/purge/prior証拠hashを含む。動的監査は実施入力での証拠、Python firewallはbest-effort。実zip検証はFreeze/提出を依頼されていないため対象外。\n\n"
    text += f"Run: `{output.relative_to(ROOT)}`。全metric/accounting/audit/config/code/input/environment hashesを保存。\n"
    (destination / "REPORT.md").write_text(text)
    (destination / "causality_audit.md").write_text("# Causality audit\n\nSource scan and manual path review: strategy features.py (canonical/load/sector_context/apply_veto/build_features), unchanged primitives.py and adapter. Exact PIT33/17; all4Train sources;3cutoffs×6suffix/truncation cases, future stocks/sector updates; all raw/history/rank/EWMA/fallback/veto/final values implicit in builder output bitwise checked. Separate baseline frozen/current/saved parity. Row shuffle/rebuild/exact index/finite coverage; research/adapter/standalone smoke; official weights/net and side/difference accounting; target maturity/purge; runtime source firewall before Train target; prior evidence unchanged. No fit. See audit/*.json for source paths/cutoffs/method/status. Empirical checks are not universal proof. No Valid or target in inference; actual submission zip not part of research scope.\n")
    exp = ROOT / "experiments" / config["experiment_id"]
    (exp / "decision.md").write_text(f"# {config['experiment_id']} decision\n\n**A: {decision[A]['decision']}。B: {decision[B]['decision']}。** Exactly2 new fixed performance trials; baseline unchanged bitwise.\n\nB pooled NetSR {cb.net_sharpe:.6f} vs baseline {base.net_sharpe:.6f}; full-year improvements {decision[B]['full_year_improvements']}/5. Failed B criteria: {', '.join(decision[B]['failed_checks']) or 'none'}.\n\n{decision['fallback']['conclusion']}。\n\n[Report](../../reports/{config['experiment_id']}/REPORT.md). Run `{output.relative_to(ROOT)}`. Known Train development evidence; no rescue/Valid/Freeze/submission; prior REJECTs unchanged.\n")
    meta = json.loads((exp / "experiment.json").read_text())
    meta.update(status="rejected" if decision[B]["decision"]=="REJECT" else "completed", run_id=output.name, actual_trials=2, report=config["report_dir"]+"/REPORT.md")
    dump(exp / "experiment.json", meta)
    rejected = [n for n in sv.CANDIDATES if decision[n]["decision"]=="REJECT"]
    if rejected:
        with (ROOT / "experiments/GRAVEYARD.md").open("a") as stream:
            stream.write(f"\n## {config['experiment_id']}: post-baseline hierarchical Sector veto\n\n[Decision]({config['experiment_id']}/decision.md) / [Report](../reports/{config['experiment_id']}/REPORT.md). Fixed2 trials, baseline bitwise unchanged, Train-only; prior REJECTs unchanged.\n\n")
            for name in rejected:
                stream.write(f"- **{name}** — REJECT; failed: {', '.join(decision[name]['failed_checks'])}.\n")


def main_work(config, output, run):
    started = time.monotonic()
    prereg = json.loads((ROOT / "experiments" / config["experiment_id"] / "preregistration.json").read_text())
    assert sha(output / "plan.md")==prereg["plan_sha256"] and sha(output / "config.json")==prereg["config_sha256"]
    for p, h in prereg["prior_evidence_sha256"].items():
        assert sha(ROOT / p)==h, p
    prior_meta = json.loads((ROOT / "experiments/DM-20261002-08/experiment.json").read_text())
    prior = ROOT / "artifacts/DM-20261002-08" / prior_meta["run_id"]
    prior_score = prior / "predictions/scores.parquet"
    pred_paths = [output / "predictions" / (name+".parquet") for name in ["features", "scores", "standalone", "standalone_"+A, "standalone_"+B]]
    firewall.install(allowed_artifacts=saved_output_paths(output)+[prior_score]+[ROOT / p for p in prereg["prior_evidence_sha256"] if p.endswith(".parquet")])
    stage = output / "stage"; stage.mkdir(); data_hashes = {}
    for name in sv.INPUT_COLUMNS:
        p = ROOT / config["input_dir"] / (name+"_train.parquet")
        (stage / p.name).symlink_to(p); data_hashes[p.name] = sha(p)
    # Target is deliberately absent from the prediction stage until all inference checks pass.
    paths = [Path(__file__), ROOT / "research/evaluation.py", ROOT / "research/firewall.py", ROOT / "stock_comp_2026/evaluate_script.py"]
    paths += [ROOT / "research/experiments" / (n+".py") for n in ["sector_momentum", "sector_confirmation", "industry_momentum_stock_reversal", "hierarchical_momentum"]]
    for slug in ["dm_baseline_sector_veto", "dm_trainonly", "dm_sector_confirmation"]:
        paths += sorted((ROOT / "stock_comp_2026/strategies" / slug).glob("*.py"))
    paths += [ROOT / "tests/strategies/dm_baseline_sector_veto/test_features.py"]
    code_hashes = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    for p in paths:
        dest = output / "code" / p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    shutil.copyfile(ROOT / "experiments" / config["experiment_id"] / "preregistration.json", output / "preregistration.json")
    run.update(status="running", command=sys.argv, code_sha256=code_hashes, train_data_sha256=data_hashes, actual_trials=0,
        environment={"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__, "pyarrow": pyarrow.__version__, "scipy": scipy.__version__, "platform": platform.platform()})
    dump(output / "run.json", run)
    dump(output / "audit/pre_result_lock.json", {"at_utc": datetime.now(timezone.utc).isoformat(), "plan_sha256": sha(output / "plan.md"), "config_sha256": sha(output / "config.json"), "code_sha256": code_hashes, "target_loaded": False, "max_trials": 2, "trials": list(sv.CANDIDATES)})
    dump(output / "audit/source_scan.json", source_scan())
    inputs = sv.load_train(stage); f = sv.build_features(inputs)
    assert f.index.equals(sv.canonical(inputs["raw_return_1day"]).index)
    assert np.isfinite(f[["BASELINE", A, B]].to_numpy()).all()
    dump(output / "audit/baseline_parity.json", baseline_parity(inputs, f, prior_score))
    dump(output / "audit/prefix_invariance.json", prefix_audit(inputs, f, config))
    signals = {"BASELINE": f.BASELINE.rename("Return"), **{n: sv.score(f, n) for n in sv.CANDIDATES}}
    for name in sv.CANDIDATES:
        exact(signals[name].to_frame(), submission.predict(stage, name))
    dump(output / "audit/adapter_parity.json", {"status": "PASS", "bitwise": True, "rows": len(f), "candidates": list(sv.CANDIDATES)})
    standalone_smoke(stage, output, signals)
    denials = []
    for name in ["target_1day_valid.parquet", "raw_target_1day_train.parquet", "unknown.parquet"]:
        try:
            pd.read_parquet(stage / name)
        except PermissionError as e:
            denials.append({"path": name, "reason": str(e)})
        else:
            raise AssertionError("Forbidden source accepted")
    assert not any("target_1day" in p for p in firewall.ACCESSES)
    dump(output / "audit/prediction_firewall.json", {"status": "PASS", "opened_before_target": sorted(firewall.ACCESSES), "denied": denials, "feature_only_stage": True})
    f.to_parquet(pred_paths[0]); pd.DataFrame(signals).to_parquet(pred_paths[1])
    calendar = f.index.get_level_values("Date").unique().sort_values()
    dates, purge = fold_dates(calendar, [x["year"] for x in config["walk_forward_folds"]])
    dump(output / "audit/purge.json", {"status": "PASS", "folds": purge})
    cover = coverage(f, dates, output / "metrics")
    dump(output / "audit/coverage.json", {"status": "PASS", "all_train_rows": len(f), "evaluation_rows": int(f.index.get_level_values("Date").isin(dates).sum()), "finite_predictions": True, "exact_index": True})
    print("All inference/causality/bitwise baseline checks PASS; now load Train target", flush=True)
    target_path = ROOT / config["input_dir"] / "target_1day_train.parquet"
    (stage / target_path.name).symlink_to(target_path); data_hashes[target_path.name] = sha(target_path)
    target = sv.canonical(pd.read_parquet(stage / target_path.name)).Return
    assert target.index.equals(f.index)
    daily, holdings, parity = {}, {}, {}
    for name, signal in signals.items():
        daily[name], h, parity[name] = account(signal, target)
        holdings[name] = enrich_holdings(h)
        daily[name].to_csv(output / "metrics" / ("daily_"+name+".csv"))
        if name!="BASELINE":
            run["actual_trials"] += 1; dump(output / "run.json", run)
        print(f"{name}: official account saved", flush=True)
    previous = pd.read_csv(prior / "metrics/daily_MOM60.csv", index_col="Date", parse_dates=["Date"], float_precision="round_trip")
    exact(daily["BASELINE"], previous)
    dump(output / "audit/official_accounting_parity.json", {"status": "PASS", "strategies": parity, "saved_baseline_daily_bitwise": True})
    results = pd.DataFrame([{"strategy": name, "scope": scope, **metrics(d.loc[ds])} for name, d in daily.items() for scope, ds in [("ALL_TRAIN", calendar)]+scopes(dates)])
    results.to_csv(output / "metrics/metrics.csv", index=False)
    results.loc[results.scope=="POOLED"].to_csv(output / "metrics/overall_metrics.csv", index=False)
    for fn in ["year_metrics", "fold_metrics"]:
        results.loc[results.scope.isin([str(y) for y in range(2011, 2017)])].to_csv(output / "metrics" / (fn+".csv"), index=False)
    results[["strategy", "scope"]+[c for c in results if "short" in c or "long" in c]].to_csv(output / "metrics/long_short.csv", index=False)
    results[["strategy", "scope"]+[c for c in results if c.startswith("q")]].to_csv(output / "metrics/quintiles.csv", index=False)
    increments = []
    for candidate, control in [(A, "BASELINE"), (B, "BASELINE"), (B, A)]:
        for scope in results.scope.unique():
            c = results.loc[(results.strategy==candidate) & (results.scope==scope)].iloc[0]
            b = results.loc[(results.strategy==control) & (results.scope==scope)].iloc[0]
            r = {"candidate": candidate, "control": control, "scope": scope, **{"delta_"+k: c[k]-b[k] for k in results if k not in ["strategy", "scope"]}}
            r["short_cost_effect"] = -r["delta_annual_short_cost"]
            r["gross_fraction_of_short_net_improvement"] = r["delta_annual_short_gross"]/r["delta_annual_short_net"] if r["delta_annual_short_net"]>0 else np.nan
            assert np.isclose(r["delta_annual_short_net"], r["delta_annual_short_gross"]+r["short_cost_effect"], atol=1e-15, rtol=0)
            increments.append(r)
    pd.DataFrame(increments).to_csv(output / "metrics/incremental.csv", index=False)
    pd.DataFrame(increments)[["candidate", "control", "scope", "delta_annual_short_gross", "short_cost_effect", "delta_annual_short_net", "gross_fraction_of_short_net_improvement"]].to_csv(output / "metrics/short_decomposition.csv", index=False)
    boot = {}
    for scope, ds in scopes(dates)[:2]:
        for candidate, control in config["bootstrap"]["pairs"]:
            boot[f"{scope}:{candidate}-{control}"] = {**evaluation.bootstrap_delta(daily[control].loc[ds].net, daily[candidate].loc[ds].net, **{k:config["bootstrap"][k] for k in ["seed", "block", "reps"]}),
                "days": len(ds), "point_delta": evaluation.sharpe(daily[candidate].loc[ds].net)-evaluation.sharpe(daily[control].loc[ds].net), "primary": scope=="POOLED" and candidate==B and control=="BASELINE"}
    dump(output / "metrics/bootstrap.json", boot)
    pd.DataFrame([{"contrast": k, **v} for k,v in boot.items()]).to_csv(output / "metrics/bootstrap.csv", index=False)
    decision = decisions(results, boot, cover, config); dump(output / "metrics/candidate_decision.json", decision)
    print("Exactly2 performance trials complete; fixed book diagnostics only", flush=True)
    dump(output / "audit/replacement_accounting.json", replacement(f, target, holdings, daily, dates, output / "metrics"))
    dump(output / "audit/fallback_accounting.json", fallback_attribution(f, target, holdings, dates, output / "metrics"))
    long_impact(holdings, dates, output / "metrics")
    idx = f.index[f.index.get_level_values("Date").isin(dates)]
    he = {n: h.loc[idx] for n,h in holdings.items()}; accounts = {n: d.loc[dates] for n,d in daily.items()}
    for level in [33, 17]:
        folder = output / "metrics" / f"sector{level}"; folder.mkdir()
        ff = f.loc[idx, [f"Sector{level}Code"]].rename(columns={f"Sector{level}Code": "Sector33Code"})
        concentration(ff, he, accounts, folder)
    for p,h in prereg["prior_evidence_sha256"].items():
        assert sha(ROOT / p)==h, p
    dump(output / "audit/prior_evidence_unchanged.json", {"status": "PASS", "hashes": prereg["prior_evidence_sha256"]})
    firewall.save(output / "audit/firewall.json")
    resources = {"elapsed_seconds": time.monotonic()-started, "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=="darwin" else 1024), "actual_trials": 2, "valid_evaluation": False}
    dump(output / "audit/resources.json", resources)
    report(config, output, results, decision, boot, cover)
    artifacts = {str(p.relative_to(output)): sha(p) for sub in ["audit", "metrics", "predictions", "code"] for p in (output / sub).rglob("*") if p.is_file()}
    run.update(resources); run.update(status="completed", exit_code=0, completed_at_utc=datetime.now(timezone.utc).isoformat(), artifact_sha256=artifacts, candidate_decision=decision)
    dump(output / "run.json", run)
    print(json.dumps(safe({"decision": decision, "resources": resources}), indent=2, ensure_ascii=False), flush=True)


def recover_report(config, output, run, source):
    """Reuse completed fixed-trial accounts and diagnostics; never rebuild candidates."""
    started = time.monotonic()
    source_run = json.loads((source / "run.json").read_text())
    assert source_run["status"]=="failed" and source_run["actual_trials"]==2
    assert source_run["error"]=="PermissionError: Train-only parquet guard denied removed_added_unchanged_names.parquet"
    assert sha(source / "config.json")==sha(output / "config.json")
    assert sha(source / "plan.md")==sha(output / "plan.md")
    # Frozen failed-run code snapshot, not changed live driver, remains source evidence.
    for p,h in source_run["code_sha256"].items():
        assert sha(source / "code" / p)==h, p
    for name in ["source_scan", "baseline_parity", "prefix_invariance", "adapter_parity", "standalone_smoke", "prediction_firewall", "purge", "coverage", "official_accounting_parity", "replacement_accounting", "fallback_accounting"]:
        assert json.loads((source / "audit" / (name+".json")).read_text())["status"]=="PASS", name
    prereg = json.loads((source / "preregistration.json").read_text())
    preserved = {p:sha(ROOT / p) for p in prereg["prior_evidence_sha256"]}
    assert preserved==prereg["prior_evidence_sha256"]
    inventory = {str(p.relative_to(source)):sha(p) for sub in ["metrics", "audit", "predictions", "code"] for p in (source / sub).rglob("*") if p.is_file()}
    for sub in ["metrics", "audit", "predictions", "code"]:
        shutil.copytree(source / sub, output / sub, dirs_exist_ok=True)
    shutil.copyfile(source / "preregistration.json", output / "preregistration.json")
    # Source final scores and stage inputs were fully checked before any target read.
    for p,h in source_run["train_data_sha256"].items():
        assert sha(ROOT / config["input_dir"] / p)==h, p
    firewall.install(allowed_artifacts=saved_output_paths(output))
    feature = pd.read_parquet(output / "predictions/features.parquet")
    scores = pd.read_parquet(output / "predictions/scores.parquet")
    for n in ["BASELINE", A, B]:
        exact(feature[n], scores[n])
    results = pd.read_csv(output / "metrics/metrics.csv", dtype={"scope":str}, float_precision="round_trip")
    cover = pd.read_csv(output / "metrics/coverage.csv", dtype={"scope":str}, float_precision="round_trip")
    boot = json.loads((output / "metrics/bootstrap.json").read_text())
    stored_decision = json.loads((output / "metrics/candidate_decision.json").read_text())
    decision = decisions(results, boot, cover, config)
    assert safe(decision)==stored_decision
    dump(output / "audit/prior_evidence_unchanged.json", {"status":"PASS", "hashes":preserved})
    recovery_hash = sha(Path(__file__))
    (output / "recovery").mkdir(); shutil.copyfile(Path(__file__), output / "recovery/baseline_sector_veto.py")
    dump(output / "audit/report_recovery.json", {"status":"PASS", "source_run":str(source.relative_to(ROOT)),
        "failure":"Runtime firewall denied hashing a preregistered past diagnostic artifact at finalization; no strategy/accounting failure",
        "source_inventory_sha256":inventory, "new_performance_trials":0, "cumulative_performance_trials":2,
        "recovery_code_sha256":recovery_hash, "source_snapshot_hashes_verified":True, "source_accounts_scores_diagnostics_reused":True})
    begin = datetime.fromisoformat(json.loads((source / "audit/pre_result_lock.json").read_text())["at_utc"])
    end = datetime.fromisoformat(source_run["completed_at_utc"])
    resources = {"report_recovery_seconds":time.monotonic()-started,
        "report_recovery_peak_rss_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=="darwin" else 1024),
        "science_pre_result_lock_to_failure_seconds":(end-begin).total_seconds(), "science_peak_rss_bytes":None,
        "science_peak_rss_limitation":"Original process stopped before its end-of-run resource record; standalone inference RSS/time retained; no extra scientific replay for profiling", "actual_trials":0, "cumulative_performance_trials":2, "valid_evaluation":False}
    dump(output / "audit/resources.json", resources)
    report(config, output, results, decision, boot, cover)
    destination = ROOT / config["report_dir"]
    with (destination / "REPORT.md").open("a") as stream:
        stream.write("\nScientific run completed2trials/all diagnostics but failed while its firewall hashed a prior diagnostic parquet. Original failed run retained unchanged. This recovery uses identical saved scores/accounts/diagnostics and verifies421prior evidence hashes and original code snapshots;0additional performance trials. No plan/config/strategy changes. Science peakRSS was not recorded before finalization failed; isolated inference resources remain in audit/standalone_smoke.json.\n")
    meta_path = ROOT / "experiments" / config["experiment_id"] / "experiment.json"
    meta = json.loads(meta_path.read_text()); meta.update(scientific_run_id=source.name, report_recovery_run_id=output.name, actual_trials=2); dump(meta_path, meta)
    artifacts = {str(p.relative_to(output)):sha(p) for sub in ["audit", "metrics", "predictions", "code", "recovery"] for p in (output / sub).rglob("*") if p.is_file()}
    run.update(status="completed", exit_code=0, actual_trials=0, cumulative_actual_trials=2, recovery_source=str(source.relative_to(ROOT)),
        command=sys.argv, code_sha256=source_run["code_sha256"], recovery_code_sha256=recovery_hash,
        train_data_sha256=source_run["train_data_sha256"], environment=source_run["environment"], artifact_sha256=artifacts,
        candidate_decision=safe(decision), resources=resources, completed_at_utc=datetime.now(timezone.utc).isoformat())
    dump(output / "run.json", run)
    print(json.dumps(safe({"decision":decision,"resources":resources}),indent=2,ensure_ascii=False),flush=True)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--config", required=True); parser.add_argument("--output", required=True)
    parser.add_argument("--recover-from")
    args = parser.parse_args(); output = Path(args.output).resolve(); config = json.loads(Path(args.config).read_text())
    assert Path(args.config).resolve()==output / "config.json"
    assert config["data_split"]=="train" and config["valid_evaluation"] is False and config["max_trials"]==2
    assert config["trials"]==[{"trial_id":n} for n in sv.CANDIDATES]
    assert config["parameters"]=={"horizon":60,"skip":1,"min_periods":60,"sector33_min_finite_members":5,"sector17_min_finite_members":10,"alpha":.25,"ewm_adjust":False,"relisting_gap":20}
    assert config["bootstrap"]["seed"]==20261002 and config["bootstrap"]["block"]==20 and config["bootstrap"]["reps"]==2000
    run = json.loads((output / "run.json").read_text()); assert run["status"]=="prepared"
    try:
        if args.recover_from:
            recover_report(config, output, run, Path(args.recover_from).resolve())
        else:
            main_work(config, output, run)
    except BaseException as e:
        run.update(status="failed", exit_code=1, error=f"{type(e).__name__}: {e}", completed_at_utc=datetime.now(timezone.utc).isoformat())
        dump(output / "run.json", run)
        if firewall._PATCHED:
            firewall.save(output / "audit/firewall.json")
        raise


if __name__=="__main__":
    main()
