# NH_REV_001 — NO-GO / CLOSED

Experiment: DM-20260925-02. Frozen release: NH_REV_001-v1. One registered candidate, one completed Train diagnostic and one completed frozen Valid evaluation. No model fitting, parameter search, BOX rescue or next phase.

## 事実

| Event-only metric | Train | Valid | Frozen Valid requirement |
|---|---:|---:|---|
| Raw RS60 mean daily RankIC | -0.038625 | -0.001195 | ≤ -0.02 |
| Raw RS60 HAC(5) t | -2.923 | -0.127 | ≤ -1.645 |
| Negative-direction Hit | 54.72% | 49.68% | descriptive |
| Raw quintile monotonicity | -1.000 | -0.100 | ≤ -0.5 |
| Raw Q5−Q1 target/day | -0.13973% | -0.02428% | < 0 |
| Negative-score RankIC | 0.038625 | 0.001195 | ≥ +0.02, same signal |
| Eligible daily ICs | 689 | 1554 | ≥252 |

score is permanently `-relative_strength_60`. Negative Primary thresholds refer to the original RS60; they do not require negative IC for the negative score. Daily statistics require five finite events, averaging days equally. Quintiles are ordered from low to high in the stated variable. Raw Q5−Q1 and score Q5−Q1 are not exact negatives because the inherited quintile boundaries allocate unequal counts and Code-based tie breaks.

Valid covers supplied 2016-04-01–2026-07-31 feature/target rows, with the last two signal dates of each year/split excluded from metrics, as registered. Full-year negative IC fraction was 44.44% (4/9 years; required ≥60%). Removing the most supportive 1% daily ICs leaves IC +0.008223 (required ≤-0.01). Removing the largest absolute 1% daily Q5−Q1 spreads leaves +0.01350%/day (required <0).

Train-only injection diagnostics: B00 Net SR 0.819703 → 0.833562, Δ+0.013859; annual Net Δ+0.0350 percentage points; average absolute weight difference 0.00005655 and 3.09% of stock-days changed. These known-Train figures are implementation diagnostics, not adoption evidence. B00 Short raw score is unchanged, but global ranking indirectly changes some final short weights; this is measured and no Short-policy alternative was tried.

### Valid quintiles (mean residual target per day)

| Order | Raw RS60 | score=-RS60 |
|---|---:|---:|
| Q1 | 0.00907% | -0.02374% |
| Q2 | -0.03930% | -0.04240% |
| Q3 | -0.06213% | -0.03870% |
| Q4 | -0.03875% | -0.06402% |
| Q5 | -0.01521% | 0.01891% |

## 解釈

The negative effect seen on Train did not reproduce at the registered practical magnitude on this Valid split. Valid IC is near zero, and the non-monotonic quintiles plus unstable trimmed spread do not support GO. A negative untrimmed raw Q5−Q1 alone does not override the failed primary criteria. This is a failure of the registered single-feature hypothesis test, so portfolio injection is not investigated as a rescue.

## 未確認事項

This Valid was already evaluated under prior releases and used in prior research ideation. It is **not untouched independent OOS**. The request for genuinely independent confirmation therefore cannot be satisfied with the supplied data. That limitation does not rescue the numerical failure. This run does not prove that every relative-strength reversal hypothesis is false; different horizons, filters and execution rules were intentionally untested. Economic causality and a new untouched future sample remain unconfirmed.

## 判定

**NO-GO / CLOSED** under the frozen criteria. Failed criteria: IC magnitude, HAC evidence, quintile monotonicity, annual stability, IC robustness, spread robustness. Train direction, sample size and untrimmed spread direction pass; all required gates had to pass. No portfolio SR summary was generated for Valid. Mechanical daily ledgers and weights were saved solely to preserve the requested audit trail. No RS20/40/80/120, filters, additional features, BOX, interactions, Short changes or next phase were attempted. PORT_SHORT_001 remains deferred.

## Artifacts and verification

- [Frozen decision memo](../../releases/NH_REV_001-v1/snapshot/decision.md), [fixed config and gates](../../releases/NH_REV_001-v1/snapshot/config.json), [Freeze manifest](../../releases/NH_REV_001-v1/manifest.json).
- [Train report](TRAIN_REPORT.md), [Train annual event metrics](train_annual_metrics.csv), [Train portfolio metrics](train_portfolio_metrics.csv), [Train B00 deltas](train_portfolio_deltas.csv), [transmission](train_signal_transmission.json).
- [Valid report](VALID_REPORT.md), [Valid annual metrics](valid_annual_metrics.csv), [machine-readable decision](decision_result.json).
- [Train artifacts](../../artifacts/DM-20260925-02/run-20260925T063642Z/), [Valid artifacts](../../releases/NH_REV_001-v1/valid-evaluation/). Each includes event_predictions, event_ranks, portfolio_weights, signal_stages, daily_pnl, daily_cost, daily_turnover, annual_metrics and decision_result. Targets are absent from inference inputs. Event labels are separately saved in event_labeled.parquet after prediction sealing.
- Eight regression tests PASS; source scan and Train-only firewall PASS; three Train cutoffs plus a 2020 Valid-input cutoff pass exact future-mutation feature/score/weight checks across all four sources. Each source is independently mutated and all-source truncation tested on synthetic inputs. Known Train B00/RS60 bitwise parity, full coverage, deterministic replay, official weight/P&L parity and leg reconciliation PASS.
- Real zip Train equivalence: 809,636 rows; two predictions in 2.78 seconds; peak RSS 650 MB. The Valid run completed in 11.72 seconds. No network, GPU or fitted model is required.
- All frozen file hashes, prediction seals and official input-manifest hashes were rechecked after completion. The old frozen release was untouched. Test results apply to the exercised inputs/cutoffs, not a universal proof.

Signal-transmission stage_daily_rankic averages all defined daily correlations, including days with 2–4 events, following prior diagnostics; primary IC requires ≥5 finite events. Pooled stock-day score/weight correlation and mean daily score/weight correlation are separately named; they have different weighting and can differ in sign. No tuning used either measure.
