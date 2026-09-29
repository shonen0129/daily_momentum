# DM-20260928-01: SN1 entry/state survival audit

Status: planned. This is post-submission paper research. Train and the previously opened historical Valid are development history. No paper-period data is permitted.

## Hypothesis

SN1's very long quintile and sleeve persistence may be caused by deterministic carry and ranking mechanics rather than persistent predictive information: after a High/Low event, the EWMA state decays without an explicit expiry, and the official portfolio ranks that state relative to the daily cross-section. In SN1, any negative Low state takes precedence over High state, even when the Low magnitude is numerically tiny.

The audit separates (1) event-date Entry information, (2) carried High/Low state, and (3) official quintile/sleeve membership. No new predictor is introduced.

## Why it may work / why it may persist

Repeated same-side events can renew a state with newly observed event information. In periods without renewal, exact EWMA recurrence predicts geometric state decay. If similarly sourced states decay at a common rate across names, cross-sectional ranks can remain unchanged as absolute scores and cross-sectional dispersion shrink together. These are mechanical hypotheses to measure; persistent membership alone is not evidence of persistent predictive value.

## Why it should survive t+1 open

No strategy change is proposed in this phase. Existing H1 Ridge labels run from Open(t+1) to Open(t+2); state persistence will be tested separately from fixed-lag future residual information. Any paper intervention requires a simple, deterministic, point-in-time rule and independent future paper observations.

## Expected turnover impact / leakage risk / complexity cost

The audit itself changes no signal, portfolio or turnover. Data access is limited to existing H1 model artifacts, historical Train/old-Valid feature inputs, saved H1 score files, and PIT listed-info metadata. It does not read target parquet, raw target, or paper data in the P/L-free structural phase. Later descriptive P/L reads only the already-opened Train and historical Valid targets. Main leakage risk is event/state age incorrectly crossing a listing reset or split boundary; replay parity and explicit segment keys address that risk. Complexity is one bounded audit driver plus fixed descriptive summaries.

## Baseline and fixed specification

Baseline/reference: `SN1_H1` from experiment DM-20260927-04, authoritative run `run-20260927T101500Z`. High EWMA alpha=0.25, Low alpha=0.50, Ridge lambda=1.0, original event/feature/universe definitions, SN1 source precedence, official five quintiles/weights, 10 bps one-way cost. No upstream or portfolio behavior is modified.

## Train / historical Valid / finite study budget

1. Phase 1: reconstruct fixed H1 event stream/state from stored H1 models and feature inputs; write Date×Code table and mechanical-only summaries. Do not read any target or calculate P/L/RankIC.
2. Phase 2: after locking the Phase 1 table/hash, run only the requested fixed age/event-renewal attribution and fixed lags 1/5/20/40/60 on Train and historical Valid separately. No threshold selection.
3. Phase 3: use Phase 1–2 evidence to preregister at most three exact state interventions and hash `STATE_INTERVENTION_PLAN.md` before candidate P/L. Candidate count may be zero. Evaluate only those fixed candidates against SN1_H1; no follow-on search.

Evaluation years and splits: Train 2011-01-04–2016-03-29 (including the already known 2016 partial), and historical Valid 2016-04-01–2026-07-31, previously opened and treated as development. No paper period. H5/H20 are not re-evaluated; their existing study already found no stable persistence/alpha benefit.

Maximum candidate count: 3; parameters: none. No alpha, age-cutoff, exit, score, threshold, lambda, feature, event, horizon, cost, portfolio-weight, session or regime search. Fixed descriptive age and lag bins are those named in the user request.

## Selection / rejection rules

Historical SR is descriptive, never an acceptance target. Candidate support requires the registered structural mechanism and P/L mechanism to agree, Train and historical Valid to point in broadly the same direction, gross/Long quality to remain intact, persistent Short loss or predictive decay to improve, and no single-year dependence, excessive turnover/cost, exposure drift, or regulation deterioration. Reject candidates that only exploit the retrospective cutoff, weaken persistent Long gains, depend on zero/tie structure, or fail to reproduce in historical Valid. If none survives, retain SN1_H1 only.

## Known data and prior experiments

Prior H1/H5/H20 results in reports/DM-20260927-04 establish that longer targets barely alter rank persistence and fail to provide period-stable forward prediction evidence; H1 is the fixed reference. Existing persistent-spell P/L is descriptive and is not causal evidence for an exit age. All Train and historical Valid performance have already been observed; neither is OOS. Future paper data is the only forward OOS.

## Reproducibility and verification

First phase reuses H1 models and saved H1 scores. Require exact reconstruction checks on available saved-score indexes, official quintile/weight replay, unique Date×Code keys, finite inputs, PIT joins, state recurrence check, and manifest/file hashes. The phase-1 run must explicitly attest `target_read=false`, `pnl_calculated=false`. Later phases use the existing official evaluator and fixed cost conventions. Record Git HEAD, dirty worktree, script/config/model/input/output hashes, Python/library versions, periods and exact command. Do not alter submission code or paper freeze.
