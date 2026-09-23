# 実験の登録

`python tools/workspace.py new-experiment DM-YYYYMMDD-NN --strategy <slug>` で作成する。
各フォルダの `experiment.json` が台帳の1レコード。中央ファイルへの重複記入はしない。
`python tools/workspace.py list` で一覧表示する。

計画と設定は実験前に記入。実行時のsnapshotは `artifacts/` へ保存する。
旧 `DM-20260908` の計画は [plan.md](DM-20260908/plan.md) に原文のまま移動した。
凍結時点のパスを持つ文書はリリースsnapshotに保存。個別の計画を `docs/` に戻さない。
却下実験の横断索引は [GRAVEYARD.md](GRAVEYARD.md)。個別の理由・証拠は各実験へリンクする。
