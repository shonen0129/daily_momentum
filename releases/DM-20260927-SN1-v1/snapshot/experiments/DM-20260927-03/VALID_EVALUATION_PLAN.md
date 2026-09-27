# Valid Evaluation Plan — D vs SN1

**Status:** preregistered before any Valid target/P&L read
**Experiment lineage:** `DM-20260927-03`
**Date:** 2026-09-27 (Asia/Tokyo)
**Purpose:** one controlled comparison after freezing the existing SN1 implementation. This is a Train-derived hypothesis test, not a claim that Train was unseen.

## Frozen candidates

Exactly these two scores will be evaluated, from one shared fitted prediction stream:

1. `D_LOW_FAST_ONLY`
2. `SIDE_SOURCE_SEPARATION` (`SN1`)

No B00, BOX_ORIGINAL, SN2, blend, or other candidate enters Valid. `submission.predict()` continues to return SN1. The evaluation adapter exposes D and SN1 together only so the preregistered comparison uses the identical upstream model and event stream.

## Frozen implementation and inputs

- Source of truth: `stock_comp_2026/strategies/dm_variable_box_breakout/submission.py` and `sn1.py`.
- High / Low EWMA alpha: `0.25 / 0.50`.
- Upstream yearly High/Low Ridge, event definitions, features, universe, training windows, two-trading-day purge, and one-way cost remain as frozen in the source.
- The existing `1e-12` raw reconstruction cleanup remains unchanged.
- Candidate scores are reconstructed from the formal submission's common base prediction stream through `sn1.rebuild_from_base_score()`.
- Ranking is the repository evaluator rule: sort `(Date, Code)`, `rank(method="first")`, then `qcut(5)`; weights are `(quintile - 2) / daily_name_count / 1.2`.
- One-way transaction cost is `0.001` of absolute weight change. Annualization is 252 signal days.
- Only `target_1day_valid.parquet` is opened as an outcome, once, after hash verification and candidate predictions. Valid target is never passed to feature construction, model fitting, score generation, or candidate selection. `raw_target_*` is never opened.

## Evaluation definitions

The target index defines the official signal-date universe. All target rows and dates are retained as the local evaluator retains them; missing labels contribute no stock-level P/L or cost, and grouped daily sums are used. No extra purge or label trimming is added.

Primary metrics use the existing `research.evaluation` definitions, matching Train reports: daily gross/net/cost/turnover and RankIC; annual return is daily mean × 252; annualized volatility is sample standard deviation (`ddof=1`) × √252; Sharpe uses sample standard deviation × √252; Max Drawdown is additive cumulative net return drawdown. The local evaluator's own SR (`compute_sr`, population standard deviation) is also recorded as a compatibility check, not substituted for the research comparison.

Overall accounting uses the existing `research.evaluation.daily_account()` and `research.evaluation.metrics()` functions. Side Gross/Net/SR uses the existing clipped Long/Short weight-turnover accounting convention (`0.001 × sleeve weight change`) and must reconcile exactly to total daily Net. Long–Short daily-return correlation is reported.

Required overall metrics for both candidates: annual Gross and Net return, Gross and Net SR, Gross and Net volatility, average daily turnover, annual transaction cost, additive Max Drawdown, RankIC, Long Gross/Net/Net SR, Short Gross/Net/Net SR. Also record exposure, label coverage and evaluator-compatible SR.

### Subperiods

Report the full Valid period and every natural calendar-year bucket in the target index. First/last incomplete calendar years are labeled partial. No result-dependent date boundary or selected regime split is allowed. Within-year metrics use the same definitions and start drawdown at that calendar bucket's first signal date.

### Paired uncertainty

For `SN1 − D`, reuse the existing paired circular block bootstrap exactly: 20 consecutive signal dates per circular block, 1,000 replications, seed `20260925`. Report 95% intervals for ΔNet SR and Δannual Net return and the positive-resample fraction for ΔNet SR. Bootstrap is uncertainty description, not OOS proof.

## Score and operational checks

Before using the target, report for each score: finite values, unique `(Date, Code)` index, exact-zero rate, duplicate-score row rate, boundary-crossing tie row rate, mean/min daily unique-score ratio, and populated official quintiles. After opening the target, confirm exact target/prediction coverage, finite official weights, five populated quintiles per date, long/short/gross/net exposures, and direct compatibility with repository `compute_weight`, `compute_pl`, and `compute_sr` functions. Zero/tie statistics are descriptive because the repository contains no numerical minimum for them.

## Frozen decision rules

No absolute Sharpe target is set from Train. Use only the relative comparison and these predeclared categories:

- **FAIL:** a freeze/hash, finite-score, unique-index, exact-coverage, official-five-quintile, weight, or evaluator-contract check fails; or both full-period ΔNet return and ΔNet SR are below zero.
- **PASS:** all operational checks pass; full-period SN1 Net return and Net SR both exceed D; at least one of Gross return or Gross SR improves; Long Net contribution and Long Net SR both improve; and SN1 has positive ΔNet return in a majority of the calendar-year buckets. The paired 95% intervals are reported; a lower bound at or below zero makes the result **MIXED**, not a pass.
- **MIXED:** all other cases, including disagreement among Net return/SR, gross/cost-only improvement, Long/Short structural disagreement, substantial year dependence, or bootstrap uncertainty crossing zero.

Short performance is reported but a negative Short sleeve does not by itself fail the total portfolio. No claim of Short alpha improvement or Short × Night repair is permitted. Day/Night is not used for portfolio construction or the decision; no session-specific strategy is evaluated.

## One-run and post-result lock

The release lock contains the plan, manifest, configuration, code, and zip hashes. The runner checks them and the frozen source commit before creating an exclusive one-time run sentinel. An existing sentinel aborts the run. After this evaluation, no parameter, threshold, feature, event, ranking, tie, holding, side, session, or candidate change is allowed. The only permitted follow-up is reporting this fixed result and the resulting PASS/MIXED/FAIL decision.
