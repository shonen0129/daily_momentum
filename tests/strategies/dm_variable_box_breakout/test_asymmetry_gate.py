import numpy as np
import pandas as pd

from research.experiments import box_asymmetry_gate as study


def test_low_no_carry_keeps_event_day_contribution_and_stops_age_one():
    dates = pd.bdate_range("2014-01-02", periods=5)
    index = pd.MultiIndex.from_product([dates, ["10000"]], names=["Date", "Code"])
    raw = pd.Series([1.0, 0.0, -0.8, 0.0, 0.0], index=index, name="raw")

    got = study.asymmetric_score_from_raw(raw, alpha=0.25)

    assert np.isclose(got.iloc[0], 1.0)
    assert np.isclose(got.iloc[1], 0.75)
    assert np.isclose(got.iloc[2], 0.5625 - 0.2)
    assert np.isclose(got.iloc[3], 0.421875)
    assert np.isclose(got.iloc[4], 0.31640625)


def test_box_eligibility_rejects_absent_and_boundary_width():
    index = pd.MultiIndex.from_product(
        [pd.bdate_range("2014-01-02", periods=4), ["10000"]],
        names=["Date", "Code"],
    )
    x = pd.DataFrame({
        "box_duration": [0.0, 10.0, 10.0, 10.0],
        "box_width_atr": [np.nan, 1.0, 3.0, 2.99],
    }, index=index)

    assert study.eligible_box_mask(x).tolist() == [False, True, False, True]


def test_official_first_tie_break_assigns_zero_score_to_both_tails_by_code():
    date = pd.Timestamp("2014-01-02")
    codes = [f"{i:05d}" for i in range(10)]
    index = pd.MultiIndex.from_product([[date], codes], names=["Date", "Code"])
    values = np.zeros(10)
    values[8] = -1.0
    values[9] = 1.0
    score = pd.Series(values, index=index, name="score")

    weights, q = study.quintile_weights(score)

    assert q.loc[(date, "00000")] == 0
    assert q.loc[(date, "00007")] == 4
    assert q.loc[(date, "00008")] == 0
    assert q.loc[(date, "00009")] == 4
    assert weights.loc[(date, "00000")] < 0.0
    assert weights.loc[(date, "00007")] > 0.0


def test_short_scaling_preserves_long_weights_and_recomputes_net_exposure():
    index = pd.MultiIndex.from_product(
        [pd.bdate_range("2014-01-02", periods=1), [f"{i:05d}" for i in range(10)]],
        names=["Date", "Code"],
    )
    score = pd.Series(np.arange(10, dtype=float), index=index, name="score")
    weight, q = study.quintile_weights(score)

    scaled = study.scale_short(weight, 0.25)

    np.testing.assert_array_equal(scaled.where(weight.gt(0.0)), weight.where(weight.gt(0.0)))
    np.testing.assert_allclose(scaled.where(weight.lt(0.0)), weight.where(weight.lt(0.0)) * 0.25)
    assert scaled.sum() > weight.sum()
    assert q.nunique() == 5


def test_score_source_fractions_keep_zero_tie_break_as_an_explicit_class():
    date = pd.Timestamp("2014-01-02")
    index = pd.MultiIndex.from_product([[date], [f"{i:05d}" for i in range(10)]], names=["Date", "Code"])
    score = pd.Series([0.0, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, -0.7, 0.0], index=index)
    _, q = study.quintile_weights(score)
    components = pd.DataFrame(0.0, index=index, columns=list(study.AGE_CATEGORIES))
    components.loc[(date, "00002"), "high_event_day"] = 0.2
    components.loc[(date, "00008"), "low_age_5_plus"] = -0.7

    fractions = study.component_fractions(score, components, q)

    np.testing.assert_allclose(fractions.sum(axis=1).to_numpy(), 1.0)
    assert fractions.loc[(date, "00000"), "score_zero_tail_tie_break"] == 1.0
    assert fractions.loc[(date, "00008"), "low_age_5_plus"] == 1.0


def test_inner_zero_quintiles_remain_code_order_tie_break_holdings():
    date = pd.Timestamp("2014-01-02")
    index = pd.MultiIndex.from_product([[date], [f"{i:05d}" for i in range(5)]], names=["Date", "Code"])
    score = pd.Series(0.0, index=index)
    q = pd.Series([0, 1, 2, 3, 4], index=index)
    components = pd.DataFrame(0.0, index=index, columns=list(study.AGE_CATEGORIES))

    fractions = study.component_fractions(score, components, q)

    assert fractions.loc[(date, "00000"), "score_zero_tail_tie_break"] == 1.0
    assert fractions.loc[(date, "00001"), "score_zero_non_tail_tie_break"] == 1.0
    assert fractions.loc[(date, "00003"), "score_zero_non_tail_tie_break"] == 1.0


def test_sector_tail_summary_groups_point_in_time_sector_labels():
    date = pd.Timestamp("2014-01-02")
    index = pd.MultiIndex.from_product([[date], [f"{i:05d}" for i in range(10)]], names=["Date", "Code"])
    score = pd.Series(np.arange(10, dtype=float), index=index, name="score")
    weights, q = study.quintile_weights(score)
    sector = pd.DataFrame({
        "Sector33Code": ["01"] * 5 + ["02"] * 5,
        "Sector33CodeName": ["A"] * 5 + ["B"] * 5,
        "Sector17Code": ["1"] * 10,
        "Sector17CodeName": ["T"] * 10,
    }, index=index)

    rows = study.sector_outputs("S", score, weights, q, sector)

    assert len(rows) == 2
    assert {row["tail"] for row in rows} == {"Q1", "Q5"}
    assert all(np.isfinite(row["gross_weight_share"]) for row in rows)


def test_yearly_attribution_reconciles_fractional_stock_days_and_turnover():
    dates = pd.bdate_range("2014-01-02", periods=2)
    index = pd.MultiIndex.from_product([dates, ["10000", "20000"]], names=["Date", "Code"])
    detail = pd.DataFrame({
        "strategy": "S",
        "portfolio_side": ["Long", "Short"] * 2,
        "weight": [0.1, -0.1] * 2,
        "primary_source": ["high_event_day", "score_zero_tail_tie_break"] * 2,
    }, index=index)
    for category in study.CATEGORIES:
        detail[f"fraction_{category}"] = 0.0
    detail.loc[(slice(None), "10000"), "fraction_high_event_day"] = 1.0
    detail.loc[(slice(None), "20000"), "fraction_score_zero_tail_tie_break"] = 1.0
    daily = pd.DataFrame([
        {"Date": date, "strategy": "S", "side": side, "category": category,
         "gross": 0.001, "cost": 0.0001, "net": 0.0009, "turnover": 0.05 / len(study.CATEGORIES)}
        for date in dates for side in ("long", "short") for category in study.CATEGORIES
    ])

    result = study.yearly_category_attribution(detail, daily)

    assert result.groupby("side").held_stock_days_fractional.sum().to_dict() == {"long": 2.0, "short": 2.0}
    np.testing.assert_allclose(result.groupby("side").turnover_share_of_sleeve.sum().to_numpy(), [1.0, 1.0])


def test_code_order_correlation_is_averaged_within_each_date():
    dates = pd.bdate_range("2014-01-02", periods=2)
    index = pd.MultiIndex.from_product([dates, [f"{i:05d}" for i in range(4)]], names=["Date", "Code"])
    score = pd.Series(0.0, index=index)
    q = pd.Series([0, 0, 3, 4, 2, 2, 2, 2], index=index)

    result = study.zero_code_order_metrics(score, q)

    assert result["zero_code_order_spanning_days"] == 1
    assert result["zero_code_order_spearman_q"] > 0.9


def test_zero_sector_pnl_is_annualized_over_all_evaluation_days():
    dates = pd.bdate_range("2014-01-02", periods=2)
    codes = [f"{i:05d}" for i in range(10)]
    index = pd.MultiIndex.from_product([dates, codes], names=["Date", "Code"])
    score = np.tile(np.arange(10, dtype=float), 2)
    score[:2] = 0.0
    score[10:12] = 0.0
    q = np.tile(np.arange(10, dtype=np.int8) // 2, 2)
    q[:2] = 0
    q[10:12] = 0
    weight = np.tile(np.array([-0.1, -0.1, -0.05, -0.05, 0.0, 0.0, 0.05, 0.05, 0.1, 0.1]), 2)
    sectors = np.tile(np.array(["A", "A", "A", "A", "A", "B", "B", "B", "B", "B"]), 2)
    sectors[10:12] = "B"
    detail = pd.DataFrame({
        "strategy": "S", "score": score, "score_zero": score == 0.0, "q": q, "weight": weight,
        "portfolio_side": np.where(weight < 0.0, "Short", np.where(weight > 0.0, "Long", "Flat")),
        "Sector33Code": sectors, "Sector33CodeName": sectors,
    }, index=index)
    target = pd.Series(0.0, index=index)
    target.loc[(dates[0], "00000")] = 0.01
    target.loc[(dates[0], "00001")] = 0.01

    result = study.zero_sector_bias(detail, target)
    sector_a_q1 = result.loc[result.Sector33Code.eq("A") & result["tail"].eq("Q1")].iloc[0]

    np.testing.assert_allclose(sector_a_q1.annual_tail_zero_gross_pnl, -0.252)
    np.testing.assert_allclose(sector_a_q1.mean_daily_tail_zero_sector_share, 0.5)
