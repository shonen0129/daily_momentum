# DM-20261001-03: SN1 source × magnitude × VOL20 diagnostic

Status: completed. Fixed Train-only attribution; no strategy candidate or prediction change.

## Hypothesis and scope

The existing SN1_H1 predictive content may vary jointly with its selected source (High, Low, or D fallback), the frozen score magnitude split, and the fixed prior-only VOL20 quintile. The preregistered directional checks are: (H1) for non-near-zero scores, V1 has stronger ranking quality than V5; (H2) for near-zero scores, V5 is at least as strong as V1; (H3) this reversal differs between High and Low selected source; and (H4) existing Long profit and Short loss have identifiable source × magnitude × volatility attribution. All outputs describe the same current membership and weights.

Trading strategy change: **None**. Do not alter scores, source precedence, weights, membership, costs, or thresholds; do not filter, veto, rescale, refit, optimize, or evaluate a candidate. Phase 2, if justified, must use one candidate in a new experiment ID.

## Fixed definitions

- Baseline: current `SN1_H1`; re-run current and independent baseline routes and match both saved references bit for bit before diagnosis.
- Selected source: existing contract, `Low` when `low_state < 0`; otherwise `High` when `low_state == 0` and `high_state > 0`; otherwise `D fallback`. Do not read the combined Train/Valid source-state artifact; reconstruct only from Train inputs and the reproduced baseline.
- Magnitude: `Near-zero = abs(score) < 1e-12`; `Non-near-zero = abs(score) >= 1e-12`.
- VOL20: exact `DM-20261001-02` definition: sample SD (`ddof=1`) of the prior 20 stock observations of `raw_return - PIT beta × TOPIX`, shifted one stock observation, with `features.segment_keys` reset, exactly 20 finite inputs, and no imputation. Per-date available-value average percentile ranks map to V1–V5 using `clip(ceil(5*pct)-1,0,4)`.
- Boundary perturbation: exact prior fixed perturbation, `1e-12 × full daily score SD × BLAKE2b(Code, digest_size=8, key=b"SN1-20260928")` mapped to `[-0.5,0.5)`; no perturbation search.
- Existing event age, sleeve age, event-age bucket, renewal count, and renewal bucket definitions are reused unchanged from the Train reconstruction contract. Age is descriptive only.

## Fixed primary comparisons and result rule

Create the complete Source × Magnitude × V1–V5 matrix for High, Low, and D fallback, pooled 2011–2016 and separately by each calendar year. 2016 is partial and reported separately. Within each fixed cell, calculate daily cross-sectional RankIC and SN1-score-ranked Q1–Q5 target spread; also report unchanged portfolio accounting contributions.

For High and Low source separately, compare V1 with V5 within Near-zero and Non-near-zero. The central reversal is H1 plus H2: non-near-zero V1 > V5, while near-zero V5 >= V1, evaluated on both RankIC and Q5−Q1 spread. SUPPORT requires at least one of High or Low to show this paired pooled ordering on both measures and the corresponding directional ordering in at least 3 of the 5 complete years (2011–2015). MIXED applies when at least one pooled comparison has the preregistered direction but the paired or year-stability rule fails, or RankIC and spread conflict. NOT SUPPORTED applies when neither source shows the paired pooled reversal. These are descriptive labels, not inferential tests; show all cells and annual values. P/L concentration is reported as supporting attribution, not a gate that can change the rule.

## Attribution and diagnostics

Use unchanged official `evaluation.weights(score)` and the official Train H1 target. For each source × magnitude × volatility cell report observations, active dates, score summaries and whole-cross-section score percentile, RankIC/HAC-5/hit rate, descriptive within-cell Q1–Q5/spread and monotonicity, centered target rank, target mean/SD, membership shares, absolute gross-weight share, annualized gross/net contribution and net-contribution Sharpe, turnover, and cost. Side tables split existing Long and Short gross/net/cost/turnover attribution by all fixed cells; membership shares include Neutral in the primary matrix. Attribute position changes and their costs to the current signal-date cell and state this convention.

Boundary sensitivity decomposes the fixed perturbation by Source × Magnitude × {V1,V5}; report changed quintile/Q1-Q2/Q4-Q5 membership and exact/near-tie boundary pairs and endpoints. Age/renewal tables overlay only the already fixed event-age, sleeve-age, and same-side renewal buckets. Year matrices save every fixed cell, with 2016 clearly marked partial.

## Data, causality, and limits

Train only, 2008-11-04 through 2016-03-31 for baseline reconstruction; diagnostic periods 2011–2016, with 2016 partial. The official `target_1day_train.parquet` is used solely for the established Train baseline fit/reproduction and target attribution. No Valid, combined Train/Valid state artifact, or raw-target file may be opened. No model is fit for this diagnostic; the existing fixed expanding Ridge route is replayed only to establish baseline identity.

Train observations are development-history evidence, not independent OOS. The analysis is observational attribution: it cannot show that volatility causes alpha or losses, or that removing/overweighting a cell improves returns. No OOS claim.

## Validation and budget

Exactly one fixed diagnostic run; candidate fits: zero. Require source scan and Train-only firewall, baseline bitwise parity, source reconstruction parity, index/coverage and deterministic VOL20 checks, official daily-account and cell-attribution reconciliation, and future-mutation prefix invariance at the three frozen cutoffs (`2012-06-29`, `2014-06-30`, `2015-06-30`) for baseline features/score, VOL20, source/state, and ages through each cutoff. Mutate all five staged Train sources strictly after cutoff and ensure changed inputs are confirmed. No Valid execution.

Run command (1,800-second bound):

`.venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.sn1_source_magnitude_volatility --data-dir artifacts/DM-20261001-02/run-20261001T104507Z-03/input_train --output-dir artifacts/DM-20261001-03/<run_id> --run-json artifacts/DM-20261001-03/<run_id>/run.json`

Save plan/config/run snapshots, baseline and source audits, source × magnitude × VOL20 matrix, side attribution, annual matrix, boundary sensitivity, age/renewal matrix, reconciliation, and `reports/DM-20261001-03/REPORT.md`.
