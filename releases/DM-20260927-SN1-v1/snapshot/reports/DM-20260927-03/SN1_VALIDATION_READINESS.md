# SN1 Validation Readiness — `SIDE_SOURCE_SEPARATION`

## Executive conclusion

### Implementation follow-up — 2026-09-27

This update supersedes the initial review's findings that the submission adapter did not contain SN1 and that regulation statistics could not be reconciled. Both issues have been addressed:

1. The formal submission adapter now uses the same shared SN1 transform as the research driver. The Train entry point matches saved research SN1 scores bit for bit on all 576,535 evaluation rows.
2. audit/regulation_checks.csv was regenerated from the saved evaluation score parquet. The prior inflated zero/tie rates were caused by calculating statistics on the full 2008–2016 in-memory stream while the saved artifact contains only 2011–2016 evaluation rows.
3. Direct Train raw-stream reconstruction, independent float64 recurrence, shuffled input rows, and Parquet round trip changed zero quintile labels and zero portfolio weights. Maximum observed score-level difference was 2.22e-16.
4. The strategy directory imports as the competition evaluator's top-level submission module; a synthetic later-split test uses Train labels only.

Detailed figures and hashes are in [SN1_IMPLEMENTATION_AUDIT.md](SN1_IMPLEMENTATION_AUDIT.md). No competition Valid files were accessed. The actual later-split code path is covered by a synthetic test but was not run on competition Valid inputs. This update does not change the prior Train performance conclusion: SN1 does not solve Short × Night. A frozen release/zip parity check remains separate from this implementation audit.

### Initial review conclusion

**初回レビュー時点の判定: FAIL（以下の初回所見は実装変更前の記録）**

研究用のSN1変換式は短く説明でき、保存済みTrainスコアに対する実装も事前登録planと実質一致する。しかし、次の提出準備上の問題が残る。

1. `stock_comp_2026/strategies/dm_variable_box_breakout/submission.py` は `BOX_BIDIR_STANDALONE` を返し、SN1変換を実装していない。現行の提出経路にSN1がない。
2. 既存の `regulation_checks.csv` と結果レポートは、同runの保存済みscore列から再計算したzero/tie/unique統計と大幅に食い違う。どの値を提出書類で使うべきか再現可能な形で解決されていない。
3. SN1の長期保有はほぼ固定化している。四分位の変化が非常に少なく、順位の多くが極小のdecayed scoreやCode順tie-breakに依存する。これはコスト低下を説明する一方、経済情報が安定した証拠とは言えない。

したがって、**SN1の研究仮説は説明可能だが、現状のSN1を提出候補としてfreezeしてValidへ進める判断はしない**。Short × Nightを直した戦略とも説明してはならない。

## 1. Scope, repository findings, reproducibility

指定された `SIDE_SOURCE_SEPARATION`, `SN1`, `SHORT_NIGHT_INTERVENTION_PLAN.md`, `SHORT_NIGHT_LEVER_RESULTS.md`, `SHORT_NIGHT_ROOT_CAUSE.md`, `D_LOW_FAST_ONLY` を検索した。SN1の式は研究driver `research/experiments/short_night_root_cause.py::candidate_score_streams` にある。保存済みrunは `artifacts/DM-20260927-03/run-20260926T191539Z/`。事前登録planと既存root-cause/result reportも同じexperimentのreports配下にある。

| Item | Recorded value |
|---|---|
| Experiment / run | `DM-20260927-03` / `run-20260926T191539Z` |
| Git HEAD | `0b8341c3c0051db4b1a54040a6c4d85847bca8ec` |
| Worktree at run | dirty。今回も既存の変更・未追跡artifactを保持し、戦略コードは変更していない |
| Fixed plan | `reports/DM-20260927-03/SHORT_NIGHT_INTERVENTION_PLAN.md` |
| Plan/run timestamp | Plan fixed 2026-09-26 19:05:06 UTC; evaluation run created 2026-09-26 19:15:45 UTC |
| Plan SHA-256 | `84c3a051556e2ee02a8744e521ed22f1c600c357c4b9caccc6cb4414111ca621` |
| Run config SHA-256 | `f039b85072872f4c02cd8fd81054af36ec507998718aa7818346aff05a442fc6` |
| SN audit/evaluation code SHA-256 | `cf2e7bf7893f8a79a952113120d7cdb128ebc8fda6bbe76be61096c837a2a1c2` |
| Saved score SHA-256 | `cde0f3c9d11ad438e6705464c427f6782e55810ba96879544b4f80d9b2e78b69` |
| Saved quintile SHA-256 | `57371c8ecbc3c13e66712fae489ce83501c81d57d3005103fc232a827428602d` |
| Saved weight SHA-256 | `572175378f0ffe123b99eb324ab83dcc3add04e3d873abb45300b9cdae3337da` |
| Evaluation | Train only, 2011-01-04–2016-03-29; 2016 partial 2016-01-04–2016-03-29; 1,275 dates; 2-date purge |
| Cost / annualization | 10 bps one way / 252 days |
| Search budget | two registered transforms, SN1 and SN2; no post-result trials |
| Run selection status | `selection_eligible=false`; existing `experiments/DM-20260927-03/decision.md` rejects SN1 for the Short × Night intervention objective |
| Prefix audit | PASS at 2012-12-28, 2014-12-30, 2015-12-30; candidate scores, quintiles, weights exact before each cutoff |
| Valid / submission eval | Valid not accessed; `submission_evaluation=false`; full evaluator was not run |

The pre-registration states that Phase 1 used score/event/eligibility and PIT metadata without target or P/L. It fixed SN1 and SN2 before opening their P/L. This is a **Train-derived hypothesis**, since the Train sample and earlier Train reports had already been viewed. It is not OOS evidence. The prior `decision.md` rejects SN1 against the experiment's primary Short × Night objective; this readiness review does not overturn that decision.

Reproducibility sources: `run.json`, `config.json`, `audit/prefix_invariance.json`, `audit/firewall.json`, `audit/train_data_hashes.json`, and the saved `predictions/{strategy_scores,official_quintiles,portfolio_weights}.parquet`. The evaluator's Train target was used for the already-saved Train performance and the spell-age contribution audit; no Valid file or submission evaluation was read.

## 2. Exact strategy specification

### Signal inputs

The upstream `BOX_BIDIR_STANDALONE` signal uses two event masks in `stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py::event_mask`:

- **High event:** signal-day close is above the maximum High over the preceding 250 observations (`close_t / prior_high_250 - 1 > 0`). Its raw signed signal is positive.
- **Low event:** signal-day close is below the minimum Low over the preceding 250 observations (`prior_low_250 / close_t - 1 > 0`). Its raw signed signal is negative.

The rolling breakout barriers end at t−1. The box/context features in `features.py` use prior-only ranges and a fixed 5-observation grid of 5–120 observations; a qualifying box has prior High–Low range below 3× prior ATR20. The price builder starts from raw OHLC and applies only observed split factors to maintain comparable price units. For each side, the upstream model is a yearly walk-forward Ridge (`lambda=1.0`) on five oriented context features, trained on centered cross-sectional ranks of the 1-day residual-return target. It uses a two-trading-day label maturity purge. Active model predictions are ranked within their date and mapped to a magnitude from 0.5 to 1; High receives a plus sign and Low a minus sign. Sector, size and liquidity are not SN1 score inputs.

The saved base signal already has alpha 0.25 smoothing. The SN1 research driver inverts that saved EWMA to reconstruct the disjoint signed raw High and Low streams. The inversion utility sets reconstructed raw values with absolute magnitude below `1e-12` to zero as a floating-point cleanup, then independently forms:

`H_t = 0.25 × HighRaw_t + 0.75 × H_(t−1)`

`L_t = 0.50 × LowRaw_t + 0.50 × L_(t−1)`

The recurrence applies after the first row in each listing segment; the first state in a segment is initialized to that row's raw value (`adjust=False`). A listing gap longer than 20 trading-date positions starts a new segment. A non-event is raw zero and therefore lets that side's state decay toward zero. The sign convention is `H ≥ 0`, `L ≤ 0` because the raw streams are split by sign before smoothing.

### SN1 final-score decision table

The base D score is `D = H + L`. The actual code applies the following ordered conditions, without a fitted threshold:

| Low state L | High state H | Final SN1 score | Interpretation / reachability |
|---|---:|---|---|
| `L < 0` | `H > 0` | `L` | Low state wins even when High is positive |
| `L < 0` | `H = 0` | `L` | Low state |
| `L < 0` | `H < 0` | `L` | Code would choose L; sign pair is unreachable under the split-stream construction |
| `L = 0` | `H > 0` | `H` | High-only carry |
| `L = 0` | `H = 0` | `D = 0` | Both states are zero; fallback |
| `L = 0` | `H < 0` | `D = H` | Unreachable under the split-stream construction |
| `L > 0` | any H | `D = H + L` | Unreachable because Low raw values are nonpositive and EWMA preserves sign |

In valid data the operational form is therefore: **use the negative Low state whenever one exists; otherwise use the positive High state if one exists; otherwise retain D (normally zero).** It is a source-precedence rule applied to one scalar score. The code does not build separate long and short orders, nor branch on final portfolio side.

```python
D = high_state + low_state
SN1 = D.copy()
SN1[low_state < 0] = low_state[low_state < 0]
high_only = (low_state == 0) & (high_state > 0)
SN1[high_only] = high_state[high_only]
```

This is 5 lines and matches `candidate_score_streams` in the research driver. The plan/run prose says “otherwise positive High”; the implementation explicitly requires `low_state == 0` for that branch. Given the sign invariant and the earlier `low_state < 0` branch, the two descriptions are behaviorally equivalent on valid states. This boundary condition should remain explicit in any filed description.

### Portfolio construction

SN1 score is ranked each date by the existing official five-quintile helper. After sorting `(Date, Code)`, exact ties use `rank(method="first")`, followed by `qcut(5)`. For daily universe count N and quintile index q=0…4, the saved helper assigns `weight = (q − 2) / (N × 1.2)`: Q1/Q2 short, Q3 zero, Q4/Q5 long. SN1 does not change the official weights, exposure convention, target, or cost. The local evaluator charges `0.001 × abs(weight_t − weight_(t−1))` per name.

## 3. Why SN1 works mechanically — and what the evidence does not establish

The upstream model's oriented target encodes the hypothesis that a High event can precede stronger relative outcomes and a Low event can precede weaker relative outcomes; that is a statement about its fitted objective, not independent confirmation of persistence. The simplest SN1 mechanism supported by code is that a single sum `H + L` lets positive High carry offset negative Low carry. If Low is active, SN1 retains the negative Low value, so a positive High component cannot lift that name within the cross-section. When no Low state remains, positive High carry can rank the name upward. This makes score direction more directly track the active side-state and explains why the Short sleeve stops including positive scores.

Observed Train mechanics are consistent with that description:

- Positive-score Q1/Q2 rows fell from 39.03% for D to 0% for SN1; SN1 Short stock-days are 96.50% negative and 3.50% exactly zero.
- Average daily rank autocorrelation rose from 0.9865 to 0.9959; average absolute rank-percentile change fell from 0.0098 to 0.0027.
- The official portfolio turnover fell 76.5%, and annual cost fell 0.625 percentage point.

These are observations of the rule's operation. They do **not** show that prices contain more stable information, that the direction split is economically causal, or that the gain generalizes. SN1 score values are heavily compressed near zero; high Q retention may reflect stable ordering of carried signals and tie-breaking rather than improved information quality. The strongest performance contribution comes from long membership spells, and the Short book remains negative.

## 4. Turnover, holding persistence and concentration audit

All path statistics below are computed from the saved daily score/quintile/weight stream; rank changes, transitions and retention use adjacent trading dates and names present on both dates. Holding spells mean consecutive daily membership in Q1/Q2 (Short) or Q4/Q5 (Long), with a quintile change within the same side counted as continued membership. Spells are truncated to the evaluation window, so the first and last spells may be left/right censored. This is membership persistence, not proof of a fixed-share buy-and-hold position.

| Statistic | D_LOW_FAST_ONLY | SN1 | Reading |
|---|---:|---:|---|
| Mean daily rank autocorrelation | 0.9865 | 0.9959 | SN1's ordinal ranking changes less |
| Mean absolute rank-percentile change | 0.0098 | 0.0027 | About 72% lower |
| Median absolute rank-percentile change | 0.00215 | 0.00000 | At least half of SN1 matched names keep exactly the same percentile rank |
| Q1 retention | 98.78% | 99.17% | One-day transition, names present on both days |
| Q2 retention | 97.91% | 99.07% | Same definition |
| Q4 retention | 95.24% | 99.39% | Same definition |
| Q5 retention | 95.80% | 99.64% | Same definition |
| Mean daily Short entrants / exits | 1.55 / 1.54 | 0.55 / 0.54 | Across 1,274 adjacent-day transitions |
| Mean daily Long entrants / exits | 2.42 / 2.41 | 0.41 / 0.40 | Same |
| Median daily nonzero-weight holdings | 362 | 362 | Number of held names is unchanged |
| Long spell duration, mean / median days | 70.7 / 35.0 | 330.5 / 140.5 | Marked increase |
| Short spell duration, mean / median days | 107.2 / 53.5 | 261.8 / 152.5 | Marked increase |
| Mean absolute score change on matched names | 0.01248 | 0.00672 | Smaller numeric moves |
| Median absolute score change on matched names | `1.62e-11` | `6.34e-61` | Extremely small median SN1 changes |
| Mean daily score cross-section standard deviation | 0.07020 | 0.05030 | Lower score spread |
| Mean daily weight turnover `Σ|w_t−w_(t−1)|` | 0.032517 | 0.007655 | Saved evaluator-compatible definition |
| Sign transition, any / nonzero reversal | 0.265% / 0.187% | 0.120% / 0.042% | Among matched names on adjacent trading dates |

| Side / strategy | Spell share lasting ≥5 / ≥10 / ≥20 days | Stock-days in spells lasting ≥5 / ≥10 / ≥20 days |
|---|---:|---:|
| Long — D | 93.41% / 83.09% / 66.48% | 99.73% / 98.72% / 95.39% |
| Short — D | 89.55% / 82.87% / 72.75% | 99.78% / 99.36% / 98.02% |
| Long — SN1 | 93.98% / 90.83% / 84.96% | 99.96% / 99.89% / 99.63% |
| Short — SN1 | 96.94% / 95.46% / 91.72% | 99.97% / 99.94% / 99.71% |

Daily quintile transitions, row = previous Q, column = current Q, over adjacent dates and matched names:

| D | Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---:|---:|---:|---:|---:|
| Q1 | 98.8% | 0.8% | 0.0% | 0.0% | 0.4% |
| Q2 | 0.8% | 97.9% | 0.5% | 0.1% | 0.7% |
| Q3 | 0.2% | 1.3% | 97.0% | 0.4% | 1.1% |
| Q4 | 0.1% | 0.0% | 2.5% | 95.2% | 2.1% |
| Q5 | 0.0% | 0.0% | 0.0% | 4.2% | 95.8% |

| SN1 | Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---:|---:|---:|---:|---:|
| Q1 | 99.2% | 0.8% | 0.0% | 0.0% | 0.0% |
| Q2 | 0.4% | 99.1% | 0.5% | 0.0% | 0.0% |
| Q3 | 0.2% | 0.1% | 99.4% | 0.3% | 0.0% |
| Q4 | 0.2% | 0.0% | 0.1% | 99.4% | 0.3% |
| Q5 | 0.1% | 0.0% | 0.0% | 0.3% | 99.6% |

SN1 behaves **close to a static membership portfolio**, although it is not concentrated in a few names: median active holdings remain 362, average daily top-10 absolute-weight share is 3.68%, and average maximum single-sector share is 10.81% (D 10.75%). The average sector HHI is 0.0563 (D 0.0547). PIT size exposure is similar: TOPIX Mid400 62.64% vs D 63.33%; TOPIX Small 2 15.57% vs 15.05%; Large70 13.85% vs 14.19%; Core30 6.50% vs 6.03%. Sector/size are diagnostics only; neither enters SN1.

The saved Train target can be allocated by membership-spell age as a descriptive weighted-return accounting. Annualized contribution from spells aged 20+ days is Long `+6.274%` and Short `−1.538%`, net `+4.736%` for SN1. D's corresponding values are Long `+4.582%`, Short `−1.302%`, net `+3.280%`. This is not a causal source decomposition, and current weights are rebalanced daily, but it shows the observed Gross P/L is concentrated in persistent Long names rather than an improved Short book.

Yearly saved account turnover (mean daily, evaluator units):

| Year | D | SN1 |
|---|---:|---:|
| 2011 | 0.01744 | 0.01593 |
| 2012 | 0.01696 | 0.00933 |
| 2013 | 0.05926 | 0.00073 |
| 2014 | 0.02615 | 0.00406 |
| 2015 | 0.04477 | 0.00348 |
| 2016 partial | 0.02520 | 0.02699 |

The reduction is concentrated in 2013–2015. SN1 turnover is slightly higher in 2016 partial, so the change is not a universal annual property.

## 5. Score quality and regulation

### Independently recalculated saved-score checks

The initial regulation table calculated score-distribution statistics on full 2008–2016 in-memory streams, but the saved score parquet contains only 2011–2016 evaluation rows. That scope mismatch caused the previously reported SN1 zero rate 34.379%, mean daily unique ratio 64.810%, duplicate rate 34.438%, and tie-boundary rate 32.688%. The corrected statistics are generated from the hashed saved score parquet in `audit/regulation_checks.csv`; its source and Train index-coverage check are recorded in `audit/regulation_checks_source.json`. Train target values were not used for score statistics or P/L.

| Recomputed Train score statistic | D | SN1 |
|---|---:|---:|
| Finite score / duplicate `(Date, Code)` index | 100% / none | 100% / none |
| Exact zero-score stock-day rate | 8.760% | 8.760% |
| Duplicate-score stock-day rate | 8.763% | 8.842% |
| Tied score rows spanning quintiles | 6.662% | 6.419% |
| Mean per-day `unique scores / names` | 91.272% | 91.211% |
| Minimum per-day unique ratio | 3.425% | 3.425% |
| Pooled unique score values | 505,638 | 497,487 |
| `abs(score) < 1e-12` | 46.18% | 75.86% |
| `abs(score) < 1e-8` | 56.84% | 81.11% |
| `abs(score) < 1e-4` | 71.65% | 88.08% |
| Absolute-score median / 90th percentile | `3.77e-11 / 0.07913` | `5.19e-61 / 0.000790` |
| Official quintiles / max daily bucket-size spread | 5 / 1 | 5 / 1 |

Within SN1's Short stock-days, 96.50% of scores are negative, 3.50% are exact zero and none are positive. In Q4/Q5 only 54.32% of SN1 scores are positive, so it is not accurate to describe all Long names as positive-High names.

The minimum daily unique ratio occurs on the first evaluation day, 2011-01-04, when 96.80% of SN1 scores are exactly zero. Daily score coverage is complete. Thus “91% average daily uniqueness” hides an extreme first-day tie case and a large mass of later nonzero scores at numerically tiny magnitudes. The score is finite and deterministic but not uniformly well-separated as a continuous signal. The `1e-12` inversion cleanup is inherited from the research implementation and is shared by the submission path; it is not an alpha or threshold search. Direct-raw, float64, row-order, and save/reload results are in `SN1_IMPLEMENTATION_AUDIT.md`.

### Code-order tie dependence

The official helper first sorts `(Date, Code)` and uses `rank(method="first")` before `qcut`. This resolves exact ties deterministically by Code order, but it gives identical scores different official quintiles when a tie crosses a boundary. Under an audit-only reverse-Code tie ordering (same values, no P/L evaluation), Q labels change for 5.01% of D stock-days and 5.29% of SN1 stock-days; 75.3%/82.4% of the respective boundary-tie rows change quintile. Within original Short holdings, 3.67% of D and 3.32% of SN1 change quintile. Short-vs-non-Short membership changes for 2.87% of D and 2.66% of SN1 stock-days overall (3.58%/3.32% of the original Short rows). Therefore determinism is confirmed; economic invariance to identifier ordering is not.

The saved Train streams passed the local one-numeric-column/index/coverage alignment checks; all five daily quintiles form, bucket-size spread is at most one name, and weights are finite. The formal Train submission entry point now exactly matches the saved research SN1 score. Replayed average exposures are Long `+0.500560`, Short `−0.501142`, net `−0.000582`, gross `1.001702`. The repository README and evaluator specify five daily quintiles, a one-column numeric prediction indexed by `(Date, Code)`, target coverage and 10 bp one-way cost. No separate competition rule or numerical minimum for zero score, unique score ratio or tie rate was found; those thresholds are **確認不能** from the repository. Full evaluator execution remains intentionally unrun because it defaults to Valid.

## 6. Performance, annual stability and causal limits

### D → SN1 summary

| Metric | D | SN1 | Change |
|---|---:|---:|---:|
| Annual Gross return | 4.532% | 4.708% | +0.176 pp |
| Annual Net return | 3.716% | 4.517% | +0.801 pp |
| Gross / Net Sharpe | 0.987 / 0.808 | 1.108 / 1.063 | +0.121 / +0.255 |
| Gross volatility | 4.593% | 4.248% | −0.346 pp |
| Maximum drawdown | −6.149% | −6.271% | 0.122 pp worse |
| Annual cost | 0.816% | 0.191% | −0.625 pp |
| Turnover/day | 0.032517 | 0.007655 | −0.024862 |
| RankIC | 0.0113 | 0.0125 | +0.0012 |
| Average net exposure | unchanged to reported precision | unchanged | ~0 |

The evaluator decomposition is `ΔGross = ΔSelection + ΔCommon`: `+0.176 = +0.284 − 0.108` percentage points. With annual cost falling by `0.625 pp`, `ΔNet = +0.176 − (−0.625) = +0.801 pp`. The bootstrap is the existing paired circular 20-day-block/1,000-draw/seed-20260925 procedure: ΔNet SR `+0.255` (95% interval `[-0.322, 0.829]`), ΔNet annual return `+0.801 pp` (`[-1.628, +3.241]`), and ΔShort × Night contribution `−0.517 pp` (`[-1.200, +0.196]`). These intervals summarize previously viewed Train, not OOS.

| Side | D Gross / Net / Net SR | SN1 Gross / Net / Net SR | Interpretation |
|---|---:|---:|---|
| Long | 5.880% / 5.307% / 1.017 | 6.230% / 6.161% / 1.253 | Net +0.854 pp; main beneficial side |
| Short | −1.348% / −1.591% / −0.324 | −1.522% / −1.644% / −0.325 | Net −0.053 pp worse; no Short alpha improvement |

Long's annual Gross rises by `0.350 pp`, and its cost falls by `0.504 pp`, yielding `+0.854 pp` Net. Short Gross falls by `0.174 pp`; its cost falls by `0.121 pp`, leaving Short Net `0.053 pp` worse. This is why the total improvement cannot be described as improved Short alpha.

SN1 Long × Day Net improves from `−0.967%` to `−0.045%`; Long × Night changes from `+6.275%` to `+6.206%`; Short × Day improves from `+3.892%` to `+4.357%`; **Short × Night worsens from `−5.483%` to `−6.001%` (−0.517 pp)**. SN1 is not a Short × Night solution. In the Short × Night source attribution, Low-age-5+ loss improves `0.354 pp`, while High-age-5+ loss worsens `0.652 pp`. The Long/Short Net-return correlation changes from `−0.590` to `−0.637`.

### Annual Net return, Net SR and Short × Night

| Period | D Net ann. | SN1 Net ann. | D Net SR | SN1 Net SR | D turnover | SN1 turnover | ΔShort × Night Net |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2011 | 0.039% | 0.033% | 0.008 | 0.007 | 0.01744 | 0.01593 | −0.172 pp |
| 2012 | 6.392% | 4.816% | 1.344 | 1.082 | 0.01696 | 0.00933 | −0.267 pp |
| 2013 | 5.017% | 7.729% | 1.025 | 1.670 | 0.05926 | 0.00073 | −0.667 pp |
| 2014 | 4.007% | 4.032% | 1.468 | 1.954 | 0.02615 | 0.00406 | −0.931 pp |
| 2015 | −0.017% | 3.664% | −0.003 | 0.920 | 0.04477 | 0.00348 | −0.702 pp |
| 2016 partial | 16.463% | 14.004% | 2.223 | 1.850 | 0.02520 | 0.02699 | +0.086 pp |
| ex-2016 | 3.098% | 4.057% | 0.701 | 1.009 | 0.0329 | 0.0067 | −0.546 pp |
| Full | 3.716% | 4.517% | 0.808 | 1.063 | 0.0325 | 0.0077 | −0.517 pp |

The pooled Net gain survives excluding 2016, so it is not a 2016-only result. But the yearly gain is uneven: 2013 and 2015 carry most of the return improvement, while 2012 and 2016 are materially worse. Short × Night deteriorates in five of six calendar periods and improves only slightly in 2016 partial. It is not year-stable evidence for an improved Short strategy.

## 7. Explainability, specification and reviewer risks

### Process integrity and post-hoc risk

- Phase 1 structural facts and candidate plan were saved before the fixed SN1 P/L run. Plan hash is preserved and run config fixes two candidates only.
- Candidate definitions were motivated by an already-seen Train Short × Night loss audit. The Train sample was already known; therefore this is not an untouched test or independent validation.
- The run states `valid_accessed=false`, `raw_target_accessed=false`, `submission_evaluation=false`, and records Train firewall/prefix checks. Current review also uses no Valid.
- `D_LOW_FAST_ONLY` remains the comparator; B00 was a diagnostic control only. No alpha, horizon, threshold, lambda, feature, or SN1 derivative was tested in this review.

### Likely reviewer questions

| Reviewer question | Defensible answer | Weak point | Additional evidence needed |
|---|---|---|---|
| 1. Why split High and Low? | They are signed directional event streams; summing them lets one offset the other. SN1 gives priority to an active negative Low state. | The choice arose from the Train loss audit and is not independent evidence. | Locked independent-period confirmation after freeze. |
| 2. Is SN1 a separate long and short ranking model? | No. It produces one scalar and retains the existing official quintile construction. | Calling it “side-specific portfolios” would overstate the code. | Use the exact decision table and code path in the filing. |
| 3. What happens when High and Low are both active? | SN1 uses Low whenever `L<0`, even if `H>0`; High is used only when `L=0` and `H>0`. | This is asymmetric source precedence, not an equal two-sided blend. | Report frequency and examples from saved Train states if asked. |
| 4. Why use High alpha 0.25 and Low alpha 0.50? | They are the fixed D specification inherited by SN1; SN1 did not tune alphas. | Alphas came from prior Train research and are unequal. | Document the historical origin and freeze both values. |
| 5. Why is Low faster than High? | Alpha 0.50 places more weight on the latest raw Low observation; alpha 0.25 gives High longer decay. | The Train record does not prove that these half-lives are economically optimal. | No new search here; explain as pre-existing fixed choice only. |
| 6. Why did turnover fall by about three quarters? | Rank changes and quintile migration fall; mean daily turnover is 0.0077 vs 0.0325. | Median Long/Short membership spells expand to 140.5/152.5 days; the change is near-static membership, not just smaller trade sizing. | Independent future evaluation of holdings persistence and performance. |
| 7. Does lower turnover mean the information is more stable? | Rank persistence is higher, but the score distribution is also compressed: 81.1% of absolute scores are below `1e-8`. | Rank stability can be produced by carried states and very small numerical differences. | Numerical stability and input-order sensitivity audit before claiming signal stability. |
| 8. Why are there exact zeroes and ties? | When both reconstructed side streams are zero in a segment, the fallback D score is exactly zero; non-event zero inputs otherwise decay prior state toward zero. Exact zero rate is 8.76%, and many carried values are tiny but nonzero. | Tie-boundary rows are 6.42%, with material Code-order sensitivity. | Reconciled score audit and disclosed tie policy; no source-derived secondary rank was tested. |
| 9. Is ticker order driving the portfolio? | The implementation is deterministic because ties use sorted Code order. | Reversing Code order changes 5.29% of SN1 quintile labels (3.32% of Q1/Q2 rows). | Demonstrate official evaluator's exact ordering and include that rule in the submission description. |
| 10. Why keep Short if Short Net is negative? | The fixed official five-quintile construction always includes Q1/Q2; SN1 did not add a Short veto. | Short Net worsens slightly and Short × Night worsens materially. | Do not claim Short alpha; state this limitation accurately. |
| 11. Did SN1 fix the Short × Night loss? | No. It worsens the pooled cell by 0.517 pp. | The experiment's motivation could invite an exaggerated claim. | Explicitly state it is not a night-loss fix. |
| 12. Is the gain robust by year? | Full and ex-2016 point estimates are positive vs D. | 2012/2016 worsen; much of the gain is in 2013/2015; paired Train intervals include zero. | Do not call Train stability OOS confirmation. |
| 13. Was the candidate selected after seeing its result? | Its conditions and hash were recorded before SN1 P/L was evaluated; exactly two candidates were fixed. | The motivating diagnosis already used known Train P/L, and all Train years were previously viewed. | Preserve the plan, run config, and this Train-derived disclosure. |
| 14. What is the difference from B00? | B00 is retained only as a diagnostic control; it is not SN1 and is not a submission candidate. | No B00 performance comparison is needed to explain SN1. | Do not present B00 as an eligible alternative. |
| 15. Does this repo contain the submitted SN1? | Yes. The formal adapter applies the shared SN1 transform, and its Train output matches the saved research score bit for bit. | The actual later-split branch was not run on competition Valid inputs; the frozen zip/package path has not been checked. | Run a Train-only package/zip parity check before freezing; do not inspect Valid during that check. |

## 8. Freeze recommendation

### Freeze recommendation at initial review

**Initial review recommendation: no freeze and no Valid evaluation.** At that time the research transformation was mechanically interpretable, but the strategy was not present in the submission adapter and score-quality report provenance was inconsistent. This recommendation is superseded on those two points by the implementation follow-up at the top of this report. Code-order tie handling remains deterministic under the official sort rule but is not invariant to changing the identifier tie order.

The truthful economic description is: “SN1 changes how a single cross-sectional score prioritizes carried Low/High breakout states; in known Train it greatly reduces turnover and improves aggregate Net performance, mainly through lower cost and persistent Long membership. It does not improve the Short book and worsens Short × Night.” Do not claim that it repairs the initiating loss, is OOS-confirmed, or has a uniformly meaningful continuous score.

### Source and artifact paths

- SN1/D code: `research/experiments/short_night_root_cause.py::candidate_score_streams`
- Event/model code: `stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py`; `features.py`
- EWMA and official quintile code: `research/experiments/box_asymmetry_gate.py`
- Submission adapter: `stock_comp_2026/strategies/dm_variable_box_breakout/submission.py`
- Fixed experiment plan: `reports/DM-20260927-03/SHORT_NIGHT_INTERVENTION_PLAN.md`
- Existing result with corrected regulation table: `reports/DM-20260927-03/SHORT_NIGHT_LEVER_RESULTS.md`
- Saved Train run: `artifacts/DM-20260927-03/run-20260926T191539Z/`
