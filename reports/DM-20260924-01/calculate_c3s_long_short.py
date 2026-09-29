"""Split the frozen C3S Valid PnL into official-weight long and short legs."""
from __future__ import annotations

import hashlib
import importlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'stock_comp_2026/input'
RELEASE = ROOT / 'releases/DM-20260924-C3S-v1'
ZIP = RELEASE / 'dm_c3s_submission.zip'
OUT_JSON = ROOT / 'reports/DM-20260924-01/c3s_long_short.json'
OUT_DAILY = ROOT / 'reports/DM-20260924-01/c3s_long_short_daily.csv'
sys.path.insert(0, str(ROOT / 'stock_comp_2026'))
from evaluate_script import (  # noqa: E402
    TRANSACTION_COST_RATE, align_prediction, compute_pl, compute_sr,
    compute_weight, load_prediction,
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    start = time.monotonic()
    manifest = json.loads((RELEASE / 'freeze_manifest.json').read_text())
    if sha256(ZIP) != manifest['submission_zip_sha256']:
        raise RuntimeError('Frozen C3S zip hash mismatch')

    for name in ('submission', 'features', 'models'):
        sys.modules.pop(name, None)
    prediction = load_prediction(ZIP, DATA)
    target = pd.read_parquet(DATA / 'target_1day_valid.parquet')
    aligned = align_prediction(prediction, target)
    if not np.isfinite(aligned.iloc[:, 0]).all():
        raise RuntimeError('C3S prediction contains non-finite scores')

    w = compute_weight(aligned).iloc[:, 0]
    y = target.iloc[:, 0]
    sides = {
        'long': w.where(w > 0, 0.0),
        'short': w.where(w < 0, 0.0),
    }
    records = {}
    daily = {}
    for side, side_w in sides.items():
        gross_rows = side_w * y
        turnover_rows = side_w.groupby(level='Code').diff().abs().fillna(side_w.abs())
        net_rows = gross_rows - TRANSACTION_COST_RATE * turnover_rows
        gross = gross_rows.groupby(level='Date').sum().rename(f'{side}_gross')
        net = net_rows.groupby(level='Date').sum().rename(f'{side}_net')
        cost = (gross - net).rename(f'{side}_cost')
        turnover = turnover_rows.groupby(level='Date').sum().rename(f'{side}_turnover')
        daily.update({f'{side}_gross': gross, f'{side}_cost': cost,
                      f'{side}_net': net, f'{side}_turnover': turnover})
        records[side] = {
            'gross_sharpe': compute_sr(gross_rows),
            'net_sharpe': compute_sr(net_rows),
            'annual_gross_pl': float(gross.mean() * 252),
            'annual_cost': float(cost.mean() * 252),
            'annual_net_pl': float(net.mean() * 252),
            'average_daily_turnover': float(turnover.mean()),
        }

    daily_frame = pd.concat(daily.values(), axis=1).sort_index()
    full_net = compute_pl(aligned, target).groupby(level='Date').sum()
    leg_net = daily_frame['long_net'] + daily_frame['short_net']
    if not np.allclose(full_net.to_numpy(), leg_net.reindex(full_net.index).to_numpy(),
                       rtol=0.0, atol=1e-15):
        raise AssertionError('Long and short net legs do not add back to official net PnL')
    total_turn = w.groupby(level='Code').diff().abs().fillna(w.abs()).groupby(level='Date').sum()
    split_turn = daily_frame['long_turnover'] + daily_frame['short_turnover']
    if not np.allclose(total_turn.to_numpy(), split_turn.reindex(total_turn.index).to_numpy(),
                       rtol=0.0, atol=1e-15):
        raise AssertionError('Long and short turnover does not add back to official turnover')

    annual = []
    dates = full_net.index
    for year in sorted(dates.year.unique()):
        row = {'year': int(year)}
        mask = dates.year == year
        for side, side_w in sides.items():
            part = daily_frame.loc[mask]
            row[f'{side}_net_sharpe'] = compute_sr(part[f'{side}_net'])
            row[f'{side}_annual_net_pl'] = float(part[f'{side}_net'].mean() * 252)
        annual.append(row)

    daily_frame.to_csv(OUT_DAILY, index_label='Date')
    result = {
        'strategy': 'C3S / DM-20260924-C3S-v1',
        'period': '2016-04-01 through 2026-07-31; previously accessed Valid, not independent OOS',
        'release_zip_sha256': manifest['submission_zip_sha256'],
        'target_sha256': sha256(DATA / 'target_1day_valid.parquet'),
        'scoring': 'official compute_weight / compute_pl / compute_sr; one-way cost 10 bps; annualization 252',
        'leg_definition': 'Long uses positive official quintile weights; Short uses negative official quintile weights. Each leg is a contribution to the full portfolio, not a separately rescaled portfolio.',
        'cost_allocation': 'Turnover and costs are computed separately on each leg weight. Long and short costs and turnover add back to the official full-portfolio values.',
        'target_rows': int(len(target)),
        'target_coverage': float(y.notna().mean()),
        'combined_official_net_sharpe': compute_sr(compute_pl(aligned, target)),
        'legs': records,
        'annual': annual,
        'checks': {'legs_add_to_official_daily_net_pnl': True,
                   'leg_turnover_adds_to_official_turnover': True},
        'elapsed_seconds': time.monotonic() - start,
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
