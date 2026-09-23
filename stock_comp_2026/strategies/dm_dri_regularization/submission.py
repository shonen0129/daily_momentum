"""Label-free inference from an explicit, local research model bundle."""
import json
from pathlib import Path

try:
    from . import features, models
except ImportError:
    import features
    import models


def predict():
    path = Path(__file__).resolve().parent / "inference_bundle.json"
    if not path.is_file():
        raise RuntimeError("No model selected or frozen; use a prepared research inference bundle")
    bundle = json.loads(path.read_text())
    inputs = features.load_inputs(Path.cwd(), bundle["split"])
    return models.predict_from_features(features.build_features(inputs), bundle).to_frame()
