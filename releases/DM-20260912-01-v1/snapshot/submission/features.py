"""Point-in-Time causal financial features and fixed-long independent short score stitching."""
from pathlib import Path
import numpy as np
import pandas as pd
from . import core

FINS_COLUMNS = ['DisclosureNumber', 'TypeOfDocument', 'TypeOfCurrentPeriod',
                'CurrentPeriodStartDate', 'CurrentPeriodEndDate',
                'CurrentFiscalYearStartDate', 'CurrentFiscalYearEndDate',
                'CashFlowsFromOperatingActivities', 'TotalAssets', 'CashAndEquivalents', 'Equity']
PERIODS = {'1Q': (80, 100), '2Q': (170, 195), '3Q': (260, 285), 'FY': (350, 380)}


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


def _comparable(current, old):
    return (current['period'] == old['period'] and current['basis'] == old['basis']
            and abs((old['start'] - (current['start'] - pd.DateOffset(years=1))).days) <= 7
            and abs((old['end'] - (current['end'] - pd.DateOffset(years=1))).days) <= 7
            and abs(current['duration'] - old['duration']) <= 7)


def financial_panel(index, fins):
    """Sparse report state machine, then strict backward joins onto each listing."""
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
        cfo_store, cash_store, snapshots = {}, {}, []
        for row in history.to_dict('records'):
            period, doc = str(row['TypeOfCurrentPeriod']), str(row['TypeOfDocument'])
            start, end = row['CurrentPeriodStartDate'], row['CurrentPeriodEndDate']
            if period not in PERIODS or 'FinancialStatements_' not in doc or pd.isna(start) or pd.isna(end):
                counts['invalid_period'] += 1
                continue
            duration = (end - start).days
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
                cfo_store[key] = dict(meta, value=cfo / assets)
            else:
                counts['missing_cfo'] += 1
            cash, equity = row['CashAndEquivalents'], row['Equity']
            if np.isfinite(assets) and assets > 0 and np.isfinite(cash) and np.isfinite(equity):
                cash_store[key] = dict(meta, value=(cash - (assets - equity)) / assets)
            current = max(cfo_store.values(), key=lambda r: (r['end'], r['disclosed'], r['period']), default=None)
            nc = max(cash_store.values(), key=lambda r: (r['end'], r['disclosed'], r['period']), default=None)
            delta, previous = np.nan, None
            if current is not None:
                matches = [r for r in cfo_store.values() if _comparable(current, r)]
                previous = max(matches, key=lambda r: (r['end'], r['disclosed']), default=None)
                if previous is not None:
                    delta = current['value'] - previous['value']
                    if cfo_ok:
                        counts['comparable'] += 1
            snapshots.append(dict(
                Date=when,
                cfo_assets=current['value'] if current else np.nan,
                cfo_yoy=delta, cfo_date=current['disclosed'] if current else pd.NaT,
                period=current['period'] if current else 'missing',
                basis=current['basis'] if current else 'missing',
                net_cash=nc['value'] if nc else np.nan,
                cash_date=nc['disclosed'] if nc else pd.NaT))
        if snapshots:
            s = pd.DataFrame(snapshots).drop_duplicates('Date', keep='last').sort_values('Date')
            for col in ['cfo_date', 'cash_date']:
                s[col] = pd.to_datetime(s[col])
            joined = pd.merge_asof(daily.sort_values('Date'), s, on='Date',
                                   direction='backward', allow_exact_matches=False)
        else:
            joined = daily.copy()
            for col in ['cfo_assets', 'cfo_yoy', 'net_cash']:
                joined[col] = np.nan
            for col in ['cfo_date', 'cash_date']:
                joined[col] = pd.NaT
            joined['period'], joined['basis'] = 'missing', 'missing'
        blocks.append(joined)
    result = pd.concat(blocks).set_index(['Date', 'Code']).reindex(index)
    for col in ['cfo_date', 'cash_date']:
        result[col] = result[col].astype('datetime64[ns]')
    result['period'] = result.period.fillna('missing')
    result['basis'] = result.basis.fillna('missing')
    result['financial_age'] = (pd.Series(dates, index=index) - result.cfo_date).dt.days
    cash_age = (pd.Series(dates, index=index) - result.cash_date).dt.days
    result.loc[~result.financial_age.between(0, 450), ['cfo_assets', 'cfo_yoy']] = np.nan
    result.loc[~cash_age.between(0, 450), 'net_cash'] = np.nan
    result['D'] = percentile(-result.cfo_yoy, result.period)
    result['W'] = percentile(-result.cfo_assets, result.period)
    result['F'] = percentile(-result.net_cash)
    result['financial_available'] = result[['cfo_assets', 'cfo_yoy', 'net_cash']].notna().any(axis=1)
    result.attrs['financial_audit'] = counts
    return result.drop(columns=['segment', 'ordinal'])


def build_features(inputs):
    f = core.build_core_features(inputs)
    fin = financial_panel(f.index, inputs['fins_statements'])
    attrs = {**f.attrs, **fin.attrs}
    f = f.join(fin, validate='one_to_one')
    f['L'] = core.smooth(f.res60s1, .25)
    f['weak_price'] = percentile(-f.res60s1.where(f.momentum_available > 0))
    # Equal weight Fundamental Deterioration
    f['fd_equal'] = (1.0 / 3.0) * f.D + (1.0 / 3.0) * f.W + (1.0 / 3.0) * f.F
    # M5 RecentCrash: lower 20% in full universe
    m5_pct = percentile(f.res5s1_sum)
    f['recent_crash'] = (f.res5s1_sum.notna() & (m5_pct <= 0.20)).astype(int)
    f['sector'] = inputs['listed_info']['Sector17Code'].reindex(f.index).astype(str).fillna('missing')
    f.attrs = attrs
    return f


def _stitch_day(sub, trial):
    if trial == 'B0':
        return sub['L']

    N = len(sub)
    r_L = sub['L'].rank(method='first').astype(int)
    k_neutral_max = int(np.floor(0.6 * (N - 1) + 1))
    k_short_max = int(np.floor(0.4 * (N - 1) + 1))

    is_long = r_L > k_neutral_max
    r_final = pd.Series(index=sub.index, dtype=float)
    r_final[is_long] = r_L[is_long]

    rem = sub.loc[~is_long]
    rem_codes = rem.index.get_level_values('Code').astype(str).to_numpy()
    rem_r_L = r_L.loc[~is_long].to_numpy()

    if trial == 'T0':
        # Exactly identical to baseline ranking
        r_final[~is_long] = r_L.loc[~is_long]
    elif trial == 'T1':
        short_risk = rem['fd_equal'].to_numpy()
        order = np.lexsort((rem_codes, rem_r_L, -short_risk))
        short_idx = rem.index[order[:k_short_max]]
        neutral_idx = rem.index[order[k_short_max:]]
        r_final[short_idx] = np.arange(1, k_short_max + 1)
        r_final[neutral_idx] = np.arange(k_short_max + 1, k_neutral_max + 1)
    elif trial == 'T2':
        short_risk = (rem['fd_equal'] * rem['weak_price']).to_numpy()
        order = np.lexsort((rem_codes, rem_r_L, -short_risk))
        short_idx = rem.index[order[:k_short_max]]
        neutral_idx = rem.index[order[k_short_max:]]
        r_final[short_idx] = np.arange(1, k_short_max + 1)
        r_final[neutral_idx] = np.arange(k_short_max + 1, k_neutral_max + 1)
    elif trial == 'T3':
        short_base = (rem['fd_equal'] * rem['weak_price']).to_numpy()
        is_crash = rem['recent_crash'].to_numpy() == 1
        non_crash_idx = np.where(~is_crash)[0]
        crash_idx = np.where(is_crash)[0]

        nc_order = non_crash_idx[np.lexsort((rem_codes[non_crash_idx],
                                             rem_r_L[non_crash_idx],
                                             -short_base[non_crash_idx]))]
        c_order = crash_idx[np.lexsort((rem_codes[crash_idx],
                                        rem_r_L[crash_idx],
                                        -short_base[crash_idx]))]

        if len(nc_order) >= k_short_max:
            chosen_short = nc_order[:k_short_max]
            chosen_neutral = np.concatenate([nc_order[k_short_max:], c_order])
        else:
            deficit = k_short_max - len(nc_order)
            chosen_short = np.concatenate([nc_order, c_order[:deficit]])
            chosen_neutral = c_order[deficit:]

        # Sort neutral by baseline r_L ascending, then Code
        n_order = chosen_neutral[np.lexsort((rem_codes[chosen_neutral], rem_r_L[chosen_neutral]))]

        r_final[rem.index[chosen_short]] = np.arange(1, k_short_max + 1)
        r_final[rem.index[n_order]] = np.arange(k_short_max + 1, k_neutral_max + 1)
    else:
        raise ValueError(f"Unknown trial {trial}")

    return (r_final - 1.0) / (N - 1.0)


def predict_from_features(f, spec):
    trial = spec.get('trial_id', 'T0')
    if trial == 'B0':
        score = f.L.copy()
    else:
        score = f.groupby(level='Date', group_keys=False).apply(_stitch_day, trial=trial)
    if not np.isfinite(score).all() or not score.index.is_unique:
        raise ValueError('Nonfinite prediction or duplicate index')
    return score.rename('Return')
