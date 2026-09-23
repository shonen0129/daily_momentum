# DM-20260910-01: Independent Short Alpha Families

Status: planned。2026-09-10にTrainのラベル非参照データ監査を完了して固定した。`prepare-run` がこの計画と `config.json` のSHA-256 snapshotを作成してから初めてscoringする。

## Hypothesis

Champion C0/T1（M60/EWMA(0.25) Long、等ウェイト Fundamental Deterioration Short）とは経済的に独立した、次の単一Short riskが翌日リターンの低下を捉えるかを有限比較する。

- V1 Valuation: 開示済み年率CFOに比べ時価総額が大きい銘柄は過大評価されやすい。
- V2 Earnings quality: 同一開示期間で会計利益がCFOを上回る銘柄は利益の質が低い。
- V3 Lottery: 当日を除く直近20営業日の最大市場残差リターンが大きい銘柄は宝くじ的過大評価を受けやすい。

これは `docs/strategies/投資戦略仮説0910-01.md` のV1–V3だけを、追加候補・合成・window探索なしに検証する。

## Why it should work / Why it may persist

価格対キャッシュフロー、accrual、極端な固有上昇はそれぞれ valuation、会計品質、投資家選好という異なる情報摩擦を表す。開示処理・投資家の過剰反応・裁定制約は即日には完全に解消しにくく、t+1寄付後の一日にも残る可能性がある。一方で、これは既読Train上の有限比較であり独立OOSの証明とは扱わない。

## Why it should survive t+1 open

財務情報は公開済みのものを翌営業日以後にのみ使い、V3もt日の残差リターンを除外する。よってt時点で形成した順位に、t+1寄付以前にまだ完全に織り込まれない断面差が残る、という仮説である。targetはt+1 Openからt+2 Openで、feature構築中には読まない。

## Expected turnover impact / Leakage risk / Complexity cost

V1/V2は開示状態の更新時のみ大きく変動し、V3は日次ローリング窓のため相対的に高回転となり得る。全財務値は開示日より後のbackward as-of状態、raw `Close` と同開示の発行済株式数だけを使う。価格水準にAdjustment列は使わない。負のshift、centered rolling、bfill、forward as-of、target/raw target/Validファイルの読込みを禁止する。計算はpandasの固定窓・日次断面順位のみで、ML・学習・探索は行わない。

## Baselineと変更点

Baseline/Championは DM-20260909-03 C0（DM-20260909-02 T1 のbitwise再現）である。M60 residual momentum、skip=1、EWMA alpha=0.25、Long上位40%、Long内部順位・weights・smoothingは変更しない。すべての候補は、Longを除く60%をShortRisk降順で下位40%（Q1/Q2）・中立20%（Q3）へ固定的にstitchする。

- H0: Champion FD equal weight（再現control）。
- V1: `CFOYield = (CFO * 365 / period_days) / (raw Close * disclosed issued shares)`。CFOが負でも連続値のまま使う。CFO、shares、raw Closeが有限かつshares/Closeが正、開示状態の年齢が0–450日でなければ欠損。
- V2: 同一の有効な開示行の `Accrual = (Profit - CFO) / TotalAssets`。TotalAssetsが正でなく、またはCFO/Profitが欠損なら欠損。
- V3: `MAX20 = max(residual_return[t-20:t-1])`、20観測を要求する。`IdioVol20` は同じlagged residualの標準偏差で診断のみとし候補にはしない。

V1/V2の欠損は日次断面percentileを0.5（中立）に、V3も履歴不足を0.5にする。tieはLong順位、Codeの順で決定する。

## Train-only期間・有限候補・採否基準

Trainは2008-11-04–2016-03-31。開発foldは2011、2012、2013、2014で、t+2ラベルが年境界を跨ぐ最後の2営業日をpurgeする。2015–2016-03と2008–2010は候補決定後に同一条件で記述的にのみ確認する。候補はH0/V1/V2/V3の4本、max_trials=4、seed=20260910で固定する。

Adoptableの必要条件は、2011–2014 pooled Short annual Net > 0、Short annual Net > 0 が3/4 fold以上、ChampionをShort annual Netで上回るfoldが3/4以上、median ΔShort annual Net > 0、Total Net Sharpe >= Champion、Long固定auditが全ゼロであること。その他はPromising but insufficientまたはRejectとする。paired circular-block bootstrap（20日block、1,000回、seed固定）は診断であり採否を後付けで変えない。

## 既知データ・確認期間・過去の失敗

2011–2014を含むTrainは既読であり、結果をindependent OOS/unseen holdoutとは呼ばない。DM-20260909-02でT1はChampionとなり、DM-20260909-03のProfitability/Balance/Multi-dimensional extensionsは全て却下された。このためFDの再重み付け、WeakPrice interaction、liquidity、ML、factor combinationは実施しない。開始時点の既知累積scoring候補は52、今回後は56である。

## 検証・実行コマンド

新strategyの静的firewall、全入力future mutation/truncation（2010-12-30、2012-06-29、2014-12-30）、決定性、C0/T1 bitwise同値、Long固定、coverage、公式weight/cost整合を実施する。`make test` 後、`tools/run_bounded.py --seconds 1800` を付けたTrain-only driverを実行する。Valid、raw target、Valid行数・coverage・prediction・performanceは一切読まない。
