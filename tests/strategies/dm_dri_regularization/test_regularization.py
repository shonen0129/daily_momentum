"""Causal estimation, shrinkage geometry, and standalone inference contracts."""
import json

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import ElasticNet
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from research.experiments import dri_regularization as driver
from stock_comp_2026.strategies.dm_dri_long_short import features as old
from stock_comp_2026.strategies.dm_dri_regularization import features, models

SETTINGS = {"l1_ratio": .5, "elasticnet_max_iter": 20000, "elasticnet_tol": 1e-8,
            "ewma_alpha": .25, "model_years": [2011],
            "ridge_lambda_grid": [.01, .1, 1.0], "elasticnet_rho_grid": [.1, .5, .9],
            "initial_cv": [{"train_end": "2009-12-31", "validation_start": "2010-01-01", "validation_end": "2010-06-30"},
                           {"train_end": "2010-06-30", "validation_start": "2010-07-01", "validation_end": "2010-12-31"}]}


@pytest.fixture(autouse=True)
def threads():
    with threadpool_limits(limits=1):
        yield


def inputs():
    dates = pd.bdate_range("2009-10-01", "2011-05-31")
    index = pd.MultiIndex.from_product([dates, ["a", "b", "c"]], names=["Date", "Code"])
    rng = np.random.default_rng(7)
    raw = pd.Series(rng.normal(0, .02, len(index)), index=index, name="Return")
    return {"raw_return_1day": raw.to_frame(),
            "beta_1day": pd.DataFrame({"Return": np.ones(len(index))}, index=index),
            "topix_return_1day": pd.DataFrame({"Return": rng.normal(0, .003, len(dates))}, index=dates.rename("Date"))}


def training_matrix():
    rng = np.random.default_rng(17)
    x = pd.DataFrame(rng.normal(size=(150, 5)))
    x[5] = x[0] + x[1]
    x[6] = 3.0
    y = pd.Series(.01 * x[0] - .02 * x[2] + rng.normal(0, .001, len(x)))
    return x, y


def test_relative_alpha_below_kkt_boundary_retains_signal():
    x, y = training_matrix()
    fitted = models.fit_model(x, y, "elasticnet", .5, SETTINGS)
    assert fitted["nonzero_count"] > 0
    assert fitted["alpha"] == .5 * fitted["alpha_max"]
    z = StandardScaler().fit_transform(x)
    boundary = ElasticNet(alpha=fitted["alpha_max"] * 1.001, l1_ratio=.5, tol=1e-10, max_iter=20000).fit(z, y)
    assert np.count_nonzero(boundary.coef_) == 0


def test_ridge_matches_normalized_closed_form_with_collinearity():
    x, y = training_matrix()
    fitted = models.fit_model(x, y, "ridge", .1, SETTINGS)
    z = StandardScaler().fit_transform(x)
    z -= z.mean(axis=0)
    expected = np.linalg.solve(z.T @ z / len(x) + .1 * np.eye(x.shape[1]), z.T @ (y - y.mean()) / len(x))
    np.testing.assert_allclose(fitted["coef"], expected, atol=1e-14, rtol=1e-12)
    assert fitted["alpha"] == len(x) * .1 and fitted["coef"][-1] == 0


@pytest.mark.parametrize("family", ["ridge", "elasticnet"])
def test_constant_label_and_features_do_not_fabricate_signal(family):
    x = pd.DataFrame({"a": [2.] * 20, "b": [3.] * 20})
    y = pd.Series([.25] * 20)
    fitted = models.fit_model(x, y, family, .5, SETTINGS)
    assert fitted["alpha_max"] == 0 and fitted["nonzero_count"] == 0
    np.testing.assert_array_equal(models.predict_matrix(x, fitted), y)


def test_index_and_feature_order_errors_are_not_silently_aligned():
    x, y = training_matrix()
    with pytest.raises(ValueError, match="index"):
        models.fit_model(x, y.iloc[::-1], "ridge", .1, SETTINGS)
    fitted = models.fit_model(x, y, "ridge", .1, SETTINGS)
    with pytest.raises(ValueError, match="feature order"):
        models.predict_matrix(x[x.columns[::-1]], fitted)


def test_feature_reproduction_missing_windows_and_relisting():
    data = inputs()
    dates = data["raw_return_1day"].index.get_level_values("Date")
    index = data["raw_return_1day"].index
    gap = (index.get_level_values("Code") == "a") & (dates >= "2010-02-01") & (dates <= "2010-04-01")
    for name in ["raw_return_1day", "beta_1day"]:
        data[name] = data[name].loc[~gap]
    data["raw_return_1day"].loc[(pd.Timestamp("2010-06-01"), "b"), "Return"] = np.nan
    actual = features.build_features(data)
    pd.testing.assert_frame_equal(actual, old.build_features(data), check_exact=True)
    assert not actual.loc[(pd.Timestamp("2010-04-02"), "a"), "raw_available"]
    assert not actual.loc[(pd.Timestamp("2010-06-02"), "b"), "raw_available"]


@pytest.mark.parametrize("family", ["ridge", "elasticnet"])
def test_pipeline_future_mutation_truncation_and_label_refit(family):
    data = inputs()
    frame = features.build_features(data)
    target = data["raw_return_1day"].Return * .2
    calendar = frame.index.get_level_values("Date").unique().sort_values()
    spec = {"trial_id": "X", "variant": "raw", "family": family}
    bundle = driver.build_bundle(frame, target, spec, .5, SETTINGS, calendar)
    score = models.predict_from_features(frame, bundle)
    cutoff = pd.Timestamp("2011-02-01")
    before = score.index[score.index.get_level_values("Date") <= cutoff]
    for mode in [False, True]:
        changed = features.build_features(driver.mutate(data, cutoff, mode))
        pd.testing.assert_frame_equal(frame.loc[before], changed.loc[before], check_exact=True)
        pd.testing.assert_series_equal(score.loc[before], models.predict_from_features(changed, bundle).loc[before], check_exact=True)
    altered = target.copy()
    altered.loc[~models.available_until(target.index, "2010-12-31", calendar)] = 999.
    assert driver.fit_year(frame, altered, spec, .5, SETTINGS, calendar, 2011) == bundle["models"]["2011"]
    restored = json.loads(json.dumps(bundle))
    pd.testing.assert_series_equal(score, models.predict_from_features(frame, restored), check_exact=True)
    assert np.isfinite(score).all() and (score.loc[~frame.raw_available] == 0).all()


def test_cv_ignores_unrealized_future_labels():
    data = inputs()
    frame = features.build_features(data)
    target = data["raw_return_1day"].Return * .2
    calendar = frame.index.get_level_values("Date").unique().sort_values()
    spec = {"trial_id": "X", "variant": "res", "family": "elasticnet"}
    result = driver.select_strength(frame, target, spec, SETTINGS, calendar)
    changed = target.copy()
    changed.loc[~models.available_until(target.index, "2010-12-31", calendar)] = 999.
    assert result == driver.select_strength(frame, changed, spec, SETTINGS, calendar)


def test_static_source_firewall():
    assert len(driver.source_scan()) == 4
