# DM-20260924-05: 採否記録

- 判定日: 2026-09-24
- Run ID: run-20260923T191504Z
- 実行結果: Train-only、LINEAR_001 1/1、31.17秒、Valid未読。
- 仮説: 前回LightGBMと同じ4特徴量の加法的関係なら、固定Ridgeがfold安定性と損益を改善する。
- 期間: 2011–2014、974日。各年末2営業日purge。2010はturnover warm-up。
- 特徴量: res60s1、250-observation new-high/new-low rank、split-safe relative volume-change rank。
- Model: 日次centered percentile target rank、過去Trainのみからimputation/標準化、Ridge lambda=1.0、EWMA alpha=0.25。

## 結果

| Strategy | Gross SR | Net SR | 年率Net | 年率Cost | Turnover/日 | RankIC | Long 年率Net / SR | Short 年率Net / SR | Max DD |
|:---|---:|---:|---:|---:|---:|---:|:---|:---|---:|
| H0 Momentum | 0.7703 | 0.4477 | +2.23% | 1.60% | 0.06364 | +0.0080 | +4.42% / 0.8452 | -2.20% / -0.4354 | -10.10% |
| B00 Breakout | 1.0699 | 0.9064 | +3.98% | 0.71% | 0.02837 | +0.0109 | +4.99% / 0.9855 | -1.01% / -0.2134 | -6.99% |
| LINEAR_001 Ridge | -0.7765 | -1.9447 | -8.08% | 4.85% | 0.19363 | -0.0063 | -0.60% / -0.1242 | -7.48% / -1.5053 | -31.68% |

H0比Net SR差は-2.3924、B00比は-2.8511。改善foldは0/4で、20-day paired block-bootstrapの95%区間はH0比[-4.4970,-0.2299]、B00比[-4.6008,-1.1076]。Q1–Q5 monotonicityは-0.700。長短両側で成績が悪化し、Turnover/Costも増えた。

## Decision

LINEAR_001を却下。今回固定した日次rank target・4特徴量・Ridge lambda=1.0の線形仕様はH0/B00を超えず、年次安定性・Short・コストの基準も満たさない。LightGBMより良いモデルとはならなかった。

全TrainとValidは既読で仮説も事後設計のため、追加lambda探索、特徴量の符号反転、別target、相互作用を結果後に試さない。この結果は当該候補1条件の不採用であり、線形モデル一般の無効性を示さない。

## 検証・再現

- 既監査feature builderの再利用、source scan、Train-only firewall: PASS。
- 3 cutoff × mutation/truncationでfeature、H0/B00 signal、成熟Train targetによるRidge refitと予測がbitwise一致。
- 年次モデル5本の決定的再fit: bitwise一致。全評価日prediction coverage、公式会計、Long+Short会計一致: PASS。
- モデルユニットテスト: 2 passed。bounded run exit code 0、1800秒期限内。
- Valid / Valid target / raw_target: 未読。Freezeなし。
- [レポート](../../reports/DM-20260924-05/REPORT.md)、[年別指標](../../reports/DM-20260924-05/fold_metrics.csv)、[比較表](../../reports/DM-20260924-05/model_comparison.csv)、[run metadata](../../artifacts/DM-20260924-05/run-20260923T191504Z/run.json)。
