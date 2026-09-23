# DM-20260910-03: Daily Turnover Information Long / Short

Run: `run-20260909T235130Z`。Train-only。Validとraw targetは未参照。これは中国A株・月次DTIのdaily-horizon adaptationであり直接replicationではない。

## Main result

| Trial | Total Net SR | Long Ann Net | Long Net SR | Short Ann Net | Short Net SR | Turnover | Cost | MaxDD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| H0 | 0.7839 | 4.41% | 0.8423 | -1.04% | -0.2326 | 0.0584 | 1.47% | -7.23% |
| M0 | -0.8450 | 0.55% | 0.0909 | -4.85% | -1.2460 | 0.0387 | 0.97% | -20.37% |
| T1 | -11.2461 | -10.93% | -2.3672 | -16.24% | -3.3325 | 1.1418 | 28.68% | -105.03% |
| T2 | -9.8885 | -9.46% | -2.1062 | -13.77% | -2.7791 | 1.0319 | 25.91% | -89.85% |
| T3 | -2.8882 | -1.75% | -0.4091 | -6.16% | -1.1830 | 0.4183 | 10.50% | -30.73% |

## Required answers

- Q1: PIT denominator preflight **PASS**. It used raw Volume divided by the last strictly-prior disclosed issued-and-outstanding share count (including treasury shares), with 450-day expiry; split-event audit is `audit/corporate_action_audit.csv`.
- M0: Net SR -0.8450 (ΔH0 -1.6290); Long Net 0.55% / SR 0.0909; Short Net -4.85% / SR -1.2460; positive Long/Short folds 2/4 and 0/4.
- T1: Net SR -11.2461 (ΔH0 -12.0301); Long Net -10.93% / SR -2.3672; Short Net -16.24% / SR -3.3325; positive Long/Short folds 0/4 and 0/4.
- T2: Net SR -9.8885 (ΔH0 -10.6725); Long Net -9.46% / SR -2.1062; Short Net -13.77% / SR -2.7791; positive Long/Short folds 0/4 and 0/4.
- T3: Net SR -2.8882 (ΔH0 -3.6721); Long Net -1.75% / SR -0.4091; Short Net -6.16% / SR -1.1830; positive Long/Short folds 1/4 and 0/4.
- Q4 / Q18–Q21: `model_comparison.csv`, `dti_correlations.csv`, `dti_overlap.csv`, `elasticnet_coefficients.csv`, and `prediction_dispersion.csv` retain the implemented comparisons.
- Q14–Q17: `turnover_cost_decomposition.csv` reports H0/M0/DTI increments and T2→T3 cost/gross decomposition. No post-result candidate, grid, target, window, denominator, or model was added.
- Q22–Q25: `fold_metrics.csv`, firewall, cutoff, causality, determinism, and coverage audits record time stability and Train-only compliance.

## Decision

- M0: Neither.
- T1: Neither.
- T2: Neither.
- T3: Neither.

## Audit and disposition

- H0 reproduction: 809,636 rows, bitwise PASS.
- Causality: future-mutation/truncation tests at 2010-12-30, 2012-06-29, and 2014-12-30 passed bitwise for all 49 features.
- Firewall: `valid_evaluation=false`, `raw_target_reads=false`.
- The experiment is rejected; no strategy is frozen and no Valid result was read.
