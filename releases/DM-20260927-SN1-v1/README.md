# DM-20260927-SN1-v1

Frozen formal implementation of `SIDE_SOURCE_SEPARATION` (SN1). The Valid comparison is restricted to `D_LOW_FAST_ONLY` and SN1 and is governed by `experiments/DM-20260927-03/VALID_EVALUATION_PLAN.md`.

Contents:

- `SN1_SUBMISSION.zip`: competition submission package. Its default `predict()` returns SN1.
- `snapshot/`: source, fixed Train research lineage, and pre-registered evaluation documents.
- `freeze_hashes.json`: SHA-256 inventory of source, plan, config, input manifest, and zip.
- `environment.json`: local run environment.
- `train_zip_smoke.json`: Train-only zip contract and exact-score parity check.
- `SN1_FREEZE_MANIFEST.md` and `valid_evaluation_lock.json`: created after the scoped source commit and before the one Valid evaluation.

The release directory is a local freeze record; it does not itself mean that a result passed or that an external submission was made.
