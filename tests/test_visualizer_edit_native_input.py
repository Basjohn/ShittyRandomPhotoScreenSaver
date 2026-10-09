"""Deliver Edit gestures through the real native window, retained QML and session."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent

from engine.display_manager import DisplayManager
from rendering.quick.ctrl_coordinator import SharedCtrlCoordinator
from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner
from rendering.quick.display_unit import create_quick_display_unit
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from tests._invisible_windows import keep_off_screen
from tests.test_qtquick_custom_layout_owner import _configure_visualizer, _LiveCommitEngine, _Settings
from tests.test_qtquick_edit_pointer_delivery import _one
from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

ALT = Qt.KeyboardModifier.AltModifier


@pytest.fixture
def edit_scene(qt_app, monkeypatch):
    from rendering import runtime_input

    # Terminal Edit's desktop recreation guard is outside these delivery tests;
    # do not let its process-global expiry suppress the next test's direct input.
    monkeypatch.setattr(runtime_input, "suppress_runtime_pointer_input", lambda *a, **k: None)
    factory = QuickSceneFactory()
    unit = create_quick_display_unit(
        screen=qt_app.primaryScreen(), screen_index=0, runtime_generation=1937,
        scene_factory=factory, window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
        ctrl_coordinator=SharedCtrlCoordinator(), adapters=(),
    )
    unit.runtime.window.resize(1000, 700)
    unit.runtime.window.setPosition(qt_app.primaryScreen().geometry().topLeft() + QPoint(40, 40))
    visualizer = QuickDisplayVisualizerOwner(
        unit.runtime, bar_count=24, initial_mode="extruded_spectrum",
        card_shadow_kwargs={
            "background_color": (0, 0, 0, 0), "border_color": (255, 255, 255, 255),
            "border_width": 4., "corner_radius": 6., "content_inset": 14.,
            "shadow_enabled": False, "shadow_color": (0, 0, 0, 0),
            "shadow_blur": 0., "shadow_offset": (0., 0.), "shadow_spread": 0.,
            "shadow_extensions": (0., 0., 0., 0.),
        }, engine_factory=lambda _count: _LiveCommitEngine(),
    )
    unit.attach_visualizer_owner(visualizer)
    settings = _Settings({"spotify_visualizer": {
        "enabled": True, "position": "Custom", "monitor": "1", "mode": "extruded_spectrum",
    }})
    layout = QuickCustomLayoutOwner(
        settings_manager=settings, participants_provider=lambda: (unit,),
        visualizer_provider=lambda: (visualizer, unit), reload_request=lambda _reason: None,
        live_config_commit=lambda _config: None,
    )
    scene = unit.runtime.scene_controller
    window = unit.runtime.window
    manager = DisplayManager.__new__(DisplayManager)
    manager._quick_visualizer_owner = visualizer
    manager._quick_view_orbit_pending = None
    manager._refresh_quick_visualizer_edit_content_envelope = lambda *a: None
    scene.custom_layout_visualizer_orbit_requested.connect(manager._orbit_quick_visualizer_view_from_edit_drag)
    try:
        _configure_visualizer(visualizer, playing=True)
        visualizer.configure_committed_layout(
            local_rect=(220., 180., 480., 270.), viewport_extent=(160., 90.),
        )
        visualizer.bind(engine_generation=3, activation_id=5)
        visualizer._apply_resolved_presentation(visualizer._resolve_current_presentation())
        assert layout.start()
        item = layout.session.items()[0]
        assert item.source_key.geometry_variant == "3d:extruded_spectrum"
        assert item.geometry_kind == "freeform_3d"
        layout.session.select_item(item)
        scene.set_visualizer_edit_content_envelope({
            "mode": "extruded_spectrum", "orbit_admitted": True,
            "admitted": True, "left": 40., "top": 40., "right": 400., "bottom": 220.,
            "pivot_x": 240., "pivot_y": 135.,
        })
        keep_off_screen(window)
        window.show()
        qt_app.processEvents()
        frame = _one(scene.scene_root, "customLayoutEditFrame-spotify_visualizer")
        assert unit.runtime.input_controller.input_state.admission_open
        assert 0 <= frame.x() and frame.x() + frame.width() <= window.width()
        assert 0 <= frame.y() and frame.y() + frame.height() <= window.height()
        assert frame.property("altThreeDGestureAdmitted")
        yield SimpleNamespace(
            unit=unit, window=window, visualizer=visualizer, layout=layout,
            settings=settings, scene=scene, frame=frame, item=item, qt_app=qt_app,
        )
    finally:
        layout.retire()
        unit.retire()
        factory.deleteLater()
        qt_app.processEvents()


def _point(edit):
    return edit.frame.mapToItem(edit.window.contentItem(), 180., 130.)


def _wheel(edit, x, y, *, inverted=False):
    point = _point(edit)
    event = QWheelEvent(
        point, QPointF(edit.window.mapToGlobal(point.toPoint())), QPoint(), QPoint(x, y),
        Qt.MouseButton.NoButton, ALT, Qt.ScrollPhase.NoScrollPhase, inverted,
    )
    QCoreApplication.sendEvent(edit.window, event)
    edit.qt_app.processEvents()


def _mouse(edit, kind, point, button, buttons, modifiers=ALT):
    event = QMouseEvent(kind, point, QPointF(edit.window.mapToGlobal(point.toPoint())),
                        button, buttons, modifiers)
    QCoreApplication.sendEvent(edit.window, event)
    edit.qt_app.processEvents()


@pytest.mark.qt
@pytest.mark.parametrize("horizontal", [False, True])
@pytest.mark.parametrize("inverted", [False, True])
def test_alt_wheel_is_signed_reversible_uniform_and_zero_is_noop(edit_scene, horizontal, inverted):
    edit = edit_scene
    original = edit.item.current_global_rect
    original_extent = edit.item.current_viewport_extent
    original_scale = edit.item.resize_scale
    original_presentation = edit.scene.visualizer_item.presentation
    for delta in (120, -120, -120, 120):
        before = edit.item.resize_scale
        _wheel(edit, delta if horizontal else 0, 0 if horizontal else delta, inverted=inverted)
        assert edit.item.resize_scale == pytest.approx(before + (0.05 if delta > 0 else -0.05))
        rect = edit.item.current_global_rect
        assert rect.x() + rect.width() / 2 == pytest.approx(original.x() + original.width() / 2, abs=.5)
        # Freeform 3D stages grow around their center; planar cards retain
        # the historical top-centre pivot. Do not undo accepted 3D authoring.
        assert rect.y() + rect.height() / 2 == pytest.approx(
            original.y() + original.height() / 2, abs=.5
        )
        assert edit.item.current_viewport_extent == original_extent
        presentation = edit.scene.visualizer_item.presentation
        # A uniform freeform-3D stage is stored as an integral QRect; rounding
        # both dimensions independently can shift the ratio by ~one pixel.
        # The actual visible stage must match the editor's rectangle exactly.
        assert presentation.outer_rect[2] == pytest.approx(rect.width(), abs=.501)
        assert presentation.outer_rect[3] == pytest.approx(rect.height(), abs=.501)
        original_aspect = original_presentation.outer_rect[2] / original_presentation.outer_rect[3]
        assert abs(presentation.outer_rect[2] - original_aspect * presentation.outer_rect[3]) <= (1 + original_aspect) / 2 + 0.01
    assert edit.item.resize_scale == pytest.approx(original_scale)
    assert edit.item.current_global_rect == original
    before_payload = dict(edit.item.current_size_payload)
    _wheel(edit, 0, 0)
    assert edit.item.resize_scale == pytest.approx(original_scale)
    assert edit.item.current_global_rect == original
    assert edit.item.current_size_payload == before_payload
    assert edit.settings.save_calls == 0
    assert edit.layout.cancel()


@pytest.mark.qt
def test_alt_left_orbits_through_native_quick_and_shared_resolver_without_moving_stage(edit_scene):
    edit = edit_scene
    from widgets.spotify_visualizer.view_orbit import view_orbit_values
    before = view_orbit_values(edit.visualizer.controller.presentation_state, "extruded_spectrum")
    rect = edit.item.current_global_rect
    point = _point(edit)
    _mouse(edit, QEvent.Type.MouseButtonPress, point, Qt.LeftButton, Qt.LeftButton)
    _mouse(edit, QEvent.Type.MouseMove, point + QPointF(24, 12), Qt.NoButton, Qt.LeftButton)
    _mouse(edit, QEvent.Type.MouseButtonRelease, point + QPointF(24, 12), Qt.LeftButton, Qt.NoButton)
    after = view_orbit_values(edit.visualizer.controller.presentation_state, "extruded_spectrum")
    assert after != before
    assert edit.item.current_global_rect == rect
    assert edit.settings.save_calls == 0
    assert not _one(edit.scene.scene_root, "customLayoutParentMoveArea-spotify_visualizer").property("altOrbitDragging")


@pytest.mark.qt
def test_alt_right_uses_edit_grab_and_releases_when_alt_lifts_first(edit_scene):
    edit = edit_scene
    menus = []
    edit.unit.runtime.input_controller.context_menu_requested.connect(menus.append)
    before = edit.item.current_global_rect
    point = _point(edit)
    moves = []
    model = edit.scene.custom_layout_overlay.model
    resolve_move = model._geometry_resolver

    def observed_move(item, proposed, cursor):
        resolved = resolve_move(item, proposed, cursor)
        moves.append((QRect(proposed), QRect(resolved)))
        return resolved

    model._geometry_resolver = observed_move
    _mouse(edit, QEvent.Type.MouseButtonPress, point, Qt.RightButton, Qt.RightButton)
    _mouse(edit, QEvent.Type.MouseMove, point + QPointF(30, 20), Qt.NoButton, Qt.RightButton)
    _mouse(edit, QEvent.Type.MouseButtonRelease, point + QPointF(30, 20), Qt.RightButton,
           Qt.NoButton, Qt.KeyboardModifier.NoModifier)
    assert menus == []
    assert len(moves) == 1
    assert moves[0][0].topLeft() == before.topLeft() + QPoint(30, 20)
    assert edit.item.current_global_rect == moves[0][1]  # canonical Edit snap/clamp is retained
    assert edit.item.current_global_rect.size() == before.size()
    move = _one(edit.scene.scene_root, "customLayoutParentMoveArea-spotify_visualizer")
    assert not move.property("altMoveDragging")
    assert edit.window.mouseGrabberItem() is None
    point = _point(edit)
    _mouse(edit, QEvent.Type.MouseButtonPress, point, Qt.RightButton, Qt.RightButton, Qt.NoModifier)
    _mouse(edit, QEvent.Type.MouseButtonRelease, point, Qt.RightButton, Qt.NoButton, Qt.NoModifier)
    assert len(menus) == 1, (
        edit.unit.runtime.input_controller.input_state,
        edit.window._custom_layout_input_blocked,
        edit.unit.is_retired,
    )
    assert edit.settings.save_calls == 0
