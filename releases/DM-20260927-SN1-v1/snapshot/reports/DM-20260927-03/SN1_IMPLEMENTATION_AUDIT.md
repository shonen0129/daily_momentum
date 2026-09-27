# SN1 implementation and numeric stability audit

## Conclusion

SN1 is now in the formal submission adapter. The Train entry point reproduces the saved research SN1 scores **bit for bit** on all 576,535 evaluation rows. The research driver and submission code call the same transform in **stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py**.

The old regulation table mixed two windows: it calculated score statistics on the full 2008–2016 in-memory stream, while the saved score parquet contains only the 2011–2016 evaluation rows. The table has been regenerated from the saved score parquet. We did not read Valid data or calculate P/L in this audit.

Direct raw reconstruction, EWMA inversion, an independent float64 recurrence, input row shuffling, and Parquet save/reload produce **identical quintile labels and weights** over the saved evaluation window. Floating-point score values can differ at machine precision, but the measured maximum difference is 2.22e-16.

## Fixed specification and implementation

- High EWMA alpha: 0.25.
- Low EWMA alpha: 0.50.
- Upstream yearly high/low Ridge fitting, events, universe, and feature definitions: unchanged.
- SN1 rule: if low_state < 0, final score is low_state; otherwise, if low_state == 0 and high_state > 0, final score is high_state; otherwise use high_state + low_state.
- Score smoothing recovery retains the pre-existing 1e-12 zero-noise floor. No threshold, alpha, or parameter was changed.
- Official rank(method="first") and five-quintile weight construction remain unchanged.
- predict() now follows the competition entry point. It uses Train labels for model fitting; for the later split it reads later feature panels and Train labels only. No Valid target is referenced.

short_night_root_cause.py::candidate_score_streams now delegates to the same sn1.rebuild_from_base_score() implementation used by the submission adapter. The source scan covers the feature builder, upstream signal module, SN1 transform, and submission adapter.

## Reconciled regulation checks

The corrected source is artifacts/DM-20260927-03/run-20260926T191539Z/predictions/strategy_scores.parquet (SHA-256 cde0f3c9d11ad438e6705464c427f6782e55810ba96879544b4f80d9b2e78b69). The Train target was read only to verify index coverage; target values were not used for these statistics.

| Saved score column | Zero rate | Duplicate stock-day rate | Tie crosses Q boundary | Pooled unique scores | Mean daily unique ratio | Min daily unique ratio | Q groups/day | Saved weight / Q mismatches |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BOX_ORIGINAL | 8.760% | 8.772% | 6.685% | 506,329 | 91.267% | 3.425% | 5 | 0 / 0 |
| D_LOW_FAST_ONLY | 8.760% | 8.763% | 6.662% | 505,638 | 91.272% | 3.425% | 5 | 0 / 0 |
| SIDE_SOURCE_SEPARATION | 8.760% | 8.842% | 6.419% | 497,487 | 91.211% | 3.425% | 5 | 0 / 0 |
| HIGH_AGE5_SHORT_VETO | 0.000% | 0.000% | 0.000% | 472 | 100.000% | 100.000% | 5 | 0 / 0 |

The minimum daily unique ratio is 3.425% on the first evaluation date, 2011-01-04, when most carried states are zero. The old SN1 row reported 34.379% zeroes, 64.810% mean daily unique ratio, and 32.688% boundary ties because its in-memory input included pre-evaluation rows. These are scope errors, not changes in saved score values or the official evaluator.

The regenerated file is artifacts/DM-20260927-03/run-20260926T191539Z/audit/regulation_checks.csv; its provenance is audit/regulation_checks_source.json. The weight and quintile reconstructions from each saved score have zero row mismatches. All evaluation dates have five populated quintiles and finite official weights. No additional repository rule sets a minimum uniqueness or zero-score rate.

## Numeric stability

All comparisons below use the 576,535 saved evaluation stock-days; no P/L metric was calculated. The direct raw stream was rebuilt by replaying the fixed annual Train model on Train inputs. This matters because the old event_predictions.parquet stores evaluation-date rows only and omits some non-evaluation year-end events that feed the next date's EWMA state.

| Comparison | Score values changed bitwise | Max absolute score difference | Quintile changes | Weight changes | Short membership changes |
|---|---:|---:|---:|---:|---:|
| Direct raw stream vs. saved-score EWMA inversion | 74,464 | 2.22e-16 | 0 | 0 | 0 |
| Independent scalar float64 EWMA vs. pandas EWMA | 77,790 | 2.22e-16 | 0 | 0 | 0 |
| Shuffled input rows, then canonical (Date, Code) sort | 0 | 0 | 0 | 0 | 0 |
| Parquet save and reload | 0 | 0 | 0 | 0 | 0 |

The inverse-reconstructed raw stream differs from direct raw at 5,500 rows, with maximum absolute difference 4.44e-16; this is floating-point recurrence noise. The shared SN1 implementation sorts and validates the (Date, Code) index before the recurrence. A fixed-seed suffix mutation at three cutoffs also leaves prior SN1 scores, quintiles, and weights bitwise unchanged.

The official quintile rule still resolves exact score ties after sorting by Code; the row-shuffle check confirms input row order has no effect. It does not claim that replacing the official Code ordering with another tie order would preserve the portfolio.

## Formal submission parity and tests

- Formal submission.predict(data_dir=Train, split=train) output aligns to the Train target index and matches the saved research SN1 score bit for bit on all 576,535 saved evaluation rows.
- The submission directory imports successfully as the evaluator's top-level submission module.
- The same Train model replay exactly reproduces the saved upstream BOX base score (max absolute error = 0).
- Research candidate path and submission scoring path are bitwise identical.
- Source scan: PASS.
- Future-prefix score/quintile/weight mutation audit: PASS at 2012-12-28, 2014-12-30, and 2015-12-30.
- Strategy tests: 33 passed, including row-order stability, direct-raw/inversion agreement, float64 finiteness, Parquet round trip, evaluator-style top-level import, and a synthetic later-split entry-point test. The synthetic fixture uses no competition Valid files.
- The actual later-split path was not run against competition Valid files. No Valid feature or target parquet was opened.

## Reproducibility

- Experiment/run: DM-20260927-03 / run-20260926T191539Z.
- Evaluation data: Train; saved evaluation 2011-01-04 through 2016-03-29 (2016 partial); upstream Train history 2008-11-04 through 2016-03-31.
- Cost specification retained: 10 bps one way. It was not used in this audit.
- Git HEAD: 0b8341c3c0051db4b1a54040a6c4d85847bca8ec.
- Worktree was already dirty before these changes; no commit was created and unrelated changes were left untouched.
- Detailed code/data hashes, model records, opened parquet paths, and numeric comparisons: artifacts/DM-20260927-03/run-20260926T191539Z/audit/sn1_numeric_stability.json.
- Corrected score-only regulation provenance: artifacts/DM-20260927-03/run-20260926T191539Z/audit/regulation_checks_source.json.

No alpha, threshold, feature, candidate, or P/L-based decision was introduced. The pre-existing strategy conclusion that SN1 does not solve Short × Night is unchanged.
