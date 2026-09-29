# Final Low Branch Audit — SN1_H1

## Result

**PASS: no Low-branch sign, target-alignment, execution-timing, EWMA-order, or P/L-sign defect was found.** The signal is directionally consistent end to end. A separate structural weakness remains: the source rule gives any strictly negative Low state precedence over High, including extremely small residual states; ranking those values can make relative ordering depend on deterministic ties.

The final selector hashed 200 trace rows before reading target values: 100 Train and 100 already-viewed historical-Valid rows. The lock records `target_values_read=false`, `pnl_calculated=false`, and `paper_data_accessed=false`. It includes the available consecutive Low, High→Low, Low→High, negative Low with positive High, near-zero negative Low, and exact-zero cases. A true first-event-after-reset case is unavailable: the only actual >20-position reset is 2025-09-29 for Code 87290, and no later High/Low event occurs for that Code in the saved historical-Valid panel. The original selector incorrectly labeled the first event in the split-start segment as post-reset; that sample/trace/manifest is preserved under `audit/diagnostics_attempts/attempt_002/pre_boundary_fix/`. No simultaneous High/Low event exists in the saved panel.

## Semantic chain

| Step | Fixed contract | Audit result |
|---|---|---|
| Signal / event / feature time | Event and five directional features use signal-date data; prediction is made after the signal-date close. | Reconstructed from saved H1 Ridge models and event features. No model was refit. |
| Ridge target | Cross-sectional centered H1 target rank; Low fitting uses its negative so a larger Low prediction means stronger bearish continuation. Training uses only labels mature before the prediction fold. | All 200 trace rows have the saved model's maximum label-maturity date on or before their signal date. |
| Raw event score | High uses the within-date prediction percentile. Low uses the negative of that percentile: more bearish Low predictions map to a more negative score. | Recreated event scores match the saved High/Low raw event stream exactly (maximum absolute difference 0). |
| EWMA | High α=0.25; Low α=0.50; `adjust=False`; update occurs on each observed row, with zero on no-event rows. | Prior and updated states follow the declared recurrence. No simultaneous raw High/Low event. |
| Source choice | Low state wins when `Low < 0`, even if High is positive; High is selected only when Low is exactly zero and High is positive; otherwise D fallback. | Trace examples match `sn1.py`. The precedence can preserve an old Low state after a new High event; this is the fixed design, not a sign inversion. |
| Cross-sectional selection | Sort by Date/Code and rank with `method="first"`; lower score quintiles receive negative weights and upper quintiles positive weights. | Saved score, all five quintiles, and weights match exactly in Phase 0. |
| Execution / label | Signal on date t; trade `Open(t+1) → Open(t+2)`; H1 target is raw asset return minus β×TOPIX over that interval. | Raw return / β / TOPIX reconstruction matches the saved H1 residual target exactly in both splits (max absolute delta 0). |
| Account contribution | `weight × H1 residual return − one-way cost`; negative weight times negative residual is positive gross P/L. | Sample row-level P/L signs match the account replay. |

## Representative locked trace rows

The rows below are from the P/L-blind locked sample. P/L was joined only after the sample hash was written. Values are decimals except quintiles and weights.

| Signal date / Code | Case | Ridge prediction → signed event score | Prior Low → updated Low; updated High | Selected source / Q / weight | H1 residual | Net account contribution |
|---|---|---:|---:|---|---:|---:|
| 2011-02-01 / 49110 | Consecutive Low | 0.00400 → −0.87500 | −0.31250 → −0.59375; 0 | Low / Q1 / −0.003805 | −3.0419% | +0.01158% |
| 2011-03-15 / 28710 | High→Low; Low<0 and High>0 | 0.07542 → −0.79459 | 0 → −0.39730; 0.00251 | Low / Q2 / −0.001898 | −2.4649% | +0.00411% |
| 2011-03-24 / 80880 | Low→High | 0.08538 → +1.00000 | −0.01537 → −0.00769; 0.25 | Low / Q1 / −0.003797 | −3.1155% | +0.01183% |
| 2011-05-13 / 28110 | Near-zero negative Low | no event | −1.19e−12 → −5.96e−13; 0 | Low / Q3 / 0 | +0.5125% | 0 |
| 2011-01-04 / 13320 | Exact-zero score | no event | 0 → 0; 0 | D fallback / Q1 / −0.003805 | −1.1466% | +0.00436% |

The High→Low and Low→High traces show that the sign mapping is consistent, while source precedence can keep a negative Low state in control over a positive High state. The exact-zero example also shows that a zero-score name can receive a short weight through the official first-rank tie rule. A Low-source name may appear in the Long book when its negative score is less negative than peers; this is relative-rank selection, not evidence that negative means bullish.

## Reset and missing-row behavior

The implementation resets a listing segment only when the next observed row is more than 20 market-date positions later. Missing rows have no score or EWMA update; the prior state carries until a row resumes, unless the gap exceeds 20. At exactly 20 positions the state carries.

| Split | State rows | Gaps 2–20 | Exactly 20 | Resets >20 | Largest gap | State equals first raw event after reset |
|---|---:|---:|---:|---:|---:|---|
| Train | 582,035 | 0 | 0 | 0 | 1 | n/a |
| Historical Valid | 1,227,148 | 0 | 0 | 1 | 1,243 | Yes; max High/Low difference 0 |

There were no observed 2–20-day missing-row cases or exact-20 boundary cases to exercise. The only long-gap reset was in historical Valid, on 2025-09-29 for Code 87290; that Code had no later event in the observed panel. IPO/delisting identity changes and corporate-action identity handling are not separately represented in this panel audit.

## Evidence files

- Locked trace: `artifacts/DM-20260928-02/run-20260928T103320Z/predictions/low_branch_trace.parquet` and `.csv`.
- Pre-read selection lock: `artifacts/DM-20260928-02/run-20260928T103320Z/audit/low_trace_sample_lock.json`.
- Event feature reconstruction: `artifacts/DM-20260928-02/run-20260928T103320Z/audit/low_trace_preparation/`.
- Reset summary: `artifacts/DM-20260928-02/run-20260928T103320Z/metrics/reset_missing_audit.csv`.
- Code: `research/experiments/sn1_low_branch_trace.py`, `research/experiments/sn1_final_diagnostics.py`, and `research/experiments/sn1_beta_exposure_audit.py`.
