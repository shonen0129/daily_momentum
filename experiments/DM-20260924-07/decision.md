# DM-20260924-07: 採否記録

## Decision

**CHANNEL_250_001は独立の戦略候補として進めない。** 固定した52週channel-position単独scoreはH0を上回る点推定だったが、20日block bootstrap区間はゼロを跨ぎ、B00には大きく届かなかった。全Train期間は既知のため、これは記述比較であり選択・採用根拠ではない。

- Run: `artifacts/DM-20260924-07/run-20260924T051044Z`
- Report: [REPORT.md](../../reports/DM-20260924-07/REPORT.md)
- 実行日: 2026-09-24。事前固定1条件を実行（1/1）。追加探索なし。
- Train-only: 入力2008-11-04〜2016-03-31、評価2010-01-04〜2016-03-29、1,518評価日。2016年は1〜3月の部分fold。年境界・終端で2取引日purge。
- 仮説 / 変更: 前日終値を、それ以前250観測のHigh/Low間へ写像し、高値側+1・安値側-1の連続scoreとして単独利用。レンジ外はclipせず、履歴不足は0。EWMA alpha=0.25。
- 比較: H0残差Momentum、B00新高値Long/新安値Shortと同一日付・五分位portfolio・片道10bps costで比較。

## 結果

| Strategy | Gross SR | Net SR | Annual Net | Cost | Turnover/day | RankIC | Long Net | Short Net | Max DD |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| H0 | 0.3074 | -0.0220 | -0.11% | 1.63% | 0.06460 | 0.0041 | +3.59% | -3.70% | -10.10% |
| B00 | 0.7334 | 0.5687 | +2.50% | 0.72% | 0.02870 | 0.0067 | +4.60% | -2.10% | -6.99% |
| CHANNEL_250_001 | 0.4036 | 0.1184 | +0.57% | 1.38% | 0.05487 | 0.0071 | +3.89% | -3.32% | -10.67% |

- H0比のNet SR差は+0.1404だが、paired 20日block bootstrap 95%区間は[-0.3477,+0.6501]。正の再標本比率は0.714。
- B00比はNet SR差-0.4503、95%区間[-0.9109,+0.0544]。CHANNELはH0よりturnover/costが低かったものの、B00より両方高く、B00のNet SRとドローダウンを下回った。
- 年別Net SRはH0比で5/7年、B00比で2/7年だけ改善。Long年率Net +3.89%に対してShortは-3.32%で、弱いShort側は解消していない。

## 検証と制約

- Source scan / Train firewall / feature・signal future-mutationおよびtruncation prefix-invariance: PASS（3 cutoff）。
- Prediction coverage: 各戦略682,038/682,038 rows。有限score、Long+Short会計照合: PASS。
- Bounded実行は期限内完了。Valid・Valid target・raw targetは未読。
- 全Trainは既読済み。追加窓・EWMA・side・閾値探索は行わず、この固定単独scoreは不採用とする。
