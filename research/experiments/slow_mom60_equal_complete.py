"""Complete audit/decision from immutable evidence; never rerun a performance trial."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import pyarrow
import scipy

from research import firewall
from research.experiments import slow_mom60_equal as experiment
from tools import workspace

ROOT = experiment.ROOT
f = experiment.f
sha, dump, exact = experiment.sha, experiment.dump, experiment.exact


def work(config, output, source, run):
    started = time.monotonic()
    old_run = json.loads((source / "run.json").read_text())
    assert old_run["status"] == "failed" and old_run["actual_trials"] == 1
    assert old_run["failure"] == "ValueError('Cannot mix tz-aware with tz-naive values')"
    assert old_run["experiment_id"] == config["experiment_id"]
    for name in ["plan.md", "config.json"]:
        assert sha(source / name) == sha(output / name) == old_run["snapshot_sha256"][name]
    # Absolutely no change to signal definitions after performance was observed.
    strategy_paths = sorted((ROOT / "stock_comp_2026/strategies" / config["strategy"]).rglob("*.py"))
    for path in strategy_paths:
        assert sha(path) == old_run["code_sha256"][str(path.relative_to(ROOT))]
    old_phases = json.loads((source / "audit/phase_gates.json").read_text())
    assert [p["phase"] for p in old_phases] == ["plan_config_code_freeze", "component_parity", "orthogonality_diagnostics",
                                               "fixed_1_1_1_trial", "incremental_attribution", "turnover_cost_analysis", "bootstrap"]
    stage = output / "feature_stage"
    stage.mkdir()
    for name in f.INPUT_COLUMNS:
        file = ROOT / config["input_dir"] / (name + "_train.parquet")
        assert sha(file) == old_run["train_data_sha256"][file.name]
        (stage / file.name).symlink_to(file)
    # Hash the target as bytes only; no target parser or new accounting is used.
    target = ROOT / config["input_dir"] / "target_1day_train.parquet"
    assert sha(target) == old_run["train_data_sha256"][target.name]
    evidence = [p for sub in ["predictions", "metrics", "audit"] for p in (source / sub).rglob("*") if p.is_file()]
    allowed = [p for p in evidence if p.suffix == ".parquet"]
    allowed += [output / p.relative_to(source) for p in allowed]
    allowed += [ROOT / r["path"] for r in config["saved_components"].values()]
    firewall.install(allowed_artifacts=allowed)
    preserved = {}
    for path in evidence:
        relative = path.relative_to(source)
        to = output / relative
        to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, to)
        assert sha(to) == sha(path)
        preserved[str(relative)] = sha(path)
    code = strategy_paths + [Path(__file__), ROOT / "research/experiments/slow_mom60_equal.py",
                            ROOT / "research/experiments/slow_multifactor.py", ROOT / "research/evaluation.py",
                            ROOT / "research/firewall.py", ROOT / "tools/workspace.py"]
    code += sorted((ROOT / "tests/strategies" / config["strategy"]).rglob("*.py"))
    run.update(status="running", actual_trials=0, cumulative_actual_trials=1, command=sys.argv,
               scientific_source_run=str(source.relative_to(ROOT)), scientific_source_run_json_sha256=sha(source / "run.json"),
               scientific_artifact_sha256=preserved, train_data_sha256=old_run["train_data_sha256"],
               frozen_strategy_code_sha256={str(p.relative_to(ROOT)): sha(p) for p in strategy_paths},
               code_sha256={str(p.relative_to(ROOT)): sha(p) for p in code},
               environment={"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
                            "pyarrow": pyarrow.__version__, "scipy": scipy.__version__, "platform": platform.platform()})
    dump(output / "run.json", run)
    for path in code:
        to = output / "code_snapshot" / path.relative_to(ROOT)
        to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, to)
    dump(output / "audit/scientific_phase_gates.json", old_phases)
    dump(output / "audit/completion_provenance.json", {"scientific_source_run": str(source.relative_to(ROOT)),
        "preserved_sha256": preserved, "new_performance_trials": 0, "cumulative_performance_trials": 1,
        "reason": "Repair audit-only future-row timezone handling. Use identical saved score/metrics/bootstrap, no re-accounting.",
        "frozen_plan_config_equal": True, "strategy_source_unchanged": True,
        "source_run_peak_rss_recorded": False})
    phases = []
    def checkpoint(name, files=()):
        phases.append({"phase": name, "at_utc": experiment.now(), "new_performance_trials": 0,
                       "cumulative_performance_trials": 1, "sha256": {str(p.relative_to(output)): sha(p) for p in files}})
        dump(output / "audit/completion_phase_gates.json", phases)
        print("completion " + name, flush=True)
    checkpoint("preserved_scientific_evidence", [output / "audit/completion_provenance.json"])
    inputs = f.load_train(stage)
    scores, mid = f.components(inputs)
    saved = pd.read_parquet(output / "predictions/component_scores.parquet")
    exact(scores, saved)
    saved_all = pd.read_parquet(output / "predictions/strategy_scores.parquet")
    candidate = f.score(scores)
    exact(candidate, saved_all[experiment.CAND].rename("Return"))
    assert candidate.index.equals(inputs["raw_return_1day"].index)
    dump(output / "audit/completion_rebuild.json", {"status": "PASS", "components_bitwise": True,
        "candidate_saved_bitwise": True, "rows": len(scores), "no_new_performance_evaluation": True})
    dump(output / "audit/source_scan_completion.json", experiment.source_scan(strategy_paths))
    dump(output / "audit/prefix_invariance.json", experiment.causality(inputs, scores, mid, config, output / "audit"))
    adapted = experiment.submission.predict(stage).Return
    exact(candidate, adapted)
    dump(output / "audit/adapter_parity.json", {"status": "PASS", "bitwise": True, "rows": len(candidate),
        "finite": bool(np.isfinite(candidate).all()), "exact_input_output_index": True,
        "self_contained_label_free": True, "stage_files": sorted(p.name for p in stage.iterdir()),
        "no_target_in_stage": True, "deterministic_rebuild": True})
    denied = []
    for filename in ["target_1day_valid.parquet", "raw_target_1day_train.parquet"]:
        try:
            pd.read_parquet(stage / filename)
        except PermissionError as error:
            denied.append({"requested": filename, "result": "DENIED", "reason": str(error)})
        else:
            raise AssertionError("Expected firewall denial: " + filename)
    dump(output / "audit/firewall_denials.json", {"status": "PASS", "cases": denied, "values_parsed": False})
    firewall.save(output / "audit/completion_firewall.json")
    assert all(Path(p).name in [name + "_train.parquet" for name in f.INPUT_COLUMNS] for p in firewall.ACCESSES)
    checkpoint("causality_audit", [output / "audit/prefix_invariance.json", output / "audit/adapter_parity.json"])
    tests = subprocess.run([sys.executable, str(ROOT / "tools/run_bounded.py"), "--seconds", "180", sys.executable,
                            "-m", "pytest", "-q", "tests/strategies/dm_slow_mom60_equal", "tests/strategies/dm_slow_multifactor"],
                           cwd=ROOT, capture_output=True, text=True)
    (output / "logs/tests.log").write_text(tests.stdout + tests.stderr)
    assert tests.returncode == 0, tests.stdout + tests.stderr
    check = subprocess.run(["make", "check"], cwd=ROOT, capture_output=True, text=True)
    (output / "logs/make_check.log").write_text(check.stdout + check.stderr)
    workspace.validate_experiment(ROOT, ROOT / "experiments" / config["experiment_id"])
    frozen_count = 0
    for path in sorted((ROOT / "reports").glob("*/freeze_manifest.json")):
        manifest = json.loads(path.read_text())
        freeze_root = ROOT
        for meta_path in (ROOT / "experiments").glob("*/experiment.json"):
            meta = json.loads(meta_path.read_text())
            if meta.get("freeze_manifest") == str(path.relative_to(ROOT)):
                freeze_root = ROOT / meta["freeze_root"]
                assert sha(path) == meta["freeze_manifest_sha256"]
                assert sha(freeze_root / meta["freeze_manifest"]) == meta["freeze_manifest_sha256"]
        for section in ["code_sha256", "artifact_sha256"]:
            for relative, expected in manifest[section].items():
                assert sha(freeze_root / relative) == expected, relative
                frozen_count += 1
    if check.returncode:
        assert "DM-20261002-04: unknown experiment kind" in check.stdout + check.stderr
    dump(output / "audit/verification.json", {"status": "PASS_WITH_EXISTING_WORKSPACE_METADATA_FAILURE" if check.returncode else "PASS",
        "tests_returncode": tests.returncode, "tests_output": tests.stdout, "own_metadata": "PASS",
        "existing_freeze_hashes": frozen_count, "existing_freeze_hashes_status": "PASS",
        "make_check_returncode": check.returncode, "make_check_output": check.stdout + check.stderr,
        "make_check_limitation": "Preexisting unsupported experiment kind DM-20261002-04. New metadata and all Freeze hashes checked separately; full workspace check not passed."})
    checkpoint("verification", [output / "audit/verification.json"])
    result = pd.read_csv(output / "metrics/metrics.csv", float_precision="round_trip")
    incremental = pd.read_csv(output / "metrics/incremental.csv", float_precision="round_trip")
    score_corr = pd.read_csv(output / "metrics/score_spearman_summary.csv", float_precision="round_trip")
    pl_corr = pd.read_csv(output / "metrics/pl_orthogonality_summary.csv", float_precision="round_trip")
    cost = pd.read_csv(output / "metrics/turnover_cost_analysis.csv", float_precision="round_trip")
    boot = json.loads((output / "metrics/bootstrap.json").read_text())
    verdict = experiment.decision(result, boot)
    dump(output / "metrics/decision.json", verdict)
    checkpoint("decision", [output / "metrics/decision.json"])
    resources = {"elapsed_seconds": time.monotonic() - started,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
        "new_performance_trials": 0, "actual_trials": 1, "valid_evaluation": False,
        "scientific_source_elapsed_wall_seconds": (datetime.fromisoformat(old_run["completed_at_utc"]) - datetime.fromisoformat(old_run["created_at_utc"])).total_seconds(),
        "scientific_source_peak_rss_bytes": None, "execution_timeout_seconds": config["execution_timeout_seconds"]}
    dump(output / "audit/resources.json", resources)
    # No predictions, predecision metrics or bootstrap may have changed in completion.
    for relative, expected in preserved.items():
        if relative.startswith(("predictions/", "metrics/")):
            assert sha(output / relative) == expected, relative
    experiment.report(config, output, result, incremental, score_corr, pl_corr, cost, boot, verdict, resources)
    run.update(status="completed", exit_code=0, completed_at_utc=experiment.now(), decision=verdict, resources=resources,
        artifact_sha256={str(p.relative_to(output)): sha(p) for sub in ["predictions", "metrics", "audit"] for p in (output / sub).rglob("*") if p.is_file()})
    dump(output / "run.json", run)
    print(json.dumps(experiment.shared.safe({"decision": verdict, "resources": resources}), indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    output, source = Path(args.output).resolve(), Path(args.source).resolve()
    run = json.loads((output / "run.json").read_text())
    assert run["status"] == "prepared" and config["max_trials"] == 1
    assert config["trials"] == [{"trial_id": experiment.CAND}]
    assert config["data_split"] == "train" and config["valid_evaluation"] is False
    try:
        work(config, output, source, run)
    except BaseException as error:
        run.update(status="failed", exit_code=1, completed_at_utc=experiment.now(), failure=repr(error))
        dump(output / "run.json", run)
        if firewall._PATCHED:
            firewall.save(output / "audit/completion_firewall.json")
        raise


if __name__ == "__main__":
    main()
