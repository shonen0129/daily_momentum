---
name: test-gen
description: 戦略変更や不具合に対応する回帰・因果性・提出契約テストを追加する。文書だけの変更には使わない。
---

# 戦略テストの追加

維持する契約は [AGENTS.md](../../../AGENTS.md) 第7・17〜19節。
既存テストを確認し、今回の不具合や変更の実害を検出できる不足分を追加する。
実装と同じ計算を転記するだけのテストは避ける。

| 変更・リスク | 検証する挙動 |
| --- | --- |
| 新規・意味変更した特徴量、時系列経路 | [leak-audit](../leak-audit/SKILL.md) の全入力future-mutation。静的検査のみで代替しない。 |
| 入力アクセス・データ処理 | source firewall、禁止データ非参照、PIT、index alignment、欠損・Inf・履歴不足。 |
| 提出・予測出力 | 引数なし `predict()`、数値1列のDataFrame、`['Date', 'Code']` MultiIndex、対象全行のcoverage、有限値。 |
| 乱数・並列化・順序 | 同一入力・seedの再実行で決定性。キャッシュに隠れた不一致も確認。 |
| 学習・fold | 学習窓とラベル終了時刻、purge、未来foldのラベル非参照。 |

予測側の対象indexは許可された入力から得る。coverage検査のために予測コードへ
Valid targetを読み込ませない。合成fixtureで境界を作り、期待値は契約・仕様から定める。
厳密比較と許容差付き比較を区別し、テスト通過を全入力に対する因果性の証明と呼ばない。

新戦略は `tests/strategies/<slug>/test_*.py`、開発基盤は `tests/workspace/` に配置する。
既存dm_trainonlyのテスト合格で新戦略の検査を代替しない。
`.venv/bin/python -m pytest <対象パス>` を期限付きで実行し、追加ケースと影響範囲を確認する。
全体検証の範囲はAGENTS第17節に従い、失敗を消すためにassertionを弱めない。
