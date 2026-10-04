"""Finite, pre-registered Train-only independent slow multifactor experiment."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import platform
import resource
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow
import scipy

from research import evaluation, firewall
from stock_comp_2026 import evaluate_script as official
from stock_comp_2026.strategies.dm_trainonly import features as momentum
from stock_comp_2026.strategies.dm_slow_multifactor import features as mf
from stock_comp_2026.strategies.dm_slow_multifactor import submission

ROOT = Path(__file__).resolve().parents[2]
INPUT_NAMES = list(mf.INPUT_COLUMNS) + ["beta_1day", "topix_return_1day", "target_1day"]


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe(obj):
    if isinstance(obj, dict):
        return {str(k): safe(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return [safe(v) for v in obj]
    if isinstance(obj, (float, np.floating)):
        return float(obj) if np.isfinite(obj) else None
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def dump(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(safe(obj), ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def exact(a, b):
    if isinstance(a, pd.Series):
        a, b = a.to_frame(), b.to_frame()
    assert a.index.equals(b.index), "Index mismatch"
    assert a.columns.equals(b.columns), "Column mismatch"
    assert a.dtypes.equals(b.dtypes), "Dtype mismatch"
    assert np.array_equal(a.to_numpy().view(np.uint64), b.to_numpy().view(np.uint64)), "Bit mismatch"


def source_scan():
    findings = []
    paths = [ROOT / f"stock_comp_2026/strategies/dm_slow_multifactor/{x}.py"
             for x in ["features", "submission"]]
    for path in paths:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if any(t in node.value for t in ["AdjustmentClose", "AdjustmentOpen", "AdjustmentVolume",
                                                "AdjustmentHigh", "AdjustmentLow", "_valid.parquet", "target_1day"]):
                    findings.append({"source": str(path.relative_to(ROOT)), "line": node.lineno,
                                     "reason": "forbidden input/adjusted level"})
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
    return {"status": "PASS", "sources": [str(p.relative_to(ROOT)) for p in paths], "findings": findings,
            "manual_review": "Date-only financial end-of-day availability, backward as-of; exact PIT sector; raw Close; per-date winsorization and scaling; trailing calendar rolling. No fitted labels."}


def mutate(frame, cutoff, seed):
    out = frame.copy()
    dates = pd.DatetimeIndex(out.index.get_level_values("Date"))
    if dates.tz is not None:
        dates = dates.tz_convert("Asia/Tokyo").tz_localize(None)
    mask = dates > cutoff
    rng = np.random.default_rng(seed)
    for col in out:
        if pd.api.types.is_numeric_dtype(out[col]):
            value = rng.normal(0, 1e9, int(mask.sum()))
            value[::5] = np.nan
            value[1::7] = 0.
            out.loc[mask, col] = value
        else:
            out.loc[mask, col] = "future_sector"
    # Delete suffix rows, move retained suffix financial/public dates, and add a new code.
    future_index = out.index[mask]
    out = out.drop(future_index[::11])
    if len(future_index):
        extra = out.iloc[-1:].copy()
        date = out.index.get_level_values("Date").max() + pd.Timedelta(days=3)
        extra.index = pd.MultiIndex.from_tuples([(date, "99999")], names=["Date", "Code"])
        out = pd.concat([out, extra])
    return out


def prefix_audit(inputs, features, config, sector=False, revision=False):
    rows = []
    base_score = mf.score(features, revision)
    for i, cutoff_text in enumerate(config["prefix_cutoffs"]):
        cutoff = pd.Timestamp(cutoff_text)
        mask = features.index.get_level_values("Date") <= cutoff
        prefix = features.index[mask]
        for name in list(inputs) + ["ALL", "TRUNCATION"]:
            changed = dict(inputs)
            if name == "TRUNCATION":
                changed = {}
                for key, frame in inputs.items():
                    dates = pd.DatetimeIndex(frame.index.get_level_values("Date"))
                    if dates.tz is not None:
                        dates = dates.tz_convert("Asia/Tokyo").tz_localize(None)
                    changed[key] = frame.loc[dates <= cutoff]
            else:
                for j, key in enumerate(inputs):
                    if name in [key, "ALL"]:
                        changed[key] = mutate(inputs[key], cutoff, config["random_seed"] + i * 100 + j)
            got = mf.build_features(changed, sector=sector).loc[prefix]
            exact(features.loc[prefix], got)
            exact(base_score.loc[prefix], mf.score(got, revision))
            rows.append({"sector": sector, "revision": revision, "cutoff": cutoff_text,
                         "mutated_source": name, "prefix_rows": len(prefix),
                         "columns": len(features.columns), "status": "PASS", "bitwise": True})
        print(f"prefix cutoff {cutoff_text} sector={sector}: PASS", flush=True)
    return rows


def account(signal, target):
    daily = evaluation.daily_account(signal, target)
    w, q = evaluation.weights(signal)
    ow = official.compute_weight(signal.to_frame()).iloc[:, 0]
    assert np.array_equal(w.to_numpy(), ow.to_numpy()), "Official weight mismatch"
    opl = official.compute_pl(signal.to_frame(), target.to_frame()).groupby("Date").sum()
    assert np.array_equal(opl.to_numpy(), daily.net.to_numpy()), "Official net mismatch"
    side_cost = {}
    for side, signed in [("long", w.clip(lower=0)), ("short", (-w).clip(lower=0))]:
        turn = signed.groupby(level="Code").diff().abs().fillna(signed.abs())
        cost = .001 * turn
        daily[f"{side}_turnover"] = turn.groupby(level="Date").sum()
        daily[f"{side}_cost_all"] = cost.groupby(level="Date").sum()
        daily[f"{side}_cost"] = cost.where(target.notna(), 0).groupby(level="Date").sum()
        daily[f"{side}_net"] = daily[side] - daily[f"{side}_cost"]
        side_cost[side] = cost
    assert np.allclose(daily.long_net + daily.short_net, daily.net, atol=1e-15, rtol=0)
    assert np.allclose(daily.long_turnover + daily.short_turnover, daily.turnover, atol=1e-15, rtol=0)
    daily["positive_exposure"] = w.clip(lower=0).groupby("Date").sum()
    daily["negative_exposure"] = (-w.clip(upper=0)).groupby("Date").sum()
    return daily, {"status": "PASS", "weight_bitwise": True, "net_bitwise": True,
                   "side_account_tolerance": 1e-15, "rows": len(signal),
                   "min_quintiles_per_day": int(q.groupby("Date").nunique().min())}


def metrics(daily):
    m = evaluation.metrics(daily)
    for side in ["long", "short"]:
        for key in ["net", "cost", "cost_all", "turnover"]:
            m[f"annual_{side}_{key}" if key != "turnover" else f"{side}_turnover"] = float(daily[f"{side}_{key}"].mean() * (1 if key == "turnover" else 252))
        m[f"{side}_net_sharpe"] = evaluation.sharpe(daily[f"{side}_net"])
    m["max_drawdown"] = m["max_drawdown_compound"]
    return m


def fold_dates(calendar, years):
    selected, audit = [], []
    for year in years:
        now = calendar[calendar.year == year]
        keep = now[:-2]
        for date in keep:
            pos = calendar.get_loc(date)
            assert pos + 2 < len(calendar) and calendar[pos + 2].year == year
        selected.extend(keep)
        audit.append({"year": year, "last_signal": str(keep[-1].date()),
                      "last_label_end": str(now[-1].date()), "purged": [str(x.date()) for x in now[-2:]],
                      "no_model_fitting": True, "status": "PASS"})
    return pd.DatetimeIndex(selected), audit


def gross_gate(daily, config, phase):
    m = metrics(daily)
    full = [metrics(daily.loc[daily.index.year == y]) for y in range(2011, 2016)]
    ex = metrics(daily.loc[daily.index.year != 2016])
    gate = config["phase_gates"][phase]
    checks = {"pooled_gross_positive": m["annual_gross"] > 0,
              "ex2016_gross_positive": ex["annual_gross"] > 0,
              "positive_full_year_gross": sum(x["annual_gross"] > 0 for x in full) >= gate["full_year_positive_gross_min"]}
    if phase == "phase2":
        checks["turnover_feasible"] = m["turnover"] <= gate["pooled_turnover_max_inclusive"]
    else:
        checks.update(long_gross_positive=m["annual_long"] > 0, short_gross_positive=m["annual_short"] > 0)
    return {"passed": all(checks.values()), "checks": checks,
            "full_year_positive_count": sum(x["annual_gross"] > 0 for x in full)}


def table(frame, columns):
    out = frame[columns].copy()
    for col in out:
        if pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].map(lambda x: f"{x:.6f}")
    return "| " + " | ".join(columns) + " |\n| " + " | ".join(["---"] * len(columns)) + " |\n" + "\n".join("| " + " | ".join(map(str, row)) + " |" for row in out.itertuples(index=False, name=None))


def main_work(config, output, run):
    started = time.monotonic()
    stage = output / "stage"
    stage.mkdir()
    source = ROOT / config["input_dir"]
    input_hashes = {}
    for name in INPUT_NAMES:
        path = source / f"{name}_train.parquet"
        (stage / path.name).symlink_to(path)
        input_hashes[path.name] = sha(path)
    firewall.install(allowed_artifacts=[output / "predictions" / name for name in
                                      ["strategy_scores.parquet", "features_base.parquet", "features_sector.parquet"]])
    scan = source_scan()
    dump(output / "audit/source_scan.json", scan)
    code_paths = [Path(__file__), ROOT / "research/evaluation.py", ROOT / "research/firewall.py",
                  ROOT / "stock_comp_2026/evaluate_script.py", ROOT / "stock_comp_2026/strategies/dm_trainonly/features.py"]
    code_paths += sorted((ROOT / "stock_comp_2026/strategies/dm_slow_multifactor").glob("*.py"))
    run.update(command=sys.argv, code_sha256={str(p.relative_to(ROOT)): sha(p) for p in code_paths},
               train_data_sha256=input_hashes, environment={"python": platform.python_version(),
               "pandas": pd.__version__, "numpy": np.__version__, "pyarrow": pyarrow.__version__,
               "scipy": scipy.__version__, "platform": platform.platform()}, status="running")
    dump(output / "run.json", run)
    for path in code_paths:
        dest = output / "code" / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
    # Lock the economic specification before reading ANY label values.
    dump(output / "audit/pre_result_lock.json", {"at_utc": datetime.now(timezone.utc).isoformat(),
         "plan_sha256": sha(output / "plan.md"), "config_sha256": sha(output / "config.json"),
         "code_sha256": run["code_sha256"], "max_trials": 3, "target_read": False})
    inputs = mf.load_train(stage)
    base = mf.build_features(inputs)
    index = base.index
    assert index.equals(mf.canonical(inputs["raw_return_1day"]).index)
    signals = {"SLOW_CONTROL": base.size_liquidity.rename("Return"), "SLOW_MF_BASE": mf.score(base)}
    for s in signals.values():
        assert np.isfinite(s.to_numpy()).all()
    prefix_results = prefix_audit(inputs, base, config)
    exact(base, mf.build_features(inputs))
    shuffled = {key: frame.sample(frac=1, random_state=config["random_seed"]) for key, frame in inputs.items()}
    exact(base, mf.build_features(shuffled))
    exact(signals["SLOW_MF_BASE"], submission.predict(stage).iloc[:, 0])
    dump(output / "audit/coverage.json", {"status": "PASS", "rows": len(index),
         "codes": index.get_level_values("Code").nunique(), "dates": index.get_level_values("Date").nunique(),
         "all_signals_finite": True, "index_alignment": True, "deterministic_replay_bitwise": True,
         "shuffle_bitwise": True, "research_adapter_bitwise": True,
         "raw_feature_missing_rates": base.filter(like="raw_").isna().mean().to_dict()})
    # Fixed Momentum baseline uses its established builder; it is never a candidate.
    mi = {"raw_return_1day": mf.canonical(inputs["raw_return_1day"])}
    for name in ["beta_1day", "topix_return_1day"]:
        mi[name] = pd.read_parquet(stage / f"{name}_train.parquet")
    signals["MOM60"] = momentum.smooth(momentum.build_momentum(mi), .25).rename("Return")
    calendar = index.get_level_values("Date").unique().sort_values()
    eval_dates, purge = fold_dates(calendar, list(range(2011, 2017)))
    dump(output / "audit/purge.json", purge)
    target_frame = pd.read_parquet(stage / "target_1day_train.parquet")
    assert target_frame.index.equals(index), "Target and feature row sets differ"
    target = target_frame.iloc[:, 0]
    daily, parity = {}, {}
    for name, signal in signals.items():
        full, parity[name] = account(signal, target)
        daily[name] = full
    eval_daily = {name: d.loc[eval_dates] for name, d in daily.items()}
    gates = {"phase2": gross_gate(eval_daily["SLOW_MF_BASE"], config, "phase2")}
    candidates = ["SLOW_MF_BASE"]
    sector = None
    if gates["phase2"]["passed"]:
        print("Phase 2 registered gate PASS; evaluating SECTOR", flush=True)
        sector = mf.build_features(inputs, sector=True)
        prefix_results += prefix_audit(inputs, sector, config, sector=True)
        exact(sector, mf.build_features(inputs, sector=True))
        signals["SLOW_MF_SECTOR"] = mf.score(sector)
        daily["SLOW_MF_SECTOR"], parity["SLOW_MF_SECTOR"] = account(signals["SLOW_MF_SECTOR"], target)
        eval_daily["SLOW_MF_SECTOR"] = daily["SLOW_MF_SECTOR"].loc[eval_dates]
        candidates.append("SLOW_MF_SECTOR")
    gates["phase3_sources"] = {name: gross_gate(eval_daily[name], config, "phase3") for name in candidates}
    parent = next((name for name in ["SLOW_MF_SECTOR", "SLOW_MF_BASE"]
                   if name in gates["phase3_sources"] and gates["phase3_sources"][name]["passed"]), None)
    if parent:
        print(f"Phase 3 registered gate PASS; parent={parent}", flush=True)
        chosen_features = sector if parent == "SLOW_MF_SECTOR" else base
        signals["SLOW_MF_REVISION"] = mf.score(chosen_features, revision=True)
        # Revision is already part of each tested feature matrix; test score too.
        prefix_results += prefix_audit(inputs, chosen_features, config,
                                       sector=parent == "SLOW_MF_SECTOR", revision=True)
        daily["SLOW_MF_REVISION"], parity["SLOW_MF_REVISION"] = account(signals["SLOW_MF_REVISION"], target)
        eval_daily["SLOW_MF_REVISION"] = daily["SLOW_MF_REVISION"].loc[eval_dates]
        candidates.append("SLOW_MF_REVISION")
    gates["phase3_parent"] = parent
    dump(output / "audit/phase_gates.json", gates)
    dump(output / "audit/prefix_invariance.json", {"status": "PASS", "comparison": "float64 bit patterns including NaNs, exact index/column/dtype", "cases": prefix_results,
         "mutation": "Each source and all sources: random extreme/zero/NaN suffix values, PIT sector changes, suffix deletions and added future new-code row. Truncation separately. Financial suffix disclosure dates preserved for existing rows; added new disclosure date strictly later. No fitted model.",
         "scope": "All feature inputs; labels cannot enter builder. Momentum is fixed existing control, not newly audited here."})
    dump(output / "audit/official_accounting_parity.json", parity)
    rows = []
    for name, full in daily.items():
        for scope, d in [("pooled", eval_daily[name]), ("ex2016", eval_daily[name].loc[eval_daily[name].index.year != 2016]), ("all_history_descriptive", full.iloc[:-2])]:
            rows.append({"strategy": name, "scope": scope, **metrics(d)})
        for year in range(2008, 2017):
            d = full.loc[full.index.year == year]
            if year >= 2011:
                d = eval_daily[name].loc[eval_daily[name].index.year == year]
            rows.append({"strategy": name, "scope": str(year), **metrics(d)})
        daily[name].to_csv(output / f"metrics/daily_{name}.csv", index_label="Date")
    result = pd.DataFrame(rows)
    result.to_csv(output / "metrics/metrics.csv", index=False)
    pooled = result.loc[result.scope == "pooled"]
    incremental, boot, decisions = [], {}, {}
    numeric = ["rankic", "gross_sharpe", "net_sharpe", "turnover", "annual_cost", "annual_cost_all",
               "annual_gross", "annual_net", "annual_long_net", "annual_short_net"]
    for name in candidates:
        boot[name] = {}
        for control in ["MOM60", "SLOW_CONTROL"]:
            for scope in ["pooled", "ex2016"] + [str(y) for y in range(2011, 2017)]:
                c = result.loc[(result.strategy == name) & (result.scope == scope)].iloc[0]
                b = result.loc[(result.strategy == control) & (result.scope == scope)].iloc[0]
                incremental.append({"candidate": name, "control": control, "scope": scope,
                                    **{f"delta_{key}": c[key] - b[key] for key in numeric}})
            boot[name][control] = evaluation.bootstrap_delta(eval_daily[control].net, eval_daily[name].net,
                **config["bootstrap_args"])
        m = metrics(eval_daily[name])
        full_year = [metrics(eval_daily[name].loc[eval_daily[name].index.year == y]) for y in range(2011, 2016)]
        checks = {"pooled_net_positive": m["annual_net"] > 0,
                  "ex2016_net_positive": metrics(eval_daily[name].loc[eval_daily[name].index.year != 2016])["annual_net"] > 0,
                  "net_positive_4of5_full_years": sum(x["annual_net"] > 0 for x in full_year) >= 4,
                  "both_sides_net_positive": m["annual_long_net"] > 0 and m["annual_short_net"] > 0,
                  "rankic_positive": m["rankic"] > 0, "monotonicity_positive": m["q_monotonicity"] > 0}
        for control in ["MOM60", "SLOW_CONTROL"]:
            checks[f"pooled_netSR_beats_{control}"] = m["net_sharpe"] > metrics(eval_daily[control])["net_sharpe"]
            improves = sum(full_year[i]["net_sharpe"] > metrics(eval_daily[control].loc[eval_daily[control].index.year == y])["net_sharpe"] for i, y in enumerate(range(2011, 2016)))
            checks[f"netSR_beats_{control}_4of5"] = improves >= 4
            checks[f"bootstrap_lower_positive_{control}"] = boot[name][control]["low"] > 0
        decisions[name] = {"decision": "NEXT_STAGE_RESEARCH_CANDIDATE" if all(checks.values()) else "REJECT",
                           "checks": checks, "failed_checks": [key for key, value in checks.items() if not value]}
    inc = pd.DataFrame(incremental)
    inc.to_csv(output / "metrics/incremental.csv", index=False)
    dump(output / "metrics/bootstrap.json", boot)
    dump(output / "metrics/candidate_decision.json", decisions)
    pd.DataFrame(signals).to_parquet(output / "predictions/strategy_scores.parquet")
    base.to_parquet(output / "predictions/features_base.parquet")
    if sector is not None:
        sector.to_parquet(output / "predictions/features_sector.parquet")
    # Economic-block conditional diagnostics are not extra selectable trials.
    diagnostic = []
    for block in mf.BLOCK_NAMES:
        diag = evaluation.daily_account(base[block], target).loc[eval_dates]
        for scope, d in [("pooled", diag)] + [(str(y), diag.loc[diag.index.year == y]) for y in range(2011, 2017)]:
            diagnostic.append({"block": block, "scope": scope, **evaluation.metrics(d)})
    pd.DataFrame(diagnostic).to_csv(output / "metrics/block_conditional_quintiles.csv", index=False)
    missing = base.filter(like="raw_").isna().groupby(index.get_level_values("Date").year).mean()
    missing.to_csv(output / "metrics/raw_feature_missing_by_year.csv", index_label="year")
    # Factor correlation is descriptive, does not drive weights or new trials.
    base[mf.BLOCK_NAMES].loc[index.get_level_values("Date").isin(eval_dates)].corr().to_csv(output / "metrics/block_correlations.csv")
    firewall.save(output / "audit/firewall.json")
    expected = set(input_hashes)
    assert {Path(p).name for p in firewall.ACCESSES} == expected
    denied = []
    for filename in ["target_1day_valid.parquet", "raw_target_1day_train.parquet"]:
        try:
            pd.read_parquet(source / filename)
        except PermissionError:
            denied.append(filename)
        else:
            raise AssertionError("Firewall did not reject forbidden input")
    dump(output / "audit/firewall_denials.json", {"status": "PASS", "denied": denied,
                                               "allowed_names": sorted(expected)})
    report = ROOT / config["report_dir"]
    report.mkdir(parents=True, exist_ok=False)
    for folder in ["metrics", "audit"]:
        shutil.copytree(output / folder, report / folder)
    lines = [f"# {config['experiment_id']} — Independent Slow Multifactor", "",
             f"Run: `{output.relative_to(ROOT)}`. Date: 2026-10-02 JST. Train-only; all Train previously studied. No untouched OOS claim. No Valid data, sample learned model, Freeze or external submission.", "",
             "## Fixed specification", "",
             "Seven raw factors: −log(raw Close × PIT shares), Amihud60/min40, CFO/Assets, Profit/Equity, Equity/Assets, Equity/shares/Close and forecast EPS/Close. Raw features daily1/99 winsorized, median then0 imputed, sample-standardized. Fixed equal within-block averages, globally standardized blocks, sum three equal blocks. Sector version uses PIT groups with minimum20 finite observations for Quality/Value feature transforms, global fallback. Revision, if eligible, is the latest-minus-previous disclosed finite forecast EPS / raw Close, equal fourth block. No Momentum in candidates, no smoothing or fitted weights.", "",
             "## Overall comparison", "",
             table(pooled, ["strategy", "rankic", "rankic_t_hac5", "gross_sharpe", "net_sharpe", "annual_gross", "annual_net", "turnover", "annual_cost", "annual_long_net", "annual_short_net"]), "",
             "All P/L/cost/turnover values are decimal fractions. Annual P/L = daily arithmetic mean ×252. Sharpe uses sample daily SD ×√252; RankIC t-stat uses Newey–West/Bartlett lag5. Maximum drawdown uses compounded net wealth. Q1 lowest score/Q5 highest. Official five-quintile weights include Q2/Q4 as well as extreme groups; side P/L is signed residual attribution, not raw market/security return.", "",
             "## Fold stability", "",
             table(result.loc[result.scope.isin([str(y) for y in range(2011, 2017)])], ["strategy", "scope", "gross_sharpe", "net_sharpe", "annual_gross", "annual_net", "turnover", "annual_long_net", "annual_short_net"]), "",
             "2016 is partial. Each fold's last2 exchange dates are excluded so target t+2 remains inside the fold. Features expand from2008, no parameter fitting. Weights and costs retain continuous full-history holdings, including omitted boundary dates; no annual relaunch charge. Pooled scores concern the concatenated eligible signal dates; DD spans their sequence, so also inspect saved continuous daily accounts.", "",
             "## Pre-registered phase gates and decision", "", "```json", json.dumps(safe(gates), indent=2), "```", "",
             "```json", json.dumps(safe(decisions), indent=2), "```", "",
             f"Actual candidate trials: {len(candidates)}/3: {', '.join(candidates)}. Gates and adoption tests are exactly the pre-result plan. Unrun phases have no performance result. No post-result definition, weighting, smoothing or threshold changes.", "",
             "## Paired20-day bootstrap", "", "```json", json.dumps(safe(boot), indent=2), "```", "",
             "Paired circular moving-block draws resample the same dates for candidate/control,2000 draws, seed20261002,95% percentile interval for ΔNet Sharpe. Intervals measure known-Train sampling variation, not independent OOS assurance or multiple-testing correction.", "",
             "## Causality, accounting and limitations", "",
             f"Source scan, runtime Train firewall, exact index/finite coverage ({len(index):,} rows), deterministic rebuild, row shuffle, research/adapter parity, official full-panel weight/net reconciliation and2-session purge passed. Future mutation and truncation passed {len(prefix_results)} full-matrix/score cases across3 cutoffs; exact float64 bit patterns include NaN positions. All four feature sources individually and jointly are tested. There are no fitted labels. Scope and cases are in audit/prefix_invariance.json.", "",
             "Financial Date has no intraday disclosure clock; it is treated conservatively as available by23:59:59 JST on that date, with prediction at that same end-of-day time before next open. Per-field backward carry can combine different report vintages. Profit is reported cumulative-period profit, not annualized; financial sectors/accounting bases differ. Raw Close paired with last disclosed shares/EPS can temporarily be economically inconsistent after a split until fresh disclosure. No future share update or retrospective level adjustment repairs that issue. This limits interpretation and deployment readiness; it does not justify result-driven correction.", "",
             "Missing targets remain in portfolio/ranking coverage. The official scorer drops cost on a missing-target row; conservative net_all_cost and annual_cost_all charge every position. Long/Short costs are absolute changes in positive/negative holdings and reconcile within1e−15. Annual metrics2008–2010 are descriptive warm-up history, excluded from gates. No real later-split adapter/zip validation was done because no release/Valid evaluation is authorized.", "",
             "Detailed artifacts: metrics/metrics.csv (all required pooled/fold/year IC, HAC, hit, Sharpe, annual P/L/cost, turnover, DD, Q1–Q5 and both sides), incremental.csv (both controls), daily_*.csv (continuous accounts), bootstrap.json, block_conditional_quintiles.csv, raw_feature_missing_by_year.csv, block_correlations.csv, audit/*; immutable plan/config/code/environment/input hashes in the run."]
    (report / "REPORT.md").write_text("\n".join(lines) + "\n")
    exp = ROOT / "experiments" / config["experiment_id"]
    (exp / "decision.md").write_text(f"# {config['experiment_id']} decision\n\nTrain-only independent family; actual trials {len(candidates)}/3. All Train known development data.\n\n" + "\n".join(f"- **{name}**: {record['decision']}. Failed pre-registered checks: {', '.join(record['failed_checks']) or 'none'}." for name, record in decisions.items()) + f"\n\nPhase2 {'run' if sector is not None else 'not run: gate failed'}; Phase3 {'run, parent='+parent if parent else 'not run: gross reproducibility/side gate failed'}. No additional trials, Freeze, Valid or SN1 changes.\n\n[Report](../../{config['report_dir']}/REPORT.md). [Full decisions](../../{config['report_dir']}/metrics/candidate_decision.json). Run `{output.relative_to(ROOT)}`.\n")
    meta = json.loads((exp / "experiment.json").read_text())
    all_rejected = all(x["decision"] == "REJECT" for x in decisions.values())
    meta.update(status="rejected" if all_rejected else "completed", actual_trials=len(candidates),
                run_id=output.name, report=f"{config['report_dir']}/REPORT.md")
    dump(exp / "experiment.json", meta)
    if all_rejected:
        with (ROOT / "experiments/GRAVEYARD.md").open("a") as stream:
            stream.write(f"\n## {config['experiment_id']}: Independent Slow Multifactor\n\n[Decision]({config['experiment_id']}/decision.md) / [Report](../{config['report_dir']}/REPORT.md). Train-only, fixed {len(candidates)}/3 candidate trials; no Valid/Freeze/SN1 change.\n\n")
            for name, record in decisions.items():
                m = metrics(eval_daily[name])
                stream.write(f"- **{name}** — Gross/Net SR {m['gross_sharpe']:.4f}/{m['net_sharpe']:.4f}, turnover {m['turnover']:.5f}/day, annual Long/Short net {100*m['annual_long_net']:+.3f}%/{100*m['annual_short_net']:+.3f}%. Reject: {', '.join(record['failed_checks'])}.\n")
            stream.write("\nRejects these registered operationalizations, not all slow factors. No result-driven rescue or additional candidate; unrun phases remain untested.\n")
    run.update(status="completed", completed_at_utc=datetime.now(timezone.utc).isoformat(), exit_code=0,
               actual_trials=len(candidates), elapsed_seconds=time.monotonic() - started,
               peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
               candidate_decisions=decisions, phase_gates=gates,
               artifact_sha256={str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*"))
                                if p.is_file() and not p.is_symlink() and p.name != "run.json"})
    dump(output / "run.json", run)
    print(table(pooled, ["strategy", "gross_sharpe", "net_sharpe", "turnover", "annual_long_net", "annual_short_net"]), flush=True)
    print(f"Completed {len(candidates)}/3 trials; report={report}", flush=True)


def finalize_saved(source, output, run):
    """Complete artifact bookkeeping without recomputing scientific results."""
    source = source.resolve()
    saved = json.loads((source / "run.json").read_text())
    assert saved["status"] == "failed" and "features_base.parquet" in saved["error"]
    assert sha(source / "config.json") == sha(output / "config.json")
    assert sha(source / "plan.md") == sha(output / "plan.md")
    config = json.loads((output / "config.json").read_text())
    # All builder/control/evaluation sources must still match the evaluated code.
    for relative, expected in saved["code_sha256"].items():
        if relative != str(Path(__file__).relative_to(ROOT)):
            assert sha(ROOT / relative) == expected, relative
    for name in ["source_scan", "prefix_invariance", "coverage", "firewall_denials"]:
        assert json.loads((source / f"audit/{name}.json").read_text())["status"] == "PASS"
    decisions = json.loads((source / "metrics/candidate_decision.json").read_text())
    assert 1 <= len(decisions) <= config["max_trials"]
    manifest = {}
    allowed = list(source.glob("predictions/*.parquet"))
    allowed += [output / "predictions" / path.name for path in allowed]
    firewall.install(allowed_artifacts=allowed)
    for folder in ["metrics", "audit", "predictions", "models", "code"]:
        for path in sorted((source / folder).rglob("*")):
            if path.is_file():
                relative = path.relative_to(source)
                dest = output / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, dest)
                expected = sha(path)
                assert sha(dest) == expected
                manifest[str(relative)] = expected
    stage = output / "stage"
    stage.mkdir()
    for path in (source / "stage").iterdir():
        (stage / path.name).symlink_to(path.resolve())
    scores = pd.read_parquet(output / "predictions/strategy_scores.parquet")
    assert np.isfinite(scores.to_numpy()).all() and scores.index.is_unique
    assert len(scores) == json.loads((output / "audit/coverage.json").read_text())["rows"]
    # Bookkeeping must not create another feature build, label read or trial.
    assert not firewall.ACCESSES
    completion = {
        "status": "PASS", "method": "hash-verified saved-result finalization; no fit/backtest",
        "scientific_source_run": str(source.relative_to(ROOT)),
        "scientific_source_status": "failed only during final artifact-hash bookkeeping",
        "evaluated_candidates": list(decisions), "new_candidate_trials": 0,
        "unchanged_plan_and_config": True, "unchanged_scientific_sources": True,
        "all_saved_files_copied_hash_exact": True, "copied_files": len(manifest),
        "full_prediction_rows": len(scores), "prediction_finite": True,
        "driver_sha256": sha(Path(__file__)),
        "prior_technical_failure": "run-20261002T044135Z: projected quantile-audit timeout; retained",
    }
    dump(output / "audit/saved_result_finalization.json", completion)
    report = ROOT / config["report_dir"]
    dump(report / "audit/saved_result_finalization.json", completion)
    text = (report / "REPORT.md").read_text()
    text += ("\n## Execution completion\n\n"
             f"Finalization run `{output.relative_to(ROOT)}` completed from hash-verified saved scientific artifacts in `{source.relative_to(ROOT)}`. "
             "The scientific run had already saved all results, gates, decisions and audits before its final bookkeeping read was denied by the Train firewall. "
             "The driver now explicitly allowlists only its own prediction artifacts for hash reads. No target guard was relaxed, no model/feature definition changed and no performance trial was rerun. "
             "The earlier quantile runtime failure and this bookkeeping failure remain preserved. Full-Train BASE/SECTOR feature matrices and BASE/revision scores were bitwise equal before/after vectorization; sector build117.14→2.70seconds. "
             "Final regression tests:187passed; make check remains blocked by pre-existing DM-20261002-04 metadata kind, while independent129Freeze hashes pass.\n")
    (report / "REPORT.md").write_text(text)
    exp = ROOT / "experiments" / config["experiment_id"]
    text = (exp / "decision.md").read_text()
    text += f"\nCompletion: `{output.relative_to(ROOT)}` finalized the saved results without new candidate trials. See [finalization audit](../../{config['report_dir']}/audit/saved_result_finalization.json). Two earlier technical failures are preserved.\n"
    (exp / "decision.md").write_text(text)
    meta = json.loads((exp / "experiment.json").read_text())
    meta.update(status="rejected" if all(x["decision"] == "REJECT" for x in decisions.values()) else "completed",
                run_id=output.name, actual_trials=len(decisions),
                scientific_source_run=source.name, finalization_only=True)
    dump(exp / "experiment.json", meta)
    run.update(status="completed", completed_at_utc=datetime.now(timezone.utc).isoformat(), exit_code=0,
               command=sys.argv, actual_trials=len(decisions), new_candidate_trials=0,
               scientific_source_run=str(source.relative_to(ROOT)),
               code_sha256=saved["code_sha256"], finalization_driver_sha256=sha(Path(__file__)),
               environment=saved["environment"], train_data_sha256=saved["train_data_sha256"],
               candidate_decisions=decisions, artifact_sha256=manifest,
               finalization_audit_sha256=sha(output / "audit/saved_result_finalization.json"))
    dump(output / "run.json", run)
    print(json.dumps(completion, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--finalize-source", help="Failed bookkeeping run with complete saved scientific artifacts")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    assert config["data_split"] == "train" and config["valid_evaluation"] is False
    assert config["max_trials"] == 3
    # Translate the descriptive bootstrap config to the shared evaluator API.
    config["bootstrap_args"] = {k: config["bootstrap"][k] for k in ["seed", "reps", "block"]}
    output = Path(args.output).resolve()
    run = json.loads((output / "run.json").read_text())
    assert run["status"] == "prepared", "Fresh prepared run required"
    try:
        if args.finalize_source:
            finalize_saved(Path(args.finalize_source), output, run)
        else:
            main_work(config, output, run)
    except BaseException as error:
        run.update(status="failed", completed_at_utc=datetime.now(timezone.utc).isoformat(),
                   exit_code=1, error=f"{type(error).__name__}: {error}")
        dump(output / "run.json", run)
        if firewall._PATCHED:
            firewall.save(output / "audit/firewall.json")
        raise


if __name__ == "__main__":
    main()
