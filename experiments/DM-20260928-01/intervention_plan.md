# State intervention plan — DM-20260928-01

## Registration

- Registered at: 2026-09-28 11:39:14 JST, before any candidate P/L run.
- Structural screen artifact: `artifacts/DM-20260928-01/intervention-structure/`
- Structural screen result SHA-256: `234fe5236fb031198fda2fef572f3ecf8f39b67c2a630cf76f341ea1b8be4270`
- Structural screen driver SHA-256: `8dba068cf329555b94d24141e89833d47a4abaf67f383c4beba1a5dccfe5e4d9`
- Fixed evaluation driver SHA-256: `5490f862964171c7f81723a5ee55b4a738186617e168a4aa9d5650b7024a0e4e`
- Final plan/code hash lock: 2026-09-28 11:40:32 JST.
- The screen used only the locked Phase 1 state table. It did not read target, return, account, or paper data.
- Candidate count is fixed at **one**. No candidate may be added after this file is hashed.

## Candidate: `SN1_LOW_STATE_EXPIRY_60D`

### Fixed transformation

At each stock-date, if `low_state < 0` and the latest Low event is more than 60 stock trading sessions old, replace that `low_state` with exactly zero. Keep every other High/Low state unchanged. Then apply the existing SN1 source-precedence code and the official `rank(method="first")` five-quintile weights without any other change.

The age condition is strictly `low_event_age_trading_days > 60`; day 60 remains active. There is no score-magnitude threshold. The 60-session boundary is fixed once because the existing causal audit already uses a 60-session renewal window; it is not selected from candidate performance.

### Hypothesis

The Low state decays recursively but can retain a tiny negative sign for a long time. Under SN1, that sign has precedence over a positive High state, even when the latest Low event is stale. Expiring only this stale negative Low state may let currently positive High information determine cross-sectional ordering again.

### Why it may fail

The stale Low state may still carry useful information; removing it can reorder much of the book, raise turnover and cost, increase zero/tie dependence, or damage profitable persistent Long holdings. The structural screen already shows broad rank movement, so this is a deliberately falsifiable challenger rather than an assumed improvement.

### Fixed evaluation

- Baseline: saved `SN1_H1` score and account.
- Candidate: the single transformation above.
- Development splits: existing Train and already-open historical Valid, shown separately.
- Target: the existing H1 residual-return artifact only, for accounting and RankIC; no model fit or strategy branching.
- One-way transaction cost: 10 bps under the existing official accounting helper.
- Report overall and calendar-year return, Net/Gross SR, volatility, drawdown, turnover, cost, RankIC, Long/Short, paired gross/cost/net decomposition, regulation/score quality, and the existing circular paired bootstrap (20 trading-day blocks, 1,000 repetitions, seed `20260908`).
- The candidate is supported only if gross and net annual contribution improve in the same direction in both development splits, Long net contribution does not decline in either split, and operational/score checks pass. Otherwise reject it. Bootstrap uncertainty is reported and does not create a new tuning threshold.
- A rise in performance that comes only from exposure drift, cost accounting, a single split/year, or increased zero/tie dependence is not support.

## Invariants

No model refit, event/feature/universe change, High/Low alpha change, state smoothing, threshold search, holding/exit grid, session-specific rule, weight change, tie-break change, candidate blend, or paper-data access. There is no use of future holding membership to make decisions. Valid and Train remain development data; any result is not OOS evidence.

## Hash lock

The SHA-256 of this file is stored in the adjacent `intervention_plan.md.sha256`. Candidate P/L evaluation is permitted only after that hash is written and verified. This file and hash are not to be amended after the evaluation starts.
