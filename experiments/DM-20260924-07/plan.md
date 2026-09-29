# DM-20260924-07: 52週レンジ位置単独スコア

既存の監査済み52週channel-positionを単独スコアとする一条件のTrain-only比較。結果と採否はdecision.mdへ記録する。

## 仮説

前営業日終値が直近52週レンジの高値側にある銘柄は相対的に強く、安値側にある銘柄は相対的に弱い可能性がある。高値を+1、安値を-1とする連続スコアなら、単純な新高値/新安値イベントよりレンジ内の位置も表現できる。

## 特徴量・タイミング

シグナル日tに、前営業日終値Close(t-1)を、前営業日自体を除いた過去250観測（t-251〜t-2）のsplit-safe High最大・Low最小に対して線形写像する。

position_t = 2 * (Close(t-1) - LowMin(t-251:t-2)) / (HighMax(t-251:t-2) - LowMin(t-251:t-2)) - 1

過去高値=+1、過去安値=-1。レンジ外ブレイクは±1を超えた値のまま保持する。rolling履歴不足またはHigh/Low幅が0のときは中立値0。raw OHLCとAdjustmentFactorだけを使い、イベント累積で因果的にsplit-safe化する。

スコア系列には既存実験と共通のEWMA alpha=0.25を適用する。公式五分位順位・weight・片道10bps costを使い、Long/Shortを別途集計する。

## 期待・リスク

52週高値への近さやその上抜けがトレンド持続を示す可能性がある。一方、52週レンジ内の位置だけでは取引方向の継続を示さないこと、既に織り込まれた高値情報がt+1寄付までに消えること、低位置銘柄Shortが反発局面で損失を出すことがリスク。連続順位を毎日更新するため、B00よりturnover/costが増える可能性がある。特徴量は前回のfuture-mutation/truncation prefix監査済みで、この実験では再計算可能な既存builderを変更しない。

## 比較・Train期間・試行上限

固定候補1つ CHANNEL_250_001をH0残差MomentumおよびB00新高値Long/新安値Shortと、2010〜2016-03の同一評価日で比較する。各年の境界前2取引日をt+2ラベルのpurgeで評価から除き、各年末2シグナル日とTrain最終2日も評価から除く。1,518日を評価対象とする想定。2016年は部分年。

全TrainとValid分析は既知のため、全結果は記述値であり、selection_eligible=false。候補の追加、窓・alpha変更、Valid閲覧やFreezeは行わない。20日paired block bootstrapを1,000回記録する。

## 実行と検証

Train firewall/source scan、2010-12-30・2012-12-28・2015-12-30 cutoffのmutation/truncationでchannel score prefixとH0/B00 prefixを厳密比較、全評価日coverage・有限値・会計照合、期限付き実行を行う。既存特徴量の定義・sourceは変更しない。

Run準備: .venv/bin/python tools/workspace.py prepare-run DM-20260924-07

期限付き実行: .venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.channel_position_250 --config artifacts/DM-20260924-07/<run_id>/config.json --output artifacts/DM-20260924-07/<run_id>
