# Slow Multifactor

Independent research family for DM-20261002-05. Seven fixed factors form equal
Size/Liquidity, Quality and Value blocks. No Momentum, learned weights or smoothing.
Definitions and conditional sector/revision trials are fixed in the experiment plan.

`predict()` without arguments reads only four `*_train.parquet` feature files from
the working directory and returns all raw-return panel rows. Research and smoke
share the same builder. This is a Train research adapter, not a frozen later-split
competition submission. There is no Valid or label loader in this strategy.
