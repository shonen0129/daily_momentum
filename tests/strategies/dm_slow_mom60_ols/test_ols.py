"""OLS recovery, mature-only training, label-refit causality and artifact inference."""
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from stock_comp_2026.strategies.dm_slow_mom60_ols import models, submission
from stock_comp_2026.strategies.dm_slow_mom60_ols.component_factors import features as f
from research.experiments.slow_mom60_ols import label_maturity, mutate_labels, exact_models
from research.experiments.slow_mom60_equal import exact, mutate, source_dates, source_scan


def toy():
    rng = np.random.default_rng(21)
    dates = pd.bdate_range("2010-10-01", periods=150)
    index = pd.MultiIndex.from_product([dates, list("abcdefghij")], names=["Date", "Code"])
    values = np.column_stack([np.concatenate([rng.permutation(10) for _ in dates]) / 5 - .9 for _ in range(3)])
    x = pd.DataFrame(values, index=index, columns=models.RANK_COLUMNS)
    coefficients = np.array([.002, .004, -.003, .001])
    y = pd.Series(coefficients[0] + values @ coefficients[1:], index=index, name="Return")
    return x, y, coefficients


def inputs_fixture():
    dates = pd.bdate_range("2008-11-03", periods=580)
    codes = [str(10000 + i) for i in range(8)]
    index = pd.MultiIndex.from_product([dates, codes], names=["Date", "Code"])
    rng = np.random.default_rng(31)
    v = np.tile(np.arange(1, 9, dtype=float), len(dates))
    prices = pd.DataFrame({"Close": 90 + v + rng.uniform(0, 10, len(index)),
                           "TurnoverValue": v * 1e6 * rng.uniform(.8, 1.2, len(index))}, index=index)
    raw = pd.DataFrame({"Return": rng.normal(0, .01, len(index))}, index=index)
    fi = pd.MultiIndex.from_product([dates[[0, 80, 220, 440]], codes], names=["Date", "Code"])
    q = np.tile(np.arange(1, 9, dtype=float), 4)
    fins = pd.DataFrame({"Equity": q * 30, "TotalAssets": q * 100,
                         "Profit": q, "CashFlowsFromOperatingActivities": q * 2,
                         "ForecastEarningsPerShare": q, f.slow.SHARES: q * 1000}, index=fi)
    return {"prices_daily_quotes": prices, "raw_return_1day": raw, "fins_statements": fins,
            "listed_info": pd.DataFrame({"Sector17Code": "A"}, index=index),
            "beta_1day": pd.DataFrame({"Return": v / 10}, index=index),
            "topix_return_1day": pd.DataFrame({"Return": rng.normal(0, .002, len(dates))}, index=dates.rename("Date"))}


def test_ols_recovers_known_conditional_weights_without_sign_constraints():
    x, y, truth = toy()
    model = models.fit_year(x, y, 2011)
    np.testing.assert_allclose(model["coefficients"], truth, rtol=0, atol=1e-14)
    assert model["coefficients"][2] < 0
    assert model["design_rank"] == 4 and model["regularization"] is None
    assert pd.Timestamp(model["max_label_maturity_date"]) < pd.Timestamp(model["fold_start"])


def test_t_plus_two_boundary_labels_are_excluded_even_with_past_signal_dates():
    x, y, _ = toy()
    dates = x.index.get_level_values("Date")
    calendar = dates.unique().sort_values()
    first = calendar[calendar.year == 2011][0]
    p = calendar.get_loc(first)
    baseline = models.fit_year(x, y, 2011)
    changed = y.copy()
    changed.loc[dates.isin(calendar[p - 2:])] = 1e9
    got = models.fit_year(x, changed, 2011)
    assert got == baseline
    # The last actually mature signal is allowed to influence the fit.
    changed = y.copy()
    changed.loc[dates == calendar[p - 3]] += 10.
    assert models.fit_year(x, changed, 2011)["coefficients"] != baseline["coefficients"]


def test_label_future_mutation_uses_availability_and_refits():
    x, y, _ = toy()
    pred, records = models.walk_forward(x, y, years=[2011])
    cutoff = pd.Timestamp("2011-01-31")
    maturity = label_maturity(y.index)
    changed = mutate_labels(y, maturity, cutoff, 20261003)
    past_unmatured = (y.index.get_level_values("Date") <= cutoff) & maturity.gt(cutoff)
    assert past_unmatured.any() and not changed.loc[past_unmatured].equals(y.loc[past_unmatured])
    got, fitted = models.walk_forward(x, changed, years=[2011])
    prefix = x.index.get_level_values("Date") <= cutoff
    exact(pred.loc[prefix], got.loc[prefix])
    exact_models(records, fitted, 2011)
    xx = x.loc[prefix]
    yy = y.loc[prefix].where(maturity.loc[prefix].le(cutoff))
    truncated, rr = models.walk_forward(xx, yy, years=[2011])
    exact(pred.loc[prefix], truncated)
    exact_models(records, rr, 2011)


def test_constant_features_use_fixed_minimum_norm_and_finite_score():
    x, y, _ = toy()
    x[:] = 0.
    pred, records = models.walk_forward(x, y, years=[2011])
    assert records[0]["design_rank"] == 1
    np.testing.assert_array_equal(records[0]["coefficients"][1:], [0., 0., 0.])
    assert np.isfinite(pred).all()


@pytest.mark.parametrize("bad", ["duplicate", "unsorted", "nan", "misaligned_label"])
def test_invalid_feature_label_contract_fails(bad):
    x, y, _ = toy()
    if bad == "duplicate":
        x = pd.concat([x, x.iloc[:1]])
    elif bad == "unsorted":
        x = x.iloc[::-1]
    elif bad == "nan":
        x.iloc[0, 0] = np.nan
    else:
        y = y.iloc[::-1]
    with pytest.raises(ValueError):
        models.fit_year(x, y, 2011)


def test_no_future_artifact_fallback_and_no_immature_model(tmp_path):
    x, y, _ = toy()
    xx = x.loc[x.index.get_level_values("Date").year == 2011]
    with pytest.raises(ValueError, match="Missing annual model"):
        models.predict_artifacts(xx, tmp_path)
    model = models.fit_year(x, y, 2011)
    model["max_label_maturity_date"] = model["fold_start"]
    with pytest.raises(ValueError, match="Immature"):
        models.apply_year(xx, model)


@pytest.mark.parametrize("source", list(f.INPUT_COLUMNS) + ["Train_labels", "ALL", "TRUNCATION"])
def test_combined_features_and_learning_prefix_causality(source):
    inputs = inputs_fixture()
    components, mid = f.components(inputs)
    x = f.factor_ranks(components)
    y = pd.Series(np.sin(np.arange(len(x))) * .02, index=x.index, name="Return")
    pred, records = models.walk_forward(x, y, years=[2009, 2010, 2011])
    cutoff = pd.Timestamp("2009-06-30")
    maturity = label_maturity(y.index)
    changed = dict(inputs)
    for i, (name, frame) in enumerate(inputs.items()):
        if source == "TRUNCATION":
            changed[name] = frame.loc[source_dates(frame) <= cutoff]
        elif source in [name, "ALL"]:
            changed[name] = mutate(frame, name, cutoff, 20261003 + i)
    labels = mutate_labels(y, maturity, cutoff, 20261003) if source in ["Train_labels", "ALL"] else y
    got, mm = f.components(changed)
    xx = f.factor_ranks(got)
    labels = labels.reindex(xx.index)
    if source == "TRUNCATION":
        labels = labels.where(maturity.reindex(xx.index).le(cutoff))
    predicted, fitted = models.walk_forward(xx, labels, years=[2009, 2010, 2011])
    prefix = x.index[x.index.get_level_values("Date") <= cutoff]
    exact(components.loc[prefix], got.loc[prefix])
    exact(mid.loc[prefix], mm.loc[prefix])
    exact(x.loc[prefix], xx.loc[prefix])
    exact(pred.loc[prefix], predicted.loc[prefix])
    exact_models(records, fitted, cutoff.year)


def test_stored_models_and_standalone_label_free_inference(tmp_path):
    inputs = inputs_fixture()
    components, _ = f.components(inputs)
    x = f.factor_ranks(components)
    target = pd.Series(np.cos(np.arange(len(x))) * .01, index=x.index, name="Return")
    directory = tmp_path / "models"
    expected, records = models.walk_forward(x, target, years=[2009, 2010, 2011], model_dir=directory)
    exact(expected, models.predict_artifacts(x, directory))
    source = Path(__file__).resolve().parents[3] / "stock_comp_2026/strategies/dm_slow_mom60_ols"
    bundle = tmp_path / "bundle"
    shutil.copytree(source, bundle, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(directory, bundle / "models")
    stage = tmp_path / "features"
    stage.mkdir()
    for name, frame in inputs.items():
        frame.to_parquet(stage / f"{name}_train.parquet")
    exact(expected.to_frame(), submission.predict(stage, directory))
    out = tmp_path / "standalone.parquet"
    command = [sys.executable, "-c", "import submission,sys; submission.predict(sys.argv[1]).to_parquet(sys.argv[2])", str(stage), str(out)]
    result = subprocess.run(command, cwd=bundle, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    exact(expected.to_frame(), pd.read_parquet(out))
    assert not list(stage.glob("*target*"))
    assert source_scan(sorted(source.rglob("*.py")))["status"] == "PASS"
    previous = source.parent / "dm_slow_mom60_equal"
    for path in previous.rglob("*.py"):
        assert path.read_bytes() == (source / "component_factors" / path.relative_to(previous)).read_bytes()
