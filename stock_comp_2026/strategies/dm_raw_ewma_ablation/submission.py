"""Self-contained Train-only adapters for exactly two preregistered rules."""
try:
    from .features import build_features, build_control, load_train, score, CANDIDATES
except ImportError:
    from features import build_features, build_control, load_train, score, CANDIDATES


def predict(data_dir="input", candidate="RAW_EWMA_SHORT_VETO"):
    if candidate not in CANDIDATES:
        raise ValueError(f"Unknown registered candidate: {candidate}")
    if candidate == "RAW_EWMA_CONTROL":
        return build_control(load_train(data_dir, use_context=False)).to_frame()
    return score(build_features(load_train(data_dir)), candidate).to_frame()
