# DM-20260924-08: B00 / 52週位置スコアの絶対値化

## 仮説

符号方向ではなく、52週レンジ端であること自体に予測力がある可能性を、既存B00新高値/新安値ブレイクと52週channel-positionで比較する。結果を見て定義や条件を追加しない。

## 事前固定した変換

- `B00_ABS`: 既存B00のEWMA alpha=0.25適用後のスコアに絶対値を取る。
- `CHANNEL_250_ABS`: DM-20260924-07の52週位置スコア（EWMA alpha=0.25適用後）に絶対値を取る。
- 変換後は再平滑化・符号復元・clipを行わない。これによりB00では新高値/新安値ブレイクがともに正方向となる。channel-positionでは高値側/安値側のどちらの端も正方向となる。五分位portfolioでは高い絶対値の端側がLong、絶対値の低い中央やゼロスコア群がShort対象になり得る。
- 比較用にH0、符号付きB00、符号付きCHANNEL_250_001を同じ日付・評価器で再生成する。

## 評価・上限

新候補は2条件（B00_ABS、CHANNEL_250_ABS）のみ。Train入力2008-11-04〜2016-03-31、同じ評価日2010-01-04〜2016-03-29（1,518日想定）、t+2境界を2日purge。2016年は部分年。公式五分位weight、片道10bps cost、EWMA alpha=0.25は元仕様どおり。

全Train期間は既に既知で、独立OOSではないため、全結果は記述比較・選択資格なし。Valid/Valid target/raw targetは未使用。結果後の追加試行、別変換順、窓、平滑化、side変更は禁止。

## 検証

既存監査済みの特徴量・signed scoreをTrain-onlyで再生成。2010-12-30、2012-12-28、2015-12-30のmutation/truncation cutoffで、元scoreとabs変換後scoreのprefix-invarianceを照合。coverage、finite score、Long+Short会計、同一日付の比較を確認。20日paired bootstrap 1,000反復を記録。
