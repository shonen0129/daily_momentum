# DM-20261002-05 decision

Train-only independent family; actual trials 2/3. All Train known development data.

- **SLOW_MF_BASE**: REJECT. Failed pre-registered checks: both_sides_net_positive, pooled_netSR_beats_SLOW_CONTROL, netSR_beats_SLOW_CONTROL_4of5, bootstrap_lower_positive_SLOW_CONTROL.
- **SLOW_MF_SECTOR**: REJECT. Failed pre-registered checks: both_sides_net_positive, netSR_beats_SLOW_CONTROL_4of5, bootstrap_lower_positive_SLOW_CONTROL.

Phase2 run; Phase3 not run: gross reproducibility/side gate failed. No additional trials, Freeze, Valid or SN1 changes.

[Report](../../reports/DM-20261002-05/REPORT.md). [Full decisions](../../reports/DM-20261002-05/metrics/candidate_decision.json). Run `artifacts/DM-20261002-05/run-20261002T045605Z`.

Completion: `artifacts/DM-20261002-05/run-20261002T050345Z` finalized the saved results without new candidate trials. See [finalization audit](../../reports/DM-20261002-05/audit/saved_result_finalization.json). Two earlier technical failures are preserved.

主要理由: 対slow controlのNet SR改善はBASE/SECTORともfull-year3/5で、sectorのpooled差+0.0478もbootstrap95%CI[-0.6713,+0.7896]。年率Short net−0.842%/−0.651%、turnover0.03654/0.03807。RevisionはShort gross gate不通過で未実施。Value除外・符号反転・再重み付けを追加しない。
