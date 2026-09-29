# Registered intervention plan — SN1 state persistence

## Lock record

| Item | Frozen value |
|---|---|
| Experiment | `DM-20260928-01` |
| Registered | 2026-09-28 11:39 JST, before candidate P/L |
| Candidate count | 1 |
| Candidate | `SN1_LOW_STATE_EXPIRY_60D` |
| Plan source | [intervention_plan.md](../../experiments/DM-20260928-01/intervention_plan.md) |
| Plan SHA-256 | `d8ce2b465b4ade283ff736f8dc7ea51667eaf397e1a57342c035d002db04db8e` |
| Final pre-metric execution lock SHA-256 | `80317cf1efbfe38e78c44a9f0d039413db0a9d01cf037b48d51da385a286df4b`; [lock file](../../experiments/DM-20260928-01/intervention_execution_lock_v2.md) |
| P/L-blind structure screen | [structural_screen.csv](../../artifacts/DM-20260928-01/intervention-structure/structural_screen.csv) |
| Structural screen manifest | [structural_manifest.json](../../artifacts/DM-20260928-01/intervention-structure/structural_manifest.json) |

The Phase 1 causal/mechanical state audit was frozen before target and P/L access. Phase 2 then measured only the pre-fixed ages and existing H1/H5 diagnostics. This intervention plan was written after those baseline diagnostics and before any candidate P/L; therefore the candidate is **Train-derived and development-data-derived**, not preregistered before all historical P/L and not OOS.

## One fixed rule

For each stock-date, if `low_state < 0` and the latest Low breakout is older than 60 stock trading sessions (`low_event_age_trading_days > 60`), set Low state to exactly zero. At age 60 the state remains active. Then apply the original SN1 precedence and official five-quintile weights. No score-magnitude threshold, new tie-break, or other strategy change is permitted.

## Structural reason

The no-target screen found stale negative Low state and positive High state together in 48.0% of Train stock-days and 71.8% of historical-Valid stock-days. The fixed expiry would expose High state to the unchanged source rule. Its structural cost was already visible without returns: on the full audit panel it changes the final score on 58.7% / 75.5% of stock-days and the official quintile on 59.2% / 58.2% in Train / historical Valid. It also raises the Train exact-zero rate from 8.7% to 17.0%, lowers mean daily unique-score ratio from 91.3% to 82.8%, and raises boundary-tie rows from 6.5% to 14.4%. Historical-Valid tie incidence falls, but the rule is not uniformly cleaner.

The exact 60-session cutoff was fixed from the existing 60-session renewal window and selected without candidate return/P&L. No neighboring age was considered.

## Hypothesis and rejection criteria

Hypothesis: once a negative Low event is over 60 stock sessions old, its tiny remaining negative sign may mask a currently positive High state without preserving useful Low information. Removing only that stale sign could improve score selection.

The plan requires Gross and Net annual contribution to improve in the same direction in both Train and historical Valid, Long Net contribution not to decline in either split, and operational checks to pass. Bootstrap uncertainty is descriptive and does not add a tuning threshold. Cost-only, exposure-only, single-year, or tie-dependent gains do not support the candidate.

## Execution corrections before candidate metrics

Two attempted candidate runs stopped before candidate P/L metrics: first the coverage assertion included label-maturity rows outside the official account window; then a stricter non-missing-target assertion conflicted with the evaluator's row-level missing-target handling. The final driver follows the existing official helper's full target-index alignment and filters reported accounts to the saved official dates. The candidate rule, H1 target, cost, dates, and decision criteria were unchanged. The final source and plan hashes were locked in [intervention_execution_lock_v2.md](../../experiments/DM-20260928-01/intervention_execution_lock_v2.md) before the successful run. The stopped runs are preserved in `artifacts/DM-20260928-01/intervention-results/` and `.../intervention-results-v2` contains the authoritative results.

No other candidate was added. There was no alpha/horizon/threshold search, model refit, paper-data access, session rule, exit grid, or weight change.
