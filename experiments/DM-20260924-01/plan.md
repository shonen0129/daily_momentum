# DM-20260924-01: 52週高値近接度のCorporate-action整合性修正

Status: planned。元C3の成果を引き継がない、単一の定義修正候補 `C3S` を検査する。Train期間は既知なので、成績は探索的な記述値に限り、採否・重み選択には使わない。

## Hypothesis

元C3の `Close_t / rolling_max(High, 250)` は、raw価格の単位が株式分割・併合で変わる前後を同じ窓に混在させる。`AdjustmentFactor` の観測済みイベントを累積してraw価格を共通単位で比較すれば、企業行動による人工的な高値乖離を除いた52週高値近接度になる。さらに `min_periods=250` とし、120〜249観測の短い履歴を52週高値と同じ断面順位へ混ぜない。

## Why it should work / Why it may persist

* 分割・併合は株主の経済価値や情報を変えず、表示株価の単位を変える。raw HighとCloseを企業行動の累積係数で揃えることで、機械的な価格段差をモメンタム信号として扱わない。
* AdjustmentFactorは各日時点の観測イベントとして扱う。`event_factor = AdjustmentFactor`（値が1の行は1）、同一listing segment内の累積積を `scale_t` とし、`High_t / scale_t` と `Close_t / scale_t` を比較する。未来イベントは過去特徴量へ適用しない。
* 250個の有効なraw Highが揃った銘柄だけを52週窓として出力する。窓不足の銘柄は `prox250_split_safe` が欠損となり、既存の横断rank処理で中立値へ写像される。

## Why it should survive t+1 open

高値近接度は当日引けまでに確定する中期の価格状態で、分割単位の正規化は既知の企業行動だけを使う。翌寄付後にも状態が残るかは元C3のTrain結果から引き継がず、Validの一度限りの最終評価まで未確定とする。

## Expected turnover impact / Leakage risk / Complexity cost

* **Turnover / Cost**: 分割後に近接度が機械的に最下位化する順位歪みを抑える。入替とコストの方向・大きさはポートフォリオ会計で測定し、改善を仮定しない。
* **Leakage risk**: 使用列はraw `High`、raw `Close`、日次の`AdjustmentFactor`。イベントは同日までの情報に限定し、将来行の変更・切詰めでprefix-invarianceを検査する。`Adjustment*` 水準、Valid、raw targetは使用しない。
* **Complexity**: 企業行動係数のlisting segment内cumprodと250行rolling。学習パラメータはなく、C3と同じ0.5/0.5合成およびEWMA alpha=0.25を固定する。

## Baselineと変更点

* **Baseline**: H0、DM-20260908-v1の `res60s1` EWMA(0.25)。
* **旧C3**: `0.5*res60s1 + 0.5*prox250`。結果はDM-20260923-01に保存し、本実験の結果と合算しない。
* **C3S**: `0.5*res60s1 + 0.5*prox250_split_safe` をEWMA(0.25)。`prox250_split_safe` はraw価格を当日時点までのAdjustmentFactorイベント累積で同一単位にし、250有効観測を必須とする。旧C3との定義差はsplit-unit処理とmin_periodsだけ。
* submission既定値は変更しない。C3Sは別実験候補であり、現時点でFreeze・Valid評価・Champion昇格は行わない。

## Train-only期間・有限候補・採否基準

* **データ範囲**: Train 2008-11-04〜2016-03-31。元実験と同じ入力hashのTrainを使う。
* **開発期間**: 2011〜2014年の4 fold、ラベル境界に2営業日purge。
* **参考期間**: 2015-01〜2016-03は既知・既読なので記述のみ。選択・採否に使わない。
* **有限候補**: H0とC3Sの2本（baseline込み、追加候補1本）。重み・window・alphaの追加探索なし。
* **判定方針**: 本Trainは既知データで、元C3結果を確認した後の定義修正である。結果はscreen指標・日次損益・コスト・fold安定性の説明に使うのみで、C3Sの候補選択や採用根拠にしない。Train Sharpeの良否で修正版の定義を選び直さない。

## 既知データ・確認期間・過去の失敗

* DM-20260923-01〜03で2011〜2014と2015〜2016-03はすでに参照済み。旧C3、C6、P250の結果は reports/DM-20260923-01〜03 を参照。
* 元C3のraw近接度では、開発期間中にAdjustmentFactor変化を含む250行窓が観測された。旧結果は修正版の成績へ移転しない。
* Valid・Valid target・raw targetは未参照。FreezeとValid評価は本実験の範囲外。

## 検証・実行コマンド

1. 境界fixture、分割係数の持続、full-250窓、全入力future-mutation prefix-invariance、ソースfirewallを含む対象テスト:
   `.venv/bin/python -m pytest -q tests/strategies/dm_high_proximity_momentum`
2. Run作成:
   `.venv/bin/python tools/workspace.py prepare-run DM-20260924-01`
3. 期限付きTrain-only比較:
   `tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.high_proximity_momentum --config artifacts/DM-20260924-01/<run_id>/config.json --output artifacts/DM-20260924-01/<run_id>`
