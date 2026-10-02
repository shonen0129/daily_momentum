import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from stock_comp_2026.strategies.dm_event_box import core
from stock_comp_2026.strategies.dm_eventbox_sn1 import features


def synthetic_inputs(rows=320):
    dates = pd.bdate_range("2010-01-04", periods=rows)
    close = 100.0 + 0.2 * np.sin(np.arange(rows) / 4.0)
    close[275:] += np.arange(rows - 275) * 0.8
    high = close + 0.8
    low = close - 0.8
    previous = np.r_[close[0], close[:-1]]
    raw_return = close / previous - 1.0
    index = pd.MultiIndex.from_arrays([dates, ["A"] * rows], names=["Date", "Code"])
    return {
        "raw_return_1day": pd.DataFrame({"Return": raw_return}, index=index),
        "beta_1day": pd.DataFrame({"Return": 1.0}, index=index),
        "topix_return_1day": pd.DataFrame({"Return": 0.0}, index=dates),
        "prices_daily_quotes": pd.DataFrame({
            "Open": close,
            "High": high,
            "Low": low,
            "Close": close,
            "AdjustmentFactor": 1.0,
        }, index=index),
    }


def manual_state():
    dates = pd.bdate_range("2020-01-06", periods=6)
    index = pd.MultiIndex.from_arrays([dates, ["A"] * len(dates)], names=["Date", "Code"])
    return pd.DataFrame({
        "state": [core.SEARCH, core.BOX, core.EXTEND, core.ANCHOR, core.BOX, core.BOX],
        "box_id": [-1, 0, -1, -1, 1, 1],
        "box_high": [np.nan, 10.0, np.nan, np.nan, 12.0, 12.0],
        "box_low": [np.nan, 9.0, np.nan, np.nan, 10.0, 10.0],
        "confirmed_at": [pd.NaT, dates[1], pd.NaT, pd.NaT, dates[4], dates[4]],
        "new_box": [False, True, False, False, True, False],
        "bo_signal": [0, 0, 1, 0, 0, 0],
        "bo_strength": [0.0, 0.0, 1.5, 0.0, 0.0, 0.0],
        "bo_exit": [False, False, False, False, True, False],
        "mr_signal": [0, 0, 0, 0, 0, 0],
        "close_position": [np.nan, 0.0, np.nan, np.nan, -0.5, -0.25],
    }, index=index)


def test_structure_direction_survives_new_box_and_builds_uptrend_pullback():
    state = manual_state()
    out = features._persistent_structure_features(state, pd.Series(1.0, index=state.index))
    assert out.iloc[2]["event_upstate"] == 1.0
    assert out.iloc[4]["event_upstate"] == 1.0
    assert out.iloc[4]["event_structure_age"] == 2.0
    assert out.iloc[4]["event_box_age"] == 0.0
    assert out.iloc[4]["event_box_width_atr"] == 2.0
    assert out.iloc[4]["pullback_up"] == 0.5
    assert out.iloc[5]["pullback_up"] == 0.25


def test_combined_builder_has_aligned_finite_state_outputs_and_is_deterministic():
    inputs = synthetic_inputs()
    first = features.build_features(inputs)
    second = features.build_features(inputs)
    assert first.index.equals(inputs["raw_return_1day"].index)
    assert first.index.is_unique
    assert np.isfinite(first[["event_upstate", "event_downstate",
                              "event_bo_up_strength", "event_bo_down_strength",
                              "event_breakout_failure"]].to_numpy()).all()
    assert_frame_equal(first, second, check_exact=True)
    assert list(first.attrs["event_a_columns"]) == list(features.EVENT_A_COLUMNS)
    assert list(first.attrs["event_b_columns"]) == list(features.EVENT_B_COLUMNS)


def test_full_builder_future_mutation_prefix_invariance_for_all_sources():
    inputs = synthetic_inputs()
    original = features.build_features(inputs)
    changed = {name: frame.copy(deep=True) for name, frame in inputs.items()}
    cutoff = pd.Timestamp("2010-11-29")
    stock_mask = changed["raw_return_1day"].index.get_level_values("Date") > cutoff
    changed["raw_return_1day"].loc[stock_mask, "Return"] *= -13.0
    changed["beta_1day"].loc[stock_mask, "Return"] += 27.0
    date_mask = changed["topix_return_1day"].index > cutoff
    changed["topix_return_1day"].loc[date_mask, "Return"] = 9.0
    quote_mask = changed["prices_daily_quotes"].index.get_level_values("Date") > cutoff
    for column in ("Open", "High", "Low", "Close"):
        changed["prices_daily_quotes"].loc[quote_mask, column] *= 3.0
    mutated = features.build_features(changed)
    prefix = original.index.get_level_values("Date") <= cutoff
    assert_frame_equal(original.loc[prefix], mutated.loc[prefix], check_exact=True)
