---
name: debugging
description: 戦略コードの再現するエラー・NaN混入・出力不整合・成績異常を調査し、原因修正と回帰検証を行う。
---

# 不具合の調査と修正

共通制約・検証範囲は [AGENTS.md](../../../AGENTS.md) 第17〜19節。
最小のTrain-only入力で再現し、観測した原因を修正する。

- 失敗コマンド、例外、対象戦略・設定・期間を確認する。日付・銘柄を絞れる場合は絞る。
- shape、index、NaN/Inf、範囲、中間出力を比較し、原因が分かるまで仮説を検証する。
- `.venv` を使う。短い検査はインラインでもよく、再利用する再現処理はテストや一時スクリプトにする。
- 関連回帰とAGENTS第17節の検査を実行する。失敗を消すためのassert削除・skip・
  リーク閾値緩和は行わない。
- 今回作成した不要なデバッグ出力を片付け、再現条件・根本原因・修正・検証結果を報告する。

採点契約・同値シグナル・コスト異常を調べる場合は
[症状別診断](references/symptoms.md) の該当節を読む。
遅延・ハングは [hang-prevention](../hang-prevention/SKILL.md)、
因果性の失敗は [leak-audit](../leak-audit/SKILL.md) の手順を使う。

成績低下がバグとは限らない。平滑化・horizon・weight等の変更が必要なら、
デバッグの修正に混ぜず仮説付きの [experiment-design](../experiment-design/SKILL.md) として扱う。
Validの結果から仕様を調整しない。
