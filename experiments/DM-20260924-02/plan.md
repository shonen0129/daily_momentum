# DM-20260924-02: Long/Short別の新高値・新安値ブレイク合成

Status: completed。Validで見たC3Sのレッグ別損益から着想した事後仮説。全Train期間も既知なので、結果は探索的な記述値に限り、独立した選択・採用根拠にはしない。Validは読み込まない。

## Hypothesis

Longでは、単に過去60日残差モメンタムが高い銘柄より、当日終値が過去250観測の高値を更新した銘柄を優先する。Shortでは、残差モメンタムが低い銘柄のうち、当日終値が過去250観測の安値を下抜けた銘柄を優先する。Long側だけ・Short側だけ・両側のbreakout合成を独立に切り替え、どちらが差分を作るかを4候補で確認する。

## Why it should work / Why it may persist

* 新高値・新安値の更新は、既存の残差Momentum方向を裏づける価格状態として扱う。新高値はLongの継続確認、新安値はShortの下落継続確認を表す。
* 250観測は約52週の価格障壁として固定する。パラメータ探索をしない。Long/ShortはそれぞれMomentum rankとbreakout rankを50/50で合成し、片側の設定をもう片側へ波及させない。
* 反証可能性: breakoutが引けまでに完全に織り込まれる、または希少なイベントがturnover・ギャップリスクを増やしてコスト控除後の改善が残らない可能性がある。

## Why it should survive t+1 open

Breakoutは日中の単発価格変化ではなく、250観測の過去障壁に対する終値更新と定義する。翌寄付までに全て織り込まれる可能性は残るため、t+1 Open→t+2 Openの既存ラベル上でTrain-only評価し、当日の同時High/Lowを障壁に含めない。Valid期間を使って減衰や閾値を調整しない。

## Expected turnover impact / Leakage risk / Complexity cost

* **Turnover / Cost**: breakout確認で入替が減る可能性と、新規更新日に入替が増える可能性の両方がある。方向を仮定せず、日次turnover/costを比較する。
* **Leakage risk**: 入力はTrainのraw High/Low/Close、AdjustmentFactor、raw_return、beta、TOPIX return。現在日tのCloseを`t-1`〜`t-250`の価格障壁と比較し、現在日のHigh/Lowは障壁に含めない。`AdjustmentFactor`イベント累積で価格単位をそろえる。遡及調整OHLCV水準、Valid target、raw targetは使わない。全入力future-mutation prefix-invarianceを検査する。
* **Complexity**: 250観測rolling max/min、rank、既存EWMAだけ。ML学習・追加パラメータなし。新高値と新安値の片側スリーブ3個を追加し、試行上限は4候補（Momentumのみを含む）に固定する。

## Baselineと変更点

* **Baseline M00**: `res60s1` EWMA(0.25)、long/shortともbreakout off。凍結H0 `DM-20260908-v1:M_res60s1_a0.25` を再現する。
* **H10**: Momentum-positive行のLong raw scoreだけ `0.5*res60s1 + 0.5*new_high_rank`。Momentum-negativeのShortは純Momentum。
* **L01**: Momentum-negative行のShort raw scoreだけ `0.5*res60s1 - 0.5*new_low_rank`。Longは純Momentum。
* **HL11**: 上記のLong/Short両方を有効化。
* Toggle-onでも当該sideのMomentum符号は反転させず、Long raw scoreは0未満を0へ、Short raw scoreは0超を0へclipする。250有効観測が揃わないside-rowはその日の合成をMomentumへfallbackする。
* EWMA alpha、ポートフォリオウェイト、片道10 bps costは全候補で固定。現行submissionとC3Sのfreezeは変更しない。

## Train-only期間・有限候補・採否基準

* **入力**: Train 2008-11-04〜2016-03-31。Valid/Valid target/raw_targetを拒否するfirewall下で実行。
* **開発fold**: 2011〜2014年、各年ごと、t+2 target horizonに2営業日purge。
* **過去に見た期間**: 2015-01〜2016-03はTrain内で既読。レポートには参考値として含めるが選択に使わない。
* **有限候補**: M00/H10/L01/HL11のちょうど4本。3件の追加案。blend比・期間・閾値・EWMA alphaは探索しない。
* **評価**: 各fold・各年の全必須指標、M00との差分、20日block bootstrapを記録する。研究仮説に沿ってLong/Short gross・net寄与を分ける。全Trainは既知データで、Valid観測後に着想した仮説でもあるため、どの結果も独立証拠・採用根拠とは扱わない。

## 既知データ・確認期間・過去の失敗

* C3SのValid長短別分析でLongは小幅プラス、Shortはマイナスだった。ただしそのValidは既読で、今回の設計着想に使われた。同じValidを再評価しない。
* `DM-20260923-01`〜`DM-20260924-01`でTrain 2011〜2016-03も既読。C3の企業行動価格単位問題とsplit-safe修正は[DM-20260924-01](../DM-20260924-01/decision.md)。
* 4通り以外へ候補を追加しない。Train成績の良し悪しを見て重み・窓・符号・対象sideの定義を変更しない。

## 検証・実行コマンド

1. Run作成。実験ドライバにsource scan、3 cutoff×mutation/truncation prefix-invariance、M00/H0完全一致、signal coverage、long/short cost reconciliationを含める:
   `.venv/bin/python tools/workspace.py prepare-run DM-20260924-02`
2. 期限付きTrain-only比較:
   `.venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.breakout_side_momentum --config artifacts/DM-20260924-02/<run_id>/config.json --output artifacts/DM-20260924-02/<run_id>`
