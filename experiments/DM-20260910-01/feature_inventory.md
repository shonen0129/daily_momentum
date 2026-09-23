# Feature inventory — DM-20260910-01

Trainのラベル非参照監査。根拠となる機械可読な生データは `financial_inventory_raw.json`、`listed_info_inventory_raw.json`、`prices_inventory_raw.json` に保存する。

| Concept | Actual Train column / source | Availability | Decision |
|---|---|---:|---|
| Raw price | `prices_daily_quotes_train.parquet: Close` | 809,636 rows | V1の時価総額分子にraw Closeのみを使う |
| Issued shares | `fins_statements_train.parquet: NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock` | 開示日付き | V1で開示後・450日以内のみ使う |
| Operating cash flow | `CashFlowsFromOperatingActivities` | 7,165 / 15,926 disclosures (45.0%) | V1/V2に利用 |
| Net income | `Profit` | 11,531 / 15,926 disclosures (72.4%) | V2に利用 |
| Total assets | `TotalAssets` | 11,592 / 15,926 disclosures (72.8%) | V2の分母 |
| Residual inputs | `raw_return_1day`, `beta_1day`, `topix_return_1day` | 日次Train | V3 MAX20に利用 |
| Liabilities | 不在 | 0% | 使用しない |

`listed_info_train` に市場価値・株式数列はなく、発行済株式数は財務開示のPIT状態としてのみ使用した。すべての候補で開示日当日は使わず、次の利用可能な営業日からbackward as-ofで反映する。V1/V2の2011–2014日次利用率は約97.5–98.6%、V3は約98.8–99.3%である（詳細は `reports/DM-20260910-01/feature_coverage.csv`）。
