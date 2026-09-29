"""Research-only prediction adapter; M00 preserves the current momentum baseline."""
from .features import load_inputs, build_features
from .models import generate_signal, TRIAL_IDS


def predict(data_dir=".", split="train", trial_id="M00"):
    if trial_id not in TRIAL_IDS:
        raise ValueError(f"Unknown trial_id: {trial_id}")
    inputs = load_inputs(data_dir, split=split)
    features = build_features(inputs)
    return generate_signal(features, trial_id).rename("Return").to_frame()
