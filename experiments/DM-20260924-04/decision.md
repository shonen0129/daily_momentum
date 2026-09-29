# DM-20260924-04: 採否記録

- 判定日: 2026-09-24
- Run ID: run-20260923T185552Z
- 実行結果: Train-only、候補1/1、実行31秒、Valid未読。
- Hypothesis: 新高値/新安値ブレイク、res60s1、相対出来高変化の条件付き関係を浅いLightGBMが捉える。
- 期間: 2011–2014の974評価日。各年末2取引日purge。2010はturnover warm-up。
- Feature / Model: res60s1、250-observation high/low breakout rank、split-safe raw volumeのprior-20 median比rank。LGBMRegressor depth=2、leaves=4、60 trees、min child=500、learning rate=.05、lambda=10、seed=20260924、EWMA alpha=.25。

## 結果

| Strategy | Gross SR | Net SR | 年率Net | Turnover/日 | RankIC | Long 年率Net / SR | Short 年率Net / SR | Max DD |
|:---|---:|---:|---:|---:|---:|:---|:---|---:|
| H0 Momentum | 0.7703 | 0.4477 | +2.23% | 0.06364 | 0.0080 | +4.42% / 0.8452 | -2.20% / -0.4354 | -10.10% |
| B00 Breakout | 1.0699 | 0.9064 | +3.98% | 0.02837 | 0.0109 | +4.99% / 0.9855 | -1.01% / -0.2134 | -6.99% |
| LGBM_001 | -0.6704 | -1.9564 | -5.90% | 0.15536 | -0.0047 | +0.57% / 0.1273 | -6.48% / -1.3473 | -22.96% |

LGBM_001はH0比Net SR -2.4041、B00比 -2.8627で、改善foldは両方とも0/4。paired 20-day block-bootstrap 95%区間はH0比[-4.3882,-0.4006]、B00比[-4.5720,-1.2340]。年間costは3.89%でH0の1.60%、B00の0.71%を上回った。Q1–Q5 monotonicityは-0.400。Short側の損失が特に大きく、出来高変化を含むこの固定モデルは採用しない。

## Decision

この1候補を却下。既知Train上でH0/B00の双方に負け、fold安定性・コスト・Long/Short一貫性のどれも満たさない。今回の固定仕様以外へ一般化してLightGBM全般を否定する結果ではないが、この結果を見て窓・深さ・特徴量・符号を追加探索することもしない。別の根拠または新しい未使用期間が得られるまで、この仮説の後付け調整を保留する。

## 検証・再現

- feature prefix-invariance、H0/B00信号prefix、成熟Train labelでの再fitと候補予測prefixを3 cutoff × mutation/truncationでbitwise一致。
- Source scan、Train-only firewall、prediction coverage、H0/B00/LGBM日次会計とLong+Short reconciliation: PASS。
- Strategy feature unit tests: 3 passed。LightGBM年次モデル5本をartifactに保存。bounded実行exit code 0、期限1800秒内。
- Valid / Valid target / raw_target: 未読。
- [レポート](../../reports/DM-20260924-04/REPORT.md)、[年別指標](../../reports/DM-20260924-04/fold_metrics.csv)、[比較表](../../reports/DM-20260924-04/model_comparison.csv)、[run metadata](../../artifacts/DM-20260924-04/run-20260923T185552Z/run.json)。

Freezeなし。2015–2016-03の既知Train参考値も今回は使っていない。
