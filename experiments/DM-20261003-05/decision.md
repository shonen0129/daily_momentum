# DM-20261003-05: REJECT

**B. Gross-only improvement**. [Report](../../reports/DM-20261003-05/REPORT.md).

POOLED Net Sharpe: candidate 1.651102 vs SLOW 2.093538; EX2016: 1.674876 vs
2.097190. Δannual gross +1.31bp is smaller than Δannual cost +49.39bp;
Δannual net -48.08bp. Turnover is 2.514549×SLOW, above the fixed1.50 cap.
2011–2015 Net Sharpe improves in1/5 years; primary paired bootstrap95% CI
[-1.007035,0.119568] fails lower>0. Short net and MaxDD also fail. Keep SLOW
alone for this known-Train comparison; end the fixed1:1:1 experiment.

Scientific performance source: `artifacts/DM-20261003-05/run-20261003T143918Z`.
Audit/decision completion: `artifacts/DM-20261003-05/run-20261003T144512Z`.
Saved metrics/score/bootstrap hashes were preserved; completion added0 trials.

| gate | passed |
| --- | --- |
| full_year_net_sharpe_improvements_ge4 | False |
| POOLED_net_sharpe_gt_slow | False |
| POOLED_annual_net_ge_slow | False |
| POOLED_long_net_gt0 | True |
| POOLED_short_net_ge_slow | False |
| POOLED_maxdd_magnitude_le_slow | False |
| POOLED_turnover_le_1p50_slow | False |
| POOLED_incremental_gross_gt_incremental_cost | False |
| EX2016_net_sharpe_gt_slow | False |
| EX2016_annual_net_ge_slow | False |
| EX2016_long_net_gt0 | True |
| EX2016_short_net_ge_slow | False |
| EX2016_maxdd_magnitude_le_slow | False |
| EX2016_turnover_le_1p50_slow | False |
| EX2016_incremental_gross_gt_incremental_cost | False |
| primary_bootstrap_lower_gt0 | False |

One fixed trial; zero rescue; Historical Valid / Valid not read.
