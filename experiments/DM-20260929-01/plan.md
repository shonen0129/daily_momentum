# DM-20260929-01: split-adjusted ATR correction regression

Status: completed after the bounded implementation-correction replay. This was not a model search or candidate-selection exercise.

## Hypothesis

In `split_safe_prices`, all historical OHLC values are converted into the same share unit. Dividing the previous close by the current day's `AdjustmentFactor` again therefore creates a false split-day gap. Using the already-normalized previous close should make economically equivalent split and non-split price histories produce identical box/ATR features.

## Why it should work / Why it may persist

Adjustment factors are observed corporate-action inputs, and the fix removes a duplicate conversion. The corrected price-unit relation is an accounting identity, so it should hold across split ratios and dates rather than depending on a fitted parameter.

## Why it should survive t+1 open

This is a feature-construction correction, not an intraday predictive effect. All inputs remain available by signal date `t`; the Train replay evaluates the existing annual expanding model for the official `t+1 Open` to `t+2 Open` target.

## Expected turnover impact / Leakage risk / Complexity cost

Turnover may change only where the ATR-dependent box width and resulting score change. No new input or fitted degree of freedom is added. The main risk is a mismatch between adjusted share units around corporate actions; target leakage risk is unchanged. Compute cost is unchanged.

## Baseline and fixed replay

Baseline is the immutable pre-fix `features.py` from `releases/DM-20260927-SN1-v1/snapshot/strategy/features.py`. Compare it with the corrected working feature builder, using the same fixed high/low Ridge models (`lambda=1`), annual expanding folds 2011–2016, and the same score smoothing. Do not tune, select, or change model parameters.

## Train-only scope and finite budget

Use only `*_train.parquet` and `target_1day_train.parquet`, dated 2008-11-04 through 2016-03-31. Replay annual folds 2011–2016; each fold excludes labels that have not matured before January 1, with the existing two-trading-day purge. There is exactly one old/new implementation comparison (`max_trials=1`). All periods are already known Train data and serve only as descriptive bug-fix verification, not as a holdout or selection basis.

## Verification and command

Run split-representation and future-mutation/truncation tests, source/runtime firewall checks, index/finite-coverage/determinism checks, then the bounded old/new Train replay. Valid files and labels are prohibited.

```sh
make test
.venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python research/experiments/variable_box_atr_regression.py --config experiments/DM-20260929-01/config.json --output artifacts/DM-20260929-01/<prepared-run>
```
