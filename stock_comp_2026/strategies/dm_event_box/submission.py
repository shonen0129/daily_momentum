"""Research adapter; the fixed event state outputs a signed daily signal."""
from pathlib import Path

try:
    from . import features
except ImportError:
    import features


def predict(data_dir=".", split=None):
    data_dir = Path(data_dir)
    if split is None:
        split = "valid" if (data_dir / "raw_return_1day_valid.parquet").is_file() else "train"
    inputs = features.load_inputs(data_dir, split=split)
    state = features.build_features(inputs)
    return features.signal_from_features(state).to_frame()
