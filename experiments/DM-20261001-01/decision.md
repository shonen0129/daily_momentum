# DM-20261001-01: decision record

Completed 2026-10-01 JST. **Decision: REJECT the fixed UP_PULLBACK feature addition.** The primary Mean RankIC gate was nonpositive; gross-return and Q5−Q1 gates were slightly positive.

- Final recovered run: [`run-20261001T052315Z`](../../artifacts/DM-20261001-01/run-20261001T052315Z/run.json); report: [REPORT.md](../../reports/DM-20261001-01/REPORT.md).
- Exactly one registered candidate was tested. Two prior technical attempts are retained as failed runs. Final report recovery used saved predictions, metrics, attribution, and passing audits; it performed zero additional candidate fits.
- Train inputs: 2008-11-04–2016-03-31; expanding folds 2011–2016; 2016 had 61 sessions and was partial. All dates and the motivating attribution bucket were previously inspected development history, not independent OOS evidence. Valid and raw target were not opened.

## Primary gates

- Mean RankIC: 0.012506495 → 0.012505239; delta -0.000001256 — **FAIL**.
- Annualized gross return: 4.77443% → 4.77907%; delta +0.4638 bp/year — **PASS**.
- Q5−Q1: 4.76534 → 4.77514 bp/day; delta +0.00979 bp/day — **PASS**.

Mean RankIC is lower, so the strict three-gate rule rejects this candidate. Excluding partial 2016, the deltas are RankIC -0.000001731, gross return -0.2741 bp/year, and Q5−Q1 -0.00035 bp/day. The pooled gross lift depends on the partial year.

Long contribution changed +0.0678 bp/year and Short contribution +0.3959 bp/year. Turnover rose +0.00000860 per day and full one-way annualized cost rose +0.02168 bp/year. Gross return also rose, so the net change is not explained by lower trading cost.

In `UPSTATE=1, x<0`, mean score change was positive, but net Q4/Q5 migration was -1 rows (baseline 6,394; candidate 6,393). That bucket's annualized gross contribution changed +0.1376 bp/year. The feature did not move additional bucket rows into Q4/Q5.

## Verification

- Current SN1_H1 matched an independent current-code rebuild and the saved DM-20260930-02 baseline bit for bit on 809,636 rows.
- Static source/leak scan, exact feature formula/column contract, 2014-06-30 future mutation of all five Train inputs including Train target, and feature/baseline/candidate prefix equality passed.
- Index coverage, 809,636 finite scores per strategy, deterministic candidate replay, two-position label maturity purge, and Train-only firewall passed.
- Model and metric generation finished in 115.0 seconds under the 1,800-second deadline. A report-render path error was recovered using saved artifacts with zero additional candidate fits.
- No new feature, parameter, threshold, horizon, Valid evaluation, or Freeze followed the result.

This rejects only this fixed `UP_PULLBACK` feature addition to SN1_H1. It does not reject Event Box generally, pullbacks generally, or trend following generally.
