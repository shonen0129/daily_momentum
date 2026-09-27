# Short × Night fixed intervention plan

- Experiment: `DM-20260927-03`
- Frozen at: `2026-09-26 19:05:06 UTC` (2026-09-27 04:05:06 JST)
- Phase 1 source: saved `D_LOW_FAST_ONLY` score/weight, saved BOX event stream and eligibility, PIT Train sector/size, Train-day turnover/volume. No target or P/L was loaded by the Phase 1 driver.
- Evaluation split: known Train only, 2011-01-04–2016-03-29; 2016 partial 2016-01-04–2016-03-29; ex-2016 pooled. Existing annual two-date purge retained.
- Baselines: `D_LOW_FAST_ONLY` primary; `BOX_ORIGINAL` context. `B00` remains diagnostic control only and is not an eligible candidate.
- Fixed cost: 10 bps one way; annualization 252; official five-quintile score-to-weight path.
- Candidate budget: exactly two candidate transformations; no follow-up trial.
- Hash is stored in `experiments/DM-20260927-03/config.json` and the run audit after this file is written. This plan will not be revised after candidate P/L is opened.

## Phase 1 facts used to define the interventions

- The audit covers 230,902 Q1/Q2 stock-days from 1,275 dates. Q1 accounts for 66.80% and Q2 33.20% of gross Short weight under the official `(q−2)/N/1.2` rule.
- Final score is positive in 39.03% of Short stock-days; every positive Short score falls below the same day's median positive score because Q1/Q2 take the low end of the signed score ordering. Score-zero is 7.59% of Short stock-days and 8.48% of Short gross weight.
- `high_age_5_plus` is an active source in 61.95% of Short stock-days and the largest absolute source in 39.03%. Its High state is positive in 100% of active observations. Among the high-age-5+ dominant Short rows, final score is positive; these rows account for 21.60% of Q1 and 56.56% of Q2 stock-days.
- `low_age_5_plus` is active in 81.09% and dominant in 47.59% of Short stock-days. Its Low state is negative in 100% of active observations. High/Low carry therefore overlaps frequently; the composite score can rank a positive High-dominant row into Q1/Q2 while a negative Low-dominant row fills the other part of the same short sleeve.
- Cross-section nonpositive score share is below the 40% Short stock share on 748/1,275 dates. A rule that refuses all positive-score Shorts would leave the official Short gross exposure unfilled on those dates.
- Exact-zero rows in Q1/Q2 have both current High and Low states equal to zero. A secondary rank from these same states cannot resolve them; sector or liquidity tie-breaking would add a new predictor without a phase-1 mechanism linking it to Short × Night.
- Many carried scores are numerically tiny: 63.94% of Short observations have absolute score below `1e-12`, and 87.18% below `1e-4`. These are decayed EWMA states; the existing raw-stream inversion clamps raw noise below `1e-12`, but a carried state can decay below that level without becoming exactly zero. This is a structural rank sensitivity, not proof that a return is noise.

## Frozen candidates

### SN1 — Side-separated source ordering (`SIDE_SOURCE_SEPARATION`)

- Hypothesis: High and Low states compete inside one signed composite. In the Short sleeve, this lets positive High-origin carry occupy ranks that should be ordered by the negative Low state. The Short ordering should use the Low state; the Long ordering should use the High state.
- Change: on each date, use `low_state` when it is negative; otherwise use `high_state` when it is positive; otherwise retain the original D score (the flat state is zero in the saved stream). No alpha, event, feature, holding, threshold, cost, or market-session change.
- Mechanism: a negative Low state remains below a positive High state even when the summed D score would put a High-dominant name inside Q1/Q2. The official five quintiles still determine all positions and weights.
- Refutation: regulation/contract failure; Short × Night does not improve; Short × Day worsens by at least the Short × Night gain; total Net Sharpe clearly worsens; cost/turnover erases gross improvement; ex-2016 or multiple years reverse the direction; or the result depends on zeros/ties or net-long/common drift.
- Regulation: preserve all five official quintiles and the official score-to-weight normalization; no hand-edited sleeve weights or session-specific execution.

### SN2 — High-age-5+ dominant Short veto (`HIGH_AGE5_SHORT_VETO`)

- Hypothesis: the strongest High-origin carry group entering Short has positive High information and reaches Q1/Q2 by relative placement. These rows should be ineligible for Short ranking while the rest of the cross-section fills the standard official quintiles.
- Change: within each date, order names lexicographically by `(high_age_5_plus is not the dominant absolute source, D score ascending, Code ascending)` and assign the resulting deterministic ordinal as the score. The sole eligibility flag is the existing `age_5_plus` source bucket; no new threshold or parameter.
- Mechanism: High-age-5+-dominant rows sort after all other names and therefore cannot enter Q1/Q2 while they are fewer than 60% of the daily universe. All official quintiles, long/short gross exposures, and cost conventions remain in force. This strong intervention may replace them with Low-aged Shorts and is expected to fail if that substitution is harmful.
- Refutation: regulation/contract failure; Short × Night does not improve; Short × Day loss matches/exceeds the Night gain; total Net Sharpe clearly worsens; cost/turnover erases improvement; improvement depends on 2016 partial; zero/tie dependence increases; or common/net-long drift alone accounts for the improvement.
- Regulation: scores are deterministic daily ordinal ranks, with no injected zero or random jitter; compute official five-quintile weights through the existing evaluation helper and verify exposures.

## Pre-registered exclusions

- Absolute-score/sign neutralization: D already ranks signed scores in numeric order. A rule that bars positive scores from Q1/Q2 cannot fill the official 40% Short stock share on 748 dates, so it changes the required exposure. It is not a candidate.
- Existing-signal secondary tie-break: exact-zero Q1/Q2 rows have `high_state = low_state = 0`; no distinct current High/Low information exists to order them. No random jitter, ticker hash, sector, or liquidity rank will be introduced.
- Low-age-5+ veto: it targets a separate lossmaking source group and would remove a large part of Short membership. This run fixes interventions on the observed positive High-origin Short mechanism and will not add another age rule after seeing P/L.
- No alpha, horizon, threshold, lambda, feature, model, score smoothing, or session-specific trading search.

## Fixed evaluation and rejection rules

- Evaluate only the two candidates above versus `D_LOW_FAST_ONLY`; report `BOX_ORIGINAL` as the existing baseline context. `B00` is diagnosis/control only.
- Required periods: 2011–2015, 2016 partial, ex-2016 pooled, full pooled. Also show Short × Night by year.
- Required metrics: gross/net annual return, gross/net Sharpe, volatility, turnover, cost, maximum drawdown, RankIC; Long/Short gross/net/Sharpe and correlation; Long × Day, Long × Night, Short × Day, Short × Night gross/net/volatility/Net Sharpe; source-age attribution for Short × Night.
- Explain change as selection/common, turnover/cost, volatility, and exposure. A Short × Night gain no larger than a Short × Day loss is failure.
- Regulation checks: row/index contract, score finite/zero/unique/tie rates, five daily quintiles, weight/exposure replay. `B00` cannot become a final candidate.
- Paired circular bootstrap only: existing `research.evaluation.bootstrap_delta`, 20-day circular blocks, 1,000 draws, seed `20260925`. Compare each candidate with D for ΔNet Sharpe, Δannual Net return, and ΔShort × Night Net contribution. Train intervals are descriptive, not OOS evidence.
- Reject any candidate for a required condition in the user brief; do not add a third candidate after results.
