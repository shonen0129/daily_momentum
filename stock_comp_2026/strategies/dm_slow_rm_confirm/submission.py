"""Fixed untrained inference; performance evaluation remains gate-controlled."""
from pathlib import Path
try:
    from . import features
except ImportError:
    import features


def predict(data_dir='.'):
    inputs = features.load_train(Path(data_dir))
    components, _ = features.components(inputs)
    panel, _ = features.construct(components)
    return features.score(panel).to_frame()
