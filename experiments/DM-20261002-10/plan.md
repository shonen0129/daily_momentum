# DM-20261002-10 — Industry Momentum + Stock Reversal

2026-10-02 JST. New family `dm_industry_momentum_stock_reversal`. Literature-motivated hypothesis test, known Train development evidence.

## Hypothesis and prior evidence

Gao/Li/Yuan/Zhou, *The Anatomy of Industry Momentum*, SSRN6371558 (written2026-08-31, revised2026-09-12) is a working paper reporting individual one-month reversal versus short-horizon industry continuation, residual-industry and intra-industry lead-lag mechanisms. Iwanaga2024, IRFA93:103190, DOI10.1016/j.irfa.2024.103190 is peer-reviewed Japanese evidence that reversal adjustment weakens residual momentum. Search-indexed primary author abstracts and author bibliographic metadata checked; unrestricted full texts were unavailable. Detailed literature caveats are in the report.

The user explicitly requests a new externally motivated sign structure, not a rescue sign flip of Sector17/33 Momentum, HIER33, Sector Confirmation or Short Veto. Reviewed06–09 plans/configs/reports/decisions, GRAVEYARD, official rules, MOM60, PIT and official accounting. All prior decisions/code/artifacts are preserved and hashed. Existing specification remains unchanged; this plan is the separate candidate family's definition.

Shared industry information may diffuse gradually; firm-specific overreaction/liquidity pressure may unwind. This could survive t+1 open over a month, but the competition's next open-to-open residual target may remove much of the effect. These are hypotheses, not guaranteed persistence.20 days is a fixed one-month approximation, not replication or optimal-horizon search. Short histories may increase turnover/cost despite EWMA; no performance-based tuning. PIT historical membership and future sector/current classification backfill are the main leak risks; computation is a simple group mean, trailing sum, ranks and EWMA, with no fitted model.

## Fixed design before implementation or target access

Exactly3 performance trials: STOCK_REV20, WITHIN33_REV20, IND33_MOM_WITHIN_REV20. Fixed controlMOM60 unchanged. Industry-only has descriptive diagnostics without a portfolio. SLOW_CONTROL omitted (optional reference).

Residual=raw_return-beta*TOPIX, existing primitives. Both Stock and Industry use20 observations, skip1, previous observed endpoint. Stock rolling is within unchanged relisting segments (>20 absent exchange dates resets); industry rolling uses raw-return exchange calendar, insufficient daily finite-member histories remain NaN. Stock gaps can extend its calendar formation span: save this mismatch rather than invent gap imputation or select timing from results. For complete histories both use t-20 through t-1. Minimum5 finite contemporaneous PIT33 members including own. Build industry history using membership at each historical u; map signal-date PIT33 to finished history. Sum returns, no compounding. Within=Stock-Industry and Reversal=-Within, registered from literature.

Single components raw->same-date centered average percentile rank (missing->neutral0)->EWMA(.25). Combined: component ranks->fixed1:1 sum->centered rank->EWMA(.25). Same existing EWMA/relisting convention. No rank-versus-zscore or alternate skip/endpoint trial. Undefined raw is never counted as covered after neutralization.

## Evaluation and stopping

Expanding input2008-11-04…2016-03-31, no fit. Chronological calendar folds2011–2015,2016partial separately. Last2 exchange sessions per fold purged; verify target maturityt+2. Full daily portfolio/cost before selecting evaluation dates preserves prior holdings. Primary adoption scopePOOLED, EX2016 independently required. All Train history is known, not independent OOS. Official five quintiles include Q2/Q4; Code tie order,10bp one-way. Annual means*252, sample SD Sharpe*sqrt252, HAC5 Bartlett RankIC t-stat, Q1 low/Q5 high, compound and additive DD, side costs and turnover, actual period sums. Missing-target official cost omission disclosed with conservative all-position cost separately.

Feasibility each: positive pooled RankIC/GrossSR, positive ex2016GrossSR, >=3/5 positive2011–2015Gross, raw>=95%, turnover<=.08/day. Combined additionally: pooled and ex2016NetSR>MOM60, >=4/5yearNetSR improvements, primary paired bootstrap lower>0, annualNet>MOM60, turnover<=1.25*MOM60, Longnet>0, Shortnet>=MOM60, positive Q monotonicity. All criteria conjunctive, never relaxed. Components passing feasibility are diagnostic components only; failed candidates REJECT. Full trial budget3 then decision; no rescue, Freeze, Valid or submission.

Paired circular moving blocks20 eligible sessions,2000reps,seed20261002,95%percentile. Primary combined-MOM60, secondary within-stock and combined-within. Save pooled and ex2016 CIs and differences. No multiple-testing or independent-OOS claim.

## Fixed diagnostics and Q1–Q4

Save raw component IC/correlation/dispersion, industry equal-sector terciles/year/sector contributions/rank-change turnover proxy, Within signs and A–D targets, fixed lag1 self-inclusive industry return vs target association, side/net/Shortcost decompositions, MOM60 tail overlap, Sector33HHI/max/Q1Q5/top2/original-bookLOSO, turnover/rank persistence/spells, raw coverage/year/sector/minimum-member failures. Diagnostics never become candidates. No LOO even in the diagnostic. The self-inclusive lag1 industry association is compared with own prior residual and within-sector results; it cannot identify pure peer diffusion. No lag search. Q3's comparison to industry-only Net cannot be identified without a prohibited fourth portfolio; report that limit explicitly while comparing combined to both reversal candidates.

## Audit, provenance and execution

Static scan; runtime Train firewall and dedicated Train stage; all-input extreme/NaN/deletion/future-only stocks/future-sector mutations plus truncation at3cutoffs, bitwise prefix checks on industry return/history, all raw features and scores; row shuffle and rebuild; exact index/finite predictions; primitive/control parity, research/adapter and isolated no-argument smoke; official accounting and two-session maturity. Meaningful regression tests cover historical PIT membership, minimum5, missing-window behavior, segment reset and transform order. Source/input/config/environment/artifact hashes retained. Prior06–09 hashes must remain identical.

Driver: `.venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.industry_momentum_stock_reversal --config <prepared-run>/config.json --output <prepared-run>`.

Deliver experiments plan/config/decision; reports literature_hypothesis, REPORT, metrics/comparisons/bootstrap, diagnostics/coverage and causality audit. Run failure artifacts retained. No external messaging/publication.
