"""Fixed final-score combination; component modules are byte-identical copies."""
import numpy as np
import pandas as pd

try:
    from .component_sn1 import features as sn_features, bidirectional, sn1
    from .component_slow import features as slow_features
except ImportError:
    from component_sn1 import features as sn_features, bidirectional, sn1
    from component_slow import features as slow_features


def components(sn_inputs, slow_inputs, train_target, years=range(2011, 2017), model_dir=None):
    x = sn_features.build_features(sn_inputs)
    f = slow_features.build_features(slow_inputs, sector=False)
    if not x.index.equals(f.index) or not x.index.equals(train_target.index):
        raise ValueError("Component features and Train labels require exact index alignment")
    predictions, records = bidirectional.walk_forward_predictions(
        x, train_target, years=years, model_dir=model_dir)
    base = bidirectional.generate_signal(x, predictions, alpha=sn1.HIGH_ALPHA)
    s = sn1.rebuild_from_base_score(base)["SIDE_SOURCE_SEPARATION"].rename("SN1_H1")
    slow = f.size_liquidity.rename("SLOW_CONTROL")
    return pd.concat([s, slow], axis=1), x, f, records


def blend(sn_score, slow_score):
    if not sn_score.index.equals(slow_score.index):
        raise ValueError("Component final-score indexes differ")
    if sn_score.index.names != ["Date", "Code"] or not sn_score.index.is_unique:
        raise ValueError("Expected unique Date/Code index")
    if not np.isfinite(sn_score.to_numpy()).all() or not np.isfinite(slow_score.to_numpy()).all():
        raise ValueError("Components must provide finite scores at every row")
    # Use the unchanged original centered average percentile implementation.
    return (sn_features.centered_rank(sn_score) + sn_features.centered_rank(slow_score)).rename("SN1_SLOW_BLEND")
