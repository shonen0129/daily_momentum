# DM-20260924-04: Breakout × Momentum × Volume Change LightGBM

Status: planned。既読Valid分析と既知Train比較から着想した事後仮説。Train-onlyの記述実験とし、候補採択には使わない。

## Hypothesis

250観測の新高値/新安値ブレイク強度、residual 60日モメンタム、直近の相対出来高変化を浅いLightGBMへ入力すると、木がブレイクと出来高確認の条件付き関係を捉え、Momentum-onlyおよびBreakout-onlyより翌寄付後のクロスセクション順位を改善する可能性がある。

## Why it should work / Why it may persist

新高値更新と新安値割れは価格方向を示し、60日residual momentumは継続方向の事前情報、出来高変化は参加の強さを表す。木の浅い分岐なら「ブレイクが出来高を伴うときだけ継続」といった少数の条件を表現できる。遅いファンダメンタル情報を追加せず、日次価格・出来高の観測だけを使う。

## Why it should survive t+1 open

特徴量はシグナル日の引けまでに確定する。ブレイクの障壁は当日High/Lowを除いた過去250観測から作る。出来高変化は当日raw Volumeと当日より前の20観測medianを比較する。予測対象は従来どおりt+1 Openからt+2 Open。引け後のブレイク・出来高情報が翌寄付に完全に織り込まれる可能性はあり、翌寄付後に残るかは固定walk-forwardで測る。

## Expected turnover impact / Leakage risk / Complexity cost

相対出来高とイベント条件で日々の順位が変わり、回転率は増える可能性がある。全信号へEWMA alpha=0.25を共通適用し、公式片道10bpsコストで評価する。

入力はTrain raw OHLCV、AdjustmentFactor、raw_return、beta、TOPIX returnとTrain targetのみ。価格は既監査済みのsplit-safe builderを利用する。出来高はraw VolumeにAdjustmentFactorの累積積を掛けて株式分割を跨ぐ単位を揃え、先行20観測median比の対数を日次クロスセクションrank化する。将来ラベルは各年fold開始の2営業日前までに成熟したTrain targetのみをfitに使う。Validおよびraw_targetにはアクセスしない。

LightGBMの新候補は1条件だけ。max_depth=2、num_leaves=4、60 trees、min_child_samples=500の浅い決定木で、feature/horizon/parameter searchはしない。処理は決定論的seed固定、CPU 2 threads、期限30分。

## Baselineと変更点

同じ2011–2014評価日・purge・official quintile weight・片道10bpsで、H0 res60s1 EWMA(0.25)と純ブレイクB00を参照比較する。新候補は次の4入力を使う: residual 60-observation rank、prior-only 250-observation new-high excessの断面rank、同new-low excessの断面rank、raw volumeの先行20観測median比rank。出力はLightGBM regression予測にEWMA(0.25)を適用する。モデルの構造・特徴量・seed・評価方法は事前固定。

## Train-only期間・有限候補・採否基準

入力はTrain split。初期モデル年は2010年で2008年以降の利用可能なラベルを使い、2011–2014各年のモデルは各fold開始の2営業日前までに成熟したTrain targetでexpanding-window fitする。2011–2014各年の最後2営業日を評価からpurgeする。2015–2016-03は既読なので評価・採否に使わない。

候補はLGBM_001一つ、最大試行数1。H0とB00は比較参照であり追加候補ではない。Net Sharpe、改善fold数、20営業日paired block bootstrap、Gross/Net、Cost/Turnover、RankIC、Q1–Q5、Long/Short、最大DDを報告する。既知Train/既読Valid分析後の仮説なのでselection_eligible=false。結果が良くても採用・仕様変更・Valid再閲覧をしない。記述上の診断目安はH0とB00の双方に対するNet Sharpe差、少なくとも3/4 fold改善、コスト後のLong/Short・順位単調性の一貫性とする。

## 既知データ・確認期間・過去の失敗

2011–2014 Trainと2015–2016-03参考Trainはすでに過去実験で確認済み。Validも既読で、今回再読しない。直前のDM-20260924-03ではB00のNet Sharpe 0.9064、H0対照のDM-20260924-02では0.4477だったが、全期間既知・事後設計で、疎なB00 scoreの同点順位問題を含む。DM-20260924-02のMomentum上への単純breakout overlayはH0よりNet Sharpeを下げた。今回は一つの非線形条件付きモデルだけを診断し、結果後の追加試行を行わない。

## 検証・実行コマンド

対象strategy feature builderのsource firewall、3 cutoffでのfuture-mutation/truncation prefix-invariance、Train label成熟時点を含む学習/prediction prefix-invariance、coverage・determinism・会計照合を実行する。

Run準備: .venv/bin/python tools/workspace.py prepare-run DM-20260924-04

期限付きTrain-only実行: .venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.breakout_momentum_volume_lgbm --config artifacts/DM-20260924-04/<run_id>/config.json --output artifacts/DM-20260924-04/<run_id>
