"""Descriptive event-forward residual contribution audit for fixed SN1 H horizons.

Uses only fixed day windows requested for DM-20260927-04; no model, candidate,
threshold, or portfolio weights are changed. Returns are averaged per event and
by equal-weighted event date, oriented High=long and Low=short.
"""
from pathlib import Path
import hashlib
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.experiments import sn1_horizon as study  # noqa: E402
from stock_comp_2026.strategies.dm_variable_box_breakout import features, bidirectional  # noqa: E402

WINDOWS = (
    ("day1", 1, 2),
    ("days2_5", 4, 3),
    ("days6_20", 15, 7),
    ("days21_40", 20, 22),
)


def _window_target(residual, width, first_offset, name):
    return study.forward_window(residual, width, first_offset).rename(name)


def run(data_dir: Path, run_dir: Path):
    train_panels = features.load_inputs(data_dir, "train")
    valid_panels = features.load_inputs(data_dir, "valid")
    train_x = features.build_features(train_panels)

    # Match the research runner's 300-session feature warm-up for old Valid.
    train_resid = study.daily_residual(
        train_panels["raw_return_1day"], train_panels["beta_1day"], train_panels["topix_return_1day"]
    )
    valid_resid = study.daily_residual(
        valid_panels["raw_return_1day"], valid_panels["beta_1day"], valid_panels["topix_return_1day"]
    )
    train_calendar = pd.DatetimeIndex(train_resid.index.get_level_values("Date").unique().sort_values())
    warm_dates = set(train_calendar[-300:])
    warm_panels = {}
    for name, panel in train_panels.items():
        if name == "topix_return_1day":
            keep = panel.index.isin(warm_dates)
        else:
            keep = panel.index.get_level_values("Date").isin(warm_dates)
        warm_panels[name] = pd.concat([panel.loc[keep], valid_panels[name]]).sort_index()
    valid_x_all = features.build_features(warm_panels)
    first_valid = pd.DatetimeIndex(valid_resid.index.get_level_values("Date").unique().sort_values()).min()
    valid_x = valid_x_all.loc[valid_x_all.index.get_level_values("Date") >= first_valid]

    records = []
    for split, x, residual, split_end in (
        ("train", train_x, train_resid, train_calendar.max()),
        ("historical_valid", valid_x, valid_resid,
         pd.DatetimeIndex(valid_resid.index.get_level_values("Date").unique().sort_values()).max()),
    ):
        signal_dates = x.index.get_level_values("Date")
        if split == "train":
            active_period = signal_dates.year.isin(study.YEARS)
            train_eval_max = pd.Timestamp("2016-03-29")
            active_period &= signal_dates <= train_eval_max
        else:
            active_period = np.ones(len(x), dtype=bool)
        for name, width, first_offset in WINDOWS:
            target = _window_target(residual, width, first_offset, name)
            for side in ("high", "low"):
                mask = bidirectional.event_mask(x, side).to_numpy() & active_period
                observed = target.reindex(x.index).to_numpy(dtype=float)
                oriented = observed if side == "high" else -observed
                valid = mask & np.isfinite(oriented)
                date_values = signal_dates[valid]
                values = oriented[valid]
                frame = pd.DataFrame({"Date": date_values, "oriented_return": values})
                daily = frame.groupby("Date", sort=True)["oriented_return"].mean()
                records.append({
                    "split": split,
                    "event_side": side,
                    "window": name,
                    "events": int(valid.sum()),
                    "event_dates": int(frame.Date.nunique()),
                    "mean_event_oriented_residual": float(np.mean(values)) if len(values) else np.nan,
                    "median_event_oriented_residual": float(np.median(values)) if len(values) else np.nan,
                    "event_positive_share": float(np.mean(values > 0)) if len(values) else np.nan,
                    "mean_equal_date_oriented_residual": float(daily.mean()) if len(daily) else np.nan,
                    "usable_last_signal_date": str(frame.Date.max().date()) if len(frame) else None,
                    "split_return_end_date": str(pd.Timestamp(split_end).date()),
                    "interpretation": "event-level oriented residual diagnostic; not portfolio P/L",
                })

    out = run_dir / "metrics/event_forward_contributions.csv"
    pd.DataFrame(records).to_csv(out, index=False)
    manifest = {
        "script": str(Path(__file__).relative_to(ROOT)),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "windows": [{"name": n, "daily_residual_width": w, "first_offset": o} for n, w, o in WINDOWS],
        "orientation": {"high": "+residual (long-oriented)", "low": "-residual (short-oriented)"},
        "aggregation": "unweighted mean by event row and equal-weight mean of daily event means",
        "selection_or_tuning": False,
        "split_local_returns_only": True,
        "result_file": str(out.relative_to(ROOT)),
    }
    (run_dir / "audit/event_forward_contribution_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return pd.DataFrame(records)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=ROOT / "stock_comp_2026/input")
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    print(run(args.data_dir.resolve(), args.run_dir.resolve()).to_string(index=False))
