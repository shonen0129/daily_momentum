import numpy as np
import pandas as pd
from features import build_features, centered_rank
from models import fit_predict_family, calibrated_oof, training_mask
from tests.test_causality import fixture_inputs


def test_model_prediction_future_mutation_and_determinism():
    data=fixture_inputs(850,12)
    f=build_features(data)
    m=f.res60s1
    target=data['raw_return_1day']['Return'].copy()
    cutoff=pd.Timestamp('2011-02-01')
    changed={k:v.copy() for k,v in data.items()}
    for name,frame in changed.items():
        if name=='listed_info':
            frame.loc[frame.index.get_level_values('Date')>cutoff,'Sector17Code']='future'
        else:
            frame.loc[frame.index.get_level_values('Date')>cutoff]*=7
    mutated=build_features(changed)
    new_target=target.copy()
    new_target.loc[new_target.index.get_level_values('Date')>cutoff]*=-100
    for family in ['C1','B','A_rank','A_raw']:
        before,audit=fit_predict_family(f,m,target,[2010,2011],family)
        after,_=fit_predict_family(mutated,mutated.res60s1,new_target,[2010,2011],family)
        again,_=fit_predict_family(f,m,target,[2010,2011],family)
        pd.testing.assert_series_equal(before.loc[:cutoff],after.loc[:cutoff],check_exact=True)
        pd.testing.assert_series_equal(before,again,check_exact=True)
        for fold in audit['folds']:
            assert pd.Timestamp(fold['max_label_available'])<pd.Timestamp(f"{fold['year']}-01-01")


def test_label_purge_boundary():
    dates=pd.bdate_range('2010-12-01','2011-01-07')
    idx=pd.MultiIndex.from_product([dates,['1','2']],names=['Date','Code'])
    mask=training_mask(idx,dates,'2011-01-01',np.ones(len(idx),dtype=bool))
    assert idx.get_level_values('Date')[mask].max()==pd.Timestamp('2010-12-29')
    assert not mask[idx.get_level_values('Date')>=pd.Timestamp('2010-12-30')].any()
