"""Official-compatible accounting and separately labelled asymmetric diagnostics."""
import numpy as np
import pandas as pd
from research.evaluation import weights, daily_account, metrics, sharpe, rankic, hac_t


def safe_dates(calendar, years):
    """Exclude labels whose t+2 leaves their evaluation year or available input."""
    calendar = pd.DatetimeIndex(calendar).sort_values().unique()
    ok = np.zeros(len(calendar), dtype=bool)
    for i in range(max(0, len(calendar)-2)):
        ok[i] = calendar[i].year in years and calendar[i+2].year == calendar[i].year
    return calendar[ok]


def side_account(w, target):
    result = {}
    for side, leg in [('long', w.clip(lower=0)), ('short', w.clip(upper=0))]:
        turn = leg.groupby(level='Code').diff().abs().fillna(leg.abs())
        cost = .001*turn
        gross = leg*target
        result[side+'_gross'] = gross.groupby(level='Date').sum()
        result[side+'_net'] = (gross-cost).groupby(level='Date').sum()
        result[side+'_net_all_cost'] = result[side+'_gross']-cost.groupby(level='Date').sum()
        result[side+'_turnover'] = turn.groupby(level='Date').sum()
        result[side+'_cost_all'] = cost.groupby(level='Date').sum()
    return pd.DataFrame(result)


def tails(score, target, population):
    """Tie-inclusive 20/80 quantiles; positive evidence required for short tail."""
    s = score.where(population)
    ranks = s.groupby(level='Date').rank(method='average', pct=True)
    lo = ranks.groupby(level='Date').transform('quantile', .2)
    hi = ranks.groupby(level='Date').transform('quantile', .8)
    high = target.where((ranks >= hi) & (s > 0)).groupby(level='Date').mean()
    low = target.where(ranks <= lo).groupby(level='Date').mean()
    return pd.DataFrame({'short_tail_high': high, 'short_tail_low': low,
                         'short_tail_gap': high-low})


def account(signal, target, short, population, baseline=None):
    signal = signal.reindex(target.index).sort_index()
    target = target.reindex(signal.index)
    d = daily_account(signal, target)
    w, _ = weights(signal)
    legs = side_account(w, target)
    d = d.join(legs).join(tails(short.reindex(signal.index), target, population.reindex(signal.index)))
    np.testing.assert_allclose(d.long_cost_all+d.short_cost_all, d.cost_all, atol=1e-15, rtol=0)
    np.testing.assert_allclose(d.long_net+d.short_net, d.net, atol=1e-15, rtol=0)
    rank = signal.groupby(level='Date').rank(method='first', pct=True)
    d['bottom_decile'] = target.where(rank <= .1).groupby(level='Date').mean()
    d['top_decile'] = target.where(rank > .9).groupby(level='Date').mean()
    if baseline is not None:
        bw, _ = weights(baseline.reindex(signal.index))
        for side, m, bm in [('long', w > 0, bw > 0), ('short', w < 0, bw < 0)]:
            d[side+'_overlap'] = (m & bm).groupby(level='Date').sum()/bm.groupby(level='Date').sum()
    return d


def extended_metrics(d):
    out = metrics(d)
    for side in ['long', 'short']:
        for kind in ['gross', 'net', 'net_all_cost']:
            out[f'annual_{side}_{kind}'] = float(d[f'{side}_{kind}'].mean()*252)
            out[f'{side}_{kind}_sharpe'] = sharpe(d[f'{side}_{kind}'])
        for kind in ['turnover', 'cost_all']:
            out[f'{side}_{kind}'] = float(d[f'{side}_{kind}'].mean()*(252 if kind == 'cost_all' else 1))
    for name in ['short_tail_high', 'short_tail_low', 'short_tail_gap', 'bottom_decile', 'top_decile', 'long_overlap', 'short_overlap']:
        if name in d:
            out[name] = float(d[name].mean())
    out['tail_paired_days'] = int(d.short_tail_gap.notna().sum()) if 'short_tail_gap' in d else 0
    return out


def fold_metrics(d):
    return [dict(year=int(y), **extended_metrics(v)) for y, v in d.groupby(d.index.year)]


def comparison(candidate, reference, rules):
    a = pd.DataFrame(candidate['folds']).set_index('year')
    b = pd.DataFrame(reference['folds']).set_index('year')
    ds = a.net_sharpe-b.net_sharpe
    dp = a.annual_short_net-b.annual_short_net
    ratio = a.turnover/b.turnover.replace(0, np.nan)
    joint = int(((ds > 0) & (dp > 0)).sum())
    tail_folds = int((a.short_tail_gap < 0).sum())
    checks = {
        'joint_improved_folds': joint >= rules['joint_improved_folds'],
        'median_delta_net_sr': ds.median() >= rules['median_delta_net_sr_min'],
        'worst_delta_net_sr': ds.min() >= rules['worst_delta_net_sr_min'],
        'turnover_ratio': ratio.notna().all() and ratio.median() <= rules['median_turnover_ratio_max'],
        'long_preserved': (a.annual_long_net-b.annual_long_net).median() >= rules['median_delta_annual_long_net_min'],
        'tail_separation': tail_folds >= rules['tail_separation_folds'],
    }
    delta_cols = ['rankic', 'net_sharpe', 'gross_sharpe', 'turnover', 'annual_cost',
                  'annual_short_net', 'annual_long_net', 'annual_net', 'max_drawdown_additive']
    deltas = (a[delta_cols]-b[delta_cols]).reset_index().to_dict('records')
    return {'reference': reference['id'], 'screen_pass': bool(all(checks.values())),
            'checks': {k: bool(v) for k, v in checks.items()}, 'joint_folds': joint,
            'median_delta_net_sr': float(ds.median()), 'worst_delta_net_sr': float(ds.min()),
            'median_turnover_ratio': float(ratio.median()), 'tail_folds': tail_folds, 'fold_deltas': deltas}


def choose(records, near=.05):
    """Deterministic preregistered representative; never adds scoring trials."""
    good = [r for r in records if r['comparison']['screen_pass']]
    pool = good or records
    count = max(r['comparison']['joint_folds'] for r in pool)
    pool = [r for r in pool if r['comparison']['joint_folds'] == count]
    best = max(r['comparison']['median_delta_net_sr'] for r in pool)
    pool = [r for r in pool if r['comparison']['median_delta_net_sr'] >= best-near]
    return min(pool, key=lambda r: (r['complexity'], r['spec']['lambda_'],
                                    r['spec'].get('gamma', 0), r['spec'].get('delta', 0),
                                    r['metrics']['turnover'], r['id']))


def fixed_long_weights(baseline, short):
    bw, _ = weights(baseline)
    frames = pd.DataFrame({'weight': bw, 'short': short.reindex(bw.index), 'baseline': baseline}).reset_index()
    parts = []
    for _, day in frames.groupby('Date', sort=True):
        long = day.weight > 0
        remaining = day.loc[~long].sort_values(['short', 'baseline', 'Code'], ascending=[False, True, True])
        slots = np.sort(day.loc[day.weight < 0, 'weight'].to_numpy())
        replacement = np.zeros(len(remaining))
        replacement[:len(slots)] = slots
        updated = day.weight.copy()
        updated.loc[remaining.index] = replacement
        parts.append(pd.Series(updated.to_numpy(), index=pd.MultiIndex.from_frame(day[['Date', 'Code']])) )
    out = pd.concat(parts).sort_index()
    np.testing.assert_array_equal(out[bw > 0], bw[bw > 0])
    np.testing.assert_allclose(out.groupby('Date').sum(), bw.groupby('Date').sum(), atol=1e-15, rtol=0)
    return out


def diagnostics(f, target, output):
    """Predeclared conditional tables, never used to invent thresholds."""
    dates = f.index.get_level_values('Date')
    valid = f.financial_available & (f.momentum_available > 0)
    weak = f.weak_price >= 2/3
    age_bin = pd.cut(f.financial_age, [-1, 20, 40, 60, 180, 450], labels=['0-20','21-40','41-60','61-180','181-450'])
    dimensions = {'all': pd.Series('all', index=f.index), 'period': f.period, 'basis': f.basis,
                  'sector': f.sector, 'age': age_bin.astype(str)}
    rows = []
    for name in ['D', 'W', 'F', 'fd_heavy', 'fd_equal']:
        eligible = {'D': f.cfo_yoy.notna(), 'W': f.cfo_assets.notna(), 'F': f.net_cash.notna()}.get(name, valid)
        s = f[name].where(eligible & valid)
        for dim, labels in dimensions.items():
            temp = pd.DataFrame({'Date': dates, 'year': dates.year, 'group': labels.to_numpy(),
                                 's': s.to_numpy(), 'target': target.reindex(f.index).to_numpy(),
                                 'weak': weak.to_numpy()})
            for (year, group), block in temp.groupby(['year','group'], observed=True):
                if year not in (2011, 2012, 2013, 2014):
                    continue
                for subset in ['all', 'weak_momentum']:
                    z = block if subset == 'all' else block.loc[block.weak]
                    z = z.dropna(subset=['s', 'target'])
                    if z.empty:
                        continue
                    ranks = z.groupby('Date').s.rank(pct=True)
                    z = z.assign(sr=ranks)
                    high = z.loc[z.sr >= 2/3].groupby('Date').target.mean()
                    low = z.loc[z.sr <= 1/3].groupby('Date').target.mean()
                    daily = z.groupby('Date')[['s','target']].corr(method='spearman').iloc[0::2, 1]
                    daily.index = daily.index.get_level_values(0)
                    rows.append(dict(feature=name, dimension=dim, group=str(group), subset=subset, year=int(year),
                                     rows=len(z), days=int(z.Date.nunique()), rankic=float(daily.mean()),
                                     rankic_t_hac5=hac_t(daily), high_return=float(high.mean()),
                                     low_return=float(low.mean()), high_minus_low=float((high-low).mean())))
    pd.DataFrame(rows).to_csv(output/'conditional_financial.csv', index=False)
    grid_rows = []
    for name in ['heavy','equal']:
        fd_rank = f[f'fd_{name}'].where(valid).groupby('Date').rank(pct=True)
        fd_bin = np.ceil(fd_rank*3).clip(1,3)
        wp_bin = np.ceil(f.weak_price*3).clip(1,3).where(valid)
        z = pd.DataFrame({'Date': dates, 'year': dates.year, 'fd_bin': fd_bin.to_numpy(),
                          'weak_bin': wp_bin.to_numpy(), 'target': target.reindex(f.index).to_numpy()})
        day = z.groupby(['year','Date','fd_bin','weak_bin'], observed=True).target.agg(['mean','count']).reset_index()
        table = day.groupby(['year','fd_bin','weak_bin']).agg(daily_return=('mean','mean'), rows=('count','sum'),days=('mean','count')).reset_index()
        table['weights'] = name
        grid_rows.append(table)
    pd.concat(grid_rows).to_csv(output/'fd_weak_3x3.csv', index=False)
