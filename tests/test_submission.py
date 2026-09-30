import numpy as np
import pandas as pd
from tests.test_causality import fixture_inputs
from tests.legacy_dm_trainonly import load_modules


with load_modules() as _dm:
    submission = _dm.submission
    smooth = _dm.features.smooth
    build_momentum = _dm.features.build_momentum


def test_later_split_contract_using_only_synthetic_inputs(monkeypatch):
    data=fixture_inputs(560)
    cutoff=pd.Timestamp('2009-01-01')
    def loader(directory,split,names):
        return {k:v.loc[(v.index.get_level_values('Date')<cutoff) if split=='train' else
                        (v.index.get_level_values('Date')>=cutoff)] for k,v in data.items() if k in names}
    monkeypatch.setattr(submission,'load_inputs',loader)
    prediction=submission.predict(split='valid')
    expected=smooth(build_momentum(data),.25).rename('Return').to_frame().loc[cutoff:]
    pd.testing.assert_frame_equal(prediction,expected,check_exact=True)
    assert np.isfinite(prediction).all().all()
