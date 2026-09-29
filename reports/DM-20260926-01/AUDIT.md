# DM-20260926-01 現行ポートフォリオ監査

- Run: `run-20260926T143032Z-08`; source run: `run-20260926T063602Z`; Train only; Valid / raw target 未読。
- 評価日: 2011-01-04〜2016-03-29（1275日）。2016部分期間: 2016-01-04〜2016-03-29（59日）。
- Score・Box event・side predictionはDM-20260925-03の保存parquet、公式Train targetと同日PIT sectorはTrain入力から取得。保存daily accountとの差は照合済み。
- 五分位は `(Date, Code)` 順にscoreを `rank(method='first')`、公式evaluate_scriptと同じ `qcut(..., 5)`。したがって厳密な同点はCodeの文字列順で決まる。Tie-break零点はQ1/Q5のscore=0保有として切り出した。
- イベント年齢の保有weight/P&LはEWMA残存source score絶対値で分配。Stock-daysには最大sourceを1件割り当て、fractional stock-daysも併記。Event attributionは実際の5分位保有内の記述帰属で、独立取引結果ではない。

## 現行BOX・B00のポートフォリオ内容

| Strategy | Net年率 | Net SR | Turnover/日 | Q1零点stock比 | Q1零点weight比 | Q5零点stock比 | Q5零点weight比 | 0点Code順rho | 0点が複数分位の日 |
|---|---|---|---|---|---|---|---|---|---|
| B00_BASE | +3.83% | +0.8197 | +0.0312 | +6.10% | +6.01% | +0.00% | +0.00% | +0.7305 | 182 |
| BOX_ORIGINAL | +3.65% | +0.7851 | +0.0319 | +9.46% | +9.48% | +0.68% | +0.70% | +0.8117 | 379 |
| A_LOW_NO_CARRY | +3.02% | +0.7389 | +0.0459 | +51.01% | +51.87% | +0.68% | +0.70% | +0.9035 | 512 |
| A_B00_LOW_NO_CARRY | +3.32% | +0.8016 | +0.0446 | +48.30% | +49.12% | +0.00% | +0.00% | +0.7715 | 474 |

公式weight式ではQ1/Q2がShort、Q3は中立でweight 0、Q4/Q5がLong。Q1はShort側の最下位quintile、Q5はLong側の最上位quintile。`q1_zero_*` と `q5_zero_*` はscore=0のうち当該tailへCode順tie-breakで割り当てられたstock-day / gross weight比。Long/Short表の `score_zero_tail_tie_break` と `score_zero_non_tail_tie_break` はscore=0の実保有で、後者のうち内側quintileに入った保有も同じ `rank(method='first')` のCode順で割り当てられる。`zero_code_order_spearman_q` は複数quintileにまたがる日ごとに0点group内の辞書順ordinalとq番号の相関を求め、その日次平均を取った診断である。

## Long / Short実保有の構成

以下は実weightのうち、High/Lowのイベント年齢、score=0、その他が占めた割合。スコアゼロ銘柄もQ1/Q5へ選ばれれば実保有として数える。

### Long sleeve

| Strategy | 分類 | 実stock-days | 配賦stock-days | Long gross weight比 | 年率Gross寄与 | 年率Net寄与 | Turnover比 |
|---|---|---|---|---|---|---|---|
| BOX_ORIGINAL | high_event_day | 12019 | +10573.4975 | +5.94% | +0.07% | -0.16% | +41.08% |
| BOX_ORIGINAL | high_age_1_4 | 33622 | +30915.6314 | +16.42% | +0.89% | +0.81% | +15.18% |
| BOX_ORIGINAL | high_age_5_plus | 170999 | +175113.1083 | +73.21% | +4.76% | +4.53% | +40.66% |
| BOX_ORIGINAL | low_event_day | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| BOX_ORIGINAL | low_age_1_4 | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| BOX_ORIGINAL | low_age_5_plus | 0 | +37.7629 | +0.02% | -0.00% | -0.00% | +0.00% |
| BOX_ORIGINAL | score_zero_tail_tie_break | 781 | +781.0000 | +0.47% | -0.03% | -0.03% | +0.28% |
| BOX_ORIGINAL | score_zero_non_tail_tie_break | 13279 | +13279.0000 | +3.95% | +0.16% | +0.15% | +2.80% |
| BOX_ORIGINAL | other | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| B00_BASE | high_event_day | 12502 | +10752.4211 | +5.99% | +0.01% | -0.21% | +40.72% |
| B00_BASE | high_age_1_4 | 33291 | +30893.2720 | +16.41% | +0.96% | +0.88% | +15.45% |
| B00_BASE | high_age_5_plus | 179635 | +183745.5574 | +76.01% | +4.90% | +4.67% | +42.45% |
| B00_BASE | low_event_day | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| B00_BASE | low_age_1_4 | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| B00_BASE | low_age_5_plus | 1934 | +1970.7495 | +0.59% | +0.02% | +0.02% | +0.70% |
| B00_BASE | score_zero_tail_tie_break | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| B00_BASE | score_zero_non_tail_tie_break | 3338 | +3338.0000 | +0.99% | +0.04% | +0.03% | +0.68% |
| B00_BASE | other | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_LOW_NO_CARRY | high_event_day | 12019 | +10573.6652 | +5.94% | +0.07% | -0.16% | +38.15% |
| A_LOW_NO_CARRY | high_age_1_4 | 33622 | +30916.2953 | +16.42% | +0.89% | +0.81% | +13.98% |
| A_LOW_NO_CARRY | high_age_5_plus | 177301 | +181452.0395 | +75.10% | +4.75% | +4.48% | +43.72% |
| A_LOW_NO_CARRY | low_event_day | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_LOW_NO_CARRY | low_age_1_4 | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_LOW_NO_CARRY | low_age_5_plus | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_LOW_NO_CARRY | score_zero_tail_tie_break | 781 | +781.0000 | +0.47% | -0.03% | -0.03% | +0.26% |
| A_LOW_NO_CARRY | score_zero_non_tail_tie_break | 6977 | +6977.0000 | +2.08% | +0.02% | -0.01% | +3.89% |
| A_LOW_NO_CARRY | other | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_B00_LOW_NO_CARRY | high_event_day | 12502 | +10752.5893 | +5.99% | +0.01% | -0.22% | +38.28% |
| A_B00_LOW_NO_CARRY | high_age_1_4 | 33291 | +30893.9351 | +16.41% | +0.96% | +0.88% | +14.35% |
| A_B00_LOW_NO_CARRY | high_age_5_plus | 184907 | +189053.4756 | +77.60% | +4.94% | +4.65% | +47.37% |
| A_B00_LOW_NO_CARRY | low_event_day | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_B00_LOW_NO_CARRY | low_age_1_4 | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_B00_LOW_NO_CARRY | low_age_5_plus | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_B00_LOW_NO_CARRY | score_zero_tail_tie_break | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_B00_LOW_NO_CARRY | score_zero_non_tail_tie_break | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_B00_LOW_NO_CARRY | other | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
### Short sleeve

| Strategy | 分類 | 実stock-days | 配賦stock-days | Short gross weight比 | 年率Gross寄与 | 年率Net寄与 | Turnover比 |
|---|---|---|---|---|---|---|---|
| BOX_ORIGINAL | high_event_day | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| BOX_ORIGINAL | high_age_1_4 | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| BOX_ORIGINAL | high_age_5_plus | 84776 | +84799.0016 | +30.25% | -1.02% | -1.12% | +43.42% |
| BOX_ORIGINAL | low_event_day | 3359 | +3057.7816 | +1.70% | +0.23% | +0.19% | +19.23% |
| BOX_ORIGINAL | low_age_1_4 | 9419 | +8907.5667 | +4.90% | -0.20% | -0.20% | +0.62% |
| BOX_ORIGINAL | low_age_5_plus | 116538 | +117327.6501 | +55.09% | -0.25% | -0.32% | +28.83% |
| BOX_ORIGINAL | score_zero_tail_tie_break | 10959 | +10959.0000 | +6.33% | -0.13% | -0.14% | +3.56% |
| BOX_ORIGINAL | score_zero_non_tail_tie_break | 5851 | +5851.0000 | +1.72% | -0.05% | -0.06% | +4.34% |
| BOX_ORIGINAL | other | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| B00_BASE | high_event_day | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| B00_BASE | high_age_1_4 | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| B00_BASE | high_age_5_plus | 84780 | +84789.4846 | +30.24% | -1.02% | -1.12% | +44.68% |
| B00_BASE | low_event_day | 3454 | +3089.6347 | +1.72% | +0.28% | +0.23% | +19.58% |
| B00_BASE | low_age_1_4 | 9349 | +8879.9481 | +4.89% | -0.23% | -0.23% | +0.59% |
| B00_BASE | low_age_5_plus | 124587 | +125410.9326 | +58.66% | -0.23% | -0.31% | +32.65% |
| B00_BASE | score_zero_tail_tie_break | 7063 | +7063.0000 | +4.01% | -0.11% | -0.11% | +1.62% |
| B00_BASE | score_zero_non_tail_tie_break | 1669 | +1669.0000 | +0.47% | -0.02% | -0.02% | +0.88% |
| B00_BASE | other | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_LOW_NO_CARRY | high_event_day | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_LOW_NO_CARRY | high_age_1_4 | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_LOW_NO_CARRY | high_age_5_plus | 126292 | +126292.8366 | +50.73% | -1.31% | -1.49% | +34.29% |
| A_LOW_NO_CARRY | low_event_day | 4287 | +4286.1634 | +2.41% | +0.27% | +0.07% | +36.21% |
| A_LOW_NO_CARRY | low_age_1_4 | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_LOW_NO_CARRY | low_age_5_plus | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_LOW_NO_CARRY | score_zero_tail_tie_break | 59078 | +59078.0000 | +34.65% | -0.66% | -0.71% | +11.31% |
| A_LOW_NO_CARRY | score_zero_non_tail_tie_break | 41245 | +41245.0000 | +12.21% | +0.15% | +0.06% | +18.20% |
| A_LOW_NO_CARRY | other | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_B00_LOW_NO_CARRY | high_event_day | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_B00_LOW_NO_CARRY | high_age_1_4 | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_B00_LOW_NO_CARRY | high_age_5_plus | 145584 | +145584.5508 | +57.32% | -0.84% | -1.06% | +42.62% |
| A_B00_LOW_NO_CARRY | low_event_day | 4287 | +4286.4492 | +2.41% | +0.29% | +0.10% | +35.50% |
| A_B00_LOW_NO_CARRY | low_age_1_4 | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_B00_LOW_NO_CARRY | low_age_5_plus | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |
| A_B00_LOW_NO_CARRY | score_zero_tail_tie_break | 55931 | +55931.0000 | +32.82% | -0.59% | -0.64% | +10.55% |
| A_B00_LOW_NO_CARRY | score_zero_non_tail_tie_break | 25100 | +25100.0000 | +7.45% | -0.33% | -0.39% | +11.32% |
| A_B00_LOW_NO_CARRY | other | 0 | 0.0000 | +0.00% | +0.00% | +0.00% | +0.00% |

## Q1/Q5 score-zero tie-breakと業種

詳細な日次・銘柄内訳は `holdings_audit.parquet` に保存。Sector33は各Date/Codeの `listed_info_train` PIT値を使用した。次表は、実際にtailへ入ったscore=0銘柄の業種構成を、その同日のscore=0全体の業種構成と比べる。Sector33の上位偏り・不足は `sector_zero_tail_bias.csv` に全件保存。

A_LOW_NO_CARRYではLow残存Short weightが 60.0%→0.0% になり、代わりにaged Highは 30.2%→50.7%、score=0のCode順tie保有は 8.1%→46.9% を占めた。Short枠は消えず、Q1のscore=0比率も上表のとおり増加している。

| Strategy | Tail | Sector33 | 0点全体比 | Tail 0点比 | 差 | Tail gross weight比 | 年率Gross P/L |
|---|---|---|---|---|---|---|---|
| A_B00_LOW_NO_CARRY | Q1 | 建設業 | +4.69% | +7.00% | +2.31% | +5.75% | -0.14% |
| A_B00_LOW_NO_CARRY | Q1 | 電気･ガス業 | +9.10% | +6.94% | -2.16% | +1.90% | +0.02% |
| A_B00_LOW_NO_CARRY | Q1 | 陸運業 | +5.24% | +3.09% | -2.15% | +0.62% | -0.00% |
| A_LOW_NO_CARRY | Q1 | 食料品 | +4.91% | +8.91% | +4.00% | +6.38% | -0.41% |
| A_LOW_NO_CARRY | Q1 | 建設業 | +2.98% | +6.73% | +3.75% | +5.84% | -0.16% |
| A_LOW_NO_CARRY | Q1 | 化学 | +5.43% | +8.99% | +3.56% | +7.53% | +0.16% |
| A_LOW_NO_CARRY | Q5 | 情報･通信業 | +6.57% | +27.81% | +21.24% | +9.14% | -0.01% |
| A_LOW_NO_CARRY | Q5 | 電気･ガス業 | +3.42% | +21.33% | +17.90% | +9.09% | +0.00% |
| A_LOW_NO_CARRY | Q5 | 小売業 | +6.88% | +18.26% | +11.38% | +5.41% | +0.01% |
| B00_BASE | Q1 | サービス業 | +12.35% | +10.99% | -1.35% | +1.28% | +0.01% |
| B00_BASE | Q1 | 水産・農林業 | +2.84% | +4.07% | +1.22% | +0.40% | +0.00% |
| B00_BASE | Q1 | 食料品 | +8.69% | +9.90% | +1.21% | +1.23% | -0.06% |
| BOX_ORIGINAL | Q1 | 食料品 | +8.53% | +11.09% | +2.56% | +2.87% | -0.05% |
| BOX_ORIGINAL | Q1 | 建設業 | +2.10% | +3.96% | +1.86% | +1.74% | -0.07% |
| BOX_ORIGINAL | Q1 | 水産・農林業 | +2.67% | +3.87% | +1.21% | +0.45% | +0.00% |
| BOX_ORIGINAL | Q5 | 情報･通信業 | +6.60% | +27.81% | +21.21% | +9.14% | -0.01% |
| BOX_ORIGINAL | Q5 | 電気･ガス業 | +3.44% | +21.33% | +17.89% | +9.09% | +0.00% |
| BOX_ORIGINAL | Q5 | 小売業 | +6.85% | +18.26% | +11.41% | +5.41% | +0.01% |

0点tailのticker順が偏りを作る場合、同点処理だけで個別銘柄・業種・P&Lが固定される。今回の監査は実現した順序依存とその寄与を計測し、別tie-breakでの再運用は候補化していない。

## 共通残差ドリフトと銘柄選択

各日の同じ評価universeにおける公式市場残差target平均を共通成分とし、`valid weight exposure × universe mean` を共通寄与、残差差分をcross-sectional selection寄与とした。Long、Short、合計の和はGross P/Lと一致する。これは会計分解であり、共通因子の因果推定ではない。

| Strategy | Common Gross寄与 | Selection Gross寄与 | Long共通 | Long選択 | Short共通 | Short選択 | Net exposure×μ proxy |
|---|---|---|---|---|---|---|---|
| B00_BASE | +0.05% | +4.56% | +3.50% | +2.44% | -3.45% | +2.11% | -0.00% |
| BOX_ORIGINAL | +0.05% | +4.39% | +3.50% | +2.37% | -3.44% | +2.03% | -0.00% |
| A_LOW_NO_CARRY | +0.09% | +4.08% | +3.50% | +2.21% | -3.41% | +1.87% | -0.00% |
| A_B00_LOW_NO_CARRY | +0.10% | +4.35% | +3.50% | +2.41% | -3.41% | +1.93% | -0.00% |
| B_BOX_GATE_B00_SCORE | +0.05% | +4.44% | +3.50% | +2.44% | -3.45% | +2.00% | -0.00% |
| B_BOX_GATE_RIDGE | +0.06% | +3.77% | +3.50% | +2.13% | -3.44% | +1.64% | -0.00% |
## Box eligibility coverage

評価期間のHighイベントは適格 10,262 / 15,314（不適格 5,052, 33.0%）、Lowイベントは適格 2,707 / 4,296（不適格 1,589, 37.0%）。B2/B3は不適格イベントを通さず、両raw scoreの非ゼロ行が同一適格イベント集合に一致することを実行時確認した。


## 年別・fold別

`fold_metrics.csv` は各yearを独立行として全指標を保存し、`category_by_year.csv` はBOX/Low-no-carry/B00のcategory別stock-days、gross weight、P/L、Turnoverを年/fold別に保存する。`annual_category_attribution.csv` は同じ区分のpooled年率。2016は上記の部分期間であり、月数を推測していない。

## 再現・制約

- Saved-account replay max absolute discrepancy: 1e-16。公式qcut weightsと既存evaluation.weightsは完全一致。
- PIT sector join coverage: 100.00%; duplicate sector keys: 0.
- B00 / BOX saved score replay: 0 / saved BOX EWMA inversion: 1.11e-16.
- Eligible-event prefix mutation/truncation: **PASS** at 3 cutoffs; full details: `../artifacts/DM-20260926-01/run-20260926T143032Z-08/audit/prefix_invariance.json`.
- Train期間は既読。Score-age attribution・common drift splitはいずれも記述診断で、独立OOSや将来期待値ではない。
