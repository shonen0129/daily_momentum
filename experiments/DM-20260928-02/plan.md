# DM-20260928-02: SN1 final structural audit

Status: `planned`. Train and already-open historical Valid are development data. Only future paper observations may be called forward OOS. Paper data is prohibited for this experiment.

## Hypothesis and scope

There may be at most one submission-relevant structural issue in fixed `SN1_H1`: a Low-branch sign/timing/reset implementation defect, a stable source-side/risk exposure mechanism, or dependence on official deterministic tie ordering. The study will separate these explanations without maximizing historical Sharpe. No strategy change is justified by descriptive attribution alone.

No model will be refit. No feature, score, age, horizon, threshold, alpha, hedge ratio, neutralization strength, holding period, or ensemble search is permitted. Existing Train and historical-Valid artifacts and the fixed H1 target are reused. Historical Valid is already observed development data.

## Why a finding could matter / why it may persist

If Low prediction sign, target date, EWMA ordering, state reset, ranking, weight sign, or P/L sign is inconsistent in the implementation, correcting it would restore the declared H1 contract. If a PIT sector/size exposure explains persistent Short losses in both development splits, a deterministic projection could be considered only if the audit implies one unique parameter-free rule. Tie sensitivity can show how much the current official `(Date, Code)` ordering contributes; it cannot authorize changing the competition ranking rule.

An event signal is entered at the next open and evaluated over the following open-to-open H1 interval. A semantic correction must preserve the existing as-of timing. Descriptive source/risk attribution does not establish that the same relation will persist after the observed history.

## Baseline and fixed inputs

- Baseline: the full saved fixed `SN1_H1` signal stream from `DM-20260927-04/run-20260927T101500Z`. Use `DM-20260928-01/intervention-results-v2` only for evaluation-window saved quintile/weight parity; its prediction files are filtered to evaluated rows and cannot substitute for the full signal history when replaying turnover.
- Train account: the exact saved H1 account dates (1,275 days; 2011-01-04–2016-03-29).
- Historical-Valid account: the exact saved H1 account dates (2,521 days; 2016-04-01–2026-07-29), already observed and development-only.
- Primary outcome: existing H1 residual return; official one-way cost 10 bps. Existing H5 results are cited only as a fixed diagnostic.
- Reuse the prior P/L-blind `date_code_state.parquet`, saved yearly H1 models/predictions, PIT `Sector17Code`, `Sector33Code`, `ScaleCategory`, and saved Train/historical-Valid target/account artifacts.
- Permitted new reads: only the exact Train and historical-Valid paths named in `config.json`. No `raw_target`, Valid target outside this historical artifact, later/paper data, or network input.
- Fixed seeds: 20260928 for deterministic code-hash and tie permutation. No resampling or candidate selection.

## Registered phases and fixed summaries

0. Record Git HEAD/status, relevant source/config/input/output hashes; independently rebuild the fixed H1 event scores from Train and historical-Valid feature panels plus saved H1 models, preserving the pre-2011 zero-signal warm-up; compare saved scores/quintiles/weights and daily Gross, Net, official Cost and Turnover to the locked artifacts. Never restart EWMA from the evaluation-window-trimmed 2011 table. Stop the new analysis if any true parity check fails.
1. Reconstruct the Low event → event feature/target → Ridge fit/prediction → signed raw score → EWMA → SN1 source → official rank/quintile/weight → H1 target → weighted account contribution contract. Save at least 100 deterministic trace rows, including reset boundary, consecutive and side-switch events, near-zero/sign coexistence, first observation, missing rows where available, and an H1 target-maturity boundary. State explicitly where a requested edge case is absent from the saved panels.
2. Attribute the fixed account by side × selected source × fixed sleeve-age/event-age buckets × fixed 60-observation renewal categories, with score-magnitude deciles descriptive only. Train and historical Valid are separate. Report stock-days, gross exposure, weight share, weighted Gross/Net contribution, RankIC and H1 cross-sectional spread; do not label attribution as counterfactual sleeve performance.
3. Decompose Short weakness into (A) event-day predictor quality, (B) state/source/rank persistence and near-zero assignment, and (C) PIT risk exposure. Reuse existing entry-score diagnostics; use no new predictor.
4. Report Long, Short, persistent Long, and persistent Short PIT sector and scale exposure, contribution, persistence, year stability, and existing market-cap/beta/volatility descriptors only if those columns are already PIT-safe and present.
5. Event-only control uses only the existing H1 event-date Ridge score; no EWMA carry, holding-period search, or new horizon.
6. Tie-only robustness uses the same saved score/target and official weight function under: Code ascending; Code descending; deterministic BLAKE2b(Code) order; fixed-seed random Code order; a deterministic perturbation of `1e-12 × daily score standard deviation`; and input row shuffle plus Parquet roundtrip. Report changed quintile/Long/Short rows, turnover, Gross/Net, side contributions and RankIC. These are sensitivity diagnostics; never select a stress ordering.
7. Audit listing segment/reset/missing-row behavior against the existing 20-market-date reset specification, using saved Train and historical-Valid state/PIT panels only. The reset threshold cannot change.
8. Fixed one-way costs: 5, 10, 20, and 30 bps. Show Gross, Net, SR, annual cost, turnover, and side contribution for `SN1_H1`; do not select a strategy by scenario.
9. Leave-one-calendar-year-out recomputation on the existing account dates, separately for Train and historical Valid. Mark partial years. Report Gross, Net, Net SR, Long/Short contribution, turnover and RankIC. Compute `SN1_H1 − D` only if saved D artifacts reproduce exactly without reopening unrelated data.

## Candidate gate and stopping rule

Candidate count is zero during the above diagnostics and is capped at one after the gate. No candidate is created before the diagnostics finish. An intervention is eligible only if Train and historical Valid show the same structural mechanism; the rule follows uniquely from that mechanism; it uses existing PIT-safe inputs; needs no fitted parameter or tuned cutoff; preserves the H1 causal contract; does not mechanically sacrifice the Long sleeve to mask Short losses; and is simple and submission-ready. If any condition fails, register Family D: none, and conclude `No structurally justified intervention candidate. Submit SN1_H1 unchanged.`

If a candidate passes, write and hash-lock its complete rule and code before reading its P/L. Exactly one P/L evaluation is allowed. No rescue, neighboring rule, or second candidate follows any result. A bug discovered in Phase 1 is reported as an implementation correction and kept separate from alpha intervention evidence.

## Known history and rejected work

The supplied request and prior artifacts already expose the expiry-60 result; that candidate is rejected. Do not create another state-age variant. Reuse `PAPER_STATE_DECISION.md`, `STATE_INTERVENTION_RESULTS.md`, `STATE_INTERVENTION_PLAN.md`, `STATE_ALPHA_DECAY.md`, `STATE_PERSISTENCE_AUDIT.md`, `PAPER_HORIZON_DECISION.md`, `HORIZON_MECHANISM.md`, `MULTI_HORIZON_RESULTS.md`, `HORIZON_TARGET_AUDIT.md`, `SN1_VALID_RESULTS.md`, `SN1_VALIDATION_READINESS.md`, `SN1_IMPLEMENTATION_AUDIT.md`, `SHORT_NIGHT_ROOT_CAUSE.md`, and `LOW_FAST_ONLY_RESULTS.md`. All prior Train and historical-Valid results are development history, not untouched validation.

## Required outputs

Create the user-requested `FINAL_LOW_BRANCH_AUDIT.md`, `SOURCE_SIDE_ATTRIBUTION.md`, `SHORT_LOSS_DECOMPOSITION.md`, `PORTFOLIO_RISK_AUDIT.md`, `SN1_ROBUSTNESS_FINAL.md`, and `SUBMISSION_DECISION.md` in this report folder. Create `FINAL_STRUCTURAL_INTERVENTION_PLAN.md` and `FINAL_STRUCTURAL_INTERVENTION_RESULTS.md` only if the gate permits exactly one candidate. Preserve raw audit tables, daily replays, and manifests in the new run directory.

## Execution and validation

Use a new `artifacts/DM-20260928-02/<run_id>/` directory and an explicit Train/historical-Valid read allowlist. Hash code, config, this plan, every input and output. Verify index uniqueness/alignment, finite score/weight coverage, all five official quintiles, deterministic replay, daily baseline parity, and no paper/raw-target reads. Use bounded execution. No Valid evaluation, submission, feature/model refit, or exploratory candidate run is part of this plan.
