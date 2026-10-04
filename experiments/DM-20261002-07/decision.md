# DM-20261002-07 decision

Known Train, exactly3 fixed trials; previous experiment remains rejected.

- **HIER33_SECTOR**: DESCRIPTIVE_COMPONENT_ONLY. Failed checks: none.
- **HIER33_WITHIN**: REJECT. Failed checks: raw_coverage_ge95pct.
- **HIER33_COMBINED**: REJECT. Failed checks: raw_coverage_ge95pct, NetSR_improvement_4of5, bootstrap_lower_gt0.

No additional candidate, parameter/weight/alpha search, filtering, sector exclusion, Freeze, Valid or submission. [Report](../../reports/DM-20261002-07/REPORT.md). [Gates](../../reports/DM-20261002-07/metrics/candidate_decision.json). Run `artifacts/DM-20261002-07/run-20261002T062103Z`.

採用・次段階候補なし。SECTORは事前feasibilityだけ通過した記述的componentで、単独adoption経路はない。WITHINはraw coverage93.890%でREJECT。COMBINEDはNet SR0.3783対MOM60 0.3081、Short gross/net改善だが、coverage93.890%、full-year改善3/5、paired ΔNet SR95%CI[−0.1203,+0.2436]のためREJECT。重み/alpha/filter/sector除外を追加しない。

212 tests・新規13・全入力18 prefixケース・primitive/control/adapter/公式会計・Freeze129hash PASS。make checkは既存DM-20261002-04 metadataで停止。Raw identityは浮動精度内、smoothed identityは独立neutral化により全域成立せず、EWMA defectで差を説明済み。Run約123秒/peakRSS1.47GiB、独立Train smoke2.226秒/1.04GiB。
