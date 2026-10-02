# DM-20261001-02: SN1_H1 VOL20 confidence diagnostic

- **Baseline:** `SN1_H1`
- **Change to trading strategy:** **None**
- **New variable:** prior-only market-residual `VOL20` (20 stock observations ending at `t-1`; sample SD, `ddof=1`) used for diagnostics only.
- **Main question:** Does SN1 ranking quality deteriorate as idiosyncratic volatility rises?
- **Result:** **NOT SUPPORTED**
- **Limitation:** Train development-history diagnostic only; no candidate strategy evaluated; no OOS claim.
- Run: `run-20261001T104507Z-03`. Valid and raw-target inputs were not opened.

## Baseline reproduction and fixed setup

Current, independent and both saved SN1_H1 references matched bit for bit over 809,636 rows. Official account daily parity was checked against the saved current baseline; result: **PASS**.
VOL20 uses the current PIT beta and TOPIX Train series with the existing listing-gap reset. Exactly 20 finite prior residual observations are required; missing VOL20 is not imputed. V1 is lowest daily percentile, V5 highest. The strategy's saved official weights and membership were held fixed.
Future mutation changed all five staged Train sources at three cutoffs and preserved features, VOL20 and SN1_H1 bitwise through each cutoff: **PASS**.

## Pooled V1–V5 prediction diagnostics

RankIC is calculated cross-sectionally inside each volatility quintile and averaged across active dates. HAC t-stat uses lag 5. Q1–Q5 returns rank SN1 scores within that volatility bucket each date; Q5−Q1 and monotonicity are descriptive. Returns are official H1 Train residual targets.

| Vol | Stock-days | Active dates | Mean RankIC | HAC-5 t | Hit ratio | Q5−Q1 (bp/day) | Centered target rank | Mean target (bp) | Target SD (bp) | Near-zero score | Unique score ratio |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| V1 | 114,842 | 1,287 | +0.007938 | +1.831 | 0.539 | +1.093 | +0.01245 | +3.161 | 133.13 | 82.160% | 90.504% |
| V2 | 115,385 | 1,287 | +0.008957 | +1.994 | 0.525 | +2.746 | +0.00162 | +2.319 | 153.95 | 79.618% | 89.712% |
| V3 | 115,429 | 1,287 | +0.009638 | +2.176 | 0.536 | +4.543 | +0.00210 | +2.501 | 166.61 | 76.387% | 88.936% |
| V4 | 115,386 | 1,287 | +0.012793 | +2.614 | 0.535 | +4.191 | -0.00427 | +2.045 | 185.26 | 73.453% | 88.901% |
| V5 | 115,883 | 1,287 | +0.015412 | +2.936 | 0.534 | +8.705 | -0.01175 | +3.319 | 237.16 | 66.731% | 88.620% |

The full pooled table also records exact-zero rate, mean/absolute score, pooled and mean-daily unique ratios, each Q1–Q5 mean, and pooled/daily target dispersion in [`pooled_volatility_quintile.csv`](../../artifacts/DM-20261001-02/run-20261001T104507Z-03/metrics/pooled_volatility_quintile.csv). Year/fold values for every V1–V5 bucket, including partial 2016, are in [`yearly_volatility_quintile.csv`](../../artifacts/DM-20261001-02/run-20261001T104507Z-03/metrics/yearly_volatility_quintile.csv).

### Year/fold RankIC and spread

| Year | V1 RankIC | V5 RankIC | V1 Q5−Q1 bp/day | V5 Q5−Q1 bp/day |
|---:|---:|---:|---:|---:|
| 2011 | -0.007803 | +0.019768 | -1.503 | +5.128 |
| 2012 | +0.014119 | +0.008416 | +4.507 | +5.734 |
| 2013 | +0.006860 | +0.007650 | +0.558 | +3.465 |
| 2014 | +0.018095 | +0.015876 | +3.504 | +9.621 |
| 2015 | +0.005428 | +0.014521 | -1.845 | +12.850 |
| 2016 * | +0.019251 | +0.059246 | +1.890 | +35.950 |

*2016 is a partial fold.*

Across complete years, V5 RankIC exceeded V1 in 4/5 years (2012 was the exception); V5 Q5−Q1 exceeded V1 in all 5/5 complete years. The 2016 partial fold also favored V5, so the spread pattern is not confined to that partial period. Hit ratios stayed near 0.53 and did not rise with volatility. These are descriptions of the same Train history, not independent annual confirmations.

## Fixed official Side × Vol attribution

This is accounting attribution of unchanged official memberships, weights and 10 bp one-way costs. It is not a counterfactual portfolio or a volatility-sorted portfolio. Trade turnover is attributed to the Long/Short sleeve and current day's VOL bucket (including `VOL_MISSING` for exits without a usable current bucket). Both official effective cost and all-turnover cost are saved. Pooled/year rows and reconciliation checks are in [`side_vol_attribution.csv`](../../artifacts/DM-20261001-02/run-20261001T104507Z-03/metrics/side_vol_attribution.csv).

| Side × Vol | Stock-days | Gross weight share | Annual gross contrib. | Annual net contrib. | Net contrib. SR | Mean H1 target (bp) | Daily turnover attrib. | Annual cost all-turnover |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| Long × V1 | 48,403 | 9.51% | +0.869% | +0.855% | +1.038 | +3.571 | 0.00055 | 0.014% |
| Long × V2 | 46,056 | 9.49% | +0.856% | +0.842% | +0.895 | +3.503 | 0.00057 | 0.014% |
| Long × V3 | 44,976 | 9.64% | +1.055% | +1.040% | +1.047 | +3.650 | 0.00058 | 0.015% |
| Long × V4 | 44,039 | 9.82% | +1.131% | +1.117% | +0.970 | +4.241 | 0.00055 | 0.014% |
| Long × V5 | 44,981 | 10.75% | +2.202% | +2.190% | +1.276 | +7.405 | 0.00047 | 0.012% |
| Short × V1 | 40,837 | 8.55% | -0.539% | -0.561% | -0.691 | +2.994 | 0.00090 | 0.023% |
| Short × V2 | 44,641 | 9.36% | -0.434% | -0.461% | -0.503 | +1.779 | 0.00104 | 0.026% |
| Short × V3 | 46,317 | 9.95% | -0.210% | -0.235% | -0.217 | +1.155 | 0.00096 | 0.024% |
| Short × V4 | 49,150 | 10.59% | -0.062% | -0.086% | -0.069 | +0.041 | 0.00095 | 0.024% |
| Short × V5 | 51,931 | 11.54% | -0.087% | -0.112% | -0.063 | -0.175 | 0.00096 | 0.024% |

Long contribution was largest in V5 (+2.202% annual gross vs +0.869% in V1). The official Short gross loss was larger in V1 (-0.539%) than V5 (-0.087%); high-volatility Short losses did not dominate. Thus the fixed portfolio attribution points opposite to the proposed high-volatility Short-loss mechanism.

## Score magnitude and boundary sensitivity

`abs(score) < 1e-12` is the frozen near-zero definition. Compare `near_zero_abs_lt_1e-12` with `non_near_zero_abs_ge_1e-12` for V1 and V5; RankIC, score-ranked spread, unchanged Long/Short membership, and side contribution are in [`score_magnitude_vol_attribution.csv`](../../artifacts/DM-20261001-02/run-20261001T104507Z-03/metrics/score_magnitude_vol_attribution.csv). Near-zero score rows can have little or no within-group ranking variation; the saved unique-score ratio and valid RankIC days make that visible.

| Fixed score group | Vol | Stock-days | Mean RankIC | HAC-5 t | Q5−Q1 (bp/day) | Long membership | Short membership |
|:--|:--|--:|--:|--:|--:|--:|--:|
| Near-zero | V1 | 94,354 | +0.002256 | +0.509 | -0.070 | 39.93% | 33.31% |
| Near-zero | V5 | 77,330 | +0.007317 | +1.339 | +0.210 | 28.48% | 47.37% |
| Non-near-zero | V1 | 20,488 | +0.027854 | +2.652 | +4.720 | 52.36% | 45.92% |
| Non-near-zero | V5 | 38,553 | +0.001787 | +0.242 | +2.120 | 59.55% | 39.69% |

Near-zero × V5 was not worse than near-zero × V1 on RankIC. In the non-near-zero slice, V1 was much stronger than V5. This is a mixed score-magnitude interaction inside the descriptive buckets; it does not reverse the pooled volatility result and does not justify choosing a shrinkage rule from these same dates.

Boundary sensitivity reuses the existing deterministic `1e-12 × daily score SD` BLAKE2b Code perturbation. No perturbation search or portfolio selection was run. Per-volatility changed quintile/Long/Short membership fractions and tie/near-tie boundary frequencies are in [`boundary_sensitivity.csv`](../../artifacts/DM-20261001-02/run-20261001T104507Z-03/metrics/boundary_sensitivity.csv).

| Vol | Changed quintile fraction | Changed Q1/Q2 membership | Changed Q4/Q5 membership | Exact tie boundary pairs | Near-tie boundary pairs |
|:--|--:|--:|--:|--:|--:|
| V1 | 61.51% | 35.30% | 37.67% | 7.69% | 86.75% |
| V5 | 49.45% | 30.30% | 26.71% | 10.39% | 88.23% |

High volatility had a slightly higher exact-tie and near-tie boundary-pair rate, but the fixed perturbation changed fewer quintile and tail-membership rows in V5 than V1. Boundary sensitivity therefore does not support greater assignment instability in the high-volatility bucket under this fixed stress.

## Interpretation

Predeclared checks: pooled V1>V5 RankIC = **False**; pooled V1>V5 Q5−Q1 = **False**; both predicted directions in complete years 2011–2015 = **0/5**; high-vol Short gross loss more negative = **False**; near-zero RankIC worse in V5 = **False**. The predicted deterioration is **NOT SUPPORTED**; overall results instead favor V5 on RankIC and Q5−Q1. The score-magnitude subgroup pattern is mixed and remains descriptive.

The observed Train sample is development history. These descriptive associations do not establish that volatility causes ranking errors or that a confidence adjustment improves performance. Phase 1 evaluated no strategy candidate and made no OOS claim.
