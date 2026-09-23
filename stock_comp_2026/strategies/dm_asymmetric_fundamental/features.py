"""Disclosure-versioned, period-comparable, causal financial short features."""
from pathlib import Path
import numpy as np
import pandas as pd
from . import core

FINS_COLUMNS = ['DisclosureNumber', 'TypeOfDocument', 'TypeOfCurrentPeriod',
                'CurrentPeriodStartDate', 'CurrentPeriodEndDate',
                'CurrentFiscalYearStartDate', 'CurrentFiscalYearEndDate',
                'CashFlowsFromOperatingActivities', 'TotalAssets', 'CashAndEquivalents', 'Equity']
PERIODS = {'1Q': (80, 100), '2Q': (170, 195), '3Q': (260, 285), 'FY': (350, 380)}
WEIGHTS = {'heavy': (.5, .3, .2), 'equal': (1/3, 1/3, 1/3)}


def load_inputs(directory, split='train'):
    result = core.load_inputs(directory, split)
    result['fins_statements'] = pd.read_parquet(
        Path(directory) / f'fins_statements_{split}.parquet', columns=FINS_COLUMNS).sort_index()
    if not result['fins_statements'].index.is_unique:
        raise ValueError('Duplicate financial disclosure index')
    return result


def percentile(s, period=None):
    s = s.replace([np.inf, -np.inf], np.nan)
    keys = [s.index.get_level_values('Date')]
    if period is not None:
        keys.append(period)
    return s.groupby(keys, observed=True).rank(method='average', pct=True).fillna(0.)


def positive_rank(s):
    return percentile(s.where(s > 0))


def event_decay(age):
    return np.select([(age >= 0) & (age <= 20), (age > 20) & (age <= 40),
                      (age > 40) & (age <= 60)], [1., .5, .25], default=0.)


def _comparable(current, old):
    return (current['period'] == old['period'] and current['basis'] == old['basis']
            and abs((old['start'] - (current['start'] - pd.DateOffset(years=1))).days) <= 7
            and abs((old['end'] - (current['end'] - pd.DateOffset(years=1))).days) <= 7
            and abs(current['duration'] - old['duration']) <= 7)


def financial_panel(index, fins):
    """Sparse report state machine, then strict backward joins onto each listing.

    Ratios are updated atomically. Old-period revisions update the version store,
    without displacing the latest period. Availability uses exchange-calendar age.
    """
    index = index.sort_values()
    calendar = index.get_level_values('Date').unique().sort_values()
    dates = index.get_level_values('Date')
    groups = core.segment_keys(index)
    base = index.to_frame(index=False)
    base['segment'] = np.asarray(groups[1])
    base['ordinal'] = calendar.get_indexer(dates)
    raw = fins.reset_index().copy()
    raw['Date'] = pd.to_datetime(raw.Date).dt.tz_localize(None).dt.normalize()
    raw['Code'] = raw.Code.astype(str)
    for c in ['CurrentPeriodStartDate', 'CurrentPeriodEndDate']:
        raw[c] = pd.to_datetime(raw[c], errors='coerce')
    for c in ['CashFlowsFromOperatingActivities', 'TotalAssets', 'CashAndEquivalents', 'Equity']:
        raw[c] = pd.to_numeric(raw[c], errors='coerce').replace([np.inf, -np.inf], np.nan)
    by_code = {k: v.sort_values(['Date', 'DisclosureNumber']) for k, v in raw.groupby('Code', observed=True)}
    blocks = []
    counts = dict(disclosures=len(raw), accepted=0, invalid_period=0, missing_cfo=0, comparable=0)
    for (code, segment), daily in base.groupby(['Code', 'segment'], sort=False):
        history = by_code.get(str(code), raw.iloc[:0])
        if segment > 0:
            history = history.loc[history.Date >= daily.Date.iloc[0]]
        history = history.loc[history.Date < daily.Date.iloc[-1]]
        cfo_store, cash_store, first_bad, snapshots = {}, {}, {}, []
        active = None
        for row in history.to_dict('records'):
            period, doc = str(row['TypeOfCurrentPeriod']), str(row['TypeOfDocument'])
            start, end = row['CurrentPeriodStartDate'], row['CurrentPeriodEndDate']
            if period not in PERIODS or 'FinancialStatements_' not in doc or pd.isna(start) or pd.isna(end):
                counts['invalid_period'] += 1
                continue
            duration = (end-start).days
            if not PERIODS[period][0] <= duration <= PERIODS[period][1]:
                counts['invalid_period'] += 1
                continue
            counts['accepted'] += 1
            when = row['Date']
            basis = doc.split('FinancialStatements_', 1)[1]
            key = (start, end, period, basis)
            meta = dict(start=start, end=end, period=period, basis=basis, duration=duration,
                        disclosed=when, key=key)
            assets, cfo = row['TotalAssets'], row['CashFlowsFromOperatingActivities']
            cfo_ok = np.isfinite(assets) and assets > 0 and np.isfinite(cfo)
            if cfo_ok:
                cfo_store[key] = dict(meta, value=cfo/assets)
            else:
                counts['missing_cfo'] += 1
            cash, equity = row['CashAndEquivalents'], row['Equity']
            if np.isfinite(assets) and assets > 0 and np.isfinite(cash) and np.isfinite(equity):
                cash_store[key] = dict(meta, value=(cash-(assets-equity))/assets)
            current = max(cfo_store.values(), key=lambda r: (r['end'], r['disclosed'], r['period']), default=None)
            nc = max(cash_store.values(), key=lambda r: (r['end'], r['disclosed'], r['period']), default=None)
            delta, previous = np.nan, None
            if current is not None:
                matches = [r for r in cfo_store.values() if _comparable(current, r)]
                previous = max(matches, key=lambda r: (r['end'], r['disclosed']), default=None)
                if previous is not None:
                    delta = current['value']-previous['value']
                    # Only a valid version update can trigger/clear an event.
                    if cfo_ok:
                        counts['comparable'] += 1
                        bad = current['value'] < 0 <= previous['value']
                        if bad:
                            first_bad.setdefault(current['key'], when)
                            active = first_bad[current['key']]
                        else:
                            active = None
            snapshots.append(dict(Date=when,
                cfo_assets=current['value'] if current else np.nan,
                cfo_yoy=delta, cfo_date=current['disclosed'] if current else pd.NaT,
                period=current['period'] if current else 'missing',
                basis=current['basis'] if current else 'missing',
                net_cash=nc['value'] if nc else np.nan,
                cash_date=nc['disclosed'] if nc else pd.NaT,
                event_date=active if active is not None else pd.NaT))
        if snapshots:
            s = pd.DataFrame(snapshots).drop_duplicates('Date', keep='last').sort_values('Date')
            for col in ['cfo_date', 'cash_date', 'event_date']:
                s[col] = pd.to_datetime(s[col])
            joined = pd.merge_asof(daily.sort_values('Date'), s, on='Date',
                                   direction='backward', allow_exact_matches=False)
        else:
            joined = daily.copy()
            for col in ['cfo_assets', 'cfo_yoy', 'net_cash']:
                joined[col] = np.nan
            for col in ['cfo_date', 'cash_date', 'event_date']:
                joined[col] = pd.NaT
            joined['period'], joined['basis'] = 'missing', 'missing'
        blocks.append(joined)
    result = pd.concat(blocks).set_index(['Date', 'Code']).reindex(index)
    for col in ['cfo_date', 'cash_date', 'event_date']:
        result[col] = result[col].astype('datetime64[ns]')
    result['period'] = result.period.fillna('missing')
    result['basis'] = result.basis.fillna('missing')
    result['financial_age'] = (pd.Series(dates, index=index)-result.cfo_date).dt.days
    cash_age = (pd.Series(dates, index=index)-result.cash_date).dt.days
    result.loc[~result.financial_age.between(0, 450), ['cfo_assets', 'cfo_yoy']] = np.nan
    result.loc[~cash_age.between(0, 450), 'net_cash'] = np.nan
    # searchsorted uses only ordinal differences; appending future dates cannot
    # alter any past event's available ordinal.
    event_ord = calendar.searchsorted(result.event_date.to_numpy(), side='right')
    age = result.ordinal.to_numpy()-event_ord
    result['event_age'] = np.where(result.event_date.notna(), age, np.nan)
    result['event'] = event_decay(result.event_age.to_numpy())
    result['D'] = percentile(-result.cfo_yoy, result.period)
    result['W'] = percentile(-result.cfo_assets, result.period)
    result['F'] = percentile(-result.net_cash)
    result['financial_available'] = result[['cfo_assets', 'cfo_yoy', 'net_cash']].notna().any(axis=1)
    result.attrs['financial_audit'] = counts
    return result.drop(columns=['segment', 'ordinal'])


def build_features(inputs):
    f = core.build_features(inputs)
    fin = financial_panel(f.index, inputs['fins_statements'])
    attrs = {**f.attrs, **fin.attrs}
    f = f.join(fin, validate='one_to_one')
    f['L'] = core.smooth(f.res60s1, .25)
    f['weak_price'] = percentile(-f.res60s1.where(f.momentum_available > 0))
    for name, weights in WEIGHTS.items():
        # A fixed scalar operation order avoids BLAS length-dependent rounding.
        f[f'fd_{name}'] = weights[0]*f.D + weights[1]*f.W + weights[2]*f.F
    required = f[['residual_value', 'impact_value', 'lag_liquidity_shock', 'lag_volume_shock']].notna().all(axis=1)
    f['vacuum'] = ((f.residual_value < 0)*positive_rank(f.impact_value)*positive_rank(-f.lag_liquidity_shock)).where(required, 0.)
    f['participation'] = ((f.residual_value < 0) & (f.lag_volume_shock > 0) &
                          (f.lag_liquidity_shock >= 0) & (f.impact_value <= 0) & required).astype(float)
    f['sector'] = inputs['listed_info']['Sector17Code'].reindex(f.index).astype(str).fillna('missing')
    f.attrs = attrs
    return f


def short_score(f, spec):
    family = spec['family']
    if family == 'baseline':
        return pd.Series(0., index=f.index)
    if family == 'Event':
        return (f.event*f.weak_price).rename('short_score')
    s = f[f"fd_{spec.get('weights', 'heavy')}"]*f.weak_price
    if family in ('B', 'C'):
        s = s*(1-spec['gamma']*f.vacuum)
    if family == 'C':
        s = s*(1+spec['delta']*f.participation)
    return s.rename('short_score')


def predict_from_features(f, spec):
    s = short_score(f, spec)
    if spec.get('smoothing', 'long') == 'final':
        score = core.smooth(f.res60s1-spec['lambda_']*s, .25)
    else:
        score = f.L-spec['lambda_']*s
    if not np.isfinite(score).all() or not score.index.is_unique:
        raise ValueError('Nonfinite prediction or duplicate index')
    return score.rename('Return')
