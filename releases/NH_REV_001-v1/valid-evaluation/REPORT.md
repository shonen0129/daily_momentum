# NH_REV_001 — VALID

Run: `/Users/takahashimasatoshi/Library/Mobile Documents/com~apple~CloudDocs/個別株/daily_momentum/releases/NH_REV_001-v1/valid-evaluation`

## 事実

Validは過去に別リリースで評価済み。今回も独立・未使用holdoutではない。Trainは実装・方向・伝達経路の診断に限る。

Primaryは元のRS60対targetのdaily Spearman平均。score=-RS60のICは逆符号。HAC lag=5。日別等ウェイト、5行以上、分位集計は5つ以上の異なる値がある日。

raw RS60 IC: **-0.001195**; HAC t: -0.127; 負方向Hit: 49.68%。
score IC: **0.001195**; HAC t: 0.127; 正方向Hit: 49.68%。
有効IC日数: 1554; event行数: 28576。
raw Q5-Q1: -0.024280%/日; monotonicity: -0.100。
score Q5-Q1: 0.042651%/日。

| Period | raw IC | HAC t | negative hit | raw Q5-Q1/day | score IC |
|---|---:|---:|---:|---:|---:|
| 2016 | -0.03326 | -0.75 | 50.0% | -0.27494% | 0.03326 |
| 2017 | -0.01462 | -0.74 | 51.7% | -0.11821% | 0.01462 |
| 2018 | -0.02988 | -1.29 | 54.7% | -0.14160% | 0.02988 |
| 2019 | -0.01687 | -0.43 | 53.8% | -0.09451% | 0.01687 |
| 2020 | 0.00663 | 0.20 | 48.1% | 0.13841% | -0.00663 |
| 2021 | 0.00310 | 0.09 | 47.4% | 0.07781% | -0.00310 |
| 2022 | -0.00663 | -0.17 | 50.0% | -0.06457% | 0.00663 |
| 2023 | 0.02422 | 0.91 | 50.0% | 0.05531% | -0.02422 |
| 2024 | 0.02095 | 0.76 | 44.6% | 0.08570% | -0.02095 |
| 2025 | 0.02131 | 0.77 | 45.6% | -0.00108% | -0.02131 |
| 2026 | -0.03141 | -0.79 | 56.4% | -0.11047% | 0.03141 |

Q1–Q5・日次IC・年別HAC/Hitの全数値は `annual_metrics.csv`, `event_daily.csv`, `event_summary.json`。年別は時系列foldであり学習なし。年末・split末の2 signal日を除外。2016 Train/Validと2026 Validは部分年。

Primary不合格のためValid portfolio集計・SR評価を実施しない。監査用weightsと日次Gross/Net/cost/turnover ledgerは保存し、救済選択には用いない。

## 解釈

固定した負方向効果は、このValid上の事前基準を満たさない。portfolio調整による救済は行わない。

## 未確認事項

未使用区間での独立再現性、因果的な経済メカニズム、別の注入方式、Short再設計は未確認。今回のfuture-mutation PASSは試験した入力とcutoffの範囲での証拠。

## 判定

**NO-GO / CLOSED**。不合格基準: ic_magnitude, hac_evidence, quintile_direction, annual_stability, ic_not_few_days, spread_not_few_days。次Phaseは実行しない。

再現性・監査は `audit.json`, `run.json`。公式costは片道10bp、日次平均×252で年率化。Sharpeは標本標準偏差、DDは累積和・複利の両方。公式の欠損target行cost除外と全保有costを別保存。raw/score分位は同点のCode順配分により完全反転しない場合がある。
