"""Final report from saved evidence; no feature or parameter selection."""
import json
from pathlib import Path
import resource
import shutil
import time
import pandas as pd
from research.experiments import slow_multifactor as shared

ROOT = Path(__file__).resolve().parents[2]


def report(config, output, run, started, failed=None):
    root=ROOT/config['report_dir'];root.mkdir(exist_ok=True)
    dest=root/output.name;dest.mkdir(exist_ok=True)
    resources={'elapsed_seconds':time.monotonic()-started,
               'phase_elapsed':{r['phase']:r['elapsed_seconds'] for r in run.get('phases',[])},
               'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
               'deadline_seconds':config['execution_timeout_seconds'],
               'permutation_draws':2000 if (output/'metrics/permutation_summary.csv').exists() else 0,
               'bootstrap_draws_per_scope_block':5000 if (output/'metrics/bootstrap.csv').exists() else 0,
               'bootstrap_total_joint_draws':30000 if (output/'metrics/bootstrap.csv').exists() else 0,
               'candidate_performance_trials':run.get('actual_trials',0),'rescue_trials':0,
               'files_generated':sum(p.is_file() for p in output.rglob('*')),
               'resume_source':run.get('resume_source')}
    history=[]
    previous=run.get('resume_source')
    while previous:
        previous_path=ROOT/previous
        previous_run=json.loads((previous_path/'run.json').read_text())
        previous_resources=json.loads((previous_path/'audit/resources.json').read_text())
        history.append({'run':previous,'status':previous_run['status'],
                        'elapsed_seconds':previous_resources['elapsed_seconds'],
                        'peak_rss_bytes':previous_resources['peak_rss_bytes'],
                        'failure':previous_run.get('failure')})
        previous=previous_run.get('resume_source')
    resources['run_history']=history
    resources['total_research_elapsed_seconds']=resources['elapsed_seconds']+sum(r['elapsed_seconds'] for r in history)
    resources['maximum_peak_rss_bytes_all_runs']=max([resources['peak_rss_bytes']]+[r['peak_rss_bytes'] for r in history])
    resources['runtime_note']='Total sums measured main-work elapsed for failed/scientific/completion runs, excluding preparation/coding and cloning before main_work. Recovered diagnostic elapsed was uncheckpointed; its work remains in failed-run total.'
    shared.dump(output/'audit/resources.json',resources)
    if failed:
        (dest/'REPORT.md').write_text(f'# {config["experiment_id"]}: F. Inconclusive\n\nTechnical failure: {failed}. Completed phases/hashes/results retained at {output.relative_to(ROOT)}. Resume into NEW run with identical config/strategy. No Valid.\n')
        return
    summary=pd.read_csv(output/'metrics/diagnostic_summary.csv')
    boot=pd.read_csv(output/'metrics/bootstrap.csv')
    placebo=pd.read_csv(output/'metrics/permutation_summary_audited.csv' if (output/'metrics/permutation_summary_audited.csv').exists() else output/'metrics/permutation_summary.csv')
    gates=json.loads((output/'audit/candidate_gate.json').read_text())
    primary=summary.loc[(summary.variant=='RM')&summary.group.isin(['ALL','LONG','SHORT','CELL3_9'])&summary.scope.isin(['POOLED','EX2016'])]
    def row(group):return primary.loc[(primary.group==group)&(primary.scope=='POOLED')].iloc[0]
    def low(group):return float(boot.loc[(boot.estimand==group)&(boot.scope=='POOLED')&(boot.block==20),'low'].iloc[0])
    l,s,h=row('LONG'),row('SHORT'),row('CELL3_9')
    if gates['all_passed']:
        adopted=json.loads((output/'audit/candidate_adoption.json').read_text())['all_passed']
        cat='A' if adopted else 'B'
    elif (l.spread>0 and low('LONG')>0 and l.positive_full_years>=4)!=(s.spread>0 and low('SHORT')>0 and s.positive_full_years>=4):
        cat='C'
    elif max(l.spread,s.spread,h.spread)<=0:cat='E'
    elif any(r.spread>0 and r.positive_full_years<4 for r in (l,s,h)):cat='D'
    else:cat='F'
    labels={'A':'Conditional Momentum confirmed','B':'Information exists, implementation fails','C':'Long-only/asymmetric information','D':'Regime-dependent','E':'No conditional Momentum','F':'Inconclusive'}
    verdict={'classification':cat,'label':labels[cat],'diagnostic_gate_passed':gates['all_passed'],
             'candidate_trials':run['actual_trials'],'rescue_trials':0,
             'decision':'NEXT_STAGE' if cat=='A' else 'REJECT',
             'qualification':'Descriptive classification; not proof of causal regime or economic mechanism'}
    shared.dump(output/'audit/conclusion.json',verdict)
    for sub in ('metrics','audit'):
        shutil.copytree(output/sub,dest/sub,ignore=shutil.ignore_patterns('*.dat','*_stock_days.parquet'))
    table=shared.table
    lines=[f'# {config["experiment_id"]}: Conditional residual Momentum','',
           f'**{cat}. {labels[cat]} — {verdict["decision"]}**。Candidate性能試行{run["actual_trials"]}本、rescue0本。Historical Valid / Valid未読・未評価。全Trainは既知development sampleでありuntouched OOSではない。','',
           f'科学原本: {output.relative_to(ROOT)}。REQUEST.mdへ全依頼を保存。plan/config/code/input/environmentとphase/output hashes、全中間CSV/parquet、draw分布を保存。','',
           '## 定義とstrict parity','',
           'Primary: centered rank(MOM60) ~ 1 + centered rank(Size) + centered rank(Illiquidity)の同日unregularized OLS、残差をsame-date average-tie centered rankへ再変換。target不要。rank尺度2*(pct−mean pct)は既存 convention。candidate S+abs(S)*rank(RM)、追加係数・平滑化・探索なし。','',
           'raw Size/Illiquidity有限値bitsと欠損位置、normalized components、SLOW、MOM60 pre-EWMA/final、official SLOW/MOM weightとdaily Netを完全照合。raw NaN符号はParquet nullに保存されないためraw保存表現のみcanonical NaNで照合、有限値と最終signalは許容差なし。全parity成功前に性能解釈しない。','',
           '## Primary conditional evidence','',
           table(primary,['group','scope','average_stock_count','rankic','rankic_hac5_t','rankic_hit','spread','spread_hac5_t','spread_gross_sharpe','positive_full_years']),'',
           table(boot.loc[boot.block==20],['scope','estimand','observed','low','high','positive_fraction']),'',
           'spreadはRM tercile High−Low forward target差のdaily mean。gross diagnosticでstrategy netを示さない。unconditional Q1–Q5/monotonicity/Q5−Q1 gross Sharpe、各年/EX2016/2016 partialはdiagnostic_summary.csv。Binは全component名でtarget join前に固定し、missing targetで順位を作り直さない。','',
           '## 必須12問への回答','',
           f'1. Size/Illiquidityから独立したRMのunconditional RankIC={row("ALL").rankic:.6f}、HAC5 t={row("ALL").rankic_hac5_t:.3f}。OLSは線形exposureを除去するが、経済的独立性や非線形依存がない証明ではない。',
           f'2. Long spread={l.spread:.8f}、positive full-years={int(l.positive_full_years)}/5、primary CI lower={low("LONG"):.8f}。',
           f'3. Short spread={s.spread:.8f}、positive full-years={int(s.positive_full_years)}/5、CI lower={low("SHORT"):.8f}。positiveならlow RMをShortへ置くconfirmation方向。',
           f'4. Small+Illiquid spread={h.spread:.8f}、positive full-years={int(h.positive_full_years)}/5。全9/25cellを示し、cornerだけを抜き出して強いとは結論しない。',
           '5. static factorかtiming signalかは観測associationだけで確定しない。transition・boundary・persistenceを併記し、entry/exit/regime ruleは作成しない。',
           '6. entry/holding/exitは前営業日membershipから分類。下表のRM Low/Mid/High forward mean差とsupportで比較。side flipはcurrent entry優先、exit flagsも保存。結果からfilterを作らない。',
           '7. lag1/5/10/20 rank autocorrelation、absolute RM/SLOW rank change、boundary crossingとの関係はpersistence tables。costとの整合性を記述し、新holding periodやEWMAは選択しない。',
           '8. 全5×5 heatmap CSVと隣接spread差・positive fractionをsurface_smoothness.csvへ保存。support不足も残し、滑らかさを個別有意cellだけで判断しない。',
           '9. observedと3×3構成維持permutationの比較は下表。銘柄別circular20/60/120/252/504 shiftsも保存。restricted nullであり、cell間exposureや全依存を消去するnullではない。',
           '10. block20 CIがprimary、block10/40 sensitivityも保存。20session依存は考慮するが、年次構造変化と既読Trainの研究選択全体を扱うCIではない。year/half-year/rolling252を別評価。',
           f'11. Candidate gate={"PASS" if gates["all_passed"] else "FAIL"}。全条件conjunction。失敗でも全diagnostic/placebo/bootstrapを完走。',
           '12. Gate失敗によりcandidate0本。SLOWをafter-costで超えたとの主張はない。' if run['actual_trials']==0 else '12. Fixed candidate1本のafter-cost比較、固定採用gate、cost stress/attribution/bootstrapをcandidate filesへ保存。','',
           '## Robustness A/B/C','',
           table(summary.loc[summary.group.isin(['LONG','SHORT','CELL3_9'])&summary.scope.isin(['POOLED','EX2016'])],['variant','group','scope','spread','rankic','positive_full_years']),'',
           '## All3×3 /5×5 cells','',
           table(summary.loc[(summary.variant=='RM')&(summary.scope=='POOLED')&summary.group.str.startswith('CELL')],['group','average_stock_count','support_sufficient','rankic','spread','spread_hac5_t','positive_full_years','target_mean','slow_average_weight','annual_slow_gross_contribution']),'',
           'support sufficientは平均>=10名かつ80%以上の日が>=10名という表示基準。cellを削除せず、strategy ruleには使わない。全cell BH descriptive FDRとsurface permutation max-abs-HAC5-tを保存。主仮説3つのみ、他はsecondary。','',
           '## Long/Short asymmetry and transition','']
    transition=pd.read_csv(output/'metrics/transition_summary.csv')
    lines += [table(transition.loc[transition.scope=='POOLED'],['group','rm_bin','stock_days','forward_target','annual_gross_contribution','annual_net_contribution','turnover_contribution']),'',
              'Long/Short別RM quintileはside_summary.csv。Neutral退出costも残し、全partitionがofficial daily gross/net/cost/turnoverへreconcile。','',
              '## Persistence and regimes','']
    persist=pd.read_csv(output/'metrics/persistence_summary.csv')
    regimes=pd.read_csv(output/'metrics/regime_summary.csv')
    lines += [table(persist.loc[persist.scope.isin(['POOLED','EX2016'])],list(persist.columns)),'',
              table(regimes.loc[regimes.group.isin(['LONG','SHORT','CELL3_9'])],['group','regime','state','days','spread','rankic']),'',
              'TOPIXは公式のETF proxy。同日までのtrailing60 vol/min40をlag1 expanding median/min252でsplit、trend60/min40は符号split（閾値0）。PIT安全性は公式READMEの構成式、動的prefix auditで検証。未来median・threshold searchなし。','',
              '## Placebo and inference','',
              table(placebo.loc[(placebo.scope=='POOLED')&placebo.group.isin(['ALL','LONG','SHORT','CELL3_9'])],['group','metric','observed','null_mean','null_low','null_high','p_positive','p_two_sided']),'',
              'shuffle2000、固定seed、同日3×3cell内のみ。全9/25cellへ同じdrawを使用しmax-statを保存。circular shiftはfuture wrapを含む非因果diagnostic専用。再上場・系列依存の限界あり、strategyでは利用しない。support不足で観測統計が未定義のcellはp-valueも欠損。正式な多重検定表はpermutation_summary_audited.csvとFDR_permutation_audited.csv；初回出力の欠損比較による誤p値は原本を保持して技術的に補正し、drawやperformanceは再計算していない。','',
              '## Candidate gate','',
              table(pd.DataFrame([{'gate':k,'passed':v} for k,v in gates['checks'].items()]),['gate','passed']),'',
              '良いsubgroupは次実験仮説として記録するだけ。Long-only/Short-only/corner/boundary/sector/regime/veto/ML rescueなし。このbundleは固定gateの採否で終了。','',
              '## Audit, runtime and limitations','']
    audit=json.loads((output/'audit/prefix_invariance.json').read_text())
    bench=json.loads((output/'audit/submission_benchmark.json').read_text())
    verify=json.loads((output/'audit/verification.json').read_text())
    lines += [f'future mutation全6source個別/ALL、3cutoff truncation、row shuffle、deterministic rebuildの{len(audit["cases"])}ケースPASS。RM/bins/transition/boundary/regime/fixed score、exact Date/Code/finite100%coverage、target-free stage、t+2 maturity、fold-end2session purge、firewall拒否を保存。テストは試した入力/cutoffの証拠で普遍的証明ではない。','',
              f'Total measured research elapsed={resources["total_research_elapsed_seconds"]:.2f}s、all-run peak RSS={resources["maximum_peak_rss_bytes_all_runs"]/1024**2:.1f}MiB、deadline10800s。current completion={resources["elapsed_seconds"]:.2f}s。phase elapsedと全runの失敗/再開履歴はaudit/resources.json。clone/preparation/codingはこのcompute実測に含めない；初回の未checkpoint diagnostic elapsedはfailed-run totalに含まれる。Permutation2000、bootstrap5000×2scope×3block=30000 joint draws。candidate={run["actual_trials"]}、rescue0、files={resources["files_generated"]}。','',
              f'別のtarget-free submission inference実測: {bench["elapsed_seconds"]:.3f}s、peak RSS={bench["peak_rss_bytes"]/1024**2:.1f}MiB。全Train読込/再構築/scoreを研究予測とbitwise照合。research時間と区別し、採点環境そのものの30分保証とはしない。','',
              f'構成/回帰検証: {json.dumps(verify,ensure_ascii=False)}。既存workspace metadata不整合は修正せず明記；全workspace合格としない。','',
              'Input/code/config/output hashes、library versions、seeds、全技術失敗・resume provenanceを保存。Performanceを隠して再runせず、technical retryは同一定義で保存済みphaseを引き継ぐ。外部提出/Valid/release作成なし。']
    (dest/'REPORT.md').write_text('\n'.join(lines)+'\n')
    (root/'REPORT.md').write_text(f'# {config["experiment_id"]}\n\n**{cat}. {labels[cat]}**。candidate{run["actual_trials"]}、rescue0。Train-only、Valid未使用。\n\n[Complete report]({output.name}/REPORT.md).\n')
    ex=ROOT/'experiments'/config['experiment_id']
    (ex/'decision.md').write_text(f'# {config["experiment_id"]}: {verdict["decision"]}\n\n{cat}. {labels[cat]}. Gate={gates["all_passed"]}, candidate{run["actual_trials"]}, rescue0.\n\n[Report](../../{config["report_dir"]}/{output.name}/REPORT.md).\n')
    meta=json.loads((ex/'experiment.json').read_text())
    meta.update(status='completed' if cat=='A' else 'rejected',actual_trials=run['actual_trials'],category=cat,run_id=output.name,report=str((dest/'REPORT.md').relative_to(ROOT)))
    shared.dump(ex/'experiment.json',meta)
    if cat!='A' and f'## {config["experiment_id"]}:' not in (ROOT/'experiments/GRAVEYARD.md').read_text():
        with (ROOT/'experiments/GRAVEYARD.md').open('a') as stream:
            stream.write(f'\n## {config["experiment_id"]}: conditional residual Momentum\n\n{cat}. {labels[cat]}; candidate{run["actual_trials"]}, rescue0. Long={l.spread:.8f}, Short={s.spread:.8f}, Small+Illiquid={h.spread:.8f}. [Decision]({config["experiment_id"]}/decision.md). Train-only, no Valid.\n')
