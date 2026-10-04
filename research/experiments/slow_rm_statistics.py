"""Fixed descriptive statistics and resampling, separated from inference."""
import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr, norm
from research import evaluation

GROUPS = ['ALL', 'LONG', 'SHORT'] + [f'Q{k}' for k in range(1, 6)] + [
    f'CELL3_{k}' for k in range(1, 10)] + [f'CELL5_{k}' for k in range(1, 26)]
VARIANTS = ['RM', 'RM_SLOW', 'RM_CELL3', 'RM_CELL5']


def group_masks(frame):
    return [np.ones(len(frame), dtype=bool), frame.slow_q.to_numpy() >= 4,
            frame.slow_q.to_numpy() <= 2] + [frame.slow_q.to_numpy() == k for k in range(1, 6)] + [
                frame.cell3.to_numpy() == k for k in range(1, 10)] + [
                frame.cell5.to_numpy() == k for k in range(1, 26)]


def batch_stat(x, y, bins=3):
    """All signal rows define bins; only finite labels enter means and RankIC."""
    x = np.atleast_2d(x)
    reps, n = x.shape
    if not n:
        return np.full(reps, np.nan), np.full(reps, np.nan)
    rank = rankdata(x, axis=1, method='average')
    q = np.ceil(bins * rank / n).clip(1, bins)
    valid = np.isfinite(y)
    yl = np.where(valid, y, 0.)
    def mean(mask):
        mask = mask & valid
        count = mask.sum(axis=1)
        return np.divide((mask * yl).sum(axis=1), count,
                         out=np.full(reps, np.nan), where=count > 0)
    spread = mean(q == bins) - mean(q == 1)
    if valid.sum() < 3:
        return spread, np.full(reps, np.nan)
    a = rankdata(x[:, valid], axis=1, method='average')
    b = rankdata(y[valid], method='average')
    a = a - a.mean(axis=1, keepdims=True)
    b = b - b.mean()
    denom = np.sqrt((a*a).sum(axis=1) * (b*b).sum())
    ic = np.divide((a*b).sum(axis=1), denom, out=np.full(reps, np.nan), where=denom > 0)
    return spread, ic


def observed(panel, target, dates):
    rows = []
    for date, frame in panel.loc[panel.index.get_level_values('Date').isin(dates)].groupby('Date', sort=False):
        y = target.reindex(frame.index).to_numpy()
        for variant in VARIANTS:
            for group, mask in zip(GROUPS, group_masks(frame)):
                x, t = frame[variant].to_numpy()[mask], y[mask]
                spread, ic = batch_stat(x, t)
                record = {'Date': date, 'variant': variant, 'group': group,
                          'stocks': len(x), 'label_stocks': int(np.isfinite(t).sum()),
                          'spread': spread[0], 'rankic': ic[0],
                          'target_mean': np.nanmean(t) if np.isfinite(t).any() else np.nan,
                          'slow_average_weight': frame.slow_w.to_numpy()[mask].mean() if mask.any() else np.nan,
                          'slow_gross_contribution': np.nansum(frame.slow_w.to_numpy()[mask] * t)}
                for n in (3, 5):
                    q = np.ceil(n * rankdata(x, method='average') / len(x)).clip(1, n) if len(x) else []
                    for k in range(1, n+1):
                        values = t[np.asarray(q) == k]
                        record[f'b{n}_{k}'] = np.nanmean(values) if np.isfinite(values).any() else np.nan
                rows.append(record)
    return pd.DataFrame(rows)


def scopes(dates):
    return [('POOLED', dates), ('EX2016', dates[dates.year != 2016])] + [
        (str(y), dates[dates.year == y]) for y in range(2011, 2017)]


def summary(daily):
    dates = pd.DatetimeIndex(daily.Date.unique()).sort_values()
    rows = []
    for (variant, group), frame in daily.groupby(['variant', 'group'], sort=False):
        frame = frame.set_index('Date').reindex(dates)
        for scope, ds in scopes(dates):
            g = frame.loc[ds]
            q5 = [g[f'b5_{k}'].mean() for k in range(1, 6)]
            rows.append({'variant': variant, 'group': group, 'scope': scope,
                         'days': len(g), 'spread_days': g.spread.notna().sum(),
                         'average_stock_count': g.stocks.mean(), 'stock_days': g.stocks.sum(),
                         'average_label_count': g.label_stocks.mean(),
                         'support_ge10_fraction': (g.stocks >= 10).mean(),
                         'support_sufficient': bool(g.stocks.mean() >= 10 and (g.stocks >= 10).mean() >= .8),
                         'rankic': g.rankic.mean(), 'rankic_hac5_t': evaluation.hac_t(g.rankic),
                         'rankic_hit': (g.rankic.dropna() > 0).mean(),
                         'spread': g.spread.mean(), 'spread_hac5_t': evaluation.hac_t(g.spread),
                         'spread_gross_sharpe': evaluation.sharpe(g.spread.dropna()) if g.spread.notna().sum() > 1 else np.nan,
                         'q5_q1': q5[-1] - q5[0],
                         'q5_q1_gross_sharpe': evaluation.sharpe((g.b5_5-g.b5_1).dropna()) if (g.b5_5-g.b5_1).notna().sum() > 1 else np.nan,
                         'q_monotonicity': spearmanr(range(1, 6), q5).statistic,
                         'target_mean': g.target_mean.mean(),
                         'slow_average_weight': g.slow_average_weight.mean(),
                         'annual_slow_gross_contribution': 252*g.slow_gross_contribution.mean(),
                         **{f'tercile_{k}': g[f'b3_{k}'].mean() for k in range(1, 4)},
                         **{f'q{k}': v for k, v in enumerate(q5, 1)}})
    result = pd.DataFrame(rows)
    years = result.loc[result.scope.isin([str(y) for y in range(2011, 2016)])]
    positives = years.assign(positive=years.spread > 0).groupby(['variant', 'group']).positive.sum()
    result['positive_full_years'] = [positives.loc[(r.variant, r.group)] for r in result.itertuples()]
    result['hypothesis'] = result.group.map({'LONG':'H1','SHORT':'H2','CELL3_9':'H3'}).fillna('secondary')
    result.loc[result.variant != 'RM', 'hypothesis'] = 'secondary_robustness'
    return result


def hac_batch(values, lag=5):
    """Match evaluation.hac_t including compressing missing sessions."""
    values = np.asarray(values, dtype=float)
    result = []
    for row in values:
        result.append(evaluation.hac_t(pd.Series(row)))
    return np.asarray(result)


def bootstrap(daily, config, folder):
    primary = daily.loc[daily.variant == 'RM']
    wide = primary.pivot(index='Date', columns='group', values='spread')
    ic = primary.loc[primary.group == 'ALL'].set_index('Date').rankic.reindex(wide.index)
    cells = [f'CELL3_{k}' for k in range(1, 10)]
    counts = primary.pivot(index='Date', columns='group', values='stocks')[cells]
    usable = wide[cells].notna()
    pooled = (wide[cells] * counts).sum(axis=1) / counts.where(usable, 0).sum(axis=1).replace(0, np.nan)
    data = pd.DataFrame({'ALL_RankIC':ic, 'LONG':wide.LONG, 'SHORT':wide.SHORT,
                         'CELL3_9':wide.CELL3_9, 'WEIGHTED_CELL3':pooled})
    data.to_csv(folder/'bootstrap_estimands_daily.csv', index_label='Date')
    rows = []
    for scope, ds in scopes(data.index)[:2]:
        a = data.loc[ds].to_numpy()
        for block in config['blocks']:
            rng = np.random.default_rng(config['seed'])
            starts = rng.integers(0, len(a), size=(config['reps'], int(np.ceil(len(a)/block))))
            ix = ((starts[:,:,None] + np.arange(block)) % len(a)).reshape(config['reps'], -1)[:,:len(a)]
            draws = np.nanmean(a[ix], axis=1)
            pd.DataFrame(draws, columns=data.columns).to_parquet(folder/f'bootstrap_{scope}_block{block}_draws.parquet')
            for j, name in enumerate(data):
                rows.append({'scope':scope, 'estimand':name, 'block':block, 'reps':config['reps'],
                             'seed':config['seed'], 'observed':np.nanmean(a[:,j]),
                             'low':np.nanquantile(draws[:,j],.025), 'high':np.nanquantile(draws[:,j],.975),
                             'positive_fraction':np.mean(draws[:,j] > 0)})
    return pd.DataFrame(rows)


def bh(p):
    a = np.asarray(p, dtype=float)
    result = np.full(len(a), np.nan)
    ix = np.flatnonzero(np.isfinite(a))
    order = ix[np.argsort(a[ix])]
    if len(order):
        result[order] = np.minimum(1., np.minimum.accumulate((a[order]*len(order)/np.arange(1,len(order)+1))[::-1])[::-1])
    return result
