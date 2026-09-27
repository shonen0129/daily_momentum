import numpy as np
import pandas as pd

from research.experiments import box_asym_ewma as study
from research.experiments import box_asym_ewma_low_fast_only as low_fast
from research.experiments import box_asymmetry_gate as prior


def example_raw(periods=8):
    dates = pd.bdate_range("2014-01-02", periods=periods)
    index = pd.MultiIndex.from_product([dates, ["10000"]], names=["Date", "Code"])
    values = np.zeros(periods)
    values[0] = 1.0
    values[2] = -0.8
    values[5] = 0.4
    return pd.Series(values, index=index, name="raw")


def test_candidate_c_smooths_signed_sides_separately_and_recombines():
    raw = example_raw()
    got, high_raw, low_raw = study.asymmetric_score(raw, "C_ASYM_EWMA")
    expected = (prior.segment_ewma(high_raw, 0.15) + prior.segment_ewma(low_raw, 0.50))

    pd.testing.assert_series_equal(got, expected.rename("C_ASYM_EWMA"))
    assert got.iloc[3] != 0.0  # the negative Low event has nonzero carry after its event day
    assert np.isclose(got.iloc[3], prior.segment_ewma(high_raw, 0.15).iloc[3] - 0.2)


def test_candidate_c_age_components_reconstruct_and_split_event_ages():
    raw = example_raw()
    score, high_raw, low_raw = study.asymmetric_score(raw, "C_ASYM_EWMA")
    components = study.score_components(high_raw, low_raw, 0.15, 0.50)

    np.testing.assert_allclose(components.sum(axis=1), score, rtol=0.0, atol=1e-12)
    assert components.loc[raw.index[2], "low_event_day"] == -0.4
    assert components.loc[raw.index[3], "low_age_1_4"] == -0.2
    assert components.loc[raw.index[7], "high_age_1_4"] > 0.0


def test_asymmetric_ewma_is_future_prefix_invariant():
    raw = example_raw()
    mutated = raw.copy()
    cutoff = raw.index.get_level_values("Date")[4]
    future = raw.index.get_level_values("Date") > cutoff
    mutated.loc[future] = np.array([9.0, -7.0, 5.0])

    original_score, _, _ = study.asymmetric_score(raw, "score")
    mutated_score, _, _ = study.asymmetric_score(mutated, "score")
    prefix = raw.index.get_level_values("Date") <= cutoff
    pd.testing.assert_series_equal(original_score.loc[prefix], mutated_score.loc[prefix])


def test_low_no_carry_comparison_uses_event_day_only_component():
    raw = example_raw()
    high_raw, low_raw = prior.split_raw_sides(raw)
    score = prior.asymmetric_score_from_raw(raw, 0.25, "A_LOW_NO_CARRY")
    components = study.score_components(high_raw, low_raw, 0.25, 0.25, low_no_carry=True)

    np.testing.assert_allclose(components.sum(axis=1), score, rtol=0.0, atol=1e-12)
    assert components.low_age_1_4.eq(0.0).all()
    assert components.low_age_5_plus.eq(0.0).all()


def test_low_fast_only_preserves_box_high_state_exactly():
    raw = example_raw()
    box_score = prior.segment_ewma(raw, 0.25)
    d_score, d_high, d_low, high_raw, low_raw = low_fast.low_fast_score(raw, "D")
    original_high = prior.segment_ewma(high_raw, 0.25)
    original_low = prior.segment_ewma(low_raw, 0.25)

    pd.testing.assert_series_equal(d_high, original_high)
    pd.testing.assert_series_equal(d_score, (original_high + prior.segment_ewma(low_raw, 0.50)).rename("D"))
    pd.testing.assert_series_equal(box_score, (original_high + original_low).rename("raw"))
    assert d_low.iloc[3] == -0.2


def test_low_fast_only_components_reconstruct_d_without_changing_high_components():
    raw = example_raw()
    d_score, _, _, high_raw, low_raw = low_fast.low_fast_score(raw, "D")
    original = study.score_components(high_raw, low_raw, 0.25, 0.25)
    candidate = study.score_components(high_raw, low_raw, 0.25, 0.50)

    pd.testing.assert_frame_equal(
        original.loc[:, ["high_event_day", "high_age_1_4", "high_age_5_plus"]],
        candidate.loc[:, ["high_event_day", "high_age_1_4", "high_age_5_plus"]],
    )
    np.testing.assert_allclose(candidate.sum(axis=1), d_score, rtol=0.0, atol=1e-12)


def test_low_fast_only_transform_is_future_prefix_invariant():
    raw = example_raw()
    mutated = raw.copy()
    cutoff = raw.index.get_level_values("Date")[4]
    future = raw.index.get_level_values("Date") > cutoff
    mutated.loc[future] = [9.0, -7.0, 5.0]

    original, *_ = low_fast.low_fast_score(raw, "D")
    changed, *_ = low_fast.low_fast_score(mutated, "D")
    prefix = raw.index.get_level_values("Date") <= cutoff
    pd.testing.assert_series_equal(original.loc[prefix], changed.loc[prefix])
