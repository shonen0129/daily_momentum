"""Prepare the output directory for DM-20260909-02 run, then execute."""
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'experiments/DM-20260909-02/config.json'
RUN_TS = datetime.now(timezone.utc).strftime('run-%Y%m%dT%H%M%SZ')
OUT = ROOT / f'artifacts/DM-20260909-02/{RUN_TS}'


def digest(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for d in ['audit', 'logs', 'metrics', 'predictions', 'source', 'train_stage']:
        (OUT / d).mkdir(exist_ok=True)

    # Copy config
    shutil.copyfile(CONFIG, OUT / 'config.json')

    # Snapshot hashes
    snap = {'config.json': digest(OUT / 'config.json')}

    run_meta = {
        'run_id': RUN_TS,
        'experiment_id': 'DM-20260909-02',
        'status': 'prepared',
        'prepared_at_utc': datetime.now(timezone.utc).isoformat(),
        'snapshot_sha256': snap,
    }
    (OUT / 'run.json').write_text(json.dumps(run_meta, indent=2, ensure_ascii=False) + '\n')

    print(f'Output directory prepared: {OUT}')
    print(f'Run ID: {RUN_TS}')
    print(f'Config hash: {snap["config.json"]}')

    # Now execute
    from research.experiments.fixed_long_short import run
    run((OUT / 'config.json').resolve(), OUT.resolve())


if __name__ == '__main__':
    main()
