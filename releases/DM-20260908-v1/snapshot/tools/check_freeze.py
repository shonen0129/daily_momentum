"""Verify frozen hashes and run the actual submission zip on Train features only."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/DM-20260908'
manifest=json.loads((OUT/'freeze_manifest.json').read_text())


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


for section in ['code_sha256','artifact_sha256']:
    for relative,expected in manifest[section].items():
        assert digest(ROOT/relative)==expected, f'Freeze mismatch: {relative}'
print('All frozen code/config/artifact hashes match',flush=True)
archive=ROOT/'stock_comp_2026/strategies/dm_trainonly.zip'
with zipfile.ZipFile(archive) as z:
    assert sorted(z.namelist())==sorted('dm_trainonly/'+name for name in ['submission.py','features.py','frozen_config.json','README.md'])
    for name in z.namelist():
        assert z.read(name)==(ROOT/'stock_comp_2026/strategies'/name).read_bytes()
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'stock_comp_2026'))
from research.firewall import install
install([OUT/'selected_train_predictions.parquet'])
from evaluate_script import load_prediction
import pandas as pd
with tempfile.TemporaryDirectory(prefix='dm_zip_train_') as folder:
    stage=Path(folder)
    for name in ['raw_return_1day','beta_1day','topix_return_1day']:
        (stage/f'{name}_train.parquet').symlink_to(ROOT/'stock_comp_2026/input'/f'{name}_train.parquet')
    p=load_prediction(archive,stage)
    expected=pd.read_parquet(OUT/'selected_train_predictions.parquet')
    pd.testing.assert_frame_equal(p,expected,check_exact=True)
print(f'Actual zip inference matches all {len(p)} Train predictions bitwise; no labels/Valid read',flush=True)
