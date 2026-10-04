import inspect
import numpy as np
import pandas as pd
import pytest
from stock_comp_2026.strategies.dm_hierarchical_momentum import features as hm, primitives, submission
from stock_comp_2026.strategies.dm_trainonly import features as old


def inputs(days=180, stocks=12):
    dates = pd.bdate_range("2011-01-03", periods=days, name="Date")
    index = pd.MultiIndex.from_product([dates, [f"{i:05d}" for i in range(stocks)]], names=["Date", "Code"])
    rng = np.random.default_rng(42)
    return {"raw_return_1day": pd.DataFrame({"Return": rng.normal(.001, .01, len(index))}, index=index),
            "beta_1day": pd.DataFrame({"Return": 1.}, index=index),
            "topix_return_1day": pd.DataFrame({"Return": rng.normal(0, .002, len(dates))}, index=dates),
            "listed_info": pd.DataFrame({"Sector33Code": "0050"}, index=index)}


def exact(a, b):
    pd.testing.assert_index_equal(a.index, b.index)
    assert a.columns.equals(b.columns) and a.dtypes.equals(b.dtypes)
    for col in a:
        if pd.api.types.is_numeric_dtype(a[col]):
            assert np.array_equal(a[col].to_numpy().view(np.uint64), b[col].to_numpy().view(np.uint64)), col
        else:
            pd.testing.assert_series_equal(a[col], b[col], check_exact=True)


def test_existing_primitive_source_and_raw_bitwise_parity(monkeypatch):
    data = inputs()
    for name in ["smooth", "segment_keys", "centered_rank"]:
        assert inspect.getsource(getattr(primitives, name)) == inspect.getsource(getattr(old, name))
    baseline = old.smooth(old.build_momentum(data), .25)
    # Observe the existing raw primitive before its final rank call; no source edit.
    with monkeypatch.context() as m:
        m.setattr(old, "centered_rank", lambda value: value)
        raw = old.build_momentum(data)
    f = hm.build_features(data)
    assert np.array_equal(f.StockMom60_raw.to_numpy().view(np.uint64), raw.to_numpy().view(np.uint64))
    assert np.array_equal(f.MOM60.to_numpy().view(np.uint64), baseline.to_numpy().view(np.uint64))


@pytest.mark.parametrize("source", list(hm.INPUT_COLUMNS) + ["ALL", "TRUNCATION"])
def test_future_mutation_prefix_all_ewma_and_zscores(source):
    data = inputs()
    f = hm.build_features(data)
    cutoff = f.index.get_level_values("Date").unique()[95]
    changed = {n: x.copy() for n, x in data.items()}
    for name, frame in changed.items():
        future = frame.index.get_level_values("Date") > cutoff
        if source == "TRUNCATION":
            changed[name] = frame.loc[~future]
        elif source in [name, "ALL"]:
            frame.loc[future] = "new_sector" if name == "listed_info" else 1e6
            changed[name] = frame.drop(frame.index[future][::11])
            if isinstance(frame.index, pd.MultiIndex):
                extra = frame.loc[future].iloc[::12].copy()
                extra.index = pd.MultiIndex.from_arrays([extra.index.get_level_values("Date"), ["FUTURE"]*len(extra)], names=["Date", "Code"])
                changed[name] = pd.concat([changed[name], extra])
    idx = f.index[f.index.get_level_values("Date") <= cutoff]
    got = hm.build_features(changed).loc[idx]
    exact(f.loc[idx], got)
    for name in hm.CANDIDATES:
        exact(hm.score(f.loc[idx], name).to_frame(), hm.score(got, name).to_frame())


def test_self_inclusion_common_constancy_minimum_and_raw_identity(monkeypatch):
    data = inputs(days=1, stocks=6)
    raw = pd.Series(np.arange(6, dtype=float), index=data["raw_return_1day"].index)
    monkeypatch.setattr(hm, "raw_momentum", lambda _: raw)
    f = hm.build_features(data)
    assert f.Sector33Common_raw.eq(2.5).all()
    assert f.Within33_raw.sum() == 0
    assert np.allclose(f.StockMom60_raw, f.Sector33Common_raw + f.Within33_raw, atol=1e-14)
    raw.iloc[0] += 6
    got = hm.build_features(data)
    assert got.Sector33Common_raw.eq(3.5).all()  # Own stock affects all common scores equally.
    raw.iloc[0] = np.nan
    assert hm.build_features(data).Sector33Common_raw.notna().all()  #5 finite members incl nonfinite-own row.
    raw.iloc[1] = np.nan
    assert hm.build_features(data).Sector33Common_raw.isna().all()  #4 finite is insufficient.


def test_ewma_identity_and_missing_neutralization_explanation():
    data = inputs()
    f = hm.build_features(data)
    error = f.StockMom60_ewm_diagnostic - f.Sector33Common_ewm - f.Within33_ewm
    assert error.abs().max() < 1e-14
    data["raw_return_1day"].iloc[100 * 12, 0] = np.nan
    f = hm.build_features(data)
    error = f.StockMom60_ewm_diagnostic - f.Sector33Common_ewm - f.Within33_ewm
    assert error.abs().max() > 1e-6  # Missing own stock while other sector members remain finite.
    assert (error - f.NeutralDefect_ewm).abs().max() < 1e-14


def test_pit_missing_unknown_membership_and_sector_history():
    data = inputs(stocks=12)
    dates = data["raw_return_1day"].index.get_level_values("Date").unique()
    date = dates[100]
    data["listed_info"].loc[(date, "00000"), "Sector33Code"] = "9999"
    data["listed_info"] = data["listed_info"].drop((date, "00001"))
    f = hm.build_features(data)
    assert f.loc[(date, ["00000", "00001"]), "Sector33Common_raw"].isna().all()
    extra = pd.DataFrame({"Sector33Code": ["0050"]}, index=pd.MultiIndex.from_tuples([(date, "NOT_IN_DATASET")], names=["Date", "Code"]))
    data["listed_info"] = pd.concat([data["listed_info"], extra])
    exact(f, hm.build_features(data))
    for d in dates[110:]:
        data["listed_info"].loc[(d, "00000"), "Sector33Code"] = "new_sector"
    got = hm.build_features(data)
    idx = f.index[f.index.get_level_values("Date") < dates[110]]
    exact(f.loc[idx], got.loc[idx])
    assert got.loc[(dates[110], "00000"), "Sector33Common_ewm"] == pytest.approx(.75*f.loc[(dates[109], "00000"), "Sector33Common_ewm"])


def test_relisting_reset_shuffle_determinism_and_adapter(monkeypatch):
    data = inputs(days=250)
    dates = data["raw_return_1day"].index.get_level_values("Date").unique()
    for name in ["raw_return_1day", "beta_1day", "listed_info"]:
        frame = data[name]
        keep = ~((frame.index.get_level_values("Code") == "00000") & frame.index.get_level_values("Date").isin(dates[100:130]))
        data[name] = frame.loc[keep]
    f = hm.build_features(data)
    assert f.loc[(slice(dates[130], dates[189]), "00000"), "StockMom60_raw"].isna().all()
    assert f.loc[(dates[130], "00000"), "Within33_ewm"] == 0
    assert np.isfinite(f.loc[(dates[190], "00000"), "StockMom60_raw"])
    exact(f, hm.build_features(data))
    exact(f, hm.build_features({n: x.sample(frac=1, random_state=8) for n, x in data.items()}))
    monkeypatch.setattr(submission, "load_train", lambda _: data)
    for name in hm.CANDIDATES:
        score = hm.score(f, name)
        assert np.isfinite(score).all()
        exact(score.to_frame(), submission.predict("unused", name))
    with pytest.raises(ValueError):
        hm.score(f, "RESCUE")


def test_zscore_zero_dispersion_exact_combined_and_duplicates():
    data = inputs(days=1)
    index = data["raw_return_1day"].index
    assert hm.zscore(pd.Series(1., index=index)).eq(0).all()
    f = hm.build_features(inputs())
    assert np.array_equal(f.Combined, f.Z_sector + f.Z_within)
    data["listed_info"] = pd.concat([data["listed_info"], data["listed_info"].iloc[:1]])
    with pytest.raises(ValueError, match="unique"):
        hm.build_features(data)


def test_source_and_diagnostic_accounting_routes(tmp_path):
    from research.experiments import hierarchical_momentum as d
    assert d.source_scan()["status"] == "PASS"
    data = inputs(days=300)
    f = hm.build_features(data)
    assert d.primitive_parity(data, f)["raw_primitive_bitwise"]
    assert d.identity_audit(f)["status"] == "PASS"
    signals = {name: hm.score(f, name) for name in hm.CANDIDATES}
    signals["MOM60"] = f.MOM60.rename("Return")
    daily, holdings = {}, {}
    target = data["raw_return_1day"].Return.copy()
    target.iloc[1400] = np.nan
    for name, score in signals.items():
        daily[name], holdings[name], audit = d.account(score, target)
        assert audit["weight_bitwise"] and audit["net_bitwise"]
    calendar = f.index.get_level_values("Date").unique()
    dates, _ = d.fold_dates(calendar, [2011, 2012])
    fe = f.loc[f.index.get_level_values("Date").isin(dates)]
    he = {n: h.loc[fe.index] for n, h in holdings.items()}
    accounts = {n: v.loc[dates] for n, v in daily.items()}
    assert d.tie_diagnostic(signals, fe, tmp_path)["perturbed_PL_evaluated"] is False
    ties = pd.read_csv(tmp_path/"tie_sensitivity.csv")
    assert ties.loc[ties.strategy=="HIER33_SECTOR", "exact_tie_share"].iloc[0] == 1
    d.rank_changes(signals, calendar, dates, tmp_path)
    # Diagnostic functions have fixed2011-2016 scopes; empty later scopes remain missing.
    d.common_alpha(fe, target.loc[fe.index], tmp_path)
    d.within_alpha(fe, target.loc[fe.index], he, tmp_path)
    d.agreement(fe, target.loc[fe.index], he, tmp_path)
    a = pd.read_csv(tmp_path/"agreement.csv")
    for strategy in ["MOM60", "HIER33_COMBINED"]:
        subset = a.loc[(a.strategy==strategy)&(a.scope=="POOLED")]
        assert subset.annual_net.sum() == pytest.approx(accounts[strategy].net.mean()*252)
