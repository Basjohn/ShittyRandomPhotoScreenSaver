"""Complete preset camera state must arrive before native editor admission."""
from copy import deepcopy
import pytest
from PySide6.QtCore import QCoreApplication,QEvent

from core.settings import visualizer_presets as vp
from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_registry import build_visualizer_mode_activation,get_visualizer_view_pose_keys

MODE='extruded_bubble'


@pytest.fixture
def camera_catalog(monkeypatch):
    # Test-owned art/poses: an extreme P8-like orbit exposes stale-pose XYZ admission.
    keys=get_visualizer_view_pose_keys(MODE)
    home={key:require_canonical_default('widgets.spotify_visualizer.'+key) for key in keys}
    extreme=dict(zip(keys,(-.72,-.17,.424,.235,-.196)))
    art={key:deepcopy(value) for key,value in require_canonical_default('widgets.spotify_visualizer').items()
         if key.startswith(MODE+'_') and key not in keys}
    art.update(extruded_bubble_light_type='Deep Light',extruded_bubble_camera_position=[0.,0.,0.])
    presets=[vp.VisualizerPreset(f'Test {i+1}','isolated camera witness',deepcopy(art),starting_view=dict(home))
             for i in range(8)]
    presets[7].starting_view=extreme
    presets[1].starting_view={**home,'extruded_bubble_turn':.1}
    presets.append(vp.VisualizerPreset('Custom','isolated Custom',{},is_custom=True))
    monkeypatch.setattr(vp,'_PRESETS',{**vp._PRESETS,MODE:presets})
    return home


@pytest.mark.parametrize('camera_built',(False,True))
def test_p8_to_p1_admits_target_xyz_against_target_pose_on_first_selection(qt_app,tmp_path,camera_catalog,camera_built):
    from core.settings.settings_manager import SettingsManager
    from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping
    from ui.tabs.visualizers_tab import VisualizersTab
    from tests.test_extruded_bubble_lazy_bucket_ui import toggle_bucket
    config=deepcopy(require_canonical_default('widgets.spotify_visualizer'))
    config.update(mode=MODE,preset_extruded_bubble=7,mode_activation=build_visualizer_mode_activation([MODE]))
    config=vp.apply_preset_starting_view(MODE,7,vp.apply_preset_to_config(MODE,7,config))
    config=normalize_visualizer_section_mapping(config,apply_preset_overlay=False)
    manager=SettingsManager(application='CameraPresetActivation',storage_base_dir=tmp_path)
    manager.set('widgets',{'spotify_visualizer':config})
    tab=VisualizersTab(manager);tab._select_mode_page(MODE)
    try:
        if camera_built:toggle_bucket(tab,'camera')
        slider=tab._extruded_bubble_preset_slider._slider
        assert slider.value()==7
        slider.setValue(0);tab.flush_pending_changes()
        first=manager.get('widgets.spotify_visualizer')
        assert first['extruded_bubble_camera_position']==pytest.approx((0.,0.,0.))
        assert {key:first[key] for key in camera_catalog}==camera_catalog
        if camera_built:
            tab.resize(1100,850);tab.show();qt_app.processEvents()
            assert tab.grab().save(str(tmp_path/'p8_to_p1_camera_native.png'))
        slider.setValue(1);tab.flush_pending_changes()
        slider.setValue(0);tab.flush_pending_changes()
        again=manager.get('widgets.spotify_visualizer')
        assert again['extruded_bubble_camera_position']==pytest.approx(first['extruded_bubble_camera_position'])
        assert {key:again[key] for key in camera_catalog}==camera_catalog
        # A manual aim between activation and its coalesced save must win.
        from ui.tabs.media import framed_camera_editor as fce
        slider.setValue(1)
        fce.set_aim(tab,MODE,(.07,.03),commit=True)
        tab.flush_pending_changes()
        assert manager.get('widgets.spotify_visualizer.extruded_bubble_turn')==pytest.approx(.07)
        assert manager.get('widgets.spotify_visualizer.extruded_bubble_tilt')==pytest.approx(.03)
        tab._load_settings()
        assert fce.camera_angles(tab,MODE)==pytest.approx((.07,.03))
    finally:
        tab._flush_pending_visualizer_save();tab.close();tab.deleteLater()
        QCoreApplication.sendPostedEvents(tab,QEvent.Type.DeferredDelete)
        assert manager.flush(timeout=5.)


@pytest.mark.parametrize('auto_enabled',(False,True))
@pytest.mark.parametrize('held',('none','orbit','flight'))
def test_hidden_preset_activation_rebases_motion_before_first_target_capture(monkeypatch,auto_enabled,held):
    from types import SimpleNamespace as NS
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner
    from widgets.spotify_visualizer import view_orbit as vo
    state=NS()
    defaults=deepcopy(require_canonical_default('widgets.spotify_visualizer'))
    apply_presentation_vis_mode_kwargs(state,defaults)
    state._extruded_bubble_turn=-.7
    state._extruded_bubble_auto_rotate=True
    state._extruded_bubble_auto_rotate_after=2.
    state._extruded_bubble_auto_rotate_speed=18.
    vo.arm_view_auto_rotate(state,MODE,90.,immediate=True)
    if held in ('orbit','flight'):
        state._view_orbit_motion=vo.ViewOrbitMotion(MODE,-.7,0.,.02,.01,90.)
    if held=='flight':
        state._view_framed_flight_motion=vo.FramedFlightMotion(MODE,90.,(.2,0.,0.),-.7,0.,.02,.01,1.,1.)
    state._view_orbit_drag_velocity=object()
    state._view_orbit_inertia=object()
    target={**defaults,'extruded_bubble_turn':.15,'extruded_bubble_tilt':0.,
            'extruded_bubble_auto_rotate':auto_enabled,'extruded_bubble_auto_rotate_after':3.,
            'extruded_bubble_auto_rotate_speed':9.}
    engine=NS(begin_activation_transaction=lambda:None,end_activation_transaction=lambda **kw:None,
              cancel_pending_compute_tasks=lambda:None,reset_smoothing_state=lambda:None,
              reset_floor_state=lambda:None,get_generation_id=lambda:4,get_activation_id=lambda:5)
    controller=NS(mode_id=MODE,ensure_engine=lambda:engine,stop_logical_runtime=lambda:True,
                  record_resolved_activation=lambda _:None,presentation_state=state,
                  thread_manager=None,process_supervisor=None,playing=True,logical_tick_state=NS())
    owner=QuickDisplayVisualizerOwner.__new__(QuickDisplayVisualizerOwner)
    owner._controller=controller
    owner._runtime=NS(bind_visualizer_render_source=lambda *a,**kw:object())
    owner._pending_mode_activation=dict(kind='preset',mode=MODE,settings_model=object(),
        resolved_activation=object(),technical_cache={MODE:{}},logical_kwargs={},presentation_kwargs=target)
    import importlib
    owner_module=importlib.import_module('widgets.spotify_visualizer.quick_display_visualizer_owner')
    monkeypatch.setattr(owner_module.time,'time',lambda:100.)
    owner._apply_configuration=lambda **kw:apply_presentation_vis_mode_kwargs(state,kw['presentation_kwargs'])
    captures=[]
    def start():
        assert state._view_orbit_drag_velocity is None
        assert state._view_orbit_inertia is None
        captures.append(vo.apply_view_orbit_motion(state,MODE,target,100.))
        captures.append(vo.apply_view_orbit_motion(state,MODE,target,101.))
    owner._start_logical_runtime=start
    owner._activate_pending_mode(10.)
    assert captures[0]['extruded_bubble_turn']==pytest.approx(.15)
    delta=.02 if held!='none' else .05 if auto_enabled else 0.
    assert captures[1]['extruded_bubble_turn']==pytest.approx(.15+delta)
    assert captures[1]['extruded_bubble_tilt']==pytest.approx(.01 if held!='none' else 0.)
    if held=='flight':
        flight=state._view_framed_flight_motion
        assert flight.since==100. and (flight.strafe,flight.travel)==(1.,1.)
        assert captures[0]['extruded_bubble_camera_position']==pytest.approx(target['extruded_bubble_camera_position'])
        assert captures[1]['extruded_bubble_camera_position']!=pytest.approx(captures[0]['extruded_bubble_camera_position'])
