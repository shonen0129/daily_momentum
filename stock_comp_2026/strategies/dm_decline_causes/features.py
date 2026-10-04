"""Fixed cause decomposition, prior completed session, no label dependencies."""
from pathlib import Path
import numpy as np
import pandas as pd
try:
    from .primitives import raw_momentum, centered_rank, smooth, segment_keys
except ImportError:
    from primitives import raw_momentum, centered_rank, smooth, segment_keys

FISCAL = ['CurrentFiscalYearStartDate', 'CurrentFiscalYearEndDate']
FINS_COLUMNS = ['ForecastOperatingProfit', 'TotalAssets', 'TypeOfDocument'] + FISCAL
INPUT_COLUMNS = {'raw_return_1day':['Return'], 'beta_1day':['Return'],
                 'topix_return_1day':['Return'], 'prices_daily_quotes':['Volume'],
                 'listed_info':['Sector33Code'], 'fins_statements':FINS_COLUMNS}
CANDIDATES = ('FUND_REV', 'FLOW_REV', 'CAUSE_COMPOSITE')
RAW_COMPONENTS = ('FUND_REV_raw', 'SECTOR33_SHOCK_raw', 'FLOW_REV_raw')


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


def load_train(directory):
    inputs = {n:pd.read_parquet(Path(directory)/f'{n}_train.parquet', columns=c) for n,c in INPUT_COLUMNS.items()}
    inputs['listed_info'] = canonical(inputs['listed_info']).reindex(canonical(inputs['raw_return_1day']).index)
    return inputs


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


def financial_state(index, tau, fins):
    events = financial_events(fins)
    numeric = ['FUND_REV_raw','FundDelta','ForecastLatest','ForecastPrevious','PITAssets']
    out = pd.DataFrame(np.nan,index=index,columns=numeric)
    for col in ['FundDisclosure','FiscalStart','FiscalEnd']:
        out[col] = pd.NaT
    out['FundBasis'] = pd.Series(pd.NA,index=index,dtype='string')
    base = index.to_frame(index=False)
    base['query_at'] = tau.to_numpy() + pd.Timedelta('23:59:59')
    base['position'] = np.arange(len(index))
    base = base.loc[base.query_at.notna()]
    if events.empty or base.empty:
        return out
    joined = pd.merge_asof(base.sort_values('query_at',kind='stable'),
                          events.sort_values('available_at',kind='stable'), by='Code',
                          left_on='query_at',right_on='available_at',direction='backward',allow_exact_matches=True)
    pos = joined.position.to_numpy()
    out.iloc[pos,:len(numeric)] = joined[numeric].to_numpy(dtype=float)
    for dst,src in [('FundDisclosure','available_at'),('FiscalStart',FISCAL[0]),('FiscalEnd',FISCAL[1])]:
        out.loc[index[pos],dst] = joined[src].to_numpy()
    out.loc[index[pos],'FundBasis'] = joined.Basis.to_numpy()
    return out


def ordinal_centered_rank(raw):
    """Fixed same-date median and Code ordering; missing is not economic zero."""
    raw = finite(raw).sort_index()
    filled = raw.fillna(raw.groupby('Date',sort=False).transform('median'))
    # All-missing dates retain the same deterministic tie convention.
    rank = filled.fillna(np.inf).groupby('Date',sort=False).rank(method='first')
    n = rank.groupby('Date',sort=False).transform('count')
    return (2*rank-(n+1))/n


def build_features(inputs):
    data = {n:canonical(inputs[n],panel=n!='topix_return_1day') for n in INPUT_COLUMNS}
    r = finite(data['raw_return_1day'].Return)
    index, dates = r.index, r.index.get_level_values('Date')
    calendar = dates.unique().sort_values()
    tau = pd.Series(calendar.to_series().shift(1).reindex(dates).to_numpy(),index=index,name='Tau')
    beta = finite(data['beta_1day'].Return).reindex(index)
    market = pd.Series(finite(data['topix_return_1day'].Return).reindex(dates).to_numpy(),index=index)
    residual = (r-beta*market).replace([np.inf,-np.inf],np.nan)
    sector = data['listed_info'].Sector33Code.reindex(index).astype('string').str.strip()
    sector = sector.mask(sector.isin(['9999','','nan','None','<NA>']))
    keys = [dates,sector]
    grouped = residual.where(sector.notna()).groupby(keys,sort=True)
    sector_return = grouped.transform('mean')  # self-inclusive, no min-size search
    sector_count = grouped.transform('count').astype(float)
    price = data['prices_daily_quotes']
    volume = finite(price.Volume).where(finite(price.Volume)>=0)
    logv = np.log1p(volume)
    groups = segment_keys(price.index)
    history = logv.groupby(groups,sort=False).shift(1).groupby(groups,sort=False).transform(
        lambda s:s.rolling(20,min_periods=20).median())
    abnormal = (logv-history).reindex(index)
    now = pd.DataFrame({'StockRawReturn':r,'StockResidualReturn':residual,
                        'Sector33Shock':sector_return,'SectorMembers':sector_count,
                        'Volume':volume.reindex(index),'AbnormalVolume':abnormal,'Sector33Code':sector},index=index)
    lookup = pd.MultiIndex.from_arrays([tau,index.get_level_values('Code')],names=index.names)
    f = now.reindex(lookup)
    f.index = index
    f['Tau'] = tau
    state = financial_state(index,tau,data['fins_statements'])
    f = pd.concat([f,state],axis=1)
    f['SECTOR33_SHOCK_raw'] = f.Sector33Shock
    f['WithinShock'] = f.StockResidualReturn-f.Sector33Shock
    f['FLOW_REV_raw'] = -f.WithinShock*f.AbnormalVolume.clip(lower=0)
    for raw in RAW_COMPONENTS:
        f[raw.removesuffix('_raw')+'_rank'] = ordinal_centered_rank(f[raw])
    f['FUND_REV'] = f.FUND_REV_rank
    f['FLOW_REV'] = f.FLOW_REV_rank
    f['CAUSE_COMPOSITE'] = f.FUND_REV_rank+f.SECTOR33_SHOCK_rank+f.FLOW_REV_rank
    f['StockMom60_raw'] = raw_momentum(data)
    f['MOM60'] = smooth(centered_rank(f.StockMom60_raw),.25)
    return f


def score(features,candidate='CAUSE_COMPOSITE'):
    if candidate not in CANDIDATES:
        raise ValueError(f'Unknown candidate: {candidate}')
    return features[candidate].rename('Return')
