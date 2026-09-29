# NH_REV_001 — TRAIN

Run: `/Users/takahashimasatoshi/Library/Mobile Documents/com~apple~CloudDocs/個別株/daily_momentum/artifacts/DM-20260925-02/run-20260925T063642Z`

## 事実

Validは過去に別リリースで評価済み。今回も独立・未使用holdoutではない。Trainは実装・方向・伝達経路の診断に限る。

Primaryは元のRS60対targetのdaily Spearman平均。score=-RS60のICは逆符号。HAC lag=5。日別等ウェイト、5行以上、分位集計は5つ以上の異なる値がある日。

raw RS60 IC: **-0.038625**; HAC t: -2.923; 負方向Hit: 54.72%。
score IC: **0.038625**; HAC t: 2.923; 正方向Hit: 54.72%。
有効IC日数: 689; event行数: 14487。
raw Q5-Q1: -0.139732%/日; monotonicity: -1.000。
score Q5-Q1: 0.118564%/日。

| Period | raw IC | HAC t | negative hit | raw Q5-Q1/day | score IC |
|---|---:|---:|---:|---:|---:|
| 2011 | 0.02872 | 0.47 | 44.9% | 0.09355% | -0.02872 |
| 2012 | -0.09137 | -2.86 | 63.5% | -0.34274% | 0.09137 |
| 2013 | -0.02186 | -0.88 | 51.5% | -0.16515% | 0.02186 |
| 2014 | -0.05236 | -2.35 | 54.0% | -0.06612% | 0.05236 |
| 2015 | -0.04072 | -1.89 | 56.3% | -0.12650% | 0.04072 |
| 2016 | 0.18673 | 2.02 | 50.0% | -0.19127% | -0.18673 |

Q1–Q5・日次IC・年別HAC/Hitの全数値は `annual_metrics.csv`, `event_daily.csv`, `event_summary.json`。年別は時系列foldであり学習なし。年末・split末の2 signal日を除外。2016 Train/Validと2026 Validは部分年。

### Portfolio (official accounting)

| Metric | B00 | NH_REV_001 | Delta |
|---|---:|---:|---:|
| rankic | 0.010869 | 0.011125 | +0.000256 |
| gross_sharpe | 0.988384 | 1.003637 | +0.015253 |
| net_sharpe | 0.819703 | 0.833562 | +0.013859 |
| annual_gross | 0.046079 | 0.046436 | +0.000356 |
| annual_net | 0.038256 | 0.038606 | +0.000350 |
| annual_cost | 0.007823 | 0.007829 | +0.000006 |
| turnover | 0.031173 | 0.031198 | +0.000025 |
| max_drawdown_compound | -0.068124 | -0.068078 | +0.000046 |
| annual_long | 0.059417 | 0.059893 | +0.000476 |
| annual_short | -0.013338 | -0.013457 | -0.000120 |

平均|weight差|=0.00005655; 変更銘柄日=3.09%; event score対最終weight相関=-0.02111。

## 解釈

Train上の方向とパイプラインを確認する記述値。探索済みTrainの好成績から採用可能性を主張しない。

## 未確認事項

未使用区間での独立再現性、因果的な経済メカニズム、別の注入方式、Short再設計は未確認。今回のfuture-mutation PASSは試験した入力とcutoffの範囲での証拠。

## 判定

TrainからはGo判定しない。固定仕様・基準をFreezeして一度だけValid評価する。

再現性・監査は `audit.json`, `run.json`。公式costは片道10bp、日次平均×252で年率化。Sharpeは標本標準偏差、DDは累積和・複利の両方。公式の欠損target行cost除外と全保有costを別保存。raw/score分位は同点のCode順配分により完全反転しない場合がある。
