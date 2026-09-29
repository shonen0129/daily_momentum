# DM-20260929-01: decision record

Completed on 2026-09-29 JST. One fixed old/new Train-only implementation replay ran in `artifacts/DM-20260929-01/run-20260928T184805Z/`; details are in [`BUGFIX_VALIDATION.md`](../../reports/DM-20260929-01/BUGFIX_VALIDATION.md). The final run completed in 30.9 seconds and recorded source, Train-data, and prediction artifact hashes.

The corrected share-unit arithmetic is retained because the previous close was already normalized by the cumulative observed split factor; applying the current factor again was a units error. The correction changed `box_duration` on 2,257 of 809,636 rows, `box_width_atr` on 2,425 rows, and `close_position` on 2,245 rows. Other output features were bitwise unchanged.

Descriptive pooled Train results moved from Gross/Net Sharpe 0.9580/0.7851 to 0.9509/0.7774; average daily turnover moved from 0.031851 to 0.031956, and RankIC from 0.011032 to 0.011053. Annual Net Sharpe changes were mixed across the six folds. This is not evidence of performance improvement and was not used to select, tune, or adopt a candidate; the correction is solely for consistent share units around splits.

Train index/coverage, finite output, deterministic replay, and runtime firewall passed. Only the five `*_train.parquet` inputs listed in the run's `audit/firewall.json` were opened. Valid was not accessed. Historical diagnostic records remain archived and are not holdouts.
