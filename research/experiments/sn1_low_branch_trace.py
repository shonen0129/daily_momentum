"""P/L-blind H1 event prediction/feature rows for the final Low audit."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from research.experiments import state_persistence_audit as state_audit
from stock_comp_2026.strategies.dm_variable_box_breakout import bidirectional, features

REF_RUN = ROOT / "artifacts/DM-20260927-04/run-20260927T101500Z"
PHASE1_TABLE = ROOT / "artifacts/DM-20260928-01/run-20260927T154814Z/audit/date_code_state.parquet"
INPUT_DIR = ROOT / "stock_comp_2026/input"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def build(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    (out / "predictions").mkdir(exist_ok=True)
    (out / "audit").mkdir(exist_ok=True)
    original_reader, accesses = None, []
    try:
        accesses = state_audit.install_phase1_read_guard()
        train_panels = features.load_inputs(INPUT_DIR, "train")
        valid_panels = features.load_inputs(INPUT_DIR, "valid")
        x_train = features.build_features(train_panels)
        x_valid = state_audit.build_valid_features(train_panels, valid_panels)
        frames = []
        for split, x in (("train", x_train), ("historical_valid", x_valid)):
            preds = state_audit.fixed_event_predictions(x, split)
            for side in bidirectional.SIDES:
                prediction = preds[side].sort_index()
                mask = bidirectional.event_mask(x, side).reindex(prediction.index).fillna(False)
                if not mask.all():
                    raise AssertionError(f"Saved-model {side} predictions include non-event rows: {split}")
                matrix = bidirectional.directional_features(x.reindex(prediction.index), side)
                unsigned = bidirectional.active_percentile(prediction)
                sign = 1.0 if side == "high" else -1.0
                row = matrix.copy()
                row["split"] = split
                row["breakout_side"] = side
                row["ridge_prediction"] = prediction
                row["raw_unsigned_event_score"] = unsigned
                row["signed_raw_event_score"] = sign * unsigned
                row["model_year"] = (
                    prediction.index.get_level_values("Date").year
                    if split == "train" else -1
                )
                frames.append(row)
        events = pd.concat(frames).sort_index()
        if not events.index.is_unique:
            raise AssertionError("High/Low event prediction index overlap")
        # Restore the ordinary reader only after the feature/saved-model firewall pass.
        import pandas.io.parquet as _pq
        # The guard installed by state_audit is restored by reloading the module's original binding.
        pd.read_parquet = _ORIGINAL_READ_PARQUET
        state_table = pd.read_parquet(PHASE1_TABLE).sort_index()
        aligned = events.index.intersection(state_table.index)
        comparisons = []
        for side, raw_col in (("high", "high_raw_event_score"), ("low", "low_raw_event_score")):
            side_events = events.loc[events.breakout_side.eq(side)]
            common = side_events.index.intersection(state_table.index)
            observed = side_events.loc[common, "signed_raw_event_score"]
            expected = state_table.loc[common, raw_col]
            if side == "high":
                expected = expected.where(state_table.loc[common, "high_event"], 0.0)
            else:
                expected = expected.where(state_table.loc[common, "low_event"], 0.0)
            delta = (observed - expected).abs()
            comparisons.append({
                "side": side, "rows": int(len(common)), "max_abs_signed_event_score_delta": float(delta.max()) if len(delta) else None,
                "pass_2e_12": bool(len(delta) and float(delta.max()) <= 2e-12),
            })
        output = out / "predictions/event_predictions_and_features.parquet"
        events.to_parquet(output, compression="zstd")
        model_paths = sorted((REF_RUN / "models/H1").rglob("*.json"))
        manifest = {
            "phase": "P/L-blind event prediction and feature trace preparation",
            "paper_data_accessed": False, "target_or_raw_target_accessed": False, "pnl_calculated": False,
            "train_and_historical_valid_development_only": True,
            "features": list(bidirectional.DIRECTIONAL_COLUMNS),
            "event_rows": int(len(events)),
            "by_split_side": {f"{split}_{side}": int(((events.split == split) & (events.breakout_side == side)).sum())
                              for split in ("train", "historical_valid") for side in ("high", "low")},
            "saved_event_score_reconstruction": comparisons,
            "feature_input_paths_read": sorted(set(accesses)),
            "feature_input_sha256": {p: sha(ROOT / p) for p in sorted(set(accesses))},
            "phase1_table_sha256": sha(PHASE1_TABLE),
            "saved_model_sha256": {str(p.relative_to(ROOT)): sha(p) for p in model_paths},
            "code_sha256": {
                "research/experiments/sn1_low_branch_trace.py": sha(Path(__file__).resolve()),
                "research/experiments/state_persistence_audit.py": sha(ROOT / "research/experiments/state_persistence_audit.py"),
                "stock_comp_2026/strategies/dm_variable_box_breakout/features.py": sha(ROOT / "stock_comp_2026/strategies/dm_variable_box_breakout/features.py"),
                "stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py": sha(ROOT / "stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py"),
                "stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py": sha(ROOT / "stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py"),
            },
            "event_predictions_and_features_sha256": sha(output),
            "no_target_values_in_trace": True,
        }
        write_json(out / "audit/trace_preparation_manifest.json", manifest)
        if not all(row["pass_2e_12"] for row in comparisons):
            raise AssertionError(f"Model event scores do not reproduce the saved signed event stream: {comparisons}")
        return manifest
    finally:
        if original_reader is not None:
            pd.read_parquet = original_reader


_ORIGINAL_READ_PARQUET = pd.read_parquet


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.out.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
