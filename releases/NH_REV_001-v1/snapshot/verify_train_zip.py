from pathlib import Path
import json,hashlib,resource,time,sys
import numpy as np,pandas as pd
from research import firewall
from stock_comp_2026.evaluate_script import load_prediction
root=Path.cwd(); release=root/'releases/NH_REV_001-v1'; run=root/'artifacts/DM-20260925-02/run-20260925T063642Z'; expected=run/'predictions.parquet'
firewall.install(allowed_artifacts=[expected])
start=time.monotonic(); a=load_prediction(release/'NH_REV_001.zip',run/'input_stage')
# Clear archive-local module so the second call actually loads the second extracted zip.
sys.modules.pop('features',None)
b=load_prediction(release/'NH_REV_001.zip',run/'input_stage')
y=pd.read_parquet(expected).NH_REV_001.rename('Return').to_frame()
pd.testing.assert_frame_equal(a,y,check_exact=True);pd.testing.assert_frame_equal(a,b,check_exact=True)
assert a.index.is_unique and np.isfinite(a).all().all()
firewall.save(release/'zip_train_firewall.json')
record={'pass':True,'zip_prediction_parity':'bitwise, all Train rows','deterministic_replay':'bitwise','rows':len(a),'columns':list(a.columns),'index_names':a.index.names,'elapsed_seconds_two_predictions':time.monotonic()-start,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'dependencies':['Python stdlib','numpy','pandas','parquet engine from official environment'],'runtime_external_dependencies':False,'target_read_during_inference':False,'zip_sha256':hashlib.sha256((release/'NH_REV_001.zip').read_bytes()).hexdigest()}
(release/'TRAIN_FREEZE_VERIFICATION.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
