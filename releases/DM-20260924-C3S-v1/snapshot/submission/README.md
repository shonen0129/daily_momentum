# DM-20260924-C3S-v1

凍結候補。元C3とは別定義であり、元C3の成績を引き継がない。

- Signal: EWMA(0.25) of `0.5*res60s1 + 0.5*prox250_split_safe`.
- `res60s1`: preceding 60 observed residual-return rows, current date excluded.
- `prox250_split_safe`: raw Close / trailing 250-row max raw High after applying observed AdjustmentFactor events to express the raw prices in a common share unit. Exactly 250 finite positive High observations are required; the window includes current date `t`.
- AdjustmentFactor is used as a dated corporate-action event multiplier; no retrospectively adjusted OHLC levels are read.
- State resets after a code is absent for more than 20 exchange-date ordinal steps.
- Inference reads feature files only; it never loads target files. CPU-only; numpy/pandas/pyarrow.

The candidate was frozen before the comparison recorded in `VALID_EVALUATION.md`. This workspace's Valid period had already been accessed for another release. The comparison is therefore a one-time evaluation on previously read Valid data, not independent OOS evidence. No changes may be selected from the Valid result.
