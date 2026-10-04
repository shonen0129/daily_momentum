# DM-20261002-06 decision

Three fixed trials completed, known Train only.

- **SECTOR17_MOM**: REJECT. Failed checks: turnover_le_MOM60, short_gross_positive, short_gross_ge_MOM60, short_net_ge_MOM60, pooled_netSR_positive, ex2016_netSR_positive, pooled_netSR_beats_MOM60, netSR_improvement_4of5, bootstrap_lower_positive.
- **SECTOR33_MOM**: REJECT. Failed checks: raw_finite_coverage_95pct, turnover_le_MOM60, short_gross_positive, short_net_ge_MOM60, pooled_netSR_positive, ex2016_netSR_positive, pooled_netSR_beats_MOM60, netSR_improvement_4of5, bootstrap_lower_positive.
- **RELATIVE33_MOM**: REJECT. Failed checks: raw_finite_coverage_95pct, turnover_le_MOM60, short_gross_positive, short_gross_ge_MOM60, short_net_ge_MOM60, pooled_netSR_positive, ex2016_netSR_positive, pooled_netSR_beats_MOM60, netSR_improvement_4of5, bootstrap_lower_positive.

No additional trials, combination, Freeze, Valid or external submission. [Report](../../reports/DM-20261002-06/REPORT.md). [Gates](../../reports/DM-20261002-06/metrics/candidate_decision.json). Run `artifacts/DM-20261002-06/run-20261002T053435Z`.

主要理由: 3候補ともturnover<=MOM60不通過、Net SR負、bootstrap ΔNet SR区間全体が負。33系はraw finite coverage95%も不通過。Sector33 Short gross損失は縮小したがShort netは悪化。D<Cのtarget差は記述的に存在しても、D Short contributionも負。組合せの次実験条件を通過した候補はない。No rescue/追加trial。

検証:199 tests/新規12、全入力18 prefixケース、公式会計、coverage/決定性/adapter parity、Freeze129hash PASS。make checkは既存DM-20261002-04 metadata kindで停止。約43.1秒・peakRSS1.60GiB、Train809,636行100%adapter出力。
