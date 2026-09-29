"""Return-blind score, ranking, turnover and holding profile for locked runs."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "artifacts/DM-20260928-01/intervention-results-v2"
OUT = RUN / "metrics/persistence_profile.csv"
STRATEGIES = ("SN1_H1", "SN1_LOW_STATE_EXPIRY_60D")
SPLITS = ("train", "historical_valid")

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()

def main():
    rows = []
    inputs = {}
    for split in SPLITS:
        for name in STRATEGIES:
            path = RUN / f"predictions/{name}_{split}.parquet"
            d = pd.read_parquet(path).sort_index()
            inputs[str(path.relative_to(ROOT))] = sha(path)
            s, q, w = d.score.astype(float), d.quintile.astype(int), d.weight.astype(float)
            dates = pd.DatetimeIndex(s.index.get_level_values("Date").unique().sort_values())
            codes = pd.Index(s.index.get_level_values("Code").unique().sort_values())
            rank = s.groupby(level="Date", sort=True).rank(method="first", pct=True)
            per_day = s.groupby(level="Date", sort=True).size()
            unique = s.groupby(level="Date", sort=True).nunique()
            boundary = pd.DataFrame({"score":s,"q":q},index=s.index).groupby(
                [s.index.get_level_values("Date"),"score"],sort=False).q.transform("nunique").gt(1)
            prior_q = q.groupby(level="Code",sort=False).shift(1)
            prior_rank = rank.groupby(level="Code",sort=False).shift(1)
            prior_score = s.groupby(level="Code",sort=False).shift(1)
            rank_pairs = []
            for day in dates[1:]:
                prev_day = dates[dates.get_loc(day)-1]
                a = rank.loc[prev_day]
                b = rank.loc[day]
                ix = a.index.intersection(b.index)
                if len(ix) > 2:
                    rank_pairs.append(float(a.loc[ix].corr(b.loc[ix])))
            qret = {}
            for qv in range(5):
                mask = prior_q.eq(qv)
                qret[f"Q{qv+1}_retention"] = float(q.loc[mask].eq(qv).mean()) if mask.any() else np.nan
            side = pd.Series(np.where(q.le(1),-1,np.where(q.ge(3),1,0)),index=q.index)
            prior_side = side.groupby(level="Code",sort=False).shift(1)
            side_stats = {}
            for label, v in (("short",-1),("long",1)):
                prev = prior_side.eq(v)
                curr = side.eq(v)
                side_stats[f"{label}_retention"] = float(curr.loc[prev].mean()) if prev.any() else np.nan
                side_stats[f"{label}_entrants_per_day"] = float((curr & ~prev).groupby(level="Date").sum().iloc[1:].mean())
                side_stats[f"{label}_exits_per_day"] = float((prev & ~curr).groupby(level="Date").sum().iloc[1:].mean())
                side_stats[f"{label}_holdings_mean"] = float(curr.groupby(level="Date").sum().mean())
            # Completed/interior observed spells; transitions to neutral break a spell.
            spell_lengths = {"short": [], "long": []}
            for code, sg in side.groupby(level="Code",sort=False):
                vals = sg.to_numpy(dtype="int8")
                if not len(vals):
                    continue
                starts = np.r_[0, np.flatnonzero(vals[1:] != vals[:-1]) + 1]
                ends = np.r_[starts[1:], len(vals)]
                for a,b in zip(starts,ends):
                    if vals[a] == -1: spell_lengths["short"].append(b-a)
                    elif vals[a] == 1: spell_lengths["long"].append(b-a)
            duration_stats = {}
            for label, arr in spell_lengths.items():
                a = np.asarray(arr,dtype=float)
                duration_stats[f"{label}_spell_count"] = int(len(a))
                duration_stats[f"{label}_spell_mean_days"] = float(a.mean()) if len(a) else np.nan
                duration_stats[f"{label}_spell_median_days"] = float(np.median(a)) if len(a) else np.nan
                duration_stats[f"{label}_spell_ge_20d_rate"] = float((a>=20).mean()) if len(a) else np.nan
                duration_stats[f"{label}_spell_ge_60d_rate"] = float((a>=60).mean()) if len(a) else np.nan
            # Fixed forward membership survival, descriptive only.
            matrix = side.unstack("Code").reindex(index=dates,columns=codes).fillna(0).to_numpy(dtype="int8")
            dpos=dates.get_indexer(side.index.get_level_values("Date")); cpos=codes.get_indexer(side.index.get_level_values("Code"))
            cur=side.to_numpy(dtype="int8")
            survival={}
            for h in (5,20,60):
                ok=dpos+h<len(dates); fut=np.zeros(len(side),dtype="int8"); fut[ok]=matrix[dpos[ok]+h,cpos[ok]]
                for label,v in (("short",-1),("long",1)):
                    ix=(cur==v)&ok
                    survival[f"{label}_survival_{h}d"] = float((fut[ix]==v).mean()) if ix.any() else np.nan
            rec={
                "split":split,"strategy":name,"rows":len(d),"dates":len(dates),
                "rank_autocorr_daily_mean":float(np.nanmean(rank_pairs)),"rank_autocorr_daily_median":float(np.nanmedian(rank_pairs)),
                "abs_rank_percentile_change_median":float((rank-prior_rank).abs().median()),
                "abs_score_daily_change_median":float((s-prior_score).abs().median()),
                "score_sign_transition_rate":float(np.sign(s).ne(np.sign(prior_score)).loc[prior_score.notna()].mean()),
                "exact_zero_rate":float(s.eq(0).mean()),"near_zero_rate":float(s.abs().lt(1e-12).mean()),
                "mean_daily_unique_ratio":float((unique/per_day).mean()),"boundary_tie_row_rate":float(boundary.mean()),
                **qret,**side_stats,**duration_stats,**survival,
            }
            rows.append(rec)
    pd.DataFrame(rows).to_csv(OUT,index=False)
    manifest={"purpose":"post-lock, return-blind profile of the sole preregistered candidate and SN1 baseline",
              "targets_or_returns_read":False,"candidate_count":1,
              "plan_sha256":sha(ROOT/"experiments/DM-20260928-01/intervention_plan.md"),
              "input_sha256":inputs,"driver_sha256":sha(Path(__file__).resolve()),"output_sha256":sha(OUT)}
    mpath=RUN/"audit/persistence_profile_manifest.json"; mpath.parent.mkdir(exist_ok=True)
    mpath.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(pd.DataFrame(rows).to_string(index=False))

if __name__=="__main__": main()
