---
name: daily-momentum-research
description: Daily Momentum の研究開始・再開や提出準備で、対象戦略と実験経路を特定する。
---

# Daily Momentum の研究・提出入口

共通制約は [AGENTS.md](../../../AGENTS.md)。コードパスはリポジトリルート基準。
依頼された段階から進め、完了済みの研究を最初から繰り返さない。

## 対象を特定する

- 配置・既存候補の確認: [WORKSPACE.md](../../../WORKSPACE.md)。
- 仮説・特徴量・モデルの確認: [戦略仕様](../../../docs/strategies/momentum_liquidity.md) と対象の `experiments/<id>/plan.md`・`config.json`。
- 実験開始・実行・Freeze: [開発手順](../../../docs/workspace/development_workflow.md)。
- データの列・配布構成が必要なとき: `stock_comp_2026/input_manifest.json`、`stock_comp_2026/input_data_explorer.ipynb`。
- 提出契約・依存関係の確認: `stock_comp_2026/README.md`、`stock_comp_2026/requirements.txt`、対象戦略の `submission.py`。

研究実行は Train-only firewall と専用 stage を使う。配布 `evaluate_script.py` の
既定入力は Valid 優先なので、通常の研究・smoke用コマンドとして直接実行しない。

## 必要な作業だけ選ぶ

| 依頼・変更 | 参照するSkill |
| --- | --- |
| 仮説・モデル・パラメータの比較 | [experiment-design](../experiment-design/SKILL.md) |
| 特徴量・時系列入力の因果性検証 | [leak-audit](../leak-audit/SKILL.md) |
| 特定の欠損・境界条件の分析 | [edge-case-finder](../edge-case-finder/SKILL.md) |
| 成績の集計・比較レポート | [backtest-report](../backtest-report/SKILL.md) |
| タイムアウト・実行遅延 | [hang-prevention](../hang-prevention/SKILL.md) |
| 再現している不具合の修正 | [debugging](../debugging/SKILL.md) |
| 挙動維持の構造整理・高速化 | [refactor](../refactor/SKILL.md) |
| 差分・提出コードの監査 | [code-review](../code-review/SKILL.md) |
| 新規・不足している回帰テスト | [test-gen](../test-gen/SKILL.md) |

この表は選択肢であり、全Skillを順番に実行する手順ではない。
完了時は対象戦略・実験ID、成果物、検証結果、採否または未解決点を示す。
