# AGENTS.md

## 1. Purpose

このフォルダでは、Stock Competition 2026 向けの新規投資戦略を研究・実装・検証する。

戦略そのものの仮説、特徴量、モデル構造、候補アーキテクチャは、同フォルダ内の投資戦略仕様書を正とする。

AI Agent は、戦略仕様書とコンペルールを踏まえて、実装・検証・比較・改善を行う。

---

## 2. Source of Truth

作業時の優先順位は以下。

1. コンペ公式ルール
2. この `AGENTS.md`
3. 投資戦略仕様書
4. 実装コード
5. 実験ログ・補助ドキュメント

コンペルールと戦略仕様書が矛盾する場合は、コンペルールを優先する。

戦略仕様書と実装が矛盾する場合は、勝手に仕様を変更せず、差分を明示する。

---

## 3. Core Principles

以下を必ず守ること。

1. Valid をモデル選択に使用しない
2. Train-only で研究・特徴量選択・モデル選択・パラメータ選択を完結する
3. 未来情報を一切使用しない
4. 取引コスト控除後の Net Sharpe を重視する
5. Full Train の単一スコア最大化ではなく、時系列安定性を重視する
6. Momentum baseline に対する incremental improvement を必ず評価する
7. 複雑なモデルより、単純で安定したモデルを優先する
8. 無制限な特徴量探索・ハイパーパラメータ探索を行わない
9. 実装変更後はリーク検査・prefix-invariance 検査を行う
10. Valid 評価前に最終候補を完全に凍結する

---

## 4. Competition Timing

シグナル日を `t` とする。

利用可能なのは `t` までに観測・公開された情報のみ。

予測対象は、

```text
t+1 Open -> t+2 Open
```

の1日市場残差リターン。

短期・Intraday・Microstructure 特徴量については、`t` 日中の情報が `t+1` 寄付までに価格へ完全に織り込まれていないかを必ず確認する。

---

## 5. Data Rules

価格・出来高の水準特徴量には raw OHLCV を使用する。

遡及調整済みの以下の水準は特徴量として使用しない。

```text
AdjustmentOpen
AdjustmentHigh
AdjustmentLow
AdjustmentClose
AdjustmentVolume
```

リターン特徴量には、主催者提供の `raw_return` を優先して使用する。

Sector や市場区分を使う場合は、各日時点の Point-in-Time 情報のみ利用する。

---

## 6. Leakage Prohibitions

以下は禁止。

```text
negative shift
dynamic future-referencing shift
center=True rolling
bfill
forward as-of join
future target の特徴量利用
Valid target の予測時読み込み
raw target の予測時読み込み
未来情報を含む ranking
未来情報を含む normalization
未来情報を含む rolling statistics
最新属性の過去への遡及適用
```

疑わしい処理は、採用前に因果性を確認する。

---

## 7. Prefix-Invariance

新規または意味変更した Competition feature builder には、future-mutation prefix-invariance test を必須とする。

cutoff より後の入力データを変更しても、cutoff 以前の特徴量・予測が変化しないことを確認する。

Static leak scan のみで代替しない。

---

## 8. Valid Policy

Valid は最終評価用であり、研究用データではない。

以下を Valid の結果に基づいて変更してはいけない。

```text
特徴量
特徴量定義
Momentum horizon
モデル構造
モデルパラメータ
lambda
Gate 定義
score smoothing
turnover control
feature selection
ensemble weight
```

Valid を見る前に、最終候補の仕様を完全に凍結する。

Valid を確認後に変更を行う場合は、別の戦略リリースとして扱う。

---

## 9. Research Procedure

研究は原則として以下の順で進める。

1. 戦略仕様書の仮説を確認する
2. 単純な baseline を実装する
3. ML を使う前に条件付き集計で仮説を検証する
4. Train-only walk-forward で評価する
5. Cost / Turnover を含めて評価する
6. Fold 間の安定性を確認する
7. 必要な場合のみモデルを複雑化する
8. 最終候補を Train-only で選択する
9. 全仕様を Freeze する
10. Freeze 後にのみ Valid を評価する

いきなり高自由度モデルの最適化から始めない。

---

## 10. Walk-Forward Validation

モデル選択は Train 内の時系列 walk-forward で行う。

```text
past -> future
```

の方向のみ使用する。

ランダム K-Fold は原則使用しない。

Target horizon が fold 境界を跨がないよう、必要な purge を入れる。

---

## 11. Evaluation Metrics

最低限、各 fold と各年について以下を記録する。

### Prediction

```text
Mean RankIC
RankIC t-stat
RankIC hit ratio
```

### Portfolio

```text
Gross Sharpe
Net Sharpe
Annual Gross P/L
Annual Net P/L
Annual Cost
Average Daily Turnover
Maximum Drawdown
```

### Cross Section

```text
Q1-Q5 returns
Q1-Q5 monotonicity
Long P/L
Short P/L
```

---

## 12. Incremental Evaluation

新モデルは絶対性能だけでなく、必ず baseline に対する差分を確認する。

最低限、

```text
IC(New) - IC(Baseline)
NetSharpe(New) - NetSharpe(Baseline)
GrossSharpe(New) - GrossSharpe(Baseline)
Turnover(New) - Turnover(Baseline)
Cost(New) - Cost(Baseline)
```

を各 fold で確認する。

特定期間だけ大幅に改善するモデルより、複数時代で小さくても一貫して改善するモデルを優先する。

---

## 13. Model Selection

Full Train Sharpe 最大モデルを自動採用しない。

優先順位は以下。

1. Net Sharpe の時系列安定性
2. Baseline に対する一貫した改善
3. Turnover / Cost
4. RankIC stability
5. Q1-Q5 monotonicity
6. Long / Short consistency
7. Maximum Drawdown
8. Model simplicity
9. Economic interpretability

複雑なモデルが単純モデルを僅差で上回る場合は、単純モデルを優先する。

---

## 14. Overfitting Control

以下を避ける。

```text
大量の特徴量生成
大量の horizon search
大量の interaction search
大規模 hyperparameter search
Train Sharpe を見ながら無制限に試行追加
特定年への最適化
Valid を見た後の再調整
```

研究仮説を先に定義し、その仮説を検証する。

---

## 15. New Ideas

戦略仕様書にない新特徴量・新モデルを提案・検証することは禁止しない。

ただし、実験前に最低限以下を明示する。

```text
Hypothesis
Why it should work
Why it may persist
Why it should survive t+1 open
Expected turnover impact
Leakage risk
Complexity cost
```

「MLなら効くかもしれない」という理由だけでは追加しない。

戦略仕様から大きく外れる変更は、既存戦略の改変ではなく新しい候補戦略として扱う。

---

## 16. Research Log

重要な実験は必ず記録する。

最低限、

```text
Experiment ID
Date
Hypothesis
Change from baseline
Feature Set
Model
Parameters
Train Window
Evaluation Window
Gross Sharpe
Net Sharpe
Turnover
RankIC
Maximum Drawdown
Fold-level results
Decision
Reason
```

を残す。

失敗実験も削除しない。

同じ失敗を繰り返さないため、却下理由を記録する。

---

## 17. Code Changes

コード変更時は以下を守る。

1. 現在の挙動を確認
2. 変更目的を明確にする
3. 必要最小限の変更を行う
4. テストを実行する
5. Smoke Test を行う
6. Backtest を行う
7. 変更前後を比較する

無関係なリファクタリングを同時に行わない。

---

## 18. Required Tests

最低限、以下を維持する。

```text
source firewall / leak scan
future-mutation prefix-invariance
index alignment
NaN handling
prediction coverage
deterministic output
smoke test
```

全対象銘柄・全対象営業日について必要な signal が出力されることを確認する。

---

## 19. Reproducibility

可能な限り結果を再現可能にする。

```text
random seed 固定
feature definition 保存
model parameters 保存
training window 保存
library version 確認
artifact hash 保存
```

重要な候補モデルは、コード・設定・学習条件を保存する。

---

## 20. Submission Constraints

提出物は採点環境で安定して実行できること。

以下を避ける。

```text
ネットワーク依存
外部 API
採点環境にない library への依存
GPU 必須
過大な memory 使用
過大な実行時間
```

GPU が存在しなくても動作する構成を優先する。

---

## 21. Freeze Policy

Valid 評価前に以下を完全に固定する。

```text
Strategy ID
Feature definitions
Model structure
Model parameters
Turnover control
Score smoothing
Random seed
Training procedure
Submission code
```

戦略固有の追加項目については、投資戦略仕様書に従う。

Freeze 後、Valid を確認するまで仕様を変更しない。

---

## 22. Final Principle

AI Agent は、

> 最高の Train スコアを探すこと

ではなく、

> **因果的で、時系列に安定し、取引コスト控除後にも残る戦略を構築すること**

を目的とする。

判断に迷った場合は、

```text
Simple
Causal
Stable
Low-Turnover
Reproducible
Train-only
```

な選択を優先する。