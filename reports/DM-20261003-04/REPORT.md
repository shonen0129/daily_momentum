# DM-20261003-04: SLOW_CONTROL Size / Illiquidity versus style diagnosis

結論: **A: Structural Size/Liquidity（測定したstyleに限る）**。SLOWの収益を2010年代のSmall Growth / Growth regimeだけで説明する仮説は、この固定Train診断では支持されない。Value/Growth bucket内でもspreadが残り、style matchingと共通銘柄集合でのOLS残差もGrossを維持する。H0の純粋な因果的証明ではない。

Diagnostic-only、Train-only。新candidate・売買rule・filter・blend・submission・Valid評価は作成していない。H0/H1への診断であり、Size/Illiquidity premiumの因果的証明ではない。

Run `artifacts/DM-20261003-04/run-20261003T132635Z`。config SHA-256 `f14f2424e0eb6dada375c887a35e8041adca74b8337704db0e31240b7998561f`。試行は固定診断1bundle、performance candidate0。全Trainは既読development sample。

## 固定方法と比較条件

元SLOWは `dm_slow_multifactor.build_features(sector=False).size_liquidity` を無変更で再構築。−log(raw Close×PIT shares)、Amihud60/min40、元のwinsor/median/zとofficial ranking/weightをそのまま使用し、保存score809,636行・official weight・official daily Netをbitwise照合した。diagnostic descriptorには元SLOWのmedian補完を使わない。

B/P=Equity/shares/raw Close、E/P=Forecast EPS/raw Close。ROE=通期FY Profit/Equity、CFO/Assets=通期FYの同一statementのCFO/Assets、Equity/Assets=最新同一statement。Growthは通期Sales・OperatingProfit・Profitの前年比。開始/終了が正確に1年前、同じ連結区分/会計基準のTypeOfDocument、365/366日、期末が開示日以前、前年分母>0のみ。開示時点で既知の前年statementを使い、後のrestatementで過去を修正しない。比較不能な新FYはGrowthを欠損へ戻す。予想Growthや代替proxyへの変更なし。

各descriptorを日次1/99 linear winsor、同日平均・sample SDでstandardize。欠損を保持。tercileはaverage-tie percentileのceil(3p): Low1/Mid2/High3、tiesはCode順に分割しない。Q1–Q5 characteristicは元official quintile、Q1がlow SLOW、Q5がhigh SLOW。Long weighted meanとShort weighted meanは各side内の観測weightへrenormalizeし、weight coverageを別記。日次表は毎営業日、年別/pooled表は日次平均。

評価2011–2015、2016は2016-03までのpartial。各年末2営業日をpurgeし、t+1 Open→t+2 Openラベルが年/fold境界を跨がない。年率P/L=日次平均×252、Sharpe=平均/sample SD×sqrt252、RankIC=同日average-tie Spearman、t-stat=HAC5。会計はpurge前の連続panelで計算する。公式はtarget欠損行のcostも落とすため、all-position cost/netもCSVへ保存。Matched/neutralは仮想構成であり採用判断へ使わない。

## SLOW Long / Short style profile と Q1–Q5

| descriptor | long_mean | short_mean | spread | long_weight_coverage | short_weight_coverage | q1 | q2 | q3 | q4 | q5 | q_style_monotonicity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bp | 0.171849 | -0.113391 | 0.285240 | 0.998649 | 1.000000 | -0.107094 | -0.126009 | -0.067438 | 0.084248 | 0.215478 | 0.900000 |
| cf_assets | -0.081661 | 0.055475 | -0.137136 | 0.990404 | 0.991744 | 0.083748 | -0.000546 | 0.060649 | -0.042098 | -0.101467 | -0.900000 |
| equity_assets | 0.106966 | -0.136706 | 0.243672 | 0.998915 | 1.000000 | -0.108013 | -0.194418 | 0.083558 | 0.119159 | 0.100875 | 0.800000 |
| ey | 0.058475 | 0.034932 | 0.023543 | 0.992311 | 0.972337 | 0.119737 | -0.129964 | -0.068353 | -0.013918 | 0.094224 | 0.000000 |
| operating_growth | -0.015830 | 0.019439 | -0.035269 | 0.880558 | 0.781278 | 0.031155 | -0.006986 | 0.016713 | -0.032580 | -0.006832 | -0.500000 |
| profit_growth | -0.043841 | 0.023192 | -0.067033 | 0.848370 | 0.804108 | 0.021172 | 0.026806 | 0.013999 | 0.010530 | -0.072799 | -0.900000 |
| roe | -0.023694 | 0.063438 | -0.087132 | 0.990404 | 0.994452 | 0.129371 | -0.068584 | -0.011817 | -0.028761 | -0.021127 | -0.300000 |
| sales_growth | 0.041911 | 0.007272 | 0.034639 | 0.920966 | 0.880337 | 0.048300 | -0.073838 | -0.042036 | 0.005736 | 0.059355 | 0.400000 |

値はwinsor後の断面z。spread>0はLongが高いcharacteristic。B/PまたはE/Pが低いことだけでGrowthとは断定しない。全raw比率、年別、日次平均・coverageは [style_profile.csv](metrics/style_profile.csv) と [daily_characteristics.csv](metrics/daily_characteristics.csv)。

## Growth / Value bucket内のSLOW spread

| descriptor | bucket | mean_spread | annual_spread | spread_t_hac5 | gross_sharpe_spread | spread_days |
| --- | --- | --- | --- | --- | --- | --- |
| bp | 1 | 0.001054 | 0.265516 | 5.008202 | 2.032532 | 1275 |
| bp | 2 | 0.000509 | 0.128210 | 3.153187 | 1.245915 | 1275 |
| bp | 3 | 0.000864 | 0.217844 | 4.445037 | 1.802970 | 1275 |
| cf_assets | 1 | 0.000964 | 0.242865 | 4.798346 | 1.906484 | 1275 |
| cf_assets | 2 | 0.000695 | 0.175117 | 4.374745 | 1.731025 | 1275 |
| cf_assets | 3 | 0.000745 | 0.187773 | 4.058155 | 1.678279 | 1275 |
| equity_assets | 1 | 0.000953 | 0.240265 | 4.668547 | 1.858786 | 1275 |
| equity_assets | 2 | 0.000879 | 0.221500 | 4.861206 | 1.949820 | 1275 |
| equity_assets | 3 | 0.000311 | 0.078342 | 1.978129 | 0.766479 | 1275 |
| ey | 1 | 0.000727 | 0.183282 | 3.832319 | 1.602066 | 1275 |
| ey | 2 | 0.000653 | 0.164629 | 3.818834 | 1.544843 | 1275 |
| ey | 3 | 0.000925 | 0.233092 | 5.068940 | 2.013005 | 1275 |
| operating_growth | 1 | 0.000579 | 0.145987 | 3.283445 | 1.287449 | 1275 |
| operating_growth | 2 | 0.000510 | 0.128528 | 3.026262 | 1.278660 | 1275 |
| operating_growth | 3 | 0.000823 | 0.207478 | 4.306400 | 1.717404 | 1275 |
| profit_growth | 1 | 0.000661 | 0.166513 | 3.716958 | 1.420247 | 1275 |
| profit_growth | 2 | 0.000566 | 0.142741 | 3.139071 | 1.272010 | 1275 |
| profit_growth | 3 | 0.000826 | 0.208247 | 4.522116 | 1.795162 | 1275 |
| roe | 1 | 0.000646 | 0.162784 | 3.515342 | 1.350230 | 1275 |
| roe | 2 | 0.000489 | 0.123224 | 2.865867 | 1.183075 | 1275 |
| roe | 3 | 0.001138 | 0.286776 | 5.673879 | 2.313739 | 1275 |
| sales_growth | 1 | 0.000551 | 0.138818 | 3.237877 | 1.226175 | 1275 |
| sales_growth | 2 | 0.000796 | 0.200502 | 4.856641 | 1.938315 | 1275 |
| sales_growth | 3 | 0.000661 | 0.166581 | 3.341683 | 1.352342 | 1275 |

各style tercile内でSLOWをaverage-tie再rankし、等weight Q5−Q1のforward市場残差returnを取る。公式portfolioのweight構成とは異なる条件付きspreadであり、新portfolioではない。日次quintile値・stock count、年別は [double_sort.csv](metrics/double_sort.csv) / [daily_double_sort.csv](metrics/daily_double_sort.csv)。

## Style matching / OLS residual

| diagnostic | gross_sharpe | net_sharpe | rankic | rankic_t_hac5 | q5_q1_spread | annual_gross | annual_net | turnover | annual_long | annual_short | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SLOW_CONTROL | 2.179334 | 2.093538 | 0.008257 | 2.802064 | 0.000772 | 0.080272 | 0.077119 | 0.012888 | 0.076748 | 0.003525 | -0.022099 |
| MOM60 | 0.613360 | 0.308092 | 0.007590 | 1.567643 | 0.000312 | 0.032108 | 0.016128 | 0.063418 | 0.054443 | -0.022335 | -0.097063 |
| SLOW_COMMON_SUPPORT | 1.921385 | 1.819549 | 0.006305 | 2.052613 | 0.000681 | 0.071943 | 0.068144 | 0.015509 | 0.079599 | -0.007656 | -0.025192 |
| STYLE_NEUTRAL_RESIDUAL | 2.004164 | 1.868398 | 0.007297 | 2.339499 | 0.000711 | 0.073653 | 0.068704 | 0.020071 | 0.081082 | -0.007429 | -0.025377 |
| STYLE_MATCHED_SLOW | 2.138160 | 1.787546 | 0.008193 | 2.448131 | 0.000738 | 0.080053 | 0.066956 | 0.052496 | 0.076140 | 0.003914 | -0.023263 |
| VALUE_MATCHED_SLOW | 2.263653 | 2.041606 | 0.008778 | 2.642606 | 0.000772 | 0.084772 | 0.076472 | 0.033501 | 0.079184 | 0.005587 | -0.020882 |

STYLE_MATCHED_SLOWはB/P×Sales Growth3×3cellで元official Long/Shortをmatch。各cell共通mass=min(元Long mass,元Short mass)、side内relative weightを保持し、総side massを元Long/Shortの小さい方へscale。VALUE_MATCHED_SLOWは固定B/P-only3cellの補助診断。weight optimizationなし。bucket内の連続descriptor差・他style差は残るため「完全なstyle除去」とは呼ばない。欠損cellと片side-only cellを除外し、その影響も含む。

STYLE_NEUTRAL_RESIDUALは同日のSLOW scoreをintercept+固定8descriptorへunregularized OLS。complete casesのみで、targetは使わない。residualを同じcomplete-case universe内でofficial quintile weightへ変換し、それ以外はweight0。SLOW_COMMON_SUPPORTは同じ銘柄集合で元SLOWをrankする基準。common supportとの比較がstyle控除の診断であり、full universeとの差にはcoverage効果が含まれる。退場時costをfull panel上で保持。MatchedのRankIC/Q値はactive original score/quintileの参考で、matching後の新scoreではない。

| scope | diagnostic | gross_sharpe | net_sharpe | rankic | annual_gross | annual_net | annual_long | annual_short | turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2011 | SLOW_CONTROL | 2.800507 | 2.728793 | 0.019412 | 0.125949 | 0.122760 | 0.122505 | 0.003444 | 0.013703 |
| 2012 | SLOW_CONTROL | 1.131319 | 1.033654 | -0.003250 | 0.037084 | 0.033888 | 0.029199 | 0.007885 | 0.013052 |
| 2013 | SLOW_CONTROL | 1.978738 | 1.896830 | 0.009615 | 0.084835 | 0.081311 | 0.064955 | 0.019880 | 0.014252 |
| 2014 | SLOW_CONTROL | 1.759505 | 1.664345 | 0.005547 | 0.054300 | 0.051361 | 0.065722 | -0.011423 | 0.011729 |
| 2015 | SLOW_CONTROL | 3.366107 | 3.267066 | 0.009255 | 0.099873 | 0.096957 | 0.097487 | 0.002386 | 0.011756 |
| 2016 | SLOW_CONTROL | 2.086547 | 2.003895 | 0.011722 | 0.079565 | 0.076413 | 0.095270 | -0.015706 | 0.012628 |
| 2011 | SLOW_COMMON_SUPPORT | 2.329718 | 2.231625 | 0.015774 | 0.107923 | 0.103407 | 0.126385 | -0.018462 | 0.019626 |
| 2012 | SLOW_COMMON_SUPPORT | 0.812818 | 0.699709 | -0.004748 | 0.025847 | 0.022270 | 0.024655 | 0.001193 | 0.014625 |
| 2013 | SLOW_COMMON_SUPPORT | 1.954939 | 1.862392 | 0.009736 | 0.086749 | 0.082638 | 0.063793 | 0.022955 | 0.016450 |
| 2014 | SLOW_COMMON_SUPPORT | 1.434104 | 1.322387 | 0.002156 | 0.045201 | 0.041705 | 0.070396 | -0.025195 | 0.013873 |
| 2015 | SLOW_COMMON_SUPPORT | 3.226503 | 3.115455 | 0.008501 | 0.095124 | 0.091798 | 0.101797 | -0.006673 | 0.013199 |
| 2016 | SLOW_COMMON_SUPPORT | 1.776751 | 1.682200 | 0.007262 | 0.069576 | 0.065909 | 0.127782 | -0.058206 | 0.014552 |
| 2011 | STYLE_NEUTRAL_RESIDUAL | 2.571135 | 2.405292 | 0.015202 | 0.107371 | 0.100454 | 0.127137 | -0.019766 | 0.029152 |
| 2012 | STYLE_NEUTRAL_RESIDUAL | 0.595687 | 0.432593 | -0.004435 | 0.018731 | 0.013633 | 0.019755 | -0.001024 | 0.020675 |
| 2013 | STYLE_NEUTRAL_RESIDUAL | 1.936805 | 1.827592 | 0.009490 | 0.085553 | 0.080776 | 0.059882 | 0.025671 | 0.019076 |
| 2014 | STYLE_NEUTRAL_RESIDUAL | 1.879179 | 1.745009 | 0.006206 | 0.057171 | 0.053132 | 0.076313 | -0.019142 | 0.016027 |
| 2015 | STYLE_NEUTRAL_RESIDUAL | 2.857895 | 2.727974 | 0.008561 | 0.091708 | 0.087503 | 0.104229 | -0.012521 | 0.016689 |
| 2016 | STYLE_NEUTRAL_RESIDUAL | 2.511283 | 2.422511 | 0.013919 | 0.108311 | 0.104605 | 0.159025 | -0.050714 | 0.014709 |
| 2011 | STYLE_MATCHED_SLOW | 2.689645 | 2.356695 | 0.019699 | 0.118059 | 0.103425 | 0.114438 | 0.003621 | 0.059775 |
| 2012 | STYLE_MATCHED_SLOW | 0.927868 | 0.514680 | -0.005484 | 0.030452 | 0.016927 | 0.024966 | 0.005486 | 0.054248 |
| 2013 | STYLE_MATCHED_SLOW | 2.010875 | 1.697359 | 0.009954 | 0.088161 | 0.074444 | 0.066742 | 0.021420 | 0.054880 |
| 2014 | STYLE_MATCHED_SLOW | 1.750107 | 1.388787 | 0.006005 | 0.056727 | 0.045041 | 0.067861 | -0.011133 | 0.046375 |
| 2015 | STYLE_MATCHED_SLOW | 3.218266 | 2.832529 | 0.009060 | 0.101430 | 0.089293 | 0.101082 | 0.000347 | 0.048163 |
| 2016 | STYLE_MATCHED_SLOW | 2.620619 | 2.317114 | 0.016002 | 0.104941 | 0.092775 | 0.102134 | 0.002807 | 0.048279 |

すべてのfold/year/pooled/ex2016でGross/Net、Annual Cost、Turnover、RankIC/HAC/hit、Q1–Q5 return/monotonicity、Long/Short、DDを [portfolio_metrics.csv](metrics/portfolio_metrics.csv) に保存。元SLOW、MOM60とcommon-support差分は [incremental.csv](metrics/incremental.csv)。Residualのquintile spreadはQ5 daily return−Q1 daily return。

## 年別style exposure / regime attribution

| scope | descriptor | long_mean | short_mean | spread | long_weight_coverage | short_weight_coverage |
| --- | --- | --- | --- | --- | --- | --- |
| 2011 | bp | 0.190252 | -0.148943 | 0.339195 | 0.998189 | 1.000000 |
| 2011 | ey | 0.028951 | 0.063864 | -0.034913 | 0.990766 | 0.976568 |
| 2011 | operating_growth | -0.060782 | 0.056834 | -0.117615 | 0.831327 | 0.778229 |
| 2011 | profit_growth | -0.028614 | 0.048240 | -0.076854 | 0.772597 | 0.729233 |
| 2011 | roe | -0.009071 | 0.080796 | -0.089867 | 0.990940 | 0.989754 |
| 2011 | sales_growth | 0.026891 | -0.032934 | 0.059825 | 0.900911 | 0.878224 |
| 2012 | bp | 0.137484 | -0.111433 | 0.248917 | 0.999632 | 1.000000 |
| 2012 | ey | 0.064895 | 0.024435 | 0.040461 | 0.989946 | 0.974863 |
| 2012 | operating_growth | -0.011608 | -0.001257 | -0.010352 | 0.901632 | 0.848979 |
| 2012 | profit_growth | -0.066998 | 0.030390 | -0.097388 | 0.859634 | 0.867345 |
| 2012 | roe | -0.016555 | 0.098589 | -0.115143 | 1.000000 | 0.998900 |
| 2012 | sales_growth | 0.065638 | -0.073255 | 0.138894 | 0.935795 | 0.917376 |
| 2013 | bp | 0.224357 | -0.135810 | 0.360167 | 0.999970 | 1.000000 |
| 2013 | ey | 0.064470 | 0.010718 | 0.053753 | 0.993544 | 0.968758 |
| 2013 | operating_growth | 0.041053 | 0.017464 | 0.023588 | 0.914923 | 0.806579 |
| 2013 | profit_growth | -0.017883 | 0.058483 | -0.076366 | 0.872463 | 0.817787 |
| 2013 | roe | -0.006602 | 0.005543 | -0.012145 | 0.998967 | 0.995723 |
| 2013 | sales_growth | 0.071314 | 0.019810 | 0.051503 | 0.947248 | 0.901861 |
| 2014 | bp | 0.164885 | -0.101744 | 0.266629 | 0.999044 | 1.000000 |
| 2014 | ey | 0.065318 | 0.048435 | 0.016883 | 0.995976 | 0.970118 |
| 2014 | operating_growth | -0.040891 | 0.070129 | -0.111020 | 0.889658 | 0.752926 |
| 2014 | profit_growth | -0.050970 | 0.020399 | -0.071368 | 0.872804 | 0.798552 |
| 2014 | roe | -0.003894 | 0.055602 | -0.059496 | 0.993979 | 0.997036 |
| 2014 | sales_growth | 0.046231 | 0.053769 | -0.007538 | 0.930943 | 0.872804 |
| 2015 | bp | 0.143316 | -0.077947 | 0.221264 | 0.996568 | 1.000000 |
| 2015 | ey | 0.066664 | 0.030350 | 0.036314 | 0.991917 | 0.971458 |
| 2015 | operating_growth | -0.011960 | -0.029494 | 0.017535 | 0.871941 | 0.729833 |
| 2015 | profit_growth | -0.056269 | -0.023664 | -0.032604 | 0.861224 | 0.806374 |
| 2015 | roe | -0.060433 | 0.077059 | -0.137492 | 0.974617 | 0.994586 |
| 2015 | sales_growth | 0.013956 | 0.054645 | -0.040689 | 0.897909 | 0.842543 |
| 2016 | bp | 0.168679 | -0.075939 | 0.244619 | 0.997911 | 1.000000 |
| 2016 | ey | 0.066960 | 0.022682 | 0.044278 | 0.990033 | 0.971831 |
| 2016 | operating_growth | 0.004333 | -0.047359 | 0.051692 | 0.851934 | 0.734662 |
| 2016 | profit_growth | -0.036691 | -0.051686 | 0.014995 | 0.861303 | 0.805980 |
| 2016 | roe | -0.114612 | 0.060099 | -0.174711 | 0.962998 | 0.978873 |
| 2016 | sales_growth | -0.019317 | 0.071962 | -0.091279 | 0.887145 | 0.831881 |

| scope | factor | correlation | beta | r_squared | intercept_annual | factor_annual_return |
| --- | --- | --- | --- | --- | --- | --- |
| POOLED | Growth_minus_Value | 0.065358 | 0.021221 | 0.004272 | 0.078718 | 0.073267 |
| EX2016 | Growth_minus_Value | 0.069255 | 0.022877 | 0.004796 | 0.079001 | 0.057077 |
| 2011 | Growth_minus_Value | -0.174233 | -0.069056 | 0.030357 | 0.119277 | -0.096613 |
| 2012 | Growth_minus_Value | 0.041116 | 0.013321 | 0.001691 | 0.035783 | 0.097656 |
| 2013 | Growth_minus_Value | 0.284577 | 0.095154 | 0.080984 | 0.067863 | 0.178359 |
| 2014 | Growth_minus_Value | 0.062795 | 0.024660 | 0.003943 | 0.051786 | 0.101941 |
| 2015 | Growth_minus_Value | 0.132737 | 0.030831 | 0.017619 | 0.099765 | 0.003507 |
| 2016 | Growth_minus_Value | 0.009957 | 0.002535 | 0.000099 | 0.078533 | 0.406954 |

固定factor: 同じuniverseでB/P tercile High−Low=Value、Sales Growth tercile High−Low=Growth、Growth−Value=両者の差。上表は元SLOW daily Grossへのintercept付きOLS。ValueとGrowthを個別に回帰した参考表も保存。同じ銘柄/targetを使うfactorとの同時相関は機械的共有・共通shockを含み、独立した因果説明/外部factor回帰ではない。年別factor meanを合わせてregimeの向きを見る。

## Long-side / Short-side cohort contribution

| descriptor | side | bucket | average_weight | stock_days | annual_gross | annual_net |
| --- | --- | --- | --- | --- | --- | --- |
| amihud | long | 0.000000 | 0.001295 | 493 | 0.000000 | 0.000000 |
| amihud | long | 1.000000 | 0.004037 | 2282 | 0.000900 | 0.000832 |
| amihud | long | 2.000000 | 0.078244 | 51583 | 0.005860 | 0.005086 |
| amihud | long | 3.000000 | 0.416984 | 176342 | 0.069988 | 0.069145 |
| amihud | short | 0.000000 | 0.000575 | 242 | 0.000000 | 0.000000 |
| amihud | short | 1.000000 | 0.417795 | 175930 | 0.001858 | 0.001136 |
| amihud | short | 2.000000 | 0.078168 | 52575 | 0.000614 | -0.000103 |
| amihud | short | 3.000000 | 0.004604 | 2155 | 0.001053 | 0.001021 |
| bp | long | 0.000000 | 0.000677 | 297 | 0.000011 | 0.000011 |
| bp | long | 1.000000 | 0.136170 | 62606 | 0.034897 | 0.034349 |
| bp | long | 2.000000 | 0.160946 | 76832 | 0.017778 | 0.017217 |
| bp | long | 3.000000 | 0.202767 | 90965 | 0.024062 | 0.023488 |
| bp | short | 0.000000 | 0.000000 | 0 | 0.000000 | 0.000000 |
| bp | short | 1.000000 | 0.195994 | 90077 | -0.004162 | -0.004719 |
| bp | short | 2.000000 | 0.155922 | 72619 | -0.000474 | -0.000994 |
| bp | short | 3.000000 | 0.149227 | 68206 | 0.008160 | 0.007767 |
| market_cap | long | 0.000000 | 0.000677 | 297 | 0.000011 | 0.000011 |
| market_cap | long | 1.000000 | 0.434899 | 190023 | 0.071902 | 0.071223 |
| market_cap | long | 2.000000 | 0.059775 | 38115 | 0.004580 | 0.003608 |
| market_cap | long | 3.000000 | 0.005209 | 2265 | 0.000255 | 0.000222 |
| market_cap | short | 0.000000 | 0.000000 | 0 | 0.000000 | 0.000000 |
| market_cap | short | 1.000000 | 0.000000 | 0 | 0.000000 | -0.000010 |
| market_cap | short | 2.000000 | 0.060258 | 41650 | -0.000455 | -0.001339 |
| market_cap | short | 3.000000 | 0.440883 | 189252 | 0.003980 | 0.003404 |
| roe | long | 0.000000 | 0.004803 | 1874 | 0.000299 | 0.000297 |
| roe | long | 1.000000 | 0.180391 | 85266 | 0.021053 | 0.020453 |
| roe | long | 2.000000 | 0.159868 | 72660 | 0.015463 | 0.015004 |
| roe | long | 3.000000 | 0.155498 | 70900 | 0.039932 | 0.039310 |
| roe | short | 0.000000 | 0.002780 | 1090 | 0.000043 | 0.000041 |
| roe | short | 1.000000 | 0.131585 | 64628 | 0.004895 | 0.004358 |
| roe | short | 2.000000 | 0.178048 | 82028 | -0.000097 | -0.000572 |
| roe | short | 3.000000 | 0.188729 | 83156 | -0.001317 | -0.001771 |
| sales_growth | long | 0.000000 | 0.039561 | 17912 | 0.009276 | 0.009133 |
| sales_growth | long | 1.000000 | 0.151022 | 69545 | 0.017708 | 0.017264 |
| sales_growth | long | 2.000000 | 0.148543 | 70280 | 0.024143 | 0.023632 |
| sales_growth | long | 3.000000 | 0.161434 | 72963 | 0.025621 | 0.025035 |
| sales_growth | short | 0.000000 | 0.059969 | 26341 | 0.001413 | 0.001262 |
| sales_growth | short | 1.000000 | 0.142102 | 67319 | 0.000122 | -0.000282 |
| sales_growth | short | 2.000000 | 0.147881 | 69388 | -0.000578 | -0.001030 |
| sales_growth | short | 3.000000 | 0.151191 | 67854 | 0.002567 | 0.002104 |

bucket0はMISSING。元official side weightのaverage massとstock-days、signed gross/netを保存。Long/Shortのmarket cap、Amihud、全styleの分布は [book_distributions.csv](metrics/book_distributions.csv)（absolute book weightによるp10/p25/p50/p75/p90）、年別全cohortは [cohort_contribution.csv](metrics/cohort_contribution.csv)。各descriptor内の全bucketは元side gross/netに1e−12で照合。exit costは現在日descriptor cohortへ帰属、stock-daysは現在active sideだけを数える。cohortからfilterを作らない。

## Coverage / PIT・corporate-action制約

| descriptor | stock_days | finite_raw | finite_z | coverage |
| --- | --- | --- | --- | --- |
| bp | 576535 | 574778 | 574778 | 0.996952 |
| ey | 576535 | 567101 | 567101 | 0.983637 |
| roe | 576535 | 571990 | 571990 | 0.992117 |
| cf_assets | 576535 | 571677 | 571677 | 0.991574 |
| equity_assets | 576535 | 575157 | 575157 | 0.997610 |
| sales_growth | 576535 | 521434 | 521434 | 0.904427 |
| operating_growth | 576535 | 481149 | 481149 | 0.834553 |
| profit_growth | 576535 | 473088 | 473088 | 0.820571 |
| OLS_COMMON_SUPPORT | 576535 | 446291 | 446291 | 0.774092 |

年度・Long/Short weight coverageも保存。Growthはpositive prior denominatorの通期比較であり、赤字→黒字や会計基準/決算期変更を網羅しない。Sales Growthは実績売上成長であり、市場が期待するSmall Growth分類そのものではない。annual descriptorは次の開示まで古くなる; [disclosure_age_summary.csv](metrics/disclosure_age_summary.csv)。同日のDate-only開示は23:59:59 JSTで利用可能と仮定し、翌寄付前に計算。公開時刻は復元不能。

raw Close×最後の開示shares（自己株式込み）とForecast EPS/raw Closeはsplit/issuance前後のshare basisが一時不整合となり得る。AdjustmentFactorは発生日を記録する診断にだけ読み、SLOWやdescriptorの遡及補正には使わない。B/P・E/Pは元のper-field past finite carryなので報告vintageが混在する場合がある。financial vendor snapshotの過去restatement vintageをDateだけで独立に保証できない。通期ROEは平均Equityベースではなく期末Equity。これらを踏まえてH0/H1を解釈する。

## Causality / 再現性と完了記録

Future mutation/truncation:2009-03-31（Growth warmup）、2012-06-29、2015-12-30。financial（値・fiscal metadata）、raw Close/turnover、raw return、PIT listedを個別/一括改変し、suffix行削除・追加も実施。各cutoffでfeature、raw/z、元SLOW、residual score、matching weightをindex/列/dtype/NaN含むfloat64 bitで比較。row shuffle、再build、indexも検証。補助検査では未来の全financial開示Dateを17日後へ移し、同じ3cutoffでbitwise一致、2,523組の年度対応/開示順序とnonnegative disclosure ageを確認した。[disclosure/fiscal audit](audit/disclosure_and_fiscal_audit.json)、[prefix audit](audit/prefix_invariance.json)、[target-free build](audit/target_free_build.json)、[firewall](audit/firewall.json)、[source scan](audit/source_scan.json)。有限cutoffの証拠でありvendor vintageや全入力への数学的証明ではない。

関連36テストPASS。元score809,636行とofficial weight/daily Net bitwise PASS。future-mutation/truncation18case、row shuffle、deterministic rebuild PASS。make checkは既存DM-20261002-04の非対応experiment kindで停止したが、本実験metadata/configと既存Freeze129file hashを個別に照合してPASS。科学計算130.60秒、peak RSS2.92GB（約2.72GiB）。最終artifact-copy guard失敗はhash照合による保存済み結果finalizationで解消し、追加backtest/候補trialなし。

初期4runの技術的失敗を保持。1件目は初期期間の空OLS table、2件目はtargetの事前hash-read検出で損益前に停止。3件目は損益計算後のDate列名欠落で停止。4件目は全診断・監査完了後、自作parquetをreportへ複写する際のfirewallで停止した。科学計算元はrun-20261003T132116Zで、run-20261003T132635Zがcode snapshot/config/結果hashを照合して保存を完了。[saved-result finalization](audit/saved_result_finalization.json)。3/4件目のportfolio metrics CSVはbyte-identical。config/descriptor選択・score・matching・OLS定義の結果後変更なし。[technical failures](../../experiments/DM-20261003-04/technical_failures.json)。performance trial0。

## 診断の解釈

- Long−Short z exposure: B/P **+0.285**、E/P **+0.024**、Sales Growth **+0.035**、Operating Growth **−0.035**、Profit Growth **−0.067**。B/Pは2011–2016各年で正、Sales Growthは2014–2016で負。LongはShortよりValue寄りで、明確なGrowth偏重ではない。ROE **−0.087**、CFO/Assets **−0.137**、Equity/Assets **+0.244**とquality exposureは混在する。
- Pooled SLOW Q5−Q1 daily spread: B/P Low/Mid/High **10.54 / 5.09 / 8.64bp**、Sales Growth Low/Mid/High **5.51 / 7.96 / 6.61bp**。Operating/Profit Growthも3bucketすべて正。B/Pは全year×3bucketで正。Sales Growthは2012年Highだけ負（**−1.10bp/day**）で、High Growthへの一貫した収益集中はない。HACは同じ固定bundle内の記述的統計で、多重比較調整後の発見とは呼ばない。
- 元SLOW GrossSR **2.179** / 年率Gross **8.027%**、B/P×Sales Growth matched **2.138** / **8.005%**。Matched NetSR **1.788**（元 **2.094**）はturnover **0.0525**（元 **0.0129**）、年率cost **1.310%**（元 **0.315%**）の影響を受ける。Gross消失を示す結果ではなく、matched仮想portfolioの採用判断には使わない。
- OLS共通銘柄集合で元SLOW GrossSR **1.921** / 年率Gross **7.194%**、style residual **2.004** / **7.365%**。RankIC **0.006305→0.007297**、daily Q5−Q1 **6.81→7.11bp**。2016除外でもGrossSR **1.928→1.976**。年別成績がすべて改善するわけではないが、残差Grossは全6評価年で正。full-universe **2.179→2.004**の差にはcomplete-case coverage効果が含まれる。
- Growth−Value factorのpooled相関 **0.0654**、beta **0.0212**、R² **0.00427**（0.43%）。2013は相関 **0.285**、R² **0.081**で一部共変動がある。全てのregime影響がゼロとは断定しない。固定factor共有targetによる同時相関は因果的なreturn attributionではない。
- Long年率Gross **7.675%**のうちSales Growth Low/Mid/Highは **1.771 / 2.414 / 2.562%**、Missing **0.928%**。High Growthだけではない。small-cap tercileは **7.190%**、high-Amihud tercileは **6.999%**。これらは別々の重複cohortで合算不可。Long weighted market-cap median **111.6bn円**、Short **1,135.3bn円**。
- Stock-day coverage: Sales Growth **90.44%**、Operating Growth **83.46%**、Profit Growth **82.06%**、OLS8descriptor共通集合 **77.41%**。missing、赤字前年、会計/決算期変更、realized Growthと市場期待styleの差に結論の限界がある。raw CloseとPIT shares/EPSのbasis不整合、自己株式、vendor restatement vintage、Date-only disclosure clockを監査限界として残す。

この結果から新candidateを作らず終了する。
