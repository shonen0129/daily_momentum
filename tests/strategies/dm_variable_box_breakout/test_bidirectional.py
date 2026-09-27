import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_variable_box_breakout import bidirectional, sn1
from stock_comp_2026.strategies.dm_variable_box_breakout.features import FEATURE_COLUMNS
from stock_comp_2026.strategies.dm_variable_box_breakout import submission


def directional_panel(years=range(2008, 2015), codes=range(10)):
    dates = pd.DatetimeIndex(np.concatenate([
        pd.bdate_range(f"{year}-01-02", periods=80).to_numpy() for year in years
    ]))
    index = pd.MultiIndex.from_product(
        [dates, [f"{code:05d}" for code in codes]], names=["Date", "Code"]
    )
    row = np.arange(len(index), dtype=float)
    code = index.get_level_values("Code").astype(int).to_numpy()
    data = pd.DataFrame(index=index)
    data["box_duration"] = 20.0 + (row % 5.0)
    data["box_width_atr"] = 1.0 + (row % 7.0) / 10.0
    data["close_position"] = 0.2 + (row % 6.0) / 10.0
    data["relative_strength_60"] = np.sin(row / 17.0)
    data["distance_to_prior_high"] = -0.01 - (row % 5.0) / 1000.0
    data["distance_to_prior_low"] = -0.01 - ((row + 2.0) % 5.0) / 1000.0
    data["new_high_excess"] = np.where(code < 5, 0.01 + (row % 5.0) / 1000.0, 0.0)
    data["new_low_excess"] = np.where(code >= 5, 0.01 + (row % 7.0) / 1000.0, 0.0)
    data["high_available"] = True
    data["low_available"] = True
    target = pd.Series(
        np.sin(row / 13.0) * 0.01 + (code - 4.5) * 0.0001,
        index=index,
        name="Return",
    )
    return data.sort_index(), target.sort_index()


def test_low_direction_orients_box_position_momentum_and_prior_trough():
    index = pd.MultiIndex.from_tuples(
        [(pd.Timestamp("2012-01-03"), "10000")], names=["Date", "Code"]
    )
    x = pd.DataFrame({
        "box_duration": [30.0],
        "box_width_atr": [1.5],
        "close_position": [0.9],
        "relative_strength_60": [0.4],
        "distance_to_prior_high": [-0.01],
        "distance_to_prior_low": [-0.02],
    }, index=index)
    high = bidirectional.directional_features(x, "high")
    low = bidirectional.directional_features(x, "low")
    assert tuple(high.columns) == bidirectional.DIRECTIONAL_COLUMNS
    assert tuple(low.columns) == bidirectional.DIRECTIONAL_COLUMNS
    assert high.iloc[0]["oriented_close_position"] == 0.9
    assert np.isclose(low.iloc[0]["oriented_close_position"], 0.1)
    assert high.iloc[0]["oriented_relative_strength_60"] == 0.4
    assert low.iloc[0]["oriented_relative_strength_60"] == -0.4
    assert low.iloc[0]["distance_to_prior_extreme"] == -0.02


def test_standalone_score_is_signed_by_side_and_zero_off_events():
    dates = pd.bdate_range("2012-01-03", periods=1)
    codes = ["10000", "20000", "30000", "40000", "50000"]
    index = pd.MultiIndex.from_product([dates, codes], names=["Date", "Code"])
    x = pd.DataFrame({
        "high_available": True,
        "low_available": True,
        "new_high_excess": [0.01, 0.02, 0.0, 0.0, 0.0],
        "new_low_excess": [0.0, 0.0, 0.01, 0.02, 0.0],
    }, index=index)
    predictions = {
        "high": pd.Series([0.1, 0.9], index=index[:2]),
        "low": pd.Series([0.1, 0.9], index=index[2:4]),
    }
    score = bidirectional.generate_raw_signal(x, predictions)
    assert score.iloc[0] > 0.0 and score.iloc[1] > score.iloc[0]
    assert score.iloc[2] < 0.0 and score.iloc[3] < score.iloc[2]
    assert score.iloc[4] == 0.0
    assert np.isfinite(score).all()


def test_low_model_uses_only_mature_low_events_and_ignores_future_targets():
    x, target = directional_panel()
    calendar = x.index.get_level_values("Date").unique().sort_values()
    model, training = bidirectional.fit_before(x, target, calendar, "2012-01-01", "low")
    assert training.sum() >= bidirectional.MIN_TRAINING_ROWS
    assert (x.loc[training, "new_low_excess"] > 0.0).all()
    assert (x.loc[training, "new_high_excess"] == 0.0).all()
    assert model["max_label_maturity_date"] < "2012-01-01"

    cutoff = pd.Timestamp("2012-04-30")
    changed = target.copy()
    future = changed.index.get_level_values("Date") > cutoff
    changed.loc[future] = 999.0
    changed_model, changed_training = bidirectional.fit_before(
        x, changed, calendar, "2012-01-01", "low"
    )
    assert model == changed_model
    np.testing.assert_array_equal(training, changed_training)

    prediction, _, _ = bidirectional.predict_year(x, target, 2012, "low")
    assert prediction.index.isin(x.index[x["new_low_excess"] > 0.0]).all()
    assert np.isfinite(prediction.to_numpy()).all()


def test_directional_feature_matrix_keeps_fixed_ridge_schema():
    x, _ = directional_panel(years=range(2011, 2012))
    matrix = bidirectional.directional_features(x, "low")
    assert list(matrix.columns) == list(bidirectional.DIRECTIONAL_COLUMNS)
    assert len(FEATURE_COLUMNS) == 5
    assert matrix.index.equals(x.index)


def test_strategy_adapter_returns_the_research_sn1_score():
    x, target = directional_panel()
    result, _ = submission.predict_from_features(x, target, years=(2011, 2012))
    predictions, _ = bidirectional.walk_forward_predictions(
        x, target, years=(2011, 2012)
    )
    base_score = bidirectional.generate_signal(x, predictions, alpha=0.25)
    expected = sn1.rebuild_from_base_score(base_score)[
        "SIDE_SOURCE_SEPARATION"
    ].rename("Return").to_frame()
    pd.testing.assert_frame_equal(result, expected, check_exact=True)
