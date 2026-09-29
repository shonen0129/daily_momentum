# DM-20260926-01: BOX holdings audit, asymmetric Low carry, and eligible-Box gate

Status: completed. This was a fixed, descriptive Train-only audit of already known data. It was not selection-eligible and did not access Valid.

## Questions and hypotheses

The saved `BOX_BIDIR_STANDALONE` predictions show positive Long and negative Short sleeve results, with Low event residuals decaying poorly after the event date. Candidate A tests one fixed change: retain the current High EWMA stream at alpha 0.25, while retaining only the current-day EWMA contribution from Low events. The Short sleeve still exists because official five-quintile construction ranks the full cross-section.

Separately, Candidate B tests whether the eligible variable-duration Box condition adds information beyond B00's 250-observation breakout. The comparison is fixed to B1 = B00, B2 = eligible Box events with B00 event scores, and B3 = the same eligible event set ranked by the existing side-specific Ridge design. No event with absent Box fields may pass B2/B3 through mean imputation.

These tests do not presume that a Train Sharpe above 1 is sufficient. All Train periods and the cited report are already known; results remain descriptive, not independent OOS evidence.

## Economic rationale and persistence

The existing age attribution suggests Low event-day direction may differ from its later carry. Stopping only Low carry could reduce stale Short scores while keeping the event-day score and High process fixed. The information is known at signal close; next-open residual returns are still the target. It may fail because Short slots remain filled by other weak or neutral-ranked stocks, and tie ordering can decide who enters Q1.

An eligible-Box gate may remove breakouts without a qualifying compressed range. Any value should persist if the pre-breakout condition is measurable using prior observations. It may fail because the Box filter reduces event coverage or because the 250-day breakout already captures the useful information.

## Fixed candidates and comparison rules

### Candidate A

- `BOX_ORIGINAL`: saved standalone BOX score and official five-quintile weights.
- `A_LOW_NO_CARRY`: current BOX High raw events remain EWMA(alpha=0.25); Low raw event scores keep their current alpha-scaled event-day contribution and are zero from age 1 onward. Do not alter features, Ridge, event definitions, train folds, target, cost, score ranking, or official portfolio normalization.
- Apply the identical Low-no-carry transform once to B00 (`A_B00_LOW_NO_CARRY`) to distinguish a general High/Low holding effect from a BOX-specific effect.
- Short-sleeve scale diagnostics use the existing BOX and B00 daily quintile weights at gamma = 1.00, 0.50, 0.25, 0.00. Gamma 1.00 is the matching official-weight baseline; gamma below 1 is a separately labelled non-official operating rule. Scale only negative weights, recompute turnover from the scaled daily weight series, and apply identical gamma values to BOX and B00.

### Candidate B

- `B00_BASE` / B1: existing 250-observation high/low event scores and EWMA(alpha=0.25).
- `B_BOX_GATE_B00_SCORE` / B2: require `box_duration > 0`, finite `box_width_atr`, and `box_width_atr < 3.0` for both sides; rank the remaining event excesses using the existing B00 side-specific percentile-score rule; then apply the existing EWMA and portfolio construction.
- `B_BOX_GATE_RIDGE` / B3: exactly the B2 eligible high/low event rows. Fit the existing side-oriented five-feature Ridge design (lambda 1.0) annually on mature eligible Train events only; score only eligible events; use the same EWMA, tie order, five-quintile weights, and cost as B1/B2.

No other strategy, grid, threshold, alpha, lambda, holding period, or interaction is permitted.

## Frozen evaluation and reporting

- Train input: 2008-11-04 through 2016-03-31. Evaluation folds: 2011 through 2016, each year's last two signal dates purged; 2016 is the exact partial interval 2016-01-04 through 2016-03-29.
- Use official target `target_1day_train.parquet`, t+1 Open to t+2 Open market-residual return, one-way cost 10 bps, annualization 252, and existing daily five-quintile weight construction.
- Preserve exact `(Date, Code)` order for `rank(method="first")`; report score-zero Q1/Q5 holdings and code-order dependence. Use same-date `listed_info_train` sector fields as point-in-time diagnostics.
- Report full Train evaluation, 2011-2015, exact 2016 partial period, each calendar year, and each annual fold. Include exposure, gross/net, cost, volatility, Sharpe, drawdown, Long/Short, RankIC, active/nonzero signals, zero-score tails, sector concentration, and paired differences to the matching B00 rule.
- A 20-day paired circular block bootstrap with 1,000 repetitions and seed 20260925 is reused from the existing DM-20260925-03 evaluation; it is descriptive only.
- Common residual drift is the same-day mean official residual return on the target-valid universe. Split each long, short, and total gross return into `net exposure × universe mean` and cross-sectional selection residual; allocate transaction cost separately.

## Reproducibility and decision criteria

The run records the saved source run ID, source artifact hashes, current git commit, Train data hashes, code hashes, environment, config, timestamp, cost, candidates, and output paths. Current-account outputs must reconcile with the existing saved daily account within numerical tolerance before modified scores are assessed.

Candidate A is not adopted solely for Net Sharpe >= 1. It must improve outside 2016, avoid material damage in weak years, survive the explicit zero-score/tie audit, retain cross-sectional selection value beyond common drift, and compare favorably with the same short scaling on B00. Gamma results are never labelled as official five-quintile strategy results.

For Candidate B, B2 <= B1 means no evidence for incremental Box gating in this series. If B2 > B1 but B3 <= B2, the gate may add value without Ridge. Only B3 > B2 supports a possible Ridge ranking increment. These known-Train comparisons are not independent OOS proof.

At most one next action will be recorded. There will be no post-result candidate addition, tuning, Valid evaluation, Freeze, or submission.

## Verification

Run the fixed driver behind Train-only firewall with the existing causal feature builder. Check saved-score/account replay, point-in-time sector join alignment, full score/weight coverage, finite values, deterministic output, official five-quantile tie order, Candidate A age behavior, Candidate B eligible-event identity, annual label maturity/purge, and a cutoff mutation/truncation prefix check for the eligible Ridge path. Run the focused synthetic regression tests and `make check`; do not call the official evaluator with its default Valid-target path.
