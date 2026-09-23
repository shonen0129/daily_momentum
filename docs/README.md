# 文書の案内

`docs/` は複数の実験で共有する文書の置き場所。個別実験の計画・採否・結果は実験IDで管理する。

| 種類 | 正本の場所 |
| --- | --- |
| ワークスペースの構成・責務 | [workspace/architecture.md](workspace/architecture.md) |
| 開発・検証・Freezeの手順 | [workspace/development_workflow.md](workspace/development_workflow.md) |
| Momentum × Liquidityの戦略仕様 | [strategies/momentum_liquidity.md](strategies/momentum_liquidity.md) |
| 個別実験の計画・設定・採否 | [../experiments/](../experiments/README.md) の `<experiment_id>/` |
| 却下実験の横断索引 | [../experiments/GRAVEYARD.md](../experiments/GRAVEYARD.md) |
| 結果と比較表 | `../reports/<experiment_id>/` |
| 凍結時点の文書・コード・成果物 | `../releases/<strategy_id>/` |

既存の [DM-20260908計画書](../experiments/DM-20260908/plan.md) も実験フォルダに配置。
凍結当時の計画書はリリースsnapshotに元の相対パス・内容で保存されている。
過去の計画書にある出典パスは当時の記録として読む。
