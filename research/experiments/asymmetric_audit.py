"""Label-free real-input causality and prediction audits."""
import ast
from pathlib import Path
import numpy as np
import pandas as pd
from stock_comp_2026.strategies.dm_asymmetric_fundamental import features as sf
from stock_comp_2026.strategies.dm_trainonly.features import build_momentum, smooth


def scan_sources():
    paths = sorted(Path(sf.__file__).parent.glob('*.py'))
    for path in paths:
        source = path.read_text()
        for token in ['AdjustmentOpen','AdjustmentHigh','AdjustmentLow','AdjustmentClose','AdjustmentVolume','raw_target','target_1day_valid']:
            if token in source:
                raise AssertionError((path, token))
        for n in ast.walk(ast.parse(source)):
            if not isinstance(n, ast.Call) or not isinstance(n.func, ast.Attribute):
                continue
            assert n.func.attr not in ('bfill','backfill'), (path,n.lineno)
            if n.func.attr == 'shift':
                v = n.args[0] if n.args else next(k.value for k in n.keywords if k.arg == 'periods')
                assert isinstance(v,ast.Constant) and type(v.value) is int and v.value >= 0
            for k in n.keywords:
                assert not (k.arg == 'center' and not (isinstance(k.value,ast.Constant) and k.value.value is False))
                assert not (k.arg == 'direction' and isinstance(k.value,ast.Constant) and k.value.value == 'forward')
    return [str(p) for p in paths]


def audit_inputs(inputs, original, emit):
    scan = scan_sources()
    pd.testing.assert_series_equal(original.L.rename('res60s1'),smooth(build_momentum(inputs),.25),check_exact=True)
    records=[]
    specs=[dict(family=family,weights=w,lambda_=1.,gamma=.5,delta=.5,smoothing=sm)
           for family in ['A','B','C','Event'] for w in ['heavy','equal'] for sm in ['long','final']]
    for cutoff in ['2010-12-30','2012-06-29','2014-12-30']:
        cutoff=pd.Timestamp(cutoff)
        changed, truncated = {}, {}
        for name, data in inputs.items():
            dt=data.index.get_level_values('Date')
            if dt.tz is not None: dt=dt.tz_localize(None)
            mask=dt>cutoff
            truncated[name]=data.loc[~mask].copy()
            altered=data.copy()
            for col in altered:
                if isinstance(altered[col].dtype,pd.CategoricalDtype): altered[col]=altered[col].astype(str)
                if pd.api.types.is_numeric_dtype(altered[col]):
                    altered.loc[mask,col]=altered.loc[mask,col]*-13+999
                elif pd.api.types.is_datetime64_any_dtype(altered[col]):
                    altered.loc[mask,col]=pd.Timestamp('1990-01-01')
                else:
                    altered.loc[mask,col]='future_changed'
            changed[name]=altered
        before=original.loc[original.index.get_level_values('Date')<=cutoff]
        mutated=sf.build_features(changed)
        prefix=mutated.loc[mutated.index.get_level_values('Date')<=cutoff]
        pd.testing.assert_frame_equal(before,prefix,check_exact=True)
        short=sf.build_features(truncated)
        pd.testing.assert_frame_equal(before,short,check_exact=True)
        for spec in specs:
            expected=sf.predict_from_features(original,spec).loc[before.index]
            pd.testing.assert_series_equal(expected,sf.predict_from_features(mutated,spec).loc[before.index],check_exact=True)
            pd.testing.assert_series_equal(expected,sf.predict_from_features(short,spec),check_exact=True)
        records.append(dict(cutoff=str(cutoff.date()),rows=len(before),features=len(before.columns),prediction_formulas=len(specs),bitwise=True,mutation=True,truncation=True))
        emit(f'prefix audit PASS {cutoff.date()}: {len(before)} rows')
    return dict(status='PASS',baseline_bitwise=True,source_files=scan,prefix_tests=records)


def coverage_tables(f, output):
    z=pd.DataFrame({'year':f.index.get_level_values('Date').year,'period':f.period.to_numpy(),
                    'basis':f.basis.to_numpy(),'cfo':f.cfo_assets.notna().to_numpy(),
                    'yoy':f.cfo_yoy.notna().to_numpy(),'net_cash':f.net_cash.notna().to_numpy(),
                    'financial_any':f.financial_available.to_numpy(),'age':f.financial_age.to_numpy()})
    for group in [['year'],['year','period'],['year','basis']]:
        table=z.groupby(group,observed=True).agg(rows=('cfo','size'),cfo_coverage=('cfo','mean'),yoy_coverage=('yoy','mean'),net_cash_coverage=('net_cash','mean'),any_coverage=('financial_any','mean'),median_age=('age','median'),max_age=('age','max'))
        table.to_csv(output/('coverage_'+'_'.join(group)+'.csv'))
