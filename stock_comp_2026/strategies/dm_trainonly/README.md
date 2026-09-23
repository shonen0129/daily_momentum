# DM-20260908-v1

Train-onlyで選択した60日市場残差Momentum＋EWMA（α=0.25）。ML補正は採用しない。

`residual[t] = raw_return[t] - beta[t] * topix_return[t]`。
各銘柄の直前60観測営業日（t-1〜t-60）の残差リターンを合計し、当日断面の平均順位を中心化して[-1,1]へ写す。
そのスコアに銘柄別 `ewm(alpha=0.25, adjust=False)` を適用する。
60個の有限観測がない場合は平滑化前のスコアを0とする。
銘柄コードが20営業日ordinal超の間隔で再登場した場合は履歴・EWMAをリセットする。
少数の行欠落がある場合、窓は取引所暦の厳密な60日ではなく銘柄の直前60観測行である。

## 予測契約

`predict()` はcwdのfeatureファイルを使用する。後続splitのfeatureがあるときはTrain履歴を連結し後続splitの行を返す。
Train-onlyの場合はTrain行を返す。明示呼出は `predict(data_dir, split="train")`。
入力は `raw_return_1day`、`beta_1day`、`topix_return_1day` の3系列のみ。
ラベル、株価水準、銘柄属性、財務、外部API、ネットワーク、GPU、学習済みモデルは不要。
提出zipはこのディレクトリのsubmission.py/features.py/frozen_config.json/README.mdのみを含む。
研究比較用models.pyはzipに含めない。

## 選択結果と限界

選択用Train開発期間2011〜2014年: Gross Sharpe 0.729、Net Sharpe 0.400、年率cost1.628%、日次turnover0.0646。
4年のNet Sharpeはいずれも正だが2013年は0.040と弱い。
選択後のTrain確認期間2015〜2016年3月29日: Net Sharpe -0.088。
候補の定義は固定したが、収益性の統計的な採用根拠は不足している。実運用採用は保留。
Validのデータ読込・評価・選択利用は行っていない。
Freezeの詳細はfrozen_config.json、全比較・却下理由は ../../../reports/DM-20260908/REPORT.md を参照。
