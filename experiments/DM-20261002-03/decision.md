# DM-20261002-03: 2025 NCMOM20 retrospective diagnostic archive

## Origin and scope

This archive contains the fixed 2025 retrospective backtest requested for `DM-20261002-02`, executed with the 2026.09 current major-customer graph held constant under the user's stability assumption. During finalization, the shared workspace's `DM-20261002-02` plan/config were changed to a separate 2024 diagnostic. Those files were left untouched, and the 2025 artifacts were copied and re-run under archive ID `DM-20261002-03`.

The original execution lock records the pre-result plan hash `5eceb142…` and config hash `8fed7f9e…`. The recovered source config copy matches its original hash. The recovered plan text was reconstructed from the fixed scope but does not match the original recorded plan hash; this archive limitation is disclosed in the report and input manifest.

## Fixed run

- Period: 2025-01-04 through 2025-12-30 inclusive; 243 trading dates (2025-01-06 to 2025-12-30).
- Network: 609 `confirmed` primary-EDINET listed-to-listed `major_customer` edges, supplier to customer; no fuzzy code matches.
- Feature: equal-weight mean of prior 20 finite customer `raw_return - beta * TOPIX` returns, ending at `t-1`; missing if no complete customer window.
- Baseline: saved fixed `SN1_H1` Valid scores, no refit or blending.
- Target: official `target_1day_valid.parquet` `Return`, read for 2025 after the original lock; no `raw_target` read.
- Candidate fits: 0. Official evaluator, release, and SN1_H1 modifications: none.
- Reproduction after archiving used identical data, graph selection, feature, dates, cost and portfolio rules to calculate conditional RankIC for groups with at least three covered names and to use valid-date denominators. It was not a variant search.

## Decision

**MIXED; no robust incremental signal established and no NCMOM20 candidate.** Pooled NCMOM20 RankIC was +0.0289 (HAC-5 t 1.56) and Q5−Q1 +4.55 bp/day (t 0.49), below same-sample SN1_H1 RankIC +0.0328 and Q5−Q1 +12.91 bp/day. Conditional RankIC was positive in SN1 Q1/Q2, negative in Q3, near zero in Q4, and unavailable in Q5; daily cross-sections were small. The costed Q5-long/Q1-short proxy had net Sharpe −0.33 and annualized net return −3.85%, with only 2.22% basket coverage and 0.380 daily turnover.

Current-graph persistence to 2025 is a hindsight assumption; it does not overturn the separate Train-period `PIT INSUFFICIENT` result. The 2025 period is already-read historical Valid/development data, not an independent OOS holdout. No entry was added to `experiments/GRAVEYARD.md` because no candidate strategy was evaluated and rejected.

## Evidence

- [2025 report](../../reports/DM-20261002-03/REPORT.md)
- [Archive plan](plan.md), [current archive config](config.json)
- [Reconstructed source plan](source_plan.md), [hash-matching source config](source_config.json), [source lock](source_pre_result_lock.json), [same-spec reproduction lock](reproduction_lock.json)
- [Input and artifact manifest](../../reports/DM-20261002-03/input_manifest.json)
- [Daily results](../../reports/DM-20261002-03/ncmom20_daily.csv), [matched comparison](../../reports/DM-20261002-03/ncmom20_vs_sn1_matched.csv), [conditional summary](../../reports/DM-20261002-03/ncmom20_conditional_sn1.csv)

Valid access: target values were accessed as explicitly requested for a retrospective diagnostic. `valid_is_holdout=false`; the official Valid evaluator was not run.
