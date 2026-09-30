# DM-20260908-v1 Train-only研究・最終選択

作成日: 2026-09-08。**最終候補は60日市場残差Momentum＋EWMA α=0.25。Liquidity / Microstructureの追加補正は採用しない。**
これはFreeze可能な研究候補の選択であり、収益性を確認した実運用モデルの採用ではない。
開発Net Sharpeは0.400だが、選択後のTrain内確認Net Sharpeは-0.088。統計的な採用根拠は不足している。
**Valid特徴量・Valid targetを開かず、raw targetはTrainを含めて開かず、Valid評価も実行していない。**
ルール確認時にREADMEの既掲載サンプル成績を読んだが、モデル選択には使用していない。

## 1. Source of Truth・期間・実行経路

AGENTS.md、docs/投資戦略案.md、stock_comp_2026/README.md、evaluate_script.pyを最初に確認した。
旧V2実装・ExperimentRegistryはこの作業フォルダに存在しないため、research/と本レポート配下に同等の追跡可能な記録を実装。
Git管理情報は作業開始時に存在せず、コード・設定・データはsha256で固定する。
公式READMEのLightGBM版には4.1.0の記載もあるが、実験環境は同梱requirements.txt指定の4.6.0に統一。提出推論にはLightGBM不要。

- 開発walk-forward: 2011、2012、2013、2014年の4fold、合計982日。過去から拡張学習し、各境界前2営業日のラベルをpurge。
- Momentum形状→EWMA→条件付き集計→C1→B→C2→A→事前固定感度検証の順。30試行（うち診断10）で終了。
- 開発結果は選択に使ったため、未使用OOSとは呼ばない。形状・平滑化の選択も同じ開発期間に依存する。
- パラメータ選択をselection_before_confirmation.jsonへ保存してから、2015-01-05〜2016-03-29の303日を確認。再選択なし。
- 2016年は59営業日の部分年。2008〜2010年の成績は最終選択後に記録する参考値のみ。
- Train配布target末尾2日は実際には有限値があるが、t+2がTrain境界を越えるため2016-03-30/31を全PL評価から除いた。予測coverageには含む。
- 全Trainは1,814日、473コード、809,636行。公式全期間ユニバース498銘柄に対し、ここではTrainに実在する全コードを検査した。
- 後続split用predict契約は合成データだけで検証。実際のValidの列・行coverage・速度は未確認。

## 2. 最終モデルの定義・選択理由

`r_res[t] = raw_return[t] - beta[t] * topix_return[t]`。
銘柄ごとに直近行を1行除外し、その前60観測営業日の残差リターンをsumする。
当日のaverage percentile rankから当日mean rankを引き2倍する。非有限値・履歴不足はこの順位スコアを0にする。
その後、銘柄別EWMA `S[t]=0.25*M[t]+0.75*S[t-1]`、adjust=Falseを適用。
コード再登場の取引日ordinal差が20を超えたときはrolling/EWMA履歴をリセットする。
したがって、通常はt-1〜t-60の窓だが、少数の行欠落があると「銘柄の60観測行」の窓になる。
60日窓、1日skip、alpha=0.25は選択前後で固定。lambda=0、gateなし、追加hysteresis/bufferなし、学習済み係数なし。

短いMomentumはturnoverが高くコスト負けした。平滑化60日候補は開発4年すべてNet Sharpeが正。
α=0.15はturnoverが低い一方、正のfoldは3/4だったため、事前の安定性優先ルールで0.25を選んだ。
B λ=0.25は3/4fold改善したがΔNet SR中央値0.032、bootstrap95%下限-0.062であり、改善幅>=0.10・CI下限>0等の採用条件を満たさない。
C1 MLは2/4fold改善・Δ中央値0.001程度で、単純モデルを置き換える根拠がない。
全Train単一Sharpeの最大化では選んでいない。

## 3. Momentumと各Modelの比較（開発2011〜2014）

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| M_res20s1_a1 | 0.621 | -1.000 | 0.00559 | 0.2849 | 7.179% | -19.113% |
| M_res60s1_a1 | 0.684 | -0.150 | 0.00746 | 0.1639 | 4.129% | -12.958% |
| M_res60s1_a0.25 | 0.729 | 0.400 | 0.00725 | 0.0646 | 1.628% | -10.350% |
| C1_rule | 0.708 | 0.329 | 0.00696 | 0.0748 | 1.885% | -10.754% |
| C1_ml | 0.731 | 0.403 | 0.00731 | 0.0645 | 1.626% | -10.424% |
| B_lambda0.25 | 0.838 | 0.434 | 0.00964 | 0.0800 | 2.006% | -10.087% |
| B_lambda0.5 | 0.980 | 0.406 | 0.01188 | 0.1127 | 2.816% | -9.962% |
| B_lambda1.0 | 1.304 | 0.322 | 0.01543 | 0.1817 | 4.539% | -9.323% |
| C2_ml | 0.437 | -1.543 | 0.00745 | 0.2537 | 6.388% | -19.973% |
| A_rank | 0.756 | -1.496 | 0.01469 | 0.3390 | 8.482% | -22.243% |
| A_raw | 1.101 | -0.877 | 0.00266 | 0.2869 | 7.215% | -13.943% |

各候補の差分は **選択Momentum M_res60s1_a0.25** をbaselineとして計算。
M_res20s1_a1は初期の単純Momentum参照、M_res60s1_a1は平滑化なしの同期間参照。
costは片道0.1%×公式ポジション変更量。day turnoverはΣ|w_t-w_prev|で、0.0646は約6.46%/日。

| Model | 2011 Net SR | 2012 Net SR | 2013 Net SR | 2014 Net SR | 改善fold数 | ΔNet SR中央値 | ΔSR bootstrap95%CI |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M_res60s1_a0.25 | 0.433 | 0.646 | 0.040 | 0.809 | 0 | 0.000 | [0.000, 0.000] |
| C1_rule | 0.362 | 0.550 | 0.013 | 0.666 | 0 | -0.083 | [-0.131, -0.022] |
| C1_ml | 0.448 | 0.674 | 0.023 | 0.796 | 2 | 0.001 | [-0.010, 0.016] |
| B_lambda0.25 | 0.440 | 0.762 | 0.097 | 0.737 | 3 | 0.032 | [-0.062, 0.140] |
| B_lambda0.5 | 0.412 | 0.633 | 0.121 | 0.748 | 1 | -0.017 | [-0.151, 0.176] |
| B_lambda1.0 | 0.079 | 0.604 | 0.257 | 0.517 | 1 | -0.167 | [-0.389, 0.249] |
| C2_ml | -1.490 | -4.470 | 0.050 | -1.538 | 1 | -2.135 | [-3.673, -0.185] |
| A_rank | -2.033 | -1.672 | -0.527 | -1.944 | 0 | -2.392 | [-3.680, -0.243] |
| A_raw | -1.515 | -1.899 | 0.212 | -0.357 | 1 | -1.557 | [-2.997, 0.342] |

全30試行のGross/Net/IC/cost/turnover/DDはmodel_comparison.csv、全foldはall_models_fold_year_metrics.csv、
IC/Gross SR/Net SR/turnover/costのfold差分はfold_incremental.csv、各試行の仮説・設定・却下理由はEXPERIMENT_LOG.md。
診断専用のB λ0.4が高くても再選択しない。

## 4. 最終候補のwalk-forward・年別指標

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| 2011 開発 | 0.733 | 0.433 | 0.00399 | 0.0694 | 1.750% | -7.134% |
| 2012 開発 | 1.038 | 0.646 | 0.01172 | 0.0653 | 1.645% | -4.300% |
| 2013 開発 | 0.300 | 0.040 | 0.00457 | 0.0633 | 1.596% | -9.831% |
| 2014 開発 | 1.310 | 0.809 | 0.00866 | 0.0604 | 1.521% | -2.401% |
| 2015 確認 | 0.155 | -0.133 | 0.00460 | 0.0661 | 1.667% | -5.247% |
| 2016 確認（1〜3月部分年） | 0.306 | 0.067 | 0.01099 | 0.0653 | 1.645% | -4.571% |

| 年/期間 | 日数 | 年率Gross PL | 年率Net PL | 年率Long PL | 年率Short PL | IC HAC-t | IC hit | Q単調性 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2011 | 245 | 4.270% | 2.521% | 7.912% | -3.641% | 0.275 | 50.204% | 0.90 |
| 2012 | 248 | 4.358% | 2.713% | 1.959% | 2.399% | 1.218 | 54.839% | 1.00 |
| 2013 | 245 | 1.844% | 0.249% | 4.551% | -2.707% | 0.443 | 51.429% | 0.50 |
| 2014 | 244 | 3.972% | 2.452% | 5.572% | -1.600% | 1.402 | 54.098% | 0.90 |
| 2015 | 244 | 0.895% | -0.772% | 5.158% | -4.263% | 0.377 | 50.820% | 0.50 |
| 2016 | 59 | 2.109% | 0.464% | 9.245% | -7.136% | 0.410 | 49.153% | 0.10 |

Long/Shortは公式残差targetに対するcost控除前の寄与であり、実資産の無ヘッジ損益ではない。
開発期間Long年率+4.989%に対してShort年率-1.376%、確認期間Long+5.954%・Short-4.822%。Shortの弱さが残る。
2013年のNet SRは0.040しかなく、alpha近傍0.20/0.30では正foldが3/4に減る。安定性の根拠は強くない。

| 年 | Q1日次bp | Q2日次bp | Q3日次bp | Q4日次bp | Q5日次bp |
| --- | --- | --- | --- | --- | --- |
| 2011 | 2.223 | 4.209 | 3.655 | 4.550 | 7.115 |
| 2012 | -2.240 | -1.226 | 0.741 | 0.753 | 1.944 |
| 2013 | 2.564 | 1.241 | -0.429 | 4.050 | 3.381 |
| 2014 | 0.707 | 2.388 | 2.092 | 3.080 | 5.085 |
| 2015 | 3.553 | 3.008 | 2.910 | 4.224 | 4.037 |
| 2016 | 6.411 | 4.104 | 4.491 | 4.014 | 8.951 |

Q単調性は年別Q1〜Q5平均リターンと1〜5のSpearman相関。Q平均は日ごと等重み平均を年内で平均。
資産曲線の最大DDは初期0を含む加算PLの最大低下幅。複利DDもCSV/JSONに保存。
PL/cost年率は日次平均×252、Sharpeは日次標本標準偏差×√252。部分年も同じ換算であり実現年率の保証ではない。
RankICはtargetが有限の行だけで両系列を日次再順位化。IC t-statはNewey-West型HAC、lag5。

開発合算: Gross SR 0.728606 / Net SR 0.400353。
確認合算: Gross SR 0.188515 / Net SR -0.088465。
開発と確認は各区間冒頭を現金開始として測定し、各区間内の年境界ではポジション継続。
補助の連続2011〜2016-03系列はNet SR 0.270155、初期売買コストを1回だけ計上（continuous_metrics.json）。
2008年からの全Train参考SRは-0.236626。これは選択に使っていない。
2008〜2016の全Train年別参考値はfull_train_descriptive_yearly.csvに保存。

## 5. 条件付き仮説検証・特徴量の採否

条件付き集計はML fit前に保存した。形状選択済みの平滑化前Mを使い、毎日の条件内でRankICを計算する。
これらも開発データの診断であり、追加の独立検定ではない。

| 特徴量/仮説 | 検証結果・理由 | 最終採否 |
| --- | --- | --- |
| 市場残差Momentum60・skip1 | raw/sector20、5/10/20日よりコストと期間安定性が良い | 採用 |
| EWMA α=0.25 | turnover0.164→0.065、開発Net SR-0.150→0.400 | 採用 |
| Raw Momentum / PIT sector residual20 | Net SR -1.878 / -2.089、改善なし。PITは同日同Code結合 | 却下 |
| 5/10/20日、current/skip2、等重み合成 | 指定9形状の比較でコスト・安定性が劣る。追加horizon探索なし | 却下 |
| Liquidity levelとshock | 通常60日medianと5/60比を区別。単体で最終採用せず | 却下 |
| Liquidity vacuum gate | vacuum条件のM ICは全4年正(0.0113,0.0084,0.0174,0.0163)。一律弱める仮説を支持せず、C1ルールは全4年悪化 | 却下 |
| Volume confirmation | 高volume群M ICは2011〜2013負、2014のみ正。低volume群が強い年もあり、事前の単純継続仮説は不安定 | 却下 |
| Expected impact / PWV / VWP | 過去年だけでlinear ridge fit、log(abs residual)を予測。rolling60日歴史関係も条件付き比較。安定した補正の利益は確認できず | 却下 |
| AM/PM・range・PM/AM volume | PM反転のICは寄付前約-0.044〜-0.066、競技区間では約-0.001〜-0.023に弱まる。AMは符号不安定。volume ratioには正ICもあるがML比較でコスト後の上積みは未確認 | 却下 |
| M×PWV/VWP/liquidity/volume、VWP×intraday | 14〜15特徴の浅いモデルで検証。Bの小幅改善は採用基準未達 | 却下 |
| C2 reversal、A direct rank/raw | 高turnoverでNet悪化。符号反転・直接予測へ自由度を増やす根拠なし | 却下 |
| C3 amplification、深いimpact木、追加horizon/interaction | 前段の補正優位性が不足し、有限探索方針により未実施 | 見送り |

Expected impactの説明変数は前日log売買代金・通常流動性・volume shock・volatility・PIT size代理。
提供raw_return[t]は前日寄付→当日寄付のため、当日引けまでのvolumeをその値動きの同時説明にしない。
過去年の5日おき固定日サンプルでridgeをfitし、当年にはOOS予測のみ使用。126過去日未満は過去60日平均のfallback。
年次fitの列平均・scale・係数はimpact_crossfit.jsonに保存。学習行自身のin-sample residualを後段学習へ渡さない。
Momentum calibrationも年次cross-fitのlinear mapping。B targetはrank(target)-calibrated_OOF(M)、単純なrank(target)-rank(M)ではない。
B correctionは当日CS rankへ変換し、Mと[-1,1]の尺度を揃えて固定lambdaを掛けた。

intraday_decay.csvの寄付前returnは、Trainの翌日raw_returnと当日raw Open/Close比から診断用に別計算。
これはfeature builderから分離し、未来リターンを特徴量へ渡していない。寄付前はrawリターン、競技targetは市場残差で、完全に同じリスク調整ではない。
各特徴量の独立した限界寄与を証明する全組合せablationは行っていない。上記却下は本リリースへの不採用で、効果不存在の証明ではない。

## 6. 過学習対策・統計的不確実性

事前計画: docs/research_plan_20260908.md。30試行を記録し、確認後に候補を追加していない。
LightGBMはdepth2/leaves4/60trees/minleaf500/lr0.05/l2=10/seed20260908/CPU2threads。
固定感度検証: alpha0.20/0.30、B lambda0.4/0.6、C1 gate倍率0.8/1.2、木48/72、minleaf400/600。
gate倍率はクリップが発動しない領域では単なる全体尺度変換となり、順位をほぼ変えない。この感度診断だけでgateの頑健性を主張しない。
Momentum60日の局所±20%窓感度は未実施。指定5/10/20/60比較までで停止した。

paired circular block bootstrapは同日baseline/candidateを対応させて20日block、1000回、seed20260908、95%CI。
Sharpe差を直接再計算し、平均PL差のt検定で代替しない。positive fractionは真の改善確率とは呼ばない。
自己相関に対する有限block近似であり、block長の感度や構造変化の保証はない。

DSRは[Bailey & López de Prado (2014) の原論文](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)の
日次SR・候補間SR分散・歪度・非超過尖度・観測数に基づく式を実装。
選択候補DSR=0.00005332（30試行）、100試行感度=0.00000047。
候補群は相関し、段階的選択とコストで大きく異なるSR分布を持つため、この値は仮定依存の厳しい参考診断である。
既存サンプルの累積探索回数は不明。30は今回の実試行数であり、100も全履歴の補正を保証しない。
DSRは時系列依存を完全には補正しない。複雑なモデルの採用条件DSR>=0.95は満たされず、Momentumも「統計的に採用済み」とは主張しない。

## 7. コスト・フォールバック・境界条件

公式は5分位すべてに(q-2)/N/1.2のweightを付け、片道0.001×銘柄別weight差absを控除する。
0スコアは公式のrank(method=first)で分位に分けられるため、履歴不足の0埋めはフラットポジションを意味しない。
60日履歴充足率は95.5894%。全評価日に予測を出し、欠損日の除外で成績を改善していない。
targetがNaNの行では公式のgross-cost全体がNaNとなりコストも落ちるため、同じ挙動の公式netと、全weightに課金するnet_all_costを併記。
開発公式Net SR 0.400353、全cost控除Net SR 0.400333。
確認期間では両者は一致。日次gross-cost=netは検査済み。
公式costは固定10bpsのみ。slippage/借株料/financing/強制買戻し/impactの独立内訳は未計測で、0とはみなさない。
上場廃止時のポジション清算、欠測ラベル時損失、寄付不成・値幅制限の実約定は公式採点の外であり、未補正。
raw volumeの分割歪みは研究したmicrostructure特徴のリスクだが、最終予測はvolume/価格水準を使わない。

## 8. リーク監査・テスト・実行性能

- source AST firewall: 新戦略の全Pythonで禁止調整水準、負/dynamic shift、center rolling、bfill、forward as-of、禁止ラベル参照を検査。
- runtime: pandas parquet読込境界＋Python open監査でValid/raw target拒否。研究の明示allowlist以外は使わない。OSレベルの汎用DLP保証ではない。
- 実Train future-mutation: 2010-12-30 / 2012-06-29 / 2014-12-30の3cutoff。全5入力の未来部分を変更し、24特徴と最終予測のprefixがbitwise一致。
- 合成: cutoffで未来行を切り落とす試験、行順入替、NaN/Inf/0除算、窓不足、code再登場、tie、label purge、校正とC1/B/Aの未来変更・決定性。
- 全11テストPASS、失敗・skipなし。tests.xml、verification.json、データ読込監査JSON、学習max_label_availableを保存。
- 公式smoke: Train featureだけが見える一時ディレクトリで公式load_prediction/align_prediction/compute_pl/compute_srを使用し、日次PL一致。
- Train 809,636行/1,814日/473コード、予測欠損0。研究結果と提出predictはbitwise一致。
- 単独Train推論約0.536秒、peak RSS約344.8MiB。このマシンでの観測でありValid/採点ホストの時間保証ではない。
- 研究全体deadline1800秒、全Train検証600秒、tests180秒、単独推論120秒。すべて期限内exit0。不要なネットワーク/GPUは使用しない。

## 9. 残るリスクとFreeze設定

確認Net SR負、ICのHAC t値が弱い、Short側損失、2013年やalpha近傍の脆さ、Trainの期間/ユニバースへの依存が残る。
498銘柄ユニバース自体の選定バイアス、ETF近似市場系列・配布betaの生成過程はここでは再構築していない。
prefix-invarianceは入力から先の因果性を検査したもので、配布データ生成の全工程を保証しない。
現状は研究候補のFreezeまでであり、利益が残る新しいLiquidity/Microstructure戦略を確立したとはいえない。
改善が確認できなかった結果も保持し、次のリリースで同じ開発/確認期間を未使用OOSとして扱わない。

Freeze対象は以下。具体値は提出frozen_config.json、ハッシュはfreeze_manifest.json。

1. Strategy ID DM-20260908-v1、選択trial M_res60s1_a0.25。
2. raw_return/beta/topixの入力、当日残差化、60観測行sum、skip1、min_periods60。
3. 当日centered percentile rank、非有限/窓不足0埋め、code間隔リセット規則。
4. EWMA alpha0.25/adjustFalse/初期状態、lambda0、gateなし、hysteresis/buffer/cost-aware updateなし。
5. 学習なし、seed20260908、開発2011〜2014の選択手順、確認結果を反映しないルール。
6. submission.py/features.py、predict契約、Train履歴warmup、後続split出力index。
7. Python3.11.15、numpy2.4.6、pandas3.0.3、pyarrow24.0.0、CPU実行。
8. 公式5分位weight・片道10bps・252年率化、同梱zipとデータ/コード/設定hash。

Validは未実行。外部提出・実取引は行っていない。最終候補の仕様を変える場合は別Strategy IDの研究リリースとする。

## 10. 成果物と再現

- [最終設定](../../stock_comp_2026/strategies/dm_trainonly/frozen_config.json)
- [全試行ログ](EXPERIMENT_LOG.md)、[全比較](model_comparison.csv)、[全fold指標](all_models_fold_year_metrics.csv)
- [fold差分](fold_incremental.csv)、[最終候補年別](selected_fold_year_metrics.csv)
- [条件付き集計](conditional_states.csv)、[intraday decay](intraday_decay.csv)
- [学習・特徴量実装](../../stock_comp_2026/strategies/dm_trainonly/features.py)、[モデル実装](../../stock_comp_2026/strategies/dm_trainonly/models.py)
- [実データ検証](verification.json)、[テスト結果](tests.xml)、[Freeze manifest](freeze_manifest.json)
- [再現コマンド](../../README.md)、[事前計画](../../docs/research_plan_20260908.md)

各学習モデルはmodels/に保存。提出zipは最終Momentumの推論に必要な4ファイルだけを同梱。
