import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype

from stock_comp_2026.strategies.dm_eventbox_sn1 import features, models


def training_panel():
    dates = pd.bdate_range("2010-01-04", periods=300, name="Date")
    codes = [f"{i:05d}" for i in range(10000, 10010)]
    index = pd.MultiIndex.from_product([dates, codes], names=["Date", "Code"])
    row = np.arange(len(index), dtype=float)
    code = index.get_level_values("Code").astype(int).to_numpy() - 10000
    frame = pd.DataFrame(index=index)
    frame["box_duration"] = 20.0 + row % 11
    frame["box_width_atr"] = 1.0 + row % 7 / 10.0
    frame["close_position"] = 0.2 + row % 6 / 10.0
    frame["relative_strength_60"] = np.sin(row / 29.0)
    frame["distance_to_prior_high"] = -0.02 + row % 5 / 1000.0
    frame["distance_to_prior_low"] = -0.03 + (row + 1.0) % 5 / 1000.0
    frame["new_high_excess"] = np.where(code < 5, 0.01 + row % 5 / 1000.0, 0.0)
    frame["new_low_excess"] = np.where(code >= 5, 0.01 + row % 5 / 1000.0, 0.0)
    frame["high_available"] = True
    frame["low_available"] = True
    frame["event_upstate"] = (row % 13 < 4).astype(float)
    frame["event_downstate"] = (row % 17 < 3).astype(float)
    frame["event_bo_up_strength"] = row % 9 / 10.0
    frame["event_bo_down_strength"] = row % 7 / 10.0
    frame["event_box_width_atr"] = 0.5 + row % 5 / 10.0
    frame["event_box_age"] = row % 23
    frame["event_structure_age"] = row % 47
    frame["event_breakout_age"] = row % 19
    frame["event_breakout_failure"] = (row % 101 == 0).astype(float)
    frame["event_box_position"] = (row % 21) / 10.0 - 1.0
    frame["pullback_up"] = frame["event_upstate"] * (-frame["event_box_position"]).clip(lower=0.0)
    target = pd.Series(np.cos(row / 31.0) * 0.02 + code * 0.0001, index=index, name="Return")
    return frame, target, dates


def test_candidate_models_purge_unmatured_rows_and_ignore_future_mutation():
    x, target, calendar = training_panel()
    fold_start = "2011-01-01"
    first_model, first_mask = models.fit_before(x, target, calendar, fold_start, "high", "A")
    assert first_model["training_rows"] >= models.MIN_TRAINING_ROWS
    assert pd.Timestamp(first_model["max_label_maturity_date"]) < pd.Timestamp(fold_start)
    assert x.index.get_level_values("Date")[first_mask].max() < pd.Timestamp(fold_start)

    future = x.index.get_level_values("Date") >= pd.Timestamp(fold_start)
    changed_x = x.copy()
    changed_target = target.copy()
    for column in changed_x.columns:
        values = pd.to_numeric(changed_x[column], errors="coerce")
        if is_bool_dtype(changed_x[column].dtype):
            changed_x.loc[future, column] = ~changed_x.loc[future, column]
        else:
            changed_x.loc[future, column] = values.loc[future].fillna(0.0) * -101.0 + 37.0
    changed_target.loc[future] = changed_target.loc[future].fillna(0.0) * -73.0 + 11.0
    second_model, second_mask = models.fit_before(
        changed_x, changed_target, calendar, fold_start, "high", "A"
    )
    np.testing.assert_array_equal(first_mask, second_mask)
    np.testing.assert_array_equal(first_model["coefficients"], second_model["coefficients"])
    np.testing.assert_array_equal(first_model["mean"], second_model["mean"])
    np.testing.assert_array_equal(first_model["scale"], second_model["scale"])


def test_candidate_b_model_contract_adds_only_the_pullback_feature():
    x, target, calendar = training_panel()
    model_a, _ = models.fit_before(x, target, calendar, "2011-01-01", "high", "A")
    model_b, _ = models.fit_before(x, target, calendar, "2011-01-01", "high", "B")
    assert model_b["columns"][:-1] == model_a["columns"]
    assert model_b["columns"][-1] == "pullback_up"
    assert len(model_b["coefficients"]) == len(model_b["columns"]) + 1
