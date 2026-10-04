"""One preregistered Train-only independent Size/Illiquidity/MOM60 experiment."""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import itertools
import json
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import pyarrow
import scipy

from research import evaluation, firewall
from research.experiments import slow_multifactor as shared
from stock_comp_2026 import evaluate_script as official
from stock_comp_2026.strategies.dm_slow_multifactor import features as original_slow
from stock_comp_2026.strategies.dm_trainonly import features as original_mom
from stock_comp_2026.strategies.dm_slow_mom60_equal import features as f, submission

ROOT = Path(__file__).resolve().parents[2]
SLOW, MOM, CAND = f.SLOW, "MOM60", f.CANDIDATE
sha, dump, exact, metrics, table = shared.sha, shared.dump, shared.exact, shared.metrics, shared.table
GROUPS = ["BOTH_HIGH", "SLOW_HIGH_MOM_LOW", "SLOW_LOW_MOM_HIGH", "BOTH_LOW", "OTHER"]


def now():
    return datetime.now(timezone.utc).isoformat()


def scopes(dates):
    return [("POOLED", dates), ("EX2016", dates[dates.year != 2016])] + [
        (str(y), dates[dates.year == y]) for y in range(2011, 2017)]


def source_dates(frame):
    dates = pd.DatetimeIndex(frame.index.get_level_values("Date"))
    return dates.tz_convert("Asia/Tokyo").tz_localize(None) if dates.tz is not None else dates


def function_sources(path):
    source = Path(path).read_text()
    return {n.name: ast.get_source_segment(source, n) for n in ast.parse(source).body
            if isinstance(n, ast.FunctionDef)}


def stored_raw_parity(computed, stored):
    """Parquet stores nulls, discarding the sign/payload of floating NaNs.

    Demand exact finite bits and exact missing positions, then compare the
    explicitly canonicalized null representation. Final signals remain subject
    to unmodified strict uint64 equality and never contain NaNs.
    """
    assert computed.index.equals(stored.index) and computed.columns.equals(stored.columns)
    assert computed.dtypes.equals(stored.dtypes)
    assert np.array_equal(computed.isna().to_numpy(), stored.isna().to_numpy())
    records = []
    for col in computed:
        a, b = computed[col].to_numpy(), stored[col].to_numpy()
        finite = ~np.isnan(a)
        assert np.array_equal(a[finite].view(np.uint64), b[finite].view(np.uint64)), col
        records.append({"column": col, "finite_bits_equal": True, "missing_positions_equal": True,
                        "nan_payload_bit_differences": int((a.view(np.uint64) != b.view(np.uint64)).sum())})
    exact(computed.mask(computed.isna(), np.nan), stored.mask(stored.isna(), np.nan))
    return {"status": "PASS", "columns": records, "canonical_null_storage_bits_equal": True,
            "note": "Parquet nulls do not preserve raw -log NaN sign/payload. No tolerance on any finite value; "
                    "final component/score bits are checked separately without canonicalization."}


def source_scan(paths):
    findings = []
    for path in paths:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if any(s in node.value for s in ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow",
                                                "AdjustmentClose", "AdjustmentVolume", "_valid.parquet",
                                                "raw_target", "target_1day"]):
                    findings.append({"source": str(path.relative_to(ROOT)), "line": node.lineno,
                                     "reason": "forbidden input"})
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                bad = node.func.attr in ["bfill", "backfill"]
                for kw in node.keywords:
                    bad |= kw.arg == "center" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                    bad |= kw.arg == "direction" and isinstance(kw.value, ast.Constant) and kw.value.value != "backward"
                if node.func.attr == "shift":
                    period = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == "periods"), None)
                    bad |= not isinstance(period, ast.Constant) or period.value < 0
                if bad:
                    findings.append({"source": str(path.relative_to(ROOT)), "line": node.lineno,
                                     "reason": "forbidden temporal operation"})
    assert not findings, findings
    return {"status": "PASS", "paths": [str(p.relative_to(ROOT)) for p in paths], "findings": findings,
            "manual_review": "Only fixed Train feature loaders. Backward disclosed-date EOD PIT shares; raw price/value. "
                             "Trailing Amihud; residual(raw_return-beta*same-date TOPIX) shifted1 before trailing60; "
                             "rank-before-EWMA .25; existing relisting reset; independent same-date final ranks. No labels or fit."}


def holdings(score, target):
    w, q = evaluation.weights(score)
    turn = w.groupby("Code").diff().abs().fillna(w.abs())
    gross = w * target
    cost = (.001 * turn).where(target.notna(), 0.)
    return pd.DataFrame({"w": w, "q": q, "gross": gross.fillna(0.), "net": gross.fillna(0.) - cost,
                         "turnover": turn, "cost": cost, "cost_all": .001 * turn}, index=w.index)


def account(score, target):
    d, receipt = shared.account(score, target)
    weight, _ = evaluation.weights(score)
    exact(weight.rename("Return"), official.compute_weight(score.rename("Return").to_frame()).Return)
    official_net = official.compute_pl(score.rename("Return").to_frame(), target.to_frame()).groupby("Date").sum()
    exact(d.net.rename("net"), official_net.rename("net"))
    receipt.update(weight_bitwise=True, net_bitwise=True, exact_uint64_checked=True)
    return d, receipt


def orthogonality(scores, accounts, h, dates, folder):
    names = ["Size", "Illiquidity", MOM, SLOW]
    daily = pd.DataFrame(index=dates)
    correlations = {}
    for a, b in itertools.combinations(names, 2):
        key = a + "__" + b
        daily[key] = evaluation.rankic(scores[a], scores[b]).reindex(dates)
        correlations[(a, b)] = daily[key]
    daily.to_csv(folder / "score_spearman_daily.csv", index_label="Date")
    rows, matrices, stacked = [], [], []
    for scope, ds in scopes(dates):
        matrix = pd.DataFrame(np.eye(len(names)), index=names, columns=names)
        for (a, b), series in correlations.items():
            x = series.loc[ds]
            value = x.mean()
            matrix.loc[a, b] = matrix.loc[b, a] = value
            rows.append({"scope": scope, "component_a": a, "component_b": b,
                         "days": len(ds), "finite_days": int(x.notna().sum()), "mean_daily_spearman": value})
        matrix.index.name = "component"
        matrix.to_csv(folder / f"score_mean_daily_spearman_matrix_{scope}.csv")
        matrices.append(matrix.reset_index().assign(scope=scope))
        sub = scores.loc[scores.index.get_level_values("Date").isin(ds), names]
        for method in ["spearman", "pearson"]:
            m = sub.corr(method=method)
            m.index.name = "component"
            m.to_csv(folder / f"score_stacked_{method}_matrix_{scope}.csv")
            stacked.append(m.reset_index().assign(scope=scope, method=method))
    pd.concat(matrices).to_csv(folder / "score_mean_daily_spearman_matrices.csv", index=False)
    pd.concat(stacked).to_csv(folder / "score_stacked_correlation_matrices.csv", index=False)
    result = pd.DataFrame(rows)
    result.to_csv(folder / "score_spearman_summary.csv", index=False)
    membership = pd.DataFrame(index=dates)
    for side, positive in [("long", True), ("short", False)]:
        a = h[SLOW].w.gt(0) if positive else h[SLOW].w.lt(0)
        b = h[MOM].w.gt(0) if positive else h[MOM].w.lt(0)
        inter = (a & b).groupby("Date").sum()
        union = (a | b).groupby("Date").sum()
        membership[side + "_intersection"] = inter
        membership[side + "_union"] = union
        membership[side + "_jaccard"] = inter / union.where(union > 0)
    for book in [SLOW, MOM]:
        for measure in ["gross", "net"]:
            membership[book + "_" + measure] = accounts[book].loc[dates, measure]
    membership.to_csv(folder / "component_pl_membership_daily.csv", index_label="Date")
    pl_rows, dd_rows = [], []
    for scope, ds in scopes(dates):
        draw = pd.DataFrame(index=ds)
        for book in [SLOW, MOM]:
            wealth = (1 + accounts[book].loc[ds, "net"]).cumprod()
            peaks = np.maximum.accumulate(np.r_[1., wealth.to_numpy()])[1:]
            draw[book + "_drawdown"] = wealth / peaks - 1
        draw.index.name = "Date"
        dd_rows.append(draw.reset_index().assign(scope=scope))
        pl_rows.append({"scope": scope, "days": len(ds),
                        "gross_pl_correlation": accounts[SLOW].loc[ds, "gross"].corr(accounts[MOM].loc[ds, "gross"]),
                        "net_pl_correlation": accounts[SLOW].loc[ds, "net"].corr(accounts[MOM].loc[ds, "net"]),
                        "long_jaccard": membership.loc[ds, "long_jaccard"].mean(),
                        "short_jaccard": membership.loc[ds, "short_jaccard"].mean(),
                        "drawdown_depth_correlation": draw.iloc[:, 0].corr(draw.iloc[:, 1])})
    pd.concat(dd_rows).to_csv(folder / "component_drawdown_depth_daily.csv", index=False)
    pl_result = pd.DataFrame(pl_rows)
    pl_result.to_csv(folder / "pl_orthogonality_summary.csv", index=False)
    return result, pl_result


def agreement_groups(slow_w, mom_w):
    if not slow_w.index.equals(mom_w.index):
        raise ValueError("Membership index mismatch")
    groups = pd.Series("OTHER", index=slow_w.index, name="group")
    for name, mask in [("BOTH_HIGH", slow_w.gt(0) & mom_w.gt(0)),
                       ("SLOW_HIGH_MOM_LOW", slow_w.gt(0) & mom_w.lt(0)),
                       ("SLOW_LOW_MOM_HIGH", slow_w.lt(0) & mom_w.gt(0)),
                       ("BOTH_LOW", slow_w.lt(0) & mom_w.lt(0))]:
        groups.loc[mask] = name
    return groups


def attribution(h, target, dates, folder):
    groups = agreement_groups(h[SLOW].w, h[MOM].w)
    panel = pd.DataFrame({"group": groups, "forward_target": target}, index=target.index)
    measures = []
    for book in [SLOW, CAND]:
        for measure in ["gross", "net", "turnover", "cost", "cost_all"]:
            col = book + "_" + measure
            panel[col] = h[book][measure]
            measures.append(col)
    for measure in ["gross", "net", "turnover", "cost", "cost_all"]:
        col = "delta_" + measure
        panel[col] = panel[CAND + "_" + measure] - panel[SLOW + "_" + measure]
        measures.append(col)
    panel = panel.loc[panel.index.get_level_values("Date").isin(dates)]
    panel.to_parquet(folder / "momentum_contribution_stock_days.parquet")
    rows, all_daily, parts = [], [], []
    for group in GROUPS:
        mask = panel.group.eq(group)
        d = panel[measures].where(mask, 0.).groupby("Date").sum().reindex(dates, fill_value=0.)
        parts.append(d.copy())
        d["stock_days"] = mask.groupby("Date").sum().reindex(dates, fill_value=0)
        d["finite_target_stock_days"] = (mask & panel.forward_target.notna()).groupby("Date").sum().reindex(dates, fill_value=0)
        d["forward_target_mean"] = panel.forward_target.where(mask).groupby("Date").mean().reindex(dates)
        all_daily.append(d.reset_index(names="Date").assign(group=group))
        for scope, ds in scopes(dates):
            m = mask & panel.index.get_level_values("Date").isin(ds)
            x = d.loc[ds]
            row = {"scope": scope, "group": group, "days": len(ds), "stock_days": int(m.sum()),
                   "finite_target_stock_days": int((m & panel.forward_target.notna()).sum()),
                   "forward_target_mean": panel.forward_target.loc[m].mean()}
            for col in measures:
                row["period_" + col] = x[col].sum()
                row["daily_mean_" + col] = x[col].mean()
                row["annual_" + col] = x[col].mean() * 252
            rows.append(row)
    total = sum(parts)
    wanted = panel[measures].groupby("Date").sum().reindex(dates)
    error = float(np.abs(total - wanted).to_numpy().max())
    assert error < 1e-14, error
    pd.concat(all_daily).to_csv(folder / "momentum_contribution_daily.csv", index=False)
    pd.DataFrame(rows).to_csv(folder / "momentum_contribution_summary.csv", index=False)
    assert sum(r["stock_days"] for r in rows if r["scope"] == "POOLED") == len(panel)
    return {"status": "PASS", "groups": GROUPS, "rows": len(panel), "stock_days_partition_exact": True,
            "daily_reconciliation_max_abs_error": error, "aggregation_atol": 1e-14,
            "neutral_exit_costs_retained_in_OTHER": True, "filter_or_veto_created": False}


def cost_analysis(result, folder):
    rows = []
    for scope in result.scope.unique():
        a = result.loc[result.scope == scope].set_index("strategy")
        slow, mom, cand = (a.loc[k] for k in [SLOW, MOM, CAND])
        gross = cand.annual_gross - slow.annual_gross
        cost = cand.annual_cost - slow.annual_cost
        net = cand.annual_net - slow.annual_net
        assert abs(net - (gross - cost)) < 1e-14
        rows.append({"scope": scope, "slow_turnover": slow.turnover, "mom60_turnover": mom.turnover,
                     "candidate_turnover": cand.turnover, "candidate_slow_turnover_ratio": cand.turnover / slow.turnover,
                     "incremental_annual_gross": gross, "incremental_annual_cost": cost,
                     "incremental_annual_net": net, "incremental_gross_cost_ratio": gross / cost if cost != 0 else np.nan,
                     "incremental_gross_gt_cost": gross > cost,
                     "cost_sign": "positive" if cost > 0 else "negative" if cost < 0 else "zero"})
    r = pd.DataFrame(rows)
    r.to_csv(folder / "turnover_cost_analysis.csv", index=False)
    return r


def mutate(frame, name, cutoff, seed):
    out = frame.copy()
    mask = source_dates(out) > cutoff
    rng = np.random.default_rng(seed)
    for col in out:
        if pd.api.types.is_numeric_dtype(out[col]):
            v = rng.normal(0, 1e6, int(mask.sum()))
            v[::7] = np.nan
            v[1::11] = 0.
            out.loc[mask, col] = v
        else:
            out.loc[mask, col] = "FUTURE_CHANGED"
    out = out.drop(out.index[mask][::13])
    if name == "fins_statements":
        arrays = out.index.to_frame(index=False)
        arrays.loc[source_dates(out) > cutoff, "Date"] += pd.Timedelta(days=1)
        out.index = pd.MultiIndex.from_frame(arrays)
        out = out.loc[~out.index.duplicated(keep="last")]
    if len(out):
        extra = out.iloc[-1:].copy()
        day = max(source_dates(out).max(), cutoff) + pd.Timedelta(days=3)
        original_dates = pd.DatetimeIndex(out.index.get_level_values("Date"))
        if original_dates.tz is not None:
            day = day.tz_localize(original_dates.tz)
        extra.index = (pd.MultiIndex.from_tuples([(day, "99999")], names=["Date", "Code"])
                       if isinstance(out.index, pd.MultiIndex) else pd.DatetimeIndex([day], name="Date"))
        out = pd.concat([out, extra])
    return out.sort_index()


def causality(inputs, scores, intermediate, config, folder):
    cases = []
    baseline = f.score(scores)
    ranks = f.factor_ranks(scores)
    for i, date in enumerate(config["prefix_cutoffs"]):
        cutoff = pd.Timestamp(date)
        prefix = scores.index[scores.index.get_level_values("Date") <= cutoff]
        for source in list(inputs) + ["ALL", "TRUNCATION"]:
            changed = dict(inputs)
            for j, (name, frame) in enumerate(inputs.items()):
                if source == "TRUNCATION":
                    changed[name] = frame.loc[source_dates(frame) <= cutoff]
                elif source in [name, "ALL"]:
                    changed[name] = mutate(frame, name, cutoff, config["random_seed"] + i * 100 + j)
            got, mid = f.components(changed)
            exact(scores.loc[prefix], got.loc[prefix])
            exact(intermediate.loc[prefix], mid.loc[prefix])
            exact(ranks.loc[prefix], f.factor_ranks(got).loc[prefix])
            exact(baseline.loc[prefix], f.score(got).loc[prefix])
            cases.append({"cutoff": date, "source": source, "rows": len(prefix), "status": "PASS", "bitwise": True})
        dump(folder / "prefix_progress.json", {"status": "running", "cases": cases})
        print("causality " + date + ": each source / ALL / truncation PASS", flush=True)
    for kind, changed in [("ROW_SHUFFLE", {k: v.sample(frac=1, random_state=config["random_seed"]) for k, v in inputs.items()}),
                          ("DETERMINISTIC_REBUILD", inputs)]:
        got, mid = f.components(changed)
        exact(scores, got)
        exact(intermediate, mid)
        exact(baseline, f.score(got))
        cases.append({"source": kind, "rows": len(scores), "status": "PASS", "bitwise": True})
    return {"status": "PASS", "cases": cases, "comparison": "exact index/columns/dtype/float64 uint64 incl NaN, zero tolerance",
            "all_input_sources": list(inputs), "no_learning_or_label_argument": True,
            "mutations": "Each and all future suffixes: extreme/NaN/zero, deletions, future new-code/date addition; "
                         "financial disclosure publication +1 day strictly after cutoff; separate truncation.",
            "scope": "Both raw and normalized SLOW factors, pre-EWMA and final MOM, final ranks and candidate score. "
                     "Tested inputs/cutoffs only, not a universal mathematical proof."}


def maturity(inputs, target, calendar, folder):
    raw = inputs["raw_return_1day"].Return.sort_index()
    beta = inputs["beta_1day"].Return.reindex(raw.index)
    market = pd.Series(inputs["topix_return_1day"].Return.reindex(raw.index.get_level_values("Date")).to_numpy(), index=raw.index)
    residual = raw - beta * market
    # Evaluation-only reconstruction of already supplied Train labels. Not a feature.
    future = residual.unstack("Code").reindex(calendar).shift(-2).stack(future_stack=True).reindex(target.index)
    valid = target.notna() & future.notna() & target.index.get_level_values("Date").isin(calendar[:-2])
    error = float((target.loc[valid] - future.loc[valid]).abs().max())
    assert error < 1e-12, error
    dates, purged = shared.fold_dates(calendar, range(2011, 2017))
    assert dates.is_unique and all(calendar[calendar.get_loc(d) + 2].year == d.year for d in dates)
    dump(folder / "maturity.json", {"status": "PASS", "target": "t+1 Open->t+2 Open, residual return at t+2",
                                    "reconstructable_rows": int(valid.sum()), "reconstruction_max_abs_error": error,
                                    "target_evaluation_only": True, "learning": False,
                                    "terminal_two_sessions_excluded": True})
    dump(folder / "purge.json", {"status": "PASS", "folds": purged, "continuous_accounting_before_date_selection": True})
    return dates


def decision(result, boot):
    def row(strategy, scope):
        return result.loc[(result.strategy == strategy) & (result.scope == scope)].iloc[0]
    checks, evidence = {}, {}
    improved = sum(row(CAND, str(y)).net_sharpe > row(SLOW, str(y)).net_sharpe for y in range(2011, 2016))
    checks["full_year_net_sharpe_improvements_ge4"] = improved >= 4
    evidence["full_year_net_sharpe_improvements"] = int(improved)
    for scope in ["POOLED", "EX2016"]:
        c, s = row(CAND, scope), row(SLOW, scope)
        measures = {"net_sharpe_gt_slow": (c.net_sharpe, s.net_sharpe, c.net_sharpe > s.net_sharpe),
                    "annual_net_ge_slow": (c.annual_net, s.annual_net, c.annual_net >= s.annual_net),
                    "long_net_gt0": (c.annual_long_net, 0., c.annual_long_net > 0),
                    "short_net_ge_slow": (c.annual_short_net, s.annual_short_net, c.annual_short_net >= s.annual_short_net),
                    "maxdd_magnitude_le_slow": (abs(c.max_drawdown), abs(s.max_drawdown), abs(c.max_drawdown) <= abs(s.max_drawdown)),
                    "turnover_le_1p50_slow": (c.turnover, 1.5 * s.turnover, c.turnover <= 1.5 * s.turnover),
                    "incremental_gross_gt_incremental_cost": (c.annual_gross - s.annual_gross, c.annual_cost - s.annual_cost,
                                                              c.annual_gross - s.annual_gross > c.annual_cost - s.annual_cost)}
        for name, (value, bound, passed) in measures.items():
            key = scope + "_" + name
            checks[key] = bool(passed)
            evidence[key] = {"candidate_value": value, "comparison_value": bound}
    primary = boot["POOLED:" + CAND + "-" + SLOW]
    checks["primary_bootstrap_lower_gt0"] = primary["low"] > 0
    evidence["primary_bootstrap_lower_gt0"] = {"candidate_value": primary["low"], "comparison_value": 0.}
    c, s = row(CAND, "POOLED"), row(SLOW, "POOLED")
    dg, dn = c.annual_gross - s.annual_gross, c.annual_net - s.annual_net
    passed = all(checks.values())
    category = "A" if passed else "B" if dg > 0 and dn <= 0 else "C" if dg <= 0 and dn <= 0 else "D"
    return {"decision": "NEXT_STAGE" if passed else "REJECT", "category": category,
            "interpretation": {"A": "Complementary Momentum", "B": "Gross-only improvement",
                               "C": "Dilution", "D": "Unstable complement"}[category],
            "all_passed": passed, "checks": checks, "evidence": evidence,
            "full_year_net_sharpe_improvements": int(improved), "actual_trials": 1, "rescue_trials": 0,
            "scope_rule": "Annual/side/DD/turnover/gross-cost gates fixed on POOLED and EX2016; year gate only2011-2015."}


def report(config, output, result, incremental, score_corr, pl_corr, cost, boot, verdict, resources):
    folder = ROOT / config["report_dir"]
    folder.mkdir()
    for sub in ["metrics", "audit"]:
        shutil.copytree(output / sub, folder / sub)
    pooled = result.loc[result.scope == "POOLED"]
    ex = result.loc[result.scope == "EX2016"]
    years = result.loc[result.scope.isin([str(y) for y in range(2011, 2017)])]
    primary = boot["POOLED:" + CAND + "-" + SLOW]
    secondary = boot["POOLED:" + CAND + "-" + MOM]
    p = pl_corr.loc[pl_corr.scope == "POOLED"].iloc[0]
    co = cost.loc[cost.scope == "POOLED"].iloc[0]
    checks = pd.DataFrame([{"gate": k, "passed": v} for k, v in verdict["checks"].items()])
    text = [f'# {config["experiment_id"]}: Size / Illiquidity / MOM60 fixed 1:1:1', "",
            f'**{verdict["decision"]}: {verdict["category"]}. {verdict["interpretation"]}**。固定候補1本、rescue0本。Historical Valid / Validは未読・未評価。', "",
            f'Completion run: `{output.relative_to(ROOT)}`。科学的performance source runはrun.jsonのscientific_source_runを参照。計画・設定・コードの事前hash、各段階のhash、入力・環境・成果物hashを保存。全Trainは既知研究データであり、未使用holdoutではない。', "",
            '目的は強い既存Size/Illiquidityへplain residual MOM60を独立factorとして追加するafter-cost増分。Size単独/Illiquidity単独のportfolioは作成していない。', "",
            'SLOW原仕様のnormalized SizeとIlliquidity、SLOW_CONTROL、保存済みMOM60およびDM-20260908-v1のTrain予測とstrict bitwise一致。SLOWはzscore(mean(z_size,z_amihud))として完全再構築。raw値も有限値bitsと欠損位置が完全一致。raw SizeのNaN符号はParquet null保存で失われるため、raw診断の保存表現だけ明示的にcanonical NaNへ統一し照合（signalを変更しない）。', "",
            '候補は各最終factorにsame-date average-tie percentile p→2*(p−mean(p))を適用し、3factorの算術平均。追加smoothingなし。これは0.5×SLOW_CONTROL+0.5×MOM60とも、portfolio weightsの混合とも異なる。', "",
            '## Primary evaluation: POOLED', "",
            table(pooled, ["strategy", "days", "rankic", "rankic_t_hac5", "rankic_hit", "gross_sharpe", "net_sharpe", "annual_gross", "annual_net", "turnover", "annual_cost", "max_drawdown", "annual_long_net", "annual_short_net"]), "",
            '## EX2016', "", table(ex, ["strategy", "net_sharpe", "annual_gross", "annual_net", "turnover", "annual_cost", "max_drawdown", "annual_long_net", "annual_short_net"]), "",
            '## Annual folds', "", table(years, ["strategy", "scope", "days", "net_sharpe", "annual_gross", "annual_net", "turnover", "annual_cost", "max_drawdown"]), "",
            f'2011–2015 Net Sharpe改善: **{verdict["full_year_net_sharpe_improvements"]}/5**。2016は部分年で安定性gateに含めない。全期間のIC/Q/Long/Short指標はmetrics/metrics.csv、候補−SLOWと候補−MOM60はmetrics/incremental.csv。', "",
            '## Orthogonality saved before candidate trial', "",
            table(score_corr.loc[score_corr.scope == "POOLED"], ["component_a", "component_b", "days", "mean_daily_spearman"]), "",
            f'SLOW/MOM pooled daily Gross P/L correlation={p.gross_pl_correlation:.6f}、Net={p.net_pl_correlation:.6f}。Long Jaccard={p.long_jaccard:.6f}、Short={p.short_jaccard:.6f}、drawdown depth correlation={p.drawdown_depth_correlation:.6f}。', "",
            'daily cross-sectional Spearman、pooled/年別平均、daily mean matrixとstacked stock-day Pearson/Spearman matrixを別ファイルで保存。年別P/L/Jaccard/DDはpl_orthogonality_summary.csv。低相関自体は採用根拠にしない。', "",
            '## Incremental gross / portfolio reshuffling / cost', "",
            table(incremental.loc[(incremental.comparison == CAND + "-" + SLOW) & incremental.scope.isin(["POOLED", "EX2016"])],
                  ["scope", "delta_rankic", "delta_gross_sharpe", "delta_net_sharpe", "delta_annual_gross", "delta_annual_cost", "delta_annual_net", "delta_turnover", "delta_annual_long_net", "delta_annual_short_net", "delta_max_drawdown"]), "",
            table(cost, ["scope", "slow_turnover", "mom60_turnover", "candidate_turnover", "candidate_slow_turnover_ratio", "incremental_annual_gross", "incremental_annual_cost", "incremental_annual_net", "incremental_gross_cost_ratio", "incremental_gross_gt_cost"]), "",
            f'POOLED Δannual gross={co.incremental_annual_gross:.6f}、Δannual cost={co.incremental_annual_cost:.6f}、Δannual net={co.incremental_annual_net:.6f}。Δgross>Δcost: **{bool(co.incremental_gross_gt_cost)}**。candidate/SLOW turnover={co.candidate_slow_turnover_ratio:.6f}。', "",
            'Δgrossは同じtargetに対するweight差の損益、Δcostはofficial weight変更によるcost差。Δnet=Δgross−Δcostを照合。Δgrossだけで情報alphaと因果的に断定せず、portfolio再配分も含む観測差とする。', "",
            '## Momentum contribution', "",
            '公式Long(Q4/Q5)/Short(Q1/Q2) membershipで5固定groupに分類。stock-days、forward target mean、candidate gross/net、Δgross/Δnet vs SLOW、turnover/costをmomentum_contribution_summary.csvに保存。日次表・stock-day parquetも保存。OTHERを含むpartitionが全公式帳簿に一致し、中立化時の退出costも残る。group結果からveto/filterは作成していない。', "",
            '## Bootstrap and adoption gates', "",
            f'paired circular moving-block20 sessions、2000 reps、seed20261003、95% percentile CI。Primary pooled ΔNet Sharpe vs SLOW={primary["observed_delta"]:.6f}、CI=[{primary["low"]:.6f}, {primary["high"]:.6f}]。Secondary vs MOM60={secondary["observed_delta"]:.6f}、CI=[{secondary["low"]:.6f}, {secondary["high"]:.6f}]。EX2016も保存。', "",
            table(checks, ["gate", "passed"]), "",
            f'解釈: **{verdict["category"]}. {verdict["interpretation"]}**。指定gateの全通過を要求し、低相関・IC・Grossの改善だけでは採用しない。SLOW単独を維持し、この固定候補の研究を終了する。' if not verdict["all_passed"] else 'すべてのgateを通過し次段階候補とする。Validは実行しない。', "",
            '## Accounting and causality', "",
            '日次公式global ranking: sorted Code first ties→five quintiles、weight=(Qindex−2)/N/1.2。Longは上位2分位、Shortは下位2分位。weightとdaily Netは公式compute_weight/compute_plとbitwise一致。欠測target行は公式式がcostも落とすため同じ処理を維持し、cost_all/net_all_costを別記。', "",
            '全連続入力panelでaccountingした後、各年最後2営業日をpurge。t+2 maturityをprovided raw_return−beta×TOPIXの評価専用再構築で確認。年間値は日次平均×252（2016も年率換算）；period_*は期間実額。Sharpeはddof1×sqrt252、RankICはdaily average-tie Spearman、tはHAC5 Bartlett、Q単調性はQ1–Q5平均returnと順序のSpearman。MaxDDは初期wealth1の複利net、additive DDも保存。', "",
            '全6入力源のfuture mutationを個別/同時で3cutoff、truncation、row shuffle、deterministic rebuild、raw/normalized/preEWMA/final component/rank/scoreのstrict bits検査。予測はtargetを受け取らず、targetがないTrain-only feature stageのadapter実行でも完全一致。source scan、Train-only firewallの拒否確認、coverage/index、関連回帰を保存。MOM4関数は凍結sourceと同じで、旧auditに加えて今回も動的検査した。', "",
            'make checkは既存DM-20261002-04の未対応experiment kindで失敗（今回変更以前にも再現）。その文書・設定・Valid結果は変更せず、今回のmetadataと全既存Freeze hashを別途検証。全workspace構成検査を合格と扱わない。audit/verification.jsonとlogs/make_check.logに制約を記録。', "",
            '動的監査は試した入力・境界に対する証拠であり普遍的証明ではない。学習・新パラメータ探索なし。公式集約とgroup/side和は明示toleranceで照合し、score bitwiseと区別する。', "",
            f'Completion/audit elapsed={resources["elapsed_seconds"]:.2f}s、peak RSS={resources["peak_rss_bytes"]/1024**2:.1f}MiB。実験期限1800秒。performance source runはbootstrap後に監査の未来行timezone不具合で停止；同一の保存済みmetrics/予測/bootstrapをhash一致で引き継いだ。追加performance trialは0、累積1本。失敗runは保持し、戦略source/config/gateは変更していない。source runの終了前peak RSSは未記録であり、ここでのRSSはcompletion/auditの実測値。提出zip/採点環境30分保証/Valid評価は依頼範囲外。']
    (folder / "REPORT.md").write_text("\n".join(text) + "\n")
    experiment = ROOT / "experiments" / config["experiment_id"]
    (experiment / "decision.md").write_text(f'# {config["experiment_id"]}: {verdict["decision"]}\n\n'
        f'**{verdict["category"]}. {verdict["interpretation"]}**. [Report](../../{config["report_dir"]}/REPORT.md).\n\n'
        + table(checks, ["gate", "passed"]) + '\n\nOne fixed trial; zero rescue; Historical Valid / Valid not read.\n')
    meta = json.loads((experiment / "experiment.json").read_text())
    meta.update(status="completed" if verdict["all_passed"] else "rejected", actual_trials=1,
                run_id=output.name, report=config["report_dir"] + "/REPORT.md", category=verdict["category"])
    dump(experiment / "experiment.json", meta)
    if not verdict["all_passed"]:
        with (ROOT / "experiments/GRAVEYARD.md").open("a") as stream:
            stream.write(f'\n## {config["experiment_id"]}: fixed Size / Illiquidity / MOM60\n\n'
                         f'{verdict["category"]}. {verdict["interpretation"]}; one trial, zero rescue. '
                         f'Net Sharpe full-year improvement {verdict["full_year_net_sharpe_improvements"]}/5; '
                         f'primary ΔNetSR CI [{primary["low"]:.6f}, {primary["high"]:.6f}]. '
                         f'[Decision]({config["experiment_id"]}/decision.md). Train-only; no Valid.\n')


def main_work(config, output, run):
    started = time.monotonic()
    stage = output / "stage"
    stage.mkdir()
    filenames = list(f.INPUT_COLUMNS) + ["target_1day"]
    for key in filenames:
        (stage / (key + "_train.parquet")).symlink_to(ROOT / config["input_dir"] / (key + "_train.parquet"))
    refs = {k: ROOT / v["path"] for k, v in config["saved_components"].items()}
    for k, path in refs.items():
        assert sha(path) == config["saved_components"][k]["sha256"]
    paths = sorted((ROOT / "stock_comp_2026/strategies" / config["strategy"]).rglob("*.py"))
    code = paths + [Path(__file__), ROOT / "research/experiments/slow_multifactor.py", ROOT / "research/evaluation.py",
                    ROOT / "research/firewall.py", ROOT / "stock_comp_2026/evaluate_script.py",
                    ROOT / "stock_comp_2026/strategies/dm_slow_multifactor/features.py",
                    ROOT / "stock_comp_2026/strategies/dm_trainonly/features.py"]
    code += sorted((ROOT / "tests/strategies" / config["strategy"]).rglob("*.py"))
    run.update(status="running", actual_trials=0, command=sys.argv,
               code_sha256={str(p.relative_to(ROOT)): sha(p) for p in code},
               train_data_sha256={key + "_train.parquet": sha(stage / (key + "_train.parquet")) for key in filenames},
               environment={"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
                            "pyarrow": pyarrow.__version__, "scipy": scipy.__version__, "platform": platform.platform()})
    dump(output / "run.json", run)
    for p in code:
        to = output / "code_snapshot" / p.relative_to(ROOT)
        to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, to)
    phases = []
    def checkpoint(phase, files=()):
        phases.append({"phase": phase, "at_utc": now(), "actual_trials": run["actual_trials"],
                       "sha256": {str(p.relative_to(output)): sha(p) for p in files}})
        dump(output / "audit/phase_gates.json", phases)
        dump(output / "run.json", run)
        print("phase " + phase, flush=True)
    for k, hsh in run["snapshot_sha256"].items():
        assert sha(output / k) == hsh
    dump(output / "audit/pre_result_lock.json", {"at_utc": now(), "plan_sha256": sha(output / "plan.md"),
                                               "config_sha256": sha(output / "config.json"), "code_sha256": run["code_sha256"],
                                               "max_trials": 1, "target_parsed": False})
    checkpoint("plan_config_code_freeze", [output / "plan.md", output / "config.json"])
    dump(output / "audit/source_scan.json", source_scan(paths))
    firewall.install(allowed_artifacts=list(refs.values()) + [output / "predictions/component_scores.parquet",
                       output / "predictions/strategy_scores.parquet", output / "predictions/intermediates.parquet",
                       output / "predictions/factor_ranks.parquet", output / "metrics/momentum_contribution_stock_days.parquet"])
    inputs = f.load_train(stage)
    inputs = {k: v.sort_index() for k, v in inputs.items()}
    scores, intermediate = f.components(inputs)
    feature_access = sorted(firewall.ACCESSES)
    assert not any("target_1day" in p for p in feature_access)
    # Parity compares score values only, never previous performance metrics.
    old = pd.read_parquet(refs["slow_features"], columns=config["saved_components"]["slow_features"]["columns"])
    raw_storage = stored_raw_parity(intermediate[["raw_size", "raw_amihud"]], old[["raw_size", "raw_amihud"]])
    exact(intermediate[["z_size", "z_amihud", "size_liquidity"]], old[["z_size", "z_amihud", "size_liquidity"]])
    old_score = pd.read_parquet(refs["slow_scores"], columns=[SLOW, MOM])
    exact(scores[[SLOW, MOM]], old_score)
    frozen = pd.read_parquet(refs["frozen_momentum"], columns=["Return"])
    exact(scores[MOM].rename("Return"), frozen.Return)
    rebuilt_slow = f.slow.zscore(scores[["Size", "Illiquidity"]].mean(axis=1)).rename(SLOW)
    exact(scores[SLOW], rebuilt_slow)
    exact(scores[MOM], original_mom.smooth(original_mom.build_momentum(inputs), .25).rename(MOM))
    slow_source = ROOT / "stock_comp_2026/strategies/dm_slow_multifactor/features.py"
    copied_slow = ROOT / "stock_comp_2026/strategies/dm_slow_mom60_equal/component_slow/features.py"
    assert slow_source.read_bytes() == copied_slow.read_bytes()
    functions = ["build_momentum", "centered_rank", "segment_keys", "smooth"]
    copies = function_sources(ROOT / "stock_comp_2026/strategies/dm_slow_mom60_equal/component_momentum.py")
    current = function_sources(ROOT / "stock_comp_2026/strategies/dm_trainonly/features.py")
    frozen_source = ROOT / "releases/DM-20260908-v1/snapshot/stock_comp_2026/strategies/dm_trainonly/features.py"
    release = function_sources(frozen_source)
    for name in functions:
        assert copies[name] == current[name] == release[name], name
    old_audit = ROOT / "releases/DM-20260908-v1/snapshot/reports/DM-20260908/verification.json"
    audit = json.loads(old_audit.read_text())
    assert audit["status"] == "PASS" and all(r["selected_predictions_bitwise_equal"] for r in audit["future_mutation"])
    scores.to_parquet(output / "predictions/component_scores.parquet")
    intermediate.to_parquet(output / "predictions/intermediates.parquet")
    dump(output / "audit/component_parity.json", {"status": "PASS", "rows": len(scores), "saved_refs": config["saved_components"],
        "raw_parquet_storage_parity": raw_storage, "normalized_Size_Illiquidity_bitwise": True,
        "SLOW_saved_and_reconstructed_bitwise": True, "MOM60_saved_and_frozen_bitwise": True,
        "SLOW_module_byte_identical": True, "MOM_functions_current_frozen_source_identical": functions,
        "frozen_momentum_source_sha256": sha(frozen_source), "old_MOM_audit_path": str(old_audit.relative_to(ROOT)),
        "old_MOM_audit_sha256": sha(old_audit), "old_MOM_audit_status": "PASS",
        "comparison": "index/columns/dtype and exact uint64 float64 bits including NaN; zero tolerance"})
    raw_index = inputs["raw_return_1day"].index
    assert scores.index.equals(raw_index) and scores.index.is_unique and np.isfinite(scores.to_numpy()).all()
    dump(output / "audit/contract.json", {"status": "PASS", "rows": len(scores), "dates": scores.index.get_level_values("Date").nunique(),
        "codes": scores.index.get_level_values("Code").nunique(), "exact_raw_input_index": True, "finite_components": True,
        "score_coverage": 1., "label_free_component_build": True, "feature_only_reads_before_target": feature_access})
    checkpoint("component_parity", [output / "audit/component_parity.json", output / "predictions/component_scores.parquet"])
    target = pd.read_parquet(stage / "target_1day_train.parquet")["Return"].sort_index()
    assert target.index.equals(scores.index)
    calendar = scores.index.get_level_values("Date").unique().sort_values()
    dates = maturity(inputs, target, calendar, output / "audit")
    accounts, h, receipts = {}, {}, {}
    for book in [SLOW, MOM]:
        accounts[book], receipts[book] = account(scores[book].rename("Return"), target)
        h[book] = holdings(scores[book], target)
    score_corr, pl_corr = orthogonality(scores, accounts, h, dates, output / "metrics")
    checkpoint("orthogonality_diagnostics", [output / "metrics/score_spearman_summary.csv", output / "metrics/pl_orthogonality_summary.csv"])
    # First creation and evaluation of the sole authorized performance candidate.
    candidate = f.score(scores)
    ranks = f.factor_ranks(scores)
    scores[CAND] = candidate
    run["actual_trials"] = 1
    scores.to_parquet(output / "predictions/strategy_scores.parquet")
    ranks.to_parquet(output / "predictions/factor_ranks.parquet")
    accounts[CAND], receipts[CAND] = account(candidate, target)
    h[CAND] = holdings(candidate, target)
    for book, d in accounts.items():
        d.to_csv(output / f"metrics/daily_{book}.csv", index_label="Date")
        for col in ["gross", "net", "cost", "turnover"]:
            assert np.allclose(h[book][col].groupby("Date").sum(), d[col], atol=1e-15, rtol=0), (book, col)
    result = pd.DataFrame([{"strategy": book, "scope": scope, **metrics(d.loc[ds])}
                           for book, d in accounts.items() for scope, ds in scopes(dates)])
    result.to_csv(output / "metrics/metrics.csv", index=False)
    increments = []
    for scope, _ in scopes(dates):
        c = result.loc[(result.strategy == CAND) & (result.scope == scope)].iloc[0]
        for base in [SLOW, MOM]:
            b = result.loc[(result.strategy == base) & (result.scope == scope)].iloc[0]
            increments.append({"comparison": CAND + "-" + base, "scope": scope,
                               **{"delta_" + col: c[col] - b[col] for col in result if col not in ["strategy", "scope"]}})
    incremental = pd.DataFrame(increments)
    incremental.to_csv(output / "metrics/incremental.csv", index=False)
    dump(output / "audit/official_accounting.json", {"status": "PASS", "books": receipts,
        "stock_contributions_reconciliation_atol": 1e-15, "global_five_quintiles": True})
    checkpoint("fixed_1_1_1_trial", [output / "predictions/strategy_scores.parquet", output / "metrics/metrics.csv"])
    dump(output / "audit/attribution.json", attribution(h, target, dates, output / "metrics"))
    checkpoint("incremental_attribution", [output / "metrics/incremental.csv", output / "metrics/momentum_contribution_summary.csv"])
    cost = cost_analysis(result, output / "metrics")
    checkpoint("turnover_cost_analysis", [output / "metrics/turnover_cost_analysis.csv"])
    boot = {}
    for scope, ds in scopes(dates)[:2]:
        for base in [SLOW, MOM]:
            boot[scope + ":" + CAND + "-" + base] = {
                **evaluation.bootstrap_delta(accounts[base].loc[ds].net, accounts[CAND].loc[ds].net,
                                              **{k: config["bootstrap"][k] for k in ["block", "reps", "seed"]}),
                "observed_delta": evaluation.sharpe(accounts[CAND].loc[ds].net) - evaluation.sharpe(accounts[base].loc[ds].net),
                "days": len(ds), "ci": .95, "primary": scope == "POOLED" and base == SLOW}
    dump(output / "metrics/bootstrap.json", boot)
    pd.DataFrame([{"comparison": k, **v} for k, v in boot.items()]).to_csv(output / "metrics/bootstrap.csv", index=False)
    checkpoint("bootstrap", [output / "metrics/bootstrap.json"])
    dump(output / "audit/prefix_invariance.json", causality(inputs, scores.drop(columns=[CAND]), intermediate, config, output / "audit"))
    feature_stage = output / "feature_stage"
    feature_stage.mkdir()
    for name in f.INPUT_COLUMNS:
        (feature_stage / (name + "_train.parquet")).symlink_to(stage / (name + "_train.parquet"))
    assert len(list(feature_stage.iterdir())) == 6
    adapted = submission.predict(feature_stage).Return
    exact(candidate, adapted)
    dump(output / "audit/adapter_parity.json", {"status": "PASS", "bitwise": True, "rows": len(candidate),
        "exact_input_output_index": candidate.index.equals(raw_index), "finite_score": bool(np.isfinite(candidate).all()),
        "self_contained_label_free": True, "deterministic": True})
    denied = []
    for forbidden in [stage / "target_1day_valid.parquet", stage / "raw_target_1day_train.parquet"]:
        try:
            pd.read_parquet(forbidden)
        except PermissionError as error:
            denied.append({"requested": forbidden.name, "result": "DENIED", "reason": str(error)})
        else:
            raise AssertionError("Firewall did not deny " + str(forbidden))
    dump(output / "audit/firewall_denials.json", {"status": "PASS", "cases": denied, "values_parsed": False})
    firewall.save(output / "audit/firewall.json")
    assert not any("_valid" in p.lower() or "raw_target" in p.lower() for p in firewall.ACCESSES)
    checkpoint("causality_audit", [output / "audit/prefix_invariance.json", output / "audit/adapter_parity.json"])
    tests = subprocess.run([sys.executable, str(ROOT / "tools/run_bounded.py"), "--seconds", "180", sys.executable,
                            "-m", "pytest", "-q", "tests/strategies/dm_slow_mom60_equal", "tests/strategies/dm_slow_multifactor"],
                           cwd=ROOT, capture_output=True, text=True)
    (output / "logs/tests.log").write_text(tests.stdout + tests.stderr)
    assert tests.returncode == 0, tests.stdout + tests.stderr
    check = subprocess.run(["make", "check"], cwd=ROOT, capture_output=True, text=True)
    (output / "logs/make_check.log").write_text(check.stdout + check.stderr)
    from tools import workspace
    workspace.validate_experiment(ROOT, ROOT / "experiments" / config["experiment_id"])
    frozen_count = 0
    for path in sorted((ROOT / "reports").glob("*/freeze_manifest.json")):
        manifest = json.loads(path.read_text())
        freeze_root = ROOT
        for meta_path in (ROOT / "experiments").glob("*/experiment.json"):
            meta = json.loads(meta_path.read_text())
            if meta.get("freeze_manifest") == str(path.relative_to(ROOT)):
                freeze_root = ROOT / meta["freeze_root"]
                assert sha(path) == meta["freeze_manifest_sha256"]
                assert sha(freeze_root / meta["freeze_manifest"]) == meta["freeze_manifest_sha256"]
        for section in ["code_sha256", "artifact_sha256"]:
            for relative, expected in manifest[section].items():
                assert sha(freeze_root / relative) == expected, relative
                frozen_count += 1
    if check.returncode:
        assert "DM-20261002-04: unknown experiment kind" in check.stdout + check.stderr, check.stdout + check.stderr
    dump(output / "audit/verification.json", {"status": "PASS_WITH_EXISTING_WORKSPACE_METADATA_FAILURE" if check.returncode else "PASS",
        "tests_returncode": tests.returncode, "tests_output": tests.stdout, "own_metadata": "PASS",
        "existing_freeze_hashes": frozen_count, "existing_freeze_hashes_status": "PASS",
        "make_check_returncode": check.returncode, "make_check_output": check.stdout + check.stderr,
        "make_check_limitation": "Preexisting unsupported experiment kind in DM-20261002-04; no edits to its files. "
                                 "Full workspace metadata validation not passed. New experiment and all Freeze hashes checked separately."})
    verdict = decision(result, boot)
    dump(output / "metrics/decision.json", verdict)
    checkpoint("decision", [output / "metrics/decision.json"])
    resources = {"elapsed_seconds": time.monotonic() - started,
                 "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
                 "actual_trials": 1, "valid_evaluation": False, "execution_timeout_seconds": config["execution_timeout_seconds"]}
    dump(output / "audit/resources.json", resources)
    report(config, output, result, incremental, score_corr, pl_corr, cost, boot, verdict, resources)
    run.update(status="completed", exit_code=0, completed_at_utc=now(), decision=verdict, resources=resources,
               artifact_sha256={str(p.relative_to(output)): sha(p) for sub in ["predictions", "metrics", "audit"]
                                for p in (output / sub).rglob("*") if p.is_file()})
    dump(output / "run.json", run)
    print(json.dumps(shared.safe({"decision": verdict, "resources": resources}), indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    output = Path(args.output).resolve()
    run = json.loads((output / "run.json").read_text())
    assert run["status"] == "prepared"
    assert config["data_split"] == "train" and config["valid_evaluation"] is False
    assert config["max_trials"] == 1 and config["trials"] == [{"trial_id": CAND}]
    assert config["parameters"]["factor_weights"] == [1, 1, 1]
    assert config["bootstrap"]["seed"] == 20261003 and config["bootstrap"]["block"] == 20 and config["bootstrap"]["reps"] == 2000
    try:
        main_work(config, output, run)
    except BaseException as error:
        run.update(status="failed", exit_code=1, completed_at_utc=now(), failure=repr(error))
        dump(output / "run.json", run)
        if firewall._PATCHED:
            firewall.save(output / "audit/firewall.json")
        raise


if __name__ == "__main__":
    main()
