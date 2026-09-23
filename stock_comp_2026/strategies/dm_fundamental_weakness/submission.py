"""Unfrozen DM-20260909-03 candidate; official one-column prediction contract."""
import importlib.util
import json
from pathlib import Path
import sys

import pandas as pd

if __package__:
    from .features import build_features, load_inputs, predict_from_features
else:
    name = "_dm_fundamental_weakness_submission"
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name("__init__.py"),
                                                  submodule_search_locations=[str(Path(__file__).parent)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    module = __import__(name + ".features", fromlist=["features"])
    build_features, load_inputs, predict_from_features = module.build_features, module.load_inputs, module.predict_from_features


def predict(data_dir=".", split=None, config=None):
    if config is None:
        config = json.loads(Path(__file__).with_name("research_config.json").read_text())
    if split is None:
        split = "valid" if (Path(data_dir) / "raw_return_1day_valid.parquet").exists() else "train"
    if split not in ("train", "valid"):
        raise ValueError("Unknown split")
    data = load_inputs(data_dir, "train")
    output_index = data["raw_return_1day"].index
    if split == "valid":
        later = load_inputs(data_dir, "valid")
        output_index = later["raw_return_1day"].index
        data = {key: pd.concat([value, later[key]]).sort_index() for key, value in data.items()}
        if any(not value.index.is_unique for value in data.values()):
            raise ValueError("Overlapping feature history")
    return predict_from_features(build_features(data), config).reindex(output_index).to_frame()
