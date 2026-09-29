# SN1 state decay, event entry and holding persistence

## Scope

This is a descriptive Train / already-open historical-Valid study of the fixed `SN1_H1` stream. Both periods are development data; the historical Valid is not called OOS. No model was refit, no paper data was accessed, and no age or horizon grid was searched. Phase 1 used no target or P/L. Phase 2 evaluated only the existing saved H1 and H5 target artifacts against fixed event/state ages `1, 5, 20, 40, 60` sessions.

The complete target-blind mechanical explanation and saved Date × Code state table are in [STATE_PERSISTENCE_AUDIT.md](STATE_PERSISTENCE_AUDIT.md). Phase 2 inputs, source hashes and daily-account parity are in [phase2_manifest.json](../../artifacts/DM-20260928-01/run-20260927T161843Z/audit/phase2_manifest.json). The detailed tables are the run's `entry_score_quality.csv`, `state_lag_quality.csv`, and age/renewal attribution CSVs.

## What the state does

For a stock with no new same-side event, the existing recurrence retains `0.75^k` of High state and `0.50^k` of Low state after `k` stock observations. At 20 sessions those amplitudes are about 0.317% and 0.0000954% of their entry values; at 60 sessions, about 0.00000319% and `8.67e-17%`. But the source rule tests the **sign**, not the remaining magnitude: any negative Low state remains the selected SN1 source while `Low < 0`, and can mask a positive High state.

Consequently absolute score magnitude can collapse while its relative order stays almost fixed. On unchanged-source, no-event pairs, the phase 1 audit measured median percentile movement of zero and quintile retention of 99.49%. In the saved H1 portfolio, adjacent-day cross-sectional rank autocorrelation is 0.9965 in Train and 0.9955 in historical Valid. Q1–Q5 retention is 99.1–99.6% in Train and 98.9–99.7% in historical Valid.

## Event-entry prediction quality

Event EntryScore is evaluated on the event date against the already-saved H1 or H5 residual-return target. Low event scores and returns are sign-oriented for this table; H5 is a pre-existing diagnostic target, not a refit.

| Split | Event side | H1 RankIC (HAC t) | H5 RankIC (HAC t) | Reading |
|---|---|---:|---:|---|
| Train | High | +0.0110 (+0.66) | +0.0018 (+0.10) | Weak at entry |
| Train | Low | +0.0071 (+0.20) | −0.0123 (−0.36) | Weak / mixed |
| Historical Valid | High | +0.0185 (+1.70) | +0.0217 (+1.89) | Positive tendency, not conclusive |
| Historical Valid | Low | −0.0265 (−1.31) | −0.0243 (−1.19) | Negative tendency |

The fixed-age same-side StateScore results do not show a common survival curve across Train and historical Valid, High and Low, or H1 and H5. One apparent exception is historical-Valid Low/H5 at age 40 (RankIC +0.0764, HAC t +2.04); Train Low/H5 at the same age is −0.0856 (t −1.58), and neighboring ages disagree. It is one cell among the pre-fixed side × horizon × age diagnostics, not a basis for an age rule.

## Holding-age contribution

The following are annualized weighted account contributions, not standalone sleeve returns. The sleeve-age groups refer to official Q membership.

| Split | Sleeve | Under 20 sessions Net contribution | 20+ sessions Net contribution |
|---|---|---:|---:|
| Train | Long | −0.076% | +6.257% |
| Train | Short | −0.048% | −1.587% |
| Historical Valid | Long | −0.052% | +2.155% |
| Historical Valid | Short | −0.266% | −1.556% |

Event age tells the same broad story. Long contribution after the event's first five sessions is positive in both periods (+5.675% Net annualized in Train, +1.798% in historical Valid). Short age-5+ contribution is negative in both (−1.553% and −1.304%). This is descriptive selection by the realized state and membership, not proof that forcing a longer holding period causes return.

Renewal separates stale carry from repeated events. Long positions with at least two same-side events in the last 60 stock observations contribute +3.299% Net annualized in Train and +1.212% in historical Valid. Short positions with recurrent Low events still lose: −0.251% and −1.240%, respectively. Stale Short carry also loses in Train (−0.490%) but less in historical Valid (−0.149%). Thus Short losses are not solely old stale-state carry; renewed Low-origin Shorts also lose in historical Valid.

## Portfolio spell profile

The profile uses the saved daily quintile stream. Durations count observed stock-days in the same Long/Short membership spell and are censored at sample edges; they are not fixed-share ownership records.

| Split | Side | Median spell | Mean spell | Same-side retention 5 / 20 / 60 sessions |
|---|---|---:|---:|---:|
| Train | Long | 140.5 | 330.5 | 98.9% / 96.1% / 90.9% |
| Train | Short | 152.5 | 261.8 | 98.6% / 94.6% / 86.6% |
| Historical Valid | Long | 207.5 | 330.5 | 98.7% / 95.3% / 87.0% |
| Historical Valid | Short | 165.0 | 224.0 | 98.1% / 93.2% / 81.7% |

This establishes that SN1 membership persists for months. It does **not** establish that a one-day Ridge target is economically mismatched: the event-entry RankIC evidence is weak and lagged StateScore results are mixed. The robust observation is persistence in portfolio ordering and Long P/L concentration, not a verified multi-week predictive horizon.

## Implication

The mechanism to test was a stale negative Low sign continuing to override positive High state. One fixed 60-session expiry was registered before candidate P/L. It changed too much of the book and failed in both development periods; details and the decision are in [STATE_INTERVENTION_RESULTS.md](STATE_INTERVENTION_RESULTS.md) and [PAPER_STATE_DECISION.md](PAPER_STATE_DECISION.md). The age audit supports keeping the H1 state rule unchanged unless a genuinely prospective paper record later shows otherwise.
