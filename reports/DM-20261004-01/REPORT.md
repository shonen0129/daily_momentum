# DM-20261004-01: SLOW_CONTROLのSize / Illiquidity収益源診断

**診断分類: F. Inconclusive（単一の源泉へ厳密に分離する点について）。** 実際のportfolio挙動はSize寄り、Long収益は共通Small–Illiquid群へ集中する。一方、Small内のIlliquidity spreadは正で、純粋な「Sizeだけ」では説明しきれない。線形残差はSizeが正、Illiquidityが弱い。この非対称性を併記し、A/C/D/Eの条件を満たしたと扱わない。

診断bundle1回、submission candidate0、結果後の定義/weight/window/threshold/filter変更0。Historical Valid / Validは未読・未評価。元SLOWと提出物は変更していない。全Trainは既知研究データであり、未使用holdoutではない。

## 1. 実験と完全一致

Run: `artifacts/DM-20261004-01/run-20261003T172950Z`。JST2026-10-04、UTC run名2026-10-03。plan/config/codeを結果前にhash固定。2008-11-04..2016-03-31を履歴に用い、2011..2015と2016部分年を評価。各年最後2営業日をt+2満期に基づきpurge、POOLED 1275日、EX2016 1216日、2016部分年59日。

原SLOWのraw Size/Amihud、1/99linear winsor、同日median/0欠損処理、sample zを再利用。Size=-log(raw Close×PIT shares)、Amihud=abs(provided raw_return)/positive TurnoverValueの60営業日平均/min40。「min40」は最少観測数であり、40で割る定義ではない。SLOW=z_cs((z_size+z_amihud)/2)。追加smoothingなし。

正規化components/保存SLOW score/再構築SLOW/公式weights/公式daily Netにstrict uint64一致。元実験の保存daily Netも全1814履歴日でstrict一致（CSV round_trip）。既存weightファイルはなく、保存scoreから公式compute_weightで再生成して照合。raw有限値bitsと欠損位置も完全一致；Parquet nullが保持しないraw NaN符号/payloadだけcanonical-null表現で照合し、最終signalの照合は無許容差。全809636 stock-days、473銘柄、signal coverage100%。

## 2. Standalone official accounting

| strategy | days | rankic | rankic_t_hac5 | rankic_hit | gross_sharpe | net_sharpe | annual_gross | annual_net | turnover | annual_cost | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SIZE_ONLY | 1275 | 0.008034 | 2.682524 | 0.529412 | 2.169020 | 2.069070 | 0.080691 | 0.076973 | 0.015168 | 0.003718 | -0.024631 |
| ILLIQ_ONLY | 1275 | 0.008962 | 2.818825 | 0.520784 | 1.932614 | 1.842911 | 0.075265 | 0.071776 | 0.013954 | 0.003489 | -0.031298 |
| SLOW_CONTROL | 1275 | 0.008257 | 2.802064 | 0.521569 | 2.179334 | 2.093538 | 0.080272 | 0.077119 | 0.012888 | 0.003153 | -0.022099 |

Size単独とSLOWのNetSR差は0.024468、年率Net差は0.000146（1.46bp）。Illiquidity単独も正のNet/RankICがあるが、これ自体はSizeと独立したalphaの証明にならない。SLOW turnoverはSize単独より15.03%、Illiquidity単独より7.64%低い。対SizeのGrossは約4.19bp低いがCostは約5.65bp低く、年率Netの1.46bp改善は主にcost節約で残る。

| strategy | q1_daily_return | q2_daily_return | q3_daily_return | q4_daily_return | q5_daily_return | q_monotonicity | annual_long | annual_long_net | annual_short | annual_short_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SIZE_ONLY | -0.000043 | 0.000049 | 0.000246 | 0.000380 | 0.000760 | 1.000000 | 0.079070 | 0.076921 | 0.001620 | 0.000052 |
| ILLIQ_ONLY | -0.000053 | 0.000114 | 0.000219 | 0.000410 | 0.000700 | 1.000000 | 0.075554 | 0.073817 | -0.000288 | -0.002041 |
| SLOW_CONTROL | -0.000061 | 0.000040 | 0.000281 | 0.000420 | 0.000711 | 1.000000 | 0.076748 | 0.075064 | 0.003525 | 0.002055 |

全3strategy×8期間の全必須指標は `metrics/performance_metrics.csv`。Long/ShortはQ4/Q5とQ1/Q2、±side gross/netの寄与は公式資本に対する年率値。EX2016も年別値も同じ定義。MOM60は保存baselineの参考差分だけを `incremental_reference.csv` に残し、今回の診断strategyとして追加していない。

## 3. Correlation / overlap / common component

| scope | mean_daily_spearman | mean_daily_pearson | stacked_spearman | stacked_pearson | mean_daily_score_difference_cs_std | mean_daily_rank_difference_cs_std |
| --- | --- | --- | --- | --- | --- | --- |
| POOLED | 0.864822 | 0.426128 | 0.789951 | 0.429610 | 1.061826 | 0.299707 |
| EX2016 | 0.864034 | 0.416125 | 0.789920 | 0.419321 | 1.071739 | 0.300575 |
| 2011 | 0.858411 | 0.291659 | 0.821727 | 0.291643 | 1.189996 | 0.307285 |
| 2012 | 0.847573 | 0.261404 | 0.802683 | 0.261391 | 1.215172 | 0.319024 |
| 2013 | 0.846316 | 0.373791 | 0.802924 | 0.374753 | 1.115059 | 0.319933 |
| 2014 | 0.887256 | 0.575973 | 0.881035 | 0.576014 | 0.920539 | 0.274287 |
| 2015 | 0.880982 | 0.581044 | 0.872389 | 0.581048 | 0.914890 | 0.281934 |
| 2016 partial | 0.881059 | 0.632300 | 0.878939 | 0.632300 | 0.857511 | 0.281813 |

平均daily Spearman0.864822は同じ銘柄をrankする傾向を示す。一方、z componentのPearson0.426128はかなり低く、順位の近さを同じ線形scale/exposureと同一視できない。z_amihudの分布の歪みとstandardizationの形が残差診断へ影響しうる。stock-day stacked相関とdaily平均相関は別推定量で、後者は日ごと等重み。Size−Illiquidityの断面std/RMSとrank差stdを日次・年別に保存。

| book_a | book_b | long_jaccard | short_jaccard | long_overlap_over_min | short_overlap_over_min |
| --- | --- | --- | --- | --- | --- |
| ILLIQ_ONLY | SLOW_CONTROL | 0.740401 | 0.747757 | 0.850124 | 0.855443 |
| SIZE_ONLY | ILLIQ_ONLY | 0.656950 | 0.708449 | 0.792711 | 0.829194 |
| SIZE_ONLY | SLOW_CONTROL | 0.882882 | 0.936281 | 0.937496 | 0.967012 |

SLOWはSizeとLong93.75%、Short96.70%のside overlap/minを持つ。Illiquidityとの対応値85.01%、85.54%より高い。

| group | stock_days | forward_target_mean | annual_SIZE_ONLY_gross | annual_SIZE_ONLY_net | annual_ILLIQ_ONLY_gross | annual_ILLIQ_ONLY_net | annual_SLOW_CONTROL_gross | annual_SLOW_CONTROL_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BOTH_LONG | 182902 | 0.000639 | 0.073078 | 0.072096 | 0.071345 | 0.070514 | 0.071400 | 0.070631 |
| SIZE_ONLY_LONG | 37233 | 0.000267 | 0.004271 | 0.003891 | 0.000000 | -0.000330 | 0.002789 | 0.002341 |
| ILLIQ_ONLY_LONG | 37657 | 0.000314 | 0.000000 | -0.000360 | 0.004430 | 0.004126 | 0.001435 | 0.001128 |
| BOTH_SHORT | 191457 | 0.000011 | 0.000585 | -0.000175 | 0.001120 | 0.000214 | 0.001362 | 0.000807 |
| SIZE_ONLY_SHORT | 29304 | -0.000032 | 0.000485 | 0.000247 | 0.000000 | -0.000279 | 0.000556 | 0.000365 |
| ILLIQ_ONLY_SHORT | 28880 | 0.000015 | 0.000000 | -0.000321 | 0.000437 | 0.000192 | 0.000474 | 0.000081 |
| SIGNAL_DISAGREEMENT | 20706 | 0.000209 | 0.002271 | 0.002023 | -0.002068 | -0.002247 | 0.002309 | 0.002064 |
| OTHER | 48396 | 0.000336 | 0.000000 | -0.000427 | 0.000000 | -0.000415 | -0.000053 | -0.000299 |

BOTH_LONGのSLOW年率Net寄与=0.070631、全SLOW Netの91.59%。BOTH_LONG+BOTH_SHORTで92.63%。これは両単独公式booksが同じsideに置く銘柄への収益集中であり、潜在共通factorの因果分解ではない。

分類は排他的で全576535評価stock-daysを覆う。SIGNAL_DISAGREEMENTは逆符号の両book、*_ONLY_LONG/SHORTは片方activeで他方neutral、OTHERは両方neutral。中立退出costも当日のgroupへ残す。group日次/stock-day/期間/年率表を保存し、フィルターは作らない。

| scope | common_slow_spearman | common_slow_pearson | weight_equal_fraction | weight_abs_difference |
| --- | --- | --- | --- | --- |
| POOLED | 0.984282 | 0.853054 | 0.850594 | 0.126433 |

COMMON=(SizeRank+IlliquidityRank)/2、Rank=2×(同日average-tie percentile−同日平均)。SLOWはz値平均なので、COMMONとSLOWのscore/weightはbitwise不一致。Spearman0.984282でもweight一致は85.06%、日次L1weight差0.126433。これは異なる定義を維持した診断結果であり、原SLOW parity失敗ではない。定義を変更して一致させていない。

## 4. Conditional spreads / residual information

| direction | conditioning_bucket | annual_spread | hac5_t | gross_sharpe | finite_spread_days |
| --- | --- | --- | --- | --- | --- |
| Illiquidity_within_Size | Large | 0.027347 | 0.835203 | 0.342176 | 1275 |
| Illiquidity_within_Size | Mid | 0.059107 | 1.433444 | 0.627524 | 1275 |
| Illiquidity_within_Size | Small | 0.118911 | 3.341292 | 1.427589 | 1275 |
| Size_within_Illiquidity | Illiquid | 0.160240 | 4.331269 | 1.855333 | 1275 |
| Size_within_Illiquidity | Liquid | 0.030684 | 0.916194 | 0.404947 | 1275 |
| Size_within_Illiquidity | Mid | 0.067533 | 1.694977 | 0.747537 | 1275 |

同日tercile固定→bucket内で他factorを再rank→High−Lowの等重みforward residual return。条件付きSizeはIlliquid内で年率16.024%、HAC5t4.331、条件付きIlliquidityはSmall内で11.891%、t3.341。Mid/LargeまたはLiquid/Midでの証拠は弱い。Small内のIlliquidity spreadは2011–2015の4/5年が正で、2013だけ負。Illiquid内Size spreadは5/5年が正。2016partialは短く両方とも弱いため、全年度の確認扱いにしない。

固定tercileは粗いSize/Liquidity統制であり、同じbucket内にも相手factorと相関するSize/Illiquidity差が残る。独立した因果効果やコスト控除後portfolioとは呼ばない。SpreadのGross Sharpeは未コスト控除等重み差分系列のSharpe。

| signal | rankic | rankic_hac5_t | rankic_hit | q5_minus_q1 | annual_spread | spread_hac5_t | gross_sharpe_spread | t1 | t2 | t3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| COMMON | 0.008804 | 2.861352 | 0.520784 | 0.000751 | 0.189317 | 4.982065 | 1.959982 | nan | nan | nan |
| DISAGREEMENT | -0.002391 | -0.697064 | 0.506667 | 0.000024 | 0.006173 | nan | nan | 0.000204 | 0.000352 | 0.000278 |
| RESIDUAL_ILLIQ | -0.001451 | -0.630033 | 0.498824 | -0.000096 | -0.024238 | -0.814468 | -0.340702 | nan | nan | nan |
| RESIDUAL_SIZE | 0.006466 | 2.275831 | 0.514510 | 0.000598 | 0.150606 | 4.280613 | 1.667765 | nan | nan | nan |

各dateでnormalized Sizeをintercept+IlliquidityへOLSし、逆も同様。targetを回帰に入れない。Residual Size RankIC0.006466(t2.276)、Q5−Q1年率15.061%(t4.281)。Residual Illiquidity RankIC−0.001451(t−0.630)、spread−2.424%(t−0.814)。両residualがpositiveというComplementary条件は満たさない。Illiquidityの非有意を「alphaなしの証明」とはしない。線形OLSは非線形/順位依存を完全には除去せず、tercile条件付き結果と推定対象が違う。

DISAGREEMENT RankIC−0.002391、Q5−Q1年率0.617%。t1–t3 target meanとQ1–Q5を上表/CSVに保存。COMMONは正の情報があるが、DISAGREEMENTをstrategyにせず、最適化・採用しない。残差のGross SharpeもQ5−Q1 spreadの記述値であり、official portfolio performanceではない。

## 5. 3×3 double sort

| cell | average_stock_count | forward_target_mean | mean_daily_cell_target | average_long_weight | average_short_weight | annual_gross | annual_net |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Large + Liquid | 124.836863 | -0.000002 | -0.000005 | 0.000000 | 0.393640 | 0.002132 | 0.001611 |
| Large + Mid | 21.953725 | -0.000046 | -0.000070 | 0.000000 | 0.042710 | 0.000674 | 0.000630 |
| Large + Illiquid | 3.658824 | -0.000220 | -0.000169 | 0.005179 | 0.004201 | 0.001429 | 0.001385 |
| Mid + Liquid | 23.483137 | 0.000018 | 0.000004 | 0.000396 | 0.024744 | -0.000349 | -0.000577 |
| Mid + Mid | 97.050980 | 0.000253 | 0.000248 | 0.017211 | 0.035410 | 0.001247 | -0.000067 |
| Mid + Illiquid | 30.099608 | 0.000308 | 0.000331 | 0.040764 | 0.000437 | 0.002765 | 0.002458 |
| Small + Liquid | 2.129412 | 0.000758 | 0.001275 | 0.003653 | 0.000000 | 0.000906 | 0.000863 |
| Small + Mid | 31.629020 | 0.000326 | 0.000331 | 0.061656 | 0.000000 | 0.004451 | 0.004325 |
| Small + Illiquid | 117.342745 | 0.000699 | 0.000691 | 0.371701 | 0.000000 | 0.067018 | 0.066491 |

forward_target_meanはstock-day pooled mean、mean_daily_cell_targetは観測できたdateのcell平均を日ごと等重みにした値。両方を保存し、空cellのtargetはNaN、count/weight/contributionは0。少数のdiscordant cellを大きな共通cellと同じ確度で解釈しない。

下記は各年の3×3表。各cellは **mean daily target(bp) / SLOW年率net寄与(%) / 平均stock count**。Size/Illiquidityは各dateの独立3分位。各cellのdaily count/finite target count/Long・Short weights/gross/netは `double_sort_daily.csv`、pooled/EX2016/年別の全値は `double_sort_summary.csv`。

### POOLED

| Size / Illiquidity | Liquid | Mid | Illiquid |
| --- | --- | --- | --- |
| Small | 12.75 / 0.086 / 2.13 | 3.31 / 0.432 / 31.63 | 6.91 / 6.649 / 117.34 |
| Mid | 0.04 / -0.058 / 23.48 | 2.48 / -0.007 / 97.05 | 3.31 / 0.246 / 30.10 |
| Large | -0.05 / 0.161 / 124.84 | -0.70 / 0.063 / 21.95 | -1.69 / 0.139 / 3.66 |

### 2011

| Size / Illiquidity | Liquid | Mid | Illiquid |
| --- | --- | --- | --- |
| Small | 61.82 / 0.233 / 1.33 | 4.27 / 0.633 / 29.43 | 10.54 / 10.110 / 116.05 |
| Mid | -0.55 / -0.248 / 22.17 | 5.10 / 0.188 / 98.59 | 8.97 / 0.753 / 25.28 |
| Large | -0.50 / 0.328 / 122.51 | -0.58 / 0.069 / 18.02 | -6.56 / 0.209 / 5.48 |

### 2012

| Size / Illiquidity | Liquid | Mid | Illiquid |
| --- | --- | --- | --- |
| Small | 12.21 / 0.071 / 1.53 | -0.69 / -0.256 / 30.97 | 3.05 / 3.216 / 115.30 |
| Mid | -2.91 / 0.170 / 23.24 | -1.09 / 0.043 / 97.76 | -1.31 / -0.345 / 26.28 |
| Large | 0.11 / -0.230 / 122.26 | -4.48 / 0.473 / 18.54 | -2.39 / 0.247 / 6.22 |

### 2013

| Size / Illiquidity | Liquid | Mid | Illiquid |
| --- | --- | --- | --- |
| Small | 2.71 / 0.130 / 3.12 | 10.08 / 1.548 / 33.07 | 5.34 / 4.943 / 114.10 |
| Mid | 6.00 / -0.197 / 24.32 | 1.49 / -0.220 / 93.69 | -2.10 / -0.373 / 31.95 |
| Large | -1.25 / 1.749 / 122.21 | -3.14 / 0.357 / 23.21 | -7.81 / 0.193 / 4.24 |

### 2014

| Size / Illiquidity | Liquid | Mid | Illiquid |
| --- | --- | --- | --- |
| Small | 0.60 / 0.036 / 2.58 | -0.23 / -0.144 / 32.34 | 6.22 / 6.230 / 118.44 |
| Mid | 0.33 / -0.083 / 23.47 | 1.94 / -0.140 / 95.87 | 3.67 / 0.274 / 33.68 |
| Large | 1.33 / -0.966 / 126.85 | 1.06 / -0.107 / 24.80 | 4.75 / 0.037 / 1.25 |

### 2015

| Size / Illiquidity | Liquid | Mid | Illiquid |
| --- | --- | --- | --- |
| Small | 0.94 / -0.010 / 2.12 | 2.25 / 0.266 / 32.58 | 9.12 / 8.507 / 120.92 |
| Mid | -2.17 / 0.048 / 23.92 | 3.74 / 0.026 / 98.10 | 6.24 / 0.829 / 33.38 |
| Large | -0.25 / 0.329 / 129.10 | 2.48 / -0.368 / 24.71 | -7.99 / 0.069 / 1.33 |

### 2016 partial

| Size / Illiquidity | Liquid | Mid | Illiquid |
| --- | --- | --- | --- |
| Small | 16.35 / -0.036 / 1.98 | 6.95 / 0.932 / 30.66 | 8.22 / 7.837 / 125.36 |
| Mid | -1.90 / 0.018 / 24.75 | 7.79 / 0.277 / 102.14 | 8.09 / 0.664 / 30.12 |
| Large | 1.36 / -1.500 / 130.27 | 4.35 / -0.420 / 24.20 | 43.92 / -0.131 / 2.53 |

Small+Illiquidは平均117.34銘柄、年率Net寄与6.649%。Small+Liquidもtargetは正（stock-day mean7.58bp、daily mean12.75bp）であり、「Smallだけでは弱くinteractionが必要」とは言えない。ただし平均2.13銘柄、Large+Illiquidも3.66銘柄しかなく、比較supportが乏しい。共通cellへの利益集中はweight集中と銘柄数の両方を含み、interactionを識別する証明ではない。

## 6. Long / Short source attribution

| descriptor | side | cohort | stock_days | average_weight | annual_gross | annual_net |
| --- | --- | --- | --- | --- | --- | --- |
| Size | long | Large | 2255 | 0.005179 | 0.000282 | 0.000250 |
| Size | long | Mid | 37023 | 0.058371 | 0.004090 | 0.003125 |
| Size | long | Small | 191422 | 0.437010 | 0.072375 | 0.071689 |
| Size | short | Large | 189022 | 0.440550 | 0.003952 | 0.003376 |
| Size | short | Mid | 41880 | 0.060591 | -0.000427 | -0.001311 |
| Size | short | Small | 0 | 0.000000 | 0.000000 | -0.000010 |
| Illiquidity | long | Liquid | 2290 | 0.004049 | 0.000973 | 0.000905 |
| Illiquidity | long | Mid | 51646 | 0.078867 | 0.005578 | 0.004807 |
| Illiquidity | long | Illiquid | 176764 | 0.417644 | 0.070197 | 0.069353 |
| Illiquidity | short | Liquid | 176311 | 0.418384 | 0.001717 | 0.000993 |
| Illiquidity | short | Mid | 52413 | 0.078120 | 0.000793 | 0.000081 |
| Illiquidity | short | Illiquid | 2178 | 0.004638 | 0.001015 | 0.000982 |
| Joint | long | Large + Liquid | 0 | 0.000000 | 0.000000 | -0.000006 |
| Joint | long | Large + Mid | 0 | 0.000000 | 0.000000 | -0.000001 |
| Joint | long | Large + Illiquid | 2255 | 0.005179 | 0.000282 | 0.000256 |
| Joint | long | Mid + Liquid | 267 | 0.000396 | 0.000067 | 0.000042 |
| Joint | long | Mid + Mid | 11859 | 0.017211 | 0.001127 | 0.000479 |
| Joint | long | Mid + Illiquid | 24897 | 0.040764 | 0.002896 | 0.002604 |
| Joint | long | Small + Liquid | 2023 | 0.003653 | 0.000906 | 0.000868 |
| Joint | long | Small + Mid | 39787 | 0.061656 | 0.004451 | 0.004328 |
| Joint | long | Small + Illiquid | 149612 | 0.371701 | 0.067018 | 0.066492 |
| Joint | short | Large + Liquid | 159167 | 0.393640 | 0.002132 | 0.001617 |
| Joint | short | Large + Mid | 27972 | 0.042710 | 0.000674 | 0.000631 |
| Joint | short | Large + Illiquid | 1883 | 0.004201 | 0.001146 | 0.001129 |
| Joint | short | Mid + Liquid | 17144 | 0.024744 | -0.000415 | -0.000619 |
| Joint | short | Mid + Mid | 24441 | 0.035410 | 0.000119 | -0.000546 |
| Joint | short | Mid + Illiquid | 295 | 0.000437 | -0.000131 | -0.000146 |
| Joint | short | Small + Liquid | 0 | 0.000000 | 0.000000 | -0.000006 |
| Joint | short | Small + Mid | 0 | 0.000000 | 0.000000 | -0.000004 |
| Joint | short | Small + Illiquid | 0 | 0.000000 | 0.000000 | -0.000001 |

SLOW Long年率Net7.506%に対し、Size Smallが95.50%、Illiquidity Illiquidが92.39%、Joint Small+Illiquidが88.58%を占める。**三つのdescriptorは同じLong bookの重複する別分解であり、これらの寄与を足し合わせない。**

Longの多くは共通Small–Illiquid exposureから来る。Size単独のLong net7.692%はSLOW Long7.506%より大きく、SLOW全体の小さな優位は主にShortの0.206%による（Size Short0.005%、Illiquidity Short−0.204%）。ShortはLarge群のnet0.338%がMid群−0.131%を相殺する。JointではLarge+Liquid0.162%、Large+Illiquid0.113%の正寄与と他cellの負寄与。Shortは2014と2016partialで負なので安定した独立factor alphaとみなせない。

stock_daysは現在のside active数。現在weight0のcohortでも退出costがあり、netが負になりうる。Costは正/負sleeveのCode差分から割り当て、日次全cell和と公式Netを明示tolerance1e−14で照合。これはsignalのbitwise検査とは区別する。

## 7. Turnover sources

| scope | mean_Size_mean_abs_rank_change | mean_Illiquidity_mean_abs_rank_change | Size_rank_change_SLOW_turnover_Pearson | Illiquidity_rank_change_SLOW_turnover_Pearson |
| --- | --- | --- | --- | --- |
| POOLED | 0.007503 | 0.007021 | 0.670270 | 0.152517 |
| EX2016 | 0.007482 | 0.006996 | 0.678730 | 0.147181 |
| 2011 | 0.007875 | 0.006209 | 0.700573 | 0.400319 |
| 2012 | 0.007399 | 0.006664 | 0.528924 | 0.085142 |
| 2013 | 0.008222 | 0.007221 | 0.839022 | 0.179231 |
| 2014 | 0.006539 | 0.007437 | 0.486090 | 0.187391 |
| 2015 | 0.007371 | 0.007457 | 0.423827 | 0.021227 |
| 2016 partial | 0.007927 | 0.007527 | 0.443090 | 0.283624 |

Size rank variationとSLOW turnoverの日次Pearson0.670270、Illiquidityは0.152517。Size変動との共変動の方が大きい。これは因果効果や「turnoverの何%がSize原因」という加算的帰属ではない。daily mean/rms rank変化、全booksのLong/Short entry/exit、official turnover、年別Pearson/Spearmanを保存。

Rank変化は前exchange dateにも存在するstockの共通support、membershipは全date-code gridで欠落=neutral。公式turnoverのCode.diffは観測行間の差分であり、欠落日の全grid membership変化とは別診断。purge前に全履歴で変化を計算する。

## 8. Year-by-year stability

| year | SIZE_ONLY_gross_sharpe | SIZE_ONLY_net_sharpe | ILLIQ_ONLY_gross_sharpe | ILLIQ_ONLY_net_sharpe | SLOW_CONTROL_gross_sharpe | SLOW_CONTROL_net_sharpe |
| --- | --- | --- | --- | --- | --- | --- |
| 2011 | 2.835050 | 2.748720 | 2.197470 | 2.135994 | 2.800507 | 2.728793 |
| 2012 | 1.092541 | 0.990741 | 1.023614 | 0.916886 | 1.131319 | 1.033654 |
| 2013 | 2.157882 | 2.065817 | 1.346787 | 1.265968 | 1.978738 | 1.896830 |
| 2014 | 1.631972 | 1.520463 | 1.927318 | 1.806619 | 1.759505 | 1.664345 |
| 2015 | 3.226072 | 3.101417 | 3.482187 | 3.365843 | 3.366107 | 3.267066 |
| 2016 partial | 2.131051 | 2.017655 | 2.028464 | 1.940626 | 2.086547 | 2.003895 |

| strategy | minimum_annual_NetSR | sd_annual_NetSR | positive_full_year_annual_net |
| --- | --- | --- | --- |
| ILLIQ_ONLY | 0.916886 | 0.946256 | 5 |
| SIZE_ONLY | 0.990741 | 0.864595 | 5 |
| SLOW_CONTROL | 1.033654 | 0.883734 | 5 |

SLOWはSizeより3/5年で高NetSR、Illiquidityより3/5年で高NetSR。2011–2015の最小annual NetSRはSLOWが双方より高い。annual NetSRの標準偏差はSLOW0.883734で、Illiquidity0.946256より低いがSize0.864595より僅かに高い。安定性が全指標で改善する結果ではなく、統計的優位や最適構成は検証していない。全3booksは5/5年の年率Netが正。2011/2013はSizeの方が強く、2014/2015はIlliquidityの方が強い。SLOWは各年のbest standaloneを追従するわけではない。

| scope | direction | conditioning_bucket | annual_spread | hac5_t |
| --- | --- | --- | --- | --- |
| 2011 | Illiquidity_within_Size | Large | -0.028937 | -0.300064 |
| 2011 | Illiquidity_within_Size | Mid | 0.134137 | 1.065015 |
| 2011 | Illiquidity_within_Size | Small | 0.110507 | 1.194721 |
| 2011 | Size_within_Illiquidity | Illiquid | 0.228380 | 2.508512 |
| 2011 | Size_within_Illiquidity | Liquid | 0.009983 | 0.155136 |
| 2011 | Size_within_Illiquidity | Mid | 0.113452 | 1.199728 |
| 2012 | Illiquidity_within_Size | Large | -0.067641 | -1.069749 |
| 2012 | Illiquidity_within_Size | Mid | 0.029972 | 0.382679 |
| 2012 | Illiquidity_within_Size | Small | 0.153996 | 2.106281 |
| 2012 | Size_within_Illiquidity | Illiquid | 0.190829 | 2.499009 |
| 2012 | Size_within_Illiquidity | Liquid | -0.088319 | -1.064091 |
| 2012 | Size_within_Illiquidity | Mid | 0.055611 | 0.698663 |
| 2013 | Illiquidity_within_Size | Large | -0.005142 | -0.071712 |
| 2013 | Illiquidity_within_Size | Mid | -0.126943 | -1.346497 |
| 2013 | Illiquidity_within_Size | Small | -0.036746 | -0.486640 |
| 2013 | Size_within_Illiquidity | Illiquid | 0.162688 | 1.827630 |
| 2013 | Size_within_Illiquidity | Liquid | 0.121725 | 1.180405 |
| 2013 | Size_within_Illiquidity | Mid | 0.166381 | 1.684588 |
| 2014 | Illiquidity_within_Size | Large | 0.100114 | 1.818630 |
| 2014 | Illiquidity_within_Size | Mid | 0.031576 | 0.541531 |
| 2014 | Illiquidity_within_Size | Small | 0.222299 | 2.999576 |
| 2014 | Size_within_Illiquidity | Illiquid | 0.157885 | 1.900248 |
| 2014 | Size_within_Illiquidity | Liquid | 0.091312 | 1.559933 |
| 2014 | Size_within_Illiquidity | Mid | -0.008624 | -0.121642 |
| 2015 | Illiquidity_within_Size | Large | 0.124214 | 1.648822 |
| 2015 | Illiquidity_within_Size | Mid | 0.206467 | 2.364178 |
| 2015 | Illiquidity_within_Size | Small | 0.170307 | 2.078645 |
| 2015 | Size_within_Illiquidity | Illiquid | 0.105726 | 1.574900 |
| 2015 | Size_within_Illiquidity | Liquid | 0.029926 | 0.493394 |
| 2015 | Size_within_Illiquidity | Mid | 0.008843 | 0.088909 |
| 2016 partial | Illiquidity_within_Size | Large | 0.093247 | 0.563835 |
| 2016 partial | Illiquidity_within_Size | Mid | 0.146340 | 0.614597 |
| 2016 partial | Illiquidity_within_Size | Small | 0.013451 | 0.077827 |
| 2016 partial | Size_within_Illiquidity | Illiquid | -0.024762 | -0.099566 |
| 2016 partial | Size_within_Illiquidity | Liquid | -0.008414 | -0.060245 |
| 2016 partial | Size_within_Illiquidity | Mid | 0.074091 | 0.324491 |

| scope | signal | rankic | rankic_hac5_t | annual_spread | spread_hac5_t |
| --- | --- | --- | --- | --- | --- |
| 2011 | RESIDUAL_ILLIQ | -0.010839 | -2.266367 | -0.140498 | -2.464644 |
| 2011 | RESIDUAL_SIZE | 0.020410 | 2.566110 | 0.284248 | 2.809630 |
| 2012 | RESIDUAL_ILLIQ | 0.003445 | 0.623113 | 0.026182 | 0.402210 |
| 2012 | RESIDUAL_SIZE | -0.002677 | -0.438394 | 0.091194 | 1.298370 |
| 2013 | RESIDUAL_ILLIQ | -0.006550 | -1.286786 | -0.097060 | -1.174966 |
| 2013 | RESIDUAL_SIZE | 0.010842 | 1.595306 | 0.213651 | 2.263081 |
| 2014 | RESIDUAL_ILLIQ | 0.005674 | 1.235251 | 0.031778 | 0.561164 |
| 2014 | RESIDUAL_SIZE | -0.000014 | -0.002552 | 0.051154 | 0.820683 |
| 2015 | RESIDUAL_ILLIQ | 0.002281 | 0.401935 | 0.064118 | 0.935309 |
| 2015 | RESIDUAL_SIZE | 0.003479 | 0.612247 | 0.103246 | 1.588927 |
| 2016 partial | RESIDUAL_ILLIQ | -0.006729 | -0.600157 | -0.047880 | -0.329706 |
| 2016 partial | RESIDUAL_SIZE | 0.007962 | 0.918392 | 0.190432 | 1.548324 |

年別のStandalone SR、全6条件付きspread、双方residual IC/spreadを1行/年にまとめた `year_by_year_stability.csv` も保存。2016は59日の部分年、年率換算であって通年実績ではない。

## 9. Central questions and A–F conclusion

1. **ほぼSizeだけか:** 公式bookの近さ/NetSR/annual netではSize優位。SLOW NetSR2.094をSize2.069でほぼ再現するが、Sizeだけの因果説明にはならない。
2. **Illiquidity単独・独立alpha:** 単独NetSR1.843は正。Size除去後の線形residualは弱い一方、Small内conditional spreadは正。独立情報の有無は統制方法によって異なる。
3. **組合せによる安定性:** 最悪年/turnoverは小幅改善。annual SR分散はIlliquidity比で改善、Size比では僅かに悪化。毎年の優位や有意な改善はない。
4. **Size固定でもIlliquidity:** Small tercileで強い、Mid/Largeでは弱い。tercile内残存Size差を除去したとは言えない。
5. **Illiquidity固定でもSize:** Illiquid tercileで強く、Residual Sizeにも正のreturn information。
6. **Long源泉:** 共通Small+Illiquid群が88.58%のLong Net。単独Size Longも同程度以上で、Sizeと共通exposureが重要。
7. **Short源泉:** Large側中心の小さな寄与。SLOWの組合せでShort netが単独より改善するが、年別に負になり、どちらかの独立premiumへ一意に帰属できない。
8. **高相関の意味:** 共通Small–Illiquid characteristicと整合的。同順位だけでlatent economic factorやliquidity premiumの因果識別はできない。

| 分類 | 判定根拠 |
| --- | --- |
| A Size-dominant | Standalone/overlap/residualはSize寄り。ただしSmall内conditional Illiquidity t3.34があるため、条件付きIlliquidityも弱いという完全なAにはしない。 |
| B Illiquidity-dominant | Size単独が近く、Residual Sizeが正なので該当しない。 |
| C Complementary | 双方residual positiveを満たさない。 |
| D Common-factor dominant | 利益集中は支持されるが、Residual Sizeが弱くない。 |
| E Interaction-dominant | Small+Liquidも正で、discordant cell supportが乏しい。interactionが必要と識別できない。 |
| F Inconclusive | 高いrank相関、粗い条件付き統制と線形残差の異なる推定対象、少数のcounterfactual cellにより、単一のeconomic源泉の分離は保留。 |

したがって**厳密分類はF、記述的結論は「Sizeに近いportfolio、共通Small–Illiquid Long収益、Small内Illiquidityの部分的条件付き情報」**。最もSharpeが高いfactorの採用を目的にせず、元SLOWを維持して終了する。

## 10. Causality / accounting / reproducibility

原feature moduleとtarget-free diagnostic moduleのsource scan PASS。全4feature入力源（raw price/TurnoverValue、raw_return、PIT financial disclosures、PIT listed sector）個別/同時future mutation＋truncationを3cutoff2009-03-31/2012-12-28/2015-12-30で実施。cutoff後の極端値/NaN/0、削除、future code/date追加、開示Date変更を含む。row shuffleとdeterministic rebuildを加え**20case**、全raw/normalized features、Date/Code、conditional/joint bins、residuals、OLS coefficients、common/disagreementがstrict bitwise PASS。beta/TOPIXは評価専用target満期確認にのみ入り、特徴量の入力源ではない。

PIT sharesは開示DateのJST23:59:59可用性、positive sharesの過去field carry、backward as-of。raw_return[t]は当日までに実現する過去Open-to-Open return。Amihudは現在tを含むtrailing60/min40、欠落exchange日を飛ばさないgrid rolling。targetはraw residual at t+2として提供Train labelsを評価専用に再構築し、最大差/coverageをmaturity.jsonへ保存。学習なし。年末2営業日purgeで境界越えラベルを除去。

公式rankはDate内sorted Codeでfirst ties→5quintiles、weight=(Qindex−2)/N/1.2。turnover=sum(abs(Code.diff(weight)))、片道cost0.001。欠測target行のcostは公式式と同じくNetから脱落し、all-position cost/netも別記。年率値=日次平均×252；period_*は期間合計。Sharpe=mean/std(ddof1)×sqrt252、IC=同日average-tie Spearman、HAC5はBartlett。t-statは事前固定した記述診断で、多重比較補正は行っていない。Q単調性はQ順とQ平均returnのSpearman。MaxDDは初期wealth1の複利Net、additive DDも保存。

因果性・prefix検査は入力/境界についての証拠で普遍的証明ではない。PIT sharesにはtreasury sharesが含まれ、split/issuance後の開示遅れを遡及修正しない。vendor revisionを独立認証できない。raw欠損は原仕様のimputationを維持し、観測coverageを報告。

| component | stock_days | finite_raw | raw_coverage | long_observed_weight_fraction | short_observed_weight_fraction |
| --- | --- | --- | --- | --- | --- |
| Size | 576535 | 574778 | 0.996952 | 0.998648 | 1.000000 |
| Illiquidity | 576535 | 574816 | 0.997018 | 0.997413 | 0.998853 |

Runtime firewall/Train-only stage PASS、禁止パスのdenial確認PASS。Targetはcomponents/bins/residualが完成してから読み、feature経路へ入れない。関連回帰16件＋runtime firewall2件PASS。現実データの全診断実行をTrain-only smokeとし、全指標3×8有限/official reconciliation/coverage/hashを最終検査。metadata PASS、既存Freeze129hash PASS。

`make check` は既存DM-20261002-04のunknown experiment kindで失敗。今回も全workspace構成検査を合格とは扱わず、該当実験は変更しない。audit/verification.jsonとlogs/make_check.logへ記録。初回run-20261003T172859Zはtargetのハッシュ読込がfirewallへ登録され、性能計測前に停止。ハッシュをtarget-free phase後へ移す技術修正のみを行い、失敗runを保存。計画/config/feature定義は同一、完了bundle1、performance candidate0。

実験run時間103.78s、peak RSS2284.2MiB、期限1800s。提出zip/Valid/新strategyは作成しない。

## 11. Files and reproduction

- 計画/固定設定: `experiments/DM-20261004-01/plan.md`, `config.json`。
- target-free transforms: `research/experiments/slow_size_illiq_components.py`。
- Train-only driver: `research/experiments/slow_size_illiq_diagnostic.py`。
- Stock-day components/transforms: run内 `predictions/components.parquet`, `diagnostic_transforms.parquet`。
- Metrics: performance, incremental, correlation, overlap/groups, conditional spread, 3×3/side cohort, residual/common/disagreement, turnover, coverage, yearly stabilityのdaily/summary CSV。
- Audits: parity/accounting/maturity/purge/source/firewall/prefix/coverage/verification/resources/hash。
- Commands/environment/input/reference/code/artifact hashes: run.json/code_snapshot/logs。

実際の実行: `.venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.slow_size_illiq_diagnostic --config artifacts/DM-20261004-01/run-20261003T172950Z/config.json --output artifacts/DM-20261004-01/run-20261003T172950Z`。既存runは上書きしない。再現する場合はprepare-runで新runを予約し、report_dirも新しい保存先へ分ける。検証/報告作成スクリプトは実験folderのverify.py/finalize_report.pyに保存。
