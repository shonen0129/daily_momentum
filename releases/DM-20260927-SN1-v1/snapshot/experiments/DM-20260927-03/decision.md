# DM-20260927-03 decision

- **Status:** Rejected / closed. Both pre-registered levers were falsified for the target Short × Night loss. `Best surviving candidate: None`.
- **SN1 `SIDE_SOURCE_SEPARATION`:** reject. Total Net +0.801pp and Net SR +0.255 vs D are not sufficient because Short × Night is 0.517pp worse, including five of six calendar periods. Gain is explained by selection/cost changes, not repair of the night loss.
- **SN2 `HIGH_AGE5_SHORT_VETO`:** reject. High-age-5+ source improves by 0.680pp but the full Short × Night cell worsens 0.070pp; Short × Day worsens 1.208pp, turnover +0.0543/day, annual cost +1.369pp, total Net -2.374pp, Net SR -0.489.
- **Regulation:** both candidates pass the located Train numeric/index/coverage contract, official five-quintile construction, weights and exposure checks. No repository numeric zero/tie threshold was found. Full submission evaluator not run because it defaults to Valid.
- **Validation:** Train-only firewall, saved D score/weight/account replay, P/L reconciliation and three-cutoff future-mutation prefix-invariance PASS. Bootstrap uses the fixed existing circular paired 20-day/1,000 draw/seed 20260925 helper; known-Train intervals are descriptive only.
- **Next action:** stop this Train-only intervention series. Keep `D_LOW_FAST_ONLY` as the current comparison candidate and do not add a post-result rescue lever.
- Reports: [structural root cause](../../reports/DM-20260927-03/SHORT_NIGHT_ROOT_CAUSE.md), [fixed intervention plan](../../reports/DM-20260927-03/SHORT_NIGHT_INTERVENTION_PLAN.md), [lever results](../../reports/DM-20260927-03/SHORT_NIGHT_LEVER_RESULTS.md), [decision](../../reports/DM-20260927-03/SHORT_NIGHT_DECISION.md).
