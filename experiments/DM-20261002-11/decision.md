# DM-20261002-11 decision

**IND17_MOM_WITHIN_REV20: REJECT**。Exactly1 new fixed granularity trial completed; no rescue/Valid/Freeze/submission. Parent10 unchanged.

Failed checks: gross_positive_3of5, turnover_le008, pooled_netSR_beats_MOM60, ex2016_netSR_beats_MOM60, netSR_improvements_4of5, bootstrap_lower_positive, annual_net_beats_MOM60, turnover_le125_MOM60, short_net_ge_MOM60.

NetSR17/33/MOM60 -0.560651/-0.539263/0.308092; raw coverage17/33 98.468%/94.214%; turnover17/33 0.127287/0.122539.

[Report](../../reports/DM-20261002-11/REPORT.md). Run `artifacts/DM-20261002-11/run-20261002T094523Z`. Known Train development evidence, not independent OOS.

粒度robustness結論: coverage+4.254ppは改善、turnover+0.004748/日で悪化。Industry continuationの正ICは維持するが低下、Within raw ICは改善せず。Shortnetは33比+0.151pp改善するがLongnet−0.170pp、NetSR差−0.021388/95%CI[−0.416967,+0.368628]で増分不支持。MOM60にも届かずREJECT。設定変更・追加trialなし。

284tests/新規24、18prefix、公式会計/adapter/parentcontrol parity、親76hash、Freeze129hash PASS。make checkは既存04metadataのみ停止。初回NaN storage bit照合失敗は0trial、科学run61.17秒/1.96GiB、smoke2.31秒/1.04GiB。
