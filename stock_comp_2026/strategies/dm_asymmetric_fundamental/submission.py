"""Unfrozen research candidate. Official no-argument, one-column contract."""
import importlib.util
import json
from pathlib import Path
import sys
import pandas as pd

if __package__:
    from .features import load_inputs, build_features, predict_from_features
else:
    # Load this directory as a unique package, avoiding another strategy's features.
    package_name = '_dm_asymmetric_submission'
    spec = importlib.util.spec_from_file_location(package_name, Path(__file__).with_name('__init__.py'),
                                                 submodule_search_locations=[str(Path(__file__).parent)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = package
    spec.loader.exec_module(package)
    module = __import__(package_name+'.features', fromlist=['features'])
    load_inputs, build_features, predict_from_features = module.load_inputs, module.build_features, module.predict_from_features


def predict(data_dir='.', split=None, config=None):
    if config is None:
        config = json.loads(Path(__file__).with_name('research_config.json').read_text())
    if split is None:
        split = 'valid' if (Path(data_dir)/'raw_return_1day_valid.parquet').exists() else 'train'
    if split not in ('train', 'valid'):
        raise ValueError('Unknown split')
    data = load_inputs(data_dir, 'train')
    output_index = data['raw_return_1day'].index
    if split == 'valid':
        later = load_inputs(data_dir, 'valid')
        output_index = later['raw_return_1day'].index
        data = {k: pd.concat([v, later[k]]).sort_index() for k, v in data.items()}
        if any(not v.index.is_unique for v in data.values()):
            raise ValueError('Overlapping feature history')
    return predict_from_features(build_features(data), config).reindex(output_index).to_frame()
