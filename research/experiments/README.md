# 新しい実験ドライバ

`docs/workspace/development_workflow.md` の契約に従い、configとoutputを引数に取るモジュールをここへ追加する。
特徴量・推論は `stock_comp_2026/strategies/<slug>/`、評価は共通モジュールを使う。
旧 `research/run_trainonly.py` を上書き・直接再実行しない。
現在は配置規約のみで、汎用学習エンジンは実装していない。
