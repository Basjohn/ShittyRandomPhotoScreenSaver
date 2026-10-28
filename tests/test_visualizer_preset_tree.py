"""Directory authority, explicit deletion ownership and recoverable replacement."""
import json
from pathlib import Path

import pytest

from core import visualizer_preset_tree as tree
from tools.regenerate_visualizer_shipped_presets import audit_repo_shipped_visualizer_preset_artifacts


def preset(root, name='preset_1_art.json', *, slot=0):
    path = root / 'spectrum' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps({'mode': 'spectrum', 'preset_index': slot,
        'description': 'authored metadata', 'settings': {'spectrum_bar_width': 1.1}}).encode())
    return path


def contents(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_scan_reads_actual_named_files_and_never_writes_inventory(tmp_path):
    preset(tmp_path)
    preset(tmp_path, 'night_study.json', slot=5)
    preset(tmp_path, 'preset_9_custom.json', slot=8)
    before = contents(tmp_path)
    assert tree.scan_curated_visualizer_preset_tree(tmp_path) == {
        'spectrum/preset_1_art.json', 'spectrum/night_study.json'}
    assert contents(tmp_path) == before


def test_frozen_runtime_duplicate_slots_never_delete_or_select_by_mtime(tmp_path, monkeypatch):
    from core.settings import visualizer_presets as vp
    from copy import deepcopy
    for name in ('_PRESET_SOURCE_PATHS', '_PRESET_SOURCE_SLOTS', '_LOADED_SOURCE_PATHS'):
        monkeypatch.setattr(vp, name, deepcopy(getattr(vp, name)))
    a = preset(tmp_path, 'preset_1_alpha.json')
    b = preset(tmp_path, 'preset_1_beta.json')
    import os
    os.utime(a, (2000000000, 2000000000))  # Alpha is newer; runtime's existing lexical warning wins.
    before = contents(tmp_path)
    monkeypatch.setattr(vp, '_is_frozen_build', lambda: True)
    monkeypatch.setattr(vp, '_presets_root', lambda: tmp_path)
    monkeypatch.setattr(vp, '_snapshot_presets_root', lambda: tmp_path / 'no_overrides')
    catalogue = vp._build_presets_for_mode('spectrum')
    assert len(catalogue) == 2 and catalogue[-1].is_custom
    assert vp.get_preset_file_path('spectrum', 0) == b
    assert contents(tmp_path) == before


@pytest.mark.parametrize('failure', ('invalid_json', 'no_settings', 'wrong_mode', 'duplicate', 'empty'))
def test_invalid_source_cannot_mutate_target(tmp_path, failure):
    source, target = tmp_path / 'incoming', tmp_path / 'active'
    source.mkdir()
    if failure != 'empty':
        path = preset(source)
        if failure == 'invalid_json': path.write_bytes(b'{broken')
        if failure == 'no_settings': path.write_bytes(b'{}')
        if failure == 'wrong_mode': path.write_bytes(b'{"mode":"bubble","settings":{"mode":"bubble"}}')
        if failure == 'duplicate': preset(source, 'preset_1_second.json')
    preset(target, 'preset_9_valuable.json', slot=8)
    before = contents(target)
    with pytest.raises(ValueError): tree.replace_curated_visualizer_preset_tree(source, target)
    assert contents(target) == before


def test_explicit_replace_snapshots_source_and_preserves_unowned_files(tmp_path):
    source, target = tmp_path / 'incoming', tmp_path / 'active'
    authored = preset(source)
    preset(target, 'preset_9_stale.json', slot=8)
    custom = preset(target, 'preset_4_custom.json', slot=3)
    operator = preset(target, 'my_personal_art.json', slot=4)
    unknown = target / 'retired_mode' / 'preset_1_saved.json'
    unknown.parent.mkdir(); unknown.write_bytes(b'operator archive')
    source_before = contents(source)
    result = tree.replace_curated_visualizer_preset_tree(source, target)
    assert result == {'spectrum/preset_1_art.json'}
    assert (target / 'spectrum' / authored.name).read_bytes() == authored.read_bytes()
    assert not (target / 'spectrum/preset_9_stale.json').exists()
    assert custom.exists() and operator.exists() and unknown.read_bytes() == b'operator archive'
    assert contents(source) == source_before


def test_failed_promotion_rolls_back_every_byte_before_any_stale_deletion(tmp_path, monkeypatch):
    source, target = tmp_path / 'incoming', tmp_path / 'active'
    preset(source); preset(source, 'preset_2_second.json', slot=1)
    preset(target, 'preset_9_valuable.json', slot=8)
    before = contents(target)
    original = tree.atomic_write_bytes
    calls = 0
    def fail_second(path, data):
        nonlocal calls
        calls += 1
        if calls == 2: raise OSError('injected second promotion')
        original(path, data)
    monkeypatch.setattr(tree, 'atomic_write_bytes', fail_second)
    with pytest.raises(OSError, match='second promotion'):
        tree.replace_curated_visualizer_preset_tree(source, target)
    assert contents(target) == before


def test_concurrent_target_edit_is_preserved_and_prior_writes_roll_back(tmp_path, monkeypatch):
    source, target = tmp_path / 'incoming', tmp_path / 'active'
    preset(source); preset(source, 'preset_2_second.json', slot=1)
    newer = preset(target, 'preset_2_second.json', slot=1)
    original = tree.atomic_write_bytes
    def concurrent(path, data):
        original(path, data)
        if path.name == 'preset_1_art.json': newer.write_bytes(b'newer operator edit')
    monkeypatch.setattr(tree, 'atomic_write_bytes', concurrent)
    with pytest.raises(RuntimeError, match='changed during replacement'):
        tree.replace_curated_visualizer_preset_tree(source, target)
    assert newer.read_bytes() == b'newer operator edit'
    assert not (target / 'spectrum/preset_1_art.json').exists()


def test_rollback_never_clobbers_newer_edit_and_retains_before_images(tmp_path, monkeypatch):
    source, target = tmp_path / 'incoming', tmp_path / 'active'
    preset(source); preset(source, 'preset_2_second.json', slot=1)
    valuable = preset(target)
    before = valuable.read_bytes()
    valuable.write_bytes(b'older target bytes')
    original = tree.atomic_write_bytes
    recovery = tmp_path / 'recovery'
    monkeypatch.setattr(tree.tempfile, 'mkdtemp', lambda **_: (recovery.mkdir(), str(recovery))[1])
    def fail_after_newer_edit(path, data):
        if path == target / 'spectrum/preset_2_second.json':
            valuable.write_bytes(b'newer independent edit')
            raise OSError('injected failure')
        original(path, data)
    monkeypatch.setattr(tree, 'atomic_write_bytes', fail_after_newer_edit)
    with pytest.raises(RuntimeError, match='before-images at'):
        tree.replace_curated_visualizer_preset_tree(source, target)
    assert valuable.read_bytes() == b'newer independent edit'
    records = json.loads((recovery / 'recovery.json').read_text())
    record = next(r for r in records if r['path'] == str(valuable.absolute()))
    assert (recovery / record['before']).read_bytes() == b'older target bytes'
    assert preset(source).read_bytes() == before


def test_source_and_target_may_not_overlap(tmp_path):
    preset(tmp_path)
    with pytest.raises(ValueError, match='overlap'):
        tree.replace_curated_visualizer_preset_tree(tmp_path, tmp_path / 'nested')


def test_shipped_refresh_is_explicit_and_readonly_audit_uses_bytes(tmp_path):
    source = tmp_path / 'presets/visualizer_modes'
    original = preset(source).read_bytes()
    result = tree.refresh_shipped_visualizer_presets(tmp_path)
    assert result['entry_count'] == 1
    assert audit_repo_shipped_visualizer_preset_artifacts(tmp_path) == ()
    assert not tuple(tmp_path.rglob('*manifest*'))
    release = result['release_root'] / 'spectrum/preset_1_art.json'
    release.write_bytes(b'newer release art')
    assert 'release content drift: spectrum/preset_1_art.json' in audit_repo_shipped_visualizer_preset_artifacts(tmp_path)
    assert (source / 'spectrum/preset_1_art.json').read_bytes() == original
