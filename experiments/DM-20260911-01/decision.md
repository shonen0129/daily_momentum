# DM-20260911-01: 採否記録

判定: **rejected**。Freezeなし、Valid未閲覧。

- 対象run/report: `run-20260911T000002Z` / `reports/DM-20260911-01/REPORT.md`
- 実行日 / 実試行数 / 累積試行数: 2026-09-11 / 7/7 / 72
- Hypothesis / Change: Strong EWMA、strictly-prior 60日median ATO、signed/up-down/return-conditioned ATO。
- Model: DM-20260910-03 RANKの既選択Elastic Net（alpha=0.0003, l1_ratio=0.1）を全表現に固定。再tuningなし。
- Train / evaluation: 2008-11-04–2016-03-31 / 2011–2014 expanding walk-forward、2営業日purge。
- 結果: S0がDTI内最良（Gross SR 1.0804, Net SR 0.0882, turnover 0.1339）だが、Net SR正は1/4 fold、Short Net SR -0.4766。R1は新表現内最良だがNet SR -1.5644。Champion H0（Net SR 0.7839）を上回る候補なし。
- 監査: H0/D0 bitwise reproduction、source scan、PIT denominator、future-mutation/truncation 3 cutoff、determinism、firewallはPASS。Valid/raw targetは未読。実行306秒（30分上限内）。
- Decision / reason: DTI salvage（Net SR>0、3/4 positive folds、annual Net>0）を満たす候補なし。全候補のShort Net SRは負で、advanced representationはA1–R1でGrossも負。停止条件に従いwindow、alpha、baseline、interaction、hybridを追加しない。
- Freeze / Valid: なし / 未閲覧。
