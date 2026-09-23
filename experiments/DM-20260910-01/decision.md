# DM-20260910-01: 採否記録

- 対象run / report: `run-20260910T000003Z` / `reports/DM-20260910-01/REPORT.md`
- 実行日 / scoring候補数 / 累積known候補数: 2026-09-10 / 4 / 56
- Hypothesis: Champion C0/T1のFundamental Deteriorationとは別のValuation、Earnings Quality、Lottery Riskが独立Short alphaを持つかを有限比較する。
- Feature set / model: H0=C0/T1。V1=開示済み年率CFO÷raw Close×PIT発行済株式数、V2=(Profit−CFO)/TotalAssetsの同一開示期間値、V3=t-20からt-1の市場残差MAX20。Long M60/EWMA(0.25)と40/40/20 stitchingを固定。
- Train / evaluation: 2008-11-04–2016-03-31 Train。2011–2014の順方向4 fold、年末2営業日purge。2015–2016-03・2008–2010は候補決定後の記述的確認のみ。

## 結果と判定

| Candidate | Net SR | ΔNet SR | Short annual Net | ΔShort annual Net | Turnover | 判定 |
|---|---:|---:|---:|---:|---:|---|
| H0 Champion | 0.7839 | +0.0000 | -1.04% | +0.00% | 0.0584 | Reference |
| V1 CFO Yield | 0.3966 | -0.3873 | -2.89% | -1.84% | 0.0627 | Reject |
| V2 Accrual | 0.4591 | -0.3249 | -2.59% | -1.55% | 0.0597 | Reject |
| V3 MAX20 | 0.4227 | -0.3613 | -2.63% | -1.59% | 0.0940 | Reject |

V1/V2/V3はいずれもpooled Short Netが負、Short positive foldは各0/4・0/4・1/4、Championを上回るShort foldは各0/4である。Total Net Sharpeも全候補でChampion未満で、Long固定auditは全差分0だった。よって事前登録されたAdoptable条件は一つも満たさない。

**Decision: 全ChallengerをReject。** Independent Short Alpha Family探索の本ラウンドは不採用とし、Champion C0/T1を維持する。結果を見た後のcandidate/window/factor combination追加、Freeze、Valid評価は行わない。

## Required evidence

- 3 cutoff（2010-12-30、2012-06-29、2014-12-30）の全入力future-mutation/truncationで、31特徴量とH0/V1/V2/V3予測がbitwise prefix-invariant。
- H0予測はDM-20260909-03 C0と809,636行でbitwise一致。全候補のQ4/Q5所属、Long weight、日次Long P/Lは完全一致。
- firewall記録はTrainの入力、Train target、過去C0予測、当runの予測だけであり、Valid/raw target readは0。
- `make test`: 46 passed。bounded Train実行は1800秒上限に対して約6分で完了。
