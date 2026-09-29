# Candidate evaluation execution lock

- Locked at: 2026-09-28 11:42 JST, before any candidate P/L metrics were calculated.
- Preregistered intervention plan SHA-256: `d8ce2b465b4ade283ff736f8dc7ea51667eaf397e1a57342c035d002db04db8e`.
- Candidate remains exactly `SN1_LOW_STATE_EXPIRY_60D` as defined in `intervention_plan.md`; one candidate only.
- Evaluation driver SHA-256 for the authoritative run: `260131d850ecf0ea71555163f259718ad56a4daba2fab330ffc1ee0b9ef64965`.
- Evaluation helper hash: `4da3e290f49e2061f2fdaf4efdb6e1ae5ecda5babc4dc9e9f6f77fc7ae891c4e`.

## Pre-metric correction

The first execution stopped while comparing full Phase 1 state-table rows with the saved H1 target. The Train state table includes the final two label-maturity dates outside the official daily-account evaluation range. The correction restricts the coverage assertion to official saved account dates. No candidate daily P/L, metric, or candidate-vs-baseline comparison was calculated in the stopped run. The candidate transformation, H1 target, cost, sample dates, metrics, and decision criteria are unchanged.

The authoritative evaluation is allowed only with this code hash and the already locked plan hash. The first stopped output is retained under `artifacts/DM-20260928-01/intervention-results/FAILED.md`.
