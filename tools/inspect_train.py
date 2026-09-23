from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq

root = Path(__file__).resolve().parents[1] / 'stock_comp_2026/input'
for name in ['raw_return_1day', 'beta_1day', 'topix_return_1day', 'prices_daily_quotes', 'listed_info', 'target_1day']:
    path = root / f'{name}_train.parquet'
    f = pq.ParquetFile(path)
    print(name, f.metadata.num_rows, f.schema.names, flush=True)
    if name in ['raw_return_1day', 'target_1day']:
        df = pd.read_parquet(path)
        print(df.head(2), df.tail(2), 'dates', df.index.get_level_values('Date').nunique(), 'nan', df.isna().sum().to_dict(), flush=True)
