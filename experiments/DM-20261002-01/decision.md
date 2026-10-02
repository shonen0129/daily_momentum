# DM-20261002-01 decision

**Phase 1 result: `PIT INSUFFICIENT` for the source package available in this audit.** Stop before Phase 2. NCMOM20 diagnostics, network feature construction, Ridge candidate fitting, portfolio evaluation, and Valid evaluation were not performed.

## Evidence

- Competition materials permit external data conditionally: public availability must be timestamped, required static files must be included with the strategy, and evaluation-time network access is unavailable. CPU fallback and a 30-minute grading limit apply. The reviewed material states no explicit maximum zip size.
- JP_Market_Vis identifies its 2026-09 snapshot and says its EDINET filings cover submissions from 2025-06-14 through 2026-06-13. Its current `major_customer`/主要販売先 definition is supplier-to-customer, principally a customer exceeding 10% of consolidated sales. These publication dates post-date all SN1 Train evaluation years; the current snapshot therefore contributes zero eligible Train edges under the frozen availability rule.
- The published README reports 2,191 major-customer relations and 656 listed-to-listed relations as reference counts, while warning the type counts may be stale. Its overall snapshot has one historical relation across all types; that is not evidence of annual major-customer history for 2011-2016.
- The workspace contains no JP_Market_Vis relation snapshot or historical EDINET relation archive; `EDINET_API_KEY` is not configured. The official EDINET service exposes public filings under PDL 1.0 and documents API access, so an independent historical reconstruction may be possible in a separate audit, but it was not retrieved, mapped, or validated here. Possibility is not counted as coverage.
- Current EDINET/source evidence records both fiscal reference date and publication date; the latter is the only acceptable start for signal availability. The current source schema does not supply enough verified Train-era successor disclosures, endpoint mappings, or edge ages for this audit to certify persistence or termination.
- Coverage denominators came only from the saved SN1_H1 Train prediction index, reading `Date` and `Code`; 582,035 scored stock-days across 1,287 dates in 2011-2016. Applying the current snapshot by publication time yields zero covered suppliers/stock-days in every year. This is a source-date exclusion, not a statement that no historical business relationships existed.

## Decision and scope limits

This is not a rejection of Customer Momentum or a claim that historical EDINET extraction is impossible. It says the strict Phase 1 gate is not established by the current snapshot and local materials. A separate, auditable retrieval of the 2011-2016 supplier filings, the corresponding subsequent disclosures, PIT endpoint mapping, and customer price coverage is required before any NCMOM analysis can start.

No entry was added to `experiments/GRAVEYARD.md`: no predictive candidate was evaluated or rejected. `SN1_H1` and all competition/portfolio contracts remain unchanged. Valid files and targets were not read; raw-target files were not read. Train is known development history, not independent OOS.
