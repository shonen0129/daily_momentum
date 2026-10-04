"""Research adapter for a fixed component; no candidate is adopted by default."""
try:
    from .features import build_features, load_train, score
except ImportError:
    from features import build_features, load_train, score


def predict(data_dir="input", candidate="SECTOR33_MOM"):
    return score(build_features(load_train(data_dir)), candidate).to_frame()
