# DM-20260930-02: Event Box structure added to SN1_H1

Status: planned. One finite Train-only comparison; no Valid evaluation or Freeze.

## Hypothesis

The fixed causal Event-Box state adds next-session cross-sectional ranking information to SN1_H1. Candidate A adds directional structure, breakout, box geometry, and age/failure features to the existing side-specific Ridge models. Candidate B adds only `UPSTATE × max(0, -x)` and is run only if A first shows positive ranking and gross-return evidence.

## Why it should work / Why it may persist

The existing SN1_H1 score forecasts high/low breakout event quality, while the Event Box state records whether the price remains in an upward or downward parent structure. A continuing upward structure may distinguish a pullback from a generic fall inside a range. The expected effect is asymmetric: downward structure informs weakness but is not treated as an independent symmetric short alpha. It may fail because the state is sparse, correlated with the existing relative-strength features, or too slow to improve the breakout-event ranking.

## Why it should survive t+1 open

All event state and geometry are computed from raw OHLC observed through signal close `t`, with prior-only ATR and confirmed-at timestamps. The fixed H1 label is the official residual return from `Open[t+1]` to `Open[t+2]`; therefore forecast performance is measured after the next open entry. No `t+1` input is read.

## Expected turnover impact / Leakage risk / Complexity cost

The candidate keeps SN1's event stream, side separation, percentile mapping, and EWMA smoothing, so score changes should be limited to existing high/low breakout events. Turnover may change through altered event ranks and persistence but is not explicitly optimized. Risks include using a future box extreme, backdating confirmation, same-day ATR, adjustment-factor retroactivity, or crossing a listing gap. The Event-Box implementation uses raw OHLC converted into a common share unit with observed split factors, `atr_prior` ending at `t-1`, and resets on missing/invalid OHLC and listing gaps over 20 trading sessions. Complexity is one deterministic state pass plus fixed annual Ridge fits.

## Baselineと変更点

Baseline is the current fixed SN1_H1 route: separate High and Low Ridge fits; same current directional five-feature input; centered cross-sectional target rank; `lambda=1`, minimum 500 mature training rows per side, 2-position label maturity purge; High/Low event percentile scores; High EWMA alpha 0.25, Low EWMA alpha 0.50; fixed `SIDE_SOURCE_SEPARATION` precedence. Candidate A adds 10 Event-Box features to the Ridge inputs. Candidate B adds one `pullback_up` feature to A. All other model, sample, fold, score, and portfolio choices remain fixed. Before candidate metrics, the current baseline path must reproduce its independently rebuilt current-code path bit for bit. The archived DM-20260927-04 H1 file is not a valid baseline reference because it was generated before the split-date ATR correction in commit `5f57b8f` (archived `features.py` SHA-256 `3c2066557ad566556bf9ed6f21910926a36e59979dafef18369090b53ca5dc0a`; current file SHA-256 `d2e4adba62a3c0497d36241c5fde8d7709e727ad7c9b2a01842809964adf46e3`). The correction changed `box_duration` on 2,257 rows, `box_width_atr` on 2,425 rows, and `close_position` on 2,245 rows. Its H1 output is retained only as historical evidence and is excluded from candidate deltas.

## Train-only期間・有限候補・採否基準

Use only Train inputs and `target_1day_train.parquet`, 2008-11-04 through 2016-03-31. Annual expanding evaluation folds are 2011–2016; each model trains only on event rows whose H1 label has matured strictly before that calendar year's first prediction date (two-trading-position purge). These historical Train years have all been inspected before and are descriptive development data, not an independent holdout. There is one baseline reproduction control and at most two fixed candidates: A, then conditional B. Do not execute B unless A has positive pooled delta RankIC, positive pooled delta gross performance and positive mean Q5−Q1 change versus baseline. No parameter or feature search is allowed.

Selection prioritizes temporal net performance and baseline consistency. A candidate can be supported only if its mean RankIC, Q5−Q1, and annual gross performance improve over SN1_H1, gross uplift is positive in at least four of six folds, Net Sharpe is not lower, and the effect is not explained only by turnover/cost. Candidate B must also show positive conditional target-rank information for `UPSTATE=1, x<0` versus `UPSTATE=0, x<0`. Otherwise reject or classify mixed; do not promote from a single year or full-Train Sharpe alone.

## 既知データ・確認期間・過去の失敗

The fixed SN1_H1 model and historical Train results are already known from DM-20260927-04 and prior SN1 development; H1 is a reference, not an untouched control. Event-Box studies through DM-20260930-01 have also inspected all available Train years, including one rejected fixed MR/BO operationalization. That earlier result does not test the present SN1 augmentation. No Valid target, raw target, or Valid evaluation is in scope.

## 検証・実行コマンド

Before scoring, test state-transition and structure persistence on synthetic paths, exact index/finite coverage, deterministic replay, source/leak scan, and future-mutation prefix invariance for the complete Train feature and fitted-prediction path. Rebuild the current SN1_H1 baseline by both fixed code paths and require bitwise equality; record the archived pre-correction H1 source mismatch without using it as a comparison. Verify label maturity, then execute only the registered candidate(s) under the Train-only firewall and `tools/run_bounded.py --seconds 1800`; write input/source hashes, environment, predictions, fold/year metrics, baseline deltas, structural buckets, and audit records into the reserved run. Do not evaluate Valid, Freeze, or extend the trial budget.
