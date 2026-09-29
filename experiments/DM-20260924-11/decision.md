# DM-20260924-11: Phase 1 診断の記録

- 対象run / report: `run-20260924T194237Z` / [REPORT](../../reports/DM-20260924-11/REPORT.md)
- 実試行: 固定6 score paths。全期間2011-01-04〜2016-03-29（既知Train）。2011–2015 full yearsと2016 stubを分けた。
- 仮説 / 変更: 既存Ridge出力がevent-only段階にないのか、blend/EWMA/portfolioで希釈されるのか、grossがcostで失われるのかを診断。公式O2O target、Ridge、特徴、B00 Short、費用条件は固定。
- モデル / 特徴: annual expanding Ridge λ=1、box duration/width/close position/relative strength 60/distance to prior high。比較はBOX blend 0/50/100% × EWMA α=.25/1。
- 主要値: BOX blend 50%、α=.25のNet SR .8225、B00同条件 .8197、Δ+.0028。blend 100%・α=.25はNet SR .8315、Δ+.0117、年率Net差+.029%、cost差+.004%/年、turnover差+.00015/日。平均|weight差|0.000054、変更率2.96%。
- Event-only: 15,314 high-event行、RankIC +.0117、HAC5 t +.72、hit 51.9%、Q monotonicity +.90。ただしQ4 > Q5、2014年寄与の偏りと2016 stubの反転がある。
- duration: event成立boxの中央値L=5、L=5比率59.8%、L≤10比率87.2%、eventの33.0%はboxなし。現定義は可変長仮説を十分識別できず。
- Matched overnight: A raw night +.00090/日、B +.00049/日、A−B +.00041/日。年別符号は2011–2015の3年正/2年負。一般的なovernight exposureとBOX群差はともに記述上見られるが、BOX固有alphaとは判断しない。
- 因果性 / 再現性: DM-20260924-10 core prefix PASS、追加Volume/touch/t-close future-mutation prefix PASS（3 cutoff）、B00/BOX scoreと6年モデル再生一致、Train firewall・index・会計PASS。Valid/raw_target未読。
- Decision: **診断完了、戦略No-Go。** 元BOX_RIDGE_001をB00の代替に採用しない。duration集中の事前分岐によりsqrt(L)補正を一度だけ[DM-20260925-01](../DM-20260925-01/decision.md)で実施。補正後はLmax=120に飽和、追加救済なしで1日BOX研究を停止。Phase 2を実行しない。
- Freeze / Valid: なし。Valid未閲覧。
- 初回report formatting失敗は `logs/first_attempt_failure.json` に保存し、診断済みCSV/JSONから同じrunのreportを再開。Parquetを再読せず、初回失敗をrun metadataに保持。
