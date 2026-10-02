# DM-20260930-01: Event-driven box MR / BO first trial

Status: completed; the fixed candidate was rejected. This was a first operationalization of `docs/strategies/投資戦略仮説0930-01.md`, not a production candidate or Valid evaluation.

## Hypothesis

Once a compact range is confirmed using only past daily OHLC, a mean-reversion trade entered near a fixed box edge has a higher take-profit-first rate and positive net episode expectancy than the driftless first-passage null. After a breakout beyond an ATR buffer, the old box should stop producing MR trades; a single ATR-reversal lifecycle can identify the next box and a breakout continuation episode.

## Why it should work / Why it may persist

Fixed, as-of box boundaries separate a genuine range from a range drawn retrospectively around the eventual price path. A first-passage test against the calculated random-walk probability controls for the mechanical center-return rate. If an edge persists, it may reflect liquidity replenishment at established boundaries. It may fail because a compact range can be an arbitrary slice of a random walk, and overnight gaps can jump past stops or targets.

## Why it should survive t+1 open

Signals use the close and OHLC available through signal date `t`; entry is the next session's raw Open. We measure the full post-entry first-passage episode, including the entry gap. We separately retain the official `t+1 Open -> t+2 Open` target for one-day descriptive RankIC; it is not used to set state or exits.

## Expected turnover impact / Leakage risk / Complexity cost

Sparse edge entries should reduce turnover versus daily rebalancing. One 20-session seed rule and one fixed transition rule keep the first candidate small. Main leakage risks are backdated box confirmation, using same-day ATR, using an extreme before it is observed, and treating close-known exits as same-close fills. Every box stores `confirmed_at`; all signal inputs use prior ATR; same-day TP and SL resolves to SL; timeout exits at the following Open.

## Baselineと変更点

Implement a new event-state engine for this experiment. The user selected the seed rule: a prior 20-session range becomes the initial BOX at `t` only if its prior-only width is 0.5–3.0 times prior ATR20 and `Close[t]` is inside its fixed boundaries. Thereafter use one fixed configuration: `k_SL=0.5`, `k_BO=1.0`, `k_fail=0.5`, reversal `m=1.0 ATR`, formation timeout 40 sessions, MR entry at `|x|>=0.8`, target at `x=0`, stop at `|x|=1.2`, and maximum hold 5 sessions. At most one MR trade per side per box. A missing or invalid OHLC row resets that security to SEARCH and starts a fresh history window; missing prices are never filled. A one-time 20-session Donchian breakout is the simple BO reference; the MR analytical reference is the driftless first-passage probability `p0`. No parameter search, fitted model, Box Score, or integration weighting.

## Train-only期間・有限候補・採否基準

Use only Train price panels and `target_1day_train.parquet`, dated 2008-11-04 through 2016-03-31. Report annual event outcomes for 2011–2016, with episodes assigned to the entry year and an end-of-window episode cutoff. There is one fixed state-machine configuration (`max_trials=1`, seed 20260930). Previous Train periods are already well studied; this is descriptive and not an independent holdout. Do not tune after seeing results.

MR continues only if the pooled cost-adjusted episode expectancy is positive, `p-p0` is positive with a date-clustered 95% interval above zero, and the direction of the effect is not confined to one year. BO is assessed separately against the registered Donchian reference. Do not integrate MR and BO unless both legs show independent evidence. If these gates fail, reject this operationalization and stop.

## 既知データ・確認期間・過去の失敗

All available Train outcomes through 2016-03-31 have been used by prior experiments, including variable-duration boxes. No Valid data or labels are opened. Relevant prior work: `DM-20260924-10` and `DM-20260925-03` tested different fixed/variable box predictors, not this confirmed-at event state machine or MR first-passage episodes. The split-safe ATR regression `DM-20260929-01` is a relevant implementation correction, not evidence for or against this hypothesis.

## 検証・実行コマンド

First validate the state transitions on synthetic paths and future-mutation prefixes. Then run the fixed Train-only event study behind `research.firewall` and `tools/run_bounded.py --seconds 1800`. Save feature/state coverage, event outcomes, annual summaries, null comparison, source/data hashes, and the firewall audit in the run. Valid evaluation and freeze are outside scope.
