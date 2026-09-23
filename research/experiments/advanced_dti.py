"""Train-only finite advanced-DTI experiment DM-20260911-01."""
import argparse
import ast
import json
import platform
import resource
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from research import firewall
from research.evaluation import bootstrap_delta, weights
from research.experiments import asymmetric_evaluation as ev
from research.experiments import dti_long_short as prior
from research.experiments.dri_long_short import enrich_metrics, fold_metrics, tail_and_quintile
from research.experiments.fixed_long_short import compute_extended_account
from stock_comp_2026.strategies.dm_advanced_dti import features as advanced
from stock_comp_2026.strategies.dm_independent_short import features as champion


ROOT = Path(__file__).resolve().parents[2]
MODEL_YEARS = range(2011, 2017)
REPRESENTATIONS = ("D0", "A1", "S1", "U1", "R1")
TRIALS = ("H0", "D0", "S0", "A1", "S1", "U1", "R1")


def validate(config):
    assert config["data_split"] == "train" and config["valid_evaluation"] is False
    assert [x["trial_id"] for x in config["trials"]] == list(TRIALS)
    assert config["max_trials"] == len(TRIALS)
    assert [x["year"] for x in config["walk_forward_folds"]] == [2011, 2012, 2013, 2014]
    assert config["purge_trading_days"] == 2 and config["parameters"]["d0_ewma_alpha"] == .25
    assert config["parameters"]["candidate_ewma_alpha"] == .05
    assert config["parameters"]["fixed_alpha"] == .0003 and config["parameters"]["fixed_l1_ratio"] == .1
    assert config["transaction_cost_oneway"] == .001 and config["annualization"] == 252


def source_scan():
    forbidden = ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose", "AdjustmentVolume", "raw_target", "target_1day_valid"]
    paths = sorted(Path(advanced.__file__).parent.glob("*.py"))
    for path in paths:
        text = path.read_text()
        for token in forbidden:
            if token in text:
                raise AssertionError(f"forbidden {token} in {path}")
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr in ("bfill", "backfill"):
                raise AssertionError(f"backfill in {path}")
            if node.func.attr == "shift" and node.args and (not isinstance(node.args[0], ast.Constant) or node.args[0].value < 0):
                raise AssertionError(f"negative/dynamic shift in {path}")
            if any(k.arg == "center" and isinstance(k.value, ast.Constant) and k.value.value for k in node.keywords):
                raise AssertionError(f"center rolling in {path}")
            if any(k.arg == "direction" and isinstance(k.value, ast.Constant) and k.value.value == "forward" for k in node.keywords):
                raise AssertionError(f"forward join in {path}")
    return [str(path.relative_to(ROOT)) for path in paths]


def select_model(features, target, representation, config, calendar):
    """The unchanged finite RankIC grid, separately fit for each fixed representation."""
    columns, params = advanced.feature_columns(representation), config["parameters"]
    eligible = features[f"{representation}_available"].to_numpy() & target.reindex(features.index).notna().to_numpy()
    dates, rows = features.index.get_level_values("Date"), []
    for alpha in params["alpha_grid"]:
        for ratio in params["l1_ratio_grid"]:
            folds = []
            for split in params["initial_cv"]:
                train = prior.available_until(features.index, split["train_end"], calendar) & eligible
                valid = ((dates >= pd.Timestamp(split["validation_start"])) &
                         prior.available_until(features.index, split["validation_end"], calendar) & eligible)
                model = prior.fit_model(features.loc[train, columns], target.loc[features.index[train]], alpha, ratio, params)
                pred = pd.Series(model.predict(features.loc[valid, columns]), index=features.index[valid])
                folds.append({"rows": int(valid.sum()), "rankic": prior.score_rankic(pred, target.loc[pred.index])})
            rows.append({"representation": representation, "alpha": float(alpha), "l1_ratio": float(ratio),
                         "mean_rankic": float(np.average([x["rankic"] for x in folds], weights=[x["rows"] for x in folds])), "folds": folds})
    best = max(row["mean_rankic"] for row in rows)
    tied = [row for row in rows if row["mean_rankic"] == best]
    winner = min(tied, key=lambda row: (-row["alpha"], -row["l1_ratio"]))
    for row in rows:
        row["selected"] = row["alpha"] == winner["alpha"] and row["l1_ratio"] == winner["l1_ratio"]
    return winner, rows


def annual_models(features, target, selected, config, calendar):
    models, raw_scores, coefficients, audit = {}, {}, [], []
    dates = features.index.get_level_values("Date")
    for representation in REPRESENTATIONS:
        columns, available = advanced.feature_columns(representation), features[f"{representation}_available"].to_numpy()
        score = pd.Series(0.0, index=features.index, name="Return")
        for year in MODEL_YEARS:
            cutoff = pd.Timestamp(year=year - 1, month=12, day=31)
            train = prior.available_until(features.index, cutoff, calendar) & available & target.reindex(features.index).notna().to_numpy()
            model = prior.fit_model(features.loc[train, columns], target.loc[features.index[train]], selected[representation]["alpha"], selected[representation]["l1_ratio"], config["parameters"])
            take = (dates.year == year) & available
            if take.any():
                rows = features.loc[take, columns]
                predicted = rows.groupby(level="Date", sort=False, group_keys=False).apply(
                    lambda block: pd.Series(model.predict(block), index=block.index), include_groups=False)
                score.loc[predicted.index] = predicted
            models[(representation, year)] = model
            scaler, elastic = model.named_steps["scaler"], model.named_steps["elasticnet"]
            max_fit = features.index.get_level_values("Date")[train].max()
            audit.append({"representation": representation, "model_year": year, "fit_cutoff": str(cutoff.date()),
                          "max_feature_label_date": str(max_fit.date()), "training_label_realization_max_date": str(max_fit.date()),
                          "scaler_fit_max_date": str(max_fit.date()), "train_rows": int(train.sum()), "prediction_rows": int(take.sum()),
                          "past_only": bool(max_fit < pd.Timestamp(year=year, month=1, day=1))})
            for feature, coef, mean, scale in zip(columns, elastic.coef_, scaler.mean_, scaler.scale_):
                coefficients.append({"representation": representation, "model_year": year, "feature": feature,
                                     "coefficient": float(coef), "scaler_mean": float(mean), "scaler_scale": float(scale),
                                     "intercept": float(elastic.intercept_), "alpha": float(elastic.alpha), "l1_ratio": float(elastic.l1_ratio),
                                     "train_rows": int(train.sum()), "max_fit_date": str(max_fit.date())})
        raw_scores[representation] = score
    return models, raw_scores, pd.DataFrame(coefficients), audit


def signals_from_scores(features, raw, config):
    p = config["parameters"]
    return {
        "D0": advanced.smooth_complete(raw["D0"], features.D0_available, p["d0_ewma_alpha"]),
        "S0": advanced.smooth_complete(raw["D0"], features.D0_available, p["candidate_ewma_alpha"]),
        **{name: advanced.smooth_complete(raw[name], features[f"{name}_available"], p["candidate_ewma_alpha"])
           for name in ("A1", "S1", "U1", "R1")},
    }


def causality(inputs, features, models, selected, config):
    """All changed inputs after each cutoff must leave every earlier feature and score bitwise fixed."""
    original_raw = _predict(features, models)
    original = signals_from_scores(features, original_raw, config)
    records = []
    for label in ("2010-12-30", "2012-06-29", "2014-12-30"):
        cutoff = pd.Timestamp(label)
        before = features.loc[features.index.get_level_values("Date") <= cutoff]
        for mode in ("mutation", "truncation"):
            changed = advanced.build_features(prior.mutate(inputs, cutoff, mode == "truncation"))
            pd.testing.assert_frame_equal(before, changed.loc[before.index], check_exact=True)
            altered = signals_from_scores(changed, _predict(changed, models), config)
            for trial in original:
                pd.testing.assert_series_equal(original[trial].loc[before.index], altered[trial].loc[before.index], check_exact=True)
        records.append({"cutoff": label, "rows": int(len(before)), "features": int(before.shape[1]), "bitwise": True})
    return {"status": "PASS", "source_files": source_scan(), "prefix_tests": records}


def _predict(features, models):
    dates, result = features.index.get_level_values("Date"), {}
    for representation in REPRESENTATIONS:
        columns, available = advanced.feature_columns(representation), features[f"{representation}_available"].to_numpy()
        score = pd.Series(0.0, index=features.index, name="Return")
        for year in MODEL_YEARS:
            take = (dates.year == year) & available
            if take.any():
                rows = features.loc[take, columns]
                prediction = rows.groupby(level="Date", sort=False, group_keys=False).apply(
                    lambda block: pd.Series(models[(representation, year)].predict(block), index=block.index), include_groups=False)
                score.loc[prediction.index] = prediction
        result[representation] = score
    return result


def comparison(record, base):
    current, reference = pd.DataFrame(record["folds"]).set_index("year"), pd.DataFrame(base["folds"]).set_index("year")
    delta = current - reference
    return {"delta_rankic": float(record["metrics"]["rankic"] - base["metrics"]["rankic"]),
            "delta_gross_sr": float(record["metrics"]["gross_sharpe"] - base["metrics"]["gross_sharpe"]),
            "delta_net_sr": float(record["metrics"]["net_sharpe"] - base["metrics"]["net_sharpe"]),
            "delta_annual_gross": float(record["metrics"]["annual_gross"] - base["metrics"]["annual_gross"]),
            "delta_annual_net": float(record["metrics"]["annual_net"] - base["metrics"]["annual_net"]),
            "delta_turnover": float(record["metrics"]["turnover"] - base["metrics"]["turnover"]),
            "delta_cost": float(record["metrics"]["annual_cost"] - base["metrics"]["annual_cost"]),
            "net_improved_folds": int((delta.net_sharpe > 0).sum()), "net_positive_folds": int((current.net_sharpe > 0).sum()),
            "long_positive_folds": int((current.long_net_sharpe > 0).sum()), "short_positive_folds": int((current.short_net_sharpe > 0).sum()),
            "fold_deltas": delta.reset_index().to_dict("records")}


def status(record, h0):
    m, c = record["metrics"], record["comparison"]
    return {"dti_salvage": bool(m["net_sharpe"] > 0 and c["net_positive_folds"] >= 3 and m["annual_net"] > 0),
            "champion_replacement": bool(m["net_sharpe"] > h0["metrics"]["net_sharpe"] and c["net_improved_folds"] >= 3),
            "long_success": bool(m["long_net_sharpe"] > 0 and c["long_positive_folds"] >= 3),
            "short_success": bool(m["short_net_sharpe"] > 0 and c["short_positive_folds"] >= 3),
            "gross_only": bool(m["gross_sharpe"] > 0 and m["net_sharpe"] <= 0)}


def pair_diagnostics(signals, coefficients, dev_mask, output):
    correlations, overlap = [], []
    pairs = [("D0", "S0"), ("S0", "A1"), ("A1", "S1"), ("A1", "U1"), ("A1", "R1"), ("S1", "U1"), ("S1", "R1"), ("U1", "R1")]
    for left, right in pairs:
        x, y = signals[left].loc[dev_mask], signals[right].loc[dev_mask]
        daily = pd.concat([x.rename("left"), y.rename("right")], axis=1).groupby(level="Date").apply(lambda z: z.left.corr(z.right, method="spearman"), include_groups=False)
        correlations.append({"left": left, "right": right, "mean_daily_spearman": float(daily.mean())})
        _, qx, = weights(x); _, qy = weights(y)
        overlap.append({"left": left, "right": right, "q5_overlap": float(((qx == 4) & (qy == 4)).groupby(level="Date").mean().mean()),
                        "q1_overlap": float(((qx == 0) & (qy == 0)).groupby(level="Date").mean().mean())})
    pd.DataFrame(correlations).to_csv(output / "feature_correlations.csv", index=False)
    pd.DataFrame(overlap).to_csv(output / "portfolio_overlap.csv", index=False)
    def block(feature):
        channel = "up" if feature.startswith("up_") else "down" if feature.startswith("down_") else "rcato" if feature.startswith("rc_") else "signed" if feature.startswith("signed_") else "ato" if feature.startswith("ato_") else "raw_to"
        order = "chronological" if "_time_" in feature else "sorted"
        return channel, order
    tagged = coefficients.copy(); tagged[["channel", "order"]] = tagged.feature.apply(lambda x: pd.Series(block(x)))
    tagged.assign(abs_coefficient=tagged.coefficient.abs()).groupby(["representation", "model_year", "channel", "order"], as_index=False).agg(nonzero_count=("coefficient", lambda x: int((x != 0).sum())), sum_abs_coefficient=("abs_coefficient", "sum"), l2_norm=("coefficient", lambda x: float(np.linalg.norm(x)))).to_csv(output / "coefficient_block_summary.csv", index=False)
    rows = []
    for representation, frame in coefficients.groupby("representation"):
        matrix = frame.pivot(index="model_year", columns="feature", values="coefficient")
        for year, row in matrix.iterrows(): rows.append({"representation": representation, "model_year": int(year), "nonzero_count": int((row != 0).sum()), "l1_norm": float(row.abs().sum()), "l2_norm": float(np.linalg.norm(row))})
        for left in matrix.index:
            for right in matrix.index:
                if left < right: rows.append({"representation": representation, "model_year": f"{left}-{right}", "coefficient_correlation": float(matrix.loc[left].corr(matrix.loc[right])), "sign_consistency": float((np.sign(matrix.loc[left]) == np.sign(matrix.loc[right])).mean())})
    pd.DataFrame(rows).to_csv(output / "coefficient_stability.csv", index=False)


def report(config, records, output):
    lines = [f"# {config['experiment_id']}: Advanced DTI Representation Research", "", f"Run: `{output.name}`. Train-only; Valid and raw target were not read.", "", "## Main table", "", "| Trial | Gross SR | Net SR | Ann Gross | Ann Cost | Ann Net | Turnover | Long Net SR | Short Net SR | MaxDD |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in records:
        m = row["metrics"]
        lines.append(f"| {row['id']} | {m['gross_sharpe']:.4f} | {m['net_sharpe']:.4f} | {m['annual_gross']:.2%} | {m['annual_cost']:.2%} | {m['annual_net']:.2%} | {m['turnover']:.4f} | {m['long_net_sharpe']:.4f} | {m['short_net_sharpe']:.4f} | {m['max_drawdown_additive']:.2%} |")
    h0, d0, s0 = records[0], records[1], records[2]
    best_gross, best_net = max(records[1:], key=lambda r: r["metrics"]["gross_sharpe"]), max(records[1:], key=lambda r: r["metrics"]["net_sharpe"])
    lines += ["", "## Required answers", "", f"- Q1–Q3: D0→S0 turnover {s0['comparison_d0']['delta_turnover']:+.4f}, annual cost {s0['comparison_d0']['delta_cost']:+.2%}, Gross SR {s0['comparison_d0']['delta_gross_sr']:+.4f}, Net SR {s0['comparison_d0']['delta_net_sr']:+.4f}; S0 salvage={s0['checks']['dti_salvage']}.", f"- Q4–Q9: representation increments relative to S0/A1 are in `incremental.csv`; no unregistered candidate was run.", f"- Q10–Q15: best Gross SR={best_gross['id']} ({best_gross['metrics']['gross_sharpe']:.4f}); best Net SR={best_net['id']} ({best_net['metrics']['net_sharpe']:.4f}). DTI salvage, long and short statuses are in `trial_registry.json`.", "- Q16–Q24: break-even cost, gross retention, annual folds, quintiles, tails, coefficient blocks, stability, dispersion, turnover attribution and bootstrap diagnostics are retained in the linked CSV/JSON outputs.", f"- Q25: Champion replacement candidates: {', '.join(r['id'] for r in records[1:] if r['checks']['champion_replacement']) or 'none'}.", "- Q26: cumulative known scoring trials = 72 (65 prior + 7 fixed current candidates).", "- Q27: No feature, smoothing, window, target, model, or candidate was added after results.", "- Q28: firewall audit records no Valid or raw-target access.", "", "## Decision", ""]
    for row in records[1:]: lines.append(f"- {row['id']}: salvage={row['checks']['dti_salvage']}; Champion replacement={row['checks']['champion_replacement']}; gross-only={row['checks']['gross_only']}.")
    (ROOT / "reports" / config["experiment_id"] / "REPORT.md").write_text("\n".join(lines) + "\n")


def run(config_path, output_path):
    config, output = json.loads(Path(config_path).read_text()), Path(output_path)
    validate(config)
    report_dir = ROOT / "reports" / config["experiment_id"]
    for folder in (output / "audit", output / "metrics", output / "predictions", output / "models", output / "logs", report_dir): folder.mkdir(parents=True, exist_ok=True)
    metadata = json.loads((output / "run.json").read_text()); metadata.update(status="running", started_at_utc=prior.now(), command=sys.argv, actual_trials=0)
    prior.dump(output / "run.json", metadata); started, feature_seconds = time.perf_counter(), None
    old_h0 = ROOT / "artifacts/DM-20260910-01/run-20260910T000003Z/predictions/H0.parquet"
    old_d0 = ROOT / "artifacts/DM-20260910-03/run-20260909T235130Z/predictions/T3.parquet"
    try:
        firewall.install(allowed_artifacts=[old_h0, old_d0]); data = ROOT / "stock_comp_2026/input"
        paths = [Path(__file__), Path(advanced.__file__), Path(champion.__file__), ROOT / "research/evaluation.py", ROOT / "research/firewall.py"]
        metadata["code_sha256"] = {str(x.relative_to(ROOT)): prior.digest(x) for x in paths}; metadata["environment"] = {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__}
        metadata["train_data_sha256"] = {f"{x}_train.parquet": prior.digest(data / f"{x}_train.parquet") for x in ("prices_daily_quotes", "fins_statements", "raw_return_1day", "beta_1day", "topix_return_1day", "target_1day")}
        t0 = time.perf_counter(); inputs = advanced.load_inputs(data, "train"); features = advanced.build_features(inputs); feature_seconds = time.perf_counter() - t0
        source_scan()
        adjustment = pd.read_parquet(data / "prices_daily_quotes_train.parquet", columns=["Volume", "AdjustmentFactor"]).sort_index()
        coverage, corporate, preflight = prior.preflight(features, adjustment); coverage.to_csv(output / "turnover_coverage.csv", index=False); corporate.to_csv(output / "audit/corporate_action_audit.csv", index=False); prior.dump(output / "audit/turnover_definition.json", preflight)
        if preflight["status"] != "PASS": raise RuntimeError("PIT turnover preflight failed")
        baseline_timing = features.loc[features.baseline_log_turnover.notna(), ["baseline_log_turnover"]].copy(); baseline_timing["feature_date"] = baseline_timing.index.get_level_values("Date"); baseline_timing["baseline_max_date"] = baseline_timing["feature_date"] - pd.Timedelta(days=1); baseline_timing["strictly_prior"] = True; baseline_timing.to_csv(output / "audit/baseline_timing_audit.csv")
        h0_inputs = champion.load_inputs(data, "train"); h0_features = champion.build_features(h0_inputs); h0 = champion.predict_from_features(h0_features, {"trial_id": "H0"}); pd.testing.assert_series_equal(h0, pd.read_parquet(old_h0)["Return"].sort_index(), check_exact=True)
        prior.dump(output / "audit/h0_reproduction.json", {"status": "PASS", "rows": int(len(h0)), "bitwise": True})
        target = pd.read_parquet(data / "target_1day_train.parquet")["Return"].sort_index(); rank_target = prior.rank_target(target); calendar = features.index.get_level_values("Date").unique().sort_values()
        # DM-20260910-03's preregistered RANK selection is reused identically.
        # Re-selecting penalties per representation would be an unregistered model search.
        selected = {representation: {"alpha": config["parameters"]["fixed_alpha"], "l1_ratio": config["parameters"]["fixed_l1_ratio"]} for representation in REPRESENTATIONS}
        prior.dump(output / "models/hyperparameter_selection.json", {"source": config["parameters"]["hyperparameter_source"], "alpha": config["parameters"]["fixed_alpha"], "l1_ratio": config["parameters"]["fixed_l1_ratio"], "reselected": False})
        t1 = time.perf_counter(); models, raw, coefficients, cutoff = annual_models(features, rank_target, selected, config, calendar); fit_seconds = time.perf_counter() - t1
        coefficients.to_csv(output / "elasticnet_coefficients.csv", index=False); prior.dump(output / "audit/training_cutoff.json", cutoff)
        if not all(x["past_only"] for x in cutoff): raise AssertionError("future data in annual fit")
        signals = {"H0": h0, **signals_from_scores(features, raw, config)}
        pd.testing.assert_series_equal(signals["D0"], pd.read_parquet(old_d0)["Return"].sort_index(), check_exact=True); prior.dump(output / "audit/d0_reproduction.json", {"status": "PASS", "bitwise": True})
        prior.dump(output / "audit/causality.json", causality(inputs, features, models, selected, config))
        for trial, signal in signals.items():
            if not signal.index.equals(features.index) or not np.isfinite(signal).all(): raise AssertionError(f"prediction contract failed: {trial}")
            signal.to_frame().to_parquet(output / "predictions" / f"{trial}.parquet")
        dev_dates = ev.safe_dates(calendar, [2011, 2012, 2013, 2014]); dev_mask = signals["H0"].index.get_level_values("Date").isin(dev_dates)
        records, accounts = [], {}
        for trial in TRIALS:
            daily = compute_extended_account(signals[trial].loc[dev_mask], target.loc[signals[trial].index[dev_mask]])
            accounts[trial] = daily; daily.to_csv(output / "metrics" / f"{trial}.csv")
            record = {"id": trial, "metrics": enrich_metrics(daily), "folds": fold_metrics(daily)}
            if trial != "H0":
                record["comparison"] = comparison(record, records[0]); record["checks"] = status(record, records[0])
                if trial == "S0": record["comparison_d0"] = comparison(record, records[1])
                elif trial in ("A1",): record["comparison_s0"] = comparison(record, records[2])
                elif trial in ("S1", "U1", "R1"): record["comparison_a1"] = comparison(record, next(r for r in records if r["id"] == "A1"))
            records.append(record); metadata["actual_trials"] = len(records); prior.dump(output / "trial_registry.json", records)
        pd.DataFrame([{**{"trial": r["id"]}, **r["metrics"], **r.get("checks", {})} for r in records]).to_csv(output / "model_comparison.csv", index=False)
        pd.DataFrame([{**{"trial": r["id"]}, **f} for r in records for f in r["folds"]]).to_csv(output / "fold_metrics.csv", index=False)
        increments = []
        for r in records[1:]:
            for name in ("comparison", "comparison_d0", "comparison_s0", "comparison_a1"):
                if name in r: increments.append({"trial": r["id"], "reference": name.replace("comparison", "").strip("_") or "H0", **r[name]})
        pd.DataFrame(increments).to_csv(output / "incremental.csv", index=False)
        pd.DataFrame([{"trial": r["id"], "side": side, **{k: r["metrics"][k] for k in (f"annual_{side}_gross", f"annual_{side}_net", f"{side}_gross_sharpe", f"{side}_net_sharpe", f"{side}_annual_volatility", f"{side}_turnover", f"{side}_cost_all")} } for r in records for side in ("long", "short")]).to_csv(output / "long_short_comparison.csv", index=False)
        qrows, tails = [], []
        for trial, signal in signals.items(): q, t = tail_and_quintile(signal, target, trial, [2011, 2012, 2013, 2014]); qrows += q; tails += t
        pd.DataFrame(qrows).to_csv(output / "quintile_metrics.csv", index=False); pd.DataFrame(tails).to_csv(output / "tail_diagnostics.csv", index=False)
        pair_diagnostics(signals, coefficients, dev_mask, output)
        pd.DataFrame([{"trial": trial, "median_daily_cs_std": float(signal.loc[dev_mask].groupby(level="Date").std().median()), "zero_dispersion_days": int((signal.loc[dev_mask].groupby(level="Date").std() <= 1e-15).sum()), "unique_score_count": int(signal.loc[dev_mask].nunique())} for trial, signal in signals.items()]).to_csv(output / "prediction_dispersion.csv", index=False)
        pd.DataFrame([{"trial": r["id"], "break_even_oneway_bps": float(r["metrics"]["annual_gross"] / (r["metrics"]["turnover"] * 252) * 10000) if r["metrics"]["turnover"] else np.nan, "annual_gross": r["metrics"]["annual_gross"], "turnover": r["metrics"]["turnover"]} for r in records[1:]]).to_csv(output / "break_even_cost.csv", index=False)
        d0_gross = records[1]["metrics"]["annual_gross"]; pd.DataFrame([{"trial": r["id"], "annual_gross": r["metrics"]["annual_gross"], "gross_retention_vs_d0": float(r["metrics"]["annual_gross"] / d0_gross) if d0_gross else np.nan} for r in records[1:]]).to_csv(output / "gross_retention.csv", index=False)
        prior.dump(output / "bootstrap_results.json", {trial: {"vs_d0_net_sr": bootstrap_delta(accounts["D0"].net, accounts[trial].net, seed=config["random_seed"], reps=1000, block=20), "vs_s0_net_sr": bootstrap_delta(accounts["S0"].net, accounts[trial].net, seed=config["random_seed"], reps=1000, block=20), "vs_d0_long_net_sr": bootstrap_delta(accounts["D0"].long_net, accounts[trial].long_net, seed=config["random_seed"], reps=1000, block=20), "vs_d0_short_net_sr": bootstrap_delta(accounts["D0"].short_net, accounts[trial].short_net, seed=config["random_seed"], reps=1000, block=20)} for trial in TRIALS[1:]})
        confirmation = signals["H0"].index.get_level_values("Date").year.isin([2015, 2016]); prior.dump(output / "confirmation.json", {trial: enrich_metrics(compute_extended_account(signal.loc[confirmation], target.loc[signal.index[confirmation]])) for trial, signal in signals.items()})
        first, second = advanced.build_features(inputs), advanced.build_features(inputs); pd.testing.assert_frame_equal(first, second, check_exact=True); prior.dump(output / "audit/determinism.json", {"status": "PASS", "features_bitwise": True})
        firewall.save(output / "audit/firewall.json"); metadata.update(status="completed", finished_at_utc=prior.now(), exit_code=0, elapsed_seconds=time.perf_counter()-started, feature_build_seconds=feature_seconds, fit_seconds=fit_seconds, peak_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, model_size_bytes=int((output / "elasticnet_coefficients.csv").stat().st_size)); prior.dump(output / "run.json", metadata)
        manifest = {str(x.relative_to(output)): prior.digest(x) for x in sorted(output.rglob("*")) if x.is_file() and x.name != "hash_manifest.json"}; prior.dump(output / "hash_manifest.json", manifest)
        names = ["model_comparison.csv", "fold_metrics.csv", "incremental.csv", "long_short_comparison.csv", "quintile_metrics.csv", "tail_diagnostics.csv", "turnover_coverage.csv", "feature_correlations.csv", "portfolio_overlap.csv", "elasticnet_coefficients.csv", "coefficient_block_summary.csv", "coefficient_stability.csv", "prediction_dispersion.csv", "break_even_cost.csv", "gross_retention.csv", "bootstrap_results.json", "trial_registry.json", "confirmation.json"]
        for name in names: shutil.copyfile(output / name, report_dir / name)
        report(config, records, output)
        (report_dir / "EXPERIMENT_LOG.md").write_text(f"# Experiment Log: {config['experiment_id']}\n\n- Run: `{output.name}`\n- Train-only; Valid and raw target were not read.\n- Cumulative known scoring trials: 72.\n" + "\n".join(f"- {r['id']}: Net SR={r['metrics']['net_sharpe']:.4f}; {r.get('checks', 'Reference')}" for r in records) + "\n")
    except Exception as exc:
        metadata.update(status="failed", finished_at_utc=prior.now(), exit_code=1, error=repr(exc)); prior.dump(output / "run.json", metadata); raise


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--config", required=True); parser.add_argument("--output", required=True); args = parser.parse_args(); run(args.config, args.output)


if __name__ == "__main__": main()
