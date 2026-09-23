"""Focused regression tests for DM-20260909-03 feature semantics."""
import ast
from pathlib import Path

import pandas as pd

from stock_comp_2026.strategies.dm_fundamental_weakness import features


def test_new_feature_missing_is_neutral_per_day():
    index = pd.MultiIndex.from_tuples(
        [(pd.Timestamp("2020-01-02"), "a"), (pd.Timestamp("2020-01-02"), "b"),
         (pd.Timestamp("2020-01-03"), "a"), (pd.Timestamp("2020-01-03"), "b")], names=["Date", "Code"])
    value = pd.Series([1.0, None, 3.0, 5.0], index=index)
    result = features.neutral_percentile(value)
    assert result.loc[(pd.Timestamp("2020-01-02"), "a")] == 1.0
    assert result.loc[(pd.Timestamp("2020-01-02"), "b")] == 0.5
    assert result.loc[(pd.Timestamp("2020-01-03"), "a")] == 0.5
    assert result.loc[(pd.Timestamp("2020-01-03"), "b")] == 1.0


def test_source_firewall_static_contract():
    folder = Path(features.__file__).parent
    forbidden = ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose",
                 "AdjustmentVolume", "raw_target", "target_1day_valid"]
    for path in folder.glob("*.py"):
        text = path.read_text()
        for token in forbidden:
            assert token not in text, (path, token)
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in ("bfill", "backfill")
                if node.func.attr == "shift":
                    arg = node.args[0] if node.args else next(k.value for k in node.keywords if k.arg == "periods")
                    assert isinstance(arg, ast.Constant) and isinstance(arg.value, int) and arg.value >= 0
                assert not any(k.arg == "center" and isinstance(k.value, ast.Constant) and k.value.value for k in node.keywords)
                assert not any(k.arg == "direction" and isinstance(k.value, ast.Constant) and k.value.value == "forward" for k in node.keywords)
