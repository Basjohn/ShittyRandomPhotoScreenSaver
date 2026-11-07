"""Held-left orbit on the freeform 3D Visualizers (Sphere, Extruded Spectrum) through the production input path.

Operator 7 Nov: "Extruded Spectrum does not rotate/orbit with left click held, both it and sphere are supposed to."
Held-left orbit was admitted only for framed card modes (scene transform + card shell), so a plain left drag on a
freeform stage did nothing. Real hidden Quick window, real scene controller and DisplayManager's own admission
projection (``_configure_quick_visualizer_input_admission``); no visible window, no native pointer capture.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from core.settings import SettingsManager
from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
from engine.display_manager import DisplayManager
from rendering.quick.ctrl_coordinator import SharedCtrlCoordinator
from rendering.quick.display_unit import create_quick_display_unit
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from tests.test_qtquick_custom_layout_owner import _configure_visualizer, _LiveCommitEngine
from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner
from widgets.spotify_visualizer.view_orbit import OrbitInertia, view_orbit_values

FREEFORM = ('sphere', 'extruded_spectrum')
LEFT = Qt.MouseButton.LeftButton
NONE = Qt.KeyboardModifier.NoModifier
CTRL = Qt.KeyboardModifier.ControlModifier
ALT = Qt.KeyboardModifier.AltModifier


@pytest.fixture
def stage(qt_app, tmp_path, monkeypatch, request):
    mode = request.param
    from rendering import runtime_input
    monkeypatch.setattr(runtime_input, 'suppress_runtime_pointer_input', lambda *a, **k: None)
    settings = SettingsManager(application='FreeformHeldLeftOrbit', storage_base_dir=tmp_path)
    widgets = settings.get_widgets_map()
    widgets['spotify_visualizer'].update({'enabled': True, 'mode': mode, 'position': 'Custom', 'monitor': '1'})
    settings.set_widgets_map(widgets)
    factory = QuickSceneFactory()
    unit = create_quick_display_unit(
        screen=qt_app.primaryScreen(), screen_index=0, runtime_generation=719, scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
        ctrl_coordinator=SharedCtrlCoordinator(), adapters=())
    unit.runtime.window.resize(1000, 700)
    visualizer = QuickDisplayVisualizerOwner(
        unit.runtime, bar_count=24, initial_mode=mode,
        card_shadow_kwargs={'background_color': (0, 0, 0, 0), 'border_color': (255, 255, 255, 255),
                            'border_width': 4., 'corner_radius': 6., 'content_inset': 14.,
                            'shadow_enabled': False, 'shadow_color': (0, 0, 0, 0), 'shadow_blur': 0.,
                            'shadow_offset': (0., 0.), 'shadow_spread': 0.,
                            'shadow_extensions': (0., 0., 0., 0.)},
        engine_factory=lambda count: _LiveCommitEngine())
    unit.attach_visualizer_owner(visualizer)
    manager = DisplayManager.__new__(DisplayManager)
    manager._quick_visualizer_owner = visualizer
    manager._quick_visualizer_unit = unit
    manager._runtime_generation = 719
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
    rates = []
    for signal, callback in [('view_orbit_requested', manager._orbit_quick_visualizer_view),
                             ('view_orbit_finished', manager._persist_quick_visualizer_view)]:
        getattr(unit.runtime, signal).connect(
            lambda *args, cb=callback: manager._route_quick_visualizer_input(unit, cb, *args))
    unit.runtime.input_controller.view_orbit_rates_changed.connect(lambda *args: rates.append(args))
    unit.runtime.input_controller.set_interaction_mode_enabled(True)
    # The production mode-capability projection (startup, replacement binds and mode edges).
    manager._configure_quick_visualizer_input_admission(unit, admitted=True)
    window = unit.runtime.window

    class Capture:  # never confine the real desktop pointer
        def acquire(self, rect):
            pass

        def release(self):
            pass
    monkeypatch.setattr(window, '_new_plain_orbit_capture', Capture)
    writes = []
    original = settings.replace_visualizer_runtime_preset_state

    def save(section, custom):
        writes.append(dict(section))
        return original(section, custom)
    monkeypatch.setattr(settings, 'replace_visualizer_runtime_preset_state', save)
    try:
        yield SimpleNamespace(mode=mode, unit=unit, window=window, visualizer=visualizer, settings=settings,
                              controller=unit.runtime.input_controller, writes=writes, rates=rates, manager=manager)
    finally:
        window.cancel_plain_orbit()
        unit.retire()
        factory.deleteLater()
        qt_app.processEvents()


def _centre(stage):
    x, y, w, h = stage.unit.runtime.scene_controller.visualizer_item.presentation.outer_rect
    return QPointF(x + w / 2, y + h / 2)


def _send(stage, kind, position, button, buttons, modifiers):
    event = QMouseEvent(kind, position, QPointF(stage.window.mapToGlobal(position.toPoint())),
                        button, buttons, modifiers)
    QCoreApplication.sendEvent(stage.window, event)


def _drag(stage, modifiers, steps=((20., 10.), (40., 20.))):
    p = _centre(stage)
    _send(stage, QEvent.Type.MouseButtonPress, p, LEFT, LEFT, modifiers)
    for dx, dy in steps:
        _send(stage, QEvent.Type.MouseMove, p + QPointF(dx, dy), Qt.MouseButton.NoButton, LEFT, modifiers)
    dx, dy = steps[-1]
    _send(stage, QEvent.Type.MouseButtonRelease, p + QPointF(dx, dy), LEFT, Qt.MouseButton.NoButton, modifiers)


def _pose(stage):
    return view_orbit_values(stage.visualizer.controller.presentation_state, stage.mode)


@pytest.mark.qt
@pytest.mark.parametrize('stage', FREEFORM, indirect=True)
@pytest.mark.parametrize('modifiers', [NONE, CTRL], ids=['plain', 'ctrl'])
def test_held_left_drag_orbits_a_freeform_stage_and_saves_once(stage, modifiers):
    assert not stage.unit.runtime.scene_controller._visualizer_root.property('cardShellEnabled')  # frameless
    before = _pose(stage)
    _drag(stage, modifiers)
    after = _pose(stage)
    turn, tilt = get_visualizer_mode_descriptor(stage.mode).view_orbit_settings
    assert after[turn] != pytest.approx(before[turn]) and after[tilt] != pytest.approx(before[tilt]), \
        f'{stage.mode}: a held-left drag on its stage did not orbit'
    assert len(stage.writes) == 1
    saved = stage.settings.get('widgets.spotify_visualizer')
    # Inertia is declared per mode (AC-11 table): Sphere coasts from the release, Extruded Spectrum stops there.
    inertia = getattr(stage.visualizer.controller.presentation_state, '_view_orbit_inertia', None)
    assert isinstance(inertia, OrbitInertia) == get_visualizer_mode_descriptor(stage.mode).view_orbit_inertia
    if inertia is None:
        assert {turn: saved[turn], tilt: saved[tilt]} == pytest.approx(after)
    assert stage.window._plain_orbit_card is None and stage.controller._view_orbit_drag is None


@pytest.mark.qt
@pytest.mark.parametrize('stage', FREEFORM, indirect=True)
def test_alt_left_drag_still_orbits_and_a_click_does_not(stage):
    before = _pose(stage)
    p = _centre(stage)
    _send(stage, QEvent.Type.MouseButtonPress, p, LEFT, LEFT, NONE)
    _send(stage, QEvent.Type.MouseButtonRelease, p, LEFT, Qt.MouseButton.NoButton, NONE)
    assert _pose(stage) == before and stage.writes == []
    _drag(stage, ALT)
    assert _pose(stage) != before and len(stage.writes) == 1


@pytest.mark.qt
@pytest.mark.parametrize('stage', FREEFORM, indirect=True)
def test_wasd_orbit_freeform_view_not_framed_flight(stage):
    assert not stage.controller._framed_flight_enabled
    for key, rate in ((Qt.Key.Key_W, (0., 1.)), (Qt.Key.Key_A, (1., 0.))):
        QCoreApplication.sendEvent(stage.window, QKeyEvent(QEvent.Type.KeyPress, key, NONE))
        assert stage.rates[-1] == rate
        QCoreApplication.sendEvent(stage.window, QKeyEvent(QEvent.Type.KeyRelease, key, NONE))
        assert stage.rates[-1] == (0., 0.)


@pytest.mark.qt
@pytest.mark.parametrize('stage', FREEFORM, indirect=True)
def test_a_switch_between_the_freeform_modes_ends_a_held_orbit(stage):
    """A held-left orbit on one freeform mode (Sphere, Extruded Spectrum) is ended by a switch to the other, as a
    framed mode's orbit is by any mode change ('mode'): the drag, its pointer capture and its cursor fade end at the
    switch, and the rest of the drag never orbits the new mode. Both modes are freeform, so the framed-only scene
    transform projection does not change and only the mode edge can end it."""
    other = next(mode for mode in FREEFORM if mode != stage.mode)
    cancels = []
    stage.controller.plain_orbit_cancel_requested.connect(cancels.append)
    p = _centre(stage)
    _send(stage, QEvent.Type.MouseButtonPress, p, LEFT, LEFT, NONE)
    _send(stage, QEvent.Type.MouseMove, p + QPointF(20., 10.), Qt.MouseButton.NoButton, LEFT, NONE)
    assert stage.window._plain_orbit_card is not None and stage.controller._view_orbit_drag is not None
    stage.visualizer.controller.set_mode(other)                                   # the mode edge
    stage.manager._configure_quick_visualizer_input_admission(stage.unit, admitted=True)
    assert 'mode' in cancels, 'the switch did not end the held orbit'
    assert stage.window._plain_orbit_card is None and stage.controller._view_orbit_drag is None
    before = view_orbit_values(stage.visualizer.controller.presentation_state, other)
    _send(stage, QEvent.Type.MouseMove, p + QPointF(60., 30.), Qt.MouseButton.NoButton, LEFT, NONE)
    _send(stage, QEvent.Type.MouseButtonRelease, p + QPointF(60., 30.), LEFT, Qt.MouseButton.NoButton, NONE)
    assert view_orbit_values(stage.visualizer.controller.presentation_state, other) == before


@pytest.mark.qt
@pytest.mark.parametrize('stage', ['sphere'], indirect=True)
def test_a_projection_for_the_same_freeform_mode_keeps_the_held_orbit(stage):
    """Only a mode change ends it: the same projection again (a preset swap in the same mode) keeps the drag."""
    cancels = []
    stage.controller.plain_orbit_cancel_requested.connect(cancels.append)
    p = _centre(stage)
    _send(stage, QEvent.Type.MouseButtonPress, p, LEFT, LEFT, NONE)
    _send(stage, QEvent.Type.MouseMove, p + QPointF(20., 10.), Qt.MouseButton.NoButton, LEFT, NONE)
    stage.manager._configure_quick_visualizer_input_admission(stage.unit, admitted=True)
    assert cancels == [] and stage.window._plain_orbit_card is not None
    _send(stage, QEvent.Type.MouseButtonRelease, p + QPointF(20., 10.), LEFT, Qt.MouseButton.NoButton, NONE)
