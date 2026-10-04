"""Fixed PIT characteristics for diagnostics only; no targets or strategy API."""
import numpy as np
import pandas as pd
from stock_comp_2026.strategies.dm_slow_multifactor import features as slow

DESCRIPTORS = ['bp', 'ey', 'roe', 'cf_assets', 'equity_assets',
               'sales_growth', 'operating_growth', 'profit_growth']
GROWTH = {'sales_growth': 'NetSales', 'operating_growth': 'OperatingProfit',
          'profit_growth': 'Profit'}
META = ['TypeOfDocument', 'TypeOfCurrentPeriod', 'CurrentPeriodStartDate',
        'CurrentPeriodEndDate', 'CurrentFiscalYearStartDate', 'CurrentFiscalYearEndDate']
FIN_COLUMNS = list(dict.fromkeys(slow.FINS_COLUMNS + META + list(GROWTH.values())))


def standardize(values):
    """Daily linear 1/99 winsorization and sample z score, preserving missing."""
    values = slow.finite(values)
    low, high = slow.group_quantile_bounds(values, values.index.get_level_values('Date'))
    clipped = values.clip(lower=low, upper=high)
    groups = clipped.groupby('Date', sort=False)
    sd = groups.transform('std')
    out = (clipped - groups.transform('mean')) / sd.where(sd > 0)
    return out.where(sd.ne(0), clipped.where(clipped.isna(), 0.))


def terciles(values, keys=None):
    """Average ties, fixed percentile boundaries; missing has no bucket."""
    if keys is None:
        keys = values.index.get_level_values('Date')
    rank = values.groupby(keys, sort=False).rank(method='average', pct=True)
    return np.ceil(3 * rank).clip(1, 3).astype('float64')


def annual_reports(fins):
    duration = (fins.CurrentPeriodEndDate - fins.CurrentPeriodStartDate).dt.days + 1
    return (fins.TypeOfCurrentPeriod.eq('FY') &
            fins.TypeOfDocument.astype(str).str.startswith('FYFinancialStatements_') &
            fins.CurrentPeriodStartDate.eq(fins.CurrentFiscalYearStartDate) &
            fins.CurrentPeriodEndDate.eq(fins.CurrentFiscalYearEndDate) &
            (fins.CurrentPeriodEndDate <= fins.index.get_level_values('Date')) &
            duration.isin([365, 366]))


def growth_events(fins):
    """Pair disclosed annual actuals with the exact prior-year fiscal interval.

    Same document/accounting/consolidation basis; denominator strictly positive.
    Corrections use the prior report known at the current disclosure, never a
    subsequently restated comparator. A new incomparable FY invalidates growth.
    """
    result = pd.DataFrame(np.nan, index=fins.index, columns=list(GROWTH))
    report = annual_reports(fins)
    used = pd.Series(False, index=fins.index)
    records = []
    for code, frame in fins.groupby('Code', sort=False, observed=True):
        history, latest_end = {}, pd.Timestamp.min
        for idx, row in frame.iterrows():
            if not report.loc[idx]:
                # Nonstandard full-year actual statements invalidate current growth.
                if (str(row.TypeOfDocument).startswith('FYFinancialStatements_') and
                    pd.notna(row.CurrentPeriodEndDate) and row.CurrentPeriodEndDate >= latest_end):
                    used.loc[idx] = True
                    latest_end = row.CurrentPeriodEndDate
                continue
            start, end, basis = row.CurrentPeriodStartDate, row.CurrentPeriodEndDate, str(row.TypeOfDocument)
            key = (start, end, basis)
            previous = history.get((start - pd.DateOffset(years=1), end - pd.DateOffset(years=1), basis))
            current_latest = end >= latest_end
            if current_latest:
                used.loc[idx] = True
                latest_end = end
                for name, field in GROWTH.items():
                    old = previous[1][field] if previous else np.nan
                    value = row[field]
                    if pd.notna(value) and pd.notna(old) and old > 0:
                        result.loc[idx, name] = value / old - 1.
                records.append({'Date': idx[0], 'Code': str(code), 'period_start': start,
                                'period_end': end, 'basis': basis,
                                'previous_disclosure': previous[0][0] if previous else pd.NaT,
                                'previous_period_start': previous[1].CurrentPeriodStartDate if previous else pd.NaT,
                                'previous_period_end': previous[1].CurrentPeriodEndDate if previous else pd.NaT,
                                'matched_previous_fiscal_period': previous is not None})
            history[key] = (idx, row)
    return result, used, pd.DataFrame(records)


def backward(index, event_values):
    """Latest event including a NaN invalidation; signal is end of JST date."""
    if event_values.empty:
        return pd.DataFrame(np.nan, index=index, columns=list(event_values.columns) + ['disclosure_age_days'])
    base = index.to_frame(index=False)
    base['pos'] = np.arange(len(base))
    events = event_values.reset_index().rename(columns={'Date': 'disclosed'})
    joined = pd.merge_asof(base.sort_values('Date', kind='stable'),
                           events.sort_values('disclosed', kind='stable'), by='Code',
                           left_on='Date', right_on='disclosed', direction='backward',
                           allow_exact_matches=True).sort_values('pos')
    out = pd.DataFrame(joined[event_values.columns].to_numpy(dtype=float), index=index,
                       columns=event_values.columns)
    out['disclosure_age_days'] = (joined.Date - joined.disclosed).dt.total_seconds().to_numpy() / 86400
    return out


def build(index, prices, financials):
    index = slow.canonical(pd.DataFrame(index=index)).index
    prices, fins = slow.canonical(prices).reindex(index), slow.canonical(financials)
    for c in set(slow.FINS_COLUMNS + list(GROWTH.values())):
        fins[c] = slow.finite(pd.to_numeric(fins[c], errors='coerce'))
    for c in META[2:]:
        fins[c] = pd.to_datetime(fins[c])
    close = slow.finite(prices.Close).where(prices.Close > 0)
    f = slow.asof_financials(index, fins)
    raw = pd.DataFrame(index=index)
    raw['bp'] = f.Equity / f[slow.SHARES].where(f[slow.SHARES] > 0) / close
    raw['ey'] = f.ForecastEarningsPerShare / close
    annual = fins.loc[annual_reports(fins)]
    quality = pd.DataFrame({'roe': annual.Profit / annual.Equity.where(annual.Equity > 0),
                            'cf_assets': annual.CashFlowsFromOperatingActivities / annual.TotalAssets.where(annual.TotalAssets > 0)}, index=annual.index)
    q = backward(index, quality)
    raw[['roe', 'cf_assets']] = q[['roe', 'cf_assets']]
    balance = fins.loc[fins.Equity.notna() & fins.TotalAssets.gt(0)]
    b = backward(index, (balance.Equity / balance.TotalAssets).rename('equity_assets').to_frame())
    raw['equity_assets'] = b.equity_assets
    growth, used, pairs = growth_events(fins)
    g = backward(index, growth.loc[used])
    raw[list(GROWTH)] = g[list(GROWTH)]
    raw = raw[DESCRIPTORS].replace([np.inf, -np.inf], np.nan).astype('float64')
    z = pd.DataFrame({c: standardize(raw[c]) for c in DESCRIPTORS}, index=index)
    ages = pd.DataFrame({'annual_quality_age_days': q.disclosure_age_days,
                         'balance_age_days': b.disclosure_age_days,
                         'growth_age_days': g.disclosure_age_days}, index=index)
    return raw, z, ages, pairs


def neutralize(score, z):
    """One daily unregularized OLS, all fixed descriptors, complete cases only."""
    residual = pd.Series(np.nan, index=score.index, name='residual')
    rows = []
    complete = z.notna().all(axis=1) & score.notna()
    for date, x in z.loc[complete].groupby('Date', sort=False):
        if len(x) <= len(DESCRIPTORS) + 1:
            continue
        design = np.column_stack([np.ones(len(x)), x.to_numpy()])
        coef, _, rank, _ = np.linalg.lstsq(design, score.loc[x.index].to_numpy(), rcond=None)
        values = score.loc[x.index].to_numpy() - design @ coef
        residual.loc[x.index] = values
        rows.append({'Date': date, 'n': len(x), 'design_rank': rank,
                     'max_normal_equation_error': float(np.abs(design.T @ values).max()),
                     **dict(zip(['intercept'] + DESCRIPTORS, coef))})
    columns = ['Date', 'n', 'design_rank', 'max_normal_equation_error', 'intercept'] + DESCRIPTORS
    return residual, pd.DataFrame(rows, columns=columns).set_index('Date')


def matching_weights(w, bp, growth):
    """Fixed 3x3 matching: min(original long, short cell mass), then scale.

    Original relative within-side weights retained. Only overlapping cells take
    risk; total side mass is min(original total long, short). No optimization.
    """
    a, b = terciles(bp), terciles(growth)
    cell = (a - 1) * 3 + b
    keys = [w.index.get_level_values('Date'), cell]
    long, short = w.clip(lower=0), (-w).clip(lower=0)
    lm = long.groupby(keys, sort=False).transform('sum')
    sm = short.groupby(keys, sort=False).transform('sum')
    common = np.minimum(lm, sm)
    matched = ((long / lm.where(lm > 0) - short / sm.where(sm > 0)) * common).fillna(0.)
    mass = matched.clip(lower=0).groupby('Date').transform('sum')
    original_mass = np.minimum(long.groupby('Date').transform('sum'), short.groupby('Date').transform('sum'))
    matched *= (original_mass / mass.where(mass > 0)).fillna(0.)
    return matched.rename('w'), cell
