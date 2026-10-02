# DM-20261001-01: UP_PULLBACK added to SN1_H1

**Baseline:** current `SN1_H1` (five Ridge inputs).  
**Candidate:** `SN1_H1 + UP_PULLBACK` (sixth and only added input).  
**Decision:** **REJECT**.  
**Primary gates:** Mean RankIC Δ -0.0000013 (FAIL); gross annual Δ +0.464 bp/year (PASS); Q5−Q1 Δ +0.00979 bp/day (PASS).
**Limitation:** all 2011–2016 Train dates and the motivating attribution bucket were already inspected; this is development-history evidence, not independent OOS evidence.

## Pooled results, 2011–2016

Annual return/cost values are annualized from daily means. Q5−Q1 is a daily residual-return spread. RankIC t-stat uses repository HAC-5. Cost_all charges 10 bp on all turnover; `net` follows the official evaluator expression and `net_all_cost` is the all-position cost diagnostic.

| Metric | Baseline | Candidate | Delta |
|---|---:|---:|---:|
| Gross Sharpe | 1.1220984 | 1.1227796 | +0.0006812409 | 
| Net Sharpe | 1.0773126 | 1.0779636 | +0.00065102656 |
| Mean RankIC | 0.012506495 | 0.012505239 | -1.2559907e-06 |
| RankIC HAC-5 t-stat | 3.1308519 | 3.1311438 | +0.00029186229 |
| RankIC hit ratio | 0.54700855 | 0.54778555 | +0.00077700078 |
| Annualized gross return (%) | 4.7744274% | 4.7790651% | +0.0046377014% |
| Annualized net return (%) | 4.5842964% | 4.5887173% | +0.0044208962% |
| Annualized cost, all turnover (%) | 0.19197646% | 0.19219326% | +0.00021680521% |
| Average daily turnover | 0.0076181135 | 0.0076267169 | +8.6033812e-06 |
| Maximum drawdown (compound, net, %) | -5.9541545% | -5.9563638% | -0.0022092836% |
| Annualized Long contribution (%) | 6.107982% | 6.1086603% | +0.00067838241% |
| Annualized Short contribution (%) | -1.3335545% | -1.3295952% | +0.003959319% |
| Quintile monotonicity | 0.9 | 0.9 | +0 |
| Q5−Q1 (bp/day) | 4.7653438 bp/day | 4.7751372 bp/day | +0.0097934581 bp/day |

## Fold and year deltas

Each annual return is that fold's daily mean × 252; 2016 covers 61 sessions and is partial. The separate sensitivity below pools only complete years 2011–2015.

| Year | Sessions | Gross return Δ | Net return Δ | RankIC Δ | Q5−Q1 Δ (bp/day) | Long Δ | Short Δ |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2011 | 245 | +1.435 bp/year | +1.435 bp/year | +0.0000166 | +0.0316 | +0.246 bp/year | +1.189 bp/year |
| 2012 | 248 | -1.263 bp/year | -1.339 bp/year | -0.0000175 | -0.0381 | +0.109 bp/year | -1.371 bp/year |
| 2013 | 245 | +0.000 bp/year | +0.000 bp/year | -0.0000077 | +0.0000 | +0.000 bp/year | +0.000 bp/year |
| 2014 | 244 | -1.535 bp/year | -1.535 bp/year | -0.0000037 | +0.0053 | +0.000 bp/year | -1.535 bp/year |
| 2015 | 244 | +0.000 bp/year | +0.000 bp/year | +0.0000039 | +0.0000 | +0.000 bp/year | +0.000 bp/year |
| 2016 * | 61 | +15.294 bp/year | +15.148 bp/year | +0.0000083 | +0.2137 | +0.000 bp/year | +15.294 bp/year |

### Partial-year sensitivity

2016 contributed 61 sessions. Excluding it, the deltas are Mean RankIC **-0.0000017**, annualized gross **-0.274 bp/year**, Q5−Q1 **-0.0003 bp/day**, and annualized net **-0.290 bp/year**.

## UP_PULLBACK attribution

Buckets are assigned from the existing as-of `event_upstate` and `event_box_position`; undefined Box positions fall into Other. Returns use official Train residual target. Portfolio migration uses the official five-quintile weights.

| Bucket | Rows | Dates | Mean centered target rank | Mean residual return | Mean score Δ | Net Q4/Q5 migration | Annual gross contribution Δ |
|---|---:|---:|---:|---:|---:|---:|---:|
| UPSTATE=1,x<0 | 13686 | 1185 | +0.021531 | +6.3043 bp | +1.703738e-05 | -1 | +0.138 bp/year |
| UPSTATE=1,x>=0 | 20406 | 1181 | -0.006348 | +0.9692 bp | -3.93759e-09 | +0 | -0.000 bp/year |
| UPSTATE=0,x<0 | 33274 | 1278 | +0.001541 | +1.4904 bp | -5.613049e-05 | -4 | -0.199 bp/year |
| Other | 510830 | 1287 | -0.000113 | +2.7496 bp | +3.199876e-06 | +5 | +0.525 bp/year |

For `UPSTATE=1, x<0`, baseline Q4/Q5 rows were 6394 and candidate rows 6393; it entered Q4/Q5 on 1 rows and exited on 2 rows. The Long contribution delta is +0.068 bp/year; the Short contribution delta is +0.396 bp/year; short deterioration / positive long improvement is 0.0.

Full quintile/side transition tables are in [`quintile_migration.csv`](../../artifacts/DM-20261001-01/run-20261001T052315Z/metrics/quintile_migration.csv) and [`long_neutral_short_migration.csv`](../../artifacts/DM-20261001-01/run-20261001T052315Z/metrics/long_neutral_short_migration.csv); full bucket values are in [`attribution_table.csv`](../../artifacts/DM-20261001-01/run-20261001T052315Z/metrics/attribution_table.csv).
Pooled/year/incremental metrics and [daily accounts](../../artifacts/DM-20261001-01/run-20261001T052315Z/metrics/) are stored with the run artifacts.

## Decision checks and audit

- Candidate decision: **REJECT**. Primary gate details: `{"positive_mean_rankic_delta": false, "positive_annual_gross_return_delta": true, "positive_q5_q1_delta": true}`.
- Complete-year sensitivity 2011–2015: `{"positive_rankic_delta_without_2016": false, "positive_gross_delta_without_2016": false, "positive_q5_q1_delta_without_2016": false}`.
- UP_PULLBACK attribution direction checks: `{"mean_score_change_positive": true, "net_migration_into_q4_q5_positive": false, "gross_contribution_change_positive": true}`.
- Baseline reproduction: **PASS**. Feature formula/source scan: **PASS**. Feature/baseline/candidate future-mutation prefix checks: **PASS**.
- Prediction coverage, index alignment, finite scores, and deterministic replay: **PASS**. Train firewall: **PASS**.
- Run: [`run.json`](../../artifacts/DM-20261001-01/run-20261001T052315Z/run.json); predictions, models, audits, metrics, and daily accounts are in the same artifact folder.
- Valid was not opened. The Train target used was only `target_1day_train.parquet`; raw target was not opened.

## Scope

A SUPPORT result would support only this fixed `UP_PULLBACK` column appended to SN1_H1. It would not show that Box Mean Reversion, Event Box generally, pullbacks generally, or trend following generally are effective. A REJECT applies only to this fixed feature/model addition.
