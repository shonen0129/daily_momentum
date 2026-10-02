import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal

from research.experiments import up_pullback_sn1
from research import evaluation
from stock_comp_2026.strategies.dm_variable_box_breakout import bidirectional


def _feature_panel():
    dates = pd.bdate_range("2014-01-06", periods=3, name="Date")
    codes = ["10000", "10001"]
    index = pd.MultiIndex.from_product([dates, codes], names=["Date", "Code"])
    row = np.arange(len(index), dtype=float)
    return pd.DataFrame({
        "box_duration": 20 + row,
        "box_width_atr": 1 + row / 10,
        "close_position": row / 10,
        "relative_strength_60": row / 100,
        "distance_to_prior_high": -row / 1000,
        "distance_to_prior_low": row / 1000,
        "new_high_excess": np.where(row % 2 == 0, 0.01, 0.0),
        "new_low_excess": np.where(row % 2 == 0, 0.0, 0.01),
        "high_available": True,
        "low_available": True,
        "pullback_up": np.where(row % 3 == 0, 0.5, 0.0),
        # These Event-Box columns exist in the full panel but must not enter the model.
        "event_upstate": 1.0,
        "event_downstate": 0.0,
        "event_box_position": -0.5,
        "event_box_age": 17.0,
        "event_structure_age": 31.0,
        "event_bo_up_strength": 2.0,
        "event_breakout_failure": 0.0,
    }, index=index)


def test_up_pullback_adds_only_one_column_to_current_directional_inputs():
    panel = _feature_panel()
    for side in bidirectional.SIDES:
        current = bidirectional.directional_features(panel, side)
        candidate = up_pullback_sn1._candidate_matrix(panel, side)
        assert list(candidate.columns) == list(bidirectional.DIRECTIONAL_COLUMNS) + ["pullback_up"]
        assert_frame_equal(candidate.loc[:, list(bidirectional.DIRECTIONAL_COLUMNS)], current)
        assert_series_equal(candidate["pullback_up"], panel["pullback_up"])
        assert "event_box_age" not in candidate.columns
        assert "event_structure_age" not in candidate.columns
        assert "event_bo_up_strength" not in candidate.columns


def test_attribution_migration_tables_partition_all_four_buckets(tmp_path):
    dates = pd.bdate_range("2011-01-03", periods=2, name="Date")
    codes = ["10000", "10001", "10002", "10003", "10004"]
    index = pd.MultiIndex.from_product([dates, codes], names=["Date", "Code"])
    x = pd.DataFrame({
        "event_upstate": [1, 1, 0, 0, 0] * 2,
        "event_box_position": [-0.5, 0.5, -0.5, 0.5, np.nan] * 2,
    }, index=index)
    target = pd.Series(np.tile([-0.02, -0.01, 0.0, 0.01, 0.02], 2),
                       index=index, name="Return")
    baseline = pd.Series(np.tile([0.0, 1.0, 2.0, 3.0, 4.0], 2),
                         index=index, name="Return")
    candidate = pd.Series(np.tile([1.1, 0.9, 2.0, 3.0, 4.0], 2),
                          index=index, name="Return")
    scores = {"SN1_H1": baseline, "UP_PULLBACK": candidate}
    accounts = {
        name: evaluation.daily_account(score, target)
        for name, score in scores.items()
    }

    attribution = up_pullback_sn1._attribution(x, target, scores, accounts, tmp_path)

    assert set(attribution.group) == {
        "UPSTATE=1,x<0", "UPSTATE=1,x>=0", "UPSTATE=0,x<0", "Other"
    }
    assert int(attribution.rows.sum()) == len(target)
    q_migration = pd.read_csv(tmp_path / "quintile_migration.csv")
    side_migration = pd.read_csv(tmp_path / "long_neutral_short_migration.csv")
    assert set(q_migration.group) == set(attribution.group)
    assert set(side_migration.group) == set(attribution.group)
