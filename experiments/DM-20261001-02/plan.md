# DM-20261001-02: SN1_H1 prior-only VOL20 confidence diagnostic

Status: planned. Phase 1 is descriptive only; no strategy candidate is created.

## Hypothesis and scope

The fixed `SN1_H1` ranking signal may be less informative for stocks with high idiosyncratic volatility. The only question is whether H1 RankIC and score-ranked Q5−Q1 spread deteriorate from volatility quintile V1 to V5, and whether high-volatility names account for disproportionate existing Short losses or near-zero-score ranking error. VOL20 is a confidence/noise descriptor, not alpha.

Trading strategy change: **None**. Do not alter score, official quintile membership, portfolio weights, or costs. Do not create a volatility filter, `score / vol`, or score shrinkage. Do not fit a candidate. Phase 2, if warranted, requires a different experiment ID.

## Why this may persist; limitations

Idiosyncratic noise can make small cross-sectional score differences less reliable. A rolling estimate available before signal date `t` may describe that noise level at `t`; high volatility also means larger realized target variance, so a lower RankIC/spread is not guaranteed. Any descriptive association may reflect size, beta, source, or market state and will not establish causality or justify a strategy change. Intraday noise measured through `t-1` is already observable before `t`; the diagnostic makes no claim that it is alpha surviving `t+1` Open.

## Frozen definition and missing data

For each stock and signal date, use the existing PIT-safe Train `raw_return_1day`, `beta_1day`, and `topix_return_1day` definitions:

`resid[i,t] = raw_return[i,t] - beta[i,t] * TOPIX[t]`

`VOL20[i,t] = sample_std(resid[i,t-20:t-1], ddof=1)`

Apply the existing listing-segment reset rule (`features.segment_keys`), a one-observation prior shift, and exactly 20 finite residual observations (`min_periods=20`). No imputation: insufficient/missing history yields missing VOL20 and is excluded from V1–V5; missing-vol official portfolio attribution is reported separately so attribution still reconciles. Cross-sectional volatility ranks use only available VOL20 values on each date; quintile assignment is fixed before evaluation. No alternate window, volatility definition, or threshold is allowed.

## Baseline and evaluation

Baseline is the current post-ATR-correction `SN1_H1` route and its official Train H1 target (`target_1day_train.parquet`). Reproduce the current baseline through the submission route and the independent walk-forward route, and match the saved current and `DM-20260930-02` references bit for bit before computing diagnostics. Reuse the fixed annual expanding 2011–2016 SN1_H1 scores; 2016 is partial. The two-position H1 maturity purge belongs to the existing baseline score generation and is unchanged.

Primary tables report pooled and year/fold V1–V5 RankIC, HAC-5 t-stat, hit ratio, score-ranked within-volatility Q1–Q5 means and Q5−Q1, centered target rank, target mean/dispersion, and score stability. Separate tables attribute unchanged official Long/Short membership, weight, gross/net contribution, turnover, and cost to side × volatility. Score magnitude uses the fixed `abs(score) < 1e-12` split. Boundary sensitivity reuses exactly the existing deterministic `1e-12 × daily score SD` BLAKE2b Code perturbation (key `SN1-20260928`); its size/order is not tuned.

## Predeclared interpretation and budget

Exactly one diagnostic run (`max_trials=1`); candidate strategy fits: zero. Report **SUPPORT** only when both pooled V1>V5 RankIC and Q5−Q1 hold, both relations hold in at least three of five complete years (2011–2015), and either V5 Short gross contribution is more negative than V1 or near-zero-score RankIC is lower in V5 than V1. Report **MIXED** when pooled primary measures are directionally mixed or aligned but yearly/corroborating evidence fails that rule. Report **NOT SUPPORTED** when neither pooled primary measure has the predicted direction. These are descriptive labels, not statistical acceptance thresholds; show all values and years.

No window search, threshold search, subgroup interaction candidate, regression neutralization, parameter selection, or Phase 2 implementation. Observed Train dates are development history, not independent OOS. Valid and raw-target inputs must remain unopened.

## Expected impact, risks, and verification

No direct turnover or strategy impact because official scores and holdings remain fixed. Diagnostic complexity is one rolling residual-volatility series and fixed subgroup summaries. Main leakage risks are same-day residual inclusion, beta/TOPIX date misalignment, rolling state across long listing gaps, and future input dependence. Use the current PIT beta/TOPIX contract, align by date and `(Date, Code)`, shift before rolling, audit source firewall/leak scan, and future-mutate every staged Train source at three cutoffs; require exact prefix equality for VOL20, baseline feature values, and baseline score. Verify index/coverage, deterministic VOL20 replay, official daily-account parity, and complete side/vol attribution reconciliation.

## Train inputs, command, and outputs

Use only the five exact Train files staged from the latest current baseline run: `raw_return_1day_train.parquet`, `beta_1day_train.parquet`, `topix_return_1day_train.parquet`, `prices_daily_quotes_train.parquet`, and `target_1day_train.parquet`. The latter supplies only the official H1 target. Do not open Valid or raw-target files.

Run with a 1,800-second bound:

`.venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.sn1_volatility_diagnostic --data-dir artifacts/DM-20261001-02/<run_id>/input_train --output-dir artifacts/DM-20261001-02/<run_id> --run-json artifacts/DM-20261001-02/<run_id>/run.json`

Save plan/config/run snapshots, baseline reproduction, VOL20 definition audit, source scan, firewall and prefix-invariance audits, pooled/year V1–V5 metrics, official side × volatility attribution, near-zero × volatility results, boundary sensitivity, unchanged baseline predictions/account, and `reports/DM-20261001-02/REPORT.md`.
