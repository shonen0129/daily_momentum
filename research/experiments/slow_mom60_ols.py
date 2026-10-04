"""One fixed annual expanding OLS trial, immutable factors and Train-only labels."""
from __future__ import annotations

import argparse
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

from research import evaluation, firewall
from research.experiments import slow_mom60_equal as previous
from stock_comp_2026.strategies.dm_slow_mom60_ols import models, submission
from stock_comp_2026.strategies.dm_slow_mom60_ols.component_factors import features as factors
from tools import workspace

ROOT = Path(__file__).resolve().parents[2]
SLOW, MOM, EQUAL, CAND = "SLOW_CONTROL", "MOM60", "SLOW_MOM60_EQUAL", "SLOW_MOM60_OLS"
sha, dump, exact, metrics, table, now = previous.sha, previous.dump, previous.exact, previous.metrics, previous.table, previous.now


def label_maturity(index):
    dates = index.get_level_values("Date")
    calendar = dates.unique().sort_values()
    p = calendar.get_indexer(dates)
    end = np.full(len(index), np.datetime64("NaT"), dtype="datetime64[ns]")
    available = p + 2 < len(calendar)
    end[available] = calendar.to_numpy(dtype="datetime64[ns]")[p[available] + 2]
    return pd.Series(end, index=index, name="maturity")


def mutate_labels(target, maturity, cutoff, seed):
    changed = target.copy()
    mask = maturity.gt(cutoff) | maturity.isna()
    rng = np.random.default_rng(seed)
    values = rng.normal(0, 1e3, int(mask.sum()))
    values[::7] = np.nan
    values[1::11] = 0.
    changed.loc[mask] = values
    return changed


def exact_models(left, right, cutoff_year):
    a = {r["year"]: r for r in left if r["year"] <= cutoff_year}
    b = {r["year"]: r for r in right if r["year"] <= cutoff_year}
    assert a.keys() == b.keys()
    for year in a:
        assert a[year] == b[year], (year, a[year], b[year])
        assert np.array_equal(np.asarray(a[year]["coefficients"]).view(np.uint64),
                              np.asarray(b[year]["coefficients"]).view(np.uint64))


def causality(inputs, target, components, intermediates, ranks, score, records, config, folder):
    maturity = label_maturity(target.index)
    cases = []
    for i, text in enumerate(config["prefix_cutoffs"]):
        cutoff = pd.Timestamp(text)
        prefix = score.index[score.index.get_level_values("Date") <= cutoff]
        for source in list(inputs) + ["Train_labels", "ALL", "TRUNCATION"]:
            changed = dict(inputs)
            labels = target
            for j, (name, frame) in enumerate(inputs.items()):
                if source == "TRUNCATION":
                    changed[name] = frame.loc[previous.source_dates(frame) <= cutoff]
                elif source in [name, "ALL"]:
                    changed[name] = previous.mutate(frame, name, cutoff, config["random_seed"] + i * 100 + j)
            if source in ["Train_labels", "ALL"]:
                labels = mutate_labels(target, maturity, cutoff, config["random_seed"] + i)
            got, mid = factors.components(changed)
            x = factors.factor_ranks(got)
            labels = labels.reindex(x.index)
            if source == "TRUNCATION":
                # The last two signal dates in the prefix have unavailable future labels.
                labels = labels.where(maturity.reindex(x.index).le(cutoff))
            pred, fitted = models.walk_forward(x, labels, years=config["parameters"]["model_years"])
            exact(components.loc[prefix], got.loc[prefix])
            exact(intermediates.loc[prefix], mid.loc[prefix])
            exact(ranks.loc[prefix], x.loc[prefix])
            exact(score.loc[prefix], pred.loc[prefix])
            exact_models(records, fitted, cutoff.year)
            cases.append({"cutoff": text, "source": source, "prefix_rows": len(prefix),
                          "status": "PASS", "bitwise": True, "training_refitted": True,
                          "label_changes_by_t_plus_2_maturity": source in ["Train_labels", "ALL", "TRUNCATION"]})
        dump(folder / "prefix_progress.json", {"status": "running", "cases": cases})
        print("causality " + text + ": features / maturity-aware labels / ALL / truncation PASS", flush=True)
    for name, changed in [("ROW_SHUFFLE", {k: v.sample(frac=1, random_state=config["random_seed"]) for k, v in inputs.items()}),
                          ("DETERMINISTIC_REBUILD", inputs)]:
        got, mid = factors.components(changed)
        x = factors.factor_ranks(got)
        labels = target.sample(frac=1, random_state=config["random_seed"]).sort_index() if name == "ROW_SHUFFLE" else target
        pred, fitted = models.walk_forward(x, labels, years=config["parameters"]["model_years"])
        exact(components, got)
        exact(intermediates, mid)
        exact(ranks, x)
        exact(score, pred)
        exact_models(records, fitted, 2016)
        cases.append({"source": name, "rows": len(score), "status": "PASS", "bitwise": True, "training_refitted": True})
    result = {"status": "PASS", "cases": cases, "comparison": "Exact index/columns/dtype/uint64 bits incl NaNs; full model records and coefficient bits",
              "all_feature_sources": list(inputs), "training_included": True,
              "label_mutation": "maturity>cutoff or unknown, including last2 prefix signal dates, extreme/NaN/zero",
              "no_performance_trials_added": True, "scope": "Tested inputs/cutoffs only; not a universal proof."}
    dump(folder / "prefix_progress.json", result)
    return result


def verdict(result, bootstrap):
    # Apply the exact previously preregistered gate function without modifying it.
    selected = result.loc[result.strategy.isin([CAND, SLOW])].copy()
    selected.loc[selected.strategy == CAND, "strategy"] = previous.CAND
    key = "POOLED:" + CAND + "-" + SLOW
    translated = {"POOLED:" + previous.CAND + "-" + SLOW: bootstrap[key]}
    d = previous.decision(selected, translated)
    d.update(candidate=CAND, gate_source="DM-20261003-05 unchanged conjunctive gates",
             primary_bootstrap_key=key, secondary_comparison=EQUAL)
    return d


def cost_analysis(result):
    rows = []
    for scope in result.scope.unique():
        r = result.loc[result.scope == scope].set_index("strategy")
        c, s = r.loc[CAND], r.loc[SLOW]
        gross, cost = c.annual_gross - s.annual_gross, c.annual_cost - s.annual_cost
        net = c.annual_net - s.annual_net
        assert abs(net - gross + cost) < 1e-14
        rows.append({"scope": scope, "OLS_turnover": c.turnover, "SLOW_turnover": s.turnover,
                     "EQUAL_turnover": r.loc[EQUAL].turnover, "MOM_turnover": r.loc[MOM].turnover,
                     "OLS_SLOW_turnover_ratio": c.turnover / s.turnover,
                     "incremental_annual_gross": gross, "incremental_annual_cost": cost, "incremental_annual_net": net,
                     "incremental_gross_cost_ratio": gross / cost if cost != 0 else np.nan,
                     "incremental_gross_gt_cost": gross > cost,
                     "cost_sign": "positive" if cost > 0 else "negative" if cost < 0 else "zero"})
    return pd.DataFrame(rows)


def verification(output, config):
    test = subprocess.run([sys.executable, str(ROOT / "tools/run_bounded.py"), "--seconds", "180", sys.executable, "-m", "pytest", "-q",
                           "tests/strategies/dm_slow_mom60_ols", "tests/strategies/dm_slow_mom60_equal"], cwd=ROOT, capture_output=True, text=True)
    (output / "logs/tests.log").write_text(test.stdout + test.stderr)
    assert test.returncode == 0, test.stdout + test.stderr
    check = subprocess.run(["make", "check"], cwd=ROOT, capture_output=True, text=True)
    (output / "logs/make_check.log").write_text(check.stdout + check.stderr)
    workspace.validate_experiment(ROOT, ROOT / "experiments" / config["experiment_id"])
    count = 0
    for path in sorted((ROOT / "reports").glob("*/freeze_manifest.json")):
        manifest = json.loads(path.read_text())
        frozen = ROOT
        for meta_path in (ROOT / "experiments").glob("*/experiment.json"):
            meta = json.loads(meta_path.read_text())
            if meta.get("freeze_manifest") == str(path.relative_to(ROOT)):
                frozen = ROOT / meta["freeze_root"]
                assert sha(path) == meta["freeze_manifest_sha256"]
                assert sha(frozen / meta["freeze_manifest"]) == meta["freeze_manifest_sha256"]
        for part in ["code_sha256", "artifact_sha256"]:
            for relative, expected in manifest[part].items():
                assert sha(frozen / relative) == expected
                count += 1
    if check.returncode:
        assert "DM-20261002-04: unknown experiment kind" in check.stdout + check.stderr
    return {"status": "PASS_WITH_EXISTING_WORKSPACE_METADATA_FAILURE" if check.returncode else "PASS",
            "tests_returncode": test.returncode, "tests_output": test.stdout, "own_metadata": "PASS",
            "existing_freeze_hashes": count, "existing_freeze_hashes_status": "PASS",
            "make_check_returncode": check.returncode, "make_check_output": check.stdout + check.stderr,
            "limitation": "Full workspace check has preexisting DM-20261002-04 metadata failure; not passed. No edits to that experiment."}


def report(config, output, result, incremental, cost, coefficients, bootstrap, decision, resources):
    folder = ROOT / config["report_dir"]
    folder.mkdir(exist_ok=True)
    if (folder / "REPORT.md").exists():
        raise FileExistsError("Do not overwrite an already completed report")
    for sub in ["metrics", "audit"]:
        for path in (output / sub).rglob("*"):
            if path.is_file():
                to = folder / path.relative_to(output)
                to.parent.mkdir(parents=True, exist_ok=True)
                if to.exists():
                    assert sha(to) == sha(path), "Existing report evidence changed: " + str(to)
                else:
                    shutil.copyfile(path, to)
    pooled = result.loc[result.scope == "POOLED"]
    ex = result.loc[result.scope == "EX2016"]
    annual = result.loc[result.scope.isin([str(y) for y in range(2011, 2017)])]
    primary = bootstrap["POOLED:" + CAND + "-" + SLOW]
    secondary = bootstrap["POOLED:" + CAND + "-" + EQUAL]
    cc = cost.loc[cost.scope == "POOLED"].iloc[0]
    gates = pd.DataFrame([{"gate": k, "passed": v} for k, v in decision["checks"].items()])
    text = [f'# {config["experiment_id"]}: annual OLS on Size / Illiquidity / MOM60 ranks', "",
            f'**{decision["decision"]}**。OLS1候補、rescue0。Historical Valid / Validは未読・未評価。Run=`{output.relative_to(ROOT)}`。', "",
            'ユーザーが別実験としてOLS1候補を明示的に指定。等ウェイト版の不採用判定は変更していない。全Trainは既知研究データであり、未使用holdoutとは呼ばない。', "",
            'Inputは以前とbitwise同一のSizeRank/IlliquidityRank/MOM60Rank。教師は主催者提供のraw residual Return。OLSはintercept+3係数、stock-day等ウェイト、expanding、年1回更新、np.linalg.lstsq(rcond=None)。regularization・係数clip・符号制約・追加smoothingなし。2008はneutral0、2009–2010にpast-onlyモデルで建玉を開始し、評価は2011以降。', "",
            '## POOLED', "", table(pooled, ["strategy", "days", "rankic", "rankic_t_hac5", "rankic_hit", "gross_sharpe", "net_sharpe", "annual_gross", "annual_net", "turnover", "annual_cost", "max_drawdown", "annual_long_net", "annual_short_net"]), "",
            '## EX2016', "", table(ex, ["strategy", "net_sharpe", "annual_gross", "annual_net", "turnover", "annual_cost", "max_drawdown", "annual_long_net", "annual_short_net"]), "",
            '## Annual walk-forward', "", table(annual, ["strategy", "scope", "days", "net_sharpe", "annual_gross", "annual_net", "turnover", "annual_cost", "max_drawdown"]), "",
            f'2011–2015 Net Sharpe改善 vs SLOW: **{decision["full_year_net_sharpe_improvements"]}/5**。2016 partialは除外。Q1–Q5/monotonicity、Long/Short gross/netとすべての期間実額はmetrics.csvに保存。', "",
            table(pooled, ["strategy", "q1_daily_return", "q2_daily_return", "q3_daily_return", "q4_daily_return", "q5_daily_return", "q_monotonicity", "annual_long", "annual_long_net", "annual_short", "annual_short_net"]), "",
            '## Learned coefficients and stability', "", table(coefficients, ["year", "rows", "training_sessions", "design_rank", "condition_number", "intercept", "SizeRank", "IlliquidityRank", "MOM60Rank", "MOM60Rank_signed_abs_share"]), "",
            '係数はsame-scale rankの条件付き寄与で、portfolio sleeve weightsではない。signed_abs_shareはβ/sum(abs(3β))という参考表示のみ。負符号もOLSの推定結果として保持し、成績を見て変更しない。warmupのrank deficiencyは固定lstsq最小ノルム、後年のcondition/rankも保存。', "",
            '## Incremental gross / cost', "", table(incremental.loc[incremental.scope.isin(["POOLED", "EX2016"])],
                  ["comparison", "scope", "delta_rankic", "delta_gross_sharpe", "delta_net_sharpe", "delta_annual_gross", "delta_annual_cost", "delta_annual_net", "delta_turnover", "delta_annual_long_net", "delta_annual_short_net", "delta_max_drawdown"]), "",
            table(cost, ["scope", "SLOW_turnover", "EQUAL_turnover", "OLS_turnover", "OLS_SLOW_turnover_ratio", "incremental_annual_gross", "incremental_annual_cost", "incremental_annual_net", "incremental_gross_cost_ratio", "incremental_gross_gt_cost"]), "",
            f'POOLED OLS−SLOW: Δannual gross={cc.incremental_annual_gross*10000:.2f}bp、Δannual cost={cc.incremental_annual_cost*10000:.2f}bp、Δannual net={cc.incremental_annual_net*10000:.2f}bp。Δgross>Δcost={bool(cc.incremental_gross_gt_cost)}。turnover ratio={cc.OLS_SLOW_turnover_ratio:.6f}。', "",
            'OLSはraw return squared errorを最小化し、cost/Net Sharpeを直接最適化しない。観測Δgrossはweight再配分の損益差、Δcostは公式turnover差。Δnet=Δgross−Δcostを照合。追加gross alphaとcost節約を区別し、係数の大小や低相関だけで採用しない。', "",
            '## Bootstrap and fixed gates', "",
            f'paired circular20 sessions、reps2000、seed20261003、95% percentile。Primary pooled OLS−SLOW ΔNetSR={primary["observed_delta"]:.6f}、CI=[{primary["low"]:.6f},{primary["high"]:.6f}]。Secondary OLS−EQUAL={secondary["observed_delta"]:.6f}、CI=[{secondary["low"]:.6f},{secondary["high"]:.6f}]。MOM referenceとEX2016も保存。実現walk-forward日次損益に条件付けたCIで、bootstrapでモデルを再fitせず、既知Trainの学習/選択不確実性全体を表すものではない。', "",
            table(gates, ["gate", "passed"]), "",
            f'採否: **{decision["decision"]}**。前回と同じSLOW比較gateをすべて要求し、等ウェイト版を上回るだけでは採用しない。追加候補・Ridge・window/target/weight searchは実行せず終了。', "",
            '## Causality / contract / reproducibility', "",
            '全6特徴入力源とTrain labelsを個別/同時にfuture-mutateし、truncation、row shuffle、決定的再fitを検証。feature/raw/normalized/rank/予測とprefixで利用される全annual model records/係数bitsが完全一致。label改変はt+2 maturity>cutoffで決め、prefix最後2signalの未成熟targetも変更。固定モデルだけの監査ではない。モデルごとの最大label maturity<fold first prediction dayを記録。', "",
            'targetのない6ファイルstageでstored-artifact inferenceがresearchとbitwise一致し、standalone adapterもsmoke。全入力Date/Code index、finite coverage、NaN/inf、source scanとTrain-only firewall、Valid/raw target拒否を確認。新candidateのweightとdaily Netは公式compute_weight/compute_plとuint64 bits一致。controlsは同一入力/target/scoreと同じaccounting関数を持つ前実験の保存済み結果をhash固定して再利用。', "",
            'Continuous full-panel建玉でaccounting後、各年最後2exchange sessionsをpurge。Sharpe=mean/sample SD×sqrt252、IC=daily average-tie Spearman、t=HAC5 Bartlett、annual=mean×252、period=実額。Compound DDはwealth1、Q1→Q5はscore昇順、Long=Q4/Q5、Short=Q1/Q2。公式missing-target行のcost欠落を再現し、all-position costも併記。', "",
            'make checkは既存DM-20261002-04 metadata種別で失敗。新experimentのmetadataと既存Freeze129 hashは別途照合；全workspace構成検査を合格とは扱わない。監査は試した入力/cutoffの証拠であり普遍的な数学的証明ではない。', "",
            f'Elapsed={resources["elapsed_seconds"]:.2f}s、peak RSS={resources["peak_rss_bytes"]/1024**2:.1f}MiB、deadline1800s。コード/入力/config/モデル/予測/metrics/auditとlibrary versionsをrun.jsonに記録。Valid/zip/release/外部提出は実施していない。']
    (folder / "REPORT.md").write_text("\n".join(text) + "\n")
    exp = ROOT / "experiments" / config["experiment_id"]
    (exp / "decision.md").write_text(f'# {config["experiment_id"]}: {decision["decision"]}\n\n'
        f'[Report](../../{config["report_dir"]}/REPORT.md). OLS1候補、rescue0、Train-only。\n\n'
        f'Primary pooled ΔNetSR={primary["observed_delta"]:.6f}, CI=[{primary["low"]:.6f},{primary["high"]:.6f}]; '
        f'full-year improvement {decision["full_year_net_sharpe_improvements"]}/5.\n\n' + table(gates, ["gate", "passed"]) + '\n')
    meta = json.loads((exp / "experiment.json").read_text())
    meta.update(status="completed" if decision["all_passed"] else "rejected", actual_trials=1, run_id=output.name,
                report=config["report_dir"] + "/REPORT.md")
    dump(exp / "experiment.json", meta)
    if not decision["all_passed"]:
        with (ROOT / "experiments/GRAVEYARD.md").open("a") as stream:
            stream.write(f'\n## {config["experiment_id"]}: fixed annual three-factor OLS\n\n'
                         f'Reject; NetSR full-year improvement {decision["full_year_net_sharpe_improvements"]}/5; '
                         f'primary CI [{primary["low"]:.6f},{primary["high"]:.6f}]. '
                         f'[Decision]({config["experiment_id"]}/decision.md). One OLS candidate, zero rescue, no Valid.\n')


def work(config, output, run):
    started = time.monotonic()
    stage = output / "stage"
    stage.mkdir()
    names = list(factors.INPUT_COLUMNS) + ["target_1day"]
    for name in names:
        (stage / (name + "_train.parquet")).symlink_to(ROOT / config["input_dir"] / (name + "_train.parquet"))
    refs = {name: ROOT / r["path"] for name, r in config["saved_evidence"].items()}
    for name, path in refs.items():
        assert sha(path) == config["saved_evidence"][name]["sha256"]
    prior_manifest = json.loads(refs["prior_manifest"].read_text())
    input_hash = {name + "_train.parquet": sha(stage / (name + "_train.parquet")) for name in names}
    assert input_hash == prior_manifest["train_data_sha256"]
    strategy_paths = sorted((ROOT / "stock_comp_2026/strategies" / config["strategy"]).rglob("*.py"))
    code = strategy_paths + [Path(__file__), ROOT / "research/experiments/slow_mom60_equal.py",
        ROOT / "research/experiments/slow_multifactor.py", ROOT / "research/evaluation.py", ROOT / "research/firewall.py",
        ROOT / "stock_comp_2026/evaluate_script.py", ROOT / "tools/workspace.py"]
    code += sorted((ROOT / "tests/strategies" / config["strategy"]).rglob("*.py"))
    run.update(status="running", actual_trials=0, command=sys.argv,
        code_sha256={str(p.relative_to(ROOT)): sha(p) for p in code}, train_data_sha256=input_hash,
        environment={"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
                     "pyarrow": pyarrow.__version__, "scipy": scipy.__version__, "platform": platform.platform()})
    dump(output / "run.json", run)
    for path in code:
        to = output / "code_snapshot" / path.relative_to(ROOT)
        to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, to)
    phases = []
    def checkpoint(name, files=()):
        phases.append({"phase": name, "at_utc": now(), "actual_trials": run["actual_trials"],
                       "sha256": {str(p.relative_to(output)): sha(p) for p in files}})
        dump(output / "audit/phase_gates.json", phases)
        dump(output / "run.json", run)
        print("phase " + name, flush=True)
    dump(output / "audit/pre_result_lock.json", {"at_utc": now(), "plan_sha256": sha(output / "plan.md"),
        "config_sha256": sha(output / "config.json"), "code_sha256": run["code_sha256"], "max_trials": 1, "target_parsed": False})
    checkpoint("plan_config_code_freeze", [output / "plan.md", output / "config.json"])
    for rel, expected in run["snapshot_sha256"].items():
        assert sha(output / rel) == expected
    scan = previous.source_scan(strategy_paths)
    scan["manual_review"] = "Immutable PIT/causal features and label-free artifact inference; models.fit_year accepts explicit Train labels only, maturity+2 strictly before annual prediction start, expanding lstsq without future fit."
    dump(output / "audit/source_scan.json", scan)
    frozen_parquets = []
    for path in (ROOT / "reports").glob("*/freeze_manifest.json"):
        manifest = json.loads(path.read_text())
        for section in ["code_sha256", "artifact_sha256"]:
            for rel in manifest[section]:
                if rel.endswith(".parquet"):
                    # These are hashed by make/check-freeze verification only, never decoded here.
                    for mpath in (ROOT / "experiments").glob("*/experiment.json"):
                        meta = json.loads(mpath.read_text())
                        if meta.get("freeze_manifest") == str(path.relative_to(ROOT)):
                            frozen_parquets.append(ROOT / meta["freeze_root"] / rel)
    firewall.install(allowed_artifacts=[p for p in refs.values() if p.suffix == ".parquet"] + frozen_parquets + [
        output / "predictions/component_scores.parquet", output / "predictions/factor_ranks.parquet", output / "predictions/strategy_scores.parquet"])
    inputs = factors.load_train(stage)
    components, intermediates = factors.components(inputs)
    ranks = factors.factor_ranks(components)
    saved_components = pd.read_parquet(refs["components"])
    saved_ranks = pd.read_parquet(refs["ranks"])
    exact(components, saved_components)
    exact(ranks, saved_ranks)
    saved_scores = pd.read_parquet(refs["scores"])
    exact(components[[SLOW, MOM]], saved_scores[[SLOW, MOM]])
    exact(factors.score(components), saved_scores[EQUAL].rename("Return"))
    copies = []
    src = ROOT / "stock_comp_2026/strategies/dm_slow_mom60_equal"
    dst = ROOT / "stock_comp_2026/strategies/dm_slow_mom60_ols/component_factors"
    for path in src.rglob("*.py"):
        copied = dst / path.relative_to(src)
        assert path.read_bytes() == copied.read_bytes()
        copies.append({"original": str(path.relative_to(ROOT)), "copy": str(copied.relative_to(ROOT)), "sha256": sha(path)})
    assert components.index.equals(inputs["raw_return_1day"].index)
    assert not any("target_1day" in p for p in firewall.ACCESSES)
    components.to_parquet(output / "predictions/component_scores.parquet")
    ranks.to_parquet(output / "predictions/factor_ranks.parquet")
    dump(output / "audit/component_parity.json", {"status": "PASS", "bitwise_components": True, "bitwise_ranks": True,
        "bitwise_controls": True, "copies": copies, "rows": len(components), "target_not_parsed_during_features": True})
    checkpoint("component_rank_parity", [output / "audit/component_parity.json"])
    target = pd.read_parquet(stage / "target_1day_train.parquet")["Return"].sort_index()
    assert target.index.equals(ranks.index)
    score, records = models.walk_forward(ranks, target, years=config["parameters"]["model_years"], model_dir=output / "models")
    assert np.isfinite(score).all() and score.index.equals(target.index)
    for model in records:
        assert pd.Timestamp(model["max_label_maturity_date"]) < pd.Timestamp(model["fold_start"])
    dump(output / "audit/training_maturity.json", {"status": "PASS", "models": records, "strict_t_plus_2_maturity": True})
    coefficients = []
    for r in records:
        beta = np.array(r["coefficients"])
        scale = np.abs(beta[1:]).sum()
        coefficients.append({**{k: r[k] for k in ["year", "rows", "training_sessions", "design_rank", "condition_number", "training_mse", "max_label_maturity_date"]},
            "intercept": beta[0], **{n: beta[i + 1] for i, n in enumerate(models.RANK_COLUMNS)},
            **{n + "_signed_abs_share": beta[i + 1] / scale if scale else 0. for i, n in enumerate(models.RANK_COLUMNS)}})
    coefficients = pd.DataFrame(coefficients)
    coefficients.to_csv(output / "metrics/annual_coefficients.csv", index=False)
    scores = saved_scores[[SLOW, MOM, EQUAL]].copy()
    scores[CAND] = score
    scores.to_parquet(output / "predictions/strategy_scores.parquet")
    run["actual_trials"] = 1
    checkpoint("one_annual_OLS_candidate", [output / "predictions/strategy_scores.parquet", output / "metrics/annual_coefficients.csv"])
    calendar = ranks.index.get_level_values("Date").unique().sort_values()
    dates = previous.maturity(inputs, target, calendar, output / "audit")
    d, receipt = previous.account(score, target)
    d.to_csv(output / f"metrics/daily_{CAND}.csv", index_label="Date")
    result = pd.read_csv(refs["metrics"], float_precision="round_trip")
    assert set(result.strategy) == {SLOW, MOM, EQUAL}
    candidate_rows = pd.DataFrame([{"strategy": CAND, "scope": scope, **metrics(d.loc[ds])} for scope, ds in previous.scopes(dates)])
    result = pd.concat([result, candidate_rows], ignore_index=True)
    accounts = {CAND: d}
    for name in [SLOW, MOM, EQUAL]:
        path = refs["daily_" + name]
        accounts[name] = pd.read_csv(path, index_col="Date", parse_dates=True, float_precision="round_trip")
        assert accounts[name].index.equals(d.index)
        for scope, ds in previous.scopes(dates):
            old = result.loc[(result.strategy == name) & (result.scope == scope)].iloc[0]
            recalculated = metrics(accounts[name].loc[ds])
            for col, value in recalculated.items():
                assert old[col] == value, (name, scope, col, old[col], value)
        shutil.copyfile(path, output / f"metrics/daily_{name}.csv")
    result.to_csv(output / "metrics/metrics.csv", index=False)
    increments = []
    for scope, _ in previous.scopes(dates):
        c = result.loc[(result.strategy == CAND) & (result.scope == scope)].iloc[0]
        for base in [SLOW, EQUAL, MOM]:
            b = result.loc[(result.strategy == base) & (result.scope == scope)].iloc[0]
            increments.append({"comparison": CAND + "-" + base, "scope": scope,
                **{"delta_" + col: c[col] - b[col] for col in result if col not in ["strategy", "scope"]}})
    incremental = pd.DataFrame(increments)
    incremental.to_csv(output / "metrics/incremental.csv", index=False)
    cost = cost_analysis(result)
    cost.to_csv(output / "metrics/turnover_cost_analysis.csv", index=False)
    dump(output / "audit/official_accounting.json", {"status": "PASS", "candidate": receipt,
        "controls": "Hash-fixed identical inputs/target/score and identical previous.account/evaluation functions; daily CSV metrics exactly reproduced",
        "prior_run": config["prior_run"], "reused_controls": [SLOW, EQUAL, MOM]})
    checkpoint("official_accounting_metrics_cost", [output / "metrics/metrics.csv", output / "metrics/incremental.csv"])
    boot = {}
    for scope, ds in previous.scopes(dates)[:2]:
        for base in [SLOW, EQUAL, MOM]:
            boot[scope + ":" + CAND + "-" + base] = {
                **evaluation.bootstrap_delta(accounts[base].loc[ds].net, d.loc[ds].net,
                    **{k: config["bootstrap"][k] for k in ["block", "reps", "seed"]}),
                "observed_delta": evaluation.sharpe(d.loc[ds].net) - evaluation.sharpe(accounts[base].loc[ds].net),
                "days": len(ds), "primary": scope == "POOLED" and base == SLOW, "bootstrap_refit": False}
    dump(output / "metrics/bootstrap.json", boot)
    pd.DataFrame([{"comparison": k, **v} for k, v in boot.items()]).to_csv(output / "metrics/bootstrap.csv", index=False)
    checkpoint("paired_bootstrap", [output / "metrics/bootstrap.json"])
    dump(output / "audit/prefix_invariance.json", causality(inputs, target, components, intermediates, ranks, score, records, config, output / "audit"))
    feature_stage = output / "feature_stage"
    feature_stage.mkdir()
    for name in factors.INPUT_COLUMNS:
        (feature_stage / (name + "_train.parquet")).symlink_to(stage / (name + "_train.parquet"))
    adapted = submission.predict(feature_stage, output / "models").Return
    exact(score, adapted)
    # Standalone package smoke with no Train labels available to the subprocess.
    bundle = output / "inference_bundle"
    shutil.copytree(ROOT / "stock_comp_2026/strategies" / config["strategy"], bundle, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(output / "models", bundle / "models")
    command = [sys.executable, "-c", "import submission,sys; submission.predict(sys.argv[1]).to_parquet(sys.argv[2])",
               str(feature_stage), str(output / "predictions/standalone_scores.parquet")]
    smoke = subprocess.run(command, cwd=bundle, capture_output=True, text=True)
    (output / "logs/standalone.log").write_text(smoke.stdout + smoke.stderr)
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    firewall.install(allowed_artifacts=[output / "predictions/standalone_scores.parquet"])
    exact(score, pd.read_parquet(output / "predictions/standalone_scores.parquet").Return)
    dump(output / "audit/contract_adapter.json", {"status": "PASS", "rows": len(score), "dates": len(calendar),
        "codes": score.index.get_level_values("Code").nunique(), "exact_index": True, "finite": True, "coverage": 1.,
        "stored_models_inference_bitwise": True, "standalone_bitwise": True, "target_absent_from_inference_stage": True})
    denied = []
    for name in ["target_1day_valid.parquet", "raw_target_1day_train.parquet"]:
        try:
            pd.read_parquet(feature_stage / name)
        except PermissionError as error:
            denied.append({"requested": name, "result": "DENIED", "reason": str(error)})
        else:
            raise AssertionError("Expected firewall denial")
    dump(output / "audit/firewall_denials.json", {"status": "PASS", "values_parsed": False, "cases": denied})
    firewall.save(output / "audit/firewall.json")
    assert not any("_valid" in p.lower() or "raw_target" in p.lower() for p in firewall.ACCESSES)
    checkpoint("learning_causality_contract", [output / "audit/prefix_invariance.json", output / "audit/contract_adapter.json"])
    dump(output / "audit/verification.json", verification(output, config))
    decision = verdict(result, boot)
    dump(output / "metrics/decision.json", decision)
    checkpoint("decision", [output / "metrics/decision.json"])
    resources = {"elapsed_seconds": time.monotonic() - started,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
        "actual_trials": 1, "rescue_trials": 0, "valid_evaluation": False, "execution_timeout_seconds": config["execution_timeout_seconds"]}
    dump(output / "audit/resources.json", resources)
    report(config, output, result, incremental, cost, coefficients, boot, decision, resources)
    for rel, expected in run["code_sha256"].items():
        assert sha(ROOT / rel) == expected
    run.update(status="completed", exit_code=0, completed_at_utc=now(), decision=decision, resources=resources,
        artifact_sha256={str(p.relative_to(output)): sha(p) for sub in ["predictions", "models", "metrics", "audit"]
                        for p in (output / sub).rglob("*") if p.is_file()})
    dump(output / "run.json", run)
    print(json.dumps(previous.shared.safe({"decision": decision, "resources": resources}), indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    output = Path(args.output).resolve()
    run = json.loads((output / "run.json").read_text())
    assert run["status"] == "prepared" and config["data_split"] == "train" and config["valid_evaluation"] is False
    assert config["max_trials"] == 1 and config["trials"] == [{"trial_id": CAND}]
    assert config["parameters"]["model_years"] == list(range(2009, 2017))
    assert config["parameters"]["regularization"] is None and config["parameters"]["target"] == "raw_residual_return"
    try:
        work(config, output, run)
    except BaseException as error:
        run.update(status="failed", exit_code=1, completed_at_utc=now(), failure=repr(error),
                   resources={"peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)})
        dump(output / "run.json", run)
        if firewall._PATCHED:
            firewall.save(output / "audit/firewall.json")
        raise


if __name__ == "__main__":
    main()
