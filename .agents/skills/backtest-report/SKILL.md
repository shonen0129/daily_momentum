---
name: backtest-report
description: バックテスト結果から、fold・年別指標とbaseline差分を追跡できるレポートを作る。
---

# バックテストレポート

必須指標・採否基準・記録項目は [AGENTS.md](../../../AGENTS.md) 第11〜16節。
既存結果の報告では保存済みartifactを使い、不足値と理由を明示する。
報告依頼だけで学習・探索・Valid評価を追加しない。

## 入力と集計

実験ID・run ID、計画・設定、コード版、Train/評価窓、fold・purge、seed、
実行コマンドと元artifactを対応付ける。研究比較はTrain-onlyに限定する。
Freeze後のValid最終評価を報告する依頼では、凍結版を特定して研究比較から分離する。

- 各fold・各年について第11節の全指標を載せ、比較では第12節のbaseline差分を並記する。
- 主評価のSharpe・DD・turnoverは全評価営業日を対象とし、都合のよい日を除かない。
  空系列・NaN/Inf・ゼロ分散は扱いを記録し、未計測値をゼロで埋めない。
- 公式採点と実験のweight、turnover、コストの定義・単位を照合する。
  片道0.1%なら `cost_t = 0.001 × turnover_t`、
  年率costは `mean(cost_t) × 252`。年内実額と年率換算を区別する。
- Sharpeの年率化、DDの資産曲線、RankIC t-statの推定法を明記する。
  分位の方向とLong/Shortの符号は実装を確認し、慣例で決めない。

## 成果物

`reports/<experiment_id>/REPORT.md` と比較表に、再現情報、全体・fold別・年別成績、
baseline差分、Q1〜Q5とLong/Short、時系列安定性の解釈を残す。
採否を行う依頼なら `experiments/<id>/decision.md` から参照し、
却下時は `experiments/GRAVEYARD.md` に理由を記録する。

統計的非有意を「効果なしの証明」と呼ばない。欠測や比較条件の違いを明示し、
根拠の足りない採用判定は保留にする。個別実験レポートを `docs/` に置かない。
