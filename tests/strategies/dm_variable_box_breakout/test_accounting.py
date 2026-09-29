import numpy as np
import pandas as pd

from research.evaluation import weights
from research.experiments.sn1_final_diagnostics import account_from_weights


def test_long_short_net_reconcile_after_exits_and_sign_flips():
    dates = pd.bdate_range("2020-01-06", periods=4)
    codes = ["A", "B", "C", "D", "E"]
    index = pd.MultiIndex.from_product([dates, codes], names=["Date", "Code"])
    score = pd.Series(
        [
            1, 2, 3, 4, 5,   # A/B short; D/E long
            3, 2, 1, 4, 5,   # A exits to neutral; C enters Short
            5, 3, 1, 4, 2,   # A enters Long; B exits Short; E reverses to Short
            1, 2, 3, 4, 5,   # A reverses to Short; C exits to neutral
        ],
        index=index,
        dtype="float64",
    )
    target = pd.Series(0.01, index=index, dtype="float64")
    target.loc[(dates[2], "B")] = np.nan
    weight, quintile = weights(score)

    daily, rows = account_from_weights(
        score, weight, quintile, target, dates, one_way_cost=0.001
    )

    np.testing.assert_allclose(
        (daily.long_net + daily.short_net).to_numpy(),
        daily.net.to_numpy(),
        rtol=0.0,
        atol=1e-15,
    )
    np.testing.assert_allclose(
        (daily.long_cost + daily.short_cost).to_numpy(),
        daily.cost.to_numpy(),
        rtol=0.0,
        atol=1e-15,
    )
    np.testing.assert_allclose(
        (rows.long_cost + rows.short_cost).to_numpy(),
        rows.cost.to_numpy(),
        rtol=0.0,
        atol=1e-15,
    )
    assert daily.loc[dates[1], "short_cost"] > 0.0  # Short exit into neutral
    assert daily.loc[dates[2], "long_cost"] > 0.0  # Long opening and exit on a sign flip
    assert rows.loc[(dates[2], "B"), "cost"] == 0.0  # Officially skipped for the missing label
    assert daily.loc[dates[3], "short_cost"] > 0.0  # Short closing on an exit and reversal
