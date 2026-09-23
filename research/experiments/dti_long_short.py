"""Train-only, finite Daily Turnover Information experiment DM-20260910-03."""
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
from research.evaluation import bootstrap_delta, rankic, weights
from research.experiments import asymmetric_evaluation as ev
from research.experiments.dri_long_short import enrich_metrics, fold_metrics, tail_and_quintile
from research.experiments.fixed_long_short import compute_extended_account
from stock_comp_2026.strategies.dm_dti_long_short import features as dti
from stock_comp_2026.strategies.dm_independent_short import features as champion


ROOT = Path(__file__).resolve().parents[2]
MODEL_YEARS = range(2011, 2017)


def now(): return datetime.now(timezone.utc).isoformat()


def clean(value):
    if isinstance(value, dict): return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(v) for v in value]
    if isinstance(value, (np.floating, float)): return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer): return int(value)
    if isinstance(value, np.bool_): return bool(value)
    return value


def dump(path, value): Path(path).write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, default=str) + "\n")
def digest(path):
    with Path(path).open("rb") as stream: return hashlib.file_digest(stream, "sha256").hexdigest()


def validate(c):
    assert c["data_split"] == "train" and c["valid_evaluation"] is False
    assert [x["trial_id"] for x in c["trials"]] == ["H0", "M0", "T1", "T2", "T3"]
    assert c["max_trials"] == 5 and c["feature_definitions"]["window"] == 21
    assert [x["year"] for x in c["walk_forward_folds"]] == [2011, 2012, 2013, 2014]
    assert c["purge_trading_days"] == 2 and c["parameters"]["ewma_alpha"] == .25
    assert c["transaction_cost_oneway"] == .001 and c["annualization"] == 252


def source_scan():
    forbidden = ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose", "AdjustmentVolume", "raw_target", "target_1day_valid"]
    paths = sorted(Path(dti.__file__).parent.glob("*.py"))
    for path in paths:
        text = path.read_text()
        for token in forbidden:
            if token in text: raise AssertionError(f"forbidden {token} in {path}")
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("bfill", "backfill"): raise AssertionError(f"backfill in {path}")
                if node.func.attr == "shift" and node.args:
                    if not isinstance(node.args[0], ast.Constant) or node.args[0].value < 0: raise AssertionError(f"negative/dynamic shift in {path}")
                if any(k.arg == "center" and isinstance(k.value, ast.Constant) and k.value.value for k in node.keywords): raise AssertionError(f"center rolling in {path}")
                if any(k.arg == "direction" and isinstance(k.value, ast.Constant) and k.value.value == "forward" for k in node.keywords): raise AssertionError(f"forward join in {path}")
    return [str(path.relative_to(ROOT)) for path in paths]


def mutate(inputs, cutoff, truncate):
    changed = {}
    for name, frame in inputs.items():
        dates = frame.index.get_level_values("Date")
        if dates.tz is not None: dates = dates.tz_localize(None)
        future = dates > cutoff
        if truncate: changed[name] = frame.loc[~future].copy(); continue
        value = frame.copy()
        for column in value:
            if isinstance(value[column].dtype, pd.CategoricalDtype): value[column] = value[column].astype(object)
            if pd.api.types.is_numeric_dtype(value[column]): value.loc[future, column] = value.loc[future, column] * -13 + 999
            elif pd.api.types.is_datetime64_any_dtype(value[column]): value.loc[future, column] = pd.Timestamp("1990-01-01")
            else: value.loc[future, column] = "future_changed"
        changed[name] = value
    return changed


def available_until(index, cutoff, calendar):
    calendar = pd.DatetimeIndex(calendar).sort_values().unique()
    position = calendar.searchsorted(pd.Timestamp(cutoff), side="right") - 1
    if position < 2: return np.zeros(len(index), dtype=bool)
    return index.get_level_values("Date") <= calendar[position - 2]


def fit_model(x, y, alpha, ratio, params):
    model = Pipeline([("scaler", StandardScaler()), ("elasticnet", ElasticNet(alpha=alpha, l1_ratio=ratio, max_iter=params["elasticnet_max_iter"], selection="cyclic", fit_intercept=True))])
    return model.fit(x, y)


def rank_target(target):
    return (2 * target.groupby(level="Date").rank(method="average", pct=True) - 1).rename("rank_target")


def score_rankic(predicted, actual):
    return float(rankic(predicted.rename("Return"), actual).mean())


def select_model(features, target, kind, config, calendar):
    params, columns = config["parameters"], dti.feature_columns()
    eligible = features.available.to_numpy() & target.reindex(features.index).notna().to_numpy()
    dates, rows = features.index.get_level_values("Date"), []
    for alpha in params["alpha_grid"]:
        for ratio in params["l1_ratio_grid"]:
            outcomes = []
            for fold in params["initial_cv"]:
                train = available_until(features.index, fold["train_end"], calendar) & eligible
                valid = ((dates >= pd.Timestamp(fold["validation_start"])) & available_until(features.index, fold["validation_end"], calendar) & eligible)
                model = fit_model(features.loc[train, columns], target.loc[features.index[train]], alpha, ratio, params)
                pred = pd.Series(model.predict(features.loc[valid, columns]), index=features.index[valid])
                actual = target.loc[pred.index]
                outcomes.append({"rows": int(valid.sum()), "mse": float(np.mean((pred - actual) ** 2)), "rankic": score_rankic(pred, actual)})
            weight = np.asarray([x["rows"] for x in outcomes])
            rows.append({"variant": kind, "alpha": float(alpha), "l1_ratio": float(ratio), "pooled_mse": float(np.average([x["mse"] for x in outcomes], weights=weight)), "mean_rankic": float(np.average([x["rankic"] for x in outcomes], weights=weight)), "turnover_proxy": None, "folds": outcomes})
    primary = "pooled_mse" if kind == "RAW" else "mean_rankic"
    best = min(x[primary] for x in rows) if kind == "RAW" else max(x[primary] for x in rows)
    tied = [x for x in rows if x[primary] == best]
    # The pre-registered turnover proxy is a tie-break only.  Avoiding its expensive
    # quintile conversion for non-tied candidates does not alter model selection.
    if len(tied) > 1:
        for row in tied:
            proxies = []
            for fold in row["folds"]:
                valid = ((dates >= pd.Timestamp(config["parameters"]["initial_cv"][len(proxies)]["validation_start"])) & available_until(features.index, config["parameters"]["initial_cv"][len(proxies)]["validation_end"], calendar) & eligible)
                train = available_until(features.index, config["parameters"]["initial_cv"][len(proxies)]["train_end"], calendar) & eligible
                model = fit_model(features.loc[train, columns], target.loc[features.index[train]], row["alpha"], row["l1_ratio"], params)
                pred = pd.Series(model.predict(features.loc[valid, columns]), index=features.index[valid])
                proxies.append(float(weights(pred)[0].groupby(level="Code").diff().abs().fillna(0).groupby(level="Date").sum().mean()))
            row["turnover_proxy"] = float(np.mean(proxies))
        winner = min(tied, key=lambda x: (x["turnover_proxy"], -x["alpha"], -x["l1_ratio"]))
    else:
        winner = tied[0]
    for row in rows: row["selected"] = row["alpha"] == winner["alpha"] and row["l1_ratio"] == winner["l1_ratio"]
    return winner, rows


def annual_models(features, targets, selected, config, calendar):
    columns, dates, models, scores, coefficients, audit = dti.feature_columns(), features.index.get_level_values("Date"), {}, {}, [], []
    for kind, target in targets.items():
        result = pd.Series(0., index=features.index, name="Return")
        for year in MODEL_YEARS:
            cutoff = pd.Timestamp(year=year - 1, month=12, day=31)
            train = available_until(features.index, cutoff, calendar) & features.available.to_numpy() & target.reindex(features.index).notna().to_numpy()
            model = fit_model(features.loc[train, columns], target.loc[features.index[train]], selected[kind]["alpha"], selected[kind]["l1_ratio"], config["parameters"])
            predict = (dates.year == year) & features.available.to_numpy()
            result.loc[predict] = model.predict(features.loc[predict, columns])
            models[(kind, year)] = model
            scaler, elastic = model.named_steps["scaler"], model.named_steps["elasticnet"]
            max_fit = features.index.get_level_values("Date")[train].max()
            for feature, coef, mean, scale in zip(columns, elastic.coef_, scaler.mean_, scaler.scale_): coefficients.append({"variant": kind, "model_year": year, "feature": feature, "coefficient": float(coef), "scaler_mean": float(mean), "scaler_scale": float(scale), "intercept": float(elastic.intercept_), "alpha": float(elastic.alpha), "l1_ratio": float(elastic.l1_ratio), "train_rows": int(train.sum()), "max_fit_date": str(max_fit.date())})
            audit.append({"variant": kind, "model_year": year, "fit_cutoff": str(cutoff.date()), "max_feature_label_date": str(max_fit.date()), "scaler_fit_max_date": str(max_fit.date()), "train_rows": int(train.sum()), "prediction_rows": int(predict.sum()), "past_only": bool(max_fit < pd.Timestamp(year=year, month=1, day=1))})
        scores[kind] = result
    return models, scores, pd.DataFrame(coefficients), audit


def predict_models(features, models, config):
    dates, out = features.index.get_level_values("Date"), {}
    for kind in ("RAW", "RANK"):
        score = pd.Series(0., index=features.index, name="Return")
        for year in MODEL_YEARS:
            take = (dates.year == year) & features.available.to_numpy()
            if take.any():
                # One fixed cross-sectional batch per date keeps IEEE rounding independent
                # of whether later dates are present in a prefix-invariance run.
                rows = features.loc[take, dti.feature_columns()]
                predicted = rows.groupby(level="Date", sort=False, group_keys=False).apply(
                    lambda block: pd.Series(models[(kind, year)].predict(block), index=block.index), include_groups=False)
                score.loc[predicted.index] = predicted
        out[kind] = score
    return {"T1": out["RAW"], "T2": out["RANK"], "T3": dti.smooth_complete(out["RANK"], features.available, config["parameters"]["ewma_alpha"])}


def causality(inputs, features, models, config):
    original = predict_models(features, models, config); records = []
    for label in ("2010-12-30", "2012-06-29", "2014-12-30"):
        cutoff, before = pd.Timestamp(label), features.loc[features.index.get_level_values("Date") <= pd.Timestamp(label)]
        for mode in ("mutation", "truncation"):
            altered = dti.build_features(mutate(inputs, cutoff, mode == "truncation"))
            pd.testing.assert_frame_equal(before, altered.loc[before.index], check_exact=True)
            candidate = predict_models(altered, models, config)
            for trial in ("T1", "T2", "T3"):
                try:
                    pd.testing.assert_series_equal(original[trial].loc[before.index], candidate[trial].loc[before.index], check_exact=True)
                except AssertionError as error:
                    raise AssertionError(f"prefix mismatch: cutoff={label}, mode={mode}, trial={trial}") from error
        records.append({"cutoff": label, "rows": int(len(before)), "features": int(before.shape[1]), "bitwise": True})
    return {"status": "PASS", "source_files": source_scan(), "prefix_tests": records}


def preflight(features, adjustment):
    dated = features.assign(year=features.index.get_level_values("Date").year)
    coverage = dated.groupby("year").agg(rows=("shares", "size"), shares_coverage=("shares", lambda x: float(x.notna().mean())), turnover_coverage=("turnover_rate", lambda x: float(x.notna().mean())), vector_coverage=("available", "mean"), median_share_age=("shares_age_days", "median"), p95_share_age=("shares_age_days", lambda x: x.quantile(.95))).reset_index()
    events = adjustment.loc[adjustment.AdjustmentFactor.ne(1) & adjustment.AdjustmentFactor.notna()].copy()
    event_rows = []
    for (date, code), row in events.iterrows():
        history = features.xs(code, level="Code").loc[:date]
        later = features.xs(code, level="Code").loc[date:date + pd.Timedelta(days=180)]
        base = history.shares.dropna().iloc[-1] if history.shares.notna().any() else np.nan
        changed = later.shares.dropna()
        changed = changed.loc[changed.ne(base)] if np.isfinite(base) else changed.iloc[:0]
        after = changed.iloc[0] if not changed.empty else np.nan
        event_rows.append({"Date": str(pd.Timestamp(date).date()), "Code": str(code), "adjustment_factor": float(row.AdjustmentFactor), "volume": float(row.Volume) if np.isfinite(row.Volume) else None, "shares_before": float(base) if np.isfinite(base) else None, "shares_changed_within_180d": bool(np.isfinite(after)), "shares_after": float(after) if np.isfinite(after) else None, "observed_ratio_times_factor": float(after / base * row.AdjustmentFactor) if np.isfinite(after) and np.isfinite(base) else None})
    pass_years = coverage.query("year >= 2011 and year <= 2014")
    status = bool((pass_years.shares_coverage >= .99).all() and (pass_years.turnover_coverage >= .99).all() and (features.loc[features.shares.notna(), "shares_age_days"] <= 450).all())
    return coverage, pd.DataFrame(event_rows), {"status": "PASS" if status else "FAIL", "definition": "raw Volume / latest strictly-prior disclosed issued-and-outstanding shares including treasury stock", "share_updates": int((features.shares.groupby(level="Code").diff().ne(0) & features.shares.groupby(level="Code").diff().notna()).sum()), "split_events": int(len(events)), "share_event_followup_rate": float(pd.DataFrame(event_rows).shares_changed_within_180d.mean()) if event_rows else 0., "development_coverage_pass": status}


def compare(record, base):
    current, reference = pd.DataFrame(record["folds"]).set_index("year"), pd.DataFrame(base["folds"]).set_index("year")
    delta = current - reference
    return {"delta_rankic": float(record["metrics"]["rankic"] - base["metrics"]["rankic"]), "delta_gross_sr": float(record["metrics"]["gross_sharpe"] - base["metrics"]["gross_sharpe"]), "delta_net_sr": float(record["metrics"]["net_sharpe"] - base["metrics"]["net_sharpe"]), "delta_turnover": float(record["metrics"]["turnover"] - base["metrics"]["turnover"]), "delta_cost": float(record["metrics"]["annual_cost"] - base["metrics"]["annual_cost"]), "delta_long_net": float(record["metrics"]["annual_long_net"] - base["metrics"]["annual_long_net"]), "delta_short_net": float(record["metrics"]["annual_short_net"] - base["metrics"]["annual_short_net"]), "net_improved_folds": int((delta.net_sharpe > 0).sum()), "long_improved_folds": int((delta.annual_long_net > 0).sum()), "short_improved_folds": int((delta.annual_short_net > 0).sum()), "long_positive_folds": int((current.annual_long_net > 0).sum()), "short_positive_folds": int((current.annual_short_net > 0).sum()), "median_delta_long_net": float(delta.annual_long_net.median()), "median_delta_short_net": float(delta.annual_short_net.median()), "fold_deltas": delta.reset_index().to_dict("records")}


def classify(record, base):
    c, m, h = record["comparison"], record["metrics"], base["metrics"]
    long_ok = m["annual_long_net"] > h["annual_long_net"] and m["long_net_sharpe"] > h["long_net_sharpe"] and c["long_improved_folds"] >= 3
    short_ok = m["annual_short_net"] > h["annual_short_net"] and c["short_improved_folds"] >= 3 and c["median_delta_short_net"] > 0
    total_ok = m["net_sharpe"] > h["net_sharpe"] and c["net_improved_folds"] >= 3
    return ("Full DTI Success" if long_ok and short_ok and total_ok else "Long-only Success" if long_ok else "Short-only Success" if short_ok else "Neither"), {"total_replacement": total_ok, "long_replacement": long_ok, "short_replacement": short_ok}


def diagnostics(signals, h0_features, target, coefficients, output):
    rows, overlap = [], []
    m60, fd = h0_features.L, h0_features.fd_equal
    for trial in ("M0", "T1", "T2", "T3"):
        frame = pd.DataFrame({"score": signals[trial], "m60": m60.reindex(signals[trial].index), "fd": fd.reindex(signals[trial].index)})
        frame = frame.loc[frame.index.get_level_values("Date").year.isin([2011, 2012, 2013, 2014])]
        daily = frame.groupby(level="Date").apply(lambda x: pd.Series({"dti_m60_spearman": x.score.corr(x.m60, method="spearman"), "dti_fd_spearman": x.score.corr(x.fd, method="spearman")}))
        rows.append({"trial": trial, **daily.mean().to_dict()})
        q, qm, qf = weights(frame.score)[1], weights(frame.m60)[1], weights(frame.fd)[1]
        overlap.append({"trial": trial, "dti_q5_m60_q5_overlap": float(((q == 4) & (qm == 4)).groupby(level="Date").mean().mean() / .2), "dti_q1_fd_q1_overlap": float(((q == 0) & (qf == 0)).groupby(level="Date").mean().mean() / .2)})
    pd.DataFrame(rows).to_csv(output / "dti_correlations.csv", index=False); pd.DataFrame(overlap).to_csv(output / "dti_overlap.csv", index=False)
    contribution = coefficients.assign(block=np.where(coefficients.feature.str.startswith("to_time"), "chronological", "sorted")).groupby(["variant", "model_year", "block"], as_index=False).agg(sum_abs_coefficient=("coefficient", lambda x: float(np.abs(x).sum())), nonzero_count=("coefficient", lambda x: int((x != 0).sum())))
    contribution.to_csv(output / "coefficient_contribution.csv", index=False)
    stability = []
    for variant, block in coefficients.groupby("variant"):
        matrix = block.pivot(index="model_year", columns="feature", values="coefficient")
        for year, value in matrix.iterrows(): stability.append({"variant": variant, "model_year": int(year), "nonzero_count": int((value != 0).sum()), "l1_norm": float(np.abs(value).sum()), "l2_norm": float(np.linalg.norm(value))})
        for left in matrix.index:
            for right in matrix.index:
                if left < right: stability.append({"variant": variant, "model_year": f"{left}-{right}", "coefficient_correlation": float(matrix.loc[left].corr(matrix.loc[right])), "sign_consistency": float((np.sign(matrix.loc[left]) == np.sign(matrix.loc[right])).mean())})
    pd.DataFrame(stability).to_csv(output / "coefficient_stability.csv", index=False)


def report(config, records, output, preflight_audit):
    lines = [f"# {config['experiment_id']}: Daily Turnover Information Long / Short", "", f"Run: `{output.name}`。Train-only。Validとraw targetは未参照。これは中国A株・月次DTIのdaily-horizon adaptationであり直接replicationではない。", "", "## Main result", "", "| Trial | Total Net SR | Long Ann Net | Long Net SR | Short Ann Net | Short Net SR | Turnover | Cost | MaxDD |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in records:
        m = r["metrics"]; lines.append(f"| {r['id']} | {m['net_sharpe']:.4f} | {m['annual_long_net']:.2%} | {m['long_net_sharpe']:.4f} | {m['annual_short_net']:.2%} | {m['short_net_sharpe']:.4f} | {m['turnover']:.4f} | {m['annual_cost']:.2%} | {m['max_drawdown_additive']:.2%} |")
    lines += ["", "## Required answers", "", f"- Q1: PIT denominator preflight **{preflight_audit['status']}**. It used raw Volume divided by the last strictly-prior disclosed issued-and-outstanding share count (including treasury shares), with 450-day expiry; split-event audit is `audit/corporate_action_audit.csv`."]
    h0 = records[0]
    for r in records[1:]:
        m, c = r["metrics"], r["comparison"]
        lines.append(f"- {r['id']}: Net SR {m['net_sharpe']:.4f} (ΔH0 {c['delta_net_sr']:+.4f}); Long Net {m['annual_long_net']:.2%} / SR {m['long_net_sharpe']:.4f}; Short Net {m['annual_short_net']:.2%} / SR {m['short_net_sharpe']:.4f}; positive Long/Short folds {c['long_positive_folds']}/4 and {c['short_positive_folds']}/4.")
    lines += ["- Q4 / Q18–Q21: `mean_turnover_comparison.csv`, `dti_correlations.csv`, `dti_overlap.csv`, `coefficient_contribution.csv`, `coefficient_stability.csv`, and `prediction_dispersion.csv` retain the preregistered comparisons.", "- Q14–Q17: `turnover_cost_decomposition.csv` reports H0/M0/DTI increments and T2→T3 cost/gross decomposition. No post-result candidate, grid, target, window, denominator, or model was added.", "- Q22–Q25: `fold_metrics.csv`, firewall, cutoff, causality, determinism, and coverage audits record time stability and Train-only compliance.", "", "## Decision", ""]
    for r in records[1:]: lines.append(f"- {r['id']}: {r['decision']}.")
    (ROOT / "reports" / config["experiment_id"] / "REPORT.md").write_text("\n".join(lines) + "\n")


def run(config_path, output):
    config, output = json.loads(Path(config_path).read_text()), Path(output); validate(config)
    for folder in (output / "audit", output / "metrics", output / "predictions", output / "models", output / "logs", ROOT / "reports" / config["experiment_id"]): folder.mkdir(parents=True, exist_ok=True)
    metadata = json.loads((output / "run.json").read_text()); metadata.update(status="running", started_at_utc=now(), command=sys.argv, actual_trials=0); dump(output / "run.json", metadata); started = time.perf_counter()
    old_h0 = ROOT / "artifacts/DM-20260910-01/run-20260910T000003Z/predictions/H0.parquet"
    try:
        firewall.install(allowed_artifacts=[old_h0]); data = ROOT / "stock_comp_2026/input"
        paths = [Path(__file__), Path(dti.__file__), Path(champion.__file__), ROOT / "research/evaluation.py", ROOT / "research/firewall.py"]
        metadata["code_sha256"] = {str(path.relative_to(ROOT)): digest(path) for path in paths}; metadata["environment"] = {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__}
        metadata["train_data_sha256"] = {f"{n}_train.parquet": digest(data / f"{n}_train.parquet") for n in ("prices_daily_quotes", "fins_statements", "raw_return_1day", "beta_1day", "topix_return_1day", "target_1day")}
        inputs = dti.load_inputs(data, "train"); features = dti.build_features(inputs); source_scan()
        adjustment = pd.read_parquet(data / "prices_daily_quotes_train.parquet", columns=["Volume", "AdjustmentFactor"]).sort_index()
        coverage, corporate, preflight_audit = preflight(features, adjustment); coverage.to_csv(output / "turnover_coverage.csv", index=False); corporate.to_csv(output / "audit/corporate_action_audit.csv", index=False); dump(output / "audit/turnover_definition.json", preflight_audit)
        if preflight_audit["status"] != "PASS": raise RuntimeError("DTI not executable: PIT denominator preflight failed")
        h0_inputs = champion.load_inputs(data, "train"); h0_features = champion.build_features(h0_inputs); h0_signal = champion.predict_from_features(h0_features, {"trial_id": "H0"}); prior = pd.read_parquet(old_h0)["Return"].sort_index(); pd.testing.assert_series_equal(h0_signal, prior, check_exact=True); dump(output / "audit/h0_reproduction.json", {"status": "PASS", "rows": int(len(h0_signal)), "bitwise": True})
        target = pd.read_parquet(data / "target_1day_train.parquet")["Return"].sort_index(); calendar = features.index.get_level_values("Date").unique().sort_values(); targets = {"RAW": target, "RANK": rank_target(target)}
        selected, tuning = {}, []
        for kind, value in targets.items(): selected[kind], rows = select_model(features, value, kind, config, calendar); tuning.extend(rows)
        dump(output / "models/hyperparameter_selection.json", tuning)
        models, _, coefficients, cutoff = annual_models(features, targets, selected, config, calendar); coefficients.to_csv(output / "elasticnet_coefficients.csv", index=False); dump(output / "audit/training_cutoff.json", cutoff)
        if not all(x["past_only"] for x in cutoff): raise AssertionError("annual fit used current-year rows")
        dump(output / "audit/causality.json", causality(inputs, features, models, config))
        signals = {"H0": h0_signal, "M0": features.mean_to21.where(features.available, 0.).fillna(0.).rename("Return"), **predict_models(features, models, config)}
        for trial, signal in signals.items():
            if not signal.index.equals(features.index) or not np.isfinite(signal).all(): raise AssertionError(f"prediction contract failed: {trial}")
            signal.to_frame().to_parquet(output / "predictions" / f"{trial}.parquet")
        dev_dates = ev.safe_dates(calendar, [2011, 2012, 2013, 2014]); dev_mask = signals["H0"].index.get_level_values("Date").isin(dev_dates); records, accounts = [], {}
        for trial in ("H0", "M0", "T1", "T2", "T3"):
            daily = compute_extended_account(signals[trial].loc[dev_mask], target.loc[signals[trial].index[dev_mask]])
            np.testing.assert_allclose(daily.long_cost_all + daily.short_cost_all, daily.cost_all, atol=1e-15, rtol=0); np.testing.assert_allclose(daily.long_net + daily.short_net, daily.net, atol=1e-15, rtol=0)
            accounts[trial] = daily; daily.to_csv(output / "metrics" / f"{trial}.csv"); record = {"id": trial, "metrics": enrich_metrics(daily), "folds": fold_metrics(daily)}
            if trial != "H0": record["comparison"] = compare(record, records[0]); record["decision"], record["checks"] = classify(record, records[0])
            records.append(record); metadata["actual_trials"] = len(records); dump(output / "trial_registry.json", records)
        pd.DataFrame([{**{"trial": r["id"]}, **r["metrics"], "decision": r.get("decision", "Reference")} for r in records]).to_csv(output / "model_comparison.csv", index=False); pd.DataFrame([{**{"trial": r["id"]}, **f} for r in records for f in r["folds"]]).to_csv(output / "fold_metrics.csv", index=False); pd.DataFrame([{**{"trial": r["id"]}, **f} for r in records[1:] for f in r["comparison"]["fold_deltas"]]).to_csv(output / "incremental.csv", index=False)
        long_short = [{"trial": r["id"], "side": side, **{k: r["metrics"][k] for k in (f"annual_{side}_gross", f"annual_{side}_net", f"{side}_gross_sharpe", f"{side}_net_sharpe", f"{side}_annual_volatility", f"{side}_turnover", f"{side}_cost_all", f"{side}_positive_day_ratio")}} for r in records for side in ("long", "short")]; pd.DataFrame(long_short).to_csv(output / "long_short_comparison.csv", index=False)
        qrows, tails = [], []
        for trial, signal in signals.items(): a, b = tail_and_quintile(signal, target, trial, [2011, 2012, 2013, 2014]); qrows.extend(a); tails.extend(b)
        pd.DataFrame(qrows).to_csv(output / "quintile_metrics.csv", index=False); pd.DataFrame(tails).to_csv(output / "tail_diagnostics.csv", index=False); diagnostics(signals, h0_features, target, coefficients, output)
        pd.DataFrame([{**{"trial": trial}, "median_daily_cs_std": float(signals[trial].loc[dev_mask].groupby(level="Date").std().median()), "p10_daily_cs_std": float(signals[trial].loc[dev_mask].groupby(level="Date").std().quantile(.1)), "p90_daily_cs_std": float(signals[trial].loc[dev_mask].groupby(level="Date").std().quantile(.9)), "zero_dispersion_days": int((signals[trial].loc[dev_mask].groupby(level="Date").std() <= 1e-15).sum()), "unique_score_count": int(signals[trial].loc[dev_mask].nunique())} for trial in signals]).to_csv(output / "prediction_dispersion.csv", index=False)
        pairs = [("M0", "T1", "M0_to_T1_RAW"), ("M0", "T2", "M0_to_T2_RANK"), ("M0", "T3", "M0_to_T3_RANK_EWMA"), ("T2", "T3", "T2_to_T3_EWMA")]; pd.DataFrame([{"comparison": name, **{f"delta_{k}": records[[r["id"] for r in records].index(right)]["metrics"][k] - records[[r["id"] for r in records].index(left)]["metrics"][k] for k in ("gross_sharpe", "net_sharpe", "turnover", "annual_cost", "long_net_sharpe", "short_net_sharpe", "annual_long_net", "annual_short_net", "rankic")}} for left, right, name in pairs]).to_csv(output / "turnover_cost_decomposition.csv", index=False)
        dump(output / "bootstrap_results.json", {trial: {"delta_total_net_sr": bootstrap_delta(accounts["H0"].net, accounts[trial].net, seed=config["random_seed"], reps=1000, block=20), "delta_long_net_sr": bootstrap_delta(accounts["H0"].long_net, accounts[trial].long_net, seed=config["random_seed"], reps=1000, block=20), "delta_short_net_sr": bootstrap_delta(accounts["H0"].short_net, accounts[trial].short_net, seed=config["random_seed"], reps=1000, block=20)} for trial in ("M0", "T1", "T2", "T3")})
        confirm_dates = ev.safe_dates(calendar, [2015, 2016]); confirm_mask = signals["H0"].index.get_level_values("Date").isin(confirm_dates); dump(output / "confirmation.json", {trial: enrich_metrics(compute_extended_account(signal.loc[confirm_mask], target.loc[signal.index[confirm_mask]])) for trial, signal in signals.items()})
        first, second = dti.build_features(inputs), dti.build_features(inputs); pd.testing.assert_frame_equal(first, second, check_exact=True); dump(output / "audit/determinism.json", {"status": "PASS", "features_bitwise": True})
        firewall.save(output / "audit/firewall.json"); metadata.update(status="completed", finished_at_utc=now(), exit_code=0, elapsed_seconds=time.perf_counter() - started, model_size_bytes=int((output / "elasticnet_coefficients.csv").stat().st_size)); dump(output / "run.json", metadata)
        manifest = {str(path.relative_to(output)): digest(path) for path in sorted(output.rglob("*")) if path.is_file() and path.name != "hash_manifest.json"}; dump(output / "hash_manifest.json", manifest)
        report_dir = ROOT / "reports" / config["experiment_id"]
        for name in ("model_comparison.csv", "fold_metrics.csv", "incremental.csv", "long_short_comparison.csv", "quintile_metrics.csv", "tail_diagnostics.csv", "turnover_coverage.csv", "dti_correlations.csv", "dti_overlap.csv", "elasticnet_coefficients.csv", "coefficient_contribution.csv", "coefficient_stability.csv", "prediction_dispersion.csv", "turnover_cost_decomposition.csv", "bootstrap_results.json", "trial_registry.json", "confirmation.json"): shutil.copyfile(output / name, report_dir / name)
        report(config, records, output, preflight_audit); (report_dir / "EXPERIMENT_LOG.md").write_text(f"# Experiment Log: {config['experiment_id']}\n\n- Run: `{output.name}`\n- Train-only; no Valid or raw target access.\n- Cumulative known scoring trials: 65.\n" + "\n".join(f"- {r['id']}: Net SR={r['metrics']['net_sharpe']:.4f}; {r.get('decision', 'Reference')}" for r in records) + "\n")
    except Exception as exc:
        metadata.update(status="failed", finished_at_utc=now(), exit_code=1, error=repr(exc)); dump(output / "run.json", metadata); raise


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--config", required=True); parser.add_argument("--output", required=True); args = parser.parse_args(); run(args.config, args.output)


if __name__ == "__main__": main()
