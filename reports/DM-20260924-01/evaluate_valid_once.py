"""One-time frozen H0 vs C3S comparison on the previously accessed Valid set."""
from __future__ import annotations

import hashlib
import importlib
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "stock_comp_2026/input"
C3S_RELEASE = ROOT / "releases/DM-20260924-C3S-v1"
C3S_ZIP = C3S_RELEASE / "dm_c3s_submission.zip"
H0_RELEASE = ROOT / "releases/DM-20260908-v1/snapshot"
H0_ZIP = H0_RELEASE / "stock_comp_2026/strategies/dm_trainonly.zip"
OUT_JSON = ROOT / "reports/DM-20260924-01/valid_comparison.json"
OUT_DAILY = ROOT / "reports/DM-20260924-01/valid_daily.csv"

sys.path.insert(0, str(ROOT / "stock_comp_2026"))
sys.path.insert(0, str(ROOT))
from evaluate_script import (  # noqa: E402
    TRANSACTION_COST_RATE,
    align_prediction,
    compute_pl,
    compute_sr,
    compute_weight,
    load_prediction,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clear_submission_modules() -> None:
    for name in ("submission", "features", "models"):
        sys.modules.pop(name, None)


def verify_freezes() -> dict:
    c3s_manifest = json.loads((C3S_RELEASE / "freeze_manifest.json").read_text())
    if sha256(C3S_ZIP) != c3s_manifest["submission_zip_sha256"]:
        raise RuntimeError("C3S frozen zip hash changed after freeze")
    for rel, expected in c3s_manifest["code_sha256"].items():
        if sha256(C3S_RELEASE / rel) != expected:
            raise RuntimeError(f"C3S frozen source hash changed: {rel}")

    h0_manifest_path = H0_RELEASE / "reports/DM-20260908/freeze_manifest.json"
    h0_manifest = json.loads(h0_manifest_path.read_text())
    expected_h0 = h0_manifest["artifact_sha256"][
        "stock_comp_2026/strategies/dm_trainonly.zip"
    ]
    if sha256(H0_ZIP) != expected_h0:
        raise RuntimeError("H0 frozen zip hash does not match its original freeze")
    if h0_manifest["selected_parameters"]["selected_trial_id"] != "M_res60s1_a0.25":
        raise RuntimeError("H0 release is not the requested res60s1 alpha=0.25 baseline")

    for filename, expected in c3s_manifest["train_input_sha256"].items():
        if sha256(DATA / filename) != expected:
            raise RuntimeError(f"Train input differs from the frozen comparison input: {filename}")

    return {
        "C3S_zip_sha256": c3s_manifest["submission_zip_sha256"],
        "H0_zip_sha256": expected_h0,
        "H0_trial_id": h0_manifest["selected_parameters"]["selected_trial_id"],
        "train_inputs_match_freeze": True,
    }


def load_frozen_prediction(path: Path) -> pd.DataFrame:
    clear_submission_modules()
    pred = load_prediction(path, DATA)
    return pred


def score_strategy(name: str, pred: pd.DataFrame, target: pd.DataFrame):
    aligned = align_prediction(pred, target)
    if not np.isfinite(aligned.iloc[:, 0]).all():
        raise RuntimeError(f"{name} produced non-finite Valid predictions")

    weights = compute_weight(aligned).iloc[:, 0]
    target_s = target.iloc[:, 0]
    gross_rows = weights * target_s
    net_rows = compute_pl(aligned, target).rename("net")
    gross = gross_rows.groupby(level="Date").sum().rename("gross")
    net = net_rows.groupby(level="Date").sum().rename("net")
    cost = (gross.reindex(net.index) - net).rename("cost")
    turnover_rows = (
        weights.groupby(level="Code").diff().abs().fillna(weights.abs())
    )
    turnover = turnover_rows.groupby(level="Date").sum().reindex(net.index)
    daily = pd.concat([gross.reindex(net.index), net, cost, turnover.rename("turnover")], axis=1)

    # Recreate the exact official five-bucket assignment for descriptive cross-section metrics.
    sorted_signal = aligned.iloc[:, 0].sort_index().fillna(0.0)
    ranks = sorted_signal.groupby(level="Date").rank(method="first")
    bins = ranks.groupby(level="Date").transform(
        lambda x: pd.qcut(x, 5, labels=False)
    )
    from research.evaluation import hac_t, rankic  # local helper; same aligned labels
    rank_ic = rankic(aligned.iloc[:, 0], target.iloc[:, 0])
    q_daily = pd.DataFrame(index=net.index)
    for q in range(5):
        q_daily[f"q{q+1}"] = target_s.where(bins == q).groupby(level="Date").mean()
    q_means = q_daily.mean()
    q_mono = float(spearmanr(np.arange(1, 6), q_means.to_numpy()).statistic)

    additive = np.r_[0.0, daily["net"].cumsum().to_numpy()]
    drawdown = additive - np.maximum.accumulate(additive)
    detail = {
        "prediction_rows": int(len(aligned)),
        "target_coverage": float(target.iloc[:, 0].notna().mean()),
        "official_net_sharpe": compute_sr(net_rows),
        "gross_sharpe_official_weights": compute_sr(gross_rows),
        "annual_gross_pl": float(daily["gross"].mean() * 252),
        "annual_cost": float(daily["cost"].mean() * 252),
        "annual_net_pl": float(daily["net"].mean() * 252),
        "average_daily_turnover": float(daily["turnover"].mean()),
        "max_additive_drawdown": float(drawdown.min()),
        "mean_rank_ic": float(rank_ic.mean()),
        "rank_ic_hac5_t": hac_t(rank_ic),
        "rank_ic_hit_ratio": float((rank_ic.dropna() > 0).mean()),
        "q1_to_q5_mean_return": [float(x) for x in q_means.to_numpy()],
        "q1_q5_monotonicity_spearman": q_mono,
    }
    annual = []
    for year, group in daily.groupby(daily.index.year):
        y_ic = rank_ic.loc[rank_ic.index.year == year]
        annual.append({
            "year": int(year),
            "days": int(len(group)),
            "gross_sharpe": compute_sr(group["gross"]),
            "official_net_sharpe": compute_sr(group["net"]),
            "annual_gross_pl": float(group["gross"].mean() * 252),
            "annual_cost": float(group["cost"].mean() * 252),
            "annual_net_pl": float(group["net"].mean() * 252),
            "average_daily_turnover": float(group["turnover"].mean()),
            "mean_rank_ic": float(y_ic.mean()),
            "rank_ic_hit_ratio": float((y_ic.dropna() > 0).mean()),
        })
    return detail, daily, annual


def main() -> None:
    started = time.monotonic()
    freeze_checks = verify_freezes()

    # Generate both frozen predictions before the evaluator opens any target file.
    h0_prediction = load_frozen_prediction(H0_ZIP)
    c3s_prediction = load_frozen_prediction(C3S_ZIP)

    # This is the first read in this run of the previously accessed Valid target.
    target_path = DATA / "target_1day_valid.parquet"
    target = pd.read_parquet(target_path)
    if list(target.index.names) != ["Date", "Code"]:
        raise RuntimeError(f"Unexpected target index names: {target.index.names}")

    baseline, h0_daily, h0_annual = score_strategy("H0", h0_prediction, target)
    candidate, c3s_daily, c3s_annual = score_strategy("C3S", c3s_prediction, target)
    if not h0_daily.index.equals(c3s_daily.index):
        raise RuntimeError("H0 and C3S scorer date indices differ")

    daily = pd.concat(
        {"H0": h0_daily, "C3S": c3s_daily},
        axis=1,
    )
    daily.to_csv(OUT_DAILY, index_label="Date")
    valid_files = [
        "raw_return_1day_valid.parquet",
        "beta_1day_valid.parquet",
        "topix_return_1day_valid.parquet",
        "prices_daily_quotes_valid.parquet",
        "target_1day_valid.parquet",
    ]
    result = {
        "evaluation": "one-time frozen H0 vs C3S comparison",
        "valid_independence": "not independent OOS; the same Valid period had previously been accessed for DM-20260912-01-v1",
        "freeze_checks": freeze_checks,
        "scorer": "stock_comp_2026/evaluate_script.py functions: load_prediction, align_prediction, compute_weight, compute_pl, compute_sr",
        "transaction_cost_rate_one_way": TRANSACTION_COST_RATE,
        "annualization": 252,
        "valid_period": {
            "start": str(target.index.get_level_values("Date").min().date()),
            "end": str(target.index.get_level_values("Date").max().date()),
            "trading_days": int(target.index.get_level_values("Date").nunique()),
            "target_rows": int(len(target)),
            "target_coverage": float(target.iloc[:, 0].notna().mean()),
        },
        "valid_input_sha256": {name: sha256(DATA / name) for name in valid_files},
        "strategies": {
            "H0": {**baseline, "annual": h0_annual},
            "C3S": {**candidate, "annual": c3s_annual},
        },
        "delta_C3S_minus_H0": {
            "official_net_sharpe": candidate["official_net_sharpe"] - baseline["official_net_sharpe"],
            "gross_sharpe_official_weights": candidate["gross_sharpe_official_weights"] - baseline["gross_sharpe_official_weights"],
            "annual_gross_pl": candidate["annual_gross_pl"] - baseline["annual_gross_pl"],
            "annual_cost": candidate["annual_cost"] - baseline["annual_cost"],
            "annual_net_pl": candidate["annual_net_pl"] - baseline["annual_net_pl"],
            "average_daily_turnover": candidate["average_daily_turnover"] - baseline["average_daily_turnover"],
            "mean_rank_ic": candidate["mean_rank_ic"] - baseline["mean_rank_ic"],
        },
        "post_freeze_code_or_parameter_change": False,
        "elapsed_seconds": time.monotonic() - started,
        "peak_rss_platform_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
