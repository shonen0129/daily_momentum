import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_breakout_momentum_volume_linear import models


def test_centered_target_rank_is_daily_and_missing_safe():
    index = pd.MultiIndex.from_product(
        [pd.to_datetime(["2011-01-04", "2011-01-05"]), ["A", "B", "C"]],
        names=["Date", "Code"],
    )
    target = pd.Series([1.0, 2.0, 3.0, 4.0, np.nan, 8.0], index=index)
    ranked = models.centered_target_rank(target)
    assert np.isclose(ranked.iloc[:3].sum(), 0.0, atol=1e-15)
    assert ranked.iloc[3] == -0.5
    assert np.isnan(ranked.iloc[4])
    assert ranked.iloc[5] == 0.5


def test_ridge_fit_imputes_scales_and_replays_deterministically():
    rng = np.random.default_rng(17)
    values = rng.normal(size=(1000, 4))
    values[::13, 2] = np.nan
    labels = 0.5 * values[:, 0] - 0.3 * np.nan_to_num(values[:, 2]) + rng.normal(0, 0.1, 1000)
    labels = labels.astype(float)
    columns = list(models.FEATURE_COLUMNS)
    x = pd.DataFrame(values, columns=columns)
    first = models.fit_arrays(values, labels)
    second = models.fit_arrays(values, labels)
    np.testing.assert_array_equal(
        models.predict_matrix(x, first),
        models.predict_matrix(x, second),
    )
    assert np.isfinite(models.predict_matrix(x, first)).all()
    assert np.all(np.asarray(first["scale"]) > 0)
