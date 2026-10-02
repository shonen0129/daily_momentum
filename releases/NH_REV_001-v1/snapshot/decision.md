# NH_REV_001 — fixed negative relative-strength event hypothesis

Experiment: DM-20260925-02. One candidate and one post-freeze Valid evaluation; no optimization or fitting. B00 + EWMA .25 is the fixed reference. Exact definitions and numerical gates are in config.json; this memo and config are frozen together.

## Hypothesis and rationale
Among new 250-observation high events, unusually strong preceding residual momentum may reflect crowded demand and subsequent reversal. Inventory adjustment or delayed unwinding could persist beyond the next open; this is a hypothesis, not an established mechanism. Event ranking replacement can increase turnover despite fixed EWMA. Complexity is one univariate rank. Leakage risks are future adjustments, rolling windows, rank timestamps and state continuity; all four input sources receive future-mutation tests.

## Fixed specification
Use existing event and RS60 definitions unchanged. RS60 is already the cross-sectional centered rank of the preceding 60 observed residual returns, ending t-1, not a 60-day price ratio. The event is raw-price split-safe Close_t strictly above the prior 250-observation high. Input information is known by t Close. Entry t+1 Open, exit t+2 Open; supplied market-residual target, one-way cost .001, 252-day annualization. No target reads during prediction. No training or labels required for inference.

On all high events replace B00 raw long score by .5+.5*pct_rank(-RS60 within event date). Other raw scores, including the low-event Short signal, remain B00. Smooth all scores per listing segment using alpha=.25, adjust=False. The official global ranking is unchanged. This fixes Short policy but cannot promise identical final Short holdings under a global rank transform; final long/short transmission is measured, never optimized.

## Primary sign convention and finite gates
The user hypothesis requires raw RS60 IC <= -.02. The tradable score is minus RS60, so its IC must be >= +.02; both are reported without flipping the hypothesis. Mean daily Spearman is the pooled primary; days require >=5 finite event labels and nonconstant ranks. Quintiles use daily first-tie ranks in sorted Code order with the existing official qcut boundaries. Average targets equally over complete five-quintile days. Raw Q5-Q1 must be negative; score Q5-Q1 positive.

Require raw mean IC <= -.02, HAC(5) t <= -1.645, raw quintile Spearman monotonicity <= -.5, raw Q5-Q1<0, >=252 eligible days, >=60% negative full-calendar-year ICs. After removing the most supportive 1% daily ICs, mean must remain <=-.01; after removing largest absolute 1% daily spreads, mean must remain negative. Train raw IC and spread must have the hypothesized direction. All criteria must pass. These stability gates operationalize the user's no-few-days and no-extreme-instability requirement; no gate is tuned after results.

Train 2011–2016Q1 and Valid 2016Q2–2026Jul use each year/split's final-two-signal-date exclusion inherited from Phase 1. Annual groups are chronological descriptive folds, with no fitted model. Continuous positions/cost are computed before date filtering. Full and partial years are identified separately. Missing targets follow the official cost-dropping expression; all-position costs are additionally saved. Empty metrics are missing, not zero.

## Independence limitation and decision scope
Train is already explored. The entire supplied Valid 2016-04-01–2026-07-31 was evaluated in prior releases (see releases/DM-20260924-C3S-v1/VALID_EVALUATION.md), and subsequent ideas used its analysis. This run can test a newly frozen signal on that distinct temporal split, but cannot establish genuinely untouched independent replication. Numerical GO is only permission to consider a separately authorized next phase, never adoption or independent confirmation. Failure is NO-GO / CLOSED. No new data is available in the workspace for independent confirmation.

## Artifacts and order
Before any new Valid access: complete Train diagnostics, four-input mutation audit, contract/coverage/determinism, official accounting equivalence, source scan, Train-only stage and firewall; freeze independent snapshot and real zip; verify real zip Train predictions and dependencies/time/memory. Hash decision/config/code/environment/input manifest, then run frozen code once. Predict and save all stages/weights before opening Valid target. Save event diagnostics and primary decision first. Interpret portfolio results only if primary survives. Mechanical daily ledgers are saved for audit even if primary fails; no portfolio summary or rescue decision is produced in that case.

## Prohibitions
No BOX revival, duration/k/Lmax/grid changes, RS-window changes, thresholds, interactions, other features, ML, alpha or blend search, target/execution change, Short redesign, or next-phase work. PORT_SHORT_001 remains deferred. No post-result relaxation.

## Execution
Bound every process with tools/run_bounded.py. Research: python -m research.experiments.nh_rev --config <prepared-run>/config.json --output <prepared-run>. Valid uses the frozen snapshot runner, --valid --freeze <release>, in a separate process after Freeze verification.

## Pre-Valid Freeze decision
Train implementation verification completed. Candidate remains exactly the single registered negative RS60 signal. Train raw event IC=-0.03862520563410759, HAC5 t=-2.923397782914338; Train direction check passes, but Train is not adoption evidence. All preregistered numeric gates remain unchanged. Eight regression tests, Train source firewall, three full-input prefix mutations, deterministic replay, prior B00/RS60 bitwise parity, full coverage and official accounting parity passed. Freeze this decision and code before new Valid feature/target access. Existing Valid disclosure prevents independent-OOS claims.
