# H0 C0/T1 Valid Evaluation

This is the first Valid evaluation of the frozen `DM-20260912-01-v1` release. It used the frozen submission zip, the official-compatible evaluator, and `target_1day_valid.parquet`. The release was not changed after this result.

- Command: `.venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python stock_comp_2026/evaluate_script.py --data-dir stock_comp_2026/input --submission releases/DM-20260912-01-v1/dm_h0_c0t1_submission.zip`
- Exit status: 0 (within the 1,800-second hard limit)
- Valid period: 2016-04-01 through 2026-07-31; 2,523 trading days
- Prediction rows: 1,227,148 / target coverage: 99.7103%
- Scoring convention: official five-quintile market-neutral weights and one-way 10 bps transaction cost

| Metric | Value |
| --- | ---: |
| Gross Sharpe | 0.0773 |
| Net Sharpe | **-0.2390** |
| Annual gross P/L | 0.35% |
| Annual transaction cost | 1.45% |
| Annual net P/L | **-1.09%** |
| Average daily turnover | 0.0576 |
| Additive maximum drawdown | -20.44% |
| Mean RankIC | 0.00242 |
| RankIC HAC(5) t-stat | 0.831 |
| RankIC hit ratio | 51.73% |

The evaluator itself printed `SHARPE: -0.23900690`. The detailed metrics were recomputed from the same frozen zip prediction and official weight/cost formula. Sandbox-only PyArrow CPU-cache warnings did not affect the successful exit status.
