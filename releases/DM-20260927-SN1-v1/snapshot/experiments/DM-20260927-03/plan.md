# DM-20260927-03 — Short × Night root-cause audit

This is a fixed, known-Train structural audit and two-intervention falsification run. The intervention registry is [frozen here](../../reports/DM-20260927-03/SHORT_NIGHT_INTERVENTION_PLAN.md); its SHA-256 is in `config.json`. No candidate P/L is inspected until that plan is saved.

## Scope

- Primary baseline: `D_LOW_FAST_ONLY`; context baseline: `BOX_ORIGINAL`; B00 diagnostic/control only.
- Train only. Evaluation dates 2011-01-04–2016-03-29, ex-2016 pooled, 2011–2015, and 2016 partial. Preserve two-date annual purge.
- Reuse existing saved BOX signals, D score/weights, source attribution, official quintile, accounting, day/night decomposition, and paired circular bootstrap.
- No new feature builder, alpha/holding/threshold/lambda search, model fitting, or session-specific trading.
- Candidate transformations: exactly `SIDE_SOURCE_SEPARATION` and `HIGH_AGE5_SHORT_VETO`.
- Cost: 10 bps one-way; 252 annualization; bootstrap seed 20260925, block 20 days, 1,000 reps.
- Valid, Freeze, submission evaluation, `target_1day_valid`, and all raw targets are prohibited.

## Selection and rejection

There is no adoption based on this known Train. Reject any candidate that fails the user's regulation, Short × Night / Short × Day, total Net, cost, year-stability, tie, or exposure-drift conditions. No post-result candidate is allowed. Source-age P/L attribution is descriptive bookkeeping, not causal proof.
