# Horizon mechanism

## Finding

There is a structural mismatch between the H1 Ridge label and the portfolio's long-lived membership, but changing only the Ridge target horizon does not resolve it in Train and historical Valid.

## Membership is much longer than the label

H1 targets Open(t+1) to Open(t+2). Sleeve membership lasts a mean 334/264 sessions for Long/Short in Train and 331/224 in old Valid; median spells are 141/154 Train and 208/165 old Valid. Over 85% of Long spells and about 90% of Short spells last at least 20 sessions. Same-sleeve retention is 98.7–99.7%; lag-1 rank autocorrelation is about .996. This is a real architecture-level mismatch, although the portfolio's daily weights may still change.

## H5/H20 do not change the persistence mechanism

Across the three fixed candidates, rank autocorrelation, Q retention, spell duration, sleeve entrants/exits, daily distinct holdings and sector/scale mix remain almost identical. Turnover rises from .7655% to .7678% in Train and .9514% to .9593% in old Valid. Transaction cost rises slightly. The persistence is therefore chiefly a property of the fixed event/EWMA/SN1 scoring architecture, not a lower turnover induced by longer labels.

## Longer-horizon forecasts do not repeat reliably

H5 score RankIC Train is .0275 (HAC t 3.56) for days 1–5 and .0389 (t 4.38) for days 6–20; old Valid falls to .0070 (t 1.23) and .0063 (t .93). H20 Train RankIC is .0423 (t 3.03) through days 1–20 and .0417 (t 2.94) for days 21–40; old Valid is .0050 (t .50) and .0076 (t .78). Thus the apparent Train relation does not repeat.

Event-side evidence is asymmetric: H20 Low events have a modest old-Valid relation through days 1–20 but none over days 21–40; High events lose their relation by days 1–20. This does not create a reliably positive Short sleeve.

## Event-date contribution profile

The event-date diagnostic averages compounded market-residual returns per breakout event, oriented High=long and Low=short. It is unweighted and is not account P/L. Fixed windows are day 1, days 2–5, days 6–20 and days 21–40; event definitions are identical across candidates. Full counts and event-weighted/date-equal means are in the results report. Script SHA256 9e68da202f5f2611c14839550894f3f597d85cd20061bed623734aa30c0dcc60.

Train event returns are mixed across High and Low windows. Historical Valid event averages are mostly small or negative through day 20, while days 21–40 show positive High and negative Low event-oriented means. This does not establish an executable forecast: it is unconditional on Ridge score rank and must not be attributed to H5/H20. It does not alter the horizon decision.

## Portfolio effect is small and not from lower cost

H5 Net change versus H1 is −0.73 bp/year Train and +7.26 bp old Valid. H20 is +9.55 bp Train including its 59-session 2016 partial, but −0.04 bp ex-2016, and +5.28 bp old Valid. Common-weight P/L is unchanged in the accounting decomposition; gross changes come from reselected weights. Turnover and cost rise slightly. Long annual Net changes are at most +1.90 bp and all paired bootstrap intervals span zero.

Persistent ≥20-session membership accounts for nearly all positive gross Long contribution under H1 as well as H5/H20. Persistent Short membership accounts for much of the negative Short gross contribution. Those are descriptive attribution results, not causal proof.

## Conclusion

A mismatch exists, but H5/H20 do not provide period-stable evidence of a durable longer-horizon forecast or meaningful Long improvement. Keep H1 in fixed paper collection; do not call target extension a solution.
