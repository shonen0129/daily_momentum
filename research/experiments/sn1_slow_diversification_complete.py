"""Finish audits and report from a saved fixed trial; no performance rerun."""
import argparse
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time

import numpy as np
import pandas as pd
from research import firewall
from research.experiments import sn1_slow_diversification as d
from tools import workspace

ROOT=d.ROOT


def freeze_paths():
    paths=[]
    for p in (ROOT/'reports').glob('*/freeze_manifest.json'):
        manifest=json.loads(p.read_text());root=ROOT
        for folder in (ROOT/'experiments').iterdir():
            meta_path=folder/'experiment.json'
            if meta_path.is_file():
                meta=json.loads(meta_path.read_text())
                if meta.get('freeze_manifest')==str(p.relative_to(ROOT)):root=ROOT/meta['freeze_root']
        for section in ['code_sha256','artifact_sha256']:
            for rel,h in manifest[section].items():paths.append((root/rel,h))
    return paths


def complete(source,output):
    start=time.monotonic();origin=json.loads((source/'run.json').read_text());run=json.loads((output/'run.json').read_text());config=json.loads((output/'config.json').read_text())
    assert run['status']=='prepared';assert origin['status']=='failed' and origin['actual_trials']==1
    assert 'datetime64[ns, Asia/Tokyo]' in origin['failure']
    for name in ['plan.md','config.json']:assert d.sha(source/name)==d.sha(output/name)
    for rel,h in origin['code_sha256'].items():assert d.sha(source/'code'/rel)==h
    # All performance and definition functions remain identical to scientific snapshot.
    driver_rel='research/experiments/sn1_slow_diversification.py'
    old_text=(source/'code'/driver_rel).read_text();new_text=Path(d.__file__).read_text()
    old_functions={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(old_text).body if isinstance(n,ast.FunctionDef)}
    new_functions={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(new_text).body if isinstance(n,ast.FunctionDef)}
    changed=[k for k in old_functions if old_functions[k]!=new_functions[k]]
    assert changed==['mutate','causality'],changed
    immutable=[p for p in origin['code_sha256'] if p.startswith('stock_comp_2026/strategies/')]
    for rel in immutable:assert d.sha(ROOT/rel)==origin['code_sha256'][rel]
    frozen=freeze_paths()
    allowed=[p for folder in ['predictions','metrics'] for p in (source/folder).rglob('*.parquet')]
    allowed += [output/p.relative_to(source) for p in allowed]
    allowed += [p for p,h in frozen if p.suffix=='.parquet']
    firewall.install(allowed_artifacts=allowed)
    # Copy original science without editing its failed run or evidence.
    scientific_hashes={str(p.relative_to(source)):d.sha(p) for folder in ['predictions','metrics'] for p in (source/folder).rglob('*') if p.is_file()}
    for folder in ['code','models','predictions','metrics','audit']:
        shutil.copytree(source/folder,output/folder,dirs_exist_ok=True)
    shutil.copyfile(source/'logs/run.log',output/'logs/scientific_run.log')
    for file in [Path(__file__),Path(d.__file__),ROOT/'tests/strategies/dm_sn1_slow_blend/test_blend.py']:
        to=output/'audit_code'/file.relative_to(ROOT);to.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,to)
    audit_code={str(p.relative_to(ROOT)):d.sha(p) for p in [Path(__file__),Path(d.__file__),ROOT/'tests/strategies/dm_sn1_slow_blend/test_blend.py']}
    run.update(status='running',command=sys.argv,scientific_source_run=str(source.relative_to(ROOT)),
               source_failure=origin['failure'],actual_trials=1,new_performance_trials=0,code_sha256=origin['code_sha256'],
               audit_code_sha256=audit_code,train_data_sha256=origin['train_data_sha256'],environment=origin['environment'])
    d.dump(output/'run.json',run)
    stage=output/'stage';stage.mkdir()
    for name,h in origin['train_data_sha256'].items():
        p=ROOT/config['input_dir']/name;assert d.sha(p)==h;(stage/name).symlink_to(p)
    keys={}
    for loader in [d.blend_features.sn_features,d.blend_features.slow_features]:
        for k,cols in loader.INPUT_COLUMNS.items():keys.setdefault(k,set()).update(cols)
    keys['listed_info'].add('Sector33Code')
    inputs={k:pd.read_parquet(stage/(k+'_train.parquet'),columns=sorted(cols)).sort_index() for k,cols in keys.items()}
    target=pd.read_parquet(stage/'target_1day_train.parquet').Return.sort_index()
    scores=pd.read_parquet(output/'predictions/strategy_scores.parquet')
    x=d.blend_features.sn_features.build_features({k:inputs[k][cols] for k,cols in d.blend_features.sn_features.INPUT_COLUMNS.items()})
    f=d.blend_features.slow_features.build_features({k:inputs[k][cols] for k,cols in d.blend_features.slow_features.INPUT_COLUMNS.items()},sector=False)
    d.exact(f.size_liquidity.rename(d.SLOW),scores[d.SLOW]);d.exact(scores[d.BLEND],d.blend_features.blend(scores[d.SN],scores[d.SLOW]))
    prefix=d.causality(inputs,target,scores[[d.SN,d.SLOW]],x,f,config,output/'audit')
    d.dump(output/'audit/prefix_invariance.json',prefix)
    adapted=d.submission.predict(stage).Return;d.exact(scores[d.BLEND].rename('Return'),adapted)
    d.dump(output/'audit/adapter_parity.json',{'status':'PASS','bitwise':True,'rows':len(adapted),'self_contained_components':True})
    tests=subprocess.run([sys.executable,str(ROOT/'tools/run_bounded.py'),'--seconds','180',sys.executable,'-m','pytest','-q',
        'tests/strategies/dm_sn1_slow_blend','tests/strategies/dm_variable_box_breakout/test_sn1.py','tests/strategies/dm_slow_multifactor','-k','not valid and not later'],cwd=ROOT,capture_output=True,text=True)
    (output/'logs/tests.log').write_text(tests.stdout+tests.stderr);assert tests.returncode==0,tests.stdout+tests.stderr
    check=subprocess.run(['make','check'],cwd=ROOT,capture_output=True,text=True);(output/'logs/make_check.log').write_text(check.stdout+check.stderr)
    workspace.validate_experiment(ROOT,ROOT/'experiments'/config['experiment_id'])
    for p,h in frozen:assert d.sha(p)==h
    d.dump(output/'audit/verification.json',{'status':'PASS','tests_returncode':tests.returncode,'tests_output':tests.stdout.strip(),
        'make_check_returncode':check.returncode,'make_check_output':check.stdout+check.stderr,
        'own_metadata':'PASS','existing_freeze_hashes':len(frozen),'existing_freeze_hashes_status':'PASS',
        'scientific_code_ast_change_only':changed,'added_function':'source_dates: audit-only JST normalization'})
    # Saved daily accounts, metrics and bootstrap only. No account/backtest call.
    results=pd.read_csv(output/'metrics/metrics.csv');incremental=pd.read_csv(output/'metrics/incremental.csv')
    ortho=pd.read_csv(output/'metrics/orthogonality_summary.csv');boot=json.loads((output/'metrics/bootstrap.json').read_text())
    decision=d.decisions(results,boot);d.dump(output/'metrics/decision.json',decision)
    for rel,h in scientific_hashes.items():assert d.sha(output/rel)==h,'Scientific performance artifact changed: '+rel
    d.dump(output/'audit/completion_parity.json',{'status':'PASS','all_saved_performance_artifacts_sha256':scientific_hashes,
        'performance_artifacts_unchanged':True,'new_performance_trials':0,'actual_unique_trials':1,
        'only_fix':'Audit dates compared on JST-naive wall dates, original component/PIT/parameters unchanged',
        'scientific_source_run':str(source.relative_to(ROOT)),'failure_retained':True})
    phases=json.loads((output/'audit/phase_gates.json').read_text())
    phases.extend([{'phase':'causality_audit_completed','at_utc':d.now(),'actual_trials':1},
                   {'phase':'decision_recorded','at_utc':d.now(),'actual_trials':1}]);d.dump(output/'audit/phase_gates.json',phases)
    resources={'elapsed_seconds':time.monotonic()-start,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),'actual_trials':1,'new_performance_trials':0,'valid_evaluation':False,'scope':'audit/report completion; scientific run elapsed recorded by timestamps'}
    d.dump(output/'audit/resources.json',resources);firewall.save(output/'audit/completion_firewall.json')
    d.report(config,output,results,incremental,ortho,boot,decision,resources)
    run.update(status='completed',completed_at_utc=d.now(),exit_code=0,decision=decision,resources=resources,
        artifact_sha256={str(p.relative_to(output)):d.sha(p) for folder in ['audit','metrics','models','predictions'] for p in (output/folder).rglob('*') if p.is_file()})
    d.dump(output/'run.json',run)
    print(json.dumps(d.safe({'decision':decision,'resources':resources}),indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    output=Path(args.output).resolve()
    try:complete(Path(args.source).resolve(),output)
    except BaseException as error:
        run=json.loads((output/'run.json').read_text());run.update(status='failed',exit_code=1,completed_at_utc=d.now(),failure=repr(error));d.dump(output/'run.json',run)
        if firewall._PATCHED:firewall.save(output/'audit/completion_firewall.json')
        raise
