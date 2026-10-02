# DM-20261002-01 — PIT feasibility of major-customer momentum vs SN1_H1

## Decision

**Phase 0: external data permitted conditionally. Phase 1: `PIT INSUFFICIENT` for the source/data available in this audit. Stop before Phase 2.**

The current 2026 JP_Market_Vis snapshot cannot be applied to 2011-2016. It documents EDINET filings from 2025-06-14 through 2026-06-13, so none of its relationship evidence was public by a Train signal date. The audit found no local historical relationship archive or extraction from historical EDINET filings. We therefore have no measured historical supplier coverage, customer price coverage, relation-age distribution, update rate, or PIT endpoint map.

This is a feasibility stop on the available source package, not a finding that historical EDINET reconstruction is impossible and not a rejection of customer momentum. Official EDINET filing history may support a separately implemented audit; until actual records, mappings, and successor updates are processed, possible future coverage is not counted as coverage.

## Coverage audit

Coverage denominators were computed from the saved baseline prediction parquet by reading only `Date` and `Code`. There were 582,035 SN1_H1 scored stock-days on 1,287 signal dates during 2011-2016; 2016 is partial through March 31. Since all current JMV relation evidence is future-dated relative to those periods, its PIT-eligible edge, supplier, customer-price, and stock-day coverage are zero for each year.

| Year | Status | Signal dates | Baseline scored stock-days | Eligible current-snapshot edges | Supplier / stock-day coverage |
|---|---|---:|---:|---:|---:|
| 2011 | Complete | 245 | 107,526 | 0 | 0% / 0% |
| 2012 | Complete | 248 | 109,644 | 0 | 0% / 0% |
| 2013 | Complete | 245 | 110,241 | 0 | 0% / 0% |
| 2014 | Complete | 244 | 112,074 | 0 | 0% / 0% |
| 2015 | Complete | 244 | 113,758 | 0 | 0% / 0% |
| 2016 | Partial | 61 | 28,792 | 0 | 0% / 0% |

The zero does **not** mean that no real customer relationships existed in those years; it is the required exclusion when only 2025-2026 publication evidence is available. The JMV README's 2,191 major-customer and 656 listed-listed counts are reference counts for the current snapshot, not historical Train counts. See the full CSVs for explicit `NA` values where age, changes, or mapping ambiguity cannot be measured.

## Source/research summary

- `major_customer` is the only relation type retained in scope, directed from supplier to customer. JMV describes it as principally a customer at or above 10% of consolidated sales.
- JMV exposes a useful evidence schema (`as_of`, `published`, `retrieved`, `doc_id`, source/type and direction provenance), but `as_of` is the fiscal reference date while `published` is the filing/publication date. Only publication controls signal availability.
- JMV's README says its 2026 snapshot covers 2025-2026 EDINET submissions and reports only one historical edge across all relation types. That does not establish annual major-customer history for Train. The current M4 company-code mapping is also a current snapshot and cannot by itself prove 2011-2016 PIT mapping.
- The Doshisha Tanaka/Tsuda paper and Customer Momentum literature support the customer-to-supplier economic direction. Their public evidence does not substitute for the relation-vintage, publication timestamp, and Train code-mapping audits required here. No CII/LiNGAM or non-equal weight is adopted.
- A Japanese firm-network study reports 92% annual customer-link and 93% supplier-link survival in 2008-2012; another 2007-2016 panel finds link survival rising with tenure. This supports carrying a dated edge forward for one annual cycle, refreshed by a complete successor filing. It does not establish persistence for the narrower major-customer disclosure category and cannot backdate the 2025-2026 snapshot. See [PLOS ONE](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0100712) and [RIETI DP 17-E-110](https://www.rieti.go.jp/jp/publications/dp/17e110.pdf).
- Competition materials allow external public data, but require PIT handling and static files in the submission bundle because evaluation has no network. EDINET source terms require attribution and API-based machine acquisition. The aggregate JMV bundle's upstream redistribution conditions were not cleared here.

## Research outputs

- [Competition external-data audit](competition_external_data_audit.md)
- [Network source review](network_source_review.md)
- [Proposed PIT relation contract](pit_relation_contract.md)
- [Yearly PIT coverage](pit_network_coverage.csv)
- [Relation age/update audit](relation_age_by_year.csv)
- [Code-mapping audit](code_mapping_audit.csv)
- [Prefix-invariance status](network_prefix_invariance.json)
- [Audit/input manifest](audit_manifest.json)

NCMOM20 descriptive tests and Phase 3 candidate outputs were not produced because Phase 1 did not pass. Relationship mutation, return mutation, feature prefix-invariance, train firewall runtime, and determinism were not run because no historical edge table or builder was constructed; the JSON audit records each status. No target values, Valid files/targets, or raw-target files were read. No changes were made to SN1_H1, its cost/quintile contract, or submission package. This Train history is known development evidence, not independent OOS.

The yearly denominator is reproducible from the saved baseline artifact listed in [audit_manifest.json](audit_manifest.json): read only the `Date` and `Code` Parquet index fields, group `Date` by calendar year, count rows as scored stock-days, and count unique dates. The relation exclusion is based on the published snapshot filing-date window; no edge-level relation file was locally read.

## Baseline

The fixed SN1_H1 request reference values remain: Gross Sharpe 1.122, Net Sharpe 1.077, annual gross +4.774%, annual net +4.584%, Mean RankIC 0.01251, turnover/day 0.00762. No candidate comparison or incremental claim was calculated.
