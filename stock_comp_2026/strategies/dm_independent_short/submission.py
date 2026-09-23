"""Competition entry point for the preregistered V1/V2/V3 implementation."""
from pathlib import Path

from . import features


def predict(directory=Path("."), split="train", trial_id="H0"):
    data = features.load_inputs(directory, split)
    return features.predict_from_features(features.build_features(data), {"trial_id": trial_id}).to_frame()
