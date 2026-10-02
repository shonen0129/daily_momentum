# 却下実験索引

DM-20260908: Train-only。詳細・再現データは ../reports/DM-20260908/EXPERIMENT_LOG.md。

- **M_res5s1_a1** — Momentum shape/smoothing stability rank
- **M_res10s1_a1** — Momentum shape/smoothing stability rank
- **M_res20s1_a1** — Momentum shape/smoothing stability rank
- **M_res60s1_a1** — Momentum shape/smoothing stability rank
- **M_res20s0_a1** — Momentum shape/smoothing stability rank
- **M_res20s2_a1** — Momentum shape/smoothing stability rank
- **M_raw20s1_a1** — Momentum shape/smoothing stability rank
- **M_sector20s1_a1** — Momentum shape/smoothing stability rank
- **M_equal_5_20_60_a1** — Momentum shape/smoothing stability rank
- **M_res60s1_a0.5** — Momentum shape/smoothing stability rank
- **M_res60s1_a0.15** — Momentum shape/smoothing stability rank
- **SENS_alpha_0.200** — Fixed sensitivity; not eligible for selection
- **SENS_alpha_0.300** — Fixed sensitivity; not eligible for selection
- **C1_rule** — Acceptance gate failed: improved folds=0/4; median delta=-0.083; bootstrap lower=-0.131; DSR=0.00003
- **C1_ml** — Acceptance gate failed: improved folds=2/4; median delta=0.001; bootstrap lower=-0.010; DSR=0.00005
- **B_lambda0.25** — Acceptance gate failed: improved folds=3/4; median delta=0.032; bootstrap lower=-0.062; DSR=0.00007
- **B_lambda0.5** — Acceptance gate failed: improved folds=1/4; median delta=-0.017; bootstrap lower=-0.151; DSR=0.00006
- **B_lambda1.0** — Acceptance gate failed: improved folds=1/4; median delta=-0.167; bootstrap lower=-0.389; DSR=0.00003
- **C2_ml** — Acceptance gate failed: improved folds=1/4; median delta=-2.135; bootstrap lower=-3.673; DSR=0.00000
- **A_rank** — Acceptance gate failed: improved folds=0/4; median delta=-2.392; bootstrap lower=-3.680; DSR=0.00000
- **A_raw** — Acceptance gate failed: improved folds=1/4; median delta=-1.557; bootstrap lower=-2.997; DSR=0.00000
- **SENS_B_lambda0.4** — Fixed sensitivity; not eligible for selection
- **SENS_B_lambda0.6** — Fixed sensitivity; not eligible for selection
- **SENS_C1_gate0.8** — Fixed sensitivity; not eligible for selection
- **SENS_C1_gate1.2** — Fixed sensitivity; not eligible for selection
- **SENS_C1_n_estimators48** — Fixed sensitivity; not eligible for selection
- **SENS_C1_n_estimators72** — Fixed sensitivity; not eligible for selection
- **SENS_C1_min_child_samples400** — Fixed sensitivity; not eligible for selection
- **SENS_C1_min_child_samples600** — Fixed sensitivity; not eligible for selection

- **C3 / deep impact / new interactions** — 未実施。前段の安定したincremental improvementがなく探索予算を拡大しない。
- **Liquidity vacuum / volume confirmation** — 条件付き効果が事前仮説と一致しない期間が多く、一律gateや符号反転を正当化しない。
- **最終Momentumの実運用採用** — 保留。Train確認Net Sharpe -0.088、統計的証拠不足。研究候補のFreezeのみ。
