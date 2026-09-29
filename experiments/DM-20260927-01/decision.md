# DM-20260927-01: Candidate C Asymmetric EWMA — decision

- **Status:** completed; fixed Train diagnostic only, not eligible for selection.
- **Run:** `run-20260926T165750Z-01`; 5 comparison rows/configured signals; evaluation 2011-01-04–2016-03-29. Valid not accessed.
- **Specification:** one fixed pair `alpha_high=0.15`, `alpha_low=0.50`, applied to BOX and B00. No parameter search or model retraining.
- **Result:** C_BOX improves over `A_LOW_NO_CARRY` by +0.0178 Net Sharpe / +0.444 annual Net percentage points. Turnover falls from 0.04589 to 0.03229/day, annual cost falls by 0.341 points, Q1 zero-score Short weight falls from 51.87% to 10.55%, and zero-code-order Spearman falls from 0.903 to 0.755. But Gross Sharpe falls from 1.024 to 0.935, ex-2016 Net Sharpe falls from 0.698 to 0.654, and 2015 annual Net return deteriorates from -0.187% to -0.416%.
- **Mechanism:** A's net deterioration versus BOX combines -0.281 points annual Gross Return (including -0.315 points selection contribution) with +0.352 points annual cost. C versus A adds +0.103 Gross Return and saves 0.341 cost points. This supports a rank/turnover/cost effect, but does not remove evidence of lost selection. The C pair also changes High alpha, so A-to-C effects cannot be assigned solely to Low carry.
- **BOX-specificity:** the same rule on B00 gives +0.0203 Net Sharpe / +0.041 annual Net points versus B00_BASE. C_BOX trails C_B00 by 0.0833 Net Sharpe / 0.407 annual Net points. Do not call this a BOX improvement.
- **Decision:** do not adopt Candidate C for BOX. Interpretation is mixed/inconclusive (D). No follow-up alpha values are proposed; this fixed Train series is closed.
- **Report:** [ASYM_EMA_RESULTS.md](../../reports/DM-20260927-01/ASYM_EMA_RESULTS.md).
- **Verification:** focused Candidate C tests 4/4 passed; `make check` passed (29 experiments, 129 frozen hashes); exact prior score/weight/account replay, official quintile match, 809,636-row coverage, Train firewall, PIT sector coverage, and component additivity passed. No feature builder or strategy source changed. No bootstrap run.
- **Failed diagnostic attempt retained:** `artifacts/DM-20260927-01/run-20260926T165750Z` used an already-purged source date index and stopped before producing portfolio results. Successful run used the saved 1,275-date evaluation index directly.
