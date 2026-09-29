# DM-20260925-03: 採否記録

Status: rejected。高値・安値方向の可変長BOX RidgeをB00と混ぜず単独スコア化した固定候補1本をTrain-onlyで記述評価した。全Train期間は既読のため、独立OOSや採用根拠ではない。

## 実験記録

- Run: `run-20260926T063602Z`。実試行数1/1、累積試行数1。
- Hypothesis: 52週高値・安値ブレイク前の圧縮状態・位置・方向別contextから同方向継続性を推定し、LongとShortの両側を独立に順位付けできる。
- Change: 高値/安値を別々のannual expanding Ridge (lambda=1.0)で学習。安値側の位置・残差モメンタム・ prior low距離を方向に合わせて反転。高値scoreは正、安値scoreは負、非イベントは0。B00 scoreを混ぜず、EWMA alpha=0.25。
- Window: Train 2008-11-04〜2016-03-31、評価2011-01-04〜2016-03-29。2016年は部分fold、年末2取引日をpurge。
- Report: [Train-only比較](../../reports/DM-20260925-03/REPORT.md)。

## 結果・判断

- Standalone candidate: Gross Sharpe 0.9580、Net Sharpe 0.7851、年率Gross +4.45%、年率Net +3.65%、年率Cost 0.80%、Turnover 0.03185/日、RankIC +0.0110、Max DD -6.23%。
- B00: Net Sharpe 0.8197、年率Net +3.83%、Turnover 0.03117/日、Cost 0.78%。候補との差はNet Sharpe -0.0346、bootstrap 95% CI [-0.1616,+0.0688]、改善fold 2/6。Long年率Net +5.30% (B00 +5.38%)、Short -1.65% (B00 -1.56%)。
- 候補の点推定・コスト・turnoverはいずれもB00を下回る。区間は0を含み改善の確証はないため、この固定仕様を却下し、結果後の再調整・追加候補は行わない。
- High event 15,314行、Low event 4,296行。両sideとも年次Ridgeの最低500成熟学習行を満たした。

## 検証・有効性の範囲

- 対象回帰テスト: **10 passed**。`make check`: **PASS**（27 experiments、129 frozen hashes）。
- Source scan、Train-only firewall、3 cutoff×mutation/truncation prefix-invariance、全576,535評価行のfinite score coverage、決定性replay、Long+Short会計一致: **PASS**。
- 実Train全809,636行で `submission.predict()` と保存済みstandalone scoreの完全一致を確認。
- Valid、Valid target、raw target: **未読**。Freeze・外部提出なし。
- スコア出力: `artifacts/DM-20260925-03/run-20260926T063602Z/predictions/signals.parquet`。side別イベント予測: `predictions/event_predictions.parquet`。
