# DM-20260930-02: Event Box features added to SN1_H1

**Decision: reject Candidate A under the registered rule. Candidate B was not run.** Candidate A's pooled RankIC, gross return, and Net Sharpe edged up, but Q5−Q1 fell slightly and the improvement was too small and uneven to support the Event-Box extension. This does not test or reject Candidate B's trend-aligned pullback feature.

## Experiment and baseline

- Plan/config: [`plan.md`](../../experiments/DM-20260930-02/plan.md), [`config.json`](../../experiments/DM-20260930-02/config.json).
- Successful Train-only run: [`run.json`](../../artifacts/DM-20260930-02/run-20260930T081524Z/run.json), run ID `run-20260930T081524Z`.
- The baseline is the current SN1_H1 route after the split-date ATR unit correction from DM-20260929-01. Its two code paths matched bit for bit on all 809,636 rows.
- The archived DM-20260927-04 H1 score was not used as a comparator: it has the pre-correction feature source hash (`3c206655…`) while current SN1 uses `d2e4adba…`. A first attempt stopped at the baseline gate before evaluating an Event-Box candidate; that failed run is retained at [`run-20260930T080725Z`](../../artifacts/DM-20260930-02/run-20260930T080725Z/run.json).
- Inputs covered 2008-11-04–2016-03-31. Expanding evaluation folds were 2011–2016, with two trading positions of label maturity purge. The label was official `target_1day_train` (`t+1 Open → t+2 Open`). All these Train years had been inspected in earlier work; they are descriptive development history, not an independent holdout.
- Candidate A added 10 Event-Box state/geometry/age features to the existing side-specific Ridge. Ridge lambda, minimum event rows, annual folds, percentile mapping, source separation, smoothing, quintile weights, and one-way cost (10 bp) matched current SN1_H1. Candidate B was permitted only after positive pooled RankIC, gross return, and Q5−Q1 deltas; Q5−Q1 failed, so B was stopped before fitting.

## Pooled results, 2011–2016

Annual return and cost figures are annualized from daily means. `Q5−Q1` is a daily return spread in basis points. RankIC t-stat uses the repository's HAC-5 calculation.

| Metric | Current SN1_H1 | Candidate A | Change |
| --- | ---: | ---: | ---: |
| Gross Sharpe | 1.1221 | 1.1241 | +0.0020 |
| Net Sharpe | 1.0773 | 1.0791 | +0.0018 |
| Mean RankIC | 0.012506 | 0.012555 | +0.000048 |
| RankIC HAC-5 t-stat | 3.131 | 3.148 | +0.017 |
| RankIC hit ratio | 54.70% | 54.62% | −0.08 pp |
| Annualized gross return | 4.774% | 4.786% | +1.11 bp/year |
| Annualized net return | 4.584% | 4.595% | +1.07 bp/year |
| Annualized cost | 0.1901% | 0.1906% | +0.046 bp/year |
| Average daily turnover | 0.007618 | 0.007635 | +0.000017 |
| Compound maximum drawdown | −5.95% | −5.83% | +0.13 pp |
| Annualized Long contribution | 6.108% | 6.147% | +3.91 bp/year |
| Annualized Short contribution | −1.334% | −1.362% | −2.80 bp/year |
| Quintile monotonicity | 0.90 | 0.90 | unchanged |
| Q5−Q1 | 4.765 bp/day | 4.715 bp/day | −0.051 bp/day |

Candidate A's annualized gross-return change was positive in four of six folds. The two negative folds were 2012 (−17.33 bp annualized) and 2015 (−1.96 bp). The 2016 fold contains only 61 trading days and contributed +37.08 bp annualized, so the pooled gross lift is sensitive to that short partial year. Complete fold and annual metrics—including Q1–Q5, cost, turnover, RankIC hit/t-stat, Long/Short, and drawdown—are in [`fold_metrics.csv`](metrics/fold_metrics.csv); all baseline deltas are in [`incremental.csv`](metrics/incremental.csv). The daily accounts are also saved for [SN1_H1](metrics/daily_account_SN1_H1.csv) and [Candidate A](metrics/daily_account_CANDIDATE_A.csv).

## Event-Box attribution

Across 2011–2016, the UPSTATE and lower-Box bucket (`UPSTATE=1, x<0`) had a mean daily centered target-rank of `0.02153` over 13,686 rows and 1,185 dates. The lower-Box rows without UPSTATE averaged `0.00154` over 33,274 rows and 1,278 dates. This is descriptive conditional evidence in the proposed direction. It did not translate into a higher portfolio Q5−Q1 spread after adding all registered Event-Box features to SN1, so it does not pass Candidate A's preregistered gate. Annual bucket values and residual returns are in [`structural_attribution.csv`](metrics/structural_attribution.csv); no separate search or threshold was applied to these buckets.

## Audit and limits

- Train-only stage contained only raw returns, beta, TOPIX returns, daily quotes, and the official Train target. The runtime firewall recorded those five Train files only; Valid and raw target were not accessed.
- Source/leak scan passed. Full-panel feature and score coverage was 809,636 rows, with exact indexes and finite candidate scores. Current-baseline reproduction was bitwise equal.
- Future mutation changed every predictor source and Train target after 2014-06-30. All 21 feature columns and the SN1_H1/Candidate A scores through the cutoff were bitwise unchanged on 609,960 rows.
- Five strategy tests passed. These cover synthetic state persistence and pullback construction, deterministic/index-aligned feature output, all-source feature prefix invariance, fold maturity/purge under future feature/label mutation, and Candidate B's one-feature model contract.
- Candidate B, an independent future period, Freeze, and Valid evaluation were not run. Candidate A is rejected as this fixed Train-only extension; the result is not evidence that every Event-Box representation lacks value.

Full audit files and fitted Candidate A Ridge models are retained under [`artifacts/DM-20260930-02/run-20260930T081524Z/`](../../artifacts/DM-20260930-02/run-20260930T081524Z/).
