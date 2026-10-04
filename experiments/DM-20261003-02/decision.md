# DM-20261003-02 decision

Exactly2/2 fixed performance trials, Train-only.

- **SLOW_FUND_EVENT** — REJECT. Failed: pooled_net_sharpe, ex2016_net_sharpe, full_year_improvements_4_of_5, bootstrap_lower_gt0, annual_net, turnover_le_1_25x, short_net_ge_control.
- **SLOW_CAUSE_AWARE** — REJECT. Failed: pooled_net_sharpe, ex2016_net_sharpe, full_year_improvements_4_of_5, bootstrap_lower_gt0, annual_net, turnover_le_1_25x, short_net_ge_control, B_net_sharpe_gt_A, B_annual_net_gt_A, Flow_incremental_cost_lt_gross.

[Report](../../reports/DM-20261003-02/REPORT.md). [All gates](../../reports/DM-20261003-02/metrics/candidate_decision.json).

Immutable SLOW_CONTROL preserved. No rescue/event-window/weight/threshold changes. Observed cause proxies only; no Valid/release/external submission.

Final verification:34 tests/24 real-Train prefix cases PASS; unchanged saved anchor and rank-only portfolio, exact809636-row signals, official P/L and turnover/state reconciliation PASS. Both candidates improve NetSR in0/5 full years. All-fold/diagnostic t+2 maturity excludes terminal Train spillover; delivered ALL_TRAIN descriptive metrics also purged. Report-only failed run retained; completion adds0 trials. Existing make check blocked by DM-20261002-04 metadata; own metadata and129 Freeze hashes PASS.
