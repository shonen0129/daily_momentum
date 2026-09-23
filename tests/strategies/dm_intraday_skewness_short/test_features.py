"""Causal invariants specific to the I1/K1 feature builders."""
import ast
from pathlib import Path

import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_intraday_skewness_short import features


def test_intraday_uses_current_raw_open_close_and_neutralizes_invalid_quotes():
    dates = pd.bdate_range("2020-01-01", periods=60)
    index = pd.MultiIndex.from_product([dates, ["a", "b"]], names=["Date", "Code"])
    prices = pd.DataFrame({"Open": 10.0, "Close": 11.0}, index=index)
    prices.loc[(dates[-1], "b"), "Open"] = 0.0
    result = features.intraday_features({"prices_daily_quotes": prices})
    np.testing.assert_allclose(result.loc[(dates[-1], "a"), "daymom60"], 6.0)
    assert np.isnan(result.loc[(dates[-1], "b"), "intraday_return"])
    assert result.loc[(dates[-1], "b"), "intraday_short_risk"] == 0.0


def test_monthly_skewness_requires_fifteen_observations_and_uses_m12_to_m2():
    dates = pd.bdate_range("2019-01-01", "2020-04-30")
    index = pd.MultiIndex.from_product([dates, ["a"]], names=["Date", "Code"])
    values = pd.Series(np.linspace(-.02, .03, len(index)), index=index)
    values.loc[(values.index.get_level_values("Date").to_period("M") == pd.Period("2019-02", "M"))] = np.nan
    monthly = features._monthly_statistics(values)
    assert monthly.observations.min() < 15
    assert monthly.loc[monthly.observations < 15, "realized_skewness"].isna().all()
    valid = monthly.loc[monthly.month == pd.Period("2020-03", "M"), "mom12_1"]
    assert valid.notna().all()


def test_expected_skewness_forecast_is_next_month_only():
    months = pd.period_range("2018-01", periods=16, freq="M")
    dates = []
    for month in months:
        dates.extend(pd.bdate_range(month.start_time, periods=16))
    index = pd.MultiIndex.from_product([dates, ["a", "b", "c", "d", "e", "f"]], names=["Date", "Code"])
    rng = np.random.default_rng(4)
    residual = pd.Series(rng.normal(0, .02, len(index)), index=index)
    forecast, _, coeffs = features.expected_skewness(residual)
    assert (forecast.forecast_month > forecast.estimation_month).all()
    assert (forecast.characteristic_max_date < forecast.forecast_month.dt.start_time).all()
    assert not coeffs.empty


def test_stitching_keeps_long_book_identical_and_is_deterministic():
    index = pd.MultiIndex.from_product([[pd.Timestamp("2020-01-02")], list("abcdefghij")], names=["Date", "Code"])
    day = pd.DataFrame({"L": np.arange(10), "intraday_short_risk": [.5] * 10,
                        "k1_short_risk": np.linspace(0, 1, 10)}, index=index)
    first = features._stitch_day(day, "intraday_short_risk")
    second = features._stitch_day(day, "intraday_short_risk")
    pd.testing.assert_series_equal(first, second, check_exact=True)
    assert (first.loc[first.index.get_level_values("Code").isin(["g", "h", "i", "j"])] > .5).all()


def test_static_source_firewall_contract():
    forbidden = ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose", "AdjustmentVolume",
                 "raw_target", "target_1day_valid"]
    for path in Path(features.__file__).parent.glob("*.py"):
        text = path.read_text()
        for token in forbidden:
            assert token not in text, (path, token)
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in ("bfill", "backfill")
                if node.func.attr == "shift":
                    value = node.args[0] if node.args else next(k.value for k in node.keywords if k.arg == "periods")
                    assert isinstance(value, ast.Constant) and value.value >= 0
                assert not any(k.arg == "center" and isinstance(k.value, ast.Constant) and k.value.value for k in node.keywords)
                assert not any(k.arg == "direction" and isinstance(k.value, ast.Constant) and k.value.value == "forward" for k in node.keywords)
