# DM-20260911-02: Experiment Log

- Date / run: 2026-09-11 / `run-20260911T031800Z`
- Hypotheses: H1 intraday-only momentum Short; H2 skewness-managed FD Short.
- Baseline: exact C0/T1 Champion (fixed M60 residual-momentum Long, equal FD Short).
- Candidates: exactly H0/I1/K1; no post-result candidate, window, threshold, predictor, or hybrid was added.
- Train evaluation: 2008-11-04–2016-03-31 Train, 2011–2014 annual folds, two-day boundary purge, 10 bps one-way cost.
- Result: H0/I1/K1 Net SR = 0.7839/0.1867/0.6658; Short annual Net = -1.04%/-3.54%/-1.67%.
- Decision: reject I1 and K1. I1 had no Short-improvement fold; K1 had one and retained negative Short Net despite smaller right-tail losses.
- Reliability: H0 bitwise reproduction; Long fixed audit zero differences; three-cutoff mutation/truncation prefix-invariance PASS; Train-only firewall PASS; all tests PASS; bounded elapsed 470.6 seconds.
- Valid: not accessed. Freeze/submission: none.
