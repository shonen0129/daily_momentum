# DM-20261002-10 decision

Exactly3 fixed trials completed, known Train only.

- **STOCK_REV20**: REJECT. Failed checks: pooled_rankic_positive, pooled_gross_positive, ex2016_gross_positive, gross_positive_3of5, turnover_le008.
- **WITHIN33_REV20**: REJECT. Failed checks: pooled_rankic_positive, pooled_gross_positive, ex2016_gross_positive, gross_positive_3of5, raw_coverage_ge95pct, turnover_le008.
- **IND33_MOM_WITHIN_REV20**: REJECT. Failed checks: raw_coverage_ge95pct, turnover_le008, pooled_netSR_beats_MOM60, ex2016_netSR_beats_MOM60, netSR_improvements_4of5, bootstrap_lower_positive, annual_net_beats_MOM60, turnover_le125_MOM60, short_net_ge_MOM60.

[Report](../../reports/DM-20261002-10/REPORT.md). Run `artifacts/DM-20261002-10/run-20261002T091211Z`. No rescue, extra trial, Valid, Freeze or submission. Prior06–09 decisions unchanged. Components have no standalone adoption criterion; passing combined means next-stage eligibility only.

主要理由: Combined Gross/Net SR0.6592/-0.5393対MOM600.6134/0.3081。raw coverage94.214%、turnover0.12254/日、full-year NetSR改善2/5、paired ΔNetSR95%CI[−2.171,+0.385]でREJECT。20観測Stock/Within reversalはpooled/ex2016Gross負。Industry continuationの記述的関連はあるが、中心符号構造の安定したNet alphaは支持しない。Short改善はMOM60に届かない。追加試行なし。

260tests・新規25・全Train入力18prefix/truncation・公式会計/control/adapter/finite/purge/priorhash PASS、Freeze129hash PASS。make checkは既存04metadataのみ停止。科学run80.45秒/1.77GiB、独立smoke2.75秒/1.08GiB。
