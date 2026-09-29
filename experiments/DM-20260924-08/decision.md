# DM-20260924-08: 採否記録

## Decision

**B00_ABS / CHANNEL_250_ABSともに進めない。** 絶対値化はフルTrain pooledのNet SharpeをH0より高くした一方、元の符号付きB00を上回らず、比較区間はいずれもゼロを含む。全Train期間は既知なので記述比較に限り、採用・選択資格はない。

- Run: `artifacts/DM-20260924-08/run-20260924T055758Z`
- Report: [REPORT.md](../../reports/DM-20260924-08/REPORT.md)
- 実試行数: 2/2、事後の条件追加なし。
- Train-only: 入力2008-11-04〜2016-03-31、評価2010-01-04〜2016-03-29（1,518日）。2016年は部分fold、各年境界・全体終端に2日purge。
- 変換: 元のalpha=0.25 EWMA後scoreにabsを適用。再平滑化なし。五分位portfolioにより、絶対値の大きい両端がLong上位に入り、絶対値の低い中央/ゼロ群がShort側に入り得る。

## 結果

| Strategy | Gross SR | Net SR | Annual Net | Cost | Turnover/day | Long Net | Short Net | Max DD |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|
| B00 | 0.7334 | 0.5687 | +2.50% | 0.72% | 0.02870 | +4.60% | -2.10% | -6.99% |
| B00_ABS | 0.6897 | 0.3892 | +1.25% | 0.96% | 0.03828 | +3.63% | -2.38% | -6.28% |
| CHANNEL_250_001 | 0.4036 | 0.1184 | +0.57% | 1.38% | 0.05487 | +3.89% | -3.32% | -10.67% |
| CHANNEL_250_ABS | 0.9950 | 0.3203 | +1.10% | 2.31% | 0.09169 | +4.15% | -3.05% | -8.04% |

- B00_ABSはB00比Net SR -0.1795（95% CI [-1.0710,+0.7459]、正差再標本比率0.362）。年別改善は2/7で、2016年foldがB00を大きく下回った。
- CHANNEL_250_ABSは符号付きchannel比Net SR +0.2020（95% CI [-0.9070,+1.2282]、正差比率0.644）。ただしturnoverは0.05487から0.09169/日、年率costは1.38%から2.31%へ増え、B00比Net SRは-0.2484（95% CI [-1.3140,+0.7855]）。改善foldは元channel比5/7。
- 両ABS候補ともShort年率Netは負。CHANNEL_250_ABSはGross SRが最も高かったが、高turnover/cost控除後にはB00に届かない。

## 検証と制約

- Source scan / Train firewall / featureとsigned/absolute scoreのfuture-mutation・truncation prefix-invariance: PASS（3 cutoff）。
- 全方式682,038/682,038 rows coverage、finite score、Long+Short会計照合: PASS。bounded実行は期限内完了。
- Valid・Valid target・raw targetは未読。既知Trainの記述結果であり独立OOSではない。絶対値化一般の無効性を示すものではないが、今回固定した2条件は不採用とし、追加の窓・平滑化・side探索は行わない。
