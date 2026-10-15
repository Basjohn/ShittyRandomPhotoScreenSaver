"""Framed 3D pose changes through real Quick window input and canonical Settings."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent

from core.settings import SettingsManager
from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor, get_visualizer_view_pose_keys
from core.settings.visualizer_presets import VISUALIZER_CUSTOM_STORAGE_KEY
from engine.display_manager import DisplayManager
from rendering.quick.ctrl_coordinator import SharedCtrlCoordinator
from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner
from rendering.quick.display_unit import create_quick_display_unit
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from tests.test_qtquick_custom_layout_owner import _configure_visualizer, _LiveCommitEngine
from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner
from widgets.spotify_visualizer.view_orbit import view_pose_values

MODE = 'shockwave_grid'
ALT = Qt.KeyboardModifier.AltModifier
NONE = Qt.KeyboardModifier.NoModifier


@pytest.fixture
def card(qt_app, tmp_path, monkeypatch):
    from rendering import runtime_input
    monkeypatch.setattr(runtime_input, 'suppress_runtime_pointer_input', lambda *a, **k: None)
    settings = SettingsManager(application='FramedScenePoseTest', storage_base_dir=tmp_path)
    widgets = settings.get_widgets_map()
    widgets['spotify_visualizer'].update({'enabled': True, 'mode': MODE, 'position': 'Custom', 'monitor': '1'})
    settings.set_widgets_map(widgets)
    factory = QuickSceneFactory()
    unit = create_quick_display_unit(screen=qt_app.primaryScreen(), screen_index=0, runtime_generation=617,
                                    scene_factory=factory, window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
                                    ctrl_coordinator=SharedCtrlCoordinator(), adapters=())
    unit.runtime.window.resize(1000, 700)
    visualizer = QuickDisplayVisualizerOwner(unit.runtime, bar_count=24, initial_mode=MODE,
        card_shadow_kwargs={'background_color': (0, 0, 0, 0), 'border_color': (255, 255, 255, 255),
                            'border_width': 4., 'corner_radius': 6., 'content_inset': 14.,
                            'shadow_enabled': False, 'shadow_color': (0, 0, 0, 0), 'shadow_blur': 0.,
                            'shadow_offset': (0., 0.), 'shadow_spread': 0., 'shadow_extensions': (0., 0., 0., 0.)},
        engine_factory=lambda count: _LiveCommitEngine())
    unit.attach_visualizer_owner(visualizer)
    layout = QuickCustomLayoutOwner(settings_manager=settings, participants_provider=lambda: (unit,),
        visualizer_provider=lambda: (visualizer, unit), reload_request=lambda reason: None, live_config_commit=lambda config: None)
    manager = DisplayManager.__new__(DisplayManager)
    manager._quick_visualizer_owner = visualizer
    manager._quick_visualizer_unit = unit
    manager._quick_custom_layout_owner = layout
    manager._runtime_generation = 617
    manager._quick_view_orbit_pending = None
    manager._quick_view_pose_owner = None
    manager._quick_scene_view_gesture = None
    manager._widgets_config_snapshot = widgets
    manager.settings_manager = settings
    manager._refresh_all_quick_context_menus = lambda: None
    manager._refresh_quick_visualizer_edit_content_envelope = lambda *a: None
    _configure_visualizer(visualizer, playing=True)
    visualizer.configure_committed_layout(local_rect=(220., 180., 480., 210.), viewport_extent=(160., 90.))
    visualizer.bind(engine_generation=3, activation_id=5)
    visualizer._apply_resolved_presentation(visualizer._resolve_current_presentation())
    # Wire the same generation-fenced product callbacks as runtime binding.
    for signal, callback in [('view_orbit_requested', manager._orbit_quick_visualizer_view),
        ('view_orbit_rates_changed', manager._set_quick_view_orbit_rates),
        ('view_orbit_finished', manager._persist_quick_visualizer_view),
        ('visualizer_move_started', manager._start_quick_visualizer_move),
        ('visualizer_move_requested', manager._move_quick_visualizer),
        ('visualizer_scale_requested', manager._scale_quick_visualizer),
        ('visualizer_gesture_finished', manager._finish_quick_visualizer_gesture)]:
        getattr(unit.runtime, signal).connect(lambda *args, cb=callback: manager._route_quick_visualizer_input(unit, cb, *args))
    unit.runtime.input_controller.set_interaction_mode_enabled(True)
    unit.runtime.input_controller.set_view_orbit_enabled(True)
    unit.runtime.input_controller.set_scene_transform_enabled(True, mode_id=MODE)
    writes = []
    original = settings.replace_visualizer_runtime_preset_state
    def save(section, custom):
        writes.append(deepcopy(section))
        return original(section, custom)
    monkeypatch.setattr(settings, 'replace_visualizer_runtime_preset_state', save)
    try:
        yield SimpleNamespace(unit=unit, window=unit.runtime.window, scene=unit.runtime.scene_controller,
                              visualizer=visualizer, manager=manager, settings=settings, layout=layout,
                              writes=writes, tmp_path=tmp_path)
    finally:
        layout.retire()
        unit.retire()
        factory.deleteLater()
        qt_app.processEvents()


def point(card):
    presentation = card.scene.visualizer_item.presentation
    x, y, w, h = presentation.outer_rect
    return QPointF(x + w / 2, y + h / 2)


def mouse(card, kind, position, button, modifiers=ALT):
    global_position = QPointF(card.window.mapToGlobal(position.toPoint()))
    buttons = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else button
    event = QMouseEvent(kind, position, global_position, button, buttons, modifiers)
    QCoreApplication.sendEvent(card.window, event)


def wheel(card, position, delta=120):
    event = QWheelEvent(position, QPointF(card.window.mapToGlobal(position.toPoint())), QPoint(), QPoint(0, delta),
                        Qt.MouseButton.NoButton, ALT, Qt.ScrollPhase.NoScrollPhase, False)
    QCoreApplication.sendEvent(card.window, event)


def release_alt(card):
    QCoreApplication.sendEvent(card.window, QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Alt, NONE))


def pose(card):
    return view_pose_values(card.visualizer.controller.presentation_state, MODE)


@pytest.mark.parametrize('editing', [False, True])
def test_native_pan_zoom_and_orbit_never_change_card_layout(card, editing):
    if editing:
        assert card.layout.start()
    baseline = deepcopy(card.settings.get_widgets_map())
    presentation = card.scene.visualizer_item.presentation
    viewport = deepcopy(card.visualizer.controller.committed_viewport_extent)
    # TEST INPUT: saved stage aspect is intentionally unlike its independent viewport.
    assert presentation.outer_rect[2:] == (480., 210.)
    assert presentation.viewport_extent == (160., 90.)
    assert presentation.border_width == 4.
    before = pose(card)
    p = point(card)
    delta = QPointF(46., 23.)
    mouse(card, QEvent.Type.MouseButtonPress, p, Qt.MouseButton.RightButton)
    mouse(card, QEvent.Type.MouseMove, p + delta, Qt.MouseButton.RightButton)
    interior_w, interior_h = presentation.content_rect[2:]
    assert pose(card)['shockwave_grid_scene_pan_x'] == pytest.approx(before['shockwave_grid_scene_pan_x'] + delta.x() / interior_w)
    assert pose(card)['shockwave_grid_scene_pan_y'] == pytest.approx(before['shockwave_grid_scene_pan_y'] + delta.y() / interior_h)
    assert card.writes == []
    wheel(card, p + delta)
    assert pose(card)['shockwave_grid_scene_scale'] > before['shockwave_grid_scene_scale']
    # Pan continues from its press, unaffected by internal zoom.
    mouse(card, QEvent.Type.MouseMove, p + delta + QPointF(10., 5.), Qt.MouseButton.RightButton)
    assert pose(card)['shockwave_grid_scene_pan_x'] == pytest.approx(before['shockwave_grid_scene_pan_x'] + 56. / interior_w)
    mouse(card, QEvent.Type.MouseButtonRelease, p + delta, Qt.MouseButton.RightButton)
    assert card.writes == []  # wheel still owns the same gesture until Alt release
    release_alt(card)
    assert len(card.writes) == 1
    live = pose(card)
    assert {key: card.settings.get('widgets.spotify_visualizer')[key] for key in live} == pytest.approx(live)
    assert card.scene.visualizer_item.presentation == presentation
    assert card.visualizer.controller.committed_viewport_extent == viewport
    after = card.settings.get_widgets_map()
    for key, value in baseline.items():
        if key != 'spotify_visualizer':
            assert after[key] == value
    for key, value in baseline['spotify_visualizer'].items():
        if key not in get_visualizer_view_pose_keys(MODE):
            assert after['spotify_visualizer'][key] == value
    # Next native press captures the current pan after zoom, not an old baseline.
    mouse(card, QEvent.Type.MouseButtonPress, p, Qt.MouseButton.RightButton)
    mouse(card, QEvent.Type.MouseMove, p + QPointF(5., 0.), Qt.MouseButton.RightButton)
    mouse(card, QEvent.Type.MouseButtonRelease, p, Qt.MouseButton.RightButton)
    assert pose(card)['shockwave_grid_scene_pan_x'] == pytest.approx(live['shockwave_grid_scene_pan_x'] + 5. / interior_w)
    assert len(card.writes) == 2
    # Alt-left retains orbit, and its settlement keeps all transform keys.
    pan_scale = {key: value for key, value in pose(card).items() if 'scene_' in key}
    mouse(card, QEvent.Type.MouseButtonPress, p, Qt.MouseButton.LeftButton)
    mouse(card, QEvent.Type.MouseMove, p + QPointF(8., 4.), Qt.MouseButton.LeftButton)
    mouse(card, QEvent.Type.MouseButtonRelease, p, Qt.MouseButton.LeftButton)
    assert {key: pose(card)[key] for key in pan_scale} == pan_scale
    assert card.scene.visualizer_item.presentation == presentation
    assert len(card.writes) == 3


def test_hit_test_and_closed_input_reject_scene_changes(card):
    before = pose(card)
    outside = QPointF(20., 20.)
    mouse(card, QEvent.Type.MouseButtonPress, outside, Qt.MouseButton.RightButton)
    wheel(card, outside)
    assert pose(card) == before and card.writes == []
    card.unit.runtime.input_controller.set_view_orbit_enabled(False)
    wheel(card, point(card))
    assert pose(card) == before
    card.unit.runtime.input_controller.close_input()
    card.unit.runtime.visualizer_scale_requested.emit(120)
    assert pose(card) == before and card.writes == []


def test_stale_generation_or_mode_pan_cannot_write_or_move_geometry(card):
    p = point(card)
    before = pose(card)
    mouse(card, QEvent.Type.MouseButtonPress, p, Qt.MouseButton.RightButton)
    card.manager._runtime_generation += 1
    mouse(card, QEvent.Type.MouseMove, p + QPointF(20., 10.), Qt.MouseButton.RightButton)
    mouse(card, QEvent.Type.MouseButtonRelease, p, Qt.MouseButton.RightButton)
    assert pose(card) == before and card.writes == []
    card.manager._runtime_generation = 617
    card.manager._quick_scene_view_gesture = None
    mouse(card, QEvent.Type.MouseButtonPress, p, Qt.MouseButton.RightButton)
    card.visualizer.controller._mode_id = 'extruded_spectrum'
    card.manager._begin_quick_visualizer_gesture = lambda: pytest.fail('stale scene gesture entered CUSTOM')
    mouse(card, QEvent.Type.MouseMove, p + QPointF(20., 10.), Qt.MouseButton.RightButton)
    mouse(card, QEvent.Type.MouseButtonRelease, p, Qt.MouseButton.RightButton)
    assert card.writes == []
    card.visualizer.controller._mode_id = MODE


def test_saved_view_survives_reload_import_and_stays_outside_presets(card):
    from core.settings.visualizer_presets import apply_preset_to_config, build_normalized_custom_snapshot, get_presets
    from core.settings.visualizer_settings_snapshot import normalize_visualizer_mode_payload
    p = point(card)
    wheel(card, p)
    release_alt(card)
    mouse(card, QEvent.Type.MouseButtonPress, p, Qt.MouseButton.RightButton)
    mouse(card, QEvent.Type.MouseMove, p + QPointF(40., 20.), Qt.MouseButton.RightButton)
    mouse(card, QEvent.Type.MouseButtonRelease, p, Qt.MouseButton.RightButton)
    live = pose(card)
    section = card.settings.get('widgets.spotify_visualizer')
    snapshot = build_normalized_custom_snapshot(MODE, section)
    assert not set(live) & set(snapshot)
    assert not set(live) & set(normalize_visualizer_mode_payload(MODE, section))
    for index, preset in enumerate(get_presets(MODE)):
        if not preset.is_custom:
            applied = apply_preset_to_config(MODE, index, section)
            assert {key: applied[key] for key in live} == live
    card.settings.save()
    reopened = SettingsManager(application='FramedScenePoseTest', storage_base_dir=card.tmp_path)
    assert {key: reopened.get('widgets.spotify_visualizer')[key] for key in live} == pytest.approx(live)
    target = card.tmp_path / 'pose.sst'
    assert card.settings.export_to_sst(str(target))
    imported = SettingsManager(application='FramedPoseImportTest', storage_base_dir=card.tmp_path)
    assert imported.import_from_sst(str(target))
    assert {key: imported.get('widgets.spotify_visualizer')[key] for key in live} == pytest.approx(live)
    assert card.settings.get(VISUALIZER_CUSTOM_STORAGE_KEY) == {}


def test_plain_edit_wheel_retains_outer_geometry_authoring(card):
    assert not card.window._framed_scene_filter_installed
    assert card.layout.start()
    assert card.window._framed_scene_filter_installed
    item = card.layout.session.items()[0]
    original_scale = item.resize_scale
    original_pose = pose(card)
    p = point(card)
    event = QWheelEvent(p, QPointF(card.window.mapToGlobal(p.toPoint())), QPoint(), QPoint(0, 120),
                        Qt.MouseButton.NoButton, NONE, Qt.ScrollPhase.NoScrollPhase, False)
    QCoreApplication.sendEvent(card.window, event)
    assert item.resize_scale > original_scale
    assert pose(card) == original_pose and card.writes == []
    assert card.layout.cancel()
    assert not card.window._framed_scene_filter_installed


def test_scene_gesture_settlement_does_not_stop_held_wasd(card, monkeypatch):
    from engine import display_manager
    from widgets.spotify_visualizer.view_orbit import view_orbit_values
    clock = [100.]
    monkeypatch.setattr(display_manager.time, 'time', lambda: clock[0])
    QCoreApplication.sendEvent(card.window, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, NONE))
    host = card.visualizer.controller.presentation_state
    assert host._view_orbit_motion is not None
    clock[0] = 100.5
    wheel(card, point(card))
    release_alt(card)
    assert len(card.writes) == 1
    assert host._view_orbit_motion is not None and host._view_orbit_motion.turn_rate != 0
    live_orbit = view_orbit_values(host, MODE, clock[0])
    assert {key: card.writes[-1][key] for key in live_orbit} == pytest.approx(live_orbit)
    scale = pose(card)['shockwave_grid_scene_scale']
    clock[0] = 101.
    QCoreApplication.sendEvent(card.window, QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_A, NONE))
    assert host._view_orbit_motion is None and len(card.writes) == 2
    assert pose(card)['shockwave_grid_scene_scale'] == scale


def test_internal_transform_uses_spec_limits_without_changing_frame(card):
    from widgets.spotify_visualizer.config_applier import presentation_setting_range
    presentation = card.scene.visualizer_item.presentation
    p = point(card)
    mouse(card, QEvent.Type.MouseButtonPress, p, Qt.MouseButton.RightButton)
    mouse(card, QEvent.Type.MouseMove, p + QPointF(10000., -10000.), Qt.MouseButton.RightButton)
    mouse(card, QEvent.Type.MouseButtonRelease, p, Qt.MouseButton.RightButton)
    scale=pose(card)['shockwave_grid_scene_scale']
    assert pose(card)['shockwave_grid_scene_pan_x'] == pytest.approx(.42)
    assert pose(card)['shockwave_grid_scene_pan_y'] == pytest.approx(.08-(.5+.18*scale))
    wheel(card, p, 12000)
    release_alt(card)
    assert pose(card)['shockwave_grid_scene_scale'] == presentation_setting_range('shockwave_grid_scene_scale')[1]
    assert card.scene.visualizer_item.presentation == presentation


def test_native_pan_can_frame_sky_at_the_reported_zoom_and_persist_within_limits(card):
    from widgets.spotify_visualizer.view_orbit import transform_visualizer_scene
    host=card.visualizer.controller.presentation_state
    transform_visualizer_scene(host,MODE,{'shockwave_grid_scene_scale':1.90333,
                                         'shockwave_grid_scene_pan_y':.0774006})
    outer=card.scene.visualizer_item.presentation
    p=point(card)
    mouse(card,QEvent.Type.MouseButtonPress,p,Qt.MouseButton.RightButton)
    mouse(card,QEvent.Type.MouseMove,p+QPointF(0.,10000.),Qt.MouseButton.RightButton)
    mouse(card,QEvent.Type.MouseButtonRelease,p,Qt.MouseButton.RightButton)
    live=pose(card)
    assert live['shockwave_grid_scene_pan_y']==pytest.approx(1.1432654)
    assert card.settings.get('widgets.spotify_visualizer')['shockwave_grid_scene_pan_y']==pytest.approx(1.1432654)
    assert card.scene.visualizer_item.presentation==outer
    assert len(card.writes)==1
