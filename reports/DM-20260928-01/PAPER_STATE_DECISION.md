# Paper state decision

## Decision

**No surviving state intervention. Paper challenger: `None`.** Keep the fixed `SN1_H1` specification as the paper reference; do not promote `SN1_LOW_STATE_EXPIRY_60D` or create another state-age variant from these historical results.

## Root cause

1. High and Low EWMA amplitudes decay geometrically, but SN1 source precedence is sign-based. A tiny negative Low state can therefore remain selected and preserve relative ranking long after its absolute magnitude has nearly vanished; it can mask positive High state.
2. Persistent Long membership is the robust positive contribution in both development periods. Persistent Shorts lose, and recurrent Low-origin Shorts also lose in historical Valid, so stale-state expiry alone does not explain or cure the Short loss.
3. The one fixed expiry resets a broad part of the cross-section. It raises turnover about 3–4.5× and cost in both periods, lowers Gross and damages Long contribution. The mechanical ranking change does not translate into better realized selection.

## Lever result

`SN1_LOW_STATE_EXPIRY_60D`: **Reject** under the preregistered rule. Gross and Net decline in both Train and already-open historical Valid; Long Net declines in both; cost increases; point-estimate Net SR declines. Train exact zeros rise from 8.76% to 17.03%, mean unique-score ratio falls from 91.21% to 82.80%, and boundary-tie rows increase from 6.42% to 14.48%. The candidate retains all five official quintiles and exposure, but that does not offset the economic and Train score-quality failures.

## Why retain H1 as the reference

- The data confirm unusually persistent portfolio membership, but fixed-lag event/state prediction diagnostics are mixed across split, side and horizon.
- Entry and holding-age returns are not uniform: persistent Long contribution is positive, while Short contribution remains negative even with recent Low-event renewal.
- The only registered age intervention reduced persistence mechanically but failed gross, net, Long and cost criteria. No evidence justifies changing the frozen SN1 state logic.

## Remaining uncertainty

- Train and historical Valid have both been viewed and are development data; neither establishes prospective performance.
- Membership spell length is based on quintile assignment, is censored at sample edges, and is not fixed-share ownership.
- The existing official ranking is deterministic by `(Date, Code)` for ties; it is not invariant to changing identifier order. No secondary tie-break was tested.

## Next action

Use unchanged `SN1_H1` only as the paper baseline and accumulate a fully forward paper record for at least six months, logging monthly Gross/Net return, cost, turnover, drawdown, Long/Short contribution and RankIC without switching state rules or horizons.

The candidate result and preregistration are in [STATE_INTERVENTION_RESULTS.md](STATE_INTERVENTION_RESULTS.md) and [STATE_INTERVENTION_PLAN.md](STATE_INTERVENTION_PLAN.md). No paper-period data has been read.
