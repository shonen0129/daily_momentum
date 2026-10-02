# DM-20261002-03 — 2025 retrospective NCMOM20 diagnostic

## Decision

**MIXED; the 2025 retrospective does not establish robust incremental value over SN1_H1.** NCMOM20's pooled RankIC and Q5−Q1 are positive but weakly estimated. The same-coverage SN1_H1 scores rank the target somewhat better, NCMOM20's costed portfolio proxy is negative, and coverage is only 2.22% of the evaluation basket. A positive conditional RankIC appeared in SN1 score quintile 2, but only on 52 dates with at least three covered names; other testable quintiles were mixed.

At the user's request, the current 2026.09 relationship graph was held fixed over 2025 under a relationship-stability assumption. This is deliberately **non-PIT and hindsight-biased**. The target period is already-read historical Valid/development data, so it is not independent OOS and this report makes no causal or adoption claim. The earlier `PIT INSUFFICIENT` conclusion for Train remains unchanged.

## Archive note

The calculation was first executed as `DM-20261002-02`. During finalization, the shared workspace changed that ID's plan/config to a separate 2024 diagnostic. To avoid overwriting those edits, this 2025 result is archived here as `DM-20261002-03`. The copied source config matches its original recorded hash. The original plan hash remains in the source lock, but the available reconstructed source-plan text does not match that hash because the original file was replaced. A post-result reproduction used the same inputs, feature, edge filter, dates, cost and portfolio rules to complete the conditional RankIC calculation; it was not a new search or selection run.

## Fixed setup

- Requested period: 2025-01-04 through 2025-12-30 inclusive. There were 243 Japanese trading dates, from 2025-01-06 through 2025-12-30.
- Graph: JP_Market_Vis `2026.09` M5 relation snapshot and M4 company map, both generated 2026-09-22; held fixed on every signal date. The repository defines `major_customer` as a directed supplier-to-customer relationship, principally a customer accounting for at least 10% of consolidated sales. [JP_Market_Vis](https://github.com/mattyamonaca/JP_Market_Vis)
- Edge filter: `major_customer`, `confirmed`, at least one primary EDINET evidence record, both endpoints listed, unique M4 securities code, exact `Code = securities_code + "0"` mapping, and normalized company name consistent on all 2025 listed-info rows. No fuzzy match, review-only relation, entity endpoint, reverse edge, or duplicate pair.
- The filter leaves **609 unique edges**, 508 suppliers, and 259 customers. The source has 2,369 `major_customer` rows (2,224 confirmed and 145 needing review); 1,572 confirmed-primary rows have a non-listed endpoint, and 43 more fail the locked exact code/name/current-panel match.
- NCMOM20 is the equal-weight mean of each linked customer's sum of 20 finite `raw_return - beta * TOPIX` returns ending on the market session before signal date `t`. A customer without a complete prior window is omitted; a supplier with no complete customer window is missing. No signal-date return, future return, or zero fill is used.
- Outcome is `target_1day_valid.parquet` `Return`, aligned on the same `(Date, Code)` as the saved fixed SN1_H1 score. `raw_target` was not accessed. No model was refit and no combined SN1_H1 + NCMOM20 score was created.

The selected EDINET records expose `as_of` dates but no `published` timestamp. The snapshot was generated in 2026 and does not establish that each edge was public on every 2025 signal date. The stability premise is an explicit retrospective scenario, not a PIT relationship contract.

## Coverage

| Measure | Result |
|---|---:|
| SN1_H1/target universe | 120,453 stock-days; 495.7 stocks per day on average |
| Graph suppliers with a computable feature in the listed market panel | 387 per day |
| Suppliers also present in the SN1_H1/target basket | 11 per day |
| Covered SN1_H1/target stock-days | 2,673 / 120,453 = **2.22%** |
| Mean complete linked customers per covered supplier | 1.27 |

Coverage is the largest practical limitation. The price panel can form features for many graph suppliers, but only 11 names per day overlap the evaluation basket. This makes matched-sample metrics noisy and prevents broad portfolio claims.

## Cross-sectional results

SN1_H1 and NCMOM20 are ranked independently on the exact same network-covered names each day. HAC t-statistics use a Bartlett/Newey–West estimator with five daily lags.

| Metric | NCMOM20 | SN1_H1 on same covered names |
|---|---:|---:|
| Mean daily RankIC | +0.0289 | +0.0328 |
| RankIC HAC(5) t | 1.56 | 1.46 |
| RankIC positive-day share | 54.3% | 55.6% |
| Mean Q5−Q1 target return | +4.55 bp/day | +12.91 bp/day |
| Q5−Q1 HAC(5) t | 0.49 | 1.39 |
| Strictly monotone quintiles, share of days | 0.82% | 2.06% |

Across paired daily observations, NCMOM20 minus SN1_H1 had RankIC difference −0.0040 (HAC(5) t −0.14) and Q5−Q1 difference −8.37 bp/day (HAC(5) t −0.64). Mean daily cross-sectional Spearman correlation between NCMOM20 and SN1_H1 was −0.027. The rankings differ, but this sample does not show that NCMOM20 improves the target ordering over SN1_H1.

Within daily full-universe SN1_H1 score quintiles, the covered sample was small. Daily RankIC was calculated only on dates with at least three covered issuers: it averaged +0.074 (HAC(5) t 1.17; 94 dates) in SN1 quintile 1, +0.144 (t 2.00; 52 dates) in quintile 2, −0.119 (t −0.91; 21 dates) in quintile 3, and +0.016 (t 0.50; 243 dates) in quintile 4; quintile 5 had no date with three names. The positive quintile-2 value comes from tiny daily cross-sections and is not consistent across testable buckets. A within-bucket five-way NCMOM quintile spread requires at least five covered names: only SN1 quintile 4 met that on 184 dates, where Q5−Q1 was −20.0 bp/day (HAC(5) t −1.01). This is mixed, sparse conditional evidence.

## Cost and portfolio diagnostic

Each signal separately formed an equal-weight Q5 long / Q1 short portfolio on the same covered names, with +0.5 total long and −0.5 total short exposure. We charged 10 bp one-way times the sum of absolute changes in target weights and charged the initial move from cash. This is a **small-subset diagnostic portfolio**, not the official competition five-quintile portfolio contract; P&L uses the residual target.

| Metric | NCMOM20 | SN1_H1 on same covered names |
|---|---:|---:|
| Annualized arithmetic gross P&L proxy | +5.73% | +16.27% |
| Annualized arithmetic net P&L proxy | **−3.85%** | +16.06% |
| Gross / net Sharpe | 0.50 / **−0.33** | 1.29 / 1.28 |
| Annualized cost | 9.58% | 0.21% |
| Average daily turnover | 0.380 | 0.0082 |
| Net compound maximum drawdown | −17.17% | −8.48% |
| Annualized long / short P&L contribution | +17.29% / −11.56% | +13.42% / +2.85% |

The paired annualized differences were −10.54 percentage points gross and −19.91 points net; NCMOM20's annualized cost was 9.37 points higher and average daily turnover 0.372 higher.

## Checks and limits

- Return-feature prefix invariance at 2025-06-30: **PASS**.
- Mutating customer returns after the cutoff did not change earlier NCMOM20: **PASS**.
- Mutating the signal-date customer return did not change that date's NCMOM20: **PASS**.
- Deterministic feature rebuild: **PASS**.
- Relationship mutation/PIT check: **not applicable by design**. The 2026 graph is projected backward; relationship publication causality and historical persistence were not tested.
- No reverse-direction diagnostic was run in this focused 2025 backtest; customer-to-supplier was fixed before results.
- Two initial executions stopped on Pandas index/column ambiguity before producing metrics. They were corrected without changing the research rules; the final bounded run exited successfully. A later same-spec reproduction completed conditional RankIC for groups with at least three names and used valid days as the hit-ratio denominator.
- One year only; no model fit, candidate, official evaluator, release, or strategy change. With 2.22% coverage, this cannot establish full-universe competition performance.

## Artifacts

- [Archive plan](../../experiments/DM-20261002-03/plan.md), [source config copy](../../experiments/DM-20261002-03/source_config.json), and [reconstructed source plan](../../experiments/DM-20261002-03/source_plan.md)
- [Original execution lock](../../experiments/DM-20261002-03/source_pre_result_lock.json) and [same-spec reproduction lock](../../experiments/DM-20261002-03/reproduction_lock.json)
- [Input manifest](input_manifest.json)
- [Code mapping audit](code_mapping_audit.csv), [daily diagnostics](ncmom20_daily.csv), [yearly metrics](ncmom20_yearly.csv), [SN1-conditional results](ncmom20_conditional_sn1.csv)
- [Matched baseline comparison](ncmom20_vs_sn1_matched.csv), [summary metrics](ncmom20_diagnostics.csv), [prefix-invariance record](network_prefix_invariance.json)
- [Mapped edges](../../artifacts/DM-20261002-03/static_graph_2025/selected_edges.csv), [NCMOM20 values](../../artifacts/DM-20261002-03/static_graph_2025/ncmom20_2025.parquet), [run summary](../../artifacts/DM-20261002-03/static_graph_2025/run_summary.json)
- [Diagnostic implementation](../../research/experiments/dm_network_momentum/static_graph_2025.py)
