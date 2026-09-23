# DM-20260911-03: DRI regularization without L1 collapse

事前登録日: 2026-09-11。ユーザーはRidge版と全ゼロ境界に対する相対alphaのElastic Net版の検証を依頼した。
既存DM-20260910-02を変更しない新規の有限比較。設定の正本はconfig.json。

## Hypothesis / Why it should work / Why it may persist

過去21観測営業日の時系列returnと同じreturnの昇順vector（42特徴量）に分散した弱い予測情報がある場合、
L2 shrinkageまたは学習標本ごとのL1境界未満のpenaltyは、その順位情報を保持しうる。
価格圧力、投資家の段階的反応、裁定制約という旧DRIの仮説を維持する。
全ゼロを回避してもノイズに順位を付けるだけの可能性があり、非ゼロ係数を成功基準としない。
旧DRIのinitial CVではnullに近いモデルのMSEが最良だった。この反証を保持する。
今回は既存線形仮説の正則化診断であり、新しい特徴量・非線形モデルは導入しない。

## Why it should survive t+1 open

提供raw_return[t]はt-1 Open→t Open。特徴量はtまで、ラベルはt+1 Open→t+2 Openを維持する。
価格圧力が翌寄付後にも持続する場合だけ有効である。効果の持続を前提に採用しない。

## Expected turnover / Leakage risk / Complexity

旧DRIの同値順位から動的順位へ変わるためturnoverが大きく増えるおそれがある。
全新候補のEWMAは0.25固定。Gross/Net/Costを分離し、追加平滑化やbufferは試さない。
scaler、alpha_max、係数は各fitの過去の実現済みTrainラベルだけで推定する。
微小ノイズ追加は禁止。alpha_max=0ならnullを保持し失敗として記録する。
42列、CPU、single BLAS thread、bounded 1800秒。RidgeとElastic Netの線形モデル。

## Fixed candidates and tuning budget

同じRAW/RES特徴量各々についてRidge、相対alpha Elastic Netの4新モデル。
Long/Shortとも旧DRIと同じ全銘柄ランキング。Long固定hybridは今回追加しない。

- H0: 現Championの保存済みTrain予測。
- B0: Momentum-only baselineの保存済みTrain予測。
- O_RAW/O_RES: 旧D2/D3の保存済みTrain予測（全ゼロ係数、EWMA 0.25）。
- R_RAW/R_RES: StandardScaler + Ridge、目的関数 MSE/2 + lambda*||w||²/2。
  lambda候補[0.01,0.1,1.0]、sklearn Ridgeのalpha=n_train*lambdaへ換算。
- E_RAW/E_RES: StandardScaler + ElasticNet、l1_ratio=0.5。
  alpha_max=max(abs(X_scaled.T@(y-y_mean)))/n/l1_ratio、alpha=rho*alpha_max。
  rho候補[0.1,0.5,0.9]。毎fitの訓練行だけでalpha_maxを再計算。

各family×RAW/RESにつき3候補を旧DRIと同じinitial CV 2foldで比較し、pooled MSE最小を選ぶ。
同値時は強い正則化を選ぶ。年次fitは選んだlambda/rhoを固定する。
計12 hyperparameter configurations、24 CV fits、4×6=24 annual fits（監査の再fitは探索に数えない）。
各CV foldの訓練平均予測をnull比較として記録するが、nullを避ける診断という目的から選択には含めない。
MSEをRankIC/Sharpeへ変更せず正則化の効果を分離する。4新候補+4対照=8 portfolio scoring trials。
既知累積採点数75に8を加えて83（対照の再採点を含む）。CV budgetは別記する。

## Evaluation and stop rule

Train: 2008-11-04–2016-03-31。initial CVは旧2fold、開発は2011/2012/2013/2014。
fit/評価境界はt+2が境界を跨がないよう2営業日purgeする。
2015–2016-03は既読の記述的確認。4候補の採否を保存後に確認し再選択しない。
2008–2010は学習のみ。全Trainは繰り返し探索済みで独立OOSとは呼ばない。

技術的成立: 各開発年で非ゼロ係数が存在し、complete rowsの予測に日次断面分散があること。
全体改善: H0超のpooled Net SR、3/4以上のNet SR改善年、median ΔNet SR>0。
Short改善: H0超のpooled Short年率Net、3/4以上のShort改善年、median ΔShort年率Net>0。
Long改善はpooled Long Net/Sharpeと3/4改善年で別記する。
Shortの安定した正収益源化はpooled Short Net>0かつpositive folds>=3/4で別記する。
Champion候補は技術的成立+全体改善+Short改善。20日block paired bootstrap 1000回95%区間を記述し、
全体ΔNetSR区間下限が0以下ならPromisingに留める。
Longも変わる比較なのでShort leg好成績だけでLong固定hybridの成功とは呼ばない。
H0、B0、対応する旧O_RAW/O_RESへの必須指標差分をfold/pooledで記録する。
追加grid、window、target、非線形化、hybrid、事後の符号反転は行わない。
全4新候補を保存して終了。Freeze/Valid評価なし。

## Verification / provenance / command

旧feature builderとのbitwise一致、全入力3cutoff future-mutation/truncation、実Trainのラベル未来改変による
年次refit一致とinitial CV選択一致、モデル保存読込一致、欠損・定数列・再上場・全ゼロ境界・決定性・
独立提出コピーTrain smoke・公式会計一致を検査する。
学習/推論の正本は新strategy内models.py。submission.pyは保存済みbundleと3特徴量ファイルだけを読む。
ラベルを読むのは研究driverだけ。推論コピーにラベルは配置しない。
コードsnapshot/hash、設定hash、Train入力hash、モデル、係数、予測、日次損益、監査、環境を保存。
実行: tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.dri_regularization --config <prepared-run>/config.json --output <prepared-run>
