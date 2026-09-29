# SN1 H1 state persistence audit — Phase 1 (P/L-blind)

## Finding

The 100–300+ session SN1 membership persistence is primarily an **unexpired-state plus relative-rank effect**, with event renewal contributing for a subset of holdings. It is not evidence that an event's absolute forecast confidence lasts for hundreds of days.

The fixed H1 stream was rebuilt from the saved yearly H1 Ridge models and Train / historical-Valid feature panels. The Phase 1 loader denied target/raw-target files; it calculated no P/L or RankIC. Train and the previously opened historical Valid are treated as development data. No paper data was accessed.

## Mechanical path

For each Date × Code, the audit table records the raw High/Low event score, separate High and Low EWMA states, final saved SN1 score, official quintile and weight, daily score percentile/dispersion, source and source ages, last 20/60/120 observed-session event counts, latest event side/age, consecutive sleeve and exact-quintile age, last sleeve-entry and side-switch dates, and point-in-time sector/size fields available from the listed-info panel (`Sector17Code`, `Sector33Code`, `ScaleCategory`). Event counts use the existing listing segment and consecutive stock observations. The `1e-12` near-zero flag is descriptive and reuses the existing reconstruction-cleanup scale; it is not an action threshold.

The fixed code path is:

1. High breakout event → positive event percentile; Low breakout event → negative event percentile.
2. Separate EWMA states: `H_t = .25 × HighRaw_t + .75 × H_(t−1)` and `L_t = .50 × LowRaw_t + .50 × L_(t−1)`. A zero raw observation decays that side's state. A listing gap over 20 market-date positions resets the state.
3. `D=H+L`; SN1 selects `L` whenever `L<0`, otherwise `H` only when `L==0 and H>0`, otherwise `D`.
4. The saved score is sorted by Date/Code and passed through the official daily `rank(method="first")` five-quintile weighting.

The decisive implementation detail is the strict `L<0` precedence. A negative Low state is not expired at an economic confidence threshold. It remains negative through repeated multiplication by 0.5 until numerical underflow or a listing reset. While it remains negative, it masks positive High state, however small the Low magnitude. Thus a Long can rank in Q4/Q5 with a tiny negative score if most other names have more negative scores; SN1 does not require a positive absolute score for a Long.

## Structural measurements

| Measurement | Train | Historical Valid | Interpretation |
|---|---:|---:|---|
| Date × Code rows | 582,035 | 1,227,148 | 2011-01-04 onward / 2016-04-01–2026-07-31 |
| Exact zero final score | 8.72% | 0.99% | Pooled rate is 3.48%; Valid exact zeros are mainly numerical fallback cases |
| `abs(final score)<1e-12` | 75.87% | 81.37% | Pooled rate is 79.60%; mostly carried values, not fresh event magnitudes |
| `L!=0` | 69.55% | 90.26% | Pooled rate is 83.60%; Low state rarely becomes exactly zero between resets |
| `L<0` and `H>0` simultaneously | 55.16% | 89.93% | Pooled rate is 78.74%; High information is active but masked by Low precedence |
| Masked score is near zero | 49.57% | 76.81% | Pooled rate is 68.04%; selected score can be tiny despite active High state |
| Official quintile/weight changes from state reconstruction | 0 | 0 | All five quintiles remain populated on every date |

The absolute EWMA amplitude decays quickly after a single event with no renewal:

| Days without another same-side event | High state remaining (`α=.25`) | Low state remaining (`α=.50`) |
|---:|---:|---:|
| 5 | 23.73% | 3.125% |
| 20 | 0.317% | 0.0000954% |
| 60 | 0.00000319% | 8.67e-17% |
| 120 | 1.02e-13% | 7.52e-35% |

Yet during adjacent no-event pairs with an unchanged source, measured absolute state ratios are 0.500006 for Low and 0.75 for High; the recurrence matches the respective geometric update within relative tolerance `2e-15` for all included pairs. The median change in the whole-universe score percentile is exactly zero. Official quintile retention is 99.45% for Low-source pairs and 99.86% for High-source pairs. Across all matched no-event, same-source pairs, quintile retention is 99.49%. The absolute state contracts while relative order usually does not move.

## Event renewal versus stale carry

The 60-session renewal figures below are stock-day shares within the indicated held-sleeve-age band. The 300+ band contains the clearest contrast:

| Split / side / sleeve age | Median age of relevant-side event | Same-side event in last 60 | Recurrent same-side events in last 60 | `abs(score)<1e-12` | Main SN1 source |
|---|---:|---:|---:|---:|---|
| Train Long, 120–299 | 66 sessions | 38.2% | 31.1% | 81.5% | Low 38.2%, High 42.9% |
| Train Long, 300+ | 54 | 51.3% | 42.9% | 54.0% | High 70.6% |
| Train Short, 120–299 | 129 | 20.0% | 14.6% | 85.2% | Low state |
| Train Short, 300+ | 310 | 11.9% | 9.1% | 90.9% | Low state |
| Historical-Valid Long, 120–299 | 68 | 44.8% | 36.4% | 98.7% | Low 93.3% |
| Historical-Valid Long, 300+ | 56 | 50.8% | 42.8% | 73.1% | Low 55.4%, High 43.3% |
| Historical-Valid Short, 120–299 | 135 | 19.6% | 14.7% | 86.6% | Low state |
| Historical-Valid Short, 300+ | 246 | 17.0% | 12.6% | 87.6% | Low state |

The “recurrent” classification means at least two same-side events in the latest 60 stock observations; it is descriptive only. Many old spells have no recent same-side renewal. In particular, the 300+ Short cohort has a median relevant Low event age of 246–310 sessions, and only 12–17% have any same-side event within 60 sessions. Repeated events therefore do not explain most old Short persistence. Old Low carry survives as a tiny negative value and remains relatively low ranked.

The 300+ Long cohort is different across periods. Train contains substantially more High-source and renewed Long rows; historical Valid's 120–299 Long rows are overwhelmingly tiny negative Low-source scores, yet their median cross-sectional score percentiles are 0.75–0.90 across the older age bands. This shows that relative placement can keep a name Long even when the selected absolute score is negative and effectively zero. Some 300+ Longs also receive new High events; that is genuine renewal for that subset, not an explanation for all persistent holdings.

## Audit table and numerical replay

The full P/L-blind table is [date_code_state.parquet](../../artifacts/DM-20260928-01/run-20260927T154814Z/audit/date_code_state.parquet). Its SHA-256 is `f23415b0544c866fe57de74e8a16c3b31cda7b260f90cd768614e4f070a809d6`.

Rebuilt scores differed from the saved H1 scores by at most `2.22e-16` (Train) and `3.33e-16` (historical Valid), so the score stream is numerically equivalent but not bit-for-bit equal. Replaying official quintiles and weights from the reconstructed High/Low states changed **zero** quintile rows and **zero** weights in both periods; every date retained five populated quintiles. The assignments, unlike the raw floating-point values, are exactly stable in this replay.

## Limits and Phase 1 lock

This is a mechanical accounting, not a test of predictive information or returns. Sleeve age is daily Q1/Q2 versus Q4/Q5 membership, not fixed-share ownership; exact-quintile age is tracked separately. The first/last spells are truncated by the study sample. Renewal counts are based on observed stock rows within the existing listing segments; a stock missing panel rows can make that count differ from elapsed market sessions. PIT fields are descriptive only and do not enter SN1. None of these findings proves an age-based exit rule would improve returns.

The fixed audit table, structural summaries and official-assignment replay were hashed in `experiments/DM-20260928-01/phase1_lock.json` before Phase 2 targets/P&L were opened. Phase 2 can now perform only the registered fixed-age/event-lag attribution; candidate P/L remains blocked until the later intervention plan is frozen and hashed.
