# DM-20260924-03: 新高値Long・新安値Shortを基準にしたモメンタム追加比較

Status: completed。前回の4条件はMomentumを土台にしていたため、今回のユーザー修正に合わせて別設計として事前固定した。C3S Validのレッグ別結果を見た後に発想した仮説であり、全Trainも既知期間。結果は記述値に限り、Validは読まない。

## Hypothesis

Longは250観測の新高値ブレイク、Shortは250観測の新安値ブレイクをベースにする。ブレイクした銘柄にだけres60s1を加えた場合、モメンタム整合性の確認により各レッグの損益が改善するかを、Long/Short独立の4通りで比較する。

## Why it should work / Why it may persist

* 過去250観測の高値を終値で更新した銘柄にはLong continuation、過去安値を終値で割った銘柄にはShort continuationを想定する。
* 60観測残差モメンタムが同じ方向ならブレイクの持続性を補強する可能性がある。一方、日中に知られたブレイク・モメンタムは翌寄付までに価格へ織り込まれる、またはブレイクの少なさが固定五分位portfolioと噛み合わない可能性がある。

## Why it should survive t+1 open

ブレイクは当日終値と過去障壁で定め、当日High/Lowを障壁に含めない。翌寄付までに価格発見が終わる可能性を残したまま、既存の`t+1 Open -> t+2 Open` targetで比較する。Validを使ったdecay調整はしない。

## Expected turnover impact / Leakage risk / Complexity cost

* **Turnover / Cost**: momentum追加はイベント銘柄の順位を変えうるため増減は未確定。公式五分位weight、片道10bpsを4候補で固定する。
* **Leakage risk**: Trainのraw High/Low/Close、AdjustmentFactor、raw_return、beta、TOPIX returnのみ。高値/安値は過去250行にshiftし、当日High/Lowを除外。raw OHLC価格の分割前後単位はAdjustmentFactorイベントの累積で揃える。遡及調整済みOHLCV水準、Valid target、raw targetは使わない。全入力のfuture-mutation prefix-invarianceを実行時監査する。
* **Complexity**: 過去250観測の高値・安値、イベント発生銘柄内のpercentile rank、固定50/50合成、EWMAのみ。モデルfitなし。候補4本を上限とし結果後の追加比較をしない。

## 固定候補・合成定義

* breakout event: `new_high_excess = max(Close_t / prior_high_250 - 1, 0)`、`new_low_excess = max(prior_low_250 / Close_t - 1, 0)`。それぞれ正のイベントだけを日別にpercentile rankし、`strength = 0.5 + 0.5 * percentile`とする。非イベント、250履歴不足は0。
* Long base score: 新高値イベントのstrength、非イベント0。Short base score: 新安値イベントの-strength、非イベント0。
* Momentum追加時はイベント行のみ、`0.5 * breakout_signed_score + 0.5 * res60s1`。Longは0以上に、Shortは0以下にclipし、ブレイクの符号を反転させない。モメンタムONでもイベント外をmomentumで置き換えない。
* B00: Long/Shortともブレイクのみ。M10: LongだけMomentumを追加。M01: ShortだけMomentumを追加。M11:両側に追加。全て最後にEWMA alpha=0.25。

## Train-only期間・比較と採否

* 入力: Train 2008-11-04〜2016-03-31。firewall下でTrain targetのみ読む。Validおよびraw targetは使わない。
* 開発fold: 2011〜2014年。各年の末尾2取引日をt+2 target境界purge。2015-01〜2016-03は既読期間なので参考表のみ、採否に使わない。
* B00を比較基準にし、M10/M01/M11の各fold差分、pooled差分、20日block×1,000回paired bootstrap、Long/Short別netを出す。Gross/Net Sharpe、P/L、Cost、Turnover、RankIC、Q1-Q5、drawdownも記録する。
* 比較結果は既知Trainを使った事後分析でselection_eligible=false。どの候補も採用せず、結果を見て重み・窓・定義を修正しない。

## 既知データ・確認期間

* 前回の`DM-20260924-02`はMomentumをベースにbreakout rankを加える逆向きの設計だった。今回の依頼修正を独立した固定比較として記録する。
* 既読ValidのLong/Short成績が仮説の着想元。今実験ではValidを再読しない。Train 2011–2016-03も過去実験で既知のため独立証拠と呼ばない。
* C3/C3Sの企業行動監査経路は[DM-20260924-01](../DM-20260924-01/decision.md)。

## 検証・実行コマンド

1. 実験driverにsource scan、3 cutoff×mutation/truncation prefix-invariance、4 signal coverage、B00 deterministic replay、Long/Short日次Net会計照合を含める。
2. Run作成: `.venv/bin/python tools/workspace.py prepare-run DM-20260924-03`
3. bounded Train-only run: `.venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.breakout_base_momentum_overlay --config artifacts/DM-20260924-03/<run_id>/config.json --output artifacts/DM-20260924-03/<run_id>`
