# Candidate evaluation execution lock — v2

- Locked at: 2026-09-28 11:45:06 JST, before any candidate P/L metrics were calculated.
- Preregistered intervention plan SHA-256: `d8ce2b465b4ade283ff736f8dc7ea51667eaf397e1a57342c035d002db04db8e`.
- Candidate and decision criteria remain exactly those in `intervention_plan.md`.
- Evaluation driver SHA-256: `3ce40af46f9603d90a263c5b4130ec8acce9b3f9367e06836230bdb772a159c6`.
- Evaluation helper hash: `4da3e290f49e2061f2fdaf4efdb6e1ae5ecda5babc4dc9e9f6f77fc7ae891c4e`.

## Pre-metric execution correction

Two pre-metric runs stopped on coverage assertions; neither wrote candidate P/L metrics. The final replay now matches the official helper's target-index alignment over the full allowed H1 target panel, preserving the pre-evaluation history that sets initial turnover. The report and paired comparison are then restricted to the saved official account dates. This matches the baseline account replay method already used in Phase 2. The candidate formula, 60-session condition, cost, target, evaluation dates, and decision criteria remain unchanged.

This lock supersedes the execution-driver hashes in the earlier supplemental lock records. The intervention plan itself remains unchanged and hash-verified.
