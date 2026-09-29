# DM-20260924-09: 事前研究計画

Status: planned。全Train既知期間の記述評価を行う。選択・採用・Valid評価には使わない。

## Hypothesis

前営業日終値が前営業日を除く52週レンジのどこにあるかは、価格トレンドの持続状態を表す。前営業日と2営業日前の取引量変化率を加えると、参加の増減を条件として加味できる可能性がある。前段のchannel単独比較はH0比で小幅改善したが不確実性が大きく、既知期間である点も踏まえ、今回の2特徴Ridgeを1条件だけ記述評価する。

## Why it should work / Why it may persist

* 52週レンジ位置は高値側を+1、安値側を-1、中央付近を0とする連続スコアで、単日のブレイク判定より中期の価格状態を保持する。
* 出来高の前日比率変化は、直近の取引参加の増減を簡潔に表す。2特徴だけの線形モデルに限定し、複雑な相互作用を避ける。
* 前日終値と前日/2日前出来高は日次で確定済み。両特徴ともsignal date tではt-1以前の情報だけを使うため、翌寄付後にも価格状態が残るかを検証対象にできる。

## Why it should survive t+1 open

価格channelは250観測の中期状態で、前営業日終値時点で計算可能。出来高変化も前営業日までに確定している。翌寄付で効果が消える可能性は残るため、t+1 Open→t+2 Openの公式targetで評価する。特徴量の将来改変・切り詰めprefix-invarianceを複数cutoffで監査する。

## Expected turnover impact / Leakage risk / Complexity cost

* 毎日更新する連続スコアでturnoverが増える可能性があり、公式五分位weightと片道10bpsコストで評価する。
* channelはraw High/Low/Closeを観測済みAdjustmentFactorイベントの累積でsplit-safe化し、t-251〜t-2の250観測High/Lowとt-1 Closeから算出する。未調整Adjusted OHLCVは読まない。
* volume changeはsplit-safe raw Volumeの`Volume(t-1)/Volume(t-2)-1`。0・欠損・非有限のvolumeは欠損とし、各foldの成熟Train平均で補完する。
* Ridge lambda=1.0、学習targetは日次centered percentile rank、スケーリングと欠損補完は各foldの成熟Trainだけからfit、EWMA alpha=0.25。候補1本で固定する。

## Baselineと変更点

* H0: `DM-20260908-v1` の60観測市場残差Momentum、skip1、EWMA(0.25)。
* B00: 既存のprior-only 250観測新高値Long/新安値Short score、EWMA(0.25)。
* 参考対照: `CHANNEL_250_001` の単独scoreを同条件で再現。
* 候補 `RIDGE_001`: 52週channel positionと1日volume changeの2特徴のみを使うannual expanding Ridge。全系列へEWMA(0.25)を適用する。

## Train-only期間・有限候補・採否基準

* Train入力: 2008-11-04〜2016-03-31。評価foldは2010〜2016年（2016年は1〜3月の部分期間）。各fold開始前にlabel horizon用2取引日をpurgeし、年末・全体終端の最後2signal日を除く。
* 既存channel単独結果はDM-20260924-07の同一定義を参照する。追加試行は`RIDGE_001` 1候補のみ。ridge lambda、window、volume定義を結果後に変更しない。
* 20日paired block bootstrap 1,000回と、各年/foldのNet/Gross Sharpe、RankIC、turnover/cost、Q1-Q5、Long/Short、drawdownを記録する。
* 全Train期間は既読。今回は依頼された固定比較の説明用であり、改善しても独立OOS・採用根拠・Freeze対象にしない。Valid/Valid target/raw targetは読まない。

## 既知データ・確認期間・過去の失敗

* `DM-20260924-07` は本件channel特徴量の単独scoreと同じ時点・250観測定義をEWMA(0.25)付きで評価済み。H0比Net Sharpe +0.1404、改善5/7 fold、bootstrap 95% CI `[-0.3477,+0.6501]`。B00比Net Sharpe -0.4503、改善2/7 foldで、強い候補根拠ではない。この小幅なH0差と正のRankICを、単純な1条件追加の理由に限って使う。
* `DM-20260924-06` の3特徴（60日価格傾き、同じchannel、60日volume z-score）に対するRidge/LightGBMは不採用。今回の特徴組合せとvolume定義・対象パラメータは異なるが、全Trainは既知であり新たな採否判断に利用しない。
* Validは既に別releaseで閲覧済み。新たなValidアクセス、独立期間扱い、結果後の追加探索は行わない。

## 検証・実行コマンド

* 対象特徴量テスト: `.venv/bin/python -m pytest -q tests/strategies/dm_channel_volume_change`
* Train firewall/source scan、raw return・OHLCV・AdjustmentFactor・Train target全入力のcutoff後mutation/truncation prefix-invarianceを2010-12-30、2012-12-28、2015-12-30で検証。成熟Train maskとRidge refit/predictionもbitwise比較。
* Run準備: `.venv/bin/python tools/workspace.py prepare-run DM-20260924-09`
* 期限付きTrain-only実行: `tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.channel_volume_change --config artifacts/DM-20260924-09/<run_id>/config.json --output artifacts/DM-20260924-09/<run_id>`
