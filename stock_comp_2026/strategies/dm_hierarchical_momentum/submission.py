"""Train research adapter; default component combination is not adoption."""
try:
    from .features import build_features, load_train, score
except ImportError:
    from features import build_features, load_train, score


def predict(data_dir="input", candidate="HIER33_COMBINED"):
    return score(build_features(load_train(data_dir)), candidate).to_frame()
