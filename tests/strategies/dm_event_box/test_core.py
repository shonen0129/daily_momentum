import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from research.experiments.event_box import active_event_account
from stock_comp_2026.strategies.dm_event_box import core, features


def lifecycle_bars(index=None):
    if index is None:
        index = pd.date_range("2020-01-01", periods=26, freq="B", name="Date")
    high = np.full(26, 10.5)
    low = np.full(26, 9.5)
    close = np.full(26, 10.0)
    high[20], low[20], close[20] = 10.5, 9.5, 10.5
    high[21], low[21], close[21] = 12.0, 10.5, 11.8
    high[22], low[22], close[22] = 12.5, 11.5, 12.2
    high[23], low[23], close[23] = 12.5, 10.9, 11.2
    high[24], low[24], close[24] = 11.8, 11.0, 11.5
    high[25], low[25], close[25] = 12.0, 11.2, 11.9
    return pd.DataFrame({"Open": close, "High": high, "Low": low,
                         "Close": close, "atr_prior": np.ones(26)}, index=index)


def test_state_machine_confirms_boxes_only_as_of_confirmation_and_tracks_lifecycle():
    bars = lifecycle_bars()
    out = core.run_state_machine(bars)
    assert out.loc[bars.index[:20], "state"].eq(core.SEARCH).all()
    assert out.loc[bars.index[20], "state"] == core.BOX
    assert out.loc[bars.index[20], "confirmed_at"] == bars.index[20]
    assert out.loc[bars.index[21], "bo_signal"] == 1
    assert out.loc[bars.index[21], "state"] == core.EXTEND
    assert out.loc[bars.index[23], "state"] == core.ANCHOR
    assert out.loc[bars.index[25], "new_box"]
    assert out.loc[bars.index[25], "state"] == core.BOX
    assert out.loc[bars.index[25], "confirmed_at"] == bars.index[25]
    assert (out.loc[bars.index[:25], "confirmed_at"].dropna() <= bars.index[24]).all()


def test_future_mutation_does_not_change_any_prefix_features():
    bars = lifecycle_bars()
    original = core.run_state_machine(bars)
    changed = bars.copy()
    changed.loc[bars.index[24]:, "High"] += 2.0
    changed.loc[bars.index[24]:, "Open"] += 0.1
    changed.loc[bars.index[24]:, "Close"] += 0.1
    changed.loc[bars.index[24]:, "Low"] += 0.1
    mutated = core.run_state_machine(changed)
    assert_frame_equal(original.iloc[:24], mutated.iloc[:24], check_exact=True)


def test_panel_builder_preserves_full_index_and_is_deterministic():
    dates = pd.date_range("2020-01-01", periods=26, freq="B")
    panels = []
    for code in ("A", "B"):
        bars = lifecycle_bars(dates)
        frame = bars[["Open", "High", "Low", "Close"]].copy()
        frame["AdjustmentFactor"] = 1.0
        frame.index = pd.MultiIndex.from_arrays([dates, [code] * len(dates)], names=["Date", "Code"])
        panels.append(frame)
    quotes = pd.concat(panels).sort_index()
    index = quotes.index
    inputs = {
        "raw_return_1day": pd.DataFrame({"Return": 0.0}, index=index),
        "prices_daily_quotes": quotes,
    }
    first = features.build_features(inputs)
    second = features.build_features(inputs)
    assert first.index.equals(index)
    assert first["mr_signal"].notna().all()
    assert_frame_equal(first, second, check_exact=True)
    score = features.signal_from_features(first)
    assert score.index.equals(index)
    assert np.isfinite(score.to_numpy()).all()


def test_split_safe_ohlc_uses_raw_levels_in_a_common_share_unit():
    dates = pd.date_range("2020-01-01", periods=2, freq="B")
    index = pd.MultiIndex.from_arrays([dates, ["A", "A"]], names=["Date", "Code"])
    inputs = {
        "raw_return_1day": pd.DataFrame({"Return": [0.0, 0.0]}, index=index),
        "prices_daily_quotes": pd.DataFrame({
            "Open": [100.0, 50.0], "High": [105.0, 52.5], "Low": [95.0, 47.5],
            "Close": [100.0, 50.0], "AdjustmentFactor": [1.0, 0.5],
        }, index=index),
    }
    out = features.split_safe_ohlc(inputs)
    assert out.loc[index[0], "Close"] == out.loc[index[1], "Close"]
    assert out.loc[index[1], "Open"] == 100.0


def test_missing_ohlc_resets_state_without_imputation_and_keeps_coverage():
    index = pd.date_range("2020-01-01", periods=24, freq="B", name="Date")
    bars = pd.DataFrame({"Open": 10.0, "High": 10.5, "Low": 9.5, "Close": 10.0}, index=index)
    bars.loc[bars.index[22], ["Open", "High", "Low", "Close"]] = np.nan
    out = features._with_missing_bar_resets(bars)
    assert out.index.equals(bars.index)
    assert out.loc[bars.index[21], "state"] == core.BOX
    assert out.loc[bars.index[22], "state"] == core.SEARCH
    assert out.loc[bars.index[22], "mr_signal"] == 0
    assert out.loc[bars.index[23], "state"] == core.SEARCH
    assert np.isfinite(out["mr_signal"].to_numpy()).all()


def test_only_one_mr_entry_per_box_side():
    bars = lifecycle_bars()
    bars.loc[bars.index[21], ["High", "Low", "Close", "Open"]] = [10.5, 9.5, 10.4, 10.4]
    out = core.run_state_machine(bars)
    assert out.loc[bars.index[20], "mr_signal"] == -1
    assert out.loc[bars.index[21], "mr_signal"] == 0


def test_driftless_random_walk_tp_rate_matches_first_passage_null():
    rng = np.random.default_rng(20260930)
    n_paths = 30000
    position = np.full(n_paths, -0.8)
    active = np.ones(n_paths, dtype=bool)
    took_profit = np.zeros(n_paths, dtype=bool)
    stopped = np.zeros(n_paths, dtype=bool)
    for _ in range(250):
        position[active] += rng.normal(0.0, 0.1, size=active.sum())
        tp = active & (position >= 0.0)
        sl = active & (position <= -1.2)
        took_profit[tp] = True
        stopped[sl] = True
        active[tp | sl] = False
        if not active.any():
            break
    empirical = took_profit.sum() / (took_profit.sum() + stopped.sum())
    analytic = (-0.8 - (-1.2)) / (0.0 - (-1.2))
    assert abs(empirical - analytic) < 0.02


def test_active_event_account_matches_required_metric_contract():
    dates = pd.date_range("2020-01-01", periods=3, freq="B", name="Date")
    index = pd.MultiIndex.from_product([dates, list("ABCDE")], names=["Date", "Code"])
    signal = pd.Series(np.tile([1.0, 0.8, -0.9, -1.0, np.nan], 3), index=index)
    target = pd.Series(np.tile([0.02, 0.01, -0.01, -0.02, 0.0], 3), index=index)
    _, daily = active_event_account(signal, target)
    metrics = __import__("research.evaluation", fromlist=["metrics"]).metrics(daily)
    assert set(("gross_sharpe", "net_sharpe", "annual_gross", "annual_net", "annual_cost",
                "turnover", "rankic", "rankic_t_hac5", "rankic_hit", "q1_daily_return",
                "q5_daily_return", "q_monotonicity", "annual_long", "annual_short",
                "max_drawdown_additive", "label_coverage")).issubset(metrics)
