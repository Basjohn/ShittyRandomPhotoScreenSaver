"""Destination-owner integration gates for H retained CUSTOM authority."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QKeyEvent

from engine.display_manager import DisplayManager
from rendering.custom_layout_contract import (
    get_screen_layout_entries_for_screen,
    get_widget_layout_variant_payload,
    load_custom_layout_map,
)
from rendering.custom_layout_session import CustomLayoutSession
from rendering.quick.ctrl_coordinator import SharedCtrlCoordinator
from rendering.quick.custom_layout_hydration import (
    apply_quick_committed_payloads,
    resolve_quick_committed_geometry,
)
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
        assert reloads == ["save_continue"]
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
