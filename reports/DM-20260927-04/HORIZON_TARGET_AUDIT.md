# Horizon target audit

## Source of truth: existing implementation

`stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py` builds the date-wise centered target rank, orients it positively for the High Ridge, and negates it for the Low Ridge. `fit_before` uses only event rows whose target is present and whose signal date is mature. Its current `calendar[:start_position-2]` rule shows that the official H1 label endpoint is two trading-calendar positions after the signal date.

`stock_comp_2026/README.md` defines the official one-day label as `raw_target_1day[t] = raw_return_1day[t+2]`, with `target[t] = raw_target[t] - beta[t+2] * topix_return[t+2]`. Dataset timing states that the signal at `t` is formed from information through date `t`, entered at Open[t+1], and evaluated at Open[t+2]. On the row convention `raw_return[u] = Open[u-1]→Open[u]`, this is one O2O interval.

Example by relative trading dates: signal on date `t`; enter the next trading date Open (`t+1`); exit the following trading date Open (`t+2`). The target is the Wednesday-ending raw return minus Wednesday's supplied beta times Wednesday's supplied market return. The Ridge target is the within-date centered percentile rank of that residual, multiplied by two. High events use this rank; Low events use its negative.

## Fixed generalization for this study

For H in `{1,5,20}`, keep entry at Open[t+1] and exit at Open[t+H+1]. For H5, compound the five consecutive supplied daily residual returns at rows `t+2` through `t+6`; for H20, compound the twenty daily residual returns at rows `t+2` through `t+21`:

`R_H(t) = product_{u=t+2}^{t+H+1}(1 + [raw_return[u] - beta[u] * topix_return[u]]) - 1`.

This retains the official H1 daily residual definition at each step and uses standard multiplicative return aggregation. H1 in the model/evaluator path comes from the official `target_1day_{train,valid}.parquet`; an independent reconstruction is checked against it. For every horizon the final Ridge target is transformed using the existing date-wise average rank, mean-centered and scaled by two.

Missing daily inputs, missing dates, listing-segment gaps, or split-boundary crossing invalidate the label. A Train target may use only Train daily returns; a historical Valid target may use only Valid daily returns. This prevents Train labels near the Train/Valid boundary from consuming Valid returns.

## Label maturity / purge

The final price/return row is at calendar position `signal_position + H + 1`. A training label is eligible only if that maturity date is strictly before the first prediction date. The number of calendar positions excluded from the beginning of the prediction fold is therefore H+1: H1=2, H5=6, H20=21. This is implemented as the mature signal-date prefix `calendar[:start_position-(H+1)]`. For H1 this exactly reproduces the existing `calendar[:start_position-2]` implementation.

The evaluation splitter applies the same split-locality rule to forward labels. H1 official daily returns remain the realized daily portfolio P/L series for all three models; H5/H20 overlapping returns are used only for target-horizon prediction diagnostics. Consequently H5/H20 annual P/L and cost stay comparable with H1 and are not computed by annualizing overlapping labels.

## Fixed candidate set

Only H1, H5, H20 are allowed. Feature set, events, yearly expanding fitting, minimum event rows, Ridge lambda 1.0, sign convention, EWMA alpha, SN1 source precedence, universe, quintile weights and one-way cost remain fixed. See `experiments/DM-20260927-04/plan.md` for the pre-result plan and `config.json` for the fixed candidate configuration.


## Calendar-date example (post-result clarification)

The source and official panel include these consecutive Train dates. With signal date 2011-01-04, entry is Open on 2011-01-05 and exit is Open on 2011-01-06. Therefore the H1 return row is dated 2011-01-06 and represents Open(2011-01-05) to Open(2011-01-06), residualized with the beta and TOPIX return attached to 2011-01-06. The target definition and experiment are unchanged.

This date illustration was added after the pre-result lock to make the relative-date description concrete. The exact pre-result audit bytes are preserved at `artifacts/DM-20260927-04/run-20260927T101500Z/audit/HORIZON_TARGET_AUDIT_LOCKED.md` and retain the locked SHA256.
