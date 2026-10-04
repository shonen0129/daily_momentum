"""Hash-verified finalization after own-artifact copy guard failure; no refit."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from research import firewall
from research.experiments.slow_multifactor import dump,sha

ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    source=Path(args.source).resolve();output=Path(args.output).resolve()
    s=json.loads((source/'run.json').read_text());r=json.loads((output/'run.json').read_text());c=json.loads((source/'config.json').read_text())
    assert r['status']=='prepared' and s['status']=='failed' and 'Train-only parquet guard denied' in s['error']
    assert s['error'].startswith('Error(') and c['diagnostic_only'] and not c['valid_evaluation']
    assert sha(source/'config.json')==sha(output/'config.json') and sha(source/'plan.md')==sha(output/'plan.md')
    for rel,expected in s['code_sha256'].items():assert sha(source/'code_snapshot'/rel)==expected,rel
    # The descriptor and original immutable feature definitions are unchanged.
    for rel in ['research/experiments/slow_style_descriptors.py','stock_comp_2026/strategies/dm_slow_multifactor/features.py']:
        assert sha(ROOT/rel)==s['code_sha256'][rel]
    required=['portfolio_metrics.csv','daily_characteristics.csv','style_profile.csv','double_sort.csv',
              'cohort_contribution.csv','book_distributions.csv','descriptor_coverage.csv','regime_factor_ols.csv']
    for name in required:assert (source/'metrics'/name).is_file()
    for name in ['slow_parity','source_scan','prefix_invariance','matching','target_free_build','coverage']:
        assert json.loads((source/f'audit/{name}.json').read_text())['status']=='PASS'
    report=ROOT/c['report_dir'];report.mkdir(exist_ok=True)
    names=[p.name for p in (source/'metrics').glob('*.parquet')]
    own=[base/'metrics'/name for base in [source,output,report] for name in names]
    firewall.install(allowed_artifacts=own)
    hashes={}
    for section in ['metrics','audit']:
        (report/section).mkdir(exist_ok=True)
        for src in (source/section).iterdir():
            if not src.is_file():continue
            expected=sha(src);hashes[str(src.relative_to(source))]=expected
            for dst in [output/section/src.name,report/section/src.name]:
                if dst.exists():assert sha(dst)==expected,(src,dst)
                else:shutil.copyfile(src,dst)
                assert sha(dst)==expected
    shutil.copytree(source/'code_snapshot',output/'code_snapshot')
    dst=output/'code_snapshot/research/experiments/slow_style_finalize.py';shutil.copyfile(Path(__file__),dst)
    record={'status':'PASS','scientific_source':str(source.relative_to(ROOT)),
            'scientific_source_status':'failed only copying own parquet artifacts after completed diagnostics',
            'source_code_snapshot_hash_verified':True,'same_config_and_plan':True,'source_result_sha256':hashes,
            'scientific_rerun':False,'additional_performance_trials':0,'finalizer_sha256':sha(__file__)}
    dump(output/'audit/saved_result_finalization.json',record);dump(report/'audit/saved_result_finalization.json',record)
    r.update(status='completed',completed_at_utc=datetime.now(timezone.utc).isoformat(),exit_code=0,actual_trials=0,
             diagnostic_bundles=1,finalization_only=True,scientific_source=str(source.relative_to(ROOT)),
             train_data_sha256=s['train_data_sha256'],environment=s['environment'],resources=json.loads((source/'audit/resources.json').read_text()),
             command=['.venv/bin/python','-m','research.experiments.slow_style_finalize','--source',str(source.relative_to(ROOT)),'--output',str(output.relative_to(ROOT))],
             code_sha256={**s['code_sha256'],'research/experiments/slow_style_finalize.py':sha(__file__)},
             artifact_sha256={str(f.relative_to(output)):sha(f) for section in ['metrics','audit'] for f in (output/section).iterdir() if f.is_file()})
    dump(output/'run.json',r)
    print('PASS saved-result finalization; zero additional calculations/trials')


if __name__=='__main__':main()
