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

## DM-20260923-01: High Proximity Momentum

[採否](DM-20260923-01/decision.md) / [結果](../reports/DM-20260923-01/REPORT.md)。Train-only、事前登録7候補、Valid未評価。

- **P60 (60日高値近接度単体)** — Net SR -0.2125 (H0比 -0.6176)、Turnover 0.0965 (H0比 +0.0329)、年率Cost 2.43% (+0.82pt) でコスト負け。改善Fold 2/4。却下。
- **C1 (20日高値近接度ブレンド)** — Net SR -0.0552 (H0比 -0.4603)、Turnover 0.1042 (+0.0406)、年率Cost 2.61% (+1.01pt) でコスト負け。改善Fold 2/4。却下。
- **C2 (60日高値近接度ブレンド)** — Net SR 0.2150 (H0比 -0.1901)、Turnover 0.0728 (+0.0092)。改善Fold 2/4。却下。
- **C4 (60日チルト)** — Net SR 0.3445 (H0比 -0.0607)。改善Fold 2/4。却下。
- **C5 (60日ゲート / 相互作用)** — Net SR 0.3143 (H0比 -0.0908)。改善Fold 0/4。却下。

※なお、本実験における最良候補 **C3 (52週高値近接度ブレンド: `0.5*M + 0.5*prox250`)** は Net SR 0.5164 (H0比 +0.1112)、改善Fold 3/4、Turnover 0.0526 (-0.0111) を達成し、一次選別基準を通過して Candidate に採択された。上記は短期・中期（20日/60日）候補の却下記録である。

2026-09-24の技術監査で、初回C3のraw `High`/`Close`が`AdjustmentFactor`イベント前後の価格単位を混在させていたことを確認した。上記は当時の判定記録として残すが、C3は現在の採用・Freeze候補から撤回する。修正版`C3S`は[DM-20260924-01](DM-20260924-01/decision.md)で別候補として記録し、Train値は探索的診断のみに使用した。

## DM-20260923-02: High Proximity 60/250 Equal Blend

[採否](DM-20260923-02/decision.md) / [結果](../reports/DM-20260923-02/REPORT.md)。ユーザー依頼による単一の探索的追加比較。既知Train期間を再利用し、候補選択・採用には使用しない。

- **C6 (`0.5*M + 0.25*prox60 + 0.25*prox250`)** — H0 Net SR 0.4051に対し0.3894 (Δ −0.0158)、改善fold 2/4。Turnover 0.0623 (Δ −0.0014)、RankIC 0.0121 (H0 0.0072)。診断基準未通過。

この結果は等ウェイト合成の当該定義に限る。高値近接度または複数horizonの一般的な有効性を結論しない。

## DM-20260924-02: Side-Specific 250-Observation Breakout

[採否](DM-20260924-02/decision.md) / [結果](../reports/DM-20260924-02/REPORT.md)。Valid閲覧後に着想した仮説のため、Train-onlyの既知期間上の記述比較。M00/H10/L01/HL11の4条件を固定し、Valid未評価。

- **H10 Long new-high** — H0比Net SR -0.0619、改善fold 0/4、turnover +0.00287/日。
- **L01 Short new-low** — H0比Net SR -0.0420、改善fold 0/4、turnover +0.00056/日。
- **HL11 両側** — H0比Net SR -0.0814、改善fold 0/4、turnover +0.00382/日。

各年のNet Sharpe差は3条件とも負で、paired block-bootstrap 95%区間もゼロ未満。固定した250観測・50/50 centered-rank blendは不採用とする。これは新高値・新安値ブレイク一般の無効性を示さない。既知期間の事後比較から別窓・重みを追加探索しない。

## DM-20260924-03: Breakout Base with Side-Specific Momentum

[採否](DM-20260924-03/decision.md) / [結果](../reports/DM-20260924-03/REPORT.md)。新高値Long・新安値Shortを基準にして、Momentumを各側へ固定50/50で追加した4条件。Valid閲覧後の仮説なのでTrain-onlyの記述比較、Valid未評価。

- **M10 Long overlay** — B00比Net SR -0.1025、改善fold 2/4。Long年率Net +4.99%→+4.74%。
- **M01 Short overlay** — B00比Net SR +0.0070、改善fold 3/4。ただし20日block bootstrap CI [-0.0332,+0.0467]が0を含む。Short年率Netは-1.01%→-0.99%で差はごく小さい。
- **M11 両側overlay** — B00比Net SR -0.0936、改善fold 1/4。

M01の微小な改善を採用根拠とせず、全組合せを凍結候補にしない。B00 scoreのゼロ値がQ1/Q5にも残るため、official five-quantileのstable-index tie-breakを含む結果である。今回の固定overlayだけを記録し、事後の重み・窓追加をしない。

## DM-20260924-04: Breakout × Momentum × Volume Change LightGBM

[採否](DM-20260924-04/decision.md) / [結果](../reports/DM-20260924-04/REPORT.md)。Train-only、LightGBM候補1/1、Valid未読。既読Valid分析後の仮説なので記述値であり採用根拠ではない。

- **LGBM_001** — 250-observation high/low breakout ranks、res60s1、split-safe relative volume-change rankを浅いannual LightGBMへ入力。H0 Net SR 0.4477、B00 0.9064に対して-1.9564。改善fold 0/4、RankIC -0.0047、Turnover 0.1554/day、annual cost 3.89%、Short annual Net -6.48%、Max DD -22.96%。
- paired 20-day block bootstrapのΔNet SR 95%区間はH0比[-4.3882,-0.4006]、B00比[-4.5720,-1.2340]。当該設定は不採用。

Source firewall、3 cutoffの全feature/prediction/refit prefix-invariance、coverage、決定性、Long+Short会計一致はPASS。これは固定した特徴量と浅いLightGBM一条件の却下であり、LightGBM一般の無効性を示さない。既知データ上の結果を見て追加の深さ・特徴量・window searchをしない。

## DM-20260924-05: Breakout × Momentum × Volume Change Ridge

[採否](DM-20260924-05/decision.md) / [結果](../reports/DM-20260924-05/REPORT.md)。Train-only、線形候補1/1、Valid未読。LightGBM候補の後に立てた仮説なので記述値であり、独立確認・採用根拠ではない。

- **LINEAR_001** — 同じ4特徴量、daily centered-rank target、fit-window scaling/imputation、Ridge lambda=1.0。H0 Net SR 0.4477とB00 0.9064に対して-1.9447。改善fold 0/4、annual cost 4.85%、Turnover 0.1936/day、Short annual Net -7.48%、Max DD -31.68%。
- Paired 20-day block bootstrap 95%区間はH0比[-4.4970,-0.2299]、B00比[-4.6008,-1.1076]。固定仕様を不採用。

Train firewall、3 cutoffのfuture-mutation/truncation refit/prediction prefix-invariance、determinism、coverage、会計一致はPASS。これは当該target・特徴量・Ridge penalty一条件の却下であり、線形モデル一般の無効性は意味しない。既知Train上での事後結果を理由にlambdaや符号等を追加探索しない。

## DM-20260924-06: 60日価格傾き・52週レンジ位置・出来高zスコア

[採否](DM-20260924-06/decision.md) / [結果](../reports/DM-20260924-06/REPORT.md)。Train-onlyの記述評価、RIDGE_001とLGBM_001の2/2条件、Valid未読。期間は2010-01〜2016-03（1518評価日）。以前に確認済みの全Trainを含む。

- **RIDGE_001** — Net SR -0.8349、H0 -0.0220 / B00 0.5687を下回る。年率Net -3.22%、turnover 0.1438/日、年率cost 3.61%、Short年率Net -4.84%、改善fold 3/7 vs H0・2/7 vs B00。B00比較paired bootstrap 95% CI [-2.7240,-0.0655]。
- **LGBM_001** — Net SR -1.4550、改善fold 0/7 vs両ベースライン。年率Net -5.23%、turnover 0.2114/日、年率cost 5.31%、Short年率Net -6.09%。B00比較paired bootstrap 95% CI [-3.3121,-0.7954]。

Feature source scan、Train firewall、3 cutoff future-mutation/truncation prefix-invariance、fit replay、coverage、会計照合はPASS。2010初回fitは完全特徴量が29 signal dates、2016 foldは59評価日で薄い。これは固定したlog-price slope、52週channel位置、出来高zスコアと2モデル設定の不採用であり、特徴量やモデル一般を棄却しない。既知Train上の結果で窓・符号・正則化・モデル構造を追加探索しない。

## DM-20260924-07: 52週レンジ位置単独スコア

[採否](DM-20260924-07/decision.md) / [結果](../reports/DM-20260924-07/REPORT.md)。事前固定1条件、既知Train期間の記述比較。Valid未読。

- **CHANNEL_250_001** — 前日終値をそれ以前の250観測High/Low間へ写像し、高値+1・安値-1とした連続scoreを単独利用。EWMA alpha=0.25。Net SR 0.1184、H0 -0.0220を+0.1404上回ったが、paired 20日block bootstrap 95% CI [-0.3477,+0.6501]。B00 0.5687に対して-0.4503、改善foldはH0比5/7・B00比2/7。
- Annual Net +0.57%（Long +3.89%、Short -3.32%）、turnover 0.05487/日、annual cost 1.38%、Max DD -10.67%。H0より改善した点はあるが、B00に対する安定した増分は確認できず単独候補として不採用。

Source scan、Train firewall、3 cutoffのfeature/signal prefix-invariance、coverage、finite score、会計照合はPASS。既知Trainの記述結果であり、単独channel score一般の無効性や独立OOSを意味しない。結果後のwindow・smoothing・side条件探索は行わない。

## DM-20260924-08: B00 / 52週位置スコアの絶対値化

[採否](DM-20260924-08/decision.md) / [結果](../reports/DM-20260924-08/REPORT.md)。Train-only、絶対値化2条件、既知Trainの記述比較。Valid未読。

- **B00_ABS** — alpha=0.25 EWMA後のB00 scoreをabs化。Net SR 0.3892（B00 0.5687、Δ -0.1795）、年別改善2/7、turnover 0.03828/日。Long年率Net +3.63%、Short -2.38%。
- **CHANNEL_250_ABS** — 同じchannel-position scoreをabs化。Net SR 0.3203（符号付き版0.1184を+0.2020上回る点推定だが、bootstrap 95% CI [-0.9070,+1.2282]）。turnover 0.09169/日、年率cost 2.31%、Long +4.15%、Short -3.05%。B00にはNet SRで0.2484届かず。

3 cutoffのfeature/signed/absolute prefix-invariance、source scan、Train firewall、coverage、finite score、会計照合はPASS。全Trainは既知で独立OOSではない。両固定条件を不採用とし、結果後に変換順・smoothing・side条件の追加探索をしない。

## DM-20260924-09: 52週レンジ位置 + 1日出来高変化 Ridge

[計画・採否](DM-20260924-09/decision.md) / [結果](../reports/DM-20260924-09/REPORT.md)。Train-only、事前固定1候補、全Train既知の記述評価。

- **RIDGE_001** — 前日終値のsplit-safe prior-only 250観測channel positionと、前日/2営業日前split-safe raw Volume比の変化率を入力したannual expanding Ridge(lambda=1)、targetは日次centered rank、EWMA alpha=0.25。H0 Net SR -0.0220に対して-0.8545 (Δ -0.8325)、B00 0.5687に対して-1.4232、channel単独0.1184に対して-0.9729。改善foldはH0比2/7、B00比1/7、channel比2/7。
- Annual Net -4.06%、cost 4.61%、turnover 0.18418/日、RankIC 0.0007、Long +1.62%、Short -5.68%、Max DD -34.17%。B00比較paired 20日block bootstrap 95% CI [-2.6561,-0.2508]。
- Source scan、Train firewall、3 cutoffの全入力future-mutation/truncation prefix-invariance、成熟Train/refit/prediction一致、coverage、決定性、会計照合はPASS。固定した2特徴・Ridge条件を不採用とし、全Trainが既知のため特徴変換・lambda等を結果後に追加探索しない。

## DM-20260924-10: Variable-Duration Box Breakout Ridge

[採否](DM-20260924-10/decision.md) / [結果](../reports/DM-20260924-10/REPORT.md)。Train-only、固定候補1本、全Train既知の記述診断。

- **BOX_RIDGE_001** — H0に対してNet SR +0.5144だが、B00に対して+0.0028のみ。paired 20日block bootstrap 95% CI `[-0.0269,+0.0291]`、B00改善4/6fold。Turnover/day +0.00019、annual cost +0.005ptで、安定した追加価値は確認できず不採用。
- 5日刻み5〜120日、ATR20比3未満のbox duration/width、t-1 close position、residual strength、prior high distanceを使ったRidgeとLong event blendの当該定義を却下する。可変長ボックス一般や圧縮後ブレイク一般を否定しない。既知Trainであり採用根拠にしない。
- 追加Phase 1診断[DM-20260924-11](DM-20260924-11/decision.md)ではevent-only RankIC +0.0117 / HAC5 t +0.72、BOX 100%でも年率Net差+0.029%・weight変更2.96%。durationはevent成立boxの87.2%がL≤10に集中したため、事前指定の√L正規化を一度だけ[DM-20260925-01](DM-20260925-01/decision.md)で再検証。補正後はeventの99.97%がLmax=120に飽和し、event-only RankIC +0.0013 / HAC5 t +0.09、BOX 100%でΔNet SR −0.0133。1日O2OのBOX候補は採用せず追加救済試行も終了する。matched overnightは元定義でA/B双方に正の夜間収益があり、年別A−Bの符号が不安定なためBOX固有アルファの証拠にしない。Valid未読。

## NH_REV_001 / DM-20260925-02 — CLOSED (2026-09-25)

Fixed negative RS60 rank within new-high events, one candidate, B00 Short signal and EWMA .25 unchanged. Frozen Valid raw event IC=-0.001195 vs required ≤-0.02; HAC5 t=-0.127; quintile monotonicity=-0.10; trimmed spread reverses positive. **NO-GO**. Supplied Valid was previously disclosed and is not independent OOS. No portfolio rescue, RS horizon/filter search, BOX revival, interaction or next-phase/Short redesign. [Decision](DM-20260925-02/decision.md) / [Report](../reports/DM-20260925-02/REPORT.md).

## DM-20260925-03: Bidirectional Variable-Box Standalone Scores

[採否](DM-20260925-03/decision.md) / [結果](../reports/DM-20260925-03/REPORT.md)。Train-onlyの固定候補1本。高値・安値イベントを別々のannual expanding Ridgeで学習し、B00を混ぜないsigned scoreを生成した。安値側scoreはnegative RankIC orientation、低値予測順位をより強いShortとして符号化。

- **BOX_BIDIR_STANDALONE** — Net SR 0.7851、B00 0.8197を-0.0346下回る。改善fold 2/6、paired 20-day block bootstrap 95% CI [-0.1616,+0.0688]。年率Net +3.65% (B00 +3.83%)、Turnover 0.03185/日 (B00 0.03117)、annual cost 0.80% (B00 0.78%)。Long/Short双方のnet attributionもB00から悪化した。
- 3-cutoff future-mutation/truncation prefix-invariance、Train firewall/source scan、coverage 576,535/576,535、決定性replay、Long+Short会計一致はPASS。全Train既知の記述診断でValid未読。固定候補を却下し、結果後の追加探索を行わない。

## DM-20260927-01: Fixed Asymmetric EWMA Diagnostic

[採否](DM-20260927-01/decision.md) / [結果](../reports/DM-20260927-01/ASYM_EMA_RESULTS.md)。既知Train上の固定診断、Valid未読。`alpha_high=0.15 / alpha_low=0.50` をBOXとB00に同じく適用した。

- **C_ASYM_EWMA** — `A_LOW_NO_CARRY` に対してNet SR +0.0178、annual Net +0.444pt、turnover/day 0.04589→0.03229、annual cost 1.151%→0.810%、Q1 zero-score Short weight 51.87%→10.55%。ただしGross SR 1.024→0.935、ex-2016 Net SR 0.698→0.654、2015 annual Net -0.187%→-0.416%。BOX_ORIGINALにはNet SRで0.0284、annual Netで0.190pt届かない。
- AのNet悪化はGross Return -0.281pt（selection component -0.315pt）とcost +0.352ptの両方。CのNet回復は主にcost低下で、固定ペアのため変更寄与をLow carryだけに帰属できない。同じruleをB00へ適用するとNet SR +0.0203でBOX版より改善が大きく、Box固有効果ではない。
- 混在結果のため不採用・追加alpha探索なし。4 focused tests、official weights/account replay、coverage、Train firewall、score-prefix invariance、`make check` はPASS。

## DM-20260927-02: Low-fast-only EWMA Diagnostic

[採否](DM-20260927-02/decision.md) / [結果](../reports/DM-20260927-02/LOW_FAST_ONLY_RESULTS.md)。既知Train上の固定診断、Valid未読。High alphaを0.25に固定し、Low alphaだけ0.50とした1候補をBOXとB00に適用。

- **D_LOW_FAST_ONLY** — BOX_ORIGINAL比Gross +0.084pt、selection +0.074pt、Net +0.067pt、Net SR +0.0231、ex-2016 Net SR +0.0262。Turnover/day 0.03252でBOX 0.03185に近い。A_LOW_NO_CARRYと比べるとturnover 0.04589→0.03252、Q1 zero-score weight 51.87%→10.13%、Short zero-score weight 46.86%→8.48%。
- Short zero/tieはBOX比で減らず（Short zero weight 8.48% vs 8.05%、zero-Code rho 0.811 vs 0.812）。2014年はBOX比悪化、2016部分Net returnも低い。D_B00はB00_BASE比Net SR +0.0518でBOX版以上。paired 20日block bootstrap 95%区間は3比較すべて0を跨ぐ。
- 連続Low decayはAの順位/コスト不安定を抑え、BOXの点推定を小幅改善した方向性はあるが、既知Train上で不確実。採用根拠にはせず、alpha追加探索なしで本系列を閉じる。

## DM-20260927-03: Short × Night Root-Cause Levers

[採否](DM-20260927-03/decision.md) / [原因監査](../reports/DM-20260927-03/SHORT_NIGHT_ROOT_CAUSE.md) / [候補結果](../reports/DM-20260927-03/SHORT_NIGHT_LEVER_RESULTS.md)。固定計画2候補のみ、既知Trainの記述検証。Valid・Freeze・raw target・submission evaluationなし。BaselineのP/L/source attributionは依頼文と既存報告によりPhase 1開始時点で既知だが、Phase 1 driverはtarget/returnを読まず、候補P/Lはplan hash確定後に計算した。

- **SN1 `SIDE_SOURCE_SEPARATION`** — High/Low stateのside-specific ordering。D比Total Net +0.801pp、Net SR +0.255、ex-2016 Net SR 1.009だが、Short × Nightは-0.517pp悪化（5/6年で悪化）。Cost/turnover減少が総Netを押し上げても、対象セルは改善せず不採用。paired 20日bootstrapのΔNet SR/ΔShort×Night CIはいずれも0を跨ぐ。
- **SN2 `HIGH_AGE5_SHORT_VETO`** — High-age-5+ dominantをShort rankingから外す固定ordinal。High-age-5+ source attributionは+0.680pp改善した一方、Short × Night全体は-0.070pp、Short × Day -1.208pp、turnover +0.0543/日、annual cost +1.369pp、Total Net -2.374pp、Net SR -0.489。zero-score rowsをCode順ordinalで埋めた`other`がShort gross weight 8.48%を占め、経済シグナルを作らなかった。

双方ともrepo内のnumeric/index/coverage contract、公式5分位・weight・exposure検査をPASS。source firewall、P/L reconciliation、3 cutoff future-mutation prefix-invariance PASS。**No surviving lever**。当系列を閉じ、結果後のalpha/threshold/feature/lever追加をしない。
