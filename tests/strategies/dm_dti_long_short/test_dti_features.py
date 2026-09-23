"""DTI causal-vector and boundary tests."""
import ast
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from research.experiments.dti_long_short import predict_models
from stock_comp_2026.strategies.dm_dti_long_short import features


def test_complete_vector_and_ascending_sort_are_exact():
    dates = pd.bdate_range("2020-01-02", periods=24)
    index = pd.MultiIndex.from_product([dates, ["a", "b"]], names=["Date", "Code"])
    turnover = pd.Series(np.arange(len(index), dtype=float) / 1000 + .001, index=index)
    result, available = features.dti_vector(turnover)
    row = result.loc[(dates[20], "a")]
    expected = np.array([.041 - lag * .002 for lag in range(21)])
    np.testing.assert_allclose(row[features.feature_columns()[:21]].to_numpy(float), expected)
    np.testing.assert_allclose(row[features.feature_columns()[21:]].to_numpy(float), np.sort(expected))
    assert available.loc[(dates[20], "a")]


def test_zero_or_missing_volume_makes_only_affected_window_unavailable():
    dates = pd.bdate_range("2020-01-02", periods=24)
    index = pd.MultiIndex.from_product([dates, ["a", "b"]], names=["Date", "Code"])
    values = pd.Series(.01, index=index)
    values.loc[(dates[10], "a")] = np.nan
    _, available = features.dti_vector(values)
    assert not available.loc[(dates[20], "a")]
    assert available.loc[(dates[20], "b")]


def test_smoothing_is_deterministic_and_preserves_missing_neutral():
    index = pd.MultiIndex.from_product([[pd.Timestamp("2020-01-02"), pd.Timestamp("2020-01-03"), pd.Timestamp("2020-01-06")], ["a"]], names=["Date", "Code"])
    score, available = pd.Series([1., 2., 3.], index=index), pd.Series([True, False, True], index=index)
    first, second = features.smooth_complete(score, available, .25), features.smooth_complete(score, available, .25)
    pd.testing.assert_series_equal(first, second, check_exact=True)
    assert first.iloc[1] == 0.0


def test_rank_ewma_prediction_is_bitwise_prefix_invariant_across_truncation():
    dates = pd.bdate_range("2011-01-03", periods=8)
    index = pd.MultiIndex.from_product([dates, ["a", "b"]], names=["Date", "Code"])
    columns = features.feature_columns()
    x = pd.DataFrame(np.arange(len(index) * len(columns), dtype=float).reshape(len(index), -1) / 1000, index=index, columns=columns)
    x["available"] = True
    model = Pipeline([("scaler", StandardScaler()), ("elasticnet", ElasticNet(alpha=.001, l1_ratio=.5, max_iter=10000))]).fit(x[columns], np.linspace(-1, 1, len(x)))
    models = {(kind, 2011): model for kind in ("RAW", "RANK")}
    original = predict_models(x, models, {"parameters": {"ewma_alpha": .25}})
    cutoff = dates[4]
    truncated = predict_models(x.loc[x.index.get_level_values("Date") <= cutoff], models, {"parameters": {"ewma_alpha": .25}})
    for trial in ("T1", "T2", "T3"):
        pd.testing.assert_series_equal(original[trial].loc[truncated[trial].index], truncated[trial], check_exact=True)


def test_source_firewall_static_contract():
    folder = Path(features.__file__).parent
    forbidden = ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose", "AdjustmentVolume", "raw_target", "target_1day_valid"]
    for path in folder.glob("*.py"):
        text = path.read_text()
        for token in forbidden:
            assert token not in text, (path, token)
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in ("bfill", "backfill")
                if node.func.attr == "shift" and node.args:
                    assert isinstance(node.args[0], ast.Constant) and node.args[0].value >= 0
                assert not any(k.arg == "center" and isinstance(k.value, ast.Constant) and k.value.value for k in node.keywords)
                assert not any(k.arg == "direction" and isinstance(k.value, ast.Constant) and k.value.value == "forward" for k in node.keywords)
