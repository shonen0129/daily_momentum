# AGENTS.md

## 1. Purpose

Stock Competition 2026 向けに、因果的で時系列に安定し、取引コスト控除後にも残る
投資戦略を研究・実装・検証する。戦略の仮説・特徴量・モデル構造は投資戦略仕様書を正とする。

依頼された変更・必要な検証・結果報告まで進める。作業範囲内の可逆的な編集やローカル検証は
都度確認せず実行する。研究依頼は事前定義した試行予算と採否記録までを完了範囲とし、
スコアを見ながら探索を無制限に延長しない。

## 2. Source of Truth

研究内容の優先順位は、コンペ公式ルール → この `AGENTS.md` → 投資戦略仕様書 →
実装コード → 実験ログ・補助ドキュメント。仕様と実装が矛盾する場合は差分を明示し、
勝手に仕様を変更しない。

Skillは作業手順の補助であり、ユーザーの明示的な依頼範囲を広げたり、独自の承認段階を
追加したりしない。Skillの推奨手順よりユーザーの指示を優先し、研究制約は維持する。
情報・権限が不足する場合は依存しない作業を進め、不足点だけを確認する。
指示が原因で停止する場合は、該当ファイルへのリンク・該当文・適用理由を示す。

## 3. Core Principles

研究・特徴量選択・モデル選択・パラメータ選択はTrain-onlyで完結する。
未来情報を使わず、Momentum baselineに対する増分を評価し、単純で安定したモデルを優先する。
選択基準は第13節、変更後のリーク・prefix-invarianceを含む検証範囲は第17〜18節、
Valid前の凍結条件は第21節に従う。

## 4. Competition Timing

シグナル日を `t` とし、利用できるのは `t` までに観測・公開された情報のみ。
予測対象は `t+1 Open -> t+2 Open` の1日市場残差リターン。

短期・Intraday・Microstructure特徴量は、`t` 日中の情報が `t+1` 寄付までに
完全に織り込まれていないかを確認する。

## 5. Data Rules

価格・出来高の水準特徴量にはraw OHLCVを使用する。遡及調整済みの
`AdjustmentOpen`、`AdjustmentHigh`、`AdjustmentLow`、`AdjustmentClose`、
`AdjustmentVolume` の水準を特徴量として使用しない。

リターン特徴量には主催者提供の `raw_return` を優先する。
Sector・市場区分は各日時点のPoint-in-Time情報のみ利用する。

## 6. Leakage Prohibitions

以下は禁止。疑わしい処理は採用前に因果性を確認する。

- negative shift、dynamic future-referencing shift、`center=True rolling`、`bfill`、forward as-of join
- future targetの特徴量利用、Valid target・raw targetの予測時読み込み
- 未来情報を含むranking・normalization・rolling statistics
- 最新属性の過去への遡及適用

## 7. Prefix-Invariance

新規または意味変更したCompetition feature builderには、全入力源を対象に
future-mutation prefix-invariance testを必須とする。cutoffより後の入力を変更しても、
cutoff以前の特徴量・予測が変化しないことを確認する。Static leak scanのみで代替しない。

## 8. Valid Policy

Validは最終評価用であり、研究・モデル選択に使用しない。
Validの結果に基づいて、特徴量・特徴量定義・Momentum horizon・モデル構造・パラメータ・
lambda・Gate定義・score smoothing・turnover control・feature selection・ensemble weightを
変更してはいけない。

Validを見る前に最終候補を完全に凍結する。Valid確認後の変更は別の戦略リリースとして扱い、
既読Validを未使用データとは呼ばない。

研究時はTrain-only firewallとTrainファイルだけのstageを使う。
`stock_comp_2026/evaluate_script.py` は既定でValid targetを選ぶため、
既定入力ディレクトリのまま研究・smokeに実行しない。
FreezeはValid評価の前提であり、研究だけの依頼からValid評価や外部提出を自動追加しない。

## 9. Research Procedure

研究は原則、仕様書の仮説確認 → 単純なbaseline → 条件付き集計による仮説検証 →
Train-only walk-forward → Cost / TurnoverとFold間安定性の評価 → 必要な場合のみ複雑化 →
Train-onlyで最終候補選択 → Freeze → 最終Valid評価の順で進める。
いきなり高自由度モデルの最適化から始めない。依頼された段階から進め、
有効な既存結果を利用できる工程は繰り返さない。

## 10. Walk-Forward Validation

モデル選択はTrain内の時系列walk-forward（past → future）で行う。
ランダムK-Foldは原則使用しない。Target horizonがfold境界を跨がないよう必要なpurgeを入れる。

## 11. Evaluation Metrics

各fold・各年について、最低限以下を記録する。

| 対象 | 必須指標 |
| --- | --- |
| Prediction | Mean RankIC、RankIC t-stat、RankIC hit ratio |
| Portfolio | Gross Sharpe、Net Sharpe、Annual Gross P/L、Annual Net P/L、Annual Cost、Average Daily Turnover、Maximum Drawdown |
| Cross Section | Q1-Q5 returns、Q1-Q5 monotonicity、Long P/L、Short P/L |

## 12. Incremental Evaluation

新モデルは各foldでbaselineとの差分を確認する:
IC(New) − IC(Baseline)、NetSharpe(New) − NetSharpe(Baseline)、
GrossSharpe(New) − GrossSharpe(Baseline)、Turnover(New) − Turnover(Baseline)、
Cost(New) − Cost(Baseline)。

特定期間だけ大幅に改善するモデルより、複数時代で小さくても一貫して改善するモデルを優先する。

## 13. Model Selection

Full Train Sharpe最大モデルを自動採用しない。優先順位は以下。

1. Net Sharpeの時系列安定性
2. Baselineに対する一貫した改善
3. Turnover / Cost
4. RankIC stability
5. Q1-Q5 monotonicity
6. Long / Short consistency
7. Maximum Drawdown
8. Model simplicity
9. Economic interpretability

複雑なモデルが単純モデルを僅差で上回る場合は、単純モデルを優先する。

## 14. Overfitting Control

研究仮説を先に定義し、その仮説を検証する。大量の特徴量生成・horizon search・
interaction search・大規模hyperparameter search、Train Sharpeを見ながらの無制限な試行追加、
特定年への最適化、Validを見た後の再調整を避ける。

## 15. New Ideas

仕様書にない新特徴量・モデルも提案・検証できるが、実験前に以下を明示する。

- Hypothesis / Why it should work / Why it may persist
- Why it should survive t+1 open
- Expected turnover impact / Leakage risk / Complexity cost

「MLなら効くかもしれない」という理由だけでは追加しない。
仕様から大きく外れる変更は既存戦略の改変ではなく、新しい候補戦略として扱う。

## 16. Research Log

重要な実験には以下を残す。

- Experiment ID / Date / Hypothesis / Change from baseline
- Feature Set / Model / Parameters / Train Window / Evaluation Window
- Gross Sharpe / Net Sharpe / Turnover / RankIC / Maximum Drawdown
- Fold-level results / Decision / Reason

失敗実験も削除せず、却下理由を記録する。

## 17. Code Changes

現在の挙動と変更目的を確認し、必要な変更と影響範囲の検証を完了する。
無関係なリファクタリングを同時に行わない。検証は変更内容に応じて選ぶ。

| 変更内容 | 必要な検証 |
| --- | --- |
| 文書・Skillのみ | 指示の整合性、参照先、Skill frontmatter、`make check` による構成・Freeze hash照合。バックテストは不要。 |
| 開発基盤・実行ツール | 影響する構成・回帰テストとsmoke。戦略実行に影響する場合はその経路の検証を追加。 |
| 特徴量・予測・学習・ポートフォリオ | 関連回帰、source firewall / leak scan、future-mutation prefix-invariance、契約・coverage・決定性、Train-only smoke / backtest、変更前後比較。 |
| Freeze・提出物 | 第18節の全項目と、実zipのTrain-only予測一致・依存関係・時間/メモリを検証。 |

合格後は新たな変更・失敗・未解決の懸念がある場合だけ検証を追加・再実行する。
未実施項目は理由と影響を報告し、未検証の性能や因果性を確認済みと扱わない。

## 18. Required Tests

維持する検査はsource firewall / leak scan、future-mutation prefix-invariance、
index alignment、NaN handling、prediction coverage、deterministic output、smoke test。
全対象銘柄・全対象営業日に必要なsignalが出力されることを確認する。

## 19. Reproducibility

random seedを固定し、feature definition・model parameters・training window・
library version・artifact hashを記録する。重要な候補はコード・設定・学習条件を保存する。

## 20. Submission Constraints

提出物は採点環境で安定して実行できること。ネットワーク依存、外部API、
採点環境にないlibrary、GPU必須、過大なmemory・実行時間を避ける。
GPUが存在しなくても動作する構成を優先する。

## 21. Freeze Policy

Valid評価前にStrategy ID、Feature definitions、Model structure、Model parameters、
Turnover control、Score smoothing、Random seed、Training procedure、Submission codeを
完全に固定する。戦略固有の追加項目は仕様書に従う。
Freeze後、Validを確認するまで仕様を変更しない。

## 22. Final Principle

判断に迷った場合はSimple / Causal / Stable / Low-Turnover / Reproducible / Train-onlyを優先する。

## 23. Document Locations

開発入口は `WORKSPACE.md`、文書索引は `docs/README.md`。
必要な資料だけを読み、小さな文書修正のために全資料・全Skillを読み込まない。

- 配置・責務を変更するとき: `docs/workspace/architecture.md`
- 実験の開始・実行・Freezeを行うとき: `docs/workspace/development_workflow.md`
- 戦略の仮説・特徴量・モデルを扱うときの正本: `docs/strategies/momentum_liquidity.md`
- 個別実験の計画・設定・採否: `experiments/<experiment_id>/`
- 却下実験の横断索引: `experiments/GRAVEYARD.md`
- 結果・比較表: `reports/<experiment_id>/`
- 凍結当時の文書・コード・成果物: `releases/<strategy_id>/`

個別実験の文書を `docs/` に追加しない。Skill内の保存先も本節に揃える。
DM-20260908の原本は `releases/DM-20260908-v1/snapshot/` に保存済み。
旧manifestの期待hashを現行ファイルのhashで更新しない。

Skillは依頼に合うものを選び、関連Skillへの参照を全件実行の指示として扱わない。
詳細な症状別手順は必要時だけ参照し、共通制約や評価項目をSkillごとに再定義しない。
結果は変更点・検証結果・残る制約を簡潔に報告する。

指示設計の参考: [Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)
