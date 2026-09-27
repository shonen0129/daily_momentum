# Short × Night decision

## Root cause

1. **Relative-rank quota admits positive High carry to the Short book.** The bottom 40% is shorted each day. `high_age_5_plus` is positive when active, and High-age-5+-dominant Short names have positive but tiny final scores; they are relatively weak versus same-day positive scores, not absolutely bearish. They occupy 56.56% of Q2 and 21.60% of Q1.
2. **Negative Low carry fills most of Q1 and loses overnight.** `low_age_5_plus` is active on 81.09% of Short stock-days and dominant on 47.59%; its state is negative on 100% of active rows. Its `-2.673pp` Short × Night annual Net contribution is the largest single source.
3. **Aged carries plus deterministic zero fills concentrate the loss.** Aged High+Low contribute `-4.506pp` (about 82% of D Short × Night loss). Exact zeros add `-0.615pp`; 8.48% of Short gross weight is zero-score, and zero membership is Code-order dependent. The observed night attribution establishes where the loss lands, not the market microstructure cause.

## Lever results

- **SN1 `SIDE_SOURCE_SEPARATION` — Reject.** The full strategy improves total Net by `+0.801pp` and Net SR by `+0.255`, but Short × Night worsens `-0.517pp`; its 20-day paired-bootstrap interval crosses zero. The `+0.465pp` Short × Day improvement cannot reverse failure of the primary night lever. High-age-5+ Short weight rises from 32.82% to 36.49% and its Short × Night loss worsens by 0.652pp.
- **SN2 `HIGH_AGE5_SHORT_VETO` — Reject.** High-age-5+ attribution improves `+0.680pp`, but the complete Short × Night cell still worsens `-0.070pp`; Short × Day falls `-1.208pp`. Turnover increases `0.0543/day`, annual cost rises `1.369pp`, total Net falls `2.374pp` and Net SR falls `0.489`. The `other` source recreates the zero-score Short mass with Code-ordered ordinal values.

Both candidates meet the repository's located numeric/index/coverage contract and retain official quintiles/exposure. The repository does not specify a numeric zero-score or unique-score threshold. Full submission evaluation was intentionally not run because its default uses Valid.

## Best surviving candidate

`None`

## Next action

End this Train-only Short × Night intervention series; retain `D_LOW_FAST_ONLY` as the current comparison candidate, with no further rescue search.

## Reproducibility

- Fixed plan: [SHORT_NIGHT_INTERVENTION_PLAN.md](SHORT_NIGHT_INTERVENTION_PLAN.md), SHA-256 `84c3a051556e2ee02a8744e521ed22f1c600c357c4b9caccc6cb4414111ca621`.
- Results: [SHORT_NIGHT_LEVER_RESULTS.md](SHORT_NIGHT_LEVER_RESULTS.md); structural audit: [SHORT_NIGHT_ROOT_CAUSE.md](SHORT_NIGHT_ROOT_CAUSE.md).
- Run: `artifacts/DM-20260927-03/run-20260926T191539Z`; source-phase audit: `artifacts/DM-20260927-03/run-20260926T185654Z`.
- HEAD `0b8341c3c0051db4b1a54040a6c4d85847bca8ec`; initial worktree was already dirty. Driver SHA-256 `cf2e7bf7893f8a79a952113120d7cdb128ebc8fda6bbe76be61096c837a2a1c2`; config SHA-256 `f039b85072872f4c02cd8fd81054af36ec507998718aa7818346aff05a442fc6`. Train file/source/helper hashes and environment are in `run.json`.
- Train firewall, P/L reconciliation and three-cutoff future-mutation prefix-invariance: PASS. Valid, raw target and submission evaluation: not accessed/run.
