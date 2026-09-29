# Short Loss Decomposition — SN1_H1

Train and historical Valid are both development data. H1 residual outcomes use the already-saved H1 target; the event-only control uses the saved event-date Ridge score with no EWMA carry and no holding-period search.

## A. Event prediction

| Split | Event side | Events with H1 target | Mean signed-score RankIC | RankIC HAC t | Hit ratio | Mean Q5−Q1 residual spread | Spread HAC t |
|---|---|---:|---:|---:|---:|---:|---:|
| Train | High | 15,513 | +0.0220 | 1.58 | 52.4% | +0.0606% | 0.86 |
| Train | Low | 4,302 | −0.0146 | −0.49 | 47.2% | +0.0532% | 0.29 |
| Historical Valid | High | 30,464 | +0.0255 | 2.72 | 52.3% | +0.1027% | 1.95 |
| Historical Valid | Low | 11,667 | −0.0009 | −0.05 | 46.8% | −0.0985% | −1.13 |

The signed Low score has the declared direction: a more negative score means a stronger bearish prediction, so a consistently informative bearish ranking should have positive association with the raw residual return as the signed score rises. Low event quality is weak and does not reproduce across Train and historical Valid. High is directionally positive in both, with stronger evidence in historical Valid. Event-score deciles are saved in `event_only_h1_score_deciles.csv`; they are descriptive and were not used to define any threshold.

## B. State and ranking

All material Short positions are Low-source positions. For persistent `≥20`-session Low Shorts, the annualized Net account contribution is:

| Split | No recent same-side event | Recurrent, ≥2 same-side events in 60 sessions | One same-side event in 60 sessions |
|---|---:|---:|---:|
| Train | −1.275% | −0.263% | −0.041% |
| Historical Valid | −0.461% | −0.963% | −0.133% |

State persistence and relative ranking extend the influence of old, near-zero Low states. Yet recent/recurrent Low Shorts also lose in historical Valid, so a stale-state-only explanation is insufficient. This matches the prior rejection of `SN1_LOW_STATE_EXPIRY_60D`; no new age rule was tried.

## C. Systematic exposure

Persistent Short weight is concentrated in `TOPIX Mid400` in both periods (67.4% Train, 74.9% historical Valid), with annualized Net contributions of −1.188% and −1.078%. Smaller-size groups also lose. The most negative Sector17 bucket differs: code 14 in Train and code 10 in historical Valid. Existing 120-day PIT beta shows persistent Long mean beta 0.905/0.956 and Short mean beta 1.110/1.065 (Train/Valid); mean daily signed beta load is +0.431/−0.514 and +0.462/−0.483. The residual target already subtracts β×TOPIX. This describes stable Short beta/size exposure, but it does not identify a unique exposure whose correction is justified by both datasets.

## Conclusion

1. The Low event predictor itself is weak and inconsistent at H1.
2. Near-zero state persistence and cross-sectional rank assignment prolong Low-source Shorts, but recent Low events also fail to prevent historical-Valid losses.
3. Size and beta exposures are visible, but the sector loss pattern changes and the attribution is descriptive; no single parameter-free risk rule follows uniquely.

No source deletion, Short gamma, age cutoff, threshold, or risk projection was tested. The evidence does not pass the candidate eligibility gate.

