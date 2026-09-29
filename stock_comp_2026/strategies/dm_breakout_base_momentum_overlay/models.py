"""Breakout-first score with pre-registered optional momentum per side."""
from .features import segment_keys

TRIAL_IDS = ("B00", "M10", "M01", "M11")


def active_percentile(excess, active):
    values = excess.where(active & (excess > 0.0))
    percentile = values.groupby(level="Date").rank(method="average", pct=True)
    return (0.5 + 0.5 * percentile).where(active & (excess > 0.0), 0.0).fillna(0.0)


def raw_signal(features, trial_id):
    if trial_id not in TRIAL_IDS:
        raise ValueError(f"Unknown trial_id: {trial_id}")
    momentum = features["res60s1"]
    high_active = features["high_available"] & (features["new_high_excess"] > 0.0)
    low_active = features["low_available"] & (features["new_low_excess"] > 0.0)
    high_score = active_percentile(features["new_high_excess"], high_active)
    low_score = active_percentile(features["new_low_excess"], low_active)

    long_score = high_score.copy()
    short_score = -low_score
    if trial_id in ("M10", "M11"):
        long_score.loc[high_active] = (
            0.5 * high_score.loc[high_active] + 0.5 * momentum.loc[high_active]
        ).clip(lower=0.0)
    if trial_id in ("M01", "M11"):
        short_score.loc[low_active] = (
            -0.5 * low_score.loc[low_active] + 0.5 * momentum.loc[low_active]
        ).clip(upper=0.0)
    return (long_score + short_score).rename(trial_id)


def smooth(signal, alpha=0.25):
    groups = segment_keys(signal.index)
    return signal.groupby(groups, sort=False).transform(
        lambda values: values.ewm(alpha=alpha, adjust=False).mean()
    )


def generate_signal(features, trial_id, alpha=0.25):
    return smooth(raw_signal(features, trial_id), alpha=alpha).rename(trial_id)
