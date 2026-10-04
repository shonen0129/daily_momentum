# DM-20261003-05: Size / Illiquidity / MOM60 fixed 1:1:1

**REJECT: B. Gross-only improvement**。固定候補1本、rescue0本。Historical Valid / Validは未読・未評価。

Completion run: `artifacts/DM-20261003-05/run-20261003T144512Z`。科学的performance source runはrun.jsonのscientific_source_runを参照。計画・設定・コードの事前hash、各段階のhash、入力・環境・成果物hashを保存。全Trainは既知研究データであり、未使用holdoutではない。

Performance source: `artifacts/DM-20261003-05/run-20261003T143918Z`。このrunだけで候補の性能を評価し、completionは予測・全metrics・bootstrapをhash一致のまま保存結果から引き継いだ。

目的は強い既存Size/Illiquidityへplain residual MOM60を独立factorとして追加するafter-cost増分。Size単独/Illiquidity単独のportfolioは作成していない。

SLOW原仕様のnormalized SizeとIlliquidity、SLOW_CONTROL、保存済みMOM60およびDM-20260908-v1のTrain予測とstrict bitwise一致。SLOWはzscore(mean(z_size,z_amihud))として完全再構築。raw値も有限値bitsと欠損位置が完全一致。raw SizeのNaN符号はParquet null保存で失われるため、raw診断の保存表現だけ明示的にcanonical NaNへ統一し照合（signalを変更しない）。

候補は各最終factorにsame-date average-tie percentile p→2*(p−mean(p))を適用し、3factorの算術平均。追加smoothingなし。これは0.5×SLOW_CONTROL+0.5×MOM60とも、portfolio weightsの混合とも異なる。

## Primary evaluation: POOLED

| strategy | days | rankic | rankic_t_hac5 | rankic_hit | gross_sharpe | net_sharpe | annual_gross | annual_net | turnover | annual_cost | max_drawdown | annual_long_net | annual_short_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SLOW_CONTROL | 1275 | 0.008257 | 2.802064 | 0.521569 | 2.179334 | 2.093538 | 0.080272 | 0.077119 | 0.012888 | 0.003153 | -0.022099 | 0.075064 | 0.002055 |
| MOM60 | 1275 | 0.007590 | 1.567643 | 0.522353 | 0.613360 | 0.308092 | 0.032108 | 0.016128 | 0.063418 | 0.015981 | -0.097063 | 0.046391 | -0.030263 |
| SLOW_MOM60_EQUAL | 1275 | 0.011162 | 2.894605 | 0.534118 | 1.835759 | 1.651102 | 0.080403 | 0.072311 | 0.032408 | 0.008092 | -0.051932 | 0.074388 | -0.002077 |

| strategy | Q1 daily return | Q2 | Q3 | Q4 | Q5 | Q monotonicity | annual Long gross | Long net | annual Short gross | Short net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SLOW_CONTROL | -0.000061 | 0.000040 | 0.000281 | 0.000420 | 0.000711 | 1.000000 | 0.076748 | 0.075064 | 0.003525 | 0.002055 |
| MOM60 | 0.000160 | 0.000208 | 0.000191 | 0.000348 | 0.000473 | 0.900000 | 0.054443 | 0.046391 | -0.022335 | -0.030263 |
| SLOW_MOM60_EQUAL | -0.000059 | 0.000075 | 0.000196 | 0.000475 | 0.000703 | 1.000000 | 0.078555 | 0.074388 | 0.001848 | -0.002077 |

## EX2016

| strategy | net_sharpe | annual_gross | annual_net | turnover | annual_cost | max_drawdown | annual_long_net | annual_short_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SLOW_CONTROL | 2.097190 | 0.080307 | 0.077153 | 0.012901 | 0.003153 | -0.022099 | 0.074158 | 0.002996 |
| MOM60 | 0.324348 | 0.032643 | 0.016685 | 0.063327 | 0.015958 | -0.097063 | 0.044555 | -0.027870 |
| SLOW_MOM60_EQUAL | 1.674876 | 0.080936 | 0.072860 | 0.032348 | 0.008077 | -0.051932 | 0.073198 | -0.000339 |

## Annual folds

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

2011–2015 Net Sharpe改善: **1/5**。2016は部分年で安定性gateに含めない。全期間のIC/Q/Long/Short指標はmetrics/metrics.csv、候補−SLOWと候補−MOM60はmetrics/incremental.csv。

## Orthogonality saved before candidate trial

| component_a | component_b | days | mean_daily_spearman |
| --- | --- | --- | --- |
| Size | Illiquidity | 1275 | 0.864822 |
| Size | MOM60 | 1275 | 0.031965 |
| Size | SLOW_CONTROL | 1275 | 0.975070 |
| Illiquidity | MOM60 | 1275 | 0.087989 |
| Illiquidity | SLOW_CONTROL | 1275 | 0.925570 |
| MOM60 | SLOW_CONTROL | 1275 | 0.044647 |

SLOW/MOM pooled daily Gross P/L correlation=0.190578、Net=0.190354。Long Jaccard=0.257122、Short=0.262403、drawdown depth correlation=0.175198。

daily cross-sectional Spearman、pooled/年別平均、daily mean matrixとstacked stock-day Pearson/Spearman matrixを別ファイルで保存。年別P/L/Jaccard/DDはpl_orthogonality_summary.csv。低相関自体は採用根拠にしない。

## Incremental gross / portfolio reshuffling / cost

| scope | delta_rankic | delta_gross_sharpe | delta_net_sharpe | delta_annual_gross | delta_annual_cost | delta_annual_net | delta_turnover | delta_annual_long_net | delta_annual_short_net | delta_max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POOLED | 0.002905 | -0.343575 | -0.442436 | 0.000131 | 0.004939 | -0.004808 | 0.019520 | -0.000676 | -0.004132 | -0.029833 |
| EX2016 | 0.002916 | -0.322667 | -0.422313 | 0.000630 | 0.004923 | -0.004294 | 0.019448 | -0.000959 | -0.003334 | -0.029833 |

| scope | slow_turnover | mom60_turnover | candidate_turnover | candidate_slow_turnover_ratio | incremental_annual_gross | incremental_annual_cost | incremental_annual_net | incremental_gross_cost_ratio | incremental_gross_gt_cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POOLED | 0.012888 | 0.063418 | 0.032408 | 2.514549 | 0.000131 | 0.004939 | -0.004808 | 0.026555 | False |
| EX2016 | 0.012901 | 0.063327 | 0.032348 | 2.507474 | 0.000630 | 0.004923 | -0.004294 | 0.127907 | False |
| 2011 | 0.013703 | 0.065571 | 0.032144 | 2.345801 | 0.001332 | 0.004750 | -0.003418 | 0.280357 | False |
| 2012 | 0.013052 | 0.065148 | 0.033669 | 2.579591 | 0.006453 | 0.005234 | 0.001219 | 1.232827 | True |
| 2013 | 0.014252 | 0.063355 | 0.033518 | 2.351773 | -0.016093 | 0.004827 | -0.020920 | -3.334159 | False |
| 2014 | 0.011729 | 0.060468 | 0.031731 | 2.705364 | 0.013181 | 0.005027 | 0.008154 | 2.621853 | True |
| 2015 | 0.011756 | 0.062057 | 0.030654 | 2.607413 | -0.001753 | 0.004775 | -0.006528 | -0.367153 | False |
| 2016 | 0.012628 | 0.065295 | 0.033635 | 2.663507 | -0.010145 | 0.005264 | -0.015408 | -1.927334 | False |

POOLED Δannual gross=0.000131、Δannual cost=0.004939、Δannual net=-0.004808。Δgross>Δcost: **False**。candidate/SLOW turnover=2.514549。

年率Grossの微増は**1.31bp**にとどまり、追加cost **49.39bp**の約**2.66%**しか補えない。年率Netは**48.08bp低下**。B分類はこの年率Grossの微増を指し、Gross Sharpe自体も2.179334→1.835759へ悪化している。低相関とRankIC上昇が、経済的に有効な追加alphaを保証する結果ではない。Long net差は-6.76bp、Short net差は-41.32bpで、Net悪化の大部分はShort側。

Δgrossは同じtargetに対するweight差の損益、Δcostはofficial weight変更によるcost差。Δnet=Δgross−Δcostを照合。Δgrossだけで情報alphaと因果的に断定せず、portfolio再配分も含む観測差とする。

## Momentum contribution

公式Long(Q4/Q5)/Short(Q1/Q2) membershipで5固定groupに分類。stock-days、forward target mean、candidate gross/net、Δgross/Δnet vs SLOW、turnover/costをmomentum_contribution_summary.csvに保存。日次表・stock-day parquetも保存。OTHERを含むpartitionが全公式帳簿に一致し、中立化時の退出costも残る。group結果からveto/filterは作成していない。

| group (POOLED) | stock-days | forward target mean | candidate annual gross | candidate annual net | Δannual gross vs SLOW | Δannual net vs SLOW | candidate daily turnover contribution |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BOTH_HIGH | 94115 | 0.000715 | 0.046952 | 0.046264 | 0.005654 | 0.005473 | 0.002728 |
| SLOW_HIGH_MOM_LOW | 89717 | 0.000480 | 0.012020 | 0.010436 | -0.011674 | -0.012813 | 0.006288 |
| SLOW_LOW_MOM_HIGH | 88220 | 0.000081 | -0.001524 | -0.002918 | 0.001137 | 0.000202 | 0.005534 |
| BOTH_LOW | 95617 | -0.000076 | 0.005143 | 0.004436 | 0.000263 | -0.000050 | 0.002809 |
| OTHER | 208866 | 0.000240 | 0.017813 | 0.014094 | 0.004751 | 0.002380 | 0.015049 |

主な負の寄与はSLOW_HIGH_MOM_LOW（年率Δnet=-128.13bp）で、BOTH_HIGHとOTHERの正の寄与を上回った。これは固定候補の事後診断であり、group選択やvetoの根拠として使用しない。各groupのannual contributionは全1275評価日の平均×252で、該当groupの日だけに分母を絞っていない。stock-days合計576535、日次/期間/年率の和は公式帳簿に照合済み。

## Bootstrap and adoption gates

paired circular moving-block20 sessions、2000 reps、seed20261003、95% percentile CI。Primary pooled ΔNet Sharpe vs SLOW=-0.442436、CI=[-1.007035, 0.119568]。Secondary vs MOM60=1.343009、CI=[0.750359, 1.951226]。EX2016も保存。

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

解釈: **B. Gross-only improvement**。指定gateの全通過を要求し、低相関・IC・Grossの改善だけでは採用しない。SLOW単独を維持し、この固定候補の研究を終了する。

## Accounting and causality

日次公式global ranking: sorted Code first ties→five quintiles、weight=(Qindex−2)/N/1.2。Longは上位2分位、Shortは下位2分位。weightとdaily Netは公式compute_weight/compute_plとbitwise一致。欠測target行は公式式がcostも落とすため同じ処理を維持し、cost_all/net_all_costを別記。

全連続入力panelでaccountingした後、各年最後2営業日をpurge。t+2 maturityをprovided raw_return−beta×TOPIXの評価専用再構築で確認。年間値は日次平均×252（2016も年率換算）；period_*は期間実額。Sharpeはddof1×sqrt252、RankICはdaily average-tie Spearman、tはHAC5 Bartlett、Q単調性はQ1–Q5平均returnと順序のSpearman。MaxDDは初期wealth1の複利net、additive DDも保存。

全6入力源のfuture mutationを個別/同時で3cutoff、truncation、row shuffle、deterministic rebuild、raw/normalized/preEWMA/final component/rank/scoreのstrict bits検査。予測はtargetを受け取らず、targetがないTrain-only feature stageのadapter実行でも完全一致。source scan、Train-only firewallの拒否確認、coverage/index、関連回帰を保存。MOM4関数は凍結sourceと同じで、旧auditに加えて今回も動的検査した。

26監査caseすべてPASS、全809636入力stock-days・1814日・473銘柄へのfinite予測coverage=100%。関連回帰29件PASS、新実験metadata PASS、既存Freezeの129 file hashes PASS。最終成果物69ファイルのhash、3戦略×8期間の必須指標の有限性、保存済み科学的結果のhash不変も確認した。

make checkは既存DM-20261002-04の未対応experiment kindで失敗（今回変更以前にも再現）。その文書・設定・Valid結果は変更せず、今回のmetadataと全既存Freeze hashを別途検証。全workspace構成検査を合格と扱わない。audit/verification.jsonとlogs/make_check.logに制約を記録。

動的監査は試した入力・境界に対する証拠であり普遍的証明ではない。学習・新パラメータ探索なし。公式集約とgroup/side和は明示toleranceで照合し、score bitwiseと区別する。

Completion/audit elapsed=103.02s、peak RSS=2578.1MiB。実験期限1800秒。performance source runはbootstrap後に監査の未来行timezone不具合で停止；同一の保存済みmetrics/予測/bootstrapをhash一致で引き継いだ。追加performance trialは0、累積1本。失敗runは保持し、戦略source/config/gateは変更していない。source runの終了前peak RSSは未記録であり、ここでのRSSはcompletion/auditの実測値。提出zip/採点環境30分保証/Valid評価は依頼範囲外。
