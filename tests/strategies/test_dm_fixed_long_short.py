"""Unit and causality tests for DM-20260909-02 (dm_fixed_long_short)."""
import numpy as np
import pandas as pd
import pytest
from tests.test_causality import fixture_inputs
from stock_comp_2026.strategies.dm_fixed_long_short import core, features, submission
from research.evaluation import weights, daily_account


def mock_financials(idx):
    """Generate minimal valid financial statements matching the listing index."""
    codes = idx.get_level_values('Code').unique()
    dates = idx.get_level_values('Date').unique()
    records = []
    num = 1
    for code in codes:
        for year in [2008, 2009, 2010]:
            for q_idx, period in enumerate(['1Q', '2Q', '3Q', 'FY']):
                disc_date = pd.Timestamp(f'{year}-0{q_idx+1}-15') if q_idx < 3 else pd.Timestamp(f'{year+1}-02-15')
                if disc_date not in dates:
                    # find closest after
                    sub = dates[dates >= disc_date]
                    if len(sub) == 0:
                        continue
                    disc_date = sub[0]
                records.append({
                    'Date': disc_date,
                    'Code': str(code),
                    'DisclosureNumber': num,
                    'TypeOfDocument': 'FinancialStatements_Consolidated',
                    'TypeOfCurrentPeriod': period,
                    'CurrentPeriodStartDate': pd.Timestamp(f'{year}-01-01'),
                    'CurrentPeriodEndDate': pd.Timestamp(f'{year}-03-31') if period == '1Q' else (
                        pd.Timestamp(f'{year}-06-30') if period == '2Q' else (
                            pd.Timestamp(f'{year}-09-30') if period == '3Q' else pd.Timestamp(f'{year}-12-31')
                        )
                    ),
                    'CurrentFiscalYearStartDate': pd.Timestamp(f'{year}-01-01'),
                    'CurrentFiscalYearEndDate': pd.Timestamp(f'{year}-12-31'),
                    'CashFlowsFromOperatingActivities': float(100.0 * (q_idx + 1)),
                    'TotalAssets': 1000.0,
                    'CashAndEquivalents': 200.0,
                    'Equity': 500.0
                })
                num += 1
    df = pd.DataFrame(records).set_index(['Date', 'Code']).sort_index()
    return df


def test_b0_t0_bitwise_and_long_preservation():
    data = fixture_inputs(200, codes=10)
    data['fins_statements'] = mock_financials(data['raw_return_1day'].index)
    f = features.build_features(data)

    target = pd.Series(np.random.default_rng(42).normal(0, 0.02, len(f)), index=f.index)

    # Evaluate all trials
    preds = {}
    accounts = {}
    w_dict = {}
    q_dict = {}
    for tid in ['B0', 'T0', 'T1', 'T2', 'T3']:
        pred = features.predict_from_features(f, {'trial_id': tid})
        preds[tid] = pred
        w, q = weights(pred)
        w_dict[tid] = w
        q_dict[tid] = q
        accounts[tid] = daily_account(pred, target)

    # 1. B0 and T0 bitwise match
    pd.testing.assert_series_equal(w_dict['B0'], w_dict['T0'], check_exact=True)
    pd.testing.assert_series_equal(q_dict['B0'], q_dict['T0'], check_exact=True)
    pd.testing.assert_series_equal(accounts['B0']['gross'], accounts['T0']['gross'], check_exact=True)
    pd.testing.assert_series_equal(accounts['B0']['net'], accounts['T0']['net'], check_exact=True)
    pd.testing.assert_series_equal(accounts['B0']['cost'], accounts['T0']['cost'], check_exact=True)

    # 2. Long preservation across all trials T1, T2, T3 vs B0
    is_long_b0 = q_dict['B0'] >= 3
    for tid in ['T1', 'T2', 'T3']:
        is_long_t = q_dict[tid] >= 3
        # Membership
        pd.testing.assert_series_equal(is_long_b0, is_long_t, check_exact=True)
        # Weights in Long Pool
        pd.testing.assert_series_equal(w_dict['B0'][is_long_b0], w_dict[tid][is_long_t], check_exact=True)
        # Daily Long gross contribution
        pd.testing.assert_series_equal(accounts['B0']['long'], accounts[tid]['long'], check_exact=True)


@pytest.mark.parametrize('cut', [80, 140])
def test_future_mutation_prefix_invariance(cut):
    data = fixture_inputs(200, codes=8)
    data['fins_statements'] = mock_financials(data['raw_return_1day'].index)
    cutoff = data['topix_return_1day'].index[cut]

    before = features.build_features(data)

    mutated = {k: v.copy() for k, v in data.items()}
    for name, frame in mutated.items():
        mask = frame.index.get_level_values('Date') > cutoff
        for col in frame:
            if name == 'listed_info' and col == 'Sector17Code':
                frame.loc[mask, col] = 'future_sector'
            elif pd.api.types.is_numeric_dtype(frame[col]):
                frame.loc[mask, col] = frame.loc[mask, col] * -7 + 88
            elif pd.api.types.is_datetime64_any_dtype(frame[col]):
                frame.loc[mask, col] = pd.Timestamp('1990-01-01')

    after = features.build_features(mutated)

    prefix = before.index.get_level_values('Date') <= cutoff
    # Features prefix must match bitwise
    pd.testing.assert_frame_equal(before.loc[prefix], after.loc[prefix], check_exact=True)

    # Predictions prefix must match bitwise for all candidates
    for tid in ['B0', 'T0', 'T1', 'T2', 'T3']:
        p_before = features.predict_from_features(before, {'trial_id': tid})
        p_after = features.predict_from_features(after, {'trial_id': tid})
        pd.testing.assert_series_equal(p_before.loc[prefix], p_after.loc[prefix], check_exact=True)
