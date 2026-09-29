# DM-20260924-11: BOX_RIDGE_001 Phase 1 仮説識別診断

Status: planned。既読Trainのみの記述診断。戦略の採用・再選択、Freeze、Valid評価には使わない。

## Hypothesis

DM-20260924-10の5特徴Ridge予測が弱い原因を、(A)新高値イベント内にボックス情報の予測力がない、(B)B00 blend・EWMA・5分位weightで情報が希釈される、(C)Gross改善が回転率・コストで消える、に分ける。追加学習target horizonは公式 `t+1 Open → t+2 Open` の1日市場残差に固定する。

## Why it should work / Why it may persist

これはモデル追加ではなく、既存予測経路を測る診断である。高値更新前の圧縮期間・幅・上限接触・出来高・事前トレンドに1日持続性があるなら、まず新高値イベント内の順位と分位収益に現れるはずである。出来高と抵抗線接触は、ブレイクへの参加の広さ・上値供給の消化を表す可能性があるが、今回それらは単変量診断だけに使う。

## Why it should survive t+1 open

既存特徴はt-1までのbox状態とt終値のブレイクで確定し、翌寄付をエントリーとする。寄付までの反応で消える可能性を含め、イベント内の公式1日残差RankICと分位収益を測る。昼 (`t+1 Open → t+1 Close`)・夜 (`t+1 Close → t+2 Open`) は原因診断のみで、執行・保有期間の変更には用いない。

## Expected turnover impact / Leakage risk / Complexity cost

候補スコア変更は最終順位とturnoverを動かし得るため、Gross P&L、weight差、turnover、10bps cost、Net P&Lを同一日付で計算する。特徴・Ridge・対象イベントはDM-20260924-10と同じで、モデル候補は増やさない。固定ablationはblend `{0, 0.5, 1}` × EWMA alpha `{0.25, 1.0}` の6通りだけ。raw出来高比率と上限接触密度はTrain raw OHLCVを使う事後の単変量診断であり、モデル学習・提出特徴には加えない。

情報時点は既存コードのsignal日t・t-1窓端を確認し、DM-20260924-10の3 cutoff future-mutation/truncation prefix auditを根拠として再掲する。診断スクリプトはtargetを予測生成に渡さず、年別予測は保存済みのTrain-only expanding Ridge手順だけから再現する。Valid・raw_target・未参照区間は禁止。

## Baselineと変更点

* **B00**: 既存250観測新高値Long / 新安値Short score。Long/ShortとEWMAを含む現行score経路を基準にする。
* **BOX raw prediction**: DM-20260924-10と同じannual expanding Ridge (lambda=1.0)・5特徴・breakout-only学習/予測。保存済み予測・モデルhashと一致を確認。
* **6 ablations**: BOX event内予測rankをB00 raw scoreへ0/50/100% blendし、alpha 0.25または1.0。全候補でShort scoreはB00のまま。alpha=1はEWMAを実質offにする診断。
* **Event-only**: BOX raw prediction順位だけで新高値イベント内RankIC、五分位平均残差、単調性、hit rate、年別符号を測る。
* **単変量**: box_duration、tightness (`-box_width_atr`)、close_position、distance_to_prior_high、relative_strength_60、breakout volume ratio、upper-touch densityをイベント内で個別に評価する。出来高比率はt出来高/ prior 20日common-unit出来高中央値。upper-touch densityは選択boxのprior高値の1%以内に入る観測比率。
* **情報時点比較**: 現行t-1 box stateと、t日High/Low/Closeまで含めて作る同じ固定定義のduration/width/close-positionを各々単変量で比較する。これは特徴タイミングの記述診断のみで、model fitや候補順位付けに使わない。既存relative_strength_60はskip-one仕様を維持し、t日intraday residualへの変更は行わない。
* **Matched control**: Group A = 新高値イベントかつbox_duration>0。Group B = 同日のB00新高値候補のうちGroup A以外（従ってbox_duration=0）。A/Bを日ごとに等ウェイト平均し、両群が存在する同一日だけで公式O2O残差とraw昼・夜収益を比較する。群サイズ差と対象日coverageも記録する。

## Train-only期間・有限候補・採否基準

* Train: 2008-11-04〜2016-03-31。既知Trainであり、2011〜2015年を中心に、2016-01〜03の部分foldを分離して報告する。既存DM-20260924-10と同じ年次expanding fit、2取引日purge、評価年末の最終2 signal日除外。
* 実験上限は固定6 score ablations。単変量とmatched-controlは同じrun上の診断集計で、追加モデル試行・追加候補ではない。
* Primary diagnosis: event-only pooled/annual RankIC、五分位単調性、日次hit、BOX 100%・alpha=1のweight/Net伝達、Gross/turnover/cost差、年次符号安定性を順に確認する。Full Train最大Sharpeで選ばず、候補を採用しない。
* 分岐: event-onlyがほぼゼロでBOX100%/alpha1でも構造がなければ現行1日BOX仮説を停止方向。イベント内では構造がありweight伝達が弱ければ希釈を主因候補とする。Gross改善がNetへ届かない場合のみコスト問題とする。durationが下限へ集中する場合は現定義を未検証とし、分布と理由を報告する。年で符号が不安定ならregime/既知Train overfitの可能性を優先する。
* Phase 2（Short policy、interaction、流動性stress等）はPhase 1結果が事前基準を満たした場合のみ別の有限計画で実施する。結果を見た無制限な救済探索は禁止。

## 既知データ・確認期間・過去の失敗

2011〜2016-03はDM-20260924-10および先行breakout/volume実験で既読。独立OOSではない。DM-20260924-10ではNet SR 0.8225、B00 0.8197、ΔNet SR +0.0028、20日block bootstrap CI `[-0.0269, +0.0291]`、ΔRankIC +0.00007のためBOX_RIDGE_001を却下済み。今回の再計算は伝達経路の説明に限る。Validは既読・未読のいずれも今回開かない。

## 検証・実行コマンド

* 既存feature builderのsource scan / leak audit / 3 cutoff future-mutation・truncation prefix-invariance結果を参照する。新しい出来高・接触密度・t-close時点の診断列は独立した3 cutoff future-mutation prefix-invarianceを追加する。戦略feature builder自体は変更しない。
* 再構成した50% blend・alpha 0.25 scoreをDM-20260924-10保存signalsにbitwise照合する。event-to-weight coverage、index一意性、日次Long+Short/コスト/Netの会計照合、決定性、Train-only firewallを検査する。
* 予定run: `.venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.box_phase1_diagnostics --config artifacts/DM-20260924-11/<run_id>/config.json --output artifacts/DM-20260924-11/<run_id>`
