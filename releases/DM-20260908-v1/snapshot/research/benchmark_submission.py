"""Isolated inference resource measurement; no labels and no evaluation."""
import json
from pathlib import Path
import resource
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stock_comp_2026/strategies/dm_trainonly'))
from research.firewall import install,save
install()
from submission import predict
start=time.monotonic()
p=predict(ROOT/'stock_comp_2026/input',split='train')
r={'rows':len(p),'seconds':time.monotonic()-start,
   'peak_rss_bytes_macos':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
   'split':'Train','labels_read':False,'gpu_required':False}
out=ROOT/'reports/DM-20260908'
(out/'submission_resources.json').write_text(json.dumps(r,indent=2))
save(out/'submission_data_access.json')
print(json.dumps(r,indent=2))
