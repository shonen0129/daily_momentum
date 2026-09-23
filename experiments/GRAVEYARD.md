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

## DM-20260909-01: Asymmetric Fundamental Short

[採否](DM-20260909-01/decision.md) / [結果](../reports/DM-20260909-01/REPORT.md)。Train-only、14/18試行、Valid未評価。

- **Candidate A（S0）** — 全9候補が一次基準不通過。代表heavy λ0.5は同時改善2/4fold、median ΔNetSR −0.0133。合成後EWMAの合算改善もfoldの一貫性不足。
- **Event Short（CFO前年比負転）** — 全4候補が不通過。代表λ1は同時改善2/4fold、median ΔNetSR −0.0030。
- **B/C（Vacuum/Participation）** — 未実行。A不通過による事前停止条件。フィルター自体の無効性を示す結果ではない。

今回の定義を却下するもので、財務Short一般の無効性の証明ではない。未実行枠への追加探索はしない。

### DM-20260909-02: T0 (Stitched Momentum Control (Bitwise match against B0 required))
- 判定日: 2026-09-09
- 却下理由: Primary Criteria不通過 (Short改善fold: 0/4, NetSR改善fold: 0/4, median ΔNetSR: 0.0000)
- 参照: reports/DM-20260909-02/REPORT.md

### DM-20260909-02: T3 (Fixed Long + Equal FD x WeakPrice + RecentCrash Avoidance)
- 判定日: 2026-09-09
- 却下理由: Primary Criteria不通過 (Short改善fold: 0/4, NetSR改善fold: 0/4, median ΔNetSR: -0.5168)
- 参照: reports/DM-20260909-02/REPORT.md

## DM-20260909-03: Continuous Fundamental Weakness Short

[採否](DM-20260909-03/decision.md) / [結果](../reports/DM-20260909-03/REPORT.md)。Train-only、4/4の事前登録候補、Valid未評価。

- **C1 Profitability deterioration** — Short改善2/4fold、pooled Short Net -0.18pt、Net SR -0.0433。却下。
- **C2 Balance-sheet weakness** — pooled Short Netは+0.05ptだがShort改善2/4fold、Net SR -0.0010。却下。
- **C3 Multi-dimensional weakness** — pooled Short Net +0.23pt / Net SR +0.0302だがShort改善1/4fold、median ΔShort Net -0.11pt、Short Netは-0.81%。一時点のTotal改善をShort alphaの採用根拠とせず却下。

今回のCash/Profitability/Balanceの固定等ウェイト拡張を却下するものであり、fundamental Short一般の無効性を意味しない。結果後の候補追加は行わない。

## DM-20260910-01: Independent Short Alpha Families

[採否](DM-20260910-01/decision.md) / [結果](../reports/DM-20260910-01/REPORT.md)。Train-only、4/4の事前登録候補、Valid未評価。

- **V1 Valuation / CFO Yield** — Short annual Net -2.89%（Champion比 -1.84pt）、Short改善0/4fold、Net SR -0.3873。却下。
- **V2 Earnings Quality / Accrual** — Short annual Net -2.59%（-1.55pt）、Short改善0/4fold、Net SR -0.3249。却下。
- **V3 Lottery / MAX20** — Short annual Net -2.63%（-1.59pt）、Short改善0/4fold、Turnover 0.0940（Champion 0.0584）、Net SR -0.3613。却下。

これは事前定義した各単体familyの不採用であり、valuation・accounting quality・lottery risk一般の無効性を意味しない。候補の合成、別multiple、別MAX window、IdioVol候補への置換は今回の結果後には行わない。

## DM-20260910-02: Full Daily Return Information Long / Short

[採否](DM-20260910-02/decision.md) / [結果](../reports/DM-20260910-02/REPORT.md)。Train-only、事前登録4/4候補、Valid未評価。

- **D1 RAW DRI** — Total Net SR -0.9916、Long annual Net +2.70%、Short annual Net -5.49%。H0比のNet SR改善0/4、Short改善0/4で却下。
- **D2 RAW DRI + EWMA(0.25)** — smoothingでD1比Net SRは+0.0167だが、Total -0.9749、Short -5.43%、H0比の改善fold 0/4で却下。
- **D3 Residual DRI + EWMA(0.25)** — 今回最良のDRI Total Net SRでも-0.9560。Long/Short/Total置換基準を全て不通過で却下。

RAW/RESともinitial-history CVが事前grid最大alpha=0.001を選び、年次Elastic Netの42係数が全てゼロとなった。この記録は、固定したdaily DRI adaptationとpenalty選択の不採用であり、DRI一般の無効性を主張しない。結果後のgrid拡張、別window、別平滑化、DRI+M60/FD hybrid、target変換、非線形modelは今回実行しない。

## DM-20260910-03: Daily Turnover Information Long / Short

[採否](DM-20260910-03/decision.md) / [結果](../reports/DM-20260910-03/REPORT.md)。Train-only、5/5候補、Valid未評価。

- **M0 DTI rank** — Net SR -0.8450（H0比 -1.6290）、RankIC -0.0149、Short年率Net -4.85%。H0比Net SRは4/4年で悪化。
- **T1 RAW / T2 rank / T3 rank+EWMA** — grossの改善はあっても、turnoverが1.1418 / 1.0319 / 0.4183、年率costが28.68% / 25.91% / 10.50%となり、Net SRは -11.2462 / -9.8885 / -2.8882。全候補がH0のNet SRを下回った。

PIT分母とfuture-mutation/truncationの因果性監査はPASSした。これは固定したdaily DTI adaptationと取引実装の不採用であり、turnover情報一般の無効性を主張しない。結果後のgrid拡張、別window、別target、別平滑化、非線形モデルの追加は行わない。

## DM-20260911-01: Advanced DTI Representations

[採否](DM-20260911-01/decision.md) / [結果](../reports/DM-20260911-01/REPORT.md)。Train-only、事前登録7/7候補、Valid未評価。

- **S0 (raw DTI, EWMA 0.05)** — D0比でturnover 0.4183→0.1339、annual cost 10.50%→3.36%、Net SR -2.8882→+0.0882へ改善。ただしpositive Net-SR foldは1/4、Short Net SR -0.4766でDTI salvage不成立。
- **A1 / S1 / U1 / R1** — ATOとreturn条件付けはS0を上回らなかった。新表現内の最良R1でもGross/Net SR -0.4282/-1.5644、Short Net SR -1.1067。Short単独の正収益源は得られなかった。

H0/D0再現、PIT分母、future-mutation/truncation、determinism、firewallはPASS。今回の固定表現群を却下し、結果後のalpha・window・ATO baseline・return scaling・新interaction・hybridは追加しない。

## DM-20260911-02: Intraday Momentum Short / Skewness-Managed FD Short

[採否](DM-20260911-02/decision.md) / [結果](../reports/DM-20260911-02/REPORT.md)。Train-only、事前登録3/3候補、Valid未評価。

- **I1 Intraday-only Momentum Short** — Short annual Net -3.54%（H0比 -2.50pt）、Short改善0/4fold、Total Net SR 0.1867（H0比 -0.5973）。RankICも-0.00037で、60日Open→Close方向は固定Short bookにalphaを与えなかった。
- **K1 Skewness-managed FD Short** — positive-return tail（p90/p95/p99）とworst 1%/5% Short lossは低下したが、Short annual Net -1.67%（-0.62pt）、Short改善1/4fold、Total Net SR 0.6658。tail controlの便益がgross alpha低下と追加costを補わず却下。

これは事前固定したintraday方向とmonthly OLS skewness overlayの不採用であり、intraday informationまたはskewness management一般の無効性を主張しない。結果後のhorizon・threshold・predictor・I1/K1 hybrid・他Short alpha候補は追加しない。

## DM-20260911-03: DRI Ridge / Alpha-Max-Relative Elastic Net

[採否](DM-20260911-03/decision.md) / [結果](../reports/DM-20260911-03/REPORT.md)。Train-only、4新候補+4対照、Valid未評価。

- **R_RAW / R_RES (Ridge)** — 開発各年42係数を保持したが、Net SR -1.1955 / -1.7771、Short年率Net -6.17% / -6.98%。H0比Short/Total改善は各0/4年。却下。
- **E_RAW / E_RES (relative-alpha Elastic Net)** — 開発年の非ゼロ係数2–3 / 6本、予測の日次断面分散も確認したが、Net SR -2.5783 / -1.7621、Short年率Net -8.49% / -6.92%。H0比Short/Total改善は各0/4年。却下。

RAW版はGrossの改善があっても全体年率Cost 7.69%/11.59%で失敗。残差版は全体Grossも負。
全候補のShort Grossも負であり、ゼロ係数問題の解消だけではShort alphaを得られなかった。
旧DRIとのfeature一致、3cutoff feature/prediction/label-refit因果性、独立推論、公式会計はPASS。
今回の固定21日daily DRIの有限比較を却下し、事後grid拡大・符号反転・平滑化変更・hybridは追加しない。
