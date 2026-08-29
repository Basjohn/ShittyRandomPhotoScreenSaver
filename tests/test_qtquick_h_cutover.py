"""H production-cutover integration bars.

These prove the production Quick pieces connect correctly at the display/runtime
owner. They assert semantic owner cardinality and the corrected-G4 visualizer
viewport-config ownership through the real QuickDisplayRuntime +
QuickSceneController + runtime controller chain, not a stand-in sink.
"""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, QPoint, QRect, QSize
from PySide6.QtGui import QPixmap

from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
from engine.display_manager import DisplayManager
from rendering.custom_layout_session import (
    CustomLayoutKey,
    CustomLayoutSession,
    CustomLayoutSessionItem,
)
from rendering.quick.runtime import QuickDisplayRuntime
from rendering.quick.display_unit import QuickDisplayUnit
from rendering.quick.display_processing import DisplayProcessingDescriptor
from rendering.display_modes import DisplayMode
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.widget_runtime_manager import WidgetRuntimeManager
from widgets.spotify_visualizer.presentation_geometry import (
    resolve_visualizer_presentation,
)
from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController


@pytest.mark.qt
def test_display_manager_constructs_only_authoritative_quick_units(
    qt_app,
    qtbot,
    monkeypatch,
) -> None:
    """The production constructor owns one factory and only Quick units."""

    screens = tuple(qt_app.screens())
    assert screens
    actions = []
    monkeypatch.setattr(QuickDisplayUnit, "show_on_screen", lambda _unit: None)
    monkeypatch.setattr(
        QuickDisplayUnit,
        "request_media_transport",
        lambda unit, key: actions.append((unit.screen_index, "transport", key))
        or True,
    )
    monkeypatch.setattr(
        QuickDisplayUnit,
        "request_app_volume_step",
        lambda unit, direction: actions.append(
            (unit.screen_index, "app_volume", direction)
        )
        or True,
    )
    monkeypatch.setattr(
        QuickDisplayUnit,
        "request_system_volume_step",
        lambda unit, delta: actions.append(
            (unit.screen_index, "system_volume", delta)
        )
        or 0.5,
    )
    monkeypatch.setattr(
        QuickDisplayUnit,
        "request_system_mute_toggle",
        lambda unit: actions.append((unit.screen_index, "mute")) or True,
    )

    manager = DisplayManager(runtime_generation=701)
    try:
        assert manager.initialize_displays() == len(screens)
        assert manager._quick_scene_factory is not None
        assert len(manager.displays) == len(screens)
        assert all(isinstance(unit, QuickDisplayUnit) for unit in manager.displays)
        assert [unit.screen_index for unit in manager.displays] == list(
            range(len(screens))
        )
        assert len({id(unit.runtime) for unit in manager.displays}) == len(screens)
        assert all(
            unit._ctrl_coordinator is manager._quick_ctrl_coordinator
            for unit in manager.displays
        )

        runtime = manager.displays[0].runtime
        runtime.play_pause_requested.emit()
        runtime.home_play_pause_requested.emit()
        runtime.previous_track_requested.emit()
        runtime.next_track_requested.emit()
        runtime.slider_volume_up_requested.emit()
        runtime.slider_volume_down_requested.emit()
        runtime.global_volume_up_requested.emit()
        runtime.global_volume_down_requested.emit()
        runtime.global_mute_toggle_requested.emit()
        assert actions == [
            (0, "transport", "play"),
            (0, "transport", "play"),
            (0, "transport", "prev"),
            (0, "transport", "next"),
            (0, "app_volume", 1),
            (0, "app_volume", -1),
            (0, "system_volume", 0.05),
            (0, "system_volume", -0.05),
            (0, "mute"),
        ]

        manager.cleanup()
        assert manager.displays == []
        assert len(manager._retiring_quick_units) == len(screens)
        qtbot.waitUntil(
            lambda: not manager._retiring_quick_units,
            timeout=3000,
        )
    finally:
        if not manager._retired:
            manager.retire_runtime()
        qt_app.processEvents()


def test_display_manager_owns_layout_slot_persistence_and_fenced_reload(
    qt_app,
) -> None:
    class _Settings:
        def __init__(self) -> None:
            self.widgets = {
                "clock": {"enabled": True, "position": "Top Left"},
            }
            self.save_calls = 0

        def get_widgets_map(self):
            return deepcopy(self.widgets)

        def set_widgets_map(self, widgets, *, emit_change=True) -> None:
            self.widgets = deepcopy(widgets)

        def save(self) -> None:
            self.save_calls += 1

    settings = _Settings()
    manager = DisplayManager(settings_manager=settings, runtime_generation=702)
    reloads = []
    manager.custom_layout_reload_requested.connect(
        lambda kind, generation, identity: reloads.append(
            (kind, generation, identity)
        )
    )
    try:
        assert manager._save_layout_slot("1") is True
        settings.widgets["clock"]["position"] = "Bottom Right"
        assert manager._load_layout_slot("1") is True
        assert settings.widgets["clock"]["position"] == "Top Left"
        assert settings.save_calls == 2
        assert reloads == [("slot_load", 702, id(manager))]
        assert manager._save_layout_slot("bad") is False
        assert manager._load_layout_slot("9") is False
    finally:
        manager.disconnect_monitor_detection()
        manager.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_display_manager_routes_descriptors_and_images_by_screen_identity(qt_app) -> None:
    published = []
    media_wakes = []

    class _MediaService:
        def wake_from_idle(self) -> None:
            media_wakes.append(True)

    class _RuntimeManager:
        def get_widget_service(self, widget_id: str):
            return _MediaService() if widget_id == "media" else None

    class _Unit:
        def __init__(self, screen_index: int, size: QSize, dpr: float) -> None:
            self.screen_index = screen_index
            self._size = QSize(size)
            self._dpr = dpr
            self.runtime = SimpleNamespace(
                widget_runtime_manager=_RuntimeManager(),
                scene_controller=SimpleNamespace(presentation_image=None),
                describe_runtime_state=lambda: {"screen_index": self.screen_index},
                auxiliary_controller=SimpleNamespace(
                    set_dimming=lambda enabled, opacity: published.append(
                        (self.screen_index, "dimming", enabled, opacity)
                    )
                ),
                display_identity=SimpleNamespace(
                    as_dict=lambda: {"screen_index": self.screen_index}
                ),
            )
            self.retirement_qobject = QObject()
            self.retirement_owner = SimpleNamespace(screen_index=screen_index)
            self.clear_calls = 0
            self.quiesce_calls = 0

        def processing_descriptor(self, display_mode: DisplayMode):
            return DisplayProcessingDescriptor(
                screen_index=self.screen_index,
                target_size=QSize(self._size),
                logical_size=QSize(
                    int(round(self._size.width() / self._dpr)),
                    int(round(self._size.height() / self._dpr)),
                ),
                display_mode=display_mode,
                device_pixel_ratio=self._dpr,
            )

        def present_image(self, pixmap, *, image_path: str = "") -> None:
            published.append((self.screen_index, pixmap.size(), image_path))

        def runtime_retirement_roots(self):
            return ((self.retirement_qobject,), (self.retirement_owner,))

        def clear(self) -> None:
            self.clear_calls += 1

        def quiesce(self) -> None:
            self.quiesce_calls += 1

        def has_running_transition(self) -> bool:
            return False

    manager = DisplayManager(display_mode=DisplayMode.FIT)
    manager.displays = [
        _Unit(2, QSize(1920, 1080), 1.0),
        _Unit(5, QSize(2560, 1440), 2.0),
    ]
    pixmap = QPixmap(8, 6)
    try:
        descriptors = manager.snapshot_processing_descriptors()
        assert [item.screen_index for item in descriptors] == [2, 5]
        assert [item.target_size for item in descriptors] == [
            QSize(1920, 1080),
            QSize(2560, 1440),
        ]
        assert [item.logical_size for item in descriptors] == [
            QSize(1920, 1080),
            QSize(1280, 720),
        ]
        assert all(item.display_mode is DisplayMode.FIT for item in descriptors)
        assert manager.has_presented_image() is False
        assert manager.wake_media_runtime() == 2
        assert media_wakes == [True, True]
        assert manager.describe_display_states() == (
            {"screen_index": 2},
            {"screen_index": 5},
        )
        qobjects, python_owners = manager.collect_runtime_retirement_roots()
        assert qobjects[0] is manager
        assert qobjects[1:] == [
            manager.displays[0].retirement_qobject,
            manager.displays[1].retirement_qobject,
        ]
        assert python_owners == [
            manager.displays[0].retirement_owner,
            manager.displays[1].retirement_owner,
        ]

        manager.present_processed_image(5, pixmap, pixmap, "five.jpg")
        manager.show_image_on_screen(2, pixmap, "two.jpg")
        manager.show_image(pixmap, "all.jpg")
        assert published == [
            (5, QSize(8, 6), "five.jpg"),
            (2, QSize(8, 6), "two.jpg"),
            (2, QSize(8, 6), "all.jpg"),
            (5, QSize(8, 6), "all.jpg"),
        ]
        assert manager.current_images == {2: "all.jpg", 5: "all.jpg"}
        manager.set_transition_work_pending(True, screen_index=5)
        assert manager.has_transition_work_pending() is True
        manager.set_transition_work_pending(False)
        assert manager.has_transition_work_pending() is False
        manager.set_dimming_all_displays(True, 0.4)
        assert published[-2:] == [
            (2, "dimming", True, 0.4),
            (5, "dimming", True, 0.4),
        ]
        assert manager.get_display_info() == [
            {"screen_index": 2},
            {"screen_index": 5},
        ]
        manager.quiesce_all()
        assert [unit.quiesce_calls for unit in manager.displays] == [1, 1]
        manager.clear_all()
        assert [unit.clear_calls for unit in manager.displays] == [1, 1]
        assert manager.current_images == {}
        manager.displays[1].runtime.scene_controller.presentation_image = object()
        assert manager.has_presented_image() is True
        with pytest.raises(IndexError):
            manager.present_processed_image(1, pixmap, pixmap, "missing.jpg")
    finally:
        manager.displays = []
        manager.disconnect_monitor_detection()
        manager.deleteLater()
        qt_app.processEvents()


def _visualizer_item(display_identity: str, extent: tuple[float, float]):
    return CustomLayoutSessionItem(
        source_key=CustomLayoutKey("spotify_visualizer", display_identity),
        model_identity="spotify_visualizer",
        baseline_global_rect=QRect(120, 90, int(extent[0]), int(extent[1])),
        current_global_rect=QRect(120, 90, int(extent[0]), int(extent[1])),
        baseline_size_payload={},
        current_size_payload={},
        baseline_enabled=True,
        current_enabled=True,
        viewport_resize_capable=True,
        baseline_viewport_extent=extent,
    )


def _committed(controller: VisualizerRuntimeController, extent) -> None:
    controller.commit_presentation_metrics(
        resolve_visualizer_presentation(
            policy=get_visualizer_presentation_policy("bubble"),
            display_size=(1920.0, 1080.0),
            outer_origin=(40.0, 60.0),
            viewport_extent=extent,
        )
    )


@pytest.mark.qt
def test_runtime_owns_exactly_one_widget_runtime_manager_and_retires_it(
    qt_app,
) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=70,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    try:
        # Exactly one neutral capability/service owner exists for this display
        # generation, and the accessor returns that same instance every time.
        manager = runtime.widget_runtime_manager
        assert isinstance(manager, WidgetRuntimeManager)
        assert runtime.widget_runtime_manager is manager
        assert manager.is_retired is False

        state = runtime.describe_runtime_state()["widget_runtime_manager"]
        assert state == {
            "present": True,
            "retired": False,
            "has_bound_host": False,
        }
    finally:
        # Closing the runtime retires the neutral owner exactly once. Retirement
        # is idempotent: a second close does not re-run service teardown.
        assert runtime.close_runtime() is True
        assert manager.is_retired is True
        retired_state = runtime.describe_runtime_state()["widget_runtime_manager"]
        assert retired_state["retired"] is True
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_replacement_generation_builds_its_own_widget_runtime_manager(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    first = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=71,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    first_manager = first.widget_runtime_manager
    assert first.close_runtime() is True
    assert first_manager.is_retired is True

    second = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=72,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    try:
        # A replacement generation owns its own live neutral manager, never the
        # retired one from the prior generation.
        assert second.widget_runtime_manager is not first_manager
        assert second.widget_runtime_manager.is_retired is False
    finally:
        second.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_runtime_binds_visualizer_render_source_with_exact_identity(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=62,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    controller = VisualizerRuntimeController(
        runtime_generation=62,
        bar_count=24,
        initial_mode="bubble",
        engine_factory=lambda _bar_count: object(),
    )
    try:
        identity = runtime.bind_visualizer_render_source(
            controller, engine_generation=3, activation_id=7
        )
        assert identity.runtime_generation == 62
        assert identity.engine_generation == 3
        assert identity.activation_id == 7
        assert identity.mode_id == "bubble"
        # The retained scene item now owns exactly that activation identity.
        assert runtime.scene_controller.visualizer_render_identity == identity
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_runtime_binds_visualizer_viewport_config_with_committed_and_custom_override(
    qt_app,
) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=61,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    controller = VisualizerRuntimeController(
        runtime_generation=61,
        bar_count=24,
        initial_mode="bubble",
        engine_factory=lambda _bar_count: object(),
    )
    try:
        # Ordinary runtime truth: a saved WIDE committed extent.
        _committed(controller, (630.0, 280.0))
        assert controller.presentation_viewport_extent == (630.0, 280.0)

        # Bind the corrected-G4 config seam once at the display owner. Binding
        # with no CUSTOM session retires any override -> committed still wins.
        runtime.bind_visualizer_viewport_config(controller.set_custom_viewport_override)
        assert controller.presentation_viewport_extent == (630.0, 280.0)

        # Enter CUSTOM; a live edge drag drives only the temporary override.
        session = CustomLayoutSession()
        item = _visualizer_item("display:a", (630.0, 280.0))
        session.add_item(item)
        runtime.scene_controller.bind_custom_layout_session(
            session,
            display_identity="display:a",
            display_origin=QPoint(0, 0),
        )
        assert controller.presentation_viewport_extent == (630.0, 280.0)

        item.set_viewport_extent(840.0, 280.0)
        session.notify_item_changed(item)
        assert controller.presentation_viewport_extent == (840.0, 280.0)

        # An ordinary committed republish during CUSTOM cannot erase the override.
        _committed(controller, (420.0, 280.0))
        assert controller.presentation_viewport_extent == (840.0, 280.0)

        # Ending CUSTOM retires the override -> falls back to committed, never a
        # manufactured canonical.
        runtime.scene_controller.clear_custom_layout_session()
        assert controller.presentation_viewport_extent == (420.0, 280.0)
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()
