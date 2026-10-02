# DM-20260930-01: decision record

Completed 2026-09-30 JST. **Decision: reject the registered fixed MR operationalization; do not integrate it with BO.** This was one fixed Train-only candidate, not a Valid evaluation or Freeze.

- Completed run: `artifacts/DM-20260930-01/run-20260929T190344Z/`; report: [`REPORT.md`](../../reports/DM-20260930-01/REPORT.md).
- Execution retries retained: `run-20260929T185518Z` failed because 722 OHLC rows had missing values; `run-20260929T185926Z` failed because the custom daily-account table omitted fields required by the standard metric helper. Both failures were implementation/data-contract corrections. The final run used the same one registered candidate; no performance-driven trials were added.
- Actual trials: 1 / max_trials 1. Seed `20260930`. Train input hashes, code hashes, environment, command, and exit status are in the final `run.json`.
- Train scope: 2008-11-04–2016-03-31 inputs; 2011–2016 event-entry cohorts. All periods are previously inspected Train, not independent OOS. Valid was not accessed.

## Findings

- MR episodes: 5,417 executed, 5,193 TP/SL resolved, 224 timeouts. Resolved TP-first `p=29.23%` versus driftless `p0=29.71%`; `p-p0=-0.475 pp`, date-clustered 95% CI `[-1.869,+1.077] pp`. Mean trade return was `+0.0056%` gross and `-0.1944%` net after 10 bp each way. The positive-edge and net-expectancy gates failed.
- The active-event one-day MR diagnostic had Net Sharpe `-3.719`, annualized net P/L `-42.32%`, annualized cost `32.19%`, average daily turnover `1.2774`, and compounded max drawdown `-88.88%`.
- BOX BO had pooled Net Sharpe `-1.845` versus Donchian `-2.639`, mainly from lower turnover/cost. Its gross result was weaker, annualized net P/L remained `-19.85%`, and annual Net Sharpe was negative in five of six cohorts. Five-session fixed-exit BO trade net expectancy was `+0.0377%`, below Donchian's `+0.0917%`.
- MR and BO were not integrated. The result does not establish that all box MR or BO definitions fail.

## Verification

- Source scan, Train firewall, exact index alignment, finite coverage, deterministic replay, future-mutation and truncation prefix-invariance: PASS.
- Eight synthetic/unit tests: PASS. Train-only submission adapter smoke: PASS for 809,636 rows, one finite numeric output column, `(Date, Code)` index.
- Missing OHLC was handled by resetting state/history without imputation. Valid and raw-target inputs were not opened.

## Scope limits

The MR execution used fixed `|x|=1.2` stop levels. The separate `k_SL=0.5 ATR` no-position band and MR-to-BO transition were not exercised by episode execution. BO was compared at a shared five-session exit, not with the proposed failure/new-box exit. The full event-state machine was not run on randomized null OHLC paths; only the direct Brownian first-passage probability was checked. Short-borrow and squeeze costs were not modeled. These prevent treating the run as validation of the integrated proposal.

No follow-up parameter search, integration, production adoption, Freeze, or Valid evaluation was performed. The fixed candidate's no-go reason is recorded in [`GRAVEYARD.md`](../GRAVEYARD.md).
