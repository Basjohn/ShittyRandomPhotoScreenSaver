"""Repair uses current migrations/keys and never sacrifices authored data to a write."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_registry import get_visualizer_view_pose_keys
from tools import visualizer_preset_repair as repair

MODE='extruded_bubble'
NEW_KEYS=tuple('extruded_bubble_drift_'+name for name in ('large','small','fused','chains','snow','specks'))+(
    'extruded_bubble_ray_modulation','extruded_bubble_ray_shimmer','extruded_bubble_camera_projection')


def payload(values,layout='snapshot'):
    result={'mode':MODE,'preset_index':0,'name':'Authored witness','description':'Preserve me',
        'author_notes':{'nested':['not settings',42]},
        'starting_view':{key:require_canonical_default('widgets.spotify_visualizer.'+key)
                         for key in get_visualizer_view_pose_keys(MODE)}}
    if layout=='snapshot':result['snapshot']={'widgets':{'spotify_visualizer':values,'clock':{'keep':'unchanged'}}}
    elif layout=='settings':result['settings']=values
    elif layout=='dotted':result['settings']={**{'widgets.spotify_visualizer.'+key:value for key,value in values.items()},'other.preference':'untouched'}
    else:result['spotify_visualizer']=values
    return result


def section(data,layout):
    if layout=='snapshot':return data['snapshot']['widgets']['spotify_visualizer']
    if layout=='settings':return data['settings']
    if layout=='dotted':return {key.removeprefix('widgets.spotify_visualizer.'):value for key,value in data['settings'].items()
                                if key.startswith('widgets.spotify_visualizer.')}
    return data['spotify_visualizer']


@pytest.mark.parametrize('layout',('snapshot','settings','dotted','direct'))
def test_repair_keeps_all_new_authored_values_layout_metadata_and_backup(tmp_path,monkeypatch,layout):
    monkeypatch.setattr(repair,'_BACKUP_ROOT',tmp_path/'backups')
    values={key:[-.42,1.71] for key in NEW_KEYS if '_drift_' in key}
    values.update(extruded_bubble_ray_modulation=.41,extruded_bubble_ray_shimmer=.73,
                  extruded_bubble_camera_projection='Orthographic',extruded_bubble_camera_fov=53)
    original=payload(values,layout);before=deepcopy(original)
    path=tmp_path/'preset_1_authored.json';path.write_text(json.dumps(original),encoding='utf-8');raw=path.read_bytes()
    backup,_=repair.repair_file(path,MODE,sync_shipped_artifacts=False)
    assert backup.read_bytes()==raw
    result=json.loads(path.read_text(encoding='utf-8'));actual=section(result,layout)
    assert all(actual[key]==value for key,value in values.items())
    for key in ('name','description','author_notes','starting_view'):assert result[key]==before[key]
    if layout=='snapshot':assert result['snapshot']['widgets']['clock']==before['snapshot']['widgets']['clock']
    if layout=='settings':assert 'snapshot' not in result
    if layout=='dotted':assert result['settings']['other.preference']=='untouched'
    repaired=path.read_bytes();repair.repair_file(path,MODE,sync_shipped_artifacts=False)
    assert path.read_bytes()==repaired


def test_legacy_ray_rename_retains_authored_value_and_missing_keys_come_from_ssot():
    cleaned,_=repair._sanitize_settings(MODE,payload({'extruded_bubble_ray_flicker':.73}))
    assert cleaned['extruded_bubble_ray_shimmer']==.73
    assert 'extruded_bubble_ray_flicker' not in cleaned
    for key in set(NEW_KEYS)-{'extruded_bubble_ray_shimmer'}:
        assert cleaned[key]==require_canonical_default('widgets.spotify_visualizer.'+key)


def test_failed_atomic_promotion_leaves_source_bytes_intact(tmp_path,monkeypatch):
    from core.utils import atomic_files
    monkeypatch.setattr(repair,'_BACKUP_ROOT',tmp_path/'backups')
    path=tmp_path/'preset_1_witness.json';path.write_text(json.dumps(payload({'extruded_bubble_drift_chains':[0.,.5]})))
    before=path.read_bytes()
    def fail(*args):raise OSError('injected replacement failure')
    monkeypatch.setattr(atomic_files.os,'replace',fail)
    with pytest.raises(OSError,match='replacement failure'):repair.repair_file(path,MODE,sync_shipped_artifacts=False)
    assert path.read_bytes()==before
    assert not tuple(tmp_path.glob('*.tmp'))


def test_repair_refuses_an_explicitly_different_preset_mode(tmp_path,monkeypatch):
    monkeypatch.setattr(repair,'_BACKUP_ROOT',tmp_path/'backups')
    path=tmp_path/'preset_1_other.json';path.write_text(json.dumps({'mode':'bubble','settings':{'bubble_small_count':12}}))
    before=path.read_bytes()
    with pytest.raises(ValueError,match='mode'):repair.repair_file(path,MODE,sync_shipped_artifacts=False)
    assert path.read_bytes()==before


def test_repair_refuses_to_overwrite_a_newer_edit(tmp_path,monkeypatch):
    monkeypatch.setattr(repair,'_BACKUP_ROOT',tmp_path/'backups')
    path=tmp_path/'preset_1_concurrent.json';path.write_text(json.dumps(payload({})))
    original=repair._sanitize_settings
    newer=json.dumps(payload({'extruded_bubble_ray_shimmer':.91})).encode()
    def concurrent(mode,data):
        result=original(mode,data);path.write_bytes(newer);return result
    monkeypatch.setattr(repair,'_sanitize_settings',concurrent)
    with pytest.raises(RuntimeError,match='changed'):repair.repair_file(path,MODE,sync_shipped_artifacts=False)
    assert path.read_bytes()==newer


def test_backup_only_legacy_payload_migrates_to_one_live_section():
    data={'mode':MODE,'snapshot':{'custom_preset_backup':{
        'widgets.spotify_visualizer.extruded_bubble_ray_flicker':.73}}}
    cleaned,_=repair._sanitize_settings(MODE,data)
    repair._apply_cleaned_payload_in_place(data,cleaned)
    assert 'custom_preset_backup' not in data['snapshot']
    assert data['snapshot']['widgets']['spotify_visualizer']['extruded_bubble_ray_shimmer']==.73


@pytest.mark.parametrize('layout',('dotted','direct'))
def test_import_uses_the_same_authoritative_migration_as_repair(layout):
    data=payload({'extruded_bubble_ray_flicker':.73,'extruded_bubble_drift_chains':[0.,.5]},layout)
    parsed=repair.vp._parse_preset_payload(Path('preset_1_test.json'),data,MODE)
    assert parsed is not None
    assert parsed[1].settings['extruded_bubble_ray_shimmer']==.73
    assert parsed[1].settings['extruded_bubble_drift_chains']==[0.,.5]


def test_undo_failure_restores_every_before_image_without_deleting_destinations(tmp_path,monkeypatch):
    source_a=tmp_path/'a.json';source_b=tmp_path/'b.json'
    backup_a=tmp_path/'a.bak';backup_b=tmp_path/'b.bak'
    source_a.write_bytes(b'new a\r\n');source_b.write_bytes(b'new b\n')
    backup_a.write_bytes(b'old a\n');backup_b.write_bytes(b'old b\r\n')
    rows=((source_a,backup_a,source_b),(source_b,backup_b,source_a))
    entry=repair.UndoEntry(*rows[0],related=(rows[1],),expected_hashes=repair._undo_hashes(rows))
    before={path:path.read_bytes() for path in (source_a,source_b)}
    original=repair.atomic_write_bytes;calls=0
    def fail_second(path,data):
        nonlocal calls
        calls+=1
        if calls==2:raise OSError('injected second undo write')
        original(path,data)
    monkeypatch.setattr(repair,'atomic_write_bytes',fail_second)
    with pytest.raises(OSError,match='second undo write'):repair.restore_undo_entry(entry)
    assert {path:path.read_bytes() for path in before}==before
    monkeypatch.setattr(repair,'atomic_write_bytes',original)
    repair.restore_undo_entry(entry)
    assert source_a.read_bytes()==backup_a.read_bytes()
    assert source_b.read_bytes()==backup_b.read_bytes()


def test_undo_refuses_new_file_created_at_original_name(tmp_path):
    source=tmp_path/'old_name.json';target=tmp_path/'moved_name.json';backup=tmp_path/'backup.json'
    source.write_bytes(b'new operator file');target.write_bytes(b'operation output');backup.write_bytes(b'old preset')
    row=(source,backup,target)
    entry=repair.UndoEntry(*row,expected_hashes=repair._undo_hashes((row,)))
    with pytest.raises(RuntimeError,match='occupied'):repair.restore_undo_entry(entry)
    assert source.read_bytes()==b'new operator file' and target.read_bytes()==b'operation output'


def test_reindex_and_swap_preserve_all_new_eb_fields_and_starting_metadata(tmp_path,monkeypatch):
    monkeypatch.setattr(repair,'ROOT',tmp_path);monkeypatch.setattr(repair,'_BACKUP_ROOT',tmp_path/'backups')
    folder=tmp_path/'presets'/'visualizer_modes'/MODE;folder.mkdir(parents=True)
    authored={}
    for slot,suffix in ((1,'alpha'),(4,'beta')):
        values={key:[-.42,1.71] for key in NEW_KEYS if '_drift_' in key}
        values.update(extruded_bubble_ray_modulation=.41,extruded_bubble_ray_shimmer=.73,
                      extruded_bubble_camera_projection='Orthographic')
        data=payload(values);data['name']=f'Preset {slot} ({suffix})';data['preset_index']=slot-1
        authored[suffix]=deepcopy(data)
        (folder/f'preset_{slot}_{suffix}.json').write_text(json.dumps(data),encoding='utf-8')
    repair.reindex_mode_presets(MODE)
    repair.swap_mode_presets(MODE,folder/'preset_1_alpha.json',folder/'preset_2_beta.json',mode_dir=folder)
    for path in folder.glob('*.json'):
        suffix=path.stem.rsplit('_',1)[-1];actual=json.loads(path.read_text(encoding='utf-8'))
        for key,value in authored[suffix].items():
            if key not in ('name','preset_index'):assert actual[key]==value
