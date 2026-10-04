# DM-20261004-01: SLOW Size / Illiquidity source diagnostic

Date: 2026-10-04 JST. Diagnostic bundle budget 1; performance candidates 0; result-driven trials 0. Seed20261004.

## Question and hypothesis
SLOW_CONTROL Net Sharpe2.09 may reflect small capitalization, illiquidity, their common exposure, conditional independent information, or interaction. Existing components are strongly correlated. Small firms and illiquid securities may share investor segmentation/limited arbitrage; independent illiquidity premium could survive the next open because trading frictions and risk are persistent. These are descriptive economic hypotheses, not causal identification. No return model or candidate selection.

Original raw inputs/winsorization/imputation/zscore stay unchanged. Existing code is reused, not edited. Original shares may lag capital changes and vendor revisions cannot be independently certified. Expected standalone turnover differences arise only from component ordering; no turnover optimization. Main leakage risks are PIT financial disclosures, trailing Amihud, future target maturity and global transforms; all transforms are by date and labels are read only after target-free decomposition is locked. Complexity is two one-regressor contemporaneous OLS plus fixed tercile sorts.

## Fixed scope and conventions
Config.json fixes all diagnostic definitions before any return results. Evaluate same known Train dates2011–2015 and2016 partial as prior SLOW experiments; purge final2 sessions of each year using t+2 maturity. Account full continuous history before selecting evaluation days. POOLED/EX2016 and yearly folds are descriptive, not unseen validation.

Three official books only: SIZE_ONLY=z_size, ILLIQ_ONLY=z_amihud, SLOW_CONTROL=zscore(mean(z_size,z_amihud)); no additional smoothing. Saved MOM60 is a descriptive baseline for AGENTS incremental metrics, no additional trial.

Within each fixed conditioning tercile, the other component is re-ranked into three fixed terciles, high-minus-low equal-weight forward target means. Residual Q5-Q1 uses five average-tie percentile bins; this is a return spread, not an official trading portfolio. Normalized components retain original missing imputation; record raw missing rates and cohort coverage. Do not filter observations based on results.

COMMON uses centered average-tie percentile ranks, while SLOW averages z components. They need not be exactly equal; report exact parity test outcome and closeness, never change definitions to force parity. Actual SLOW must strictly match saved signals, components, official weights and net; saved daily CSV read with float_precision=round_trip.

Overlap groups are an exhaustive disjoint partition, prioritizing opposite-sign SIGNAL_DISAGREEMENT; one-factor-only means other neutral. SLOW side attribution includes exit costs assigned current tercile even when current position zero. Different descriptor partitions overlap and must not be added. Attribution sums reconcile with official accounting within explicitly recorded float summation tolerance; bitwise signal checks have zero tolerance.

## Execution and reproducibility
New target-free decomposition module and experiment driver in research/experiments; meaningful regression tests in tests/workspace. Run with tools/run_bounded.py1800 seconds on prepare-run snapshot, Train-only stage and firewall. Record config/plan/code/input/reference/environment/artifact hashes, commands, checkpoints, elapsed time and peak RSS. No strategy, release, submission, Valid or existing result is edited.

Sequence: plan/config/code lock → component parity → standalone accounting → correlation/overlap → conditional/double sorts → residual diagnostics → common/disagreement → Long/Short attribution → turnover diagnostics → causality audit → report/decision. Precompute all target-free labels/residuals/ranks before loading targets. Full input future-mutation (individual and simultaneous), truncation, row shuffle and deterministic rebuild at three cutoffs include the decomposition, OLS coefficients and conditional bins. Verify raw timing, trailing rolling, PIT shares, exact Date/Code, finite coverage, t+2/fold purge, official accounting and firewall denial.

## Finish
Save requested daily/pooled/year tables, component stock-day scores/groups/cells, audits and report under artifacts/reports. Answer all eight central questions and assign A–F with statistical and measurement limits. decision.md records DIAGNOSTIC_COMPLETE/no adoption. No graveyard entry because there is no rejected candidate. Stop after this bundle; no weight/threshold/window/filter change or rescue.

Command: .venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.slow_size_illiq_diagnostic --config <run>/config.json --output <run>.
