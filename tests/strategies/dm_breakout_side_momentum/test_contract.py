import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal, assert_series_equal

from stock_comp_2026.strategies.dm_breakout_side_momentum import features, models, submission
from tests.strategies._breakout_fixtures import make_inputs, prefix_rows, suffix_rows


PACKAGE = Path(__file__).resolve().parents[3] / "stock_comp_2026/strategies/dm_breakout_side_momentum"
FORBIDDEN_INPUTS = {
    "AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose",
    "AdjustmentVolume", "raw_target", "target_1day", "target_1day_valid",
}


def test_source_firewall_and_causal_operations():
    for source_path in PACKAGE.glob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        for token in FORBIDDEN_INPUTS:
            assert token not in source, (source_path, token)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            assert node.func.attr not in {"bfill", "backfill"}, source_path
            if node.func.attr == "shift":
                periods = node.args[0] if node.args else next(
                    (kw.value for kw in node.keywords if kw.arg in {"periods", "period"}), None
                )
                assert isinstance(periods, ast.Constant) and type(periods.value) is int
                assert periods.value >= 0
            if node.func.attr == "rolling":
                assert not any(
                    kw.arg == "center"
                    and not (isinstance(kw.value, ast.Constant) and kw.value.value is False)
                    for kw in node.keywords
                )

    assert set(features.INPUT_COLUMNS) == {
        "raw_return_1day", "beta_1day", "topix_return_1day", "prices_daily_quotes"
    }
    assert all(
        column not in FORBIDDEN_INPUTS
        for columns in features.INPUT_COLUMNS.values()
        for column in columns
    )


@pytest.mark.parametrize("cut", [120, 260])
def test_all_inputs_future_mutation_and_truncation_are_prefix_invariant(cut):
    data = make_inputs()
    baseline = features.build_features(data)
    cutoff = data["topix_return_1day"].index[cut]

    mutated = {name: frame.copy() for name, frame in data.items()}
    for name, frame in mutated.items():
        mask = suffix_rows(frame, cutoff)
        for column in frame:
            if name == "prices_daily_quotes" and column == "AdjustmentFactor":
                frame.loc[mask, column] *= 1.25
            else:
                frame.loc[mask, column] = frame.loc[mask, column] * 3.0 + 0.17
    changed = features.build_features(mutated)
    prefix = baseline.index.get_level_values("Date") <= cutoff
    assert_frame_equal(baseline.loc[prefix], changed.loc[prefix], check_exact=True)

    truncated = {
        name: prefix_rows(frame, cutoff)
        for name, frame in data.items()
    }
    assert_frame_equal(baseline.loc[prefix], features.build_features(truncated), check_exact=True)


def test_split_adjustment_missing_values_and_invalid_factors():
    data = make_inputs()
    prices = features.split_safe_prices(data)
    raw = data["prices_daily_quotes"]
    split_date = raw.index.get_level_values("Date").unique()[-35]
    split_index = (split_date, "C0")
    assert raw.loc[split_index, "AdjustmentFactor"] == 0.5
    assert prices.loc[split_index, "close"] == raw.loc[split_index, "Close"] / 0.5
    after_split = (raw.index.get_level_values("Date") >= split_date) & (
        raw.index.get_level_values("Code") == "C0"
    )
    np.testing.assert_allclose(
        prices.loc[after_split, "close"].to_numpy(),
        (raw.loc[after_split, "Close"] / 0.5).to_numpy(),
        rtol=0,
        atol=0,
    )

    missing = {name: frame.copy() for name, frame in data.items()}
    missing_prices = missing["prices_daily_quotes"]
    missing_prices.loc[(raw.index[10]), ["High", "Low", "Close"]] = np.nan
    missing_prices.loc[raw.index[11], "High"] = np.inf
    missing_prices.loc[raw.index[12], "Low"] = -np.inf
    missing_prices.loc[raw.index[13], "Close"] = np.inf
    missing["raw_return_1day"].loc[raw.index[14], "Return"] = np.inf
    result = features.build_features(missing)
    assert not result.loc[raw.index[10], "high_available"]
    assert not result.loc[raw.index[10], "low_available"]
    assert np.isfinite(result[["res60s1", "new_high_rank", "new_low_rank"]].to_numpy()).all()
    for trial in models.TRIAL_IDS:
        assert np.isfinite(models.generate_signal(result, trial).to_numpy()).all()

    invalid = {name: frame.copy() for name, frame in data.items()}
    invalid["prices_daily_quotes"].iloc[4, invalid["prices_daily_quotes"].columns.get_loc("AdjustmentFactor")] = 0.0
    with pytest.raises(ValueError, match="finite and positive"):
        features.split_safe_prices(invalid)


def test_relisting_gap_resets_rolling_and_ewma_state():
    data = make_inputs(n_dates=380)
    index = data["raw_return_1day"].index
    dates = index.get_level_values("Date").unique()
    missing_dates = dates[150:181]
    for name, frame in data.items():
        if isinstance(frame.index, pd.MultiIndex):
            drop = (frame.index.get_level_values("Code") == "C0") & (
                frame.index.get_level_values("Date").isin(missing_dates)
            )
            data[name] = frame.loc[~drop]

    index = data["raw_return_1day"].index
    segment = features.segment_keys(index)[1]
    before = (dates[149], "C0")
    reentry = (dates[181], "C0")
    assert segment.loc[reentry] > segment.loc[before]

    values = pd.Series(0.7, index=index)
    values.loc[reentry] = 0.0
    assert features.smooth(values, alpha=0.25).loc[reentry] == 0.0

    built = features.build_features(data)
    assert not built.loc[reentry, "high_available"]
    assert not built.loc[reentry, "low_available"]
    assert built.loc[reentry, "res60s1"] == 0.0


def test_row_order_determinism_and_all_submission_trials(monkeypatch):
    data = make_inputs()
    baseline = features.build_features(data)
    shuffled = {
        name: frame.sample(frac=1.0, random_state=37)
        for name, frame in data.items()
    }
    assert_frame_equal(baseline, features.build_features(shuffled), check_exact=True)

    def loader(data_dir=".", split="train"):
        assert split == "train"
        return data

    monkeypatch.setattr(submission, "load_inputs", loader)
    for trial in models.TRIAL_IDS:
        expected = models.generate_signal(baseline, trial).rename("Return").to_frame()
        actual = submission.predict(trial_id=trial)
        again = submission.predict(trial_id=trial)
        assert_frame_equal(actual, expected, check_exact=True)
        assert_frame_equal(actual, again, check_exact=True)
        assert isinstance(actual.index, pd.MultiIndex)
        assert actual.index.names == ["Date", "Code"]
        assert actual.index.equals(baseline.index)
        assert list(actual.columns) == ["Return"]
        assert np.isfinite(actual.to_numpy()).all()

    with pytest.raises(ValueError, match="Unknown trial_id"):
        submission.predict(trial_id="unknown")
