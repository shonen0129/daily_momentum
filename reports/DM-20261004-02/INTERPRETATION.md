# DM-20261004-02: 最終解釈（全diagnostic完走後）

**F. Inconclusive。RMの正の条件付き情報を示唆するが、固定gateを通らず、SLOWへの組込みは採用しない。candidate性能試行0、rescue0。Historical Valid / Valid未使用。全Trainは既知development sample。**

[全表・監査を含む完全レポート](run-20261003T185022Z/REPORT.md)。[事前登録](../../experiments/DM-20261004-02/config.json)。科学原本はrun-20261003T183736Z、統計出力の欠損処理だけをrun-20261003T185022Zで補正した。Draw、feature、score、gate、performanceは再計算していない。

1. **独立した情報はあるか**：RM単独Mean RankIC=0.007288、HAC5 t=1.599、block20 95% CI=[−0.001453,0.016033]。線形Size/Illiquidity exposureを除いた後も正の点推定だが、独立情報が確定したとは言えない。残差の再rank後まで全ての非線形依存が除去されたとも主張しない。

2–4. **Long・Short・Small+Illiquidで有効か**：三領域のpooled/EX2016 spreadは全て正。LongとSmall+Illiquidは5/5年、Shortは4/5年positive。しかしprimary block20 CIは三領域とも0を含む。

| region | daily_spread_bp | CI_low_bp | CI_high_bp | positive_2011_2015 |
| --- | --- | --- | --- | --- |
| LONG | 2.816393 | -1.023532 | 6.506902 | 5 |
| SHORT | 1.410560 | -2.711078 | 5.321164 | 4 |
| CELL3_9 | 3.265104 | -0.637116 | 7.008667 | 5 |

表のbpは日次equal-weight RM tercile High−Lowのforward residual target差。取引可能なportfolio netではない。

time-series calendar結果：

| group | scope | spread | rankic | spread_hac5_t |
| --- | --- | --- | --- | --- |
| LONG | 2011 | 0.000459 | 0.009818 | 0.860511 |
| LONG | 2012 | 0.000416 | 0.012556 | 1.125063 |
| LONG | 2013 | 0.000244 | 0.002504 | 0.466134 |
| LONG | 2014 | 0.000175 | 0.001263 | 0.683678 |
| LONG | 2015 | 0.000009 | 0.000754 | 0.017126 |
| LONG | 2016 | 0.000704 | 0.021733 | 0.844720 |
| SHORT | 2011 | 0.000230 | 0.003054 | 0.392146 |
| SHORT | 2012 | 0.000224 | 0.012025 | 0.561742 |
| SHORT | 2013 | 0.000125 | 0.008011 | 0.219163 |
| SHORT | 2014 | 0.000504 | 0.016022 | 2.069213 |
| SHORT | 2015 | -0.000242 | 0.000734 | -0.542337 |
| SHORT | 2016 | -0.000421 | 0.002356 | -0.344025 |
| CELL3_9 | 2011 | 0.000199 | 0.004675 | 0.465097 |
| CELL3_9 | 2012 | 0.000484 | 0.010940 | 1.379178 |
| CELL3_9 | 2013 | 0.000476 | 0.007274 | 0.853319 |
| CELL3_9 | 2014 | 0.000229 | 0.000397 | 0.773837 |
| CELL3_9 | 2015 | 0.000128 | 0.004104 | 0.231798 |
| CELL3_9 | 2016 | 0.000788 | 0.028599 | 0.818317 |

5. **static factorかtimingか**：このbundleだけでは判別できない。残差化後の持続性は高く、entry/exit診断のsupportは薄い。短命なentry timing alphaが頑健に確認されたとは言えない。

6. **entry/holding/exitのどこか**：正の点推定はnew Long entry 11.33bp、new Short entry 10.57bpとcontinuingより大きいが、High/Lowが両方存在するのは69/49日（全1,275日の5.4%/3.8%）。Exiting Shortの−54.40bpも46日の薄いsupportに依存する。最も広く観測されるのはcontinuing holdingのLong2.90bp、Short1.43bpで、両方1,275日。entryが最適との判断やentry/exit filterは作成しない。

| group | daily_spread_bp | count | support_fraction |
| --- | --- | --- | --- |
| continuing_Long | 2.899659 | 1275 | 1.000000 |
| continuing_Short | 1.425211 | 1275 | 1.000000 |
| exiting_Long | 3.187211 | 60 | 0.047059 |
| exiting_Short | -54.401594 | 46 | 0.036078 |
| neutral | 2.736922 | 1275 | 1.000000 |
| newly_entered_Long | 11.330922 | 69 | 0.054118 |
| newly_entered_Short | 10.571709 | 49 | 0.038431 |

7. **persistenceとcostは整合するか**：RM rank autocorrelationはlag1=0.996、5=0.949、10=0.862、20=0.678。平均absolute rank changeはRM0.03444、SLOW0.00652、約5.29倍。RMの単日相関が高くても、SLOW順位を動かす情報は相対的に速く、追加turnover/costという既存研究の問題と整合する。今回candidate0本なので追加costの実額やafter-cost改善は測定していない。

8. **5×5 surfaceは滑らかか**：確認できない。25cellのうち12cellはsupport不足、2cellはspread/IC自体が未定義。極端なoff-diagonalの大きな値は平均1名未満などのsupportに依存する。統計が定義できた23cellのpositiveは15/23（65.2%）、Size方向/Illiquidity方向の隣接増加は各47.1%（各17組中8組）。主cornerが他cellより一貫して特別強い、SizeやIlliquidityに沿って滑らかに強まるとは言えない。3×3は8/9 positiveだが、Mid+LiquidはSmall+Illiquidより大きい点推定で、corner独占の構造ではない。

| surface | defined_cells | all_cells | positive_cells | positive_fraction_defined | positive_fraction_all_cells | size_adjacent_comparisons_defined | size_adjacent_positive_fraction_defined | illiq_adjacent_comparisons_defined | illiq_adjacent_positive_fraction_defined |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3x3 | 9 | 9 | 8 | 0.888889 | 0.888889 | 6 | 0.833333 | 6 | 0.666667 |
| 5x5 | 23 | 25 | 15 | 0.652174 | 0.600000 | 17 | 0.470588 | 17 | 0.470588 |

9. **placeboに対して異常か**：同日3×3内shuffleのtwo-sided pはLong0.00450、Short0.07696、Small+Illiquid0.00550。Long/cornerには横断shuffle比の信号がある一方、Shortは弱い。全3×3 surfaceのmax-statでcornerのadjusted p=0.606であり、多数cellの表示を個別有意性だけで発見扱いしない。

| group | observed | null_low | null_high | p_positive | p_two_sided |
| --- | --- | --- | --- | --- | --- |
| ALL | 0.000218 | -0.000102 | 0.000114 | 0.000500 | 0.000500 |
| LONG | 0.000282 | -0.000158 | 0.000205 | 0.003998 | 0.004498 |
| SHORT | 0.000141 | -0.000154 | 0.000154 | 0.040480 | 0.076962 |
| CELL3_9 | 0.000327 | -0.000225 | 0.000227 | 0.002999 | 0.005497 |

circular shift結果も全offset/年/cellで保存。これは未来wrapを含むdiagnostic-only placeboでありstrategy inputではない。横断shuffleは日付間依存を保つ経済的null全体を表さず、block bootstrapとの結論差を矛盾とは扱わない。

10. **bootstrapで残るか**：Long/Short/cornerのblock10/20/40 CI下限は全て負。3×3 stock-count weighted pooled effectもblock20 CI=[−1.33,5.94]bp。全年で正のことやpooled pの小ささだけで、時系列不確実性を通過したとは言えない。

| estimand | block | observed | low | high |
| --- | --- | --- | --- | --- |
| LONG | 10 | 0.000282 | -0.000104 | 0.000655 |
| SHORT | 10 | 0.000141 | -0.000262 | 0.000541 |
| CELL3_9 | 10 | 0.000327 | -0.000070 | 0.000712 |
| LONG | 20 | 0.000282 | -0.000102 | 0.000651 |
| SHORT | 20 | 0.000141 | -0.000271 | 0.000532 |
| CELL3_9 | 20 | 0.000327 | -0.000064 | 0.000701 |
| LONG | 40 | 0.000282 | -0.000086 | 0.000656 |
| SHORT | 40 | 0.000141 | -0.000274 | 0.000536 |
| CELL3_9 | 40 | 0.000327 | -0.000055 | 0.000717 |

市場状態では低vol/positive trendで効果が大きい傾向。高volのShort、negative-trendのShortは負、negative-trendのcornerはほぼ0。この異質性は記録するがregime ruleにはしない。カレンダーの符号は概ね安定するため、最終分類は統計的不確実性を主因としたFとする。

| group | regime | state | days | spread | rankic |
| --- | --- | --- | --- | --- | --- |
| CELL3_9 | market_high_vol | 0.0 | 686 | 0.000397 | 0.007501 |
| CELL3_9 | market_high_vol | 1.0 | 589 | 0.000244 | 0.005477 |
| LONG | market_high_vol | 0.0 | 686 | 0.000470 | 0.009315 |
| LONG | market_high_vol | 1.0 | 589 | 0.000062 | 0.002485 |
| SHORT | market_high_vol | 0.0 | 686 | 0.000330 | 0.011468 |
| SHORT | market_high_vol | 1.0 | 589 | -0.000080 | 0.003351 |
| CELL3_9 | market_positive_trend | 0.0 | 515 | 0.000013 | 0.000740 |
| CELL3_9 | market_positive_trend | 1.0 | 760 | 0.000539 | 0.010514 |
| LONG | market_positive_trend | 0.0 | 515 | 0.000171 | 0.004180 |
| LONG | market_positive_trend | 1.0 | 760 | 0.000356 | 0.007501 |
| SHORT | market_positive_trend | 0.0 | 515 | -0.000014 | 0.000809 |
| SHORT | market_positive_trend | 1.0 | 760 | 0.000246 | 0.012400 |

Long/ShortのRM quintileも厳密単調ではない。端点の方向が正でも中間bucketの逆転があり、confirmation効果を単純な単調構造として確定しない。

| group | rm_bin | stock_days | forward_target | annual_net_contribution |
| --- | --- | --- | --- | --- |
| Long | 1.000000 | 45639 | 0.000374 | 0.010057 |
| Long | 2.000000 | 46060 | 0.000617 | 0.015055 |
| Long | 3.000000 | 46126 | 0.000409 | 0.010435 |
| Long | 4.000000 | 46055 | 0.000526 | 0.014715 |
| Long | 5.000000 | 46820 | 0.000886 | 0.025329 |
| Short | 1.000000 | 45643 | -0.000140 | 0.003009 |
| Short | 2.000000 | 46093 | -0.000040 | 0.001924 |
| Short | 3.000000 | 46253 | 0.000028 | -0.000624 |
| Short | 4.000000 | 46093 | 0.000090 | -0.001905 |
| Short | 5.000000 | 46820 | 0.000008 | 0.000100 |

11. **candidate gate**：FAIL。失敗条件はLongとShortのpooled bootstrap lower>0の2項目。他のpooled/EX2016、year sign、3variant方向robustnessの固定条件は通った。Gateを緩和してcandidateを実施していない。

12. **SLOWをafter-costで超えたか**：candidate0本のため未評価。Section17–22のperformance/cost stress/attribution/candidate bootstrapは規定どおりgate依存でSKIP。after-cost優越、Long-only、corner-only、boundary-only、regime switch等の主張/試行はしない。

次実験の仮説メモは「entryで見える大きい点推定のsupport確認」「市場状態の異質性」。このrunでは戦略化・試行追加をせず終了する。

検証はcomponent/official accounting strict parity、全6source未来改変/3cutoff/切詰め/row shuffle/決定的rebuild26ケース、exact809,636行Date/Code coverage、target-free adapter/standalone smoke、t+2 maturity/年末2session purge、source/firewall、関連テスト36件、旧Freeze129 hash照合を完了。

[関連テストログ](../../artifacts/DM-20261004-02/run-20261003T183736Z/logs/related_tests.log)。[make checkログ](../../artifacts/DM-20261004-02/run-20261003T183736Z/logs/make_check.log)。make check自体は既存DM-20261002-04のunknown experiment kindで失敗した。今回metadataとFreeze hashesは別途合格；workspace全体の構成検査合格とは扱わない。再利用されたverification.jsonのlogsは科学原本runを参照する。

全run合計の実測research計算時間=730.83s（12.18分）、peak RSS=3.052GiB。Permutation2,000 draws、bootstrap5,000 draws×2scope×3block=30,000 joint draws（5estimandsで150,000 scalar estimates）。候補/rescue=0/0。submission adapter全Train推論を別計測して5.986s、peak RSS=1.104GiB、研究scoreとbitwise一致。最終完了runは114ファイルを記録し、詳細file hashesはrun.json。clone・コーディング・準備時間はresearch計算実測に含めない。

本番時間はTrain1,814 sessions/473 codes/809,636行の実測から、同程度のuniverseと線形スケーリングを仮定した参考値としてsession比2倍なら約12秒、3倍なら約18秒。Validファイル/metadata/実行は使っていないため本番30分の実測保証ではない。research wall budget3時間とは分離する。

技術履歴：初回は全diagnostic保存後のhash読込がfirewall artifact登録漏れで停止、失敗runを保持。新runで保存済みphaseを引き継ぎ全科学計算を完走。未定義cellのNaN比較が小さいpを生成した8行は、更に別runでNaNへ補正しBHを再集計；元出力/drawを保持、science/candidate再実行0。preflightでは登録スクリプトのPYTHONPATH不足とregime warmupを越えていないテストcutoffを修正し、結果を見てfeature定義を変更していない。

正式な多重検定表は最終runのpermutation_summary_audited.csv / FDR_permutation_audited.csv。原本の未定義cellの数値pは科学的に無効として扱う。共通の入力/feature/設定hashと再開provenanceを保存し、不利な結果を隠して再runしていない。
