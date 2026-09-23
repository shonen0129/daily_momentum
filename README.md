# Stock Competition 2026: Momentum研究

開発の入口は [WORKSPACE.md](WORKSPACE.md)、作業規約は [AGENTS.md](AGENTS.md)。
文書の置き場所は [docs/README.md](docs/README.md) を参照。

- [ワークスペース設計](docs/workspace/architecture.md)
- [開発・検証手順](docs/workspace/development_workflow.md)
- [戦略仕様](docs/strategies/momentum_liquidity.md)
- [実験台帳](experiments/README.md)・[却下実験索引](experiments/GRAVEYARD.md)
- [コンペ公式仕様](stock_comp_2026/README.md)

## 環境と日常の検証

Python 3.11と固定依存バージョンを使う。

```sh
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements-research.txt
make check
make test
make check-freeze
```

## 既存研究

[DM-20260908計画](experiments/DM-20260908/plan.md)・[結果](reports/DM-20260908/REPORT.md)。
最終候補は60日市場残差Momentum＋EWMA α=0.25。Valid未評価。
Train確認期間のNet Sharpeは負であり、実運用採用の根拠は不足している。

凍結当時の再現記録は [旧README](releases/DM-20260908-v1/snapshot/README.md)。
原本は独立snapshotに保存済み。旧研究の再生成はsnapshot自体を上書きせず、別コピーで行う。
