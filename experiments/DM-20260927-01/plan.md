# DM-20260927-01: Candidate C Asymmetric EWMA

Status: completed. This was a fixed diagnostic on previously seen Train data, not model selection or OOS evidence.

## Hypothesis

`A_LOW_NO_CARRY` may have improved gross risk-adjusted returns while worsening net results because deleting all Low carry changes ranks discontinuously, expands score-zero Q1 membership, and increases rebalancing cost. A continuous asymmetric decay may retain useful recent Low information while avoiding some of that turnover. High and Low event raw scores and their signs remain unchanged.

## Why it may work / persist / survive the next open

Existing event-age diagnostics show persistent High-side contribution and weaker aged Low-side contribution. A faster but nonzero Low decay can reduce stale Low influence without abruptly removing the entire Low state. Any signal used here was already produced causally from information available by signal date `t`; the EWMA uses only current and previous rows within the existing listing segment. The evaluated target remains the existing `t+1 Open -> t+2 Open` residual return. This is a descriptive known-Train check, not evidence of independent out-of-sample persistence.

## Fixed candidate and comparisons

One asymmetric rule only: `alpha_high=0.15`, `alpha_low=0.50`; baseline score alpha is `0.25`. Apply the same fixed pair to saved BOX and saved B00 raw event score streams. Compare exactly `B00_BASE`, `BOX_ORIGINAL`, `A_LOW_NO_CARRY`, `C_ASYM_EWMA`, and `C_B00_ASYM_EWMA`. No alpha search, retraining, feature addition, gate, threshold, holding, portfolio, timing, cost, or tie-break change.

The carry update, first-row initialization, segmentation, and signed High-plus-Low merge follow the existing `adjust=False` listing-segment EWMA. Candidate C is computed by separately smoothing the positive High raw stream and negative Low raw stream, then summing them. It is causal because no future row is read.

## Train-only period and evaluation

- Source Train signals: `artifacts/DM-20260925-03/run-20260926T063602Z/predictions/signals.parquet`.
- Train target and point-in-time sector data only: `stock_comp_2026/input/target_1day_train.parquet` and `listed_info_train.parquet`.
- Signal source span: 2008-11-04 through 2016-03-31.
- Descriptive evaluation: 2011-01-04 through 2016-03-29, preserving the existing two-date annual tail purge.
- Annual rows: 2011, 2012, 2013, 2014, 2015, and partial 2016-01-04 through 2016-03-29. Also report pooled ex-2016.
- One-way cost: 10 bps; annualization: 252; official five-quintile construction and equal gross sleeve normalization remain fixed.
- No Valid files or targets are opened.

## Pre-registered diagnostics and interpretation

Report gross return/volatility/Sharpe, common and cross-sectional selection components, turnover/cost/net performance, rank autocorrelation, Q1/Q5 retention and entries/exits, score-zero and code-order tie diagnostics, PIT sector concentration, source-age sleeve attribution, exposure, and yearly metrics. Explain net change as gross change less cost change. Compare C against A directly and compare BOX-C against same-rule B00-C. No bootstrap is introduced.

Candidate C is only described as promising if it improves Net Sharpe over A, reduces turnover and score-zero Short weight, reduces mechanical code-order dependence, points in the same direction ex-2016, and does not make 2011 or 2015 extreme. This does not select an optimal alpha. Any mixed or failed result is retained as such; no post-result trial is permitted.

## Reproducibility and verification

The run records source and Train-data hashes, git commit, fixed parameters, library versions, source artifacts, cost, dates, and outputs. Reuse the saved prediction stream and repository account/weight helpers; do not retrain Ridge or regenerate features. Focused tests check the recurrence, signed additivity, and future-prefix invariance. Run `make check`, focused tests, and the bounded Train-only driver. Do not run Valid evaluation.

## Known data and prior results

All periods in this plan are already known Train. `DM-20260926-01` reported BOX Net Sharpe about 0.7851, Gross Sharpe 0.9580, turnover/day 0.0319, and A Low-no-carry Net Sharpe about 0.7389, Gross Sharpe 1.0236, turnover/day 0.0459. These are diagnostics and not an untouched holdout. Prior report: `reports/DM-20260926-01/EXPERIMENT_RESULTS.md`; prior short composition and tie audit: `reports/DM-20260926-01/AUDIT.md`.

## Command

```sh
.venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.box_asym_ewma --config artifacts/DM-20260927-01/<run-id>/config.json --output artifacts/DM-20260927-01/<run-id>
```
