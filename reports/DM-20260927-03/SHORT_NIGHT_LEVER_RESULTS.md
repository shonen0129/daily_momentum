# Short × Night intervention results

- Experiment: `DM-20260927-03`; Train-only descriptive analysis, not OOS evidence.
- Fixed plan: [SHORT_NIGHT_INTERVENTION_PLAN.md](SHORT_NIGHT_INTERVENTION_PLAN.md), frozen 2026-09-26 19:05:06 UTC; SHA-256 `84c3a051556e2ee02a8744e521ed22f1c600c357c4b9caccc6cb4414111ca621`.
- Evaluated exactly two registered transformations: `SIDE_SOURCE_SEPARATION` and `HIGH_AGE5_SHORT_VETO`. No post-result candidate or parameter trials.
- Evaluation: 2011-01-04–2016-03-29; 2016 partial 2016-01-04–2016-03-29; ex-2016 through 2015; two-date annual purge; official five-quintile weights; 10 bps one-way cost; 252 days/year.
- Primary baseline: `D_LOW_FAST_ONLY`; context baseline: `BOX_ORIGINAL`; B00 stayed diagnostic-only and was not promoted or re-evaluated as a candidate.

## Overall and ex-2016

| Strategy           | Period          | Gross ann. | Net ann. | Gross SR | Net SR | Gross vol. | Net vol. | Turnover/day | Cost ann. | Max DD   | RankIC | RankIC HAC5 t | RankIC hit |
| ------------------ | --------------- | ---------- | -------- | -------- | ------ | ---------- | -------- | ------------ | --------- | -------- | ------ | ------------- | ---------- |
| BOX_ORIGINAL | full_train_eval | 4.448% | 3.649% | 0.958 | 0.785 | 4.643% | 4.648% | 0.032 | 0.799% | -6.225% | 0.011 | 2.620 | 54.039% |
| BOX_ORIGINAL | ex_2016 | 3.819% | 3.009% | 0.858 | 0.675 | 4.453% | 4.457% | 0.032 | 0.810% | -6.225% | 0.010 | 2.347 | 53.865% |
| D_LOW_FAST_ONLY | full_train_eval | 4.532% | 3.716% | 0.987 | 0.808 | 4.593% | 4.598% | 0.033 | 0.816% | -6.149% | 0.011 | 2.730 | 54.275% |
| D_LOW_FAST_ONLY | ex_2016 | 3.923% | 3.098% | 0.889 | 0.701 | 4.413% | 4.418% | 0.033 | 0.825% | -6.149% | 0.010 | 2.470 | 54.112% |
| SN1 side-separated | full_train_eval | 4.708% | 4.517% | 1.108 | 1.063 | 4.248% | 4.248% | 0.008 | 0.191% | -6.271% | 0.012 | 3.106 | 54.510% |
| SN1 side-separated | ex_2016 | 4.224% | 4.057% | 1.051 | 1.009 | 4.021% | 4.021% | 0.007 | 0.167% | -6.271% | 0.011 | 2.853 | 54.276% |
| SN2 High-age veto | full_train_eval | 3.526% | 1.342% | 0.842 | 0.320 | 4.190% | 4.191% | 0.087 | 2.185% | -10.628% | 0.010 | 2.658 | 53.804% |
| SN2 High-age veto | ex_2016 | 2.885% | 0.641% | 0.724 | 0.160 | 3.986% | 3.986% | 0.089 | 2.244% | -10.628% | 0.009 | 2.388 | 53.618% |

The baseline D values reproduce the supplied report (Net SR 0.808 pooled, 0.701 ex-2016). SN1 raises pooled Net SR to 1.063 and ex-2016 to 1.009, but that gain does not come from Short × Night. SN2 lowers Net SR to 0.320 pooled and 0.160 ex-2016.

Full-pool paired change against each required baseline:

| Candidate | Baseline | ΔNet annual | ΔNet SR | ΔTurnover/day | ΔRankIC |
|---|---|---:|---:|---:|---:|
| SN1 side-separated | D_LOW_FAST_ONLY | +0.801% | +0.255 | -0.02486 | +0.00115 |
| SN1 side-separated | BOX_ORIGINAL | +0.869% | +0.278 | -0.02420 | +0.00143 |
| SN2 High-age veto | D_LOW_FAST_ONLY | -2.374% | -0.489 | +0.05432 | -0.00107 |
| SN2 High-age veto | BOX_ORIGINAL | -2.307% | -0.466 | +0.05498 | -0.00079 |

## Long/Short attribution and dependence

Full-period side portfolio results:

| Strategy           | Side  | Gross ann. | Net ann. | Net vol. | Net SR |
| ------------------ | ----- | ---------- | -------- | -------- | ------ |
| BOX_ORIGINAL       | long  | 5.867%     | 5.297%   | 5.234%   | 1.012  |
| BOX_ORIGINAL       | short | -1.419%    | -1.649%  | 4.947%   | -0.333 |
| D_LOW_FAST_ONLY    | long  | 5.880%     | 5.307%   | 5.220%   | 1.017  |
| D_LOW_FAST_ONLY    | short | -1.348%    | -1.591%  | 4.915%   | -0.324 |
| SN1 side-separated | long  | 6.230%     | 6.161%   | 4.917%   | 1.253  |
| SN1 side-separated | short | -1.522%    | -1.644%  | 5.056%   | -0.325 |
| SN2 High-age veto  | long  | 5.387%     | 4.211%   | 5.050%   | 0.834  |
| SN2 High-age veto  | short | -1.861%    | -2.869%  | 4.938%   | -0.581 |

L/S net-return correlation is BOX `-0.584`, D `-0.590`, SN1 `-0.637`, SN2 `-0.647`. D's Short book remains net-negative overall (`-1.591%` annual Net), while Long is `+5.307%`.

## Four diagnostic Day/Night cells

These are return decompositions of the unchanged O2O portfolio and cost convention; no session-specific trade was introduced.

| Strategy           | Period          | Side  | Session | Gross ann. | Cost ann. | Net ann. | Net vol. | Net SR |
| ------------------ | --------------- | ----- | ------- | ---------- | --------- | -------- | -------- | ------ |
| BOX_ORIGINAL       | full_train_eval | long  | day     | -0.662%    | 0.285%    | -0.947%  | 5.190%   | -0.182 |
| BOX_ORIGINAL       | full_train_eval | long  | night   | 6.529%     | 0.285%    | 6.244%   | 6.376%   | 0.979  |
| BOX_ORIGINAL       | full_train_eval | short | day     | 4.040%     | 0.115%    | 3.925%   | 5.096%   | 0.770  |
| BOX_ORIGINAL       | full_train_eval | short | night   | -5.459%    | 0.115%    | -5.574%  | 6.317%   | -0.882 |
| BOX_ORIGINAL       | ex_2016         | long  | day     | -1.295%    | 0.295%    | -1.590%  | 5.075%   | -0.313 |
| BOX_ORIGINAL       | ex_2016         | long  | night   | 6.638%     | 0.295%    | 6.343%   | 6.089%   | 1.042  |
| BOX_ORIGINAL       | ex_2016         | short | day     | 4.065%     | 0.110%    | 3.955%   | 4.947%   | 0.799  |
| BOX_ORIGINAL       | ex_2016         | short | night   | -5.590%    | 0.110%    | -5.700%  | 5.854%   | -0.974 |
| D_LOW_FAST_ONLY    | full_train_eval | long  | day     | -0.681%    | 0.286%    | -0.967%  | 5.185%   | -0.187 |
| D_LOW_FAST_ONLY    | full_train_eval | long  | night   | 6.561%     | 0.286%    | 6.275%   | 6.362%   | 0.986  |
| D_LOW_FAST_ONLY    | full_train_eval | short | day     | 4.014%     | 0.121%    | 3.892%   | 5.077%   | 0.767  |
| D_LOW_FAST_ONLY    | full_train_eval | short | night   | -5.362%    | 0.121%    | -5.483%  | 6.290%   | -0.872 |
| D_LOW_FAST_ONLY    | ex_2016         | long  | day     | -1.324%    | 0.297%    | -1.621%  | 5.069%   | -0.320 |
| D_LOW_FAST_ONLY    | ex_2016         | long  | night   | 6.664%     | 0.297%    | 6.367%   | 6.074%   | 1.048  |
| D_LOW_FAST_ONLY    | ex_2016         | short | day     | 4.075%     | 0.115%    | 3.959%   | 4.939%   | 0.802  |
| D_LOW_FAST_ONLY    | ex_2016         | short | night   | -5.492%    | 0.115%    | -5.608%  | 5.835%   | -0.961 |
| SN1 side-separated | full_train_eval | long  | day     | -0.011%    | 0.034%    | -0.045%  | 4.873%   | -0.009 |
| SN1 side-separated | full_train_eval | long  | night   | 6.241%     | 0.034%    | 6.206%   | 5.928%   | 1.047  |
| SN1 side-separated | full_train_eval | short | day     | 4.418%     | 0.061%    | 4.357%   | 5.223%   | 0.834  |
| SN1 side-separated | full_train_eval | short | night   | -5.940%    | 0.061%    | -6.001%  | 6.678%   | -0.899 |
| SN1 side-separated | ex_2016         | long  | day     | -0.518%    | 0.032%    | -0.549%  | 4.748%   | -0.116 |
| SN1 side-separated | ex_2016         | long  | night   | 6.329%     | 0.032%    | 6.297%   | 5.620%   | 1.121  |
| SN1 side-separated | ex_2016         | short | day     | 4.515%     | 0.052%    | 4.463%   | 5.084%   | 0.878  |
| SN1 side-separated | ex_2016         | short | night   | -6.103%    | 0.052%    | -6.154%  | 6.254%   | -0.984 |
| SN2 High-age veto  | full_train_eval | long  | day     | -1.749%    | 0.588%    | -2.337%  | 5.035%   | -0.464 |
| SN2 High-age veto  | full_train_eval | long  | night   | 7.136%     | 0.588%    | 6.548%   | 6.300%   | 1.039  |
| SN2 High-age veto  | full_train_eval | short | day     | 3.188%     | 0.504%    | 2.684%   | 5.093%   | 0.527  |
| SN2 High-age veto  | full_train_eval | short | night   | -5.049%    | 0.504%    | -5.553%  | 6.357%   | -0.873 |
| SN2 High-age veto  | ex_2016         | long  | day     | -2.432%    | 0.607%    | -3.039%  | 4.917%   | -0.618 |
| SN2 High-age veto  | ex_2016         | long  | night   | 7.271%     | 0.607%    | 6.663%   | 5.995%   | 1.111  |
| SN2 High-age veto  | ex_2016         | short | day     | 3.203%     | 0.515%    | 2.689%   | 4.958%   | 0.542  |
| SN2 High-age veto  | ex_2016         | short | night   | -5.158%    | 0.515%    | -5.672%  | 5.913%   | -0.959 |

D Short × Night is `-5.483%` annual Net / `-0.872` SR; Short × Day is `+3.892%` / `+0.767`. SN1 makes Short × Night **0.517pp worse** while Short × Day improves `0.465pp`. SN2 makes Short × Night `0.070pp worse` and Short × Day `1.208pp worse`.

## Annual stability

Annual portfolio and prediction diagnostics for each required year, ex-2016 and full pooled. The 2016 row is the specified partial period.

| Period          | Strategy           | Gross ann. | Net ann. | Gross SR | Net SR | Gross vol. | Net vol. | Turnover/day | Cost ann. | Max DD   | RankIC | RankIC HAC5 t | RankIC hit | Q1–Q5 mono. |
| --------------- | ------------------ | ---------- | -------- | -------- | ------ | ---------- | -------- | ------------ | --------- | -------- | ------ | ------------- | ---------- | ----------- |
| full_train_eval | BOX_ORIGINAL       | 4.448%     | 3.649%   | 0.958    | 0.785  | 4.643%     | 4.648%   | 0.0319       | 0.799%    | -6.225%  | 0.0110 | 2.620         | 54.04%     | 0.90        |
| ex_2016         | BOX_ORIGINAL       | 3.819%     | 3.009%   | 0.858    | 0.675  | 4.453%     | 4.457%   | 0.0323       | 0.810%    | -6.225%  | 0.0098 | 2.347         | 53.87%     | 0.80        |
| 2011            | BOX_ORIGINAL       | 0.262%     | -0.158%  | 0.057    | -0.034 | 4.627%     | 4.623%   | 0.0168       | 0.420%    | -5.424%  | 0.0011 | 0.109         | 52.67%     | 0.20        |
| 2012            | BOX_ORIGINAL       | 6.514%     | 6.119%   | 1.346    | 1.263  | 4.842%     | 4.843%   | 0.0157       | 0.395%    | -3.258%  | 0.0191 | 1.752         | 54.47%     | 0.90        |
| 2013            | BOX_ORIGINAL       | 6.379%     | 4.894%   | 1.303    | 0.997  | 4.896%     | 4.912%   | 0.0591       | 1.485%    | -6.168%  | 0.0128 | 1.729         | 54.73%     | 0.60        |
| 2014            | BOX_ORIGINAL       | 4.802%     | 4.161%   | 1.757    | 1.521  | 2.733%     | 2.736%   | 0.0256       | 0.641%    | -1.706%  | 0.0112 | 1.748         | 52.89%     | 0.70        |
| 2015            | BOX_ORIGINAL       | 1.094%     | -0.021%  | 0.228    | -0.004 | 4.791%     | 4.796%   | 0.0444       | 1.114%    | -5.736%  | 0.0045 | 0.418         | 54.55%     | 0.50        |
| 2016            | BOX_ORIGINAL       | 17.420%    | 16.841%  | 2.299    | 2.220  | 7.578%     | 7.585%   | 0.0232       | 0.579%    | -3.946%  | 0.0374 | 1.244         | 57.63%     | 0.90        |
| full_train_eval | D_LOW_FAST_ONLY    | 4.532%     | 3.716%   | 0.987    | 0.808  | 4.593%     | 4.598%   | 0.0325       | 0.816%    | -6.149%  | 0.0113 | 2.730         | 54.27%     | 0.80        |
| ex_2016         | D_LOW_FAST_ONLY    | 3.923%     | 3.098%   | 0.889    | 0.701  | 4.413%     | 4.418%   | 0.0329       | 0.825%    | -6.149%  | 0.0101 | 2.470         | 54.11%     | 0.80        |
| 2011            | D_LOW_FAST_ONLY    | 0.475%     | 0.039%   | 0.104    | 0.008  | 4.585%     | 4.582%   | 0.0174       | 0.436%    | -4.858%  | 0.0020 | 0.207         | 53.09%     | 0.20        |
| 2012            | D_LOW_FAST_ONLY    | 6.818%     | 6.392%   | 1.435    | 1.344  | 4.753%     | 4.754%   | 0.0170       | 0.427%    | -3.236%  | 0.0196 | 1.866         | 55.69%     | 0.90        |
| 2013            | D_LOW_FAST_ONLY    | 6.505%     | 5.017%   | 1.332    | 1.025  | 4.882%     | 4.897%   | 0.0593       | 1.488%    | -6.149%  | 0.0133 | 1.777         | 55.56%     | 0.70        |
| 2014            | D_LOW_FAST_ONLY    | 4.662%     | 4.007%   | 1.710    | 1.468  | 2.727%     | 2.730%   | 0.0261       | 0.655%    | -1.746%  | 0.0108 | 1.689         | 51.65%     | 0.90        |
| 2015            | D_LOW_FAST_ONLY    | 1.109%     | -0.017%  | 0.233    | -0.003 | 4.756%     | 4.760%   | 0.0448       | 1.125%    | -5.724%  | 0.0047 | 0.445         | 54.55%     | 0.50        |
| 2016            | D_LOW_FAST_ONLY    | 17.089%    | 16.463%  | 2.310    | 2.223  | 7.398%     | 7.406%   | 0.0252       | 0.626%    | -3.635%  | 0.0360 | 1.223         | 57.63%     | 1.00        |
| full_train_eval | SN1 side-separated | 4.708%     | 4.517%   | 1.108    | 1.063  | 4.248%     | 4.248%   | 0.0077       | 0.191%    | -6.271%  | 0.0125 | 3.106         | 54.51%     | 0.90        |
| ex_2016         | SN1 side-separated | 4.224%     | 4.057%   | 1.051    | 1.009  | 4.021%     | 4.021%   | 0.0067       | 0.167%    | -6.271%  | 0.0113 | 2.853         | 54.28%     | 0.90        |
| 2011            | SN1 side-separated | 0.432%     | 0.033%   | 0.098    | 0.007  | 4.425%     | 4.423%   | 0.0159       | 0.399%    | -4.789%  | 0.0010 | 0.112         | 53.09%     | 0.30        |
| 2012            | SN1 side-separated | 5.050%     | 4.816%   | 1.135    | 1.082  | 4.449%     | 4.450%   | 0.0093       | 0.234%    | -2.770%  | 0.0155 | 1.568         | 53.25%     | 0.90        |
| 2013            | SN1 side-separated | 7.745%     | 7.729%   | 1.674    | 1.670  | 4.628%     | 4.628%   | 0.0007       | 0.016%    | -4.366%  | 0.0166 | 2.023         | 51.44%     | 0.90        |
| 2014            | SN1 side-separated | 4.132%     | 4.032%   | 1.999    | 1.954  | 2.067%     | 2.064%   | 0.0041       | 0.100%    | -1.352%  | 0.0117 | 2.090         | 57.44%     | 0.90        |
| 2015            | SN1 side-separated | 3.750%     | 3.664%   | 0.942    | 0.920  | 3.980%     | 3.981%   | 0.0035       | 0.086%    | -3.424%  | 0.0114 | 1.128         | 56.20%     | 0.30        |
| 2016            | SN1 side-separated | 14.685%    | 14.004%  | 1.942    | 1.850  | 7.561%     | 7.570%   | 0.0270       | 0.680%    | -3.925%  | 0.0372 | 1.273         | 59.32%     | 0.90        |
| full_train_eval | SN2 High-age veto  | 3.526%     | 1.342%   | 0.842    | 0.320  | 4.190%     | 4.199%   | 0.0868       | 2.185%    | -10.628% | 0.0102 | 2.658         | 53.80%     | 0.90        |
| ex_2016         | SN2 High-age veto  | 2.885%     | 0.641%   | 0.724    | 0.160  | 3.986%     | 3.994%   | 0.0892       | 2.244%    | -10.628% | 0.0090 | 2.388         | 53.62%     | 0.90        |
| 2011            | SN2 High-age veto  | 0.733%     | 0.159%   | 0.159    | 0.034  | 4.620%     | 4.617%   | 0.0229       | 0.575%    | -4.641%  | 0.0030 | 0.337         | 53.91%     | 0.30        |
| 2012            | SN2 High-age veto  | 6.803%     | 5.820%   | 1.482    | 1.267  | 4.591%     | 4.592%   | 0.0391       | 0.984%    | -3.153%  | 0.0209 | 2.062         | 56.50%     | 0.80        |
| 2013            | SN2 High-age veto  | 5.102%     | 1.345%   | 1.267    | 0.332  | 4.027%     | 4.055%   | 0.1493       | 3.757%    | -7.094%  | 0.0152 | 2.120         | 53.09%     | 0.90        |
| 2014            | SN2 High-age veto  | 1.876%     | -0.663%  | 0.781    | -0.276 | 2.403%     | 2.406%   | 0.1009       | 2.539%    | -2.375%  | 0.0028 | 0.452         | 51.24%     | 0.40        |
| 2015            | SN2 High-age veto  | -0.155%    | -3.543%  | -0.040   | -0.912 | 3.879%     | 3.885%   | 0.1346       | 3.388%    | -6.036%  | 0.0029 | 0.338         | 53.31%     | 0.10        |
| 2016            | SN2 High-age veto  | 16.749%    | 15.791%  | 2.319    | 2.186  | 7.223%     | 7.225%   | 0.0384       | 0.958%    | -3.728%  | 0.0353 | 1.222         | 57.63%     | 1.00        |

Quintile returns are average daily cross-sectional residual returns before portfolio costs (basis points/day); Q1–Q5 monotonicity is listed in the annual diagnostics above.

| Period          | Strategy           | Q1 (bp/day) | Q2 (bp/day) | Q3 (bp/day) | Q4 (bp/day) | Q5 (bp/day) |
| --------------- | ------------------ | ----------- | ----------- | ----------- | ----------- | ----------- |
| full_train_eval | BOX_ORIGINAL       | 1.11        | 1.25        | 3.02        | 2.97        | 5.49        |
| ex_2016         | BOX_ORIGINAL       | 1.30        | 1.13        | 3.05        | 2.64        | 5.03        |
| 2011            | BOX_ORIGINAL       | 4.87        | 4.09        | 4.16        | 4.95        | 4.78        |
| 2012            | BOX_ORIGINAL       | -1.70       | -2.06       | -1.10       | 0.80        | 4.59        |
| 2013            | BOX_ORIGINAL       | -0.84       | -1.17       | 5.47        | 1.91        | 5.13        |
| 2014            | BOX_ORIGINAL       | 0.25        | 2.65        | 2.31        | 2.40        | 6.02        |
| 2015            | BOX_ORIGINAL       | 3.95        | 2.18        | 4.48        | 3.17        | 4.65        |
| 2016            | BOX_ORIGINAL       | -2.68       | 3.73        | 2.25        | 9.66        | 14.92       |
| full_train_eval | D_LOW_FAST_ONLY    | 1.18        | 0.93        | 3.25        | 2.95        | 5.51        |
| ex_2016         | D_LOW_FAST_ONLY    | 1.27        | 0.91        | 3.33        | 2.58        | 5.05        |
| 2011            | D_LOW_FAST_ONLY    | 4.95        | 3.63        | 4.45        | 4.97        | 4.86        |
| 2012            | D_LOW_FAST_ONLY    | -1.94       | -2.60       | 0.07        | 0.43        | 4.61        |
| 2013            | D_LOW_FAST_ONLY    | -1.07       | -1.07       | 5.54        | 1.91        | 5.13        |
| 2014            | D_LOW_FAST_ONLY    | 0.56        | 2.41        | 2.14        | 2.47        | 6.02        |
| 2015            | D_LOW_FAST_ONLY    | 3.91        | 2.22        | 4.47        | 3.17        | 4.65        |
| 2016            | D_LOW_FAST_ONLY    | -0.78       | 1.31        | 1.72        | 10.49       | 14.92       |
| full_train_eval | SN1 side-separated | 1.22        | 1.16        | 2.51        | 3.04        | 5.95        |
| ex_2016         | SN1 side-separated | 1.37        | 1.03        | 2.34        | 2.97        | 5.49        |
| 2011            | SN1 side-separated | 4.81        | 3.81        | 5.18        | 3.61        | 5.45        |
| 2012            | SN1 side-separated | -2.33       | -1.21       | 0.75        | 0.74        | 2.70        |
| 2013            | SN1 side-separated | -0.18       | -1.66       | 1.80        | 4.54        | 6.02        |
| 2014            | SN1 side-separated | 1.18        | 1.95        | 1.83        | 3.14        | 5.64        |
| 2015            | SN1 side-separated | 3.40        | 2.29        | 2.18        | 2.87        | 7.68        |
| 2016            | SN1 side-separated | -1.68       | 3.81        | 5.86        | 4.45        | 15.53       |
| full_train_eval | SN2 High-age veto  | 1.43        | 1.67        | 3.02        | 2.65        | 5.07        |
| ex_2016         | SN2 High-age veto  | 1.54        | 1.67        | 3.06        | 2.28        | 4.61        |
| 2011            | SN2 High-age veto  | 4.95        | 3.63        | 4.45        | 4.35        | 5.47        |
| 2012            | SN2 High-age veto  | -1.94       | -2.60       | 0.43        | -0.21       | 4.91        |
| 2013            | SN2 High-age veto  | -0.40       | 0.08        | 4.67        | 1.07        | 5.07        |
| 2014            | SN2 High-age veto  | 1.16        | 4.55        | 1.24        | 2.21        | 4.49        |
| 2015            | SN2 High-age veto  | 4.01        | 2.75        | 4.56        | 4.01        | 3.09        |
| 2016            | SN2 High-age veto  | -0.90       | 1.59        | 2.06        | 10.21       | 14.68       |

Short × Night Net contribution and standalone Net SR by year:

| Period  | Strategy           | Short × Night Net | Net SR |
| ------- | ------------------ | ----------------- | ------ |
| ex_2016 | BOX_ORIGINAL       | -5.700%           | -0.974 |
| 2011    | BOX_ORIGINAL       | -5.016%           | -0.690 |
| 2012    | BOX_ORIGINAL       | -7.375%           | -1.322 |
| 2013    | BOX_ORIGINAL       | -10.154%          | -1.730 |
| 2014    | BOX_ORIGINAL       | -5.927%           | -1.167 |
| 2015    | BOX_ORIGINAL       | 0.017%            | 0.003  |
| 2016    | BOX_ORIGINAL       | -2.985%           | -0.237 |
| ex_2016 | D_LOW_FAST_ONLY    | -5.608%           | -0.961 |
| 2011    | D_LOW_FAST_ONLY    | -4.987%           | -0.687 |
| 2012    | D_LOW_FAST_ONLY    | -7.015%           | -1.271 |
| 2013    | D_LOW_FAST_ONLY    | -10.070%          | -1.718 |
| 2014    | D_LOW_FAST_ONLY    | -5.923%           | -1.168 |
| 2015    | D_LOW_FAST_ONLY    | -0.005%           | -0.001 |
| 2016    | D_LOW_FAST_ONLY    | -2.919%           | -0.234 |
| ex_2016 | SN1 side-separated | -6.154%           | -0.984 |
| 2011    | SN1 side-separated | -5.158%           | -0.713 |
| 2012    | SN1 side-separated | -7.282%           | -1.300 |
| 2013    | SN1 side-separated | -10.737%          | -1.529 |
| 2014    | SN1 side-separated | -6.854%           | -1.213 |
| 2015    | SN1 side-separated | -0.707%           | -0.127 |
| 2016    | SN1 side-separated | -2.833%           | -0.224 |
| ex_2016 | SN2 High-age veto  | -5.672%           | -0.959 |
| 2011    | SN2 High-age veto  | -4.987%           | -0.687 |
| 2012    | SN2 High-age veto  | -7.015%           | -1.271 |
| 2013    | SN2 High-age veto  | -10.020%          | -1.633 |
| 2014    | SN2 High-age veto  | -5.750%           | -1.118 |
| 2015    | SN2 High-age veto  | -0.554%           | -0.105 |
| 2016    | SN2 High-age veto  | -3.088%           | -0.248 |

Against D, SN1 Short × Night worsens in 2011–2015 (`-0.172`, `-0.267`, `-0.667`, `-0.931`, `-0.702pp`) and improves only `+0.086pp` in 2016 partial. SN2 is unchanged in 2011/2012, improves `+0.050pp` in 2013 and `+0.173pp` in 2014, then worsens `-0.548pp` in 2015 and `-0.169pp` in 2016 partial. Neither shows a robust annual repair.

## Mechanism decomposition versus D

`ΔNet = ΔGross (selection + common) − ΔCost`; volatility changes affect SR. Exposure values below are changes in average net exposure and the evaluator's common-exposure proxy.

| Candidate          | Period          | ΔGross  | ΔNet    | ΔSelection | ΔCommon | ΔCost   | ΔGross vol. | ΔNet SR | ΔTurnover/day | ΔNet exposure | ΔExposure common proxy |
| ------------------ | --------------- | ------- | ------- | ---------- | ------- | ------- | ----------- | ------- | ------------- | ------------- | ---------------------- |
| SN1 side-separated | full_train_eval | 0.176%  | 0.801%  | 0.284%     | -0.107% | -0.625% | -0.346%     | 0.255   | -0.025        | 0.000         | 0.000                  |
| SN1 side-separated | ex_2016         | 0.302%  | 0.959%  | 0.400%     | -0.098% | -0.658% | -0.392%     | 0.308   | -0.026        | 0.000         | 0.000                  |
| SN2 High-age veto  | full_train_eval | -1.005% | -2.374% | -1.005%    | -0.000% | 1.369%  | -0.403%     | -0.489  | 0.054         | -0.000        | -0.000                 |
| SN2 High-age veto  | ex_2016         | -1.038% | -2.457% | -1.038%    | -0.000% | 1.419%  | -0.428%     | -0.541  | 0.056         | -0.000        | -0.000                 |

- SN1: `ΔSelection +0.284pp`, `ΔCommon -0.108pp`, gross +0.176pp, cost falls 0.625pp, turnover/day falls 0.02486, gross volatility falls 0.346pp. Average net exposure and common-exposure proxy are unchanged. Total Net rises 0.801pp (ΔNet SR +0.255), but `ΔShort × Night = -0.517pp`; the total gain is not evidence that the requested loss source was repaired.
- SN2: selection/gross falls 1.005pp, common/exposure proxy essentially unchanged, cost rises 1.369pp and turnover/day rises 0.05432. Total Net falls 2.374pp, ΔNet SR -0.489. The small gross-volatility decline does not compensate.

## Short × Night source attribution

Annualized contribution, attributed standalone SR, weight share, and fractional stock-day share:

| Strategy           | Short × Night source          | Gross contrib. | Cost contrib. | Net contrib. | Attributed SR | Gross wt. share | Stock-days share |
| ------------------ | ----------------------------- | -------------- | ------------- | ------------ | ------------- | --------------- | ---------------- |
| D_LOW_FAST_ONLY    | high_age_5_plus               | -1.777%        | 0.056%        | -1.833%      | -0.721        | 32.816%         | 39.095%          |
| D_LOW_FAST_ONLY    | low_event_day                 | 0.046%         | 0.023%        | 0.022%       | 0.015         | 1.983%          | 1.532%           |
| D_LOW_FAST_ONLY    | low_age_1_4                   | -0.383%        | 0.001%        | -0.384%      | -0.268        | 5.134%          | 4.031%           |
| D_LOW_FAST_ONLY    | low_age_5_plus                | -2.641%        | 0.033%        | -2.673%      | -0.735        | 51.589%         | 47.755%          |
| D_LOW_FAST_ONLY    | score_zero_tail_tie_break     | -0.455%        | 0.003%        | -0.458%      | -0.837        | 6.768%          | 5.080%           |
| D_LOW_FAST_ONLY    | score_zero_non_tail_tie_break | -0.152%        | 0.006%        | -0.157%      | -0.266        | 1.709%          | 2.506%           |
| D_LOW_FAST_ONLY    | other                         | 0.000%         | 0.000%        | 0.000%       | 0.000         | 0.000%          | 0.000%           |
| SN1 side-separated | high_age_5_plus               | -2.474%        | 0.010%        | -2.485%      | -0.800        | 36.493%         | 41.055%          |
| SN1 side-separated | low_event_day                 | 0.046%         | 0.026%        | 0.020%       | 0.013         | 1.983%          | 1.532%           |
| SN1 side-separated | low_age_1_4                   | -0.383%        | 0.001%        | -0.384%      | -0.268        | 5.134%          | 4.031%           |
| SN1 side-separated | low_age_5_plus                | -2.302%        | 0.017%        | -2.319%      | -0.675        | 48.094%         | 44.776%          |
| SN1 side-separated | score_zero_tail_tie_break     | -0.250%        | 0.002%        | -0.252%      | -0.528        | 2.320%          | 1.687%           |
| SN1 side-separated | score_zero_non_tail_tie_break | -0.129%        | 0.004%        | -0.133%      | -0.226        | 1.244%          | 1.809%           |
| SN1 side-separated | other                         | 0.000%         | 0.000%        | 0.000%       | 0.000         | 0.000%          | 0.000%           |
| SN2 High-age veto  | high_age_5_plus               | -1.010%        | 0.143%        | -1.153%      | -0.566        | 21.102%         | 26.948%          |
| SN2 High-age veto  | low_event_day                 | 0.046%         | 0.024%        | 0.022%       | 0.014         | 1.983%          | 1.532%           |
| SN2 High-age veto  | low_age_1_4                   | -0.383%        | 0.001%        | -0.384%      | -0.268        | 5.134%          | 4.031%           |
| SN2 High-age veto  | low_age_5_plus                | -2.636%        | 0.028%        | -2.664%      | -0.733        | 51.575%         | 47.743%          |
| SN2 High-age veto  | score_zero_tail_tie_break     | 0.000%         | 0.000%        | 0.000%       | 0.000         | 0.000%          | 0.000%           |
| SN2 High-age veto  | score_zero_non_tail_tie_break | 0.000%         | 0.000%        | 0.000%       | 0.000         | 0.000%          | 0.000%           |
| SN2 High-age veto  | other                         | -0.607%        | 0.008%        | -0.615%      | -0.592        | 8.477%          | 7.586%           |

Source allocation follows the existing attribution helper; it is a bookkeeping allocation of a combined portfolio, not proof that one source causally generated a return. SN1 lowers Low-age-5+ loss by 0.354pp but increases High-age-5+ loss by 0.652pp; Short × Night deteriorates. SN2 reduces High-age-5+ loss by 0.680pp, but adds losses in high event/age 1–4 and the `other` group while leaving Low-age-5+ almost unchanged. `other` carries 8.48% of Short gross weight and 7.59% of Short stock-days, matching the original zero-score population re-encoded as ordinal ranks. Its unique scores hide the absence of a source signal; it does not create information.

## Paired circular bootstrap versus D

Existing helper only: circular paired 20-day blocks, 1,000 repetitions, seed 20260925. These intervals summarize known Train, not independent OOS evidence.

| Candidate          | ΔNet SR | 95% low | 95% high | ΔNet ann. | 95% low | 95% high | Pr(ΔSR>0) | ΔShort × Night | 95% low | 95% high |
| ------------------ | ------- | ------- | -------- | --------- | ------- | -------- | --------- | -------------- | ------- | -------- |
| SN1 side-separated | 0.255   | -0.322  | 0.829    | 0.801%    | -1.628% | 3.241%   | 81.900%   | -0.517%        | -1.200% | 0.196%   |
| SN2 High-age veto  | -0.489  | -1.002  | -0.079   | -2.374%   | -4.373% | -0.573%  | 0.700%    | -0.069%        | -0.518% | 0.329%   |

SN1 has positive annual Net point estimate, but its ΔNet SR and ΔShort × Night intervals cross zero. SN2's ΔNet SR and annual Net intervals are below zero; its Short × Night interval crosses zero around a slightly negative point estimate.

## Regulation and score structure

The repository exposes `evaluate_script.load_prediction` / `align_prediction`; no separate competition regulation checker or numerical minimum uniqueness/zero/tie threshold was found. On saved evaluation Train scores all four streams pass the one-numeric-column/index/coverage contract, finite values, daily official five quintiles, and saved weight/quintile replay. The formal SN1 Train submission entry point also matches the saved research SN1 score bit for bit. Full `evaluate_script.py` submission evaluation was not run because it defaults to Valid and Valid is prohibited here.

| Strategy           | Zero score | Unique scores | Mean unique ratio | Duplicate score | Tie boundary | Q min | Q max | Bucket spread max | Long exp. | Short exp. | Net exp. | Gross exp. | Contract |
| ------------------ | ---------- | ------------- | ----------------- | --------------- | ------------ | ----- | ----- | ----------------- | --------- | ---------- | -------- | ---------- | -------- |
| BOX_ORIGINAL | 8.760% | 506329 | 91.267% | 8.772% | 6.685% | 5 | 5 | 1 | 0.501 | 0.501 | -0.001 | 1.002 | PASS |
| D_LOW_FAST_ONLY | 8.760% | 505638 | 91.272% | 8.763% | 6.662% | 5 | 5 | 1 | 0.501 | 0.501 | -0.001 | 1.002 | PASS |
| SN1 side-separated | 8.760% | 497487 | 91.211% | 8.842% | 6.419% | 5 | 5 | 1 | 0.501 | 0.501 | -0.001 | 1.002 | PASS |
| SN2 High-age veto | 0.000% | 472 | 100.000% | 0.000% | 0.000% | 5 | 5 | 1 | 0.501 | 0.501 | -0.001 | 1.002 | PASS |

These values are calculated on the exact 576,535 rows in the saved 2011-01-04 to 2016-03-29 score artifact. The earlier table used full 2008-2016 in-memory streams while the saved artifact omits pre-evaluation rows; those pre-evaluation zeroes caused the inflated rates and old exposure figures. The corrected sole source is `audit/regulation_checks.csv`, with score hash and calculation provenance in `audit/regulation_checks_source.json`. Recomputed saved weights and quintiles have zero row mismatches. SN1 has 8.760% exact zero scores, 8.842% duplicate stock-days, and 6.419% boundary-crossing ties on the evaluation window. SN2 removes zeros and ties through daily ordinals, but its rank key includes Code; zeros are not a formal evaluator-rule violation, and zero removal alone is not proof of a valid economic short signal. B00 remains diagnostic-only by the user's explicit rule.

## Verification / reproducibility

- Reconciliation: reconstructed target max absolute difference `0`; saved D score and weight replay max errors `0`; four Day/Night cells reconcile exactly.
- Train firewall: PASS; only `*_train.parquet` data opened. Valid and raw target flags false.
- Future-mutation prefix invariance: PASS at 2012-12-28, 2014-12-30, 2015-12-30. Mutated only score cross-sections after each cutoff; candidate score prefixes, quintiles and weights remained exact.
- Official evaluator contract: `align_prediction` called on in-memory Train only; no submission evaluation.
- Run: `artifacts/DM-20260927-03/run-20260926T191539Z/`; audit and complete outputs are saved there. The two failed debug runs (`...191239Z`, `...191349Z`) are retained; they failed on purge-date and index-shape implementation bugs before a completed candidate evaluation. They are not candidate outcomes.
- Run metadata records commit `0b8341c3c0051db4b1a54040a6c4d85847bca8ec`, dirty worktree, config SHA-256 `f039b85072872f4c02cd8fd81054af36ec507998718aa7818346aff05a442fc6`, plan SHA-256 above, Train dataset hashes, source artifact hashes, cost, fold dates, seed and library versions.
- Candidate driver SHA-256 `cf2e7bf7893f8a79a952113120d7cdb128ebc8fda6bbe76be61096c837a2a1c2`; helper/evaluator hashes are recorded in `run.json`.

## Falsification decision

Both interventions pass the located mechanical submission contract and preserve the official daily five-quintile accounting. Both fail the primary economic intervention test: neither improves pooled Short × Night Net contribution, neither delivers annual stability, and neither survives the combined Short × Day / total Net rules. SN1's favorable total return is cost/selection-driven and is not a Short × Night repair. SN2's High-age-5+ source attribution improves locally but the replacement short membership, Code-ordered fillers, turnover and cost make the complete portfolio materially worse. There is no surviving lever.
