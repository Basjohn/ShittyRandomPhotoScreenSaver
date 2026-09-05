"""Destination-owner integration gates for H retained CUSTOM authority."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QKeyEvent

from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS

from engine.display_manager import DisplayManager
from rendering.custom_layout_contract import (
    get_screen_layout_entries_for_screen,
    get_widget_layout_variant_payload,
    load_custom_layout_map,
)
from rendering.custom_layout_session import (
    CustomLayoutKey,
    CustomLayoutSession,
    CustomLayoutSessionItem,
)
from rendering.quick.ctrl_coordinator import SharedCtrlCoordinator
from rendering.quick.custom_layout_hydration import (
    apply_quick_committed_payloads,
    resolve_quick_committed_geometry,
)
from rendering.quick import custom_layout_owner as custom_owner_module
from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner, _DisplayBinding
from rendering.quick.display_unit import create_quick_display_unit
from rendering.quick.input_controller import QuickInputController
from rendering.quick.runtime import QuickDisplayRuntime
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.widgets.family_binder import ClockFamilyAdapter
from rendering.quick.widgets.host import OverlayWidgetGeometry
from widgets.spotify_visualizer.presentation_geometry import (
    resolve_visualizer_presentation,
)
from widgets.spotify_visualizer import tick_pipeline
from widgets.spotify_visualizer.quick_display_visualizer_owner import (
    QuickDisplayVisualizerOwner,
)


class _Settings:
    def __init__(self, widgets: dict) -> None:
        self.widgets = deepcopy(widgets)
        self.save_calls = 0

    def get_widgets_map(self):
        return deepcopy(self.widgets)

    def set_widgets_map(self, widgets, *, emit_change=True) -> None:
        self.widgets = deepcopy(widgets)

    def save(self) -> None:
        self.save_calls += 1

    def get(self, key: str, default=None):
        current = self.widgets if key == "widgets" else {"widgets": self.widgets}
        for part in key.split("."):
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return deepcopy(current)

    def set(self, key: str, value) -> None:
        if key == "widgets":
            self.widgets = deepcopy(value)
            return
        parts = key.split(".")
        if parts[0] == "widgets":
            parts = parts[1:]
        current = self.widgets
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = deepcopy(value)


def _clock_widgets() -> dict:
    return {
        "clock": {
            "enabled": True,
            "display_mode": "digital",
            "font_size": 48,
            "position": "Top Left",
            "monitor": "ALL",
        },
        "clock2": {"enabled": False},
        "clock3": {"enabled": False},
    }


def _clock_unit(
    qt_app,
    widgets: dict,
    *,
    generation: int = 810,
    screen_index: int = 0,
    factory: QuickSceneFactory | None = None,
    ctrl_coordinator: SharedCtrlCoordinator | None = None,
):
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = factory or QuickSceneFactory()
    unit = create_quick_display_unit(
        screen=screen,
        screen_index=screen_index,
        runtime_generation=generation,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
        ctrl_coordinator=ctrl_coordinator or SharedCtrlCoordinator(),
        adapters=(ClockFamilyAdapter(),),
    )
    unit.bind_families(
        widgets_config=widgets,
        committed_rect_resolver=lambda widget_id: resolve_quick_committed_geometry(
            widgets, screen, widget_id
        ),
    )
    apply_quick_committed_payloads(unit, widgets)
    return unit, factory


def test_authored_clock_switch_stays_anchored_until_custom_save_installs_binding(qt_app) -> None:
    """Authored mode changes keep anchors; CUSTOM Save installs variant replay."""
    widgets = _clock_widgets()
    unit, factory = _clock_unit(qt_app, widgets, generation=809)
    settings = _Settings(widgets)
    owner = QuickCustomLayoutOwner(
        settings_manager=settings, participants_provider=lambda: (unit,),
        visualizer_provider=lambda: (None, None), reload_request=lambda _kind: None,
    )
    try:
        family = unit.presenter.presentation_for_widget_id("clock")
        assert family is not None
        binding = next(entry for widget_id, entry in unit.presenter._geometry_bindings if widget_id == "clock")
        assert binding.policy.has_committed_rect is False
        assert family.set_display_mode("analog") is True
        assert binding.policy.has_committed_rect is False
        assert owner.start() is True
        assert owner.save() is True
        assert binding.policy.has_committed_rect is True
        handler = family._geometry_commit_handler
        assert handler is not None
        assert handler.__self__ is binding
        assert family.set_display_mode("digital") is True
        assert binding.policy.has_committed_rect is True
    finally:
        owner.retire()
        unit.retire()
        factory.deleteLater()
        qt_app.processEvents()


def test_uniform_custom_admission_uses_visible_card_envelope_not_dead_letterbox(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None

    class _QmlItem:
        def property(self, name: str):
            return {
                "preferredContentWidth": 600.0,
                "preferredContentHeight": 400.0,
            }.get(name)

    presentation = SimpleNamespace(item=_QmlItem(), model=SimpleNamespace(config=None))
    presenter = SimpleNamespace(
        bound_widget_ids=("reddit",),
        geometry_for=lambda _widget_id: OverlayWidgetGeometry(100, 120, 600, 800),
        presentation_for_widget_id=lambda _widget_id: presentation,
    )
    unit = SimpleNamespace(presenter=presenter)
    binding = _DisplayBinding(
        identity="display:test",
        monitor_route="1",
        unit=unit,
        screen=screen,
        geometry=QRect(screen.geometry()),
    )
    settings = _Settings({
        "reddit": {
            "enabled": True,
            "position": "Custom",
            "monitor": "1",
        }
    })
    owner = QuickCustomLayoutOwner(
        settings_manager=settings,
        participants_provider=lambda: (),
        visualizer_provider=lambda: (None, None),
        reload_request=lambda _kind: None,
    )
    session = CustomLayoutSession()
    descriptors = {}

    owner._admit_ordinary_items(
        session, descriptors, binding, settings.widgets
    )

    assert len(session.items()) == 1
    item = session.items()[0]
    # Assigned 600x800 renders a 600x400 Reddit card centred vertically. The
    # edit frame must outline that actual visible card, not the 400px dead axis.
    assert item.current_global_rect == QRect(
        screen.geometry().x() + 100,
        screen.geometry().y() + 320,
        600,
        400,
    )
    assert item.baseline_resize_scale == 1.0
    assert item.resize_scale == 1.0


def test_custom_owner_publishes_peer_and_center_guides_from_snap_resolution() -> None:
    class _GuideScene:
        def __init__(self) -> None:
            self.calls: list[dict[str, tuple[tuple[int, str], ...]]] = []

        def set_custom_layout_guides(self, *, vertical=(), horizontal=()) -> None:
            self.calls.append({
                "vertical": tuple(vertical),
                "horizontal": tuple(horizontal),
            })

    def _binding(identity: str, scene: _GuideScene) -> _DisplayBinding:
        return _DisplayBinding(
            identity=identity,
            monitor_route="1",
            unit=SimpleNamespace(
                runtime=SimpleNamespace(scene_controller=scene),
            ),
            screen=None,
            geometry=QRect(0, 0, 800, 600),
        )

    owner = QuickCustomLayoutOwner(
        settings_manager=_Settings({}),
        participants_provider=lambda: (),
        visualizer_provider=lambda: (None, None),
        reload_request=lambda _kind: None,
    )
    active = _GuideScene()
    other = _GuideScene()
    owner._bindings = {
        "display:a": _binding("display:a", active),
        "display:b": _binding("display:b", other),
    }
    guide = lambda position, kind: SimpleNamespace(position=position, kind=kind)
    resolution = SimpleNamespace(
        vertical_guides=(
            guide(260, "peer"),
            guide(400, "display_center"),
            guide(240, "grid"),
        ),
        vertical_assists=(
            guide(260, "peer"),  # duplicate is deliberately collapsed
            guide(310, "peer_center"),
        ),
        horizontal_guides=(guide(300, "peer_center"),),
        horizontal_assists=(guide(24, "gutter"),),
    )

    owner._publish_move_guides("display:a", resolution)

    assert active.calls == [{
        "vertical": (
            (260, "peer"),
            (400, "display_center"),
            (310, "peer_center"),
        ),
        "horizontal": ((300, "peer_center"),),
    }]
    assert other.calls == [{"vertical": (), "horizontal": ()}]

    owner.clear_move_guides()
    assert active.calls[-1] == {"vertical": (), "horizontal": ()}
    assert other.calls[-1] == {"vertical": (), "horizontal": ()}


def test_visualizer_move_latches_one_cross_display_transfer_until_release(monkeypatch) -> None:
    class _Scene:
        def set_custom_layout_guides(self, *, vertical=(), horizontal=()):
            return None

    screen_a, screen_b = object(), object()
    scene_a, scene_b = _Scene(), _Scene()
    owner = QuickCustomLayoutOwner(
        settings_manager=_Settings({}),
        participants_provider=lambda: (),
        visualizer_provider=lambda: (None, None),
        reload_request=lambda _kind: None,
    )
    owner._bindings = {
        "display:a": _DisplayBinding(
            "display:a", "1", SimpleNamespace(runtime=SimpleNamespace(scene_controller=scene_a)),
            screen_a, QRect(0, 0, 800, 600),
        ),
        "display:b": _DisplayBinding(
            "display:b", "2", SimpleNamespace(runtime=SimpleNamespace(scene_controller=scene_b)),
            screen_b, QRect(800, 0, 800, 600),
        ),
    }
    item = CustomLayoutSessionItem(
        source_key=CustomLayoutKey("spotify_visualizer", "display:a"),
        model_identity="spotify_visualizer",
        baseline_global_rect=QRect(100, 100, 420, 280),
        current_global_rect=QRect(100, 100, 420, 280),
        baseline_size_payload={}, current_size_payload={},
        baseline_enabled=True, current_enabled=True,
        resize_capable=True, viewport_resize_capable=True,
        baseline_viewport_extent=(420.0, 280.0),
        source_monitor_route="1",
    )
    candidates = [screen_b, screen_a]
    calls = []

    def choose(*_args, **_kwargs):
        calls.append(True)
        return candidates[min(len(calls) - 1, len(candidates) - 1)]

    monkeypatch.setattr(custom_owner_module, "choose_best_screen_for_global_rect", choose)
    monkeypatch.setattr(custom_owner_module, "should_transfer_rect_to_screen", lambda *_a, **_k: True)
    monkeypatch.setattr(
        custom_owner_module,
        "resolve_snap_local_rect_for_edit",
        lambda rect, *_a, **_k: SimpleNamespace(
            rect=QRect(rect), vertical_guides=(), horizontal_guides=(),
            vertical_assists=(), horizontal_assists=(),
        ),
    )

    owner.resolve_move(item, QRect(900, 100, 420, 280), QPoint(1000, 200))
    assert item.current_display_identity == "display:b"
    assert item.source_key in owner._visualizer_move_transfer_latch

    # Hovering around the seam during the same native drag cannot immediately
    # ping-pong the retained GL admission back to the first display.
    owner.resolve_move(item, QRect(760, 100, 420, 280), QPoint(780, 200))
    assert item.current_display_identity == "display:b"
    assert len(calls) == 1

    owner.clear_move_guides()
    owner.resolve_move(item, QRect(760, 100, 420, 280), QPoint(780, 200))
    assert item.current_display_identity == "display:a"
    assert len(calls) == 2


def test_visualizer_display_hop_uses_nearest_direction_and_preserves_shape() -> None:
    class _Scene:
        def set_custom_layout_guides(self, *, vertical=(), horizontal=()):
            return None

    def binding(identity: str, route: str, x: int) -> _DisplayBinding:
        return _DisplayBinding(
            identity, route,
            SimpleNamespace(runtime=SimpleNamespace(scene_controller=_Scene())),
            object(), QRect(x, 0, 800, 600),
        )

    owner = QuickCustomLayoutOwner(
        settings_manager=_Settings({}),
        participants_provider=lambda: (),
        visualizer_provider=lambda: (None, None),
        reload_request=lambda _kind: None,
    )
    owner._bindings = {
        "display:left": binding("display:left", "1", 0),
        "display:middle": binding("display:middle", "2", 800),
        "display:right": binding("display:right", "3", 1600),
    }
    item = CustomLayoutSessionItem(
        source_key=CustomLayoutKey("spotify_visualizer", "display:middle"),
        model_identity="spotify_visualizer",
        baseline_global_rect=QRect(900, 100, 420, 280),
        current_global_rect=QRect(900, 100, 420, 280),
        baseline_size_payload={}, current_size_payload={},
        baseline_enabled=True, current_enabled=True,
        resize_capable=True, viewport_resize_capable=True,
        baseline_viewport_extent=(420.0, 280.0),
        source_monitor_route="2",
    )

    assert owner._adjacent_display_binding(item, "left").identity == "display:left"
    assert owner._adjacent_display_binding(item, "right").identity == "display:right"
    assert owner.transfer_display(item, "left") is True
    assert item.current_display_identity == "display:left"
    assert item.current_monitor_route == "1"
    assert item.current_global_rect == QRect(100, 100, 420, 280)
    assert item.current_viewport_extent == (420.0, 280.0)

    # From the left display the nearest rightward neighbour is the middle one,
    # not a leap over it to the far-right display.
    assert owner._adjacent_display_binding(item, "right").identity == "display:middle"
    assert owner.transfer_display(item, "right") is True
    assert item.current_display_identity == "display:middle"
    assert item.current_global_rect == QRect(900, 100, 420, 280)


def test_single_quick_custom_owner_cancel_restores_same_retained_item(qt_app) -> None:
    widgets = _clock_widgets()
    settings = _Settings(widgets)
    unit, factory = _clock_unit(qt_app, widgets)
    reloads: list[str] = []
    owner = QuickCustomLayoutOwner(
        settings_manager=settings,
        participants_provider=lambda: (unit,),
        visualizer_provider=lambda: (None, None),
        reload_request=reloads.append,
    )
    try:
        presentation = unit.presenter.presentation_for_widget_id("clock")
        assert presentation is not None
        retained_item = presentation.item
        baseline = unit.presenter.geometry_for("clock")
        assert baseline is not None

        assert owner.start() is True
        assert owner.start() is True
        session = owner.session
        assert session is not None
        assert len(session.items()) == 1
        item = session.items()[0]
        item.set_geometry(
            QRect(
                item.current_global_rect.x() + 140,
                item.current_global_rect.y() + 90,
                item.current_global_rect.width() + 80,
                item.current_global_rect.height() + 40,
            ),
            size_payload={"font_size": 72},
            resize_scale=1.5,
        )
        session.notify_item_changed(item)
        assert presentation.item is retained_item
        assert presentation.model.config.font_size == 72

        assert owner.cancel() is True
        assert owner.is_active is False
        assert presentation.item is retained_item
        assert presentation.model.config.font_size == 48
        assert settings.save_calls == 0
        assert reloads == []
    finally:
        owner.retire()
        unit.retire()
        factory.deleteLater()
        qt_app.processEvents()


def test_single_quick_custom_owner_save_commits_geometry_size_and_enabled(
    qt_app,
) -> None:
    widgets = _clock_widgets()
    settings = _Settings(widgets)
    unit, factory = _clock_unit(qt_app, widgets, generation=811)
    reloads: list[str] = []
    owner = QuickCustomLayoutOwner(
        settings_manager=settings,
        participants_provider=lambda: (unit,),
        visualizer_provider=lambda: (None, None),
        reload_request=reloads.append,
    )
    try:
        assert owner.start() is True
        session = owner.session
        assert session is not None
        item = session.items()[0]
        target = QRect(
            item.current_global_rect.x() + 100,
            item.current_global_rect.y() + 70,
            item.current_global_rect.width() + 60,
            item.current_global_rect.height() + 30,
        )
        item.set_geometry(
            target,
            size_payload={"font_size": 64},
            resize_scale=4.0 / 3.0,
        )
        session.notify_item_changed(item)

        assert owner.save() is True
        assert settings.save_calls == 1
        assert reloads == []
        assert settings.widgets["clock"]["position"] == "Custom"
        assert settings.widgets["clock"]["monitor"] == "ALL"
        custom_map = load_custom_layout_map(settings.widgets)
        matched, entries = get_screen_layout_entries_for_screen(
            custom_map,
            unit.runtime.window.screen(),
        )
        assert matched is not None
        payload = get_widget_layout_variant_payload(entries, "clock", "digital")
        assert payload is not None
        # The committed size_payload now carries the absolute CUSTOM resize scale
        # so a later session restores the same scaled geometry rather than a fresh
        # 100% baseline.
        assert payload["size_payload"] == {
            "font_size": 64,
            "_custom_resize_scale": 4.0 / 3.0,
        }

        committed = resolve_quick_committed_geometry(
            settings.widgets,
            unit.runtime.window.screen(),
            "clock",
        )
        assert committed is not None
        screen = unit.runtime.window.screen().geometry()
        assert committed.x == target.x() - screen.x()
        assert committed.y == target.y() - screen.y()
        assert committed.width == target.width()
        assert committed.height == target.height()
        # A later preferred-size publication must use the live-promoted binding
        # rather than replay the pre-edit committed rectangle.
        binding = next(
            entry
            for widget_id, entry in unit.presenter._geometry_bindings
            if widget_id == "clock"
        )
        binding.update_content_size((240.0, 72.0))
        assert unit.presenter.geometry_for("clock") == OverlayWidgetGeometry(
            float(committed.x),
            float(committed.y),
            float(committed.width),
            float(committed.height),
        )
    finally:
        owner.retire()
        unit.retire()
        factory.deleteLater()
        qt_app.processEvents()


def test_quick_custom_singleton_x_is_working_off_and_save_is_ordinary_off(
    qt_app,
) -> None:
    widgets = _clock_widgets()
    settings = _Settings(widgets)
    unit, factory = _clock_unit(qt_app, widgets, generation=812)
    owner = QuickCustomLayoutOwner(
        settings_manager=settings,
        participants_provider=lambda: (unit,),
        visualizer_provider=lambda: (None, None),
        reload_request=lambda _kind: None,
    )
    try:
        assert owner.start() is True
        model = unit.runtime.scene_controller.custom_layout_overlay.model
        assert model.rowCount() == 1
        model.closeItem(0)
        session = owner.session
        assert session is not None
        item = session.items()[0]
        assert item.removed is False
        assert item.current_enabled is False
        assert settings.widgets["clock"]["enabled"] is True

        assert owner.save() is True
        assert settings.widgets["clock"]["enabled"] is False
    finally:
        owner.retire()
        unit.retire()
        factory.deleteLater()
        qt_app.processEvents()


def test_custom_save_persistence_failure_keeps_the_live_edit_session(qt_app) -> None:
    class _FailingSettings(_Settings):
        def save(self) -> None:
            raise OSError("disk unavailable")

    widgets = _clock_widgets()
    settings = _FailingSettings(widgets)
    unit, factory = _clock_unit(qt_app, widgets, generation=913)
    owner = QuickCustomLayoutOwner(
        settings_manager=settings,
        participants_provider=lambda: (unit,),
        visualizer_provider=lambda: (None, None),
        reload_request=lambda _kind: None,
    )
    try:
        assert owner.start() is True
        session = owner.session
        assert session is not None
        item = session.items()[0]
        target = QRect(item.current_global_rect)
        target.translate(40, 30)
        item.set_geometry(target, size_payload={"font_size": 64})
        session.notify_item_changed(item)
        with pytest.raises(OSError, match="disk unavailable"):
            owner.save()
        assert owner.is_active is True
        assert owner.session is session
        assert item.current_global_rect == target
    finally:
        owner.retire()
        unit.retire()
        factory.deleteLater()
        qt_app.processEvents()


def test_quick_input_enter_and_escape_are_custom_actions_not_exit(qt_app) -> None:
    active = True
    controller = QuickInputController(
        screen_index=0,
        runtime_generation=813,
        custom_layout_active_provider=lambda: active,
    )
    actions: list[str] = []
    controller.custom_layout_save_requested.connect(lambda: actions.append("save"))
    controller.custom_layout_cancel_requested.connect(lambda: actions.append("cancel"))
    controller.exit_requested.connect(lambda: actions.append("exit"))

    enter = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Return,
        Qt.KeyboardModifier.NoModifier,
    )
    escape = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Escape,
        Qt.KeyboardModifier.NoModifier,
    )
    assert controller.handle_key_press(enter) is True
    assert controller.handle_key_press(escape) is True
    assert actions == ["save", "cancel"]

    active = False
    assert controller.handle_key_press(escape) is True
    assert actions == ["save", "cancel", "exit"]
    controller.close_input()


def test_display_manager_menu_routes_one_quick_custom_owner(qt_app) -> None:
    widgets = _clock_widgets()
    settings = _Settings(widgets)
    unit, factory = _clock_unit(qt_app, widgets, generation=815)
    manager = DisplayManager(settings_manager=settings, runtime_generation=815)
    manager.displays = [unit]
    owner = manager._quick_custom_layout_owner
    try:
        manager._refresh_quick_context_menu(unit)
        entries = unit.runtime.context_menu_model.entries
        assert any(entry["actionId"] == "edit_layout" for entry in entries)
        assert manager._handle_quick_context_action(
            unit, "edit_layout", ""
        ) is True
        assert manager._quick_custom_layout_owner is owner
        assert owner.is_active is True
        entries = unit.runtime.context_menu_model.entries
        assert any(entry["actionId"] == "save_layout" for entry in entries)
        assert any(entry["actionId"] == "cancel_layout" for entry in entries)

        assert manager._handle_quick_context_action(
            unit, "cancel_layout", ""
        ) is True
        assert owner.is_active is False
        assert settings.save_calls == 0
    finally:
        manager.displays = []
        manager.retire_runtime()
        unit.retire()
        factory.deleteLater()
        qt_app.processEvents()


def test_cross_display_transfer_coherence_gate_is_fail_safe() -> None:
    """Interactive Save may live-commit a cross-display Visualizer move only when
    the transfer already left a fully target-owned graph.

    This is the safety gate that keeps a partially moved graph (the historic
    split that produced the retained-scene-admission warning storm and shutdown
    barrier timeout) on the reconciliation path. It is pure decision logic, so it
    runs without a real display.
    """

    owner = object()
    source_unit = object()
    target_unit = object()

    def _item(model: str, current_display: str, source_display: str):
        return SimpleNamespace(
            model_identity=model,
            current_display_identity=current_display,
            source_key=SimpleNamespace(display_identity=source_display),
        )

    bindings = {
        "display:a": SimpleNamespace(unit=source_unit),
        "display:b": SimpleNamespace(unit=target_unit),
    }

    def _stub(items, provider_unit):
        return SimpleNamespace(
            _session=SimpleNamespace(items=lambda: items),
            _bindings=bindings,
            _visualizer_provider=lambda: (owner, provider_unit),
        )

    check = QuickCustomLayoutOwner._cross_display_transfer_is_coherent
    moved = [_item("spotify_visualizer", "display:b", "display:a")]

    # Coherent: visualizer moved a -> b and the provider now reports target unit.
    assert check(_stub(moved, target_unit)) is True
    # Incoherent: provider still reports the source unit -> must reconcile.
    assert check(_stub(moved, source_unit)) is False
    # No admitted owner/unit -> must reconcile.
    assert check(
        SimpleNamespace(
            _session=SimpleNamespace(items=lambda: moved),
            _bindings=bindings,
            _visualizer_provider=lambda: (None, None),
        )
    ) is False
    # A non-visualizer family moving displays cannot live-commit yet -> reconcile.
    assert check(_stub([_item("clock", "display:b", "display:a")], target_unit)) is False
    # No cross-display item at all -> nothing blocks a live commit.
    assert check(_stub([_item("spotify_visualizer", "display:a", "display:a")], source_unit)) is True


class _LiveCommitEngine:
    """Complete immutable-capture fake for a real started owner."""

    def acquire(self): pass
    def release(self): pass
    def set_playback_state(self, _playing): pass
    def get_activation_id(self): return 5
    def get_generation_id(self): return 3
    def get_latest_generation_with_frame(self): return 3
    def get_latest_generation_with_waveform(self): return 3
    def get_latest_authoritative_frame(self): return (0.0, 3, 5)
    def get_waveform(self): return (0.0, 0.1, -0.1, 0.05)
    def get_waveform_count(self): return 4
    def get_energy_bands(self): return SimpleNamespace(bass=.2, mid=.1, high=.05, overall=.15)
    def get_bubble_energy_bands(self): return self.get_energy_bands()
    def get_transient_energy_bands(self): return SimpleNamespace(bass_transient=0., mid_transient=0., high_transient=0., onset_detected=False, onset_type="", onset_strength=0.)
    def get_event_scheduler(self): return None
    def get_floor_snapshot(self): return None
    def get_perf_diagnostics(self): return {}


@pytest.mark.parametrize("mode_id", VISUALIZER_MODE_IDS)
@pytest.mark.parametrize("edge", ("left", "right", "top", "bottom"))
@pytest.mark.parametrize(
    ("initial_rect", "initial_extent"),
    (
        ((80.0, 60.0, 412.5, 147.5), (137.5, 49.25)),
        ((80.0, 60.0, 412.0, 79.0), (8240.0, 1579.0)),
    ),
    ids=("fractional-world", "huge-world"),
)
def test_live_visualizer_session_save_preserves_visible_projection_and_identity(
    qt_app, monkeypatch, mode_id, edge, initial_rect, initial_extent,
) -> None:
    """A real CUSTOM QRect edit promotes the retained projection before Save clears it."""
    monkeypatch.setattr(tick_pipeline, "consume_engine_bars", lambda _o, _n: (True, True))
    monkeypatch.setattr(tick_pipeline, "process_heartbeat", lambda _o, _n: None)
    monkeypatch.setattr(tick_pipeline, "record_tick_perf", lambda _o, _n: None)
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    unit = create_quick_display_unit(
        screen=screen, screen_index=0, runtime_generation=917,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
        ctrl_coordinator=SharedCtrlCoordinator(), adapters=(),
    )
    visualizer = QuickDisplayVisualizerOwner(
        unit.runtime, bar_count=24, initial_mode=mode_id,
        engine_factory=lambda _count: _LiveCommitEngine(),
    )
    unit.attach_visualizer_owner(visualizer)
    settings = _Settings({"spotify_visualizer": {"enabled": True, "position": "Custom", "monitor": "1"}})
    layout = QuickCustomLayoutOwner(
        settings_manager=settings, participants_provider=lambda: (unit,),
        visualizer_provider=lambda: (visualizer, unit), reload_request=lambda _kind: None,
    )
    try:
        visualizer.configure(playing=True)
        # Fractional extent forces the same independent-QRect rounding envelope
        # used in production; old 1e-4 equality rejects this legitimate save.
        visualizer.configure_committed_layout(
            local_rect=initial_rect,
            viewport_extent=initial_extent,
        )
        identity = visualizer.bind(engine_generation=3, activation_id=5)
        visualizer._apply_resolved_presentation(visualizer._resolve_current_presentation())
        visualizer.start(interval_s=10.0)
        state = visualizer.controller.logical_tick_state
        state._mode_teardown_block_until_ready = False
        state._mode_transition_ready = True
        state._waiting_for_fresh_engine_frame = False
        state._display_bars_source_generation = 3
        state._display_bars_source_activation = 5
        assert tick_pipeline.logical_tick(state) is not None
        assert visualizer.sync_present() is True
        old_state = visualizer.controller.peek_logical_mode_state(mode_id)
        assert old_state is not None
        last_revision = 0

        assert layout.start() is True
        session = layout.session
        assert session is not None
        item = next(entry for entry in session.items() if entry.model_identity == "spotify_visualizer")
        before = unit.runtime.scene_controller.visualizer_item.presentation
        assert before is not None
        def resize_live(handle: str) -> None:
            nonlocal last_revision
            rect = QRect(item.current_global_rect)
            start = QPoint(rect.center())
            cursor = QPoint(start)
            preview = QPoint(start)
            if handle == "left":
                cursor.setX(rect.left() - 17)
                preview.setX(rect.left() - 8)
            elif handle == "right":
                cursor.setX(rect.right() + 17)
                preview.setX(rect.right() + 8)
            elif handle == "top":
                cursor.setY(rect.top() - 13)
                preview.setY(rect.top() - 6)
            else:
                cursor.setY(rect.bottom() + 13)
                preview.setY(rect.bottom() + 6)
            assert layout.begin_resize(item, handle, start)
            assert layout.update_resize(item, handle, preview, False)
            session.notify_item_changed(item)
            assert tick_pipeline.logical_tick(state) is not None
            assert visualizer.sync_present() is True
            assert layout.update_resize(item, handle, cursor, True)
            session.notify_item_changed(item)
            visible = unit.runtime.scene_controller.visualizer_item.presentation
            assert visible is not None
            assert visible.viewport_extent == item.current_viewport_extent
            working_rect = item.current_global_rect
            assert visible.outer_rect[0] == pytest.approx(float(working_rect.x() - screen.geometry().x()), abs=0.500001)
            assert visible.outer_rect[1] == pytest.approx(float(working_rect.y() - screen.geometry().y()), abs=0.500001)
            assert visible.outer_rect[2] == pytest.approx(float(working_rect.width()), abs=0.500001)
            assert visible.outer_rect[3] == pytest.approx(float(working_rect.height()), abs=0.500001)
            snapshot = visualizer.controller.render_bridge.take_for_render(
                runtime_generation=identity.runtime_generation,
                engine_generation=identity.engine_generation,
                activation_id=identity.activation_id,
                mode_id=identity.mode_id,
                required_presentation=visible,
                allow_presentation_rebase=True,
            )
            assert snapshot is not None
            assert snapshot.logical_revision > last_revision
            last_revision = snapshot.logical_revision

        # Real edits are a sequence, not one isolated drag: alternate axes so
        # rounded pixels cannot become the next world-conversion authority.
        resize_live(edge)
        resize_live("bottom" if edge in {"left", "right"} else "right")
        resize_live("bottom_right")
        extent_before_wheel = item.current_viewport_extent
        assert layout.resize_wheel(item, 120)
        assert item.current_viewport_extent == extent_before_wheel
        session.notify_item_changed(item)
        working = unit.runtime.scene_controller.visualizer_item.presentation
        assert working is not None
        # Cancel must discard the working world even after edit-time normal
        # publications, then the same running owner returns to its baseline.
        assert layout.cancel() is True
        assert tick_pipeline.logical_tick(state) is not None
        assert visualizer.sync_present() is True
        restored = unit.runtime.scene_controller.visualizer_item.presentation
        assert restored is not None
        assert restored.viewport_extent == initial_extent
        assert restored.outer_rect == pytest.approx(before.outer_rect)

        assert layout.start() is True
        session = layout.session
        assert session is not None
        item = next(entry for entry in session.items() if entry.model_identity == "spotify_visualizer")
        resize_live(edge)
        extent_before_wheel = item.current_viewport_extent
        assert layout.resize_wheel(item, 120)
        assert item.current_viewport_extent == extent_before_wheel
        session.notify_item_changed(item)
        working = unit.runtime.scene_controller.visualizer_item.presentation
        assert working is not None
        assert layout.save() is True
        assert visualizer.render_identity is identity
        assert visualizer.controller.peek_logical_mode_state(mode_id) is old_state
        assert unit.runtime.scene_controller.visualizer_item.presentation is not None
        assert visualizer.controller.committed_viewport_extent == working.viewport_extent
        # The next ordinary frame resolves the exact retained floating footprint,
        # not the independently rounded edit QRect or a second display fit.
        assert tick_pipeline.logical_tick(state) is not None
        assert visualizer.sync_present() is True
        normal = unit.runtime.scene_controller.visualizer_item.presentation
        assert normal is not None
        assert normal.outer_rect == pytest.approx(working.outer_rect)
        assert normal.viewport_extent == working.viewport_extent
    finally:
        layout.retire()
        unit.retire()
        factory.deleteLater()
        qt_app.processEvents()


def test_visualizer_custom_transfer_retargets_same_owner_publication(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    source = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=814,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    target = QuickDisplayRuntime(
        screen_index=1,
        runtime_generation=814,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    owner = QuickDisplayVisualizerOwner(
        source,
        bar_count=24,
        initial_mode="bubble",
        engine_factory=lambda _count: object(),
    )
    try:
        owner.configure()
        owner.configure_committed_layout(
            local_rect=(120.0, 80.0, 630.0, 280.0),
            viewport_extent=(630.0, 280.0),
        )
        # Recreation regression: if an intermediate construction publication
        # temporarily commits canonical metrics, the persisted CUSTOM extent must
        # still hydrate the first retained presentation. A cold app restart was
        # masking this by rebuilding directly from persisted truth.
        owner.controller.commit_presentation_metrics(
            resolve_visualizer_presentation(
                policy=owner.controller.presentation_policy,
                display_size=(1920.0, 1080.0),
                viewport_extent=(420.0, 280.0),
            )
        )
        owner.bind(engine_generation=3, activation_id=5)
        first = owner._resolve_current_presentation()
        assert first.viewport_extent == (630.0, 280.0)
        owner._apply_resolved_presentation(first)
        admission = object()
        middle_admission = object()
        source.scene_controller.set_visualizer_double_click_admission(admission)
        source.scene_controller.set_visualizer_middle_click_admission(
            middle_admission
        )

        source.scene_controller.transfer_visualizer_to(target.scene_controller)
        assert owner.set_presentation_runtime(target) is True
        assert owner.presentation_runtime is target
        assert owner._runtime is target
        second = resolve_visualizer_presentation(
            policy=owner.controller.presentation_policy,
            display_size=(1920.0, 1080.0),
            outer_origin=(260.0, 190.0),
            viewport_extent=(630.0, 280.0),
        )
        owner._apply_resolved_presentation(second)

        assert source.scene_controller._visualizer_item is None
        assert target.scene_controller.visualizer_item is not None
        assert target.scene_controller.visualizer_item.presentation is second
        assert target.scene_controller._visualizer_double_click_admission is admission
        assert (
            target.scene_controller._visualizer_middle_click_admission
            is middle_admission
        )
        assert owner.controller.committed_viewport_extent == (630.0, 280.0)
    finally:
        owner.retire()
        source.close_runtime()
        target.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


def test_routed_ordinary_custom_transfer_moves_same_item_cancel_and_save(qt_app) -> None:
    widgets = _clock_widgets()
    widgets["clock"]["monitor"] = "1"
    settings = _Settings(widgets)
    factory = QuickSceneFactory()
    coordinator = SharedCtrlCoordinator()
    units = tuple(
        _clock_unit(
            qt_app,
            widgets,
            generation=816,
            screen_index=index,
            factory=factory,
            ctrl_coordinator=coordinator,
        )[0]
        for index in (0, 1)
    )
    assert units[0].presenter.bound_widget_ids == ("clock",)
    assert units[1].presenter.bound_widget_ids == ()

    logical_screens = tuple(
        SimpleNamespace(
            geometry=lambda rect=QRect(x, 0, 800, 600): QRect(rect),
            name=lambda name=name: name,
            serialNumber=lambda name=name: name,
            manufacturer=lambda: "",
            model=lambda: "",
        )
        for name, x in (("logical-a", 0), ("logical-b", 800))
    )
    routes = tuple(
        SimpleNamespace(
            screen_index=unit.screen_index,
            presenter=unit.presenter,
            is_retired=False,
            runtime=SimpleNamespace(
                window=SimpleNamespace(screen=lambda screen=screen: screen),
                scene_controller=unit.runtime.scene_controller,
            ),
        )
        for unit, screen in zip(units, logical_screens)
    )
    reloads: list[str] = []
    owner = QuickCustomLayoutOwner(
        settings_manager=settings,
        participants_provider=lambda: routes,
        visualizer_provider=lambda: (None, None),
        reload_request=reloads.append,
    )
    source_host = units[0].runtime.scene_controller.ordinary_widget_host
    target_host = units[1].runtime.scene_controller.ordinary_widget_host
    family = units[0].presenter.presentation_for_widget_id("clock")
    assert family is not None
    retained_item = family.item

    def _move_to_target() -> None:
        source_model = units[0].runtime.scene_controller.custom_layout_overlay.model
        assert source_model.rowCount() == 1
        source_model.moveItem(0, 860.0, 120.0, 900.0, 150.0)

    try:
        assert owner.start() is True
        _move_to_target()
        assert source_host.presentation_for_model_identity("clock") is None
        moved = target_host.presentation_for_model_identity("clock")
        assert moved is not None
        assert moved.item is retained_item
        target_model = units[1].runtime.scene_controller.custom_layout_overlay.model
        assert target_model.rowCount() == 1

        assert owner.cancel() is True
        restored = source_host.presentation_for_model_identity("clock")
        assert restored is not None
        assert restored.item is retained_item
        assert target_host.presentation_for_model_identity("clock") is None
        assert settings.widgets["clock"]["monitor"] == "1"
        assert reloads == []

        assert owner.start() is True
        _move_to_target()
        assert owner.save() is True
        moved = target_host.presentation_for_model_identity("clock")
        assert moved is not None
        assert moved.item is retained_item
        assert settings.widgets["clock"]["monitor"] == "2"
        assert settings.widgets["clock"]["position"] == "Custom"
        assert reloads == ["save_continue"]
    finally:
        owner.retire()
        units[0].retire()
        units[1].retire()
        factory.deleteLater()
        qt_app.processEvents()


def test_display_manager_visualizer_transfer_moves_unit_retirement_authority() -> None:
    """Manager/unit ownership follows the retained scene to the target display."""

    class _Owner:
        def __init__(self, runtime) -> None:
            self.runtime = runtime
            self.moves = []

        @property
        def presentation_runtime(self):
            return self.runtime

        @property
        def is_retired(self) -> bool:
            return False

        def set_presentation_runtime(self, runtime) -> bool:
            self.moves.append(runtime)
            self.runtime = runtime
            return True

    class _Unit:
        def __init__(self, screen_index: int) -> None:
            self.screen_index = screen_index
            self.runtime = object()
            self.is_retired = False
            self.visualizer_owner = None

        def attach_visualizer_owner(self, owner) -> None:
            if self.visualizer_owner is not None:
                raise RuntimeError("already owned")
            self.visualizer_owner = owner

        def detach_visualizer_owner(self, owner) -> bool:
            if self.visualizer_owner is None:
                return False
            if self.visualizer_owner is not owner:
                raise RuntimeError("wrong owner")
            self.visualizer_owner = None
            return True

    source, target = _Unit(0), _Unit(1)
    visualizer = _Owner(source.runtime)
    source.visualizer_owner = visualizer
    manager = SimpleNamespace(
        _retired=False,
        _quick_visualizer_owner=visualizer,
        _quick_visualizer_unit=source,
        displays=[source, target],
    )

    assert DisplayManager._transfer_quick_visualizer_unit(manager, target) is True
    assert manager._quick_visualizer_unit is target
    assert source.visualizer_owner is None
    assert target.visualizer_owner is visualizer
    assert visualizer.runtime is target.runtime
    assert visualizer.moves == [target.runtime]


def test_custom_layout_visualizer_display_transaction_moves_scene_and_manager_edge() -> None:
    class _Scene:
        def __init__(self) -> None:
            self.transfers = []

        def transfer_visualizer_to(self, target) -> None:
            self.transfers.append(target)

    class _Runtime:
        def __init__(self, scene) -> None:
            self.scene_controller = scene

    class _Unit:
        def __init__(self, scene) -> None:
            self.runtime = _Runtime(scene)

    source_scene, target_scene = _Scene(), _Scene()
    source_unit, target_unit = _Unit(source_scene), _Unit(target_scene)
    visualizer = object()
    current = {"unit": source_unit}
    transfers = []

    def _transfer(unit) -> bool:
        transfers.append(unit)
        current["unit"] = unit
        return True

    layout = QuickCustomLayoutOwner(
        settings_manager=None,
        participants_provider=lambda: (),
        visualizer_provider=lambda: (visualizer, current["unit"]),
        reload_request=lambda _kind: None,
        visualizer_unit_transfer=_transfer,
    )
    layout._bindings = {
        "source": _DisplayBinding(
            identity="source",
            monitor_route="1",
            unit=source_unit,
            screen=object(),
            geometry=QRect(0, 0, 800, 600),
        ),
        "target": _DisplayBinding(
            identity="target",
            monitor_route="2",
            unit=target_unit,
            screen=object(),
            geometry=QRect(800, 0, 800, 600),
        ),
    }

    layout._transfer_visualizer_display_transaction(source_scene, target_scene)

    assert source_scene.transfers == [target_scene]
    assert target_scene.transfers == []
    assert transfers == [target_unit]
    assert current["unit"] is target_unit


def test_custom_layout_visualizer_display_transaction_rolls_scene_back_on_lifecycle_failure() -> None:
    class _Scene:
        def __init__(self) -> None:
            self.transfers = []

        def transfer_visualizer_to(self, target) -> None:
            self.transfers.append(target)

    class _Runtime:
        def __init__(self, scene) -> None:
            self.scene_controller = scene

    class _Unit:
        def __init__(self, scene) -> None:
            self.runtime = _Runtime(scene)

    source_scene, target_scene = _Scene(), _Scene()
    source_unit, target_unit = _Unit(source_scene), _Unit(target_scene)
    visualizer = object()
    layout = QuickCustomLayoutOwner(
        settings_manager=None,
        participants_provider=lambda: (),
        visualizer_provider=lambda: (visualizer, source_unit),
        reload_request=lambda _kind: None,
        visualizer_unit_transfer=lambda _unit: (_ for _ in ()).throw(
            RuntimeError("manager transfer failed")
        ),
    )
    layout._bindings = {
        "source": _DisplayBinding(
            identity="source", monitor_route="1", unit=source_unit,
            screen=object(), geometry=QRect(0, 0, 800, 600),
        ),
        "target": _DisplayBinding(
            identity="target", monitor_route="2", unit=target_unit,
            screen=object(), geometry=QRect(800, 0, 800, 600),
        ),
    }

    with pytest.raises(RuntimeError, match="manager transfer failed"):
        layout._transfer_visualizer_display_transaction(source_scene, target_scene)

    assert source_scene.transfers == [target_scene]
    assert target_scene.transfers == [source_scene]
