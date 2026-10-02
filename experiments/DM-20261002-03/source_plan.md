# DM-20261002-02: 2025 retrospective NCMOM20 diagnostic using current major-customer graph

## Hypothesis and scope

The fixed SN1_H1 baseline uses issuer price history. Under the user's explicit stability assumption, a current `major_customer` graph held constant through 2025 may let the prior 20 customer residual returns rank next-session supplier returns. This is a hindsight descriptive sensitivity check, not a PIT-feasible feature test: the graph was published in 2026 and is deliberately projected backward to 2025. The requested period is inclusive, 2025-01-04 through 2025-12-30. It overlaps the already-read historical Valid/development period, so it cannot establish an independent out-of-sample result or authorize a strategy change.

No model is fitted and no SN1 score is blended or modified. The fixed saved SN1_H1 historical Valid scores are used only for a matched-coverage benchmark and conditional ranking summaries. The report will state whether the observed NCMOM20 ordering is descriptively consistent with information beyond SN1; it will not call that causal or PIT evidence.

## Fixed data and feature contract

- Graph: the downloaded JP_Market_Vis `2026.09` snapshot (`M5_company_relations`, generated 2026-09-22), held constant on every 2025 signal date. Its paired `M4_companies` mapping is the endpoint master.
- Edges: `major_customer` only, supplier to customer. Retain `confirmed` relations only when the evidence array contains a primary EDINET source. Exclude `needs_review`, other relation types, non-primary-only evidence, self-edges, duplicate pairs, and endpoints without a unique exact listed-code crosswalk into the 2025 competition panel. This high-confidence subset is fixed before outcomes are read.
- NCMOM20 for supplier `i` on signal date `t`: the equal-weight mean across its mapped customers of the sum of 20 preceding market-session residual returns, `raw_return - beta * TOPIX`, ending at the prior market session. Require 20 finite observations for each customer's full preceding 20-session window. Exclude customers without a complete window; leave the supplier score missing when no mapped customer has a complete window. Never use signal-date or later customer returns; never fill a missing score with zero.
- Target: the provided `target_1day_valid.parquet` `Return` on the same signal-date/code index, restricted to 2025-01-04..2025-12-30. No `raw_target` file or column is used. Because this is Valid history, target access is explicitly retrospective and non-holdout.
- Baseline: the already-saved `SN1_H1_historical_valid.parquet` `Return` score; no refit or changes to its definition.
- Code crosswalk: derive from current M4 securities codes and the per-date `listed_info_valid` Code/CompanyName records. Accept only a unique, exact documented code relation with consistent company-name match; list unmatched/ambiguous edges. Do not fuzzy-match names.

## Fixed descriptive evaluation

Use only dates with NCMOM, saved baseline score, and target alignment. Report full-universe baseline coverage separately from matched network-covered stock-days. On the same covered names each day, compare baseline score and NCMOM20 as independent ranking diagnostics, not as competing production portfolios. Calculate daily Spearman RankIC, pooled mean, HAC(5) t-statistic, positive-day hit ratio, NCMOM quintile target means, monotonicity, and Q5-Q1. Also report mean daily cross-sectional Spearman correlation between NCMOM20 and SN1_H1.

For incremental-information context, compute NCMOM RankIC and NCMOM Q5-Q1 inside each daily SN1_H1 full-universe score quintile. Quintiles are recomputed daily, ties are broken deterministically by Code, and each conditional bucket is formed only from covered names in that baseline quintile. Do not choose favorable buckets after seeing results.

For portfolio context only, construct separate daily equal-weight Q5-long/Q1-short diagnostic portfolios for NCMOM20 and SN1_H1 over the identical covered subset: +0.5 total long weight and -0.5 total short weight, no holdings overlap, rebalance daily, 10 bps one-way cost times sum of absolute target-weight changes. Initialize the first in-period portfolio from cash and charge the resulting turnover. Report annualized arithmetic gross/net P&L, annualized Sharpe, total cost, mean turnover, Q spread, long and short contribution, and compound maximum drawdown. These portfolios do not use the official 5-quintile portfolio contract and are not submission performance.

## Stop and interpretation rules

One fixed graph and one 20-session horizon; no edge/status, horizon, weighting, subset, or portfolio-rule search. Results are descriptive regardless of sign because the relation graph postdates the evaluation period and 2025 is already-read Valid history. Do not fit a combined SN1_H1 + NCMOM20 model, alter SN1_H1, inspect raw targets, run the official Valid evaluator, or claim PIT validity. Report coverage and source limitations alongside every performance summary. If source files or exact mapping do not support the locked contract, stop and report the data failure without relaxing filters.

## Reproducibility and verification

Save code, package versions, input hashes, edge counts, mapping audit, daily and yearly diagnostics, and a concise report. Verify deterministic output, index alignment, no use of signal-day/future return in NCMOM, and feature prefix invariance with the graph held fixed. The edge source's retrospective nature is an intentional assumption, not a leakage test passed. No strategy source, baseline artifact, portfolio contract, release, or submission is modified.
