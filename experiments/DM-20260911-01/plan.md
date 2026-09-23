# DM-20260911-01: 事前研究計画

Status: planned。設定の正本は `config.json`、仮説の正本は `docs/strategies/投資戦略仮説0911-01.md`。

## Hypothesis

通常DTIの日次適応は弱いGross edgeを示した一方で、EWMA 0.25でもコスト控除後は負であった。事前固定したS0/A1/S1/U1/R1が、強いEWMA（0.05）、銘柄固有の通常換手率の除去、return方向・大きさの条件付けにより、DTIを10bpsコスト後に正のNet Sharpeへ変換できるかを検証する。

## Why it should work / Why it may persist

TOの水準ではなく、通常状態からの参加強度の乖離と、その際の価格方向・大きさが、需給の継続または過熱を表し得る。各表現は21日形状と分布を保持し、Elastic Netは過度な自由度を避けて安定的な成分のみを選ぶ。

## Why it should survive t+1 open

t日のraw Volumeと同日までのraw return、同日時点で厳密に過去の開示済み発行済株数だけを使う。引け後から翌寄付までに参加強度の全情報が織り込まれない、という限定仮説であり、t+1 openからt+2 openの許可targetでTrain-only評価する。

## Expected turnover impact / Leakage risk / Complexity cost

alpha=0.05はD0より順位変動と片道10bpsコストを下げると予想する。60日medianはstrictly-priorで、特徴量・モデル・スケーラは全てpast-only。future mutation/truncation、baseline時点、年次cutoff、zero volume・履歴不足を検査する。候補は7本に固定し、CPUのみの最大84列Elastic Netで実行する。

## Baselineと変更点

H0は現在Championを既存artifactとbitwise再現する。D0は前回T3をexact reproduction、S0はD0のalphaを0.05へ固定して変更するcontrol。A1/S1/U1/R1は仮説書どおりの表現だけを変更する。21日window、60日strictly-prior median、daily rank target、DM-20260910-03 RANKで選択済みのElastic Net（alpha=0.0003, l1_ratio=0.1）、年次expanding fit、purge、公式5分位weightsと10bpsは固定する。新representationごとのpenalty再選択はしない。

## Train-only期間・有限候補・採否基準

Trainは2008-11-04–2016-03-31。評価foldは2011–2014、各fitは前年末までにt+2が実現したlabelのみを用い、2営業日purgeする。H0/D0/S0/A1/S1/U1/R1の7候補だけを評価する。DTI salvageはNet SR>0、positive Net-SR folds 3/4以上、Annual Net>0。H0置換はさらにH0超過かつ改善3/4以上を要する。

## 既知データ・確認期間・過去の失敗

2011–2014は既読Trainであり独立OOSではない。DM-20260910-03のT3はNet SR -2.8882で、D0 controlとして再現する。前回の既知累積trial 65に今回の実scoring 7を加える。2015–2016-03は判定後の記述的確認のみであり、再選択しない。

## 検証・実行コマンド

`tests/strategies/dm_advanced_dti/`でstrictly-prior median、future mutation、zero volume、vector完全性、determinismを検査する。実行前にsource scan、全input future-mutation/truncation、H0/D0 reproduction、annual cutoff、coverage、official accountingを監査する。実行は `tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.advanced_dti --config artifacts/DM-20260911-01/<run>/config.json --output artifacts/DM-20260911-01/<run>`。Validとraw targetは読まない。
