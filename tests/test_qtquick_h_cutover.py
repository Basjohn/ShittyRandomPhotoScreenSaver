"""H production-cutover integration bars.

These prove the production Quick pieces connect correctly at the display/runtime
owner. They assert semantic owner cardinality and the corrected-G4 visualizer
viewport-config ownership through the real QuickDisplayRuntime +
QuickSceneController + runtime controller chain, not a stand-in sink.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import inspect
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, QPoint, QRect, QSize
from PySide6.QtGui import QPixmap

from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
import engine.engine_handlers as engine_handlers_module
import engine.display_manager as display_manager_module
import engine.screensaver_engine as screensaver_engine_module
from engine.display_manager import DisplayManager
from rendering.custom_layout_session import (
    CustomLayoutKey,
    CustomLayoutSession,
    CustomLayoutSessionItem,
)
from rendering.quick.runtime import QuickDisplayRuntime
from rendering.quick.display_unit import QuickDisplayUnit
from rendering.quick.display_image_route import (
    presentation_image_from_processed_pixmap,
)
from rendering.quick.display_processing import DisplayProcessingDescriptor
from rendering.display_modes import DisplayMode
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.frame_pacer import QuickFrameDemand
from rendering.widget_runtime_manager import WidgetRuntimeManager
from widgets.spotify_visualizer import tick_pipeline
from widgets.spotify_visualizer.presentation_geometry import (
    resolve_visualizer_presentation,
)
from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController


class _ManagerVisualizerEngine:
    def __init__(self) -> None:
        self.acquire_count = 0
        self.release_count = 0
        self.playback: list[bool] = []
        self.generation = 17
        self.activation = 23
        self.transaction_depth = 0
        self.transaction_pending = False
        self.begin_count = 0
        self.end_count = 0
        self.reset_count = 0
        self.cancel_count = 0
        self.floor_reset_count = 0
        self.bar_count = 32
        self._audio_worker = SimpleNamespace(
            set_audio_block_size=lambda _size: None,
        )

    def set_floor_config(self, *_args) -> None:
        pass

    def set_sensitivity_config(self, *_args) -> None:
        pass

    def set_energy_boost(self, *_args) -> None:
        pass

    def set_agc_strength(self, *_args) -> None:
        pass

    def set_input_gain(self, *_args) -> None:
        pass

    def get_generation_id(self) -> int:
        return self.generation

    def get_activation_id(self) -> int:
        return self.activation

    def begin_activation_transaction(self) -> None:
        self.begin_count += 1
        self.transaction_depth += 1

    def end_activation_transaction(self, *, reason: str) -> int:
        assert reason.startswith("quick_mode_change:")
        self.end_count += 1
        self.transaction_depth -= 1
        if self.transaction_depth == 0 and self.transaction_pending:
            self.transaction_pending = False
            self.generation += 1
            self.activation += 1
        return self.activation

    def reconfigure_bar_count(self, count: int) -> None:
        if int(count) != self.bar_count:
            self.bar_count = int(count)
            self.transaction_pending = True

    def cancel_pending_compute_tasks(self) -> None:
        self.cancel_count += 1

    def reset_smoothing_state(self) -> None:
        self.reset_count += 1
        self.transaction_pending = True

    def reset_floor_state(self) -> None:
        self.floor_reset_count += 1

    def set_thread_manager(self, _manager) -> None:
        pass

    def set_runtime_generation(self, _generation) -> None:
        pass

    def set_playback_state(self, playing: bool) -> None:
        self.playback.append(bool(playing))

    def acquire(self) -> None:
        self.acquire_count += 1

    def release(self) -> None:
        self.release_count += 1

    def get_bubble_energy_bands(self):
        return SimpleNamespace(bass=0.0, mid=0.0, high=0.0, overall=0.0)

    def get_transient_energy_bands(self):
        return SimpleNamespace(
            bass_transient=0.0,
            mid_transient=0.0,
            high_transient=0.0,
            onset_detected=False,
            onset_type="",
            onset_strength=0.0,
        )

    def get_event_scheduler(self):
        return None

    def get_perf_diagnostics(self):
        return {}


def test_display_manager_has_no_legacy_presenter_compatibility_surface() -> None:
    source = inspect.getsource(display_manager_module)
    for retired_token in (
        "DisplayWidget",
        "rendering.display_widget",
        "_gl_compositor",
        "_custom_layout_manager",
        "spotify_visualizer_widget",
        "quiesce_for_runtime_pause",
        "set_processed_image",
    ):
        assert retired_token not in source


def test_engine_callers_have_no_legacy_presenter_or_custom_owner_import() -> None:
    source = "\n".join(
        (
            inspect.getsource(engine_handlers_module),
            inspect.getsource(screensaver_engine_module),
        )
    )
    for retired_token in (
        "DisplayWidget",
        "rendering.display_widget",
        "CustomLayoutManager",
        "rendering.custom_layout_manager",
        "suppress_pointer_input_globally",
    ):
        assert retired_token not in source


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


@pytest.mark.qt
def test_display_manager_admits_exactly_one_configured_quick_visualizer_owner(
    qt_app,
    qtbot,
    monkeypatch,
) -> None:
    """Production orchestration resolves settings once and owns one destination."""

    class _Settings:
        def __init__(self) -> None:
            self.widgets = {
                "family_activation": {"media": True, "visualizers": True},
                "clock": {"enabled": False},
                "weather": {"enabled": False},
                "media": {"enabled": True, "monitor": "ALL"},
                "reddit": {"enabled": False},
                "gmail": {"enabled": False},
                "achievement_pulse": {"enabled": False},
                "abandonment_issues": {"enabled": False},
                "spotify_visualizer": {
                    "enabled": True,
                    "visualizers_enabled": True,
                    "monitor": "ALL",
                    "mode": "bubble",
                    "preset_bubble": 3,
                    "bubble_bar_count": 32,
                    "bubble_big_count": 7,
                    "bubble_small_count": 19,
                },
            }
            self.save_calls = 0

        def get_widgets_map(self):
            return deepcopy(self.widgets)

        def get(self, key: str, default=None):
            if key == "widgets":
                return deepcopy(self.widgets)
            value = {"widgets": self.widgets}
            for part in key.split("."):
                if not isinstance(value, dict) or part not in value:
                    return default
                value = value[part]
            return value

        def set(self, key: str, value) -> None:
            target = {"widgets": self.widgets}
            parts = key.split(".")
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = value

        def save(self) -> None:
            self.save_calls += 1

    engine = _ManagerVisualizerEngine()
    monkeypatch.setattr(
        "widgets.spotify_visualizer.beat_engine.get_shared_spotify_beat_engine",
        lambda _count: engine,
    )
    monkeypatch.setattr(
        tick_pipeline, "consume_engine_bars", lambda _owner, _now: (True, True)
    )
    monkeypatch.setattr(
        tick_pipeline, "process_heartbeat", lambda _owner, _now: None
    )
    monkeypatch.setattr(
        tick_pipeline, "record_tick_perf", lambda _owner, _now: None
    )
    monkeypatch.setattr(QuickDisplayUnit, "show_on_screen", lambda _unit: None)

    settings = _Settings()
    manager = DisplayManager(
        settings_manager=settings,
        runtime_generation=702,
    )
    owner = None
    owner_runtime = None
    try:
        assert manager.initialize_displays() == len(qt_app.screens())
        owner = manager._quick_visualizer_owner
        chosen = manager._quick_visualizer_unit
        assert owner is not None
        assert chosen in manager.displays
        participating = [
            unit for unit in manager.displays if unit.is_visualizer_participant()
        ]
        assert chosen.screen_index == min(
            unit.screen_index for unit in participating
        )
        assert [unit._visualizer_owner is not None for unit in manager.displays].count(True) == 1
        assert owner.controller.mode_id == "bubble"
        assert (
            owner.controller.logical_tick_state._bubble_big_count
            == owner.controller.settings_model.bubble_big_count
        )
        assert owner.render_identity.runtime_generation == 702
        assert owner.render_identity.engine_generation == 17
        assert owner.render_identity.activation_id == 23
        assert engine.acquire_count == 1
        assert engine.release_count == 0
        assert owner.is_started is True
        assert chosen.runtime.frame_pacer.demands & QuickFrameDemand.VISUALIZER
        ownership = manager.describe_resource_ownership()["by_generation"]["702"]
        assert ownership["display_units"] == len(qt_app.screens())
        assert ownership["visualizer_owners"] == 1
        assert ownership["visualizer_identities"] == [
            {
                "runtime_generation": 702,
                "engine_generation": 17,
                "activation_id": 23,
                "mode_id": "bubble",
            }
        ]
        owner_runtime = owner.controller.logical_runtime
        assert owner_runtime is not None and owner_runtime.is_running()

        media_presentation = chosen.presenter.presentation_for_widget_id("media")
        assert media_presentation is not None
        media_model = media_presentation.model
        assert manager._quick_visualizer_media_model is media_model
        assert engine.playback[-1] is False
        media_model._replace_snapshot(
            replace(media_model._snapshot, playback_state="playing")
        )
        assert engine.playback[-1] is True

        # The retained menu and visualizer-region double-click both route into
        # this exact owner. A zero-duration test clock preserves the real
        # hidden-boundary transaction while avoiding wall-clock sleeps.
        menu = chosen.runtime.context_menu_model
        visualizer_menu = next(
            entry for entry in menu.entries if entry["label"] == "⟳  Change Visualizer"
        )
        assert next(
            child for child in visualizer_menu["children"] if child["payload"] == "bubble"
        )["checked"] is True
        admission = chosen.runtime.scene_controller._visualizer_double_click_admission
        assert admission is not None
        admission._region_contains = lambda _position: True
        transition_now = [0.0]
        owner._transition_clock = lambda: transition_now[0]
        owner._transition_half_duration_s = 0.25
        owner._sync = SimpleNamespace(sync_latest=lambda: True)
        assert admission.handles_semantic_double_click_at(object()) is True
        assert owner._mode_transition_phase == "fading_out"

        outgoing_runtime = owner_runtime
        transition_now[0] = 0.125
        assert owner.sync_present() is True
        assert owner._mode_transition_fade == pytest.approx(0.5)
        assert outgoing_runtime.is_running() is True
        transition_now[0] = 0.25
        assert owner.sync_present() is True
        assert outgoing_runtime.is_running() is False
        assert owner.controller.mode_id == "devcurve"
        assert owner.render_identity.engine_generation == 18
        assert owner.render_identity.activation_id == 24
        assert engine.begin_count == engine.end_count == 1
        assert engine.reset_count == 1
        assert engine.floor_reset_count == 1
        assert owner.controller.logical_runtime is not outgoing_runtime
        assert owner.controller.logical_runtime.is_running() is True
        assert engine.acquire_count == 1
        assert engine.release_count == 0

        owner.controller.logical_tick_state._waiting_for_fresh_engine_frame = False
        assert owner.sync_present() is True
        assert owner._mode_transition_phase == "fading_in"
        transition_now[0] = 0.375
        assert owner.sync_present() is True
        assert owner._mode_transition_fade == pytest.approx(0.5)
        assert owner._mode_transition_phase == "fading_in"
        transition_now[0] = 0.5
        assert owner.sync_present() is True
        assert owner._mode_transition_phase == "idle"
        assert settings.get("widgets.spotify_visualizer.mode") == "devcurve"
        assert settings.save_calls == 1
        visualizer_menu = next(
            entry for entry in menu.entries if entry["label"] == "⟳  Change Visualizer"
        )
        assert next(
            child for child in visualizer_menu["children"] if child["payload"] == "devcurve"
        )["checked"] is True

        # Context-menu selection uses the same transaction/runtime owner.
        owner._transition_half_duration_s = 0.0
        assert menu.open_at(10.0, 12.0) is True
        assert menu.requestAction("visualizer", "spectrum", True) is True
        second_outgoing_runtime = owner.controller.logical_runtime
        assert owner.sync_present() is True
        assert second_outgoing_runtime.is_running() is False
        owner.controller.logical_tick_state._waiting_for_fresh_engine_frame = False
        assert owner.sync_present() is True
        assert owner.sync_present() is True
        assert owner.controller.mode_id == "spectrum"
        assert settings.get("widgets.spotify_visualizer.mode") == "spectrum"
        assert settings.save_calls == 2
        assert engine.begin_count == engine.end_count == 2
        assert engine.acquire_count == 1
        assert [unit._visualizer_owner is not None for unit in manager.displays].count(True) == 1

        manager.cleanup()
        assert manager._quick_visualizer_owner is None
        assert owner.is_retired is True
        assert owner_runtime.is_running() is False
        assert engine.release_count == 1
        qtbot.waitUntil(
            lambda: not manager._retiring_quick_units,
            timeout=3000,
        )
    finally:
        if not manager._retired:
            if manager.displays:
                manager.cleanup()
                qtbot.waitUntil(
                    lambda: not manager._retiring_quick_units,
                    timeout=3000,
                )
            manager.retire_runtime()
        qt_app.processEvents()


@pytest.mark.qt
def test_display_manager_populates_and_routes_retained_context_menu(
    qt_app,
    qtbot,
    monkeypatch,
) -> None:
    class _Settings:
        def __init__(self) -> None:
            self.data = {
                "widgets": {
                    widget_id: {"enabled": False}
                    for widget_id in (
                        "clock",
                        "weather",
                        "media",
                        "reddit",
                        "gmail",
                        "achievement_pulse",
                        "abandonment_issues",
                    )
                },
                "transitions": {
                    "type": "Crossfade",
                    "random_always": False,
                    "pool": {"Wipe": True},
                },
                "accessibility": {
                    "dimming": {"enabled": False, "opacity": 40},
                    "pixel_shift": {"enabled": False, "rate": 1},
                },
                "display": {"hw_accel": False},
                "input": {"interaction_mode": False},
            }
            self.save_calls = 0

        def get(self, key: str, default=None):
            value = self.data
            for part in key.split("."):
                if not isinstance(value, dict) or part not in value:
                    return default
                value = value[part]
            return value

        def set(self, key: str, value) -> None:
            target = self.data
            parts = key.split(".")
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = value

        def save(self) -> None:
            self.save_calls += 1

        def get_widgets_map(self):
            return deepcopy(self.data["widgets"])

    settings = _Settings()
    monkeypatch.setattr("core.mc.is_mc_build", lambda: False)
    monkeypatch.setattr(QuickDisplayUnit, "show_on_screen", lambda _unit: None)
    manager = DisplayManager(settings_manager=settings, runtime_generation=704)
    previous = []
    next_images = []
    settings_requests = []
    exits = []
    manager.previous_requested.connect(lambda: previous.append(True))
    manager.next_requested.connect(lambda: next_images.append(True))
    manager.settings_requested.connect(lambda: settings_requests.append(True))
    manager.exit_requested.connect(lambda: exits.append(True))
    try:
        assert manager.initialize_displays() == len(qt_app.screens())
        unit = manager.displays[0]
        model = unit.runtime.context_menu_model
        labels = [entry["label"] for entry in model.entries]
        assert "✥  Edit Widget Layout" not in labels
        assert "⟳  Change Visualizer" not in labels

        def _request(action_id: str, payload: str = "", checked: bool = True):
            assert model.open_at(10.0, 12.0) is True
            assert model.requestAction(action_id, payload, checked) is True

        _request("previous")
        _request("next")
        _request("settings")
        assert previous == [True]
        assert next_images == [True]
        assert settings_requests == [True]

        _request("transition", "Wipe")
        assert settings.get("transitions.type") == "Wipe"
        assert settings.get("transitions.random_always") is False

        _request("toggle_dimming", checked=True)
        assert settings.get("accessibility.dimming.enabled") is True
        assert all(
            display.runtime.auxiliary_controller.state.dimming_enabled
            for display in manager.displays
        )

        _request("toggle_interaction", checked=True)
        assert settings.get("input.interaction_mode") is True
        _request("exit")
        assert exits == [True]
        assert settings.save_calls == 3

        manager.cleanup()
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

        def capture_image(self, pixmap, *, image_path: str = ""):
            return presentation_image_from_processed_pixmap(
                pixmap,
                image_path=image_path,
            )

        def current_image(self):
            return self.runtime.scene_controller.presentation_image

        def present_captured_image(self, image) -> None:
            self.runtime.scene_controller.presentation_image = image
            published.append(
                (self.screen_index, QSize(*image.pixel_size), image.source_path)
            )

        def start_transition(self, _request) -> None:
            raise AssertionError("settings-free image route must not admit a transition")

        def runtime_retirement_roots(self):
            return ((self.retirement_qobject,), (self.retirement_owner,))

        def clear(self) -> None:
            self.clear_calls += 1
            self.runtime.scene_controller.presentation_image = None

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


@pytest.mark.qt
def test_display_manager_resolves_one_transition_spec_and_commits_on_finalize(
    qt_app,
) -> None:
    class _Settings:
        def get(self, key: str, default=None):
            if key == "transitions":
                return {
                    "type": "Slide",
                    "random_always": False,
                    "durations": {"Slide": 275},
                    "slide": {"direction": "Random"},
                }
            if key == "display.hw_accel":
                return False
            return default

    class _Unit:
        def __init__(self, screen_index: int, source_path: str) -> None:
            self.screen_index = screen_index
            self._current = presentation_image_from_processed_pixmap(
                QPixmap(4, 3),
                image_path=source_path,
            )
            self.request = None
            self.active = False

        def capture_image(self, pixmap, *, image_path: str = ""):
            return presentation_image_from_processed_pixmap(
                pixmap,
                image_path=image_path,
            )

        def current_image(self):
            return self._current

        def present_captured_image(self, image) -> None:
            self._current = image

        def start_transition(self, request) -> None:
            assert self.request is None
            self.request = request
            self.active = True

        def has_running_transition(self) -> bool:
            return self.active

        def finalize(self, manager: DisplayManager) -> None:
            assert self.request is not None
            self._current = self.request.destination_image
            self.active = False
            manager._on_quick_transition_finalized(
                self,
                SimpleNamespace(
                    destination_image_identity=self._current.identity,
                ),
            )

    manager = DisplayManager(
        settings_manager=_Settings(),
        runtime_generation=703,
    )
    first = _Unit(2, "old-two.jpg")
    second = _Unit(5, "old-five.jpg")
    manager.displays = [first, second]
    completed = []
    manager.transition_completed.connect(completed.append)
    try:
        manager.set_transition_work_pending(True)
        manager.present_processed_image(2, QPixmap(8, 6), QPixmap(), "two.jpg")
        manager.present_processed_image(5, QPixmap(10, 7), QPixmap(), "five.jpg")

        assert first.request is not None
        assert second.request is not None
        assert first.request.transition_id == second.request.transition_id == "slide"
        assert first.request.duration_ms == second.request.duration_ms == 275
        assert first.request.direction == second.request.direction
        assert first.request.parameters == second.request.parameters
        assert first.request.source_image.source_path == "old-two.jpg"
        assert second.request.source_image.source_path == "old-five.jpg"
        assert first.request.destination_image.source_path == "two.jpg"
        assert second.request.destination_image.source_path == "five.jpg"
        assert manager.current_images == {}
        assert manager.has_transition_work_pending() is True

        first.finalize(manager)
        assert manager.current_images == {2: "two.jpg"}
        assert manager.has_transition_work_pending() is True
        second.finalize(manager)
        assert manager.current_images == {2: "two.jpg", 5: "five.jpg"}
        assert manager.has_transition_work_pending() is False
        assert completed == [2, 5]
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
