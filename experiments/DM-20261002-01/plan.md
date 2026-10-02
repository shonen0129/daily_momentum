# DM-20261002-01: PIT feasibility audit for Customer Momentum vs SN1_H1

Status: completed at Phase 1 gate. No signal feature, model candidate, or portfolio candidate was evaluated.

## Hypothesis

Historically disclosed major-customer returns may carry information from customer to supplier that is incremental to the fixed SN1_H1 score. Test only the feasibility of constructing the directed `major_customer` relation as it was public at each Train signal date before considering NCMOM20.

## Why it should work / Why it may persist

Customer business conditions can be reflected first in customer prices and later in suppliers through slower information diffusion. A major-customer relationship may be economically persistent, but its observed public disclosure can be much later than its economic start and the relationship can change. Therefore only publication-time evidence can establish availability; an economic period-end date cannot.

## Why it should survive t+1 open

The proposed, unrun NCMOM20 would use customer residual returns from `t-20` through `t-1` to forecast the supplier's fixed `Open[t+1] -> Open[t+2]` relative return. Excluding day `t` leaves one full signal-day lag before entry. No return feature was computed in this feasibility audit.

## Expected turnover impact / Leakage risk / Complexity cost

Equal-weight customer momentum could add ranking changes and turnover to SN1_H1; the direction and size are unknown. Relationship publication look-ahead, stale edges, issuer/customer code mismatch, delisted or out-of-basket counterparties, and missing customer prices are the central risks. An event-sourced historical disclosure table and joins would add data, code, and package size. No feature or portfolio implementation was made.

## Baseline and scope

Baseline is the fixed `SN1_H1` described in the request. Existing model, features, annual fits, purge, EWMA, source precedence, quintiles, weights, costs, submission code, and evaluation contracts were not modified. This experiment covers Phase 0 competition-use audit and Phase 1 source/PIT feasibility only. It has one fixed audit trial and zero candidate fits. If Phase 1 does not pass, Phase 2/3 are not run.

## Train-only period and decision rule

Audit period: Train signal dates in 2011–2016; 2011–2015 complete, 2016 partial through 2016-03-31. The baseline evaluation index was read from saved `SN1_H1_train.parquet` using only `Date` and `Code` columns for denominators. No target values, raw-target files, Valid input parquet, or Valid target were read. This Train history is known development history, not independent OOS.

Phase 1 passes only if at least one directed listed-to-listed major-customer edge is shown to have been available by a Train date from archived primary evidence, with a reproducible publication timestamp, PIT-safe endpoint mapping, price coverage, and a defensible successor-disclosure rule. If those checks are unavailable, label `PIT INSUFFICIENT` and stop before NCMOM diagnostics or candidate fitting. No relationship availability is inferred from current membership.

## Validation and command

This fixed desk audit used the competition materials, public source documentation, and the saved Train baseline index. It did not build a feature or prediction route, so feature source scans, data firewall execution, edge/return mutation, feature prefix-invariance, prediction determinism, smoke/backtest, and portfolio reconciliation were not applicable or not run. Phase 1 evidence and limitations are in `reports/DM-20261002-01/`. No bounded Train model run was prepared because the feasibility gate failed.
