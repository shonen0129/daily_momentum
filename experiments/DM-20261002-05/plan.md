# DM-20261002-05 — Independent Slow Multifactor (2026-10-02 JST)

## Hypothesis and scope
Size/illiquidity risk compensation, persistent cash-generating ability/balance strength, and value may yield stable Japanese-equity cross-sectional residual-return premia independent of price Momentum. Quarterly fundamentals and structural liquidity need not be fully priced by the next open because compensation and slow information assimilation persist. Expected turnover is around .03/day from slowly changing rankings; daily raw-price denominators and corporate actions can still increase turnover. Complexity: seven ratios, three fixed equal blocks, no fitted model. Principal leakage risks are disclosure dates, future shares/sectors, adjustment levels, future normalization, and rolling across absent dates.

User explicitly requests a separate family; existing momentum_liquidity.md excludes slow factors in its Momentum correction design. This is a new strategy, not a change to that specification or SN1_H1. Current freeze/submission remains untouched.

## Prior evidence read before results
AGENTS.md, stock_comp_2026/README.md (contains already-published sample Valid summaries; those numbers are not selection evidence), experiments/GRAVEYARD.md, sample02/03/04 implementation, SN1_IMPLEMENTATION_AUDIT.md and SN1_ROBUSTNESS_FINAL.md were read. Prior financial experiments DM-20260909-01/03 and DM-20260910-01 were Short supplements/standalone Short levers. None is this independent three-block portfolio. Prior SN1 audits already rule out the simple sign/timing bug hypothesis. All Train is known development history. No Historical Valid data or sample models/Valid metrics will enter evaluation or tuning.

## Fixed definitions and finite budget
The exact formulas, missing-value rules, PIT timing, normalization and revision parent priority are in config.json. Quality uses Equity/Assets directly, not the supplied EquityToAssetRatio substitute. No Scale fallback is used. Zero/negative denominators are missing, infinity becomes missing, missing is same-date median then neutral zero. Sample size20 is fixed for sector transforms. Per-field backward carry is allowed; no future fill.

BASE is mandatory (one trial). SECTOR runs only if BASE pooled and ex-2016 annual gross >0, at least3/5 full years have gross >0, and turnover <=.06/day (a generous feasibility screen, distinct from .03 design aim). REVISION runs only if BASE or SECTOR has pooled/ex-2016 gross >0, at least4/5 full years gross >0, and BOTH pooled long and short gross >0; SECTOR has fixed parent priority if it qualifies. REVISION is latest-minus-previous finite disclosed ForecastEPS / raw Close, global normalization, equal fourth block. Max3 candidate trials, no result-driven new trials, weight/alpha/horizon/threshold search or short veto. Diagnostic block-only attribution is not a selectable candidate.

## Evaluation contract
Train-only firewall and stage containing seven allowed Train files (prices, fins, listed, raw_return, beta, topix_return, target). Predictions never read labels. Fixed controls are frozen res60s1+EWMA .25 and equal size/liquidity only (a label-free adaptation of sample02 rather than its full-Train trained coefficients).

Walk-forward expands causal input history, evaluates2011–2015 full calendar years plus2016 partial, without any fitting. Purge final2 exchange dates of each fold so t+2 remains within its fold; no target learning, and normalization always signal-date only. Portfolio weights/costs are computed continuously from full history before filtering evaluation dates, preserving prior holdings at fold starts and purge gaps. Also report descriptive2008–2010 annual metrics, excluded from adoption gates, and all-history pooled separately.

Official5-quintile Code tie ordering and weights,10bp one-way cost, annualization252, HAC5 RankIC t-stat, arithmetic annual P/L, compound maximum drawdown. Report official missing-target cost behavior plus conservative all-position cost; long/short cost allocation by prior/current sign half each (entry assigned new side, exit old side, crossing split). Long+Short cost/gross/net must reconcile. Report fold/year/pooled, Q1–Q5, baseline deltas, cost/turnover decomposition, feature coverage and conditional block quintiles. Paired circular20-day bootstrap2000 draws seed20261002, both controls, no label-based adjustment.

## Causality and acceptance
Full new builder (all raw, standardized, block, revision columns) and predictions must remain bitwise identical before3 cutoffs under each-source and joint future mutation; suffix row deletions/new records and PIT date/sector/shares changes plus prefix truncation. Test deterministic replay, row shuffle, index/finite/NaN coverage, raw-level independence, disclosure timing, rolling calendar and standalone submission parity. Runtime firewall must reject forbidden parquet reads. Static scan is additional evidence.

Next-stage eligibility is config.selection_rule (stable net improvement vs both controls, both sides positive, positive RankIC/monotonicity and bootstrap lower bounds); pooled maximum Sharpe is not an adoption rule. Failing candidates are retained and rejected clearly. No Freeze/Valid/external submission within this task.

## Execution and artifacts
Driver: research/experiments/slow_multifactor.py --config <run>/config.json --output <run>, wrapped by tools/run_bounded.py --seconds1800. Tests use180-second limit. Code/config/plan/environment/input hashes, seed, command, elapsed/peak RSS, actual trials and failures stored in new run. Results in reports/DM-20261002-05, decision in this experiment, rejection in GRAVEYARD. Technical retries keep unchanged economic definitions and retain failed runs.
