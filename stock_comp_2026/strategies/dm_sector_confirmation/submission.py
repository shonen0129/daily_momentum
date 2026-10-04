"""Self-contained Train-only research adapter, default is the registered C veto."""
try:
    from .features import build_features, load_train, score
except ImportError:
    from features import build_features, load_train, score


def predict(data_dir="input", candidate="SHORT_DISAGREE_VETO"):
    return score(build_features(load_train(data_dir)), candidate).to_frame()
