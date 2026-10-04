import numpy as np
import pandas as pd
import pytest
from stock_comp_2026.strategies.dm_industry_momentum_stock_reversal17 import features as im, submission
from research.experiments import industry_granularity_robustness as driver
from tests.strategies.dm_industry_momentum_stock_reversal.test_features import inputs as parent_inputs


def inputs(days=200):
    data = parent_inputs(days=days)
    data["listed_info"] = data["listed_info"].rename(columns={"Sector33Code":"Sector17Code"})
    return data


@pytest.mark.parametrize("cut",[30,90,160])
@pytest.mark.parametrize("source",list(im.INPUT_COLUMNS)+["ALL","TRUNCATION"])
def test_full_history_final_prefix_17(source,cut):
    data = inputs();f,h = im.build_features(data,True);cutoff = f.index.get_level_values("Date").unique()[cut]
    changed = dict(data)
    for i,(name,frame) in enumerate(data.items()):
        if source=="TRUNCATION":changed[name]=frame.loc[frame.index.get_level_values("Date")<=cutoff]
        elif source in [name,"ALL"]:changed[name]=driver.parent.mutate(frame,name,cutoff,i+15)
    got,gh = im.build_features(changed,True)
    idx = f.index[f.index.get_level_values("Date")<=cutoff]
    driver.exact(f.loc[idx],got.loc[got.index.get_level_values("Date")<=cutoff])
    driver.exact(h.loc[h.index.get_level_values("Date")<=cutoff],gh.loc[gh.index.get_level_values("Date")<=cutoff])
    driver.exact(im.score(f.loc[idx]),im.score(got.loc[idx]))


def test_only_classification_source_change_and_exact_parent_golden(monkeypatch):
    data = inputs();f,h = im.build_features(data,True)
    assert driver.classification_only_parity(data,f,h)["bitwise_same_classifications"]
    assert driver.parent.primitive_parity(data,f)["MOM60_bitwise"]
    assert driver.source_scan()["status"]=="PASS"
    assert list(im.CANDIDATES)==[driver.CANDIDATE]
    monkeypatch.setattr(submission,"load_train",lambda _:data)
    driver.exact(im.score(f).to_frame(),submission.predict("unused"))
    for forbidden in ["WITHIN17_REV20","STOCK_REV20",driver.CONTROL,"RESCUE"]:
        with pytest.raises(ValueError):im.score(f,forbidden)


def test_pit_historical_mean_minimum5_gaps_and_skip():
    data = inputs(days=70);dates = data["topix_return_1day"].index
    data["topix_return_1day"].Return = 0.
    data["raw_return_1day"].Return = np.tile([.01]*6+[.03]*6,70)
    data["listed_info"].loc[(slice(dates[30],None),"00006"),"Sector17Code"] = "0050"
    f,h = im.build_features(data,True)
    assert h.loc[(dates[29],"0050"),"IndustryResidualReturn"]==pytest.approx(.01)
    assert h.loc[(dates[30],"0050"),"IndustryResidualReturn"]==pytest.approx(.09/7)
    assert f.loc[(dates[30],"00006"),"IndustryMom20"]==pytest.approx(.20)
    assert f.loc[(dates[30],"00006"),"Within17Rev20"]==pytest.approx(-.40)
    assert f.loc[(dates[20],"00000"),"StockMom20"]==pytest.approx(.20)
    assert np.isnan(f.loc[(dates[19],"00000"),"StockMom20"])
    data = inputs(days=70)
    data["raw_return_1day"].loc[(dates[30],"00000"),"Return"] = np.nan
    _,h = im.build_features(data,True)
    assert h.loc[(dates[30],"0050"),"FiniteMembers"]==5
    assert np.isfinite(h.loc[(dates[30],"0050"),"IndustryResidualReturn"])
    data["raw_return_1day"].loc[(dates[30],"00001"),"Return"] = np.inf
    f,h = im.build_features(data,True)
    assert h.loc[(dates[30],"0050"),"FiniteMembers"]==4
    assert h.loc[(slice(dates[31],dates[50]),"0050"),"IndustryMom20"].isna().all()
    assert np.isfinite(h.loc[(dates[51],"0050"),"IndustryMom20"])
    assert np.isfinite(f[driver.CANDIDATE]).all()


def test_coarsening_can_improve_coverage_without_extra_performance_candidate():
    data = inputs(days=60)
    # Three4-member industries become two6-member sectors, with min5 unchanged.
    fine = dict(data)
    fine["listed_info"] = pd.DataFrame({"Sector33Code":np.tile(["A"]*4+["B"]*4+["C"]*4,60)},index=data["listed_info"].index)
    coarse = dict(data)
    coarse["listed_info"] = pd.DataFrame({"Sector17Code":np.tile(["X"]*6+["Y"]*6,60)},index=data["listed_info"].index)
    f17 = im.build_features(coarse);f33 = driver.im33.build_features(fine)
    assert f33.Within33Rev20.isna().all()
    assert f17.Within17Rev20.loc[f17.index.get_level_values("Date")==data["topix_return_1day"].index[-1]].notna().all()
    for col in ["ResidualReturn","StockMom20","MOM60"]:driver.exact(f17[col],f33[col])


def test_shuffle_reset_missing_sector_and_duplicates():
    data = inputs(days=240);dates = data["topix_return_1day"].index
    for name in ["raw_return_1day","beta_1day","listed_info"]:
        x = data[name];keep = ~((x.index.get_level_values("Code")=="00000")&x.index.get_level_values("Date").isin(dates[90:120]));data[name] = x.loc[keep]
    data["listed_info"].loc[(dates[150],"00001"),"Sector17Code"] = "9999"
    f,h = im.build_features(data,True);got,gh = im.build_features({n:x.sample(frac=1,random_state=7) for n,x in data.items()},True)
    driver.exact(f,got);driver.exact(h,gh)
    assert f.loc[(slice(dates[120],dates[139]),"00000"),"StockMom20"].isna().all()
    assert np.isfinite(f.loc[(dates[140],"00000"),"StockMom20"])
    # Reset EWMA starts from today's transformed combined score. A missing own
    # history neutralizes Within only; its available industry component remains.
    assert f.loc[(dates[120],"00000"),driver.CANDIDATE]==im.centered_rank(f.CombinedRaw).loc[(dates[120],"00000")]
    assert np.isnan(f.loc[(dates[150],"00001"),"Within17Rev20"])
    data["listed_info"] = pd.concat([data["listed_info"],data["listed_info"].iloc[:1]])
    with pytest.raises(ValueError,match="unique"):im.build_features(data)


def test_account_csv_roundtrip_and_same_partition_concentration(tmp_path):
    data = inputs(days=1350);f,h = im.build_features(data,True)
    reference = dict(data);reference["listed_info"] = data["listed_info"].rename(columns={"Sector17Code":"Sector33Code"})
    f33,h33 = driver.im33.build_features(reference,True)
    target = data["raw_return_1day"].Return.copy();target.iloc[1000] = np.nan
    signals = {driver.CANDIDATE:im.score(f),driver.CONTROL:f33[driver.CONTROL].rename("Return"),"MOM60":f.MOM60.rename("Return")}
    accounts,holdings = {},{}
    for name,s in signals.items():
        accounts[name],holdings[name],audit = driver.account(s,target)
        assert audit["weight_bitwise"] and audit["net_bitwise"]
        csv = tmp_path/f"{name}.csv";accounts[name].to_csv(csv)
        driver.exact(accounts[name],pd.read_csv(csv,index_col="Date",parse_dates=["Date"],float_precision="round_trip"))
    dates = f.index.get_level_values("Date").unique()
    driver.component_diagnostics({17:f,33:f33},{17:h,33:h33},target,dates,tmp_path)
    r = pd.read_csv(tmp_path/"component_incremental.csv")
    assert r.delta_rankic_17_minus33.abs().max()==0
    cover = driver.coverage({17:f,33:f33},dates,tmp_path)
    a = cover.loc[cover.granularity==17].reset_index(drop=True);b = cover.loc[cover.granularity==33].reset_index(drop=True)
    assert np.array_equal(a.raw_coverage,b.raw_coverage)
    # Shared concentration helper compares books on the SAME membership partition.
    partition = f[["Sector17Code"]].rename(columns={"Sector17Code":"Sector33Code"})
    driver.sector_concentration(partition,holdings,accounts,tmp_path)
    conc = pd.read_csv(tmp_path/"sector_concentration.csv")
    a = conc.loc[conc.strategy==driver.CANDIDATE,"mean_daily_HHI"].to_numpy()
    b = conc.loc[conc.strategy==driver.CONTROL,"mean_daily_HHI"].to_numpy()
    assert np.array_equal(a,b)


def test_stored_parquet_missing_payload_exception_is_scoped_and_finite_strict(tmp_path):
    data = inputs(days=80)
    f = im.build_features(data)
    path = tmp_path/"features.parquet";f.to_parquet(path);stored = pd.read_parquet(path)
    result = driver.stored_feature_parity(f,stored)
    assert result["defined_values_bitwise"] and result["NaN_masks_exact"]
    # NaN sign is a storage detail, while every finite change remains rejected.
    changed = stored.copy();col = "StockMom20";i = np.flatnonzero(changed[col].notna().to_numpy())[0]
    changed.iloc[i,changed.columns.get_loc(col)] = np.nextafter(changed.iloc[i,changed.columns.get_loc(col)],np.inf)
    with pytest.raises(AssertionError):driver.stored_feature_parity(f,changed)
    changed = stored.copy();changed.iloc[0,changed.columns.get_loc(col)] = 0.
    with pytest.raises(AssertionError):driver.stored_feature_parity(f,changed)
