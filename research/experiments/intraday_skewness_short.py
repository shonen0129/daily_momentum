"""DM-20260911-02: fixed-long I1/K1 Train-only experiment."""
import argparse
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

from research import firewall
from research.evaluation import bootstrap_delta, weights, rankic
from research.experiments import asymmetric_evaluation as ev
from research.experiments.fixed_long_short import compute_extended_account, long_side_audit
from stock_comp_2026.strategies.dm_intraday_skewness_short import features as strategy


ROOT = Path(__file__).resolve().parents[2]
TRIALS = ["H0", "I1", "K1"]


def now(): return datetime.now(timezone.utc).isoformat()


def clean(x):
    if isinstance(x, dict): return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [clean(v) for v in x]
    if isinstance(x, (np.floating, float)): return float(x) if np.isfinite(x) else None
    if isinstance(x, (np.integer,)): return int(x)
    if isinstance(x, (np.bool_,)): return bool(x)
    if isinstance(x, (pd.Timestamp, pd.Period)): return str(x)
    return x


def dump(path, value): Path(path).write_text(json.dumps(clean(value), ensure_ascii=False, indent=2) + "\n")


def digest(path):
    with Path(path).open("rb") as file: return hashlib.file_digest(file, "sha256").hexdigest()


def source_scan():
    import ast
    paths = sorted(Path(strategy.__file__).parent.glob("*.py"))
    forbidden = ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose", "AdjustmentVolume",
                 "raw_target", "target_1day_valid"]
    for path in paths:
        text = path.read_text()
        for token in forbidden:
            if token in text: raise AssertionError(f"forbidden {token}: {path}")
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("bfill", "backfill"): raise AssertionError(f"backfill: {path}")
                if any(k.arg == "center" and isinstance(k.value, ast.Constant) and k.value.value for k in node.keywords):
                    raise AssertionError(f"center rolling: {path}")
                if any(k.arg == "direction" and isinstance(k.value, ast.Constant) and k.value.value == "forward" for k in node.keywords):
                    raise AssertionError(f"forward join: {path}")
    return [str(path.relative_to(ROOT)) for path in paths]


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


def causality(inputs, original, specs):
    records = []
    for label in ("2010-12-30", "2012-06-29", "2014-12-30"):
        cutoff = pd.Timestamp(label)
        prefix = original.index.get_level_values("Date") <= cutoff
        expected = original.loc[prefix]
        for mode in ("mutation", "truncation"):
            actual = strategy.build_features(mutate(inputs, cutoff, truncate=mode == "truncation"))
            pd.testing.assert_frame_equal(expected, actual.loc[expected.index], check_exact=True)
            for spec in specs:
                left = strategy.predict_from_features(original, spec).loc[expected.index]
                right = strategy.predict_from_features(actual, spec).loc[expected.index]
                pd.testing.assert_series_equal(left, right, check_exact=True)
        records.append({"cutoff": label, "rows": int(prefix.sum()), "features": int(original.shape[1]), "bitwise": True})
    return {"status": "PASS", "source_files": source_scan(), "prefix_tests": records}


def annual_deltas(record, baseline):
    a = pd.DataFrame(record["folds"]).set_index("year")
    b = pd.DataFrame(baseline["folds"]).set_index("year")
    cols = ["rankic", "gross_sharpe", "net_sharpe", "turnover", "annual_cost", "annual_net",
            "annual_short_gross", "annual_short_net", "short_cost_all", "annual_long_net",
            "max_drawdown_additive"]
    return (a[cols] - b[cols]).reset_index().to_dict("records")


def short_tail_diagnostics(signals, target, years):
    rows = []
    for trial in ("H0", "K1"):
        score = signals[trial]
        weight, _ = weights(score)
        data = pd.DataFrame({"target": target.reindex(score.index), "weight": weight, "year": score.index.get_level_values("Date").year})
        for year, block in data.groupby("year"):
            if year not in years: continue
            values = block.loc[block.weight < 0, "target"].dropna()
            if values.empty: continue
            rows.append({"trial": trial, "year": int(year), "rows": int(len(values)), "mean": values.mean(),
                         "median": values.median(), "p90": values.quantile(.90), "p95": values.quantile(.95),
                         "p99": values.quantile(.99), "maximum": values.max()})
        values = data.loc[(data.weight < 0) & data.year.isin(years), "target"].dropna()
        rows.append({"trial": trial, "year": "pooled", "rows": int(len(values)), "mean": values.mean(),
                     "median": values.median(), "p90": values.quantile(.90), "p95": values.quantile(.95),
                     "p99": values.quantile(.99), "maximum": values.max()})
    return pd.DataFrame(rows)


def disaster_days(daily):
    rows = []
    for trial in ("H0", "K1"):
        values = daily[trial].short_net.dropna()
        for fraction in (.01, .05):
            n = max(1, int(np.ceil(len(values) * fraction)))
            rows.append({"trial": trial, "tail": f"worst_{int(fraction * 100)}pct", "days": n,
                         "mean_short_net": float(values.nsmallest(n).mean())})
    return pd.DataFrame(rows)


def intraday_diagnostics(features, target, signals, years):
    day_rank = features.daymom60_rank
    mask = day_rank.index.get_level_values("Date").year.isin(years)
    data = pd.DataFrame({"score": day_rank.loc[mask], "target": target.reindex(day_rank.index[mask])})
    daily_ic = rankic(data.score, data.target)
    ranks = data.score.groupby(level="Date").rank(method="first", pct=True)
    rows = [{"metric": "mean_rankic", "value": daily_ic.mean()},
            {"metric": "rankic_t_hac5", "value": ev.hac_t(daily_ic)},
            {"metric": "rankic_hit_ratio", "value": (daily_ic.dropna() > 0).mean()}]
    for bucket, selected in (("Q1", ranks <= .2), ("Q2", (ranks > .2) & (ranks <= .4)),
                             ("Q3", (ranks > .4) & (ranks <= .6)), ("Q4", (ranks > .6) & (ranks <= .8)),
                             ("Q5", ranks > .8), ("bottom_decile", ranks <= .1), ("top_decile", ranks > .9)):
        rows.append({"metric": bucket + "_future_return", "value": data.target.where(selected).groupby(level="Date").mean().mean()})
    persistence = day_rank.groupby(core_segment_keys(day_rank.index), sort=False).transform(lambda x: x.shift(1))
    corr = pd.DataFrame({"a": day_rank, "b": persistence}).groupby(level="Date").apply(
        lambda x: x.a.corr(x.b, method="spearman")
    )
    rows.append({"metric": "daily_rank_autocorrelation", "value": corr.mean()})
    # Compare the intended Short directions: I1 risk versus a weak existing M60 Long score.
    compare = pd.DataFrame({"i1_risk": features.intraday_short_risk, "m60_short_risk": -features.L})
    compare = compare.loc[mask]
    daily_corr = compare.groupby(level="Date").apply(lambda x: x.i1_risk.corr(x.m60_short_risk, method="spearman"))
    q_i = compare.i1_risk.groupby(level="Date").rank(method="first", pct=True) > .8
    q_m = compare.m60_short_risk.groupby(level="Date").rank(method="first", pct=True) > .8
    overlap = (q_i & q_m).groupby(level="Date").sum() / q_m.groupby(level="Date").sum()
    return pd.DataFrame(rows), pd.DataFrame({"Date": daily_corr.index, "daily_spearman": daily_corr.values,
                                               "short_quintile_overlap": overlap.reindex(daily_corr.index).values})


def core_segment_keys(index):
    from stock_comp_2026.strategies.dm_fixed_long_short import core
    return core.segment_keys(index)


def skewness_validation(features):
    forecasts = features.attrs["expected_skewness_forecasts"].copy()
    monthly = features.attrs["monthly_statistics"][["Code", "segment", "month", "realized_skewness"]].copy()
    table = forecasts.merge(monthly, left_on=["Code", "segment", "forecast_month"], right_on=["Code", "segment", "month"], how="left")
    table["all_source_before_forecast"] = table.characteristic_max_date < table.forecast_month.dt.start_time
    rows = []
    for month, block in table.groupby("forecast_month", observed=True):
        good = block.dropna(subset=["expected_skewness", "realized_skewness"])
        if len(good) < 3: continue
        low = good.expected_skewness.rank(method="first", pct=True) <= .2
        high = good.expected_skewness.rank(method="first", pct=True) > .8
        rows.append({"forecast_month": str(month), "rows": int(len(good)),
                     "rankic": spearmanr(good.expected_skewness, good.realized_skewness).statistic,
                     "pearson": pearsonr(good.expected_skewness, good.realized_skewness).statistic,
                     "top_minus_bottom_realized_skewness": good.loc[high, "realized_skewness"].mean() - good.loc[low, "realized_skewness"].mean()})
    return table, pd.DataFrame(rows), features.attrs["skewness_coefficients"].copy()


def report(config, records, output, report_dir):
    baseline = records[0]
    lines = [f"# {config['experiment_id']}: Intraday Momentum Short / Skewness-Managed FD Short", "",
             f"Run: `{output.name}`. Train-only: Valid and raw target files were blocked and not read.", "",
             "## Required conclusion table", "",
             "| Trial | Decision | Total Net SR | Short Ann Gross | Short Ann Net | Short Gross SR | Short Net SR | Short Positive Folds | Short Improved Folds | Short Turnover |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for item in records:
        m, c = item["metrics"], item.get("comparison", {})
        lines.append(f"| {item['id']} | {item.get('decision', 'Reference')} | {m['net_sharpe']:.4f} | {m['annual_short_gross']:.2%} | {m['annual_short_net']:.2%} | {m['short_gross_sharpe']:.4f} | {m['short_net_sharpe']:.4f} | {c.get('short_positive_folds', '—')} | {c.get('short_improved_folds', '—')} | {m['short_turnover']:.4f} |")
    lines += ["", "## Main performance", "", "| Trial | Total Net SR | Long Ann Net | Long Net SR | Short Ann Net | Short Net SR | Short Turnover | Total Turnover | Cost | MaxDD |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for item in records:
        m = item["metrics"]
        lines.append(f"| {item['id']} | {m['net_sharpe']:.4f} | {m['annual_long_net']:.2%} | {m['long_net_sharpe']:.4f} | {m['annual_short_net']:.2%} | {m['short_net_sharpe']:.4f} | {m['short_turnover']:.4f} | {m['turnover']:.4f} | {m['annual_cost']:.2%} | {m['max_drawdown_additive']:.2%} |")
    lines += ["", "## Fixed Long audit", "", "All I1/K1 Q4/Q5 memberships, Long weights, and daily Long P/L are required to equal H0 exactly; `long_fixed_audit.csv` records the zero-difference evidence.", "",
              "## Fold stability", "", "| Trial | Year | Total Net SR | Short Ann Gross | Short Ann Net | Short Gross SR | Short Net SR | Short Turnover | Q1 | Q2 |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for item in records:
        for fold in item["folds"]:
            lines.append(f"| {item['id']} | {fold['year']} | {fold['net_sharpe']:.4f} | {fold['annual_short_gross']:.2%} | {fold['annual_short_net']:.2%} | {fold['short_gross_sharpe']:.4f} | {fold['short_net_sharpe']:.4f} | {fold['short_turnover']:.4f} | {fold['q1_daily_return']:.5%} | {fold['q2_daily_return']:.5%} |")
    lines += ["", "## Answers", "",
              "- Q1: `audit/h0_reproduction.json` records the exact C0/T1 prediction reproduction.",
              "- Q2: `long_fixed_audit.csv` is the required zero-difference audit.",
              "- Q3–Q8: I1 gross/net, fold counts, RankIC, quintiles, persistence, and M60 overlap are in the main table, `short_side_metrics.csv`, `intraday_momentum_metrics.csv`, and `intraday_vs_m60.csv`.",
              "- Q9–Q16: K1 gross/net, expected-skew forecast diagnostics, underlying right-tail, and worst short P/L days are in `short_side_metrics.csv`, `expected_skewness_validation.csv`, `short_tail_diagnostics.csv`, and `short_disaster_days.csv`.",
              "- Q17–Q20: Total-Net-SR deltas, bootstrap diagnostics, and four annual folds are in `incremental.csv`, `bootstrap_results.json`, and `fold_metrics.csv`; no independent-OOS claim is made for this previously explored Train period.",
              "- Q21: only preregistered H0/I1/K1 were scored. Q22: cumulative known scoring count is 75 (72 prior + 3). Q23: firewall audit records no Valid or raw-label read.", "",
              "## Decision rule", "", "I1/K1 require ≥3/4 Short improvement folds, positive median ΔShort annual Net, and pooled Short Net above H0. Champion replacement also requires Total pooled Net SR above H0 and ≥3/4 Total-Net-SR improvement folds. No candidate is added after this report."]
    (report_dir / "REPORT.md").write_text("\n".join(lines) + "\n")


def run(config_path, output_path):
    started = time.monotonic()
    config = json.loads(Path(config_path).read_text())
    assert config["data_split"] == "train" and config["valid_evaluation"] is False
    assert [x["trial_id"] for x in config["trials"]] == TRIALS and config["max_trials"] == 3
    output, report_dir = Path(output_path), ROOT / "reports" / config["experiment_id"]
    for folder in (output / "audit", output / "metrics", output / "predictions", output / "logs", report_dir): folder.mkdir(parents=True, exist_ok=True)
    metadata = json.loads((output / "run.json").read_text())
    metadata.update(status="running", started_at_utc=now(), command=sys.argv, actual_trials=0,
                    environment={"python": sys.version, "platform": platform.platform()})
    dump(output / "run.json", metadata)
    h0_artifact = ROOT / "artifacts/DM-20260909-03/run-20260909T080902Z/predictions/C0.parquet"
    firewall.install(allowed_artifacts=[h0_artifact])
    try:
        data_dir = ROOT / "stock_comp_2026/input"
        input_names = ["raw_return_1day", "beta_1day", "topix_return_1day", "listed_info", "fins_statements", "prices_daily_quotes"]
        metadata["train_data_sha256"] = {f"{name}_train.parquet": digest(data_dir / f"{name}_train.parquet") for name in input_names}
        metadata["code_sha256"] = {str(path.relative_to(ROOT)): digest(path) for path in [Path(__file__), Path(strategy.__file__), ROOT / "research/evaluation.py", ROOT / "research/firewall.py"]}
        inputs = strategy.load_inputs(data_dir, "train")
        features = strategy.build_features(inputs)
        specs = config["trials"]
        dump(output / "audit/causality.json", causality(inputs, features, specs))
        h0 = strategy.predict_from_features(features, specs[0])
        prior_h0 = pd.read_parquet(h0_artifact)["Return"].sort_index()
        pd.testing.assert_series_equal(h0, prior_h0, check_exact=True)
        dump(output / "audit/h0_reproduction.json", {"status": "PASS", "rows": int(len(h0)), "bitwise": True})
        forecast_table, validation, coefficients = skewness_validation(features)
        if not forecast_table.all_source_before_forecast.fillna(False).all(): raise AssertionError("skewness source date entered forecast month")
        forecast_table.to_csv(output / "expected_skewness_monthly.csv", index=False)
        validation.to_csv(output / "expected_skewness_validation.csv", index=False)
        coefficients.to_csv(output / "skewness_regression_coefficients.csv", index=False)
        dump(output / "audit/expected_skewness_timing.json", {"status": "PASS", "forecasts": int(len(forecast_table)),
             "all_source_dates_before_forecast": True, "minimum_observations": 15, "predictors": strategy.PREDICTORS})
        target_path = data_dir / "target_1day_train.parquet"
        target = pd.read_parquet(target_path)["Return"].sort_index()
        metadata["train_data_sha256"][target_path.name] = digest(target_path)
        calendar = features.index.get_level_values("Date").unique().sort_values()
        evaluation_dates = ev.safe_dates(calendar, [2011, 2012, 2013, 2014])
        mask = features.index.get_level_values("Date").isin(evaluation_dates)
        signals, daily, records, bootstrap = {}, {}, [], {}
        for spec in specs:
            ident = spec["trial_id"]
            signal = strategy.predict_from_features(features, spec); signals[ident] = signal
            signal.to_frame().to_parquet(output / "predictions" / f"{ident}.parquet")
            account = compute_extended_account(signal.loc[mask], target.reindex(signal.index[mask]), base_sig=signals["H0"].loc[mask])
            daily[ident] = account; account.to_csv(output / "metrics" / f"{ident}.csv")
            audit = ({"membership_diff_count": 0, "long_weight_diff_max": 0.0, "long_gross_pl_diff_max": 0.0,
                      "long_gross_pl_diff_sum": 0.0, "long_preserved": True} if ident == "H0" else
                     long_side_audit(signals["H0"].loc[mask], signal.loc[mask], target.reindex(signal.index[mask])))
            record = {"id": ident, "spec": spec, "metrics": ev.extended_metrics(account), "folds": ev.fold_metrics(account), "long_audit": audit}
            if ident != "H0":
                base, candidate = pd.DataFrame(records[0]["folds"]).set_index("year"), pd.DataFrame(record["folds"]).set_index("year")
                delta_short, delta_total = candidate.annual_short_net - base.annual_short_net, candidate.net_sharpe - base.net_sharpe
                checks = {"short_improved_folds": int((delta_short > 0).sum()) >= 3, "median_delta_short_net": float(delta_short.median()) > 0,
                          "pooled_short_above_h0": record["metrics"]["annual_short_net"] > records[0]["metrics"]["annual_short_net"],
                          "total_net_sr_above_h0": record["metrics"]["net_sharpe"] > records[0]["metrics"]["net_sharpe"],
                          "total_net_sr_improved_folds": int((delta_total > 0).sum()) >= 3, "long_exact": audit["long_preserved"]}
                bootstrap[ident] = {"delta_short_net_sr": bootstrap_delta(daily["H0"].short_net, account.short_net, seed=config["random_seed"], reps=1000, block=20),
                                    "delta_total_net_sr": bootstrap_delta(daily["H0"].net, account.net, seed=config["random_seed"], reps=1000, block=20)}
                record["comparison"] = {"checks": checks, "short_positive_folds": int((candidate.annual_short_net > 0).sum()),
                    "short_improved_folds": int((delta_short > 0).sum()), "median_delta_short_net": float(delta_short.median()),
                    "delta_short_net": float(record["metrics"]["annual_short_net"] - records[0]["metrics"]["annual_short_net"]),
                    "delta_total_net_sr": float(record["metrics"]["net_sharpe"] - records[0]["metrics"]["net_sharpe"]), "fold_deltas": annual_deltas(record, records[0])}
                record["decision"] = "Champion candidate" if all(checks.values()) else ("Short success; not Champion" if all(list(checks.values())[:3]) else "Reject")
            records.append(record); metadata["actual_trials"] = len(records); dump(output / "trial_registry.json", records)
        pd.DataFrame([{**{"trial": x["id"]}, **x["metrics"], "decision": x.get("decision", "Reference")} for x in records]).to_csv(output / "model_comparison.csv", index=False)
        pd.DataFrame([{**{"trial": x["id"]}, **fold} for x in records for fold in x["folds"]]).to_csv(output / "fold_metrics.csv", index=False)
        pd.DataFrame([{**{"trial": x["id"]}, **row} for x in records[1:] for row in x["comparison"]["fold_deltas"]]).to_csv(output / "incremental.csv", index=False)
        pd.DataFrame([{**{"trial": x["id"]}, **x["long_audit"]} for x in records]).to_csv(output / "long_fixed_audit.csv", index=False)
        pd.DataFrame([{**{"trial": x["id"]}, **{key: x["metrics"][key] for key in ["annual_long_gross", "annual_long_net", "long_gross_sharpe", "long_net_sharpe", "long_turnover", "long_cost_all"]}} for x in records]).to_csv(output / "long_side_metrics.csv", index=False)
        pd.DataFrame([{**{"trial": x["id"]}, **{key: x["metrics"][key] for key in ["annual_short_gross", "annual_short_net", "short_gross_sharpe", "short_net_sharpe", "short_turnover", "short_cost_all", "short_net_all_cost_sharpe"]}} for x in records]).to_csv(output / "short_side_metrics.csv", index=False)
        pd.DataFrame([{**{"trial": x["id"]}, **{key: x["metrics"][key] for key in ["q1_daily_return", "q2_daily_return", "q3_daily_return", "q4_daily_return", "q5_daily_return", "q_monotonicity"]}} for x in records]).to_csv(output / "quintile_metrics.csv", index=False)
        intraday_metrics, intraday_vs_m60 = intraday_diagnostics(features, target, signals, [2011, 2012, 2013, 2014])
        intraday_metrics.to_csv(output / "intraday_momentum_metrics.csv", index=False)
        intraday_vs_m60.to_csv(output / "intraday_vs_m60.csv", index=False)
        intraday_vs_m60.to_csv(output / "intraday_feature_diagnostics.csv", index=False)
        short_tail_diagnostics(signals, target, [2011, 2012, 2013, 2014]).to_csv(output / "short_tail_diagnostics.csv", index=False)
        disaster_days(daily).to_csv(output / "short_disaster_days.csv", index=False)
        pd.DataFrame([{**{"trial": x["id"]}, "delta_gross_sharpe": x["metrics"]["gross_sharpe"] - records[0]["metrics"]["gross_sharpe"],
                       "delta_cost": x["metrics"]["annual_cost"] - records[0]["metrics"]["annual_cost"], "delta_net_sharpe": x["metrics"]["net_sharpe"] - records[0]["metrics"]["net_sharpe"]} for x in records[1:]]).to_csv(output / "turnover_cost_decomposition.csv", index=False)
        dump(output / "bootstrap_results.json", bootstrap)
        confirmation = {}
        confirm_dates = ev.safe_dates(calendar, [2015, 2016]); confirm_dates = confirm_dates[confirm_dates <= pd.Timestamp("2016-03-31")]
        cmask = features.index.get_level_values("Date").isin(confirm_dates)
        for ident, signal in signals.items(): confirmation[ident] = ev.extended_metrics(compute_extended_account(signal.loc[cmask], target.reindex(signal.index[cmask]), base_sig=signals["H0"].loc[cmask]))
        dump(output / "confirmation.json", confirmation)
        firewall.save(output / "audit/firewall.json")
        report(config, records, output, report_dir)
        for source in sorted(output.iterdir()):
            if source.is_file():
                target_report = report_dir / source.name
                target_report.write_bytes(source.read_bytes())
        manifest = {str(path.relative_to(output)): digest(path) for path in sorted(output.rglob("*")) if path.is_file() and path.name != "hash_manifest.json"}
        dump(output / "hash_manifest.json", manifest)
        metadata.update(status="completed", completed_at_utc=now(), exit_code=0, elapsed_seconds=time.monotonic() - started)
        dump(output / "run.json", metadata)
    except BaseException:
        metadata.update(status="failed", completed_at_utc=now(), exit_code=1, elapsed_seconds=time.monotonic() - started)
        dump(output / "run.json", metadata)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.config, args.output)
