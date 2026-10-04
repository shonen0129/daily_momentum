"""Two fixed sparse event overlays. No labels, fitted weights or revision carry."""
from pathlib import Path
import numpy as np
import pandas as pd
try:
    from . import anchor
    from .financial import canonical, finite, financial_events, FISCAL
    from .primitives import centered_rank, raw_momentum, smooth, segment_keys
except ImportError:
    import anchor
    from financial import canonical, finite, financial_events, FISCAL
    from primitives import centered_rank, raw_momentum, smooth, segment_keys

FINS_COLUMNS = list(dict.fromkeys(anchor.FINS_COLUMNS +
    ['ForecastOperatingProfit', 'TypeOfDocument'] + FISCAL))
INPUT_COLUMNS = {'raw_return_1day':['Return'], 'beta_1day':['Return'],
    'topix_return_1day':['Return'], 'prices_daily_quotes':['Close','TurnoverValue','Volume'],
    'listed_info':['Sector17Code','Sector33Code'], 'fins_statements':FINS_COLUMNS}
CANDIDATES = ('SLOW_FUND_EVENT','SLOW_CAUSE_AWARE')


def load_train(directory):
    inputs = {n:pd.read_parquet(Path(directory)/f'{n}_train.parquet', columns=c)
              for n,c in INPUT_COLUMNS.items()}
    inputs['listed_info'] = canonical(inputs['listed_info']).reindex(canonical(inputs['raw_return_1day']).index)
    return inputs


def event_rank(raw, active):
    """Only finite active events enter an average-rank centered percentile."""
    eligible = finite(raw).where(active)
    rank = eligible.groupby('Date',sort=False).rank(method='average')
    n = eligible.groupby('Date',sort=False).transform('count')
    return ((2*rank-(n+1))/n.where(n>0)).fillna(0.)


def fresh_financial(index, calendar, fins):
    events = financial_events(fins)
    numeric = ['FUND_REV_raw','FundDelta','ForecastLatest','ForecastPrevious','PITAssets']
    out = pd.DataFrame(np.nan,index=index,columns=numeric)
    out['FundDisclosure'] = pd.NaT
    out['FiscalStart'] = pd.NaT
    out['FiscalEnd'] = pd.NaT
    out['FundBasis'] = pd.Series(pd.NA,index=index,dtype='string')
    out['FreshDisclosure'] = 0.
    out['FreshFundEvent'] = 0.
    if events.empty:
        out = out.rename(columns={'FUND_REV_raw':'FUND_EVENT_RAW'})
        return out
    base = index.to_frame(index=False)
    base['signal_at'] = base.Date.dt.normalize()
    previous = pd.Series(calendar.to_series().shift(1).reindex(base.Date).to_numpy())
    base['previous_signal_at'] = previous
    base['position'] = np.arange(len(base))
    joined = pd.merge_asof(base.sort_values('signal_at',kind='stable'),
        events.sort_values('available_at',kind='stable'), by='Code',
        left_on='signal_at',right_on='available_at',direction='backward',allow_exact_matches=True)
    fresh = joined.available_at.notna() & (
        joined.previous_signal_at.isna() | (joined.available_at>joined.previous_signal_at))
    event = fresh & np.isfinite(joined.FundDelta) & joined.FundDelta.ne(0)
    positions = joined.position.to_numpy()
    # Comparison values exist only on the first available session; no revision state.
    out.iloc[positions,:len(numeric)] = joined[numeric].where(fresh,axis=0).to_numpy(dtype=float)
    for dst,src in [('FundDisclosure','available_at'),('FiscalStart',FISCAL[0]),('FiscalEnd',FISCAL[1])]:
        out.loc[index[positions],dst] = joined[src].where(fresh).to_numpy()
    out.loc[index[positions],'FundBasis'] = joined.Basis.where(fresh).to_numpy()
    out.loc[index[positions],'FreshDisclosure'] = fresh.to_numpy(dtype=float)
    out.loc[index[positions],'FreshFundEvent'] = event.to_numpy(dtype=float)
    out['FUND_REV_raw'] = out.FUND_REV_raw.where(out.FreshFundEvent.eq(1))
    return out.rename(columns={'FUND_REV_raw':'FUND_EVENT_RAW'})


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
    grouped = residual.where(sector.notna()).groupby([dates,sector],sort=True)
    sector_return = grouped.transform('mean')
    sector_count = grouped.transform('count').astype(float)
    price = data['prices_daily_quotes']
    volume = finite(price.Volume).where(finite(price.Volume)>=0)
    logv = np.log1p(volume)
    groups = segment_keys(price.index)
    history = logv.groupby(groups,sort=False).shift(1).groupby(groups,sort=False).transform(
        lambda s:s.rolling(20,min_periods=20).median())
    abnormal = (logv-history).reindex(index)
    now = pd.DataFrame({'StockRawReturn':r,'StockResidualReturn':residual,
        'SectorShock':sector_return,'SectorMembers':sector_count,'Volume':volume.reindex(index),
        'AbnormalVolume':abnormal,'Sector33Code':sector},index=index)
    lookup = pd.MultiIndex.from_arrays([tau,index.get_level_values('Code')],names=index.names)
    f = now.reindex(lookup);f.index = index;f['Tau'] = tau
    f = pd.concat([f,fresh_financial(index,calendar,data['fins_statements'])],axis=1)
    f['WithinShock'] = f.StockResidualReturn-f.SectorShock
    flow = f.FreshFundEvent.eq(0) & f.WithinShock.lt(0) & f.AbnormalVolume.gt(0)
    f['FLOW_EVENT_RAW'] = (-f.WithinShock*f.AbnormalVolume.clip(lower=0)).where(flow)
    f['FundActive'] = (f.FreshFundEvent.eq(1) & np.isfinite(f.FUND_EVENT_RAW)).astype(float)
    f['FlowActive'] = (flow & np.isfinite(f.FLOW_EVENT_RAW)).astype(float)
    f['FundOverlay'] = event_rank(f.FUND_EVENT_RAW,f.FundActive.eq(1))
    f['FlowOverlay'] = event_rank(f.FLOW_EVENT_RAW,f.FlowActive.eq(1))
    # Exactly the unchanged global anchor module and its unchanged original inputs.
    anchor_data = {n:data[n][cols] for n,cols in anchor.INPUT_COLUMNS.items()}
    f['SLOW_CONTROL'] = anchor.build_features(anchor_data,sector=False).size_liquidity
    f['SlowRank'] = centered_rank(f.SLOW_CONTROL)
    f['SLOW_FUND_EVENT'] = f.SlowRank+f.FundOverlay
    f['SLOW_CAUSE_AWARE'] = f.SLOW_FUND_EVENT+f.FlowOverlay
    f['StockMom60_raw'] = raw_momentum(data)
    f['MOM60'] = smooth(centered_rank(f.StockMom60_raw),.25)
    return f


def score(features,candidate='SLOW_CAUSE_AWARE'):
    if candidate not in CANDIDATES:
        raise ValueError(f'Unknown candidate: {candidate}')
    return features[candidate].rename('Return')
