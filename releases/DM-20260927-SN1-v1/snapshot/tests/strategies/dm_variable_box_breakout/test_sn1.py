import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from stock_comp_2026.evaluate_script import compute_weight
from research.experiments.sn1_valid_once import classify_result
from stock_comp_2026.strategies.dm_variable_box_breakout import features, sn1, submission


def raw_panel():
    dates = pd.bdate_range("2012-01-04", periods=24)
    codes = [f"{code:05d}" for code in range(10000, 10012)]
    index = pd.MultiIndex.from_product([dates, codes], names=["Date", "Code"])
    raw = pd.Series(0.0, index=index, name="raw", dtype="float64")
    for day, date in enumerate(dates):
        for code, ticker in enumerate(codes):
            if (day + code) % 7 == 0:
                raw.loc[(date, ticker)] = 0.50 + 0.02 * code
            elif (day + 2 * code) % 9 == 0:
                raw.loc[(date, ticker)] = -(0.50 + 0.015 * code)
    return raw


def weights(score):
    return compute_weight(score.rename("Return").to_frame()).iloc[:, 0]


def test_sn1_row_order_is_canonical_and_deterministic():
    raw = raw_panel()
    expected = sn1.score_from_raw(raw)["SIDE_SOURCE_SEPARATION"]
    shuffled = raw.sample(frac=1.0, random_state=20260927)
    actual = sn1.score_from_raw(shuffled)["SIDE_SOURCE_SEPARATION"]
    pd.testing.assert_series_equal(actual, expected, check_exact=True)
    pd.testing.assert_series_equal(weights(actual), weights(expected), check_exact=True)


def test_sn1_base_ewma_inversion_matches_direct_raw_rebuild():
    raw = raw_panel()
    base_score = sn1.ewma_by_listing(raw, sn1.HIGH_ALPHA).rename("BOX")
    recovered = sn1.rebuild_from_base_score(base_score)
    direct = sn1.score_from_raw(raw)
    np.testing.assert_allclose(
        recovered["SIDE_SOURCE_SEPARATION"].to_numpy(),
        direct["SIDE_SOURCE_SEPARATION"].to_numpy(),
        rtol=0.0,
        atol=2e-12,
    )
    pd.testing.assert_series_equal(
        weights(recovered["SIDE_SOURCE_SEPARATION"]),
        weights(direct["SIDE_SOURCE_SEPARATION"]),
        check_exact=True,
    )


def test_submission_candidate_comparison_returns_only_d_and_sn1(monkeypatch):
    raw = raw_panel()
    base_score = sn1.ewma_by_listing(raw, sn1.HIGH_ALPHA).rename("BOX")
    monkeypatch.setattr(
        submission.bidirectional,
        "generate_signal",
        lambda _x, _predictions, alpha: base_score,
    )
    x = pd.DataFrame(index=raw.index)
    candidates = submission.candidate_scores_from_predictions(x, {})
    replay = sn1.rebuild_from_base_score(base_score)

    assert tuple(candidates) == ("D_LOW_FAST_ONLY", "SIDE_SOURCE_SEPARATION")
    pd.testing.assert_series_equal(
        candidates["D_LOW_FAST_ONLY"], replay["D_LOW_FAST_ONLY"], check_exact=True
    )
    pd.testing.assert_series_equal(
        candidates["SIDE_SOURCE_SEPARATION"],
        replay["SIDE_SOURCE_SEPARATION"],
        check_exact=True,
    )


def test_valid_decision_uses_only_preregistered_relative_rules():
    overall = pd.DataFrame([
        {"candidate": "D_LOW_FAST_ONLY", "annual_net_return": 0.02, "net_sharpe": 0.8,
         "annual_gross_return": 0.03, "gross_sharpe": 0.9, "annual_long_net": 0.01,
         "long_net_sharpe": 0.7},
        {"candidate": "SIDE_SOURCE_SEPARATION", "annual_net_return": 0.025, "net_sharpe": 0.9,
         "annual_gross_return": 0.035, "gross_sharpe": 1.0, "annual_long_net": 0.02,
         "long_net_sharpe": 0.8},
    ])
    annual = pd.DataFrame([
        {"candidate": "D_LOW_FAST_ONLY", "period": "2020", "annual_net_return": 0.01},
        {"candidate": "SIDE_SOURCE_SEPARATION", "period": "2020", "annual_net_return": 0.011},
        {"candidate": "D_LOW_FAST_ONLY", "period": "2021", "annual_net_return": 0.02},
        {"candidate": "SIDE_SOURCE_SEPARATION", "period": "2021", "annual_net_return": 0.019},
        {"candidate": "D_LOW_FAST_ONLY", "period": "2022 partial", "annual_net_return": 0.03},
        {"candidate": "SIDE_SOURCE_SEPARATION", "period": "2022 partial", "annual_net_return": 0.031},
    ])
    bootstrap = {"delta_net_sharpe_ci_low": 0.01, "delta_net_annual_return_ci_low": 0.001}
    assert classify_result(overall, annual, bootstrap)["category"] == "PASS"
    bootstrap["delta_net_sharpe_ci_low"] = 0.0
    assert classify_result(overall, annual, bootstrap)["category"] == "MIXED"
    overall.loc[1, "annual_net_return"] = 0.01
    overall.loc[1, "net_sharpe"] = 0.7
    assert classify_result(overall, annual, bootstrap)["category"] == "FAIL"


def test_sn1_saved_score_round_trip_preserves_values_and_weights(tmp_path):
    raw = raw_panel()
    score = sn1.score_from_raw(raw)["SIDE_SOURCE_SEPARATION"]
    path = tmp_path / "sn1_score.parquet"
    score.rename("Return").to_frame().to_parquet(path)
    loaded = pd.read_parquet(path)["Return"].sort_index()
    np.testing.assert_array_equal(loaded.to_numpy(), score.to_numpy())
    pd.testing.assert_series_equal(weights(loaded), weights(score), check_exact=True)


def test_sn1_preserves_directional_state_signs():
    result = sn1.score_from_raw(raw_panel())
    assert result["high_state"].ge(0.0).all()
    assert result["low_state"].le(0.0).all()
    assert np.isfinite(result["SIDE_SOURCE_SEPARATION"].to_numpy()).all()


def test_official_later_split_path_uses_only_train_labels(monkeypatch, tmp_path):
    dates = pd.DatetimeIndex(np.concatenate([
        pd.bdate_range(f"{year}-01-03", periods=60).to_numpy()
        for year in range(2008, 2014)
    ]))
    codes = [f"{code:05d}" for code in range(10000, 10020)]
    index = pd.MultiIndex.from_product([dates, codes], names=["Date", "Code"])
    row = np.arange(len(index), dtype=float)
    code = index.get_level_values("Code").astype(int).to_numpy() - 10000
    x = pd.DataFrame({
        "box_duration": 20.0 + row % 7,
        "box_width_atr": 1.0 + row % 5 / 10.0,
        "close_position": 0.2 + row % 6 / 10.0,
        "relative_strength_60": np.sin(row / 19.0),
        "distance_to_prior_high": -0.01 - row % 5 / 1000.0,
        "distance_to_prior_low": -0.01 - (row + 2.0) % 5 / 1000.0,
        "new_high_excess": np.where(code < 10, 0.01 + row % 7 / 1000.0, 0.0),
        "new_low_excess": np.where(code >= 10, 0.01 + row % 9 / 1000.0, 0.0),
        "high_available": True,
        "low_available": True,
    }, index=index).sort_index()
    train_mask = x.index.get_level_values("Date").year < 2013
    x_train = x.loc[train_mask]
    x_later = x.loc[~train_mask]
    target = pd.Series(
        np.cos(row / 23.0) * 0.01 + code * 0.00001,
        index=index,
        name="Return",
    ).loc[x_train.index]
    panels = {
        "raw_return_1day": pd.DataFrame(
            {"Return": 0.0}, index=x.index
        )
    }
    train_panels = {
        "raw_return_1day": panels["raw_return_1day"].reindex(x_train.index)
    }
    later_panels = {
        "raw_return_1day": panels["raw_return_1day"].reindex(x_later.index)
    }
    reads = []

    def fake_load_inputs(directory, split="train"):
        return train_panels if split == "train" else later_panels

    built = 0

    def fake_build_features(input_panels):
        nonlocal built
        built += 1
        return x_train if built == 1 else x

    def fake_read_parquet(path, *args, **kwargs):
        reads.append(str(path))
        if str(path).endswith("target_1day_train.parquet"):
            return target.to_frame("Return")
        raise AssertionError(f"Unexpected data read: {path}")

    monkeypatch.setattr(features, "load_inputs", fake_load_inputs)
    monkeypatch.setattr(features, "build_features", fake_build_features)
    monkeypatch.setattr(pd, "read_parquet", fake_read_parquet)
    result = submission.predict(data_dir=tmp_path, split="valid")
    assert result.index.equals(x_later.index)
    assert result.shape == (len(x_later), 1)
    assert np.isfinite(result.to_numpy()).all()
    assert reads == [str(tmp_path / "target_1day_train.parquet")]


def test_competition_top_level_submission_import():
    strategy_dir = (
        Path(__file__).resolve().parents[3]
        / "stock_comp_2026/strategies/dm_variable_box_breakout"
    )
    result = subprocess.run(
        [sys.executable, "-c", "import submission; assert callable(submission.predict)"],
        cwd=strategy_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
