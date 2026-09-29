"""Continuous, PIT-safe beta exposure summary for the fixed SN1_H1 audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "artifacts/DM-20260928-01/run-20260927T154814Z/audit/date_code_state.parquet"
SPLIT_FILE = {"train": "train", "historical_valid": "valid"}
ACCOUNT_PERIODS = {
    "train": (pd.Timestamp("2011-01-04"), pd.Timestamp("2016-03-29")),
    "historical_valid": (pd.Timestamp("2016-04-01"), pd.Timestamp("2026-07-29")),
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_beta(split: str) -> pd.Series:
    frame = pd.read_parquet(ROOT / f"stock_comp_2026/input/beta_1day_{SPLIT_FILE[split]}.parquet", columns=["Return"])
    frame.index = pd.MultiIndex.from_arrays(
        [pd.DatetimeIndex(frame.index.get_level_values("Date")), frame.index.get_level_values("Code").astype(str)],
        names=["Date", "Code"],
    )
    return pd.to_numeric(frame["Return"], errors="coerce").astype("float64").sort_index()


def summarize(rows: pd.DataFrame, split: str, account_dates: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame]:
    beta = load_beta(split).reindex(rows.index)
    frame = rows.copy()
    frame["beta_120d_pit"] = beta
    frame = frame.loc[frame.portfolio_side.astype(str).isin(["long", "short"])].copy()
    frame["persistence"] = np.where(pd.to_numeric(frame.sleeve_age, errors="coerce").fillna(0).ge(20), "persistent_20_plus", "under_20")
    frame["signed_beta_load"] = frame.weight * frame.beta_120d_pit
    frame["gross_beta_load"] = frame.weight.abs() * frame.beta_120d_pit
    frame["abs_weight"] = frame.weight.abs()

    details = []
    yearly = []
    for (side, persistence), group in frame.groupby([frame.portfolio_side.astype(str), "persistence"], sort=True):
        daily = group.groupby(level="Date").agg(
            signed_beta_load=("signed_beta_load", "sum"),
            gross_beta_load=("gross_beta_load", "sum"),
            abs_weight=("abs_weight", "sum"),
        ).reindex(account_dates).fillna(0.0)
        details.append({
            "split": split,
            "side": side,
            "persistence": persistence,
            "stock_days": int(len(group)),
            "beta_coverage": float(group.beta_120d_pit.notna().mean()) if len(group) else np.nan,
            "mean_stock_beta": float(group.beta_120d_pit.mean()) if group.beta_120d_pit.notna().any() else np.nan,
            "median_stock_beta": float(group.beta_120d_pit.median()) if group.beta_120d_pit.notna().any() else np.nan,
            "mean_abs_weight": float(group.abs_weight.mean()) if len(group) else np.nan,
            "mean_daily_signed_beta_load": float(daily.signed_beta_load.mean()),
            "mean_daily_gross_beta_load": float(daily.gross_beta_load.mean()),
            "gross_exposure_weight_sum": float(group.abs_weight.sum()),
        })
        temp = daily.copy()
        temp["year"] = temp.index.year
        for year, yearly_frame in temp.groupby("year", sort=True):
            dates = yearly_frame.index
            yearly.append({
                "split": split,
                "side": side,
                "persistence": persistence,
                "year": int(year),
                "partial_year": bool((split == "historical_valid" and year in {2016, 2026}) or (split == "train" and year == 2016)),
                "days": int(len(yearly_frame)),
                "mean_daily_signed_beta_load": float(yearly_frame.signed_beta_load.mean()),
                "mean_daily_gross_beta_load": float(yearly_frame.gross_beta_load.mean()),
                "annualized_signed_beta_load": float(yearly_frame.signed_beta_load.mean() * 252),
                "annualized_gross_beta_load": float(yearly_frame.gross_beta_load.mean() * 252),
            })
    return pd.DataFrame(details), pd.DataFrame(yearly)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    state = pd.read_parquet(STATE_PATH).sort_index()
    if not state.index.is_unique:
        raise AssertionError("Duplicate state Date×Code rows")
    detail_frames, year_frames = [], []
    accesses = [STATE_PATH]
    for split in ("train", "historical_valid"):
        selected = state.loc[state.split.astype(str).eq(split)].copy()
        start, end = ACCOUNT_PERIODS[split]
        dates = pd.DatetimeIndex(selected.index.get_level_values("Date"))
        in_period = (dates >= start) & (dates <= end)
        selected = selected.loc[in_period]
        account_dates = pd.DatetimeIndex(sorted(selected.index.get_level_values("Date").unique()), name="Date")
        detail, year = summarize(selected, split, account_dates)
        detail_frames.append(detail)
        year_frames.append(year)
        accesses.append(ROOT / f"stock_comp_2026/input/beta_1day_{SPLIT_FILE[split]}.parquet")
    details = pd.concat(detail_frames, ignore_index=True)
    years = pd.concat(year_frames, ignore_index=True)
    details.to_csv(out / "risk_beta_exposure.csv", index=False)
    years.to_csv(out / "risk_beta_exposure_by_year.csv", index=False)
    manifest = {
        "phase": "continuous PIT beta exposure; no target or P/L file read",
        "paper_data_accessed": False,
        "raw_target_file_accessed": False,
        "beta_definition": "existing 120-market-day rolling raw-return/TOPIX beta; signal-date beta is used for exposure",
        "thresholds_or_buckets_added": False,
        "state_path_sha256": sha(STATE_PATH),
        "code_sha256": sha(Path(__file__).resolve()),
        "input_hashes": {str(p.relative_to(ROOT)): sha(p) for p in accesses},
        "outputs": {name: sha(out / name) for name in ("risk_beta_exposure.csv", "risk_beta_exposure_by_year.csv")},
        "rows": {"overview": int(len(details)), "by_year": int(len(years))},
    }
    (out / "risk_beta_exposure_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
