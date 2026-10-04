# DM-20261002-08 decision

Exactly2 fixed Train-only trials, previous REJECT evidence unchanged.

- **SECTOR_CONFIRM**: REJECT. Failed checks: raw_context_coverage_ge95pct, NetSR_improvement_4of5, bootstrap_lower_gt0.
- **SHORT_DISAGREE_VETO**: REJECT. Failed checks: raw_context_coverage_ge95pct, NetSR_improvement_4of5.

No rescue, extra trial, Valid, Freeze or submission. Known Train evidence, not independent OOS. [Report](../../reports/DM-20261002-08/REPORT.md). Run `artifacts/DM-20261002-08/run-20261002T070900Z`.

主評価Net SR: MOM60 0.3243 / SECTOR_CONFIRM 0.4148 / SHORT_DISAGREE_VETO 0.4346。Hard改善2/5、Veto3/5、raw coverage pooled93.890%/primary93.944%で両方REJECT。Veto pooled bootstrap95%[+0.0034,+0.2895]でも、primary95%[−0.0302,+0.2550]は0を跨ぐ。Veto ΔShortnet+0.4622pp=Δgross+0.4798pp−cost増0.0177pp、gross寄与103.8%。Added Short自体は年率−0.1587pp;旧損失回避+0.3845ppとunchanged weight差+0.2540ppが改善を作る。Transform order差があるためcontext単独効果とは呼ばない。

223 tests、18 full-input prefixケース、control/common/adapter/公式会計/coverage/決定性、Freeze129hash PASS。make checkは既存DM-20261002-04 metadataのみ停止。科学runは最終parquet複製のfirewall allowlist漏れでfailedとして保持し、report-only run `run-20261002T071247Z`で保存成果物から復旧（新performance trial0、累積2）。No rescue/Valid/Freeze。
