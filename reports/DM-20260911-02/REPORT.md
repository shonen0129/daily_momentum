# DM-20260911-02: Intraday Momentum Short / Skewness-Managed FD Short

Run: `run-20260911T031800Z`. Train-only: Valid and raw target files were blocked and not read.

## Required conclusion table

| Trial | Decision | Total Net SR | Short Ann Gross | Short Ann Net | Short Gross SR | Short Net SR | Short Positive Folds | Short Improved Folds | Short Turnover |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| H0 | Reference | 0.7839 | -0.40% | -1.04% | -0.0883 | -0.2326 | — | — | 0.0258 |
| I1 | Reject | 0.1867 | -2.75% | -3.54% | -0.5650 | -0.7289 | 0 | 0 | 0.0318 |
| K1 | Reject | 0.6658 | -0.72% | -1.67% | -0.1674 | -0.3902 | 1 | 1 | 0.0379 |

## Main performance

| Trial | Total Net SR | Long Ann Net | Long Net SR | Short Ann Net | Short Net SR | Short Turnover | Total Turnover | Cost | MaxDD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| H0 | 0.7839 | 4.41% | 0.8423 | -1.04% | -0.2326 | 0.0258 | 0.0584 | 1.47% | -7.23% |
| I1 | 0.1867 | 4.41% | 0.8423 | -3.54% | -0.7289 | 0.0318 | 0.0645 | 1.62% | -9.17% |
| K1 | 0.6658 | 4.41% | 0.8423 | -1.67% | -0.3902 | 0.0379 | 0.0705 | 1.77% | -6.82% |

## Fixed Long audit

All I1/K1 Q4/Q5 memberships, Long weights, and daily Long P/L are required to equal H0 exactly; `long_fixed_audit.csv` records the zero-difference evidence.

## Fold stability

| Trial | Year | Total Net SR | Short Ann Gross | Short Ann Net | Short Gross SR | Short Net SR | Short Turnover | Q1 | Q2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| H0 | 2011 | 0.7141 | -3.12% | -3.84% | -0.5845 | -0.7187 | 0.0287 | 0.02067% | 0.03273% |
| H0 | 2012 | 0.5823 | 1.46% | 0.79% | 0.3581 | 0.1933 | 0.0268 | -0.01214% | -0.01068% |
| H0 | 2013 | 0.6858 | 0.27% | -0.35% | 0.0598 | -0.0768 | 0.0247 | -0.00374% | 0.00076% |
| H0 | 2014 | 1.4104 | -0.22% | -0.79% | -0.0561 | -0.2055 | 0.0229 | -0.00348% | 0.01240% |
| I1 | 2011 | 0.3491 | -4.72% | -5.54% | -0.7778 | -0.9129 | 0.0328 | 0.03740% | 0.03737% |
| I1 | 2012 | 0.0744 | -0.18% | -1.01% | -0.0401 | -0.2292 | 0.0333 | -0.00397% | 0.01220% |
| I1 | 2013 | -0.2272 | -4.29% | -5.07% | -0.8909 | -1.0522 | 0.0313 | 0.03927% | 0.02377% |
| I1 | 2014 | 0.8518 | -1.82% | -2.57% | -0.4669 | -0.6603 | 0.0299 | 0.01602% | 0.01144% |
| K1 | 2011 | 0.4907 | -4.09% | -5.09% | -0.7955 | -0.9893 | 0.0398 | 0.03787% | 0.02184% |
| K1 | 2012 | 0.8555 | 2.41% | 1.43% | 0.6052 | 0.3606 | 0.0388 | -0.01482% | -0.02781% |
| K1 | 2013 | 0.5908 | 0.08% | -0.89% | 0.0192 | -0.2090 | 0.0387 | -0.00254% | 0.00306% |
| K1 | 2014 | 0.9649 | -1.30% | -2.17% | -0.3634 | -0.6023 | 0.0343 | 0.01080% | 0.00968% |

## Answers

- Q1: `audit/h0_reproduction.json` records the exact C0/T1 prediction reproduction.
- Q2: `long_fixed_audit.csv` is the required zero-difference audit.
- Q3–Q8: I1 gross/net, fold counts, RankIC, quintiles, persistence, and M60 overlap are in the main table, `short_side_metrics.csv`, `intraday_momentum_metrics.csv`, and `intraday_vs_m60.csv`.
- Q9–Q16: K1 gross/net, expected-skew forecast diagnostics, underlying right-tail, and worst short P/L days are in `short_side_metrics.csv`, `expected_skewness_validation.csv`, `short_tail_diagnostics.csv`, and `short_disaster_days.csv`.
- Q17–Q20: Total-Net-SR deltas, bootstrap diagnostics, and four annual folds are in `incremental.csv`, `bootstrap_results.json`, and `fold_metrics.csv`; no independent-OOS claim is made for this previously explored Train period.
- Q21: only preregistered H0/I1/K1 were scored. Q22: cumulative known scoring count is 75 (72 prior + 3). Q23: firewall audit records no Valid or raw-label read.

## Decision rule

I1/K1 require ≥3/4 Short improvement folds, positive median ΔShort annual Net, and pooled Short Net above H0. Champion replacement also requires Total pooled Net SR above H0 and ≥3/4 Total-Net-SR improvement folds. No candidate is added after this report.

## Diagnostic interpretation and final decision

- **Q3–Q7 (I1):** Short annual gross/net was -2.75%/-3.54%, with gross/net Sharpe -0.5650/-0.7289. It improved H0 in 0/4 folds and had a positive Short fold in 0/4; pooled Short Net was negative. The I1 RankIC was -0.00037 (HAC t=-0.078; hit=48.8%). Thus neither gross alpha nor cost supported I1: annual cost also rose 1.47%→1.62%.
- **Q8:** I1 was not an independent Short source in this data. Its intended Short-direction daily Spearman correlation with M60 averaged 0.6966, and its Short-quintile overlap averaged 58.6%. Its own rank persistence was high (0.9833), so failure was directional alpha, not merely excessive rank turnover.
- **Q9–Q13 (K1):** Short annual gross/net was -0.72%/-1.67%, with gross/net Sharpe -0.1674/-0.3902. It improved H0 in 1/4 folds and was positive in 1/4; pooled Short Net remained negative. Its extra turnover raised annual cost 1.47%→1.77%.
- **Q14:** The expected-skew forecast had positive but modest descriptive monthly validation: mean next-month RankIC 0.0390, Pearson 0.0421, and top-minus-bottom realized skewness 0.0780 (75 monthly cross-sections). This did not translate into portfolio alpha.
- **Q15–Q16:** K1 reduced pooled Short-underlying positive-return p90/p95/p99 from 1.82%/2.59%/4.78% to 1.75%/2.48%/4.48%. Worst 1%/5% daily Short net losses also improved from -0.940%/-0.635% to -0.888%/-0.613%. The risk benefit was smaller than the loss of gross alpha and added cost.
- **Q17–Q20:** I1/K1 Total Net SRs were 0.1867/0.6658 versus H0 0.7839; neither improved any required stability criterion. I1's paired 20-day bootstrap ΔShort-SR 95% interval was [-0.875, -0.113]; K1's was [-0.438, +0.140]. On this previously explored Train period, neither literature-based hypothesis is a Champion replacement; I1 is decisively weaker, while K1 offers a tail-risk diagnostic benefit that is not investable under the fixed formulation.

**Decision: reject I1 and K1; retain H0 C0/T1 as Champion.** No Freeze or Valid evaluation was performed.
