# Experiment Log: DM-20260909-02

- Date: 2026-09-09T06:19:05.934883+00:00
- Run: `run-20260909T061458Z`
- Hypothesis: Fixed Momentum Long / Independent Short Ranking
- Cumulative known trial count: 48

## Trials Summary

### Trial B0
- Description: Existing Residual Momentum Baseline (M60 + EWMA alpha=0.25)
- Gross Sharpe: 0.7703
- Net Sharpe: 0.4413
- Turnover: 0.0649
- RankIC: 0.00797
- Max DD: -10.11%
- Decision: **Baseline**

### Trial T0
- Description: Stitched Momentum Control (Bitwise match against B0 required)
- Gross Sharpe: 0.7703
- Net Sharpe: 0.4413
- Turnover: 0.0649
- RankIC: 0.00797
- Max DD: -10.11%
- Decision: **却下**

### Trial T1
- Description: Fixed Long + Equal FD Short
- Gross Sharpe: 1.1263
- Net Sharpe: 0.7839
- Turnover: 0.0584
- RankIC: 0.01005
- Max DD: -7.23%
- Decision: **採用可能**

### Trial T2
- Description: Fixed Long + Equal FD x WeakPrice Short
- Gross Sharpe: 1.0438
- Net Sharpe: 0.5628
- Turnover: 0.0886
- RankIC: 0.01077
- Max DD: -8.41%
- Decision: **Promising but insufficient**

### Trial T3
- Description: Fixed Long + Equal FD x WeakPrice + RecentCrash Avoidance
- Gross Sharpe: 1.0900
- Net Sharpe: 0.0108
- Turnover: 0.1802
- RankIC: 0.00785
- Max DD: -9.86%
- Decision: **却下**

