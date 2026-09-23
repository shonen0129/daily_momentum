# DM-20260908 実験ログ

事前計画: ../../experiments/DM-20260908/plan.md。全30試行を保持。20本が選択対象、10本は診断専用。
MLの判定は固定baselineと同じ開発営業日の対応比較。確認期間で候補を追加・再選択していない。

## M_res5s1_a1

Date: 2026-09-08; Decision: rejected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: Momentum; Feature Set: res5s1
Parameters: `{"family": "Momentum", "momentum": "res5s1", "alpha": 1.0}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| M_res5s1_a1 | -0.117 | -4.003 | 0.00068 | 0.5833 | 14.697% | -58.998% |

Fold Net Sharpe: 2011=-4.4053, 2012=-5.0222, 2013=-3.0061, 2014=-4.1433
理由: Momentum shape/smoothing stability rank

## M_res10s1_a1

Date: 2026-09-08; Decision: rejected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: Momentum; Feature Set: res10s1
Parameters: `{"family": "Momentum", "momentum": "res10s1", "alpha": 1.0}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| M_res10s1_a1 | 0.337 | -2.267 | 0.00321 | 0.4114 | 10.365% | -35.669% |

Fold Net Sharpe: 2011=-2.8116, 2012=-3.3176, 2013=-0.6028, 2014=-3.0390
理由: Momentum shape/smoothing stability rank

## M_res20s1_a1

Date: 2026-09-08; Decision: rejected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: Momentum; Feature Set: res20s1
Parameters: `{"family": "Momentum", "momentum": "res20s1", "alpha": 1.0}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| M_res20s1_a1 | 0.621 | -1.000 | 0.00559 | 0.2849 | 7.179% | -19.113% |

Fold Net Sharpe: 2011=-1.1651, 2012=-1.7256, 2013=0.2721, 2014=-2.3653
理由: Momentum shape/smoothing stability rank

## M_res60s1_a1

Date: 2026-09-08; Decision: rejected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: Momentum; Feature Set: res60s1
Parameters: `{"family": "Momentum", "momentum": "res60s1", "alpha": 1.0}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| M_res60s1_a1 | 0.684 | -0.150 | 0.00746 | 0.1639 | 4.129% | -12.958% |

Fold Net Sharpe: 2011=-0.2774, 2012=-0.1734, 2013=-0.2692, 2014=0.3371
理由: Momentum shape/smoothing stability rank

## M_res20s0_a1

Date: 2026-09-08; Decision: rejected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: Momentum; Feature Set: res20s0
Parameters: `{"family": "Momentum", "momentum": "res20s0", "alpha": 1.0}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| M_res20s0_a1 | 0.332 | -1.284 | 0.00286 | 0.2850 | 7.180% | -22.735% |

Fold Net Sharpe: 2011=-1.5320, 2012=-2.3501, 2013=0.1269, 2014=-2.2708
理由: Momentum shape/smoothing stability rank

## M_res20s2_a1

Date: 2026-09-08; Decision: rejected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: Momentum; Feature Set: res20s2
Parameters: `{"family": "Momentum", "momentum": "res20s2", "alpha": 1.0}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| M_res20s2_a1 | 0.677 | -0.951 | 0.00636 | 0.2849 | 7.179% | -17.991% |

Fold Net Sharpe: 2011=-1.2750, 2012=-1.2913, 2013=0.2466, 2014=-2.4656
理由: Momentum shape/smoothing stability rank

## M_raw20s1_a1

Date: 2026-09-08; Decision: rejected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: Momentum; Feature Set: raw20s1
Parameters: `{"family": "Momentum", "momentum": "raw20s1", "alpha": 1.0}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| M_raw20s1_a1 | -0.201 | -1.878 | -0.00312 | 0.2894 | 7.254% | -34.531% |

Fold Net Sharpe: 2011=-1.1598, 2012=-3.4486, 2013=-1.2797, 2014=-2.0822
理由: Momentum shape/smoothing stability rank

## M_sector20s1_a1

Date: 2026-09-08; Decision: rejected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: Momentum; Feature Set: sector20s1
Parameters: `{"family": "Momentum", "momentum": "sector20s1", "alpha": 1.0}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| M_sector20s1_a1 | 0.186 | -2.089 | 0.00134 | 0.2931 | 7.385% | -26.498% |

Fold Net Sharpe: 2011=-2.3458, 2012=-2.1591, 2013=-1.4815, 2014=-2.7398
理由: Momentum shape/smoothing stability rank

## M_equal_5_20_60_a1

Date: 2026-09-08; Decision: rejected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: Momentum; Feature Set: equal_5_20_60
Parameters: `{"family": "Momentum", "momentum": "equal_5_20_60", "alpha": 1.0}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| M_equal_5_20_60_a1 | 0.583 | -1.477 | 0.00666 | 0.3676 | 9.263% | -25.907% |

Fold Net Sharpe: 2011=-2.0747, 2012=-2.0756, 2013=-0.5073, 2014=-1.6287
理由: Momentum shape/smoothing stability rank

## M_res60s1_a0.5

Date: 2026-09-08; Decision: rejected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: Momentum; Feature Set: res60s1
Parameters: `{"family": "Momentum", "momentum": "res60s1", "alpha": 0.5}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| M_res60s1_a0.5 | 0.701 | 0.214 | 0.00765 | 0.0958 | 2.413% | -11.376% |

Fold Net Sharpe: 2011=0.1776, 2012=0.3121, 2013=-0.0063, 2014=0.6343
理由: Momentum shape/smoothing stability rank

## M_res60s1_a0.25

Date: 2026-09-08; Decision: selected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: Momentum; Feature Set: res60s1
Parameters: `{"family": "Momentum", "momentum": "res60s1", "alpha": 0.25}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| M_res60s1_a0.25 | 0.729 | 0.400 | 0.00725 | 0.0646 | 1.628% | -10.350% |

Fold Net Sharpe: 2011=0.4326, 2012=0.6463, 2013=0.0404, 2014=0.8087
理由: Train development stability and preregistered acceptance rule

## M_res60s1_a0.15

Date: 2026-09-08; Decision: rejected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: Momentum; Feature Set: res60s1
Parameters: `{"family": "Momentum", "momentum": "res60s1", "alpha": 0.15}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| M_res60s1_a0.15 | 0.616 | 0.356 | 0.00691 | 0.0509 | 1.283% | -10.836% |

Fold Net Sharpe: 2011=0.5406, 2012=0.5748, 2013=-0.0678, 2014=0.6252
理由: Momentum shape/smoothing stability rank

## SENS_alpha_0.200

Date: 2026-09-08; Decision: diagnostic only
Hypothesis: Causal momentum persistence with transaction-cost control
Model: Momentum; Feature Set: res60s1
Parameters: `{"family": "Momentum", "momentum": "res60s1", "alpha": 0.2}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| SENS_alpha_0.200 | 0.667 | 0.372 | 0.00710 | 0.0581 | 1.463% | -10.548% |

Fold Net Sharpe: 2011=0.4537, 2012=0.5925, 2013=-0.0253, 2014=0.7907
理由: Fixed sensitivity; not eligible for selection

## SENS_alpha_0.300

Date: 2026-09-08; Decision: diagnostic only
Hypothesis: Causal momentum persistence with transaction-cost control
Model: Momentum; Feature Set: res60s1
Parameters: `{"family": "Momentum", "momentum": "res60s1", "alpha": 0.3}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| SENS_alpha_0.300 | 0.700 | 0.338 | 0.00739 | 0.0713 | 1.796% | -10.566% |

Fold Net Sharpe: 2011=0.3183, 2012=0.5657, 2013=-0.0099, 2014=0.8275
理由: Fixed sensitivity; not eligible for selection

## C1_rule

Date: 2026-09-08; Decision: rejected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: C1_rule; Feature Set: res60s1, liquidity_shock_value, pwv
Parameters: `{"family": "C1_rule", "momentum": "res60s1", "alpha": 0.25, "gate_vacuum": 0.5, "pwv_threshold": 0.333}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| C1_rule | 0.708 | 0.329 | 0.00696 | 0.0748 | 1.885% | -10.754% |

Fold Net Sharpe: 2011=0.3623, 2012=0.5498, 2013=0.0129, 2014=0.6660
理由: Acceptance gate failed: improved folds=0/4; median delta=-0.083; bootstrap lower=-0.131; DSR=0.00003

## C1_ml

Date: 2026-09-08; Decision: rejected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: C1; Feature Set: liquidity_level, liquidity_shock, volume_shock, pwv, vwp, am, pm, intraday_range, volume_ratio, m_pwv, m_vwp, m_liquidity, m_volume, vwp_intraday
Parameters: `{"family": "C1", "momentum": "res60s1", "alpha": 0.25, "objective": "regression", "max_depth": 2, "num_leaves": 4, "n_estimators": 60, "min_child_samples": 500, "learning_rate": 0.05, "reg_lambda": 10.0, "random_state": 20260908, "n_jobs": 2, "verbosity": -1, "deterministic": true, "force_col_wise": true}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| C1_ml | 0.731 | 0.403 | 0.00731 | 0.0645 | 1.626% | -10.424% |

Fold Net Sharpe: 2011=0.4476, 2012=0.6736, 2013=0.0232, 2014=0.7962
理由: Acceptance gate failed: improved folds=2/4; median delta=0.001; bootstrap lower=-0.010; DSR=0.00005

## B_lambda0.25

Date: 2026-09-08; Decision: rejected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: B; Feature Set: liquidity_level, liquidity_shock, volume_shock, pwv, vwp, am, pm, intraday_range, volume_ratio, m_pwv, m_vwp, m_liquidity, m_volume, vwp_intraday
Parameters: `{"family": "B", "momentum": "res60s1", "alpha": 0.25, "lambda": 0.25, "objective": "regression", "max_depth": 2, "num_leaves": 4, "n_estimators": 60, "min_child_samples": 500, "learning_rate": 0.05, "reg_lambda": 10.0, "random_state": 20260908, "n_jobs": 2, "verbosity": -1, "deterministic": true, "force_col_wise": true}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| B_lambda0.25 | 0.838 | 0.434 | 0.00964 | 0.0800 | 2.006% | -10.087% |

Fold Net Sharpe: 2011=0.4399, 2012=0.7623, 2013=0.0971, 2014=0.7372
理由: Acceptance gate failed: improved folds=3/4; median delta=0.032; bootstrap lower=-0.062; DSR=0.00007

## B_lambda0.5

Date: 2026-09-08; Decision: rejected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: B; Feature Set: liquidity_level, liquidity_shock, volume_shock, pwv, vwp, am, pm, intraday_range, volume_ratio, m_pwv, m_vwp, m_liquidity, m_volume, vwp_intraday
Parameters: `{"family": "B", "momentum": "res60s1", "alpha": 0.25, "lambda": 0.5, "objective": "regression", "max_depth": 2, "num_leaves": 4, "n_estimators": 60, "min_child_samples": 500, "learning_rate": 0.05, "reg_lambda": 10.0, "random_state": 20260908, "n_jobs": 2, "verbosity": -1, "deterministic": true, "force_col_wise": true}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| B_lambda0.5 | 0.980 | 0.406 | 0.01188 | 0.1127 | 2.816% | -9.962% |

Fold Net Sharpe: 2011=0.4119, 2012=0.6333, 2013=0.1212, 2014=0.7483
理由: Acceptance gate failed: improved folds=1/4; median delta=-0.017; bootstrap lower=-0.151; DSR=0.00006

## B_lambda1.0

Date: 2026-09-08; Decision: rejected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: B; Feature Set: liquidity_level, liquidity_shock, volume_shock, pwv, vwp, am, pm, intraday_range, volume_ratio, m_pwv, m_vwp, m_liquidity, m_volume, vwp_intraday
Parameters: `{"family": "B", "momentum": "res60s1", "alpha": 0.25, "lambda": 1.0, "objective": "regression", "max_depth": 2, "num_leaves": 4, "n_estimators": 60, "min_child_samples": 500, "learning_rate": 0.05, "reg_lambda": 10.0, "random_state": 20260908, "n_jobs": 2, "verbosity": -1, "deterministic": true, "force_col_wise": true}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| B_lambda1.0 | 1.304 | 0.322 | 0.01543 | 0.1817 | 4.539% | -9.323% |

Fold Net Sharpe: 2011=0.0791, 2012=0.6040, 2013=0.2568, 2014=0.5171
理由: Acceptance gate failed: improved folds=1/4; median delta=-0.167; bootstrap lower=-0.389; DSR=0.00003

## C2_ml

Date: 2026-09-08; Decision: rejected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: C2; Feature Set: liquidity_level, liquidity_shock, volume_shock, pwv, vwp, am, pm, intraday_range, volume_ratio, m_pwv, m_vwp, m_liquidity, m_volume, vwp_intraday
Parameters: `{"family": "C2", "momentum": "res60s1", "alpha": 0.25, "objective": "regression", "max_depth": 2, "num_leaves": 4, "n_estimators": 60, "min_child_samples": 500, "learning_rate": 0.05, "reg_lambda": 10.0, "random_state": 20260908, "n_jobs": 2, "verbosity": -1, "deterministic": true, "force_col_wise": true}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| C2_ml | 0.437 | -1.543 | 0.00745 | 0.2537 | 6.388% | -19.973% |

Fold Net Sharpe: 2011=-1.4896, 2012=-4.4705, 2013=0.0503, 2014=-1.5384
理由: Acceptance gate failed: improved folds=1/4; median delta=-2.135; bootstrap lower=-3.673; DSR=0.00000

## A_rank

Date: 2026-09-08; Decision: rejected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: A_rank; Feature Set: liquidity_level, liquidity_shock, volume_shock, pwv, vwp, am, pm, intraday_range, volume_ratio, m_pwv, m_vwp, m_liquidity, m_volume, vwp_intraday, momentum
Parameters: `{"family": "A_rank", "momentum": "res60s1", "alpha": 0.25, "objective": "regression", "max_depth": 2, "num_leaves": 4, "n_estimators": 60, "min_child_samples": 500, "learning_rate": 0.05, "reg_lambda": 10.0, "random_state": 20260908, "n_jobs": 2, "verbosity": -1, "deterministic": true, "force_col_wise": true}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| A_rank | 0.756 | -1.496 | 0.01469 | 0.3390 | 8.482% | -22.243% |

Fold Net Sharpe: 2011=-2.0334, 2012=-1.6719, 2013=-0.5267, 2014=-1.9439
理由: Acceptance gate failed: improved folds=0/4; median delta=-2.392; bootstrap lower=-3.680; DSR=0.00000

## A_raw

Date: 2026-09-08; Decision: rejected
Hypothesis: Causal momentum persistence with transaction-cost control
Model: A_raw; Feature Set: liquidity_level, liquidity_shock, volume_shock, pwv, vwp, am, pm, intraday_range, volume_ratio, m_pwv, m_vwp, m_liquidity, m_volume, vwp_intraday, momentum
Parameters: `{"family": "A_raw", "momentum": "res60s1", "alpha": 0.25, "objective": "regression", "max_depth": 2, "num_leaves": 4, "n_estimators": 60, "min_child_samples": 500, "learning_rate": 0.05, "reg_lambda": 10.0, "random_state": 20260908, "n_jobs": 2, "verbosity": -1, "deterministic": true, "force_col_wise": true}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| A_raw | 1.101 | -0.877 | 0.00266 | 0.2869 | 7.215% | -13.943% |

Fold Net Sharpe: 2011=-1.5150, 2012=-1.8986, 2013=0.2124, 2014=-0.3567
理由: Acceptance gate failed: improved folds=1/4; median delta=-1.557; bootstrap lower=-2.997; DSR=0.00000

## SENS_B_lambda0.4

Date: 2026-09-08; Decision: diagnostic only
Hypothesis: Causal momentum persistence with transaction-cost control
Model: B; Feature Set: liquidity_level, liquidity_shock, volume_shock, pwv, vwp, am, pm, intraday_range, volume_ratio, m_pwv, m_vwp, m_liquidity, m_volume, vwp_intraday
Parameters: `{"family": "B", "momentum": "res60s1", "alpha": 0.25, "lambda": 0.4}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| SENS_B_lambda0.4 | 0.938 | 0.438 | 0.01099 | 0.0990 | 2.474% | -9.794% |

Fold Net Sharpe: 2011=0.4261, 2012=0.6564, 2013=0.1963, 2014=0.7425
理由: Fixed sensitivity; not eligible for selection

## SENS_B_lambda0.6

Date: 2026-09-08; Decision: diagnostic only
Hypothesis: Causal momentum persistence with transaction-cost control
Model: B; Feature Set: liquidity_level, liquidity_shock, volume_shock, pwv, vwp, am, pm, intraday_range, volume_ratio, m_pwv, m_vwp, m_liquidity, m_volume, vwp_intraday
Parameters: `{"family": "B", "momentum": "res60s1", "alpha": 0.25, "lambda": 0.6}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| SENS_B_lambda0.6 | 1.039 | 0.383 | 0.01270 | 0.1271 | 3.178% | -9.919% |

Fold Net Sharpe: 2011=0.3553, 2012=0.6123, 2013=0.1189, 2014=0.7322
理由: Fixed sensitivity; not eligible for selection

## SENS_C1_gate0.8

Date: 2026-09-08; Decision: diagnostic only
Hypothesis: Causal momentum persistence with transaction-cost control
Model: C1; Feature Set: liquidity_level, liquidity_shock, volume_shock, pwv, vwp, am, pm, intraday_range, volume_ratio, m_pwv, m_vwp, m_liquidity, m_volume, vwp_intraday
Parameters: `{"family": "C1", "momentum": "res60s1", "alpha": 0.25, "gate_factor": 0.8}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| SENS_C1_gate0.8 | 0.731 | 0.403 | 0.00732 | 0.0645 | 1.626% | -10.424% |

Fold Net Sharpe: 2011=0.4490, 2012=0.6736, 2013=0.0232, 2014=0.7962
理由: Fixed sensitivity; not eligible for selection

## SENS_C1_gate1.2

Date: 2026-09-08; Decision: diagnostic only
Hypothesis: Causal momentum persistence with transaction-cost control
Model: C1; Feature Set: liquidity_level, liquidity_shock, volume_shock, pwv, vwp, am, pm, intraday_range, volume_ratio, m_pwv, m_vwp, m_liquidity, m_volume, vwp_intraday
Parameters: `{"family": "C1", "momentum": "res60s1", "alpha": 0.25, "gate_factor": 1.2}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| SENS_C1_gate1.2 | 0.732 | 0.404 | 0.00731 | 0.0645 | 1.626% | -10.424% |

Fold Net Sharpe: 2011=0.4510, 2012=0.6736, 2013=0.0232, 2014=0.7962
理由: Fixed sensitivity; not eligible for selection

## SENS_C1_n_estimators48

Date: 2026-09-08; Decision: diagnostic only
Hypothesis: Causal momentum persistence with transaction-cost control
Model: C1; Feature Set: liquidity_level, liquidity_shock, volume_shock, pwv, vwp, am, pm, intraday_range, volume_ratio, m_pwv, m_vwp, m_liquidity, m_volume, vwp_intraday
Parameters: `{"family": "C1", "momentum": "res60s1", "alpha": 0.25, "n_estimators": 48}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| SENS_C1_n_estimators48 | 0.731 | 0.403 | 0.00731 | 0.0645 | 1.627% | -10.431% |

Fold Net Sharpe: 2011=0.4494, 2012=0.6683, 2013=0.0231, 2014=0.7983
理由: Fixed sensitivity; not eligible for selection

## SENS_C1_n_estimators72

Date: 2026-09-08; Decision: diagnostic only
Hypothesis: Causal momentum persistence with transaction-cost control
Model: C1; Feature Set: liquidity_level, liquidity_shock, volume_shock, pwv, vwp, am, pm, intraday_range, volume_ratio, m_pwv, m_vwp, m_liquidity, m_volume, vwp_intraday
Parameters: `{"family": "C1", "momentum": "res60s1", "alpha": 0.25, "n_estimators": 72}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| SENS_C1_n_estimators72 | 0.734 | 0.406 | 0.00732 | 0.0646 | 1.627% | -10.407% |

Fold Net Sharpe: 2011=0.4552, 2012=0.6747, 2013=0.0213, 2014=0.8027
理由: Fixed sensitivity; not eligible for selection

## SENS_C1_min_child_samples400

Date: 2026-09-08; Decision: diagnostic only
Hypothesis: Causal momentum persistence with transaction-cost control
Model: C1; Feature Set: liquidity_level, liquidity_shock, volume_shock, pwv, vwp, am, pm, intraday_range, volume_ratio, m_pwv, m_vwp, m_liquidity, m_volume, vwp_intraday
Parameters: `{"family": "C1", "momentum": "res60s1", "alpha": 0.25, "min_child_samples": 400}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| SENS_C1_min_child_samples400 | 0.736 | 0.408 | 0.00732 | 0.0645 | 1.626% | -10.424% |

Fold Net Sharpe: 2011=0.4595, 2012=0.6767, 2013=0.0257, 2014=0.7962
理由: Fixed sensitivity; not eligible for selection

## SENS_C1_min_child_samples600

Date: 2026-09-08; Decision: diagnostic only
Hypothesis: Causal momentum persistence with transaction-cost control
Model: C1; Feature Set: liquidity_level, liquidity_shock, volume_shock, pwv, vwp, am, pm, intraday_range, volume_ratio, m_pwv, m_vwp, m_liquidity, m_volume, vwp_intraday
Parameters: `{"family": "C1", "momentum": "res60s1", "alpha": 0.25, "min_child_samples": 600}`
Train: expanding 2008-11 onward, two-day boundary purge; Evaluation: 2011-01 through 2014-12
Baseline差分: see parameters and fold_incremental.csv; same official portfolio/cost/dates

| Model / 期間 | Gross SR | Net SR | RankIC | 日次turnover | 年率cost | 最大DD（加算） |
| --- | --- | --- | --- | --- | --- | --- |
| SENS_C1_min_child_samples600 | 0.732 | 0.404 | 0.00731 | 0.0645 | 1.626% | -10.434% |

Fold Net Sharpe: 2011=0.4586, 2012=0.6677, 2013=0.0203, 2014=0.7939
理由: Fixed sensitivity; not eligible for selection
