# Short × Night root-cause audit

- Experiment: `DM-20260927-03`
- Audit run: `run-20260926T185654Z` (structural phase; completed 2026-09-26 18:56 UTC)
- Evaluation run: `run-20260926T191539Z` (fixed interventions; completed 2026-09-26 19:16 UTC)
- Scope: Train only, 2011-01-04–2016-03-29; 2016 partial 2016-01-04–2016-03-29; 1,275 evaluation dates.
- Status: no Valid, Freeze, `raw_target`, or submission evaluation accessed. Structural phase did not open returns or compute P/L. Baseline performance and source-attribution figures supplied in the request / existing reports were already known; only new candidate P/L was withheld until the fixed plan was saved.

## Existing work reused

Found and reused the source reports and saved streams instead of rebuilding or refitting:

- [DM-20260927-02 LOW_FAST_ONLY_RESULTS](../DM-20260927-02/LOW_FAST_ONLY_RESULTS.md), [DM-20260927-01 ASYM_EMA_RESULTS](../DM-20260927-01/ASYM_EMA_RESULTS.md). These contain the found `BOX_ORIGINAL`, `D_LOW_FAST_ONLY`, `D_B00_LOW_FAST_ONLY`, `A_LOW_NO_CARRY`, and `C_ASYM_EWMA` lineage; B00 is kept as a diagnostic control only.
- [DM-20260926-01 AUDIT](../DM-20260926-01/AUDIT.md) and `EXPERIMENT_RESULTS.md`
- Saved signal: `artifacts/DM-20260925-03/run-20260926T063602Z/predictions/signals.parquet`
- Saved D score/weights: `artifacts/DM-20260927-02/run-20260926T174234Z/predictions/`
- Event masks: `artifacts/DM-20260926-01/run-20260926T143032Z-08/predictions/event_masks.parquet`

The intervention plan was frozen at 2026-09-26 19:05:06 UTC, SHA-256 `84c3a051556e2ee02a8744e521ed22f1c600c357c4b9caccc6cb4414111ca621`. See [fixed plan](SHORT_NIGHT_INTERVENTION_PLAN.md). The plan is unchanged after results.

## Structural data boundary and holdings audit

Phase 1 used saved D scores/weights, BOX event masks and eligibility, Train PIT listing information, and same-day Train quotes. It did not read target/returns or compute P/L. The output table contains every D Short holding with Date, Code, final score, cross-sectional rank/rank percentile, official quintile, portfolio weight, High/Low state, High/Low raw event score, dominant source and age, score sign/absolute value, zero and tie-break flags, Box eligibility, PIT sector/name, PIT size category, turnover and volume, and High/Low aged-source components.

- Full holdings: `artifacts/DM-20260927-03/run-20260926T185654Z/audit/short_holdings_structure.parquet` (`.csv.gz` is also saved).
- Q1/Q2 source-age and zero structure: `q1_q2_structure.csv`, `q1_q2_source_age.csv`, `aged_source_short_mechanics.csv`.
- Sign, zero-sector and code-order diagnostics: `cross_section_score_sign.csv`, `zero_score_short_sector.csv`, `zero_score_sector_bias.csv`.
- Phase 1 audit summary: `structural_audit.json` (`target_or_return_read=false`, `pnl_calculated=false`).

### A. Q1 and Q2 are materially different sleeves

| Sleeve | Short stock-days | Share of Short gross weight | High-age-5+ dominant | Low-age-5+ dominant | Exact-zero | Positive score |
|---|---:|---:|---:|---:|---:|---:|
| Q1 | 115,809 | 66.80% | 21.60% | 57.68% | 10.13% | 21.60% |
| Q2 | 115,093 | 33.20% | 56.56% | 37.42% | 5.03% | 56.56% |

Q1 is mostly negative Low carry. Q2 is mostly weak positive High carry. This is the direct structural reason that one composite signal produces two different Short populations.

### B. Why High-origin names enter Short

`high_age_5_plus` is active on 61.95% of Short stock-days and is the dominant absolute source on 39.03%. When active, its High state is positive in 100% of rows; for High-age-5+-dominant Short rows the final score is positive. The dominant High-age-5+ rows split 21.60% into Q1 and 56.56% into Q2. The Q1 median absolute final score is `2.50e-22` (p90 `2.31e-10`); Q2 median is `5.88e-18` (p90 `3.30e-6`).

These are old EWMA states, not fresh event-day observations: the current High and Low raw event scores for aged rows are zero, while their carried states remain nonzero and can decay to tiny magnitudes. Each date still assigns a fixed bottom 40% of cross-sectional ranks to Short. When most of the universe has positive final scores (67.38% overall), the bottom 40% can contain positive values. In fact, 39.03% of all D Short stock-days have positive scores; all are below that day's median positive score. Hence `high_age_5_plus` is not being selected as an absolute bearish signal: it is a positive, often nearly-zero residual carry that is relatively weak against the day's stronger scores and is pushed into Q1/Q2 by the fixed rank quota. It is concentrated more in Q2, though a meaningful 21.6% of Q1 is also High-age-5+ dominant.

This distinction answers the “absolute weakness or relative weakness?” question: **High-age-5+ Short rows are positive-scored and relatively low-ranked, rather than absolutely negative-scored.** The signal's tiny magnitude makes rank placement sensitive to cross-sectional ordering but does not itself prove that the signal is noise.

### C. Low-aged Short mechanism

`low_age_5_plus` is active in 81.09% and dominant in 47.59% of Short rows. Its Low state is negative in 100% of active observations and its old-state component is most concentrated in Q1: 57.68% of Q1 versus 37.42% of Q2 is Low-age-5+-dominant. This is an actual negative signed carry, so the normal ascending score order places it into Short. High and Low states overlap frequently; among Low-age-5+-dominant rows, High is also positive in 52.83% of Q1 and 23.72% of Q2 rows, showing that the combined score can net competing old states.

The distinction is structural: aged Low names are Short because their composite remains negative; aged High names are Short because their positive composite is still in the cross-section's bottom 40%.

### D. Absolute scores, zero ties, sector/size

- 63.94% of Short scores have `abs(score) < 1e-12`, 74.95% are below `1e-8`, and 87.18% below `1e-4`. Exact zero is 7.59% of Short stock-days and 8.48% of Short gross weight. Q1 exact-zero rates are 10.13% by stock-days / 10.13% by gross weight; Q2 rates are 5.03% / 5.15%.
- Exact-zero names in Q1/Q2 have both current High and Low state equal to zero. Existing state therefore cannot distinguish them. Across the 347 dates where the zero group crossed Q1/Q2, the two sleeve memberships had Code-order Spearman 0.811; zero names span multiple quintiles on 80 dates. This is material deterministic Code-order exposure, not an independent signal.
- Among zero-score rows, Short-tail sector shares exceed the same-day zero pool by Food +5.85pp, Pharmaceuticals +3.19pp, Other finance +2.19pp, Real estate +2.17pp, and Services +1.97pp. PIT size/sector are present in the audit; same-day raw turnover median is ¥1.291bn and volume median 1.153m shares. No new sector/liquidity predictor was registered because Phase 1 supplied no mechanism to justify one.
- Box eligible: 79.78% of Short rows; Q1 78.25%, Q2 81.31%.
- The full cross-section has 23.86% negative, 8.76% exact-zero, 67.38% positive scores. On 748 of 1,275 dates, nonpositive scores cover less than the 40% Short share. A rule that simply bans positive Shorts would leave official Short exposure unfilled on those dates.

## Night loss evidence

The baseline P/L/source-attribution figures were supplied in the request and existed in prior reports, so they were known before the structural pass. The candidate P/L below was generated only after the plan hash was fixed. Attribution is descriptive accounting and cannot by itself identify an economic cause; it confirms that the structural populations above are where the observed loss lands:

| D source in Short × Night | Annual gross contribution | Annual net contribution | Standalone attributed Net SR | Short gross-weight share | Fractional stock-day share |
|---|---:|---:|---:|---:|---:|
| `low_age_5_plus` | -2.641% | -2.673% | -0.735 | 51.59% | 47.76% |
| `high_age_5_plus` | -1.777% | -1.833% | -0.721 | 32.82% | 39.10% |
| `low_age_1_4` | -0.383% | -0.384% | -0.268 | 5.13% | 4.03% |
| `low_event_day` | +0.046% | +0.022% | +0.015 | 1.98% | 1.53% |
| zero tail tie-break | -0.455% | -0.458% | -0.837 | 6.77% | 5.08% |
| zero non-tail tie-break | -0.152% | -0.157% | -0.266 | 1.71% | 2.51% |

Aged High and Low together account for `-4.506pp`, about 82% of D's `-5.483%` Short × Night Net contribution. Low-age-5+ is the largest weight share and loss; High-age-5+ is the key **selection mechanism** that the Low-alpha-only change does not fix. D Short × Night is negative in 2011–2014 and 2016 partial, near flat in 2015. The losses therefore are not confined to 2016.

The previous `BOX_ORIGINAL` → `D_LOW_FAST_ONLY` EMA change (`low alpha 0.25 → 0.50`, High alpha fixed at 0.25) only partly repaired the source mix:

| Short × Night source | BOX net contribution | D net contribution | Change |
|---|---:|---:|---:|
| `low_age_5_plus` | -2.927% | -2.673% | +0.254pp |
| `high_age_5_plus` | -1.713% | -1.833% | -0.120pp |
| aged High + Low | -4.640% | -4.506% | +0.134pp |

So faster Low decay improves the largest Low-age bucket, but it does not prevent positive High carry entering the lower-ranked Short tail; the High-age loss increases and offsets nearly half of the Low-age improvement. This is the limit of an EMA-only fix in the observed state composition.

The age-source attribution is not uniform over time (annualized percentage contribution; 2016 is partial):

| Year | `low_age_5_plus` | `high_age_5_plus` |
|---|---:|---:|
| 2011 | -3.192% | -0.005% |
| 2012 | -7.047% | -0.016% |
| 2013 | -3.839% | -5.493% |
| 2014 | -1.372% | -3.321% |
| 2015 | +1.158% | -0.392% |
| 2016 partial | +1.446% | -1.671% |

Thus Low-age-5+ explains much of the 2011–2014 loss and reverses in 2015/2016 partial; High-age-5+ is especially damaging in 2013/2014 and remains negative in 2015/2016 partial. This split argues against a single uniform aging decay explanation.

## Competition contract/regulation boundary

Repository search found no separate numeric rule for minimum score uniqueness, zero-score rate, or tie rate. The source of truth for prediction contract is [`stock_comp_2026/evaluate_script.py::load_prediction/align_prediction`](../../stock_comp_2026/evaluate_script.py): exactly one numeric prediction column; index names `Date`, `Code`; unique prediction index; complete target-row coverage. The competition README specifies daily five quintiles and 10bp one-way cost. The official quintile helper and weight construction were replayed. The full submission evaluator was not run because its default selects Valid; Train-only `align_prediction` validation was run in memory. Zero/tie rates are reported as diagnostics, not represented as a formal rule. Per user instruction, B00 remains diagnostic-only even though that is stricter than the located mechanical contract.

## Causal scope / conclusion

The measurable structural cause is rank allocation, not a proven market microstructure story: the fixed five-quintile score ordering assigns a Short sleeve to the lowest 40%; negative aged Low states naturally fill Q1, while positive but tiny aged High states are relatively weak and fill much of Q2 (and part of Q1). Overnight attribution shows both groups lose, with Low-age-5+ the largest loss pool. The current evidence does not identify whether this overnight effect is sector, liquidity, risk, gap behavior, or another economic channel. The two pre-fixed interventions directly tested side-source separation and a High-age-5+ Short veto; neither improved Short × Night.
