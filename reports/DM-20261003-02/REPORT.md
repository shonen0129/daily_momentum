# DM-20261003-02 — Fresh information / industry context / transient pressure

採否: SLOW_FUND_EVENT=REJECT, SLOW_CAUSE_AWARE=REJECT.
2026-10-03 JST。指定2/2候補のみ。既知Trainの研究であり独立OOSではない。Historical Valid/Valid未使用、追加候補・window/weight/threshold変更なし。
Run: `artifacts/DM-20261003-02/run-20261003T070500Z`。計画/設定hashを実装前、code/input/environmentをtarget読込前に固定。

## Pooled results

| strategy | rankic | rankic_t_hac5 | gross_sharpe | net_sharpe | annual_gross | annual_net | turnover | annual_cost | annual_long_net | annual_short_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SLOW_FUND_EVENT | 0.008355 | 2.839502 | 2.185216 | 2.059688 | 0.080456 | 0.075861 | 0.018621 | 0.004594 | 0.074792 | 0.001069 |
| SLOW_CAUSE_AWARE | 0.006552 | 2.342675 | 2.013875 | -0.313298 | 0.068550 | -0.010674 | 0.314840 | 0.079224 | 0.031066 | -0.041739 |
| SLOW_CONTROL | 0.008257 | 2.802064 | 2.179334 | 2.093538 | 0.080272 | 0.077119 | 0.012888 | 0.003153 | 0.075064 | 0.002055 |
| MOM60 | 0.007590 | 1.567643 | 0.613360 | 0.308092 | 0.032108 | 0.016128 | 0.063418 | 0.015981 | 0.046391 | -0.030263 |

P/Lはdecimal。年率=日次平均×252、Sharpe=sample SD×√252、IC t=Newey–West/Bartlett HAC5。Q1低score/Q5高score。Long/Shortは符号付き残差損益。SLOW_CONTROLは不変のglobal Size/Liquidity block、MOM60は記述参照。2016 partialは別集計。

## Full years and 2016 partial

| strategy | scope | net_sharpe | annual_net | turnover | annual_long_net | annual_short_net |
| --- | --- | --- | --- | --- | --- | --- |
| SLOW_FUND_EVENT | 2011 | 2.690472 | 0.120908 | 0.019863 | 0.119457 | 0.001451 |
| SLOW_FUND_EVENT | 2012 | 0.992549 | 0.032558 | 0.019795 | 0.027244 | 0.005314 |
| SLOW_FUND_EVENT | 2013 | 1.880233 | 0.080685 | 0.019667 | 0.063287 | 0.017398 |
| SLOW_FUND_EVENT | 2014 | 1.644590 | 0.050684 | 0.016178 | 0.064535 | -0.013851 |
| SLOW_FUND_EVENT | 2015 | 3.199596 | 0.094981 | 0.017415 | 0.095325 | -0.000345 |
| SLOW_FUND_EVENT | 2016 | 1.990715 | 0.075863 | 0.019271 | 0.094321 | -0.018458 |
| SLOW_CAUSE_AWARE | 2011 | 0.858136 | 0.034524 | 0.309335 | 0.077592 | -0.043068 |
| SLOW_CAUSE_AWARE | 2012 | -1.848714 | -0.057389 | 0.324140 | -0.021624 | -0.035765 |
| SLOW_CAUSE_AWARE | 2013 | -0.241755 | -0.009667 | 0.311892 | 0.016413 | -0.026080 |
| SLOW_CAUSE_AWARE | 2014 | -1.281227 | -0.036291 | 0.311297 | 0.020050 | -0.056341 |
| SLOW_CAUSE_AWARE | 2015 | 0.585090 | 0.016584 | 0.313559 | 0.058473 | -0.041889 |
| SLOW_CAUSE_AWARE | 2016 | -0.367882 | -0.012924 | 0.330664 | 0.052245 | -0.065169 |
| SLOW_CONTROL | 2011 | 2.728793 | 0.122760 | 0.013703 | 0.120853 | 0.001907 |
| SLOW_CONTROL | 2012 | 1.033654 | 0.033888 | 0.013052 | 0.027510 | 0.006378 |
| SLOW_CONTROL | 2013 | 1.896830 | 0.081311 | 0.014252 | 0.063015 | 0.018295 |
| SLOW_CONTROL | 2014 | 1.664345 | 0.051361 | 0.011729 | 0.064063 | -0.012702 |
| SLOW_CONTROL | 2015 | 3.267066 | 0.096957 | 0.011756 | 0.095971 | 0.000986 |
| SLOW_CONTROL | 2016 | 2.003895 | 0.076413 | 0.012628 | 0.093747 | -0.017334 |
| MOM60 | 2011 | 0.506792 | 0.029635 | 0.065571 | 0.075618 | -0.045983 |
| MOM60 | 2012 | 0.636144 | 0.026788 | 0.065148 | 0.013081 | 0.013708 |
| MOM60 | 2013 | 0.081809 | 0.005051 | 0.063355 | 0.038139 | -0.033088 |
| MOM60 | 2014 | 0.910504 | 0.027522 | 0.060468 | 0.050474 | -0.022952 |
| MOM60 | 2015 | -0.099053 | -0.005742 | 0.062057 | 0.045884 | -0.051626 |
| MOM60 | 2016 | 0.067276 | 0.004639 | 0.065295 | 0.084217 | -0.079579 |

## Incremental Flow: B minus A

| scope | delta_rankic | delta_gross_sharpe | delta_net_sharpe | delta_annual_gross | delta_annual_net | delta_turnover | delta_annual_cost |
| --- | --- | --- | --- | --- | --- | --- | --- |
| POOLED | -0.001803 | -0.171341 | -2.372987 | -0.011906 | -0.086535 | 0.296219 | 0.074629 |
| EX2016 | -0.001747 | -0.174518 | -2.372747 | -0.011979 | -0.086426 | 0.295482 | 0.074447 |

## Bootstrap and adoption

| contrast | point_delta | low | high |
| --- | --- | --- | --- |
| POOLED:SLOW_CAUSE_AWARE-SLOW_CONTROL | -2.406837 | -2.735846 | -2.120861 |
| POOLED:SLOW_FUND_EVENT-SLOW_CONTROL | -0.033850 | -0.058845 | -0.012804 |
| POOLED:SLOW_CAUSE_AWARE-SLOW_FUND_EVENT | -2.372987 | -2.700686 | -2.095150 |
| EX2016:SLOW_CAUSE_AWARE-SLOW_CONTROL | -2.407625 | -2.742542 | -2.104606 |
| EX2016:SLOW_FUND_EVENT-SLOW_CONTROL | -0.034878 | -0.060985 | -0.011703 |
| EX2016:SLOW_CAUSE_AWARE-SLOW_FUND_EVENT | -2.372747 | -2.698840 | -2.070036 |

Paired circular20 sessions/2000 reps/seed20261003/95% percentile。POOLED B−SLOW_CONTROL primary。A−control、B−A secondary、EX2016も保存。連結したeligible sessionsの年境界purge gapは連結。探索履歴の多重性は補正しておらず、既知Trainの標本不確実性。

- SLOW_FUND_EVENT: 改善0/5年。不通過: pooled_net_sharpe, ex2016_net_sharpe, full_year_improvements_4_of_5, bootstrap_lower_gt0, annual_net, turnover_le_1_25x, short_net_ge_control.
- SLOW_CAUSE_AWARE: 改善0/5年。不通過: pooled_net_sharpe, ex2016_net_sharpe, full_year_improvements_4_of_5, bootstrap_lower_gt0, annual_net, turnover_le_1_25x, short_net_ge_control, B_net_sharpe_gt_A, B_annual_net_gt_A, Flow_incremental_cost_lt_gross.

## Fixed mechanism diagnostics

| cohort | horizon | event_count | complete_target_count | cumulative_residual_mean | daily_event_return_t_hac5 |
| --- | --- | --- | --- | --- | --- |
| FRESH_UP | 1 | 1234 | 1232 | -0.001042 | -1.187027 |
| FRESH_DOWN | 1 | 891 | 888 | -0.000967 | -0.883840 |
| NO_FUND_WITHIN_NEG_HIGH_VOL | 1 | 139415 | 139405 | 0.000416 | 3.659236 |
| NO_FUND_WITHIN_NEG_NORMAL_VOL | 1 | 151287 | 151275 | 0.000354 | 3.635029 |
| FRESH_UP | 2 | 1232 | 1230 | -0.000241 | -0.557418 |
| FRESH_DOWN | 2 | 890 | 887 | -0.001674 | -1.577401 |
| NO_FUND_WITHIN_NEG_HIGH_VOL | 2 | 139107 | 139095 | 0.000630 | 3.929622 |
| NO_FUND_WITHIN_NEG_NORMAL_VOL | 2 | 150259 | 150239 | 0.000695 | 3.649806 |
| FRESH_UP | 3 | 1231 | 1229 | -0.000324 | -0.080413 |
| FRESH_DOWN | 3 | 887 | 884 | -0.001662 | -1.743083 |
| NO_FUND_WITHIN_NEG_HIGH_VOL | 3 | 138572 | 138558 | 0.000916 | 4.065909 |
| NO_FUND_WITHIN_NEG_NORMAL_VOL | 3 | 149431 | 149405 | 0.000941 | 3.800293 |
| FRESH_UP | 5 | 1228 | 1226 | -0.001162 | 0.594741 |
| FRESH_DOWN | 5 | 885 | 882 | -0.001426 | -1.120073 |
| NO_FUND_WITHIN_NEG_HIGH_VOL | 5 | 137218 | 137192 | 0.001426 | 4.258358 |
| NO_FUND_WITHIN_NEG_NORMAL_VOL | 5 | 148024 | 147990 | 0.001720 | 4.801626 |

1/2/3/5-sessionは固定event studyでholding候補ではない。累積はofficial residual targetの算術和、calendar連続、全ラベル有限、終点t+h+1をyear内にpurge。Industry negative move sector<0/>=0/missingもCSV。イベント重複と将来開示は自然経過を含み、因果識別やhalf-lifeの確定推定ではない。診断結果からcandidateを変更していない。

## Turnover attribution

| strategy | group | average_daily_turnover | annual_cost | annual_delta_gross | annual_delta_cost | annual_delta_net |
| --- | --- | --- | --- | --- | --- | --- |
| SLOW_FUND_EVENT | CURRENT_EVENT | 0.002585 | 0.000650 | 0.000377 | 0.000625 | -0.000249 |
| SLOW_FUND_EVENT | NON_EVENT | 0.013422 | 0.003288 | -0.000159 | 0.000176 | -0.000335 |
| SLOW_FUND_EVENT | PRIOR_EVENT_ONLY | 0.002615 | 0.000657 | -0.000034 | 0.000640 | -0.000674 |
| SLOW_CAUSE_AWARE | CURRENT_EVENT | 0.178523 | 0.044986 | -0.008809 | 0.044159 | -0.052967 |
| SLOW_CAUSE_AWARE | NON_EVENT | 0.023044 | 0.005695 | -0.001989 | 0.003896 | -0.005885 |
| SLOW_CAUSE_AWARE | PRIOR_EVENT_ONLY | 0.113273 | 0.028543 | -0.000925 | 0.028016 | -0.028940 |

CURRENT_EVENT＋PRIOR_EVENT_ONLYがevent-active銘柄のturnover（当日または前日のevent support）。NON_EVENTはその両方に非該当。ENTRY/EXIT/SIGN_FLIP/RESIZEは別の排他的内訳。rank displacementはanchorのquintile membershipとの比較で、entry/exitと重なる別軸。非eventが押し出されるturnover、event翌日の退出も計測。これは観測会計であり真の因果attributionではない。B−Aのstock/daily gross/cost/netは別CSVで照合。

## Definitions and limitations

Fresh fundは総額ForecastOperatingProfitの同一fiscal/basis revisionのみ。Date-only開示EODから最初のsignal sessionに一度だけactive、次日は0。scaled missingはoverlay0、既知fresh revisionならFlow排除。休日開示は次signalに利用可。複数開示は最新を優先。予想据置はno event。Assetsは開示時点既知値、過去へ遡及しない。
Sector33はτのhistorical PIT membership/self-inclusive等weight residual mean、min1。SectorShockはcontextでscoreへ加算しない。raw-returnはopen-to-open、raw通日Volumeは終点open後の取引も含むため同時刻の純粋flow観測ではない。τは共通直前exchange session、株row欠落はmissing。Volume surpriseは固定20観測log1p中央値差。raw Volumeのsplit/単位変化は補正していない。
非event/missing overlayはexact0。active有限のみaverage centered rank、Code ordinalを使わない。singleton/all tie=0、全fund符号を同じevent cross-sectionでrank。指定のcentered percentileのため小さいpositive Flow eventがnegative overlayにもなる。Final official quintile tieは公式Code-orderを保持。再EWMAなし。旧anchorのmedian normalizationと元入力は変更していない。
Negative stock moveの固定4statesはobserved proxy classificationであり真の原因を識別したとは呼ばない。Fresh downward→no-fund sector<0→no-fund sector>=0/Within<0/high-volume→OTHERの順序。各state count/target/HAC5RankIC/LongShort membership/grossを保存しnegative subset損益へ照合。

## Causality and artifacts

全入力個別/joint future mutationとtruncationを3cutoffで全中間特徴量/anchor/2scores bitwise検査。suffix値/NaN/zero/日付・fiscal・basis・sector変更/行削除/future-only stocks、row shuffle、deterministic rebuild、exact index/finite coverage、disclosure/fiscal/basis/Volume/PIT fixtures、adapter/standalone parity。動的検査は試した入力/cutoffの証拠。
保存済みSLOW_CONTROLとMOM60をbitwise再現。SlowRank-only official weights/quintilesと日次P/Lは不変。全Train official weight/netP/L bitwise、LongShort会計1e−15、state/turnover内訳1e−12照合。公式missing-target cost脱落とall-position conservative cost/netを両方保存。全Train上で継続weight/costを計算後、年末2session purge。
`metrics.csv`全指標、`fold_metrics.csv`/`year_metrics.csv`、`incremental.csv`、`long_short.csv`、`quintiles.csv`、`bootstrap.csv`、`event_study.csv`/panel、`cause_state_metrics.csv`/states、`event_coverage.csv`、`event_ties_daily.csv`、`turnover_attribution.csv`/daily/stock panel、`flow_incremental_attribution.csv`、`daily_*.csv`。audit/*、run予測/コードsnapshot/環境/hash/コマンドを保存。

## Interpretation and final verification

**両候補REJECT。** Aはcontrolに対しannual Gross +1.834bp、annual Cost +14.411bp、annual Net -12.577bp。Turnoverは1.445倍で1.25倍制約を超え、2011–2015のNetSR改善は0/5。fresh情報に限定しても今回のrank overlayはnet増分を残さなかった。
B−Aではannual Gross -1.191 percentage points、annual Cost +7.463 points、annual Net -8.654 points。Flowはgrossから悪化し、追加costが損失を拡大した。B/control turnover=24.429倍。Bの92.68%のturnoverが当日または前日event-active銘柄に生じ、非event銘柄もrank displacementで入替えが増えた。short netもcontrolを下回る。
Downward fresh revisionの次target平均はnegativeで2/3/5累積もnegative。一方、Upward fresh revisionの平均もpositiveではなく、up/down全体の対称的continuationは確認できない。これはknown Trainの観測関連で、因果的情報ショックの証明ではない。
高出来高stock-specific下落の1-session event-weighted平均はnormal-volume群を約0.62bp上回るが、日付を揃えた平均差はnegative。2/3/5-session event-weighted差もnegative。両群自体はpositive residual平均を持つため、高出来高に固有の反転増分は弱く、安定したhalf-lifeを確定できない。日付を揃えた平均差/HAC5も保存し、結果から期間を選んでいない。

| horizon | event_weighted_mean_difference | common_date_mean_difference | common_date_hac5_t | common_dates |
| --- | --- | --- | --- | --- |
| 1 | 0.000062 | -0.000106 | -1.030700 | 1274 |
| 2 | -0.000065 | -0.000106 | -0.641937 | 1268 |
| 3 | -0.000025 | -0.000110 | -0.556111 | 1262 |
| 5 | -0.000294 | -0.000364 | -1.360074 | 1250 |

Industry-contextのnegative-stock-move群はsector<0/>=0とも次target平均positive。context別の平均だけでindustry continuationを識別できない。この診断を理由にsector scoreやvetoを追加しない。Sectorをcontextへ置き、fresh fundとFlowを分けても今回の固定Bは低turnover anchorを改善しなかった。前回は別portfolio/rank/missing仕様なので、fresh versus heldの単独効果を因果的に分離した比較ではない。

Scientific runは112.68秒、peak RSS2.604GB（decimal）。レポートコピー時のみ、生成diagnostic parquetの許可登録漏れで失敗したrunを保持。登録を明示して計算済みresultsからcompletion runを作成し、追加performance trialは0、feature/anchor/parametersは不変。
Train split末尾2日の有限label942行はt+2がTrain特徴量期間外となる。事前のyear/pooled/event-study purgeで採否対象から全て除外済み。最終報告のALL_TRAIN参考集計も末尾2sessionを除去した。元のunpurged参考集計は失敗scientific run/completion snapshotに監査用として保持し、選択には利用していない。Raw/β/marketから再構成可能な成熟Train label803101行はt+2 residualと誤差0。
34テスト、real Train24 prefix cases、exact809636-row signal index/finite scores、adapter parity、official P/L、turnover/state accountingを確認。`make check`は既存DM-20261002-04のunsupported metadataで失敗。今回metadataと既存129 Freeze hashesは個別に照合。詳細は`audit/final_verification.json`。

再現: scientific driverはconfig/outputをrunに指定してbounded1800s、report-only recoveryは同driver`--complete-from`（bounded180s）。保存済み結果の最終解釈・Train末尾maturity補正は`research/experiments/cause_event_overlay_report.py --output <completion run>`、最終receiptは`cause_event_overlay_verify.py --output <completion run>`（各bounded180s）。Historical Valid/Valid、提出zip/strategy releaseは実行していない。

Timing clarification:凍結計画/configの「signal t at start」は新event部分の観測cutoff（t開始時点）の表記。変更禁止のSLOW_CONTROL本体は原仕様通りtの日次raw Close/TurnoverValueを使うので、最終scoreの情報時点はcompetition契約のt日終了時点。全入力がt開始時点に利用可能という監査結果ではない。新価格/sector/volume overlayは直前session τ、fresh財務eventはt開始までに公開済みの最初のsessionのみという固定の保守的定義で実行した。最終scoreにはtより後の価格/開示を使用しない。plan/configの原本hashは変更せず、この表記上の区別を監査補足として残す。
