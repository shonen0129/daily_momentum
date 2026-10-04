# DM-20261002-11 — Sector granularity robustness, one trial

2026-10-02 JST. ParentDM-20261002-10 remains REJECT. This is a granularity robustness test, not a new strategy search or a rescue sign/weight/horizon trial. Known Train development evidence only; no independent OOS.

Hypothesis: broader PIT17 groups may reduce sparse-industry missingness and noisy daily means, stabilize signal ranks and lower turnover/cost. Broader common information may still persist beyond t+1 open, but mixing industries can dilute industry continuation. Within reversal may remain weak and costs may overwhelm gross. Aggregation/noise is the only economic mechanism varied. PIT historical membership is the main leakage risk; computational complexity remains a mean/trailing sum/rank/EWMA. No new beta/factor/fit.

## Fixed before implementation or target/results

Exactly1 new performance candidate IND17_MOM_WITHIN_REV20. IND33_MOM_WITHIN_REV20 is the unchanged primary control; MOM60 unchanged reference. Replay prior saved scores and verify bitwise rebuild/control-account parity; old STOCK_REV20/WITHIN33_REV20 portfolios are not rerun.

Only PIT33→PIT17 changes. All other feature timing, skip1, horizon20, rolling min20, raw_return-beta*TOPIX, missing treatment and relisting gap20 remain exactly parent10. Historical industry daily return uses that historical date's present raw-return members and exact PIT17, self-inclusive equal finite mean, minimum5 (not the old Sector17 minimum10 from another strategy). Invalid/9999/blank excluded. Industry history on raw-return exchange calendar, gaps stayNaN; shift1/rolling20 sum, assign finished history using signal-date PIT17. Stock uses unchanged per-Code observed history. Within=Stock-Industry; Reversal=-Within. Component-centered average percentile ranks, fixed1:1 sum, centered rank of sum then per-Code EWMA alpha.25/adjustFalse. Raw NaN persists for coverage; neutral0 after ranking. No LOO, alternative horizons/skips/scales/weights/alpha/threshold/filter.

## Evaluation and stopping

Same expanding input2008-11-04…2016-03-31, no fit; chronological calendar folds2011–2015 and2016partial separately. Last2 exchange sessions per fold purged with target maturityt+2 checked. Full-history daily book/cost before fold selection preserves prior holdings. Official quintiles/Q2Q4 and Code ties;10bp one-way, sampleSD SR*sqrt252, arithmetic annual mean*252, RankIC HAC5 Bartlett/hit, Q1low/Q5high, additive/compound DD. Missing-target official cost omission plus conservative all-position cost saved. No borrow costs.

Unchanged parent feasibility: positive pooledRankIC/GrossSR, positive ex2016GrossSR, >=3/5positive2011–2015Gross, rawcoverage>=95%, turnover<=.08. Unchanged combined criteria againstMOM60: pooled/ex2016NetSRgreater,>=4/5full-yearNetSRimprovements, paired pooled17-minusMOM60 lowerCI>0, annualNetgreater, turnover<=MOM60*1.25, Longnet>0, Shortnet>=MOM60, positiveQmonotonicity. Any failed gate REJECT. Primary17-minus33 evidence is a descriptive robustness contrast; no new threshold/tuned gate. One trial then decision, regardless results. No Freeze/Valid/submission/rescue.

Bootstrap paired circular20eligible sessions/2000reps/seed20261002/95%percentile. Primary17-minus33, reference17-minusMOM60; pooled andex2016. Eligible purge gaps concatenated, no multiplicity/OOS claim.

Answer five questions: rawcoverage17>33; turnover17<33; Industry continuationIC retains positive direction and stability; raw Within reversalIC and original-bookShortgross/net improve; NetSR17beats33andMOM60. Save overall/year/fold and all deltas. Raw component RankIC on respective finite sets and joint finite17/33 rows distinguishes coverage effects; no component trading portfolio. Sector concentration all3 books under BOTH PIT17 andPIT33 so partition coarsening is not confused with changing positions. Same persistence/rank-change/spell definitions asparent, boundary censored full spells intersect evaluation; no duration filters.

## Audits and provenance

New self-contained strategy folder preserves parent source; copied primitive source parity and classification-only normalized-source comparison. New builder all4Train sources future-mutation/truncation3cutoffs including future PIT sectors, membership, new stocks; full industry history and features/final bitwise invariant. Row shuffle/rebuild, exact index/NaN/finitecoverage, research/adapter and standalone no-argument parity, source scan, runtime Train firewall, dedicatedTrainstage, official accounting, target maturity. Rebuild33features/control and compare prior saved raw/features/scores/daily accounts. All parent10files/code and run.json hashes remain unchanged. Save plan/config/code/input/environment/artifact hashes/resources; boundedrun1800s. Synthetic tests directly cover17PIT history, minimum5/gaps, timing/transform andprefix. No performance-driven changes.

Driver: `.venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.industry_granularity_robustness --config <prepared-run>/config.json --output <prepared-run>`.

Results in reports/<ID>, decision in experiments/<ID>, rejection appended toGRAVEYARD. Previous evidence is retained. Weak17meansREJECT, not another trial.
