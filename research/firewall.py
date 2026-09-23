"""Runtime read guard: deny every Valid parquet and every raw label file."""
import json
import os
import sys
from pathlib import Path

ACCESSES = set()


def install(allowed_artifacts=()):
    import pandas as pd
    original_read = pd.read_parquet
    artifacts={str(Path(p).resolve()) for p in allowed_artifacts}

    def guarded_read(path, *args, **kwargs):
        name = Path(path).name
        if '_valid' in name or 'raw_target' in name or (not name.endswith('_train.parquet') and str(Path(path).resolve()) not in artifacts):
            raise PermissionError(f'Train-only parquet loader denied {name}')
        ACCESSES.add(str(Path(path).resolve()))
        return original_read(path, *args, **kwargs)

    pd.read_parquet = guarded_read
    def audit(event, args):
        if event != 'open' or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = os.fsdecode(args[0])
        name = Path(path).name
        if name.endswith('.parquet'):
            if '_valid' in name or 'raw_target' in name:
                raise PermissionError(f'Train-only source firewall denied {name}')
            ACCESSES.add(str(Path(path).resolve()))
    sys.addaudithook(audit)


def save(path):
    Path(path).write_text(json.dumps({'opened_parquets': sorted(ACCESSES),
                                    'valid_evaluation': False, 'raw_target_reads': False}, indent=2))
