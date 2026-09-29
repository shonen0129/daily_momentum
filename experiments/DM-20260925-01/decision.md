# DM-20260925-01: 採否記録

- 対象成功run / report: `run-20260924T202625Z` / [REPORT](../../reports/DM-20260925-01/REPORT.md)
- Run状態: 完了。事前登録6/6 score paths、実行時間222.1秒。`run-20260924T202434Z`・`run-20260924T202528Z` は研究runnerの検証エラーで予測前に失敗し、証跡として保持。
- 仮説 / 変更: 元定義の成立durationがL=5〜10に偏ったため、案AのCR=`Range/(ATR20*sqrt(L))` を閾値3.0未満で使う最長durationへ一度だけ変更。公式holding期間・target・cost・purgeは不変。
- Feature / Model: 原5特徴、annual expanding Ridge λ=1、high-event population。変えたのはduration・その選択窓幅・close positionのみ。
- Train / evaluation: 既読Train 2008-11-04〜2016-03-31、評価日2011-01-04〜2016-03-29。2011–2015 full years、2016 stubを分離。2日purge。
- Event-only raw prediction: RankIC +0.0013、HAC5 t +0.09、hit 49.9%、Q monotonicity +0.50。正符号年2012/2014/2015/2016、負符号年2011/2013。2016はstub。
- BOX 100%・α=.25 vs B00: Net SR .806 vs .820（Δ−.0133）、年率Net差−0.079%、Gross差−0.076%、cost差+0.003%/年、turnover差+.00012/日。平均|weight差| .000056、weight変更銘柄日3.03%。
- duration分布: high-eventの99.97%がLmax=120。修正案はduration分散を下限側から上限側へ移すだけとなった。成立状態がほぼ一定なのでQ1–Q5は非識別、レポートでは欠測扱い。matched B対照も0行となり比較不能。
- 検証: corrected duration/width/close_position/CRは価格OHLC・AdjustmentFactor未来改変の3 cutoffでbitwise prefix-invariance PASS。補助特徴future-mutation prefix PASS。元の未変更列は保存済み全Train featuresの共通評価範囲で完全一致。B00 score bitwise一致。Ridge決定性、Train firewall、index alignment、全6会計照合PASS。Valid/raw_target未読。
- Decision: **No-Go。** √L定義を採用せず、BOX_RIDGE_001の1日O2O研究を終了する。閾値変更、duration別案B、interaction、Short policy、追加モデル試行はしない。Phase 2なし。
- Candidate adoption / Freeze: なし。Valid未閲覧。
- 成果物: [各段階・全6条件の結果](../../artifacts/DM-20260925-01/run-20260924T202625Z/metrics/ablation_summary.csv)、[全監査](../../artifacts/DM-20260925-01/run-20260924T202625Z/audit/summary.json)。
