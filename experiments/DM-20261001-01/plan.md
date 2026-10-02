# DM-20261001-01: UP_PULLBACK as one SN1_H1 feature

Status: planned. One fixed Train-only candidate; no Valid evaluation or Freeze.

## Fixed hypothesis

Add only `UP_PULLBACK = I(UPSTATE=1) * max(0, -x)` to the current `SN1_H1` five-feature Ridge inputs. Test whether this single trend-aligned lower-Box pullback feature improves cross-sectional ranking and the official quintile portfolio. This is a targeted follow-up to the rejected broad Event-Box augmentation in `DM-20260930-02`; it does not retest Event-Box features as a family.

The descriptive attribution already observed in `DM-20260930-02` found higher centered target rank for `UPSTATE=1, x<0` than for `UPSTATE=0, x<0` (0.02153 vs 0.00154; 13,686 vs 33,274 rows). Those same Train years and this same bucket have already been inspected. This run is development-history confirmation, not independent OOS evidence.

## Why it may work / persistence / costs / risks

An upward parent structure may distinguish a temporary pullback toward the lower Box edge from an otherwise similar lower-Box observation without a positive structure. If so, the state interaction can add ranking information to SN1's breakout-event score. The signal is measured at close `t` and predicts the fixed H1 residual return from `Open[t+1]` to `Open[t+2]`, so it must persist beyond the next open to help.

The feature may add little beyond SN1's existing directional inputs, may be sparse or missing outside confirmed Boxes, and may change rankings enough to raise turnover. Event state, box boundaries, and `x` must use the existing causal implementation exactly: raw OHLC in split-safe share units, prior-only ATR, and signal-date confirmations. No alternate formula or threshold is allowed.

## Baseline and candidate

- Baseline: current `SN1_H1` route, separate High/Low Ridge, existing five directional inputs, centered cross-sectional target rank, lambda 1, minimum 500 mature event rows per side, two-position H1 maturity purge, fixed percentile score mapping, source separation and side-specific smoothing, official quintile weights, and one-way 10 bp transaction cost.
- Candidate: the same route and settings with exactly one additional Ridge input, `pullback_up` (reported as `UP_PULLBACK`); its value is the existing Event-Box implementation of `event_upstate * max(0, -event_box_position)`. No other Event-Box input or model change is permitted.
- Before fitting the candidate, the two current-code baseline paths and the prior `DM-20260930-02` baseline prediction must reproduce bit for bit. Any failure stops the run before candidate evaluation.

## Train-only window and run budget

Use the five staged Train files only, from 2008-11-04 through 2016-03-31. Use the existing annual expanding prediction folds 2011–2016; each fold trains on mature High/Low event rows with the existing two-trading-position purge. The 2016 fold ends on 2016-03-31 and has 61 sessions, so it is explicitly partial. All periods are known development history.

There is one baseline reproduction control and exactly one candidate fit (`UP_PULLBACK_SN1_H1`); `max_trials=1`. No rescue candidate, feature or threshold search, alternate horizon, or post-result tuning is allowed. Valid and raw-target files must not be opened.

## Primary decision rule

Candidate support requires all three pooled 2011–2016 deltas versus current `SN1_H1` to be strictly positive:

1. Mean RankIC.
2. Annualized gross return.
3. Daily Q5−Q1 return spread.

If any one is nonpositive, reject this fixed feature candidate. Also report fold/year deltas, the pooled comparison with partial 2016 removed, gross contribution from Long and Short, turnover/cost, and attribution. A SUPPORT decision additionally requires that the apparent pooled improvement remains directionally positive without 2016, that Long/Short and net/gross comparisons do not show an offset or cost-only explanation, and that the UPSTATE lower-Box attribution moves in the hypothesized direction. If the primary gates pass but these checks are mixed, record MIXED rather than promote the candidate.

## Required audits and outputs

Rebuild features and scores after mutating every post-cutoff Train input, including the Train target, and require exact prefix equality for features, baseline score, and candidate score. Check the feature definition and source/leak scan; baseline parity; fold maturity; prediction coverage; exact indexes; finite scores; deterministic candidate replay; Train-only firewall; and official accounting/cost conventions.

Save `plan.md`, `config.json`, and `run.json` with the run snapshot; baseline reproduction and feature-causality/prefix audits; pooled, fold/year and incremental metrics; four-bucket attribution including quintile and Long/Neutral/Short migration and gross contribution changes; daily accounts; and a final decision report. Preserve the failure run if the baseline gate fails.
