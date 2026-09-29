"""Bounded Train-only old/new replay for the split-adjusted ATR correction."""
import argparse
import importlib.util
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from research import evaluation, firewall
from stock_comp_2026.strategies.dm_variable_box_breakout import bidirectional, features


EXPERIMENT_ID = "DM-20260929-01"
BASELINE_FEATURES = ROOT / "releases/DM-20260927-SN1-v1/snapshot/strategy/features.py"
EVALUATION_YEARS = tuple(range(2011, 2017))


def digest(path):
    with Path(path).open("rb") as stream:
        import hashlib
        return hashlib.file_digest(stream, "sha256").hexdigest()


def dump(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                          encoding="utf-8")


def load_baseline_features():
    spec = importlib.util.spec_from_file_location("dm_variable_box_breakout_pref_fix", BASELINE_FEATURES)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load immutable baseline features: {BASELINE_FEATURES}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def feature_differences(old, new):
    if not old.index.equals(new.index) or list(old.columns) != list(new.columns):
        raise AssertionError("Old/new feature index or column contract differs")
    rows = []
    for column in old:
        left, right = old[column], new[column]
        equal = left.eq(right) | (left.isna() & right.isna())
        both = left.notna() & right.notna()
        delta = (right[both].astype(float) - left[both].astype(float)).abs()
        rows.append({
            "feature": column,
            "rows": len(old),
            "changed_rows": int((~equal).sum()),
            "changed_fraction": float((~equal).mean()),
            "max_abs_delta": float(delta.max()) if len(delta) else 0.0,
            "old_missing": int(left.isna().sum()),
            "new_missing": int(right.isna().sum()),
        })
    return rows


def fit_and_score(x, target):
    predictions, training_records = bidirectional.walk_forward_predictions(
        x, target, years=EVALUATION_YEARS, model_dir=None
    )
    score = bidirectional.generate_signal(x, predictions, alpha=0.25)
    if not score.index.equals(target.index) or not np.isfinite(score.to_numpy()).all():
        raise AssertionError("Train score index coverage or finite-value check failed")
    if not score.index.is_unique:
        raise AssertionError("Train score index is not unique")
    for side in bidirectional.SIDES:
        dates = x.index.get_level_values("Date")
        expected_mask = bidirectional.event_mask(x, side) & dates.year.isin(EVALUATION_YEARS)
        expected = x.index[expected_mask.to_numpy()]
        if not predictions[side].index.equals(expected):
            raise AssertionError(f"{side} prediction event coverage differs from feature events")
        if not np.isfinite(predictions[side].to_numpy()).all():
            raise AssertionError(f"{side} predictions contain nonfinite values")
    return predictions, score, training_records


def evaluation_dates(index):
    dates = pd.DatetimeIndex(index.get_level_values("Date").unique().sort_values())
    selected = []
    for year in EVALUATION_YEARS:
        year_dates = dates[dates.year == year]
        if len(year_dates) <= 2:
            raise AssertionError(f"Insufficient Train dates for fold {year}")
        selected.extend(year_dates[:-2].tolist())
    return pd.DatetimeIndex(selected).sort_values()


def summarize_score(score, target, dates):
    daily = evaluation.daily_account(score, target).loc[dates]
    overall = evaluation.metrics(daily)
    yearly = [{"year": int(year), **evaluation.metrics(frame)}
              for year, frame in daily.groupby(daily.index.year)]
    return daily, overall, yearly


def run(config_path, output_path):
    started = time.monotonic()
    output = Path(output_path).resolve()
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if (config.get("experiment_id") != EXPERIMENT_ID or config.get("data_split") != "train"
            or config.get("valid_evaluation") is not False or config.get("selection_eligible") is not False
            or config.get("max_trials") != 1):
        raise ValueError("Unexpected replay scope; only the registered single Train-only comparison is allowed")
    metadata_path = output / "run.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    code_paths = [Path(__file__).resolve(), Path(features.__file__).resolve(),
                  Path(bidirectional.__file__).resolve(), Path(evaluation.__file__).resolve(),
                  Path(firewall.__file__).resolve(), BASELINE_FEATURES]
    metadata.update({
        "status": "running",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": sys.argv,
        "actual_trials": 1,
        "valid_accessed": False,
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "numpy": np.__version__, "pandas": pd.__version__},
        "code_sha256": {str(path.relative_to(ROOT)): digest(path) for path in code_paths},
    })
    dump(metadata_path, metadata)
    try:
        firewall.install()
        data_dir = ROOT / "stock_comp_2026/input"
        train_inputs = features.load_inputs(data_dir, split="train")
        target_frame = pd.read_parquet(data_dir / "target_1day_train.parquet")
        target = target_frame["Return"].sort_index()
        old_module = load_baseline_features()
        old_x = old_module.build_features(train_inputs)
        new_x = features.build_features(train_inputs)
        if not old_x.index.equals(target.index) or not new_x.index.equals(target.index):
            raise AssertionError("Old/new feature index does not exactly match Train target")
        calendar = pd.DatetimeIndex(target.index.get_level_values("Date").unique().sort_values())
        if str(calendar.min().date()) != "2008-11-04" or str(calendar.max().date()) != "2016-03-31":
            raise AssertionError("Unexpected Train date span")

        old_predictions, old_score, old_training = fit_and_score(old_x, target)
        new_predictions, new_score, new_training = fit_and_score(new_x, target)
        replay_predictions, replay_score, replay_training = fit_and_score(new_x, target)
        pd.testing.assert_series_equal(new_score, replay_score, check_exact=True)
        for side in bidirectional.SIDES:
            pd.testing.assert_series_equal(new_predictions[side], replay_predictions[side], check_exact=True)
        if new_training != replay_training:
            raise AssertionError("Annual model training records changed on deterministic replay")

        dates = evaluation_dates(target.index)
        old_daily, old_overall, old_yearly = summarize_score(old_score, target, dates)
        new_daily, new_overall, new_yearly = summarize_score(new_score, target, dates)
        old_by_year = {item["year"]: item for item in old_yearly}
        new_by_year = {item["year"]: item for item in new_yearly}
        metrics_to_diff = ("rankic", "gross_sharpe", "net_sharpe", "annual_net", "annual_cost",
                           "turnover", "q_monotonicity", "max_drawdown_additive")
        year_rows = []
        for year in EVALUATION_YEARS:
            row = {"year": year}
            for name in metrics_to_diff:
                row[f"old_{name}"] = old_by_year[year][name]
                row[f"new_{name}"] = new_by_year[year][name]
                row[f"delta_{name}"] = new_by_year[year][name] - old_by_year[year][name]
            year_rows.append(row)

        prediction_frame = pd.DataFrame({"old_score": old_score, "corrected_score": new_score}, index=target.index)
        for side in bidirectional.SIDES:
            prediction_frame[f"old_{side}_event_prediction"] = old_predictions[side].reindex(target.index)
            prediction_frame[f"corrected_{side}_event_prediction"] = new_predictions[side].reindex(target.index)
        artifact_path = output / "predictions/paired_train_scores.parquet"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        prediction_frame.sort_index().to_parquet(artifact_path)
        yearly_path = output / "metrics/yearly_comparison.csv"
        yearly_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(year_rows).to_csv(yearly_path, index=False)
        summary = {
            "status": "PASS",
            "comparison": "immutable pre-fix feature builder versus corrected feature builder",
            "valid_accessed": False,
            "raw_target_accessed": False,
            "train_span": [str(calendar.min().date()), str(calendar.max().date())],
            "evaluation_span": [str(dates.min().date()), str(dates.max().date())],
            "evaluation_years": list(EVALUATION_YEARS),
            "purge": "last two signal dates of each evaluation year omitted",
            "feature_differences": feature_differences(old_x, new_x),
            "old_score": old_overall,
            "corrected_score": new_overall,
            "delta_corrected_minus_old": {
                key: new_overall[key] - old_overall[key]
                for key in metrics_to_diff if isinstance(old_overall.get(key), (int, float))
            },
            "annual_metrics": year_rows,
            "prediction_rows": len(prediction_frame),
            "prediction_dates": int(target.index.get_level_values("Date").nunique()),
            "prediction_codes": int(target.index.get_level_values("Code").nunique()),
            "prediction_finite_and_full_index": True,
            "event_prediction_rows_old": {side: len(old_predictions[side]) for side in bidirectional.SIDES},
            "event_prediction_rows_corrected": {side: len(new_predictions[side]) for side in bidirectional.SIDES},
            "deterministic_replay": "bitwise exact for corrected scores, event predictions and model records",
            "old_training_records": old_training,
            "corrected_training_records": new_training,
            "artifact": str(artifact_path.relative_to(ROOT)),
        }
        dump(output / "metrics/summary.json", summary)
        firewall.install(allowed_artifacts=[artifact_path])
        metadata["artifact_sha256"] = {str(artifact_path.relative_to(ROOT)): digest(artifact_path)}
        metadata["train_data_sha256"] = {
            path.name: digest(path) for path in [
                *(data_dir / f"{name}_train.parquet" for name in features.INPUT_COLUMNS),
                data_dir / "target_1day_train.parquet",
            ]
        }
        firewall.save(output / "audit/firewall.json")
        access = json.loads((output / "audit/firewall.json").read_text(encoding="utf-8"))
        if any("_valid" in path.lower() or "raw_target" in path.lower()
               for path in access["opened_parquets"]):
            raise AssertionError("Train-only runtime firewall recorded prohibited data access")
        metadata.update({
            "status": "completed",
            "exit_code": 0,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": time.monotonic() - started,
            "valid_accessed": False,
            "source_firewall": "PASS",
            "index_alignment": "PASS",
            "finite_coverage": "PASS",
            "deterministic_replay": "PASS",
            "run_summary": str((output / "metrics/summary.json").relative_to(ROOT)),
            "firewall_audit": str((output / "audit/firewall.json").relative_to(ROOT)),
        })
        dump(metadata_path, metadata)
        report = [
            "# DM-20260929-01: split-adjusted ATR correction regression", "",
            f"- Run: `{output.name}`; Train only; Valid and raw target were not accessed.",
            f"- Old features: `{BASELINE_FEATURES.relative_to(ROOT)}`.",
            "- Fixed annual expanding high/low Ridge models and score smoothing were held constant; no model or parameter selection was performed.",
            f"- Evaluation: {summary['evaluation_span'][0]} through {summary['evaluation_span'][1]}, with each year's last two signal dates purged.",
            "- Feature-level changes and overall metrics are in the run's `metrics/summary.json`; annual paired differences are in `metrics/yearly_comparison.csv`.",
            f"- Corrected candidate Net Sharpe: {new_overall['net_sharpe']:.4f}; old implementation: {old_overall['net_sharpe']:.4f}; descriptive difference: {new_overall['net_sharpe']-old_overall['net_sharpe']:+.4f}.",
            f"- Full Train signal coverage: {len(prediction_frame):,} rows; deterministic replay: PASS; firewall: PASS.",
            "- This replay verifies an implementation correction and does not declare a strategy improvement or create a new holdout.",
            "",
        ]
        (ROOT / "reports" / EXPERIMENT_ID).mkdir(parents=True, exist_ok=True)
        (ROOT / "reports" / EXPERIMENT_ID / "BUGFIX_VALIDATION.md").write_text("\n".join(report), encoding="utf-8")
        return summary
    except BaseException as error:
        metadata.update({"status": "failed", "exit_code": 1,
                         "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                         "failure": repr(error), "elapsed_seconds": time.monotonic() - started})
        try:
            firewall.save(output / "audit/firewall.json")
        except BaseException:
            pass
        dump(metadata_path, metadata)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    result = run(arguments.config, arguments.output)
    print(json.dumps({"status": result["status"], "overall_old_net_sharpe": result["old_score"]["net_sharpe"],
                      "overall_corrected_net_sharpe": result["corrected_score"]["net_sharpe"],
                      "valid_accessed": result["valid_accessed"]}, indent=2))
