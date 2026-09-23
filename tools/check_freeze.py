"""Verify the archived DM-20260908 release and its actual zip on Train only."""
from pathlib import Path
import subprocess
import sys

from workspace import check_workspace, inside, read_json

ROOT = Path(__file__).resolve().parents[1]


def main():
    # Validate hashes before executing archived code.
    print(check_workspace(ROOT), flush=True)
    meta = read_json(ROOT / 'experiments/DM-20260908/experiment.json')
    snapshot = inside(ROOT, meta['freeze_root'])
    return subprocess.call([sys.executable, str(snapshot / 'tools/check_freeze.py')], cwd=snapshot)


if __name__ == '__main__':
    sys.exit(main())
