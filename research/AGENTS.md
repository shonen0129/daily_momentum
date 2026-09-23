# 研究コードの配置規約

ルート `AGENTS.md` に従う。配置を調べるときは `WORKSPACE.md`、
実験の開始・実行・Freezeを行うときは `docs/workspace/development_workflow.md` を参照する。

- 新しい実験は `experiments/<id>/` に計画・有限候補・採否基準を登録してから始める。
- 新しいドライバは `research/experiments/` に置き、config/outputを引数で受け取る。
  日付・出力ディレクトリをソースへ固定しない。
- 旧Freezeの正本は `releases/DM-20260908-v1/snapshot/`。内容を変更しない。
  既存のrun/verify/benchmark/finalizeモジュールを通常開発で再実行しない。
- 実行時にTrain-only firewallを有効化。新しいrunへ計画・設定・コード・環境・
  入力hashと終了状態を保存し、既存結果を上書きしない。
- 特徴量・モデルの正本は戦略フォルダに置き、研究と提出で重複実装しない。
