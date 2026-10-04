# Annual OLS: Size / Illiquidity / MOM60

One Train-only research candidate. Exact DM-20261003-05 component and rank
definitions; every file in component_factors is copied unchanged. No windows,
weights, sign constraints, filters, regularization, smoothing or risk-overlay
search. Ordinary least squares estimates an intercept and three coefficients
from raw supplied residual target, equal weight per finite mature stock-day.

Expanding annual fits2009–2016 require t+2 label end strictly before each year's
first prediction session. 2008 is neutral feature-history warmup. The inference
adapter reads only six Train feature files and supplied annual JSON coefficients,
never labels. Missing required model raises; no future-year fallback.

Run models are preserved in artifacts, supplied explicitly via model_dir.
No Valid adapter, release or external submission in this experiment.
Plan: [DM-20261003-06](../../../experiments/DM-20261003-06/plan.md).
