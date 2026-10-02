# DM-20260930-01: Event-driven box first trial

**Decision: reject this fixed MR operationalization; do not integrate MR with BO.** BO's entry-day portfolio was less costly than the 20-session Donchian reference, but its gross result was weaker and its net result remained negative. No parameter search followed the registered trial.

## Reproduction

- Plan/config: [`plan.md`](../../experiments/DM-20260930-01/plan.md), [`config.json`](../../experiments/DM-20260930-01/config.json).
- Completed run: `artifacts/DM-20260930-01/run-20260929T190344Z/`; one fixed candidate, seed `20260930`, 146.6 seconds, Python 3.11.13 / NumPy 2.4.6 / pandas 3.0.3.
- Command: `.venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python research/experiments/event_box.py --config artifacts/DM-20260930-01/run-20260929T190344Z/config.json --output artifacts/DM-20260930-01/run-20260929T190344Z`.
- Data: Train only, 2008-11-04–2016-03-31; event-entry cohorts 2011–2016. These Train years are already known and are not independent OOS. No Valid or raw target file was opened.
- Two earlier attempts are retained as failed runs: the first exposed 722 missing OHLC rows; the second exposed missing fields in the event-account metric adapter. The final run resets state at invalid OHLC rows without imputation and completed all registered checks.

## Fixed design

The initial box uses the prior 20 sessions if its width is 0.5–3.0 prior ATR20 and the signal-date close remains inside its boundaries. Post-breakout box formation uses one ATR reversal to confirm each side. There is one MR entry per box and direction: `|x|>=0.8`, target `x=0`, stop `|x|=1.2`, next-open entry, five-session timeout, and conservative stop-first handling if daily OHLC hits both target and stop. MR episode returns are raw stock price returns with 10 bp per side; they are not market-residualized.

For the entry-day portfolio diagnostic, available long and short events each receive 0.5 gross exposure; inactive names remain cash. Returns use the official Train `target_1day` and 10 bp one-way turnover cost. Q1–Q5 are computed only among active events. This is a research diagnostic, not the competition evaluator's full-universe portfolio. BO and Donchian event trades also use a common five-session fixed exit to isolate entry timing; this does not test a BO hold-to-failure or hold-to-new-box exit.

## Causality, coverage, and execution checks

- Static source scan passed. Future-mutation and truncation prefix-invariance both passed at 2014-12-30 after mutating all feature inputs.
- Train firewall opened only `prices_daily_quotes_train.parquet`, `raw_return_1day_train.parquet`, and `target_1day_train.parquet`; `raw_target` was not read.
- Feature/state output covered 809,636/809,636 target rows, exact index alignment and deterministic replay passed. The submission adapter smoke returned a finite one-column `(Date, Code)` score for all 809,636 rows, using only the two Train feature files.
- 722 rows (0.089% of the panel) had missing OHLC. Those rows reset state and history; no price was imputed.
- Synthetic transition tests covered SEARCH→BOX→EXTEND→ANCHOR→BOX, one entry per box side, split-safe OHLC representation, missing-data reset, deterministic output, future mutation, and the analytical first-passage probability under a driftless random walk: **8 tests passed**.

## MR episode result

There were 5,417 executed MR episodes in the six entry cohorts; 5,193 reached target or stop and 224 timed out. Another 4,278 edge signals were canceled because the next Open had already passed a target/stop boundary. Among resolved episodes:

- TP-first rate `p = 29.23%`; mean driftless first-passage probability `p0 = 29.71%`; `p - p0 = -0.475` percentage points.
- The date-clustered 20-session bootstrap 95% interval for `p - p0` was `[-1.869, +1.077]` percentage points; 28.1% of bootstrap draws were positive. This is inconclusive about a small edge and does not satisfy the preregistered positive-lower-bound gate.
- Mean episode return was `+0.0056%` gross and `-0.1944%` after two 10 bp costs per round trip. The median net return was `-0.5563%`.

| Entry year | Resolved | TP first | Mean p0 | p − p0 | Mean net return |
|---:|---:|---:|---:|---:|---:|
| 2011 | 1,007 | 32.47% | 32.35% | +0.12 pp | -0.193% |
| 2012 | 988 | 25.81% | 27.77% | -1.96 pp | -0.275% |
| 2013 | 990 | 27.88% | 27.97% | -0.09 pp | -0.130% |
| 2014 | 971 | 31.31% | 30.98% | +0.33 pp | -0.163% |
| 2015 | 993 | 29.91% | 29.14% | +0.77 pp | -0.139% |
| 2016* | 244 | 24.18% | 30.92% | -6.74 pp | -0.498% |

\* 2016 is a partial Train period through March 31. The episode sample is censored to trades that could finish inside Train.

MR failed both required continuation checks: the net episode mean was negative and the confidence interval for `p-p0` included zero. Only three of six annual `p-p0` point estimates were positive.

## Entry-day portfolio and Donchian comparison

Sharpe ratios below use daily net/gross returns and `sqrt(252)` annualization. Annual P/L and cost are annualized daily means; turnover is mean daily one-way turnover; drawdown is compounded. RankIC t-statistic uses the repository's HAC5 estimator.

| Signal | Gross SR | Net SR | Annual gross | Annual net | Annual cost | Turnover/day | RankIC / HAC5 t | Long / Short gross P/L | Q1–Q5 monotonicity | Max DD |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MR entry | -0.891 | -3.719 | -10.13% | -42.32% | 32.19% | 1.2774 | +0.0293 / +1.43 | -0.80% / -9.33% | +0.30 | -88.88% |
| BOX BO entry | -0.082 | -1.845 | -0.88% | -19.85% | 18.96% | 0.7525 | +0.0083 / +0.33 | -0.88% / 0.00% | -0.10 | -69.00% |
| Donchian 20 entry | +0.231 | -2.639 | +1.91% | -21.79% | 23.70% | 0.9406 | -0.0232 / -1.96 | +1.91% / 0.00% | -0.10 | -68.26% |

BOX BO improved pooled Net Sharpe by `+0.794` and reduced annualized cost by `4.74 pp` versus Donchian, while gross Sharpe fell by `0.314` and annual gross P/L fell by `2.79 pp`. Annual Net Sharpe was still negative in five of six BOX BO years and the 2016 delta was `-1.895`; annual net P/L improved in only three of six years. The difference is mainly lower event turnover, not stronger gross breakout returns.

With the same five-session fixed exit, mean BO trade net return was `+0.0377%` for event-box breakouts (4,582 trades) versus `+0.0917%` for Donchian (28,171 trades). Both results are descriptive raw-price trade returns; they are not evidence for the complete event-driven BO lifecycle.

Full annual metrics including Q1–Q5 returns, RankIC hit ratio, annual Long/Short P/L, and drawdown are in [`entry_daily_metrics.csv`](entry_daily_metrics.csv). The year-by-year BO-minus-Donchian deltas are in [`box_bo_vs_donchian_delta.csv`](box_bo_vs_donchian_delta.csv). Episode tables and the MR bootstrap are also saved beside this report.

## Decision and limits

Reject this fixed MR event definition and stop the registered one-candidate trial. Do not combine MR with BO. This is not proof that all box mean-reversion methods are ineffective. The tested MR stop was the fixed box coordinate `|x|=1.2`; the separate `k_SL=0.5 ATR` no-position band and MR-to-BO transition were not implemented in episode execution. The BO comparison also used a shared five-session exit instead of the proposed failure/new-box exit. A full same-state-machine randomized-path null and short-borrow costs were not evaluated. These limits prevent claiming the integrated proposal was fully validated; they do not change the no-go decision for the registered fixed candidate.
