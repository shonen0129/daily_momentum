# DM-20261001-03 decision

**Result: MIXED.** The fixed diagnostic found source- and magnitude-specific pooled differences, but the paired H1/H2 reversal did not recur consistently enough across 2011–2015 to pass the preregistered Phase 2 gate. **No strategy change; no candidate fit or evaluation.**

## Run and scope

- Run: `run-20261001T111539Z`; one fixed diagnostic; candidate fits: 0.
- Baseline: current `SN1_H1`, reproduced bit for bit through current, independent, saved-current, saved-prior and existing selected-source replay paths (809,636 rows).
- Train only; evaluation periods 2011–2016, with 2016 partial. This is known development history, not an independent OOS sample.
- Valid, the combined Train/Valid state artifact, and raw-target inputs were not opened. The existing official `target_1day_train` was used only to reproduce the fixed baseline and attribute its Train H1 target.
- Strategy code, score, source precedence, `VOL20`, threshold, official membership and weights were unchanged.

## Evidence and interpretation

- High × Non-near-zero had stronger pooled V1 than V5 RankIC (`0.01719` vs `0.00193`), with the direction in 4/5 complete years. Its Q5−Q1 spread instead favored V5 (`4.22` vs `1.12` bp/day), and V1 was higher in only 2/5 complete years.
- Low × Near-zero favored V5 on pooled RankIC (`0.00723` vs `0.00305`) and Q5−Q1 (`1.13` vs `0.33` bp/day), but the year direction held in only 2/5 RankIC years and 3/5 spread years.
- High × Near-zero favored V1 on both pooled measures; Low × Non-near-zero favored V1 on pooled measures, but neither ordering was stable across complete years.
- The V5 Long gross profit is concentrated in High × Non-near-zero × V5 (`+1.842%` annualized contribution). The largest listed Short loss is Low × Near-zero × V1 (`−0.581%`); V5 is `−0.022%`. Low-source Near-zero V1 loss is concentrated in the fixed `20_plus × no_recent_same_side` sleeve-age/renewal bucket (`−0.550%` annual gross attribution), while that bucket is positive in V5 (`+0.148%`). These are accounting attributions, not counterfactual results.
- Near-zero boundary changes were high across both sources and volatility endpoints: 70.2%–77.0% changed quintile; near-tie boundary endpoints were 94.5%–99.9%. This does not isolate high volatility as the instability source.
- Therefore the pooled high-volatility RankIC advantage is only partly traced to Low × Near-zero V5 and High × Non-near-zero Long P/L; other cells move oppositely, and pooled RankIC is non-additive across the overlapping cell ranks. There is no single stable interaction to take forward.

## Verification

- Source scan and Train-only firewall: PASS; only the five staged Train files were recorded as input parquet reads.
- Baseline score reproduction and source reconstruction: bitwise PASS.
- Future mutation/prefix invariance: PASS at `2012-06-29`, `2014-06-30`, and `2015-06-30` across all five staged Train inputs; exact prefix equality held for features, score, VOL20, selected source/state, fixed ages/renewal, weights and membership.
- Daily account, cell gross/net/cost/turnover, Long/Short contribution and gross-weight-share reconciliation: PASS. Saved-account parity remained within `2e-15`.
- Full diagnostics: [final report](../../reports/DM-20261001-03/REPORT.md); pooled/year matrices and audits are under `artifacts/DM-20261001-03/run-20261001T111539Z/`.

Phase 2 is not authorized by this result. No entry was added to `experiments/GRAVEYARD.md` because no candidate strategy was evaluated and rejected.
