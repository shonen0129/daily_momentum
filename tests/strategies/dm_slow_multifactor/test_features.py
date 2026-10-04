"""PIT, missingness, calendar, normalization and adapter contracts."""
import numpy as np
import pandas as pd
import pytest

from stock_comp_2026.strategies.dm_slow_multifactor import features as f
from stock_comp_2026.strategies.dm_slow_multifactor import submission


def fixture():
    dates = pd.bdate_range("2012-01-02", periods=85)
    codes = [str(10000 + i) for i in range(45)]
    idx = pd.MultiIndex.from_product([dates, codes], names=["Date", "Code"])
    n = len(idx)
    v = np.tile(np.arange(1, 46, dtype=float), len(dates))
    prices = pd.DataFrame({"Close": 100 + v, "TurnoverValue": v * 1e6}, index=idx)
    r = pd.DataFrame({"Return": np.sin(np.arange(n)) * .01}, index=idx)
    sector = np.tile(["A"] * 25 + ["B"] * 15 + [None] * 5, len(dates))
    listed = pd.DataFrame({"Sector17Code": sector}, index=idx)
    fi = pd.MultiIndex.from_product([dates[[5, 40, 70]], codes], names=["Date", "Code"])
    v = np.tile(np.arange(1, 46, dtype=float), 3)
    fins = pd.DataFrame({"Equity": v * 20, "TotalAssets": v * 100,
                         "Profit": v, "CashFlowsFromOperatingActivities": v * 2,
                         "ForecastEarningsPerShare": v + np.repeat([0, 1, 3], 45),
                         f.SHARES: v * 1000}, index=fi)
    return dict(prices_daily_quotes=prices, raw_return_1day=r,
                fins_statements=fins, listed_info=listed)


def assert_bitwise(a, b):
    assert a.index.equals(b.index)
    assert a.columns.equals(b.columns)
    assert a.dtypes.equals(b.dtypes)
    assert np.array_equal(a.to_numpy().view(np.uint64), b.to_numpy().view(np.uint64))


@pytest.mark.parametrize("sector", [False, True])
def test_all_source_future_mutation_and_truncation(sector):
    inputs = fixture()
    cutoff = pd.Timestamp("2012-03-01")
    base = f.build_features(inputs, sector)
    mask = base.index.get_level_values("Date") <= cutoff
    future = {}
    prefix = {}
    for name, frame in inputs.items():
        future[name] = frame.copy()
        suffix = frame.index.get_level_values("Date") > cutoff
        for col in frame:
            future[name].loc[suffix, col] = "Z" if col == "Sector17Code" else 999999.
        future[name] = future[name].drop(frame.index[suffix][::3])
        prefix[name] = frame.loc[~suffix]
    for changed in [future, prefix]:
        got = f.build_features(changed, sector).loc[base.index[mask]]
        assert_bitwise(base.loc[mask], got)
        for revision in [False, True]:
            assert_bitwise(f.score(base.loc[mask], revision).to_frame(),
                           f.score(got, revision).to_frame())


def test_date_only_disclosure_and_previous_actual_observation():
    inputs = fixture()
    raw, _ = f.raw_factors(inputs)
    code = "10000"
    dates = inputs["raw_return_1day"].index.get_level_values("Date").unique()
    assert np.isnan(raw.loc[(dates[4], code), "ey"])
    assert raw.loc[(dates[5], code), "ey"] == 1 / 101
    assert np.isnan(raw.loc[(dates[39], code), "eps_revision_yield"])
    assert raw.loc[(dates[40], code), "eps_revision_yield"] == 1 / 101
    # Unchanged disclosed EPS is still the previous event; missing events aren't.
    inputs["fins_statements"].loc[(dates[40], code), "ForecastEarningsPerShare"] = 1.
    raw, _ = f.raw_factors(inputs)
    assert raw.loc[(dates[40], code), "eps_revision_yield"] == 0
    assert raw.loc[(dates[70], code), "eps_revision_yield"] == 3 / 101


def test_zero_denominators_all_missing_and_raw_level_only():
    inputs = fixture()
    original = f.build_features(inputs)
    inputs["prices_daily_quotes"]["AdjustmentClose"] = 1e20
    assert_bitwise(original, f.build_features(inputs))
    inputs["prices_daily_quotes"].loc[:, ["Close", "TurnoverValue"]] = 0
    inputs["fins_statements"].loc[:, :] = np.nan
    got = f.build_features(inputs)
    assert got.filter(regex="^(z_|size_liquidity|quality|value|revision)").eq(0).all().all()
    assert np.isfinite(f.score(got)).all()


def test_sector_small_and_unknown_fallback_and_local_centering():
    inputs = fixture()
    raw, sectors = f.raw_factors(inputs)
    values = raw["ey"]
    glob, local = f.normalize(values), f.normalize(values, sectors)
    fallback = sectors.isna() | sectors.eq("B")
    assert np.array_equal(glob[fallback].to_numpy(), local[fallback].to_numpy())
    a = local[sectors.eq("A")].groupby(level="Date").mean()
    assert a.abs().max() < 1e-14


def test_rolling_uses_exchange_dates_and_not_observation_count():
    inputs = fixture()
    dates = inputs["raw_return_1day"].index.get_level_values("Date").unique()
    drop = [(date, "10000") for date in dates[20:65]]
    inputs["raw_return_1day"] = inputs["raw_return_1day"].drop(drop)
    raw, _ = f.raw_factors(inputs)
    assert np.isnan(raw.loc[(dates[65], "10000"), "amihud"])
    assert np.isfinite(raw.loc[(dates[65], "10010"), "amihud"])


def test_adapter_label_free_index_coverage_and_shuffle(tmp_path):
    inputs = fixture()
    expected = f.score(f.build_features(inputs)).to_frame()
    shuffled = {name: frame.sample(frac=1, random_state=7) for name, frame in inputs.items()}
    assert_bitwise(f.build_features(inputs), f.build_features(shuffled))
    for name, frame in inputs.items():
        frame.to_parquet(tmp_path / f"{name}_train.parquet")
    got = submission.predict(tmp_path)
    assert_bitwise(expected, got)
    assert list(got.columns) == ["Return"]
    assert got.index.equals(inputs["raw_return_1day"].index)
    assert np.isfinite(got.to_numpy()).all()


def test_duplicate_input_is_rejected():
    inputs = fixture()
    frame = inputs["raw_return_1day"]
    inputs["raw_return_1day"] = pd.concat([frame, frame.iloc[:1]])
    with pytest.raises(ValueError, match="unique"):
        f.build_features(inputs)


def test_vectorized_quantiles_preserve_reference_rounding_and_empty_groups():
    rng = np.random.default_rng(9)
    dates = pd.bdate_range("2012-01-02", periods=8)
    index = pd.MultiIndex.from_product([dates, range(47)], names=["Date", "Code"])
    values = pd.Series(rng.normal(size=len(index)), index=index)
    values.iloc[::7] = np.nan
    values.loc[dates[0]] = np.nan
    values.loc[dates[1]] = 3.0
    keys = values.index.get_level_values("Date")
    for got, quantile in zip(f.group_quantile_bounds(values, keys), [.01, .99]):
        reference = values.groupby(keys, sort=False).transform(lambda x: x.quantile(quantile))
        assert np.array_equal(got.to_numpy().view(np.uint64), reference.to_numpy().view(np.uint64))
