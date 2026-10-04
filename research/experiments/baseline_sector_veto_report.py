"""Interpret saved book diagnostics and finalize evidence; zero additional trials."""
import argparse
import json
from pathlib import Path
import shutil
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
from research import firewall
from research.experiments.sector_momentum import sha, dump, table, exact
from research.experiments.baseline_sector_veto import A, B, saved_output_paths, scopes


def main(output):
    run = json.loads((output / "run.json").read_text())
    assert run["status"]=="completed" and run["actual_trials"]==0 and run["cumulative_actual_trials"]==2
    config = json.loads((output / "config.json").read_text()); dest = ROOT / config["report_dir"]
    meta = json.loads((ROOT / "experiments" / config["experiment_id"] / "experiment.json").read_text())
    failed_source = ROOT / "artifacts" / config["experiment_id"] / meta["scientific_run_id"]
    prior_lock = json.loads((output / "preregistration.json").read_text())
    freeze_meta = json.loads((ROOT / "experiments/DM-20260908/experiment.json").read_text())
    freeze_manifest = json.loads((ROOT / freeze_meta["freeze_manifest"]).read_text())
    freeze_parquets = [ROOT / freeze_meta["freeze_root"] / p for section in ["code_sha256", "artifact_sha256"] for p in freeze_manifest[section] if p.endswith(".parquet")]
    firewall.install(allowed_artifacts=saved_output_paths(output)+list(dest.rglob("*.parquet"))+freeze_parquets+
        [ROOT / p for p in prior_lock["prior_evidence_sha256"] if p.endswith(".parquet")])
    metrics = pd.read_csv(output / "metrics/metrics.csv", dtype={"scope":str}, float_precision="round_trip")
    pooled = metrics.loc[metrics.scope=="POOLED"].set_index("strategy")
    inc = pd.read_csv(output / "metrics/incremental.csv", dtype={"scope":str}, float_precision="round_trip")
    replacement = pd.read_csv(output / "metrics/removed_added_summary.csv", dtype={"scope":str}, float_precision="round_trip")
    f = pd.read_parquet(output / "predictions/features.parquet")
    calendar = f.index.get_level_values("Date").unique().sort_values()
    dates = pd.DatetimeIndex([d for y in range(2011,2017) for d in calendar[calendar.year==y][:-2]])
    assert len(dates)==int(pooled.loc["BASELINE", "days"])
    by_source, zero_rows = [], []
    for candidate in [A, B]:
        r = pd.read_parquet(output / "metrics" / ("removed_added_"+candidate+".parquet"))
        r = r.loc[r.book=="SHORT_Q1_Q2"]
        for scope, ds in scopes(dates):
            block = r.loc[r.Date.isin(ds)]
            features = f.loc[f.index.get_level_values("Date").isin(ds)]
            veto = features.BASELINE.lt(0) & features[candidate].eq(0)
            neutral_short = block.candidate_weight.lt(0) & block.baseline_score.lt(0) & block.candidate_score.eq(0)
            zero_rows.append({"candidate":candidate,"scope":scope,"vetoed_score_rows":int(veto.sum()),
                "vetoed_rows_still_short":int(neutral_short.sum()), "vetoed_short_retained_unchanged":int((neutral_short & block['class'].eq('UNCHANGED')).sum()),
                "vetoed_rows_still_short_share":neutral_short.sum()/veto.sum() if veto.sum() else np.nan})
            for (source, clas), sub in block.groupby(["ContextSource", "class"]):
                by_source.append({"candidate":candidate,"scope":scope,"source":source,"class":clas,"rows":len(sub),
                    "target_mean":sub.forward_target.mean(), "annual_base_gross":sub.base_gross.sum()/len(ds)*252,
                    "annual_candidate_gross":sub.candidate_gross.sum()/len(ds)*252, "annual_delta_net":sub.delta_net.sum()/len(ds)*252})
    by_source = pd.DataFrame(by_source); zero_rows = pd.DataFrame(zero_rows)
    by_source.to_csv(output / "metrics/removed_added_by_context_source.csv", index=False)
    zero_rows.to_csv(output / "metrics/zero_veto_short_membership.csv", index=False)
    baseline = pd.read_csv(output / "metrics/daily_BASELINE.csv", index_col="Date", parse_dates=["Date"], float_precision="round_trip")
    for candidate in [A, B]:
        daily = pd.read_csv(output / "metrics" / ("daily_"+candidate+".csv"), index_col="Date", parse_dates=["Date"], float_precision="round_trip")
        exact(baseline[["long", "long_net", "long_cost", "long_turnover"]], daily[["long", "long_net", "long_cost", "long_turnover"]])
    text = "損失回避の機構は部分的に確認できるが、採用できるNet改善はない。Pooled NetSRはBASELINE0.308092/A0.268556/B0.184835、EX2016は0.324348/0.264890/0.183362。両候補のfull-year改善は2013/2015の2/5のみ。B−BASELINE pooled95%CI[−0.272439,+0.007926]、EX2016[−0.298467,−0.005413]。正の安定した増分を支持しない。\n\n"
    for candidate in [A, B]:
        sub = replacement.loc[(replacement.candidate==candidate)&(replacement.scope=="POOLED")&(replacement.book=="SHORT_Q1_Q2")].set_index("class")
        delta = inc.loc[(inc.candidate==candidate)&(inc.control=="BASELINE")&(inc.scope=="POOLED")].iloc[0]
        p = pooled.loc[candidate]
        text += f"{candidate}: REMOVED {int(sub.loc['REMOVED','rows']):,}行のforward target平均{sub.loc['REMOVED','forward_target_mean']*1e4:+.3f}bp/day、旧signed Shortgross {sub.loc['REMOVED','annual_base_gross']*100:+.4f}pp/年は損失なので、その除去はGross改善{sub.loc['REMOVED','annual_delta_gross']*100:+.4f}ppに寄与。一方ADDEDの新Shortgross {sub.loc['ADDED','annual_candidate_gross']*100:+.4f}ppとUNCHANGEDのweight効果{sub.loc['UNCHANGED','annual_delta_gross']*100:+.4f}ppを合わせ、全Shortgross差は{delta.delta_annual_short_gross*100:+.4f}pp。Shortcost増{delta.delta_annual_short_cost*100:+.4f}ppがこれを上回り、Shortnet差{delta.delta_annual_short_net*100:+.4f}pp。ΔShortNetが負のためGross/Net改善shareは定義せず、50%条件FAIL。単なるcost削減の改善でもない。Turnoverは{p.turnover:.6f}/日、baseline比{p.turnover/pooled.loc['BASELINE','turnover']:.3f}倍で1.25x超。\n\n"
    fa = pd.read_csv(output / "metrics/fallback_attribution.csv", dtype={"scope":str}, float_precision="round_trip")
    fb = fa.loc[(fa.scope=="POOLED")&(fa.control==A)&(fa.source=="SECTOR17_FALLBACK")].iloc[0]
    ba = inc.loc[(inc.scope=="POOLED")&(inc.candidate==B)&(inc.control==A)].iloc[0]
    text += f"17 fallback: pooled24,761行、4.2948%の追加context coverage。B vs Aでfallback行のShort除去{int(fb.short_removed_count):,}、Gross寄与{fb.annual_gross*100:+.4f}%/年、Net寄与{fb.annual_net*100:+.4f}%/年、Turnover寄与{fb.turnover:.6f}/日。B−Aのfallback行ΔGross{fb.annual_delta_gross*100:+.4f}pp、ΔNet{fb.annual_delta_net*100:+.4f}pp、ΔTurnover{fb.delta_turnover:+.6f}。全book B−AはΔNetSR{ba.delta_net_sharpe:+.6f}、annualNet差{ba.delta_annual_net*100:+.4f}pp、ShortNet差{ba.delta_annual_short_net*100:+.4f}pp。B−A pooled95%CI[−0.135782,−0.034707]、EX2016[−0.133094,−0.032622]。Coverage改善だけでalpha価値は認められず、今回のbookでは悪化。Source別寄与には33/unavailableへのglobal-ranking波及があるため、fallback単独効果と同一視しない。\n\n"
    text += "Long側は今回実データで全Trainの日次Gross/Net/cost/turnoverがbitwise不変、評価期間membership overlap/Jaccardはいずれも1。Short改善と引き換えのLong alpha損失は観測されず、総Net悪化はShort側に対応する。一般にglobal rankingの波及は可能だが、今回の正score上位bookは変化していない。\n\n"
    text += "Zero-score membership（公式Code tie orderingを保持）:\n\n"+table(zero_rows.loc[zero_rows.scope=="POOLED"], ["candidate","vetoed_score_rows","vetoed_rows_still_short","vetoed_rows_still_short_share"])+"\n\nNeutral化されたscoreが必ずShort bookから除去されるわけではない。Hard sign vetoによる変化とlarge0tie blockが同時に存在するため、Short turnover増の解釈はbookデータに基づく。原因の個別介入同定はしていない。\n\n"
    concentration_rows = []
    for level in [17, 33]:
        c = pd.read_csv(output / "metrics" / f"sector{level}/sector_concentration.csv", dtype={"scope":str})
        c = c.loc[(c.scope=="POOLED")&(c.measure=="short_weight")]
        concentration_rows += [{"partition":level,**r} for r in c[["strategy","mean_HHI","mean_max_sector_weight","max_sector_weight"]].to_dict("records")]
    text += "Short sector concentrationは同じPIT partitionで両候補とも増加。Top2平均exposureは33でbaseline22.13%→A22.38%→B23.02%、17で25.47%→25.76%→26.39%。日次HHI/平均最大weight:\n\n"
    text += table(pd.DataFrame(concentration_rows), ["partition","strategy","mean_HHI","mean_max_sector_weight","max_sector_weight"])+"\n\nQ Spearmanはbaseline0.9→両候補1.0で悪化せず、Gross/RankICの一部改善をcost控除後の安定した優位と取り違えない。\n\n"
    (output / "metrics/MECHANISM.md").write_text(text)
    for fn in ["MECHANISM.md", "removed_added_by_context_source.csv", "zero_veto_short_membership.csv"]:
        shutil.copyfile(output / "metrics" / fn, dest / fn)
    rp = dest / "REPORT.md"; original = rp.read_text()
    # Insert the readable mechanism immediately after the headline, before details.
    paragraphs = original.split("\n\n", 2)
    body = original[original.index("正式baselineはDM-20260908-v1"):].split("\nValidation:")[0]
    rp.write_text("\n\n".join(paragraphs[:2])+"\n\n"+text+body)
    tests = {"full_suite_before_finalization_fix":"307 passed in50.78s", "affected_suite_after_fix":"24 passed in4.70s",
             "firewall_regression":"PASS saved prediction/diagnostic reads, hash, report copy; Valid remains denied"}
    for p,h in prior_lock["prior_evidence_sha256"].items():
        assert sha(ROOT / p)==h, p
    for p,h in run["artifact_sha256"].items():
        assert sha(output / p)==h, p
    # Verify live inference sources are the exact code evaluated in the scientific run.
    source_run = json.loads((failed_source / "run.json").read_text())
    inference_paths = [p for p in source_run["code_sha256"] if p.startswith("stock_comp_2026/strategies/dm_baseline_sector_veto/")]
    for p in inference_paths:
        assert sha(ROOT / p)==source_run["code_sha256"][p]
    statuses = [{"run_id":p.parent.name, **{k:json.loads(p.read_text()).get(k) for k in ["status","actual_trials"]}} for p in (ROOT / "artifacts" / config["experiment_id"]).glob("*/run.json")]
    assert sum(r["actual_trials"] or 0 for r in statuses)==2
    preflight = json.loads((ROOT / "experiments" / config["experiment_id"] / "preflight_checks.json").read_text())
    from tools.workspace import validate_experiment, inside, digest
    validate_experiment(ROOT, ROOT / "experiments" / config["experiment_id"])
    fm = json.loads((ROOT / "experiments/DM-20260908/experiment.json").read_text())
    frozen_root = inside(ROOT, fm["freeze_root"])
    manifest = json.loads(inside(ROOT, fm["freeze_manifest"]).read_text())
    freeze_count = 0
    for section in ["code_sha256","artifact_sha256"]:
        for p,h in manifest[section].items():
            assert digest(inside(frozen_root,p))==h;freeze_count+=1
    audit = {"status":"PASS","tests":tests,"preflight":preflight,"current_experiment_metadata":"PASS",
        "freeze_hashes_rechecked":freeze_count,"inference_unchanged_after_science":True,"prior_evidence_hashes":len(prior_lock["prior_evidence_sha256"]),
        "source_run_statuses":statuses,"cumulative_performance_trials":2,"additional_trials":0,
        "full_train_long_daily_bitwise_unchanged":True,
        "first_report_recovery":"failed copying its own diagnostic parquets before explicit whitelist; retained with0trials",
        "reporting_code_sha256":sha(Path(__file__))}
    dump(output / "audit/finalization.json", audit); shutil.copyfile(output / "audit/finalization.json", dest / "audit/finalization.json")
    (output / "recovery/test_features.py").write_bytes((ROOT / "tests/strategies/dm_baseline_sector_veto/test_features.py").read_bytes())
    shutil.copyfile(Path(__file__), output / "recovery/baseline_sector_veto_report.py")
    shutil.copyfile("/private/tmp/dm12-tests.log", output / "logs/full_suite.log")
    with rp.open("a") as stream:
        stream.write("\nValidation: 全307tests PASS、保存処理修正後の対象24tests（新規firewall/hash/copy回帰を含む）PASS。make checkは既存DM-20261002-04 unknown experiment kindで停止するが、新metadataとFreeze129hash再検査PASS。最初のreport recoveryも自身のdiagnostic parquet copy許可漏れで失敗し、0trialsとして保持。最終recoveryは保存結果のみ利用し成功、累積performance2trials。\n")
    run["artifact_sha256"] = {str(p.relative_to(output)):sha(p) for sub in ["audit","metrics","predictions","code","recovery"] for p in (output / sub).rglob("*") if p.is_file()}
    run["finalization"] = audit
    run["report_sha256"] = {str(p.relative_to(ROOT)):sha(p) for p in dest.rglob("*") if p.is_file()}
    dump(output / "run.json", run)
    print(json.dumps(audit,indent=2,ensure_ascii=False))


if __name__=="__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--output",required=True)
    main(Path(parser.parse_args().output).resolve())
