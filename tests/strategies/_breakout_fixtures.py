"""Synthetic panels shared by the two breakout strategy contract suites."""
import numpy as np
import pandas as pd


def make_inputs(n_dates=290, n_codes=4, seed=20260930):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=n_dates, name="Date")
    codes = [f"C{i}" for i in range(n_codes)]
    index = pd.MultiIndex.from_product([dates, codes], names=["Date", "Code"])

    inputs = {
        "raw_return_1day": pd.DataFrame(
            {"Return": rng.normal(0.0002, 0.015, len(index))}, index=index
        ),
        "beta_1day": pd.DataFrame(
            {"Return": rng.uniform(0.7, 1.3, len(index))}, index=index
        ),
        "topix_return_1day": pd.DataFrame(
            {"Return": rng.normal(0.0001, 0.01, n_dates)}, index=dates
        ),
    }

    price_parts = []
    split_at = n_dates - 35
    for code_number, code in enumerate(codes):
        close = 80.0 + 7.0 * code_number + np.cumsum(rng.normal(0.0, 0.3, n_dates))
        high = close * (1.0 + rng.uniform(0.002, 0.02, n_dates))
        low = close * (1.0 - rng.uniform(0.002, 0.02, n_dates))
        factor = np.ones(n_dates)
        if code_number == 0:
            # Simulate a 2-for-1 split with a 0.5 event factor on the split row.
            high[split_at:] *= 0.5
            low[split_at:] *= 0.5
            close[split_at:] *= 0.5
            factor[split_at] = 0.5
        frame = pd.DataFrame(
            {
                "High": high,
                "Low": low,
                "Close": close,
                "AdjustmentFactor": factor,
            },
            index=pd.MultiIndex.from_product(
                [dates, [code]], names=["Date", "Code"]
            ),
        )
        price_parts.append(frame)
    inputs["prices_daily_quotes"] = pd.concat(price_parts).sort_index()
    return inputs


def prefix_rows(frame, cutoff):
    return frame.loc[frame.index.get_level_values("Date") <= cutoff]


def suffix_rows(frame, cutoff):
    return frame.index.get_level_values("Date") > cutoff
