# ワークスペース設計

設計日: 2026-09-08。この文書は配置・依存関係の規約であり、戦略仕様やコンペルールを変更しない。

## 置き場所と責務

| パス | 置くもの | 更新の単位 |
| --- | --- | --- |
| `stock_comp_2026/input/` | 主催者配布データ | 配布manifestを正として保管。加工・移動しない |
| `stock_comp_2026/README.md`, `evaluate_script.py` | 配布ルール・採点実装 | 研究用に改変しない |
| `stock_comp_2026/strategies/<strategy_slug>/` | `submission.py`, `features.py`, 必要時の `models.py`, 推論用設定 | 戦略単位。Freeze済みは別slugへ分岐 |
| `research/experiments/<driver>.py` | Train-only読み込み、WF、有限候補の比較を組み立てるCLI | 再利用可能な実験ドライバ |
| `research/evaluation.py`, `research/firewall.py` | 共通評価・読み込み制限 | 変更時は回帰検証。凍結当時の旧版はsnapshotに保存 |
| `experiments/<experiment_id>/` | `experiment.json`, `plan.md`, `config.json`, `decision.md` | 仮説・探索予算ごと。結果値を設定に混ぜない |
| `artifacts/<experiment_id>/<run_id>/` | 実行snapshot、予測、モデル、日次PL、監査、ログ | 実行ごとに新規作成。失敗も保存 |
| `reports/<experiment_id>/` | 最終レポート、fold/年別比較CSV、実験ログ | 判断根拠。元run_idへの参照が必須 |
| `releases/<strategy_id>/` | 提出zip、設定・コード・モデル・環境のハッシュ、Freeze/Valid記録 | 凍結候補ごと。再生成による上書き禁止 |
| `tests/strategies/<strategy_slug>/` | 因果性・予測契約・境界値テスト | 戦略単位 |
| `tests/workspace/` | 計画生成・実行ディレクトリ・構成検証のテスト | 開発基盤単位 |
| `tools/` | 構成管理・期限付き実行・リリース検査 | ドメインの特徴量やモデルを置かない |
| `docs/workspace/` | ワークスペースの構成・開発手順 | 実験に依存しない共通規約 |
| `docs/strategies/` | 複数実験が参照する戦略仕様 | 戦略の仮説・定義単位 |
| `experiments/GRAVEYARD.md` | 却下実験の横断索引 | 個別の採否記録への参照 |

個別実験の計画書を `docs/` に置かない。実験ID付き文書は `experiments/<id>/`、
実行後の結果は `reports/<id>/` に置き、共通手順や仕様からリンクする。

`experiment_id` は `DM-YYYYMMDD-NN`、`run_id` は `run-YYYYMMDDTHHMMSSZ`、
戦略slugは `dm_liquidity_v2` のようなPython識別子とする。同日でも別の仮説には別IDを付ける。
候補のパラメータ違いは事前に列挙したtrial IDで区別し、試行数を記録する。
リリースIDは `DM-YYYYMMDD-NN-v1` など、元の実験と版を追跡できる名前にする。

## 依存関係

```text
実験計画・config → research/experiments のドライバ
                    ├─ Train-only loader / firewall
                    ├─ strategies/<slug> の特徴量・モデル
                    └─ 共通評価 → artifacts → reports → 採否

凍結した strategies/<slug> + 推論用依存ファイル → releases/<strategy_id>
```

- 推論コードから `research/`, `reports/`, `experiments/`, `tools/` をimportしない。
  提出フォルダだけで `predict()` が動くようにし、同梱物は `__file__` 基準で読む。
- 研究と提出で同じ特徴量関数を使う。学習ラベルを読むのは研究・学習側だけ。
  推論は引数なし `predict()`、`(Date, Code)` MultiIndex、予測1列の公式契約を守る。
- 新しい戦略はpackageとしてimportし、複数戦略の `features.py` を同じトップレベル名で
  `sys.path` に差し込まない。提出時のimportも別プロセスで検証する。
- Notebookは可視化・調査用。採用する処理はPythonモジュールとテストへ移す。
- 複数の実験で必要になった処理だけを共通化する。将来のためだけの抽象クラス、
  特徴量登録機構、巨大な汎用pipelineは先に作らない。

## 実験と実行の境界

`experiments/` は実行前の入力、`artifacts/` はその実行の証拠、`reports/` は解釈。
ドライバは `--config` と `--output` を受け取り、日付・研究ID・出力先をソースに固定しない。
`prepare-run` は計画・設定のsnapshotとhashを作成するだけで、学習・評価は実行しない。
ドライバはsnapshotを読み、開始時にコード・環境・利用Trainデータのhash、実行コマンドを追記する。
完了/失敗時は `run.json` に終了時刻・終了コード・試行数を記録し、完了後は変更しない。
再実行には新しいrunを予約する。再利用cacheを導入する場合は、入力hash・コードhash・設定hash・
splitをkeyに含め、TrainとValidを混在させない。

## 既存研究の扱い

DM-20260908の計画は `experiments/DM-20260908/plan.md`、却下索引は
`experiments/GRAVEYARD.md` に配置する。計画書の内容は凍結時点と同一。
`experiments/DM-20260908/experiment.json` が現行の計画・レポートと旧Freezeの保存先を結ぶ。
旧 `research/run_trainonly.py`, `verify_trainonly.py`, `benchmark_submission.py`,
`finalize_report.py` は出力先固定の**旧リリース再現用**。
特に `finalize_report.py` はレポート・却下索引・Freeze manifestまで再生成する。
日常開発のコマンドから呼ばず、必要時は独立コピーでのみ再現する。

旧manifestはルート `README.md`, `AGENTS.md`, 戦略仕様、共通コード、テストまでhashを持つため、
文書移動前に `releases/DM-20260908-v1/snapshot/` へ129対象ファイルと元のmanifestをコピーし、
全hashと実zipのTrain予測一致を検証した。snapshot内は当時のパスを保つ。
移行の記録は同リリースの `migration.json`。既存manifestの期待hashは変更していない。
`experiment.json` の `freeze_root` をsnapshotに設定し、`make check` と `make check-freeze` は
凍結当時の証拠を検証する。現行ワークスペースの文書は新しい配置に合わせて更新できる。
snapshotには推論smokeに必要な3つのTrain特徴量への相対symlinkだけを追加し、
Validやラベルは配置しない。データ本体は元の `stock_comp_2026/input/` で保持する。

新しいFreezeは提出ファイルと実験再現に必要な依存ファイルを明示列挙し、
変化するワークスペース全体をglobで凍結しない。コードsnapshotをリリースに同梱し、
開発側の将来の編集で過去リリースの検証が壊れない構造にする。

## バージョン管理・保管

コード・計画・設定・軽量レポート・manifestはGit管理、配布parquet・仮想環境・cache・
新しい実行成果物・zipは `.gitignore` で除外する。既存Freezeの証拠は削除しない。
新しい成果物のローカル保管先は `artifacts/` と `releases/`。これらはGitだけでは復元できないため、
重要runとリリースはデータ配布物とともに別媒体にも保管する。
現状はGit未初期化。`.gitignore` は導入済みで、初期化・初回コミットは別作業として行う。
