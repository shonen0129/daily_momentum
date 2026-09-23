# DM-20260909-03: Continuous Fundamental Weakness Short

Run: `run-20260909T080902Z`. Train-only; Valid and raw target were not opened. No Freeze/submission was created.

## Result

| Trial | Decision | Net SR | ΔNet SR vs C0 | Short annual Net | ΔShort annual Net | Turnover | RankIC | Max DD |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| C0 | Reference | 0.7839 | +0.0000 | -1.04% | +0.00% | 0.0584 | 0.01005 | -7.23% |
| C1 | 却下 | 0.7406 | -0.0433 | -1.22% | -0.18% | 0.0604 | 0.00779 | -7.36% |
| C2 | 却下 | 0.7830 | -0.0010 | -0.99% | +0.05% | 0.0558 | 0.00935 | -7.14% |
| C3 | 却下 | 0.8142 | +0.0302 | -0.81% | +0.23% | 0.0582 | 0.01041 | -7.31% |

## Primary short-side criteria (vs C0)

| Trial | Short improvement folds | Median ΔShort Net | Pooled Short > C0 | Net SR ≥ C0 | Long fixed | Decision |
|---|---:|---:|:---:|:---:|:---:|---|
| C1 | 2/4 | +0.09% | FAIL | FAIL | PASS | **却下** |
| C2 | 2/4 | +0.12% | PASS | FAIL | PASS | **却下** |
| C3 | 1/4 | -0.11% | PASS | PASS | PASS | **却下** |

## Fold detail

| Trial | Year | Net SR | ΔNet SR | Short annual Net | ΔShort annual Net | Turnover |
|---|---:|---:|---:|---:|---:|---:|
| C0 | 2011 | 0.7141 | +0.0000 | -3.84% | +0.00% | 0.0639 |
| C0 | 2012 | 0.5823 | +0.0000 | 0.79% | +0.00% | 0.0602 |
| C0 | 2013 | 0.6858 | +0.0000 | -0.35% | +0.00% | 0.0568 |
| C0 | 2014 | 1.4104 | +0.0000 | -0.79% | +0.00% | 0.0527 |
| C1 | 2011 | 0.6813 | -0.0328 | -4.16% | -0.32% | 0.0662 |
| C1 | 2012 | 0.7034 | +0.1211 | 1.29% | +0.50% | 0.0606 |
| C1 | 2013 | 0.8116 | +0.1258 | 0.54% | +0.89% | 0.0587 |
| C1 | 2014 | 0.8856 | -0.5248 | -2.60% | -1.81% | 0.0562 |
| C2 | 2011 | 0.7749 | +0.0608 | -3.56% | +0.28% | 0.0608 |
| C2 | 2012 | 0.5566 | -0.0257 | 0.76% | -0.03% | 0.0579 |
| C2 | 2013 | 0.7803 | +0.0945 | 0.27% | +0.62% | 0.0543 |
| C2 | 2014 | 1.1717 | -0.2387 | -1.45% | -0.65% | 0.0503 |
| C3 | 2011 | 0.6675 | -0.0466 | -4.00% | -0.16% | 0.0635 |
| C3 | 2012 | 0.5435 | -0.0388 | 0.72% | -0.07% | 0.0603 |
| C3 | 2013 | 0.9134 | +0.2276 | 0.98% | +1.33% | 0.0562 |
| C3 | 2014 | 1.3420 | -0.0684 | -0.96% | -0.17% | 0.0526 |

## Descriptive only: previously seen Train

2015–2016-03 and 2008–2010 were evaluated only after the fixed four-candidate comparison; they were not used for selection.

| Window | Trial | Net SR | Short annual Net | Turnover |
|---|---|---:|---:|---:|
| 2015-2016-03 | C0 | 0.2185 | -4.20% | 0.0603 |
| 2015-2016-03 | C1 | -0.1921 | -6.27% | 0.0628 |
| 2015-2016-03 | C2 | 0.6439 | -1.92% | 0.0569 |
| 2015-2016-03 | C3 | 0.3017 | -3.72% | 0.0599 |
| 2008-2010 | C0 | -1.0744 | -5.60% | 0.0613 |
| 2008-2010 | C1 | -1.6790 | -8.09% | 0.0649 |
| 2008-2010 | C2 | -1.2324 | -6.18% | 0.0584 |
| 2008-2010 | C3 | -1.0915 | -5.69% | 0.0609 |

## Conclusion

C0 is an exact reproduction control for DM-20260909-02 T1. C1–C3 are judged only by the preregistered criteria above. A positive Train short leg, if any, is not evidence of future alpha.

Artifacts: `artifacts/DM-20260909-03/run-20260909T080902Z`.
