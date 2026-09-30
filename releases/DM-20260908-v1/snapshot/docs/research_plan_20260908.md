# DM-20260908: 事前固定研究計画

データ成績を見る前に作成。根拠: AGENTS.md、docs/投資戦略案.md、stock_comp_2026/README.md と evaluate_script.py。
Validデータは特徴量も含めて研究時に開かない。raw_target はTrainを含めて一切開かない。
READMEに掲載されたサンプルの成績を既読だが、期間不明・Valid由来の可能性があるため採否の証拠にしない。
過去の研究registry/reportsはこの作業開始時に存在しない。サンプル5本は今回の探索外で既存試行数不明。

## 期間・評価・選択

- Train: 2008-11-04〜2016-03-31。開発walk-forward: 2011, 2012, 2013, 2014の暦年4fold。
- 学習は2008年から拡張、各境界直前2営業日をpurge。Expected impactは観測済みリターンのみで前年末まで学習。
- Momentum calibrationも年次cross-fit。学習ラベルのt+2が予測ブロック開始より前であることを検査。
- 2015〜2016-03は選択後のTrain内確認専用。ここで再選択・再調整しない。2016年は部分年と明記。
- 評価の末尾2営業日は特徴量・coverage検査に含め、未確定ラベルとしてPL比較期間から除く。
- 公式weightとcostの実装に厳密照合。5分位ウェイト=(q-2)/N/1.2、片道cost=0.001×銘柄別abs(weight差)。
- 比較期間冒頭は全候補現金開始。年境界ではpositionを継続。全評価営業日を集計、欠測ラベルの公式コスト欠落も別途診断。
- 年率252、Sharpeは標本標準偏差、PL年率は日次平均×252、DDは累積加算PLと複利を併記。
- 候補順位はpositive Net Sharpe fold数、median fold Net Sharpe、worst fold、turnover、複雑性。median差0.05以内は低turnover・単純さを優先。
- 追加MLの採用条件: baseline比3/4以上fold改善、median改善>=0.10、worst fold悪化<=0.25、paired block bootstrap Sharpe差95%下限>0、DSR>=0.95。満たさなければMomentum候補維持。
- 開発結果は選択に使うため純粋な未使用OOSではない。確認期間も最終モデルの保証ではない。
- 平均RankIC/t-stat(HAC lag5)/hit率、Q1〜Q5/単調性、long/short、Net/Gross Sharpe、PL、cost、turnover、DDをfold/年別に保存。
- paired circular block bootstrap: block20日、1000回、seed20260908、95%CI。DSRは日次SR、歪度・非超過尖度、候補間SR分散、実試行数と保守的100試行を報告。

## 有限候補（上限32 scoring trials）

1. Momentum9本: 市場残差5/10/20/60日(skip1)、20日skip0/skip2、raw20日skip1、PIT sector残差20日skip1、残差5/20/60日rank等重み(skip1)。期間は取引日窓、sum returnを用いる。
2. Phase1 winnerにEWMA alpha=0.5,0.25,0.15（alpha1は既存）。最適化追加禁止。
3. 選択alphaの0.8倍/1.2倍（上限1）を診断のみ。Momentum horizon感度は既定5/10/20/60比較で扱う。
4. 条件付き集計: liquidity/volume/PWV/VWP高低、AM↓PM↑/AM↑PM↓。選択baselineの条件付きICと符号付target、翌寄付前のdecayを診断。Price impact: 過去年のみでfitするlinear ridgeを本命、過去60日関係を非ML条件付き診断に使用。
5. C1ルールgate: liquidity shock<0かつPWV高のとき0.5、それ以外1。
6. C1 learned gate: shallow regressionでcontinuation確率、gate=clip(p,0,1)。
7. B: 年次cross-fitしたlinear momentum calibrationによるresidual rank target。lambda=0.25/0.5/1.0。Correctionを当日CS rank [-1,1]へ変換してMとの尺度を固定。
8. C2: gate=clip(2p-1,-1,1)、C1と同じ学習器。
9. A: direct shallow LightGBM、rank target/raw residual targetの2本。
10. B lambda0.5の0.4/0.6、C1 gateの0.8/1.2摂動、C1 tree数48/72、leaf min400/600を診断のみ。主設定はdepth2/leaves4/trees60/minleaf500/lr0.05/lambda_l2=10/seed固定/CPU2thread。
11. C3、深いimpact LGBM、追加horizon/interactionは本リリースでは実施しない。新探索を必要としないことを優先。

## 経済仮説と固定特徴量

Momentumは情報の段階的反映で持続し、volume確認は翌寄付以降の執行需要を示す可能性。liquidity vacuumでは一時的な価格飛びを減衰する。PWVは予想以上の値動き、VWPは吸収。朝夕の反転は機関の分割発注が翌日にも残る場合のみ有効。これらは仮説であって事実と扱わない。t+1寄付以降の提供targetで直接検証する。
通常流動性/ショックを区別。raw OHLCVのみ。SizeはPIT ScaleCategoryの粗い代理をimpact推定だけに用いる。stock自身の過去60日中央値と5日中央値、volatility60日。Returnのopen-open時刻と当日売買量の不整合を明記し、impactの説明変数volume/liquidityは1日lagを基本とする。
MLは最大15特徴: M, liquidity_level, liquidity_shock, volume_shock, PWV,VWP,AM,PM,range,PM/AM volume,M×PWV,M×VWP,M×liquidity_shock,M×volume_shock,VWP×(PM-AM)。B/CではM単独を除く。
短期特徴追加でturnover上昇が予想されるため同一EWMAで比較。リスクは取引コスト、翌寄付までのdecay、splitのraw volume比歪み、PIT結合、将来ラベル、年次モデル切替。複雑性は15特徴・浅い木・年次更新まで。

## 安全性・再現性

入力はファイル名allowlistを持つTrain-only loader。研究全体でValid/raw_targetへのopenを拒否する監査hookを有効化しアクセスログを保存。source AST scan、新旧未来値のbitwise prefix-invariance、cutoff truncation、列/行並べ替え、欠損・0・inf、銘柄再上場、学習purge、決定性、公式scorer一致、全Train予測coverageを検査。
データsha256・コードsha256・設定・library version・fold学習条件・モデル・全試行・不採用理由を保存。全ジョブdeadline付き。Validを実行しない。
