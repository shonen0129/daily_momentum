"""Saved-result attribution only: no feature rebuild, trial or candidate change."""
import argparse
import json
from pathlib import Path
import shutil

from research.experiments.sector_momentum import ROOT, dump, sha, daily_corr
from research import evaluation, firewall
from stock_comp_2026.strategies.dm_sector_momentum import features as sm
import numpy as np
import pandas as pd


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    source = Path(args.run).resolve()
    run = json.loads((source / "run.json").read_text())
    config = json.loads((source / "config.json").read_text())
    assert run["status"] == "completed" and run["actual_trials"] == 3
    for relative, expected in run["code_sha256"].items():
        assert sha(ROOT / relative) == expected
    for relative, expected in run["artifact_sha256"].items():
        assert sha(source / relative) == expected
    output = Path(args.output).resolve()
    assert output.parent == source
    output.mkdir()
    feature_path, score_path = [source / "predictions" / (x + ".parquet") for x in ["features", "scores"]]
    target_path = source / "stage/target_1day_train.parquet"
    assert sha(target_path) == run["train_data_sha256"][target_path.name]
    firewall.install(allowed_artifacts=[feature_path, score_path])
    f, scores = pd.read_parquet(feature_path), pd.read_parquet(score_path)
    target = pd.read_parquet(target_path).Return.reindex(f.index)
    daily = pd.read_csv(source / "metrics/daily_MOM60.csv", index_col=0, parse_dates=True)
    calendar = daily.index
    evaluation_dates = pd.DatetimeIndex(pd.read_csv(source / "metrics/rank_persistence_daily.csv").iloc[:, 0].unique(), name="Date")
    dates = f.index.get_level_values("Date")
    valid = dates.isin(evaluation_dates)
    rows, raw_ic = [], []
    scopes = [("POOLED", evaluation_dates)] + [(str(y), evaluation_dates[evaluation_dates.year == y]) for y in range(2011, 2017)]
    for strategy in scores:
        w, q = evaluation.weights(scores[strategy].rename("Return"))
        shortpos = (-w).clip(lower=0)
        cost = .001 * shortpos.groupby("Code").diff().abs().fillna(shortpos.abs()).where(target.notna(), 0.)
        for level in [17, 33]:
            peer = f[f"Sector{level}Mom"]
            groups = {"NEGATIVE": peer < 0, "POSITIVE": peer > 0,
                      "ZERO_OR_MISSING": peer.isna() | (peer == 0)}
            for sign, mask in groups.items():
                gross = (w.where((w < 0) & mask, 0.) * target).groupby("Date").sum()
                attributed_cost = cost.where(mask, 0.).groupby("Date").sum()
                exposure = shortpos.where(mask, 0.).groupby("Date").sum()
                for scope, ds in scopes:
                    g, c = gross.loc[ds], attributed_cost.loc[ds]
                    rows.append({"strategy": strategy, "level": level, "sector_sign": sign, "scope": scope,
                        "annual_short_gross_contribution": g.mean() * 252,
                        "annual_short_net_contribution": (g - c).mean() * 252,
                        "annual_attributed_cost": c.mean() * 252, "mean_short_exposure": exposure.loc[ds].mean(),
                        "short_gross_sharpe": evaluation.sharpe(g), "short_net_sharpe": evaluation.sharpe(g - c),
                        "method": "original full portfolio positions/costs, classified by contemporaneous peer sign; no filter/rerank"})
    pd.DataFrame(rows).to_csv(output / "short_sector_sign.csv", index=False)
    missing_rows = []
    for strategy, col in sm.CANDIDATES.items():
        level = 17 if strategy == "SECTOR17_MOM" else 33
        missing = f[col].isna()
        for scope, ds in scopes:
            keep = dates.isin(ds)
            reasons = {"missing_PIT_classification": missing & f[f"Sector{level}Code"].isna(),
                       "insufficient_finite_peers": missing & f[f"Sector{level}Code"].notna() & (f[f"Peer{level}Count"] < (10 if level == 17 else 5)),
                       "own_history_insufficient_only": missing & f[f"Sector{level}Mom"].notna() & f.StockMom60.isna()}
            for reason, mask in reasons.items():
                missing_rows.append({"strategy": strategy, "scope": scope, "reason": reason,
                                     "rows": int((mask & keep).sum()), "fraction_of_all_rows": (mask & keep).sum() / keep.sum()})
            ic = evaluation.rankic(f[col], target).loc[ds]
            raw_ic.append({"strategy": strategy, "scope": scope, "mean_rankic": ic.mean(),
                           "HAC5_t": evaluation.hac_t(ic), "hit_ratio": (ic.dropna() > 0).mean(),
                           "note": "finite raw components only, diagnostic; not another candidate"})
    pd.DataFrame(missing_rows).to_csv(output / "coverage_reasons.csv", index=False)
    pd.DataFrame(raw_ic).to_csv(output / "raw_component_rankic.csv", index=False)
    rank = f.StockMom60.groupby("Date").rank(pct=True)
    ordinal = pd.Series(calendar.get_indexer(dates), index=f.index)
    adjacent = (ordinal - ordinal.groupby("Code").shift(1)) == 1
    previous = rank.groupby("Code").shift(1).where(adjacent)
    rho = daily_corr(rank, previous)
    pd.DataFrame({"raw_StockMom60_rank_autocorrelation": rho}).loc[evaluation_dates].to_csv(output / "raw_stock_rank_persistence_daily.csv")
    dump(output / "raw_stock_rank_persistence.json", {"diagnostic_only": True,
        "mean_rank_autocorrelation": rho.loc[evaluation_dates].mean(), "new_performance_trials": 0,
        "purpose": "Unsmoothed raw stock rank persistence separates control smoothing confound; no P/L or weight/cost strategy evaluation."})
    manifest = {p.name: sha(p) for p in output.iterdir() if p.is_file()}
    dump(output / "manifest.json", {"status": "PASS", "source_run": str(source.relative_to(ROOT)),
        "original_code_and_artifact_hashes_verified": True, "new_performance_trials": 0,
        "feature_rebuilds": 0, "new_strategy": False, "script_sha256": sha(Path(__file__)),
        "artifact_sha256": manifest, "inputs": {str(p.relative_to(source)): sha(p) for p in [feature_path, score_path, target_path]},
        "firewall_opened": sorted(firewall.ACCESSES), "valid_evaluation": False})
    report = ROOT / config["report_dir"]
    for path in output.iterdir():
        target_copy = report / ("audit" if path.name == "manifest.json" else "metrics") / ("saved_diagnostics_manifest.json" if path.name == "manifest.json" else path.name)
        shutil.copyfile(path, target_copy)
    print("Saved-result supplemental diagnostics complete; new performance trials=0", flush=True)


if __name__ == "__main__":
    main()
