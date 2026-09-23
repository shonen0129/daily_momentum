"""Train-only, preregistered DRI Long/Short evaluation for DM-20260910-02."""
import argparse
import ast
import hashlib
import json
import platform
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from research import firewall
from research.evaluation import bootstrap_delta, weights
from research.experiments import asymmetric_evaluation as ev
from research.experiments.fixed_long_short import compute_extended_account
from stock_comp_2026.strategies.dm_dri_long_short import features as dri
from stock_comp_2026.strategies.dm_independent_short import features as champion


ROOT = Path(__file__).resolve().parents[2]
MODEL_YEARS = range(2011, 2017)


def now():
    return datetime.now(timezone.utc).isoformat()


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def dump(path, value):
    Path(path).write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, default=str) + "\n")


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate(config):
    assert config["data_split"] == "train" and config["valid_evaluation"] is False
    assert [x["trial_id"] for x in config["trials"]] == ["H0", "D1", "D2", "D3"]
    assert config["max_trials"] == 4 and config["feature_definitions"]["window"] == 21
    assert [x["year"] for x in config["walk_forward_folds"]] == [2011, 2012, 2013, 2014]
    assert config["purge_trading_days"] == 2 and config["parameters"]["ewma_alpha"] == .25
    assert config["transaction_cost_oneway"] == .001 and config["annualization"] == 252


def source_scan():
    forbidden = ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose", "AdjustmentVolume",
                 "raw_target", "target_1day_valid"]
    paths = sorted(Path(dri.__file__).parent.glob("*.py"))
    for path in paths:
        text = path.read_text()
        for token in forbidden:
            if token in text:
                raise AssertionError(f"forbidden {token} in {path}")
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("bfill", "backfill"):
                    raise AssertionError(f"backfill in {path}")
                if any(k.arg == "center" and isinstance(k.value, ast.Constant) and k.value.value for k in node.keywords):
                    raise AssertionError(f"center rolling in {path}")
                if any(k.arg == "direction" and isinstance(k.value, ast.Constant) and k.value.value == "forward" for k in node.keywords):
                    raise AssertionError(f"forward join in {path}")
    return [str(path.relative_to(ROOT)) for path in paths]


def mutate(inputs, cutoff, truncate):
    result = {}
    for name, frame in inputs.items():
        dates = frame.index.get_level_values("Date")
        if dates.tz is not None:
            dates = dates.tz_localize(None)
        future = dates > cutoff
        if truncate:
            result[name] = frame.loc[~future].copy()
            continue
        changed = frame.copy()
        for column in changed:
            changed.loc[future, column] = changed.loc[future, column] * -13.0 + 999.0
        result[name] = changed
    return result


def available_until(index, cutoff, calendar):
    """Rows with labels realized two exchange dates before the date cutoff."""
    calendar = pd.DatetimeIndex(calendar).sort_values().unique()
    end_position = calendar.searchsorted(pd.Timestamp(cutoff), side="right") - 1
    if end_position < 2:
        return np.zeros(len(index), dtype=bool)
    latest = calendar[end_position - 2]
    return index.get_level_values("Date") <= latest


def fit_model(x, y, alpha, params):
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("elasticnet", ElasticNet(alpha=alpha, l1_ratio=params["l1_ratio"], max_iter=params["elasticnet_max_iter"],
                                    selection="cyclic", fit_intercept=True)),
    ])
    model.fit(x, y)
    return model


def select_alpha(features, target, variant, config, calendar):
    params, columns = config["parameters"], dri.feature_columns(variant)
    eligible = features[f"{variant}_available"].to_numpy() & target.reindex(features.index).notna().to_numpy()
    dates = features.index.get_level_values("Date")
    records = []
    for alpha in params["alpha_grid"]:
        errors = []
        for fold in params["initial_cv"]:
            train = available_until(features.index, fold["train_end"], calendar) & eligible
            validation = ((dates >= pd.Timestamp(fold["validation_start"])) &
                          available_until(features.index, fold["validation_end"], calendar) & eligible)
            model = fit_model(features.loc[train, columns], target.loc[features.index[train]], alpha, params)
            predicted = model.predict(features.loc[validation, columns])
            actual = target.loc[features.index[validation]].to_numpy()
            errors.append((float(np.mean((predicted - actual) ** 2)), int(validation.sum())))
        mse = float(np.average([x[0] for x in errors], weights=[x[1] for x in errors]))
        records.append({"variant": variant, "alpha": float(alpha), "pooled_mse": mse,
                        "fold_mse": [x[0] for x in errors], "validation_rows": [x[1] for x in errors]})
    winner = min(records, key=lambda row: (row["pooled_mse"], row["alpha"]))
    return winner["alpha"], records


def extract_model(model, variant, year, columns, train_rows, max_fit_date):
    scaler, elastic = model.named_steps["scaler"], model.named_steps["elasticnet"]
    return [{"variant": variant, "model_year": int(year), "feature": feature, "coefficient": float(coef),
             "scaler_mean": float(mean), "scaler_scale": float(scale), "intercept": float(elastic.intercept_),
             "alpha": float(elastic.alpha), "l1_ratio": float(elastic.l1_ratio), "train_rows": int(train_rows),
             "max_fit_date": str(pd.Timestamp(max_fit_date).date())}
            for feature, coef, mean, scale in zip(columns, elastic.coef_, scaler.mean_, scaler.scale_)]


def annual_models(features, target, chosen, config, calendar):
    models, scores, coefficients, cutoff_audit = {}, {}, [], []
    dates = features.index.get_level_values("Date")
    for variant in ("raw", "res"):
        columns = dri.feature_columns(variant)
        available = features[f"{variant}_available"].to_numpy()
        scores[variant] = pd.Series(0.0, index=features.index, name="Return")
        for year in MODEL_YEARS:
            cutoff = pd.Timestamp(year=year - 1, month=12, day=31)
            train = available_until(features.index, cutoff, calendar) & available & target.reindex(features.index).notna().to_numpy()
            model = fit_model(features.loc[train, columns], target.loc[features.index[train]], chosen[variant], config["parameters"])
            predict = (dates.year == year) & available
            scores[variant].loc[predict] = model.predict(features.loc[predict, columns])
            models[(variant, year)] = model
            max_fit = features.index.get_level_values("Date")[train].max()
            coefficients.extend(extract_model(model, variant, year, columns, train.sum(), max_fit))
            cutoff_audit.append({"variant": variant, "model_year": year, "fit_cutoff": str(cutoff.date()),
                                 "max_feature_label_date": str(max_fit.date()), "train_rows": int(train.sum()),
                                 "prediction_rows": int(predict.sum()), "past_only": bool(max_fit < pd.Timestamp(year=year, month=1, day=1))})
    return models, scores, pd.DataFrame(coefficients), cutoff_audit


def predict_with_models(features, models, config):
    dates = features.index.get_level_values("Date")
    outputs = {}
    for variant in ("raw", "res"):
        raw = pd.Series(0.0, index=features.index, name="Return")
        available = features[f"{variant}_available"].to_numpy()
        columns = dri.feature_columns(variant)
        for year in MODEL_YEARS:
            take = (dates.year == year) & available
            if take.any():
                raw.loc[take] = models[(variant, year)].predict(features.loc[take, columns])
        outputs[variant] = raw
    return {
        "D1": outputs["raw"].rename("Return"),
        "D2": dri.smooth_complete(outputs["raw"], features.raw_available, config["parameters"]["ewma_alpha"]),
        "D3": dri.smooth_complete(outputs["res"], features.res_available, config["parameters"]["ewma_alpha"]),
    }


def causality(inputs, features, models, config):
    records = []
    for label in ("2010-12-30", "2012-06-29", "2014-12-30"):
        cutoff = pd.Timestamp(label)
        before = features.loc[features.index.get_level_values("Date") <= cutoff]
        original = predict_with_models(features, models, config)
        for mode in ("mutation", "truncation"):
            changed = dri.build_features(mutate(inputs, cutoff, truncate=(mode == "truncation")))
            pd.testing.assert_frame_equal(before, changed.loc[before.index], check_exact=True)
            scores = predict_with_models(changed, models, config)
            for trial in ("D1", "D2", "D3"):
                pd.testing.assert_series_equal(original[trial].loc[before.index], scores[trial].loc[before.index], check_exact=True)
        records.append({"cutoff": label, "rows": int(len(before)), "features": int(before.shape[1]), "bitwise": True})
    return {"status": "PASS", "source_files": source_scan(), "prefix_tests": records}


def enrich_metrics(daily):
    value = ev.extended_metrics(daily)
    for side in ("long", "short"):
        value[f"{side}_annual_volatility"] = float(daily[f"{side}_net"].std(ddof=1) * np.sqrt(252))
        value[f"{side}_positive_day_ratio"] = float((daily[f"{side}_net"] > 0).mean())
    return value


def fold_metrics(daily):
    return [dict(year=int(year), **enrich_metrics(rows)) for year, rows in daily.groupby(daily.index.year)]


def comparison(record, baseline):
    current, reference = pd.DataFrame(record["folds"]).set_index("year"), pd.DataFrame(baseline["folds"]).set_index("year")
    delta = current - reference
    return {"delta_net_sr": float(record["metrics"]["net_sharpe"] - baseline["metrics"]["net_sharpe"]),
            "delta_gross_sr": float(record["metrics"]["gross_sharpe"] - baseline["metrics"]["gross_sharpe"]),
            "delta_turnover": float(record["metrics"]["turnover"] - baseline["metrics"]["turnover"]),
            "delta_cost": float(record["metrics"]["annual_cost"] - baseline["metrics"]["annual_cost"]),
            "delta_long_net": float(record["metrics"]["annual_long_net"] - baseline["metrics"]["annual_long_net"]),
            "delta_short_net": float(record["metrics"]["annual_short_net"] - baseline["metrics"]["annual_short_net"]),
            "net_improved_folds": int((delta.net_sharpe > 0).sum()),
            "long_improved_folds": int((delta.annual_long_net > 0).sum()),
            "short_improved_folds": int((delta.annual_short_net > 0).sum()),
            "long_positive_folds": int((current.annual_long_net > 0).sum()),
            "short_positive_folds": int((current.annual_short_net > 0).sum()),
            "median_delta_long_net": float(delta.annual_long_net.median()),
            "median_delta_short_net": float(delta.annual_short_net.median()),
            "fold_deltas": delta.reset_index().to_dict("records")}


def classify(record, base):
    comp, metric, h0 = record["comparison"], record["metrics"], base["metrics"]
    long_ok = (metric["annual_long_net"] > h0["annual_long_net"] and metric["long_net_sharpe"] > h0["long_net_sharpe"] and comp["long_improved_folds"] >= 3)
    short_ok = (metric["annual_short_net"] > h0["annual_short_net"] and comp["short_improved_folds"] >= 3 and comp["median_delta_short_net"] > 0)
    total_ok = metric["net_sharpe"] > h0["net_sharpe"] and comp["net_improved_folds"] >= 3
    label = "Full DRI Success" if long_ok and short_ok and total_ok else ("Long-only Success" if long_ok else ("Short-only Success" if short_ok else "Neither"))
    return label, {"total_replacement": total_ok, "long_replacement": long_ok, "short_replacement": short_ok}


def tail_and_quintile(signal, target, trial, years):
    rows, tails = [], []
    selected = signal.index.get_level_values("Date").year.isin(years)
    score, target = signal.loc[selected], target.reindex(signal.index[selected])
    _, quantile = weights(score)
    rank = score.groupby(level="Date").rank(method="first", pct=True)
    for year, mask in pd.Series(selected, index=signal.index).groupby(signal.index.get_level_values("Date").year):
        if year not in years:
            continue
        year_index = mask.index
        for bucket in range(5):
            daily = target.loc[year_index].where(quantile.loc[year_index] == bucket).groupby(level="Date").mean()
            rows.append({"trial": trial, "year": int(year), "bucket": f"Q{bucket + 1}", "daily_return": float(daily.mean()), "days": int(daily.notna().sum())})
        for name, test in (("bottom_decile", rank.loc[year_index] <= .1), ("top_decile", rank.loc[year_index] > .9)):
            daily = target.loc[year_index].where(test).groupby(level="Date").mean()
            tails.append({"trial": trial, "year": int(year), "bucket": name, "daily_return": float(daily.mean()), "days": int(daily.notna().sum())})
    return rows, tails


def independence(signals, h0_features, h0_signal, years):
    rows, overlap = [], []
    m60, fd = h0_features.L, h0_features.fd_equal
    for trial in ("D1", "D2", "D3"):
        frame = pd.DataFrame({"dri": signals[trial], "m60": m60.reindex(signals[trial].index), "fd": fd.reindex(signals[trial].index)})
        frame = frame.loc[frame.index.get_level_values("Date").year.isin(years)]
        for date, block in frame.groupby(level="Date"):
            rows.append({"trial": trial, "Date": date, "dri_m60_spearman": block.dri.corr(block.m60, method="spearman"),
                         "dri_fd_spearman": block.dri.corr(block.fd, method="spearman")})
        _, q_dri = weights(signals[trial].loc[frame.index])
        _, q_m60 = weights(m60.loc[frame.index])
        _, q_fd = weights(h0_signal.loc[frame.index])
        overlap.append({"trial": trial, "dri_q5_m60_q5_overlap": float(((q_dri == 4) & (q_m60 == 4)).groupby(level="Date").mean().mean() / .2),
                        "dri_q1_fd_q1_overlap": float(((q_dri == 0) & (q_fd == 0)).groupby(level="Date").mean().mean() / .2)})
    data = pd.DataFrame(rows)
    return data.groupby("trial", as_index=False)[["dri_m60_spearman", "dri_fd_spearman"]].mean(), pd.DataFrame(overlap)


def coefficient_stability(coefficients):
    rows = []
    for variant, block in coefficients.groupby("variant"):
        matrix = block.pivot(index="model_year", columns="feature", values="coefficient")
        for year, value in matrix.iterrows():
            rows.append({"variant": variant, "model_year": int(year), "nonzero_count": int((value != 0).sum()),
                         "positive_count": int((value > 0).sum()), "negative_count": int((value < 0).sum())})
        for left in matrix.index:
            for right in matrix.index:
                if left < right:
                    rows.append({"variant": variant, "model_year": f"{left}-{right}", "pair_correlation": float(matrix.loc[left].corr(matrix.loc[right])),
                                 "sign_agreement": float((np.sign(matrix.loc[left]) == np.sign(matrix.loc[right])).mean())})
    return pd.DataFrame(rows)


def report(config, records, output, confirmation, alpha_rows):
    base = records[0]
    lines = [f"# {config['experiment_id']}: Daily Return Information Long / Short", "",
             f"Run: `{output.name}`。Train-only。Validおよびraw targetは未参照。原論文の月次予測を日次targetへ適応した有限比較であり、直接replicationではない。", "",
             "## Main result", "", "| Trial | Total Net SR | Long Ann Net | Long Net SR | Short Ann Net | Short Net SR | Turnover | Cost | MaxDD |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for record in records:
        m = record["metrics"]
        lines.append(f"| {record['id']} | {m['net_sharpe']:.4f} | {m['annual_long_net']:.2%} | {m['long_net_sharpe']:.4f} | {m['annual_short_net']:.2%} | {m['short_net_sharpe']:.4f} | {m['turnover']:.4f} | {m['annual_cost']:.2%} | {m['max_drawdown_additive']:.2%} |")
    lines += ["", "## Decisions", "", "| Trial | Classification | Total replacement | Long replacement | Short replacement | Net-SR improved folds | Long improved folds | Short improved folds |",
              "|---|---|:---:|:---:|:---:|---:|---:|---:|"]
    for record in records[1:]:
        c, q = record["comparison"], record["checks"]
        lines.append(f"| {record['id']} | {record['decision']} | {'PASS' if q['total_replacement'] else 'FAIL'} | {'PASS' if q['long_replacement'] else 'FAIL'} | {'PASS' if q['short_replacement'] else 'FAIL'} | {c['net_improved_folds']}/4 | {c['long_improved_folds']}/4 | {c['short_improved_folds']}/4 |")
    lines += ["", "## Required answers", ""]
    best = max(records[1:], key=lambda row: row["metrics"]["net_sharpe"])
    for record in records[1:]:
        m, c = record["metrics"], record["comparison"]
        lines.append(f"- {record['id']}: Total Net SR {'exceeded' if m['net_sharpe'] > base['metrics']['net_sharpe'] else 'did not exceed'} H0 ({m['net_sharpe']:.4f} vs {base['metrics']['net_sharpe']:.4f}); Long annual Net/SR={m['annual_long_net']:.2%}/{m['long_net_sharpe']:.4f}, ΔLong Net={c['delta_long_net']:.2%}; Short annual Net/SR={m['annual_short_net']:.2%}/{m['short_net_sharpe']:.4f}, ΔShort Net={c['delta_short_net']:.2%}.")
    lines += [f"- Q1–Q10: main table and fold-level `fold_metrics.csv` provide total, Long, Short, positive and Champion-improvement fold counts. Best total DRI trial is {best['id']} ({best['decision']}).",
              "- Q11–Q13: `turnover_cost_decomposition.csv` reports D1→D2 smoothing and D2→D3 residualization; no additional window, alpha, transform, model, or hybrid was scored.",
              "- Q14–Q16: `dri_correlations.csv`, `dri_overlap.csv`, `elasticnet_coefficients.csv`, `coefficient_stability.csv`, `quintile_metrics.csv`, and `tail_diagnostics.csv` contain the predeclared independence, coefficient, and monotonicity diagnostics.",
              "- Q17: all annual fold metrics are retained; pooled performance was not used alone for selection.",
              "- Q18: runtime firewall and audit files record Train-only accesses; no Valid or raw target file was opened.", "",
              "## Elastic Net preregistration", "", "The original paper's annual expanding re-estimation was confirmed. Its exact penalty-selection procedure could not be safely reproduced from the accessible source, so RAW and RES each selected one fixed alpha using only the preregistered 2008–2010 chronological validation blocks. The selected alpha was not changed after scoring.", "",
              "| Variant | alpha | pooled MSE |", "|---|---:|---:|"]
    for row in alpha_rows:
        if row["selected"]:
            lines.append(f"| {row['variant']} | {row['alpha']:.7g} | {row['pooled_mse']:.8g} |")
    lines += ["", "## Descriptive-only 2015–2016-03", "", "This previously explored Train period was run only after decision calculation and did not alter it.", "",
              "| Trial | Net SR | Long Ann Net | Short Ann Net | Turnover |", "|---|---:|---:|---:|---:|"]
    for trial, values in confirmation.items():
        lines.append(f"| {trial} | {values['net_sharpe']:.4f} | {values['annual_long_net']:.2%} | {values['annual_short_net']:.2%} | {values['turnover']:.4f} |")
    (ROOT / "reports" / config["experiment_id"] / "REPORT.md").write_text("\n".join(lines) + "\n")


def run(config_path, output):
    config, output = json.loads(Path(config_path).read_text()), Path(output)
    validate(config)
    report_dir = ROOT / "reports" / config["experiment_id"]
    for folder in (output / "audit", output / "metrics", output / "predictions", output / "models", output / "logs", report_dir):
        folder.mkdir(parents=True, exist_ok=True)
    metadata = json.loads((output / "run.json").read_text())
    metadata.update(status="running", started_at_utc=now(), command=sys.argv, actual_trials=0)
    dump(output / "run.json", metadata)
    started = time.perf_counter()
    old_h0 = ROOT / "artifacts/DM-20260910-01/run-20260910T000003Z/predictions/H0.parquet"
    try:
        firewall.install(allowed_artifacts=[old_h0])
        data = ROOT / "stock_comp_2026/input"
        paths = [Path(__file__), Path(dri.__file__), Path(champion.__file__), ROOT / "research/evaluation.py", ROOT / "research/firewall.py"]
        metadata["code_sha256"] = {str(path.relative_to(ROOT)): digest(path) for path in paths}
        metadata["environment"] = {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__}
        metadata["train_data_sha256"] = {f"{name}_train.parquet": digest(data / f"{name}_train.parquet") for name in ("raw_return_1day", "beta_1day", "topix_return_1day", "fins_statements", "listed_info", "prices_daily_quotes")}
        inputs = dri.load_inputs(data, "train")
        features = dri.build_features(inputs)
        dump(output / "audit/feature_coverage.json", {variant: {"available_rate": float(features[f"{variant}_available"].mean()), "neutral_rate": float((~features[f"{variant}_available"]).mean())} for variant in ("raw", "res")})
        source_scan()
        h0_inputs = champion.load_inputs(data, "train")
        h0_features = champion.build_features(h0_inputs)
        h0_signal = champion.predict_from_features(h0_features, {"trial_id": "H0"})
        prior = pd.read_parquet(old_h0)["Return"].sort_index()
        pd.testing.assert_series_equal(h0_signal, prior, check_exact=True)
        dump(output / "audit/h0_reproduction.json", {"status": "PASS", "rows": int(len(h0_signal)), "bitwise": True})
        target = pd.read_parquet(data / "target_1day_train.parquet")["Return"].sort_index()
        metadata["train_data_sha256"]["target_1day_train.parquet"] = digest(data / "target_1day_train.parquet")
        calendar = features.index.get_level_values("Date").unique().sort_values()
        chosen, tuning = {}, []
        for variant in ("raw", "res"):
            chosen[variant], rows = select_alpha(features, target, variant, config, calendar)
            for row in rows:
                row["selected"] = row["alpha"] == chosen[variant]
            tuning.extend(rows)
        dump(output / "models/alpha_selection.json", tuning)
        models, _, coefficients, cutoff_audit = annual_models(features, target, chosen, config, calendar)
        coefficients.to_csv(output / "elasticnet_coefficients.csv", index=False)
        dump(output / "audit/training_cutoff.json", cutoff_audit)
        if not all(row["past_only"] for row in cutoff_audit):
            raise AssertionError("annual fit included current-year data")
        dump(output / "audit/causality.json", causality(inputs, features, models, config))
        signals = {"H0": h0_signal, **predict_with_models(features, models, config)}
        for trial, signal in signals.items():
            if not signal.index.equals(features.index) or not np.isfinite(signal).all():
                raise AssertionError(f"prediction contract failed: {trial}")
            signal.to_frame().to_parquet(output / "predictions" / f"{trial}.parquet")
        dev_dates = ev.safe_dates(calendar, [2011, 2012, 2013, 2014])
        dev_mask = signals["H0"].index.get_level_values("Date").isin(dev_dates)
        records, accounts = [], {}
        for trial in ("H0", "D1", "D2", "D3"):
            signal = signals[trial].loc[dev_mask]
            daily = compute_extended_account(signal, target.loc[signal.index])
            np.testing.assert_allclose(daily.long_cost_all + daily.short_cost_all, daily.cost_all, atol=1e-15, rtol=0)
            np.testing.assert_allclose(daily.long_net + daily.short_net, daily.net, atol=1e-15, rtol=0)
            accounts[trial] = daily
            daily.to_csv(output / "metrics" / f"{trial}.csv")
            record = {"id": trial, "metrics": enrich_metrics(daily), "folds": fold_metrics(daily)}
            if trial != "H0":
                record["comparison"] = comparison(record, records[0])
                record["decision"], record["checks"] = classify(record, records[0])
            records.append(record)
            metadata["actual_trials"] = len(records)
            dump(output / "trial_registry.json", records)
        bootstrap = {trial: {"delta_total_net_sr": bootstrap_delta(accounts["H0"].net, accounts[trial].net, seed=config["random_seed"], reps=1000, block=20),
                              "delta_long_net_sr": bootstrap_delta(accounts["H0"].long_net, accounts[trial].long_net, seed=config["random_seed"], reps=1000, block=20),
                              "delta_short_net_sr": bootstrap_delta(accounts["H0"].short_net, accounts[trial].short_net, seed=config["random_seed"], reps=1000, block=20)} for trial in ("D1", "D2", "D3")}
        dump(output / "bootstrap_results.json", bootstrap)
        pd.DataFrame([{**{"trial": r["id"]}, **r["metrics"], "decision": r.get("decision", "Reference")} for r in records]).to_csv(output / "model_comparison.csv", index=False)
        pd.DataFrame([{**{"trial": r["id"]}, **f} for r in records for f in r["folds"]]).to_csv(output / "fold_metrics.csv", index=False)
        pd.DataFrame([{**{"trial": r["id"]}, **f} for r in records[1:] for f in r["comparison"]["fold_deltas"]]).to_csv(output / "incremental.csv", index=False)
        long_short = []
        for r in records:
            for side in ("long", "short"):
                m = r["metrics"]
                long_short.append({"trial": r["id"], "side": side, "annual_gross": m[f"annual_{side}_gross"], "annual_net": m[f"annual_{side}_net"], "gross_sharpe": m[f"{side}_gross_sharpe"], "net_sharpe": m[f"{side}_net_sharpe"], "annual_volatility": m[f"{side}_annual_volatility"], "turnover": m[f"{side}_turnover"], "annual_cost": m[f"{side}_cost_all"], "max_drawdown": float(np.min(np.r_[0., accounts[r['id']][f'{side}_net'].cumsum()] - np.maximum.accumulate(np.r_[0., accounts[r['id']][f'{side}_net'].cumsum()]))), "positive_day_ratio": m[f"{side}_positive_day_ratio"]})
        pd.DataFrame(long_short).to_csv(output / "long_short_comparison.csv", index=False)
        qrows, trows = [], []
        for trial, signal in signals.items():
            a, b = tail_and_quintile(signal, target, trial, [2011, 2012, 2013, 2014]); qrows.extend(a); trows.extend(b)
        pd.DataFrame(qrows).to_csv(output / "quintile_metrics.csv", index=False)
        pd.DataFrame(trows).to_csv(output / "tail_diagnostics.csv", index=False)
        corr, overlap = independence(signals, h0_features, h0_signal, [2011, 2012, 2013, 2014])
        corr.to_csv(output / "dri_correlations.csv", index=False); overlap.to_csv(output / "dri_overlap.csv", index=False)
        coefficient_stability(coefficients).to_csv(output / "coefficient_stability.csv", index=False)
        decomposition = []
        for left, right, label in (("D1", "D2", "D1_to_D2_smoothing"), ("D2", "D3", "D2_to_D3_residual")):
            a, b = records[[r["id"] for r in records].index(left)]["metrics"], records[[r["id"] for r in records].index(right)]["metrics"]
            decomposition.append({"comparison": label, "delta_gross_sr": b["gross_sharpe"] - a["gross_sharpe"], "delta_net_sr": b["net_sharpe"] - a["net_sharpe"], "delta_turnover": b["turnover"] - a["turnover"], "delta_cost": b["annual_cost"] - a["annual_cost"], "delta_long_net_sr": b["long_net_sharpe"] - a["long_net_sharpe"], "delta_short_net_sr": b["short_net_sharpe"] - a["short_net_sharpe"]})
        pd.DataFrame(decomposition).to_csv(output / "turnover_cost_decomposition.csv", index=False)
        confirmation = {}
        confirm_dates = ev.safe_dates(calendar, [2015, 2016])
        confirm_mask = signals["H0"].index.get_level_values("Date").isin(confirm_dates)
        for trial, signal in signals.items():
            confirmation[trial] = enrich_metrics(compute_extended_account(signal.loc[confirm_mask], target.loc[signal.index[confirm_mask]]))
        dump(output / "confirmation.json", confirmation)
        firewall.save(output / "audit/firewall.json")
        metadata.update(status="completed", finished_at_utc=now(), exit_code=0, elapsed_seconds=time.perf_counter() - started,
                        model_size_bytes=int((output / "elasticnet_coefficients.csv").stat().st_size))
        dump(output / "run.json", metadata)
        manifest = {str(path.relative_to(output)): digest(path) for path in sorted(output.rglob("*")) if path.is_file() and path.name != "hash_manifest.json"}
        dump(output / "hash_manifest.json", manifest)
        names = ["model_comparison.csv", "fold_metrics.csv", "incremental.csv", "long_short_comparison.csv", "quintile_metrics.csv", "tail_diagnostics.csv", "dri_correlations.csv", "dri_overlap.csv", "elasticnet_coefficients.csv", "coefficient_stability.csv", "turnover_cost_decomposition.csv", "bootstrap_results.json", "trial_registry.json", "confirmation.json"]
        for name in names:
            shutil.copyfile(output / name, report_dir / name)
        report(config, records, output, confirmation, tuning)
        (report_dir / "EXPERIMENT_LOG.md").write_text("\n".join([f"# Experiment Log: {config['experiment_id']}", "", f"- Run: `{output.name}`", "- Train-only; no Valid or raw target access.", "- Cumulative known scoring trials: 60.", *[f"- {r['id']}: Net SR={r['metrics']['net_sharpe']:.4f}; {r.get('decision', 'Reference')}" for r in records]]) + "\n")
    except Exception as exc:
        metadata.update(status="failed", finished_at_utc=now(), exit_code=1, error=repr(exc))
        dump(output / "run.json", metadata)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.config, args.output)


if __name__ == "__main__":
    main()
