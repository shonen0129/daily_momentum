import numpy as np
import pandas as pd
import pytest

from stock_comp_2026.strategies.dm_sector_momentum import features as sm
from stock_comp_2026.strategies.dm_sector_momentum import submission
from stock_comp_2026.strategies.dm_trainonly import features as old


def fixture_inputs(days=170, stocks=24):
    dates = pd.bdate_range("2010-01-01", periods=days, name="Date")
    codes = [f"{i:05d}" for i in range(stocks)]
    idx = pd.MultiIndex.from_product([dates, codes], names=["Date", "Code"])
    rng = np.random.default_rng(47)
    return {
        "raw_return_1day": pd.DataFrame({"Return": rng.normal(.001, .01, len(idx))}, index=idx),
        "beta_1day": pd.DataFrame({"Return": rng.uniform(.5, 1.5, len(idx))}, index=idx),
        "topix_return_1day": pd.DataFrame({"Return": rng.normal(0, .002, days)}, index=dates),
        "listed_info": pd.DataFrame({"Sector17Code": "1", "Sector33Code": "0050"}, index=idx),
    }


def assert_exact(a, b):
    assert a.index.equals(b.index) and a.columns.equals(b.columns) and a.dtypes.equals(b.dtypes)
    for col in a:
        if pd.api.types.is_numeric_dtype(a[col]):
            assert np.array_equal(a[col].to_numpy().view(np.uint64), b[col].to_numpy().view(np.uint64))
        else:
            pd.testing.assert_series_equal(a[col], b[col], check_exact=True)


@pytest.mark.parametrize("source", list(sm.INPUT_COLUMNS) + ["ALL", "TRUNCATION"])
def test_full_builder_future_mutation(source):
    data = fixture_inputs()
    f = sm.build_features(data)
    cutoff = f.index.get_level_values("Date").unique()[95]
    changed = {name: frame.copy() for name, frame in data.items()}
    for name, frame in changed.items():
        future = frame.index.get_level_values("Date") > cutoff
        if source == "TRUNCATION":
            changed[name] = frame.loc[~future]
        elif source in [name, "ALL"]:
            frame.loc[future] = "future" if name == "listed_info" else 1e6
            changed[name] = frame.drop(frame.index[future][::9])
    prefix = f.loc[f.index.get_level_values("Date") <= cutoff]
    got = sm.build_features(changed).loc[prefix.index]
    assert_exact(prefix, got)
    for candidate in sm.CANDIDATES:
        assert_exact(sm.score(prefix, candidate).to_frame(), sm.score(got, candidate).to_frame())


def test_loo_minimum_and_own_independence():
    data = fixture_inputs(days=1, stocks=12)
    idx = data["raw_return_1day"].index
    stock = pd.Series(np.arange(12, dtype=float), index=idx)
    sector = pd.Series("1", index=idx)
    mom, n, breadth = sm.peer_components(stock, sector, 10)
    for pos in range(12):
        peers = stock.drop(idx[pos])
        assert mom.iloc[pos] == pytest.approx(peers.mean())
        assert n.iloc[pos] == 11
        assert breadth.iloc[pos] == pytest.approx((peers > 0).mean())
    changed = stock.copy(); changed.iloc[0] = 100.
    assert sm.peer_components(changed, sector, 10)[0].iloc[0] == mom.iloc[0]
    stock.iloc[0] = np.nan
    assert sm.peer_components(stock, sector, 11)[0].iloc[0] == pytest.approx(stock.mean())
    assert sm.peer_components(stock, sector, 11)[0].iloc[1:].isna().all()


def test_stock_definition_matches_existing_and_relisting():
    data = fixture_inputs(days=230)
    f = sm.build_features(data)
    pd.testing.assert_series_equal(old.centered_rank(f.StockMom60).rename("res60s1"), old.build_momentum(data))
    assert f.StockMom60.groupby("Code").head(60).isna().all()
    assert f.StockMom60.groupby("Code").nth(60).notna().all()
    dates = data["raw_return_1day"].index.get_level_values("Date").unique()
    for name in ["raw_return_1day", "beta_1day", "listed_info"]:
        frame = data[name]
        keep = ~((frame.index.get_level_values("Code") == "00000") & frame.index.get_level_values("Date").isin(dates[80:110]))
        data[name] = frame.loc[keep]
    f = sm.build_features(data)
    assert f.loc[(slice(dates[110], dates[169]), "00000"), "StockMom60"].isna().all()
    assert np.isfinite(f.loc[(dates[170], "00000"), "StockMom60"])


def test_pit_changes_missing_unknown_and_absent_membership():
    data = fixture_inputs()
    dates = data["raw_return_1day"].index.get_level_values("Date").unique()
    cutoff = dates[90]
    data["listed_info"].loc[(cutoff, "00000"), ["Sector17Code", "Sector33Code"]] = ["99", "9999"]
    data["listed_info"] = data["listed_info"].drop((cutoff, "00001"))
    f = sm.build_features(data)
    assert f.loc[(cutoff, ["00000", "00001"]), "Sector33Mom"].isna().all()
    assert f.loc[(cutoff, "00002"), "Peer33Count"] == 21
    # A stock present only in the listed table cannot enter the peer universe.
    extra = pd.DataFrame({"Sector17Code": "1", "Sector33Code": "0050"},
                         index=pd.MultiIndex.from_tuples([(cutoff, "99999")], names=["Date", "Code"]))
    data["listed_info"] = pd.concat([data["listed_info"], extra])
    assert_exact(f, sm.build_features(data))
    data["listed_info"].loc[(dates[100], "00002"), "Sector33Code"] = "different"
    got = sm.build_features(data)
    assert_exact(f.loc[f.index.get_level_values("Date") < dates[100]], got.loc[got.index.get_level_values("Date") < dates[100]])
    assert np.isnan(got.loc[(dates[100], "00002"), "Sector33Mom"])


def test_shuffle_determinism_decomposition_adapter_and_nonfinite(monkeypatch):
    data = fixture_inputs()
    data["raw_return_1day"].iloc[70, 0] = np.inf
    f = sm.build_features(data)
    assert_exact(f, sm.build_features(data))
    assert_exact(f, sm.build_features({n: x.sample(frac=1, random_state=2) for n, x in data.items()}))
    assert np.allclose(f.StockMom60, f.Sector33Mom + f.Rel33Mom, atol=1e-15, equal_nan=True)
    monkeypatch.setattr(submission, "load_train", lambda path: data)
    for candidate in sm.CANDIDATES:
        score = sm.score(f, candidate)
        assert score.index.equals(data["raw_return_1day"].index)
        assert np.isfinite(score).all()
        assert_exact(score.to_frame(), submission.predict("unused", candidate))
    with pytest.raises(ValueError):
        sm.score(f, "RESCUE")


def test_duplicate_index_rejected():
    data = fixture_inputs()
    data["listed_info"] = pd.concat([data["listed_info"], data["listed_info"].iloc[:1]])
    with pytest.raises(ValueError, match="unique"):
        sm.build_features(data)


def test_source_scan_accounting_purge_and_bootstrap():
    from research.experiments import sector_momentum as driver
    from research import evaluation
    assert driver.source_scan()["status"] == "PASS"
    data = fixture_inputs(days=540)
    f = sm.build_features(data)
    signal = sm.score(f)
    target = data["raw_return_1day"].Return.copy()
    target.iloc[70] = np.nan
    daily, h, audit = driver.account(signal, target)
    assert audit["weight_bitwise"] and audit["net_bitwise"]
    assert np.allclose(h.net.groupby("Date").sum(), daily.net, atol=1e-15)
    calendar = daily.index
    dates, purge = driver.fold_dates(calendar, [2011])
    assert len(dates) == len(calendar[calendar.year == 2011]) - 2
    assert purge[0]["status"] == "PASS"
    boot = evaluation.bootstrap_delta(daily.net, daily.net, seed=3, reps=50, block=20)
    assert boot["low"] == boot["high"] == 0
