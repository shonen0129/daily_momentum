"""Fixed-baseline semantic, attribution and robustness audit for SN1_H1.

This driver deliberately has only a baseline gate and one fixed diagnostics
phase. It has no candidate-generation path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from research import evaluation
from stock_comp_2026.strategies.dm_variable_box_breakout import sn1

EXP = ROOT / "experiments/DM-20260928-02"
PHASE1 = ROOT / "artifacts/DM-20260928-01/run-20260927T154814Z/audit/date_code_state.parquet"
PRED_DIR = ROOT / "artifacts/DM-20260928-01/intervention-results-v2/predictions"
REF_RUN = ROOT / "artifacts/DM-20260927-04/run-20260927T101500Z"
PHASE2 = ROOT / "artifacts/DM-20260928-01/run-20260927T161843Z/metrics"
ACCOUNT_DATES = {
    "train": (pd.Timestamp("2011-01-04"), pd.Timestamp("2016-03-29")),
    "historical_valid": (pd.Timestamp("2016-04-01"), pd.Timestamp("2026-07-29")),
}
ALIASES = {"train": "train", "historical_valid": "valid"}
ACCOUNTS = {"train": "daily_account_train_H1.csv", "historical_valid": "daily_account_valid_H1.csv"}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def permitted_inputs() -> set[Path]:
    config = json.loads((EXP / "config.json").read_text(encoding="utf-8"))
    return {(ROOT / p).resolve() for p in config["allowed_inputs"]}


def guarded_parquet_reader(extra_allowed=()):
    allowed = permitted_inputs() | {Path(p).resolve() for p in extra_allowed}
    original = pd.read_parquet
    accesses: list[str] = []

    def guarded(path, *args, **kwargs):
        resolved = Path(path).resolve()
        if resolved not in allowed or "paper" in str(resolved).lower() or "raw_target" in resolved.name.lower():
            raise PermissionError(f"Final audit firewall denied parquet: {resolved}")
        accesses.append(str(resolved.relative_to(ROOT)))
        return original(path, *args, **kwargs)

    pd.read_parquet = guarded
    return original, accesses


def load_target(split: str) -> pd.Series:
    frame = pd.read_parquet(REF_RUN / f"predictions/target_{ALIASES[split]}_H1.parquet")
    out = frame["Return"] if "Return" in frame else frame.iloc[:, 0]
    out.index = pd.MultiIndex.from_arrays(
        [pd.DatetimeIndex(out.index.get_level_values("Date")), out.index.get_level_values("Code").astype(str)],
        names=["Date", "Code"],
    )
    out = pd.to_numeric(out, errors="coerce").astype("float64").sort_index()
    if not out.index.is_unique:
        raise AssertionError(f"Duplicate H1 target index: {split}")
    return out


def load_score(split: str) -> pd.DataFrame:
    frame = pd.read_parquet(PRED_DIR / f"SN1_H1_{split}.parquet").sort_index()
    frame.index = pd.MultiIndex.from_arrays(
        [pd.DatetimeIndex(frame.index.get_level_values("Date")), frame.index.get_level_values("Code").astype(str)],
        names=["Date", "Code"],
    )
    if not frame.index.is_unique or not {"score", "quintile", "weight"}.issubset(frame.columns):
        raise AssertionError(f"Invalid fixed-score artifact: {split}")
    return frame


def load_full_signal(split: str) -> pd.Series:
    frame = pd.read_parquet(REF_RUN / f"predictions/SN1_H1_{split}.parquet")
    out = frame["Return"] if "Return" in frame else frame.iloc[:, 0]
    out.index = pd.MultiIndex.from_arrays(
        [pd.DatetimeIndex(out.index.get_level_values("Date")), out.index.get_level_values("Code").astype(str)],
        names=["Date", "Code"],
    )
    out = pd.to_numeric(out, errors="coerce").astype("float64").sort_index()
    if not out.index.is_unique:
        raise AssertionError(f"Duplicate full fixed-signal index: {split}")
    return out


def load_saved_account(split: str) -> pd.DataFrame:
    path = REF_RUN / "metrics" / ACCOUNTS[split]
    d = pd.read_csv(path, parse_dates=["Date"]).set_index("Date").sort_index()
    return d


def max_abs(a: pd.Series, b: pd.Series) -> float:
    x, y = a.align(b, join="outer")
    if x.isna().any() or y.isna().any():
        return float("inf")
    return float(np.max(np.abs(x.to_numpy(dtype="float64") - y.to_numpy(dtype="float64")))) if len(x) else 0.0


def baseline_phase(out: Path, reconstruction_dir: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    reconstruction_manifest_path = reconstruction_dir / "audit/phase1_manifest.json"
    reconstruction_manifest = json.loads(reconstruction_manifest_path.read_text(encoding="utf-8"))
    reconstruction_paths = {
        "train": reconstruction_dir / "predictions/SN1_H1_RECONSTRUCTED_train.parquet",
        "historical_valid": reconstruction_dir / "predictions/SN1_H1_RECONSTRUCTED_historical_valid.parquet",
    }
    prior_reader, accesses = guarded_parquet_reader(reconstruction_paths.values())
    rows: list[dict] = []
    replay_outputs = []
    phase_table = pd.read_parquet(PHASE1).sort_index()

    for split, (first, last) in ACCOUNT_DATES.items():
        pred = load_score(split)
        full_signal = load_full_signal(split)
        current = pd.read_parquet(reconstruction_paths[split]).sort_index()
        target = load_target(split)
        if not pred.index.is_unique or not target.index.is_unique or not full_signal.index.is_unique:
            raise AssertionError(f"Index uniqueness failure: {split}")
        if full_signal.index.intersection(target.index).size != len(full_signal):
            raise AssertionError(f"Full saved H1 signal rows are not covered by H1 target: {split}")
        if not current.index.equals(full_signal.index) or current.isna().any().any():
            raise AssertionError(f"Full warm-up-preserving reconstruction coverage failure: {split}")
        state = phase_table.loc[phase_table["split"].astype(str).eq(split)]
        state_current = current.reindex(state.index)
        if state_current.isna().any().any():
            raise AssertionError(f"Current reconstruction misses state rows: {split}")
        state_error = max_abs(current["score"], full_signal)
        eval_rebuilt = current.reindex(pred.index)
        q_error = max_abs(eval_rebuilt["quintile"].astype(float), pred["quintile"].astype(float))
        w_error = max_abs(eval_rebuilt["weight"], pred["weight"])
        state_rebuilt_q_error = max_abs((state_current["quintile"] + 1).astype(float), state["official_quintile"].astype(float))
        state_rebuilt_w_error = max_abs(state_current["weight"], state["weight"])
        state_q_error = max_abs((state["official_quintile"].reindex(pred.index) - 1).astype(float), pred["quintile"].astype(float))
        state_w_error = max_abs(state["weight"].reindex(pred.index), pred["weight"])

        daily_full = evaluation.daily_account(current["score"], target)
        period_dates = daily_full.index[(daily_full.index >= first) & (daily_full.index <= last)]
        saved_daily = load_saved_account(split)
        saved_daily = saved_daily.loc[(saved_daily.index >= first) & (saved_daily.index <= last)]
        # The official saved account schedule excludes immature year-end H1 rows.
        # Compare only those exact official account dates; record other target dates.
        daily = daily_full.reindex(saved_daily.index)
        if daily.isna().any().any() or not daily.index.equals(saved_daily.index):
            raise AssertionError(f"Official account date alignment failure: {split}")
        field_delta = {}
        for field in ("gross", "net", "cost", "turnover"):
            field_delta[field] = max_abs(daily[field], saved_daily[field])
            rows.append({"split": split, "check": f"daily_{field}", "max_abs_delta": field_delta[field]})
        rows.extend([
            {"split": split, "check": "score_reconstruction", "max_abs_delta": state_error},
            {"split": split, "check": "current_score_to_saved_quintile", "max_abs_delta": q_error},
            {"split": split, "check": "current_score_to_saved_weight", "max_abs_delta": w_error},
            {"split": split, "check": "reconstructed_quintile_to_state_table", "max_abs_delta": state_rebuilt_q_error},
            {"split": split, "check": "reconstructed_weight_to_state_table", "max_abs_delta": state_rebuilt_w_error},
            {"split": split, "check": "state_quintile_to_saved", "max_abs_delta": state_q_error},
            {"split": split, "check": "state_weight_to_saved", "max_abs_delta": state_w_error},
        ])
        replay_outputs.append({
            "split": split, "full_signal_rows": int(len(full_signal)), "reconstructed_rows": int(len(current)), "evaluation_score_rows": int(len(pred)), "state_rows": int(len(state)), "target_rows": int(len(target)),
            "account_days": int(len(daily)), "account_start": str(daily.index.min().date()),
            "account_end": str(daily.index.max().date()), "target_coverage_on_full_signal_rows": float(target.reindex(full_signal.index).notna().mean()),
            "target_dates_in_period_excluded_from_official_account": [str(d.date()) for d in period_dates.difference(saved_daily.index)],
            "max_abs_delta": {"score_reconstruction": state_error, "quintile": q_error, "weight": w_error,
                              "reconstructed_quintile_to_state_table": state_rebuilt_q_error,
                              "reconstructed_weight_to_state_table": state_rebuilt_w_error, **field_delta},
            "pass": max(state_error, q_error, w_error, state_rebuilt_q_error, state_rebuilt_w_error,
                        state_q_error, state_w_error, *field_delta.values()) <= 2e-12,
        })
        daily.to_csv(out / f"baseline_daily_replay_{split}.csv", index_label="Date")

    pd.DataFrame(rows).to_csv(out / "baseline_parity_checks.csv", index=False)
    passed = all(item["pass"] for item in replay_outputs)
    result = {
        "phase": "phase_0_reproducibility_no_regression",
        "pass": passed,
        "paper_data_accessed": False,
        "raw_target_accessed": False,
        "reference_state_table_sha256": sha(PHASE1),
        "full_model_reconstruction_manifest_sha256": sha(reconstruction_manifest_path),
        "full_model_reconstruction_manifest": str(reconstruction_manifest_path.relative_to(ROOT)),
        "code_sha256": {
            "research/experiments/sn1_final_structural_audit.py": sha(Path(__file__).resolve()),
            "research/evaluation.py": sha(ROOT / "research/evaluation.py"),
            "stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py": sha(ROOT / "stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py"),
        },
        "accessed_parquets": sorted(set(accesses)),
        "splits": replay_outputs,
    }
    write_json(out / "baseline_parity.json", result)
    if not passed:
        raise AssertionError("SN1_H1 Phase 0 baseline parity failed; stop all new analysis")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["baseline", "analysis"])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--reconstruction-dir", type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if args.phase == "baseline":
        if args.reconstruction_dir is None:
            raise SystemExit("--reconstruction-dir is required for a full warm-up-preserving score reconstruction")
        result = baseline_phase(out, args.reconstruction_dir.resolve())
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        baseline_path = out / "baseline_parity.json"
        if not baseline_path.exists() or not json.loads(baseline_path.read_text()).get("pass"):
            raise SystemExit("Analysis stopped: Phase 0 baseline parity is missing or failed")
        raise NotImplementedError("Fixed diagnostics are added after the baseline gate")


if __name__ == "__main__":
    main()
