import inspect
import numpy as np
import pandas as pd
import pytest
from stock_comp_2026.strategies.dm_industry_momentum_stock_reversal import features as im, primitives, submission
from stock_comp_2026.strategies.dm_trainonly import features as old
from research.experiments import industry_momentum_stock_reversal as driver


def inputs(days=200, stocks=12):
    dates = pd.bdate_range("2011-01-03", periods=days, name="Date")
    index = pd.MultiIndex.from_product([dates, [f"{i:05d}" for i in range(stocks)]], names=["Date", "Code"])
    rng = np.random.default_rng(72)
    sectors = np.tile(["0050"]*6+["1050"]*(stocks-6), days)
    return {"raw_return_1day": pd.DataFrame({"Return": rng.normal(.001, .01, len(index))}, index=index),
            "beta_1day": pd.DataFrame({"Return": 1.}, index=index),
            "topix_return_1day": pd.DataFrame({"Return": rng.normal(0, .002, len(dates))}, index=dates),
            "listed_info": pd.DataFrame({"Sector33Code": sectors}, index=index)}


@pytest.mark.parametrize("cut", [30, 90, 160])
@pytest.mark.parametrize("source", list(im.INPUT_COLUMNS)+["ALL", "TRUNCATION"])
def test_future_mutation_full_history_and_final_bitwise(source, cut):
    data = inputs()
    f, h = im.build_features(data, True)
    cutoff = f.index.get_level_values("Date").unique()[cut]
    changed = dict(data)
    for i, (name, frame) in enumerate(data.items()):
        if source=="TRUNCATION":
            changed[name] = frame.loc[frame.index.get_level_values("Date") <= cutoff]
        elif source in [name, "ALL"]:
            changed[name] = driver.mutate(frame, name, cutoff, i+13)
    got, gh = im.build_features(changed, True)
    driver.exact(f.loc[f.index.get_level_values("Date") <= cutoff], got.loc[got.index.get_level_values("Date") <= cutoff])
    driver.exact(h.loc[h.index.get_level_values("Date") <= cutoff], gh.loc[gh.index.get_level_values("Date") <= cutoff])
    for name in im.CANDIDATES:
        idx = f.index[f.index.get_level_values("Date") <= cutoff]
        driver.exact(im.score(f.loc[idx], name), im.score(got.loc[idx], name))


def test_historical_pit_mean_not_current_membership_retrospective():
    data = inputs(days=60)
    dates = data["topix_return_1day"].index
    data["topix_return_1day"].Return = 0.
    data["raw_return_1day"].Return = np.tile([.01]*6+[.03]*6, 60)
    # At30, move a high-return stock into the low-return industry.
    data["listed_info"].loc[(slice(dates[30], None), "00006"), "Sector33Code"] = "0050"
    f, h = im.build_features(data, True)
    assert h.loc[(dates[29], "0050"), "IndustryResidualReturn"]==pytest.approx(.01)
    assert h.loc[(dates[30], "0050"), "IndustryResidualReturn"]==pytest.approx(.09/7)
    assert f.loc[(dates[30], "00006"), "IndustryMom20"]==pytest.approx(.20)
    assert f.loc[(dates[30], "00006"), "StockMom20"]==pytest.approx(.60)
    assert f.loc[(dates[30], "00006"), "Within33Rev20"]==pytest.approx(-.40)
    # The switched stock receives the old industry's actual historical mean,
    # not an average recomputed using today's7 members over the whole history.
    assert f.loc[(dates[31], "00006"), "IndustryMom20"]==pytest.approx(.19+.09/7)


def test_daily_minimum_finite5_self_inclusion_and_missing_calendar_window():
    data = inputs(days=65)
    dates = data["topix_return_1day"].index
    data["raw_return_1day"].loc[(dates[30], "00000"), "Return"] = np.nan
    f, h = im.build_features(data, True)
    assert h.loc[(dates[30], "0050"), "FiniteMembers"]==5
    assert np.isfinite(h.loc[(dates[30], "0050"), "IndustryResidualReturn"])
    data["raw_return_1day"].loc[(dates[30], "00001"), "Return"] = np.inf
    f, h = im.build_features(data, True)
    assert h.loc[(dates[30], "0050"), "FiniteMembers"]==4
    assert np.isnan(h.loc[(dates[30], "0050"), "IndustryResidualReturn"])
    assert np.isfinite(h.loc[(dates[30], "0050"), "IndustryMom20"])
    assert h.loc[(slice(dates[31], dates[50]), "0050"), "IndustryMom20"].isna().all()
    assert np.isfinite(h.loc[(dates[51], "0050"), "IndustryMom20"])
    assert np.isfinite(f[list(im.CANDIDATES)].to_numpy()).all()
    data = inputs(days=30)
    before = im.build_features(data)
    data["raw_return_1day"].loc[(data["topix_return_1day"].index[5], "00000"), "Return"] += .06
    after = im.build_features(data)
    delta = after.IndustryResidualReturn-before.IndustryResidualReturn
    assert delta.loc[(data["topix_return_1day"].index[5], "00000")]==pytest.approx(.01)


def test_skip_one_endpoint_and_fixed_transform_order():
    data = inputs(days=55)
    dates = data["topix_return_1day"].index
    data["topix_return_1day"].Return = 0.
    f = im.build_features(data)
    r = data["raw_return_1day"].Return.xs("00000", level="Code")
    assert np.isnan(f.loc[(dates[19], "00000"), "StockMom20"])
    assert f.loc[(dates[20], "00000"), "StockMom20"]==pytest.approx(r.iloc[:20].sum())
    data["raw_return_1day"].loc[(dates[20], "00000"), "Return"] = 1e5
    got = im.build_features(data)
    assert f.loc[(dates[20], "00000"), "StockMom20"]==got.loc[(dates[20], "00000"), "StockMom20"]
    assert f.loc[(dates[20], "00000"), "IndustryMom20"]==got.loc[(dates[20], "00000"), "IndustryMom20"]
    expected = primitives.smooth(primitives.centered_rank(primitives.centered_rank(f.IndustryMom20)+primitives.centered_rank(f.Within33Rev20)), .25)
    driver.exact(expected.rename("IND33_MOM_WITHIN_REV20"), f.IND33_MOM_WITHIN_REV20)
    driver.exact((-f.Within33Mom20).rename("Within33Rev20"), f.Within33Rev20)
    driver.exact(primitives.smooth(primitives.centered_rank(-f.StockMom20), .25).rename("STOCK_REV20"), f.STOCK_REV20)


def test_relisting_reset_exact_index_missing_sector_duplicates_adapter(monkeypatch):
    data = inputs(days=240)
    dates = data["topix_return_1day"].index
    for name in ["raw_return_1day", "beta_1day", "listed_info"]:
        frame = data[name]
        keep = ~((frame.index.get_level_values("Code")=="00000") & frame.index.get_level_values("Date").isin(dates[90:120]))
        data[name] = frame.loc[keep]
    data["listed_info"].loc[(dates[150], "00001"), "Sector33Code"] = "9999"
    data["listed_info"] = data["listed_info"].drop((dates[151], "00001"))
    f = im.build_features(data)
    assert f.loc[(slice(dates[120], dates[139]), "00000"), "StockMom20"].isna().all()
    assert f.loc[(dates[120], "00000"), "STOCK_REV20"]==0
    assert np.isfinite(f.loc[(dates[140], "00000"), "StockMom20"])
    assert np.isnan(f.loc[(dates[150], "00001"), "IndustryMom20"])
    assert np.isnan(f.loc[(dates[151], "00001"), "Within33Rev20"])
    assert f.index.equals(data["raw_return_1day"].index)
    monkeypatch.setattr(submission, "load_train", lambda _: data)
    for name in im.CANDIDATES:
        driver.exact(im.score(f, name).to_frame(), submission.predict("unused", name))
    with pytest.raises(ValueError):
        im.score(f, "FOURTH")
    data["raw_return_1day"] = pd.concat([data["raw_return_1day"], data["raw_return_1day"].iloc[:1]])
    with pytest.raises(ValueError, match="unique"):
        im.build_features(data)


def test_shuffle_determinism_and_unchanged_baseline():
    data = inputs()
    f, h = im.build_features(data, True)
    got, gh = im.build_features({n: x.sample(frac=1,random_state=7) for n,x in data.items()}, True)
    driver.exact(f, got); driver.exact(h, gh)
    assert driver.primitive_parity(data, f)["MOM60_bitwise"]
    assert driver.source_scan()["status"]=="PASS"
    for name in ["centered_rank", "smooth", "segment_keys"]:
        assert inspect.getsource(getattr(old,name))==inspect.getsource(getattr(primitives,name))


def test_all_missing_sector_and_flat_returns_neutral_finite():
    data = inputs(days=45)
    data["listed_info"].iloc[:,0] = "9999"
    f,h = im.build_features(data,True)
    assert h.empty and f.IndustryMom20.isna().all() and f.Within33Rev20.isna().all()
    assert f.WITHIN33_REV20.eq(0).all() and f.IND33_MOM_WITHIN_REV20.eq(0).all()
    data = inputs(days=45)
    data["raw_return_1day"].Return = 0.
    data["topix_return_1day"].Return = 0.
    f = im.build_features(data)
    assert f[list(im.CANDIDATES)].eq(0).all().all()


def test_accounting_and_mechanism_reconciliation(tmp_path):
    data = inputs(days=1350)
    f,h = im.build_features(data, True)
    target = data["raw_return_1day"].Return.copy()
    target.iloc[1000] = np.nan
    signals = {n: im.score(f,n) for n in im.CANDIDATES}
    signals["MOM60"] = f.MOM60.rename("Return")
    daily,holdings = {},{}
    for n,s in signals.items():
        daily[n],holdings[n],audit = driver.account(s,target)
        assert audit["weight_bitwise"] and audit["net_bitwise"]
        m = driver.metrics(daily[n])
        assert m["annual_short_net"]==pytest.approx(m["annual_short_gross"]-m["annual_short_cost"])
    # Diagnostics support the available scopes; empty later years are missing.
    dates = f.index.get_level_values("Date").unique()
    assert driver.mechanism(f,target,holdings,dates,tmp_path)["new_candidates"]==0
    driver.lead_lag(f,h,target,dates,tmp_path)
    lag = pd.read_csv(tmp_path/"lead_lag_descriptive.csv")
    assert lag.loc[lag.diagnostic=="LAG1_INDUSTRY_WITHIN_SECTOR","defined_days"].eq(0).all()
    driver.industry_diagnostics(f,h,target,dates,tmp_path)
    assert not pd.read_csv(tmp_path/"industry_momentum_diagnostics.csv").industry_only_portfolio_evaluated.any()
