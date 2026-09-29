# Fixed state intervention results

## Executive result

`SN1_LOW_STATE_EXPIRY_60D` is **REJECTED**. It lowers gross return, raises turnover and transaction cost, and lowers net return in both Train and already-open historical Valid. Short losses become smaller but remain negative; the more profitable Long contribution falls substantially. This does not support a state-age expiry or a paper challenger.

## Run and sample

- Baseline: saved fixed `SN1_H1`; candidate count: one.
- Train account: 1,275 days, 2011-01-04–2016-03-29.
- Historical-Valid account: 2,521 days, 2016-04-01–2026-07-29. This was already observed and is development data, not OOS.
- H1 residual-return target and official 10 bp one-way cost; no model refit, no paper data.
- Frozen plan SHA-256: `d8ce2b465b4ade283ff736f8dc7ea51667eaf397e1a57342c035d002db04db8e`.
- Candidate run: [intervention-results-v2](../../artifacts/DM-20260928-01/intervention-results-v2/); audit manifest SHA-256 is recorded by the run.

The baseline was replayed with the existing target-index alignment and full pre-evaluation account history. Compared with the saved baseline daily account, the maximum absolute differences in Gross, Net, Cost and Turnover were all **0.0** in both splits. The evaluation read guard allowed only the locked state table and existing H1 Train/Valid target artifacts. No raw-target or paper file was read.

## Overall performance

Returns, cost, volatility and drawdown are account-level annualized values. Long/Short numbers below are weighted account contributions, not sleeve-normalized returns.

| Split | Strategy | Gross ann. | Net ann. | Gross SR | Net SR | Gross vol. | Net vol. | Turnover/day | Cost ann. | Max DD | RankIC |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Train | SN1_H1 | 4.708% | 4.517% | 1.108 | 1.063 | 4.248% | 4.248% | 0.00765 | 0.191% | −6.27% | 0.01246 |
| Train | Expiry 60 | 4.575% | 3.720% | 1.014 | 0.824 | 4.512% | 4.517% | 0.03406 | 0.855% | −6.13% | 0.01146 |
| Historical Valid | SN1_H1 | 0.483% | 0.244% | 0.102 | 0.052 | 4.730% | 4.729% | 0.00951 | 0.239% | −11.30% | 0.00603 |
| Historical Valid | Expiry 60 | 0.197% | −0.582% | 0.036 | −0.107 | 5.449% | 5.447% | 0.03097 | 0.779% | −14.49% | 0.00517 |

## Gross, cost and selection decomposition

`ΔNet = ΔGross − ΔCost`, where positive `ΔCost` means the candidate paid more cost. The gross selection split counts a same-side shared-name weight change as “common names”; names entering/exiting or switching side are “membership/side”.

| Split | ΔGross ann. | ΔCost ann. | ΔNet ann. | ΔNet SR | Common-name ΔGross | Membership/side ΔGross | Turnover: H1 → expiry |
|---|---:|---:|---:|---:|---:|---:|---:|
| Train | −0.134 pt | +0.664 pt | −0.797 pt | −0.240 | −0.111 pt | −0.023 pt | 0.00765 → 0.03406 |
| Historical Valid | −0.286 pt | +0.541 pt | −0.827 pt | −0.159 | +0.002 pt | −0.288 pt | 0.00951 → 0.03097 |

Turnover rose 4.45× in Train and 3.26× in historical Valid. Neither gross selection nor lower cost offsets the turnover charge; gross itself also declines in both periods.

## Long and Short

| Split | Strategy | Long Gross | Long Net | Long Net SR | Short Gross | Short Net | Short Net SR | L/S Net correlation |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Train | SN1_H1 | +6.230% | +6.181% | 1.257 | −1.522% | −1.635% | −0.323 | −0.638 |
| Train | Expiry 60 | +5.795% | +5.262% | 1.007 | −1.220% | −1.407% | −0.289 | −0.601 |
| Historical Valid | SN1_H1 | +2.141% | +2.103% | 0.441 | −1.658% | −1.822% | −0.350 | −0.553 |
| Historical Valid | Expiry 60 | +1.511% | +1.072% | 0.211 | −1.314% | −1.534% | −0.293 | −0.442 |

The expiry rule makes the Short sleeve's loss smaller by about 0.23 pt in Train and 0.29 pt in historical Valid. It remains Net-negative in both. Long Net contribution falls by about 0.92 pt and 1.03 pt, respectively, and Long Net SR falls in both. Therefore the candidate does not establish a Short alpha improvement and fails the preregistered “Long Net must not decline” condition.

## Calendar-year stability

Values are candidate minus SN1_H1. Train 2016 is the existing Jan–Mar partial; historical-Valid 2016 is Apr–Dec partial and 2026 runs through July. No new subperiod was selected.

| Split / year | ΔGross ann. | ΔNet ann. | ΔTurnover/day | ΔRankIC |
|---|---:|---:|---:|---:|
| Train 2011 | +0.882 pt | +0.764 pt | +0.0047 | +0.0030 |
| Train 2012 | +1.674 pt | +1.381 pt | +0.0116 | +0.0033 |
| Train 2013 | −1.831 pt | −3.319 pt | +0.0591 | −0.0040 |
| Train 2014 | +0.519 pt | −0.025 pt | +0.0216 | −0.0006 |
| Train 2015 | −2.599 pt | −3.653 pt | +0.0419 | −0.0067 |
| Train 2016 partial | +2.573 pt | +2.620 pt | −0.0015 | −0.0017 |
| Historical Valid 2016 partial | −1.111 pt | −1.493 pt | +0.0152 | −0.0003 |
| Historical Valid 2017 | −4.027 pt | −5.041 pt | +0.0402 | −0.0072 |
| Historical Valid 2018 | +1.306 pt | +1.037 pt | +0.0106 | +0.0036 |
| Historical Valid 2019 | −0.357 pt | −0.700 pt | +0.0136 | +0.0003 |
| Historical Valid 2020 | +2.097 pt | +1.834 pt | +0.0105 | +0.0050 |
| Historical Valid 2021 | −3.994 pt | −4.510 pt | +0.0205 | −0.0065 |
| Historical Valid 2022 | −1.174 pt | −1.411 pt | +0.0094 | −0.0033 |
| Historical Valid 2023 | −3.461 pt | −4.326 pt | +0.0343 | −0.0053 |
| Historical Valid 2024 | +0.465 pt | −0.096 pt | +0.0223 | −0.0055 |
| Historical Valid 2025 | +1.298 pt | +0.621 pt | +0.0269 | +0.0043 |
| Historical Valid 2026 partial | +10.242 pt | +9.301 pt | +0.0374 | +0.0104 |

The large 2026 partial improvement does not offset widespread historical-Valid deterioration and is not a selection basis. Train also has large losses in 2013 and 2015.

## Holding and turnover mechanism

The return-blind saved-score profile shows the intended rule materially shortens membership spells, but still does not resolve the economics:

- Mean daily rank autocorrelation falls from 0.9965 to 0.9865 in Train and from 0.9955 to 0.9878 in historical Valid.
- Median Long spell falls from 140.5 to 35 sessions in Train and from 207.5 to 59 in historical Valid. Median Short spell falls from 152.5 to 60 and from 165 to 64.
- Long membership entrants rise from 0.41 to 2.45 per day in Train and 0.51 to 2.12 in historical Valid; same-side 5/20/60-session survival falls from 98.9/96.1/90.9% to 94.0/82.4/65.1% in Train.

Thus the candidate's lower persistence is a mechanical consequence of a broad ordering reset. It is not evidence that event-entry forecasts remain predictive for the new holding spells.

## Score and operational checks

| Split | Strategy | Finite | Exact zero | `abs(score)<1e-12` | Mean unique ratio | Boundary-tie rows | Five quintiles every date | Mean gross / net exposure |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Train | SN1_H1 | Yes | 8.76% | 75.86% | 91.21% | 6.42% | Yes | 1.00170 / −0.00058 |
| Train | Expiry 60 | Yes | 17.03% | 46.34% | 82.80% | 14.48% | Yes | 1.00170 / −0.00058 |
| Historical Valid | SN1_H1 | Yes | 0.99% | 81.36% | 99.17% | 0.147% | Yes | 1.00155 / −0.00062 |
| Historical Valid | Expiry 60 | Yes | 1.18% | 45.92% | 99.01% | 0.028% | Yes | 1.00155 / −0.00062 |

Official `rank(method="first")`, sorted `(Date, Code)`, and the five-quintile weights are unchanged. The candidate passes finite-score, coverage and five-populated-quintile checks. It materially worsens Train zero/duplicate/tie quality, while historical-Valid tie rows improve. The repository contains no formal minimum threshold for unique-score ratio or boundary-tie frequency; such a competition rule is not inferred here. All quality figures are disclosed. No new secondary tie-break was added.

## Uncertainty and final call

The existing circular paired block bootstrap (20 trading days, 1,000 repetitions, seed `20260908`) gives `ΔNet SR` 95% intervals of [−0.823, +0.337] in Train and [−0.537, +0.222] in historical Valid. The candidate's bootstrap-positive fractions are 19.9% and 20.7%. Both intervals include zero, with point estimates and annualized Net changes negative in both splits.

The candidate fails its preregistered criteria on Gross, Net, Long Net, cost and Train tie quality. It is rejected regardless of the historical partial-year positives. No variant or follow-up threshold was tested.

Detailed metrics are in [overall_metrics.csv](../../artifacts/DM-20260928-01/intervention-results-v2/metrics/overall_metrics.csv), [annual_metrics.csv](../../artifacts/DM-20260928-01/intervention-results-v2/metrics/annual_metrics.csv), [decomposition.csv](../../artifacts/DM-20260928-01/intervention-results-v2/metrics/decomposition.csv), [regulation_checks.csv](../../artifacts/DM-20260928-01/intervention-results-v2/metrics/regulation_checks.csv), and [persistence_profile.csv](../../artifacts/DM-20260928-01/intervention-results-v2/metrics/persistence_profile.csv). Candidate outputs and hashes are recorded in [audit_manifest.json](../../artifacts/DM-20260928-01/intervention-results-v2/audit_manifest.json).

## Reproducibility record

| Record | Value |
|---|---|
| Git HEAD | `09920d4221594b961a5793be02baab9214382f4e` |
| Worktree | Already dirty at task entry; 94 paths currently show changes/untracked files, including unrelated pre-existing work. No unrelated file was reverted and no commit was made. |
| Experiment config SHA-256 | `8fd12cc903bdd52a3c9cffe372c993fc008d732e9636c5a63d2a9fb1324b4d59` |
| Phase 1 lock SHA-256 | `e281307d3b66db7f3312eb9d01db7d20e2a96f849f99fc31913032598bdd8c4f` |
| Phase 1 state-table SHA-256 | `f23415b0544c866fe57de74e8a16c3b31cda7b260f90cd768614e4f070a809d6` |
| Phase 2 run | `run-20260927T161843Z`; manifest SHA-256 `d51767de5623467280f1bd6515198b90a987206236120c152c2d0393f0c608c0` |
| Phase 2 driver SHA-256 | `3076020c3d15fe80d7a8702e7ab29d3f46b6822f79dfbaecda896710691b50c8` |
| Intervention plan SHA-256 | `d8ce2b465b4ade283ff736f8dc7ea51667eaf397e1a57342c035d002db04db8e` |
| Final pre-metric execution lock SHA-256 | `80317cf1efbfe38e78c44a9f0d039413db0a9d01cf037b48d51da385a286df4b` |
| Candidate run directory | `artifacts/DM-20260928-01/intervention-results-v2/` |
| Candidate driver SHA-256 | `3ce40af46f9603d90a263c5b4130ec8acce9b3f9367e06836230bdb772a159c6` |
| Evaluation helper SHA-256 | `4da3e290f49e2061f2fdaf4efdb6e1ae5ecda5babc4dc9e9f6f77fc7ae891c4e` |
| Candidate audit manifest SHA-256 | `4acd91f5a23dd1ec7a3c0db60ffd982aed1e64cac4025f8f554e42f08a0e763a` |
| Consolidated reproducibility record SHA-256 | `218df8ff9f900f3dba14cb7b8584ec1a13b0fc8a29660843596f1f5cb4413537` |
| Entry/lag target hashes | H1 Train `ac6a75b73827902248f3f911d5886f99270e6dfe7d8a3e2e55aebc4ec3e5f4a9`; H1 historical Valid `f6a3b56886e15131c318022df97366cbf9f7b494bf98b3ab3b1dde988b9b7c48`; fixed H5 diagnostics are listed in the Phase 2 manifest. |
| Cost / resampling | One-way cost 0.001; existing circular paired block, 20 sessions, 1,000 repetitions, seed `20260908`. |

The P/L-blind profile code and output are separately hashed in `artifacts/DM-20260928-01/intervention-results-v2/audit/persistence_profile_manifest.json`. The consolidated record is [reproducibility_record.json](../../artifacts/DM-20260928-01/intervention-results-v2/audit/reproducibility_record.json). The fixed rule passed a row-wise prefix truncation and future-suffix mutation check before candidate scoring. No fitted model, raw target, or paper data was used.
