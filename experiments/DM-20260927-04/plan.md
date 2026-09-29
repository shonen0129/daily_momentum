# DM-20260927-04: SN1 Ridge target horizon study

## Objective

Test whether the fixed SN1 signal architecture benefits from Ridge targets aligned with persistent portfolio membership. This is post-submission paper research. Train and the previously opened historical Valid period are development data. Historical Sharpe is descriptive and is not a selection threshold; future paper observations are the only final OOS.

## Fixed candidates

Exactly three Ridge label horizons are evaluated: H1, H5, and H20 trading days. No other horizon, parameter, feature, event, state, portfolio, or cost candidate is permitted. H1 is the reproduction control. If it does not reproduce the existing SN1 path, stop before evaluating H5/H20.

For signal date `t`, H1 uses the official target for Open[t+1] to Open[t+2]. H5 and H20 compound the one-day market-residual returns for intervals Open[t+1]→Open[t+2] through Open[t+H]→Open[t+H+1], equivalently daily return rows `t+2` through `t+H+1`. Each daily residual is `raw_return[u] - beta[u] * topix_return[u]`; the compounded target is `product(1 + residual[u]) - 1`. Each horizon's target receives the existing date-wise average-rank centered transform. H1 uses the official target file without recomputation in the fit/evaluation path; an independent arithmetic check against the daily residual formula is only a label integrity assertion.

## Fixed model and signal

- Existing five directional box features, high/low event definitions, 250-observation breakout, universe and listing-segment handling.
- Separate High and Low Ridge models, Ridge lambda 1.0, existing minimum 500 training event rows, existing yearly expanding Train folds (2011–2016).
- High model target is positive centered cross-sectional rank; Low target is its negative, unchanged.
- H1/H5/H20 use the same prediction-to-event-percentile-to-EWMA mapping. High alpha 0.25; Low alpha 0.50; fixed SN1 precedence `D=high_state+low_state; if low_state<0 use low_state; else if low_state==0 and high_state>0 use high_state; else use D`.
- Official five quintiles, official weights, one-way cost 10 bps. Signal architecture and all non-target inputs are frozen.
- Valid-period model is fit once from mature Train labels, matching the existing formal SN1 entry point. Valid labels are used only as development evaluation outcomes, not for fitting or branching.

## Purge and evaluation boundaries

Horizon H matures at signal calendar position `t + H + 1`. A training signal is eligible only when this final label date is strictly before the first prediction date. Thus the exclusive calendar slice ends at `fold_start_position - (H + 1)`, giving H1's current two-position purge and H5/H20 maturity purges of 6/21 signal dates. All forward target windows are required to remain inside their designated Train or historical Valid split and listing segment. No Train label may consume a Valid return.

Portfolio performance means the actual daily O2O account under the existing daily quintile weights, using the official H1 realized daily residual target for every candidate. H-specific overlapping forward returns are forecast-quality diagnostics, not daily P/L observations; they are not annualized as standalone portfolio P/L. This avoids treating overlapping H-day labels as independent daily wealth or charging a daily rebalance cost against a multi-day return.

## Predeclared metrics and fixed uncertainty method

- Event-only daily cross-sectional RankIC by side and pooled, HAC t-stat with lag exactly H trading days, hit rate, coefficient tables/sign stability, event counts, daily prediction dispersion.
- Actual daily-account gross/net return, gross/net SR, volatility, max drawdown, average daily turnover, annual cost, RankIC, long/short gross/net/SR and annual/calendar-year rows; same definitions and 10 bps cost as existing evaluation.
- Membership rank autocorrelation; Q1/Q2/Q4/Q5 retention; quintile transitions, entrants/exits; holding spell duration; score/rank changes; year turnover; concentration/sector diagnostics where available.
- Horizon consistency uses pre-fixed windows: H5 predictions against day 1, days 1–5, and days 6–20; H20 predictions against day 1, days 1–5, days 1–20, and days 21–40 (a fixed 20-day post-horizon window for the `day 21+` diagnostic). These are compounded residual returns and are truncated at each split boundary.
- If daily-account paired uncertainty is computed, use the existing circular paired block bootstrap unchanged: 20 trading days, 1,000 replications, seed 20260908. Do not change bootstrap choices after looking at results.
- Show Train, historical Valid, and combined development descriptively; combined results are never an optimization objective. Calendar-year partitions remain fixed.

## Decision rules

Each horizon is SUPPORTED only when implementation/leakage checks pass and Train and historical Valid point in the same favorable direction on multiple structural dimensions: gross behavior, Long behavior, RankIC/target-horizon consistency, and year stability. A cost-only effect, historical SR maximum, one-period concentration, or apparent result from overlapping-return annualization is insufficient. Otherwise classify MIXED or REJECT. H1 remains the paper choice if neither H5 nor H20 has structural evidence beyond H1. Select at most one paper challenger; do not switch by month.

## Prohibitions

No H2/H3/H10/H15/H40, horizon grid, interpolation, alpha/lambda/event/feature/threshold/weight tuning, new strategy branch, Short/session/regime modification, Valid-driven selection beyond this fixed comparison, or post-result candidate addition. No historical Sharpe 1.0 pass threshold. Future paper results are the final forward OOS.
