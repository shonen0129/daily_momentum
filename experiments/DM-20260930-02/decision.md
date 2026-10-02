# DM-20260930-02: decision record

Completed 2026-09-30 JST. **Decision: reject Candidate A; Candidate B was not run. No adoption, Freeze, or Valid evaluation.** The registered 2-candidate maximum was respected: one candidate was fitted and scored.

- Successful run: [`run-20260930T081524Z`](../../artifacts/DM-20260930-02/run-20260930T081524Z/run.json); results: [`REPORT.md`](../../reports/DM-20260930-02/REPORT.md).
- A first run stopped before candidate evaluation because the archived H1 reference used the pre-split-ATR-correction feature source. The current-code SN1_H1 route was then fixed as the baseline, verified through an independent reconstruction bit for bit, and the revised plan/config were snapshotted in the successful run. Both attempts are retained.
- Train period: 2008-11-04–2016-03-31 inputs; 2011–2016 expanding evaluation folds; 2-position H1 label maturity purge. All are previously inspected Train years, not independent out-of-sample data. Valid was not accessed.

## Findings

- Candidate A versus current SN1_H1: annualized gross +1.11 bp, annualized net +1.07 bp, Net Sharpe +0.0018, and mean RankIC +0.000048. Annual gross uplift was positive in 4/6 folds, with 2016 a 61-session partial contributing +37.08 bp annualized.
- The registered information gate failed because Q5−Q1 fell 0.051 bp per day (4.765 to 4.715 bp/day). RankIC hit ratio also fell 0.08 percentage points; average turnover and annualized cost rose slightly. Quintile monotonicity was unchanged.
- The pooled UPSTATE/lower-Box bucket had positive centered target-rank attribution relative to lower-Box rows without UPSTATE, but Candidate A did not improve the portfolio spread. The pre-registered sequence therefore stopped before Candidate B; no extra search was authorized by the result.

## Verification

- Current SN1_H1 baseline: 809,636 rows bitwise equal across both code paths.
- Source/leak scan and Train-only source firewall: PASS. Only the five registered `*_train.parquet` inputs were opened; Valid and raw target were not read.
- Full feature and score future-mutation prefix-invariance at cutoff 2014-06-30: PASS, bitwise equal on 609,960 rows.
- Feature index/coverage, finite scores, synthetic deterministic replay, state persistence, purge/future-label mutation, and Candidate B model-column contract: PASS. Five strategy tests passed.
- Run bounded at 1,800 seconds; successful elapsed time 109.6 seconds.

The fixed Candidate A extension is recorded in [`GRAVEYARD.md`](../GRAVEYARD.md). Candidate B and other Event-Box variants remain untested by this experiment.
