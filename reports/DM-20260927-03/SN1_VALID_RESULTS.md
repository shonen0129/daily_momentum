# SN1 Valid Results — Single Frozen Run

## Executive result

**MIXED（事前登録判定）**。SN1はValid全体でDをNet年率・Net SRとも上回り、GrossとLong側も改善しました。一方、Short側は悪化し、2026 partialではSN1がDを大きく下回りました。事前登録したpaired-bootstrap区間はrunnerの後段チェック不具合で保存されず、PASS条件を確認できません。

- SN1 − D: Net年率 **+0.867 pp**、Net SR **+0.164**。Gross年率 **+0.373 pp**、年率Cost **−0.494 pp**。
- Long Net年率 **+1.084 pp** / Long Net SR **+0.240**。Short Net年率は **−0.216 pp** 悪化。SN1はShort alpha改善やShort × Night修復ではありません。
- calendar-year bucketは **7/11** でSN1のNet年率差がプラス。ただし2026 partialは **−9.144 pp**。

対象コード・targetは再読せず、保存済みoverall/yearly CSVから差分表を生成しています。Valid予測・P/L評価は1回だけです。

## Freeze verification

- Freeze source commit: `09920d4221594b961a5793be02baab9214382f4e`; run HEAD: `09920d4221594b961a5793be02baab9214382f4e`.
- Manifest SHA-256: `a252dab98382694d6bb580fa0e1bfea965f0c22df077dbf45ec9b8fba2dc5a00`.
- Evaluation plan SHA-256: `680b0a2b7c0b6e8de089cfeee530ffa3b155bd27705152b167943affce67da9d`; config SHA-256: `5efd7a38137edc7773fef9ee0507bfe848d40845693f26f667a7cfcd592356ac`.
- Submission zip SHA-256: `945ba58e9011ed7a285b0b47ad29cfed69533868502bb3d96fe4a16f254617b6`; source code hashes: `run.json` / `valid_evaluation_lock.json`.
- Candidate IDs in the run: `D_LOW_FAST_ONLY`, `SIDE_SOURCE_SEPARATION` only. Cost 10 bps one way; no strategy branch or parameter was changed.
- Valid target read count: `1`; rows: `1227148`; raw target accessed: `False`.
- Run file status is `failed_after_single_use_lock` because the runner stopped after metric CSV persistence at the paired-account NaN guard. No retry was run.

## Overall metrics

Annual return, annualized volatility and cost are shown as percent. Sharpe uses the preregistered research `ddof=1` definition; official evaluator `ddof=0` SR is also recorded and agrees to displayed precision.

| Metric | D | SN1 | SN1 − D |
|---|---:|---:|---:|
| Gross annual return | 0.110% | 0.483% | 0.373% |
| Net annual return | -0.623% | 0.244% | 0.867% |
| Gross SR | 0.020 | 0.102 | +0.082 |
| Net SR | -0.112 | 0.052 | +0.164 |
| Gross volatility | 5.552% | 4.728% | -0.825% |
| Net volatility | 5.550% | 4.727% | -0.823% |
| Turnover/day | 0.02912 | 0.00951 | -0.01962 |
| Annual transaction cost | 0.733% | 0.238% | -0.494% |
| Additive max drawdown | -15.490% | -11.296% | 4.195% |
| RankIC | 0.00536 | 0.00603 | +0.00067 |
| Mean net exposure | -0.000616 | -0.000616 | +0.000000 |

### Gross / cost decomposition

`ΔNet = ΔGross − ΔCost`: `+0.373 pp − (−0.494 pp) = +0.867 pp`. Turnover fell 67.4%; mean gross/net exposure is effectively unchanged. The Valid point estimates therefore show both Gross improvement and lower cost, alongside lower volatility.

## Long / Short

| Sleeve | D Gross | SN1 Gross | D Net | SN1 Net | D Net SR | SN1 Net SR |
|---|---:|---:|---:|---:|---:|---:|
| Long | 1.460% | 2.139% | 0.986% | 2.069% | 0.194 | 0.434 |
| Short | -1.350% | -1.657% | -1.609% | -1.825% | -0.304 | -0.351 |

Long–Short Net correlation: D `-0.428`, SN1 `-0.553`. Short remains Net-negative and is worse in SN1.

## Calendar-year stability

Calendar-year partitions were fixed before Valid; endpoints are partial periods. Net return is annualized within each bucket; ΔSR uses the same research definition.

| Period | D Net | SN1 Net | Δ Net | D Net SR | SN1 Net SR | Δ Net SR | D turnover | SN1 turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2016 partial | -9.287% | -8.617% | 0.670% | -1.397 | -1.324 | +0.073 | 0.0243 | 0.0171 |
| 2017 | 1.852% | 6.666% | 4.814% | 0.616 | 2.963 | +2.348 | 0.0413 | 0.0014 |
| 2018 | -1.544% | -2.567% | -1.024% | -0.400 | -0.744 | -0.344 | 0.0300 | 0.0196 |
| 2019 | -1.161% | 0.022% | 1.183% | -0.290 | 0.006 | +0.295 | 0.0192 | 0.0105 |
| 2020 | 10.230% | 9.456% | -0.775% | 1.070 | 1.030 | -0.040 | 0.0260 | 0.0164 |
| 2021 | -7.796% | -2.957% | 4.838% | -1.736 | -0.594 | +1.142 | 0.0260 | 0.0060 |
| 2022 | -4.917% | -4.418% | 0.499% | -1.201 | -1.230 | -0.030 | 0.0190 | 0.0132 |
| 2023 | -0.750% | 3.754% | 4.504% | -0.210 | 1.181 | +1.391 | 0.0368 | 0.0031 |
| 2024 | 3.956% | 4.675% | 0.719% | 0.961 | 1.328 | +0.367 | 0.0285 | 0.0066 |
| 2025 | 1.476% | 0.352% | -1.124% | 0.319 | 0.095 | -0.225 | 0.0307 | 0.0056 |
| 2026 partial | -1.219% | -10.363% | -9.144% | -0.113 | -2.691 | -2.578 | 0.0426 | 0.0055 |

SN1のNet年率差は11 bucket中7つでプラスです。2025と2026 partialはマイナスで、特に2026 partialの悪化が大きく、期間安定性はMixedです。

## Score / regulation

Valid scoreだけから事前に保存された監査。zero/tie/uniqueにはrepository内の数値minimum ruleがないため、値を報告し、恣意的な足切りは加えていません。

| Check | D | SN1 |
|---|---:|---:|
| Rows / dates | 1,227,148 / 2,523 | 1,227,148 / 2,523 |
| Finite / unique index | 100.0% / True | 100.0% / True |
| Exact zero rate | 0.993% | 0.993% |
| Duplicate-score row rate | 0.977% | 1.024% |
| Boundary-crossing tie row rate | 0.044% | 0.147% |
| Mean / min daily unique ratio | 99.204% / 97.484% | 99.172% / 92.308% |
| Five populated quintiles / max bucket size spread | True / 1 | True / 1 |
| Mean gross / net exposure | 1.001551 / -0.000616 | 1.001551 / -0.000616 |

Exact target/score index coverage, finite weights, official quintiles, official `compute_weight`/`compute_pl` behavior, and research-vs-official Net account reconciliation passed before the final reporting guard. Two signal dates had no valid labels (2,521/2,523 label days), which naturally yields missing daily RankIC.

## Train → Valid

- **Train observed before Valid:** SN1 Net SR ≈ 1.063 vs D ≈ 0.808; annual Net return ≈ 4.517% vs 3.716%; turnover/day ≈ 0.0077 vs 0.03252. Train contribution was Long-centered; Short was not improved.
- **Valid saved point estimates:** SN1 has higher Gross/Net return and SR, lower volatility, turnover and cost than D; Long Net improved; Short Net worsened and remains negative.
- **Reproduced:** lower turnover/cost and stronger Long contribution are present in the saved Valid point metrics.
- **Not reproduced / unresolved:** Short improvement is absent; 2026 partial underperforms D materially; no paired bootstrap CI is available.
- Day/Night was not used to build, branch, or trade either candidate. SN1 remains no Short × Night repair claim.

## Bootstrap and execution limitation

Preregistered paired circular block bootstrap (20 dates, 1,000 reps, seed 20260925) was **not completed**. The runner saved `overall_metrics.csv` and `annual_metrics.csv`, then checked `candidate.isna().any().any()` across every daily-account column. The two no-label dates have expected missing RankIC, so that whole-frame check raised `Paired daily accounts are not aligned` even though the official and research Net returns had already reconciled. Daily account series were not persisted before the error. Reopening the target to recreate the bootstrap would violate the one-read rule; no retry was performed.

## Decision

**MIXED.** The point estimates meet the preregistered full-period relative direction and show Gross plus Long-side support, but the required uncertainty interval is unavailable and the 2026 partial year is adverse. The evaluation did not meet the preregistered PASS criteria; the failed runner guard is documented rather than treated as a candidate score failure.

**Next action:** stop Valid analysis here; keep the release frozen and report SN1 as Mixed, with no tuning or second target read.

### Saved artifacts

- Run record: `artifacts/DM-20260927-03/valid-once-sn1-vs-d/run.json`.
- Score audit: `artifacts/DM-20260927-03/valid-once-sn1-vs-d/audit/score_regulation.csv`.
- Overall / annual metrics: `artifacts/DM-20260927-03/valid-once-sn1-vs-d/metrics/overall_metrics.csv`, `annual_metrics.csv`.
- Derived comparison tables: `overall_deltas.csv`, `annual_net_return_deltas.csv`.
- Bootstrap state: `paired_bootstrap_status.json` (intervals unavailable; no bootstrap result is claimed).
