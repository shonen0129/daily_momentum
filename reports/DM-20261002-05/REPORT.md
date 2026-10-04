# DM-20261002-05 — Independent Slow Multifactor

**Decision: BASEとSECTORをともに却下。Phase3は事前gate不通過で未実施（2/3候補）。**

既知Train2011–2016では、Gross alphaと正のNet収益は両候補に存在した。だがSize/Liquidity単独controlへの安定した増分、Long/Short双方の正の寄与という採用条件を満たさない。BASEのNet SR1.810、SECTOR2.141、slow control2.094。SECTORの対control差+0.0478も、20日paired bootstrap95%区間[-0.6713,+0.7896]で0を跨ぎ、改善full-year foldは3/5のみ。年率Netはcontrol7.712%に対しBASE5.524%、SECTOR5.674%で劣る。

TurnoverはBASE0.03654、SECTOR0.03807/日（control0.01289）。年率Short netはBASE−0.842%、SECTOR−0.651%（control+0.206%）。Short grossも両候補で負のためRevision追加は許可条件を満たさない。0.03/dayは採否hard thresholdに使っていない。Sector化だけでShort問題や追加costが解消したとは扱わない。

ブロック単独の記述診断ではSize/Liquidity Gross SR2.179、Quality1.558、Value−0.513。ValueはRankIC−0.00561、Q単調性−0.9、Short gross年率−4.591%。これは事前定義したValueブロックの弱さを示すが、結果を見た符号反転・除外・再重み付けは行わない。低速ファクター一般の無効性の証明でも、controlの実運用採用根拠でもない。

Run: `artifacts/DM-20261002-05/run-20261002T045605Z`. Date: 2026-10-02 JST. Train-only; all Train previously studied. No untouched OOS claim. No Valid data, sample learned model, Freeze or external submission.

## Fixed specification

Seven raw factors: −log(raw Close × PIT shares), Amihud60/min40, CFO/Assets, Profit/Equity, Equity/Assets, Equity/shares/Close and forecast EPS/Close. Raw features daily1/99 winsorized, median then0 imputed, sample-standardized. Fixed equal within-block averages, globally standardized blocks, sum three equal blocks. Sector version uses PIT groups with minimum20 finite observations for Quality/Value feature transforms, global fallback. Revision, if eligible, is the latest-minus-previous disclosed finite forecast EPS / raw Close, equal fourth block. No Momentum in candidates, no smoothing or fitted weights.

## Overall comparison

| strategy | rankic | rankic_t_hac5 | gross_sharpe | net_sharpe | annual_gross | annual_net | turnover | annual_cost | annual_long_net | annual_short_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SLOW_CONTROL | 0.008257 | 2.802064 | 2.179334 | 2.093538 | 0.080272 | 0.077119 | 0.012888 | 0.003153 | 0.075064 | 0.002055 |
| SLOW_MF_BASE | 0.010706 | 4.073946 | 2.107988 | 1.810082 | 0.064356 | 0.055244 | 0.036542 | 0.009112 | 0.063660 | -0.008416 |
| MOM60 | 0.007590 | 1.567643 | 0.613360 | 0.308092 | 0.032108 | 0.016128 | 0.063418 | 0.015981 | 0.046391 | -0.030263 |
| SLOW_MF_SECTOR | 0.011152 | 4.898716 | 2.499074 | 2.141358 | 0.066241 | 0.056739 | 0.038069 | 0.009502 | 0.063245 | -0.006506 |

All P/L/cost/turnover values are decimal fractions. Annual P/L = daily arithmetic mean ×252. Sharpe uses sample daily SD ×√252; RankIC t-stat uses Newey–West/Bartlett lag5. Maximum drawdown uses compounded net wealth. Q1 lowest score/Q5 highest. Official five-quintile weights include Q2/Q4 as well as extreme groups; side P/L is signed residual attribution, not raw market/security return.

## Fold stability

| strategy | scope | gross_sharpe | net_sharpe | annual_gross | annual_net | turnover | annual_long_net | annual_short_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SLOW_CONTROL | 2011 | 2.800507 | 2.728793 | 0.125949 | 0.122760 | 0.013703 | 0.120853 | 0.001907 |
| SLOW_CONTROL | 2012 | 1.131319 | 1.033654 | 0.037084 | 0.033888 | 0.013052 | 0.027510 | 0.006378 |
| SLOW_CONTROL | 2013 | 1.978738 | 1.896830 | 0.084835 | 0.081311 | 0.014252 | 0.063015 | 0.018295 |
| SLOW_CONTROL | 2014 | 1.759505 | 1.664345 | 0.054300 | 0.051361 | 0.011729 | 0.064063 | -0.012702 |
| SLOW_CONTROL | 2015 | 3.366107 | 3.267066 | 0.099873 | 0.096957 | 0.011756 | 0.095971 | 0.000986 |
| SLOW_CONTROL | 2016 | 2.086547 | 2.003895 | 0.079565 | 0.076413 | 0.012628 | 0.093747 | -0.017334 |
| SLOW_MF_BASE | 2011 | 4.056466 | 3.717511 | 0.118518 | 0.108603 | 0.039912 | 0.116303 | -0.007700 |
| SLOW_MF_BASE | 2012 | 0.631181 | 0.313747 | 0.018224 | 0.009067 | 0.036546 | 0.012071 | -0.003004 |
| SLOW_MF_BASE | 2013 | 2.376777 | 2.127850 | 0.091168 | 0.081566 | 0.038453 | 0.066707 | 0.014859 |
| SLOW_MF_BASE | 2014 | 2.281856 | 1.921205 | 0.052302 | 0.044047 | 0.033192 | 0.051184 | -0.007137 |
| SLOW_MF_BASE | 2015 | 2.139252 | 1.848995 | 0.063374 | 0.054684 | 0.034857 | 0.076029 | -0.021344 |
| SLOW_MF_BASE | 2016 | -0.649308 | -0.894079 | -0.023332 | -0.032170 | 0.035430 | 0.049826 | -0.081996 |
| MOM60 | 2011 | 0.789398 | 0.506792 | 0.046155 | 0.029635 | 0.065571 | 0.075618 | -0.045983 |
| MOM60 | 2012 | 1.026104 | 0.636144 | 0.043206 | 0.026788 | 0.065148 | 0.013081 | 0.013708 |
| MOM60 | 2013 | 0.340451 | 0.081809 | 0.021016 | 0.005051 | 0.063355 | 0.038139 | -0.033088 |
| MOM60 | 2014 | 1.414193 | 0.910504 | 0.042759 | 0.027522 | 0.060468 | 0.050474 | -0.022952 |
| MOM60 | 2015 | 0.170703 | -0.099053 | 0.009896 | -0.005742 | 0.062057 | 0.045884 | -0.051626 |
| MOM60 | 2016 | 0.305757 | 0.067276 | 0.021093 | 0.004639 | 0.065295 | 0.084217 | -0.079579 |
| SLOW_MF_SECTOR | 2011 | 4.005138 | 3.632198 | 0.112875 | 0.102278 | 0.042725 | 0.110240 | -0.007962 |
| SLOW_MF_SECTOR | 2012 | 0.556540 | 0.188170 | 0.014149 | 0.004785 | 0.037360 | 0.006233 | -0.001449 |
| SLOW_MF_SECTOR | 2013 | 2.769567 | 2.455176 | 0.088468 | 0.078441 | 0.040116 | 0.064849 | 0.013592 |
| SLOW_MF_SECTOR | 2014 | 2.215577 | 1.842531 | 0.048796 | 0.040589 | 0.032710 | 0.049814 | -0.009226 |
| SLOW_MF_SECTOR | 2015 | 3.442440 | 3.049320 | 0.080002 | 0.070718 | 0.037304 | 0.084180 | -0.013462 |
| SLOW_MF_SECTOR | 2016 | 0.540943 | 0.192117 | 0.014938 | 0.005316 | 0.038543 | 0.070002 | -0.064686 |

2016 is partial. Each fold's last2 exchange dates are excluded so target t+2 remains inside the fold. Features expand from2008, no parameter fitting. Weights and costs retain continuous full-history holdings, including omitted boundary dates; no annual relaunch charge. Pooled scores concern the concatenated eligible signal dates; DD spans their sequence, so also inspect saved continuous daily accounts.

## Pre-registered phase gates and decision

```json
{
  "phase2": {
    "passed": true,
    "checks": {
      "pooled_gross_positive": true,
      "ex2016_gross_positive": true,
      "positive_full_year_gross": true,
      "turnover_feasible": true
    },
    "full_year_positive_count": 5
  },
  "phase3_sources": {
    "SLOW_MF_BASE": {
      "passed": false,
      "checks": {
        "pooled_gross_positive": true,
        "ex2016_gross_positive": true,
        "positive_full_year_gross": true,
        "long_gross_positive": true,
        "short_gross_positive": false
      },
      "full_year_positive_count": 5
    },
    "SLOW_MF_SECTOR": {
      "passed": false,
      "checks": {
        "pooled_gross_positive": true,
        "ex2016_gross_positive": true,
        "positive_full_year_gross": true,
        "long_gross_positive": true,
        "short_gross_positive": false
      },
      "full_year_positive_count": 5
    }
  },
  "phase3_parent": null
}
```

```json
{
  "SLOW_MF_BASE": {
    "decision": "REJECT",
    "checks": {
      "pooled_net_positive": true,
      "ex2016_net_positive": true,
      "net_positive_4of5_full_years": true,
      "both_sides_net_positive": false,
      "rankic_positive": true,
      "monotonicity_positive": true,
      "pooled_netSR_beats_MOM60": true,
      "netSR_beats_MOM60_4of5": true,
      "bootstrap_lower_positive_MOM60": true,
      "pooled_netSR_beats_SLOW_CONTROL": false,
      "netSR_beats_SLOW_CONTROL_4of5": false,
      "bootstrap_lower_positive_SLOW_CONTROL": false
    },
    "failed_checks": [
      "both_sides_net_positive",
      "pooled_netSR_beats_SLOW_CONTROL",
      "netSR_beats_SLOW_CONTROL_4of5",
      "bootstrap_lower_positive_SLOW_CONTROL"
    ]
  },
  "SLOW_MF_SECTOR": {
    "decision": "REJECT",
    "checks": {
      "pooled_net_positive": true,
      "ex2016_net_positive": true,
      "net_positive_4of5_full_years": true,
      "both_sides_net_positive": false,
      "rankic_positive": true,
      "monotonicity_positive": true,
      "pooled_netSR_beats_MOM60": true,
      "netSR_beats_MOM60_4of5": true,
      "bootstrap_lower_positive_MOM60": true,
      "pooled_netSR_beats_SLOW_CONTROL": true,
      "netSR_beats_SLOW_CONTROL_4of5": false,
      "bootstrap_lower_positive_SLOW_CONTROL": false
    },
    "failed_checks": [
      "both_sides_net_positive",
      "netSR_beats_SLOW_CONTROL_4of5",
      "bootstrap_lower_positive_SLOW_CONTROL"
    ]
  }
}
```

Actual candidate trials: 2/3: SLOW_MF_BASE, SLOW_MF_SECTOR. Gates and adoption tests are exactly the pre-result plan. Unrun phases have no performance result. No post-result definition, weighting, smoothing or threshold changes.

## Paired20-day bootstrap

```json
{
  "SLOW_MF_BASE": {
    "MOM60": {
      "low": 0.2705732446113895,
      "high": 2.7173579129960523,
      "bootstrap_positive_fraction": 0.994,
      "reps": 2000,
      "block": 20,
      "seed": 20261002
    },
    "SLOW_CONTROL": {
      "low": -1.0236994513523494,
      "high": 0.4727025608983575,
      "bootstrap_positive_fraction": 0.2415,
      "reps": 2000,
      "block": 20,
      "seed": 20261002
    }
  },
  "SLOW_MF_SECTOR": {
    "MOM60": {
      "low": 0.6212324806824991,
      "high": 3.03885755199927,
      "bootstrap_positive_fraction": 1.0,
      "reps": 2000,
      "block": 20,
      "seed": 20261002
    },
    "SLOW_CONTROL": {
      "low": -0.6712721855315755,
      "high": 0.7896247156921371,
      "bootstrap_positive_fraction": 0.587,
      "reps": 2000,
      "block": 20,
      "seed": 20261002
    }
  }
}
```

Paired circular moving-block draws resample the same dates for candidate/control,2000 draws, seed20261002,95% percentile interval for ΔNet Sharpe. Intervals measure known-Train sampling variation, not independent OOS assurance or multiple-testing correction.

## Causality, accounting and limitations

Source scan, runtime Train firewall, exact index/finite coverage (809,636 rows), deterministic rebuild, row shuffle, research/adapter parity, official full-panel weight/net reconciliation and2-session purge passed. Future mutation and truncation passed 36 full-matrix/score cases across3 cutoffs; exact float64 bit patterns include NaN positions. All four feature sources individually and jointly are tested. There are no fitted labels. Scope and cases are in audit/prefix_invariance.json.

Financial Date has no intraday disclosure clock; it is treated conservatively as available by23:59:59 JST on that date, with prediction at that same end-of-day time before next open. Per-field backward carry can combine different report vintages. Profit is reported cumulative-period profit, not annualized; financial sectors/accounting bases differ. Raw Close paired with last disclosed shares/EPS can temporarily be economically inconsistent after a split until fresh disclosure. No future share update or retrospective level adjustment repairs that issue. This limits interpretation and deployment readiness; it does not justify result-driven correction.

Missing targets remain in portfolio/ranking coverage. The official scorer drops cost on a missing-target row; conservative net_all_cost and annual_cost_all charge every position. Long/Short costs are absolute changes in positive/negative holdings and reconcile within1e−15. Annual metrics2008–2010 are descriptive warm-up history, excluded from gates. No real later-split adapter/zip validation was done because no release/Valid evaluation is authorized.

Detailed artifacts: metrics/metrics.csv (all required pooled/fold/year IC, HAC, hit, Sharpe, annual P/L/cost, turnover, DD, Q1–Q5 and both sides), incremental.csv (both controls), daily_*.csv (continuous accounts), bootstrap.json, block_conditional_quintiles.csv, raw_feature_missing_by_year.csv, block_correlations.csv, audit/*; immutable plan/config/code/environment/input hashes in the run.

## Execution completion

Finalization run `artifacts/DM-20261002-05/run-20261002T050345Z` completed from hash-verified saved scientific artifacts in `artifacts/DM-20261002-05/run-20261002T045605Z`. The scientific run had already saved all results, gates, decisions and audits before its final bookkeeping read was denied by the Train firewall. The driver now explicitly allowlists only its own prediction artifacts for hash reads. No target guard was relaxed, no model/feature definition changed and no performance trial was rerun. The earlier quantile runtime failure and this bookkeeping failure remain preserved. Full-Train BASE/SECTOR feature matrices and BASE/revision scores were bitwise equal before/after vectorization; sector build117.14→2.70seconds. Final regression tests:187passed; make check remains blocked by pre-existing DM-20261002-04 metadata kind, while independent129Freeze hashes pass.

Independent no-argument top-level Train smoke:809,636/809,636 finite predictions, research parity bitwise PASS,2.316seconds, peak RSS1,113,227,264bytes (~1.04GiB). See audit/standalone_smoke.json. Finalization checked32copied scientific artifacts by SHA-256; added human-readable metric views do not change results. Research-wide peak RSS was not captured because the scientific run failed at the final hash step; no later-split/zip resource guarantee is claimed.
