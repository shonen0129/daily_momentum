"""One preregistered Train-only source diagnostic; never creates a candidate."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
import platform
import resource
import shutil
import sys
import time

import numpy as np
import pandas as pd
import pyarrow
import scipy

from research import evaluation, firewall
from research.experiments import slow_multifactor as shared
from research.experiments import slow_mom60_equal as reuse
from research.experiments import slow_size_illiq_components as dc
from stock_comp_2026 import evaluate_script as official
from stock_comp_2026.strategies.dm_slow_multifactor import features as slow

ROOT = Path(__file__).resolve().parents[2]
sha, dump, exact = shared.sha, shared.dump, shared.exact
SLOW = 'SLOW_CONTROL'


def scopes(dates):
    return [('POOLED', dates), ('EX2016', dates[dates.year != 2016])] + [
        (str(y) if y != 2016 else '2016 partial', dates[dates.year == y]) for y in range(2011, 2017)]


def pearson(x, y):
    good = x.notna() & y.notna()
    a, b = x.where(good), y.where(good)
    a, b = a - a.groupby('Date').transform('mean'), b - b.groupby('Date').transform('mean')
    return (a*b).groupby('Date').sum() / np.sqrt((a*a).groupby('Date').sum() * (b*b).groupby('Date').sum())


def holdings(score, target):
    if not score.index.equals(target.index):
        raise ValueError('Account index mismatch')
    w, q = evaluation.weights(score)
    turn = w.groupby('Code').diff().abs().fillna(w.abs())
    cost_all = .001 * turn
    gross = w * target
    h = pd.DataFrame({'w': w, 'q': q, 'gross': gross.fillna(0.),
                      'net': (gross-cost_all).fillna(0.), 'turnover': turn,
                      'cost': cost_all.where(target.notna(), 0.), 'cost_all': cost_all})
    for side, sleeve in [('long', w.clip(lower=0)), ('short', (-w).clip(lower=0))]:
        h[side+'_weight'] = sleeve
        h[side+'_stock_days'] = sleeve.gt(0).astype(int)
        h[side+'_gross'] = gross.where(sleeve.gt(0), 0.).fillna(0.)
        t = sleeve.groupby('Code').diff().abs().fillna(sleeve.abs())
        h[side+'_cost_all'] = .001 * t
        h[side+'_cost'] = h[side+'_cost_all'].where(target.notna(), 0.)
        h[side+'_net'] = h[side+'_gross'] - h[side+'_cost']
    return h


def account(score, target):
    signal = score.rename('Return')
    d, receipt = shared.account(signal, target)
    h = holdings(signal, target)
    exact(h.w.rename('Return'), official.compute_weight(signal.to_frame()).Return)
    exact(d.net.rename('net'), official.compute_pl(signal.to_frame(), target.to_frame()).groupby('Date').sum().rename('net'))
    exact(d.net.rename('net'), h.net.groupby('Date').sum().rename('net'))
    receipt.update(weight_bitwise=True, daily_net_bitwise=True, stock_day_net_reconciles_bitwise=True,
                   strict_uint64=True)
    return d, h, receipt


def correlation(panel, dates, folder):
    a, b = panel.SIZE_ONLY, panel.ILLIQ_ONLY
    daily = pd.DataFrame({'spearman': evaluation.rankic(a, b), 'pearson': pearson(a, b),
                          'score_difference_cs_std': (a-b).groupby('Date').std(),
                          'score_difference_cs_rms': np.sqrt(((a-b)**2).groupby('Date').mean()),
                          'rank_difference_cs_std': (panel.SizeRank-panel.IlliquidityRank).groupby('Date').std()}).loc[dates]
    daily.to_csv(folder/'component_correlation_daily.csv', index_label='Date')
    rows = []
    for scope, ds in scopes(dates):
        mask = panel.index.get_level_values('Date').isin(ds)
        rows.append({'scope': scope, 'days': len(ds), 'stock_days': int(mask.sum()),
                     **{'mean_daily_'+c: daily.loc[ds, c].mean() for c in daily},
                     'stacked_spearman': a.loc[mask].corr(b.loc[mask], method='spearman'),
                     'stacked_pearson': a.loc[mask].corr(b.loc[mask], method='pearson')})
    pd.DataFrame(rows).to_csv(folder/'component_correlation_summary.csv', index=False)


def overlap(h, dates, folder):
    frames = []
    for a, b in itertools.combinations(dc.BOOKS, 2):
        daily = pd.DataFrame(index=dates)
        for side, sign in [('long', 1), ('short', -1)]:
            am, bm = (h[a].w*sign).gt(0), (h[b].w*sign).gt(0)
            inter = (am & bm).groupby('Date').sum()
            union = (am | bm).groupby('Date').sum()
            minimum = pd.concat([am.groupby('Date').sum(), bm.groupby('Date').sum()], axis=1).min(axis=1)
            daily[side+'_intersection'] = inter
            daily[side+'_union'] = union
            daily[side+'_minimum_side_size'] = minimum
            daily[side+'_jaccard'] = inter / union.where(union > 0)
            daily[side+'_overlap_over_min'] = inter / minimum.where(minimum > 0)
        frames.append(daily.reset_index(names='Date').assign(book_a=a, book_b=b))
    daily = pd.concat(frames, ignore_index=True)
    daily.to_csv(folder/'overlap_daily.csv', index=False)
    rows = []
    for scope, ds in scopes(dates):
        for (a, b), frame in daily.loc[daily.Date.isin(ds)].groupby(['book_a', 'book_b']):
            rows.append({'scope': scope, 'book_a': a, 'book_b': b, 'days': len(ds),
                         **frame.select_dtypes('number').mean().to_dict()})
    pd.DataFrame(rows).to_csv(folder/'overlap_summary.csv', index=False)


def partition(label, labels, values, target, dates):
    """Exhaustive cohorts including neutral exit costs; empty cells retained."""
    keys = [label.index.get_level_values('Date'), label]
    index = pd.MultiIndex.from_product([dates, labels], names=['Date', 'group'])
    daily = values.groupby(keys, sort=True).sum().reindex(index, fill_value=0.)
    daily['stock_count'] = label.groupby(keys, sort=True).size().reindex(index, fill_value=0)
    daily['finite_target_count'] = target.notna().groupby(keys, sort=True).sum().reindex(index, fill_value=0)
    daily['forward_target_mean'] = target.groupby(keys, sort=True).mean().reindex(index)
    rows = []
    idx_dates = label.index.get_level_values('Date')
    for scope, ds in scopes(dates):
        for group in labels:
            x = daily.xs(group, level='group').loc[ds]
            mask = label.eq(group) & idx_dates.isin(ds)
            row = {'scope': scope, 'group': group, 'days': len(ds), 'stock_days': int(mask.sum()),
                   'finite_target_stock_days': int((mask & target.notna()).sum()),
                   'average_stock_count': x.stock_count.mean(),
                   'forward_target_mean': target.loc[mask].mean(),
                   'mean_daily_cell_target': x.forward_target_mean.mean()}
            for col in values:
                row['average_'+col] = x[col].mean()
                row['period_'+col] = x[col].sum()
                row['annual_'+col] = x[col].mean() * 252
            rows.append(row)
    wanted = values.groupby('Date').sum().loc[dates]
    error = float((daily[list(values)].groupby('Date').sum()-wanted).abs().to_numpy().max())
    assert error < 1e-14, error
    assert daily.stock_count.sum() == int(idx_dates.isin(dates).sum())
    return daily.reset_index(), pd.DataFrame(rows), error


def overlap_attribution(panel, h, target, dates, folder):
    label = dc.agreement_groups(h['SIZE_ONLY'].w, h['ILLIQ_ONLY'].w)
    values = pd.concat([h[book][['gross', 'net', 'cost', 'cost_all', 'turnover']].add_prefix(book+'_')
                        for book in dc.BOOKS], axis=1)
    daily, summary, error = partition(label, dc.GROUPS, values, target, dates)
    daily.to_csv(folder/'overlap_group_daily.csv', index=False)
    summary.to_csv(folder/'overlap_group_summary.csv', index=False)
    stock = pd.concat([label, target.rename('forward_target'), values], axis=1)
    stock.loc[stock.index.get_level_values('Date').isin(dates)].to_parquet(folder/'overlap_group_stock_days.parquet')
    return {'status': 'PASS', 'exclusive_groups': dc.GROUPS, 'daily_reconciliation_max_abs': error,
            'summation_atol': 1e-14, 'other_retains_neutral_exit_costs': True, 'filter_created': False}


def conditional(panel, target, dates, folder):
    frames = []
    for direction, outer, inner, mapping in [
        ('Illiquidity_within_Size', 'size_bin', 'illiq_within_size_bin', dc.SIZE_NAMES),
        ('Size_within_Illiquidity', 'illiq_bin', 'size_within_illiq_bin', dc.ILLIQ_NAMES)]:
        for b, name in mapping.items():
            daily = pd.DataFrame(index=dates)
            for k in range(1, 4):
                mask = panel[outer].eq(b) & panel[inner].eq(k)
                daily[f't{k}'] = target.where(mask).groupby('Date').mean()
                daily[f'n{k}'] = mask.groupby('Date').sum()
                daily[f'finite_n{k}'] = (mask & target.notna()).groupby('Date').sum()
            daily['spread'] = daily.t3-daily.t1
            frames.append(daily.reset_index(names='Date').assign(direction=direction, conditioning_bucket=name))
    daily = pd.concat(frames, ignore_index=True)
    daily.to_csv(folder/'conditional_spread_daily.csv', index=False)
    rows = []
    for scope, ds in scopes(dates):
        for (direction, b), x in daily.loc[daily.Date.isin(ds)].groupby(['direction', 'conditioning_bucket']):
            sp = x.spread.dropna()
            rows.append({'scope': scope, 'direction': direction, 'conditioning_bucket': b,
                         'days': len(ds), 'finite_spread_days': len(sp), 'daily_spread': sp.mean(),
                         'annual_spread': sp.mean()*252, 'hac5_t': evaluation.hac_t(sp),
                         'gross_sharpe': evaluation.sharpe(sp) if len(sp) > 1 else np.nan,
                         **{f't{k}_mean': x[f't{k}'].mean() for k in range(1, 4)},
                         **{f't{k}_mean_count': x[f'n{k}'].mean() for k in range(1, 4)}})
    pd.DataFrame(rows).to_csv(folder/'conditional_spread_summary.csv', index=False)


def joint_and_side_attribution(panel, h, target, dates, folder):
    groups = {float((s-1)*3+i): dc.SIZE_NAMES[s]+' + '+dc.ILLIQ_NAMES[i]
              for s in range(1, 4) for i in range(1, 4)}
    values = h.drop(columns=['w', 'q'])
    double_daily, double_summary, error = partition(panel.joint_cell, list(groups), values, target, dates)
    for frame in [double_daily, double_summary]:
        frame['cell'] = frame.group.map(groups)
    double_daily.to_csv(folder/'double_sort_daily.csv', index=False)
    double_summary.to_csv(folder/'double_sort_summary.csv', index=False)
    all_daily, rows, errors = [], [], [error]
    for descriptor, label, names in [('Size', panel.size_bin, dc.SIZE_NAMES),
                                     ('Illiquidity', panel.illiq_bin, dc.ILLIQ_NAMES),
                                     ('Joint', panel.joint_cell, groups)]:
        for side in ['long', 'short']:
            cols = ['weight', 'stock_days', 'gross', 'net', 'cost', 'cost_all']
            v = h[[side+'_'+c for c in cols]].copy()
            v.columns = cols
            daily, summary, err = partition(label, list(names), v, target, dates)
            errors.append(err)
            for frame in [daily, summary]:
                frame['cohort'] = frame.group.map(names)
                frame['descriptor'], frame['side'] = descriptor, side
            # Active stock-days, not all cohort rows; exit costs remain even if weight0.
            summary['cohort_stock_days_all_rows'] = summary.stock_days
            summary['stock_days'] = summary.period_stock_days.astype(int)
            all_daily.append(daily)
            rows.append(summary)
    pd.concat(all_daily).to_csv(folder/'slow_side_cohort_daily.csv', index=False)
    pd.concat(rows).to_csv(folder/'slow_side_cohort_summary.csv', index=False)
    return {'status': 'PASS', 'daily_reconciliation_max_abs': max(errors), 'summation_atol': 1e-14,
            'partitions': ['Size', 'Illiquidity', 'Joint'], 'overlap_between_partitions': True,
            'never_sum_different_descriptors': True, 'neutral_exit_costs_in_current_bucket': True}


def signal_diagnostics(panel, target, dates, folder):
    frames = []
    for name in ['RESIDUAL_SIZE', 'RESIDUAL_ILLIQ', 'COMMON', 'DISAGREEMENT']:
        daily = pd.DataFrame(index=dates)
        daily['rankic'] = evaluation.rankic(panel[name], target)
        q = panel[name+'_q'] if name+'_q' in panel else dc.bins(panel[name], 5)
        for k in range(1, 6):
            daily[f'q{k}'] = target.where(q.eq(k)).groupby('Date').mean()
        daily['spread'] = daily.q5-daily.q1
        if name == 'DISAGREEMENT':
            for k in range(1, 4):
                daily[f't{k}'] = target.where(panel.DISAGREEMENT_tercile.eq(k)).groupby('Date').mean()
        frames.append(daily.reset_index(names='Date').assign(signal=name))
    daily = pd.concat(frames, ignore_index=True)
    daily.to_csv(folder/'descriptive_signal_daily.csv', index=False)
    rows = []
    for scope, ds in scopes(dates):
        for name, x in daily.loc[daily.Date.isin(ds)].groupby('signal'):
            rows.append({'scope': scope, 'signal': name, 'days': len(ds), 'rankic': x.rankic.mean(),
                         'rankic_hac5_t': evaluation.hac_t(x.rankic), 'rankic_hit': (x.rankic.dropna() > 0).mean(),
                         'q5_minus_q1': x.spread.mean(), 'annual_spread': x.spread.mean()*252,
                         'spread_hac5_t': evaluation.hac_t(x.spread),
                         'gross_sharpe_spread': evaluation.sharpe(x.spread.dropna()),
                         **{f'q{k}': x[f'q{k}'].mean() for k in range(1, 6)},
                         **{f't{k}': x[f't{k}'].mean() for k in range(1, 4)}})
    result = pd.DataFrame(rows)
    # DISAGREEMENT: RankIC, target terciles and Q spread only, no SR or portfolio.
    result.loc[result.signal.eq('DISAGREEMENT'), ['gross_sharpe_spread', 'spread_hac5_t']] = np.nan
    result.to_csv(folder/'descriptive_signal_summary.csv', index=False)
    w, _ = evaluation.weights(panel.COMMON)
    slow_w, _ = evaluation.weights(panel[SLOW])
    same = w.eq(slow_w).groupby('Date').mean()
    daily_parity = pd.DataFrame({'common_slow_spearman': evaluation.rankic(panel.COMMON, panel[SLOW]),
                                 'common_slow_pearson': pearson(panel.COMMON, panel[SLOW]),
                                 'weight_equal_fraction': same,
                                 'weight_abs_difference': (w-slow_w).abs().groupby('Date').sum()}).loc[dates]
    daily_parity.to_csv(folder/'common_slow_closeness_daily.csv', index_label='Date')
    rows = []
    for scope, ds in scopes(dates):
        rows.append({'scope': scope, **daily_parity.loc[ds].mean().to_dict()})
    pd.DataFrame(rows).to_csv(folder/'common_slow_closeness_summary.csv', index=False)
    return {'status': 'CHECK_COMPLETE', 'score_bitwise_equal': bool(np.array_equal(panel.COMMON.to_numpy().view(np.uint64),
                                                                               panel[SLOW].to_numpy().view(np.uint64))),
            'weight_bitwise_equal': bool(np.array_equal(w.to_numpy().view(np.uint64), slow_w.to_numpy().view(np.uint64))),
            'different_definitions_preserved': True, 'rank_common_is_not_original_zscore_mean': True}


def turnover(panel, h, accounts, dates, folder):
    daily = pd.DataFrame(index=dates)
    for name, col in [('Size', 'SizeRank'), ('Illiquidity', 'IlliquidityRank')]:
        rank = panel[col].unstack('Code')
        change = rank.diff()
        daily[name+'_mean_abs_rank_change'] = change.abs().mean(axis=1)
        daily[name+'_rms_rank_change'] = np.sqrt((change**2).mean(axis=1))
        daily[name+'_common_stock_count'] = change.notna().sum(axis=1)
    for book in dc.BOOKS:
        w = h[book].w.unstack('Code').fillna(0.)
        for side, sign in [('long', 1), ('short', -1)]:
            member = (sign*w).gt(0)
            prev = member.shift(1, fill_value=False)
            daily[book+'_'+side+'_entry'] = (member & ~prev).sum(axis=1)
            daily[book+'_'+side+'_exit'] = (~member & prev).sum(axis=1)
        daily[book+'_official_turnover'] = accounts[book].turnover
    daily.to_csv(folder/'turnover_sources_daily.csv', index_label='Date')
    rows = []
    for scope, ds in scopes(dates):
        x = daily.loc[ds]
        rows.append({'scope': scope, 'days': len(ds),
                     **{'mean_'+c: x[c].mean() for c in x},
                     'Size_rank_change_SLOW_turnover_Pearson': x.Size_mean_abs_rank_change.corr(x[SLOW+'_official_turnover']),
                     'Illiquidity_rank_change_SLOW_turnover_Pearson': x.Illiquidity_mean_abs_rank_change.corr(x[SLOW+'_official_turnover']),
                     'Size_rank_change_SLOW_turnover_Spearman': x.Size_mean_abs_rank_change.corr(x[SLOW+'_official_turnover'], method='spearman'),
                     'Illiquidity_rank_change_SLOW_turnover_Spearman': x.Illiquidity_mean_abs_rank_change.corr(x[SLOW+'_official_turnover'], method='spearman')})
    pd.DataFrame(rows).to_csv(folder/'turnover_sources_summary.csv', index=False)


def causality(inputs, features, panel, coefficients, config, folder):
    cases = []
    for i, text in enumerate(config['prefix_cutoffs']):
        cutoff = pd.Timestamp(text)
        prefix = features.index[features.index.get_level_values('Date') <= cutoff]
        for source in list(inputs) + ['ALL', 'TRUNCATION']:
            changed = dict(inputs)
            for j, (name, frame) in enumerate(inputs.items()):
                if source == 'TRUNCATION':
                    changed[name] = frame.loc[reuse.source_dates(frame) <= cutoff]
                elif source in [name, 'ALL']:
                    changed[name] = reuse.mutate(frame, name, cutoff, config['random_seed']+100*i+j)
            got_f = slow.build_features(changed, sector=False)
            got_p, got_c = dc.decompose(got_f)
            exact(features.loc[prefix], got_f.loc[prefix])
            exact(panel.loc[prefix], got_p.loc[prefix])
            ci = coefficients.index[coefficients.index <= cutoff]
            exact(coefficients.loc[ci], got_c.loc[ci])
            cases.append({'source': source, 'cutoff': text, 'prefix_rows': len(prefix), 'status': 'PASS', 'bitwise': True})
        dump(folder/'prefix_progress.json', {'status': 'running', 'cases': cases})
        print('causality '+text+': individual / ALL / truncation PASS', flush=True)
    for name, changed in [('ROW_SHUFFLE', {k: v.sample(frac=1, random_state=config['random_seed']) for k, v in inputs.items()}),
                          ('DETERMINISTIC_REBUILD', inputs)]:
        got_f = slow.build_features(changed, sector=False)
        got_p, got_c = dc.decompose(got_f)
        exact(features, got_f)
        exact(panel, got_p)
        exact(coefficients, got_c)
        cases.append({'source': name, 'prefix_rows': len(panel), 'status': 'PASS', 'bitwise': True})
    return {'status': 'PASS', 'cases': cases, 'all_feature_input_sources': list(inputs),
            'comparison': 'Exact index,columns,dtype,uint64 float bits including NaN; zero tolerance',
            'mutations': 'Extreme values,NaN,zeros,row deletion,new future code/date,financial disclosure date shift; each/all sources and truncation',
            'scope': 'All original raw/normalized features and target-free bins,double sort,conditional sort,residuals,OLS coefficients,common/disagreement',
            'labels_used_in_transforms': False, 'no_training': True,
            'limitations': 'Evidence on tested cutoffs and inputs; not a universal proof or vendor revision certification'}


def main_work(config, output, run):
    started = time.monotonic()
    stage = output/'stage'
    stage.mkdir()
    keys = list(slow.INPUT_COLUMNS) + ['beta_1day', 'topix_return_1day', 'target_1day']
    for key in keys:
        (stage/(key+'_train.parquet')).symlink_to(ROOT/config['input_dir']/(key+'_train.parquet'))
    refs = {k: ROOT/v['path'] for k, v in config['saved_components'].items()}
    code = [Path(__file__), Path(dc.__file__), Path(reuse.__file__), Path(shared.__file__),
            Path(evaluation.__file__), Path(firewall.__file__), Path(slow.__file__), Path(official.__file__),
            ROOT/'tests/workspace/test_slow_size_illiq_diagnostic.py']
    run.update(status='running', command=sys.argv, actual_trials=0, diagnostic_bundles=1,
               code_sha256={str(p.relative_to(ROOT)): sha(p) for p in code},
               environment={'python': sys.version, 'numpy': np.__version__, 'pandas': pd.__version__,
                            'scipy': scipy.__version__, 'pyarrow': pyarrow.__version__, 'platform': platform.platform()})
    dump(output/'run.json', run)
    for p in code:
        to = output/'code_snapshot'/p.relative_to(ROOT)
        to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, to)
    for key, expected in run['snapshot_sha256'].items():
        assert sha(output/key) == expected
    dump(output/'audit/pre_result_lock.json', {'at_utc': reuse.now(), 'plan_sha256': sha(output/'plan.md'),
         'config_sha256': sha(output/'config.json'), 'code_sha256': run['code_sha256'],
         'performance_candidates': 0, 'diagnostic_bundle_budget': 1, 'target_opened': False})
    phases = []
    def checkpoint(name):
        phases.append({'phase': name, 'at_utc': reuse.now(), 'actual_trials': 0})
        dump(output/'audit/phases.json', phases)
        print('phase '+name, flush=True)
    checkpoint('plan_config_code_freeze')
    firewall.install(allowed_artifacts=list(refs.values()) + [output/'predictions/components.parquet',
        output/'predictions/diagnostic_transforms.parquet', output/'metrics/overlap_group_stock_days.parquet'])
    run['train_data_sha256'] = {k+'_train.parquet': sha(stage/(k+'_train.parquet')) for k in keys if k != 'target_1day'}
    dump(output/'run.json', run)
    for k, path in refs.items():
        assert sha(path) == config['saved_components'][k]['sha256']
    dump(output/'audit/source_scan.json', reuse.source_scan([Path(slow.__file__), Path(dc.__file__)]))
    inputs = slow.load_train(stage)
    features = slow.build_features(inputs, sector=False)
    panel, coefficients = dc.decompose(features)
    raw_cols, z_cols = ['raw_size', 'raw_amihud'], ['z_size', 'z_amihud', 'size_liquidity']
    old_f = pd.read_parquet(refs['slow_features'], columns=raw_cols+z_cols).sort_index()
    raw_parity = reuse.stored_raw_parity(features[raw_cols], old_f[raw_cols])
    exact(features[z_cols], old_f[z_cols])
    old_scores = pd.read_parquet(refs['slow_scores'], columns=[SLOW, 'MOM60']).sort_index()
    exact(panel[SLOW], old_scores[SLOW])
    rebuilt = slow.zscore(panel[dc.BOOKS[:2]].mean(axis=1)).rename(SLOW)
    exact(panel[SLOW], rebuilt)
    old_official_w = official.compute_weight(old_scores[[SLOW]].rename(columns={SLOW:'Return'})).Return
    own_w, _ = evaluation.weights(panel[SLOW])
    exact(own_w.rename('Return'), old_official_w)
    panel[dc.BOOKS].to_parquet(output/'predictions/components.parquet')
    panel.to_parquet(output/'predictions/diagnostic_transforms.parquet')
    coefficients.to_csv(output/'metrics/residual_ols_coefficients_daily.csv', index_label='Date')
    assert panel.index.equals(slow.canonical(inputs['raw_return_1day']).index)
    assert np.isfinite(panel.to_numpy()).all()
    assert not any('target_1day' in p for p in firewall.ACCESSES)
    dump(output/'audit/component_parity.json', {'status':'PASS', 'rows':len(panel),
        'raw_storage':raw_parity, 'normalized_components_bitwise':True, 'SLOW_saved_and_reconstructed_bitwise':True,
        'saved_score_official_weight_bitwise':True, 'target_free_transforms_complete':True,
        'feature_only_reads_before_target': sorted(firewall.ACCESSES), 'refs':config['saved_components']})
    checkpoint('component_parity')
    run['train_data_sha256']['target_1day_train.parquet'] = sha(stage/'target_1day_train.parquet')
    dump(output/'run.json', run)
    target = slow.canonical(pd.read_parquet(stage/'target_1day_train.parquet')).Return
    assert target.index.equals(panel.index)
    calendar = pd.DatetimeIndex(panel.index.get_level_values('Date').unique())
    maturity_inputs = dict(inputs)
    for key in ['beta_1day', 'topix_return_1day']:
        frame = pd.read_parquet(stage/(key+'_train.parquet'))
        if key == 'beta_1day':
            frame = slow.canonical(frame)
        else:
            frame = frame.sort_index()
            dates = pd.DatetimeIndex(frame.index)
            if dates.tz is not None:
                frame.index = dates.tz_convert('Asia/Tokyo').tz_localize(None)
        maturity_inputs[key] = frame
    dates = reuse.maturity(maturity_inputs, target, calendar, output/'audit').rename('Date')
    accounts, h, receipts, rows = {}, {}, {}, []
    for book in dc.BOOKS:
        accounts[book], h[book], receipts[book] = account(panel[book], target)
        accounts[book].loc[dates].to_csv(output/f'metrics/daily_{book}.csv', index_label='Date')
        for scope, ds in scopes(dates):
            rows.append({'strategy':book, 'scope':scope, **shared.metrics(accounts[book].loc[ds])})
    # CSV round-trip preserves original stored float bits, no tolerance.
    old_d = pd.read_csv(refs['slow_daily'], index_col=0, parse_dates=True, float_precision='round_trip')
    exact(accounts[SLOW].loc[dates, 'net'].rename('net'), old_d.loc[dates, 'net'].rename('net'))
    old_net = official.compute_pl(old_scores[SLOW].rename('Return').to_frame(), target.to_frame()).groupby('Date').sum()
    exact(accounts[SLOW].net.rename('net'), old_net.rename('net'))
    dump(output/'audit/accounting.json', {'status':'PASS', 'receipts':receipts,
        'SLOW_saved_daily_net_bitwise':True, 'SLOW_saved_score_official_full_daily_net_bitwise':True,
        'official_target_missing_drops_cost':True, 'all_position_cost_also_saved':True,
        'continuous_accounting_before_purge':True})
    metrics = pd.DataFrame(rows)
    metrics.to_csv(output/'metrics/performance_metrics.csv', index=False)
    mom, _, _ = account(old_scores.MOM60, target)
    delta = []
    for row in rows:
        ds = dict(scopes(dates))[row['scope']]
        for base, b in [(SLOW, shared.metrics(accounts[SLOW].loc[ds])), ('MOM60', shared.metrics(mom.loc[ds]))]:
            delta.append({'strategy':row['strategy'], 'scope':row['scope'], 'baseline':base,
                          **{'delta_'+k:row[k]-b[k] for k in ['rankic','net_sharpe','gross_sharpe','turnover','annual_cost']}})
    pd.DataFrame(delta).to_csv(output/'metrics/incremental_reference.csv', index=False)
    checkpoint('standalone_diagnostics')
    correlation(panel, dates, output/'metrics')
    overlap(h, dates, output/'metrics')
    dump(output/'audit/overlap_attribution.json', overlap_attribution(panel, h, target, dates, output/'metrics'))
    checkpoint('correlation_overlap')
    conditional(panel, target, dates, output/'metrics')
    cohorts = joint_and_side_attribution(panel, h[SLOW], target, dates, output/'metrics')
    checkpoint('conditional_double_sorts')
    dump(output/'audit/common_parity.json', signal_diagnostics(panel, target, dates, output/'metrics'))
    checkpoint('residualization_common_disagreement')
    dump(output/'audit/side_cohort_reconciliation.json', cohorts)
    checkpoint('long_short_attribution')
    turnover(panel, h, accounts, dates, output/'metrics')
    checkpoint('turnover_attribution')
    coverage = []
    for scope, ds in scopes(dates):
        mask = panel.index.get_level_values('Date').isin(ds)
        for name, col in [('Size','raw_size'),('Illiquidity','raw_amihud')]:
            obs = features[col].notna()
            coverage.append({'scope':scope, 'component':name, 'stock_days':int(mask.sum()),
                             'finite_raw':int((obs & mask).sum()), 'raw_coverage':obs.loc[mask].mean(),
                             **{side+'_observed_weight_fraction':
                                h[SLOW].loc[mask, side+'_weight'].where(obs.loc[mask],0.).sum()/h[SLOW].loc[mask, side+'_weight'].sum()
                                for side in ['long','short']}})
    pd.DataFrame(coverage).to_csv(output/'metrics/raw_component_coverage.csv', index=False)
    dump(output/'audit/coverage.json', {'status':'PASS', 'rows':len(panel), 'dates':len(calendar),
        'codes':panel.index.get_level_values('Code').nunique(), 'all_components_transforms_finite':True,
        'unique_exact_Date_Code_index':True, 'evaluation_days':len(dates), 'target_coverage':target.notna().mean(),
        'all_stock_days_signal_coverage':1., 'raw_missingness_unchanged':True})
    dump(output/'audit/prefix_invariance.json', causality(inputs, features, panel, coefficients, config, output/'audit'))
    # Denial tested without reading any forbidden data.
    denied = []
    for name in ['target_1day_valid.parquet','raw_target_1day_train.parquet','historical_valid.parquet']:
        try:
            firewall._canonical_source(stage/name)
        except PermissionError:
            denied.append(name)
        else:
            raise AssertionError('Firewall failed '+name)
    dump(output/'audit/firewall_denials.json', {'status':'PASS','denied':denied})
    firewall.save(output/'audit/firewall.json')
    dump(output/'audit/manual_causality_review.json', {
        'PIT_shares':'Original asof_financials: positive field-level carry; disclosure Date EOD JST; backward merge_asof only',
        'raw_return_timing':'Provided raw_return_1day is Open-to-Open realized at date t; used abs at t only; t+2 target reconstructed separately',
        'Amihud':'Full exchange date grid trailing60 mean min40 including current t, no centered rolling, future rows cannot alter prefix',
        'normalization':'Original same-date raw1/99winsor, median/0, sample z unchanged',
        'diagnostics':'Same-date transforms, no target argument, labels enter only post-decomposition diagnostics, no fitted return model',
        'source_scan_scope':'Original feature module and target-free diagnostic module; driver manually reviewed: negative shift only in reused evaluation-only maturity reconstruction',
        'measurement_limits':['Shares include treasury; stale share basis after corporate actions not retrospectively corrected',
                              'Vendor historical revisions cannot be independently certified',
                              'Raw-missing rows retain original imputed components, not missing-only sample selection',
                              'High correlations and descriptive conditional spreads do not identify causal economic premia',
                              'Official Code diff skips absent rows; membership grid treats absent as neutral; the two are explicitly different diagnostics']})
    checkpoint('causality_audit')
    resources = {'elapsed_seconds':time.monotonic()-started,
                 'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    dump(output/'audit/resources.json', resources)
    report = ROOT/config['report_dir']
    report.mkdir(exist_ok=False)
    shutil.copytree(output/'metrics', report/'metrics')
    shutil.copytree(output/'audit', report/'audit')
    run.update(status='completed', completed_at_utc=reuse.now(), exit_code=0, actual_trials=0,
               diagnostic_bundles=1, resources=resources,
               artifact_sha256={str(p.relative_to(output)):sha(p) for parent in ['predictions','metrics','audit']
                                for p in (output/parent).glob('*') if p.is_file()})
    dump(output/'run.json', run)
    print('DIAGNOSTIC COMPUTATION COMPLETE '+json.dumps(resources), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    config = json.loads(Path(args.config).read_text())
    run = json.loads((output/'run.json').read_text())
    assert config['diagnostic_only'] and config['data_split']=='train' and config['valid_evaluation'] is False
    assert config['performance_trial_budget']==0 and config['diagnostic_run_budget']==1
    assert config['parameters']=={'terciles':3,'quintiles':5,'additional_smoothing':None,'turnover_control':None,'optimization':False}
    assert run['status']=='prepared' and sha(args.config)==run['snapshot_sha256']['config.json']
    try:
        main_work(config, output, run)
    except BaseException as error:
        run.update(status='failed', completed_at_utc=reuse.now(), exit_code=1, error=repr(error))
        dump(output/'run.json', run)
        if firewall._PATCHED:
            firewall.save(output/'audit/firewall.json')
        raise


if __name__=='__main__':
    main()
