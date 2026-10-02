# H0 C0/T1 Freeze

Strategy ID: `DM-20260912-01-v1`  
Frozen submission: `snapshot/submission/` and `dm_h0_c0t1_submission.zip`

The frozen specification is deterministic and rule based:

- Long: 60-day, one-day-skipped market-residual momentum, daily cross-sectional rank, EWMA alpha 0.25.
- Short: equal-weight fundamental deterioration (CFO/assets YoY deterioration, CFO/assets weakness, and net-cash weakness).
- Portfolio: fixed 40% Long / 20% neutral / 40% Short score stitching, then the official five-quintile market-neutral weights.
- Cost: official one-way 10 bps transaction cost.

Before the first Valid access, the direct H0 strategy tests passed (3 tests) and the archived release hash and zip verification passed. The complete-workspace test suite exceeded its 180-second wall-clock limit without reporting an individual test failure.

Valid results are recorded separately in `VALID_EVALUATION.md`; they must not be used to alter this release.
