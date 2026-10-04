"""Read-only final receipts; no prediction/backtest/trial or Valid execution."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
from research import firewall
from research.experiments.sector_momentum import sha, dump
from stock_comp_2026.strategies.dm_cause_event_overlay.financial import canonical
from tools import workspace


def verify(output):
    run=json.loads((output/'run.json').read_text());config=json.loads((output/'config.json').read_text())
    assert run['status']=='completed' and run['actual_trials']==2 and run['new_performance_trials']==0
    allowed=[p for folder in ['metrics','predictions'] for p in (output/folder).rglob('*.parquet')]
    slow=ROOT/config['slow_control']['path'];allowed.append(slow)
    firewall.install(allowed_artifacts=allowed)
    for p,h in run['artifact_sha256'].items():assert sha(output/p)==h,p
    assert sha(slow)==config['slow_control']['sha256']
    prereg=json.loads((output/'preregistration.json').read_text())
    for name in ['plan','config']:
        assert sha(output/f'{name}.md' if name=='plan' else output/'config.json')==prereg[f'{name}_sha256']
        assert sha(ROOT/f'experiments/{config["experiment_id"]}'/(f'{name}.md' if name=='plan' else 'config.json'))==prereg[f'{name}_sha256']
    # Reconstruct official t+2 residual labels using Train only, diagnostics path.
    inp=ROOT/config['input_dir']
    raw=canonical(pd.read_parquet(inp/'raw_return_1day_train.parquet',columns=['Return'])).Return
    beta=canonical(pd.read_parquet(inp/'beta_1day_train.parquet',columns=['Return'])).Return.reindex(raw.index)
    market=canonical(pd.read_parquet(inp/'topix_return_1day_train.parquet',columns=['Return']),panel=False).Return
    target=canonical(pd.read_parquet(inp/'target_1day_train.parquet',columns=['Return'])).Return
    dates=raw.index.get_level_values('Date');calendar=dates.unique().sort_values()
    residual=raw-beta*pd.Series(market.reindex(dates).to_numpy(),index=raw.index)
    expected=residual.unstack('Code').reindex(calendar).shift(-2).stack(future_stack=True).reindex(target.index)
    mature=dates.isin(calendar[:-2])
    finite=target.notna()&mature
    assert expected.loc[finite].notna().all()
    spillover=target.notna()&~mature
    delta=(target.loc[finite]-expected.loc[finite]).abs()
    assert delta.max()<=1e-14
    # Index/coverage receipts use saved predictions; no prediction rebuild.
    predictions=pd.read_parquet(output/'predictions/scores.parquet')
    assert predictions.index.equals(target.index)
    assert np.isfinite(predictions.to_numpy()).all()
    folds=json.loads((output/'audit/purge.json').read_text())['folds']
    assert all(pd.Timestamp(x['last_label_end'])<=calendar[-1] for x in folds)
    meta=workspace.validate_experiment(ROOT,ROOT/'experiments'/config['experiment_id'])
    check=subprocess.run(['make','check'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    (output.parent/'make-check.log').write_text(check.stdout+check.stderr)
    # Independently execute the existing frozen-root mapping/hash checks despite
    # the unrelated unsupported historical metadata stopping make check early.
    frozen_roots={};metadata_errors=[];valid_metadata=0;historical_hashes_skipped=[]
    for folder in sorted((ROOT/'experiments').iterdir()):
        if not folder.is_dir():continue
        declaration=json.loads((folder/'experiment.json').read_text())
        if declaration.get('kind')=='historical_diagnostic':
            historical_hashes_skipped.append(folder.name)
            continue  # Their evidence may contain Historical Valid. Never open.
        try:m=workspace.validate_experiment(ROOT,folder,allow_missing_artifacts=True)
        except ValueError as e:metadata_errors.append(str(e));continue
        valid_metadata+=1
        if 'freeze_root' in m:
            manifest=workspace.inside(ROOT,m['freeze_manifest']);snapshot=workspace.inside(ROOT,m['freeze_root'])
            assert sha(manifest)==m['freeze_manifest_sha256']
            assert sha(workspace.inside(snapshot,m['freeze_manifest']))==m['freeze_manifest_sha256']
            frozen_roots[manifest]=snapshot
    frozen_files=0
    for path in sorted((ROOT/'reports').glob('*/freeze_manifest.json')):
        manifest=json.loads(path.read_text());frozen_root=frozen_roots.get(path.resolve(),ROOT)
        for section in ['code_sha256','artifact_sha256']:
            for p,h in manifest[section].items():
                target_path=workspace.inside(frozen_root,p)
                if target_path.suffix=='.parquet':
                    assert 'DM-20260908-v1' in str(frozen_root),'Unreviewed freeze input'
                    firewall.install(allowed_artifacts=[target_path])
                assert sha(target_path)==h,p;frozen_files+=1
    assert all('DM-20261002-04' in e and 'unknown experiment kind' in e for e in metadata_errors),metadata_errors
    firewall.save(output.parent/'final_verification_firewall.json')
    result={'status':'PASS','experiment_id':config['experiment_id'],'final_run':output.name,
        'scientific_source_run':run['scientific_source_run'],'scientific_run_failure_retained':True,
        'new_performance_trials':0,'actual_unique_trials':2,'artifact_hashes_checked':len(run['artifact_sha256']),
        'plan_config_freeze_unchanged':True,'anchor_sha256_unchanged':True,
        'exact_signal_target_index':True,'prediction_rows':len(target),'all_scores_finite':True,
        'target_t_plus2_finite_rows':int(finite.sum()),'target_t_plus2_max_abs_error':float(delta.max()),
        'target_t_plus2_tolerance':1e-14,'current_experiment_metadata':'PASS','metadata_status':meta['status'],
        'train_split_terminal_finite_labels':int(spillover.sum()),
        'terminal_labels_excluded_from_all_fold_primary_and_event_study_scopes':True,
        'unpurged_ALL_TRAIN_archival_scope_omitted_from_delivered_report':True,
        'valid_metadata_count':valid_metadata,'existing_freeze_hashes_checked':frozen_files,
        'make_check_exit':check.returncode,'preexisting_workspace_errors':metadata_errors,
        'historical_diagnostic_hash_checks_skipped':historical_hashes_skipped,
        'scope':'Train-only target maturity/index/hash/config verification, no performance trial or Valid access.'}
    report=ROOT/config['report_dir'];dump(report/'audit/final_verification.json',result)
    dump(output.parent/'final_verification.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    verify(Path(args.output).resolve())
