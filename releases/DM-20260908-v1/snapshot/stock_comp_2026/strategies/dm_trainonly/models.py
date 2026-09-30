"""Small annual models with explicit label-maturity purging."""
import numpy as np
import pandas as pd
import lightgbm as lgb
from features import fit_linear, predict_linear, centered_rank, model_features

PARAMETERS = dict(objective='regression', max_depth=2, num_leaves=4,
                  n_estimators=60, min_child_samples=500, learning_rate=.05,
                  reg_lambda=10., random_state=20260908, n_jobs=2,
                  verbosity=-1, deterministic=True, force_col_wise=True)


def training_mask(index, calendar, start, available):
    k = calendar.searchsorted(pd.Timestamp(start))
    safe_dates = calendar[:max(0,k-2)]
    return index.get_level_values('Date').isin(safe_dates) & available


def calibrated_oof(momentum, target):
    dates=momentum.index.get_level_values('Date')
    calendar=dates.unique().sort_values()
    y=centered_rank(target).where(target.notna())
    out=pd.Series(np.nan,index=momentum.index)
    audit=[]
    for year in sorted(dates.year.unique()):
        mask=training_mask(momentum.index, calendar, f'{year}-01-01', y.notna())
        if dates[mask].nunique()<60:
            continue
        model=fit_linear(momentum.loc[mask].to_numpy()[:,None], y.loc[mask])
        now=dates.year==year
        out.loc[now]=predict_linear(momentum.loc[now].to_numpy()[:,None],model)
        last=dates[mask].max()
        audit.append({'year':int(year),'max_fit_signal':str(last.date()),
                      'max_label_available':str(calendar[calendar.get_loc(last)+2].date()),
                      'model':model})
    return out,y,audit


def fit_predict_family(f, momentum, target, years, family, overrides=None, model_dir=None):
    dates=f.index.get_level_values('Date')
    calendar=dates.unique().sort_values()
    calibration,y,cal_audit=calibrated_oof(momentum,target)
    x=model_features(f,momentum,include_momentum=family.startswith('A'))
    if family.startswith('C'):
        labels=(momentum*y>0).astype(float).where(y.notna())
        labels=labels.where(momentum.abs()>.1)
    elif family=='B':
        labels=y-calibration
    elif family=='A_raw':
        labels=target
    elif family=='A_rank':
        labels=y
    else:
        raise ValueError(family)
    result=pd.Series(0.,index=f.index)
    audit=[]
    params={**PARAMETERS,**(overrides or {})}
    for year in years:
        mask=training_mask(f.index,calendar,f'{year}-01-01',labels.notna())
        now=dates.year==year
        if not now.any() or mask.sum()<2000:
            continue
        model=lgb.LGBMRegressor(**params)
        model.fit(x.loc[mask],labels.loc[mask])
        result.loc[now]=model.predict(x.loc[now])
        last=dates[mask].max()
        audit.append({'year':int(year),'rows':int(mask.sum()),
                      'min_fit_signal':str(dates[mask].min().date()),
                      'max_fit_signal':str(last.date()),
                      'max_label_available':str(calendar[calendar.get_loc(last)+2].date()),
                      'feature_names':list(x.columns),
                      'importance_gain':model.booster_.feature_importance(importance_type='gain').tolist(),
                      'parameters':params})
        if model_dir is not None:
            model_dir.mkdir(parents=True,exist_ok=True)
            model.booster_.save_model(str(model_dir/f'{family}_{year}.txt'))
    return result,{'folds':audit,'calibration':cal_audit,'parameters':params}
