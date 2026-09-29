# Multi-horizon results

## Executive result

**Retain H1 as the fixed paper reference. Select no H5/H20 challenger.** Changing only the Ridge target horizon did not yield a consistent structural gain across Train and the already-opened historical Valid.

- H1 reproduces the saved SN1 path bit-for-bit on audited intersections. H5/H20 only slightly alter fitted scores and leave membership persistence nearly unchanged.
- H5/H20 show small gross and Net lifts in historical Valid, but paired intervals include zero. Train is flat/slightly worse for H5; most H20 Train pooled uplift is the 59-session 2016 partial.
- Longer labels do not reduce turnover or cost. Both rise slightly, Long contribution barely changes, and Short remains Net-negative.

Train and old Valid are development history, not OOS evidence. Future paper observations are the only forward OOS.

## Frozen experiment and reproducibility

- Experiment DM-20260927-04; authoritative run run-20260927T101500Z; Git HEAD 09920d4221594b961a5793be02baab9214382f4e.
- Worktree was already dirty at pre-result lock and remains dirty; unrelated state was not reset or staged.
- Exactly H1/H5/H20 were registered. Plan SHA256 6472f0d761eaa073748bb94d1faac7b58d3142a169e422487c836f173d9f417e; config SHA256 60de01773ed417ea56868a48f27ff7bbd60a959e8356ad819a79954f5d7fd457; research driver SHA256 e462bfc43f0f87812967d4b5e86b5952b48a3e9b53da22aabc5eae6d7493f1d8.
- High/Low alpha .25/.50, Ridge lambda 1.0, yearly expanding Train fits, five existing features/events, SN1 transform, official five quintiles/weights and one-way 10 bps cost were fixed.
- Old Valid was evaluated only as development data and was not used in fit. Raw target file was not read. No Sharpe-based selection was run.
- H1 reproduction gate PASS: max score error 0; event predictions error 0; 576,535 Train and 1,227,148 historical Valid saved-score rows were bitwise equal.
- Prefix/maturity checks PASS at each H. At cutoff 2014-06-30, the feature prefix was bitwise equal for 48 sorted codes; safe labels matched (H1 604,281; H5 602,203; H20 594,642). Future outcome mutation did not change any yearly-fit coefficients (High/Low training rows: H1 9,971/3,886; H5 9,886/3,886; H20 9,614/3,886). Feature prefix comparison covers a 48-code sample; label maturity and fit checks cover full Train features.
- Requested target tests: .venv/bin/pytest -q tests/strategies/dm_variable_box_breakout/test_horizon_targets.py — 5 passed. Driver compilation passed.
- Locked target-audit SHA256: b18cde4dc29ec55d4d2a8328dd8855d3004f11707fa10c5b3439e20586e43631; the exact pre-result bytes are preserved in audit/HORIZON_TARGET_AUDIT_LOCKED.md. A concrete calendar-date illustration was appended after the lock without changing target or run logic; current audit file SHA256 is b47bfa2e0d4351174616d5ead6ef7529c7a99995ac38e9415c2a12e42b38383a.
- H1 independently reconstructed within 1.11e-16 max error. Train reconstruction excluded 942 official rows on the last two signal dates, 2016-03-30 and 2016-03-31, whose label maturities extend beyond the Train account boundary; both dates are outside Train fit maturity and the Train account ends 2016-03-29. Historical Valid reconstructed coverage matched 1,223,593 rows. This is split-boundary coverage, not an evaluated target difference.
- Initial run 101000Z was marked invalidated before its boundary coverage explanation was resolved. Its metadata now marks it superseded duplicate: the authoritative absolute-calendar run 101500Z reproduced all candidate targets and scores bit-for-bit.
- Original portfolio-period CSV omitted a candidate label. The derived portfolio_period_metrics_with_candidate.csv assigns its ordered 21-row blocks to the fixed driver order H1/H5/H20; source CSV is untouched.

### Fixed upstream source hashes

- stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py: SHA256 7cec7be6d45bfba9debee9c07af6d6abf5229961014654de17b23b88b145e287
- stock_comp_2026/strategies/dm_variable_box_breakout/features.py: SHA256 3c2066557ad566556bf9ed6f21910926a36e59979dafef18369090b53ca5dc0a
- stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py: SHA256 55f95ab669e506d61a1d20442efe9b266b56ab14737a7d46b666fee7c0f9c7ae
- stock_comp_2026/strategies/dm_variable_box_breakout/submission.py: SHA256 943feac6a150148cd162b7ba96adff343de8643c2940343be307aae5649dfa32
- stock_comp_2026/README.md: SHA256 d3c64be74f68d059afd9f84de048c9144f152dd1d1725362bf26af871fcb1352
- stock_comp_2026/input_manifest.json: SHA256 62ec8e2f18b4523541c8f7623793f74eeed3f21af2c8ab43b74b1d71cf283c58

## Overall portfolio performance

Annual returns, cost, volatility and drawdown are percentages. Turnover/day is weight turnover ratio; RankIC is daily score versus official one-day realized residual.

| Candidate | Window | Days | Gross ann. | Net ann. | Cost ann. | Gross SR | Net SR | Gross vol. | Net vol. | Turnover/day | Max DD | Daily RankIC |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SN1_H1 | Full Train | 1275 | 4.708% | 4.517% | 0.191% | 1.108 | 1.063 | 4.248% | 4.248% | 0.00765 | -6.131% | 0.01246 |
| SN1_H1 | Train ex-2016 | 1216 | 4.224% | 4.057% | 0.167% | 1.051 | 1.009 | 4.021% | 4.021% | 0.00672 | -6.131% | 0.01126 |
| SN1_H1 | Historical Valid | 2521 | 0.483% | 0.244% | 0.239% | 0.102 | 0.052 | 4.729% | 4.729% | 0.00951 | -10.765% | 0.00603 |
| SN1_H1 | Historical Valid ex-2016 | 2337 | 1.166% | 0.942% | 0.224% | 0.256 | 0.207 | 4.558% | 4.559% | 0.00892 | -9.205% | 0.00761 |
| SN1_H5 | Full Train | 1275 | 4.701% | 4.510% | 0.191% | 1.107 | 1.062 | 4.247% | 4.248% | 0.00767 | -6.256% | 0.01239 |
| SN1_H5 | Train ex-2016 | 1216 | 4.217% | 4.049% | 0.167% | 1.049 | 1.007 | 4.021% | 4.022% | 0.00672 | -6.256% | 0.01117 |
| SN1_H5 | Historical Valid | 2521 | 0.557% | 0.317% | 0.240% | 0.118 | 0.067 | 4.723% | 4.723% | 0.00957 | -10.618% | 0.00603 |
| SN1_H5 | Historical Valid ex-2016 | 2337 | 1.187% | 0.961% | 0.226% | 0.261 | 0.212 | 4.542% | 4.543% | 0.00899 | -8.830% | 0.00757 |
| SN1_H20 | Full Train | 1275 | 4.804% | 4.613% | 0.192% | 1.135 | 1.090 | 4.233% | 4.233% | 0.00768 | -6.213% | 0.01240 |
| SN1_H20 | Train ex-2016 | 1216 | 4.224% | 4.057% | 0.168% | 1.048 | 1.007 | 4.029% | 4.030% | 0.00673 | -6.213% | 0.01115 |
| SN1_H20 | Historical Valid | 2521 | 0.538% | 0.297% | 0.241% | 0.118 | 0.065 | 4.545% | 4.544% | 0.00959 | -10.458% | 0.00599 |
| SN1_H20 | Historical Valid ex-2016 | 2337 | 1.139% | 0.913% | 0.226% | 0.261 | 0.209 | 4.366% | 4.367% | 0.00902 | -8.792% | 0.00746 |


## Long/Short

Short remains Net-negative in every pooled window and all candidates. H5/H20 do not establish a Short-alpha improvement.

| Candidate | Window | Long gross | Long net | Long SR | Short gross | Short net | Short SR | L/S corr. | Gross exp. | Net exp. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SN1_H1 | Full Train | 6.230% | 6.161% | 1.253 | -1.522% | -1.644% | -0.325 | -0.638 | 1.0017 | -0.0006 |
| SN1_H1 | Train ex-2016 | 5.812% | 5.748% | 1.226 | -1.587% | -1.691% | -0.359 | -0.634 | 1.0016 | -0.0006 |
| SN1_H1 | Historical Valid | 2.141% | 2.071% | 0.434 | -1.658% | -1.826% | -0.351 | -0.553 | 1.0016 | -0.0006 |
| SN1_H1 | Historical Valid ex-2016 | 2.323% | 2.258% | 0.483 | -1.157% | -1.316% | -0.252 | -0.581 | 1.0016 | -0.0006 |
| SN1_H5 | Full Train | 6.235% | 6.166% | 1.255 | -1.534% | -1.656% | -0.328 | -0.637 | 1.0017 | -0.0006 |
| SN1_H5 | Train ex-2016 | 5.818% | 5.755% | 1.228 | -1.602% | -1.706% | -0.362 | -0.634 | 1.0016 | -0.0006 |
| SN1_H5 | Historical Valid | 2.157% | 2.087% | 0.438 | -1.600% | -1.770% | -0.341 | -0.553 | 1.0016 | -0.0006 |
| SN1_H5 | Historical Valid ex-2016 | 2.344% | 2.279% | 0.488 | -1.157% | -1.318% | -0.253 | -0.583 | 1.0016 | -0.0006 |
| SN1_H20 | Full Train | 6.230% | 6.162% | 1.253 | -1.426% | -1.549% | -0.308 | -0.638 | 1.0017 | -0.0006 |
| SN1_H20 | Train ex-2016 | 5.810% | 5.747% | 1.225 | -1.586% | -1.690% | -0.359 | -0.632 | 1.0016 | -0.0006 |
| SN1_H20 | Historical Valid | 2.160% | 2.090% | 0.439 | -1.622% | -1.793% | -0.350 | -0.579 | 1.0016 | -0.0006 |
| SN1_H20 | Historical Valid ex-2016 | 2.339% | 2.274% | 0.487 | -1.199% | -1.361% | -0.264 | -0.609 | 1.0016 | -0.0006 |


## Gross, selection, cost and exposure

Account decomposition uses ΔNet = ΔGross − ΔCost. Common weights are held fixed; ΔGross equals arithmetic changed-weight selection. This is attribution, not causal proof. Mean net-exposure drift is zero to displayed precision.

| Candidate vs H1 | Split | ΔGross bp/y | ΔCost bp/y | ΔNet bp/y | ΔTurn/day | ΔGross vol pp | ΔNet exp. | Selection bp/y |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H5 | train | -0.69 | 0.039 | -0.73 | 0.000014 | -0.001 | 0.0000000 | -0.69 |
| H5 | valid | 7.40 | 0.144 | 7.26 | 0.000057 | -0.006 | -0.0000000 | 7.40 |
| H20 | train | 9.61 | 0.061 | 9.55 | 0.000023 | -0.015 | -0.0000000 | 9.61 |
| H20 | valid | 5.48 | 0.199 | 5.28 | 0.000079 | -0.185 | -0.0000000 | 5.48 |


H5 Train is −0.73 bp/year Net; H5 old Valid +7.26 bp. H20 Train +9.55 bp full-period but −0.04 bp ex-2016; old Valid +5.28 bp. Turnover and cost rise slightly in all four comparisons, so any gains are selection/risk changes rather than cheaper trading. Long annual Net contribution changes are only +0.50/+1.59 bp for H5 and +0.03/+1.90 bp for H20 (Train/old Valid). Short remains negative. H20's gross vol falls modestly in old Valid; all other volatility shifts are very small.

## Calendar-year stability

Annualized Net is mean daily Net × 252. 2016 Train is a 59-session partial; 2016 historical Valid is a separate 184-session partial; 2026 Valid is 139 sessions. Years were not selected after seeing the results.

| Candidate | Split | Year | Days | Net annualized | Net SR | Turnover/day | Daily RankIC |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SN1_H1 | train | 2011 | 243 | 0.033% | 0.007 | 0.01593 | 0.00105 |
| SN1_H1 | train | 2012 | 246 | 4.816% | 1.082 | 0.00933 | 0.01551 |
| SN1_H1 | train | 2013 | 243 | 7.729% | 1.670 | 0.00073 | 0.01663 |
| SN1_H1 | train | 2014 | 242 | 4.032% | 1.954 | 0.00406 | 0.01171 |
| SN1_H1 | train | 2015 | 242 | 3.664% | 0.920 | 0.00348 | 0.01137 |
| SN1_H1 | train | 2016* | 59 | 14.004% | 1.850 | 0.02699 | 0.03724 |
| SN1_H1 | valid | 2016* | 184 | -8.617% | -1.324 | 0.01708 | -0.01402 |
| SN1_H1 | valid | 2017 | 247 | 6.666% | 2.963 | 0.00136 | 0.01653 |
| SN1_H1 | valid | 2018 | 245 | -2.567% | -0.744 | 0.01965 | -0.00168 |
| SN1_H1 | valid | 2019 | 241 | 0.022% | 0.006 | 0.01048 | 0.00883 |
| SN1_H1 | valid | 2020 | 242 | 9.456% | 1.030 | 0.01641 | 0.02339 |
| SN1_H1 | valid | 2021 | 245 | -2.957% | -0.594 | 0.00599 | 0.00085 |
| SN1_H1 | valid | 2022 | 244 | -4.418% | -1.230 | 0.01317 | -0.00149 |
| SN1_H1 | valid | 2023 | 246 | 3.754% | 1.181 | 0.00311 | 0.01734 |
| SN1_H1 | valid | 2024 | 245 | 4.675% | 1.328 | 0.00656 | 0.01294 |
| SN1_H1 | valid | 2025 | 243 | 0.352% | 0.095 | 0.00562 | 0.00262 |
| SN1_H1 | valid | 2026* | 139 | -10.512% | -2.711 | 0.00558 | -0.01144 |
| SN1_H5 | train | 2011 | 243 | 0.116% | 0.026 | 0.01597 | 0.00089 |
| SN1_H5 | train | 2012 | 246 | 4.732% | 1.067 | 0.00930 | 0.01548 |
| SN1_H5 | train | 2013 | 243 | 7.686% | 1.660 | 0.00073 | 0.01653 |
| SN1_H5 | train | 2014 | 242 | 4.067% | 1.977 | 0.00407 | 0.01160 |
| SN1_H5 | train | 2015 | 242 | 3.635% | 0.914 | 0.00348 | 0.01128 |
| SN1_H5 | train | 2016* | 59 | 14.005% | 1.853 | 0.02723 | 0.03752 |
| SN1_H5 | valid | 2016* | 184 | -7.865% | -1.194 | 0.01699 | -0.01351 |
| SN1_H5 | valid | 2017 | 247 | 6.739% | 2.947 | 0.00137 | 0.01660 |
| SN1_H5 | valid | 2018 | 245 | -2.591% | -0.754 | 0.01980 | -0.00176 |
| SN1_H5 | valid | 2019 | 241 | -0.348% | -0.089 | 0.01047 | 0.00845 |
| SN1_H5 | valid | 2020 | 242 | 9.325% | 1.022 | 0.01675 | 0.02359 |
| SN1_H5 | valid | 2021 | 245 | -2.812% | -0.562 | 0.00597 | 0.00100 |
| SN1_H5 | valid | 2022 | 244 | -4.174% | -1.164 | 0.01323 | -0.00154 |
| SN1_H5 | valid | 2023 | 246 | 3.785% | 1.190 | 0.00311 | 0.01732 |
| SN1_H5 | valid | 2024 | 245 | 4.829% | 1.387 | 0.00667 | 0.01293 |
| SN1_H5 | valid | 2025 | 243 | 0.351% | 0.094 | 0.00568 | 0.00236 |
| SN1_H5 | valid | 2026* | 139 | -10.417% | -2.710 | 0.00553 | -0.01148 |
| SN1_H20 | train | 2011 | 243 | 0.058% | 0.013 | 0.01594 | 0.00095 |
| SN1_H20 | train | 2012 | 246 | 4.723% | 1.069 | 0.00938 | 0.01553 |
| SN1_H20 | train | 2013 | 243 | 7.661% | 1.654 | 0.00073 | 0.01642 |
| SN1_H20 | train | 2014 | 242 | 4.073% | 1.977 | 0.00407 | 0.01153 |
| SN1_H20 | train | 2015 | 242 | 3.759% | 0.937 | 0.00346 | 0.01129 |
| SN1_H20 | train | 2016* | 59 | 16.076% | 2.209 | 0.02729 | 0.03818 |
| SN1_H20 | valid | 2016* | 184 | -7.524% | -1.181 | 0.01693 | -0.01267 |
| SN1_H20 | valid | 2017 | 247 | 6.783% | 2.911 | 0.00136 | 0.01645 |
| SN1_H20 | valid | 2018 | 245 | -2.875% | -0.840 | 0.01986 | -0.00174 |
| SN1_H20 | valid | 2019 | 241 | 0.641% | 0.166 | 0.01054 | 0.00982 |
| SN1_H20 | valid | 2020 | 242 | 8.457% | 0.994 | 0.01738 | 0.02108 |
| SN1_H20 | valid | 2021 | 245 | -2.490% | -0.533 | 0.00593 | 0.00104 |
| SN1_H20 | valid | 2022 | 244 | -4.188% | -1.182 | 0.01299 | -0.00079 |
| SN1_H20 | valid | 2023 | 246 | 3.820% | 1.202 | 0.00311 | 0.01720 |
| SN1_H20 | valid | 2024 | 245 | 4.552% | 1.306 | 0.00658 | 0.01263 |
| SN1_H20 | valid | 2025 | 243 | 0.331% | 0.090 | 0.00561 | 0.00236 |
| SN1_H20 | valid | 2026* | 139 | -11.091% | -2.903 | 0.00547 | -0.01172 |


H20's Train pooled gain is concentrated in 2016 partial (+207.16 bp annualized vs H1); 2011–2015 deltas are small/mixed. Old Valid differences change sign by year.

## Forecast quality and horizon consistency

Daily cross-sectional RankIC uses the fixed SN1 score versus date-centered rank of the specified forward residual window; HAC lag is exactly H. Overlapping returns are prediction diagnostics, never annualized as daily portfolio P/L.

| H | Period | Forward residual window | Mean daily RankIC | HAC t (lag=H) | Hit rate | Days |
| --- | --- | --- | --- | --- | --- | --- |
| H1 | train | day1 | 0.01273 | 3.26 | 0.546 | 1285 |
| H1 | valid | day1 | 0.00603 | 2.08 | 0.532 | 2521 |
| H5 | train | day1 | 0.01265 | 3.16 | 0.546 | 1285 |
| H5 | train | days1_5 | 0.02754 | 3.56 | 0.593 | 1281 |
| H5 | train | days6_20 | 0.03893 | 4.38 | 0.623 | 1266 |
| H5 | valid | day1 | 0.00603 | 2.07 | 0.532 | 2521 |
| H5 | valid | days1_5 | 0.00705 | 1.23 | 0.558 | 2517 |
| H5 | valid | days6_20 | 0.00626 | 0.93 | 0.535 | 2502 |
| H20 | train | day1 | 0.01266 | 3.25 | 0.545 | 1285 |
| H20 | train | days1_5 | 0.02756 | 3.32 | 0.591 | 1281 |
| H20 | train | days1_20 | 0.04234 | 3.03 | 0.637 | 1266 |
| H20 | train | days21_40 | 0.04167 | 2.94 | 0.652 | 1246 |
| H20 | valid | day1 | 0.00599 | 2.20 | 0.534 | 2521 |
| H20 | valid | days1_5 | 0.00708 | 1.17 | 0.555 | 2517 |
| H20 | valid | days1_20 | 0.00503 | 0.50 | 0.538 | 2502 |
| H20 | valid | days21_40 | 0.00764 | 0.78 | 0.536 | 2482 |


H5 Train relates to days 1–5 and 6–20, but old Valid t-statistics are 1.23 and .93. H20's Train 1–20/21–40 t-statistics are 3.03/2.94; old Valid is .50/.78. That is not repeatable evidence for persistent 20-day alpha.

Event-only RankIC is computed cross-sectionally among active events for each side. HAC lag remains the fixed candidate horizon. It is noisier than the whole-book score IC:

| H | Period | Event side | Window | Mean RankIC | HAC t (lag=H) | Hit rate | Days |
| --- | --- | --- | --- | --- | --- | --- | --- |
| H1 | train | High | day1 | 0.01143 | 0.68 | 0.518 | 941 |
| H1 | train | Low | day1 | 0.00715 | 0.20 | 0.488 | 332 |
| H1 | valid | High | day1 | 0.01848 | 1.70 | 0.519 | 2090 |
| H1 | valid | Low | day1 | -0.02645 | -1.31 | 0.463 | 1048 |
| H5 | train | High | day1 | 0.00801 | 0.50 | 0.504 | 941 |
| H5 | train | High | days1_5 | -0.02451 | -1.41 | 0.473 | 938 |
| H5 | train | High | days6_20 | 0.03202 | 1.86 | 0.523 | 929 |
| H5 | train | Low | day1 | -0.05461 | -1.58 | 0.476 | 332 |
| H5 | train | Low | days1_5 | 0.00714 | 0.17 | 0.491 | 332 |
| H5 | train | Low | days6_20 | 0.02067 | 0.51 | 0.473 | 332 |
| H5 | valid | High | day1 | 0.01837 | 1.72 | 0.504 | 2090 |
| H5 | valid | High | days1_5 | 0.01622 | 1.38 | 0.509 | 2086 |
| H5 | valid | High | days6_20 | -0.01455 | -1.22 | 0.473 | 2071 |
| H5 | valid | Low | day1 | 0.01271 | 0.70 | 0.479 | 1048 |
| H5 | valid | Low | days1_5 | 0.00221 | 0.10 | 0.487 | 1048 |
| H5 | valid | Low | days6_20 | 0.00755 | 0.35 | 0.489 | 1048 |
| H20 | train | High | day1 | 0.00879 | 0.47 | 0.506 | 941 |
| H20 | train | High | days1_20 | 0.00636 | 0.37 | 0.488 | 929 |
| H20 | train | High | days21_40 | 0.01517 | 0.74 | 0.506 | 924 |
| H20 | train | Low | day1 | 0.01340 | 0.47 | 0.509 | 332 |
| H20 | train | Low | days1_20 | 0.05511 | 1.53 | 0.518 | 332 |
| H20 | train | Low | days21_40 | -0.02353 | -0.69 | 0.433 | 319 |
| H20 | valid | High | day1 | 0.02126 | 2.08 | 0.506 | 2090 |
| H20 | valid | High | days1_20 | -0.00814 | -0.77 | 0.486 | 2071 |
| H20 | valid | High | days21_40 | 0.00683 | 0.60 | 0.487 | 2052 |
| H20 | valid | Low | day1 | 0.04352 | 2.08 | 0.512 | 1048 |
| H20 | valid | Low | days1_20 | 0.03957 | 1.97 | 0.538 | 1048 |
| H20 | valid | Low | days21_40 | 0.00219 | 0.10 | 0.503 | 1035 |

The notable old-Valid asymmetry is that H20 High events relate to day 1 but not days 1–20; H20 Low events have a modest days 1–20 relation that disappears over days 21–40. Whole-book Short remains negative.

### Event-date forward residual contribution (descriptive)

The fixed breakout events also have a per-event forward residual profile. High events are oriented long (+residual), Low events short (−residual). Returns compound daily market residuals over the four user-specified windows. This is an unweighted event-level diagnostic, not SN1 portfolio P/L; no candidate or decision is selected from it. Event definitions are fixed, so values are common across H1/H5/H20. Script SHA256 9e68da202f5f2611c14839550894f3f597d85cd20061bed623734aa30c0dcc60; exact offsets are in audit/event_forward_contribution_manifest.json.

| Split | Event side | Forward window | Events | Event dates | Mean oriented bp/event | Mean date-equal bp | Positive event share |
| --- | --- | --- | --- | --- | --- | --- | --- |
| train | High | day1 | 15506 | 1079 | -0.43 | -4.50 | 48.5% |
| train | Low | day1 | 4300 | 513 | 12.55 | 6.89 | 52.4% |
| train | High | days2_5 | 15481 | 1075 | 6.34 | 18.54 | 49.3% |
| train | Low | days2_5 | 4300 | 513 | -14.80 | -3.59 | 49.3% |
| train | High | days6_20 | 15447 | 1065 | 67.44 | 90.66 | 52.3% |
| train | Low | days6_20 | 4296 | 509 | -61.71 | -9.70 | 47.6% |
| train | High | days21_40 | 15419 | 1054 | 41.76 | 107.33 | 49.7% |
| train | Low | days21_40 | 3764 | 492 | -47.42 | -42.74 | 48.8% |
| Historical Valid | High | day1 | 30464 | 2291 | -4.54 | -4.79 | 48.7% |
| Historical Valid | Low | day1 | 11667 | 1470 | -7.35 | -0.63 | 49.0% |
| Historical Valid | High | days2_5 | 30354 | 2287 | -2.98 | 2.14 | 48.3% |
| Historical Valid | Low | days2_5 | 11667 | 1470 | -24.52 | -2.65 | 48.6% |
| Historical Valid | High | days6_20 | 30195 | 2272 | 10.37 | 17.84 | 47.9% |
| Historical Valid | Low | days6_20 | 11667 | 1470 | -10.24 | -18.58 | 50.1% |
| Historical Valid | High | days21_40 | 29986 | 2253 | 42.29 | 58.10 | 49.3% |
| Historical Valid | Low | days21_40 | 11622 | 1451 | -69.18 | -26.32 | 48.4% |

Train signals stop at 2016-03-29 and historical-Valid event windows stop as soon as a fixed forward return is unavailable. Event counts vary with each window's maturity.


### Training sample and coefficient stability

| H | Fold year | High event rows | Low event rows |
| --- | --- | --- | --- |
| H1 | 2011 | 1006 | 1150 |
| H1 | 2012 | 1946 | 2380 |
| H1 | 2013 | 3596 | 3711 |
| H1 | 2014 | 8907 | 3733 |
| H1 | 2015 | 12184 | 4191 |
| H1 | 2016 | 16388 | 4521 |
| H5 | 2011 | 998 | 1148 |
| H5 | 2012 | 1941 | 2367 |
| H5 | 2013 | 3512 | 3710 |
| H5 | 2014 | 8827 | 3733 |
| H5 | 2015 | 12107 | 4191 |
| H5 | 2016 | 16383 | 4505 |
| H20 | 2011 | 900 | 1141 |
| H20 | 2012 | 1934 | 2353 |
| H20 | 2013 | 3283 | 3708 |
| H20 | 2014 | 8677 | 3731 |
| H20 | 2015 | 11716 | 4179 |
| H20 | 2016 | 16334 | 4477 |


All folds pass the fixed 500-event minimum. Coefficient-sign consistency across the six annual expanding fits is only a descriptive check; sign stability varies by side/horizon and does not increase uniformly.

Standardized Ridge slopes by feature are summarized below as mean, population SD, and range across the six Train folds. The feature scaling is re-fit in each fold, so compare direction/stability within this table rather than interpreting cross-feature slope magnitudes as importance.

| H | Side | Feature | Mean slope | Fold SD | Fold range |
| --- | --- | --- | --- | --- | --- |
| H1 | High | box_duration | 0.0009 | 0.0155 | -0.0106…0.0336 |
| H1 | High | box_width_atr | 0.0041 | 0.0069 | -0.0040…0.0146 |
| H1 | High | distance_to_prior_extreme | -0.0021 | 0.0196 | -0.0353…0.0159 |
| H1 | High | oriented_close_position | -0.0200 | 0.0104 | -0.0329…-0.0017 |
| H1 | High | oriented_relative_strength_60 | -0.0211 | 0.0123 | -0.0417…-0.0027 |
| H1 | Low | box_duration | 0.0155 | 0.0084 | 0.0057…0.0283 |
| H1 | Low | box_width_atr | 0.0077 | 0.0033 | 0.0010…0.0115 |
| H1 | Low | distance_to_prior_extreme | 0.0103 | 0.0048 | 0.0056…0.0202 |
| H1 | Low | oriented_close_position | 0.0223 | 0.0080 | 0.0074…0.0337 |
| H1 | Low | oriented_relative_strength_60 | -0.0178 | 0.0137 | -0.0465…-0.0062 |
| H5 | High | box_duration | -0.0036 | 0.0145 | -0.0140…0.0283 |
| H5 | High | box_width_atr | 0.0154 | 0.0152 | 0.0006…0.0365 |
| H5 | High | distance_to_prior_extreme | -0.0071 | 0.0193 | -0.0449…0.0083 |
| H5 | High | oriented_close_position | -0.0066 | 0.0200 | -0.0304…0.0278 |
| H5 | High | oriented_relative_strength_60 | -0.0074 | 0.0132 | -0.0243…0.0095 |
| H5 | Low | box_duration | 0.0017 | 0.0088 | -0.0075…0.0197 |
| H5 | Low | box_width_atr | 0.0200 | 0.0031 | 0.0139…0.0231 |
| H5 | Low | distance_to_prior_extreme | -0.0006 | 0.0043 | -0.0047…0.0079 |
| H5 | Low | oriented_close_position | 0.0223 | 0.0195 | -0.0205…0.0357 |
| H5 | Low | oriented_relative_strength_60 | -0.0207 | 0.0091 | -0.0347…-0.0138 |
| H20 | High | box_duration | -0.0051 | 0.0196 | -0.0212…0.0332 |
| H20 | High | box_width_atr | 0.0129 | 0.0088 | 0.0048…0.0291 |
| H20 | High | distance_to_prior_extreme | -0.0073 | 0.0146 | -0.0345…0.0091 |
| H20 | High | oriented_close_position | -0.0059 | 0.0165 | -0.0316…0.0235 |
| H20 | High | oriented_relative_strength_60 | -0.0021 | 0.0196 | -0.0185…0.0264 |
| H20 | Low | box_duration | -0.0067 | 0.0036 | -0.0138…-0.0029 |
| H20 | Low | box_width_atr | 0.0303 | 0.0057 | 0.0212…0.0401 |
| H20 | Low | distance_to_prior_extreme | -0.0177 | 0.0026 | -0.0221…-0.0134 |
| H20 | Low | oriented_close_position | -0.0152 | 0.0079 | -0.0310…-0.0050 |
| H20 | Low | oriented_relative_strength_60 | -0.0078 | 0.0211 | -0.0546…0.0069 |

| H | Side | Feature signs stable across six folds | Annual fit rows min–max | Final Train rows for Valid fit |
| --- | --- | --- | --- | --- |
| H1 | High | 2/5 | 1006–16388 | 16520 |
| H1 | Low | 5/5 | 1150–4521 | 5450 |
| H5 | High | 1/5 | 998–16383 | 16495 |
| H5 | Low | 2/5 | 1148–4505 | 5450 |
| H20 | High | 1/5 | 900–16334 | 16461 |
| H20 | Low | 4/5 | 1141–4477 | 5446 |


Event prediction dispersion changes by side rather than shrinking uniformly:

| H | Split | Side | Events/day mean | median | Pred. SD median/day | mean/day | pooled SD |
| --- | --- | --- | --- | --- | --- | --- | --- |
| H1 | Train | High | 14.36 | 7.0 | 0.02489 | 0.03065 | 0.03984 |
| H1 | Train | Low | 8.35 | 2.0 | 0.02570 | 0.03711 | 0.06271 |
| H1 | Valid | High | 13.29 | 8.0 | 0.02266 | 0.02406 | 0.02951 |
| H1 | Valid | Low | 7.94 | 3.0 | 0.01297 | 0.01368 | 0.02127 |
| H5 | Train | High | 14.36 | 7.0 | 0.02438 | 0.02887 | 0.04880 |
| H5 | Train | Low | 8.35 | 2.0 | 0.03152 | 0.03725 | 0.05806 |
| H5 | Valid | High | 13.29 | 8.0 | 0.01803 | 0.01978 | 0.02396 |
| H5 | Valid | Low | 7.94 | 3.0 | 0.01384 | 0.01466 | 0.02052 |
| H20 | Train | High | 14.36 | 7.0 | 0.02157 | 0.02765 | 0.06079 |
| H20 | Train | Low | 8.35 | 2.0 | 0.03283 | 0.04446 | 0.08569 |
| H20 | Valid | High | 13.29 | 8.0 | 0.01499 | 0.01977 | 0.02618 |
| H20 | Valid | Low | 7.94 | 3.0 | 0.02032 | 0.02148 | 0.03178 |


## Holding persistence and turnover

Sleeve spells are continuous Long/Short membership, not a claim that exact share quantities are never rebalanced. H1's one-day target coexists with these long membership spells:

| H | Split | 1d rank autocorr | Q1 retain | Q2 retain | Q4 retain | Q5 retain | Long mean d | Long median d | Long ≥20d | Short mean d | Short median d | Short ≥20d |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H1 | train | 99.598% | 99.180% | 99.077% | 99.387% | 99.642% | 333.7 | 141.0 | 84.957% | 264.3 | 154.0 | 91.723% |
| H1 | valid | 99.555% | 98.883% | 98.748% | 99.465% | 99.743% | 330.8 | 207.5 | 87.399% | 224.1 | 165.0 | 90.055% |
| H5 | train | 99.598% | 99.174% | 99.079% | 99.391% | 99.643% | 334.6 | 141.5 | 85.345% | 264.0 | 149.0 | 91.733% |
| H5 | valid | 99.551% | 98.870% | 98.738% | 99.465% | 99.743% | 331.4 | 207.0 | 87.171% | 222.9 | 164.0 | 89.746% |
| H20 | train | 99.593% | 99.165% | 99.074% | 99.390% | 99.643% | 334.6 | 141.5 | 85.345% | 266.4 | 149.0 | 92.343% |
| H20 | valid | 99.543% | 98.869% | 98.733% | 99.463% | 99.749% | 328.8 | 198.0 | 87.609% | 221.2 | 162.0 | 89.914% |


Train mean daily turnover: H1 .7655%, H5 .7669%, H20 .7678%. Old Valid: .9514%, .9571%, .9593%. H1/H5/H20 mean rank autocorrelation and Q retention differ negligibly.

- Mean distinct codes/day: 452 Train and 486 old Valid; Long/Short membership averages about 181/181 and 195/195. Effective weighted holdings are 326/350.
- Daily entrants/exits are below one per sleeve: Train Long .38/.40, Short .55/.54; old Valid Long .50/.51, Short .79/.79.
- Lag-1 rank correlation is ~.996; score Spearman ~.996, Pearson .805 Train/.782 old Valid. Mean absolute score change is .00668/.00645; nonzero sign flips .046%/.034%.
- Fixed score-decay profile:

| Split | Lag d | Pearson | Spearman | Daily CS rank corr. | Mean abs score change | Nonzero sign flip |
| --- | --- | --- | --- | --- | --- | --- |
| Train | 1 | 0.805 | 0.996 | 0.996 | 0.00668 | 0.046% |
| Train | 5 | 0.374 | 0.980 | 0.982 | 0.01537 | 0.229% |
| Train | 20 | 0.146 | 0.922 | 0.937 | 0.02004 | 0.912% |
| Train | 40 | 0.095 | 0.852 | 0.889 | 0.02062 | 1.775% |
| Historical Valid | 1 | 0.782 | 0.995 | 0.996 | 0.00645 | 0.034% |
| Historical Valid | 5 | 0.313 | 0.977 | 0.978 | 0.01411 | 0.163% |
| Historical Valid | 20 | 0.091 | 0.914 | 0.920 | 0.01788 | 0.624% |
| Historical Valid | 40 | 0.072 | 0.838 | 0.851 | 0.01832 | 1.222% |


Daily quintile transitions (rows are prior quintile, columns are next quintile) for H1:

| Split | Prior quintile | To Q1 | To Q2 | To Q3 | To Q4 | To Q5 |
| --- | --- | --- | --- | --- | --- | --- |
| train | H1 Q1 | 99.183% | 0.777% | 0.020% | 0.000% | 0.021% |
| train | H1 Q2 | 0.363% | 99.080% | 0.525% | 0.000% | 0.031% |
| train | H1 Q3 | 0.180% | 0.088% | 99.361% | 0.332% | 0.039% |
| train | H1 Q4 | 0.201% | 0.043% | 0.098% | 99.392% | 0.266% |
| train | H1 Q5 | 0.083% | 0.013% | 0.000% | 0.258% | 99.646% |
| valid | H1 Q1 | 98.887% | 1.112% | 0.000% | 0.001% | 0.000% |
| valid | H1 Q2 | 0.432% | 98.754% | 0.810% | 0.004% | 0.000% |
| valid | H1 Q3 | 0.265% | 0.065% | 99.156% | 0.514% | 0.000% |
| valid | H1 Q4 | 0.226% | 0.035% | 0.022% | 99.467% | 0.249% |
| valid | H1 Q5 | 0.199% | 0.027% | 0.013% | 0.017% | 99.744% |

The largest normalized transition-cell difference versus H1 is tiny:

| Split | Candidate | Max row-normalized cell difference vs H1 |
| --- | --- | --- |
| train | H5 | 0.0060 pp |
| train | H20 | 0.0171 pp |
| valid | H5 | 0.0130 pp |
| valid | H20 | 0.0151 pp |

Persistent sleeve P/L by the predeclared ≥20-day spell split:

| H | Split | Spell group | Side | Stock-days | Gross contribution/y |
| --- | --- | --- | --- | --- | --- |
| H1 | train | persistent_20plus | long | 220787 | 6.160% |
| H1 | train | persistent_20plus | short | 217055 | -1.362% |
| H1 | train | newer_under20 | long | 12115 | -0.047% |
| H1 | train | newer_under20 | short | 16051 | 0.024% |
| H5 | train | persistent_20plus | long | 220754 | 6.133% |
| H5 | train | persistent_20plus | short | 217036 | -1.389% |
| H5 | train | newer_under20 | long | 12148 | -0.018% |
| H5 | train | newer_under20 | short | 16070 | 0.042% |
| H20 | train | persistent_20plus | long | 220761 | 6.116% |
| H20 | train | persistent_20plus | short | 217126 | -1.332% |
| H20 | train | newer_under20 | long | 12141 | -0.006% |
| H20 | train | newer_under20 | short | 15980 | 0.095% |
| H1 | Historical Valid | persistent_20plus | long | 464969 | 2.294% |
| H1 | Historical Valid | persistent_20plus | short | 452585 | -1.473% |
| H1 | Historical Valid | newer_under20 | long | 25879 | -0.154% |
| H1 | Historical Valid | newer_under20 | short | 38718 | -0.183% |
| H5 | Historical Valid | persistent_20plus | long | 465118 | 2.273% |
| H5 | Historical Valid | persistent_20plus | short | 452532 | -1.434% |
| H5 | Historical Valid | newer_under20 | long | 25730 | -0.117% |
| H5 | Historical Valid | newer_under20 | short | 38771 | -0.165% |
| H20 | Historical Valid | persistent_20plus | long | 464803 | 2.318% |
| H20 | Historical Valid | persistent_20plus | short | 451855 | -1.518% |
| H20 | Historical Valid | newer_under20 | long | 26045 | -0.160% |
| H20 | Historical Valid | newer_under20 | short | 39448 | -0.102% |


Persistent Longs account for nearly all positive gross Long contribution; persistent Shorts account for most negative gross Short contribution. Those contributions are already present under H1 and are not created by target extension.

Sector and scale concentration barely change from H1 to H20:

| H | Split | PIT classification | Side | Mean HHI | Top category share |
| --- | --- | --- | --- | --- | --- |
| H1 | train | Sector17Code | long | 0.093 | 17.7% |
| H1 | train | Sector17Code | short | 0.096 | 17.5% |
| H1 | train | ScaleCategory | long | 0.403 | 58.1% |
| H1 | train | ScaleCategory | short | 0.497 | 67.1% |
| H20 | train | Sector17Code | long | 0.093 | 17.7% |
| H20 | train | Sector17Code | short | 0.096 | 17.4% |
| H20 | train | ScaleCategory | long | 0.403 | 58.2% |
| H20 | train | ScaleCategory | short | 0.495 | 67.0% |
| H1 | Historical Valid | Sector17Code | long | 0.096 | 18.2% |
| H1 | Historical Valid | Sector17Code | short | 0.090 | 16.1% |
| H1 | Historical Valid | ScaleCategory | long | 0.475 | 65.6% |
| H1 | Historical Valid | ScaleCategory | short | 0.590 | 74.8% |
| H20 | Historical Valid | Sector17Code | long | 0.096 | 18.4% |
| H20 | Historical Valid | Sector17Code | short | 0.089 | 15.8% |
| H20 | Historical Valid | ScaleCategory | long | 0.474 | 65.6% |
| H20 | Historical Valid | ScaleCategory | short | 0.590 | 74.8% |


Top scale-category weight shares are about 58% Long/67% Short Train and 66%/75% old Valid; sector shares are lower.

## Paired uncertainty

Existing paired circular block bootstrap: 20 sessions, 1,000 replications, seed 20260908. All 95% intervals include zero.

| Candidate | Split | ΔSR median | 95% interval | ΔNet/y median | 95% interval | Share ΔSR>0 | Block | Rep. | Seed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H5 | train | -0.001 | [-0.034, 0.027] | -0.005% | [-0.142%, 0.114%] | 47.800% | 20 | 1000 | 20260908 |
| H5 | valid | 0.016 | [-0.010, 0.041] | 0.075% | [-0.057%, 0.188%] | 88.200% | 20 | 1000 | 20260908 |
| H20 | train | 0.025 | [-0.024, 0.082] | 0.087% | [-0.103%, 0.323%] | 83.200% | 20 | 1000 | 20260908 |
| H20 | valid | 0.014 | [-0.047, 0.076] | 0.053% | [-0.268%, 0.366%] | 65.700% | 20 | 1000 | 20260908 |


## Score and portfolio checks

| H | Split | Zero | Duplicate | Unique mean | Unique min/day | Boundary ties | Days w/tie | 5 buckets | Days | Gross exp. | Net exp. | Finite |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H1 | train | 8.906% | 8.747% | 91.253% | 3.425% | 14.433% | 48.329% | 1287 | 1287 | 1.0017 | -0.0006 | PASS |
| H1 | valid | 0.996% | 0.828% | 99.172% | 92.308% | 1.803% | 7.214% | 2523 | 2523 | 1.0016 | -0.0006 | PASS |
| H5 | train | 8.906% | 8.765% | 91.235% | 3.425% | 14.472% | 48.329% | 1287 | 1287 | 1.0017 | -0.0006 | PASS |
| H5 | valid | 0.996% | 0.943% | 99.057% | 91.498% | 1.843% | 7.372% | 2523 | 2523 | 1.0016 | -0.0006 | PASS |
| H20 | train | 8.906% | 8.750% | 91.250% | 3.425% | 14.433% | 48.329% | 1287 | 1287 | 1.0017 | -0.0006 | PASS |
| H20 | valid | 0.996% | 0.926% | 99.074% | 91.498% | 1.843% | 7.372% | 2523 | 2523 | 1.0016 | -0.0006 | PASS |


Official rank(method="first") and existing weights were preserved. All five quintiles were populated on every account date (1,287 Train, 2,523 old Valid); scores are finite. Train exact-zero rate is 8.9%, duplicate rows 8.7%, minimum daily unique ratio 3.42%, and boundary ties occur on 48.3% of days. Historical Valid is much more continuous. No secondary tie-break changed.

## Interpretation

A horizon mismatch is present mechanically: median sleeve membership lasts roughly 141–208 sessions while H1 matures two trading-calendar positions after signal. But H5/H20 alone do not materially change scores' ranks, spells, Long/Short composition, or turnover. H5/H20 are **MIXED**. Keep the existing H1 reference for paper collection.
