# DM-20260924-06: 採否記録

## Decision

**RIDGE_001とLGBM_001の固定条件はともに不採用。** これは事前登録した3特徴量定義と2モデル設定に対する既知Train上の記述判断であり、機械学習や特徴量一般を棄却する結論ではない。全Train期間が既知であるため採用・選択資格はない。

- Run: artifacts/DM-20260924-06/run-20260924T044119Z
- Report: reports/DM-20260924-06/REPORT.md
- 実試行数: 2/2。追加探索なし。
- Train-only: 2008-11-04〜2016-03-31の入力、評価2010-01-04〜2016-03-29。1518評価日、2016年は1〜3月。
- 特徴量: t-60〜t-1 log CloseのOLS傾き、t-1終値のprior-only 250観測High/Low位置、t-1出来高のprior-only 60観測z score。
- モデル: 同一日次centered target rankとfit内標準化を用いたRidge lambda=1と、固定浅型LightGBM。年次expanding fit、EWMA alpha=0.25。

## 結果

- H0: pooled Gross/Net SR 0.3074 / -0.0220、年率Net -0.11%、turnover 0.0646/日、cost 1.63%。
- B00: pooled Gross/Net SR 0.7334 / 0.5687、年率Net +2.50%、turnover 0.0287/日、cost 0.72%。
- RIDGE_001: Gross/Net SR 0.1004 / -0.8349、年率Gross +0.39% / Net -3.22%、年率cost 3.61%、turnover 0.1438/日、RankIC +0.0007、Long +1.63% / Short -4.84%、Max DD -24.44%。年別Net SR改善はH0比3/7、B00比2/7。20日block bootstrap CIはH0比[-2.2881,+0.6646]、B00比[-2.7240,-0.0655]。
- LGBM_001: Gross/Net SR 0.0206 / -1.4550、年率Gross +0.07% / Net -5.23%、年率cost 5.31%、turnover 0.2114/日、RankIC +0.0023、Long +0.86% / Short -6.09%、Max DD -32.59%。年別Net SR改善0/7。20日block bootstrap CIはH0比[-2.8855,+0.0433]、B00比[-3.3121,-0.7954]。

候補の粗利益はコスト控除前から弱く、特にShort損失が大きい。turnoverとcostもH0/B00より高く、当該モデル二条件を進める根拠はない。2010 foldの初回Ridge/LightGBM fitは特徴履歴が揃う2009-11-16以降の29 signal datesのみ。2016 foldは59評価日で、年率換算値の不確実性が高い。

## 検証

- 特徴量の窓境界・出来高z・分割イベント連続性テスト: 3 passed。
- Source scan / Train firewall / future-mutation・truncation prefix-invariance: PASS。2010-12-30、2012-12-28、2015-12-30 cutoffで、特徴量prefix、H0/B00 prefix、成熟Train refitと近傍予測をbitwise照合。
- RIDGE/LightGBM 2016 fold再fit予測: bitwise exact。
- 評価日signal coverage: 682,038/682,038 rows for each method。accountとLong+Short P/L照合PASS。
- Valid / Valid target / raw_targetは未読。
- make check: PASS (19 experiments; 129 frozen file hashes)。
- `make test` は既存tests配置の同名test_features/test_models import mismatchで収集停止。新規特徴量テスト3件はPASS。完全な既存suiteは実行完了していない。

## 今後の制約

全期間が既知のため、Train Sharpeを根拠に定義、符号、窓幅、Ridge lambda、LightGBM構造を追加探索しない。独立評価・採用・Freezeは行わず、Validも読み込んでいない。
