"""Self-contained Train-only research adapter."""
try:
    from .features import load_train, build_features, score
except ImportError:
    from features import load_train, build_features, score


def predict(data_dir='.',candidate='SLOW_CAUSE_AWARE'):
    return score(build_features(load_train(data_dir)),candidate).to_frame()
