"""Self-contained Train-only research adapter; no later-split release."""
try:
    from .features import load_train, build_features, score
except ImportError:
    from features import load_train, build_features, score


def predict(data_dir='.',candidate='CAUSE_COMPOSITE'):
    return score(build_features(load_train(data_dir)),candidate).to_frame()
