# DM-20261003-03: immutable SN1 × SLOW diversification

Status: planned; 2026-10-03 JST. User-directed independent combination hypothesis; existing strategy definitions are authoritative and unchanged.

## Hypothesis and rationale
Momentum/Breakout SN1_H1 and Size/Liquidity SLOW_CONTROL may earn residual returns from different sources. Information diffusion/trend continuation and capacity/illiquidity compensation can have different loss episodes. A fixed same-scale 1:1 combination may stabilize after-cost returns. This is a new combination candidate, not a rewrite of the shared Momentum/Liquidity specification. Economic source labels are observational hypotheses, not causal identification.

## Why it might survive t+1 open
Original signals target t+1 Open→t+2 Open. Multi-day trend state and slow size/illiquidity exposures may persist beyond the next open. We test the unchanged official target; no close-to-open proxy, no horizon search, no new filter.

## Turnover, leakage, complexity
SN1 faster ranks may raise turnover relative to SLOW. Ranking interaction can defeat low daily P/L correlation. Cost and actual tradable portfolio determine adoption. Every operation is per-date or causal original history; annual SN1 refits use only t+2-mature prior-year Train labels. Original date-only SLOW financials are available at end of same signal day. No fitting blend weights, no extra EWMA. Both original source trees are copied byte-for-byte into a self-contained Train adapter and checked against originals and saved scores.

## Budget, sequence and locked interpretation
Exactly ONE new performance trial: SN1_SLOW_BLEND. The two controls and saved MOM60 are fixed references. The 50/50 official-weight portfolio is diagnostic only, including netted and non-netted sleeve-cost accounting.
Sequence: plan/config/code lock → component parity → saved orthogonality diagnostics → saved pure-weight diagnostic → ONE score blend trial → paired bootstrap → dynamic causality audit → decision. No performance candidate score is built before the first two diagnostics are saved.

2011–2015 full-year folds, 2016 partial separately. Each fold removes last2 exchange dates so t+2 stays in that fold. Full-panel positions/turnover are continuous across purged days; no annual holding reset. Annual metrics use mean×252; period totals are separate. All Train is known development evidence; no unseen OOS claim. No Historical Valid or Valid file/artifact access. Past experiment failures remain in GRAVEYARD; we test this fixed user hypothesis without reuse of old Valid conclusions.

Centered percentile uses original average-tie rank formula 2*(rank(pct=True)-daily mean rank). Both streams use same factor2 so fixed sum ranking is unaffected. Official final ranking breaks ties by sorted Code. Net follows official missing-target cost expression; conservative all-position cost also saved. MDD gate compares absolute compounded drawdown depth, not signed negative numbers.

Adoption requires all user gates: pooled/ex2016 NetSR>SLOW, >=4/5 yearly NetSR improvements vs SLOW, primary pooled bootstrap lower95>0, annualNet>=SLOW, MDD magnitude<=SLOW, LongNet>0, ShortNet>=0, turnover<=max(component turnovers). AnnualNet/MDD/side/turnover gates checked pooled AND ex2016; ex2016 bootstrap saved as robustness evidence, not searched. Gross-only gain insufficient. REJECT when tradable blend does not improve, even if correlation is low. Stop after decision.

## Evidence and diagnostics
Daily gross/net correlations, 2011–2015/2016 separate correlations, per-date score Spearman, Long/Short overlap/Jaccard, PIT33 exposure correlations, underwater overlap/episodes/depths, conditional loss-day returns/counts. Virtual portfolio pooled/ex2016/year Sharpe/annual/period returns/cost/turnover/sides/drawdowns. Blend comparisons vs BOTH components and descriptive MOM60 include IC/HAC5/hit/Q1–Q5/monotonicity and all required portfolio metrics. Attribution exclusive partition plus explicitly overlapping requested marginal masks; bothNeutral exit costs retained. No filters from groups.

## Verification and execution
Source file hashes/copies and saved-score bit parity, exact index/finite809636-row coverage, deterministic rebuild, original and adapter parity, official full-panel accounting reconciliation. Prefix audit changes each/all input sources plus Train labels after three cutoffs, and truncates every source; checks feature matrices and all3 score prefixes bitwise. SN1 models refit per available annual fold, so this includes learning causality; current-year unavailable labels cannot enter fit. Training maturity records and raw/β/market target reconstruction check t+2. Synthetic tie/NaN/index smoke tests exercise blend; original component regressions run unchanged.

Create run with tools/workspace.py prepare-run DM-20261003-03. Execute:
`.venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.sn1_slow_diversification --config <run>/config.json --output <run>`
Tests: bounded180s pytest for new strategy, SN1 and slow original tests. Run make check and retain pre-existing workspace failures separately. No release, zip or Valid evaluation is authorized or required by this experiment.
