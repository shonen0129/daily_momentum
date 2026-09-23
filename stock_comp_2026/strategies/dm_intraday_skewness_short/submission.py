"""Unfrozen research candidate; the final score family is selected by explicit config only."""
import importlib.util
from pathlib import Path
import sys

import pandas as pd

if __package__:
    from .features import build_features, load_inputs, predict_from_features
else:
    package_name = "_dm_intraday_skewness_short_submission"
    spec = importlib.util.spec_from_file_location(
        package_name, Path(__file__).with_name("__init__.py"),
        submodule_search_locations=[str(Path(__file__).parent)],
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = package
    spec.loader.exec_module(package)
    module = __import__(package_name + ".features", fromlist=["features"])
    build_features, load_inputs, predict_from_features = module.build_features, module.load_inputs, module.predict_from_features


def predict(data_dir=".", split="train", config=None):
    """Research contract; this un-frozen strategy intentionally defaults to H0."""
    config = config or {"trial_id": "H0"}
    data = load_inputs(data_dir, split)
    return predict_from_features(build_features(data), config).to_frame()
