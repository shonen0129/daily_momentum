"""Submission entry point for dm_high_proximity_momentum."""
from pathlib import Path
import numpy as np
import pandas as pd
from .features import load_inputs, build_features, INPUT_COLUMNS
from .models import generate_signal


def predict(data_dir='.', split=None):
    """Official prediction entry point."""
    if split is None:
        split = 'valid' if (Path(data_dir) / 'raw_return_1day_valid.parquet').exists() else 'train'
    names = list(INPUT_COLUMNS.keys())
    inputs = load_inputs(data_dir, 'train')
    output_index = inputs['raw_return_1day'].index

    if split == 'valid':
        later = load_inputs(data_dir, 'valid')
        output_index = later['raw_return_1day'].index
        inputs = {k: pd.concat([inputs[k], later[k]]).sort_index() for k in names}
        if any(not v.index.is_unique for v in inputs.values()):
            raise ValueError('Overlapping feature history')
    elif split != 'train':
        raise ValueError(f'Unknown prediction split: {split}')

    features = build_features(inputs)
    # Default to C2 (60d blend) or whichever is evaluated as champion
    score = generate_signal(features, 'C2', alpha=0.25).reindex(output_index)
    if not score.index.is_unique or not np.isfinite(score).all():
        raise ValueError('Prediction coverage or finiteness failure')
    return score.rename('Return').to_frame()
