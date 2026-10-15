"""Framed preset camera metadata seeds the one live owner, never artwork/reloads."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from core.settings import visualizer_presets as vp
from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_registry import build_visualizer_mode_activation, get_visualizer_view_pose_keys
from core.settings.visualizer_view_orbit import validate_visualizer_starting_view

MODE='shockwave_grid'
KEYS=get_visualizer_view_pose_keys(MODE)
HOME=dict(zip(KEYS,(.12,.24,1.8,.1,.55)))
LIVE=dict(zip(KEYS,(-.1,.4,1.2,-.1,-.05)))


def _payload(home=HOME):
    result={'mode':MODE,'name':'Test landscape','preset_index':0,
            'settings':{'mode':MODE,'shockwave_grid_wave_height':.32}}
    if home is not None:
        result['starting_view']=dict(home)
    return result


@pytest.fixture
def catalog(tmp_path,monkeypatch):
    root=tmp_path/'catalog'
    folder=root/MODE
    folder.mkdir(parents=True)
    for index,home in enumerate((HOME,None)):
        payload=_payload(home)
        payload['preset_index']=index
        (folder/f'preset_{index+1}_landscape.json').write_text(json.dumps(payload),encoding='utf-8')
    for name in ('_PRESETS','_PRESET_SOURCE_PATHS','_PRESET_SOURCE_SLOTS','_LOADED_SOURCE_PATHS'):
        monkeypatch.setattr(vp,name,dict(getattr(vp,name)))
    monkeypatch.setattr(vp,'_presets_root',lambda:root)
    monkeypatch.setattr(vp,'_snapshot_presets_root',lambda:tmp_path/'overrides')
    monkeypatch.setattr(vp,'_CURATED_TREE_SYNCED',True)
    vp.reload_presets(MODE)
    return folder


def _section(index=0):
    result=deepcopy(require_canonical_default('widgets.spotify_visualizer'))
    result.update(LIVE)
    result.update(mode=MODE,preset_shockwave_grid=index,
                  mode_activation=build_visualizer_mode_activation([MODE]))
    return result


def test_metadata_loads_separately_and_only_explicit_selection_changes_live_pose(catalog):
    assert vp.get_presets(MODE)[0].starting_view==HOME
    assert not set(KEYS)&set(vp.get_preset_settings(MODE,0))
    live=_section()
    assert {k:vp.resolve_visualizer_activation_payload(live).resolved_config[k] for k in KEYS}==LIVE
    selected=vp.apply_preset_starting_view(MODE,0,live)
    assert {k:selected[k] for k in KEYS}==HOME
    assert {k:live[k] for k in KEYS}==LIVE
    # Plain artwork hydration, resume and Custom preserve the adjusted pose.
    assert {k:vp.apply_preset_to_config(MODE,0,live)[k] for k in KEYS}==LIVE
    assert vp.apply_preset_starting_view(MODE,vp.get_custom_preset_index(MODE),live)==live
    assert not set(KEYS)&set(vp.build_normalized_custom_snapshot(MODE,selected))
    assert vp.resolve_visualizer_activation_payload({'mode':MODE,'preset_shockwave_grid':0}).resolved_config['shockwave_grid_scene_pan_y']==HOME['shockwave_grid_scene_pan_y']


def test_missing_metadata_uses_canonical_default_only_on_selection(catalog):
    selected=vp.apply_preset_starting_view(MODE,1,_section())
    assert {k:selected[k] for k in KEYS}=={k:require_canonical_default(f'widgets.spotify_visualizer.{k}') for k in KEYS}
    assert {k:vp.resolve_visualizer_activation_payload(_section(1)).resolved_config[k] for k in KEYS}==LIVE


@pytest.mark.parametrize('bad',[None,{}, {'camera_x':1}, {**HOME,'extra':1},
    {**HOME,KEYS[0]:True},{**HOME,KEYS[0]:'0.1'},{**HOME,KEYS[0]:float('nan')},
    {**HOME,KEYS[1]:float('inf')},{**HOME,KEYS[2]:100.},{**HOME,KEYS[4]:10**400}])
def test_invalid_or_foreign_camera_metadata_is_rejected(bad):
    with pytest.raises(ValueError):
        validate_visualizer_starting_view(MODE,bad)
    with pytest.raises(ValueError):
        vp._parse_preset_payload(Path('preset_1_invalid.json'),
                                 {**_payload(),'starting_view':bad},MODE)


def test_unframed_mode_cannot_acquire_camera_metadata():
    with pytest.raises(ValueError):
        validate_visualizer_starting_view('sphere',HOME)
    section={'mode':'sphere','sphere_turn':.3}
    assert vp.apply_preset_starting_view('sphere',0,section)==section


def test_runtime_cycle_seeds_target_home_and_custom_does_not_become_a_pose_cache(catalog):
    from core.settings.visualizer_runtime_preset_cycle import resolve_next_visualizer_runtime_preset
    section=_section(vp.get_custom_preset_index(MODE))
    target=resolve_next_visualizer_runtime_preset(section,{},mode=MODE)
    assert target.target_index==0
    assert {k:target.visualizer_config[k] for k in KEYS}==HOME
    assert not set(KEYS)&set(target.custom_presets[MODE])
    from types import SimpleNamespace
    from core.settings.models import SpotifyVisualizerSettings
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
    from widgets.spotify_visualizer.view_orbit import view_pose_values
    from dataclasses import asdict
    owner=SimpleNamespace()
    model=SpotifyVisualizerSettings.from_mapping(target.visualizer_config,apply_preset_overlay=False)
    apply_presentation_vis_mode_kwargs(owner,asdict(model))
    assert view_pose_values(owner,MODE)==HOME
    # A saved manual adjustment survives activation/hydration of that same preset.
    adjusted={**target.visualizer_config,**LIVE}
    assert {k:vp.resolve_visualizer_activation_payload(adjusted).resolved_config[k] for k in KEYS}==LIVE


def test_bad_metadata_file_is_logged_and_not_admitted(catalog,monkeypatch):
    path=catalog/'preset_3_invalid.json'
    path.write_text(json.dumps({**_payload(),'starting_view':{}}),encoding='utf-8')
    warnings=[]
    monkeypatch.setattr(vp.logger,'warning',lambda *args,**kw:warnings.append(args))
    vp.reload_presets(MODE)
    assert vp.get_preset_count(MODE)==3  # two authored files and Custom
    assert any(str(path.name) in str(args) and 'starting_view' in str(args) for args in warnings)


def test_explicit_override_preserves_camera_metadata(catalog):
    folder=catalog.parent.parent/'overrides'
    folder.mkdir()
    payload={**_payload(LIVE),'visualizer_preset_override':True,'visualizer_preset_mode':MODE}
    (folder/'preset_1_override.json').write_text(json.dumps(payload),encoding='utf-8')
    vp.reload_presets(MODE)
    assert vp.get_presets(MODE)[0].starting_view==LIVE


def test_unframed_save_ui_has_no_starting_camera_checkbox(qt_app):
    from ui.tabs.media.preset_slider import VisualizerPresetSlider
    slider=VisualizerPresetSlider('bubble')
    assert slider._include_starting_view is None
    slider.deleteLater()


@pytest.fixture
def body(catalog,qt_app,tmp_path):
    from core.settings.settings_manager import SettingsManager
    from ui.tabs.visualizers_tab import VisualizersTab
    manager=SettingsManager(application='PresetStartingViewTest',storage_base_dir=tmp_path/'profile')
    manager.set('widgets',{'spotify_visualizer':_section(vp.get_custom_preset_index(MODE))})
    tab=VisualizersTab(manager)
    tab._select_mode_page(MODE)
    try:
        yield tab,manager
    finally:
        tab._flush_pending_visualizer_save()
        tab.close()
        tab.deleteLater()
        qt_app.processEvents()
        assert manager.flush(timeout=5.)


def test_real_settings_selection_seeds_once_and_saves_preserve_adjustments(body):
    tab,manager=body
    slider=tab._shockwave_grid_preset_slider
    slider._slider.setValue(0)
    tab.flush_pending_changes()
    assert {k:manager.get('widgets.spotify_visualizer')[k] for k in KEYS}==HOME
    section=manager.get('widgets.spotify_visualizer')
    section.update(LIVE)
    manager.set('widgets.spotify_visualizer',section)
    tab._save_settings_now()
    tab._load_settings()
    assert {k:manager.get('widgets.spotify_visualizer')[k] for k in KEYS}==LIVE


@pytest.mark.parametrize('include',[True,False])
def test_actual_save_as_writes_optional_home_and_reload_reads_it(body,catalog,monkeypatch,include):
    from PySide6.QtWidgets import QDialog
    from ui.tabs.media import preset_slider as module
    from tools import visualizer_preset_repair as repair
    tab,manager=body
    slider=tab._shockwave_grid_preset_slider
    assert slider._include_starting_view.isChecked()
    assert not slider._include_starting_view.isHidden()
    slider._include_starting_view.setChecked(include)
    path=catalog/'preset_3_saved.json'
    monkeypatch.setattr(module.QFileDialog,'getSaveFileName',lambda *a,**k:(str(path),''))
    monkeypatch.setattr(module.StyledPopup,'exec',lambda *a:QDialog.DialogCode.Accepted)
    before=manager.get('widgets.spotify_visualizer')
    slider._save_custom_preset_as()
    payload=json.loads(path.read_text(encoding='utf-8'))
    assert ('starting_view' in payload)==include
    assert not set(KEYS)&set(payload['snapshot']['widgets']['spotify_visualizer'])
    if include:
        assert payload['starting_view']=={k:before[k] for k in KEYS}
    assert vp.get_presets(MODE)[2].starting_view==(payload.get('starting_view'))
    cleaned,_=repair._sanitize_settings(MODE,payload)
    repaired,_=repair._build_clean_payload(path,payload,MODE,cleaned)
    assert repaired.get('starting_view')==payload.get('starting_view')
    assert {k:manager.get('widgets.spotify_visualizer')[k] for k in KEYS}=={k:before[k] for k in KEYS}
