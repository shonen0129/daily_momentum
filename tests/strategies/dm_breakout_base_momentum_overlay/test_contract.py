import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from stock_comp_2026.strategies.dm_breakout_base_momentum_overlay import (
    features, models, submission,
)
from stock_comp_2026.strategies.dm_breakout_side_momentum import features as side_features
from stock_comp_2026.strategies.dm_breakout_side_momentum import models as side_models
from tests.strategies._breakout_fixtures import make_inputs, prefix_rows, suffix_rows


PACKAGE = Path(__file__).resolve().parents[3] / "stock_comp_2026/strategies/dm_breakout_base_momentum_overlay"
FORBIDDEN_INPUTS = {
    "AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose",
    "AdjustmentVolume", "raw_target", "target_1day", "target_1day_valid",
}


def test_source_firewall_and_causal_operations():
    shared_feature_package = Path(side_features.__file__).resolve().parent
    source_paths = list(PACKAGE.glob("*.py")) + list(shared_feature_package.glob("*.py"))
    for source_path in source_paths:
        source = source_path.read_text(encoding="utf-8")
        for token in FORBIDDEN_INPUTS:
            assert token not in source, (source_path, token)
        for node in ast.walk(ast.parse(source)):
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


@pytest.mark.parametrize("cut", [120, 260])
def test_delegated_features_are_prefix_invariant_for_every_input(cut):
    data = make_inputs()
    baseline = features.build_features(data)
    assert_frame_equal(baseline, side_features.build_features(data), check_exact=True)
    shuffled = {
        name: panel.sample(frac=1.0, random_state=41)
        for name, panel in data.items()
    }
    assert_frame_equal(baseline, features.build_features(shuffled), check_exact=True)
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
    truncated = {name: prefix_rows(frame, cutoff) for name, frame in data.items()}
    assert_frame_equal(baseline.loc[prefix], features.build_features(truncated), check_exact=True)


def test_all_trial_models_submission_contract_and_determinism(monkeypatch):
    data = make_inputs()
    frame = features.build_features(data)

    def loader(data_dir=".", split="train"):
        assert split == "train"
        return data

    monkeypatch.setattr(submission, "load_inputs", loader)
    for trial in models.TRIAL_IDS:
        expected = models.generate_signal(frame, trial).rename("Return").to_frame()
        actual = submission.predict(trial_id=trial)
        again = submission.predict(trial_id=trial)
        assert_frame_equal(actual, expected, check_exact=True)
        assert_frame_equal(actual, again, check_exact=True)
        assert isinstance(actual.index, pd.MultiIndex)
        assert actual.index.names == ["Date", "Code"]
        assert actual.index.equals(frame.index)
        assert list(actual.columns) == ["Return"]
        assert np.isfinite(actual.to_numpy()).all()

    with pytest.raises(ValueError, match="Unknown trial_id"):
        submission.predict(trial_id="unknown")
    with pytest.raises(ValueError, match="restricted to Train"):
        submission.predict(split="valid")


def test_side_specific_overlay_is_independent_and_gap_state_resets():
    date = pd.Timestamp("2026-01-05")
    index = pd.MultiIndex.from_product([[date], ["A", "B", "C", "D"]], names=["Date", "Code"])
    high_only = pd.DataFrame(
        {
            "res60s1": [0.1, 0.6, 0.1, 0.2],
            "new_high_excess": [0.01, 0.02, 0.0, 0.0],
            "new_low_excess": [0.0, 0.0, 0.0, 0.0],
            "high_available": [True, True, False, False],
            "low_available": [False, False, False, False],
        },
        index=index,
    )
    high_base = models.raw_signal(high_only, "B00")
    high_long_overlay = models.raw_signal(high_only, "M10")
    pd.testing.assert_series_equal(
        models.raw_signal(high_only, "M01").rename("score"),
        high_base.rename("score"), check_exact=True,
    )
    pd.testing.assert_series_equal(
        models.raw_signal(high_only, "M11").rename("score"),
        high_long_overlay.rename("score"), check_exact=True,
    )
    assert not high_long_overlay.equals(high_base)

    low_only = high_only.copy()
    low_only["new_high_excess"] = 0.0
    low_only["high_available"] = False
    low_only["new_low_excess"] = [0.01, 0.02, 0.0, 0.0]
    low_only["low_available"] = [True, True, False, False]
    low_base = models.raw_signal(low_only, "B00")
    high_toggle_only = models.raw_signal(low_only, "M10")
    low_overlay = models.raw_signal(low_only, "M01")
    pd.testing.assert_series_equal(
        high_toggle_only.rename("score"), low_base.rename("score"), check_exact=True
    )
    pd.testing.assert_series_equal(
        models.raw_signal(low_only, "M11").rename("score"),
        low_overlay.rename("score"), check_exact=True,
    )
    assert not low_overlay.equals(low_base)

    data = make_inputs(n_dates=380)
    side_frame = side_features.build_features(data)
    frame = features.build_features(data)
    assert_frame_equal(frame, side_frame, check_exact=True)

    for side_trial, base_trial in zip(side_models.TRIAL_IDS, models.TRIAL_IDS):
        side_signal = side_models.raw_signal(side_frame, side_trial)
        base_signal = models.raw_signal(frame, base_trial)
        assert side_signal.index.equals(base_signal.index)
        assert np.isfinite(side_signal.to_numpy()).all()
        assert np.isfinite(base_signal.to_numpy()).all()

    index = frame.index
    dates = index.get_level_values("Date").unique()
    remove_dates = dates[150:181]
    gapped = {}
    for name, panel in data.items():
        if isinstance(panel.index, pd.MultiIndex):
            drop = (panel.index.get_level_values("Code") == "C0") & (
                panel.index.get_level_values("Date").isin(remove_dates)
            )
            gapped[name] = panel.loc[~drop]
        else:
            gapped[name] = panel
    gapped_features = features.build_features(gapped)
    reentry = (dates[181], "C0")
    assert not gapped_features.loc[reentry, "high_available"]
    assert not gapped_features.loc[reentry, "low_available"]
    assert gapped_features.loc[reentry, "res60s1"] == 0.0

    scores = pd.Series(0.7, index=gapped_features.index)
    scores.loc[reentry] = 0.0
    assert models.smooth(scores, alpha=0.25).loc[reentry] == 0.0
