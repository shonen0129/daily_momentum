# DM-20260929-01: split-adjusted ATR correction regression

- Run: `run-20260928T184805Z`; Train only; Valid and raw target were not accessed.
- Baseline: immutable `releases/DM-20260927-SN1-v1/snapshot/strategy/features.py`.
- The same annual expanding high/low Ridge models (`lambda=1`), event ranking, EWMA smoothing (`alpha=0.25`), evaluation dates, target, and cost were used on both sides. No model or parameter selection was performed.
- Evaluation: 2011-01-04 through 2016-03-29 (1,275 dates), with each year's last two signal dates purged.
- Full prediction index: 809,636 Train stock-days; all scores finite and index-aligned.

## Feature effect

| Feature | Changed rows | Maximum absolute change |
|:---|---:|---:|
| `box_duration` | 2,257 | 120 observations |
| `box_width_atr` | 2,425 | 2.9592 |
| `close_position` | 2,245 | 0.8118 |
| All other features | 0 | 0 |

## Pooled descriptive Train results

| Implementation | Gross Sharpe | Net Sharpe | Annual Net P/L | Annual Cost | Average Daily Turnover | RankIC |
|:---|---:|---:|---:|---:|---:|---:|
| Pre-fix | 0.9580 | 0.7851 | 3.6486% | 0.7993% | 0.031851 | 0.011032 |
| Corrected | 0.9509 | 0.7774 | 3.6146% | 0.8020% | 0.031956 | 0.011053 |
| Change | -0.0071 | -0.0077 | -0.0340 pp | +0.0027 pp | +0.000105 | +0.000021 |

Annual Net Sharpe improved in 2012, 2014, and 2016, and declined in 2011, 2013, and 2015. The mixed result is recorded as descriptive implementation impact, not as a candidate-selection signal. The fix is retained because `split_safe_prices` already places historical OHLC in a common share unit; dividing the previous close by today's adjustment factor again violated that unit convention.

## Verification and artifacts

- Split/no-split synthetic representation equality and feature future-mutation/truncation prefix-invariance tests passed.
- The corrected model replay was bitwise deterministic. Train index alignment and finite coverage passed.
- Runtime firewall passed; `artifacts/DM-20260929-01/run-20260928T184805Z/audit/firewall.json` lists only the five Train Parquet sources.
- Code/data hashes and the paired old/new score artifact hash are in `artifacts/DM-20260929-01/run-20260928T184805Z/run.json`. Annual metrics are in `metrics/yearly_comparison.csv`; full summaries and feature differences are in `metrics/summary.json`.
- This check is not a new holdout, freeze, submission evaluation, or strategy adoption decision.
