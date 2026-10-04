# DM-20261002-09 decision

RAW_EWMA_CONTROL: DIAGNOSTIC_NEGATIVE_CONTROL.
RAW_EWMA_SHORT_VETO: **REJECT**.

Failed checks: NetSR_improvements_4of5, primary_bootstrap_lower_gt0. Full-year NetSR improvements 3/5.

Exactly2 fixed trials, raw->EWMA matched primary contrast. Prior08 decisions unchanged. Known Train, not independent OOS; no rescue/extra trial/Valid/Freeze/submission. [Report](../../reports/DM-20261002-09/REPORT.md). Run `artifacts/DM-20261002-09/run-20261002T074832Z`.

主評価: RAW NetSR 0.319879、Veto 0.434558、Δ+0.114679、95% CI[-0.024014,+0.252484]。3/5年改善でREJECT。ShortnetΔ+0.3694pp=grossΔ+0.4002pp+cost effect-0.0308pp（gross寄与108.34%）。Transform-orderを揃えても点改善は残るが、安定した独立context価値の判定は事前基準未達。235 tests・27 full-input prefix・official/parity/audit・Freeze129hash PASS。make checkは既存04 metadata不整合。No rescue/Valid/Freeze/next candidate。
