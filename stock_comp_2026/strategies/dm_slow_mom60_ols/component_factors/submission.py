"""Self-contained label-free Train adapter for this fixed research candidate."""
try:
    from .features import load_train, components, score
except ImportError:
    from features import load_train, components, score


def predict(data_dir="."):
    scores, _ = components(load_train(data_dir))
    return score(scores).to_frame()
