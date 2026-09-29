# DM-20260924-02: 採否記録

- 判定日: 2026-09-24
- 戦略: `dm_breakout_side_momentum`
- 最終Run: `run-20260923T174435Z`（Train-only、実施4パターン）
- 試行記録: 初回run `run-20260923T174110Z` はM00/H0の予測が不一致と判明したため無効化。中心化を修正し、同じ4候補を再実行した。候補追加・パラメータ変更はなし。
- 仮説: MomentumのLongに250観測新高値、Shortに250観測新安値を別々に合成すると継続確認になる。
- 変更: 各側のMomentum rankと対応するbreakout rankを固定50/50で合成。EWMA alpha 0.25、公式五分位weight、片道10bps costを共通化。
- 評価: Train 2011–2014、各年末のt+2越境2取引日をpurge。2015-01〜2016-03は既知Train参考値に限定。Valid未読。

## 結果

M00のNet Sharpeは0.4477（Gross 0.7703、年率Net +2.23%、turnover/日0.06364）。基準M00は既存H0予測809,636行とbitwise完全一致した。

| 条件 | Pooled Net SR | ΔNet SR | 改善年 | Bootstrap 95% CI (ΔNet SR) | Long 年率Net / Net SR | Short 年率Net / Net SR |
|:---|---:|---:|:---:|:---|:---|:---|
| M00: 両側off | 0.4477 | — | — | — | +4.42% / 0.8452 | -2.20% / -0.4354 |
| H10: Long新高値on | 0.3858 | -0.0619 | 0/4 | [-0.1217, -0.0089] | +4.19% / 0.8013 | -2.26% / -0.4475 |
| L01: Short新安値on | 0.4057 | -0.0420 | 0/4 | [-0.0787, -0.0077] | +4.35% / 0.8299 | -2.34% / -0.4642 |
| HL11: 両側on | 0.3663 | -0.0814 | 0/4 | [-0.1354, -0.0307] | +4.15% / 0.7930 | -2.33% / -0.4630 |

3つのoverlay全てでNet Sharpeが4/4年低下し、Bootstrap区間もゼロ未満だった。Overlayはturnoverと年率costも上げた。今回の固定された50/50・250観測定義は不採用とする。事後のValid由来仮説かつ既知Trainでの比較なので、結果から別定義を探索・選択しない。これは新高値/新安値ブレイク一般の無効性を意味しない。

## 監査・成果物

- Source scan、3 cutoffでのfuture mutation / truncation prefix-invariance: PASS。
- M00/H0完全一致、予測index/finite coverage、Long+Short日次Net損益と全体Net損益の一致: PASS。
- 詳細結果: [レポート](../../reports/DM-20260924-02/REPORT.md)、[年別/fold比較](../../reports/DM-20260924-02/fold_metrics.csv)、[Pooled比較](../../reports/DM-20260924-02/model_comparison.csv)。
- 完了状態: 実験完了、候補不採用、Freezeなし、Valid未閲覧。
