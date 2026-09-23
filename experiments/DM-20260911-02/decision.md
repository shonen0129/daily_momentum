# DM-20260911-02: 採否記録

判定: **rejected**。Freezeなし、Valid未閲覧。

- 対象run ID / report: `run-20260911T031800Z` / `reports/DM-20260911-02/REPORT.md`
- 実行日 / 実試行数 / 累積試行数: 2026-09-11 / 3/3 / 75（既知72 + H0/I1/K1の3候補）。
- Hypothesis / Change from baseline: H0のM60/EWMA(0.25) Longを厳密固定し、I1は60 observed-row Raw Open→Close momentum/EWMA(0.25)だけでShortを順位付け、K1はH0 FD rank × monthly low expected-skewness preferenceだけでShortを順位付けした。
- Feature Set / Model / Parameters: Raw OHLCの当日比率、60日単純和、alpha=0.25; K1は最低15日/月、RS/RV/前月残差和/m-12..m-2残差momentum、intercept付き月次OLS。size/industryなし。window、alpha、predictor、overlayの追加/変更なし。
- Train Window / Evaluation Window: 2008-11-04–2016-03-31 Train / 2011–2014年次walk-forward、t+2年跨ぎ除外（2営業日purge）。2015–2016-03は選択後の記述的確認のみ。
- Gross Sharpe / Net Sharpe / Turnover / RankIC / Maximum Drawdown: H0=1.1263/0.7839/0.0584/0.01005/-7.23%。I1=0.5358/0.1867/0.0645/0.00471/-9.17%。K1=1.0952/0.6658/0.0705/0.00598/-6.82%。
- fold/年別結果・baseline差分へのリンク: `reports/DM-20260911-02/fold_metrics.csv`、`incremental.csv`、`short_side_metrics.csv`、`bootstrap_results.json`。
- リーク・coverage・決定性・smoke・時間制限の検証結果: H0はDM-20260909-03 C0の809,636予測とbitwise一致。I1/K1のQ4/Q5所属、Long weight、日次Long P/Lは差分0。3 cutoff（2010-12-30、2012-06-29、2014-12-30）のmutation/truncationで30特徴量・3候補予測はbitwise prefix-invariant。expected-skew source dateは全forecast月開始前。source scan/firewall PASS、Valid/raw target read=0。全テスト66 passed、bounded run 470.6秒（1800秒以内）。
- Decision / Reason: **I1/K1をともにReject。** I1はShort annual Net -3.54%（H0比 -2.50pt）、Short改善0/4、Total Net SR -0.5973。K1はright-tail指標（pooled target p90/p95/p99: 1.82/2.59/4.78%→1.75/2.48/4.48%）とworst 1%/5% daily short loss（-0.940/-0.635%→-0.888/-0.613%）を小さくしたが、Short annual Net -1.67%（-0.62pt）、Short改善1/4、Total Net SR -0.1182で主基準不通過。結果後のhorizon、threshold、predictor、hybrid、候補追加は行わない。
- Freezeした場合のstrategy ID / manifest: なし。
- Valid閲覧状態: 未閲覧。
