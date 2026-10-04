"""Exactly three fixed Train-only hierarchical Momentum trials and diagnostics."""
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
from research.experiments.sector_momentum import sha, dump, safe, exact, account, metrics, fold_dates, mutate, daily_corr, persistence, table
from stock_comp_2026.strategies.dm_hierarchical_momentum import features as hm, primitives, submission
from stock_comp_2026.strategies.dm_trainonly import features as old


def source_scan():
    paths = sorted((ROOT / "stock_comp_2026/strategies/dm_hierarchical_momentum").glob("*.py"))
    findings = []
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if any(t in node.value for t in ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose",
                       "AdjustmentVolume", "raw_target", "target_1day", "_valid.parquet", "Sector17"]):
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
            "manual_review": "Self-inclusive same-date finite member mean; PIT33 exact projection; raw residual60 lag1; per-Code trailing EWMA and same-date sample zscore; no LOO or fitted/label path."}


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
            got = hm.build_features(changed).loc[idx]
            exact(base.loc[idx], got)
            for candidate in hm.CANDIDATES:
                exact(hm.score(base.loc[idx], candidate), hm.score(got, candidate))
            cases.append({"cutoff": cutoff, "source": name, "status": "PASS", "bitwise": True,
                          "prefix_rows": len(idx), "all_features_including_EWMA_Z_control": True})
        print(f"hierarchy prefix {cutoff}: PASS all sources/membership/truncation", flush=True)
    exact(base, hm.build_features(inputs))
    exact(base, hm.build_features({n: x.sample(frac=1, random_state=9) for n, x in inputs.items()}))
    return {"status": "PASS", "cases": cases, "row_shuffle": True, "deterministic_rebuild": True,
            "comparison": "Exact index/columns/dtypes/string values, float64 uint64 bits including NaN; no tolerance",
            "suffix_mutation": "Each/joint returns beta TOPIX, PIT sector/member changes, row deletion, future-only added stocks, full input truncation"}


def primitive_parity(inputs, f):
    for name in ["smooth", "segment_keys", "centered_rank"]:
        assert inspect.getsource(getattr(primitives, name)) == inspect.getsource(getattr(old, name))
    control = old.smooth(old.build_momentum(inputs), .25).rename("MOM60")
    exact(control, f.MOM60)
    with patch.object(old, "centered_rank", side_effect=lambda v: v):
        raw = old.build_momentum(inputs).rename("StockMom60_raw")
    exact(raw, f.StockMom60_raw)
    return {"status": "PASS", "raw_primitive_bitwise": True, "MOM60_bitwise": True,
            "unchanged_primitive_source": ["smooth", "segment_keys", "centered_rank"],
            "raw_reference_method": "Observe existing build_momentum value before final rank with temporary rank identity in audit only; frozen source never edited"}


def identity_audit(f):
    joint = f[["StockMom60_raw", "Sector33Common_raw", "Within33_raw"]].notna().all(axis=1)
    raw = (f.StockMom60_raw - f.Sector33Common_raw - f.Within33_raw).loc[joint]
    error = f.StockMom60_ewm_diagnostic - f.Sector33Common_ewm - f.Within33_ewm
    unexplained = error - f.NeutralDefect_ewm
    assert raw.abs().max() <= 1e-14
    assert unexplained.abs().max() <= 1e-14
    constancy = f.Sector33Common_raw.groupby([f.index.get_level_values("Date"), f.Sector33Code]).nunique()
    assert (constancy <= 1).all()
    return {"status": "PASS", "raw_valid_rows": int(joint.sum()), "max_raw_identity_error": raw.abs().max(),
            "raw_common_within_sector_constancy": True, "max_smoothed_identity_error": error.abs().max(),
            "smoothed_identity_fraction_within_1e14": (error.abs() <= 1e-14).mean(),
            "global_smoothed_identity_holds": bool((error.abs() <= 1e-14).all()),
            "max_unexplained_after_EWMA_neutral_defect": unexplained.abs().max(),
            "max_smoothed_error_on_joint_raw_valid_rows": error.loc[joint].abs().max(),
            "reason": "Different raw availability masks independently neutralized0; Stock0-common0-within0 is not always0, and its Code EWMA exactly explains the smoothed discrepancy within floating precision. Control smooths centered ranks and is not a raw identity term.",
            "identity_tolerance_only": 1e-14, "prefix_tolerance": 0}


def scopes(dates):
    return [("POOLED", dates), ("EX2016", dates[dates.year != 2016])] + [(str(y), dates[dates.year == y]) for y in range(2011, 2017)]


def coverage(f, folder, dates):
    rows, masks = [], {
        "HIER33_SECTOR": f.Sector33Common_raw.notna(),
        "HIER33_WITHIN": f.Within33_raw.notna(),
        "HIER33_COMBINED": f.Sector33Common_raw.notna() & f.Within33_raw.notna(),
    }
    for name, mask in masks.items():
        for scope, ds in [("ALL_TRAIN", f.index.get_level_values("Date").unique())] + scopes(dates):
            keep = f.index.get_level_values("Date").isin(ds)
            rows.append({"strategy": name, "scope": scope, "rows": int(keep.sum()),
                "raw_finite_coverage": mask.loc[keep].mean(), "adapter_finite_coverage": 1.,
                "missing_sector_rows": int((keep & f.Sector33Code.isna()).sum()),
                "too_few_members_rows": int((keep & (f.FiniteMembers < 5)).sum()),
                "own_history_missing_rows": int((keep & f.StockMom60_raw.isna()).sum())})
    frame = pd.DataFrame(rows)
    frame.to_csv(folder / "coverage.csv", index=False)
    return frame


def tie_diagnostic(signals, f, folder):
    rows, memberships = [], []
    for strategy, score in signals.items():
        score = score.loc[f.index]
        w, q = evaluation.weights(score)
        n = score.groupby("Date").transform("size")
        code_rank = score.groupby("Date").cumcount() / (n - 1)
        scale = score.abs().groupby("Date").transform("max").clip(lower=1.)
        perturbed = score - 1e-12 * scale * (code_rank - .5)
        wp, qp = evaluation.weights(perturbed)
        keys = [score.index.get_level_values("Date"), score]
        count = score.groupby(keys).transform("size")
        within_tie_order = score.groupby(keys).cumcount()
        membership = pd.DataFrame({"score": score, "sector": f.Sector33Code, "tie_size": count,
            "Code_tie_ordinal": within_tie_order, "Code_date_percentile": code_rank,
            "official_q": q + 1, "tiny_perturbed_q": qp + 1}, index=score.index).loc[count > 1]
        membership["strategy"] = strategy
        memberships.append(membership.reset_index())
        ordered = pd.DataFrame({"score": score, "perturbed": perturbed}).reset_index().sort_values(["Date", "score", "Code"])
        unequal = ordered.groupby("Date").score.diff().gt(0)
        reversal = unequal & ordered.groupby("Date").perturbed.diff().lt(0)
        near_reversal = reversal.groupby(ordered.Date).sum()
        for date, s in score.groupby("Date"):
            now_q, changed_q = q.loc[s.index], qp.loc[s.index]
            row = {"Date": date, "strategy": strategy, "rows": len(s), "unique_scores": s.nunique(),
                "exact_tie_share": (count.loc[s.index] > 1).mean(), "largest_tie_share": count.loc[s.index].max() / len(s),
                "tail_migration_share": (now_q != changed_q).mean(),
                "weight_l1_change": (w.loc[s.index] - wp.loc[s.index]).abs().sum(),
                "max_perturbation": (score.loc[s.index] - perturbed.loc[s.index]).abs().max(),
                "changed_unequal_adjacent_score_orders": near_reversal.get(date, 0)}
            for tail, value in [("Q1", 0), ("Q5", 4)]:
                a, b = now_q == value, changed_q == value
                row[f"{tail}_membership_jaccard"] = (a & b).sum() / (a | b).sum()
                row[f"{tail}_exact_tie_share"] = (count.loc[s.index].loc[a] > 1).mean()
                row[f"{tail}_mean_Code_date_percentile"] = code_rank.loc[s.index].loc[a].mean()
                shares = f.Sector33Code.loc[s.index].loc[a].fillna("UNKNOWN").value_counts(normalize=True)
                row[f"{tail}_max_same_sector_share"] = shares.max()
            rows.append(row)
    d = pd.DataFrame(rows)
    d.to_csv(folder / "tie_sensitivity_daily.csv", index=False)
    d.groupby("strategy").mean(numeric_only=True).reset_index().to_csv(folder / "tie_sensitivity.csv", index=False)
    pd.concat(memberships).to_csv(folder / "Code_tie_tail_membership.csv", index=False)
    return {"status": "PASS", "one_fixed_perturbation": "score-1e-12*max(1,date maxabs)*centered same-date Code percentile",
            "perturbed_PL_evaluated": False, "new_performance_candidates": 0,
            "interpretation": "Sensitivity of official tail membership/weights only; also record unequal adjacent near-score order changes. No random tie break or outcome search."}


def rank_changes(signals, calendar, dates, folder):
    rows, daily = [], []
    for name, score in signals.items():
        rank = score.groupby("Date").rank(method="average", pct=True)
        ordinal = pd.Series(calendar.get_indexer(score.index.get_level_values("Date")), index=score.index)
        adjacent = (ordinal - ordinal.groupby("Code").shift(1)) == 1
        change = rank.groupby("Code").diff().where(adjacent)
        frame = pd.DataFrame({"mean_abs_rank_change": change.abs().groupby("Date").mean(),
            "p95_abs_rank_change": change.abs().groupby("Date").quantile(.95),
            "max_abs_rank_change": change.abs().groupby("Date").max()}).loc[dates]
        frame["strategy"] = name
        daily.append(frame.rename_axis("Date").reset_index())
        for scope, ds in scopes(dates):
            x = change.loc[change.index.get_level_values("Date").isin(ds)].dropna()
            rows.append({"strategy": name, "scope": scope, "rows": len(x), "mean": x.mean(),
                         "mean_abs": x.abs().mean(), "max_abs": x.abs().max(),
                         **{f"q{q:g}": x.quantile(q) for q in [.005, .05, .25, .5, .75, .95, .995]}})
    pd.DataFrame(rows).to_csv(folder / "rank_change_distribution.csv", index=False)
    pd.concat(daily).to_csv(folder / "rank_change_daily.csv", index=False)


def sector_concentration(f, holdings, accounts, folder):
    dates = f.index.get_level_values("Date").unique().sort_values()
    sector = f.Sector33Code.fillna("UNKNOWN")
    keys = [f.index.get_level_values("Date"), sector]
    exposures, summaries, daily_concentration, contributions, top2, loso = [], [], [], [], [], []
    for name, h in holdings.items():
        grouped = pd.DataFrame({"long_weight": h.w.clip(lower=0), "short_weight": (-h.w).clip(lower=0),
            "gross_weight": h.w.abs(), "Q1_count": h.q.eq(0).astype(float), "Q5_count": h.q.eq(4).astype(float),
            "gross": h.gross.fillna(0), "net": h.net, "cost": h.cost,
            "long_gross": h.gross.where(h.w > 0, 0).fillna(0), "short_gross": h.gross.where(h.w < 0, 0).fillna(0),
            "long_net": h.gross.where(h.w > 0, 0).fillna(0)-h.long_cost,
            "short_net": h.gross.where(h.w < 0, 0).fillna(0)-h.short_cost}, index=f.index).groupby(keys).sum()
        grouped.index.names = ["Date", "sector"]
        exposure = grouped.copy()
        for col in ["long_weight", "short_weight", "gross_weight", "Q1_count", "Q5_count"]:
            shares = grouped[col] / grouped[col].groupby("Date").transform("sum").where(lambda v: v > 0)
            exposure[col + "_share"] = shares
            stats = pd.DataFrame({"HHI": (shares*shares).groupby("Date").sum(), "max_sector_weight": shares.groupby("Date").max()})
            stats["strategy"], stats["measure"] = name, col
            daily_concentration.append(stats.reset_index())
            for code, value in (shares.groupby("sector").sum() / len(dates)).items():
                summaries.append({"strategy": name, "measure": col, "sector": code, "mean_daily_sector_share": value,
                    "mean_daily_HHI": stats.HHI.mean(), "mean_daily_max_sector_weight": stats.max_sector_weight.mean(),
                    "daily_max_sector_concentration": stats.max_sector_weight.max()})
        exposure["strategy"] = name
        exposures.append(exposure.reset_index())
        for scope, ds in scopes(dates):
            subset = grouped.loc[grouped.index.get_level_values("Date").isin(ds)]
            block = subset.groupby("sector").sum() / len(ds) * 252
            for code, row in block.iterrows():
                contributions.append({"strategy": name, "scope": scope, "sector": code,
                    **{f"annual_{col}": row[col] for col in ["gross", "net", "cost", "long_gross", "short_gross", "long_net", "short_net"]}})
            highest = block.nlargest(2, "gross")
            top2.append({"strategy": name, "scope": scope, "top2_sector_codes": ",".join(highest.index.astype(str)),
                         "top2_annual_gross": highest.gross.sum(), "top2_annual_net": highest.net.sum(),
                         "top2_fraction_of_total_gross": highest.gross.sum() / accounts[name].loc[ds].gross.mean() / 252})
        for code, block in grouped.groupby("sector"):
            for scope, ds in scopes(dates):
                removed_g = accounts[name].loc[ds].gross - block.gross.droplevel("sector").reindex(ds, fill_value=0)
                removed_n = accounts[name].loc[ds].net - block.net.droplevel("sector").reindex(ds, fill_value=0)
                loso.append({"strategy": name, "scope": scope, "excluded_sector": code,
                    "annual_gross": removed_g.mean()*252, "annual_net": removed_n.mean()*252,
                    "gross_sharpe": evaluation.sharpe(removed_g), "net_sharpe": evaluation.sharpe(removed_n),
                    "method": "original portfolio minus attributed sector; no rerank/renormalization"})
        sums = grouped[["gross", "net", "cost"]].groupby("Date").sum()
        assert np.allclose(sums, accounts[name][["gross", "net", "cost"]], atol=1e-15, rtol=0)
    pd.concat(exposures).to_csv(folder / "sector_exposure_daily.csv", index=False)
    pd.concat(daily_concentration).to_csv(folder / "sector_concentration_daily.csv", index=False)
    pd.DataFrame(summaries).to_csv(folder / "sector_concentration.csv", index=False)
    pd.DataFrame(contributions).to_csv(folder / "sector_contribution.csv", index=False)
    pd.DataFrame(top2).to_csv(folder / "top2_sector_contribution.csv", index=False)
    pd.DataFrame(loso).to_csv(folder / "leave_one_sector_out.csv", index=False)


def common_alpha(f, target, folder):
    keys = [f.index.get_level_values("Date"), f.Sector33Code]
    panel = pd.DataFrame({"raw_common": f.Sector33Common_raw, "smoothed_common": f.Sector33Common_ewm,
                         "target": target, "stock": f.StockMom60_raw}).groupby(keys).agg(
        raw_common=("raw_common", "mean"), smoothed_common=("smoothed_common", "mean"),
        forward_target=("target", "mean"), finite_members=("stock", "count"))
    panel.index.names = ["Date", "sector"]
    panel = panel.loc[panel.raw_common.notna()]
    rank = panel.smoothed_common.groupby("Date").rank(method="average", pct=True)
    panel["bucket"] = np.ceil(3*rank).clip(1, 3).map({1: "LOW", 2: "MIDDLE", 3: "HIGH"})
    panel.to_csv(folder / "sector_common_daily.csv")
    dispersion = panel.groupby("Date")[["raw_common", "smoothed_common"]].std()
    dispersion.to_csv(folder / "sector_common_dispersion_daily.csv")
    dates = f.index.get_level_values("Date").unique().sort_values()
    by_bucket = panel.groupby(["Date", "bucket"]).forward_target.mean()
    rows = []
    for scope, ds in scopes(dates):
        now = panel.loc[panel.index.get_level_values("Date").isin(ds)]
        for bucket in ["LOW", "MIDDLE", "HIGH"]:
            t = by_bucket.loc[by_bucket.index.get_level_values("bucket") == bucket].droplevel("bucket").reindex(ds)
            rows.append({"scope": scope, "bucket": bucket, "equal_sector_equal_date_forward_target": t.mean(),
                         "sector_days": int((now.bucket == bucket).sum())})
    pd.DataFrame(rows).to_csv(folder / "sector_common_bucket.csv", index=False)
    renamed = panel.rename_axis(index=["Date", "Code"])
    ic = evaluation.rankic(renamed.smoothed_common, renamed.forward_target)
    ic.rename("cross_sector_RankIC").to_csv(folder / "sector_common_cross_sector_rankic_daily.csv")
    pd.DataFrame([{"scope": scope, "rankic": ic.reindex(ds).mean(), "HAC5_t": evaluation.hac_t(ic.reindex(ds)),
                   "hit_ratio": (ic.reindex(ds).dropna() > 0).mean()} for scope, ds in scopes(dates)]).to_csv(folder / "sector_common_cross_sector_rankic.csv", index=False)


def within_alpha(f, target, holdings, folder):
    dates = f.index.get_level_values("Date").unique().sort_values()
    sector = f.Sector33Code
    keys = [f.index.get_level_values("Date"), sector]
    score = f.Within33_ewm.where(f.Within33_raw.notna())
    good = score.notna() & target.notna()
    x = score.where(good).groupby(keys).rank()
    y = target.where(good).groupby(keys).rank()
    x -= x.groupby(keys).transform("mean")
    y -= y.groupby(keys).transform("mean")
    ic = (x*y).groupby(keys).sum() / np.sqrt((x*x).groupby(keys).sum()*(y*y).groupby(keys).sum())
    ic.index.names = ["Date", "sector"]
    rank = score.groupby(keys).rank(method="first")
    n = score.groupby(keys).transform("count")
    q = (np.ceil(5*(rank-1)/(n-1).where(n > 1))-1).clip(0, 4)
    daily = ic.to_frame("RankIC")
    for i in range(5):
        ret = target.where(q == i).groupby(keys).mean()
        ret.index.names = ["Date", "sector"]
        daily[f"q{i+1}_target"] = ret
    h = holdings["HIER33_WITHIN"]
    for side, mask in [("long", h.w > 0), ("short", h.w < 0)]:
        ret = h.gross.where(mask, 0).fillna(0).groupby(keys).sum()
        ret.index.names = ["Date", "sector"]
        daily[f"original_book_{side}_gross"] = ret
    daily.to_csv(folder / "within_sector_daily.csv")
    rows = []
    for code, d in daily.groupby("sector"):
        d = d.droplevel("sector")
        for scope, ds in scopes(dates):
            part = d.reindex(ds)
            means = [part[f"q{i}_target"].mean() for i in range(1, 6)]
            rows.append({"sector": code, "scope": scope, "RankIC": part.RankIC.mean(), "HAC5_t": evaluation.hac_t(part.RankIC),
                "IC_days": int(part.RankIC.notna().sum()), "IC_hit": (part.RankIC.dropna() > 0).mean(),
                "annual_original_book_long_gross": part.original_book_long_gross.fillna(0).mean()*252,
                "annual_original_book_short_gross": part.original_book_short_gross.fillna(0).mean()*252,
                **{f"q{i+1}_daily_target": v for i, v in enumerate(means)}})
    pd.DataFrame(rows).to_csv(folder / "within_sector.csv", index=False)


def agreement(f, target, holdings, folder):
    dates = f.index.get_level_values("Date").unique().sort_values()
    s, c = f.StockMom60_raw, f.Sector33Common_raw
    bucket = pd.Series("ZERO_OR_MISSING", index=f.index)
    for name, mask in [("A", (s > 0)&(c > 0)), ("B", (s > 0)&(c < 0)), ("C", (s < 0)&(c > 0)), ("D", (s < 0)&(c < 0))]:
        bucket.loc[mask] = name
    rows, daily_rows = [], []
    for b in ["A", "B", "C", "D", "ZERO_OR_MISSING"]:
        mask = bucket == b
        mean = target.where(mask).groupby("Date").mean().reindex(dates)
        ic = {name: evaluation.rankic(value.where(mask), target) for name, value in
              [("stock", s), ("sector", c), ("within", f.Within33_ewm)]}
        for strategy in ["MOM60", "HIER33_COMBINED"]:
            h = holdings[strategy]
            block = pd.DataFrame({"forward_target_mean": mean, **{name+"_RankIC": v for name, v in ic.items()}})
            for col in ["gross", "net", "cost"]:
                block[col] = h[col].where(mask, 0).groupby("Date").sum().reindex(dates, fill_value=0)
            for side, side_mask in [("long", h.w > 0), ("short", h.w < 0)]:
                g = h.gross.where(mask & side_mask, 0).fillna(0).groupby("Date").sum().reindex(dates, fill_value=0)
                cost = h[side+"_cost"].where(mask, 0).groupby("Date").sum().reindex(dates, fill_value=0)
                block[side+"_gross"], block[side+"_net"] = g, g-cost
            for scope, ds in scopes(dates):
                d = block.reindex(ds)
                rows.append({"strategy": strategy, "bucket": b, "scope": scope, "forward_target_mean": d.forward_target_mean.mean(),
                    **{name+"_RankIC": d[name+"_RankIC"].mean() for name in ic},
                    **{name+"_HAC5_t": evaluation.hac_t(d[name+"_RankIC"]) for name in ic},
                    **{"annual_"+col: d[col].mean()*252 for col in ["gross", "net", "cost", "long_gross", "short_gross", "long_net", "short_net"]}})
            block["strategy"], block["bucket"] = strategy, b
            daily_rows.append(block.rename_axis("Date").reset_index())
    pd.DataFrame(rows).to_csv(folder / "agreement.csv", index=False)
    pd.concat(daily_rows).to_csv(folder / "agreement_daily.csv", index=False)


def decide(accounts, cover, boot):
    result = {}
    baseline = metrics(accounts["MOM60"])
    base_ex = metrics(accounts["MOM60"].loc[accounts["MOM60"].index.year != 2016])
    for name in hm.CANDIDATES:
        d = accounts[name]
        m, ex = metrics(d), metrics(d.loc[d.index.year != 2016])
        years = [metrics(d.loc[d.index.year == y]) for y in range(2011, 2016)]
        cov = cover.loc[(cover.strategy == name)&(cover.scope == "POOLED")].iloc[0].raw_finite_coverage
        feasibility = {"pooled_RankIC_positive": m["rankic"] > 0,
            "pooled_GrossSR_positive": m["gross_sharpe"] > 0, "ex2016_GrossSR_positive": ex["gross_sharpe"] > 0,
            "gross_positive_3of5": sum(v["annual_gross"] > 0 for v in years) >= 3,
            "raw_coverage_ge95pct": cov >= .95, "turnover_le1p25_MOM60": m["turnover"] <= 1.25*baseline["turnover"]}
        adoption = {}
        if name == "HIER33_COMBINED":
            improvements = sum(metrics(d.loc[d.index.year == y])["net_sharpe"] > metrics(accounts["MOM60"].loc[accounts["MOM60"].index.year == y])["net_sharpe"] for y in range(2011, 2016))
            adoption = {"pooled_NetSR_gt_MOM60": m["net_sharpe"] > baseline["net_sharpe"],
                "ex2016_NetSR_gt_MOM60": ex["net_sharpe"] > base_ex["net_sharpe"],
                "NetSR_improvement_4of5": improvements >= 4, "bootstrap_lower_gt0": boot[name]["low"] > 0,
                "annual_net_gt_MOM60": m["annual_net"] > baseline["annual_net"],
                "turnover_le1p25_MOM60": m["turnover"] <= 1.25*baseline["turnover"],
                "Short_gross_ge_MOM60": m["annual_short_gross"] >= baseline["annual_short_gross"],
                "Short_net_ge_MOM60": m["annual_short_net"] >= baseline["annual_short_net"],
                "Q_monotonicity_positive": m["q_monotonicity"] > 0}
        all_checks = {**feasibility, **adoption}
        passed = all(all_checks.values())
        result[name] = {"decision": ("NEXT_STAGE_ELIGIBLE" if adoption else "DESCRIPTIVE_COMPONENT_ONLY") if passed else "REJECT",
            "feasibility": feasibility, "adoption": adoption, "failed_checks": [k for k, v in all_checks.items() if not v],
            "no_release_adoption": True, "raw_coverage": cov}
    return result


def report_results(config, output, results, decision, boot):
    report = ROOT / config["report_dir"]
    report.mkdir(parents=True, exist_ok=True)
    for sub in ["metrics", "audit"]:
        shutil.copytree(output / sub, report / sub)
    pooled = results.loc[results.scope == "POOLED"]
    lines = [f"# {config['experiment_id']} — Sector33 common/within hierarchical Momentum", "",
        "All three pre-registered performance trials completed on known Train history. Prior experiment's three candidates remain REJECT. No independent OOS claim, Valid, release, Freeze or external submission.", "",
        f"Run `{output.relative_to(ROOT)}`. Self-inclusive Sector33 finite-stock mean, minimum5, and raw Within=Stock−Common; fixed60 observations/skip1. Both raw components independently neutral0 then unchanged per-Code/relisting EWMA(.25). Combined=same-date sample z(Sector EWM)+z(Within EWM), fixed1:1, no additional smoothing. MOM60 remains centered-rank-before-EWMA. Same operator/alpha does not make raw-before-EWMA equivalent to rank-before-EWMA.", "",
        "## Overall2011–2016 partial, matched official accounting", "",
        table(pooled, ["strategy", "rankic", "rankic_t_hac5", "gross_sharpe", "net_sharpe", "annual_gross", "annual_net", "turnover", "annual_cost", "annual_short_gross", "annual_short_net"]), "",
        "All P/L decimal fractions; arithmetic daily mean×252 annualized, sample-SD Sharpe×sqrt252, HAC/Bartlett lag5, compound and additive DD. period_* are actual sums, annual_* annualizations including2016 partial. Official five-quintile Code order/10bp one-way; continuous accounting before final2-date annual purge. Missing-target cost omission matches official scorer; all-position conservative net/cost recorded separately. Long/Short gross/net/Sharpe/cost and Q1–Q5/hit/DD are in metrics.csv.", "",
        "## Full-year fold metrics and2016 partial", "",
        table(results.loc[results.scope.isin([str(y) for y in range(2011, 2017)])], ["strategy", "scope", "rankic", "gross_sharpe", "net_sharpe", "annual_net", "turnover", "annual_short_gross", "annual_short_net"]), "",
        "## Fixed feasibility and combined eligibility", "", "```json", json.dumps(safe(decision), indent=2), "```", "",
        "A/B are descriptive component identification, not selectable standalone replacements. Combined must satisfy all user-fixed feasibility/adoption criteria; failure does not trigger weights, alpha, filters, side changes or sector exclusion. Components/diagnostics remain saved regardless of gates.", "",
        "## Paired circular20-session ΔNetSR bootstrap vs MOM60", "", "```json", json.dumps(safe(boot), indent=2), "```", "",
        "2000 paired draws, seed20261002, percentile95% intervals, same eligible dates for candidate/control. Blocks run over concatenated eligible sessions including gaps left by purge. Intervals describe known-Train sampling variation, not independent OOS or multiplicity-adjusted assurance.", "",
        "## Interpretation conventions and saved diagnostics", "",
        "Raw common is exactly equal inside a PIT sector/date and includes own observed stock; no LOO negative own coefficient. Its smoothed per-Code history can differ for new stocks, relistings and sector changes because the existing Code EWMA carries state across sector changes. This history effect and ties are measured. Raw decomposition identity is tested on joint-finite rows. Missing components independently neutralized0 can violate smoothed identity; EWMA(Stock0−Common0−Within0) must explain the entire discrepancy within1e−14. Prefix comparisons remain bitwise with zero tolerance. Full real identity error and explanation are in audit/decomposition_identity.json.", "",
        "tie_sensitivity*.csv reports unique scores/exact tied-row share, Code ranks in Q1/Q5, same-sector concentration and one tiny deterministic score perturbation's membership/Jaccard/weight changes. Code_tie_tail_membership.csv saves tied-row tail allocation. No perturbed P/L, random tie-breaking, candidate or performance search is evaluated. The perturbation can also reorder numerically near but unequal adjacent scores, explicitly counted.", "",
        "sector_common_daily.csv saves sector mean raw/smoothed signal, finite members and mean future residual target; dispersion and fixed rank-thirds low/middle/high buckets are descriptive. Cross-sector RankIC uses equal sector mean target. within_sector*.csv saves each sector's finite-raw smoothedWithin RankIC/HAC5 and deterministic internal quintile target means; its Long/Short gross are contributions of the ORIGINAL globally ranked Within portfolio, not an independently constructed within-sector trading rule.", "",
        "Agreement A(++),B(+-),C(-+),D(--) uses raw Stock/Common signs. agreement*.csv saves equal-date target mean, rawStock/rawCommon/smoothedWithin RankIC/HAC and original MOM60/COMBINED book gross/net/Long/Short/cost attribution. No D-only portfolio/filter is created. Attributed cost on the bucket's date rows is not a standalone bucket strategy's turnover.", "",
        "Sector33 daily exposure/normalized side weights/HHI/max/Q1Q5 shares, annual gross/net/side contribution and top2 concentration are saved. LOSO subtracts one original sector's P/L and attributed costs, without reranking/renormalization; remaining gross exposure differs, so its Sharpe is descriptive. Rank autocorrelation uses adjacent exchange dates and average percentile ranks; retention uses official quintiles; tail spells intersecting evaluation retain full contiguous observed lengths, right-censored marked. Rank-change percentiles are stock-day distributions; daily versions are also saved.", "",
        "## Causality, parity and limitations", "",
        "Static source scan, runtime Train firewall, full-feature/score/EWMA/Z/control bitwise future-mutation/truncation at3 cutoffs (four sources individually/jointly), future-only stocks/membership/source-row deletion, row shuffle/rebuild, exact index and finite adapter coverage pass. Prediction/adapter audits precede any Train target read. Existing raw primitive and MOM60 output are bitwise equal; cloned smooth/rank/segment function sources identical. Separate-process no-argument adapter smoke matches all809,636 Train rows. All raw-coverage gates use availability before neutral0; finite adapter output does not imply raw coverage passed.", "",
        "Runtime Python firewall is best-effort, not an OS-level sandbox. Mutations are exercised-case evidence rather than a mathematical proof. Supplied498-stock dataset's historical survivorship cannot be independently removed; daily membership only uses present rows with PIT33. Short P/L is signed market-residual attribution, not raw-security short return or borrow cost. Real later split/Valid/zip runtime is outside scope. Existing global make check metadata failure, if present, is reported separately from strategy tests and original Freeze hash verification.", "",
        "Full features/scores, immutable plan/config/source/environment/data hashes and resources are in the run. Metrics contain overall/fold/year/incremental/bootstrap, Long/Short cost decomposition, Q1Q5, coverage, rank persistence/changes, ties, identities, agreement, common/within alpha, sector exposure/contribution/top2 and LOSO. Technical failures remain retained; no post-result trial added."]
    (report / "REPORT.md").write_text("\n".join(lines)+"\n")
    exp = ROOT / "experiments" / config["experiment_id"]
    (exp / "decision.md").write_text(f"# {config['experiment_id']} decision\n\nKnown Train, exactly3 fixed trials; previous experiment remains rejected.\n\n" +
        "\n".join(f"- **{name}**: {d['decision']}. Failed checks: {', '.join(d['failed_checks']) or 'none'}." for name, d in decision.items()) +
        f"\n\nNo additional candidate, parameter/weight/alpha search, filtering, sector exclusion, Freeze, Valid or submission. [Report](../../{config['report_dir']}/REPORT.md). [Gates](../../{config['report_dir']}/metrics/candidate_decision.json). Run `{output.relative_to(ROOT)}`.\n")
    meta = json.loads((exp / "experiment.json").read_text())
    meta.update(status="rejected" if all(v["decision"] == "REJECT" for v in decision.values()) else "completed",
                actual_trials=3, run_id=output.name, report=f"{config['report_dir']}/REPORT.md")
    dump(exp / "experiment.json", meta)
    rejected = [name for name, d in decision.items() if d["decision"] == "REJECT"]
    if rejected:
        with (ROOT / "experiments/GRAVEYARD.md").open("a") as stream:
            stream.write(f"\n## {config['experiment_id']}: Sector33 Hierarchical Momentum\n\n[Decision]({config['experiment_id']}/decision.md) / [Report](../{config['report_dir']}/REPORT.md). Fixed3 trials; self-inclusive common/within, causalEWMA(.25), combination1:1. Known Train-only, no Valid/Freeze/rescue.\n\n")
            for name in rejected:
                m = pooled.loc[pooled.strategy == name].iloc[0]
                stream.write(f"- **{name}** — Gross/Net SR {m.gross_sharpe:.4f}/{m.net_sharpe:.4f}, turnover {m.turnover:.5f}, Short gross/net {m.annual_short_gross:+.3%}/{m.annual_short_net:+.3%}. Reject: {', '.join(decision[name]['failed_checks'])}.\n")
            stream.write("\nRejects fixed candidate definitions, not all hierarchy hypotheses. Prior DM-20261002-06 remains REJECT; no sector/side/filter/weight rescue.\n")


def standalone_smoke(stage, output, signals):
    smoke = output / "adapter_smoke"
    smoke.mkdir()
    (smoke / "input").symlink_to(stage, target_is_directory=True)
    prediction = output / "predictions/standalone.parquet"
    result = output / "audit/standalone_smoke.json"
    script = "\n".join([
        "import sys,time,resource,json,os",
        f"sys.path.insert(0, {str(ROOT)!r})",
        "from research import firewall; firewall.install()",
        f"sys.path.insert(0, {str(ROOT / 'stock_comp_2026/strategies/dm_hierarchical_momentum')!r})",
        "import submission",
        f"os.chdir({str(smoke)!r})",
        "t=time.monotonic(); p=submission.predict()",
        f"p.to_parquet({str(prediction)!r})",
        "r={'status':'PASS','rows':len(p),'finite':bool(p.notna().all().all()),'seconds':time.monotonic()-t, 'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),'opened':sorted(firewall.ACCESSES),'no_argument_predict':True}",
        f"open({str(result)!r},'w').write(json.dumps(r,indent=2)+'\\n')",
    ])
    # Keep script file as resource/provenance evidence and isolate bare imports.
    (smoke / "script.py").write_text(script+"\n")
    completed = subprocess.run([sys.executable, str(smoke / "script.py")], capture_output=True, text=True, timeout=120)
    (output / "logs/standalone.log").write_text(completed.stdout+completed.stderr)
    assert completed.returncode == 0, completed.stderr
    got = pd.read_parquet(prediction)
    exact(signals["HIER33_COMBINED"].to_frame(), got)
    record = json.loads(result.read_text())
    record["bitwise_research_parity"] = True
    dump(result, record)
    return record


def main_work(config, output, run):
    started = time.monotonic()
    stage = output / "stage"
    stage.mkdir()
    data_hashes = {}
    for name in list(hm.INPUT_COLUMNS) + ["target_1day"]:
        source = ROOT / config["input_dir"] / f"{name}_train.parquet"
        (stage / source.name).symlink_to(source)
        data_hashes[source.name] = sha(source)
    prior_exp = ROOT / "experiments" / config["prior_experiment"]
    prior_meta = json.loads((prior_exp / "experiment.json").read_text())
    prior_run = ROOT / "artifacts" / config["prior_experiment"] / prior_meta["run_id"]
    prior_score = prior_run / "predictions/scores.parquet"
    prior_saved = json.loads((prior_run / "run.json").read_text())
    assert prior_meta["status"] == "rejected" and prior_saved["status"] == "completed"
    assert sha(prior_score) == prior_saved["artifact_sha256"]["predictions/scores.parquet"]
    prior_files = [prior_exp / name for name in ["plan.md", "config.json", "decision.md", "experiment.json"]]
    prior_files += [ROOT / "reports" / config["prior_experiment"] / "REPORT.md"]
    prior_files += list((ROOT / "stock_comp_2026/strategies/dm_sector_momentum").glob("*.py"))
    prior_hashes = {str(p.relative_to(ROOT)): sha(p) for p in prior_files}
    prediction_paths = [output / "predictions" / f"{n}.parquet" for n in ["features", "scores", "standalone"]]
    firewall.install(allowed_artifacts=prediction_paths + [prior_score])
    code_paths = [Path(__file__), ROOT / "research/evaluation.py", ROOT / "research/firewall.py",
        ROOT / "research/experiments/sector_momentum.py", ROOT / "stock_comp_2026/evaluate_script.py",
        ROOT / "stock_comp_2026/strategies/dm_trainonly/features.py"]
    code_paths += sorted((ROOT / "stock_comp_2026/strategies/dm_hierarchical_momentum").glob("*.py"))
    code_hashes = {str(p.relative_to(ROOT)): sha(p) for p in code_paths}
    for path in code_paths:
        dest = output / "code" / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
    run.update(status="running", command=sys.argv, code_sha256=code_hashes, train_data_sha256=data_hashes,
        prior_evidence_sha256=prior_hashes, actual_trials=0,
        environment={"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
                     "scipy": scipy.__version__, "pyarrow": pyarrow.__version__, "platform": platform.platform()})
    dump(output / "run.json", run)
    dump(output / "audit/pre_result_lock.json", {"at_utc": datetime.now(timezone.utc).isoformat(),
        "plan_sha256": sha(output / "plan.md"), "config_sha256": sha(output / "config.json"),
        "code_sha256": code_hashes, "prior_evidence_sha256": prior_hashes, "target_read": False,
        "trials": list(hm.CANDIDATES), "max_trials": 3})
    dump(output / "audit/source_scan.json", source_scan())
    inputs = hm.load_train(stage)
    f = hm.build_features(inputs)
    assert f.index.equals(hm.canonical(inputs["raw_return_1day"]).index)
    assert np.isfinite(f[list(hm.CANDIDATES.values()) + ["MOM60"]].to_numpy()).all()
    dump(output / "audit/primitive_parity.json", primitive_parity(inputs, f))
    prior_control = pd.read_parquet(prior_score, columns=["MOM60"]).MOM60
    exact(f.MOM60, prior_control)
    dump(output / "audit/prior_control_parity.json", {"status": "PASS", "rows": len(f), "bitwise": True,
        "source": str(prior_score.relative_to(ROOT)), "source_sha256": sha(prior_score), "no_old_candidate_rerun": True})
    dump(output / "audit/prefix_invariance.json", prefix_audit(inputs, f, config))
    identity = identity_audit(f)
    dump(output / "audit/decomposition_identity.json", identity)
    signals = {name: hm.score(f, name) for name in hm.CANDIDATES}
    signals["MOM60"] = f.MOM60.rename("Return")
    for name in hm.CANDIDATES:
        exact(signals[name].to_frame(), submission.predict(stage, name))
    dump(output / "audit/adapter_parity.json", {"status": "PASS", "rows": len(f), "all_candidates_bitwise": True})
    standalone_smoke(stage, output, signals)
    denied = []
    for name in ["target_1day_valid.parquet", "raw_target_1day_train.parquet", "unknown.parquet"]:
        try:
            pd.read_parquet(stage / name)
        except PermissionError as error:
            denied.append({"path": name, "denial": str(error)})
        else:
            raise AssertionError("Forbidden path accepted")
    assert not any("target_1day" in p for p in firewall.ACCESSES)
    dump(output / "audit/firewall_denials.json", {"status": "PASS", "cases": denied})
    dump(output / "audit/prediction_source_firewall.json", {"status": "PASS", "opened": sorted(firewall.ACCESSES), "predictions_and_audits_before_any_Train_target": True})
    f.to_parquet(prediction_paths[0])
    pd.DataFrame(signals).to_parquet(prediction_paths[1])
    calendar = f.index.get_level_values("Date").unique().sort_values()
    dates, purge = fold_dates(calendar, [x["year"] for x in config["walk_forward_folds"]])
    dump(output / "audit/purge.json", {"status": "PASS", "folds": purge})
    fe = f.loc[f.index.get_level_values("Date").isin(dates)]
    cover = coverage(f, output / "metrics", dates)
    dump(output / "audit/coverage.json", {"status": "PASS", "rows": len(f), "exact_index": True, "adapter_finite": True,
         "raw_coverage_gate_before_neutral": True})
    print("Full features/EWMA/primitive/prefix/adapter PASS; now read Train target", flush=True)
    tf = hm.canonical(pd.read_parquet(stage / "target_1day_train.parquet"))
    assert tf.index.equals(f.index)
    target = tf.Return
    daily, holdings, parity = {}, {}, {}
    for name, signal in signals.items():
        daily[name], holdings[name], parity[name] = account(signal, target)
        daily[name].to_csv(output / f"metrics/daily_{name}.csv")
        if name in hm.CANDIDATES:
            run["actual_trials"] += 1
            dump(output / "run.json", run)
        print(f"fixed trial/account {name}: saved", flush=True)
    dump(output / "audit/official_accounting_parity.json", {"status": "PASS", "strategies": parity})
    accounts = {name: d.loc[dates] for name, d in daily.items()}
    rows = []
    for name, d in daily.items():
        for scope, ds in [("ALL_TRAIN", calendar)] + scopes(dates):
            rows.append({"strategy": name, "scope": scope, **metrics(d.loc[ds])})
    results = pd.DataFrame(rows)
    results.to_csv(output / "metrics/metrics.csv", index=False)
    results.loc[results.scope == "POOLED"].to_csv(output / "metrics/overall_metrics.csv", index=False)
    for name in ["fold_metrics", "year_metrics"]:
        results.loc[results.scope.isin([str(y) for y in range(2011, 2017)])].to_csv(output / f"metrics/{name}.csv", index=False)
    results[["strategy", "scope"] + [k for k in results if "long" in k or "short" in k]].to_csv(output / "metrics/long_short.csv", index=False)
    results[["strategy", "scope"] + [k for k in results if k.startswith("q")]].to_csv(output / "metrics/quintiles.csv", index=False)
    increments = []
    for name in hm.CANDIDATES:
        for scope in results.scope.unique():
            c = results.loc[(results.strategy == name)&(results.scope == scope)].iloc[0]
            b = results.loc[(results.strategy == "MOM60")&(results.scope == scope)].iloc[0]
            increments.append({"strategy": name, "scope": scope, "control": "MOM60",
                **{"delta_"+key: c[key]-b[key] for key in ["rankic", "gross_sharpe", "net_sharpe", "turnover", "annual_cost", "annual_gross", "annual_net", "annual_short_gross", "annual_short_net", "annual_short_cost", "annual_long_gross", "annual_long_net", "annual_long_cost"]}})
    increment = pd.DataFrame(increments)
    assert np.allclose(increment.delta_annual_short_net, increment.delta_annual_short_gross-increment.delta_annual_short_cost, atol=1e-15, rtol=0)
    increment.to_csv(output / "metrics/incremental.csv", index=False)
    increment[["strategy", "scope", "control"] + [k for k in increment if "cost" in k or "turnover" in k or "short" in k or "long" in k]].to_csv(output / "metrics/side_cost_decomposition.csv", index=False)
    boot = {name: evaluation.bootstrap_delta(accounts["MOM60"].net, accounts[name].net,
            **{k: config["bootstrap"][k] for k in ["seed", "block", "reps"]}) for name in hm.CANDIDATES}
    dump(output / "metrics/bootstrap.json", boot)
    pd.DataFrame([{"strategy": k, "control": "MOM60", **v} for k, v in boot.items()]).to_csv(output / "metrics/bootstrap.csv", index=False)
    decision = decide(accounts, cover, boot)
    dump(output / "metrics/candidate_decision.json", decision)
    print("All3 trials complete; fixed diagnostics only", flush=True)
    he = {name: h.loc[fe.index] for name, h in holdings.items()}
    dump(output / "audit/tie_diagnostic.json", tie_diagnostic(signals, fe, output / "metrics"))
    persistence(signals, holdings, calendar, dates.rename("Date"), output / "metrics")
    rank_changes(signals, calendar, dates, output / "metrics")
    sector_concentration(fe, he, accounts, output / "metrics")
    common_alpha(fe, target.loc[fe.index], output / "metrics")
    within_alpha(fe, target.loc[fe.index], he, output / "metrics")
    agreement(fe, target.loc[fe.index], he, output / "metrics")
    for path, expected in prior_hashes.items():
        assert sha(ROOT / path) == expected, path
    dump(output / "audit/prior_evidence_unchanged.json", {"status": "PASS", "prior": config["prior_experiment"], "hashes": prior_hashes})
    firewall.save(output / "audit/firewall.json")
    resources = {"status": "PASS", "elapsed_seconds": time.monotonic()-started,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform == "darwin" else 1024), "actual_trials": 3, "valid_evaluation": False}
    dump(output / "audit/resources.json", resources)
    report_results(config, output, results, decision, boot)
    artifacts = {str(p.relative_to(output)): sha(p) for sub in ["audit", "metrics", "predictions", "code"] for p in (output / sub).rglob("*") if p.is_file()}
    run.update(resources)
    run.update(status="completed", exit_code=0, completed_at_utc=datetime.now(timezone.utc).isoformat(),
               artifact_sha256=artifacts, candidate_decisions=decision)
    dump(output / "run.json", run)
    print(json.dumps(safe({"decisions": decision, "resources": resources, "identity": identity}), indent=2), flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    output = Path(args.output).resolve()
    config = json.loads(Path(args.config).read_text())
    assert Path(args.config).resolve() == output / "config.json"
    assert config["data_split"] == "train" and config["valid_evaluation"] is False and config["max_trials"] == 3
    assert [x["trial_id"] for x in config["trials"]] == list(hm.CANDIDATES)
    assert config["parameters"] == {"horizon": 60, "skip": 1, "min_periods": 60,
        "sector33_min_finite_members": 5, "alpha": .25, "ewm_adjust": False, "relisting_gap": 20,
        "ddof": 1, "weights": [1, 1], "neutral_before_ewma": 0}
    run = json.loads((output / "run.json").read_text())
    assert run["status"] == "prepared"
    try:
        main_work(config, output, run)
    except BaseException as error:
        run.update(status="failed", exit_code=1, error=f"{type(error).__name__}: {error}", completed_at_utc=datetime.now(timezone.utc).isoformat())
        dump(output / "run.json", run)
        if firewall._PATCHED:
            firewall.save(output / "audit/firewall.json")
        raise


if __name__ == "__main__":
    main()
