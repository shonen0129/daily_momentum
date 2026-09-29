"""Workspace metadata commands. No model imports, data reads, or training side effects."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = Path(__file__).resolve().parent / 'templates'
EXPERIMENT_ID = re.compile(r'DM-\d{8}-\d{2}')
STRATEGY = re.compile(r'[a-z][a-z0-9_]*')
RUN_ID = re.compile(r'run-\d{8}T\d{6}Z(?:-\d{2})?')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inside(root, relative):
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError(f'Path must stay inside workspace: {relative}')
    return path


def validate_id(value, pattern):
    if not pattern.fullmatch(value):
        raise ValueError(f'Invalid identifier: {value}')


def new_experiment(root, experiment_id, strategy):
    validate_id(experiment_id, EXPERIMENT_ID)
    validate_id(strategy, STRATEGY)
    datetime.strptime(experiment_id.split('-')[1], '%Y%m%d')
    parent = inside(root, 'experiments')
    parent.mkdir(exist_ok=True)
    destination = inside(root, f'experiments/{experiment_id}')
    # Reserve the directory exclusively; never overwrite even an empty prior experiment.
    destination.mkdir()
    try:
        for source, name in [('experiment_plan.md', 'plan.md'),
                             ('experiment_config.json', 'config.json'),
                             ('experiment_decision.md', 'decision.md')]:
            content = (TEMPLATES / source).read_text(encoding='utf-8')
            content = content.replace('__EXPERIMENT_ID__', experiment_id).replace('__STRATEGY__', strategy)
            (destination / name).write_text(content, encoding='utf-8')
        write_json(destination / 'experiment.json', {
            'schema_version': 1, 'experiment_id': experiment_id, 'kind': 'experiment',
            'status': 'draft', 'strategy': strategy, 'valid_evaluation': False,
        })
    except BaseException:
        shutil.rmtree(destination)
        raise
    return destination


def validate_experiment(root, folder, ready=False):
    meta = read_json(folder / 'experiment.json')
    if meta.get('schema_version') != 1 or meta.get('experiment_id') != folder.name:
        raise ValueError(f'{folder}: schema/experiment_id mismatch')
    if meta.get('kind') == 'historical_diagnostic':
        validate_id(folder.name, EXPERIMENT_ID)
        if meta.get('status') != 'archived' or meta.get('rerunnable') is not False:
            raise ValueError(f'{folder}: historical diagnostics must be archived and non-rerunnable')
        if meta.get('historical_valid_accessed') is not True or meta.get('valid_is_holdout') is not False:
            raise ValueError(f'{folder}: historical-valid access must remain explicit and non-holdout')
        if ready:
            raise ValueError('Archived historical diagnostics cannot reserve or execute a new run')
        references = meta.get('references')
        if not isinstance(references, list) or not references:
            raise ValueError(f'{folder}: archived diagnostics need hashed source and result references')
        for item in references:
            if not isinstance(item, dict) or not isinstance(item.get('path'), str):
                raise ValueError(f'{folder}: invalid diagnostic evidence reference')
            path = inside(root, item['path'])
            if not path.is_file() or digest(path) != item.get('sha256'):
                raise ValueError(f'{folder}: historical diagnostic evidence mismatch: {item.get("path")}')
        return meta
    if meta.get('kind') == 'legacy':
        if ready:
            raise ValueError('Legacy experiments cannot reserve new runs')
        for field in ('plan', 'report', 'freeze_manifest'):
            if not inside(root, meta[field]).is_file():
                raise ValueError(f'Missing legacy {field}: {meta[field]}')
        return meta
    if meta.get('kind') != 'experiment':
        raise ValueError(f'{folder}: unknown experiment kind')
    validate_id(folder.name, EXPERIMENT_ID)
    validate_id(meta['strategy'], STRATEGY)
    if meta.get('status') not in ('draft', 'planned', 'running', 'completed', 'rejected', 'frozen'):
        raise ValueError(f'{folder}: invalid status')
    if not (folder / 'decision.md').is_file():
        raise ValueError(f'{folder}: missing decision.md')
    plan = (folder / 'plan.md').read_text(encoding='utf-8')
    config = read_json(folder / 'config.json')
    if config.get('schema_version') != 1:
        raise ValueError(f'{folder}: invalid config schema')
    if config.get('experiment_id') != folder.name or config.get('strategy') != meta['strategy']:
        raise ValueError(f'{folder}: config identity mismatch')
    if config.get('data_split') != 'train' or config.get('valid_evaluation') is not False or meta.get('valid_evaluation') is not False:
        raise ValueError(f'{folder}: research must remain Train-only; record Valid in releases')
    if ready:
        if meta['status'] != 'planned':
            raise ValueError('prepare-run requires status=planned')
        if 'TODO' in plan:
            raise ValueError('Complete plan.md before preparing a run')
        for key in ('baseline', 'train_window', 'walk_forward_folds', 'confirmation_policy',
                    'feature_definitions', 'model', 'selection_rule'):
            if not config.get(key):
                raise ValueError(f'Complete config field: {key}')
        if not isinstance(config.get('parameters'), dict):
            raise ValueError('parameters must be an object (empty is allowed for a parameter-free model)')
        if type(config.get('random_seed')) is not int:
            raise ValueError('random_seed must be an integer')
        if type(config.get('purge_trading_days')) is not int or config['purge_trading_days'] < 2:
            raise ValueError('At least two trading days of purge are required')
        trials, budget = config.get('trials'), config.get('max_trials')
        if type(budget) is not int or budget < 1 or not isinstance(trials, list) or not 1 <= len(trials) <= budget:
            raise ValueError('List finite trials within a positive max_trials budget')
        trial_ids = [trial.get('trial_id') if isinstance(trial, dict) else None for trial in trials]
        if not all(isinstance(x, str) and x for x in trial_ids) or len(set(trial_ids)) != len(trial_ids):
            raise ValueError('Each trial needs a unique nonempty trial_id')
        if not inside(root, f"stock_comp_2026/strategies/{meta['strategy']}/submission.py").is_file():
            raise ValueError('Implement the strategy submission.py before preparing a run')
    return meta


def prepare_run(root, experiment_id, run_id=None):
    validate_id(experiment_id, EXPERIMENT_ID)
    folder = inside(root, f'experiments/{experiment_id}')
    validate_experiment(root, folder, ready=True)
    now = datetime.now(timezone.utc)
    run_id = run_id or now.strftime('run-%Y%m%dT%H%M%SZ')
    validate_id(run_id, RUN_ID)
    destination = inside(root, f'artifacts/{experiment_id}/{run_id}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    try:
        for name in ('plan.md', 'config.json', 'experiment.json'):
            shutil.copyfile(folder / name, destination / name)
        for name in ('models', 'predictions', 'metrics', 'audit', 'logs'):
            (destination / name).mkdir()
        write_json(destination / 'run.json', {
            'schema_version': 1, 'experiment_id': experiment_id, 'run_id': run_id,
            'status': 'prepared', 'created_at_utc': now.isoformat(),
            'snapshot_sha256': {name: digest(destination / name) for name in ('plan.md', 'config.json', 'experiment.json')},
            'command': None, 'code_sha256': None, 'environment': None,
            'train_data_sha256': None, 'completed_at_utc': None,
            'exit_code': None, 'actual_trials': None,
        })
    except BaseException:
        shutil.rmtree(destination)
        raise
    return destination


def check_workspace(root):
    for relative in ('WORKSPACE.md', 'docs/README.md', 'docs/workspace/architecture.md', 'docs/workspace/development_workflow.md',
                     'docs/strategies/momentum_liquidity.md', 'experiments/GRAVEYARD.md',
                     'experiments', 'artifacts', 'reports', 'releases', 'research/experiments',
                     'tests/workspace', 'tests/strategies', 'stock_comp_2026/strategies'):
        if not inside(root, relative).exists():
            raise ValueError(f'Missing workspace path: {relative}')
    count = 0
    frozen_roots = {}
    for folder in sorted((root / 'experiments').iterdir()):
        if folder.is_dir():
            meta = validate_experiment(root, folder)
            if 'freeze_root' in meta:
                manifest_path = inside(root, meta['freeze_manifest'])
                snapshot = inside(root, meta['freeze_root'])
                expected = meta['freeze_manifest_sha256']
                if digest(manifest_path) != expected or digest(inside(snapshot, meta['freeze_manifest'])) != expected:
                    raise ValueError(f'Freeze manifest mismatch: {folder.name}')
                frozen_roots[manifest_path] = snapshot
            count += 1
    checked = 0
    for path in sorted((root / 'reports').glob('*/freeze_manifest.json')):
        manifest = read_json(path)
        frozen_root = frozen_roots.get(path.resolve(), root)
        for section in ('code_sha256', 'artifact_sha256'):
            for relative, expected in manifest[section].items():
                target = inside(frozen_root, relative)
                if not target.is_file() or digest(target) != expected:
                    raise ValueError(f'Freeze mismatch: {relative}')
                checked += 1
    return f'PASS: {count} experiments; {checked} frozen file hashes; no input data opened'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('check')
    commands.add_parser('list')
    new = commands.add_parser('new-experiment')
    new.add_argument('experiment_id')
    new.add_argument('--strategy', required=True)
    run = commands.add_parser('prepare-run')
    run.add_argument('experiment_id')
    run.add_argument('--run-id')
    args = parser.parse_args()
    try:
        if args.command == 'check':
            print(check_workspace(ROOT))
        elif args.command == 'list':
            for folder in sorted((ROOT / 'experiments').iterdir()):
                if folder.is_dir():
                    meta = validate_experiment(ROOT, folder)
                    print(f"{folder.name}\t{meta['status']}\t{meta['strategy']}")
        elif args.command == 'new-experiment':
            print(new_experiment(ROOT, args.experiment_id, args.strategy))
        else:
            print(prepare_run(ROOT, args.experiment_id, args.run_id))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f'ERROR: {error}\n')


if __name__ == '__main__':
    main()
