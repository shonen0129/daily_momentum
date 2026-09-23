# DM-20260911-01: Advanced DTI Representation Research

Run: `run-20260911T000002Z`. Train-only; Valid and raw target were not read.

## Main table

| Trial | Gross SR | Net SR | Ann Gross | Ann Cost | Ann Net | Turnover | Long Net SR | Short Net SR | MaxDD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| H0 | 1.1263 | 0.7839 | 4.83% | 1.47% | 3.36% | 0.0584 | 0.8423 | -0.2326 | -7.23% |
| D0 | 0.9496 | -2.8882 | 2.60% | 10.50% | -7.90% | 0.4183 | -0.4091 | -1.1830 | -30.73% |
| S0 | 1.0804 | 0.0882 | 3.66% | 3.36% | 0.30% | 0.1339 | 0.7196 | -0.4766 | -4.43% |
| A1 | -1.2324 | -2.6996 | -2.93% | 3.49% | -6.43% | 0.1390 | -0.0706 | -1.3300 | -25.24% |
| S1 | -1.2293 | -2.6529 | -3.14% | 3.64% | -6.78% | 0.1447 | -0.0762 | -1.4137 | -26.20% |
| U1 | -0.8126 | -1.9325 | -2.47% | 3.40% | -5.87% | 0.1355 | 0.0403 | -1.2834 | -22.90% |
| R1 | -0.4282 | -1.5644 | -1.27% | 3.39% | -4.66% | 0.1348 | 0.2510 | -1.1067 | -18.11% |

## Required answers

- Q1–Q3: D0→S0 turnover -0.2844, annual cost -7.14%, Gross SR +0.1308, Net SR +2.9764; S0 salvage=False.
- Q4–Q9: representation increments relative to S0/A1 are in `incremental.csv`; no unregistered candidate was run.
- Q10–Q15: best Gross SR=S0 (1.0804); best Net SR=S0 (0.0882). DTI salvage, long and short statuses are in `trial_registry.json`.
- Q16–Q24: break-even cost, gross retention, annual folds, quintiles, tails, coefficient blocks, stability, dispersion, and bootstrap diagnostics are retained in the linked CSV/JSON outputs. Turnover is reported directly in the main and fold tables; no separate within-quintile attribution is used for this decision.
- Q25: Champion replacement candidates: none.
- Q26: cumulative known scoring trials = 72 (65 prior + 7 fixed current candidates).
- Q27: No feature, smoothing, window, target, model, or candidate was added after results.
- Q28: firewall audit records no Valid or raw-target access.

## Decision

- D0: salvage=False; Champion replacement=False; gross-only=True.
- S0: salvage=False; Champion replacement=False; gross-only=False.
- A1: salvage=False; Champion replacement=False; gross-only=False.
- S1: salvage=False; Champion replacement=False; gross-only=False.
- U1: salvage=False; Champion replacement=False; gross-only=False.
- R1: salvage=False; Champion replacement=False; gross-only=False.

## Interpretation and stop condition

S0 isolates the benefit of strong smoothing: versus D0, turnover fell by 0.2844 and annual cost by 7.14 percentage points while Gross SR rose 0.1308. It produced a small positive pooled Net SR (0.0882) and a positive Long Net SR (0.7196), but only 1/4 Net-SR folds was positive and the Short Net SR remained -0.4766. It therefore fails the preregistered DTI-salvage rule.

A1 degraded Gross SR by 2.3128 and Net SR by 2.7879 relative to S0. Adding sign did not repair it (S1 Net SR -2.6529); separating up/down improved on A1 but remained -1.9325; R1 was the strongest advanced representation (RankIC 0.00931, Net SR -1.5644) but still had negative Gross and Net returns. No candidate had a positive Short Net SR or met Champion replacement. Sorted-vector coefficient blocks generally carried more absolute coefficient mass than chronological blocks, but this was not investable alpha.

The break-even one-way cost was 2.46 bps for D0 and 10.85 bps for S0. A1/S1/U1/R1 had negative Gross P/L and hence no positive break-even cost. Q1–Q5 monotonicity was 1.0 for S0 but negative for all advanced representations; RankIC alone was not used for selection. All new models had nonzero coefficients and nonzero daily dispersion, so rejection is performance-based rather than an all-zero-model degeneracy.

The research is closed under the preregistered stop condition. No alpha, window, median baseline, return scaling, interaction, hybrid, model, or Valid-driven revision was added.
