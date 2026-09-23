"""Label-free inventory for PIT-safe financial-statement research."""
import argparse
import json
from pathlib import Path

import pandas as pd


CONCEPTS = {
    "operating_cash_flow": ["CashFlowsFromOperatingActivities"],
    "total_assets": ["TotalAssets"],
    "cash_equivalents": ["CashAndEquivalents"],
    "equity": ["Equity", "EquityToAssetRatio"],
    "liabilities": ["TotalLiabilities", "Liabilities"],
    "sales": ["NetSales", "Sales"],
    "operating_profit": ["OperatingProfit"],
    "ordinary_profit": ["OrdinaryProfit"],
    "net_income": ["Profit", "NetIncome"],
    "forecast_sales": ["ForecastNetSales", "ForecastSales"],
    "forecast_operating_profit": ["ForecastOperatingProfit"],
    "forecast_ordinary_profit": ["ForecastOrdinaryProfit"],
    "forecast_net_income": ["ForecastProfit", "ForecastNetIncome"],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    frame = pd.read_parquet(args.input)
    found = []
    for concept, names in CONCEPTS.items():
        actual = next((name for name in names if name in frame.columns), None)
        found.append({
            "concept": concept,
            "available": actual is not None,
            "column": actual,
            "non_null": int(frame[actual].notna().sum()) if actual else 0,
            "coverage": float(frame[actual].notna().mean()) if actual else 0.0,
        })
    output = {
        "source": str(args.input),
        "rows": int(len(frame)),
        "date_min": str(frame.index.get_level_values("Date").min()),
        "date_max": str(frame.index.get_level_values("Date").max()),
        "all_columns": list(frame.columns),
        "concept_inventory": found,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
