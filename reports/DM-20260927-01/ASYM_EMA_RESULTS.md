# Asymmetric EWMA diagnostic — DM-20260927-01

**Interpretation: D — results are mixed; the cause cannot be reduced to lost Low-side signal or trading cost alone.** The fixed Candidate C materially reduces the zero-score/tie-driven Short book and reverses much of `A_LOW_NO_CARRY`'s turnover increase. Net Sharpe improves only slightly versus A, remains below `BOX_ORIGINAL`, and falls ex-2016. A also loses gross selection contribution while its trading cost increases. The experiment therefore does not establish a generally useful asymmetric rule or a BOX-specific improvement.

All figures below use previously seen Train data. They are descriptive diagnostics, not independent out-of-sample evidence. Candidate C is the single pre-registered pair `alpha_high=0.15`, `alpha_low=0.50`; no alpha search or Valid evaluation was run.

## 1. Gross effect

| Strategy | Annual Gross | Gross Vol | Gross Sharpe | Annual Common | Annual Selection |
| --- | ---: | ---: | ---: | ---: | ---: |
| BOX_ORIGINAL | 4.448% | 4.643% | 0.958 | 0.055% | 4.393% |
| A_LOW_NO_CARRY | 4.167% | 4.071% | 1.024 | 0.089% | 4.078% |
| C_ASYM_EWMA | 4.269% | 4.567% | 0.935 | 0.059% | 4.211% |

`A_LOW_NO_CARRY` is not a pure cost failure: against BOX its annual Gross Return is lower by **0.281 percentage points**, and its cross-sectional selection component is lower by **0.315 points**. Its Gross Sharpe rises because annualized Gross Vol falls by 0.572 points. Candidate C recovers 0.103 points of Gross Return and 0.133 points of selection versus A, while common residual contribution falls by 0.031 points. It does not retain A's Gross Sharpe: 0.935 versus 1.024.

Long / Short gross contributions for the full evaluation are in the table below; positive portfolio return is shown as positive and Short losses as negative.

| Strategy | Long Gross | Long Net | Short Gross | Short Net |
| --- | ---: | ---: | ---: | ---: |
| B00_BASE | +5.942% | +5.384% | -1.334% | -1.559% |
| BOX_ORIGINAL | +5.867% | +5.297% | -1.419% | -1.649% |
| A_LOW_NO_CARRY | +5.711% | +5.092% | -1.544% | -2.077% |
| C_ASYM_EWMA | +5.642% | +5.093% | -1.373% | -1.634% |
| C_B00_ASYM_EWMA | +5.906% | +5.371% | -1.239% | -1.504% |

The decomposition uses the same-day, target-valid universe residual mean multiplied by each sleeve's label-valid exposure; selection is the remainder of actual sleeve Gross P/L. This is the same accounting definition used in the previous BOX audit. Full daily components are saved in each `daily_account_*.csv`.

## 2. Cost effect

| Strategy | Turnover / day | Annual Cost | Mean score-rank autocorrelation | Q1 retention | Q5 retention | Q1 entries / exits per day | Q5 entries / exits per day | Q1 weight turnover / day | Q5 weight turnover / day | Quintile changes / day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BOX_ORIGINAL | 0.03185 | 0.799% | 0.98680 | 0.98854 | 0.95822 | 1.05 / 1.04 | 3.80 / 3.80 | 0.00772 | 0.02792 | 13.49 |
| A_LOW_NO_CARRY | 0.04589 | 1.151% | 0.97873 | 0.96584 | 0.95756 | 3.09 / 3.09 | 3.86 / 3.86 | 0.02292 | 0.02836 | 18.91 |
| C_ASYM_EWMA | 0.03229 | 0.810% | 0.98794 | 0.98668 | 0.96168 | 1.22 / 1.21 | 3.49 / 3.49 | 0.00896 | 0.02562 | 14.01 |
| C_B00_ASYM_EWMA | 0.03189 | 0.800% | 0.98910 | 0.98643 | 0.96315 | 1.24 / 1.23 | 3.36 / 3.36 | 0.00913 | 0.02464 | 14.03 |

Rank autocorrelation and retention are means over adjacent evaluation-date transitions; entrants/exits count names changing tail membership; tail weight turnover is the absolute daily change in Q1 or Q5 weights. Candidate C versus A raises score-rank autocorrelation from 0.97873 to 0.98794, Q1 retention from 96.58% to 98.67%, and reduces Q1 entrants from 3.09 to 1.22 per day. Total turnover falls 29.7%, from 0.04589 to 0.03229. The Q1 weight turnover falls from 0.02292 to 0.00896. The Q5 metrics change less.

This is consistent with the discontinuous rank / rebalance mechanism behind A's cost increase. It does not prove Low carry alone caused the change: C also changes High alpha from 0.25 to 0.15, as specified by the one fixed asymmetric rule.

## 3. Portfolio composition effect

Short gross weight attribution (% of the Short sleeve):

| Strategy | High event | High age 1–4 | High age 5+ | Low event | Low age 1–4 | Low age 5+ | Zero tail tie | Zero non-tail tie |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BOX_ORIGINAL | 0.00% | 0.00% | 30.25% | 1.70% | 4.90% | 55.09% | 6.33% | 1.72% |
| A_LOW_NO_CARRY | 0.00% | 0.00% | 50.73% | 2.41% | 0.00% | 0.00% | 34.65% | 12.21% |
| C_ASYM_EWMA | 0.00% | 0.00% | 37.38% | 1.98% | 5.13% | 46.63% | 7.05% | 1.82% |
| C_B00_ASYM_EWMA | 0.00% | 0.00% | 38.62% | 2.00% | 5.12% | 48.95% | 4.76% | 0.55% |

Candidate C restores a nonzero Low aged component in Short positions while avoiding A's large replacement by aged High and zero-score names. A's Q1 score-zero weight share is **51.87%**, versus **10.55%** for C and **9.48%** for BOX. The mean code-order/quintile Spearman diagnostic among zero scores falls from **0.903** in A to **0.755** in C; BOX is 0.812. The mechanical tie dependence is lower than A but remains present. Q1 average maximum sector weight share / sector HHI are 16.36% / 0.0873 for A, 15.33% / 0.0752 for C, and 15.28% / 0.0768 for BOX.

Long attribution (annual P/L contribution as percentage points; turnover share is of Long-sleeve turnover):

| Strategy | High source | Long weight share | Gross contribution | Net contribution | Turnover share |
| --- | --- | ---: | ---: | ---: | ---: |
| BOX_ORIGINAL | Event day | 5.94% | +0.073% | -0.161% | 41.08% |
| BOX_ORIGINAL | Age 1–4 | 16.42% | +0.895% | +0.808% | 15.18% |
| BOX_ORIGINAL | Age 5+ | 73.21% | +4.763% | +4.531% | 40.66% |
| A_LOW_NO_CARRY | Event day | 5.94% | +0.072% | -0.164% | 38.15% |
| A_LOW_NO_CARRY | Age 1–4 | 16.42% | +0.894% | +0.808% | 13.98% |
| A_LOW_NO_CARRY | Age 5+ | 75.10% | +4.755% | +4.484% | 43.72% |
| C_ASYM_EWMA | Event day | 4.97% | +0.021% | -0.185% | 37.46% |
| C_ASYM_EWMA | Age 1–4 | 14.74% | +0.776% | +0.704% | 12.95% |
| C_ASYM_EWMA | Age 5+ | 77.15% | +4.827% | +4.574% | 46.14% |

High age 5+ remains the largest positive Long source for all three. Its weight share and turnover share increase for C, but the whole C Long Gross sleeve falls versus BOX. These age figures are source attribution within the official portfolio, not independent entry or holding strategies. The full Long and Short event-age, zero-score, P/L, cost, and turnover attribution is in `annual_category_attribution.csv`; year-by-year attribution is in `category_by_year.csv`.

## 4. Net effect

| Strategy | Annual Gross | Annual Net | Gross Vol | Gross SR | Net SR | Turnover / day | Annual Cost | Max additive DD | ex-2016 Net | ex-2016 Net SR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B00_BASE | 4.608% | 3.826% | 4.662% | 0.988 | 0.820 | 0.03117 | 0.782% | -6.988% | 3.163% | 0.705 |
| BOX_ORIGINAL | 4.448% | 3.649% | 4.643% | 0.958 | 0.785 | 0.03185 | 0.799% | -6.225% | 3.009% | 0.675 |
| A_LOW_NO_CARRY | 4.167% | 3.015% | 4.071% | 1.024 | 0.739 | 0.04589 | 1.151% | -6.130% | 2.784% | 0.698 |
| C_ASYM_EWMA | 4.269% | 3.459% | 4.567% | 0.935 | 0.757 | 0.03229 | 0.810% | -6.073% | 2.878% | 0.654 |
| C_B00_ASYM_EWMA | 4.667% | 3.866% | 4.598% | 1.015 | 0.840 | 0.03189 | 0.800% | -6.604% | 3.265% | 0.736 |

The accounting identity is `annual Net = annual Gross − annual transaction cost` (small rounding differences aside):

- A versus BOX: **−0.633 percentage points Net = −0.281 Gross − 0.352 higher cost**.
- C versus A: **+0.444 points Net = +0.103 Gross + 0.341 lower cost**. C therefore improves Net mostly through lower trading cost, while Gross Return also recovers slightly; Gross Sharpe falls by 0.089.
- C versus BOX: **−0.190 points Net = −0.179 Gross − 0.011 higher cost**. Candidate C does not beat the original BOX result.

| Strategy | 2011 Net return / SR | 2012 | 2013 | 2014 | 2015 | 2016 partial |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B00_BASE | 0.706% / 0.154 | 6.161% / 1.275 | 4.812% / 0.962 | 4.197% / 1.527 | -0.106% / -0.022 | 17.476% / 2.331 |
| BOX_ORIGINAL | -0.158% / -0.034 | 6.119% / 1.263 | 4.894% / 0.997 | 4.161% / 1.521 | -0.021% / -0.004 | 16.841% / 2.220 |
| A_LOW_NO_CARRY | -1.088% / -0.295 | 6.834% / 1.786 | 4.656% / 0.959 | 3.643% / 1.362 | -0.187% / -0.041 | 7.792% / 1.372 |
| C_ASYM_EWMA | -0.406% / -0.089 | 6.655% / 1.413 | 5.001% / 1.019 | 3.496% / 1.286 | -0.416% / -0.088 | 15.445% / 2.115 |
| C_B00_ASYM_EWMA | 1.195% / 0.263 | 6.548% / 1.412 | 4.767% / 0.947 | 3.970% / 1.447 | -0.206% / -0.042 | 16.251% / 2.250 |

The exact 2016 partial period is **2016-01-04 through 2016-03-29** (59 evaluation days). C improves 2011 versus A but worsens 2015: annual Net is -0.406% versus -1.088% in 2011, then -0.416% versus -0.187% in 2015. Ex-2016 Net Return is slightly higher than A (+0.094 points), while ex-2016 Net Sharpe is lower (0.654 versus 0.698). Thus the ex-2016 Sharpe condition is not met.

## 5. B00 comparison

Applying the exact same fixed alpha pair to B00 yields Net Sharpe **0.840** versus B00_BASE **0.820** (+0.020) and annual Net Return **3.866%** versus **3.826%** (+0.041 points), while annual cost rises by 0.018 points. Ex-2016 Net Sharpe improves by 0.031. This small Train result means the asymmetric persistence rule is not a BOX-specific effect.

Compared with `C_B00_ASYM_EWMA`, `C_ASYM_EWMA` has 0.083 lower Net Sharpe and 0.407 points lower annual Net Return. In 2011, the BOX candidate is also 0.352 lower Net Sharpe than same-rule B00. Treat this as an attribution control on known Train, not proof that the rule generalizes.

## 6. Interpretation

**D — mixed and inconclusive.** A's net loss is not explained by one mechanism alone: the gross selection component falls by 0.315 points versus BOX, and annual cost rises by 0.352 points. C substantially reduces A's score-zero Short book and turnover; its Net improvement over A is largely cost-related, with a smaller recovery in Gross Return and selection. Yet C's Gross Sharpe is lower than A's, its ex-2016 Net Sharpe is worse, 2015 deteriorates, and original BOX remains better on pooled Net Return and Net Sharpe. Because the fixed C rule also changes High alpha, this comparison cannot assign all portfolio changes solely to Low carry.

### Reproducibility and limits

- Evaluation: 2011-01-04 to 2016-03-29, 1,275 dates; 2016 partial fold: 59 dates. Results are previously reviewed Train, never Valid.
- One-way transaction cost 10 bps; annualization 252; official five-quintile weights and tie-break retained. RankIC, exposure, long/short correlation, active/nonzero scores, Q1/Q5 sector measures, all period metrics, daily accounts, and full stock-day weights are in the CSV/Parquet outputs below.
- Saved `B00_BASE`, `BOX_ORIGINAL`, and `A_LOW_NO_CARRY` scores and weights replayed exactly (maximum score error 0; weight/account error below `1e-16`). All five signals cover 809,636 Train stock-days. PIT sector join coverage is 100%; the source score EWMA inversion error is below `1.2e-16`.
- The official weight helper and repository evaluation helper matched exactly. Four focused tests passed, including recurrence/additivity and future-prefix invariance; `make check` passed. Valid was not accessed. No bootstrap was run; this is a fixed descriptive comparison, and small differences should not be treated as statistical confirmation.
- One initial diagnostic run was retained as failed after detecting that an already-purged saved date index was about to be purged a second time. The successful run reused the saved 1,275-date evaluation span; no model result from the failed run was used.

Artifacts from successful run `run-20260926T165750Z-01`:

- `../../artifacts/DM-20260927-01/run-20260926T165750Z-01/metrics/period_metrics.csv`
- `../../artifacts/DM-20260927-01/run-20260926T165750Z-01/metrics/paired_period_differences.csv`
- `../../artifacts/DM-20260927-01/run-20260926T165750Z-01/metrics/rank_diagnostics_period.csv` and `rank_diagnostics_daily.csv`
- `../../artifacts/DM-20260927-01/run-20260926T165750Z-01/metrics/annual_category_attribution.csv` and `category_by_year.csv`
- `../../artifacts/DM-20260927-01/run-20260926T165750Z-01/predictions/strategy_scores.parquet`, `portfolio_weights.parquet`, and `holdings_audit.parquet`
- Run hashes, parameters, Train firewall log, and replay checks: `../../artifacts/DM-20260927-01/run-20260926T165750Z-01/run.json` and `audit/`
