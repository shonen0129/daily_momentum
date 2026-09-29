# Paper horizon freeze

## Decision

- Selected horizon: **H1**.
- H5/H20 paper challenger: **None**.
- Keep the existing H1 SN1 as the fixed paper reference; no longer horizon showed consistent structural improvement across Train and already-opened historical Valid.
- Scope: post-submission paper research. This does not change competition submission logic. Train and historical Valid are development data; future paper observations are forward OOS.
- Freeze date: 2026-09-27.

## Exact H1 target and training

For signal date t, enter Open(t+1), exit Open(t+2). Use the existing official one-day residual target:

    raw_return_1day[t+2] - beta_1day[t+2] * TOPIX_return[t+2]

The Ridge fitting label stays the date-wise average percentile rank centered at its cross-sectional mean and scaled by two. High events use the positive centered rank; Low events use its negative. Use the official H1 target file. A training label must mature before the next fold; H1 excludes the last two trading-calendar signal positions.

- Separate High/Low Ridge models; lambda 1.0; 500-row minimum per side.
- Existing annual expanding Train fit in 2011–2016 folds; events use the unchanged 250-observation breakout. Fixed directional Ridge features, in code order: box_duration, box_width_atr, oriented_close_position, oriented_relative_strength_60, distance_to_prior_extreme.
- High EWMA alpha .25; Low EWMA alpha .50.
- SN1 precedence: D=High+Low; choose Low when Low<0; else High when Low=0 and High>0; else D.
- Existing universe, official rank(method=first), quintiles, weights, turnover accounting and one-way 10 bps cost.
- No monthly horizon switching or interim parameter changes.

## Frozen lineage

- Git HEAD: 09920d4221594b961a5793be02baab9214382f4e; worktree was dirty at freeze because pre-existing unrelated changes remain. No freeze commit was made.
- Authoritative run: run-20260927T101500Z; H1 reproduction PASS; prefix/maturity checks PASS.
- Pre-result plan SHA256: 6472f0d761eaa073748bb94d1faac7b58d3142a169e422487c836f173d9f417e.
- Config SHA256: 60de01773ed417ea56868a48f27ff7bbd60a959e8356ad819a79954f5d7fd457.
- Research driver SHA256: e462bfc43f0f87812967d4b5e86b5952b48a3e9b53da22aabc5eae6d7493f1d8.
- Holding diagnostics SHA256: 62962a7dbab8a0ce5cb06e541541175ed7b608abf72f7782556ebb0eb4e868b0.
- Post-result event-window descriptive audit SHA256: 9e68da202f5f2611c14839550894f3f597d85cd20061bed623734aa30c0dcc60 (four windows fixed by the task; no model or P/L candidate change).
- Run artifacts: artifacts/DM-20260927-04/run-20260927T101500Z/.

### Upstream source hashes

- stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py: SHA256 7cec7be6d45bfba9debee9c07af6d6abf5229961014654de17b23b88b145e287
- stock_comp_2026/strategies/dm_variable_box_breakout/features.py: SHA256 3c2066557ad566556bf9ed6f21910926a36e59979dafef18369090b53ca5dc0a
- stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py: SHA256 55f95ab669e506d61a1d20442efe9b266b56ab14737a7d46b666fee7c0f9c7ae
- stock_comp_2026/strategies/dm_variable_box_breakout/submission.py: SHA256 943feac6a150148cd162b7ba96adff343de8643c2940343be307aae5649dfa32
- stock_comp_2026/README.md: SHA256 d3c64be74f68d059afd9f84de048c9144f152dd1d1725362bf26af871fcb1352
- stock_comp_2026/input_manifest.json: SHA256 62ec8e2f18b4523541c8f7623793f74eeed3f21af2c8ab43b74b1d71cf283c58

## Paper observation protocol

Accumulate 6–12 months of fully forward daily paper records before making a performance claim. Keep horizon fixed throughout. Record monthly Gross/Net return, SR, turnover, transaction cost, Long/Short contribution, RankIC and drawdown, together with the code/config/source hashes. Do not switch horizon from interim results.
