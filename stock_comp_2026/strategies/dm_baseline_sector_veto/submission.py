"""Train-only research adapter; candidate B is the fixed no-argument smoke path."""
try:
    from .features import load_train, build_features, score
except ImportError:
    from features import load_train, build_features, score


def predict(data_dir="input", candidate="BASELINE_HIER_SECTOR_VETO"):
    return score(build_features(load_train(data_dir)), candidate).to_frame()
