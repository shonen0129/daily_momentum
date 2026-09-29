"""Infrastructure regression tests: no market data and no experiment execution."""
import json

import pytest

from tools.workspace import check_workspace, digest, inside, new_experiment, prepare_run, validate_experiment


def planned_experiment(root):
    folder = new_experiment(root, 'DM-20260909-01', 'dm_example_v2')
    meta = json.loads((folder / 'experiment.json').read_text())
    meta['status'] = 'planned'
    (folder / 'experiment.json').write_text(json.dumps(meta))
    (folder / 'plan.md').write_text('A completed economic hypothesis with finite Train-only evaluation.')
    config = json.loads((folder / 'config.json').read_text())
    config.update(random_seed=42, train_window=['2008-11-04', '2016-03-31'],
                  walk_forward_folds=[{'year': 2011}], confirmation_policy='No reselection',
                  feature_definitions={'momentum': 'lagged return'}, model='momentum', parameters={},
                  selection_rule='stable incremental net sharpe', max_trials=1,
                  trials=[{'trial_id': 'baseline'}])
    (folder / 'config.json').write_text(json.dumps(config))
    strategy = root / 'stock_comp_2026/strategies/dm_example_v2'
    strategy.mkdir(parents=True)
    (strategy / 'submission.py').write_text('# synthetic placeholder, never executed\n')
    return folder


def test_scaffold_preserves_existing_experiment_and_cannot_run_draft(tmp_path):
    folder = new_experiment(tmp_path, 'DM-20260909-01', 'dm_example_v2')
    (folder / 'plan.md').write_text('User work')
    with pytest.raises(FileExistsError):
        new_experiment(tmp_path, 'DM-20260909-01', 'dm_other')
    assert (folder / 'plan.md').read_text() == 'User work'
    with pytest.raises(ValueError, match='planned'):
        prepare_run(tmp_path, folder.name)
    assert not (tmp_path / 'artifacts').exists()


@pytest.mark.parametrize('identifier', ['../escape', '/tmp/escape', 'DM-20261340-01'])
def test_scaffold_rejects_bad_identifiers(tmp_path, identifier):
    with pytest.raises(ValueError):
        new_experiment(tmp_path, identifier, 'dm_example')
    assert not (tmp_path / 'experiments').exists()


def test_rejects_symlink_escape(tmp_path):
    root = tmp_path / 'workspace'
    outside = tmp_path / 'outside'
    root.mkdir()
    outside.mkdir()
    (root / 'experiments').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='inside workspace'):
        new_experiment(root, 'DM-20260909-01', 'dm_example')
    with pytest.raises(ValueError):
        inside(root, '../outside/file')
    assert not list(outside.iterdir())


def test_run_snapshot_survives_later_edits_and_refuses_overwrite(tmp_path):
    folder = planned_experiment(tmp_path)
    run = prepare_run(tmp_path, folder.name, 'run-20260909T000000Z')
    metadata = json.loads((run / 'run.json').read_text())
    assert metadata['status'] == 'prepared'
    assert metadata['exit_code'] is None
    for name, expected in metadata['snapshot_sha256'].items():
        assert digest(run / name) == expected
    original = (run / 'config.json').read_bytes()
    (folder / 'config.json').write_text((folder / 'config.json').read_text() + '\n')
    with pytest.raises(FileExistsError):
        prepare_run(tmp_path, folder.name, run.name)
    assert (run / 'config.json').read_bytes() == original


@pytest.mark.parametrize('change', [
    {'data_split': 'valid'}, {'valid_evaluation': True}, {'purge_trading_days': 0},
    {'max_trials': 0}, {'random_seed': None},
    {'max_trials': 2, 'trials': [{'trial_id': 'same'}, {'trial_id': 'same'}]},
])
def test_run_refuses_invalid_research_config(tmp_path, change):
    folder = planned_experiment(tmp_path)
    config = json.loads((folder / 'config.json').read_text())
    config.update(change)
    (folder / 'config.json').write_text(json.dumps(config))
    with pytest.raises(ValueError):
        prepare_run(tmp_path, folder.name)
    assert not (tmp_path / 'artifacts').exists()


def test_configuration_identity_must_match_registry(tmp_path):
    folder = planned_experiment(tmp_path)
    config = json.loads((folder / 'config.json').read_text())
    config['experiment_id'] = 'DM-20260909-02'
    (folder / 'config.json').write_text(json.dumps(config))
    with pytest.raises(ValueError, match='identity mismatch'):
        validate_experiment(tmp_path, folder)


def test_archived_historical_diagnostic_is_auditable_but_cannot_be_rerun(tmp_path):
    folder = tmp_path / 'experiments/DM-20260928-01'
    folder.mkdir(parents=True)
    plan = tmp_path / 'experiments/DM-20260928-01/plan.md'
    result = tmp_path / 'reports/DM-20260928-01/decision.md'
    result.parent.mkdir(parents=True)
    plan.write_text('Train and previously viewed Valid; descriptive diagnosis only.')
    result.write_text('Candidate rejected. Valid is not an independent holdout.')
    evidence = [
        {'path': str(path.relative_to(tmp_path)), 'sha256': digest(path)}
        for path in (plan, result)
    ]
    meta = {
        'schema_version': 1,
        'experiment_id': folder.name,
        'kind': 'historical_diagnostic',
        'status': 'archived',
        'historical_valid_accessed': True,
        'valid_is_holdout': False,
        'rerunnable': False,
        'references': evidence,
    }
    (folder / 'experiment.json').write_text(json.dumps(meta))

    assert validate_experiment(tmp_path, folder)['kind'] == 'historical_diagnostic'
    with pytest.raises(ValueError, match='cannot reserve or execute'):
        validate_experiment(tmp_path, folder, ready=True)

    result.write_text('Changed historical report')
    with pytest.raises(ValueError, match='evidence mismatch'):
        validate_experiment(tmp_path, folder)


def test_check_detects_modified_frozen_evidence(tmp_path):
    for path in ('experiments', 'artifacts', 'reports/test', 'releases', 'research/experiments',
                 'tests/workspace', 'tests/strategies', 'stock_comp_2026/strategies', 'docs'):
        (tmp_path / path).mkdir(parents=True, exist_ok=True)
    for path in ('WORKSPACE.md', 'docs/README.md', 'docs/workspace/architecture.md',
                 'docs/workspace/development_workflow.md', 'docs/strategies/momentum_liquidity.md',
                 'experiments/GRAVEYARD.md'):
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text('synthetic documentation')
    frozen = tmp_path / 'reports/test/evidence.txt'
    frozen.write_text('original evidence')
    manifest = {'code_sha256': {}, 'artifact_sha256': {'reports/test/evidence.txt': digest(frozen)}}
    (frozen.parent / 'freeze_manifest.json').write_text(json.dumps(manifest))
    assert '1 frozen file hashes' in check_workspace(tmp_path)
    frozen.write_text('changed evidence')
    with pytest.raises(ValueError, match='Freeze mismatch'):
        check_workspace(tmp_path)

    # Archived evidence stays authoritative while current documents can evolve.
    snapshot = tmp_path / 'releases/test/snapshot'
    (snapshot / 'reports/test').mkdir(parents=True)
    (snapshot / 'reports/test/evidence.txt').write_text('original evidence')
    archived_manifest = snapshot / 'reports/test/freeze_manifest.json'
    archived_manifest.write_bytes((frozen.parent / 'freeze_manifest.json').read_bytes())
    experiment = tmp_path / 'experiments/legacy'
    experiment.mkdir()
    (experiment / 'experiment.json').write_text(json.dumps({
        'schema_version': 1, 'experiment_id': 'legacy', 'kind': 'legacy',
        'plan': 'WORKSPACE.md', 'report': 'reports/test/evidence.txt',
        'freeze_manifest': 'reports/test/freeze_manifest.json',
        'freeze_root': 'releases/test/snapshot', 'freeze_manifest_sha256': digest(archived_manifest),
    }))
    assert '1 frozen file hashes' in check_workspace(tmp_path)
    (snapshot / 'reports/test/evidence.txt').write_text('corrupted archive')
    with pytest.raises(ValueError, match='Freeze mismatch'):
        check_workspace(tmp_path)
    archived_manifest.write_text('{}')
    with pytest.raises(ValueError, match='Freeze manifest mismatch'):
        check_workspace(tmp_path)
