# DM-20260924-06: 60日価格傾き・52週レンジ位置・出来高zスコア

事前計画。実行後の結果と採否はdecision.mdを参照。特徴量定義を固定し、Train-onlyでRidgeとLightGBMを各1条件だけ比較した。

## Hypothesis

過去60観測の価格トレンド傾き、52週レンジ内で前営業日終値がどの位置にあるか、過去60観測に対する前営業日の出来高ショックを組み合わせると、トレンドの持続と高値/安値近辺の状態、参加の強さを簡潔に表現できる可能性がある。

## Why it should work / Why it may persist

対数価格OLS傾きは価格水準に依存せず、単日の変動よりも期間を通した方向を捉える。チャンネル位置は52週の高値を+1、安値を-1に写像し、レンジ中央を0とする。出来高zスコアは銘柄自身の直近分布から外れた参加量を表す。これらは公開済みの日次価格・出来高に基づく低次元の特徴で、取引可能なclose後の状態を記述する。

## Why it should survive t+1 open

予測対象はシグナル日tの後のt+1 Openからt+2 Open。特徴量に使う観測はすべてt-1以前に確定した値とするため、少なくともtの引け情報が翌寄付までに消える問題は避ける。翌寄付後にも残るかは固定walk-forwardで記述評価する。

## Expected turnover impact / Leakage risk / Complexity cost

連続特徴を毎日更新してcross-sectionへ流すため、既存Momentumよりturnoverが上がる可能性がある。OHLCVはraw値を使い、AdjustmentFactorの観測済みイベント累積で企業行動を跨ぐ単位を揃える。rolling窓はsignal dateより前で終え、train mean/std・欠損補完は各foldの成熟Trainだけから推定する。Ridgeと浅い決定木各1条件のみで、試行予算は合計2。

## Baselineと変更点

同一評価日・公式五分位weight・片道10bpsで、既存H0（60観測残差Momentum、EWMA 0.25）とB00（ prior-only 250観測新高値Long/新安値Short）を参照する。候補モデルの目的変数は両方とも日次横断centered percentile rankとし、同じ三特徴量、同じfold、同じfit-only標準化、同じEWMA 0.25を使用する。

特徴量の固定定義:

1. Momentum: 前営業日t-1までのsplit-safe Close対数値60観測を等間隔OLS回帰し、傾きを10,000倍してbp/観測日で記録。傾き計算の観測窓はt-60〜t-1。
2. 52週channel position: 前営業日Closeを、その前の250観測High最大/Low最小へ線形写像する。2*(Close(t-1)-LowMin(t-251:t-2))/(HighMax(t-251:t-2)-LowMin(t-251:t-2))-1。高値=+1、安値=-1。範囲外ブレイクは±1を超える値として保持。
3. Volume: 前営業日split-safe raw Volumeを、それより前の60観測t-61〜t-2の平均・母標準偏差でzスコア化。標準偏差0は欠損としてfold内平均で補完。

候補はRidge lambda=1.0、LightGBM depth=2 / leaves=4 / 60 trees / min child=500 / learning rate=0.05 / lambda=10 / seed=20260924各1条件。候補を横断rank化せず、特徴量値を保持し、両モデルでfold内平均補完・標準化する。

## Train-only期間・有限候補・採否基準

Trainファイル範囲は2008-11-04〜2016-03-31。250観測窓と拡大型fitを成立させる最初の年次foldを2010年とし、2010〜2016年3月までを評価する。年ごとに前年末までの成熟Train targetでfitし、fold境界を跨ぐt+2ラベルのため直前2取引日をpurgeする。各fold最終2シグナル日とTrain全体最終2日は評価しない。2016年はQ1までの部分fold。

候補2つ（RIDGE_001、LGBM_001）、最大試行数2。モデル・特徴量の追加探索はしない。H0 / B00に対するNet Sharpe差、年別fold一貫性、gross/net、cost/turnover、RankIC/t-stat/hit、Q1-Q5単調性、Long/Short、最大DDを合わせて記述評価する。全Trainは既知、selection_eligible=falseとし、結果から仕様変更や採用を行わない。比較には20取引日paired block bootstrap 1,000回を記録する。

## 既知データ・確認期間・過去の失敗

2011〜2014 TrainはDM-20260924-04/-05などで参照済み。2015〜2016-03も以前に参照済みで、今回も未使用確認期間ではない。Validは読み込まない。過去の固定LGBM/Ridge breakout-volume実験はH0とB00の双方を下回って却下済み。本件は特徴定義を変更した新しい事後記述実験で、独立検証・採用根拠にはしない。

## 検証・実行コマンド

戦略feature unit tests、Train firewall / source scan、2010-12-30・2012-12-28・2015-12-30 cutoffの全入力future-mutationとtruncation prefix-invariance、成熟targetによるRidge/LightGBM refitと近傍予測、代表foldの決定性replay、index・NaN処理・prediction coverage・account reconciliationを検査する。

Run準備: .venv/bin/python tools/workspace.py prepare-run DM-20260924-06

期限付き実行: .venv/bin/python tools/run_bounded.py --seconds 3600 .venv/bin/python -m research.experiments.slope_range_volume_ml --config artifacts/DM-20260924-06/<run_id>/config.json --output artifacts/DM-20260924-06/<run_id>
