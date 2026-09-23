"""Finite Train-only comparison of DRI Ridge and relative-alpha Elastic Net."""
import argparse
import ast
import importlib.metadata
import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from research import firewall
from research.evaluation import bootstrap_delta
from research.experiments import asymmetric_evaluation as ev
from research.experiments.dri_long_short import clean, digest, dump, enrich_metrics, fold_metrics, mutate, now
from research.experiments.fixed_long_short import compute_extended_account
from stock_comp_2026.strategies.dm_dri_long_short import features as old_features
from stock_comp_2026.strategies.dm_dri_regularization import features, models

ROOT = Path(__file__).resolve().parents[2]
TRIALS = ["H0", "B0", "O_RAW", "O_RES", "R_RAW", "R_RES", "E_RAW", "E_RES"]


def validate(config):
    assert config["data_split"] == "train" and config["valid_evaluation"] is False
    assert [s["trial_id"] for s in config["trials"]] == TRIALS and config["max_trials"] == 8
    assert config["feature_definitions"]["window"] == 21
    assert config["parameters"]["ridge_lambda_grid"] == [.01, .1, 1.0]
    assert config["parameters"]["elasticnet_rho_grid"] == [.1, .5, .9]
    assert config["parameters"]["l1_ratio"] == .5 and config["parameters"]["ewma_alpha"] == .25
    assert config["purge_trading_days"] == 2 and config["transaction_cost_oneway"] == .001
    assert [s["year"] for s in config["walk_forward_folds"]] == [2011, 2012, 2013, 2014]


def source_scan():
    paths = sorted(Path(features.__file__).parent.glob("*.py"))
    for path in paths:
        source = path.read_text()
        for token in ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose",
                      "AdjustmentVolume", "raw_target", "target_1day_valid"]:
            assert token not in source, (path, token)
        for node in ast.walk(ast.parse(source)):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            assert node.func.attr not in ("bfill", "backfill"), path
            if node.func.attr == "shift" and node.args:
                assert isinstance(node.args[0], ast.Constant) and node.args[0].value >= 0, path
            assert not any(k.arg == "center" and isinstance(k.value, ast.Constant) and k.value.value for k in node.keywords), path
            assert not any(k.arg == "direction" and isinstance(k.value, ast.Constant) and k.value.value == "forward" for k in node.keywords), path
    return [str(p.relative_to(ROOT)) for p in paths]


def select_strength(frame, target, spec, settings, calendar):
    ident, variant, family = spec["trial_id"], spec["variant"], spec["family"]
    columns = features.feature_columns(variant)
    target = target.reindex(frame.index)
    eligible = frame[f"{variant}_available"].to_numpy() & np.isfinite(target.to_numpy())
    dates = frame.index.get_level_values("Date")
    grid = settings["ridge_lambda_grid" if family == "ridge" else "elasticnet_rho_grid"]
    rows = []
    for strength in grid:
        for number, fold in enumerate(settings["initial_cv"]):
            train = models.available_until(frame.index, fold["train_end"], calendar) & eligible
            check = ((dates >= pd.Timestamp(fold["validation_start"])) &
                     models.available_until(frame.index, fold["validation_end"], calendar) & eligible)
            fitted = models.fit_model(frame.loc[train, columns], target.loc[train], family, strength, settings)
            prediction = models.predict_matrix(frame.loc[check, columns], fitted)
            actual = target.loc[check].to_numpy()
            rows.append({"trial": ident, "strength": strength, "cv_fold": number,
                         "train_end": fold["train_end"], "max_label_signal_date": str(dates[train].max().date()),
                         "validation_rows": int(check.sum()), "train_rows": int(train.sum()),
                         "mse": float(np.mean((actual - prediction) ** 2)),
                         "null_mse": float(np.mean((actual - fitted["null_intercept"]) ** 2)),
                         "alpha": fitted["alpha"], "alpha_max": fitted["alpha_max"],
                         "nonzero_count": fitted["nonzero_count"], "prediction_std": float(prediction.std()),
                         "iterations": fitted["iterations"], "dual_gap": fitted["dual_gap"]})
    summary = []
    for strength in grid:
        subset = [r for r in rows if r["strength"] == strength]
        size = sum(r["validation_rows"] for r in subset)
        mse = sum(r["mse"] * r["validation_rows"] for r in subset) / size
        null = sum(r["null_mse"] * r["validation_rows"] for r in subset) / size
        summary.append({"trial": ident, "strength": strength, "pooled_mse": mse,
                        "pooled_null_mse": null, "delta_mse_vs_null": mse - null,
                        "relative_mse_change": mse / null - 1})
    winner = min(summary, key=lambda row: (row["pooled_mse"], -row["strength"]))["strength"]
    for row in rows + summary:
        row["selected"] = row["strength"] == winner
    return winner, rows, summary


def fit_year(frame, target, spec, strength, settings, calendar, year):
    target = target.reindex(frame.index)
    cutoff = pd.Timestamp(year=year - 1, month=12, day=31)
    take = (models.available_until(frame.index, cutoff, calendar) &
            frame[f"{spec['variant']}_available"].to_numpy() & np.isfinite(target.to_numpy()))
    fitted = models.fit_model(frame.loc[take, features.feature_columns(spec["variant"])], target.loc[take],
                              spec["family"], strength, settings)
    last = frame.index.get_level_values("Date")[take].max()
    realization = calendar[calendar.get_loc(last) + 2]
    assert realization <= cutoff
    fitted.update(model_year=year, max_label_signal_date=str(last.date()),
                  max_label_realization_date=str(realization.date()), fit_cutoff=str(cutoff.date()))
    return fitted


def build_bundle(frame, target, spec, strength, settings, calendar):
    return {"schema_version": 1, "trial": spec["trial_id"], "variant": spec["variant"],
            "family": spec["family"], "strength": strength, "split": "train",
            "ewma_alpha": settings["ewma_alpha"], "models": {
                str(year): fit_year(frame, target, spec, strength, settings, calendar, year)
                for year in settings["model_years"]}}


def causality(inputs, frame, target, specs, bundles, chosen, cv_records, settings, config, calendar):
    records = []
    originals = {s["trial_id"]: models.predict_from_features(frame, bundles[s["trial_id"]]) for s in specs}
    for label in config["causality_cutoffs"]:
        cutoff = pd.Timestamp(label)
        prefix = frame.index[frame.index.get_level_values("Date") <= cutoff]
        for mode in ("mutation", "truncation"):
            changed = features.build_features(mutate(inputs, cutoff, mode == "truncation"))
            pd.testing.assert_frame_equal(frame.loc[prefix], changed.loc[prefix], check_exact=True)
            for spec in specs:
                ident = spec["trial_id"]
                score = models.predict_from_features(changed, bundles[ident])
                pd.testing.assert_series_equal(originals[ident].loc[prefix], score.loc[prefix], check_exact=True)
            del changed
        # Refit with corrupt labels that were not yet realized at the cutoff.
        changed = features.build_features(mutate(inputs, cutoff, False))
        altered_target = target.reindex(frame.index).copy()
        unknown = ~models.available_until(frame.index, cutoff, calendar)
        altered_target.loc[unknown] = 987.0
        year = cutoff.year + 1 if cutoff.month == 12 else cutoff.year
        for spec in specs:
            ident = spec["trial_id"]
            refit = fit_year(changed, altered_target, spec, chosen[ident], settings, calendar, year)
            assert refit == bundles[ident]["models"][str(year)], (ident, year, "refit prefix")
        if label == config["causality_cutoffs"][0]:
            for spec in specs:
                ident = spec["trial_id"]
                choice, _, summary = select_strength(changed, altered_target, spec, settings, calendar)
                assert choice == chosen[ident] and summary == cv_records[ident], (ident, "CV future access")
        records.append({"cutoff": label, "rows": len(prefix), "feature_columns": len(frame.columns),
                        "feature_mutation_truncation_bitwise": True, "prediction_mutation_truncation_bitwise": True,
                        "label_future_mutation_refit_year": year, "refit_bitwise": True})
        del changed, altered_target
        print(f"causality PASS {label}", flush=True)
    return {"status": "PASS", "source_files": source_scan(), "initial_cv_future_mutation": "PASS", "cutoffs": records}


def coefficient_tables(bundles):
    coefficients, counts = [], []
    for ident, bundle in bundles.items():
        previous = None
        for year, fitted in sorted(bundle["models"].items()):
            coef = np.asarray(fitted["coef"])
            row = {"trial": ident, "year": int(year), "nonzero_count": fitted["nonzero_count"],
                   "alpha": fitted["alpha"], "alpha_max": fitted["alpha_max"], "strength": fitted["strength"],
                   "iterations": fitted["iterations"], "dual_gap": fitted["dual_gap"],
                   "coef_l1": float(np.abs(coef).sum()), "coef_l2": float(np.linalg.norm(coef))}
            if previous is not None:
                row["previous_year_sign_agreement"] = float((np.sign(coef) == np.sign(previous)).mean())
                row["previous_year_correlation"] = float(np.corrcoef(coef, previous)[0, 1]) if coef.std() > 0 and previous.std() > 0 else np.nan
            counts.append(row)
            for j, name in enumerate(fitted["columns"]):
                coefficients.append({"trial": ident, "year": int(year), "feature": name, "coefficient": coef[j],
                                     "mean": fitted["mean"][j], "scale": fitted["scale"][j],
                                     "intercept": fitted["intercept"], "train_rows": fitted["n_train"],
                                     "max_label_realization_date": fitted["max_label_realization_date"]})
            previous = coef
    return pd.DataFrame(coefficients), pd.DataFrame(counts)


def dispersion(frame, signals, bundles, evaluation_dates):
    rows = []
    for ident, bundle in bundles.items():
        raw = models.predict_from_features(frame, bundle, smooth=False)
        available = frame[f"{bundle['variant']}_available"]
        for label, score in [("raw", raw), ("smoothed", signals[ident])]:
            take = score.index.get_level_values("Date").isin(evaluation_dates) & available.to_numpy()
            grouped = score.loc[take].groupby(level="Date")
            table = pd.DataFrame({"std": grouped.std(), "unique": grouped.nunique(), "count": grouped.size()})
            for year, part in table.groupby(table.index.year):
                rows.append({"trial": ident, "year": int(year), "score": label, "mean_daily_std": float(part["std"].mean()),
                             "min_daily_std": float(part["std"].min()), "constant_days": int((part["unique"] <= 1).sum()),
                             "days": len(part), "mean_unique_fraction": float((part["unique"] / part["count"]).mean())})
    return pd.DataFrame(rows)


def decision(record, h0, counts, disp, bootstrap):
    ident = record["id"]
    annual, reference = pd.DataFrame(record["folds"]).set_index("year"), pd.DataFrame(h0["folds"]).set_index("year")
    delta = annual - reference
    c = counts.loc[(counts.trial == ident) & counts.year.isin([2011, 2012, 2013, 2014])]
    d = disp.loc[(disp.trial == ident) & (disp.score == "raw")]
    technical = bool((c.nonzero_count > 0).all() and (d.constant_days == 0).all())
    short = bool(record["metrics"]["annual_short_net"] > h0["metrics"]["annual_short_net"] and
                 (delta.annual_short_net > 0).sum() >= 3 and delta.annual_short_net.median() > 0)
    total = bool(record["metrics"]["net_sharpe"] > h0["metrics"]["net_sharpe"] and
                 (delta.net_sharpe > 0).sum() >= 3 and delta.net_sharpe.median() > 0)
    long = bool(record["metrics"]["annual_long_net"] > h0["metrics"]["annual_long_net"] and
                record["metrics"]["long_net_sharpe"] > h0["metrics"]["long_net_sharpe"] and
                (delta.annual_long_net > 0).sum() >= 3)
    checks = {"technical_nonzero": technical, "short_improvement": short, "total_improvement": total,
              "long_improvement": long, "short_positive_folds": int((annual.annual_short_net > 0).sum()),
              "short_improved_folds": int((delta.annual_short_net > 0).sum()),
              "total_improved_folds": int((delta.net_sharpe > 0).sum()),
              "median_delta_short_net": float(delta.annual_short_net.median()),
              "median_delta_net_sr": float(delta.net_sharpe.median()),
              "short_positive_source": bool(record["metrics"]["annual_short_net"] > 0 and (annual.annual_short_net > 0).sum() >= 3)}
    lower = bootstrap["low"]
    label = ("Adoptable" if lower > 0 else "Promising") if technical and short and total else "Reject"
    return label, checks


def standalone_smoke(output, specs, bundles, signals, data):
    audit = []
    worker = ROOT / "research/experiments/dri_regularization_smoke.py"
    for spec in specs:
        ident = spec["trial_id"]
        folder = output / "smoke" / ident
        folder.mkdir(parents=True)
        for path in Path(features.__file__).parent.glob("*.py"):
            shutil.copyfile(path, folder / path.name)
        dump(folder / "inference_bundle.json", bundles[ident])
        for name in features.INPUT_COLUMNS:
            (folder / f"{name}_train.parquet").symlink_to(data / f"{name}_train.parquet")
        start = time.monotonic()
        result = subprocess.run([sys.executable, str(worker), str(folder)], capture_output=True, text=True, timeout=120)
        (output / "logs" / f"smoke_{ident}.log").write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        actual = pd.read_parquet(folder / "prediction.parquet")["Return"]
        pd.testing.assert_series_equal(actual, signals[ident], check_exact=True)
        audit.append({"trial": ident, "status": "PASS", "rows": len(actual), "seconds": time.monotonic() - start,
                      "standalone_no_labels": True, "deterministic_twice": True, "bitwise": True})
    return audit


def render_report(config, records, cv, counts, disp, confirmation, output):
    lines = [f"# {config['experiment_id']}: DRI Ridge / relative-alpha Elastic Net", "",
             f"Run: `{output.name}`。Train-only、Valid/raw target未参照。旧実験・既存Championは変更していない。", "",
             "## 結論", "",
             "係数が非ゼロになったかと、予測力・コスト控除後損益が改善したかを別々に判定する。", "",
             "| Trial | Nonzero coefficients (2011/12/13/14) | Net SR | Long年率Net | Short年率Net | Short改善年 | 全体改善年 | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---|"]
    for record in records:
        ident, metric = record["id"], record["metrics"]
        subset = counts.loc[(counts.trial == ident) & counts.year.isin([2011, 2012, 2013, 2014])]
        nonzero = "/".join(subset.nonzero_count.astype(str)) if len(subset) else ("0/0/0/0" if ident.startswith("O_") else "—")
        check = record.get("checks", {})
        lines.append(f"| {ident} | {nonzero} | {metric['net_sharpe']:.4f} | {metric['annual_long_net']:.2%} | {metric['annual_short_net']:.2%} | {check.get('short_improved_folds', '—')} | {check.get('total_improved_folds', '—')} | {record.get('decision', 'Reference')} |")
    lines += ["", "## 総合指標", "", "2011–2014の974営業日。各年末でt+2越境日をpurge。",
              "片道0.1%、年率252、Sharpeは標本標準偏差、MDDは加算日次Net損益。",
              "Long/Short年率損益は公式ウェイトでのポートフォリオ全体への寄与であり、各leg単独100%投資利回りではない。", "",
              "| Trial | Gross SR | Net SR | 年率Gross | 年率Cost | 年率Net | Turnover | MDD | RankIC | HAC t | Hit |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for record in records:
        m = record["metrics"]
        lines.append(f"| {record['id']} | {m['gross_sharpe']:.4f} | {m['net_sharpe']:.4f} | {m['annual_gross']:.2%} | {m['annual_cost']:.2%} | {m['annual_net']:.2%} | {m['turnover']:.4f} | {m['max_drawdown_additive']:.2%} | {m['rankic']:.5f} | {m['rankic_t_hac5']:.3f} | {m['rankic_hit']:.1%} |")
    lines += ["", "## 正則化とnull比較", "",
              "Ridge lambdaは目的関数MSE/2 + lambda*||w||²/2で定義。sklearn alphaはn_train*lambda。",
              "Elastic Netはl1_ratio=0.5、各fitのalpha=rho*alpha_max。特徴量のみ学習期間で標準化、yの単位は変更しない。",
              "parameterは2008–2010の2つの時間順CVからpooled MSEで1回選択し、年次fitでは固定する。",
              "nullは各CV訓練期間の平均予測。非ゼロを保つ診断のためnullを選択肢に含めない。",
              "nullよりMSEが悪い場合も記録する。非ゼロ化だけで効果ありとはしない。", "",
              "| Trial | Selected lambda/rho | CV MSE | Null MSE | Relative MSE change |",
              "|---|---:|---:|---:|---:|"]
    for row in cv:
        if row["selected"]:
            lines.append(f"| {row['trial']} | {row['strength']} | {row['pooled_mse']:.10f} | {row['pooled_null_mse']:.10f} | {row['relative_mse_change']:+.4%} |")
    lines += ["", "## 年別安定性", "", "| Trial | Year | Net SR | Short年率Gross | Short年率Net | Long年率Net | Turnover | RankIC |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for record in records:
        for row in record["folds"]:
            lines.append(f"| {record['id']} | {row['year']} | {row['net_sharpe']:.4f} | {row['annual_short_gross']:.2%} | {row['annual_short_net']:.2%} | {row['annual_long_net']:.2%} | {row['turnover']:.4f} | {row['rankic']:.5f} |")
    lines += ["", "## 採否と統計的不確実性", "",
              "Champion候補は各年の非ゼロ係数・日次断面分散に加え、Short/全体ともH0を3/4年以上で改善し、",
              "pooled/median差が正であることを要求。全体ΔNetSR bootstrap下限が0以下ならPromising止まり。",
              "Longも変わる全銘柄DRIの比較であり、Short legの改善をLong固定hybridの成功としない。",
              "20日circular block bootstrap、1000回、固定seed。区間は多重比較未補正の記述的診断で、独立OOSの証明ではない。", ""]
    for record in records:
        if "checks" in record:
            c, b = record["checks"], record["bootstrap"]["total"]
            lines.append(f"- {record['id']}: {record['decision']}。技術的非ゼロ={c['technical_nonzero']}、Short改善={c['short_improvement']}、全体改善={c['total_improvement']}、Short正収益源={c['short_positive_source']}。ΔNetSR 95% CI [{b['low']:+.4f}, {b['high']:+.4f}]。")
    lines += ["", "## 既読Trainの記述的確認", "", "2015–2016-03。採否保存後に集計し、再選択に使用しない。", "",
              "| Trial | Net SR | Long年率Net | Short年率Net |", "|---|---:|---:|---:|"]
    for ident, m in confirmation.items():
        lines.append(f"| {ident} | {m['net_sharpe']:.4f} | {m['annual_long_net']:.2%} | {m['annual_short_net']:.2%} |")
    lines += ["", "## 監査と成果物", "",
              "- 旧DRIとの全特徴量bitwise一致。future mutation/truncationは3cutoffで全入力・全予測を検査。",
              "- 学習ラベルの未実現部分改変で年次refitとinitial CV選択がbitwise一致。",
              "- JSONモデル保存読込・独立推論コピー・決定性・全Train coverage・公式weight/PL一致を検証。",
              "- 詳細: `audit/causality.json`, `audit/standalone_smoke.json`, `audit/contracts.json`, `audit/firewall.json`。",
              "- `incremental.csv`はH0/B0/対応する旧DRIへの全fold/pooled差分。",
              "- `coefficient_counts.csv`, `prediction_dispersion.csv`, `quintile_metrics.csv`, `fold_metrics.csv`に診断を保存。",
              "- `models/*.json`は学習/scaler値とlabel実現日を保持。source snapshot、環境、入力hashはrunに保存。",
              f"- 4新候補+4対照=8採点。既知累積={config['known_prior_scoring_trials'] + config['max_trials']}（対照再採点を含む）。別途12 hyperparameter configurations / 24 CV fits / 24 annual fits。",
              "- 事後の候補追加・符号反転・grid拡大・hybrid・Freeze・Valid評価なし。", ""]
    return "\n".join(lines)


def snapshot_sources(output):
    paths = {Path(__file__), ROOT / "research/experiments/dri_regularization_smoke.py",
             ROOT / "stock_comp_2026/evaluate_script.py", ROOT / "tools/run_bounded.py"}
    for module in list(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if name:
            path = Path(name).resolve()
            if path.is_relative_to(ROOT) and path.suffix == ".py" and ".venv" not in path.relative_to(ROOT).parts:
                paths.add(path)
    paths.update(Path(features.__file__).parent.glob("*.py"))
    paths.update((ROOT / "tests/strategies/dm_dri_regularization").glob("*.py"))
    hashes = {}
    for path in sorted(paths):
        relative = path.relative_to(ROOT)
        destination = output / "source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        hashes[str(relative)] = digest(path)
    return hashes


def run(config_path, output_path):
    start = time.monotonic()
    config = json.loads(Path(config_path).read_text())
    validate(config)
    output = Path(output_path).resolve()
    metadata = json.loads((output / "run.json").read_text())
    assert metadata["status"] == "prepared", "A fresh prepared run is required"
    report_dir = ROOT / "reports" / config["experiment_id"]
    report_dir.mkdir(parents=True, exist_ok=True)
    settings = config["parameters"]
    specs = [s for s in config["trials"] if "family" in s]
    references = [s for s in config["trials"] if "artifact" in s]
    allowed = [ROOT / s["artifact"] for s in references]
    allowed += [output / "smoke" / s["trial_id"] / "prediction.parquet" for s in specs]
    firewall.install(allowed_artifacts=allowed)
    metadata.update(status="running", started_at_utc=now(), command=sys.argv, actual_trials=0,
                    environment={"python": sys.version, "platform": platform.platform(),
                                 **{name: importlib.metadata.version(name) for name in ["numpy", "pandas", "scipy", "scikit-learn", "pyarrow"]}},
                    code_sha256=snapshot_sources(output))
    dump(output / "run.json", metadata)
    try:
        data = ROOT / "stock_comp_2026/input"
        metadata["train_data_sha256"] = {f"{name}_train.parquet": digest(data / f"{name}_train.parquet")
                                         for name in [*features.INPUT_COLUMNS, "target_1day"]}
        metadata["reference_sha256"] = {s["artifact"]: digest(ROOT / s["artifact"]) for s in references}
        source_scan()
        inputs = features.load_inputs(data, "train")
        frame = features.build_features(inputs)
        pd.testing.assert_frame_equal(frame, old_features.build_features(inputs), check_exact=True)
        target = pd.read_parquet(data / "target_1day_train.parquet")["Return"].sort_index()
        calendar = frame.index.get_level_values("Date").unique().sort_values()
        chosen, cv_folds, cv_summary, cv_by_trial = {}, [], [], {}
        for spec in specs:
            ident = spec["trial_id"]
            chosen[ident], rows, summary = select_strength(frame, target, spec, settings, calendar)
            cv_folds.extend(rows); cv_summary.extend(summary); cv_by_trial[ident] = summary
            print(f"initial CV {ident}: strength={chosen[ident]}", flush=True)
        pd.DataFrame(cv_folds).to_csv(output / "cv_folds.csv", index=False)
        pd.DataFrame(cv_summary).to_csv(output / "cv_selection.csv", index=False)
        dump(output / "chosen_before_development.json", chosen)
        bundles = {}
        for spec in specs:
            ident = spec["trial_id"]
            bundles[ident] = build_bundle(frame, target, spec, chosen[ident], settings, calendar)
            dump(output / "models" / f"{ident}.json", bundles[ident])
            assert json.loads((output / "models" / f"{ident}.json").read_text()) == bundles[ident]
            print(f"annual fits {ident}: nonzeros=" + str([x["nonzero_count"] for x in bundles[ident]["models"].values()]), flush=True)
        coefficients, counts = coefficient_tables(bundles)
        coefficients.to_csv(output / "coefficients.csv", index=False)
        counts.to_csv(output / "coefficient_counts.csv", index=False)
        dump(output / "audit/causality.json", causality(inputs, frame, target, specs, bundles, chosen,
                                                        cv_by_trial, settings, config, calendar))
        signals = {s["trial_id"]: pd.read_parquet(ROOT / s["artifact"])["Return"].sort_index() for s in references}
        signals.update({s["trial_id"]: models.predict_from_features(frame, bundles[s["trial_id"]]) for s in specs})
        for ident, signal in signals.items():
            assert signal.index.equals(frame.index) and signal.index.is_unique and np.isfinite(signal).all(), ident
            signal.to_frame().to_parquet(output / "predictions" / f"{ident}.parquet")
        dump(output / "audit/standalone_smoke.json", standalone_smoke(output, specs, bundles, signals, data))
        dev_dates = ev.safe_dates(calendar, [2011, 2012, 2013, 2014])
        assert len(dev_dates) == 974
        mask = frame.index.get_level_values("Date").isin(dev_dates)
        disp = dispersion(frame, signals, bundles, dev_dates)
        disp.to_csv(output / "prediction_dispersion.csv", index=False)
        records, accounts = [], {}
        for spec in config["trials"]:
            ident = spec["trial_id"]
            score = signals[ident].loc[mask]
            daily = compute_extended_account(score, target.reindex(score.index), base_sig=signals["H0"].loc[mask])
            assert daily.index.equals(dev_dates) and np.isfinite(daily.net).all()
            np.testing.assert_allclose(daily.long_net + daily.short_net, daily.net, atol=1e-15, rtol=0)
            np.testing.assert_allclose(daily.long_cost_all + daily.short_cost_all, daily.cost_all, atol=1e-15, rtol=0)
            # Independent literal official qcut implementation on all development dates.
            from stock_comp_2026.evaluate_script import compute_pl, compute_weight
            official_weight = compute_weight(score.to_frame()).iloc[:, 0]
            local_weight, _ = ev.weights(score)
            pd.testing.assert_series_equal(official_weight, local_weight, check_names=False, check_exact=True)
            official = compute_pl(score.to_frame(), target.reindex(score.index).to_frame()).groupby("Date").sum()
            np.testing.assert_array_equal(official.to_numpy(), daily.net.to_numpy())
            daily.to_csv(output / "metrics" / f"{ident}.csv")
            accounts[ident] = daily
            record = {"id": ident, "spec": spec, "metrics": enrich_metrics(daily), "folds": fold_metrics(daily)}
            if "family" in spec:
                record["bootstrap"] = {name: bootstrap_delta(accounts["H0"][column], daily[column],
                    seed=config["random_seed"], reps=config["bootstrap"]["reps"], block=config["bootstrap"]["block"])
                    for name, column in [("total", "net"), ("short", "short_net"), ("long", "long_net")]}
                record["decision"], record["checks"] = decision(record, records[0], counts, disp, record["bootstrap"]["total"])
            records.append(record)
            metadata["actual_trials"] = len(records)
            dump(output / "trial_registry.json", records)
            print(f"scored {ident}: Net SR={record['metrics']['net_sharpe']:.4f}; Short Net={record['metrics']['annual_short_net']:.2%}", flush=True)
        dump(output / "decision_before_confirmation.json", records)
        compare = pd.DataFrame([{"trial": r["id"], **r["metrics"], "decision": r.get("decision", "Reference")} for r in records])
        compare.to_csv(output / "model_comparison.csv", index=False)
        folds = pd.DataFrame([{"trial": r["id"], **f} for r in records for f in r["folds"]])
        folds.to_csv(output / "fold_metrics.csv", index=False)
        deltas = []
        metrics = ["rankic", "gross_sharpe", "net_sharpe", "turnover", "annual_cost", "annual_gross", "annual_net",
                   "annual_short_gross", "annual_short_net", "annual_long_net", "max_drawdown_additive"]
        for spec in specs:
            ident = spec["trial_id"]
            for baseline in ["H0", "B0", "O_RAW" if spec["variant"] == "raw" else "O_RES"]:
                for year in ["pooled", 2011, 2012, 2013, 2014]:
                    table = compare if year == "pooled" else folds.loc[folds.year == year]
                    a, b = table.loc[table.trial == ident].iloc[0], table.loc[table.trial == baseline].iloc[0]
                    deltas.append({"trial": ident, "baseline": baseline, "year": year,
                                   **{f"delta_{key}": float(a[key] - b[key]) for key in metrics}})
        pd.DataFrame(deltas).to_csv(output / "incremental.csv", index=False)
        qkeys = [f"q{k}_daily_return" for k in range(1, 6)] + ["q_monotonicity", "bottom_decile", "top_decile"]
        folds[["trial", "year", *qkeys]].to_csv(output / "quintile_metrics.csv", index=False)
        compare[["trial", *qkeys]].to_csv(output / "quintile_pooled.csv", index=False)
        dump(output / "bootstrap_results.json", {r["id"]: r["bootstrap"] for r in records if "bootstrap" in r})
        confirm_dates = ev.safe_dates(calendar, [2015, 2016])
        cmask = frame.index.get_level_values("Date").isin(confirm_dates)
        confirmation = {}
        for ident, signal in signals.items():
            score = signal.loc[cmask]
            daily = compute_extended_account(score, target.reindex(score.index), base_sig=signals["H0"].loc[cmask])
            confirmation[ident] = enrich_metrics(daily)
            daily.to_csv(output / "metrics" / f"confirmation_{ident}.csv")
        dump(output / "confirmation.json", confirmation)
        dump(output / "audit/contracts.json", {"status": "PASS", "rows": len(frame), "development_days": len(dev_dates),
             "legacy_features_bitwise": True, "all_predictions_finite": True, "all_official_weights_pl_bitwise": True,
             "input_coverage": {v: float(frame[f"{v}_available"].mean()) for v in ["raw", "res"]}})
        firewall.save(output / "audit/firewall.json")
        (output / "REPORT.md").write_text(render_report(config, records, cv_summary, counts, disp, confirmation, output))
        (output / "EXPERIMENT_LOG.md").write_text("\n".join([f"# {config['experiment_id']}", "", f"Run: {output.name}",
            "Preregistered 4 model candidates + 4 controls; 12 tuning configurations; Train-only.",
            *[f"- {r['id']}: {r.get('decision', 'Reference')}; NetSR={r['metrics']['net_sharpe']:.6f}; ShortNet={r['metrics']['annual_short_net']:.6f}" for r in records], ""]))
        for relative, expected in metadata["code_sha256"].items():
            assert digest(ROOT / relative) == expected, f"Code changed during run: {relative}"
        metadata.update(status="completed", completed_at_utc=now(), exit_code=0,
                        elapsed_seconds=time.monotonic() - start, max_rss_bytes=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
                        actual_cv_fits=len(cv_folds), actual_new_model_families=4,
                        cumulative_known_scoring_trials=config["known_prior_scoring_trials"] + len(records))
        dump(output / "run.json", metadata)
        for path in sorted(output.iterdir()):
            if path.is_file():
                shutil.copyfile(path, report_dir / path.name)
        manifest = {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*"))
                    if p.is_file() and not p.is_symlink() and p.name != "hash_manifest.json" and "logs" not in p.relative_to(output).parts}
        dump(output / "hash_manifest.json", {"sha256": manifest, "excluded": "symlink inputs (hashed in run.json) and growing execution logs"})
        print(f"completed {output.name}: {time.monotonic() - start:.1f}s", flush=True)
    except BaseException as error:
        metadata.update(status="failed", completed_at_utc=now(), exit_code=1, error=repr(error), elapsed_seconds=time.monotonic() - start)
        dump(output / "run.json", metadata)
        firewall.save(output / "audit/firewall.json")
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        run(args.config, args.output)


if __name__ == "__main__":
    main()
