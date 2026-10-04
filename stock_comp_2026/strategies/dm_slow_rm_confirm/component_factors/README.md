# SLOW_MOM60_EQUAL

Train-only, label-free research candidate. Three independent factors: existing
SLOW z_size, z_amihud, and frozen residual60/skip1 → daily centered rank →
EWMA(alpha=.25) MOM60. Each final factor is independently transformed to
average-tie daily percentile rank p, then 2*(p-mean(p)). Final score is the
arithmetic mean of these three ranks, without further smoothing.

This differs from 0.5*SLOW_CONTROL+0.5*MOM60 and from combined official sleeves.
The copied SLOW module is byte-identical; MOM60's four reachable functions are
source-identical to dm_trainonly/features.py. predict(data_dir) reads only the
six explicitly named Train feature files. No target is read or model fitted.

Experiment: [DM-20261003-05](../../../experiments/DM-20261003-05/plan.md).
No Valid adapter, release freeze, or external submission is part of this research.
