"""Hash and publish the completed diagnostic records; never evaluates returns."""
from pathlib import Path
import json, shutil
from research.experiments.slow_multifactor import sha, dump
from research.experiments.slow_mom60_equal import now
from tools.workspace import validate_experiment
root=Path.cwd();exp=root/'experiments/DM-20261004-01';out=root/'artifacts/DM-20261004-01/run-20261003T172950Z';rep=root/'reports/DM-20261004-01'
run=json.loads((out/'run.json').read_text())
for rel,expected in run['artifact_sha256'].items():assert sha(out/rel)==expected,rel
for rel,expected in run['snapshot_sha256'].items():assert sha(out/rel)==expected,rel
for rel,expected in run['code_sha256'].items():assert sha(root/rel)==expected,rel
validate_experiment(root,exp)
assert sha(exp/'config.json')==sha(out/'config.json')
assert sha(exp/'plan.md')==sha(out/'plan.md')
v=json.loads((out/'audit/verification.json').read_text());assert v['own_metadata']=='PASS' and v['existing_freeze_hashes']==129
for parent in ['metrics','audit']:
 for path in (out/parent).glob('*'):
  if path.is_file():assert sha(path)==sha(rep/parent/path.name),path
conclusion={'phase':'diagnostic_conclusion','at_utc':now(),'classification':'F. Inconclusive',
 'interpretation':'Portfolio closely follows Size; Long profits concentrate in common Small+Illiquid; conditional Illiquidity inside Small remains positive; no unique economic source or interaction necessity identified',
 'performance_candidates':0,'diagnostic_bundles':1,'strategy_changed':False,'valid_accessed':False,
 'report_sha256':sha(rep/'REPORT.md'),'decision_sha256':sha(exp/'decision.md')}
dump(out/'audit/conclusion.json',conclusion);shutil.copyfile(out/'audit/conclusion.json',rep/'audit/conclusion.json')
for p in [rep/'REPORT.md',exp/'decision.md']:
 shutil.copyfile(p,out/p.name)
for p in [exp/'verify.py',exp/'finalize_report.py',Path(__file__).resolve()]:
 shutil.copyfile(p,out/'code_snapshot'/p.name)
manifest={'status':'DIAGNOSTIC_COMPLETE','at_utc':now(),'scientific_run':out.name,
 'config_sha256':sha(out/'config.json'),'plan_sha256':sha(out/'plan.md'),
 'artifact_sha256':{str(p.relative_to(out)):sha(p) for parent in ['metrics','audit','predictions','logs','code_snapshot'] for p in (out/parent).rglob('*') if p.is_file() and p.name!='final_manifest.json'},
 'report_sha256':sha(rep/'REPORT.md'),'decision_sha256':sha(exp/'decision.md'),
 'report_file_sha256':{str(p.relative_to(rep)):sha(p) for p in rep.rglob('*') if p.is_file() and p.name!='final_manifest.json'},
 'final_metadata_sha256':sha(exp/'experiment.json')}
dump(out/'final_manifest.json',manifest);dump(rep/'final_manifest.json',manifest)
print('DIAGNOSTIC COMPLETE:',len(manifest['artifact_sha256']),'hashed run files;',len(manifest['report_file_sha256']),'hashed report files')
