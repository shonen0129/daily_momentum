"""Causal competition features. No label files are accepted by this module."""
from pathlib import Path
import numpy as np
import pandas as pd

INPUT_COLUMNS = {
    'raw_return_1day': ['Return'], 'beta_1day': ['Return'],
    'topix_return_1day': ['Return'],
    'prices_daily_quotes': ['Open', 'High', 'Low', 'Close', 'Volume', 'TurnoverValue',
                            'MorningOpen', 'MorningClose', 'MorningVolume',
                            'AfternoonOpen', 'AfternoonClose', 'AfternoonVolume'],
    'listed_info': ['Sector17Code', 'ScaleCategory'],
}
MOMENTUM_NAMES = ['res5s1', 'res10s1', 'res20s1', 'res60s1', 'res20s0',
                  'res20s2', 'raw20s1', 'sector20s1', 'equal_5_20_60']
STATE_NAMES = ['liquidity_level', 'liquidity_shock', 'volume_shock', 'pwv', 'vwp',
               'am', 'pm', 'intraday_range', 'volume_ratio']


def load_inputs(directory, split='train', names=None):
    if split not in ('train', 'valid'):
        raise ValueError('Unknown feature split')
    result = {}
    for name, columns in INPUT_COLUMNS.items():
        if names is not None and name not in names:
            continue
        frame = pd.read_parquet(Path(directory) / f'{name}_{split}.parquet', columns=columns)
        if not frame.index.is_unique:
            raise ValueError(f'Duplicate index in {name}')
        result[name] = frame.sort_index()
    return result


def build_momentum(inputs):
    """Selected res60s1 only, exactly equivalent to build_features()['res60s1']."""
    r = inputs['raw_return_1day']['Return'].sort_index().replace([np.inf, -np.inf], np.nan)
    idx = r.index
    dates = idx.get_level_values('Date')
    beta = inputs['beta_1day']['Return'].reindex(idx)
    market = pd.Series(inputs['topix_return_1day']['Return'].reindex(dates).to_numpy(), index=idx)
    residual = (r-beta*market).replace([np.inf, -np.inf], np.nan)
    groups = segment_keys(idx)
    lagged = residual.groupby(groups, sort=False).shift(1)
    value = lagged.groupby(groups, sort=False).transform(
        lambda v: v.rolling(60, min_periods=60).sum())
    return centered_rank(value).rename('res60s1')


def centered_rank(s):
    s = s.replace([np.inf, -np.inf], np.nan)
    rank = s.groupby(level='Date').rank(method='average', pct=True)
    return (2 * (rank - rank.groupby(level='Date').transform('mean'))).fillna(0.)


def segment_keys(index):
    """Reset state after >20 absent exchange dates (code reuse/relisting)."""
    dates = index.get_level_values('Date')
    calendar = dates.unique().sort_values()
    ordinal = pd.Series(calendar.get_indexer(dates), index=index)
    code = index.get_level_values('Code')
    starts = ordinal.groupby(code, sort=False).diff().gt(20)
    segment = starts.groupby(code, sort=False).cumsum().astype(int)
    return [code, segment]


def smooth(s, alpha):
    return s.groupby(segment_keys(s.index), sort=False).transform(
        lambda v: v.ewm(alpha=alpha, adjust=False).mean())


def fit_linear(x, y, ridge=1.0):
    """Training-only imputation/scaling, stored for exactly matching inference."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mean = np.nanmean(np.where(np.isfinite(x), x, np.nan), axis=0)
    mean = np.nan_to_num(mean)
    x = np.where(np.isfinite(x), x, mean)
    scale = x.std(axis=0)
    scale[scale < 1e-8] = 1
    z = np.column_stack([np.ones(len(x)), (x - mean) / scale])
    penalty = np.eye(z.shape[1]) * ridge
    penalty[0, 0] = 0
    coef = np.linalg.solve(z.T @ z + penalty, z.T @ y)
    return {'mean': mean.tolist(), 'scale': scale.tolist(), 'coef': coef.tolist()}


def predict_linear(x, model):
    x = np.asarray(x, dtype=float)
    mean, scale, coef = (np.asarray(model[k]) for k in ('mean', 'scale', 'coef'))
    x = np.where(np.isfinite(x), x, mean)
    z = (x - mean) / scale
    result = np.full(len(x), coef[0], dtype=float)
    for j in range(z.shape[1]):
        result = result + z[:, j] * coef[j+1]
    return result


def build_features(inputs):
    r = inputs['raw_return_1day']['Return'].sort_index().replace([np.inf, -np.inf], np.nan)
    idx = r.index
    dates = idx.get_level_values('Date')
    groups = segment_keys(idx)
    p = inputs['prices_daily_quotes'].reindex(idx).replace([np.inf, -np.inf], np.nan)
    listed = inputs['listed_info'].reindex(idx)
    beta = inputs['beta_1day']['Return'].reindex(idx)
    market = pd.Series(inputs['topix_return_1day']['Return'].reindex(dates).to_numpy(), index=idx)
    residual = (r - beta * market).replace([np.inf, -np.inf], np.nan)
    sector = listed['Sector17Code'].fillna('unknown').astype(str)
    sr = residual - residual.groupby([dates, sector]).transform('mean')

    def lag1(s):
        return s.groupby(groups, sort=False).shift(1)

    def roll(s, window, method='mean'):
        return s.groupby(groups, sort=False).transform(
            lambda v: getattr(v.rolling(window, min_periods=window), method)())

    f = pd.DataFrame(index=idx)
    lagres = lag1(residual)
    for h in (5, 10, 20, 60):
        f[f'res{h}s1'] = centered_rank(roll(lagres, h, 'sum'))
    f['res20s0'] = centered_rank(roll(residual, 20, 'sum'))
    f['res20s2'] = centered_rank(roll(residual.groupby(groups, sort=False).shift(2), 20, 'sum'))
    f['raw20s1'] = centered_rank(roll(lag1(r), 20, 'sum'))
    f['sector20s1'] = centered_rank(roll(lag1(sr), 20, 'sum'))
    f['equal_5_20_60'] = f[['res5s1', 'res20s1', 'res60s1']].mean(axis=1)

    value = p['TurnoverValue'].where(p['TurnoverValue'] > 0)
    volume = p['Volume'].where(p['Volume'] > 0)
    v60, q60 = roll(value, 60, 'median'), roll(volume, 60, 'median')
    liq = np.log(v60)
    shock = np.log(roll(value, 5, 'median') / v60)
    volshock = np.log(volume / q60)
    volatility = roll(residual, 60, 'std')
    size = listed['ScaleCategory'].map({'TOPIX Core30': 5., 'TOPIX Large70': 4.,
                                      'TOPIX Mid400': 3., 'TOPIX Small 1': 2.,
                                      'TOPIX Small 2': 1.}).astype(float)
    # raw_return[t] is open[t-1] -> open[t]. Prior day's trading is known and
    # temporally relevant; contemporaneous intraday volume ends after that move.
    impact_x = pd.DataFrame({'value': lag1(np.log(value)), 'liquidity': lag1(liq),
                             'volume': lag1(volshock), 'volatility': lag1(np.log(volatility)),
                             'size': lag1(size)}, index=idx).replace([np.inf, -np.inf], np.nan)
    observed = residual.abs()
    historical = roll(lag1(observed), 60)
    expected = historical.copy()
    impact_audit = []
    for year in sorted(dates.year.unique()):
        start = pd.Timestamp(year=int(year), month=1, day=1)
        past = (dates < start) & observed.notna() & impact_x.notna().all(axis=1)
        now = dates.year == year
        if dates[past].nunique() < 126:
            continue
        # Fixed date subsample, independent of how many future rows are supplied.
        past_dates = dates[past].unique().sort_values()[::5]
        fit = past & dates.isin(past_dates)
        model = fit_linear(impact_x.loc[fit], np.log(observed.loc[fit].clip(lower=1e-6)))
        pred = np.exp(np.clip(predict_linear(impact_x.loc[now], model), -14, 0))
        expected.loc[now] = pred
        impact_audit.append({'year': int(year), 'max_fit_date': str(dates[fit].max().date()),
                             'rows': int(fit.sum()), 'model': model})
    impact = observed - expected
    f['liquidity_level'] = centered_rank(liq)
    f['liquidity_shock'] = centered_rank(shock)
    f['volume_shock'] = centered_rank(volshock)
    f['pwv'] = centered_rank(impact.clip(lower=0))
    f['vwp'] = centered_rank((-impact).clip(lower=0))
    f['pwv_historical'] = centered_rank((observed-historical).clip(lower=0))
    f['vwp_historical'] = centered_rank((historical-observed).clip(lower=0))
    am = p['MorningClose'] / p['MorningOpen'].where(p['MorningOpen'] > 0) - 1
    pm = p['AfternoonClose'] / p['AfternoonOpen'].where(p['AfternoonOpen'] > 0) - 1
    f['am'], f['pm'] = centered_rank(am), centered_rank(pm)
    f['intraday_range'] = centered_rank((p['High']-p['Low'])/p['Open'].where(p['Open']>0))
    f['volume_ratio'] = centered_rank(np.log(p['AfternoonVolume'].where(p['AfternoonVolume']>0) /
                                              p['MorningVolume'].where(p['MorningVolume']>0)))
    f['liquidity_shock_value'] = shock.fillna(0.)
    f['am_value'], f['pm_value'] = am.fillna(0.), pm.fillna(0.)
    f['momentum_available'] = roll(lagres, 60, 'sum').notna().astype(float)
    f = f.replace([np.inf, -np.inf], np.nan).fillna(0.)
    # Raw aligned state is retained for the new short confirmation formulas.
    # Add after finite-score filling: missing state must not become confirmation.
    f['residual_value'] = residual
    f['impact_value'] = impact
    f['lag_liquidity_shock'] = lag1(shock)
    f['lag_volume_shock'] = lag1(volshock)
    f.attrs['impact_audit'] = impact_audit
    return f


def model_features(f, momentum, include_momentum=False):
    x = f[STATE_NAMES].copy()
    if include_momentum:
        x['momentum'] = momentum
    x['m_pwv'] = momentum * f['pwv']
    x['m_vwp'] = momentum * f['vwp']
    x['m_liquidity'] = momentum * f['liquidity_shock']
    x['m_volume'] = momentum * f['volume_shock']
    x['vwp_intraday'] = f['vwp'] * (f['pm'] - f['am'])
    return x
