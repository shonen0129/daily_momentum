# DM-20260909-03: 採否記録

- 対象run / report: `run-20260909T080902Z` / `reports/DM-20260909-03/REPORT.md`
- 実行日 / scoring候補数 / 累積known候補数: 2026-09-09 / 4 / 52
- Hypothesis: Fixed M60 Longを壊さず、Cash Flow、Profitability、Balance Sheetの継続的なPIT weaknessでShort側を改善する。
- Feature set / model: C0=T1 cash FD、C1=Operating/Ordinary/Profit assets YoY、C2=Equity/Assets・Cash/Assets、C3=3 block等ウェイト。固定式の日次cross-sectional rank・score stitching。
- Train / evaluation: 2008-11-04–2016-03-31 Train。2011–2014を開発fold、年末2営業日purge。2015–2016-03と2008–2010は記述的確認のみ。

## 結果と判定

| Candidate | Net SR | Short annual Net | Turnover | RankIC | 判定 |
|---|---:|---:|---:|---:|---|
| C0 (T1 reproduction) | 0.7839 | -1.04% | 0.0584 | 0.01005 | Reference |
| C1 Profitability | 0.7406 | -1.22% | 0.0604 | 0.00779 | 却下 |
| C2 Balance | 0.7830 | -0.99% | 0.0558 | 0.00935 | 却下 |
| C3 Multi-dimensional | 0.8142 | -0.81% | 0.0582 | 0.01041 | 却下 |

- C1: Short改善は2/4fold、pooled Short NetとNet SharpeがC0未満。
- C2: pooled Short Netは+0.05pt改善したが2/4fold、Net SharpeもC0未満。
- C3: pooled Short Netは+0.23pt、Net Sharpeは+0.0302改善したが、Short改善は1/4fold、median ΔShort Netは-0.11pt。Short側は-0.81%で依然マイナス。
- 全候補でQ4/Q5 membership、Long weight、日次Long P/LはC0と完全一致。

**Decision: 全Challengerを却下。** 事前登録したShort-side consistency基準を満たす候補はなく、C3の合算Net Sharpe改善だけで採用しない。C0/T1をChampionのまま保持し、FreezeおよびValid評価は行わない。

## Required evidence

- Validとraw targetは未読。targetは因果性監査後にTrain評価のためだけに読んだ。
- C0 predictionは既存T1と809,636行でbitwise一致。portfolio日次値は既存CSVの再読込精度内（最大差 <1e-15）で一致。
- 3 cutoff（2010-12-30, 2012-06-29, 2014-12-30）の全入力future-mutation/truncationで、43特徴量とC0–C3予測がbitwise prefix-invariant。
- `make test`: 41 passed。bounded execution: 1800秒上限内で完走。
