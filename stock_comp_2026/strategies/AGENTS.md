# 戦略開発の配置規約

ルート `AGENTS.md` に従う。新戦略の配置・依存関係を変更するときは
`WORKSPACE.md` と `docs/workspace/architecture.md` を参照する。

- `dm_trainonly/` と既存zipはFreeze済み。新候補は別の戦略slug配下に実装する。
- 提出フォルダは自己完結させる。`research/`, `reports/`, `experiments/`, `tools/`
  への推論時依存を追加しない。
- 新規戦略のテストは `tests/strategies/<slug>/` に置く。既存dm_trainonlyテストの
  合格を新戦略の因果性・契約・coverage検証の代替にしない。
- source scan対象を新戦略へ広げ、feature builderには全入力のfuture-mutation
  prefix-invarianceを実行する。研究と提出の予測一致も確認する。
- Freeze時は開発フォルダの将来の編集から独立したsnapshotと実zipを
  `releases/<strategy_id>/` へ保存する。
