import numpy as np
import pandas as pd

from research.experiments.sn1_horizon import account_period_metrics, forward_window, maturity_mask, side_account


def _panel(days=50):
    dates = pd.bdate_range("2020-01-01", periods=days)
    index = pd.MultiIndex.from_product([dates, ["0001"]], names=["Date", "Code"])
    residual = pd.Series(0.01, index=index, name="residual")
    return dates, index, residual


def test_horizon_window_starts_at_second_future_return_row_and_compounds():
    dates, index, residual = _panel()
    for horizon in (1, 5, 20):
        target = forward_window(residual, horizon, first_offset=2)
        expected = (1.01 ** horizon) - 1.0
        assert np.isclose(target.loc[(dates[0], "0001")], expected)
        last_valid_position = len(dates) - horizon - 2
        assert np.isfinite(target.loc[(dates[last_valid_position], "0001")])
        assert np.isnan(target.loc[(dates[last_valid_position + 1], "0001")])


def test_future_offset_uses_global_trading_date_when_stock_row_is_missing():
    dates = pd.bdate_range("2021-01-04", periods=8)
    index = pd.MultiIndex.from_product([dates, ["0001", "0002"]], names=["Date", "Code"])
    index = index.drop((dates[1], "0001"))
    residual = pd.Series(0.01, index=index)
    target = forward_window(residual, 1, first_offset=2)
    # Signal date 0 reads the date-2 return row for code 0001, despite its absent date-1 row.
    assert np.isclose(target.loc[(dates[0], "0001")], 0.01)


def test_horizon_purge_requires_label_maturity_before_fold_start():
    dates, index, _ = _panel()
    for horizon, expected_last_signal_position in ((1, 7), (5, 3), (20, 2)):
        fold_position = 10 if horizon < 20 else 24
        mature, _ = maturity_mask(dates, index, dates[fold_position], horizon)
        selected = np.flatnonzero(mature)
        assert selected[-1] == expected_last_signal_position
        assert selected[-1] + horizon + 1 < fold_position


def test_maturity_purge_matches_existing_h1_two_position_cut():
    dates, index, _ = _panel()
    mature, _ = maturity_mask(dates, index, dates[20], 1)
    old_rule = index.get_level_values("Date").isin(dates[:18])
    assert np.array_equal(mature, old_rule)


def test_daily_side_account_reconciles_to_official_net_account():
    dates = pd.bdate_range("2022-01-03", periods=30)
    codes = [f"{i:04d}" for i in range(40)]
    index = pd.MultiIndex.from_product([dates, codes], names=["Date", "Code"])
    signal = pd.Series(np.tile(np.linspace(-1, 1, len(codes)), len(dates)), index=index)
    target = pd.Series(np.sin(np.arange(len(index)) / 13.0) * 0.02, index=index)
    daily, _, _ = side_account(signal, target)
    assert np.allclose(daily.long_gross + daily.short_gross, daily.gross)
    assert np.allclose(daily.long_net + daily.short_net, daily.net)
    assert daily.net_all_cost.notna().all()
    assert account_period_metrics(daily, "train")
