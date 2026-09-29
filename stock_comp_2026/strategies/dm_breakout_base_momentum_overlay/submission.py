"""Research-only Train prediction adapter for the breakout-base variants."""
from .features import load_inputs, build_features
from .models import generate_signal, TRIAL_IDS


def predict(data_dir=".", split="train", trial_id="B00"):
    if split != "train":
        raise ValueError("This exploratory strategy adapter is restricted to Train")
    if trial_id not in TRIAL_IDS:
        raise ValueError(f"Unknown trial_id: {trial_id}")
    panel = load_inputs(data_dir, split="train")
    frame = build_features(panel)
    return generate_signal(frame, trial_id).rename("Return").to_frame()
