"""Prediction models for dm_high_proximity_momentum."""
import numpy as np
import pandas as pd
from features import smooth


def generate_signal(features, trial_id, alpha=0.25):
    """Generate smoothed cross-sectional rank signal for a specified trial.

    Trial Candidates:
    - H0: Baseline Champion res60s1 EWMA(0.25)
    - P60: Pure 60-day high proximity EWMA(0.25)
    - P250: Pure 250-day (52-week) high proximity EWMA(0.25)
    - C3S: 0.5 * res60s1 + 0.5 * split-safe prox250 with a full 250-row window
    - C1: Blend 0.5 * res60s1 + 0.5 * prox20 EWMA(0.25)
    - C2: Blend 0.5 * res60s1 + 0.5 * prox60 EWMA(0.25)
    - C3: Blend 0.5 * res60s1 + 0.5 * prox250 EWMA(0.25)
    - C4: Tilt res60s1 + 0.25 * prox60 EWMA(0.25)
    - C5: Interaction res60s1 * (1.0 + 0.5 * prox60) EWMA(0.25)
    - C6: Equal blend of C2 and C3: 0.5 * res60s1 + 0.25 * prox60 + 0.25 * prox250
    """
    m = features['res60s1']
    p20 = features['prox20']
    p60 = features['prox60']
    p250 = features['prox250']

    if trial_id == 'H0':
        raw = m
    elif trial_id == 'P60':
        raw = p60
    elif trial_id == 'P250':
        raw = p250
    elif trial_id == 'C1':
        raw = 0.5 * m + 0.5 * p20
    elif trial_id == 'C2':
        raw = 0.5 * m + 0.5 * p60
    elif trial_id == 'C3':
        raw = 0.5 * m + 0.5 * p250
    elif trial_id == 'C3S':
        raw = 0.5 * m + 0.5 * features['prox250_split_safe']
    elif trial_id == 'C4':
        raw = m + 0.25 * p60
    elif trial_id == 'C5':
        raw = m * (1.0 + 0.5 * p60)
    elif trial_id == 'C6':
        # Equivalent to averaging the C2 and C3 score streams before smoothing.
        raw = 0.5 * m + 0.25 * p60 + 0.25 * p250
    else:
        raise ValueError(f'Unknown trial_id: {trial_id}')

    return smooth(raw, alpha=alpha)
