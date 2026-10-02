# DM-20261001-03: SN1 source × magnitude × VOL20 diagnostic

- **Baseline:** `SN1_H1`
- **Trading strategy change:** **None**
- **Fixed diagnostics:** existing selected source; frozen near-zero threshold `1e-12`; existing prior-only residual `VOL20`.
- **Main question:** SN1のvolatility依存性は、sourceとscore magnitudeによって説明できるか？
- **Result:** **MIXED**
- **Strategy candidate:** None. **OOS claim:** None.
- Run: `run-20261001T111539Z`. Train development-history evidence only; Valid and raw-target inputs were not opened.

## Baseline and audit

Current, independent, saved-current, saved-prior, and selected-source reconstruction paths matched bit for bit over 809,636 rows. Source precedence audit: **PASS**.
Future mutation changed all five staged Train inputs after each frozen cutoff and preserved baseline features, VOL20, SN1_H1, source/state, official membership/weights, event/sleeve ages and renewal through cutoff: **PASS**.
The combined Train/Valid source-state artifact was not read. High/Low/fallback and fixed age buckets were reconstructed from Train baseline inputs and the existing SN1 contract.

The reused VOL20 formula, PIT beta/TOPIX inputs, listing-gap reset, missing-row counts, and prior-only contract are recorded in [`volatility_feature.json`](../../artifacts/DM-20261001-03/run-20261001T111539Z/audit/volatility_feature.json).

Unchanged baseline account summary over 2011–2016: Gross Sharpe **1.122**, Net Sharpe **1.077**, annual gross/net **+4.774% / +4.584%**, annual official cost **0.190%**, mean daily turnover **0.00762**, Mean RankIC **0.01251**, and additive maximum drawdown **−6.08%**. The yearly and partial-2016 baseline metrics are in [`baseline_metrics.csv`](../../artifacts/DM-20261001-03/run-20261001T111539Z/metrics/baseline_metrics.csv). These are reproduced Train development-history metrics, not OOS results.

## Fixed source × magnitude × volatility matrix

Near-zero is `abs(score) < 1e-12`; Non-near-zero is `>= 1e-12`. V1/V5 are endpoints of the exact prior-only residual VOL20 quintiles. Within-cell RankIC and score-ranked Q1–Q5 spreads describe ranking quality inside each fixed cell. P/L, turnover and cost rows are additive accounting attribution under unchanged weights. Turnover entries/exits are assigned to the current signal-date cell, including current neutral rows; these are not counterfactual sub-portfolios.

### Pooled High and Low endpoint comparisons

| Source | Magnitude | V1 RankIC | V5 RankIC | V1 Q5−Q1 (bp/day) | V5 Q5−Q1 (bp/day) | Annual gross contrib. V1/V5 | Long gross V1/V5 | Short gross V1/V5 |
|:--|:--|--:|--:|--:|--:|:--|:--|:--|
| High | Near-zero | -0.003808 | -0.019877 | -0.349 | -6.539 | +0.202% / +0.219% | +0.202% / +0.219% | +0.000% / +0.000% |
| High | Non-near-zero | +0.017187 | +0.001932 | +1.123 | +4.221 | +0.331% / +1.842% | +0.331% / +1.842% | +0.000% / +0.000% |
| Low | Near-zero | +0.003051 | +0.007231 | +0.326 | +1.135 | -0.257% / +0.086% | +0.324% / +0.107% | -0.581% / -0.022% |
| Low | Non-near-zero | +0.008646 | +0.006035 | -3.403 | -6.263 | +0.002% / +0.040% | +0.000% / +0.000% | +0.002% / +0.040% |

Complete pooled/yearly cells and the requested score, target, membership, weight, contribution, Sharpe, turnover, cost, and Q1–Q5 columns are in [`source_magnitude_vol_matrix.csv`](../../artifacts/DM-20261001-03/run-20261001T111539Z/metrics/source_magnitude_vol_matrix.csv). Annual rows, with 2016 marked partial, are in [`yearly_matrix.csv`](../../artifacts/DM-20261001-03/run-20261001T111539Z/metrics/yearly_matrix.csv). Long/Short detail is in [`side_source_magnitude_vol_attribution.csv`](../../artifacts/DM-20261001-03/run-20261001T111539Z/metrics/side_source_magnitude_vol_attribution.csv).

### What changes between pooled V1 and V5?

| Source × magnitude | Share of V1 rows | Share of V5 rows | RankIC V1 → V5 | Q5−Q1 V1 → V5 (bp/day) | Annual gross attribution V1 → V5 |
|:--|--:|--:|:--|:--|:--|
| D fallback × Near-zero | 7.5% | 8.0% | unavailable | unavailable | +0.052% → −0.073% |
| High × Near-zero | 8.1% | 7.3% | −0.00381 → −0.01988 | −0.35 → −6.54 | +0.202% → +0.219% |
| High × Non-near-zero | 9.3% | 19.8% | +0.01719 → +0.00193 | +1.12 → +4.22 | +0.331% → +1.842% |
| Low × Near-zero | 66.6% | 51.4% | +0.00305 → +0.00723 | +0.33 → +1.13 | −0.257% → +0.086% |
| Low × Non-near-zero | 8.5% | 13.5% | +0.00865 → +0.00604 | −3.40 → −6.26 | +0.002% → +0.040% |

The cell mix changes materially: V5 has more High × Non-near-zero observations, while Low × Near-zero still supplies just over half its rows. Ranking quality moves in opposite directions across the two sources: Low × Near-zero improves from V1 to V5, but High × Near-zero weakens; in Non-near-zero, High-source RankIC weakens while its score-ranked spread and existing Long contribution increase. Low-source Non-near-zero spread remains negative at both endpoints. So the pooled high-volatility strength is partly aligned with the Low × Near-zero cell and the High × Non-near-zero Long P/L attribution, but it is opposed by High × Near-zero and does not produce a consistent source-independent interaction. Because pooled RankIC ranks all names together, cell RankICs cannot be added to produce an exact decomposition of the pooled statistic. The fixed cells therefore describe contributors to the pooled pattern, but do not fully explain it through one stable mechanism. The composition table is saved in [`v1_v5_cell_composition.csv`](../../artifacts/DM-20261001-03/run-20261001T111539Z/metrics/v1_v5_cell_composition.csv).

### Preregistered V1/V5 comparisons

| Source | Magnitude | Metric | V1 | V5 | Direction | Pooled | Years in direction (2011–2015) |
|:--|:--|:--|--:|--:|:--|:--:|--:|
| High | Near-zero | mean_rankic | -0.003808 | -0.019877 | V5>=V1 | False | 2/5 |
| High | Near-zero | q5_q1_spread | -0.348819 | -6.539140 | V5>=V1 | False | 2/5 |
| High | Non-near-zero | mean_rankic | +0.017187 | +0.001932 | V1>V5 | True | 4/5 |
| High | Non-near-zero | q5_q1_spread | +1.123101 | +4.220623 | V1>V5 | False | 2/5 |
| Low | Near-zero | mean_rankic | +0.003051 | +0.007231 | V5>=V1 | True | 2/5 |
| Low | Near-zero | q5_q1_spread | +0.326242 | +1.134603 | V5>=V1 | True | 3/5 |
| Low | Non-near-zero | mean_rankic | +0.008646 | +0.006035 | V1>V5 | True | 1/5 |
| Low | Non-near-zero | q5_q1_spread | -3.402969 | -6.263256 | V1>V5 | True | 2/5 |

The result rule was fixed before the run. It requires the paired Non-near-zero V1>V5 and Near-zero V5≥V1 ordering on both RankIC and Q5−Q1 for one source, with each direction recurring in at least three complete years. P/L concentration is descriptive evidence, not a rule for changing strategy.

No source satisfies this joint gate. For High, only Non-near-zero RankIC follows H1 in 4/5 complete years; its Q5−Q1 endpoint direction is opposite, and its Near-zero results favor V1. For Low, both pooled Near-zero comparisons favor V5, but that ordering recurs in only 2/5 RankIC years and 3/5 spread years; Non-near-zero favors V1 on both pooled measures, but only in 1/5 and 2/5 years respectively. The paired interaction is therefore **MIXED**, with weak year stability.

### Existing Long / Short contribution locations

The largest listed Long profit is High × Non-near-zero × V5 at **+1.842% annual gross contribution** (with +1.837% net after attributed official cost). The largest listed Short loss is Low × Near-zero × V1 at **−0.581% annual gross** (−0.588% net); the corresponding V5 cell is −0.022% gross. Within Low × Near-zero × V1, existing 20-plus-session sleeves with no recent same-side renewal account for −0.550% annual gross Short contribution. In the V5 cell, that same age/renewal bucket is +0.148%, while 20-plus-session sleeves with recurrent same-side renewal are −0.176%. These are accounting and composition differences under the current portfolio, not evidence that changing volatility exposure or renewal state would improve results.

## Boundary sensitivity

The original fixed tiny perturbation is reused without tuning. Source × magnitude × V1/V5 results (changed quintile/Q1-Q2/Q4-Q5 membership, exact/near-tie boundaries) are in [`boundary_sensitivity_matrix.csv`](../../artifacts/DM-20261001-03/run-20261001T111539Z/metrics/boundary_sensitivity_matrix.csv).

Near-zero membership changed substantially in every High/Low source endpoint cell: about **70.2%–77.0%** of rows changed official quintile; the near-tie endpoint fraction was **94.5%–99.9%**. Exact-tie endpoints were absent in High/Low cells, while D fallback near-zero cells had both many exact ties and 71.6%–75.3% changed quintiles. This points to broad near-zero boundary sensitivity, not a distinctive High-volatility-only instability pattern; the fixed stress remains descriptive.

## Event age, sleeve age and renewal

Existing fixed buckets are shown in [`age_renewal_matrix.csv`](../../artifacts/DM-20261001-03/run-20261001T111539Z/metrics/age_renewal_matrix.csv). This is a composition description only; no age threshold was introduced.

## Reconciliation and interpretation

Row-level baseline gross/net/cost/turnover reconciliation passed with maximum absolute daily differences: `{"gross": 0.0, "net": 0.0, "cost": 3.198396408832238e-18, "turnover": 0.0}`. The Long/Short side table separately reconciles gross P/L, net P/L, effective/all-turnover cost, and sleeve turnover to the official account within `1.2e-15`; matrix gross-weight shares sum to 1 within each year/pooled period, including VOL_MISSING accounting rows.

The evidence is observational attribution within unchanged baseline membership and weights. It does not establish that volatility causes predictive content, that source causes volatility dependence, or that changing cell exposure would improve performance. All dates are already seen Train development history; no independent OOS claim is made.

No single clear, year-stable source × magnitude × VOL20 structure passed the preregistered Phase 2 gate. This run therefore creates no candidate and does not authorize a Phase 2 adjustment.
