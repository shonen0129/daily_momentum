# DM-20260924-03: 採否記録

- 判定日: 2026-09-24
- 最終Run: `run-20260923T182752Z`（Train-only、4パターン）
- 仮説: 新高値Long・新安値Shortをベースに、該当側のイベント銘柄へres60s1を50%加える。
- 評価: 2011–2014、各年末t+2越境2取引日をpurgeした974日。2015–2016-03は既知Train参考値のみ。Valid未読。

## 結果

| ID | Momentum追加 | Net SR | B00差 | 改善fold | paired bootstrap 95% CI |
|:---|:---|---:|---:|:---:|:---|
| B00 | なし | 0.9064 | — | — | — |
| M10 | Longのみ | 0.8039 | -0.1025 | 2/4 | [-0.4448, +0.1659] |
| M01 | Shortのみ | 0.9133 | +0.0070 | 3/4 | [-0.0332, +0.0467] |
| M11 | 両側 | 0.8128 | -0.0936 | 1/4 | [-0.4375, +0.1699] |

Shortだけへの追加M01は小幅に上がったが、bootstrap区間はゼロをまたぐ。Short年率NetもB00の-1.01%から-0.99%、Short Net SRは-0.2134から-0.2076で、Short損失をわずかに縮めた程度。Long追加M10はNet SR -0.1025、Long年率Net +4.99%から+4.74%へ低下。両側追加M11も改善しなかった。

結論: momentumをLongへ加える支持はなく、Short追加は記述上わずかに改善したが、安定した増分の根拠はない。どの条件も採用せず、M01の小幅差を根拠に探索・調整・Valid再閲覧をしない。これは今回固定した50/50 overlayの結果であり、Momentum一般またはbreakout一般の無効性を示さない。

## 監査と注意

- Split-safe過去250 High/Low特徴量のsource scan、3 cutoffのfuture-mutation/truncation、4出力coverage/determinism、イベント外score scope・符号、Long+Short会計一致: PASS。
- B00の予測scoreは全行の22.32%が厳密に0。公式五分位は現金化せず全銘柄を順位づけするため、Q1の22.13%、Q5の14.98%は0点同士のtieをstable index orderで割り当てる。疎なブレイク戦略に対するこの採点仕様の影響を含む。
- [レポート](../../reports/DM-20260924-03/REPORT.md)、[年別/fold指標](../../reports/DM-20260924-03/fold_metrics.csv)、[Pooled比較](../../reports/DM-20260924-03/model_comparison.csv)。Freezeなし、Valid未閲覧。
