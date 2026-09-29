# DM-20260926-01 採否記録

Status: completed。全12条件を固定Train-onlyで実行し、結果は既読Trainの記述比較として記録した。独立OOS評価や採用判断には使わない。

## 実験記録

- Run: `run-20260926T143032Z-08`、実試行数12/12。run metadata: `artifacts/DM-20260926-01/run-20260926T143032Z-08/run.json`。
- 対象: 現行 `BOX_BIDIR_STANDALONE` holdings audit、Low-no-carry Candidate A、別運用仕様のShort比例縮小 gamma 1.00/0.50/0.25/0.00、Candidate BのB1/B2/B3。
- 評価: Train 2008-11-04〜2016-03-31、評価2011-01-04〜2016-03-29（1275日）。2016部分期間は2016-01-04〜2016-03-29（59日）。年別・fold別結果とex-2016を併記。
- 取引費用: 片道10bps、年率換算252日。全候補で公式Train残差target、O2O評価、日次5分位を使用。gamma<1はShort weightだけを縮小する別運用仕様で、公式5分位結果ではない。
- 仮説・固定条件: [plan.md](plan.md)、[config.json](config.json)。

## 結果・判断

### 1. Current BOX

- **Reject**。BOX Net Sharpe 0.7851、年率Net +3.65%に対し、B00は0.8197、+3.83%。RankICもBOX +0.0110、B00 +0.0109でほぼ同水準。現行Box/RidgeにB00超過の安定した根拠がない。
- セーブ済みscore、accountを再現し、Q1/Q5・Long/Shortの実保有とCode順zero-score tie依存を監査した。Q1/Q5・業種偏り・score-zeroのgross/net P&L、年別category attribution、共通残差ドリフト分解は[監査レポート](../../reports/DM-20260926-01/AUDIT.md)に記録。

### 2. Candidate A

- **Stop**。Low残存を止めた公式5分位候補はBOXでNet Sharpe 0.7389（現行比 -0.0461）、年率Net +3.02%（-0.63pp）、Turnover 0.0459/日、年率Cost 1.15%。B00にも同じ変更をするとNet Sharpe 0.8016（B00比 -0.0181）、年率Net +3.32%。
- BOXのex-2016 Sharpeだけは+0.0228改善したが、2016部分期間の成績と2011/2015が悪化し、全期間では改善しない。Common成分の変化は+0.034pp、selection成分は-0.315ppで、Short枠は残った。Q1 score-zero weightは9.48%から51.87%へ上昇し、Short gross weight中のscore-zero/Code順tie保有は8.05%から46.86%へ増えた。aged Low 60.0%が消えた分、aged Highは30.25%から50.73%、zero-score保有が増えてQ1を埋めた。
- Separate Short scalingでは、BOXのNet Sharpeはgamma .50/.25/0で1.0434/1.0571/1.0122、B00は1.0602/1.0644/1.0131。BOXは同じgammaのB00を下回り、ex-2016はいずれもSharpe 1未満。改善はShort lossとcostの減少に加え、net-long exposureと共通残差成分の増加を含む。BOX gamma .50/.25/0のnet exposureは+25.0/+37.5/+50.1%、common成分は+1.78/+2.64/+3.50%、selection成分は+3.38/+2.87/+2.37%、年率Net volatilityは4.29/4.62/5.23%（現行4.65%）。Long/Short別、year/fold別、paired block bootstrapは[結果レポート](../../reports/DM-20260926-01/EXPERIMENT_RESULTS.md)とCSVに保存した。
- gamma<1は非公式のShort比例縮小ルールであり、公式5分位戦略として扱わない。

### 3. Candidate B

- Box条件: **弱いpooled point-estimateの可能性のみ**。B2−B1はNet Sharpe +0.0424、年率Net +0.006pp、ex-2016 Sharpe +0.0509。ただしGrossは低下、6年中2年のみ改善、paired 20日block bootstrap区間は0を含むため、Box gateの追加価値を確認したとはしない。
- Ridge順位付け: **追加価値の根拠なし**。B3−B2 Net Sharpe -0.1517、年率Net -0.68pp、ex-2016 Sharpe -0.1634。B2/B3のeligible event集合一致を確認した。
- Box窓長・幅thresholdの追加探索はしない。

## 検証・有効性の範囲

- focused regression tests: **10 passed**。`make check`: **PASS**（28 experiments、129 frozen hashes）。
- Train-only firewall/source scan、保存score/account replay、公式quintile weight一致、PIT sector key重複なし・coverage 100%、score coverage 576,535/576,535、B2/B3 eligible-event一致、3 cutoffでのmutation/truncation prefix-invariance: **PASS**。
- event age、sector bias、common residual driftは実保有への記述帰属であり、独立取引期待値ではない。全Train期間は既読であり、結果をOOSと呼ばない。
- Valid / Valid target / raw targetは未読。Freeze、仕様変更、外部提出なし。

## 最終決定

1. Current BOX: **Reject**（B00に対する増分優位がない）。
2. Candidate A: **Stop**（Low-no-carryはfull Trainで悪化し、Short shrinkのSharpe 1超は同じgammaのB00でも同等以上、かつex-2016で1未満）。
3. Candidate B: **Box gateの弱い可能性のみ記録、Ridgeは不採用**。
4. Next actionは1つ: **eligible-Box gateを弱い固定仮説として記録して本Train系列を終了する。追加探索もValid評価も行わない。**

## 出力

- [AUDIT.md](../../reports/DM-20260926-01/AUDIT.md)
- [EXPERIMENT_RESULTS.md](../../reports/DM-20260926-01/EXPERIMENT_RESULTS.md)
- [DECISION.md](../../reports/DM-20260926-01/DECISION.md)
- [run-20260926T143032Z-08](../../artifacts/DM-20260926-01/run-20260926T143032Z-08/run.json)
