---
name: experiment-design
description: シグナル・モデル・パラメータの比較実験をTrain-onlyで設計・評価する。挙動維持や文書修正は対象外。
---

# 戦略改善実験

研究制約・必須指標・採否順位は [AGENTS.md](../../../AGENTS.md) 第9〜16節。
作成・実行・保存は [開発手順](../../../docs/workspace/development_workflow.md) に従う。

## 実行前に固定する

`experiments/<id>/plan.md` と `config.json` に、次を記録する。

- 第15節の仮説・経済的論拠・翌寄付後に残る理由・turnover影響・リークリスク・複雑性。
- Momentum baseline と比較条件。既存採用戦略を加える場合も Momentum との差分を残す。
- 特徴量定義、モデル、有限候補一覧、試行予算、seed、採否基準。
- Train範囲、開発fold、purge、確認期間の扱い。既読期間を未使用holdoutと呼ばない。

時系列は past → future。purge はラベルの終了時刻と次foldの開始時刻から決め、
`t+1 Open → t+2 Open` のラベルが境界を跨がないことを検証する。
行数を営業日数と取り違えない。

## 評価と完了

まず baseline・条件付き集計で仮説を確認する。特徴量・予測経路の変更には
[leak-audit](../leak-audit/SKILL.md) を適用し、Train-only firewall と専用stageで期限付き実行する。
実行コマンド・設定・入力とコードのhash・library version・終了状態を新しいrunに残す。

各fold・各年で第11節の全指標と第12節のbaseline差分を評価し、
時系列安定性・コスト・単純さを優先して採否を記録する。
結果は `reports/<id>/`、採否は `experiments/<id>/decision.md`、
却下理由は `experiments/GRAVEYARD.md`。失敗runも保持する。

事前定義した比較と採否記録で実験を完了する。試行追加は仮説・理由・累積試行数と
予算の変更を記録し、成績だけを根拠に際限なく追加しない。
Freeze・Valid評価は依頼範囲に含まれる場合だけ開発手順の該当段階へ進む。
Validを研究や選択に使用しない。
