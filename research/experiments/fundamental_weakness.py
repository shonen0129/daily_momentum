"""Train-only, preregistered C0--C3 evaluation for DM-20260909-03."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

import numpy as np
import pandas as pd

from research import firewall
from research.evaluation import bootstrap_delta
from research.experiments import asymmetric_evaluation as ev
from research.experiments.fixed_long_short import compute_extended_account, long_side_audit
from stock_comp_2026.strategies.dm_fundamental_weakness import features as fw

ROOT = Path(__file__).resolve().parents[2]


def now():
    return datetime.now(timezone.utc).isoformat()


def dump(path, value):
    def clean(x):
        if isinstance(x, dict): return {k: clean(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)): return [clean(v) for v in x]
        if isinstance(x, (np.floating, float)): return float(x) if np.isfinite(x) else None
        if isinstance(x, np.integer): return int(x)
        if isinstance(x, np.bool_): return bool(x)
        return x
    Path(path).write_text(json.dumps(clean(value), indent=2, ensure_ascii=False, default=str) + "\n")


def sha256(path):
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
        altered = frame.copy()
        for column in altered:
            if isinstance(altered[column].dtype, pd.CategoricalDtype): altered[column] = altered[column].astype(str)
            if pd.api.types.is_numeric_dtype(altered[column]): altered.loc[future, column] = altered.loc[future, column] * -13 + 999
            elif pd.api.types.is_datetime64_any_dtype(altered[column]): altered.loc[future, column] = pd.Timestamp("1990-01-01")
            else: altered.loc[future, column] = "future_changed"
        result[name] = altered
    return result


def source_scan():
    forbidden = ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose", "AdjustmentVolume", "raw_target", "target_1day_valid"]
    paths = sorted(Path(fw.__file__).parent.glob("*.py"))
    for path in paths:
        text = path.read_text()
        for token in forbidden:
            if token in text: raise AssertionError(f"forbidden {token} in {path}")
    return [str(path.relative_to(ROOT)) for path in paths]


def causality_audit(inputs, features):
    trials = [{"trial_id": x} for x in ["C0", "C1", "C2", "C3"]]
    records = []
    for value in ["2010-12-30", "2012-06-29", "2014-12-30"]:
        cutoff = pd.Timestamp(value)
        before = features.loc[features.index.get_level_values("Date") <= cutoff]
        for mode in ["mutation", "truncation"]:
            after = fw.build_features(mutate(inputs, cutoff, truncate=(mode == "truncation")))
            pd.testing.assert_frame_equal(before, after.loc[before.index], check_exact=True)
            for trial in trials:
                expected = fw.predict_from_features(features, trial).loc[before.index]
                actual = fw.predict_from_features(after, trial).loc[before.index]
                pd.testing.assert_series_equal(expected, actual, check_exact=True)
        records.append({"cutoff": value, "rows": len(before), "features": len(before.columns), "bitwise": True})
    return {"status": "PASS", "source_files": source_scan(), "prefix_tests": records}


def fold_delta(candidate, baseline):
    a, b = pd.DataFrame(candidate).set_index("year"), pd.DataFrame(baseline).set_index("year")
    cols = ["rankic", "gross_sharpe", "net_sharpe", "turnover", "annual_cost", "annual_short_net", "annual_long_net", "annual_net", "max_drawdown_additive"]
    return (a[cols] - b[cols]).reset_index().to_dict("records")


def report(config, records, confirmation, out, report_dir, run_id):
    base = records[0]
    lines = [f"# {config['experiment_id']}: Continuous Fundamental Weakness Short", "",
             f"Run: `{run_id}`. Train-only; Valid and raw target were not opened. No Freeze/submission was created.", "",
             "## Result", "", "| Trial | Decision | Net SR | ΔNet SR vs C0 | Short annual Net | ΔShort annual Net | Turnover | RankIC | Max DD |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for item in records:
        metric = item["metrics"]
        comp = item.get("comparison", {})
        lines.append(f"| {item['id']} | {item.get('decision', 'Reference')} | {metric['net_sharpe']:.4f} | {comp.get('pooled_delta_net_sr', 0):+.4f} | {metric['annual_short_net']:.2%} | {comp.get('pooled_delta_short_net', 0):+.2%} | {metric['turnover']:.4f} | {metric['rankic']:.5f} | {metric['max_drawdown_additive']:.2%} |")
    lines += ["", "## Primary short-side criteria (vs C0)", "", "| Trial | Short improvement folds | Median ΔShort Net | Pooled Short > C0 | Net SR ≥ C0 | Long fixed | Decision |",
              "|---|---:|---:|:---:|:---:|:---:|---|"]
    for item in records[1:]:
        comp = item["comparison"]
        checks = comp["checks"]
        lines.append(f"| {item['id']} | {comp['short_improved_folds']}/4 | {comp['median_delta_short_net']:+.2%} | {'PASS' if checks['pooled_short_net'] else 'FAIL'} | {'PASS' if checks['net_sharpe'] else 'FAIL'} | {'PASS' if checks['long_fixed'] else 'FAIL'} | **{item['decision']}** |")
    lines += ["", "## Fold detail", "", "| Trial | Year | Net SR | ΔNet SR | Short annual Net | ΔShort annual Net | Turnover |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for item in records:
        delta = {row['year']: row for row in item.get('comparison', {}).get('fold_deltas', [])}
        for metric in item["folds"]:
            d = delta.get(metric["year"], {})
            lines.append(f"| {item['id']} | {metric['year']} | {metric['net_sharpe']:.4f} | {d.get('net_sharpe', 0):+.4f} | {metric['annual_short_net']:.2%} | {d.get('annual_short_net', 0):+.2%} | {metric['turnover']:.4f} |")
    lines += ["", "## Descriptive only: previously seen Train", "", "2015–2016-03 and 2008–2010 were evaluated only after the fixed four-candidate comparison; they were not used for selection.", "",
              "| Window | Trial | Net SR | Short annual Net | Turnover |", "|---|---|---:|---:|---:|"]
    for window, values in confirmation.items():
        for trial, value in values.items():
            metric = value["metrics"]
            lines.append(f"| {window} | {trial} | {metric['net_sharpe']:.4f} | {metric['annual_short_net']:.2%} | {metric['turnover']:.4f} |")
    lines += ["", "## Conclusion", "", "C0 is an exact reproduction control for DM-20260909-02 T1. C1–C3 are judged only by the preregistered criteria above. A positive Train short leg, if any, is not evidence of future alpha.", "",
              f"Artifacts: `artifacts/{config['experiment_id']}/{run_id}`."]
    (report_dir / "REPORT.md").write_text("\n".join(lines) + "\n")


def run(config_path, out):
    config = json.loads(Path(config_path).read_text())
    assert config["data_split"] == "train" and config["valid_evaluation"] is False
    assert [x["trial_id"] for x in config["trials"]] == ["C0", "C1", "C2", "C3"]
    out = Path(out); report_dir = ROOT / "reports" / config["experiment_id"]
    for path in [out / "audit", out / "metrics", out / "predictions", out / "logs", report_dir]: path.mkdir(parents=True, exist_ok=True)
    run_meta = json.loads((out / "run.json").read_text())
    run_meta.update(status="running", started_at_utc=now(), command=sys.argv, actual_trials=0)
    dump(out / "run.json", run_meta)
    old_pred = ROOT / "artifacts/DM-20260909-02/run-20260909T061458Z/predictions/T1.parquet"
    firewall.install(allowed_artifacts=[old_pred])
    try:
        data = ROOT / "stock_comp_2026/input"
        names = ["raw_return_1day", "beta_1day", "topix_return_1day", "listed_info", "fins_statements"]
        run_meta["train_data_sha256"] = {f"{name}_train.parquet": sha256(data / f"{name}_train.parquet") for name in names}
        run_meta["code_sha256"] = {str(p.relative_to(ROOT)): sha256(p) for p in [Path(__file__), Path(fw.__file__), ROOT / "research/firewall.py", ROOT / "research/evaluation.py"]}
        inputs = fw.load_inputs(data, "train")
        features = fw.build_features(inputs)
        dump(out / "audit/extended_financial.json", features.attrs.get("extended_financial_audit", {}))
        dump(out / "audit/causality.json", causality_audit(inputs, features))
        c0 = fw.predict_from_features(features, {"trial_id": "C0"})
        pd.testing.assert_series_equal(c0, pd.read_parquet(old_pred)["Return"], check_exact=True)
        dump(out / "audit/c0_t1_prediction.json", {"status": "PASS", "rows": len(c0), "bitwise": True})
        # Labels are opened only after all feature/causality checks have passed.
        target = pd.read_parquet(data / "target_1day_train.parquet")["Return"].sort_index()
        run_meta["train_data_sha256"]["target_1day_train.parquet"] = sha256(data / "target_1day_train.parquet")
        dates = features.index.get_level_values("Date"); calendar = dates.unique().sort_values()
        dev_dates = ev.safe_dates(calendar, [2011, 2012, 2013, 2014])
        records, signals, daily = [], {}, {}
        for trial in config["trials"]:
            ident = trial["trial_id"]; signal = fw.predict_from_features(features, trial); signals[ident] = signal
            signal.to_frame().to_parquet(out / f"predictions/{ident}.parquet")
            mask = dates.isin(dev_dates); account = compute_extended_account(signal.loc[mask], target.loc[signal.index[mask]], base_sig=signals["C0"].loc[mask])
            daily[ident] = account; account.to_csv(out / f"metrics/{ident}.csv")
            audit = {"long_preserved": True, "membership_diff_count": 0, "long_weight_diff_max": 0.0, "long_gross_pl_diff_max": 0.0} if ident == "C0" else long_side_audit(signals["C0"].loc[mask], signal.loc[mask], target.loc[signal.index[mask]])
            record = {"id": ident, "spec": trial, "metrics": ev.extended_metrics(account), "folds": ev.fold_metrics(account), "long_audit": audit}
            if ident != "C0":
                bfold, cfold = pd.DataFrame(records[0]["folds"]).set_index("year"), pd.DataFrame(record["folds"]).set_index("year")
                dshort, dsr = cfold.annual_short_net - bfold.annual_short_net, cfold.net_sharpe - bfold.net_sharpe
                checks = {"short_folds": int((dshort > 0).sum()) >= config["selection_rule"]["short_improved_folds_min"], "median_short": float(dshort.median()) > 0, "pooled_short_net": record["metrics"]["annual_short_net"] > records[0]["metrics"]["annual_short_net"], "net_sharpe": record["metrics"]["net_sharpe"] >= records[0]["metrics"]["net_sharpe"], "long_fixed": audit["long_preserved"]}
                boot = bootstrap_delta(daily["C0"]["net"], account["net"], seed=config["random_seed"], reps=1000, block=20)
                record["comparison"] = {"checks": checks, "short_improved_folds": int((dshort > 0).sum()), "median_delta_short_net": float(dshort.median()), "pooled_delta_short_net": record["metrics"]["annual_short_net"] - records[0]["metrics"]["annual_short_net"], "pooled_delta_net_sr": record["metrics"]["net_sharpe"] - records[0]["metrics"]["net_sharpe"], "fold_deltas": fold_delta(record["folds"], records[0]["folds"]), "bootstrap": boot}
                record["decision"] = "採用可能" if all(checks.values()) and boot["low"] > 0 else ("Promising but insufficient" if all(checks.values()) else "却下")
            records.append(record); run_meta["actual_trials"] = len(records); dump(out / "trial_registry.json", records)
        old_daily = pd.read_csv(ROOT / "artifacts/DM-20260909-02/run-20260909T061458Z/metrics/T1.csv", index_col=0)
        np.testing.assert_allclose(daily["C0"][["gross", "net", "turnover", "cost"]].to_numpy(), old_daily[["gross", "net", "turnover", "cost"]].to_numpy(), rtol=0, atol=1e-15)
        dump(out / "audit/c0_t1_portfolio.json", {"status": "PASS", "q_membership": "implied by bitwise score", "daily_pl": "CSV round-trip tolerance <=1e-15", "rows": len(daily["C0"])})
        confirmation = {}
        for label, years in [("2015-2016-03", [2015, 2016]), ("2008-2010", [2008, 2009, 2010])]:
            selected = ev.safe_dates(calendar, years); mask = dates.isin(selected); confirmation[label] = {}
            for ident, signal in signals.items():
                account = compute_extended_account(signal.loc[mask], target.loc[signal.index[mask]], base_sig=signals["C0"].loc[mask])
                confirmation[label][ident] = {"metrics": ev.extended_metrics(account)}
        pd.DataFrame([{**{"trial": r["id"]}, **r["metrics"], **({"decision": r.get("decision", "Reference")})} for r in records]).to_csv(out / "model_comparison.csv", index=False)
        pd.DataFrame([{"trial": r["id"], **f} for r in records for f in r["folds"]]).to_csv(out / "fold_metrics.csv", index=False)
        pd.DataFrame([{"trial": r["id"], **row} for r in records[1:] for row in r["comparison"]["fold_deltas"]]).to_csv(out / "incremental.csv", index=False)
        pd.DataFrame([{"trial": r["id"], **r["long_audit"]} for r in records]).to_csv(out / "long_fixed_audit.csv", index=False)
        dump(out / "confirmation.json", confirmation)
        for name in ["model_comparison.csv", "fold_metrics.csv", "incremental.csv", "long_fixed_audit.csv", "trial_registry.json", "confirmation.json"]: shutil.copyfile(out / name, report_dir / name)
        report(config, records, confirmation, out, report_dir, run_meta["run_id"])
        (report_dir / "EXPERIMENT_LOG.md").write_text("\n".join([f"# Experiment Log: {config['experiment_id']}", "", f"- Run: `{run_meta['run_id']}`", "- Train-only; Valid/raw target not read.", "", *[f"- {r['id']}: NetSR={r['metrics']['net_sharpe']:.4f}; ShortNet={r['metrics']['annual_short_net']:.2%}; {r.get('decision', 'Reference')}" for r in records]]) + "\n")
        run_meta.update(status="completed", finished_at_utc=now()); dump(out / "run.json", run_meta)
        return records
    except Exception as exc:
        run_meta.update(status="failed", finished_at_utc=now(), error=repr(exc)); dump(out / "run.json", run_meta); raise


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--config", required=True); parser.add_argument("--output", required=True)
    run(parser.parse_args().config, parser.parse_args().output)


if __name__ == "__main__": main()
