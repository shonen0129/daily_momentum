"""DM-20260908-v1: frozen, label-free, CPU-only Momentum submission."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from features import load_inputs, build_momentum, smooth

NAMES=('raw_return_1day','beta_1day','topix_return_1day')


def predict(data_dir='.', split=None):
    """Official no-argument entry point; explicit split='train' for research.

    The automatic split uses only presence of feature files. It never discovers
    labels. Training history supplies rolling/EWMA warmup for a later split.
    """
    config=json.loads((Path(__file__).resolve().parent/'frozen_config.json').read_text())
    if config['momentum']!='res60s1' or config['family']!='Momentum':
        raise ValueError('This frozen release supports only selected Momentum')
    if split is None:
        split='valid' if (Path(data_dir)/'raw_return_1day_valid.parquet').exists() else 'train'
    inputs=load_inputs(data_dir,'train',NAMES)
    output_index=inputs['raw_return_1day'].index
    if split=='valid':
        later=load_inputs(data_dir,'valid',NAMES)
        output_index=later['raw_return_1day'].index
        inputs={k:pd.concat([inputs[k],later[k]]).sort_index() for k in NAMES}
        if any(not v.index.is_unique for v in inputs.values()):
            raise ValueError('Overlapping feature history')
    elif split!='train':
        raise ValueError('Unknown prediction split')
    score=smooth(build_momentum(inputs),config['alpha']).reindex(output_index)
    if not score.index.is_unique or not np.isfinite(score).all():
        raise ValueError('Prediction coverage or finiteness failure')
    return score.rename('Return').to_frame()
