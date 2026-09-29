import numpy as np
import pandas as pd

from stock_comp_2026.strategies.dm_breakout_momentum_volume_lgbm import features


def synthetic_inputs(days=320):
    dates = pd.bdate_range("2008-11-04", periods=days)
    codes = ["10000", "20000", "30000"]
    index = pd.MultiIndex.from_product([dates, codes], names=["Date", "Code"])
    close = np.tile(np.linspace(100.0, 180.0, days), len(codes))
    volume = np.full(len(index), 100.0)
    factor = np.ones(len(index))
    split_date = dates[270]
    split_rows = index.get_level_values("Date") >= split_date
    code_a = index.get_level_values("Code") == "10000"
    close[split_rows & code_a] *= 0.5
    volume[split_rows & code_a] *= 2.0
    factor[index.get_level_values("Date") == split_date] = np.where(
        code_a[index.get_level_values("Date") == split_date], 0.5, 1.0
    )
    prices = pd.DataFrame(
        {
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": volume,
            "AdjustmentFactor": factor,
        },
        index=index,
    )
    returns = pd.DataFrame({"Return": np.tile(np.linspace(-0.01, 0.01, days), len(codes))}, index=index)
    beta = pd.DataFrame({"Return": 0.0}, index=index)
    market = pd.DataFrame({"Return": 0.0}, index=pd.Index(dates, name="Date"))
    return {
        "raw_return_1day": returns.sort_index(),
        "beta_1day": beta.sort_index(),
        "topix_return_1day": market.sort_index(),
        "prices_daily_quotes": prices.sort_index(),
    }


def test_split_safe_volume_removes_split_step():
    inputs = synthetic_inputs()
    volume = features.split_safe_volume(inputs)
    code = volume.xs("10000", level="Code")
    assert code.iloc[269] == code.iloc[270] == 100.0


def test_features_are_prefix_invariant_to_future_mutation():
    inputs = synthetic_inputs()
    original = features.build_features(inputs)
    cutoff = pd.Timestamp("2009-12-01")
    changed = {}
    for name, frame in inputs.items():
        dates = frame.index.get_level_values("Date")
        future = dates > cutoff
        mutated = frame.copy()
        for column in mutated:
            if pd.api.types.is_numeric_dtype(mutated[column]):
                mutated.loc[future, column] = mutated.loc[future, column] * -3.0 + 17.0
        changed[name] = mutated
    actual = features.build_features(changed)
    prefix = original.index.get_level_values("Date") <= cutoff
    pd.testing.assert_frame_equal(original.loc[prefix], actual.loc[prefix], check_exact=True)


def test_feature_contract_and_missing_history():
    inputs = synthetic_inputs()
    result = features.build_features(inputs)
    assert tuple(result.columns) == features.FEATURE_COLUMNS
    assert result.index.equals(inputs["raw_return_1day"].index)
    assert result["relative_volume_change_rank"].isna().any()
    assert np.isfinite(result["res60s1"].to_numpy()).all()
