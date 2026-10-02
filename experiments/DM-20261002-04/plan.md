# DM-20261002-04: fixed current graph NCMOM20 descriptive backtest

## Hypothesis

Holding the current directed `major_customer` graph fixed over 2024, the equal-weight mean of each major customer's prior 20 observed market-residual returns may rank supplier H1 residual returns in a way that adds information to the unchanged `SN1_H1` score.

## Why it may work / why it may persist

Customer demand and earnings information may reach the customer's price before it is reflected in the supplier. This run uses only customer residual returns strictly before the supplier signal date. The user explicitly requests the assumption that customer/business links persist for a few years; that assumption is imposed for 2024 and is not independently validated by this current snapshot.

## Why it should survive t+1 open

For signal date `t`, each customer contribution is the sum of its last 20 observed residual returns with dates `< t`. The supplier target remains the competition H1 target, `Open[t+1] -> Open[t+2]` relative return. No signal-date or later customer return is used.

## Fixed relation and feature contract

- Source: `JP_Market_Vis` M5/M4 snapshot version `2026.09`, generated `2026-09-22`.
- Keep only `major_customer`, `status=confirmed`, and listed supplier → listed customer edges. Do not include other relation types, review-status edges, reverse propagation, or multi-hop links in NCMOM20.
- Map each four-character M4 securities code to the competition code by appending the J-Quants trailing `0`; verify mapping against the 2024 price panel and report misses/collisions.
- Freeze the mapped current edge list over all signal dates `2024-01-04` through `2024-12-30`. The current graph is not PIT for 2024; the fixed-graph persistence premise is a user-directed sensitivity assumption.
- `resid[j,d] = raw_return[j,d] - beta[j,d] * TOPIX[d]`.
- `NCMOM20[i,t] = mean_j(sum of the last 20 observed residual returns for customer j with dates strictly before t)`. Equal weight. A code's rolling history resets after a gap over 20 exchange-date positions, consistent with the existing SN1 listing-segment rule. Require all 20 residuals to be finite for a customer's contribution. Average only customers with a complete observable window; if none are available, leave NCMOM20 missing.
- Missing NCMOM20 is not imputed to zero in its quintile/rankIC diagnostics. The official NCMOM account is restricted to the covered supplier rows. Its SN1 comparator uses the exact same date-by-date covered supplier rows and official five-quantile/weight/cost rule. Also report the full-universe official SN1_H1 account.

## Baseline, scope, and fixed budget

- Baseline: the current `SN1_H1` source after the split-safe ATR correction, regenerated with current code and the existing fixed H1 specification. Model fitting reads Train features and Train labels only; Valid targets are not used for fitting.
- Evaluation target: `target_1day_valid.parquet`, filtered at read time to `2024-01-04 <= Date <= 2024-12-30` only.
- Feature prices: Train history plus Valid market inputs through `2024-12-30` only. No post-period Valid price inputs or raw-target files are read.
- One fixed descriptive backtest, one horizon (20 observed customer returns), one relation type, no candidate model fit, no threshold/weight/horizon search, no strategy change.
- Main comparison: official NCMOM20-only eligible-universe account against the SN1_H1 account on the same NCMOM20-covered suppliers. The full-universe SN1_H1 result is a reference, not a matched comparison.
- Also report NCMOM20 RankIC/HAC-5/hit ratio, feature quintile Q1-Q5 returns and spread, own-RS60 and SN1 score correlations, conditional NCMOM20 RankIC within SN1 and own-RS60 quintiles, and the reverse supplier→customer direction as a sanity check only.

## Accounting and decision policy

Use official `compute_weight`: daily `rank(method="first")`, five `qcut` buckets, weight `(quintile-2)/N/1.2`, and 10 bp one-way cost on absolute weight changes. Report daily Sharpe, annualized P/L and cost (252 sessions), period cumulative P/L, turnover, compounded maximum drawdown, Q1-Q5 monotonicity, and long/short P/L. The NCMOM feature account is a descriptive network-only portfolio, not a combined SN1 candidate.

This one-year already-open Valid slice is descriptive development evidence, not an independent holdout. No result on this period may be treated as PIT-valid, OOS, a model-selection gate, or a submission-usable claim. No combined-model candidate is fit in this experiment.
