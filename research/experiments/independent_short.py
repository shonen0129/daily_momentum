"""Train-only preregistered H0/V1/V2/V3 evaluation for DM-20260910-01."""
import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from research import firewall
from research.evaluation import bootstrap_delta, weights
from research.experiments import asymmetric_evaluation as ev
from research.experiments.fixed_long_short import compute_extended_account, long_side_audit
from stock_comp_2026.strategies.dm_independent_short import features as strategy

ROOT = Path(__file__).resolve().parents[2]


def now():
    return datetime.now(timezone.utc).isoformat()


def clean(value):
    if isinstance(value, dict): return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(v) for v in value]
    if isinstance(value, (np.floating, float)): return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer): return int(value)
    if isinstance(value, np.bool_): return bool(value)
    return value


def dump(path, value):
    Path(path).write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, default=str) + "\n")


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def mutate(inputs, cutoff, truncate=False):
    result = {}
    for name, frame in inputs.items():
        dates = frame.index.get_level_values("Date")
        if dates.tz is not None: dates = dates.tz_localize(None)
        future = dates > cutoff
        if truncate:
            result[name] = frame.loc[~future].copy()
            continue
        changed = frame.copy()
        for column in changed:
            if isinstance(changed[column].dtype, pd.CategoricalDtype): changed[column] = changed[column].astype(str)
            if pd.api.types.is_numeric_dtype(changed[column]): changed.loc[future, column] = changed.loc[future, column] * -13 + 999
            elif pd.api.types.is_datetime64_any_dtype(changed[column]): changed.loc[future, column] = pd.Timestamp("1990-01-01")
            else: changed.loc[future, column] = "future_changed"
        result[name] = changed
    return result


def source_scan():
    forbidden = ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose", "AdjustmentVolume",
                 "raw_target", "target_1day_valid"]
    paths = sorted(Path(strategy.__file__).parent.glob("*.py"))
    for path in paths:
        text = path.read_text()
        for token in forbidden:
            if token in text: raise AssertionError(f"forbidden {token} in {path}")
    return [str(path.relative_to(ROOT)) for path in paths]


def causality(inputs, original, trials):
    records = []
    for label in ["2010-12-30", "2012-06-29", "2014-12-30"]:
        cutoff = pd.Timestamp(label)
        prefix = original.index.get_level_values("Date") <= cutoff
        for mode in ["mutation", "truncation"]:
            actual = strategy.build_features(mutate(inputs, cutoff, truncate=(mode == "truncation")))
            pd.testing.assert_frame_equal(original.loc[prefix], actual.loc[original.index[prefix]], check_exact=True)
            for trial in trials:
                expected = strategy.predict_from_features(original, trial).loc[original.index[prefix]]
                result = strategy.predict_from_features(actual, trial).loc[original.index[prefix]]
                pd.testing.assert_series_equal(expected, result, check_exact=True)
        records.append({"cutoff": label, "rows": int(prefix.sum()), "feature_count": len(original.columns), "bitwise": True})
    return {"status": "PASS", "source_files": source_scan(), "prefix_tests": records}


def annual_folds(record, baseline):
    a, b = pd.DataFrame(record["folds"]).set_index("year"), pd.DataFrame(baseline["folds"]).set_index("year")
    columns = ["rankic", "gross_sharpe", "net_sharpe", "turnover", "annual_cost", "annual_short_net",
               "annual_long_net", "annual_net", "max_drawdown_additive"]
    return (a[columns] - b[columns]).reset_index().to_dict("records")


def coverage(features):
    dates = features.index.get_level_values("Date")
    rows = []
    for name, raw, risk in [("V1", "cfo_yield", "v1_risk"), ("V2", "accrual", "v2_risk"), ("V3", "max20", "v3_risk")]:
        for year, values in features.groupby(dates.year):
            rows.append({"candidate": name, "year": int(year), "rows": int(len(values)),
                         "usable_rate": float(values[raw].notna().mean()),
                         "missing_rate": float(values[raw].isna().mean()),
                         "cross_section_mean": float(values.groupby(level="Date")[raw].count().mean()),
                         "neutral_rate": float((values[risk] == .5).mean())})
    return pd.DataFrame(rows)


def correlations(features):
    values = pd.DataFrame({"H0_FD": features.fd_equal, "V1": features.v1_risk,
                           "V2": features.v2_risk, "V3": features.v3_risk})
    rows = []
    for date, block in values.groupby(level="Date"):
        corr = block.corr(method="spearman")
        for i, left in enumerate(corr.columns):
            for right in corr.columns[i + 1:]:
                rows.append({"Date": date, "left": left, "right": right, "correlation": corr.loc[left, right]})
    data = pd.DataFrame(rows)
    return data.groupby(["left", "right"], as_index=False).correlation.agg(["mean", "count"]).reset_index()


def tail_table(features, target, years):
    rows = []
    data = features.loc[features.index.get_level_values("Date").year.isin(years)]
    for trial, risk in [("V1", "v1_risk"), ("V2", "v2_risk"), ("V3", "v3_risk")]:
        for year, block in data.groupby(data.index.get_level_values("Date").year):
            value, ret = block[risk], target.reindex(block.index)
            rank = value.groupby(level="Date").rank(method="average", pct=True)
            for label, mask in [("top_short_risk_decile", rank >= .9), ("bottom_short_risk_decile", rank <= .1),
                                ("Q1", rank <= .2), ("Q2", (rank > .2) & (rank <= .4))]:
                daily = ret.where(mask).groupby(level="Date").mean()
                rows.append({"trial": trial, "year": int(year), "bucket": label, "daily_return": float(daily.mean()),
                             "days": int(daily.notna().sum())})
    return pd.DataFrame(rows)


def report(config, records, output, report_dir, confirmation):
    baseline = records[0]
    lines = [f"# {config['experiment_id']}: Independent Short Alpha Families", "",
             f"Run: `{output.name}`. Train-only; no Valid or raw-target file was opened. No Freeze/submission was created.", "",
             "## Result", "", "| Candidate | Decision | Net SR | ΔNet SR | Short annual Net | ΔShort annual Net | Turnover | Short-positive folds | Short-improved folds | Long fixed |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|:---:|"]
    for item in records:
        m, c = item["metrics"], item.get("comparison", {})
        lines.append(f"| {item['id']} | {item.get('decision', 'Reference')} | {m['net_sharpe']:.4f} | {c.get('delta_net_sr', 0):+.4f} | {m['annual_short_net']:.2%} | {c.get('delta_short_net', 0):+.2%} | {m['turnover']:.4f} | {c.get('short_positive_folds', '—')} | {c.get('short_improved_folds', '—')} | {'PASS' if item['long_audit']['long_preserved'] else 'FAIL'} |")
    lines += ["", "## Primary criteria", "", "A candidate is Adoptable only with pooled Short annual Net > 0, at least 3/4 positive Short folds, at least 3/4 Short-improvement folds, positive median ΔShort annual Net, Net SR >= H0, and exact Long preservation.", "",
              "| Candidate | Pooled Short > 0 | Positive Short folds | Improved Short folds | Median ΔShort > 0 | Net SR >= H0 |", "|---|:---:|:---:|:---:|:---:|:---:|"]
    for item in records[1:]:
        q = item["comparison"]["checks"]
        lines.append(f"| {item['id']} | {'PASS' if q['pooled_short_positive'] else 'FAIL'} | {'PASS' if q['short_positive_folds'] else 'FAIL'} | {'PASS' if q['short_improved_folds'] else 'FAIL'} | {'PASS' if q['median_short_improvement'] else 'FAIL'} | {'PASS' if q['net_sharpe'] else 'FAIL'} |")
    lines += ["", "## Fold detail", "", "| Candidate | Year | Net SR | ΔNet SR | Short annual Net | ΔShort annual Net | Turnover |", "|---|---:|---:|---:|---:|---:|---:|"]
    for item in records:
        delta = {x["year"]: x for x in item.get("comparison", {}).get("fold_deltas", [])}
        for metric in item["folds"]:
            d = delta.get(metric["year"], {})
            lines.append(f"| {item['id']} | {metric['year']} | {metric['net_sharpe']:.4f} | {d.get('net_sharpe', 0):+.4f} | {metric['annual_short_net']:.2%} | {d.get('annual_short_net', 0):+.2%} | {metric['turnover']:.4f} |")
    lines += ["", "## Required answers", "",
              "- Q1–Q5: The table above records each family relative to Champion and the primary Short/Total tests.",
              "- Q6: Turnover and annual cost are in `model_comparison.csv` and the incremental table.",
              "- Q7–Q9: `tail_diagnostics.csv`, `feature_correlations.csv`, and annual folds record tail separation, information overlap, and year dependence.",
              "- Q10: `long_fixed_audit.csv` requires every difference to be zero.",
              "- Q11: Known cumulative scoring trials are 56 (52 before this four-candidate experiment).",
              "- Q12: Only H0/V1/V2/V3 were scored; no formula/window/candidate was added after the prepared snapshot.",
              "- Q13: Firewall audit records Train-only reads; Valid was not referenced.", "",
              "## Descriptive-only previously seen Train", "", "2015–2016-03 and 2008–2010 were generated only after the candidate decisions and did not alter them.", "",
              "| Window | Candidate | Net SR | Short annual Net | Turnover |", "|---|---|---:|---:|---:|"]
    for name, trials in confirmation.items():
        for trial, metric in trials.items(): lines.append(f"| {name} | {trial} | {metric['net_sharpe']:.4f} | {metric['annual_short_net']:.2%} | {metric['turnover']:.4f} |")
    (report_dir / "REPORT.md").write_text("\n".join(lines) + "\n")


def run(config_path, output):
    config = json.loads(Path(config_path).read_text())
    assert config["data_split"] == "train" and config["valid_evaluation"] is False
    assert [x["trial_id"] for x in config["trials"]] == ["H0", "V1", "V2", "V3"]
    output, report_dir = Path(output), ROOT / "reports" / config["experiment_id"]
    for path in [output / "audit", output / "metrics", output / "predictions", output / "logs", report_dir]: path.mkdir(parents=True, exist_ok=True)
    metadata = json.loads((output / "run.json").read_text())
    metadata.update(status="running", started_at_utc=now(), command=sys.argv, actual_trials=0)
    dump(output / "run.json", metadata)
    old = ROOT / "artifacts/DM-20260909-03/run-20260909T080902Z/predictions/C0.parquet"
    firewall.install(allowed_artifacts=[old])
    try:
        data = ROOT / "stock_comp_2026/input"
        names = ["raw_return_1day", "beta_1day", "topix_return_1day", "listed_info", "fins_statements", "prices_daily_quotes"]
        metadata["train_data_sha256"] = {f"{name}_train.parquet": digest(data / f"{name}_train.parquet") for name in names}
        metadata["code_sha256"] = {str(path.relative_to(ROOT)): digest(path) for path in [Path(__file__), Path(strategy.__file__), ROOT / "research/firewall.py", ROOT / "research/evaluation.py"]}
        inputs = strategy.load_inputs(data, "train")
        features = strategy.build_features(inputs)
        dump(output / "audit/financial_state.json", features.attrs["financial_state_audit"])
        dump(output / "audit/causality.json", causality(inputs, features, config["trials"]))
        h0 = strategy.predict_from_features(features, config["trials"][0])
        previous = pd.read_parquet(old)["Return"].sort_index()
        pd.testing.assert_series_equal(h0, previous, check_exact=True)
        dump(output / "audit/h0_c0_prediction.json", {"status": "PASS", "rows": len(h0), "bitwise": True})
        target_path = data / "target_1day_train.parquet"
        target = pd.read_parquet(target_path)["Return"].sort_index()
        metadata["train_data_sha256"][target_path.name] = digest(target_path)
        calendar = features.index.get_level_values("Date").unique().sort_values()
        dev = ev.safe_dates(calendar, [2011, 2012, 2013, 2014]); mask = features.index.get_level_values("Date").isin(dev)
        signals, daily, records, boot = {}, {}, [], {}
        for trial in config["trials"]:
            ident = trial["trial_id"]; signal = strategy.predict_from_features(features, trial); signals[ident] = signal
            signal.to_frame().to_parquet(output / f"predictions/{ident}.parquet")
            account = compute_extended_account(signal.loc[mask], target.loc[signal.index[mask]], base_sig=signals["H0"].loc[mask])
            daily[ident] = account; account.to_csv(output / f"metrics/{ident}.csv")
            audit = {"membership_diff_count": 0, "long_weight_diff_max": 0.0, "long_gross_pl_diff_max": 0.0, "long_gross_pl_diff_sum": 0.0, "long_preserved": True} if ident == "H0" else long_side_audit(signals["H0"].loc[mask], signal.loc[mask], target.loc[signal.index[mask]])
            record = {"id": ident, "spec": trial, "metrics": ev.extended_metrics(account), "folds": ev.fold_metrics(account), "long_audit": audit}
            if ident != "H0":
                base_folds, cand_folds = pd.DataFrame(records[0]["folds"]).set_index("year"), pd.DataFrame(record["folds"]).set_index("year")
                delta_short = cand_folds.annual_short_net - base_folds.annual_short_net
                checks = {"pooled_short_positive": record["metrics"]["annual_short_net"] > 0,
                          "short_positive_folds": int((cand_folds.annual_short_net > 0).sum()) >= 3,
                          "short_improved_folds": int((delta_short > 0).sum()) >= 3,
                          "median_short_improvement": float(delta_short.median()) > 0,
                          "net_sharpe": record["metrics"]["net_sharpe"] >= records[0]["metrics"]["net_sharpe"],
                          "long_fixed": audit["long_preserved"]}
                boot[ident] = {"delta_net_sharpe": bootstrap_delta(daily["H0"].net, account.net, seed=config["random_seed"], reps=1000, block=20),
                               "delta_short_net": bootstrap_delta(daily["H0"].short_net, account.short_net, seed=config["random_seed"], reps=1000, block=20)}
                record["comparison"] = {"checks": checks, "short_positive_folds": int((cand_folds.annual_short_net > 0).sum()), "short_improved_folds": int((delta_short > 0).sum()), "median_delta_short_net": float(delta_short.median()), "delta_short_net": float(record["metrics"]["annual_short_net"] - records[0]["metrics"]["annual_short_net"]), "delta_net_sr": float(record["metrics"]["net_sharpe"] - records[0]["metrics"]["net_sharpe"]), "fold_deltas": annual_folds(record, records[0])}
                record["decision"] = "Adoptable" if all(checks.values()) else ("Promising but insufficient" if checks["pooled_short_positive"] or checks["short_positive_folds"] else "Reject")
            records.append(record); metadata["actual_trials"] = len(records); dump(output / "trial_registry.json", records)
        pd.DataFrame([{**{"trial": x["id"]}, **x["metrics"], "decision": x.get("decision", "Reference")} for x in records]).to_csv(output / "model_comparison.csv", index=False)
        pd.DataFrame([{**{"trial": x["id"]}, **fold} for x in records for fold in x["folds"]]).to_csv(output / "fold_metrics.csv", index=False)
        pd.DataFrame([{**{"trial": x["id"]}, **row} for x in records[1:] for row in x["comparison"]["fold_deltas"]]).to_csv(output / "incremental.csv", index=False)
        pd.DataFrame([{**{"trial": x["id"]}, **x["long_audit"]} for x in records]).to_csv(output / "long_fixed_audit.csv", index=False)
        pd.DataFrame([{**{"trial": x["id"]}, "short_gross_annual": x["metrics"]["annual_short_gross"], "short_net_annual": x["metrics"]["annual_short_net"], "short_net_sharpe": x["metrics"]["short_net_sharpe"], "short_turnover": x["metrics"]["short_turnover"], "short_cost_annual": x["metrics"]["short_cost_all"]} for x in records]).to_csv(output / "short_side_metrics.csv", index=False)
        pd.DataFrame([{**{"trial": x["id"]}, "long_gross_annual": x["metrics"]["annual_long_gross"], "long_net_annual": x["metrics"]["annual_long_net"], "long_net_sharpe": x["metrics"]["long_net_sharpe"], "long_turnover": x["metrics"]["long_turnover"], "long_cost_annual": x["metrics"]["long_cost_all"]} for x in records]).to_csv(output / "long_side_metrics.csv", index=False)
        pd.DataFrame([{**{"trial": x["id"]}, **{key: x["metrics"][key] for key in ["q1_daily_return", "q2_daily_return", "q3_daily_return", "q4_daily_return", "q5_daily_return", "q_monotonicity"]}} for x in records]).to_csv(output / "quintile_metrics.csv", index=False)
        coverage(features).to_csv(output / "feature_coverage.csv", index=False)
        correlations(features).to_csv(output / "feature_correlations.csv", index=False)
        tail_table(features, target, [2011, 2012, 2013, 2014]).to_csv(output / "tail_diagnostics.csv", index=False)
        dump(output / "bootstrap_results.json", boot)
        confirmation = {}
        for window in config["confirmation_policy"]["windows"]:
            chosen = ev.safe_dates(calendar, window["years"]); selected = features.index.get_level_values("Date").isin(chosen); confirmation[window["name"]] = {}
            for ident, signal in signals.items(): confirmation[window["name"]][ident] = ev.extended_metrics(compute_extended_account(signal.loc[selected], target.loc[signal.index[selected]], base_sig=signals["H0"].loc[selected]))
        dump(output / "confirmation.json", confirmation); firewall.save(output / "audit/firewall.json")
        manifest = {str(path.relative_to(output)): digest(path) for path in sorted(output.rglob("*")) if path.is_file() and path.name != "hash_manifest.json"}
        dump(output / "hash_manifest.json", manifest)
        copy_names = ["model_comparison.csv", "fold_metrics.csv", "incremental.csv", "long_fixed_audit.csv", "short_side_metrics.csv", "long_side_metrics.csv", "quintile_metrics.csv", "tail_diagnostics.csv", "feature_coverage.csv", "feature_correlations.csv", "bootstrap_results.json", "trial_registry.json", "confirmation.json"]
        for name in copy_names: shutil.copyfile(output / name, report_dir / name)
        report(config, records, output, report_dir, confirmation)
        (report_dir / "EXPERIMENT_LOG.md").write_text("\n".join([f"# Experiment Log: {config['experiment_id']}", "", f"- Run: `{output.name}`", "- Train-only; no Valid or raw target access.", "", *[f"- {x['id']}: NetSR={x['metrics']['net_sharpe']:.4f}; ShortNet={x['metrics']['annual_short_net']:.2%}; {x.get('decision', 'Reference')}" for x in records]]) + "\n")
        metadata.update(status="completed", finished_at_utc=now(), exit_code=0); dump(output / "run.json", metadata)
    except Exception as exc:
        metadata.update(status="failed", finished_at_utc=now(), error=repr(exc), exit_code=1); dump(output / "run.json", metadata); raise


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--config", required=True); parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.config, args.output)


if __name__ == "__main__": main()
