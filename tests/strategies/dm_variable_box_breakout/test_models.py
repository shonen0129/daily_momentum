import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_variable_box_breakout import models
from stock_comp_2026.strategies.dm_variable_box_breakout.features import FEATURE_COLUMNS


def training_panel(years=range(2008, 2015), codes=range(10)):
    dates = pd.DatetimeIndex(np.concatenate([
        pd.bdate_range(f"{year}-01-02", periods=80).to_numpy() for year in years
    ]))
    index = pd.MultiIndex.from_product([dates, [f"{code:05d}" for code in codes]], names=["Date", "Code"])
    row = np.arange(len(index), dtype=float)
    features = pd.DataFrame(index=index)
    for position, name in enumerate(FEATURE_COLUMNS):
        features[name] = np.sin(row / (11.0 + position)) + position * 0.1
    features["new_high_excess"] = 0.01 + (row % 7.0) / 100.0
    features["high_available"] = True
    target = pd.Series(np.cos(row / 13.0) * 0.01, index=index, name="Return")
    return features.sort_index(), target.sort_index()


def test_ridge_is_deterministic_and_predictions_are_finite():
    rng = np.random.default_rng(24)
    x = pd.DataFrame(rng.normal(size=(100, len(FEATURE_COLUMNS))), columns=FEATURE_COLUMNS)
    x.iloc[::9, 0] = np.nan
    y = x.fillna(0.0).iloc[:, 0].to_numpy() + 0.1 * x.iloc[:, 1].to_numpy()
    one = models.fit_arrays(x, y)
    two = models.fit_arrays(x, y)
    assert one == two
    assert np.isfinite(models.predict_matrix(x, one)).all()


def test_mature_target_fit_is_unchanged_by_future_target_mutation():
    x, target = training_panel()
    calendar = x.index.get_level_values("Date").unique().sort_values()
    model, training = models.fit_before(x, target, calendar, "2012-01-01")
    selected = (x.index.get_level_values("Date").year == 2012) & x["new_high_excess"].gt(0.0).to_numpy()
    prediction = models.predict_matrix(x.loc[selected, list(FEATURE_COLUMNS)], model)

    cutoff = pd.Timestamp("2012-04-30")
    changed = target.copy()
    changed.loc[changed.index.get_level_values("Date") > cutoff] = 999.0
    changed_model, changed_training = models.fit_before(x, changed, calendar, "2012-01-01")
    changed_prediction = models.predict_matrix(x.loc[selected, list(FEATURE_COLUMNS)], changed_model)
    np.testing.assert_array_equal(training, changed_training)
    np.testing.assert_array_equal(prediction, changed_prediction)
    assert model["max_label_maturity_date"] < "2012-01-01"
