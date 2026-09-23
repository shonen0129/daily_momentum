# DM-20260911-02: 事前研究計画

Status: planned。設定の正本は `config.json`、仮説の正本は `docs/strategies/投資戦略仮説0911-02.md`。

## Hypothesis

H1 は、当日 Raw Open→Raw Close の60営業日単純和だけで作る intraday momentum の弱さが翌日残差リターンにも継続し、固定Longの独立Short順位として H0 Fundamental Deterioration (FD) を改善するという仮説である。H2 は、H0 FDのShort候補から、翌月予測される正の歪度が高い銘柄を連続的に下げることで、lottery-like銘柄のright-tail short lossを抑えるという仮説である。両者は混ぜない。

## Why it should work / Why it may persist

H1 は overnight と日中の情報を分ける文献ベースのcontinuation仮説であり、日中の持続的な売り圧力が翌日寄付後にも完全には織り込まれない可能性を検証する。H2 はFDの弱いShort情報を維持したまま、極端なpositive-return銘柄のShortを減らすrisk-management仮説である。どちらもH0 Longとは別の経済機構である。

## Why it should survive t+1 open

Competition READMEのtiming preflightにより、signal日tのRaw Closeはtまでの観測値として利用可能で、約定はt+1 Open、評価はt+2 Openである。I1はtのRaw Open/Closeを含める。H2のforecastはforecast月開始前（月m終了）までの残差リターンだけを用いる。結果はt+1 Open以降に残るかを、許可されたTrain `target_1day_train` のみで評価する。

## Expected turnover impact / Leakage risk / Complexity cost

I1は日次価格signalなのでH0よりShort turnover/costが増える可能性がある。K1は月次expected-skewnessと低速FDであり、回転率増加は小さいと予想する。Raw OHLCは同日比率のみ、60日窓はpast/current observationsのみ、日次rankは同日断面のみ、月次forecastはforecast月より前のsource datesだけを用いる。invalid OHLC、60日履歴不足、月15観測未満、rank-deficiency、relisting segment、expected-skew欠損はそれぞれmissing→中立に固定する。CPUのみの月次最小二乗であり、候補は3本、30分上限で実行する。

## Baselineと変更点

H0 は現Champion C0/T1（M60 residual momentum + EWMA 0.25 Long、equal-weight FD Short）を既存artifactとbitwise再現する。I1 はLongとLongの順位を完全固定し、ShortRiskを `-EWMA(alpha=0.25, adjust=False)[2*rank_pct(sum_{0..59}(RawClose/RawOpen-1))-1]` にだけ置換する。K1 はLongを完全固定し、H0 FDの同日percentile rankと `1-ExpectedSkew` percentile rank を乗算する。ExpectedSkewは月次 residual-return skewness（minimum 15日）、volatility、当月残差和、m-12からm-2の11か月残差和をpredictorとする、intercept付きordinary cross-sectional least squares。係数は month m の RS_m ~ X_(m-1)、forecast は X_m に適用し m+1 の全営業日に固定する。size/industryは既存PIT入力を追加せず省略する。K1のexpected-skew欠損は0.5のneutral preferenceとする。

## Train-only期間・有限候補・採否基準

Trainは2008-11-04–2016-03-31。2011–2014を4つの年次walk-forward評価foldとして、t+2が年を跨ぐsignal日を除外する（2営業日purge）。これはモデルparameterの再選択を伴わない固定formula評価である。スコア候補は H0/I1/K1 の3本だけ、seed=20260911、片道cost=0.1%。I1/K1はShort improvement folds≥3/4、median ΔShort annual Net>0、pooled Short Net>H0を満たす場合だけShort成功とする。Strong successはpooled Short Net>0かつShort-positive folds≥3/4。Champion候補にはさらにTotal pooled Net SR>H0かつTotal Net SR改善fold≥3/4を要求する。

## 既知データ・確認期間・過去の失敗

2011–2014および2015–2016-03は既読Trainで、independent OOSではない。前回DM-20260911-01終了時のknown cumulative scoring trial count=72を引継ぎ、本実験の新規scoringは3本として75と記録する。2015–2016-03は全判定保存後に同条件の記述的確認だけを行う。DM-20260909-03のC0/T1がChampionであり、DM-20260910-01（V1/V2/V3）、DM-20260910-02（DRI）、DM-20260910-03/DM-20260911-01（DTI）はShort Netの一貫性不足またはコスト過大で却下済みである。

## 検証・実行コマンド

`tests/strategies/dm_intraday_skewness_short/`でI1のcurrent-day OHLC window、K1の月次forecast timing・minimum observations・rank deficient fallback・欠損neutral、future-mutation、決定性、fixed-long stitchingを検査する。run driverはsource firewall下で全入力の3 cutoff mutation/truncation、H0 bitwise reproduction、forecast source-date audit、prediction coverage、accounting reconciliationを実施する。実行: `tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.intraday_skewness_short --config artifacts/DM-20260911-02/<run>/config.json --output artifacts/DM-20260911-02/<run>`。
