# DM-20260924-05: Breakout × Momentum × Volume Change Ridge

Status: planned。前のLightGBM一条件が大きく悪化したため、同じ特徴量を足し合わせる線形モデルを一条件だけ評価する。Train-onlyの記述実験で、Validは使わない。

## Hypothesis

前実験と同じ4特徴量（res60s1、250観測新高値rank、新安値rank、出来高変化rank）に対し、浅い木の分岐や相互作用が過適合の原因なら、学習期間内で標準化した特徴量のRidge線形結合は、年次fold間でより安定し、H0またはB00へ近づく可能性がある。

## Why it should work / Why it may persist

特徴量の方向が 여러 시代で概ね加法的なら、Ridgeは係数を縮小しながら低次元の情報をまとめる。4列だけなので推定自由度を抑えやすい。木より線形が必ず良いとはせず、目的変数を日次cross-sectional rankに固定し、各市場日のreturn尺度変化・外れ値によるfit支配を抑える。

## Why it should survive t+1 open

特徴量はsignal day tの引けまでの既知情報。高値・安値は当日High/Lowを除くprior-only 250観測、出来高変化は当日raw Volumeをstrictly prior 20観測medianと比較する。従来のt+1 Open→t+2 Openラベルで将来の順位予測力を測り、翌寄付までに消える効果は成績に残らない。

## Expected turnover / Leakage risk / Complexity

線形係数は年次refit時に変わるためturnoverは増えるおそれがある。EWMA alpha=0.25は全候補に共通。公式片道10bpsでcostを評価する。

feature valuesは前実験で監査済みの同一Train-only builderを再利用する。Ridgeのimputation mean/scaleはfit期間だけで計算し、欠損をfit期間meanに置換する。目的変数rankもfitに使うTrain signal datesごとに横断順位化し、その日t+2まで成熟したtargetのみ学習へ入れる。Valid / raw_targetを読まない。

候補はRidge lambda=1.0の一条件だけ。追加feature、horizon、regularization search、interaction searchはしない。CPUで4係数+interceptを閉形式で解く。

## Baselineと変更点

DM-20260924-04と同じ2011–2014評価日、各年末2取引日purge、H0 res60s1、B00純ブレイク比較、五分位weight、片道10bps costを使う。feature builderを変更せず、目的変数とモデルだけを固定変更する。

特徴量4列をfit期間mean/stdで標準化し、欠損はfit平均を代入する。Train target Returnを日ごとにcentered percentile rank [-1, 1]へ変換し、Ridge lambda=1.0、intercept unpenalizedでfitする。年次expanding-window、出力EWMA alpha=0.25。

## Train-only期間・試行予算・採否基準

Train splitのみ。2010年モデルはportfolio turnoverのwarm-upに使い、2011–2014各foldのモデルは各年初の2取引日前までに成熟した過去Train targetでfitする。評価は2011–2014、各年末2取引日をpurge。既知2015–2016-03は使わない。

候補はLINEAR_001一つ、max trials=1。H0/B00は固定比較対象。fold/pooled Net Sharpe、Gross/Net、turnover/cost、RankICとHAC t/hit、Q1–Q5、Long/Short、MaxDD、paired 20-day block bootstrapを報告する。3/4以上の改善foldは今後の候補検討に必要な記述目安だが、既知データなので採用資格にはならない。事後の仕様変更や追加探索はしない。

## 既知データ・確認期間

2011–2014 Train、2015–2016-03 Train、Validはいずれも既読。直前の固定LGBM_001はH0 Net SR 0.4477、B00 0.9064に対して-1.9564、Turnover 0.1554/day、Short年率Net -6.48%だった。この状況でのRidge比較は事後仮説であり、同じTrainを独立holdoutとは呼ばない。Validは再読せず、採用・Freezeもしない。

## 検証・実行コマンド

再利用feature source scan、3 cutoffのmutation/truncation featureと予測一致、未来target改変後のmature-label Ridge refit/prediction一致、index・NaN・coverage・決定性・日次会計一致を確認する。

Run準備: .venv/bin/python tools/workspace.py prepare-run DM-20260924-05

期限付きTrain-only実行: .venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.breakout_momentum_volume_linear --config artifacts/DM-20260924-05/<run_id>/config.json --output artifacts/DM-20260924-05/<run_id>
