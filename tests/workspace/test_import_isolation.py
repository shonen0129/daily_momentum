"""The frozen evaluator's top-level imports must not pollute pytest's global path."""
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
STRATEGY_DIR = ROOT / "stock_comp_2026/strategies/dm_trainonly"


def test_shared_conftest_does_not_add_strategy_paths(tmp_path):
    conftest = ROOT / "tests/conftest.py"
    script = (
        "import runpy, sys; "
        "runpy.run_path(sys.argv[1]); "
        "assert not any('stock_comp_2026/strategies/' in str(p) for p in sys.path)"
    )
    environment = dict(os.environ, PYTHONPATH="")
    result = subprocess.run(
        [sys.executable, "-c", script, str(conftest)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_evaluator_style_import_is_confined_to_a_subprocess(tmp_path):
    script = (
        "import sys; from pathlib import Path; import features, submission; "
        "expected = Path(sys.argv[1]).resolve(); "
        "assert Path(features.__file__).resolve().parent == expected; "
        "assert Path(submission.__file__).resolve().parent == expected"
    )
    environment = dict(os.environ, PYTHONPATH=str(STRATEGY_DIR))
    result = subprocess.run(
        [sys.executable, "-c", script, str(STRATEGY_DIR)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
