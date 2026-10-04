"""Self-contained Train smoke adapter; later-split release is not frozen."""
try:
    from .features import load_train, build_features, score
except ImportError:  # evaluator imports submission as a top-level module
    from features import load_train, build_features, score


def predict(data_dir=".", sector=False, revision=False):
    return score(build_features(load_train(data_dir), sector=sector), revision=revision).to_frame()
