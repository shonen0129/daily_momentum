# DRI regularization research

DM-20260911-03 tests Ridge and alpha-max-relative Elastic Net on unchanged 21-day
DRI vectors (chronological + sorted, 42 features, RAW and market residual variants).
EWMA 0.25 and the official horizon remain fixed. See the experiment's plan/config.

`features.py` preserves the existing DRI definitions but includes its own relisting
helper so that inference is self-contained. `models.py` fits only explicitly supplied
past data, and serializes numeric model/scaler parameters. Inference uses a fixed
feature summation order and never reads a label file.

No production model is selected here. The experiment creates four separate research
copies with `inference_bundle.json` for Train-only standalone smoke checks. These
bundles cover 2011–2016 and are not frozen competition submissions.
