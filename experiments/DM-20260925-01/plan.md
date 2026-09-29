# DM-20260925-01: √L-normalized box duration: one conditional Phase 1 retest

Status: planned. This is the single duration-definition correction authorized by the DM-20260924-11 audit. It is descriptive research on already-seen Train and is not eligible for candidate selection or adoption.

## Hypothesis

The existing duration selects the longest L for which `Range(L)/ATR20 < 3`. In DM-20260924-11, the qualifying high-event duration had median 5 observations and 87.2% were at or below 10, leaving variable-duration structure weakly identified. Normalize range by `sqrt(L)` and choose the longest qualifying window to test the pre-registered alternative definition once.

## Why it may work / why it may persist

Dividing range by `sqrt(L)` scales the admissible range for window length and may allow the duration statistic to distinguish compact boxes from short windows without simply favoring shorter L. The threshold remains fixed at 3.0 and the candidate window set remains `{5, 10, …, 120}`; no threshold or window search is allowed. Any apparent result remains subject to known-Train overfit and is not evidence of independent persistence.

## Why it should survive t+1 Open

All corrected box state uses raw High/Low and prior ATR20 through t−1. The breakout event is finalized at t Close; entry remains t+1 Open and exit remains t+2 Open. Day/night returns are diagnostics only. A three-cutoff future-mutation audit checks all changed box-state columns before interpreting results.

## Expected turnover impact / leakage risk / complexity cost

Changing duration, corresponding width, and close-position can change Ridge ranks and portfolio weights. Compare the fixed six blend/EWMA score paths and report weight deltas, gross, turnover, exact existing 10bps cost, and net. The only changed feature logic reads prior raw price data and ATR20; adjustment factors only convert share units. Run source firewall plus future-mutation prefix checks at 2010-12-30, 2012-12-28, and 2015-12-30. Complexity is one scalar normalization and a fixed 24-window loop.

## Baseline and change

* Baseline: B00, plus the rejected BOX_RIDGE_001 phase-1 definition and its frozen diagnostic outputs in DM-20260924-11.
* Change: `CR(t,L) = (prior High max − prior Low min) / (prior ATR20 × sqrt(L))`; corrected `box_duration` is the largest L in `{5,10,…,120}` with `CR < 3.0`. `box_width_atr` is the selected range / prior ATR20 and `close_position` uses the selected prior box and t−1 Close.
* Fixed: all other four original Ridge feature definitions, annual expanding Ridge lambda 1.0, centered target rank, high-event train/score population, official t+1 Open→t+2 Open target, B00 Short score, transaction costs, purge, blend `{0,.5,1}`, EWMA alpha `{.25,1.0}`.
* Diagnostic only: volume, upper-touch density, t-close timing comparator, event-only feature metrics, duration distribution, matched same-date overnight control.

## Train-only period, finite candidates, and decision criteria

Use previously seen Train 2008-11-04–2016-03-31, annual expanding folds 2011–2016, two-day purge, and the established final-two-signal-date year-end exclusion. 2011–2015 are full-year diagnostics; 2016 is a separate partial stub. Six score paths are fixed: BOX blend 0/50/100% × EWMA alpha .25/1.0. There are no threshold, feature, target, or model parameter alternatives. Do not adopt a candidate from pooled Sharpe. Assess event-only RankIC/HAC t, Q1–Q5 and annual signs, whether BOX 100% moves weights, and baseline differences in gross/net/cost/turnover by year. If the modified event-only structure is still weak or inconsistent, stop the one-day BOX track without additional duration or model rescue trials. Phase 2 does not run automatically.

## Known data and prior result

All evaluation periods have been seen in DM-20260924-10 and DM-20260924-11. The original BOX_RIDGE_001 was rejected: ΔNet SR approximately +0.0028 with its 95% interval crossing zero and ΔRankIC about +0.00007. Phase 1 found pooled event-only prediction RankIC +0.0117 (HAC5 t +0.72), while the alpha .25 100% BOX path moved only 2.96% of weights and improved annual Net by +0.03%. The duration concentration triggered this one and only pre-registered correction. No Valid or unseen interval will be opened.

## Verification and command

Use the unmodified competition feature/model implementation for all non-duration features; the corrected duration lives in the research-only `box_sqrt_duration_features.py`. Check unchanged columns bitwise against DM-20260924-10, verify B00 score bitwise against DM-20260924-11, rerun Ridge deterministically, verify official Long/Short account reconciliation, Train firewall, and three-cutoff future mutation of the four corrected box-state outputs. Execute only the six registered cells with:

```sh
tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.box_sqrt_duration_phase1 --config artifacts/DM-20260925-01/<run_id>/config.json --output artifacts/DM-20260925-01/<run_id>
```
