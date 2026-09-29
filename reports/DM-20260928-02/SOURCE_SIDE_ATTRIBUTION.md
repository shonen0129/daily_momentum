# Source × Side Attribution — SN1_H1

Train and already-viewed historical Valid are reported separately and treated as development data. Contributions are account-weighted daily P/L contributions annualized as daily mean ×252. Current-day source receives that day's turnover cost. Weight share is the share of absolute position weight-days. The table is descriptive attribution, not counterfactual sleeve performance.

## Source and side totals

| Split | Side | Selected source | Weight share | Gross contribution / year | Net contribution / year | Mean within-bucket H1 RankIC |
|---|---|---|---:|---:|---:|---:|
| Train | Long | High | 34.17% | +5.288% | +5.257% | +0.0017 |
| Train | Long | Low | 10.75% | +0.771% | +0.761% | +0.0167 |
| Train | Long | D fallback | 5.05% | +0.171% | +0.163% | n/a |
| Train | Short | Low | 48.25% | −1.465% | −1.574% | +0.0057 |
| Train | Short | D fallback | 1.78% | −0.057% | −0.061% | n/a |
| Historical Valid | Long | High | 14.58% | +0.863% | +0.859% | +0.0011 |
| Historical Valid | Long | Low | 33.80% | +1.063% | +1.029% | +0.0080 |
| Historical Valid | Long | D fallback | 1.59% | +0.215% | +0.214% | n/a |
| Historical Valid | Short | Low | 50.03% | −1.658% | −1.822% | +0.0023 |

The account-level annualized Long/Short Net contributions reconcile to +6.181%/−1.635% in Train and +2.103%/−1.822% in historical Valid. No High-source Short or historical-Valid D-fallback Short rows were present.

## Persistent sleeve × renewal

The following rows are the existing fixed `sleeve_age ≥20` bucket and existing 60-session side-matched renewal categories. Contributions are annualized account contributions.

| Split | Side / source | No recent same-side event | One event in 60 sessions | Recurrent: ≥2 in 60 sessions |
|---|---|---:|---:|---:|
| Train | Long / High | +1.610% | +0.720% | +2.827% |
| Train | Long / Low | +0.304% | +0.103% | +0.432% |
| Train | Short / Low | −1.275% | −0.041% | −0.263% |
| Historical Valid | Long / High | +0.281% | +0.051% | +0.527% |
| Historical Valid | Long / Low | +0.215% | +0.208% | +0.659% |
| Historical Valid | Short / Low | −0.461% | −0.133% | −0.963% |

Persistent Long contribution totals about +6.257% in Train and +2.155% in historical Valid. High accounts for about +5.156% Train but +0.859% Valid; Low accounts for +0.840% Train but +1.081% Valid. High-source renewal therefore explains a large part of Train Long profit, but it does not explain Long profit consistently across both periods. Long profit also appears in the fixed no-recent-event categories. Low-source Long contribution is positive in both periods, but its relative importance reverses against High.

Persistent Short losses occur both with no recent same-side event and with recurrent events. The negative historical-Valid contribution in the recurrent bucket rules out ancient state as the only explanation. The positive signed-score RankIC within Short buckets is small and does not offset the negative weighted Short P/L.

Across **all** sleeve ages, pooling the same fixed 60-observation recurrence bucket gives Short/Low Net contributions of −0.251% Train and −1.240% historical Valid, reproducing the prior audit. The table above restricts to the fixed `≥20` sleeve-age group, where the corresponding recurrent contributions are −0.263% and −0.963%. The difference is the sleeve-age filter, not a changed recurrence definition.

Across **all** sleeve ages, pooling the same fixed 60-observation recurrence bucket gives Short/Low Net contributions of −0.251% Train and −1.240% historical Valid, reproducing the prior audit. The table above restricts to the fixed `≥20` sleeve-age group, where the corresponding recurrent contributions are −0.263% and −0.963%. The difference is the sleeve-age filter, not a changed recurrence definition.

## Full fixed matrix and magnitude diagnostics

The machine-readable fixed matrix includes Side × source × 60-session renewal × `<20`/`≥20` sleeve age × event age, with stock-days, exposure, contribution, RankIC, Q5−Q1 spread, score percentile, absolute score, near-zero share, and event age. The descriptive absolute-score deciles use per-date ranks and do not define thresholds.

- `artifacts/DM-20260928-02/run-20260928T103320Z/metrics/source_side_attribution.csv`
- `artifacts/DM-20260928-02/run-20260928T103320Z/metrics/source_side_renewal_age_matrix.csv`
- `artifacts/DM-20260928-02/run-20260928T103320Z/metrics/source_side_absolute_score_decile.csv`
- `artifacts/DM-20260928-02/run-20260928T103320Z/metrics/source_side_by_year_train.csv`
- `artifacts/DM-20260928-02/run-20260928T103320Z/metrics/source_side_by_year_historical_valid.csv`

The large Low-source Long near-zero shares (Train 100%; historical Valid about 99%) reflect the signed Low-state and ranking rule: even tiny negative values can be relatively high within a cross-section. This is tie/rank sensitivity, not an absolute bullish Low signal.
