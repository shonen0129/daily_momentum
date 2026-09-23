# モデル開発の入口

今後の開発は [ディレクトリ設計](docs/workspace/architecture.md) と
[開発手順](docs/workspace/development_workflow.md) に従う。コンペ公式ルールと `AGENTS.md` が優先する。
文書の分類は [文書索引](docs/README.md) を参照。

```text
docs/workspace/              ワークスペース共通の設計・運用手順
docs/strategies/             複数実験で共有する戦略仕様
experiments/GRAVEYARD.md     実験を横断する却下理由の索引
experiments/<experiment_id>/  実験前に固定する計画・設定・採否記録
research/experiments/         今後の実験ドライバ（Train-only）
research/                     既存の評価・firewallと旧研究ドライバ
stock_comp_2026/strategies/    戦略ごとの自己完結した推論コード
tests/                       戦略テストと開発基盤テスト
artifacts/<experiment_id>/    実行ごとの設定snapshot・予測・モデル・監査ログ
reports/<experiment_id>/      人が読む結果・比較表
releases/<strategy_id>/       新しい凍結候補の提出zip・manifest
tools/                       データに依存しない開発・検証コマンド
```

Python環境の準備は既存 `README.md` の環境作成手順を使う。
普段の入口は以下。`make check` はデータを開かず、構成と既存Freezeのハッシュを検証する。

```sh
make help
make check
make test
make check-freeze
.venv/bin/python tools/workspace.py list
# 新しい実験を始める際に、意味のある固有IDを付ける（作成のみ。学習しない）。
.venv/bin/python tools/workspace.py new-experiment DM-20260909-01 --strategy dm_liquidity_v2
```

新規実験の `plan.md` と `config.json` を記入してから、開発手順のチェックを通す。
既存実験のコピーによる日付・出力先の置換を標準手順にはしない。

既存候補: [DM-20260908 計画](experiments/DM-20260908/plan.md)、[レポート](reports/DM-20260908/REPORT.md)。
60日残差Momentum＋EWMA α=0.25をFreeze済み、Valid未評価。
今後の実験でも比較対象として参照するが、Train確認期間の結果は既知であることを計画に記録する。
当時の文書・コード・成果物は `releases/DM-20260908-v1/snapshot/` に保存し、
`make check-freeze` はこの独立snapshotの提出zipを検証する。
