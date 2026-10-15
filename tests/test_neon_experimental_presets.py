"""Preset schema/selection contracts; mutable artwork is never a golden."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from core.settings.default_contract import require_canonical_default
from core.settings.models import SpotifyVisualizerSettings
from core.settings.visualizer_mode_registry import get_visualizer_view_pose_keys
from core.settings.visualizer_presets import (
    apply_preset_to_config, build_normalized_custom_snapshot, get_custom_preset_index,
    get_presets, get_preset_file_path, resolve_visualizer_activation_payload,
    restore_visualizer_snapshot,
)
from core.settings.visualizer_settings_snapshot import normalize_visualizer_mode_payload


def test_each_current_neon_art_file_has_owned_schema_roundtrip_and_independent_view():
    from core.visualizer_preset_manifest import load_curated_visualizer_preset_manifest
    mode='shockwave_grid'
    root=Path(__file__).resolve().parents[1]/'presets'/'visualizer_modes'
    manifest=load_curated_visualizer_preset_manifest(root)
    view=get_visualizer_view_pose_keys(mode)
    for index,preset in enumerate(get_presets(mode)):
        if preset.is_custom:
            assert index==get_custom_preset_index(mode)
            continue
        source=get_preset_file_path(mode,index)
        assert source is not None and source.relative_to(root).as_posix() in manifest
        raw=json.loads(source.read_text())
        # Both canonical authored payload forms are intentionally supported.
        settings=raw.get('settings',raw.get('snapshot',{}).get('widgets',{}).get('spotify_visualizer',{}))
        assert not set(view)&set(settings)
        normalized=normalize_visualizer_mode_payload(mode,settings)
        assert normalize_visualizer_mode_payload(mode,normalized)==normalized
        model=SpotifyVisualizerSettings.from_mapping(normalized,apply_preset_overlay=False,resolve_preset_indices=False)
        assert normalize_visualizer_mode_payload(mode,model.to_dict())==normalized
        live={**require_canonical_default('widgets.spotify_visualizer'),
              'mode':mode,'preset_shockwave_grid':index,
              'shockwave_grid_turn':.12,'shockwave_grid_tilt':.31,
              'shockwave_grid_scene_scale':1.52,'shockwave_grid_scene_pan_x':.03,'shockwave_grid_scene_pan_y':-.04}
        applied=apply_preset_to_config(mode,index,live)
        assert all(applied[key]==live[key] for key in view)
        activation=resolve_visualizer_activation_payload(live)
        assert activation.preset_index==index and activation.mode==mode
        assert normalize_visualizer_mode_payload(mode,activation.resolved_config)==normalized


@pytest.mark.parametrize(('schema','selected','custom'),[(11,1,True),(11,0,False),(10,1,True),(10,2,True),(10,3,True),(12,1,False)])
def test_catalog_expansion_remaps_only_historical_selection(schema,selected,custom):
    from core.settings.visualizer_settings_contract import migrate_neon_experimental_catalog_selection
    old={'mode':'shockwave_grid','preset_shockwave_grid':selected,'shockwave_grid_glow':.271,
         'shockwave_grid_terrain':{'version':1,'size':2,'heights':[0.,.31,.44,0.]}}
    untouched=deepcopy(old)
    new=migrate_neon_experimental_catalog_selection(old,schema_version=schema)
    assert old==untouched
    assert new['preset_shockwave_grid']==(get_custom_preset_index('shockwave_grid') if custom else selected)
    assert {k:v for k,v in new.items() if k!='preset_shockwave_grid'}=={k:v for k,v in old.items() if k!='preset_shockwave_grid'}


@pytest.mark.qt
@pytest.mark.parametrize('schema',[10,11])
def test_isolated_settings_schema_upgrade_preserves_live_custom_and_cache_before_overlay(qt_app,tmp_path,monkeypatch,schema):
    from core.settings.settings_manager import SettingsManager
    import core.settings.visualizer_presets as presets
    app='NeonPresetMigrationTest'
    manager=SettingsManager(organization='TestOrg',application=app,storage_base_dir=tmp_path)
    live=deepcopy(require_canonical_default('widgets.spotify_visualizer'))
    live.update({'mode':'shockwave_grid','preset_shockwave_grid':1,'shockwave_grid_glow':.271,
                 'shockwave_grid_terrain':{'version':1,'size':3,'heights':[.23,.11,0.,.44,0.,0.,.56,.31,.07]},
                 'shockwave_grid_moon_phase':.17,'shockwave_grid_input_gain':.83,
                 'shockwave_grid_shape_nodes':[[0.,.19],[.43,.72],[1.,.31]],
                 'shockwave_grid_scene_scale':1.63,'shockwave_grid_scene_pan_x':.06})
    custom=build_normalized_custom_snapshot('shockwave_grid',live)
    manager._settings.setValue('widgets',{'spotify_visualizer':deepcopy(live)})
    manager._settings.setValue('visualizer_custom_presets',{'shockwave_grid':deepcopy(custom)})
    manager._settings.update_metadata(visualizer_schema_version=schema)
    assert manager.flush(timeout=5.)
    original=presets.apply_preset_to_config
    def reject_experiment_overlay(mode,index,config,*args,**kwargs):
        if mode=='shockwave_grid':
            assert int(index) in (0,get_custom_preset_index(mode)), 'historical Custom became an experimental slot'
        return original(mode,index,config,*args,**kwargs)
    monkeypatch.setattr(presets,'apply_preset_to_config',reject_experiment_overlay)
    reloaded=SettingsManager(organization='TestOrg',application=app,storage_base_dir=tmp_path)
    saved=reloaded.get('widgets.spotify_visualizer')
    assert saved['preset_shockwave_grid']==get_custom_preset_index('shockwave_grid')
    assert normalize_visualizer_mode_payload('shockwave_grid',saved)==custom
    assert reloaded.get('visualizer_custom_presets')['shockwave_grid']==custom
    assert saved['shockwave_grid_scene_scale']==live['shockwave_grid_scene_scale']
    assert saved['shockwave_grid_scene_pan_x']==live['shockwave_grid_scene_pan_x']
    assert reloaded._settings.metadata()['visualizer_schema_version']==SettingsManager._VISUALIZER_SCHEMA_VERSION
    # A newly selected experiment at runtime index1 must survive the next load;
    # the historical remap is versioned, never heuristic runtime selection.
    saved['preset_shockwave_grid']=1
    reloaded._settings.setValue('widgets',{'spotify_visualizer':saved})
    assert reloaded.flush(timeout=5.)
    again=SettingsManager(organization='TestOrg',application=app,storage_base_dir=tmp_path)
    assert again.get('widgets.spotify_visualizer.preset_shockwave_grid')==1
    # The independent Custom snapshot still restores every authored mode value.
    applied=apply_preset_to_config('shockwave_grid',0,dict(saved))
    assert restore_visualizer_snapshot('shockwave_grid',applied,custom)
    assert normalize_visualizer_mode_payload('shockwave_grid',applied)==custom
