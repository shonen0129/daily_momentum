# 提出リリース

新しい候補のFreeze時に `<strategy_id>/` を新規作成する。提出zip、再現用コードsnapshot、
設定、環境、学習済みモデル、SHA-256 manifest、検査結果を同梱する。
Valid結果は凍結後に別ファイルへ追記し、凍結内容を変更しない。
このフォルダの作成自体は候補のFreezeや外部提出を意味しない。

既存 `DM-20260908-v1` の凍結当時の文書・コード・成果物は
`DM-20260908-v1/snapshot/` に保存。元のmanifestと全129対象ファイルを含む。
`migration.json` が移行時のmanifest hashと追加ファイルを記録する。
`make check-freeze` はsnapshot内の旧検査コードと提出zipを実行する。
