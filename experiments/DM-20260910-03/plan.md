# DM-20260910-03: 事前研究計画

Status: planned。設定の正本は `config.json`、戦略仕様正本は
`docs/strategies/投資戦略仮説0910-03.md`。公式ルールおよび `AGENTS.md` を最優先する。

## Hypothesis

西部証券の Daily Turnover Information (DTI) を、raw `Volume` と開示済みの
発行済株式数から作る21営業日の換手率時系列・その昇順系列（計42列）の Elastic Net として
日次competitionへ適応する。High scoreをLong、Low scoreをShortとする単一全銘柄ランキングが、
Champion H0（M60 Long + equal FD Short）および単純な21日平均換手率 M0 を上回るかを検証する。
これは中国A株・月次の原研究の直接replicationではない。

## Why it should work / Why it may persist

日々の参加強度の時系列順序と分布形状は、平均換手率だけでは捨てられる需給の持続・集中・
過熱を表す可能性がある。原研究はDTIについて正のICを報告しているため、M0/DTIとも高スコアを
Longへ固定する。市場制度・投資家・保有期間は異なるため、本実験で独立に確認する。

## Why it should survive t+1 open

公式READMEはt日までに観測された日次価格・出来高をsignalに利用できるとしているため、
`Volume_t / Shares_t` を使う。日中の参加強度が引け後から翌寄付までに完全に反映されない場合のみ
残る仮説であり、t+1以降の価格・出来高・labelは用いない。

## Expected turnover impact / Leakage risk / Complexity cost

順位は日々更新されるため高回転の可能性がある。T3だけは事前固定のEWMA(0.25, adjust=False)で
cost低下を診断する。分母は `NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock`
だけを、開示日より厳密に後の日へbackward-asof状態として使い、450日超の古い状態は無効にする。
これは自己株式を含む発行済株式数であり浮動株数ではない。raw Volumeとのsplit整合、更新頻度、欠損を
preflightで監査し、PIT安全かつ十分な分母を構築できなければ候補を採点せず `not executable` とする。
raw/logの選択、window、分母、target、modelの事後変更はしない。CPUの42列Elastic Net・年次fitのみで、
ネットワーク/GPUは不要である。

## Baselineと変更点

H0はDM-20260910-01 artifactからbitwise再現する現Champion。M0は同じcomplete 21日換手率の
算術平均、T1はraw target Elastic Net、T2は日次cross-sectional rank target Elastic Net、T3は
T2のEWMA(0.25)である。M0/T1/T2/T3はDTI系scoreだけで公式5分位のLong/Short両側を決める。
ターゲットは `target_1day_train` のみ。各年は前年末までにt+2が実現したlabelだけでfitする。
Scalerも同じfit行だけでfitする。T1/T2のalpha/l1_ratio有限gridはconfigに固定し、RAWは過去MSE、
RANKは過去mean daily Spearman RankICで選ぶ（同点は低turnover proxy、強い正則化、辞書順）。

## Train-only期間・有限候補・採否基準

Trainは2008-11-04–2016-03-31、開発foldは2011–2014、各年末の2営業日をpurgeする。
H0/M0/T1/T2/T3の5候補以外は採点しない。Full replacementには pooled Net SR > H0 かつ
Net SR改善3/4以上、Long replacementにはpooled Long Net/SR > H0かつ改善3/4以上、Short replacementには
pooled Short Net > H0、改善3/4以上、median ΔShort Net >0を要求する。2015–2016-03は採否後の記述的確認のみ。

## 既知データ・確認期間・過去の失敗

2011–2014は既読Trainであり、independent OOS/unseen holdoutとは呼ばない。DM-20260910-02のDRIは
全係数ゼロ・Full replacement失敗で却下済みだが、DTIは別alpha familyとして事前登録する。既知累積
scoring trial数は60で、今回の5候補を完遂した場合65となる。2015–2016-03は選択後のみ同一仕様で記述する。

## 検証・実行コマンド

実行前にdenominator preflightを行う。pass時のみstrategy source scan、source firewall、Volume/FINS全入力の
future-mutation/truncation prefix-invariance、H0再現、annual cutoff/scaler、NaN・complete-window・zero-volume・
relisting・determinism、coverage、official weight/costとLong/Short allocationを検査する。
`make test` 後、`tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.dti_long_short --config artifacts/DM-20260910-03/<run>/config.json --output artifacts/DM-20260910-03/<run>` を実行する。
Valid、raw targetは読まない。Freeze/submission/Valid評価は範囲外である。
