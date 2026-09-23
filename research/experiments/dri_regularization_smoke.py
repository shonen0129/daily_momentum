"""Run a standalone inference copy with only three feature files allowed."""
import importlib.util
import os
from pathlib import Path
import sys

import pandas as pd

folder = Path(sys.argv[1]).resolve()
os.chdir(folder)
sys.path.insert(0, str(folder))
allowed = {"raw_return_1day_train.parquet", "beta_1day_train.parquet", "topix_return_1day_train.parquet"}
original_read = pd.read_parquet


def read_features(path, *args, **kwargs):
    if Path(path).name not in allowed:
        raise PermissionError("Inference attempted a non-feature read")
    return original_read(path, *args, **kwargs)


pd.read_parquet = read_features
spec = importlib.util.spec_from_file_location("submission", folder / "submission.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
first, second = module.predict(), module.predict()
pd.testing.assert_frame_equal(first, second, check_exact=True)
assert first.index.names == ["Date", "Code"] and first.shape[1] == 1 and first.index.is_unique
first.to_parquet(folder / "prediction.parquet")
print(f"PASS {len(first)} rows; standalone deterministic inference; no labels")
