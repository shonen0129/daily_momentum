"""Regression tests for the DM-20260910-01 causal feature implementation."""
import ast
from pathlib import Path

import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_independent_short import features


def test_missing_values_are_daily_neutral():
    index = pd.MultiIndex.from_tuples(
        [(pd.Timestamp("2020-01-02"), "a"), (pd.Timestamp("2020-01-02"), "b"),
         (pd.Timestamp("2020-01-03"), "a"), (pd.Timestamp("2020-01-03"), "b")], names=["Date", "Code"])
    result = features.neutral_percentile(pd.Series([1.0, np.nan, 2.0, 4.0], index=index))
    assert result.loc[(pd.Timestamp("2020-01-02"), "b")] == .5
    assert result.loc[(pd.Timestamp("2020-01-03"), "a")] == .5
    assert result.loc[(pd.Timestamp("2020-01-03"), "b")] == 1.0


def test_raw_close_and_disclosed_shares_define_cfo_yield():
    index = pd.MultiIndex.from_product([[pd.Timestamp("2010-02-01"), pd.Timestamp("2010-02-02"),
                                          pd.Timestamp("2010-02-03")], ["a"]], names=["Date", "Code"])
    row = pd.DataFrame([{
        "Date": pd.Timestamp("2010-02-01"), "Code": "a", "DisclosureNumber": 1,
        "TypeOfDocument": "FYFinancialStatements_Consolidated_JP", "TypeOfCurrentPeriod": "FY",
        "CurrentPeriodStartDate": "2009-01-01", "CurrentPeriodEndDate": "2009-12-31",
        "CashFlowsFromOperatingActivities": 100.0, "Profit": 120.0, "TotalAssets": 1000.0,
        "NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock": 10.0,
    }]).set_index(["Date", "Code"])
    state = features.financial_state(index, row)
    close = pd.Series([10.0, 10.0, 10.0], index=index)
    value = state.annual_cfo / (close * state.shares)
    assert pd.isna(value.iloc[0])
    np.testing.assert_allclose(value.iloc[1:], [100.0 * 365.0 / 364.0 / 100.0] * 2)
    np.testing.assert_allclose(state.accrual.iloc[1:], [.02, .02])


def test_source_firewall_static_contract():
    folder = Path(features.__file__).parent
    forbidden = ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose", "AdjustmentVolume",
                 "raw_target", "target_1day_valid"]
    for path in folder.glob("*.py"):
        text = path.read_text()
        for token in forbidden: assert token not in text, (path, token)
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in ("bfill", "backfill")
                if node.func.attr == "shift":
                    argument = node.args[0] if node.args else next(k.value for k in node.keywords if k.arg == "periods")
                    assert isinstance(argument, ast.Constant) and isinstance(argument.value, int) and argument.value >= 0
                assert not any(k.arg == "center" and isinstance(k.value, ast.Constant) and k.value.value for k in node.keywords)
                assert not any(k.arg == "direction" and isinstance(k.value, ast.Constant) and k.value.value == "forward" for k in node.keywords)


def test_stitching_is_deterministic_when_risks_tie():
    index = pd.MultiIndex.from_product([[pd.Timestamp("2020-01-02")], list("abcde")], names=["Date", "Code"])
    day = pd.DataFrame({"L": [.1, .2, .3, .4, .5], "v1_risk": [.5] * 5}, index=index)
    first = features._stitch_day(day, "v1_risk")
    second = features._stitch_day(day, "v1_risk")
    pd.testing.assert_series_equal(first, second, check_exact=True)
    assert first.loc[(pd.Timestamp("2020-01-02"), "e")] > .6
