# DM-20260924-10 採否

Status: rejected。候補 `BOX_RIDGE_001` は、今回固定した可変長ボックス特徴・Ridge・B00合成定義として採用しない。全Train期間が既知なので、以下は独立OOSや候補選択の証拠ではなくTrain-only記述診断である。Valid評価・Freezeは行わない。

## 結果

- 成功run: `run-20260924T081826Z`。指標・fold差分は[レポート](../../reports/DM-20260924-10/REPORT.md)、実行記録は `artifacts/DM-20260924-10/run-20260924T081826Z/`。
- `BOX_RIDGE_001` pooled Net Sharpe 0.8225、B00 0.8197、差 +0.0028。B00対の20日paired block bootstrap 95%区間は `[-0.0269, +0.0291]`、改善foldは4/6。
- B00比のRankIC差 +0.00007、Gross Sharpe差 +0.0044。Turnoverは0.03117から0.03136/日に増え、年率Costは0.782%から0.787%へわずかに増加。Long年率Netは5.38%から5.36%へ小幅低下し、Short attributionも差はごく小さい。
- 差分の大きさは実務上ほぼゼロで、bootstrap区間はゼロを含む。B00を上回る安定した増分を確認できず、candidateを却下する。

## 実行・検証

- 初回 `run-20260924T081216Z` は2010年fold開始時の成熟新高値イベント99件が最低500件に届かず、候補採点前に停止。成績を見た変更ではなく、2010年をwarm-upにして2011年開始へ移した。同候補・特徴量・パラメータを保った最終runは正常終了。
- 対象テスト **5 passed**、`make check` は **PASS**（23 experiments、129 frozen hashes）。
- Source firewall / leak scan / 3 cutoff future-mutation・truncation prefix-invariance / mature-target fit replay / 576,535全評価行の有限スコアcoverage / Long+Short会計一致はPASS。Valid・Valid target・raw targetは未読。

この判定は今回固定した「5日刻み5〜120日、ATR20の3倍未満、5特徴Ridge、Longイベント50/50合成」に限る。可変長ボックスや圧縮後ブレイク全般が無効だとは結論しない。結果を見て窓・閾値・重み・モデルを追加探索しない。
