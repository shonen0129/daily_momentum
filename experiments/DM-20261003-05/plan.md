# DM-20261003-05: independent Size / Illiquidity / MOM60

Date: 2026-10-03 JST. Strategy: dm_slow_mom60_equal. [User request](request.md).
Train-only known development evidence. Historical Valid / Valid and their saved
artifacts are prohibited. No release or external submission.

## Hypothesis and fixed budget

Size and illiquidity reflect persistent cross-sectional premia; residual60
momentum reflects gradual information diffusion. Different economic drivers
could complement SLOW after the next open. Persistence beyond overnight repricing
is a hypothesis tested using the official t+1→t+2 open residual target, not a
claim justified by correlation. Momentum can dilute SLOW or increase reshuffling
and cost. Added complexity: three same-date ranks, no learned coefficients.

One performance candidate SLOW_MOM60_EQUAL, zero rescue trials. SN1_H1 is excluded.
No window/skip/alpha/weight/sign/threshold/filter/sector/regime/risk-target search,
side weights, or extra smoothing. Keep existing economic definitions unchanged.
This explicit new style-combination candidate does not change the shared strategy
specification. Prior slow experiments are known evidence, see
[previous decision](../DM-20261002-05/decision.md) and [graveyard](../GRAVEYARD.md).

## Components and parity before performance

Rebuild original SLOW raw_size, raw_amihud, z_size, z_amihud and size_liquidity.
Size=-log(raw Close*latest positive PIT disclosed shares). Amihud=abs(organizer
raw_return)/positive raw TurnoverValue, trailing60 exchange sessions/min40.
Preserve original 1/99 winsorization, daily median then0, sample standardization.
SLOW=zscore(mean(z_size,z_amihud)), preserving arithmetic order and float64 bits.
Compare raw/normalized components and SLOW to the config's hashed saved artifacts.

MOM60 uses original residual60/skip1→same-date centered average rank→EWMA(.25).
Match both the saved SLOW experiment and frozen DM-20260908-v1 Train score bitwise.
The copied SLOW module is byte-identical; four MOM60 functions are source-identical
and compared to current and frozen code. Unused general feature loaders are omitted.

For each final component independently: p=same-date average-tie percentile rank;
rank=2*(p-mean(p)), the existing centered rank convention (factor2 cannot change
portfolio order). All ties/singletons yield0. Score=(SizeRank+IlliquidityRank+
MOM60Rank)/3. No extra EWMA. This differs from .5*SLOW_CONTROL+.5*MOM60 and from
portfolio sleeves. Score goes to official global five-quintile weights.

## Ordered phases and evaluation

Freeze plan/config/code→component parity→save orthogonality→one fixed trial→
incremental attribution→turnover/cost→bootstrap→causality audit→decision.
Hash checkpoints and retain failed runs. Build components before parsing target.
Only six explicit Train feature sources and target_1day_train are staged; firewall
is installed before any parquet parsing. Candidate/adapter accepts no labels.

2011–2015 full-year past→future evaluation folds and 2016 partial; no fitting.
Use all prior feature history; each year's final two exchange dates purged so t+2
maturity cannot cross a fold or Train end. Account on the full continuous panel
before selecting dates. POOLED and EX2016 plus six annual scopes. All Train has
been previously studied; no untouched holdout or out-of-sample selection claim.
2016 partial is excluded from the 4/5 full-year stability gate.

Official .001 one-way cost*sum(abs(weight change)), including original missing-
target cost semantics. Report all-position cost separately. Annualized means*252,
actual period sums separately, sample-SD Sharpe*sqrt252, daily Spearman IC,
Bartlett/Newey-West HAC5 t, Q1→Q5 increasing score; Long Q4/Q5, Short Q1/Q2.
Compound net wealth starts at1 for MaxDD; retain additive DD too.

Save every requested IC/Sharpe/gross/net/cost/turnover/DD/quintile/side metric and
candidate deltas vs SLOW and MOM60. Orthogonality: daily Spearman and pooled/year
unweighted mean matrices; stacked stock-day Pearson/Spearman labeled separately.
SLOW/MOM daily gross/net P/L Pearson, Long/Short Jaccard, per-scope drawdown depth
correlation. Low correlation is descriptive. Skip optional pure sleeves.

Five official-membership agreement groups partition all stock-days, including
OTHER and neutral exit costs: BOTH_HIGH, SLOW_HIGH_MOM_LOW, SLOW_LOW_MOM_HIGH,
BOTH_LOW, OTHER. Save target means and candidate/SLOW gross/net/cost/turnover and
deltas, daily plus all scopes; reconcile all sums to official accounting.
Distinguish Δgross from Δcost: Δnet=Δgross−Δcost. Report turnover ratio and
incremental gross/cost ratio with zero/negative incremental costs explicit.

## Bootstrap and conjunctive adoption

Paired circular moving blocks20 sessions, reps2000, seed20261003, 95% percentile
CI. Primary pooled candidate−SLOW ΔNet Sharpe; secondary candidate−MOM60.
EX2016 versions descriptive. All requested gates must pass: pooled/EX2016 Net
Sharpe>SLOW, annual net>=SLOW, >=4/5 full-year Net Sharpe improvements, primary
pooled CI lower>0, Long net>0, Short net>=SLOW, MaxDD magnitude<=SLOW,
turnover<=1.50*SLOW, Δannual gross>Δannual cost. For unspecified aggregate scopes
of annual net/side/DD/turnover/gross-cost gates, require both POOLED and EX2016;
this conservative interpretation is fixed before trial. No rescue.

A=complementary if all gates pass; B=gross-only if gross improves but cost
prevents net improvement; C=dilution if gross/net worsen; D=unstable complement
if pooled improvement fails stability/bootstrap/side/etc gates. Describe mixed
patterns explicitly without changing thresholds.

## Verification and execution

All six sources individually/jointly: suffix extreme/NaN/zero changes, financial
publication shifts/deletions, future row additions/deletions; truncation at
warmup/mid-history/year-end cutoffs; row shuffle; deterministic rebuild; exact
index/dtypes/uint64 values including NaNs; coverage/missing/inf/ties; label
independence; source scan/firewall; t+2 target reconstruction and fold-end purge.
Compare old MOM residual source and audit and dynamically test its path again.
Aggregation reconciliation may use stated numerical tolerance, never described
as bitwise score parity. Exact raw input/output index is checked.

Relevant regression tests and make check; full Train-only smoke and adapter
parity. No zip/Valid testing. Bound research job1800 seconds; save RSS/time,
input/code/artifact hashes, library versions, command, trial count and status.
New runs never overwrite old artifacts.

```sh
.venv/bin/python tools/workspace.py prepare-run DM-20261003-05
.venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.slow_mom60_equal --config artifacts/DM-20261003-05/<run_id>/config.json --output artifacts/DM-20261003-05/<run_id>
```

Report: reports/DM-20261003-05/REPORT.md; decision.md and GRAVEYARD.md for rejection.

## Pre-performance storage diagnosis

The first run (run-20261003T143513Z, actual_trials=0) failed an extra raw-factor
uint64 comparison before candidate creation. Diagnosis: 28115 raw_size missing
values have sign-bit NaN 0xfff8000000000000 from -log; Parquet stores nulls and
loads 0x7ff8000000000000. All finite raw bits, all raw_amihud bits, normalized
Size/Illiquidity, SLOW and MOM scores matched exactly (zero mismatches).
For raw saved diagnostics only, assert exact missing positions and finite bits,
then canonicalize null representation explicitly for the storage comparison.
Do not change feature computation, score, tolerance, parameters, budget or gates.
The four requested final component/score comparisons retain strict uint64 bits
without canonicalization. Keep the failed run; reserve a new run for completion.
