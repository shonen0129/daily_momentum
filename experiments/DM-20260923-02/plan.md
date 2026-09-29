# DM-20260923-02: 60日・250日高値近接度の等ウェイト合成

Status: planned。探索候補はC6の1件に固定。Train期間は既知データなので、結果は事後的・探索的な参考値とし、選択・採用には使わない。

## Hypothesis

60日高値近接度は直近の抵抗水準への接近を、250日高値近接度は長期の参照価格への接近を表す。両者を等ウェイトで合わせれば、60日成分の短期反応性と250日成分の低回転・持続性を両立できるかもしれない。

## Why it should work / Why it may persist

* 60日と250日は価格アンカーの異なる時間軸を測る。同じ銘柄が複数期間で高値に近ければ、継続性の強い上昇状態を識別できる可能性がある。
* Momentumの半分を保ち、残り半分をprox60とprox250に四分の一ずつ配分する。期間・係数を追加探索せず、単一の等ウェイト合成だけを評価する。
* 高値近接度はシグナル日tまでの価格履歴から得る状態量で、t+1寄付の小さなギャップで直ちに消える短期情報ではないと考える。ただし対象がt+1 Openからt+2 Openの1日残差リターンであり、持続性は本Train比較だけでは独立に確認できない。

## Expected turnover impact / Leakage risk / Complexity cost

* **Turnover / Cost**: 60日成分によりC3単独より回転率が上がる可能性がある。合成後の順位・portfolio turnoverは非線形なので、結果を単純平均から推定せず、公式accountingで直接測る。
* **Leakage risk**: 新規入力はなく、既存のraw `prices_daily_quotes`、raw return、PIT beta、TOPIX returnのみを利用する。全入力源のfuture-mutationとtruncationを実データで監査する。遡及調整価格は使用しない。raw高値は分割をまたぐ比較に不整合が残りうる点を解釈上の制約として記録する。
* **Complexity**: 固定線形合成1本。モデル学習・係数最適化・追加horizon探索なし。

## Baselineと変更点

* **Baseline**: H0、Championの60日残差Momentum `res60s1` + EWMA(0.25)。
* **C6**: C2とC3のスコアストリームを50:50合成する。EWMA前の式は `0.5*res60s1 + 0.25*prox60 + 0.25*prox250`、EWMA alphaは0.25。
* 研究実装にC6を追加する。submissionの既定候補やChampionは変更しない。

## Train-only期間・有限候補・採否基準

* **Train期間**: 2008-11-04〜2016-03-31。初期warmupは2008〜2010。
* **開発fold**: 2011、2012、2013、2014。各foldで`t+2 Open`ラベルがfold境界をまたがないよう2営業日purge。
* **有限試行**: H0 baseline再現 + 新規候補C6の1件。`max_trials=2`はbaseline込み。係数・期間の結果後変更は行わない。
* **診断基準**: 3/4 fold以上でNet Sharpe改善、中央値差>0、pooled Net Sharpe改善、TurnoverがH0の1.5倍以内を記録する。基準通過も探索的screen passに留め、候補選択・採用には使わない。
* Bootstrapは20日block、1000回、seed固定。信頼区間は選択調整なしの記述統計として示す。

## 既知データ・確認期間・過去の失敗

* この組み合わせはDM-20260923-01のC2/C3結果を見た後に依頼された事後的な単一検証である。2011〜2014および2015〜2016-03は以前の研究で利用済みで、独立OOSではない。
* 2015〜2016-03は既知の記述情報として算出しても、選択基準に含めない。
* 本実験ではValidを読まない。選択や採用を目的にせず、結果を見た後の追加試行も行わない。

## 検証・実行コマンド

1. 戦略回帰、C6算式、prefix-invariance:
   `.venv/bin/python -m pytest -q tests/strategies/dm_high_proximity_momentum`
2. 実行stage作成:
   `.venv/bin/python tools/workspace.py prepare-run DM-20260923-02`
3. 期限付きTrain-only実験:
   `tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.high_proximity_momentum --config artifacts/DM-20260923-02/<run_id>/config.json --output artifacts/DM-20260923-02/<run_id>`
