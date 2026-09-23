# DM-20260910-02: Daily Return Information Long / Short

Run: `run-20260909T161108Z`。Train-only。Validおよびraw targetは未参照。原論文の月次予測を日次targetへ適応した有限比較であり、直接replicationではない。

## Main result

| Trial | Total Net SR | Long Ann Net | Long Net SR | Short Ann Net | Short Net SR | Turnover | Cost | MaxDD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| H0 | 0.7839 | 4.41% | 0.8423 | -1.04% | -0.2326 | 0.0584 | 1.47% | -7.23% |
| D1 | -0.9916 | 2.70% | 0.6129 | -5.49% | -1.2738 | 0.0016 | 0.04% | -11.79% |
| D2 | -0.9749 | 2.71% | 0.6189 | -5.43% | -1.2601 | 0.0020 | 0.04% | -11.47% |
| D3 | -0.9560 | 2.66% | 0.6032 | -5.34% | -1.2451 | 0.0020 | 0.05% | -11.36% |

## Decisions

| Trial | Classification | Total replacement | Long replacement | Short replacement | Net-SR improved folds | Long improved folds | Short improved folds |
|---|---|:---:|:---:|:---:|---:|---:|---:|
| D1 | Neither | FAIL | FAIL | FAIL | 0/4 | 1/4 | 0/4 |
| D2 | Neither | FAIL | FAIL | FAIL | 0/4 | 1/4 | 0/4 |
| D3 | Neither | FAIL | FAIL | FAIL | 0/4 | 1/4 | 0/4 |

## Required answers

- D1: Total Net SR did not exceed H0 (-0.9916 vs 0.7839); Long annual Net/SR=2.70%/0.6129, ΔLong Net=-1.71%; Short annual Net/SR=-5.49%/-1.2738, ΔShort Net=-4.45%.
- D2: Total Net SR did not exceed H0 (-0.9749 vs 0.7839); Long annual Net/SR=2.71%/0.6189, ΔLong Net=-1.69%; Short annual Net/SR=-5.43%/-1.2601, ΔShort Net=-4.39%.
- D3: Total Net SR did not exceed H0 (-0.9560 vs 0.7839); Long annual Net/SR=2.66%/0.6032, ΔLong Net=-1.75%; Short annual Net/SR=-5.34%/-1.2451, ΔShort Net=-4.30%.
- Q1–Q10: main table and fold-level `fold_metrics.csv` provide total, Long, Short, positive and Champion-improvement fold counts. Best total DRI trial is D3 (Neither).
- Q11–Q13: `turnover_cost_decomposition.csv` reports D1→D2 smoothing and D2→D3 residualization; no additional window, alpha, transform, model, or hybrid was scored.
- Q14–Q16: `dri_correlations.csv`, `dri_overlap.csv`, `elasticnet_coefficients.csv`, `coefficient_stability.csv`, `quintile_metrics.csv`, and `tail_diagnostics.csv` contain the predeclared independence, coefficient, and monotonicity diagnostics.
- Q17: all annual fold metrics are retained; pooled performance was not used alone for selection.
- Q18: runtime firewall and audit files record Train-only accesses; no Valid or raw target file was opened.

## Elastic Net preregistration

The original paper's annual expanding re-estimation was confirmed. Its exact penalty-selection procedure could not be safely reproduced from the accessible source, so RAW and RES each selected one fixed alpha using only the preregistered 2008–2010 chronological validation blocks. The selected alpha was not changed after scoring.

| Variant | alpha | pooled MSE |
|---|---:|---:|
| raw | 0.001 | 0.00025326801 |
| res | 0.001 | 0.00025324646 |

## Descriptive-only 2015–2016-03

This previously explored Train period was run only after decision calculation and did not alter it.

| Trial | Net SR | Long Ann Net | Short Ann Net | Turnover |
|---|---:|---:|---:|---:|
| H0 | 0.2185 | 5.29% | -4.20% | 0.0603 |
| D1 | -2.5157 | 4.05% | -10.67% | 0.0038 |
| D2 | -2.5428 | 4.05% | -10.64% | 0.0042 |
| D3 | -2.5014 | 4.19% | -10.64% | 0.0043 |

## Detailed required answers

1. **Q1:** No. Best DRI was D3 at -0.9560 Net SR, versus H0 at +0.7839.
2. **Q2–Q4:** D1/D2/D3 Long annual Net was +2.70%/+2.71%/+2.66%, with Net SR +0.6129/+0.6189/+0.6032. Each was below H0 Long (+4.41%, +0.8423) by -1.71/-1.69/-1.75 percentage points; only 1/4 folds improved.
3. **Q5–Q7:** D1/D2/D3 Short annual Net was -5.49%/-5.43%/-5.34%, with Net SR -1.2738/-1.2601/-1.2451. Each was below H0 Short (-1.04%, -0.2326) by -4.45/-4.39/-4.30 percentage points; none had positive Short Net or improved H0 in any fold.
4. **Q8–Q10:** The Short leg was the dominant failure: it lost 4.30–4.45 points of annual Net versus H0, while Long lost 1.69–1.75 points. Long was positive in 4/4 folds for all DRI variants but only improved H0 in 1/4; Short was positive in 0/4 and improved H0 in 0/4.
5. **Q11–Q13:** D1 turnover was only 0.0016, so cost was not the failure. EWMA raised, rather than reduced, turnover to 0.0020 because D1 was almost constant; it improved Net SR only +0.0167 and did not retain useful alpha. RES D3 added +0.0189 Net SR versus D2 but remained strongly negative.
6. **Q14:** Mean daily Spearman DRI correlations with M60/FD were respectively D1 +0.0004/+0.0434, D2 +0.0009/+0.0109, D3 +0.0072/+0.0434. Q5-M60-Q5 and Q1-FD-Q1 overlaps were about 18–19%, close to the 20% random membership benchmark.
7. **Q15:** No meaningful coefficient stability can be claimed: both RAW and RES selected alpha=0.001 at the upper preregistered grid boundary, and every annual fit had 0 non-zero coefficients.
8. **Q16:** No. DRI Q1–Q5 returns were non-monotone in every candidate; its pooled diagnostic monotonicity was -0.2 (D1) and similarly failed for D2/D3.
9. **Q17:** The result was not a single-year exception: all four DRI Total Net SR fold outcomes were below H0. The year-level table is `fold_metrics.csv`.
10. **Q18:** Yes. The Train-only runtime firewall log records no Valid or raw-target read; causality, annual-cutoff, prediction-coverage, allocation, determinism, and H0-reproduction audits passed.

## Interpretation

The preregistered daily adaptation did not fail through trading cost: D1's annual cost was only 0.04%. It failed because the initial-history CV selected the upper alpha boundary, fully shrinking every annual DRI coefficient. This is a rejection of the fixed experiment specification, not a licence to tune the grid after seeing these results.
