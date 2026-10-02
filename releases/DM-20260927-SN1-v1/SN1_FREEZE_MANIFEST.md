# SN1 Freeze Manifest — DM-20260927-SN1-v1

**Freeze purpose:** one Valid evaluation of exactly `D_LOW_FAST_ONLY` and `SIDE_SOURCE_SEPARATION` (SN1). This manifest and the evaluation plan were saved and hashed before any Valid target or Valid P/L was read.

## Repository state

- Final freeze commit / Git HEAD: `09920d4221594b961a5793be02baab9214382f4e`.
- Parent HEAD before the final freeze commit: `f23ae60fc8f532522fb50a3c177b726c70dc4daa`. Initial work HEAD before this freeze task: `0b8341c3c0051db4b1a54040a6c4d85847bca8ec`.
- Worktree status: dirty. Pre-existing unrelated files were retained; only the SN1 strategy, its evaluation runner/tests, lineage documents and release snapshot were committed. `experiments/GRAVEYARD.md` and unrelated untracked experiment/report/source folders were not staged.
- Exact porcelain status captured after the final freeze commit and before Valid access: `worktree_status_at_freeze.txt`, SHA-256 `0bf11c536862df80c145ba337dc3ce1e20435da2d6a11efe8d05e671ae0ae1a9`, 79 entries. The manifest, lock and status snapshot are post-commit freeze metadata; source code is fixed by the commit and per-file hashes below.
- Freeze time: 2026-09-27 06:42:46 UTC (2026-09-27 15:42:46 Asia/Tokyo).

## Frozen strategy and candidate scope

- Formal source of truth: `stock_comp_2026/strategies/dm_variable_box_breakout/submission.py` and `sn1.py`; research lineage: `research/experiments/short_night_root_cause.py`.
- The only Valid candidates are `D_LOW_FAST_ONLY` and `SIDE_SOURCE_SEPARATION`. D is the sole comparison baseline; `submission.predict()` returns SN1. B00, BOX_ORIGINAL, SN2, vetoes, blends, and every other score are excluded from Valid.
- High EWMA alpha `0.25`; Low EWMA alpha `0.50`; raw reconstruction cleanup `1e-12` unchanged.
- Fixed SN1 transform: `D = high_state + low_state`; begin with D; use `low_state` when `low_state < 0`; use `high_state` when `low_state == 0 and high_state > 0`; otherwise retain D.
- Upstream annual expanding High/Low Ridge and the event, feature, and universe definitions are unchanged. Ridge lambda `1.0`; 2011–2016 annual Train folds; two-trading-day purge; minimum 500 eligible observations per side/fold. Directional columns: `box_duration`, `box_width_atr`, `oriented_close_position`, `oriented_relative_strength_60`, `distance_to_prior_extreme`.
- Inputs: `raw_return_1day`, `beta_1day`, `topix_return_1day`, `prices_daily_quotes`; point-in-time rows define the existing competition universe. No new universe filter.
- Official portfolio: sort `(Date, Code)`, `rank(method="first")`, `qcut(5)`; weight `(quintile_index - 2) / N / 1.2`; one-way cost `0.001`; annualization 252.
- Valid outcome: only `target_1day_valid.parquet`, column `Return`, read once after plan/config/manifest/source/zip hashes pass and candidate scores are saved. No Valid outcome has been opened as of this manifest. `raw_target_1day_valid.parquet` is excluded.

## Plan, config and data hashes

- Valid plan: `experiments/DM-20260927-03/VALID_EVALUATION_PLAN.md` — SHA-256 `680b0a2b7c0b6e8de089cfeee530ffa3b155bd27705152b167943affce67da9d`.
- Valid config (candidate list, metrics, costs, annual partitions, bootstrap and decision rules): `experiments/DM-20260927-03/valid_evaluation_config.json` — SHA-256 `5efd7a38137edc7773fef9ee0507bfe848d40845693f26f667a7cfcd592356ac`.
- Competition input manifest (metadata; no Valid outcome values): `stock_comp_2026/input_manifest.json` — SHA-256 `62ec8e2f18b4523541c8f7623793f74eeed3f21af2c8ab43b74b1d71cf283c58`.
- Submission zip: `releases/DM-20260927-SN1-v1/SN1_SUBMISSION.zip` — SHA-256 `945ba58e9011ed7a285b0b47ad29cfed69533868502bb3d96fe4a16f254617b6`.
- Environment: `environment.json`; source and fixed research snapshot: `snapshot/`; inventory: `freeze_hashes.json`.

## Code SHA-256

| File | SHA-256 |
|---|---|
| `stock_comp_2026/strategies/dm_variable_box_breakout/__init__.py` | `cae7cbdb3b7175d80d8ff9f08335721dc4d526f7fd2e3bcca7037dfcd947e853` |
| `stock_comp_2026/strategies/dm_variable_box_breakout/features.py` | `3c2066557ad566556bf9ed6f21910926a36e59979dafef18369090b53ca5dc0a` |
| `stock_comp_2026/strategies/dm_variable_box_breakout/models.py` | `b301ee3e4ce1f85b712269cb094087fff73d1465fda99f6628eae0aacb2e1216` |
| `stock_comp_2026/strategies/dm_variable_box_breakout/bidirectional.py` | `7cec7be6d45bfba9debee9c07af6d6abf5229961014654de17b23b88b145e287` |
| `stock_comp_2026/strategies/dm_variable_box_breakout/sn1.py` | `55f95ab669e506d61a1d20442efe9b266b56ab14737a7d46b666fee7c0f9c7ae` |
| `stock_comp_2026/strategies/dm_variable_box_breakout/submission.py` | `943feac6a150148cd162b7ba96adff343de8643c2940343be307aae5649dfa32` |
| `research/experiments/short_night_root_cause.py` | `82a9defa364f34e9c4c0bbf4392dd2257e6ef85306ad6e8cd675c41031402588` |
| `research/experiments/sn1_valid_once.py` | `becbd2e370a630b6c1c106dc740cf9c881dafe46afd4be4cadcb1abe2a5b537d` |
| `research/evaluation.py` | `4da3e290f49e2061f2fdaf4efdb6e1ae5ecda5babc4dc9e9f6f77fc7ae891c4e` |
| `stock_comp_2026/evaluate_script.py` | `4945e4b50169abc3de4d84c60b73b0b38c4ded091fc6631bfa6828ec87261818` |
| `tests/strategies/dm_variable_box_breakout/test_sn1.py` | `ce184da050abd0dfda8aea31b62934c931f40d2f0b7ddefb8105f3e2b1d25c87` |

## Train evidence recorded before Valid

Prior Train evaluation: 2011-01-04–2016-03-29 (2016 partial), one-way cost 10 bps. These are historical Train observations and are not Valid targets or thresholds: D Net SR ≈ 0.808, ex-2016 ≈ 0.701, annual Net return ≈ 3.716%, turnover/day ≈ 0.03252; SN1 Net SR ≈ 1.063, ex-2016 ≈ 1.009, annual Net return ≈ 4.517%, turnover/day ≈ 0.0077. The prior decomposition is Long-centered and includes lower turnover/cost; Short improvement is not claimed, and SN1 is not described as a Short × Night repair.

Zip Train-only smoke: `train_zip_smoke.json` — PASS. The frozen zip returned finite one-column `(Date, Code)` output and matched saved research SN1 bit-for-bit on 576,535 evaluation rows. The run staged Train input files only and did not access Valid target or raw target.

Prior direct raw reconstruction, float64 recurrence, row shuffle, Parquet round-trip and future-prefix checks are documented in `snapshot/reports/DM-20260927-03/SN1_IMPLEMENTATION_AUDIT.md`; those are numerical/causality checks, not a substitute for the one Valid evaluation.

## Locked execution

`valid_evaluation_lock.json` binds this manifest hash, plan/config hashes, final freeze commit, source hashes, input-manifest hash, and submission zip hash. `research/experiments/sn1_valid_once.py` verifies those values before opening Valid features and creates an exclusive one-run sentinel. It reads the Valid target once only after saving both fixed score streams. A pre-target failure or an existing sentinel aborts; no retry or candidate change is permitted after target access.
