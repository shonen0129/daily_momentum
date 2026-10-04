"""Train research adapter, using the same feature builder as evaluation."""
try:
    from .features import build_features, load_train, score
except ImportError:
    from features import build_features, load_train, score


def predict(data_dir="input", candidate="IND33_MOM_WITHIN_REV20"):
    return score(build_features(load_train(data_dir)), candidate).to_frame()
