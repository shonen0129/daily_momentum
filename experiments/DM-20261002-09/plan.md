# DM-20261002-09 — transform-order matched Sector C-veto ablation

Registered 2026-10-02 JST before new performance. This is an ablation removing transform-order confounding, not parameter rescue of SHORT_DISAGREE_VETO. Primary inference is RAW_EWMA_SHORT_VETO minus RAW_EWMA_CONTROL, never Veto minus MOM60 alone.

## Audit and evidence already known

Read root/research/strategy AGENTS, WORKSPACE, architecture/development workflow, competition README and official compute_weight/compute_pl, momentum_liquidity specification, GRAVEYARD, 06/07/08 plans/config/decisions/reports, and actual MOM60/raw60/PIT33 common/EWMA sources. The requested ablation is a separate candidate family; shared specification is not rewritten. 06 peer Momentum failed cost/net/bootstrap; 07 Combined failed coverage/stability/bootstrap; 08 SECTOR_CONFIRM and SHORT_DISAGREE_VETO both remain REJECT. Prior08 Short gross loss shrank, but full-year improvement3/5 and raw context coverage<95%. MOM60 uses centered rank before EWMA;08 Veto uses raw operation before EWMA, confounding context inference. Previous sources/decisions/reports are hashed and preserved. 08 scientific run failed during report publication and a successful report-only recovery followed: its scores are reused only after checking recovery source hashes. No prior candidate performance rerun.

## Hypothesis and fixed implementation

08 improvement may be caused by transform order rather than independent Sector information. Alternatively C neutralization could reduce Short losses because sector flows/information diffuse beyond next open while an individual negative trend is temporary. t+1-open survival is tested on the official residual target, not asserted. Expected turnover may increase on sign transitions/global replacement. Risks: PIT/future peers, rolling/segmentation, missing history and smoothing. Complexity: raw60, one same-date sector mean and two fixed EWMA streams; no fit.

Exactly2 unconditional performance trials. RAW_EWMA_CONTROL: exact residual StockMom60_raw (skip1 observation, rolling60 min60) -> nonfinite neutral0 -> unchanged Code/relisting EWMA(.25) -> final score. No context/ranking. Control adapter reads only raw_return/beta/TOPIX. Neutral0 maintains finite output and existing initial-history/relisting convention; finite values unchanged. RAW_EWMA_SHORT_VETO: exact08 joint-finite rule keeps Stock>=0 or Stock<0/Common<=0, neutralizes C (Stock<0/Common>0), missing context neutral0, then EWMA(.25) ONCE. This also neutralizes positive Stock with unavailable context, exactly as08; report this operational difference rather than repair it. Sector zero keeps negative Stock.

Common exactly08: signal-date PIT33 exact Date/Code projected to required raw-return rows, self-inclusive equal finite mean, minimum5, unchanged unknown policy. A/B/C/D raw signs unchanged, zero/nonfinite separate. Reset EWMA after >20 absent exchange-date ordinal gap only; sector changes preserve Code history. Secondary MOM60 unchanged centered rank before EWMA. New self-contained dm_raw_ewma_ablation clones unchanged primitives and checks source/bitwise parity, without editing previous strategy sources.

## Budget, periods and fixed decision

config.json is the precise contract:2 trials,alpha.25,horizon60,skip1,min5,no fitted model. No partial/soft/threshold/strength/weight/duration/breadth/regime/sector filter, blends, new features, additional rank or rank-order candidate. No search after results. Known Train development evidence, never independent OOS; Historical Valid unread. No Freeze/release/zip/submission added.

Expanding history2008-11-04 to2016-03-31. Primary EX2016=2011-2015,2016partial separate,POOLED continuity includes2016. Every year drops final2 exchange sessions and verifies t+2 maturity within fold. Full-row official continuous accounts BEFORE filtering, retaining positions across year boundaries/purge dates. No random folds or target training.

Veto relative to RAW control: pooled and EX2016 NetSR exceed control; primary EX2016 annualNet exceeds,Shortgross/net at least control,turnover<=1.25control,Longnet>0,Qmonotonicity>0. Full-year2011-2015 NetSR improvement>=4/5;2016 never counts. Primary EX2016 paired circular moving-block20sessions/2000reps/seed20261002 percentile95% deltaNetSR lower>0. Primary deltaShortnet>0 and deltaShortgross/deltaShortnet>=50%. Pooled analogs/bootstrap also saved, never replace primary. Coverage is reported, not an added95% gate here. All required; failure REJECT, success NEXT_EXPERIMENT_ELIGIBLE_TRAIN_ONLY, not adoption. RAW control descriptive only. Future RANK_PIPELINE_SHORT_VETO may be proposed only if all gates pass, never implemented here.

## Accounting and locked mechanism diagnostics

Official5 quintiles/Code ties,weights(q-2)/N/1.2,10bp one-way costs. Arithmetic mean*252 annual P/L/cost and period sums, sample-SD Sharpe*sqrt252,HAC5 RankIC t/hit,compound/additive DD,Q1-Q5/monotonicity,side gross/net/turnover and baseline/primary differences each year/fold. Official missing-label cost omission and conservative all-position cost separate.

RAW control vs Veto replacement:ShortQ1+Q2,Q1,Q2 REMOVED/ADDED/UNCHANGED row targets,signed gross/net/cost,weight contributions,Stock/Common distributions,sector distribution. Preserve OTHER exit-only costs for exact full Short delta. deltaShortnet=deltaShortgross+(controlShortcost-vetoShortcost). C original Shorts all/removed/retained:count,target,annual gross/net,average signed/absolute weights,sector distribution. Raw C neutralization may leave actual Short positions through EWMA/global ranking.

A/B/C/D/ZERO attribution is original full globally ranked book contribution, never standalone state strategies; row/equal-date targets,rawStock/final RankIC,side gross/net/cost/turn. C entry/exit/spells/durations/1&5day uninterrupted persistence on observable adjacent sessions; diagnostic gaps reset,boundaries censored. No duration rule derived. Total/side turnover,C transition-name share; disjoint delta-turnover buckets removed C positions,added replacements,unchanged weight changes,removed non-C,OTHER. Temporal C exit differs from portfolio removal; decomposition is descriptive, not unique delayed causal attribution.

Long gross/net/turnover and overlap/Jaccard vs RAW control (MOM60 also saved). Short33 exposure/dailyHHI/max/top2,Q1/Q2 sector distributions and signed contributions. Coverage by year/33:Stock,Common,joint C evaluable; control needs Stock only,Veto both. Output100% neutralized predictions is not raw coverage.

Matched-row diagnostic uses EXACT same joint-finite Stock/Common rows for both final scores:daily RankIC and score-ranking Q1-Q5 diagnostics; full-book holdings contributions on matched/unavailable rows. No additional subset strategy or P/L reranking; full required-row official P/L remains primary. Current matched availability does not remove past missingness already carried in EWMA.

## Audit, resources and completion

New builder/control/adapter directly tested. AST scan/runtime Train firewall/isolated stage only4 feature Train files plus Train target;control adapter only3. Before target read hash/lock plan/config/code/inputs/library versions and audit Stock/PIT/Common/state/veto/EWMA/control/final. Three cutoffs:each/all-source suffix extremes/NaNs/row addition/deletion/PIT changes/truncation, separate future stocks/future sectors/suffix deletion. Exact numeric bit-pattern,index,column,dtype equality including NaNs,zero tolerance. Full row shuffle,deterministic rebuild,synthetic zero/missing/min5/relisting/purge/official accounting,exact index/finite100% output,research-adapter parity,no-arg standalone Train smoke. Changing even historical sector rows must leave negative control score unchanged.

New run snapshots/command/hash/environment/status/trial count,failures retained. Bounded1800seconds through research/experiments/raw_ewma_ablation.py --config <run>/config.json --output <run>; tests180seconds. Complete mechanism reconciliation,reports/decision/GRAVEYARD. make check and old Freeze hashes; known04 metadata failure if present reported without unrelated repair.

Inference is limited to raw->EWMA C-veto incremental effect, not rank->EWMA MOM60/other orders/general Sector context. Missingness and self-inclusion remain limitations. If matched improvement disappears,transform order/other operational differences become plausible explanations for08; weak statistical evidence is not proof of no information.
