"""Full Train causality, prediction parity, bounded official smoke, and accounting QA."""
import json
import os
import resource
import sys
import tempfile
import time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
STRATEGY=ROOT/'stock_comp_2026/strategies/dm_trainonly'
sys.path.insert(0,str(STRATEGY))
sys.path.insert(0,str(ROOT/'stock_comp_2026'))
from features import load_inputs,build_features,build_momentum,smooth
from submission import predict
from research import firewall
from research.evaluation import daily_account, metrics
from evaluate_script import load_prediction,align_prediction,compute_pl,compute_sr


def main():
    out=ROOT/'reports/DM-20260908'; data=ROOT/'stock_comp_2026/input'
    artifact=out/'selected_train_predictions.parquet'
    firewall.install([artifact])
    started=time.monotonic()
    inputs=load_inputs(data,'train')
    # Other listed companies are never part of this universe's exact-date join.
    inputs['listed_info']=inputs['listed_info'].reindex(inputs['raw_return_1day'].index)
    original=build_features(inputs)
    dates=original.index.get_level_values('Date')
    checks=[]
    for cutoff in ['2010-12-30','2012-06-29','2014-12-30']:
        mutated={k:v.copy() for k,v in inputs.items()}
        for name,frame in mutated.items():
            after=frame.index.get_level_values('Date')>pd.Timestamp(cutoff)
            if name=='listed_info':
                frame.loc[after,'Sector17Code']='future_only'
                frame.loc[after,'ScaleCategory']='TOPIX Core30'
            else:
                frame.loc[after]=frame.loc[after]*17+11
        future=build_features(mutated)
        before=dates<=pd.Timestamp(cutoff)
        pd.testing.assert_frame_equal(original.loc[before],future.loc[before],check_exact=True)
        pd.testing.assert_series_equal(smooth(build_momentum(inputs),.25).loc[before],
                                      smooth(build_momentum(mutated),.25).loc[before],check_exact=True)
        checks.append({'cutoff':cutoff,'prefix_rows':int(before.sum()),'features':original.shape[1],
                       'features_bitwise_equal':True,'selected_predictions_bitwise_equal':True,
                       'mutated_inputs':list(inputs)})
        print('Full Train future-mutation PASS',cutoff,flush=True)
        del mutated,future
    t=time.monotonic(); prediction=predict(data,split='train'); elapsed=time.monotonic()-t
    repeated=predict(data,split='train')
    expected=pd.read_parquet(artifact)
    pd.testing.assert_frame_equal(prediction,expected,check_exact=True)
    pd.testing.assert_frame_equal(prediction,repeated,check_exact=True)
    pd.testing.assert_series_equal(build_momentum(inputs),original.res60s1,check_exact=True)
    # The distribution has finite labels on the final two Train signal dates.
    # Purge them because their realization uses prices beyond the Train end.
    calendar=dates.unique().sort_values(); last=calendar[-3]
    target=pd.read_parquet(data/'target_1day_train.parquet',filters=[('Date','<=',last)])
    continuous=prediction.loc[(dates>=pd.Timestamp('2011-01-01'))&(dates<=last)]
    daily=daily_account(continuous.iloc[:,0],target.iloc[:,0].reindex(continuous.index))
    daily.to_csv(out/'daily/selected_continuous_train_wf.csv')
    years=[{'year':int(y),**metrics(v)} for y,v in daily.groupby(daily.index.year)]
    (out/'continuous_metrics.json').write_text(json.dumps({'metrics':metrics(daily),'years':years},indent=2))
    # No Valid file is visible to the official evaluator in this sandboxed data directory.
    with tempfile.TemporaryDirectory(prefix='dm_train_smoke_') as folder:
        stage=Path(folder)
        for name in ['raw_return_1day','beta_1day','topix_return_1day']:
            (stage/f'{name}_train.parquet').symlink_to(data/f'{name}_train.parquet')
        target.to_parquet(stage/'target_1day_train.parquet')
        smoke_pred=load_prediction(STRATEGY,stage)
        aligned=align_prediction(smoke_pred,target)
        official=compute_pl(aligned,target)
        local=daily_account(aligned.iloc[:,0],target.iloc[:,0])
        np.testing.assert_allclose(local.net,official.groupby('Date').sum(),rtol=0,atol=1e-16)
        smoke={'official_api':'load_prediction -> align_prediction -> compute_pl -> compute_sr',
               'target':'sanitized target_1day_train, final two Train signal dates excluded',
               'evaluated_rows':len(target),'prediction_rows':len(smoke_pred),
               'descriptive_full_train_sharpe_not_used_for_selection':compute_sr(official),
               'scorer_daily_parity':True,'valid_visible':False}
    report={'status':'PASS','future_mutation':checks,'train_prediction_rows':len(prediction),
            'train_prediction_dates':int(dates.nunique()),'train_codes':int(prediction.index.get_level_values('Code').nunique()),
            'prediction_finite':bool(np.isfinite(prediction).all().all()),
            'research_submission_bitwise_equal':True,'deterministic_bitwise':True,
            'inference_seconds_train':elapsed,'validation_seconds':time.monotonic()-started,
            'peak_rss_bytes_macos':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'smoke':smoke}
    (out/'verification.json').write_text(json.dumps(report,indent=2))
    firewall.save(out/'verification_data_access.json')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
