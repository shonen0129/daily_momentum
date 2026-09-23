# DM-20260911-02 Audit Summary

- H0 prediction: exact equality with `DM-20260909-03` C0 artifact, 809,636 rows.
- Long preservation: H0/I1/K1 Q4/Q5 membership differences, maximum Long-weight difference, and maximum daily Long-P/L difference are all zero.
- Causality: all 30 features and all three trial predictions were bitwise prefix-invariant under mutation and truncation of every Train input after 2010-12-30, 2012-06-29, and 2014-12-30.
- Timing: I1 uses signal-day Raw Open/Close only; each K1 forecast's maximum characteristic and regression-target date precedes its forecast-month start.
- PIT: no Size or Industry predictor was used. H0 financial state is inherited from the existing strict backward, disclosure-date implementation.
- Determinism: fixed tie-breaks use existing rank/code ordering; repeated feature/prediction construction in every cutoff audit gave exact prefix equality.
- Firewall: only Train feature inputs, `target_1day_train` for portfolio evaluation, and the permitted historical C0 artifact were opened. Valid and raw-label reads were zero.
- Tests: `make test` completed 66/66 passed after the final code change. Bounded experiment runtime: 470.6 seconds, below 1,800 seconds.
