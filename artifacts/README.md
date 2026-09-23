# 実行成果物

`tools/workspace.py prepare-run <experiment_id>` が新しいrunを予約する。
`<experiment_id>/<run_id>/` に計画・config・experimentのsnapshotと `run.json` を保持。
ドライバの出力はこのrun内の `models/`, `predictions/`, `metrics/`, `audit/`, `logs/` に分ける。
完了後のrunを上書きせず、失敗runも終了状態とともに保存する。
新しい成果物はGit対象外。重要な成果物はhashとともに別途バックアップする。
