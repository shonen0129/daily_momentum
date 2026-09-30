"""Narrowly scoped imports for the frozen evaluator-style dm_trainonly modules."""
from contextlib import contextmanager
import importlib
from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_DIR = ROOT / "stock_comp_2026" / "strategies" / "dm_trainonly"


@contextmanager
def load_modules():
    """Load legacy top-level modules while their strategy path is temporarily active."""
    module_names = ("features", "models", "submission")
    previous = {name: sys.modules.pop(name, None) for name in module_names}
    sys.path.insert(0, str(STRATEGY_DIR))
    try:
        imported = {name: importlib.import_module(name) for name in module_names}
        yield SimpleNamespace(**imported)
    finally:
        for name in module_names:
            sys.modules.pop(name, None)
        for name, module in previous.items():
            if module is not None:
                sys.modules[name] = module
        sys.path.remove(str(STRATEGY_DIR))
