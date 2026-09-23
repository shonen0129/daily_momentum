# DM-20260910-01: Independent Short Alpha Families

Run: `run-20260910T000003Z`. Train-only; no Valid or raw-target file was opened. No Freeze/submission was created.

## Result

| Candidate | Decision | Net SR | ΔNet SR | Short annual Net | ΔShort annual Net | Turnover | Short-positive folds | Short-improved folds | Long fixed |
|---|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| H0 | Reference | 0.7839 | +0.0000 | -1.04% | +0.00% | 0.0584 | — | — | PASS |
| V1 | Reject | 0.3966 | -0.3873 | -2.89% | -1.84% | 0.0627 | 0 | 0 | PASS |
| V2 | Reject | 0.4591 | -0.3249 | -2.59% | -1.55% | 0.0597 | 0 | 0 | PASS |
| V3 | Reject | 0.4227 | -0.3613 | -2.63% | -1.59% | 0.0940 | 1 | 0 | PASS |

## Portfolio and prediction metrics

All values use the official five-quintile weights, one-way 10 bps transaction cost, 252-day annualization, and full 974 purged evaluation days. MDD is additive daily Net P/L drawdown.

| Candidate | Gross SR | Net SR | Annual Gross | Annual Net | Annual Cost | Turnover | Max DD | RankIC | HAC t | Hit ratio |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| H0 | 1.1263 | 0.7839 | 4.83% | 3.36% | 1.47% | 0.0584 | -7.23% | 0.01005 | 2.2887 | 53.08% |
| V1 | 0.8071 | 0.3966 | 3.09% | 1.52% | 1.57% | 0.0627 | -7.10% | 0.00515 | 1.3404 | 50.72% |
| V2 | 0.8392 | 0.4591 | 3.31% | 1.81% | 1.50% | 0.0597 | -6.49% | 0.00557 | 1.4196 | 52.36% |
| V3 | 0.9852 | 0.4227 | 4.15% | 1.78% | 2.37% | 0.0940 | -7.79% | 0.01018 | 2.3644 | 52.98% |

V3's small RankIC increase did not survive the 61.0% turnover increase and higher cost; it did not improve the Short leg in any fold.

## Incremental performance versus H0

| Candidate | ΔRankIC | ΔGross SR | ΔNet SR | ΔTurnover | ΔAnnual Cost | Bootstrap 95% CI ΔNet SR |
|---|---:|---:|---:|---:|---:|---|
| V1 | -0.00489 | -0.3193 | -0.3873 | +0.0043 | +0.10% | [-0.7517, -0.0326] |
| V2 | -0.00448 | -0.2871 | -0.3249 | +0.0012 | +0.03% | [-0.6264, +0.0023] |
| V3 | +0.00013 | -0.1412 | -0.3613 | +0.0356 | +0.90% | [-0.6714, -0.0475] |

## Primary criteria

A candidate is Adoptable only with pooled Short annual Net > 0, at least 3/4 positive Short folds, at least 3/4 Short-improvement folds, positive median ΔShort annual Net, Net SR >= H0, and exact Long preservation.

| Candidate | Pooled Short > 0 | Positive Short folds | Improved Short folds | Median ΔShort > 0 | Net SR >= H0 |
|---|:---:|:---:|:---:|:---:|:---:|
| V1 | FAIL | FAIL | FAIL | FAIL | FAIL |
| V2 | FAIL | FAIL | FAIL | FAIL | FAIL |
| V3 | FAIL | FAIL | FAIL | FAIL | FAIL |

## Fold detail

| Candidate | Year | Net SR | ΔNet SR | Short annual Net | ΔShort annual Net | Turnover |
|---|---:|---:|---:|---:|---:|---:|
| H0 | 2011 | 0.7141 | +0.0000 | -3.84% | +0.00% | 0.0639 |
| H0 | 2012 | 0.5823 | +0.0000 | 0.79% | +0.00% | 0.0602 |
| H0 | 2013 | 0.6858 | +0.0000 | -0.35% | +0.00% | 0.0568 |
| H0 | 2014 | 1.4104 | +0.0000 | -0.79% | +0.00% | 0.0527 |
| V1 | 2011 | 0.5179 | -0.1962 | -5.15% | -1.31% | 0.0686 |
| V1 | 2012 | 0.2422 | -0.3401 | -0.55% | -1.34% | 0.0624 |
| V1 | 2013 | 0.2049 | -0.4809 | -2.85% | -2.50% | 0.0623 |
| V1 | 2014 | 0.7827 | -0.6277 | -3.03% | -2.23% | 0.0576 |
| V2 | 2011 | 0.4101 | -0.3040 | -5.48% | -1.64% | 0.0661 |
| V2 | 2012 | 0.2236 | -0.3587 | -0.62% | -1.41% | 0.0598 |
| V2 | 2013 | 0.3168 | -0.3690 | -2.35% | -2.00% | 0.0591 |
| V2 | 2014 | 1.1293 | -0.2811 | -1.95% | -1.16% | 0.0537 |
| V3 | 2011 | 0.2452 | -0.4689 | -6.30% | -2.46% | 0.1017 |
| V3 | 2012 | 0.5205 | -0.0617 | 0.61% | -0.18% | 0.0910 |
| V3 | 2013 | 0.3357 | -0.3501 | -2.08% | -1.73% | 0.0927 |
| V3 | 2014 | 0.8833 | -0.5272 | -2.79% | -1.99% | 0.0907 |

## Required answers

- Q1–Q5: The table above records each family relative to Champion and the primary Short/Total tests.
- Q6: Turnover and annual cost are in `model_comparison.csv` and the incremental table.
- Q7–Q9: `tail_diagnostics.csv`, `feature_correlations.csv`, and annual folds record tail separation, information overlap, and year dependence.
- Q10: `long_fixed_audit.csv` requires every difference to be zero.
- Q11: Known cumulative scoring trials are 56 (52 before this four-candidate experiment).
- Q12: Only H0/V1/V2/V3 were scored; no formula/window/candidate was added after the prepared snapshot.
- Q13: Firewall audit records Train-only reads; Valid was not referenced.

## Tail and independence diagnostics

V1 and V2 both showed high-ShortRisk returns below low-ShortRisk returns in 3/4 years in the unrestricted diagnostic, with V2 having the larger average separation. This did not translate into a viable constrained Short portfolio: every candidate's Short annual Net remained negative and every candidate lost to H0 in all four folds. V3 showed the reverse tail direction in 2011, 2012, and 2014 and materially increased turnover.

Mean daily Spearman correlations were H0-FD/V1 0.157, H0-FD/V2 0.382, H0-FD/V3 -0.035; V1/V2 0.649; V1/V3 0.078; and V2/V3 0.008. Thus V3 was the most independent from the Champion, but not profitable. The full tables are `feature_correlations.csv` and `tail_diagnostics.csv`.

## Descriptive-only previously seen Train

2015–2016-03 and 2008–2010 were generated only after the candidate decisions and did not alter them.

| Window | Candidate | Net SR | Short annual Net | Turnover |
|---|---|---:|---:|---:|
| 2015-2016-03 | H0 | 0.2185 | -4.20% | 0.0603 |
| 2015-2016-03 | V1 | -0.5058 | -7.40% | 0.0651 |
| 2015-2016-03 | V2 | -0.1582 | -6.05% | 0.0606 |
| 2015-2016-03 | V3 | -0.1928 | -6.23% | 0.1014 |
| 2008-2010 | H0 | -1.0744 | -5.60% | 0.0613 |
| 2008-2010 | V1 | -1.4877 | -6.79% | 0.0645 |
| 2008-2010 | V2 | -1.5055 | -7.14% | 0.0622 |
| 2008-2010 | V3 | -2.4776 | -10.52% | 0.0949 |
