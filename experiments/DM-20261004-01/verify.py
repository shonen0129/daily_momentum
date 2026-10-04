from pathlib import Path
import json, hashlib
import numpy as np
import pandas as pd
from research import firewall
from research.experiments.slow_multifactor import exact, sha, dump
from stock_comp_2026 import evaluate_script as official
from tools.workspace import validate_experiment, digest
root=Path.cwd(); output=root/'artifacts/DM-20261004-01/run-20261003T172950Z'; report=root/'reports/DM-20261004-01'
config=json.loads((output/'config.json').read_text());run=json.loads((output/'run.json').read_text())
refs=config['saved_components']; scorepath=output/'predictions/components.parquet'
freeze_meta=json.loads((root/'experiments/DM-20260908/experiment.json').read_text())
freeze_snapshot=root/freeze_meta['freeze_root']
freeze_manifest=json.loads((root/freeze_meta['freeze_manifest']).read_text())
assert freeze_manifest['valid_evaluation'] is False
freeze_parquets=[freeze_snapshot/rel for sec in ['code_sha256','artifact_sha256'] for rel in freeze_manifest[sec] if rel.endswith('.parquet')]
firewall.install(allowed_artifacts=[scorepath, output/'predictions/diagnostic_transforms.parquet', output/'metrics/overlap_group_stock_days.parquet']+freeze_parquets)
scores=pd.read_parquet(scorepath)
target=pd.read_parquet(output/'stage/target_1day_train.parquet').Return
assert scores.index.equals(target.index)
net=official.compute_pl(scores[['SLOW_CONTROL']].rename(columns={'SLOW_CONTROL':'Return'}),target.to_frame()).groupby('Date').sum().rename('net')
old=pd.read_csv(root/refs['slow_daily']['path'],index_col=0,parse_dates=True,float_precision='round_trip').net.rename('net')
exact(net,old)
net.to_csv(output/'metrics/SLOW_full_history_official_net.csv',index_label='Date')
firewall.save(output/'audit/verification_firewall.json')
for rel,hsh in run['artifact_sha256'].items():assert sha(output/rel)==hsh,rel
for rel,hsh in run['code_sha256'].items():assert sha(root/rel)==hsh,rel
for rel,hsh in run['snapshot_sha256'].items():assert sha(output/rel)==hsh,rel
validate_experiment(root,root/'experiments/DM-20261004-01')
meta=json.loads((root/'experiments/DM-20260908/experiment.json').read_text());snap=root/meta['freeze_root'];manifest=root/meta['freeze_manifest']
assert digest(manifest)==meta['freeze_manifest_sha256']==digest(snap/meta['freeze_manifest'])
m=json.loads(manifest.read_text());count=0
for section in ['code_sha256','artifact_sha256']:
 for rel,expected in m[section].items():assert digest(snap/rel)==expected,rel;count+=1
metrics=pd.read_csv(output/'metrics/performance_metrics.csv')
assert len(metrics)==24 and metrics.strategy.nunique()==3 and metrics.scope.nunique()==8
required=['rankic','rankic_t_hac5','rankic_hit','gross_sharpe','net_sharpe','annual_gross','annual_net','turnover','annual_cost','max_drawdown','q_monotonicity','annual_long','annual_long_net','annual_short','annual_short_net']+[f'q{k}_daily_return' for k in range(1,6)]
assert np.isfinite(metrics[required].to_numpy()).all()
for book in ['SIZE_ONLY','ILLIQ_ONLY','SLOW_CONTROL']:
 d=pd.read_csv(output/f'metrics/daily_{book}.csv',index_col=0,parse_dates=True)
 assert len(d)==1275 and d.index.is_unique
 assert np.allclose(d.long_net+d.short_net,d.net,rtol=0,atol=1e-15)
 assert np.allclose(d.gross-d.cost,d.net,rtol=0,atol=1e-15)
ca=json.loads((output/'audit/prefix_invariance.json').read_text());assert len(ca['cases'])==20 and all(c['status']=='PASS' for c in ca['cases'])
v={'status':'PASS_WITH_EXISTING_WORKSPACE_METADATA_FAILURE','own_metadata':'PASS','existing_freeze_hashes':count,'existing_freeze_hashes_status':'PASS',
'config_plan_code_and_computed_artifact_hashes':'PASS','required_metrics_3x8_finite':'PASS','SLOW_full_saved_daily_net_bits':'PASS','SLOW_full_saved_daily_net_dates':len(net),
'regression_tests':{'diagnostics_and_original_slow':{'passed':16,'seconds':2.08},'runtime_firewall':{'passed':2,'seconds':4.62,'deselected':7}},
'make_check_returncode':2,'make_check_reason':'Preexisting DM-20261002-04 unknown experiment kind; unchanged; whole workspace check not passed',
'failed_run':{'id':'run-20261003T172859Z','reason':'Target hash under firewall registered an open before target-free phase assertion','performance_evaluations':0,'retained':True},
'performance_candidates':0,'completed_diagnostic_bundles':1,'result_driven_adjustments':0}
dump(output/'audit/verification.json',v)
(output/'logs/tests.log').write_text('Command: .venv/bin/python tools/run_bounded.py --seconds 180 .venv/bin/python -m pytest -q tests/workspace/test_slow_size_illiq_diagnostic.py tests/strategies/dm_slow_multifactor\n16 passed in 2.08s; exit0\nCommand: .venv/bin/python tools/run_bounded.py --seconds 180 .venv/bin/python -m pytest -q tests/test_causality.py -k runtime_firewall\n2 passed, 7 deselected in 4.62s; exit0\nRecorded from executed tool output; not a new test run.\n')
(output/'logs/make_check.log').write_text('.venv/bin/python tools/workspace.py check\nERROR: experiments/DM-20261002-04: unknown experiment kind\nmake: *** [check] Error 1\nexit2\n')
for p in [output/'audit/verification.json',output/'audit/verification_firewall.json',output/'metrics/SLOW_full_history_official_net.csv']:
 dest=report/p.relative_to(output);dest.write_bytes(p.read_bytes())
print(json.dumps(v,ensure_ascii=False,indent=2))
