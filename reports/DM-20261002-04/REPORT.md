# DM-20261002-04: fixed current graph NCMOM20 backtest (2024)

## Decision

**2024 descriptive result: `MIXED`. No combined SN1_H1 + NCMOM20 candidate was fit or adopted.**

NCMOM20 had a small positive mean RankIC, but the H1 target spread was negative and non-monotone. On the same covered suppliers, NCMOM20's net Sharpe and net P/L were below unchanged SN1_H1, with much higher turnover and cost. Only 11 of 496 target suppliers had a complete customer-momentum value throughout this window, so this does not establish a robust incremental network signal.

This is the exact historical Valid slice requested by the user: 245 signal dates, 2024-01-04 through 2024-12-30, 121,087 stock-days. It is already-open development data, not an independent holdout or OOS result. The final Valid target was read only for those dates; 137 stock-days are missing H1 target labels and are handled by the official evaluator's missing-target rule. No raw-target input was read.

The user-requested persistence assumption was applied by holding the current [JP_Market_Vis](https://github.com/mattyamonaca/JP_Market_Vis) M5/M4 snapshot (`2026.09`, generated 2026-09-22) fixed throughout 2024. This is **not PIT evidence**: all 652 mapped confirmed listed-to-listed `major_customer` edges have an `as_of` value after 2024, and the M5 edge evidence has no `published` timestamp. Without the requested persistence assumption, this graph is not usable for this period or for a competition feature. The earlier 2011–2016 feasibility result remains [`PIT INSUFFICIENT`](../DM-20261002-01/REPORT.md).

## Coverage and graph mapping

The source defines `major_customer` as a directed disclosure from supplier to customer, primarily a customer representing at least 10% of consolidated sales. This run retained only `status=confirmed` listed-to-listed edges. M4 securities codes mapped to the competition code by adding the trailing `0`; all 652 edges mapped without a duplicate code collision. Among the 496 companies in the 2024 target panel, 14 had at least one mapped source edge and 493 appeared as a mapped customer. After requiring 20 complete prior customer-return observations, 11 suppliers remained, averaging 1.27 observable customers each.

| Coverage measure | Result |
|---|---:|
| Confirmed listed supplier → listed major-customer edges | 652 |
| Unmapped edges / M4 code collisions | 0 / 0 |
| 2024 target companies | 496 |
| Suppliers with a current-graph edge in the target panel | 14 (2.8%) |
| Suppliers with observable NCMOM20 | 11 (2.2%) |
| NCMOM20 covered stock-days | 2,695 / 121,087 (2.23%) |
| Edges with `as_of` after 2024 / published timestamp present | 652 / 0 |

The low supplier coverage is a major limit on both the RankIC diagnostics and any use as a full-universe signal. Missing NCMOM20 stayed missing. The NCMOM20 portfolio and its SN1_H1 comparator were both ranked only over the same covered suppliers; the full-universe SN1_H1 account is shown separately for context.

## Portfolio backtest

The table uses official five-quantile weights, 10 bp one-way transaction cost, and annualized P/L/cost at 252 sessions. Net Sharpe and P/L follow the official evaluator's treatment of missing H1 targets. Maximum drawdown is compounded. Q5−Q1 is the mean daily quintile return spread.

| Account | Covered suppliers | Mean RankIC (HAC-5 t) | Gross / Net Sharpe | Annual gross / net P/L | Annual cost | Daily turnover | Max DD | Q5−Q1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SN1_H1, full official universe | 496 | 0.01296 (1.59) | 1.382 / 1.305 | +4.86% / +4.59% | 0.27% | 0.01063 | −1.99% | +7.23 bp/day |
| SN1_H1, NCMOM20-matched universe | 11 | 0.00534 (0.28) | −0.715 / −0.738 | −8.31% / −8.57% | 0.26% | 0.01051 | −18.42% | −8.71 bp/day |
| NCMOM20 customer → supplier | 11 | 0.00963 (0.49) | −0.372 / −1.088 | −4.52% / −13.24% | 8.71% | 0.34570 | −14.63% | −2.54 bp/day |
| Reverse supplier → customer (sanity check only) | 13 | −0.01867 (−1.00) | −0.819 / −1.772 | −7.31% / −15.84% | 8.53% | 0.33857 | −19.43% | −1.96 bp/day |

On the matched universe, NCMOM20 exceeded SN1_H1 by 0.00429 in mean RankIC and 3.78 percentage points in annual gross P/L, but its annual net P/L was 4.66 points lower, net Sharpe was 0.35 lower, cost was 8.45 points higher, and daily turnover was 0.335 higher. Its quintile means were Q1 `+7.53`, Q2 `+2.76`, Q3 `−10.05`, Q4 `+3.54`, Q5 `+4.99` bp/day; the negative spread and −0.10 quintile monotonicity do not support the requested customer-to-supplier prediction claim. Long P/L was positive, but losses on the short sleeve and cost dominated.

The full-universe SN1_H1 reference must not be compared directly with the 11-supplier NCMOM20 portfolio as if they had identical coverage. The matched-universe comparison and all primary metric deltas are in [`incremental_vs_matched_sn1.csv`](metrics/incremental_vs_matched_sn1.csv).

## Incremental signal diagnostics

- Mean daily Spearman correlation was `+0.107` between NCMOM20 and own RS60, and `−0.047` between NCMOM20 and SN1_H1. This suggests the covered NCMOM20 values were not simply duplicating either score, but the 11-supplier sample is too small to establish useful independent information.
- Within SN1_H1 quintiles, conditional RankIC was estimable on 144 days in Q2 (`+0.082`, HAC-5 t `1.35`), 245 days in Q3 (`+0.009`, `0.24`), and 101 days in Q4 (`+0.032`, `0.44`). Q1 and Q5 had too few covered names per day for a conditional RankIC. There is no consistent conditional result.
- Within own-RS60 quintiles, average NCMOM20 RankIC was positive but small in all five buckets; HAC-5 t-statistics ranged from `0.10` to `1.30`. This single-year pattern is not selection evidence.
- The specified customer → supplier direction had positive, weak RankIC; reverse supplier → customer was negative. Neither direction produced a positive net account.

This one-year diagnostic does not pass the original multi-year Phase 2 gate: Q5−Q1 is negative, complete-year stability cannot be assessed from one year, and conditional evidence is sparse. It is recorded as `MIXED`; no rescue variant, composite weight, or NCMOM-augmented Ridge model was tried.

## Baseline and accounting verification

The `SN1_H1` baseline was regenerated with the current code after the split-safe ATR correction. Its model fit used Train features and Train H1 labels only. Valid market-feature inputs were staged only through 2024-12-30, and the baseline score index exactly covered the 121,087 requested target rows.

The full-universe SN1_H1 daily gross, net, cost, turnover, and official quintile assignments were replayed directly through `stock_comp_2026/evaluate_script.py`: **PASS**. The maximum daily gross/net/cost/turnover difference was below `1.0e-16`; quintile assignments changed on zero rows. The 137 missing target stock-days match the official behavior, which omits both that row's P/L and cost from daily net. The separate all-position cost is also retained in the metrics CSV.

Return-feature checks passed: deterministic NCMOM20 feature reconstruction produced identical values, and mutating 61,750 residual-return rows after 2024-06-28 left all 59,280 earlier feature rows unchanged (maximum difference `0`). This confirms return-side prefix invariance for the diagnostic calculation. Relationship publication causality and future-edge mutation are **not** claimed as passed: the fixed 2026 graph is the explicit retrospective assumption and has no publication timestamps.

## Artifacts

- Plan/configuration/decision: [`experiments/DM-20261002-04/`](../../experiments/DM-20261002-04/)
- Fixed research driver: [`ncmom20_current_graph_2024.py`](../../research/experiments/ncmom20_current_graph_2024.py)
- Main metrics: [`ncmom20_diagnostics.csv`](metrics/ncmom20_diagnostics.csv), [`ncmom20_yearly.csv`](metrics/ncmom20_yearly.csv), [`daily_account_2024.csv`](metrics/daily_account_2024.csv)
- Incremental comparison and conditional diagnostics: [`incremental_vs_matched_sn1.csv`](metrics/incremental_vs_matched_sn1.csv), [`ncmom20_conditional_sn1.csv`](metrics/ncmom20_conditional_sn1.csv), [`ncmom20_conditional_rs60.csv`](metrics/ncmom20_conditional_rs60.csv), [`direction_sanity_check.csv`](metrics/direction_sanity_check.csv)
- Coverage, mapping, and prefix checks: [`code_mapping_audit.csv`](metrics/code_mapping_audit.csv), [`network_coverage_daily.csv`](metrics/network_coverage_daily.csv), [`graph_and_coverage.json`](audit/graph_and_coverage.json), [`network_prefix_invariance.json`](audit/network_prefix_invariance.json)
- Reproducibility and official accounting: [`run_manifest.json`](audit/run_manifest.json), [`official_accounting_parity.json`](audit/official_accounting_parity.json)

The downloaded M5/M4 JSON files remained in a temporary directory and are not included in the repository. Their source, snapshot identifiers, and SHA-256 hashes are recorded in the run manifest. Upstream data redistribution rights were not cleared; this is local research only.

## Repository record note

During execution, a pre-existing `DM-20261002-02` archive for a 2025 diagnostic was discovered in the shared workspace. The first 2024 draft had been written under that occupied ID before the collision was noticed, so the final 2024 files were re-homed under `DM-20261002-04`. In the process, the prior `DM-20261002-02/REPORT.md` was overwritten and its `decision.md` removed. A workspace and temporary-file search found no exact-hash copy of either original file; their hashes in the older experiment record therefore no longer validate. The older numeric artifacts were not changed. No files under `DM-20261002-03` were changed.
