# DM-20260910-03: 採否記録

## Status: 却下（Train-only採点完了、Valid未閲覧）

Train-only実行を3回試みた。PIT分母preflightは通過したが、採点前に必須の
future-mutation/truncation prefix-invarianceでT3（RANK + EWMA 0.25）の予測が
cutoff以前の25行で不一致となり、当時はポートフォリオ成績を算出・比較・採用していない。
原因は特徴量リークではなく、全期間行列への一括予測時の入力長依存の浮動小数点丸め差だった。
日付単位の固定断面バッチ予測へ修正後、保存済み係数による実データ再現でRAW/RANK/T3の
mutation/truncation prefix差分が全て0件となった。

- 失敗run: `run-20260909T163724Z`（category改変テストの実装バグ）
- 失敗run: `run-20260909T171612Z`（truncation時の空年度prediction境界バグ）
- 最終失敗run: `run-20260909T173133Z`（T3 prefix-invariance 25行不一致）
- PIT分母: raw Volume / strict-prior disclosed issued-and-outstanding shares, 450日失効。
  開発年のcoverageは99%以上、split係数イベント132件のうち90.2%で180日以内の株数更新を確認。
- Valid / raw target: 未参照。Freeze / submission / Valid評価: 未実施。

修正後、新規の完全runで同じ事前登録済みの候補・grid・評価期間を採点した。結果後の候補、
grid、target、window、denominator、モデルの追加・変更はない。

- 対象run / report: `run-20260909T235130Z` / `reports/DM-20260910-03/REPORT.md`
- 実行日 / 実試行数: 2026-09-10 / 5候補（H0, M0, T1, T2, T3）
- 仮説: 日次turnover情報（DTI）が、long/short双方でMomentum H0への安定した増分を持つ。
- Feature / model: strict-prior開示済み発行済株式数を分母とする21日DTI系列。RAW / 日次rank / rank+EWMA(0.25)のElastic Net。
- 選択済みパラメータ: RAW=(alpha 1e-4, l1_ratio 0.1)、RANK=(alpha 3e-4, l1_ratio 0.1)。
- Train評価（2011--2014、974日）: H0 Net SR 0.7839、M0 -0.8450、T1 -11.2462、T2 -9.8885、T3 -2.8882。
- H0との差分: 全候補がNet SR・年次Net損益で劣後。T3でもturnover 0.4183、年率cost 10.50%（H0: 0.0584、1.47%）。
- 時系列安定性: M0はH0比Net SRが4/4年で悪化。T1/T2/T3はいずれも4/4年でNet SRが悪化し、T3のRankICは正でもコスト控除後には残らない。
- 監査: H0再現809,636行でbitwise PASS。Valid / raw_target未参照。future-mutation/truncation prefix-invarianceは3 cutoff・49特徴量で全てbitwise PASS。
- Decision / Reason: **M0/T1/T2/T3を却下**。M0は方向・Shortが悪く、学習版はgross改善があっても回転率とコストが支配してH0へのincremental improvementを満たさない。
- Freeze / Valid: 不採用のためFreeze・submission・Valid評価は行わない。
