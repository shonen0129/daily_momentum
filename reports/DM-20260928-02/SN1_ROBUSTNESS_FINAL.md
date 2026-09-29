# SN1_H1 Robustness Final

Train and already-viewed historical Valid are development data. Historical Valid is not an untouched holdout. No candidate P/L was evaluated, no Valid retuning was performed, and no paper or raw-target file was read.

## Phase 0: reproducibility and no-regression

Git HEAD was `09920d4221594b961a5793be02baab9214382f4e`. The worktree was already dirty at the start; 96 status paths were recorded in the run snapshot. Existing unrelated edits were left untouched. The full saved H1 score stream was independently reconstructed while preserving pre-2011 EWMA warm-up.

| Split | Saved/rebuilt rows | Daily account dates | Max score delta | Quintile / weight delta | Max daily Gross/Net/Cost/Turnover delta | Result |
|---|---:|---:|---:|---:|---:|---|
| Train | 809,636 | 1,275 | 2.22e−16 | 0 / 0 | <2.23e−16 | PASS |
| Historical Valid | 1,227,148 | 2,521 | 3.33e−16 | 0 / 0 | <2.23e−16 | PASS |

All five quintiles were reproduced. Row-shuffle plus Parquet roundtrip reproduced weights exactly. Account target coverage averaged 99.3437% Train and 99.7900% historical Valid. The exact saved account dates were used: Train 2011-01-04–2016-03-29; historical Valid 2016-04-01–2026-07-29.

The generic `prepare-run` command stopped because its default policy is Train-only. This user-authorized audit then used an explicit historical-Valid development allowlist; it did not read newly held-out Valid or paper inputs. Three earlier preflight attempts are preserved as failed runs; their mismatches came from filtered/cropped replay inputs or a driver error. The complete full-history replay passed before diagnostics began.

## Near-zero and ordering sensitivity

| Split | Exact zero share | `abs(score)<1e−12` share |
|---|---:|---:|
| Train | 8.76% | 75.86% |
| Historical Valid | 0.99% | 81.36% |

Official order is Date/Code ascending with `rank(method="first")`; it remains the submission rule. Ordering-only stresses change the following counts:

| Split | Stress | Changed quintile rows | Changed Long rows | Changed Short rows | Net / year | Net SR | Turnover / day |
|---|---|---:|---:|---:|---:|---:|---:|
| Train | Code descending | 212,954 | 202,770 | 197,764 | +4.668% | 1.118 | 0.754% |
| Train | BLAKE2b Code order | 204,223 | 126,710 | 115,344 | +4.606% | 1.101 | 0.754% |
| Train | Fixed-seed Code permutation | 196,094 | 117,070 | 105,946 | +4.500% | 1.072 | 0.758% |
| Train | `1e−12 × daily score SD` perturbation | 328,467 | 189,876 | 197,030 | +3.225% | 0.981 | 1.603% |
| Historical Valid | Code descending | 1,154 | 0 | 0 | +0.253% | 0.053 | 0.951% |
| Historical Valid | BLAKE2b Code order | 872 | 0 | 0 | +0.243% | 0.051 | 0.952% |
| Historical Valid | Fixed-seed Code permutation | 640 | 0 | 0 | +0.255% | 0.054 | 0.951% |
| Historical Valid | `1e−12 × daily score SD` perturbation | 751,723 | 443,542 | 402,836 | −1.164% | −0.353 | 1.693% |

The tiny perturbation changes many rows because most absolute scores are below `1e−12`. Historical-Valid baseline Net is already small; the perturbation flips it negative. These are robustness stresses only. No alternative ordering was selected.

## Fixed transaction-cost stress

| Split | One-way cost | Gross / year | Net / year | Net SR | Annual cost | Long Net / year | Short Net / year |
|---|---:|---:|---:|---:|---:|---:|---:|
| Train | 5 bps | +4.708% | +4.613% | 1.086 | 0.096% | +6.206% | −1.579% |
| Train | 10 bps | +4.708% | +4.517% | 1.063 | 0.191% | +6.181% | −1.635% |
| Train | 20 bps | +4.708% | +4.326% | 1.018 | 0.382% | +6.131% | −1.749% |
| Train | 30 bps | +4.708% | +4.135% | 0.973 | 0.573% | +6.082% | −1.862% |
| Historical Valid | 5 bps | +0.483% | +0.364% | 0.077 | 0.119% | +2.122% | −1.740% |
| Historical Valid | 10 bps | +0.483% | +0.245% | 0.052 | 0.239% | +2.103% | −1.822% |
| Historical Valid | 20 bps | +0.483% | +0.006% | 0.001 | 0.477% | +2.064% | −1.986% |
| Historical Valid | 30 bps | +0.483% | −0.233% | −0.049 | 0.716% | +2.026% | −2.150% |

Historical Valid SN1_H1's own net profitability is close to flat at 20 bps and negative at 30 bps. A relative cost advantage versus D cannot be stated: the fixed run contains no saved D score/weight artifact to reproduce exactly, so no D comparison was run.

## Leave-one-calendar-year-out

Every leave-one-year-out aggregate remains net-positive. Train Net SR ranges 0.905–1.325; historical-Valid Net SR ranges 0.048–0.207. Thus the aggregate sign does not rely on one year, although historical-Valid strength remains modest. 2016 Train and 2016/2026 historical Valid are partial account years; 2026 ends July 29.

Year-level results are in `leave_one_year_out.csv` and daily account replays. Historical-Valid annual side contributions vary materially; persistent Short net contribution changes sign across years. This does not establish stable forward performance.

## Reset, coverage, and boundaries

The 20-market-date reset rule matches the saved raw High/Low event stream on reset rows exactly. Train had no observed gap; historical Valid had one reset after a 1,243-position gap. No exact-20 or 2–20 missing-panel gap occurred, and the only reset Code had no subsequent event in the observed panel. The final P/L-blind sample includes 200 matured rows and all available event-transition, near-zero, and exact-zero cases; simultaneous High/Low, missing-row-near-event, and true post-reset event cases were absent. An earlier lock incorrectly labeled a split-start event as post-reset; its sample is preserved under `audit/diagnostics_attempts/attempt_002/pre_boundary_fix/`, and the corrected final lock contains no post-reset event label.

## Reproducibility files

- Baseline parity: `artifacts/DM-20260928-02/run-20260928T103320Z/audit/baseline_parity.json` and `baseline_parity_checks.csv`.
- Final diagnostic manifest: `artifacts/DM-20260928-02/run-20260928T103320Z/audit/final_diagnostics_manifest.json`.
- Beta exposure manifest: `artifacts/DM-20260928-02/run-20260928T103320Z/metrics/risk_beta_exposure_manifest.json`.
- Run snapshot: `artifacts/DM-20260928-02/run-20260928T103320Z/run.json`.
