# Verification notes before Valid

Eight new regression tests passed (1.40 seconds). `make check` passed (26 experiments; 129 old Freeze hashes; no data opened). Real zip produced identical predictions on all 809,636 Train rows on both calls; 2.78 seconds total, peak RSS 650,166,272 bytes, no external service or target reads. Full Train runner: 16.53 seconds.

Primary event statistics require at least five finite event rows/day. Signal-transmission `stage_daily_rankic` uses every defined daily correlation (including days with two to four events), matching the previous diagnostic convention; it is not the primary statistic. Event score/final-weight Spearman pooled across rows and equal-date daily correlation are both saved and must not be conflated.

One zip verification shell invocation used an incorrect runpy invocation and exited before loading the strategy; the corrected command completed successfully. No strategy or specification changed.
