"""Finalize a report-only failure from identical completed scientific artifacts."""
import argparse
import json
from pathlib import Path
import resource
import shutil
import sys
import time

import pandas as pd

from research import firewall
from research.experiments import slow_mom60_ols as experiment

ROOT = experiment.ROOT
sha, dump, now = experiment.sha, experiment.dump, experiment.now


def work(config, output, source, run):
    started = time.monotonic()
    old = json.loads((source / "run.json").read_text())
    assert old["status"] == "failed" and old["actual_trials"] == 1
    assert "MOM60_signed_abs_share" in old["failure"]
    assert old["experiment_id"] == config["experiment_id"]
    for name in ["plan.md", "config.json"]:
        assert sha(source / name) == sha(output / name) == old["snapshot_sha256"][name]
    paths = sorted((ROOT / "stock_comp_2026/strategies" / config["strategy"]).rglob("*.py"))
    for path in paths:
        assert sha(path) == old["code_sha256"][str(path.relative_to(ROOT))]
    # Only the report function changed after the scientific run.
    current = experiment.previous.function_sources(ROOT / "research/experiments/slow_mom60_ols.py")
    snapshot = experiment.previous.function_sources(source / "code_snapshot/research/experiments/slow_mom60_ols.py")
    assert current.keys() == snapshot.keys()
    changed = [k for k in current if current[k] != snapshot[k]]
    assert changed == ["report"], changed
    phases = json.loads((source / "audit/phase_gates.json").read_text())
    assert phases[-1]["phase"] == "decision"
    assert json.loads((source / "audit/prefix_invariance.json").read_text())["status"] == "PASS"
    assert json.loads((source / "audit/contract_adapter.json").read_text())["status"] == "PASS"
    evidence = [p for sub in ["predictions", "models", "metrics", "audit"] for p in (source / sub).rglob("*") if p.is_file()]
    firewall.install(allowed_artifacts=[p for p in evidence if p.suffix == ".parquet"] +
        [output / p.relative_to(source) for p in evidence if p.suffix == ".parquet"])
    hashes = {}
    for path in evidence:
        to = output / path.relative_to(source)
        to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, to)
        assert sha(path) == sha(to)
        hashes[str(path.relative_to(source))] = sha(path)
    code = paths + [Path(__file__), ROOT / "research/experiments/slow_mom60_ols.py"]
    for path in code:
        to = output / "code_snapshot" / path.relative_to(ROOT)
        to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, to)
    run.update(status="running", actual_trials=0, cumulative_actual_trials=1, command=sys.argv,
        scientific_source_run=str(source.relative_to(ROOT)), scientific_source_run_sha256=sha(source / "run.json"),
        scientific_artifact_sha256=hashes, original_scientific_code_sha256=old["code_sha256"],
        code_sha256={str(p.relative_to(ROOT)): sha(p) for p in code}, train_data_sha256=old["train_data_sha256"], environment=old["environment"])
    dump(output / "run.json", run)
    provenance = {"status": "PASS", "scientific_source_run": str(source.relative_to(ROOT)),
        "new_performance_trials": 0, "cumulative_performance_trials": 1,
        "strategy_source_plan_config_unchanged": True, "changed_driver_functions": changed,
        "change": "Report column MOM60_signed_abs_share corrected to existing MOM60Rank_signed_abs_share; add-only report evidence copy",
        "preserved_sha256": hashes, "training_backtest_bootstrap_audits_rerun": False}
    dump(output / "audit/report_completion_provenance.json", provenance)
    read = lambda name: pd.read_csv(output / "metrics" / name, float_precision="round_trip")
    result = read("metrics.csv")
    incremental = read("incremental.csv")
    cost = read("turnover_cost_analysis.csv")
    coefficients = read("annual_coefficients.csv")
    bootstrap = json.loads((output / "metrics/bootstrap.json").read_text())
    decision = json.loads((output / "metrics/decision.json").read_text())
    # Decision can be verified from saved values; no P/L or candidate recomputation.
    assert decision == experiment.verdict(result, bootstrap)
    resources = json.loads((output / "audit/resources.json").read_text())
    experiment.report(config, output, result, incremental, cost, coefficients, bootstrap, decision, resources)
    firewall.save(output / "audit/report_completion_firewall.json")
    assert not firewall.ACCESSES, "Report completion must not decode Train input parquets"
    for rel, expected in hashes.items():
        assert sha(output / rel) == expected, rel
        assert sha(source / rel) == expected, rel
    completion_resource = {"elapsed_seconds": time.monotonic() - started,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
        "new_performance_trials": 0, "cumulative_performance_trials": 1, "valid_evaluation": False}
    dump(output / "audit/report_completion_resources.json", completion_resource)
    run.update(status="completed", exit_code=0, completed_at_utc=now(), decision=decision,
        scientific_resources=resources, completion_resources=completion_resource,
        artifact_sha256={str(p.relative_to(output)): sha(p) for sub in ["predictions", "models", "metrics", "audit"]
                        for p in (output / sub).rglob("*") if p.is_file()})
    dump(output / "run.json", run)
    print(json.dumps(experiment.previous.shared.safe({"decision": decision, "scientific_resources": resources,
                                                    "completion_resources": completion_resource}), indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    output, source = Path(args.output).resolve(), Path(args.source).resolve()
    run = json.loads((output / "run.json").read_text())
    assert run["status"] == "prepared"
    assert config["max_trials"] == 1 and config["data_split"] == "train" and config["valid_evaluation"] is False
    try:
        work(config, output, source, run)
    except BaseException as error:
        run.update(status="failed", exit_code=1, completed_at_utc=now(), failure=repr(error))
        dump(output / "run.json", run)
        raise


if __name__ == "__main__":
    main()
