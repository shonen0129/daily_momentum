# DM-20260924-C3S-v1: Valid Evaluation

## Scope and protocol

This is a one-time, post-freeze comparison of the frozen C3S zip against the exact frozen `DM-20260908-v1` baseline trial `M_res60s1_a0.25`. The earlier Valid evaluation in this workspace was for a different H0+C0/T1 strategy (`DM-20260912-01-v1`). This report uses pure H0, but it reuses the same Valid period that had already been accessed; it is **not independent OOS evidence**.

The C3S zip was frozen before this comparison. Its code, zip, and Train input hashes were checked before the Valid target was opened. Both predictions were generated from the frozen zips first, then aligned to the Valid target and scored with the official-compatible functions in `stock_comp_2026/evaluate_script.py`: five ranked quintiles, one-way transaction cost 10 bps, and 252-day annualization. No strategy or parameter changes followed the result.

- Valid period: 2016-04-01 through 2026-07-31; 2,523 trading days.
- Target rows: 1,227,148; finite-label coverage: 99.7103%.
- H0 and C3S each predicted all 1,227,148 target rows.
- Freeze and data hashes, detailed annual metrics, and daily series: [comparison JSON](../../reports/DM-20260924-01/valid_comparison.json), [daily series](../../reports/DM-20260924-01/valid_daily.csv).
- Train parity check before Valid: [TRAIN_FREEZE_VERIFICATION.json](../../reports/DM-20260924-01/TRAIN_FREEZE_VERIFICATION.json). Both frozen zips matched their research Train predictions exactly on 809,636 rows and 1,814 dates.

## Pooled results

| Metric | H0 | C3S | C3S − H0 |
|---|---:|---:|---:|
| Official Net Sharpe | -0.3899 | **-0.2409** | +0.1490 |
| Gross Sharpe | -0.0706 | -0.0097 | +0.0609 |
| Annual Gross P/L | -0.36% | -0.06% | +0.31 pp |
| Annual transaction cost | 1.63% | 1.33% | -0.30 pp |
| Annual Net P/L | -1.99% | -1.39% | +0.61 pp |
| Average daily turnover | 0.0649 | 0.0528 | -0.0121 |
| Mean RankIC | 0.0027 | 0.0058 | +0.0031 |
| RankIC HAC(5) t-stat | 0.83 | 1.61 | — |
| Q1–Q5 mean-return monotonicity (Spearman) | 0.00 | 0.10 | — |
| Additive maximum drawdown | -29.59% | -29.69% | -0.10 pp |

C3S had a less negative Net Sharpe than H0 in this period, with a small Gross improvement and lower costs. Its annual Net P/L remained negative, and its maximum drawdown was marginally worse. The annual result was mixed:

| Year | H0 Net Sharpe | C3S Net Sharpe |
|---:|---:|---:|
| 2016 | -1.677 | -1.765 |
| 2017 | 0.676 | 0.565 |
| 2018 | -0.458 | -0.086 |
| 2019 | -1.149 | -1.123 |
| 2020 | 0.196 | 0.541 |
| 2021 | -2.019 | -2.253 |
| 2022 | -1.823 | -1.367 |
| 2023 | 0.207 | 0.306 |
| 2024 | 0.316 | 0.639 |
| 2025 | 0.384 | 0.782 |
| 2026 through July | 0.283 | 0.325 |

## Long / Short contribution for C3S

The following is the C3S contribution split under the same official quintile weights. Positive weights are assigned to Long and negative weights to Short. Each leg keeps its weight contribution to the full portfolio; weights are not separately rescaled. Turnover and 10 bps one-way costs are computed by leg. Their daily Net P/L adds back to the official portfolio's daily Net P/L exactly.

| C3S leg | Gross Sharpe | Net Sharpe | Annual Gross P/L | Annual cost | Annual Net P/L | Average daily turnover |
|---|---:|---:|---:|---:|---:|---:|
| Long | 0.2741 | **0.1297** | +1.35% | 0.71% | **+0.64%** | 0.0282 |
| Short | -0.2583 | **-0.3720** | -1.41% | 0.62% | **-2.02%** | 0.0246 |

The short leg accounts for the negative full-period net contribution; the long leg is modestly positive. The two leg Sharpes do not add to the combined portfolio Sharpe because the portfolio's risk also depends on covariance between the legs.

| Year | Long Net Sharpe | Long annual Net P/L | Short Net Sharpe | Short annual Net P/L |
|---:|---:|---:|---:|---:|
| 2016 | -0.133 | -0.76% | -2.138 | -10.35% |
| 2017 | 0.722 | +2.57% | -0.199 | -0.57% |
| 2018 | 0.719 | +3.25% | -0.696 | -3.67% |
| 2019 | -0.701 | -2.80% | -0.469 | -1.91% |
| 2020 | 0.435 | +2.71% | 0.312 | +2.60% |
| 2021 | -1.157 | -5.41% | -1.131 | -4.89% |
| 2022 | -0.144 | -0.63% | -1.249 | -7.15% |
| 2023 | 0.065 | +0.25% | 0.288 | +1.12% |
| 2024 | 0.183 | +0.93% | 0.351 | +1.93% |
| 2025 | 0.695 | +3.78% | 0.050 | +0.32% |
| 2026 through July | 0.616 | +4.31% | -0.210 | -1.52% |

Full leg series and checks are in [c3s_long_short.json](../../reports/DM-20260924-01/c3s_long_short.json) and [c3s_long_short_daily.csv](../../reports/DM-20260924-01/c3s_long_short_daily.csv).

## Disposition

Treat this as a descriptive comparison on a previously accessed sample. It does not establish independent out-of-sample performance or adoption readiness. C3S remains a separate frozen research candidate; the current submission default and Champion were not changed. Do not tune the candidate from these Valid results. Any independent confirmation requires a genuinely untouched evaluation period.
