"""Official-score-compatible accounting plus explicitly separate cost diagnostics."""
import numpy as np
import pandas as pd
from scipy.stats import norm, skew, kurtosis, spearmanr


def weights(signal):
    s = signal.sort_index().fillna(0.)
    r = s.groupby(level='Date').rank(method='first')
    n = s.groupby(level='Date').transform('count')
    q = (np.ceil(5 * (r-1)/(n-1))-1).clip(0, 4)
    return (q-2)/n/1.2, q


def rankic(signal, target):
    good = signal.notna() & target.notna()
    x = signal.where(good).groupby(level='Date').rank()
    y = target.where(good).groupby(level='Date').rank()
    x = x-x.groupby(level='Date').transform('mean')
    y = y-y.groupby(level='Date').transform('mean')
    return (x*y).groupby(level='Date').sum()/np.sqrt(
        (x*x).groupby(level='Date').sum() * (y*y).groupby(level='Date').sum())


def daily_account(signal, target):
    signal = signal.reindex(target.index).sort_index()
    target = target.reindex(signal.index)
    w, q = weights(signal)
    turn = w.groupby(level='Code').diff().abs().fillna(w.abs())
    gross = w*target
    cost = .001*turn
    # Official pandas expression drops cost on a missing-target row. Keep its
    # exact score, and report all-position cost/conservative PL separately.
    out = pd.DataFrame({
        'gross': gross.groupby(level='Date').sum(),
        'net': (gross-cost).groupby(level='Date').sum(),
        'turnover': turn.groupby(level='Date').sum(),
        'cost_all': cost.groupby(level='Date').sum(),
        'long': gross.where(w>0, 0).groupby(level='Date').sum(),
        'short': gross.where(w<0, 0).groupby(level='Date').sum(),
        'rankic': rankic(signal, target),
        'label_coverage': target.notna().groupby(level='Date').mean(),
    })
    out['cost'] = out['gross']-out['net']
    out['net_all_cost'] = out['gross']-out['cost_all']
    for k in range(5):
        out[f'q{k+1}'] = target.where(q==k).groupby(level='Date').mean()
    return out


def sharpe(r):
    r = np.asarray(r, dtype=float)
    return float(np.mean(r)/np.std(r, ddof=1)*np.sqrt(252)) if np.std(r, ddof=1)>0 else 0.


def hac_t(values, lag=5):
    x = np.asarray(values.dropna(), dtype=float)
    if len(x)<3:
        return np.nan
    e = x-x.mean()
    var = np.dot(e,e)/len(x)
    for k in range(1, min(lag+1,len(x))):
        var += 2*(1-k/(lag+1))*np.dot(e[k:], e[:-k])/len(x)
    return float(x.mean()/np.sqrt(max(var, 1e-30)/len(x)))


def metrics(d):
    additive = np.r_[0., d.net.cumsum()]
    wealth = np.r_[1., (1+d.net).cumprod()]
    q = [d[f'q{k}'].mean() for k in range(1,6)]
    return {
        'days': len(d), 'gross_sharpe': sharpe(d.gross), 'net_sharpe': sharpe(d.net),
        'net_all_cost_sharpe': sharpe(d.net_all_cost),
        'rankic': float(d.rankic.mean()), 'rankic_t_hac5': hac_t(d.rankic),
        'rankic_hit': float((d.rankic.dropna()>0).mean()), 'rankic_days': int(d.rankic.notna().sum()),
        'annual_gross': float(d.gross.mean()*252), 'annual_net': float(d.net.mean()*252),
        'annual_cost': float(d.cost.mean()*252), 'annual_cost_all': float(d.cost_all.mean()*252),
        'turnover': float(d.turnover.mean()),
        'max_drawdown_additive': float(np.min(additive-np.maximum.accumulate(additive))),
        'max_drawdown_compound': float(np.min(wealth/np.maximum.accumulate(wealth)-1)),
        'annual_long': float(d.long.mean()*252), 'annual_short': float(d.short.mean()*252),
        'period_gross': float(d.gross.sum()), 'period_net': float(d.net.sum()),
        'period_cost': float(d.cost.sum()), 'label_coverage': float(d.label_coverage.mean()),
        'q_monotonicity': float(spearmanr(range(1,6),q).statistic) if len(set(q))>1 else 0.,
        **{f'q{k+1}_daily_return':float(v) for k,v in enumerate(q)},
    }


def bootstrap_delta(base, candidate, seed=20260908, reps=1000, block=20):
    b,c = np.asarray(base), np.asarray(candidate)
    rng = np.random.default_rng(seed)
    starts = rng.integers(0,len(b),size=(reps,int(np.ceil(len(b)/block))))
    ix = ((starts[:,:,None]+np.arange(block))%len(b)).reshape(reps,-1)[:,:len(b)]
    bs,cs = b[ix],c[ix]
    ds = np.sqrt(252)*(cs.mean(axis=1)/cs.std(axis=1,ddof=1)-bs.mean(axis=1)/bs.std(axis=1,ddof=1))
    return {'low':float(np.quantile(ds,.025)), 'high':float(np.quantile(ds,.975)),
            'bootstrap_positive_fraction':float((ds>0).mean()), 'reps':reps,'block':block,'seed':seed}


def dsr(values, variance_daily_sr, trials):
    x=np.asarray(values,dtype=float)
    sr=x.mean()/x.std(ddof=1)
    gamma=.5772156649015329
    threshold=np.sqrt(max(variance_daily_sr,0))*((1-gamma)*norm.ppf(1-1/trials)+gamma*norm.ppf(1-1/(trials*np.e)))
    sk=float(skew(x,bias=False)); ku=float(kurtosis(x,fisher=False,bias=False))
    denom=np.sqrt(max(1-sk*sr+(ku-1)*sr*sr/4,1e-30))
    value=norm.cdf((sr-threshold)*np.sqrt(len(x)-1)/denom)
    return {'dsr':float(value),'daily_sr':float(sr),'daily_sr_threshold':float(threshold),
            'daily_sr_cross_trial_variance':float(variance_daily_sr),'trials':trials,
            'n':len(x),'skew':sk,'nonexcess_kurtosis':ku}
