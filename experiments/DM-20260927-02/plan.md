# DM-20260927-02: Low-fast-only EWMA diagnostic

Status: planned. This is one fixed known-Train diagnostic, not parameter selection or OOS validation.

## Hypothesis

The prior `A_LOW_NO_CARRY` turnover jump may come from the discontinuity created by deleting Low state after its event day. Keeping High persistence exactly at the existing `alpha=0.25` and applying only `alpha_low=0.50` could preserve Q1 stability and reduce cost while limiting the old Low contribution. The same transform on B00 distinguishes a general persistence-rule effect from a BOX-specific result.

## Fixed specification

One pair only: `alpha_high=0.25`, `alpha_low=0.50`; no alternate alpha values. Evaluate exactly `B00_BASE`, `BOX_ORIGINAL`, `A_LOW_NO_CARRY`, `C_ASYM_EWMA`, `C_B00_ASYM_EWMA`, `D_LOW_FAST_ONLY`, and `D_B00_LOW_FAST_ONLY`. High and Low raw streams, event definitions, saved Ridge outputs, universe, folds, two-date annual purge, `t+1 Open -> t+2 Open` target, transaction cost (10 bps one-way), five-quintile qcut/normalization, tie-break, and execution timing remain as in the existing experiment.

High and Low raw streams are reconstructed by exact inversion of the saved common-alpha `adjust=False` EWMA (`alpha=0.25`), then split by their existing signs. D applies the existing listing-segment EWMA to High with `alpha=0.25` and Low with `alpha=0.50`, summing the states. Runtime assertions verify that D's High state matches BOX's High state and that the first five prior score/weight series replay the preceding diagnostic.

## Train-only evaluation

- Signal source: `artifacts/DM-20260925-03/run-20260926T063602Z/predictions/signals.parquet`.
- Reuse the completed evaluation span and diagnostics in `DM-20260927-01/run-20260926T165750Z-01`.
- Train target/PIT sector sources only: `target_1day_train.parquet`, `listed_info_train.parquet`.
- Evaluation: 2011-01-04–2016-03-29 (1,275 days); 2016 partial: 2016-01-04–2016-03-29 (59 days); report ex-2016 and each year.
- Cost: 0.001 one-way; annualization: 252. Valid files/targets are prohibited.

## Diagnostics and decision rule

Report full gross/common/selection/trading/net results, paired period changes, event-age and zero-score sleeve attribution, score ranks, Q1/Q5 retention/entrants/exits/weight turnover, sector concentration, and exact High-state equality. Reuse `research.evaluation.bootstrap_delta` with its existing circular block procedure: 20-day blocks, 1,000 repetitions, seed 20260925. Run the three pre-specified comparisons: D_BOX vs BOX, D_B00 vs B00, and D_BOX vs D_B00. Bootstrap intervals are descriptive known-Train diagnostics, not OOS evidence.

Candidate D is not called promising solely from pooled Sharpe. Require improvement direction versus BOX, markedly lower turnover and Q1 zero-score Short dependence than A, non-worse ex-2016, and no dependence on a single one of 2011/2015. Classify one of A–E in the final report; no follow-up alpha or threshold search is allowed.

## Reproducibility and verification

Save the fixed config, git commit, run time, Train/data/source hashes, library versions, candidate names, parameters, cost, and outputs. Reuse saved predictions and prior diagnostic helper functions; no feature rebuild or Ridge fit. Add focused tests for High-state identity, Low-only update, score decomposition, and future-prefix invariance. Run `make check`, focused tests, and one bounded Train-only evaluation. No Valid evaluation.

## Known results

The previous fixed Candidate C changed both sides (`alpha_high=0.15`, `alpha_low=0.50`), so it could not isolate Low persistence. Full details are in `reports/DM-20260927-01/ASYM_EMA_RESULTS.md`. All evaluation dates are already seen Train data.

## Command

```sh
.venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.box_asym_ewma_low_fast_only --config artifacts/DM-20260927-02/<run-id>/config.json --output artifacts/DM-20260927-02/<run-id>
```
