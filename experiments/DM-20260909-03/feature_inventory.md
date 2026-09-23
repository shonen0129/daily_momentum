# Financial feature inventory — DM-20260909-03

Source: `fins_statements_train.parquet`, label-free audit on 2026-09-09. 15,926 disclosure rows,
2008-11-04 through 2016-03-31. Coverage is disclosure-row non-null coverage, not daily as-of coverage.

| Concept | Actual Train column | Disclosure-row coverage | Use |
|---|---|---:|---|
| Operating cash flow | `CashFlowsFromOperatingActivities` | 45.0% | C0 retained |
| Total assets | `TotalAssets` | 72.8% | denominator |
| Cash equivalents | `CashAndEquivalents` | 45.0% | C0, C2 |
| Equity | `Equity` | 72.8% | C0 proxy, C2 |
| Net sales | `NetSales` | 72.8% | audited only |
| Operating profit | `OperatingProfit` | 69.3% | C1 |
| Ordinary profit | `OrdinaryProfit` | 67.0% | C1 |
| Net income | `Profit` | 72.4% | C1 |
| Liabilities | — | 0.0% | unavailable; excluded |
| Forecast fields | `Forecast*` | 62.6–67.1% | audited only; excluded |

Full schema and counts were produced by `research/experiments/audit_fundamental_inventory.py` without
opening a target or Valid file. No assumed `Liabilities` column is used.
