# DM-20260924-01: C3 correctness audit

Audit date: 2026-09-24. Sections 1–3 document the Train-only correctness audit; the separately frozen Valid comparison is in section 5.

## 1. Original H0/C3 accounting comparability

The prediction Parquets for H0 and the original C3 have identical unique `(Date, Code)` indices: 809,636 rows each, with finite scores on every row. Their account files have identical date indices. For the 2011-01-01 through 2014-12-31 development window, both have the same 982 evaluation dates and exactly equal daily label coverage (mean 99.3548%). The five Train input hashes recorded by the original run match the current Train files.

The daily PnL decomposition reproduces the run summary:

| Metric (annualized unless stated) | H0 | Original C3 | C3 − H0 |
|---|---:|---:|---:|
| Gross Sharpe | 0.7286 | 0.7832 | +0.0545 |
| Net Sharpe | 0.4051 | 0.5164 | +0.1112 |
| Gross P/L | 3.6131% | 3.8906% | +0.2775 pp |
| Cost | 1.6040% | 1.3242% | -0.2797 pp |
| Net P/L | 2.0091% | 2.5663% | +0.5572 pp |
| Average daily turnover | 0.06365 | 0.05256 | -0.01110 |

Thus the mean-return improvement contains both a gross-return increase and lower trading cost. Sharpe differences are not additive. The original C3 maximum drawdown was worse than H0 (-11.76% versus -10.35%).

## 2. `prox250` price-unit and window audit

`prices_daily_quotes_train.parquet` and `raw_return_1day_train.parquet` have identical unique indices (809,636 rows). The raw price file includes `AdjustmentFactor`. The workspace data contract allows that field as dated event metadata when causal prefix-invariance is tested; retrospective `Adjustment*` OHLCV levels remain prohibited. JPX describes its price dataset as providing before/after-adjustment prices together with the adjustment factor ([official dataset description](https://pro.jpx-jquants.com/datasets/9)).

The old formula used raw `Close / rolling_max(High, 250)` with `min_periods=120`. During 2011–2014:

* 436,080 rows had an available `prox250` value; 6,228 (1.43%) used only 120–249 valid High observations. These rows do not represent a complete 52-week window.
* 16,765 of those valid rows (3.84%) had at least one non-unit `AdjustmentFactor` event inside the 250-row history window. Raw price levels from different share units were therefore mixed in the maximum.
* For code 16050 on 2013-09-26, raw High/Close moved from 467,000/461,500 to 1,161/1,154, with `AdjustmentFactor=0.0025`; the factor returned to 1 the next row. The old proximity ratio was 0.002129 on the event date and 0.002142 the next day. Carrying the dated event factor cumulatively within the listing segment produces ratios 0.851661 and 0.856827 for those dates.
* Across development rows whose 250-row window crossed a factor event, the old ratio median was 0.2616; the cumulative-factor diagnostic median was 0.8963. Values below 0.1 fell from 6,076 rows to 0. This is a feature-definition/data-unit issue, not evidence that the corrected candidate predicts better.

The 120-row partial-window behavior follows the old experiment config, but it does not equal a 250-observation high. The new fixed definition requires 250 valid raw High values. In the development sample this affects 6,228 rows (1.43% of previously available proximity rows); missing proximity values map to the established neutral centered-rank value. No performance result was used to choose this definition.

## 3. Corrected candidate and Train-only verification

`C3S` is a separate exploratory definition: it carries forward dated AdjustmentFactor event multipliers by cumulative product within each listing segment, expresses raw High and Close in a common historical share unit, and requires 250 valid High observations. It uses the original 0.5/0.5 blend and EWMA(0.25). It does not inherit the original C3 result.

The Train-only H0/C3S predictions have identical unique `(Date, Code)` indices (809,636 rows), finite scores on every row, identical account date indices, and identical label coverage. The 2011–2014 result is descriptive because the period is known and the definition was created after the old C3 was reviewed:

| Metric | H0 | C3S |
|---|---:|---:|
| Net Sharpe | 0.4051 | 0.6567 |
| Gross Sharpe | 0.7286 | 0.9187 |
| Annual gross P/L | 3.6131% | 4.6497% |
| Annual cost | 1.6040% | 1.3246% |
| Annual net P/L | 2.0091% | 3.3252% |
| Average daily turnover | 0.06365 | 0.05257 |
| RankIC | 0.0072 | 0.0137 |
| Maximum drawdown | -10.35% | -11.25% |

C3S passed the preset descriptive screen (3/4 folds, median delta +0.3541), but its unadjusted bootstrap interval `[-0.1076, +0.6278]` crosses zero. It was frozen as a separate research release so the exact artifact could be compared reproducibly. It is not adopted. Its maximum drawdown also remains worse than H0.

The focused strategy suite passed (7 tests). The Train-only run passed source scan and future-mutation/truncation prefix-invariance at 2010-12-30, 2012-06-29, and 2014-12-30, with exact feature/signal equality. Runtime was 21.38 seconds under the 1,800-second bound. Train data hashes and code hashes are in the run metadata.

After the run, the report-generator wording was clarified to distinguish prohibited retrospective `Adjustment*` price levels from the permitted dated `AdjustmentFactor` event input. The run metadata retains the SHA-256 of the generator bytes used during execution; the feature and model source hashes are unchanged.

## 4. Freeze and Train parity before Valid

C3S was frozen as `DM-20260924-C3S-v1` before the comparison. Its frozen zip and source hashes were checked; the H0 comparator was the original frozen `DM-20260908-v1` `M_res60s1_a0.25` trial, not the later H0+C0/T1 release. Both zip predictions matched the existing Train artifacts exactly on 809,636 rows and 1,814 dates, with unique indices and finite scores ([verification record](TRAIN_FREEZE_VERIFICATION.json)).

## 5. One-time comparison on the previously accessed Valid period

The same Valid period had already been evaluated for `DM-20260912-01-v1` ([that record](../../releases/DM-20260912-01-v1/VALID_EVALUATION.md)). It is therefore not independent OOS evidence. After freezing C3S, both frozen submissions were predicted first and then scored against the same target using the official-compatible evaluator. The full result is recorded in [VALID_EVALUATION.md](../../releases/DM-20260924-C3S-v1/VALID_EVALUATION.md) and [valid_comparison.json](valid_comparison.json).

| Metric | H0 | C3S | C3S − H0 |
|---|---:|---:|---:|
| Official Net Sharpe | -0.3899 | -0.2409 | +0.1490 |
| Gross Sharpe | -0.0706 | -0.0097 | +0.0609 |
| Annual Gross P/L | -0.36% | -0.06% | +0.31 pp |
| Annual transaction cost | 1.63% | 1.33% | -0.30 pp |
| Annual Net P/L | -1.99% | -1.39% | +0.61 pp |
| Average daily turnover | 0.0649 | 0.0528 | -0.0121 |
| Mean RankIC | 0.0027 | 0.0058 | +0.0031 |
| Additive maximum drawdown | -29.59% | -29.69% | -0.10 pp |

Both strategies had negative full-period Net Sharpe and Net P/L. C3S reduced turnover and costs, and had a less negative relative result, but its Gross improvement was small and maximum drawdown was marginally worse. This is descriptive only because the Valid period was already used; the result did not change any feature, parameter, Champion, or submission default.

**Disposition:** the original C3 definition should not be promoted because raw price-unit changes distort its 250-row proximity feature. C3S is a separate frozen research candidate, not an adopted strategy. An independent performance claim requires a genuinely untouched evaluation period. The current proximity strategy's `submission.py` still defaults to C2.
