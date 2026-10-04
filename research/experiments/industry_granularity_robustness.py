"""One fixed Sector17-versus-Sector33 granularity robustness trial."""
import argparse
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
import pyarrow
import scipy
from research import evaluation, firewall
from research.experiments import industry_momentum_stock_reversal as parent
from research.experiments.sector_momentum import sha, dump, safe, exact, account, fold_dates, persistence, table
from research.experiments.hierarchical_momentum import scopes, rank_changes, sector_concentration
from stock_comp_2026.strategies.dm_industry_momentum_stock_reversal17 import features as im, submission
from stock_comp_2026.strategies.dm_industry_momentum_stock_reversal import features as im33

CANDIDATE = "IND17_MOM_WITHIN_REV20"
CONTROL = "IND33_MOM_WITHIN_REV20"


def source_scan():
    sources = sorted((ROOT / "stock_comp_2026/strategies/dm_industry_momentum_stock_reversal17").glob("*.py"))
    findings = []
    for path in sources:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if any(t in node.value for t in ["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose",
                        "AdjustmentVolume", "raw_target", "target_1day", "_valid.parquet", "Sector33"]):
                    findings.append([str(path), node.lineno, "forbidden input"])
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                bad = node.func.attr in ["bfill", "backfill"]
                if node.func.attr=="shift":
                    n = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg=="periods"),None)
                    bad |= not isinstance(n,ast.Constant) or not isinstance(n.value,int) or n.value<0
                for k in node.keywords:
                    bad |= k.arg=="center" and not (isinstance(k.value,ast.Constant) and k.value.value is False)
                    bad |= k.arg=="direction" and not (isinstance(k.value,ast.Constant) and k.value.value=="backward")
                if bad:
                    findings.append([str(path),node.lineno,"forbidden temporal operation"])
    assert not findings, findings
    return {"status":"PASS","sources":[str(p.relative_to(ROOT)) for p in sources],"findings":findings,
        "review":"Historical PIT17 self-inclusive equal finite daily residual mean min5;20/skip1; unchanged rank/1:1/rerank/EWMA. No label/LOO/model/filter."}


def stored_feature_parity(rebuilt, stored):
    """Parquet canonicalizes NaN payloads; require all defined bits and masks."""
    assert rebuilt.index.equals(stored.index) and rebuilt.columns.equals(stored.columns) and rebuilt.dtypes.equals(stored.dtypes)
    payload = {}
    for col in rebuilt:
        if pd.api.types.is_numeric_dtype(rebuilt[col]):
            a,b = rebuilt[col].to_numpy(),stored[col].to_numpy()
            missing = np.isnan(a)
            assert np.array_equal(missing,np.isnan(b)),col
            assert np.array_equal(a[~missing].view(np.uint64),b[~missing].view(np.uint64)),col
            payload[col] = int((a[missing].view(np.uint64)!=b[missing].view(np.uint64)).sum())
        else:
            pd.testing.assert_series_equal(rebuilt[col],stored[col],check_exact=True)
    return {"status":"PASS","index_columns_dtypes_exact":True,"defined_values_bitwise":True,"NaN_masks_exact":True,
            "NaN_payload_differences":payload,"scope":"Stored parquet comparison only. In-memory prefix/rebuild/golden comparisons still strict uint64 incl NaN; no tolerance."}


def classification_only_parity(inputs, f, history):
    """Original33 builder receives identical classifications relabeled as33."""
    reference = dict(inputs)
    reference["listed_info"] = inputs["listed_info"].rename(columns={"Sector17Code":"Sector33Code"})
    rf, rh = im33.build_features(reference, True)
    mapping = {c:c.replace("17","33") for c in f.columns}
    exact(f.rename(columns=mapping),rf[list(mapping.values())])
    exact(history.rename_axis(index=["Date","Sector33Code"]),rh)
    p = ROOT / "stock_comp_2026/strategies/dm_industry_momentum_stock_reversal"
    q = ROOT / "stock_comp_2026/strategies/dm_industry_momentum_stock_reversal17"
    expected = (p/"features.py").read_text().replace("33","17")
    expected = expected.replace('CANDIDATES = {"STOCK_REV20": "STOCK_REV20", "WITHIN17_REV20": "WITHIN17_REV20",\n              "IND17_MOM_WITHIN_REV20": "IND17_MOM_WITHIN_REV20"}', 'CANDIDATES = {"IND17_MOM_WITHIN_REV20": "IND17_MOM_WITHIN_REV20"}')
    expected = expected.replace('    f["STOCK_REV20"] = smooth(centered_rank(-f.StockMom20), .25)\n', '').replace('    f["WITHIN17_REV20"] = smooth(f.WithinReversalComponent, .25)\n', '')
    assert expected==(q/"features.py").read_text()
    assert (p/"primitives.py").read_bytes()==(q/"primitives.py").read_bytes()
    return {"status":"PASS","bitwise_same_classifications":True,"all_features_and_history":True,
        "source_change":"33->17 identifiers only; unused STOCK/standalone-WITHIN score exports pruned; combined formula unchanged",
        "primitives_bytes_unchanged":True,"rows":len(f)}


def prefix_audit(inputs, f, history, config):
    cases = []
    for i, cut in enumerate(config["prefix_cutoffs"]):
        cut = pd.Timestamp(cut)
        for name in list(inputs)+["ALL","TRUNCATION"]:
            changed = dict(inputs)
            for j,(source,frame) in enumerate(inputs.items()):
                if name=="TRUNCATION":
                    changed[source] = frame.loc[frame.index.get_level_values("Date")<=cut]
                elif name in [source,"ALL"]:
                    changed[source] = parent.mutate(frame,source,cut,config["random_seed"]+100*i+j)
            got,gh = im.build_features(changed,True)
            idx = f.index[f.index.get_level_values("Date")<=cut]
            hi = history.index[history.index.get_level_values("Date")<=cut]
            exact(f.loc[idx],got.loc[got.index.get_level_values("Date")<=cut])
            exact(history.loc[hi],gh.loc[gh.index.get_level_values("Date")<=cut])
            exact(im.score(f.loc[idx]),im.score(got.loc[idx]))
            cases.append({"cutoff":str(cut.date()),"source":name,"status":"PASS","bitwise":True,
                          "stock_rows":len(idx),"industry_rows":len(hi)})
        print(f"PIT17 prefix {cut.date()}: full inputs/history/scores/truncation PASS",flush=True)
    for data in [inputs,{n:x.sample(frac=1,random_state=91) for n,x in inputs.items()}]:
        got,gh = im.build_features(data,True)
        exact(f,got);exact(history,gh)
    return {"status":"PASS","cases":cases,"row_shuffle":True,"deterministic_rebuild":True,
        "comparison":"Exact index/columns/dtype and numeric uint64 bits incl NaN, no tolerance",
        "mutations":"All4 inputs individually/jointly: return/beta/TOPIX extremes+NaN, PIT17 changes, suffix row deletion, future-only stocks/new sectors, truncation",
        "features":list(f),"history":list(history),"scope":"Full Train3cutoffs, no fitting; empirical evidence on exercised inputs"}


def coverage(frames, dates, folder):
    rows,sectors = [],[]
    for granularity,f in frames.items():
        field = f"Sector{granularity}Code"
        masks = {"StockMom20":f.StockMom20.notna(),"IndustryMom20":f.IndustryMom20.notna(),
                 "WithinReversal":f[f"Within{granularity}Rev20"].notna()}
        for scope,ds in [("ALL_TRAIN",f.index.get_level_values("Date").unique())]+scopes(dates):
            keep = f.index.get_level_values("Date").isin(ds)
            for component,mask in masks.items():
                panel = pd.DataFrame({"finite":mask.loc[keep],"sector":f[field].loc[keep].fillna("UNKNOWN"),
                    "min_fail":f.FiniteMembers.loc[keep].lt(5)})
                rows.append({"granularity":granularity,"component":component,"scope":scope,"rows":len(panel),
                    "raw_coverage":panel.finite.mean(),"minimum5_failure_rows":int(panel.min_fail.sum()),
                    "missing_sector_rows":int(f[field].loc[keep].isna().sum()),"finite_prediction_coverage":1.})
                for code,block in panel.groupby("sector"):
                    sectors.append({"granularity":granularity,"component":component,"scope":scope,"sector":code,
                        "rows":len(block),"raw_coverage":block.finite.mean(),"minimum5_failure_rows":int(block.min_fail.sum())})
    result = pd.DataFrame(rows)
    result.to_csv(folder/"coverage.csv",index=False)
    pd.DataFrame(sectors).to_csv(folder/"coverage_sector.csv",index=False)
    return result


def component_diagnostics(frames,histories,target,dates,folder):
    rows,daily = [],[]
    matched = frames[17].IndustryMom20.notna() & frames[33].IndustryMom20.notna() & frames[17].Within17Rev20.notna() & frames[33].Within33Rev20.notna()
    for granularity,f in frames.items():
        raw = {"IndustryContinuation":f.IndustryMom20,"WithinReversal":f[f"Within{granularity}Rev20"]}
        for component,s in raw.items():
            for population,signal in [("OWN_FINITE",s),("MATCHED_JOINT_FINITE",s.where(matched))]:
                ic = evaluation.rankic(signal,target)
                daily.append(ic.rename(f"{granularity}:{component}:{population}"))
                for scope,ds in scopes(dates):
                    x = ic.reindex(ds)
                    rows.append({"granularity":granularity,"component":component,"population":population,"scope":scope,
                        "rankic":x.mean(),"HAC5_t":evaluation.hac_t(x),"hit":(x.dropna()>0).mean(),"days":x.notna().sum()})
        h = histories[granularity]
        sector = f[f"Sector{granularity}Code"]
        y = target.groupby([f.index.get_level_values("Date"),sector]).mean()
        y.index.names = h.index.names
        panel = h.copy();panel["forward_target"] = y.reindex(h.index)
        panel.to_csv(folder/f"industry{granularity}_daily.csv")
        cross = panel.rename_axis(index=["Date","Code"])
        ic = evaluation.rankic(cross.IndustryMom20,cross.forward_target)
        daily.append(ic.rename(f"{granularity}:IndustryContinuation:CROSS_INDUSTRY"))
        for scope,ds in scopes(dates):
            x = ic.reindex(ds)
            rows.append({"granularity":granularity,"component":"IndustryContinuation","population":"CROSS_INDUSTRY","scope":scope,
                "rankic":x.mean(),"HAC5_t":evaluation.hac_t(x),"hit":(x.dropna()>0).mean(),"days":x.notna().sum()})
    result = pd.DataFrame(rows)
    result.to_csv(folder/"component_rankic.csv",index=False)
    pd.concat(daily,axis=1).to_csv(folder/"component_rankic_daily.csv")
    deltas = []
    for (component,population,scope),block in result.groupby(["component","population","scope"]):
        b = block.set_index("granularity")
        deltas.append({"component":component,"population":population,"scope":scope,"delta_rankic_17_minus33":b.loc[17,"rankic"]-b.loc[33,"rankic"]})
    pd.DataFrame(deltas).to_csv(folder/"component_incremental.csv",index=False)


def decide(accounts,cover,boot):
    d = accounts[CANDIDATE];b = accounts["MOM60"]
    m = parent.metrics(d);base = parent.metrics(b)
    ex = parent.metrics(d.loc[d.index.year!=2016]);bx = parent.metrics(b.loc[b.index.year!=2016])
    positive = sum(evaluation.sharpe(d.loc[d.index.year==y].gross)>0 for y in range(2011,2016))
    improvements = sum(evaluation.sharpe(d.loc[d.index.year==y].net)>evaluation.sharpe(b.loc[b.index.year==y].net) for y in range(2011,2016))
    raw = cover.loc[(cover.granularity==17)&(cover.component=="WithinReversal")&(cover.scope=="POOLED"),"raw_coverage"].iloc[0]
    feasible = {"pooled_rankic_positive":m["rankic"]>0,"pooled_gross_positive":m["gross_sharpe"]>0,
        "ex2016_gross_positive":ex["gross_sharpe"]>0,"gross_positive_3of5":positive>=3,
        "raw_coverage_ge95pct":raw>=.95,"turnover_le008":m["turnover"]<=.08}
    extra = {"pooled_netSR_beats_MOM60":m["net_sharpe"]>base["net_sharpe"],
        "ex2016_netSR_beats_MOM60":ex["net_sharpe"]>bx["net_sharpe"],"netSR_improvements_4of5":improvements>=4,
        "bootstrap_lower_positive":boot[f"POOLED:{CANDIDATE}-MOM60"]["low"]>0,
        "annual_net_beats_MOM60":m["annual_net"]>base["annual_net"],"turnover_le125_MOM60":m["turnover"]<=base["turnover"]*1.25,
        "long_net_positive":m["annual_long_net"]>0,"short_net_ge_MOM60":m["annual_short_net"]>=base["annual_short_net"],
        "Q_monotonicity_positive":m["q_monotonicity"]>0}
    failed = [k for k,v in {**feasible,**extra}.items() if not v]
    return {"candidate":CANDIDATE,"decision":"REJECT" if failed else "NEXT_STAGE_ELIGIBLE",
        "unchanged_parent_gates":True,"feasibility":feasible,"combined_adoption":extra,"failed_checks":failed,
        "raw_coverage":raw,"full_year_gross_positive":positive,"full_year_netSR_improvements_vs_MOM60":improvements}


def standalone_smoke(stage,output,signal):
    smoke = output/"adapter_smoke";smoke.mkdir();(smoke/"input").symlink_to(stage,target_is_directory=True)
    prediction = output/"predictions/standalone.parquet";audit = output/"audit/standalone_smoke.json"
    script = "\n".join(["import sys,time,resource,json,os",f"sys.path.insert(0,{str(ROOT)!r})",
        "from research import firewall; firewall.install()",
        f"sys.path.insert(0,{str(ROOT/'stock_comp_2026/strategies/dm_industry_momentum_stock_reversal17')!r})",
        "import submission",f"os.chdir({str(smoke)!r})","t=time.monotonic(); p=submission.predict()",
        f"p.to_parquet({str(prediction)!r})",
        "r={'status':'PASS','rows':len(p),'finite':bool(p.notna().all().all()),'seconds':time.monotonic()-t,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),'opened':sorted(firewall.ACCESSES),'no_argument_predict':True}",
        f"open({str(audit)!r},'w').write(json.dumps(r,indent=2)+'\\n')"])
    (smoke/"script.py").write_text(script+"\n")
    result = subprocess.run([sys.executable,str(smoke/"script.py")],capture_output=True,text=True,timeout=120)
    (output/"logs/standalone.log").write_text(result.stdout+result.stderr)
    assert result.returncode==0,result.stderr
    exact(signal.to_frame(),pd.read_parquet(prediction))
    record = json.loads(audit.read_text());record["bitwise_research_parity"]=True;dump(audit,record)


def report(config,output,results,decision,boot):
    destination = ROOT/config["report_dir"];destination.mkdir(exist_ok=False)
    for sub in ["metrics","audit"]:shutil.copytree(output/sub,destination/sub)
    pooled = results.loc[results.scope=="POOLED"].set_index("strategy")
    c,b,m = [pooled.loc[n] for n in [CANDIDATE,CONTROL,"MOM60"]]
    cover = pd.read_csv(output/"metrics/coverage.csv")
    cv = {g:cover.loc[(cover.granularity==g)&(cover.component=="WithinReversal")&(cover.scope=="POOLED"),"raw_coverage"].iloc[0] for g in [17,33]}
    component = pd.read_csv(output/"metrics/component_rankic.csv")
    ic = component.loc[(component.scope=="POOLED")&(component.population=="OWN_FINITE")].set_index(["granularity","component"])
    text = f"# {config['experiment_id']} — Sector17 granularity robustness\n\n**{CANDIDATE}: {decision['decision']}**。新規performance trialは1本で終了。Sector33→17以外は固定、parent10の採否・証拠は不変。Known Train development evidence、独立OOSではない。Valid・rescue・追加candidate・Freeze・外部提出なし。\n\nRun `{output.relative_to(ROOT)}`。\n\n"
    text += table(results.loc[results.scope=="POOLED"],["strategy","rankic","rankic_t_hac5","gross_sharpe","net_sharpe","annual_gross","annual_net","annual_cost","turnover","annual_long_net","annual_short_net"])+"\n\n"
    text += f"1. Raw coverage: 17={cv[17]*100:.3f}%、33={cv[33]*100:.3f}%、差{(cv[17]-cv[33])*100:+.3f}pp。Neutral0後の100%finite predictionとは分ける。\n\n"
    text += f"2. Turnover: 17={c.turnover:.6f}/日、33={b.turnover:.6f}/日、差{c.turnover-b.turnover:+.6f}。MOM60={m.turnover:.6f}。Annualcost差{(c.annual_cost-b.annual_cost)*100:+.3f}pp。\n\n"
    text += f"3. Industry continuation raw stock-row RankIC: 17={ic.loc[(17,'IndustryContinuation'),'rankic']:.6f}、33={ic.loc[(33,'IndustryContinuation'),'rankic']:.6f}。HAC5・年別・cross-industryと同じjoint-finite raw rows上のICをcomponent_rankic.csvに保存。分類数変更でcross-industry ICの母集団も変わるため、単純な有意性比較は避ける。\n\n"
    text += f"4. Within raw reversal IC: 17={ic.loc[(17,'WithinReversal'),'rankic']:.6f}、33={ic.loc[(33,'WithinReversal'),'rankic']:.6f}。17 Short gross/net={c.annual_short_gross*100:+.3f}%/{c.annual_short_net*100:+.3f}%、33差{(c.annual_short_gross-b.annual_short_gross)*100:+.3f}pp/{(c.annual_short_net-b.annual_short_net)*100:+.3f}pp。MOM60差{(c.annual_short_gross-m.annual_short_gross)*100:+.3f}pp/{(c.annual_short_net-m.annual_short_net)*100:+.3f}pp。Withinのみの追加portfolioは作らない。\n\n"
    text += f"5. NetSR:17={c.net_sharpe:.6f}、33={b.net_sharpe:.6f}、MOM60={m.net_sharpe:.6f}。17−33={c.net_sharpe-b.net_sharpe:+.6f}、17−MOM60={c.net_sharpe-m.net_sharpe:+.6f}。Year/fold/EX2016・bootstrapを併せて判定する。\n\n"
    text += "2011–2015 full-yearと2016 partialを分離。Chronological expanding history、fitなし、fold末2exchange sessions purge/t+2 maturity検証。全期間book/costを先に計算してから評価日を抽出し、前日保有を維持。\n\n"
    text += table(results.loc[results.scope.isin([str(y) for y in range(2011,2017)])],["strategy","scope","rankic","gross_sharpe","net_sharpe","annual_net","annual_long_net","annual_short_net","turnover"])+"\n\n"
    text += "固定gate（parent10と同じMOM60基準）:\n\n```json\n"+json.dumps(safe(decision),indent=2)+"\n```\n\nPaired circular moving-block20eligible sessions/2000reps/seed20261002/95%percentile ΔNetSR。Primary17−33、reference17−MOM60、pooledとex2016。purge gapsを除いたeligible sessionsを連結、multiplicity correction/OOS保証なし。\n\n```json\n"+json.dumps(safe(boot),indent=2)+"\n```\n\n"
    text += "Same residual raw_return−beta×TOPIX、skip1/20observations、daily historical PIT finite mean min5 incl own、missing history NaN保持、current-date PITから完成済みhistoryを参照。Within=Stock−Industry、Reversal=−Within。Separate centered component ranks→1:1 sum→centered rank→EWMA(.25)。Relisting>20gap resetも同じ。33builderへ17分類だけを与えるreference parityは全feature/history bitwise一致し、sourceも分類識別子変更と未使用standalone score exports削除だけ。元33builderとsaved scores/daily accountsのparityも検証。\n\n"
    text += "Official5quintiles/Code ties/Q2Q4、one-way0.1%cost、sampleSD Sharpe×sqrt252、annual arithmetic mean×252、HAC5 Bartlett、Q1low/Q5high/monotonicity、additive/compound DD、period sums。Missing-target cost omission follows official score; net_all_cost conservative diagnostic also saved. Short residual signed P/L excludes borrow costs.2016 annualized values are not a realized full-year return.\n\n"
    text += "Concentrationは全3bookを共通PIT17と共通PIT33の両partitionで測定し、side HHI/max/Q1Q5/exposure/top2をsector17/sector33へ保存。共通helperの列名Sector33Codeへ17を一時投影するが、値はexact contemporaneous PIT17のまま。分類が粗くなるだけでHHIが増える効果と、position変化を区別する。LOSOは元bookのsector寄与とcostを減算する記述診断のみ、rerank/exclusionなし。Rank persistence/quintile retention/spells/percentile changesはparentと同じ定義。Full observed spellsが評価期と交差する場合を集計、gap reset/境界censorを保存。\n\n"
    text += "Audit: source scan、runtime Train firewall/dedicated stage、3cutoff18全入力future-mutation/truncationのIndustry history/raw/final scores bitwise検査、row shuffle/決定性、exact index/finite coverage、classification-only parity、unchanged primitive/MOM60と33saved source/control-account parity、research/adapterと独立no-argument smoke、公式会計/purge、parent evidence hash preservation。Python firewallはbest-effort、動的監査は実施入力での証拠。Independent OOS/actual zip deploymentは本研究の範囲外。\n"
    (destination/"REPORT.md").write_text(text)
    (destination/"causality_audit.md").write_text("# Causality audit\n\nAll4Train prediction sources,3cutoffs×6mutation/truncation cases, full industry historical PIT17 table/features/final scores exact uint64 bits. Row shuffle/rebuild/adapter/exact index, source firewall/pre-target reads, isolated smoke, classification-only parity and parent control bitwise/account parity; official accounting and t+2 maturity. No fit. See audit/*.json for inputs/cutoffs/method/status. Prefix checks are empirical, not proof for every input. No Valid or target in inference.\n")
    exp = ROOT/"experiments"/config["experiment_id"]
    (exp/"decision.md").write_text(f"# {config['experiment_id']} decision\n\n**{CANDIDATE}: {decision['decision']}**。Exactly1 new fixed granularity trial completed; no rescue/Valid/Freeze/submission. Parent10 unchanged.\n\nFailed checks: {', '.join(decision['failed_checks']) or 'none'}.\n\nNetSR17/33/MOM60 {c.net_sharpe:.6f}/{b.net_sharpe:.6f}/{m.net_sharpe:.6f}; raw coverage17/33 {cv[17]*100:.3f}%/{cv[33]*100:.3f}%; turnover17/33 {c.turnover:.6f}/{b.turnover:.6f}.\n\n[Report](../../reports/{config['experiment_id']}/REPORT.md). Run `{output.relative_to(ROOT)}`. Known Train development evidence, not independent OOS.\n")
    meta = json.loads((exp/"experiment.json").read_text());meta.update(status="rejected" if decision["decision"]=="REJECT" else "completed",run_id=output.name,actual_trials=1,report=config["report_dir"]+"/REPORT.md");dump(exp/"experiment.json",meta)
    if decision["decision"]=="REJECT":
        with (ROOT/"experiments/GRAVEYARD.md").open("a") as stream:
            stream.write(f"\n## {config['experiment_id']}: Sector17 granularity robustness\n\n[Decision]({config['experiment_id']}/decision.md) / [Report](../reports/{config['experiment_id']}/REPORT.md). One fixed new trial only, parent10 unchanged, Train-only/no rescue/Valid/Freeze.\n\n- **{CANDIDATE}** — REJECT; failed: {', '.join(decision['failed_checks'])}. NetSR17/33/MOM60={c.net_sharpe:.4f}/{b.net_sharpe:.4f}/{m.net_sharpe:.4f}.\n")


def main_work(config,output,run):
    started = time.monotonic();exp = ROOT/"experiments"/config["experiment_id"]
    prereg = json.loads((exp/"preregistration.json").read_text());prior_hashes = prereg["prior_evidence_sha256"]
    assert sha(output/"plan.md")==prereg["plan_sha256"] and sha(output/"config.json")==prereg["config_sha256"]
    for path,h in prior_hashes.items():assert sha(ROOT/path)==h,path
    prior_exp = ROOT/"experiments"/config["prior_experiment"];prior_meta = json.loads((prior_exp/"experiment.json").read_text())
    assert prior_meta["status"]=="rejected"
    prior = ROOT/"artifacts"/config["prior_experiment"]/prior_meta["run_id"];prior_run = json.loads((prior/"run.json").read_text())
    assert prior_run["status"]=="completed"
    for path,h in prior_run["code_sha256"].items():assert sha(ROOT/path)==h,path
    prior_score = prior/"predictions/scores.parquet";prior_feature = prior/"predictions/features.parquet"
    for path in [prior_score,prior_feature]:assert sha(path)==prior_run["artifact_sha256"][str(path.relative_to(prior))]
    stage = output/"stage";stage.mkdir();data_hashes = {}
    for name in list(im.INPUT_COLUMNS)+["target_1day"]:
        path = ROOT/config["input_dir"]/f"{name}_train.parquet";(stage/path.name).symlink_to(path);data_hashes[path.name]=sha(path)
        assert data_hashes[path.name]==prior_run["train_data_sha256"][path.name],path.name
    predictions = [output/"predictions"/f"{n}.parquet" for n in ["features17","industry_history17","scores","standalone"]]
    firewall.install(allowed_artifacts=predictions+[prior_score,prior_feature]+[ROOT/p for p in prior_hashes if p.endswith(".parquet")])
    code_paths = [Path(__file__),ROOT/"research/experiments/industry_momentum_stock_reversal.py",ROOT/"research/experiments/sector_momentum.py",ROOT/"research/experiments/hierarchical_momentum.py",ROOT/"research/evaluation.py",ROOT/"research/firewall.py",ROOT/"stock_comp_2026/evaluate_script.py",ROOT/"stock_comp_2026/strategies/dm_trainonly/features.py",
        ROOT/"tests/strategies/dm_industry_momentum_stock_reversal17/test_features.py",ROOT/"tests/strategies/dm_industry_momentum_stock_reversal/test_features.py"]
    for slug in ["dm_industry_momentum_stock_reversal","dm_industry_momentum_stock_reversal17"]:code_paths+=sorted((ROOT/"stock_comp_2026/strategies"/slug).glob("*.py"))
    hashes = {str(p.relative_to(ROOT)):sha(p) for p in code_paths}
    for p in code_paths:
        dest = output/"code"/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    shutil.copyfile(exp/"preregistration.json",output/"preregistration.json")
    run.update(status="running",command=sys.argv,code_sha256=hashes,train_data_sha256=data_hashes,actual_trials=0,
        environment={"python":platform.python_version(),"pandas":pd.__version__,"numpy":np.__version__,"pyarrow":pyarrow.__version__,"scipy":scipy.__version__,"platform":platform.platform()})
    dump(output/"run.json",run);dump(output/"audit/pre_result_lock.json",{"at_utc":datetime.now(timezone.utc).isoformat(),"plan_sha256":sha(output/"plan.md"),"config_sha256":sha(output/"config.json"),"code_sha256":hashes,"target_loaded":False,"max_trials":1,"trials":[CANDIDATE]})
    dump(output/"audit/source_scan.json",source_scan())
    inputs = im.load_train(stage);f,h = im.build_features(inputs,True)
    assert f.index.equals(im.canonical(inputs["raw_return_1day"]).index)
    assert np.isfinite(f[[CANDIDATE,"MOM60"]].to_numpy()).all()
    dump(output/"audit/classification_only_parity.json",classification_only_parity(inputs,f,h))
    dump(output/"audit/primitive_parity.json",parent.primitive_parity(inputs,f))
    inputs33 = im33.load_train(stage);f33,h33 = im33.build_features(inputs33,True)
    saved = pd.read_parquet(prior_score,columns=[CONTROL,"MOM60"])
    stored_parity = stored_feature_parity(f33,pd.read_parquet(prior_feature))
    exact(f33[[CONTROL,"MOM60"]],saved);exact(f.MOM60,f33.MOM60)
    for col in ["ResidualReturn","StockMom20","StockMom60_raw"]:exact(f[col],f33[col])
    dump(output/"audit/prior_control_parity.json",{"status":"PASS","stored_parent_feature_parity":stored_parity,"control_scores_bitwise":True,"stock_residuals_unchanged":True,"rows":len(f),"source":str(prior_score.relative_to(ROOT)),"sha256":sha(prior_score),"new_control_trials":0})
    dump(output/"audit/prefix_invariance.json",prefix_audit(inputs,f,h,config))
    signal = im.score(f);exact(signal.to_frame(),submission.predict(stage));dump(output/"audit/adapter_parity.json",{"status":"PASS","rows":len(f),"bitwise":True})
    standalone_smoke(stage,output,signal)
    denied = []
    for name in ["target_1day_valid.parquet","raw_target_1day_train.parquet","unknown.parquet"]:
        try:pd.read_parquet(stage/name)
        except PermissionError as e:denied.append({"path":name,"reason":str(e)})
        else:raise AssertionError("Forbidden path accepted")
    assert not any("target_1day" in p for p in firewall.ACCESSES)
    dump(output/"audit/firewall_denials.json",{"status":"PASS","cases":denied});dump(output/"audit/prediction_source_firewall.json",{"status":"PASS","opened":sorted(firewall.ACCESSES),"all_scores_before_Train_target_loaded":True})
    signals = {CANDIDATE:signal,CONTROL:saved[CONTROL].rename("Return"),"MOM60":saved.MOM60.rename("Return")}
    f.to_parquet(predictions[0]);h.to_parquet(predictions[1]);pd.DataFrame(signals).to_parquet(predictions[2])
    calendar = f.index.get_level_values("Date").unique().sort_values();dates,purge = fold_dates(calendar,[x["year"] for x in config["walk_forward_folds"]])
    dump(output/"audit/purge.json",{"status":"PASS","folds":purge});cover = coverage({17:f,33:f33},dates,output/"metrics")
    dump(output/"audit/coverage.json",{"status":"PASS","rows":len(f),"finite_prediction":True,"exact_index":True,"raw_before_neutral":True})
    print("PIT17 feature/history/source/prefix/adapter and parent33 parity PASS; now load Train target",flush=True)
    target = im.canonical(pd.read_parquet(stage/"target_1day_train.parquet")).Return;assert target.index.equals(f.index)
    daily,holdings,parity = {},{},{}
    for name,s in signals.items():
        daily[name],holdings[name],parity[name] = account(s,target);daily[name].to_csv(output/f"metrics/daily_{name}.csv")
        if name==CANDIDATE:run["actual_trials"]=1;dump(output/"run.json",run)
        else:
            original = pd.read_csv(prior/f"metrics/daily_{name}.csv",index_col="Date",parse_dates=["Date"],float_precision="round_trip")
            exact(daily[name],original)
        print(f"{'One new trial' if name==CANDIDATE else 'Unchanged control replay'} {name}: saved",flush=True)
    dump(output/"audit/official_accounting_parity.json",{"status":"PASS","strategies":parity})
    dump(output/"audit/prior_account_parity.json",{"status":"PASS","prior_daily_bitwise":True,"controls":[CONTROL,"MOM60"],"new_performance_trials":1})
    accounts = {n:d.loc[dates] for n,d in daily.items()}
    results = pd.DataFrame([{"strategy":n,"scope":scope,**parent.metrics(d.loc[ds])} for n,d in daily.items() for scope,ds in [("ALL_TRAIN",calendar)]+scopes(dates)])
    results.to_csv(output/"metrics/metrics.csv",index=False);results.loc[results.scope=="POOLED"].to_csv(output/"metrics/overall_metrics.csv",index=False)
    for name in ["fold_metrics","year_metrics"]:results.loc[results.scope.isin([str(y) for y in range(2011,2017)])].to_csv(output/f"metrics/{name}.csv",index=False)
    results[["strategy","scope"]+[k for k in results if "long" in k or "short" in k]].to_csv(output/"metrics/long_short.csv",index=False)
    results[["strategy","scope"]+[k for k in results if k.startswith("q")]].to_csv(output/"metrics/quintiles.csv",index=False)
    increments = []
    for control in [CONTROL,"MOM60"]:
        for scope in results.scope.unique():
            c = results.loc[(results.strategy==CANDIDATE)&(results.scope==scope)].iloc[0];b = results.loc[(results.strategy==control)&(results.scope==scope)].iloc[0]
            increments.append({"strategy":CANDIDATE,"control":control,"scope":scope,**{"delta_"+k:c[k]-b[k] for k in results if k not in ["strategy","scope"]}})
    increments = pd.DataFrame(increments);assert np.allclose(increments.delta_annual_short_net,increments.delta_annual_short_gross-increments.delta_annual_short_cost,atol=1e-15,rtol=0);increments.to_csv(output/"metrics/incremental.csv",index=False)
    boot = {}
    for scope,ds in scopes(dates)[:2]:
        for candidate,control in config["bootstrap"]["pairs"]:
            boot[f"{scope}:{candidate}-{control}"] = {**evaluation.bootstrap_delta(accounts[control].loc[ds].net,accounts[candidate].loc[ds].net,**{k:config["bootstrap"][k] for k in ["seed","block","reps"]}),"days":len(ds),"point_delta":evaluation.sharpe(accounts[candidate].loc[ds].net)-evaluation.sharpe(accounts[control].loc[ds].net),"primary":scope=="POOLED" and control==CONTROL}
    dump(output/"metrics/bootstrap.json",boot);pd.DataFrame([{"contrast":k,**v} for k,v in boot.items()]).to_csv(output/"metrics/bootstrap.csv",index=False)
    decision = decide(accounts,cover,boot);dump(output/"metrics/candidate_decision.json",decision)
    print("One trial complete; fixed component/persistence/concentration diagnostics only",flush=True)
    component_diagnostics({17:f,33:f33},{17:h,33:h33},target,dates,output/"metrics")
    persistence(signals,holdings,calendar,dates.rename("Date"),output/"metrics");rank_changes(signals,calendar,dates,output/"metrics")
    idx = f.index[f.index.get_level_values("Date").isin(dates)];he = {n:x.loc[idx] for n,x in holdings.items()}
    for granularity,ff in [(17,f),(33,f33)]:
        dest = output/"metrics"/f"sector{granularity}";dest.mkdir()
        # Shared accounting helper's legacy field name is only an API projection.
        partition = ff.loc[idx, [f"Sector{granularity}Code"]].rename(columns={f"Sector{granularity}Code":"Sector33Code"})
        sector_concentration(partition,he,accounts,dest)
    for path,hsh in prior_hashes.items():assert sha(ROOT/path)==hsh,path
    dump(output/"audit/prior_evidence_unchanged.json",{"status":"PASS","parent":config["prior_experiment"],"hashes":prior_hashes})
    firewall.save(output/"audit/firewall.json")
    resources = {"elapsed_seconds":time.monotonic()-started,"peak_rss_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=="darwin" else 1024),"actual_trials":1,"valid_evaluation":False};dump(output/"audit/resources.json",resources)
    report(config,output,results,decision,boot)
    artifacts = {str(p.relative_to(output)):sha(p) for sub in ["audit","metrics","predictions","code"] for p in (output/sub).rglob("*") if p.is_file()}
    run.update(resources);run.update(status="completed",exit_code=0,completed_at_utc=datetime.now(timezone.utc).isoformat(),artifact_sha256=artifacts,candidate_decision=decision);dump(output/"run.json",run)
    print(json.dumps(safe({"decision":decision,"resources":resources}),indent=2),flush=True)


def main():
    parser = argparse.ArgumentParser();parser.add_argument("--config",required=True);parser.add_argument("--output",required=True);args = parser.parse_args()
    output = Path(args.output).resolve();config = json.loads(Path(args.config).read_text());assert Path(args.config).resolve()==output/"config.json"
    assert config["data_split"]=="train" and config["valid_evaluation"] is False and config["max_trials"]==1
    assert config["trials"]==[{"trial_id":CANDIDATE}] and list(im.CANDIDATES)==[CANDIDATE]
    assert config["parameters"]=={"horizon":20,"skip":1,"min_periods":20,"sector17_min_finite_members":5,"alpha":.25,"ewm_adjust":False,"relisting_gap":20,"scale":"centered_rank","weights":[1,1]}
    pc = json.loads((ROOT/"experiments"/config["prior_experiment"]/"config.json").read_text())
    for key in ["feasibility_gates","combined_adoption_gates","walk_forward_folds","purge_trading_days","train_window","prefix_cutoffs"]:assert config[key]==pc[key],key
    for key in ["seed","reps","block"]:assert config["bootstrap"][key]==pc["bootstrap"][key],key
    run = json.loads((output/"run.json").read_text());assert run["status"]=="prepared"
    try:main_work(config,output,run)
    except BaseException as e:
        run.update(status="failed",exit_code=1,error=f"{type(e).__name__}: {e}",completed_at_utc=datetime.now(timezone.utc).isoformat());dump(output/"run.json",run)
        if firewall._PATCHED:firewall.save(output/"audit/firewall.json")
        raise


if __name__=="__main__":main()
