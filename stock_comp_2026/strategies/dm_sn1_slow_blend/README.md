# SN1_SLOW_BLEND

[Experiment DM-20261003-03](../../../experiments/DM-20261003-03/plan.md).
Exactly one fixed Train-only final-score blend: original centered average percentile rank of SN1_H1 plus the same rank of SLOW_CONTROL, no additional smoothing.

component_sn1/{features,bidirectional,sn1}.py and component_slow/features.py are byte-identical copies of the existing strategy modules. Component definitions, horizon, parameters and annual H1 training procedure are unchanged. copies are verified against originals and saved Train scores.

submission.predict(data_dir='.') explicitly loads Train files and mature prior-fold Train labels for the original annual SN1 Ridge. It is a self-contained research adapter. This experiment does not implement a later-split release or submission zip. The 50/50 official-weight virtual portfolio exists only in the research diagnostics.
