"""Label-free inference with annual OLS artifacts supplied by Train research."""
from pathlib import Path

try:
    from .component_factors import features as factors
    from .models import predict_artifacts
except ImportError:
    from component_factors import features as factors
    from models import predict_artifacts


def predict(data_dir=".", model_dir=None):
    models = Path(model_dir) if model_dir is not None else Path(__file__).resolve().parent / "models"
    components, _ = factors.components(factors.load_train(data_dir))
    x = factors.factor_ranks(components)
    return predict_artifacts(x, models).to_frame()
