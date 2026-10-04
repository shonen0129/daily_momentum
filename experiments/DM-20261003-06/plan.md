# DM-20261003-06: one annual OLS on existing three factor ranks

Plan date:2026-10-04 JST; ID allocated before midnight2026-10-03. User explicitly
selected 「OLSを1候補だけ実験する」 after the fixed equal experiment was rejected.
This is a distinct preregistered learned combination, not a revision of the old
1:1:1 experiment or its decision. [Previous decision](../DM-20261003-05/decision.md)
remains unchanged. No Historical Valid/Valid, release or external submission.
Use the experiment-design, leak-audit and backtest-report workflows already read.

## Hypothesis and budget

Size and Illiquidity overlap strongly. Pooled past-data linear regression can
estimate their conditional marginal predictive contribution together with the
existing residual momentum and avoid arbitrarily giving momentum1/3 of score.
Persistent size/liquidity premia and gradual information diffusion could survive
t+1 open; test exactly the official t+1→t+2 residual target. This does not assume
OLS improves net: its squared-error objective excludes transaction cost, and
collinearity can destabilize coefficients and holdings. Annual updates bound
parameter changes; only4 coefficients per model, with no optimization search.

Exactly1 new performance candidate SLOW_MOM60_OLS; zero rescue. No Ridge/Lasso,
label-transformation, window, regularization, coefficient/sign-constraint,
refit-frequency or rolling-window comparison. The prior experiment's prohibition
on weight search stays intact; here coefficients are estimated by the explicitly
requested fixed OLS procedure, never manually selected from performance.

## Definitions frozen before performance

Copy the complete previous strategy factor module unchanged. Size and Illiquidity
retain original raw levels/PIT shares, Amihud60/min40, 1/99 winsor/median/zero/
sample standardization. MOM60 retains residual60/skip1→same-date average centered
rank→EWMA(.25). Input columns are independently same-date p→2*(p-mean(p)) ranks,
bitwise compared to saved component_scores and factor_ranks before fitting.

Label: raw organizer target_1day_train Return. OLS has intercept plus3 ranks,
np.linalg.lstsq(rcond=None), uniform finite mature stock-days, expanding history.
No label rank/standardization/winsorization, extra feature scaling, clipping,
regularization, sign constraints, score smoothing or turnover overlay.
Coefficients may have either sign because they are learned, not sign trials.

At the first exchange session of each year, fit on prior signal dates whose
label endpoint(calendar position+2) is strictly earlier than that session.
No target ending at the first prediction open is allowed. Refit once per year.
Models2009–2010 establish continuous pre-evaluation holdings; primary evaluation
remains2011–2015 and2016 partial. Initial2008 history scores are neutral0. Fixed
lstsq minimum-norm handles rank-deficient early warmup; record design rank,
singular values, condition number, coefficients, samples and exact maturity.
Missing required annual artifact raises; never use a later-year model.

## Evaluation and gates

Stages: plan/config/code lock→component/rank parity→one annual OLS walk-forward
trial→official accounting and metrics→incremental gross/cost analysis→paired
bootstrap→all-input/learning causality audit→decision. Finite candidate output on
every input row; inference uses stored JSON models and six Train feature files,
no target. Fit labels are accepted by training API only.

Use the same full continuous panel and annual last2 exchange-session purge as
DM-20261003-05. Retain feature history; no random folds. Controls SLOW_CONTROL,
MOM60 and SLOW_MOM60_EQUAL reuse verified identical-source saved accounting,
with hashes and same exact target/input/weight definitions. Four strategies,
eight scopes: POOLED, EX2016, 2011–2015, 2016 partial. All Train is known research
evidence, not an unused holdout. 2016 never contributes to the full-year gate.

Save all RankIC/HAC5/hit, Gross/Net Sharpe, annual/actual period gross/net/cost,
turnover, compound/additive DD, Q1–Q5/monotonicity and Long/Short gross/net metrics.
Compare OLS−SLOW (primary), OLS−EQUAL, OLS−MOM. Record annual coefficients,
condition numbers and signed relative coefficient magnitudes as diagnostics,
without using them to change the model. Δnet=Δgross−Δcost, incremental gross/cost
and OLS/SLOW turnover ratio; explain whether any gain is alpha or cost saving.

Same conjunctive gates as prior experiment: pooled and EX2016 NetSR>SLOW,
annual net>=SLOW, Long net>0, Short net>=SLOW, MaxDD magnitude<=SLOW,
turnover<=1.50*SLOW, incremental annual gross>incremental annual cost;
2011–2015 NetSR improvement>=4/5 years, primary pooled bootstrap lower>0.
No gate relaxation based on this or previously known outcomes.

Paired circular moving blocks20 sessions, reps2000, seed20261003, 95% percentile
CI. Primary OLS−SLOW; secondary OLS−EQUAL; MOM reference; pooled and EX2016.
Bootstrap conditions on realized walk-forward P/L without refitting models; it
does not capture full training/selection uncertainty of repeatedly studied Train.

## Causality and reproducibility

Install firewall before parquet parsing. Dedicated stage contains only six Train
features and Train target; separate inference stage omits target. No default
Valid-prioritizing evaluator invocation. Explicit official compute_weight/PL only.
Source scan and reachable-path review distinguish training-label access from
label-free feature/inference. Future mutation/truncation tests recompute features
AND annual fits, not just fixed-model inference, at2009-06-30,2012-12-28,2015-12-30.

Mutate each feature source, Train labels, ALL; extreme/NaN/zero suffix values,
future row additions/deletions and financial publication movement preserving
original timezone. Label changes use maturity>cutoff (including the last2 past
signal dates whose labels are still future). Truncation sets unavailable mature
labels missing. Compare raw/normalized components, ranks, scores and all models
used in the prefix strictly, including float64 bits; no tolerance relaxation.
Parquet raw NaN sign/payload handling is separately documented in prior parity.

Row shuffle canonicalization, deterministic refit/rebuild, exact alignment,
missing/inf/coverage/ties, model maturity, purge, saved-model inference parity,
standalone target-free adapter smoke, official accounting reconciliation,
Train-only firewall and relevant regression tests. Run make check; its known
DM-20261002-04 unsupported metadata failure is reported, with own metadata and
all129 Freeze hashes separately validated. No unrelated metadata edits.

Bound jobs1800s; save code/config/input/model/output hashes, environment/seed,
commands, elapsed/RSS and completion status. Snapshot strategy and model artifacts
before evaluation. Failed runs are retained; no new candidates after a result.

```sh
.venv/bin/python tools/workspace.py prepare-run DM-20261003-06
.venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.slow_mom60_ols --config artifacts/DM-20261003-06/<run_id>/config.json --output artifacts/DM-20261003-06/<run_id>
```

Report:reports/DM-20261003-06/REPORT.md; decision:decision.md; reject index:GRAVEYARD.md.
