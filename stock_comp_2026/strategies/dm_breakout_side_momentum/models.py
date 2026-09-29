"""Four pre-registered independent Long/Short breakout toggles."""
from .features import smooth


TRIAL_IDS = ("M00", "H10", "L01", "HL11")


def raw_signal(features, trial_id):
    """Compose side-specific breakout ranks without changing the other leg."""
    if trial_id not in TRIAL_IDS:
        raise ValueError(f"Unknown trial_id: {trial_id}")
    momentum = features["res60s1"]
    raw = momentum.copy()
    if trial_id in ("H10", "HL11"):
        use = (momentum > 0) & features["high_available"]
        raw.loc[use] = (
            0.5 * momentum.loc[use] + 0.5 * features.loc[use, "new_high_rank"]
        ).clip(lower=0.0)
    if trial_id in ("L01", "HL11"):
        use = (momentum < 0) & features["low_available"]
        raw.loc[use] = (
            0.5 * momentum.loc[use] - 0.5 * features.loc[use, "new_low_rank"]
        ).clip(upper=0.0)
    return raw.rename(trial_id)


def generate_signal(features, trial_id, alpha=0.25):
    """Return the EWMA-smoothed score used by the common portfolio accounting."""
    return smooth(raw_signal(features, trial_id), alpha=alpha).rename(trial_id)
