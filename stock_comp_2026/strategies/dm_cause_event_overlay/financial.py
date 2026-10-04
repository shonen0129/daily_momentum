"""Unchanged forecast comparison and canonicalization from prior experiment."""
import numpy as np
import pandas as pd
FISCAL = ["CurrentFiscalYearStartDate", "CurrentFiscalYearEndDate"]

def canonical(frame, panel=True):
    names = ['Date','Code'] if panel else ['Date']
    if frame.index.names != names or not frame.index.is_unique:
        raise ValueError(f'Expected unique {names} index')
    result = frame.copy()
    dates = pd.DatetimeIndex(frame.index.get_level_values('Date'))
    if dates.tz is not None:
        dates = dates.tz_convert('Asia/Tokyo').tz_localize(None)
    result.index = (pd.MultiIndex.from_arrays([dates, frame.index.get_level_values('Code').astype(str)], names=names)
                    if panel else pd.DatetimeIndex(dates, name='Date'))
    if not result.index.is_unique:
        raise ValueError('Duplicate canonical index')
    return result.sort_index()


def finite(s):
    return pd.to_numeric(s, errors='coerce').replace([np.inf, -np.inf], np.nan).astype(float)


def financial_events(fins):
    """Each disclosure replaces state; comparable forecasts never cross fiscal/basis keys."""
    e = canonical(fins).reset_index()
    e['available_at'] = e.Date.dt.normalize() + pd.Timedelta('23:59:59')
    # Revision-only documents inherit a past disclosed reporting basis.
    e['Basis'] = e.TypeOfDocument.astype('string').str.extract(
        r'_(Consolidated_(?:JP|US|IFRS)|NonConsolidated_(?:JP|US|IFRS))$', expand=False)
    e['Basis'] = e.groupby('Code', sort=False).Basis.ffill()
    e['ForecastLatest'] = finite(e.ForecastOperatingProfit)
    assets = finite(e.TotalAssets)
    e['PITAssets'] = assets.where(assets > 0).groupby([e.Code,e.Basis], sort=False).ffill()
    for col in FISCAL:
        e[col] = pd.to_datetime(e[col], errors='coerce')
    good = e.ForecastLatest.notna() & e.Basis.notna() & e[FISCAL].notna().all(axis=1)
    forecasts = e.loc[good]
    keys = ['Code'] + FISCAL + ['Basis']
    e['ForecastPrevious'] = np.nan
    e.loc[good, 'ForecastPrevious'] = forecasts.groupby(keys, sort=False).ForecastLatest.shift(1)
    e['FundDelta'] = e.ForecastLatest - e.ForecastPrevious
    e['FUND_REV_raw'] = (e.FundDelta/e.PITAssets).replace([np.inf,-np.inf],np.nan)
    return e
