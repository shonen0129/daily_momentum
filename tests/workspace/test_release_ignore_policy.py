"""Ensure a new release's evidence is trackable and generated payloads stay ignored."""
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def is_ignored(relative_path):
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", "--", relative_path],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    return result.returncode == 0


def test_release_manifests_and_source_are_trackable_but_payloads_are_ignored():
    trackable = (
        "releases/DM-CI-POLICY-v1/freeze_manifest.json",
        "releases/DM-CI-POLICY-v1/README.md",
        "releases/DM-CI-POLICY-v1/snapshot/strategy/features.py",
    )
    ignored = (
        "releases/DM-CI-POLICY-v1/submission.zip",
        "releases/DM-CI-POLICY-v1/snapshot/models/fold_model.txt",
        "releases/DM-CI-POLICY-v1/artifacts/run-1/predictions.parquet",
        "releases/DM-CI-POLICY-v1/valid-evaluation/input_stage/feature.parquet",
        "releases/DM-CI-POLICY-v1/valid-evaluation/daily_metrics.csv",
    )

    assert all(not is_ignored(path) for path in trackable)
    assert all(is_ignored(path) for path in ignored)
