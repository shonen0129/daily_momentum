---
name: hang-prevention
description: 長時間の研究・採点処理に実行期限を設け、タイムアウトやメモリ増大を診断する。
---

# 実行期限と遅延診断

提出制約は [AGENTS.md](../../../AGENTS.md) 第20節。
研究実行は [開発手順](../../../docs/workspace/development_workflow.md) のTrain-only経路を使う。

## 実行を制限する

長時間ジョブは `tools/run_bounded.py --seconds <予算秒> <コマンド>` で囲む。
これはプロセスグループへSIGTERM、猶予後にSIGKILLを送り回収する。
研究ジョブの期限と採点全体の30分制限を区別し、提出では読込・学習・推論を含む時間を測る。

関連テストの例（対象パスを置換）:

```sh
.venv/bin/python tools/run_bounded.py --seconds 180 .venv/bin/python -m pytest tests/strategies/<slug> -q
```

短い読取検査はインラインPythonでもよい。長い・繰り返す処理はスクリプトにして
コマンドとログを残す。タイムアウト後は終了状態と原因を確認し、同じ高負荷実行を反復しない。

## 計測して対処する

- 小さいTrain期間で読込・特徴量・学習・推論を分け、時間とピークメモリを計測する。
- ボトルネックに応じてベクトル化、重複計算・コピーの削減、列の絞込みを行う。
  dtype変更・キャッシュは精度とprefix-invarianceへの影響を確認する。
- macOSのfork/spawn、joblibとBLASの過剰並列、デッドロック、スワップを確認する。
  並列数は実測したCPU・メモリ予算に収める。
- 反復最適化には収束条件と反復上限を設ける。提出コードの外部接続待ちを除く。

原因・修正・同条件での時間/メモリ比較・終了状態を報告する。
上限内の実測がなければ採点時間を保証したと扱わない。
