# DM-20261003-06: annual OLS on Size / Illiquidity / MOM60 ranks

**REJECT — C: Dilution**。OLS1候補、rescue0。Historical Valid / Validは未読・未評価。Run=`artifacts/DM-20261003-06/run-20261003T153253Z`。

POOLEDのNet SharpeはSLOW 2.094、等ウェイト1.651、OLS 1.494。OLSは等ウェイトより平均日次turnoverを17.3%減らしたが、annual grossも1.676ポイント減り、annual netは1.532ポイント低下した。SLOWに対するfull-year改善は2013の1/5年のみで、固定した採用条件を満たさない。CIは0を含むため、点推定の低下を統計的に確定した劣化とは扱わない。

ユーザーが別実験としてOLS1候補を明示的に指定。等ウェイト版の不採用判定は変更していない。全Trainは既知研究データであり、未使用holdoutとは呼ばない。

Inputは以前とbitwise同一のSizeRank/IlliquidityRank/MOM60Rank。教師は主催者提供のraw residual Return。OLSはintercept+3係数、stock-day等ウェイト、expanding、年1回更新、np.linalg.lstsq(rcond=None)。regularization・係数clip・符号制約・追加smoothingなし。2008の予測scoreは全銘柄0。公式rank処理では同点時のCode順に建玉が生じるため、2008をcash期間とは扱わない。2009–2010はpast-onlyモデルを使用し、連続accounting後の評価対象は2011以降。

## POOLED

| strategy | days | rankic | rankic_t_hac5 | rankic_hit | gross_sharpe | net_sharpe | annual_gross | annual_net | turnover | annual_cost | max_drawdown | annual_long_net | annual_short_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SLOW_CONTROL | 1275 | 0.008257 | 2.802064 | 0.521569 | 2.179334 | 2.093538 | 0.080272 | 0.077119 | 0.012888 | 0.003153 | -0.022099 | 0.075064 | 0.002055 |
| MOM60 | 1275 | 0.007590 | 1.567643 | 0.522353 | 0.613360 | 0.308092 | 0.032108 | 0.016128 | 0.063418 | 0.015981 | -0.097063 | 0.046391 | -0.030263 |
| SLOW_MOM60_EQUAL | 1275 | 0.011162 | 2.894605 | 0.534118 | 1.835759 | 1.651102 | 0.080403 | 0.072311 | 0.032408 | 0.008092 | -0.051932 | 0.074388 | -0.002077 |
| SLOW_MOM60_OLS | 1275 | 0.005440 | 1.754966 | 0.520000 | 1.668740 | 1.494424 | 0.063640 | 0.056990 | 0.026815 | 0.006650 | -0.034044 | 0.065155 | -0.008165 |

## EX2016

| strategy | net_sharpe | annual_gross | annual_net | turnover | annual_cost | max_drawdown | annual_long_net | annual_short_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SLOW_CONTROL | 2.097190 | 0.080307 | 0.077153 | 0.012901 | 0.003153 | -0.022099 | 0.074158 | 0.002996 |
| MOM60 | 0.324348 | 0.032643 | 0.016685 | 0.063327 | 0.015958 | -0.097063 | 0.044555 | -0.027870 |
| SLOW_MOM60_EQUAL | 1.674876 | 0.080936 | 0.072860 | 0.032348 | 0.008077 | -0.051932 | 0.073198 | -0.000339 |
| SLOW_MOM60_OLS | 1.465869 | 0.062766 | 0.055978 | 0.027373 | 0.006788 | -0.034044 | 0.063312 | -0.007334 |

## Annual walk-forward

| strategy | scope | days | net_sharpe | annual_gross | annual_net | turnover | annual_cost | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SLOW_CONTROL | 2011 | 243 | 2.728793 | 0.125949 | 0.122760 | 0.013703 | 0.003189 | -0.021303 |
| SLOW_CONTROL | 2012 | 246 | 1.033654 | 0.037084 | 0.033888 | 0.013052 | 0.003196 | -0.016957 |
| SLOW_CONTROL | 2013 | 243 | 1.896830 | 0.084835 | 0.081311 | 0.014252 | 0.003524 | -0.018996 |
| SLOW_CONTROL | 2014 | 242 | 1.664345 | 0.054300 | 0.051361 | 0.011729 | 0.002939 | -0.022099 |
| SLOW_CONTROL | 2015 | 242 | 3.267066 | 0.099873 | 0.096957 | 0.011756 | 0.002916 | -0.009106 |
| SLOW_CONTROL | 2016 | 59 | 2.003895 | 0.079565 | 0.076413 | 0.012628 | 0.003152 | -0.008544 |
| MOM60 | 2011 | 243 | 0.506792 | 0.046155 | 0.029635 | 0.065571 | 0.016520 | -0.067854 |
| MOM60 | 2012 | 246 | 0.636144 | 0.043206 | 0.026788 | 0.065148 | 0.016417 | -0.042207 |
| MOM60 | 2013 | 243 | 0.081809 | 0.021016 | 0.005051 | 0.063355 | 0.015965 | -0.094273 |
| MOM60 | 2014 | 242 | 0.910504 | 0.042759 | 0.027522 | 0.060468 | 0.015238 | -0.023834 |
| MOM60 | 2015 | 242 | -0.099053 | 0.009896 | -0.005742 | 0.062057 | 0.015638 | -0.051788 |
| MOM60 | 2016 | 59 | 0.067276 | 0.021093 | 0.004639 | 0.065295 | 0.016454 | -0.044982 |
| SLOW_MOM60_EQUAL | 2011 | 243 | 2.259693 | 0.127280 | 0.119342 | 0.032144 | 0.007939 | -0.041731 |
| SLOW_MOM60_EQUAL | 2012 | 246 | 0.985387 | 0.043537 | 0.035107 | 0.033669 | 0.008430 | -0.018593 |
| SLOW_MOM60_EQUAL | 2013 | 243 | 1.134828 | 0.068741 | 0.060390 | 0.033518 | 0.008351 | -0.051932 |
| SLOW_MOM60_EQUAL | 2014 | 242 | 1.946794 | 0.067481 | 0.059515 | 0.031731 | 0.007966 | -0.015988 |
| SLOW_MOM60_EQUAL | 2015 | 242 | 2.223448 | 0.098120 | 0.090429 | 0.030654 | 0.007691 | -0.021422 |
| SLOW_MOM60_EQUAL | 2016 | 59 | 1.222913 | 0.069420 | 0.061004 | 0.033635 | 0.008416 | -0.020015 |
| SLOW_MOM60_OLS | 2011 | 243 | 0.823418 | 0.054612 | 0.041747 | 0.052290 | 0.012866 | -0.034044 |
| SLOW_MOM60_OLS | 2012 | 246 | 0.575744 | 0.026468 | 0.019705 | 0.027222 | 0.006763 | -0.024931 |
| SLOW_MOM60_OLS | 2013 | 243 | 2.003962 | 0.089092 | 0.083665 | 0.021856 | 0.005427 | -0.018808 |
| SLOW_MOM60_OLS | 2014 | 242 | 1.381180 | 0.047352 | 0.042794 | 0.018214 | 0.004558 | -0.026742 |
| SLOW_MOM60_OLS | 2015 | 242 | 3.164912 | 0.096831 | 0.092525 | 0.017205 | 0.004306 | -0.009436 |
| SLOW_MOM60_OLS | 2016 | 59 | 2.085466 | 0.081644 | 0.077836 | 0.015321 | 0.003808 | -0.008364 |

2011–2015 Net Sharpe改善 vs SLOW: **1/5**。2016 partialは除外。Q1–Q5/monotonicity、Long/Short gross/netとすべての期間実額はmetrics.csvに保存。

| strategy | q1_daily_return | q2_daily_return | q3_daily_return | q4_daily_return | q5_daily_return | q_monotonicity | annual_long | annual_long_net | annual_short | annual_short_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SLOW_CONTROL | -0.000061 | 0.000040 | 0.000281 | 0.000420 | 0.000711 | 1.000000 | 0.076748 | 0.075064 | 0.003525 | 0.002055 |
| MOM60 | 0.000160 | 0.000208 | 0.000191 | 0.000348 | 0.000473 | 0.900000 | 0.054443 | 0.046391 | -0.022335 | -0.030263 |
| SLOW_MOM60_EQUAL | -0.000059 | 0.000075 | 0.000196 | 0.000475 | 0.000703 | 1.000000 | 0.078555 | 0.074388 | 0.001848 | -0.002077 |
| SLOW_MOM60_OLS | -0.000009 | 0.000138 | 0.000283 | 0.000310 | 0.000669 | 1.000000 | 0.068655 | 0.065155 | -0.005015 | -0.008165 |

## Learned coefficients and stability

| year | rows | training_sessions | design_rank | condition_number | intercept | SizeRank | IlliquidityRank | MOM60Rank | MOM60Rank_signed_abs_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2009 | 15613 | 37 | 2 | nan | 0.000908 | -0.000154 | 0.000000 | 0.000000 | 0.000000 |
| 2010 | 119441 | 280 | 4 | 3.579950 | 0.000545 | 0.000449 | 0.000015 | -0.000370 | -0.443416 |
| 2011 | 224980 | 525 | 4 | 4.013417 | 0.000371 | 0.000472 | -0.000071 | -0.000375 | -0.407982 |
| 2012 | 331885 | 770 | 4 | 4.180169 | 0.000404 | 0.000556 | -0.000005 | -0.000164 | -0.225945 |
| 2013 | 441024 | 1018 | 4 | 4.248241 | 0.000303 | 0.000487 | -0.000022 | -0.000057 | -0.100866 |
| 2014 | 550105 | 1263 | 4 | 4.291031 | 0.000282 | 0.000548 | -0.000082 | -0.000022 | -0.033388 |
| 2015 | 661570 | 1507 | 4 | 4.411977 | 0.000282 | 0.000472 | -0.000016 | 0.000016 | 0.031853 |
| 2016 | 774611 | 1751 | 4 | 4.500930 | 0.000294 | 0.000412 | 0.000080 | 0.000014 | 0.027503 |

係数はsame-scale rankの条件付き寄与で、portfolio sleeve weightsではない。signed_abs_shareはβ/sum(abs(3β))という参考表示のみ。負符号もOLSの推定結果として保持し、成績を見て変更しない。warmupのrank deficiencyは固定lstsq最小ノルム、後年のcondition/rankも保存。

MOM60係数は評価年2011–2014に負、2015–2016に小幅な正。Illiquidityも2011–2015は負だった。Sizeと併用した過去データ上の条件付き推定であり、単純な正方向の3因子合成とは異なる。これらの符号だけから将来の反転効果や今回の成績低下の原因を確定しない。

## Incremental gross / cost

| comparison | scope | delta_rankic | delta_gross_sharpe | delta_net_sharpe | delta_annual_gross | delta_annual_cost | delta_annual_net | delta_turnover | delta_annual_long_net | delta_annual_short_net | delta_max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SLOW_MOM60_OLS-SLOW_CONTROL | POOLED | -0.002816 | -0.510594 | -0.599114 | -0.016633 | 0.003497 | -0.020129 | 0.013927 | -0.009910 | -0.010220 | -0.011945 |
| SLOW_MOM60_OLS-SLOW_MOM60_EQUAL | POOLED | -0.005722 | -0.167019 | -0.156678 | -0.016764 | -0.001443 | -0.015321 | -0.005593 | -0.009234 | -0.006087 | 0.017887 |
| SLOW_MOM60_OLS-MOM60 | POOLED | -0.002149 | 1.055380 | 1.186331 | 0.031531 | -0.009331 | 0.040862 | -0.036603 | 0.018764 | 0.022098 | 0.063019 |
| SLOW_MOM60_OLS-SLOW_CONTROL | EX2016 | -0.002900 | -0.539542 | -0.631320 | -0.017541 | 0.003634 | -0.021175 | 0.014472 | -0.010845 | -0.010330 | -0.011945 |
| SLOW_MOM60_OLS-SLOW_MOM60_EQUAL | EX2016 | -0.005816 | -0.216875 | -0.209007 | -0.018170 | -0.001289 | -0.016881 | -0.004976 | -0.009886 | -0.006995 | 0.017887 |
| SLOW_MOM60_OLS-MOM60 | EX2016 | -0.002236 | 1.009002 | 1.141522 | 0.030123 | -0.009170 | 0.039293 | -0.035955 | 0.018757 | 0.020536 | 0.063019 |

| scope | SLOW_turnover | EQUAL_turnover | OLS_turnover | OLS_SLOW_turnover_ratio | incremental_annual_gross | incremental_annual_cost | incremental_annual_net | incremental_gross_cost_ratio | incremental_gross_gt_cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POOLED | 0.012888 | 0.032408 | 0.026815 | 2.080598 | -0.016633 | 0.003497 | -0.020129 | -4.756929 | False |
| EX2016 | 0.012901 | 0.032348 | 0.027373 | 2.121791 | -0.017541 | 0.003634 | -0.021175 | -4.826352 | False |
| 2011 | 0.013703 | 0.032144 | 0.052290 | 3.815999 | -0.071336 | 0.009677 | -0.081013 | -7.372031 | False |
| 2012 | 0.013052 | 0.033669 | 0.027222 | 2.085613 | -0.010616 | 0.003567 | -0.014183 | -2.976245 | False |
| 2013 | 0.014252 | 0.033518 | 0.021856 | 1.533488 | 0.004257 | 0.001903 | 0.002355 | 2.237641 | True |
| 2014 | 0.011729 | 0.031731 | 0.018214 | 1.552927 | -0.006948 | 0.001619 | -0.008567 | -4.291255 | False |
| 2015 | 0.011756 | 0.030654 | 0.017205 | 1.463457 | -0.003042 | 0.001390 | -0.004432 | -2.189200 | False |
| 2016 | 0.012628 | 0.033635 | 0.015321 | 1.213270 | 0.002079 | 0.000656 | 0.001423 | 3.169268 | True |

POOLED OLS−SLOW: Δannual gross=-166.33bp、Δannual cost=34.97bp、Δannual net=-201.29bp。Δgross>Δcost=False。turnover ratio=2.080598。

OLSはraw return squared errorを最小化し、cost/Net Sharpeを直接最適化しない。観測Δgrossはweight再配分の損益差、Δcostは公式turnover差。Δnet=Δgross−Δcostを照合。追加gross alphaとcost節約を区別し、係数の大小や低相関だけで採用しない。

## Bootstrap and fixed gates

paired circular20 sessions、reps2000、seed20261003、95% percentile。Primary pooled OLS−SLOW ΔNetSR=-0.599114、CI=[-1.229396,0.033688]。Secondary OLS−EQUAL=-0.156678、CI=[-1.151389,0.942468]。MOM referenceとEX2016も保存。実現walk-forward日次損益に条件付けたCIで、bootstrapでモデルを再fitせず、既知Trainの学習/選択不確実性全体を表すものではない。

| gate | passed |
| --- | --- |
| full_year_net_sharpe_improvements_ge4 | False |
| POOLED_net_sharpe_gt_slow | False |
| POOLED_annual_net_ge_slow | False |
| POOLED_long_net_gt0 | True |
| POOLED_short_net_ge_slow | False |
| POOLED_maxdd_magnitude_le_slow | False |
| POOLED_turnover_le_1p50_slow | False |
| POOLED_incremental_gross_gt_incremental_cost | False |
| EX2016_net_sharpe_gt_slow | False |
| EX2016_annual_net_ge_slow | False |
| EX2016_long_net_gt0 | True |
| EX2016_short_net_ge_slow | False |
| EX2016_maxdd_magnitude_le_slow | False |
| EX2016_turnover_le_1p50_slow | False |
| EX2016_incremental_gross_gt_incremental_cost | False |
| primary_bootstrap_lower_gt0 | False |

採否: **REJECT**。前回と同じSLOW比較gateをすべて要求し、等ウェイト版を上回るだけでは採用しない。追加候補・Ridge・window/target/weight searchは実行せず終了。

## Causality / contract / reproducibility

全6特徴入力源とTrain labelsを個別/同時にfuture-mutateし、truncation、row shuffle、決定的再fitを検証。feature/raw/normalized/rank/予測とprefixで利用される全annual model records/係数bitsが完全一致。label改変はt+2 maturity>cutoffで決め、prefix最後2signalの未成熟targetも変更。固定モデルだけの監査ではない。モデルごとの最大label maturity<fold first prediction dayを記録。

targetのない6ファイルstageでstored-artifact inferenceがresearchとbitwise一致し、standalone adapterもsmoke。全入力Date/Code index、finite coverage、NaN/inf、source scanとTrain-only firewall、Valid/raw target拒否を確認。新candidateのweightとdaily Netは公式compute_weight/compute_plとuint64 bits一致。controlsは同一入力/target/scoreと同じaccounting関数を持つ前実験の保存済み結果をhash固定して再利用。

Continuous full-panel建玉でaccounting後、各年最後2exchange sessionsをpurge。Sharpe=mean/sample SD×sqrt252、IC=daily average-tie Spearman、t=HAC5 Bartlett、annual=mean×252、period=実額。Compound DDはwealth1、Q1→Q5はscore昇順、Long=Q4/Q5、Short=Q1/Q2。公式missing-target行のcost欠落を再現し、all-position costも併記。

make checkは既存DM-20261002-04 metadata種別で失敗。新experimentのmetadataと既存Freeze129 hashは別途照合；全workspace構成検査を合格とは扱わない。監査は試した入力/cutoffの証拠であり普遍的な数学的証明ではない。

関連テスト39件、再学習を含むprefix監査29ケースは合格。coverageは809,636行・1,814日・473銘柄で100%。保存モデルによるtarget不要の推論と研究予測のbitwise一致も確認。

科学計算の原本は`artifacts/DM-20261003-06/run-20261003T152501Z`。採否・全監査を保存後、レポートの係数列名の誤記だけで終了した。completion runでは表示関数のみ修正し、原本から科学成果物をSHA256完全一致で複製して報告を完了した。学習・backtest・bootstrap・監査の再実行は0、累計候補試行は1。詳細は`audit/report_completion_provenance.json`。

科学計算Elapsed=122.46s、peak RSS=2308.1MiB、deadline1800s。報告completionのみ0.39s。コード/入力/config/モデル/予測/metrics/auditとlibrary versionsをrun.jsonに記録。Valid/zip/release/外部提出は実施していない。
