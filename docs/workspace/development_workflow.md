# 継続開発の手順

## 1. 実験前

公式ルール、`AGENTS.md`、戦略仕様、過去の採否と却下理由を確認する。
`WORKSPACE.md` が現在の開発入口。リリースsnapshot内の旧READMEにある再現コマンドは証拠を上書きするため、
通常の開発では以下を使う。

```sh
make check
.venv/bin/python tools/workspace.py list
.venv/bin/python tools/workspace.py new-experiment DM-20260909-01 --strategy dm_liquidity_v2
```

生成された `plan.md` に経済仮説、翌寄付後にも残る理由、turnover、リーク、複雑性を記入。
`config.json` にfeature definitions、モデル・パラメータ、有限候補一覧、seed、
Train範囲、開発fold、purge、選択基準、確認期間の扱いを記入する。
既存の2015〜2016-03の確認成績は既知なので、次の研究で未使用holdoutとは呼ばない。
試行を追加する場合は理由と累積試行数を記録し、旧計画を消して探索履歴を隠さない。

## 2. 実装・小さい検証

新しいstrategy slug配下に因果的な特徴量・予測を実装し、
`tests/strategies/<slug>/` にその実装を直接検査するテストを置く。
旧 `tests/test_*.py` はdm_trainonly専用であり、新規戦略の検査を自動で保証しない。

- source firewall / leak scanと、全入力のcutoff後改変によるprefix-invariance。
- ラベルのpurge、index一致、欠損・inf・出来高0・履歴不足・再上場。
- 予測coverage、決定性、研究と提出の予測一致。
- 合成データのsmoke、公式weight/costとの照合。

新しい/意味変更した特徴量は静的検査だけで採用しない。
新戦略のsource scan対象とprefix-invariance対象を明示し、`make test` に収集される名前にする。
検証範囲は `AGENTS.md` 第17節に従う。文書・Skillのみなら参照・指示の整合性と
`make check` による既存Freeze hash照合で検証する。基盤変更は影響するテストとsmokeを行う。
成績を見直してモデルを再選択しない。以下の全テスト・実zip検証は戦略変更やFreezeに応じて選ぶ。

```sh
make test
make check-freeze
```

GitHub Actions の `.github/workflows/ci.yml` は push と pull request で Python 3.11.15 と
`requirements-research.txt` の固定依存を使い、`make check` と `make test` を実行する。
`make check-freeze` はFreeze済み提出zipをTrainデータで実行するため、配布parquetを含まないCIでは実行しない。
Freeze後は配布Train parquetがあるローカル環境で `make check-freeze` を実行し、zipの予測一致を確認する。

## 3. Train-only実行

計画を記入し、`experiment.json` の `status` を `planned` にする。

```sh
.venv/bin/python tools/workspace.py prepare-run DM-20260909-01
```

新しい `artifacts/<experiment_id>/<run_id>/` が作られる。重複runの上書きは拒否する。
作成時点の `run.json` は `prepared` であり、学習成功・Freezeを意味しない。
設定内容の妥当性や探索予算の遵守は、実験ドライバとレビューで検証する。

新しいドライバは `research/experiments/` に実装し、snapshot configとoutputを引数で渡す。
現在、汎用学習ドライバは未実装。各戦略の仮説に必要な処理を実装した時点で具体的な実行コマンドを計画に記録する。
全ジョブは `tools/run_bounded.py --seconds 1800` などの期限付きで実行する。
研究プロセスでfirewallを有効化し、Trainファイルだけのstageを使う。
配布 `evaluate_script.py` はValid優先のため、入力ディレクトリを既定のまま直接採点しない。

各runでコードhash・データhash・library version・seed・学習条件・コマンド・
実試行数・終了状態を保存する。失敗runは `failed` と理由を記録し保持する。
モデル選択はTrain内の開発foldで完結し、確認期間を見て再調整しない。

## 4. レポート・採否

`reports/<experiment_id>/REPORT.md` と比較CSVに、各fold/年の以下を残す。

| 種類 | 必須項目 |
| --- | --- |
| 予測 | Mean RankIC、HAC等の定義付きt-stat、hit ratio |
| 損益 | Gross/Net Sharpe、Annual Gross/Net P/L、cost、turnover、最大DD |
| 断面 | Q1〜Q5リターンと単調性、Long/Short P/L |
| baseline差分 | ΔRankIC、ΔGross/Net Sharpe、Δturnover、Δcost |

実験ID・run ID・仮説・変更点・feature set・モデル・パラメータ・期間・採否と理由を
`experiments/<id>/decision.md` から参照する。却下理由は `experiments/GRAVEYARD.md` に追記する。
Full Train最大Sharpeだけで採用しない。報告は経済的解釈と時系列安定性を含める。

## 5. FreezeとValid

最終候補決定後、`releases/<strategy_id>/` を新規作成。
仕様・特徴量・モデル・パラメータ・平滑化・turnover制御・seed・学習手順・提出コード・
環境・学習済みartifact・入力manifestを固定し、相対パスとSHA-256を記録する。
release内の自己完結したsnapshotを正とし、manifest自身も別途hashで記録する。
実zipでTrain-only smoke、coverage・決定性・同値性・時間/メモリ・全依存の同梱を確認する。

Freeze検証後にだけValid評価を行い、その記録は学習成果物と分離する。
Valid結果で同じリリースを調整しない。別リリースでも既読Validを未使用データとは呼ばない。
現在の構成管理CLIにValid実行・外部提出の機能はない。
