"""F1 production-shaped gates for the retained Quick Clock family."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtQml import QQmlEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

from rendering.quick.input_controller import QuickInputController
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.scene_controller import QuickSceneController
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.widgets.clock import (
    ClockGeometryVariantStore,
    ClockPresentationConfig,
    ClockPresentationModel,
    ClockPresentationStyle,
    RetainedClockPresentation,
)
from rendering.quick.widgets.host import (
    OrdinaryWidgetPresentationHost,
    OverlayWidgetGeometry,
)
from rendering.quick.window import QuickDisplayWindow
from widgets.clock_ticker import GlobalClockTicker


ROOT = Path(__file__).resolve().parents[1]
QML_ROOT = ROOT / "rendering" / "quick" / "qml"


class _FakeTicker:
    def __init__(self) -> None:
        self.thread_manager = None
        self.subscribers = []

    def set_thread_manager(self, thread_manager) -> None:
        self.thread_manager = thread_manager

    def subscribe(self, callback) -> None:
        if callback not in self.subscribers:
            self.subscribers.append(callback)

    def unsubscribe(self, callback) -> None:
        self.subscribers = [entry for entry in self.subscribers if entry != callback]

    def tick(self) -> None:
        for callback in tuple(self.subscribers):
            callback()


class _TimerHandle:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True

    def deleteLater(self) -> None:
        pass

    def isActive(self) -> bool:
        return not self.stopped


class _ThreadManager:
    def __init__(self) -> None:
        self.scheduled = []

    def schedule_recurring(self, **kwargs):
        self.scheduled.append(kwargs)
        return _TimerHandle()


def _clock_config(**overrides) -> ClockPresentationConfig:
    values = {
        "format": "24h",
        "show_seconds": True,
        "timezone": "UTC+2",
        "show_timezone": True,
        "show_day_of_week": True,
        "show_date": True,
        "show_separator": True,
        "calendar_layout": "shared_line",
        "calendar_font_size": 22,
        "font_family": "Inter",
        "font_size": 48,
        "color": [240, 245, 250, 230],
        "show_background": True,
        "bg_color": [20, 25, 30, 255],
        "bg_opacity": 0.4,
        "border_color": [255, 255, 255, 255],
        "border_opacity": 0.8,
        "display_mode": "digital",
        "show_numerals": True,
        "analog_face_shadow": True,
    }
    values.update(overrides)
    return ClockPresentationConfig.from_mapping("clock", values)


def _shadow_values(**overrides):
    values = {
        "enabled": True,
        "color": [0, 0, 0, 255],
        "blur_radius": 18,
        "frame_opacity": 0.77,
        "frame_extra_offset": 0,
        "text_enabled": True,
        "text_opacity": 0.33,
        "text_extra_offset": 0,
        "header_enabled": True,
        "direction": "SE",
    }
    values.update(overrides)
    return values


def _model(
    now_box: list[datetime],
    ticker: _FakeTicker,
    *,
    config: ClockPresentationConfig | None = None,
) -> ClockPresentationModel:
    resolved = config or _clock_config()
    return ClockPresentationModel(
        resolved,
        ClockPresentationStyle.project(resolved, _shadow_values()),
        now_provider=lambda _zone: now_box[0],
        ticker_provider=lambda: ticker,  # type: ignore[arg-type]
    )


def _create_host(factory: QuickSceneFactory, owner: QObject):
    context, root = factory.create_display_root(
        owner=owner,
        screen_index=0,
        runtime_generation=7,
    )
    host_item = root.findChild(QQuickItem, "ordinaryWidgetHost")
    assert host_item is not None
    host = OrdinaryWidgetPresentationHost(
        host_item=host_item,
        context=context,
        create_overlay_item=factory.create_overlay_widget,
        create_family_item=factory.create_ordinary_widget_family,
    )
    return context, root, host


def _find_visual_item(root: QQuickItem, object_name: str) -> QQuickItem | None:
    if root.objectName() == object_name:
        return root
    for child in root.childItems():
        found = _find_visual_item(child, object_name)
        if found is not None:
            return found
    return None


def test_clock_model_uses_existing_global_ticker_as_sole_cadence_owner(qt_app) -> None:
    GlobalClockTicker.reset()
    manager = _ThreadManager()
    config = _clock_config(show_background=False)
    model = ClockPresentationModel(
        config,
        ClockPresentationStyle.project(config, _shadow_values()),
        now_provider=lambda _zone: datetime(
            2026,
            8,
            25,
            13,
            24,
            30,
            tzinfo=timezone(timedelta(hours=2)),
        ),
    )
    try:
        model.activate(manager)
        ticker = GlobalClockTicker._instance
        assert ticker is not None
        assert model.is_active is True
        assert manager.scheduled[0]["interval_ms"] == 1000
        assert manager.scheduled[0]["description"] == "GlobalClockTicker"
        assert model.timeText == "13:24:30"
        assert model.calendarText == "TUESDAY - 25/08/2026"
        assert model.timezoneText == "UTC+2"
        assert model.hourAngle == pytest.approx(42.25)
        assert model.minuteAngle == pytest.approx(147.0)
        assert model.secondAngle == pytest.approx(180.0)

        model.retire()
        assert model.is_active is False
        assert ticker.get_lifecycle_ownership_snapshot()["total"] == 0
    finally:
        model.retire()
        GlobalClockTicker.reset()


@pytest.mark.qt
def test_clock_family_reuses_display_engine_and_retains_static_analogue_face_across_ticks(
    qt_app,
) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    context, root, host = _create_host(factory, owner)
    ticker = _FakeTicker()
    now_box = [datetime(2026, 8, 25, 13, 24, 30)]
    config = _clock_config(display_mode="analog")
    model = _model(now_box, ticker, config=config)
    presentation = RetainedClockPresentation(
        host=host,
        model=model,
        geometry=OverlayWidgetGeometry(100.0, 80.0, 420.0, 540.0),
        display_bounds=OverlayWidgetGeometry(0.0, 0.0, 1920.0, 1080.0),
        display_identity="screen:a",
    )
    try:
        item = presentation.item
        assert item.parentItem() is root.findChild(QQuickItem, "ordinaryWidgetHost")
        assert QQmlEngine.contextForObject(item).engine() is QQmlEngine.contextForObject(root).engine()
        static_face = item.findChild(QQuickItem, "clockAnalogueStaticFace")
        numeral = _find_visual_item(item, "clockAnalogueNumeral0")
        hour_hand = item.findChild(QQuickItem, "clockAnalogueHourHand")
        assert static_face is not None and numeral is not None and hour_hand is not None

        presentation.activate(object())
        assert ticker.subscribers
        now_box[0] = datetime(2026, 8, 25, 13, 24, 31)
        ticker.tick()
        qt_app.processEvents()

        assert presentation.item is item
        assert item.findChild(QQuickItem, "clockAnalogueStaticFace") is static_face
        assert _find_visual_item(item, "clockAnalogueNumeral0") is numeral
        assert item.findChild(QQuickItem, "clockAnalogueHourHand") is hour_hand
        assert model.secondAngle == pytest.approx(186.0)

        assert presentation.retire() is True
        assert ticker.subscribers == []
    finally:
        host.retire_all()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        factory.deleteLater()
        owner.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_clock_retained_custom_resize_payload_updates_same_model_and_item(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    context, root, host = _create_host(factory, owner)
    model = _model(
        [datetime(2026, 8, 25, 13, 24, 30)],
        _FakeTicker(),
        config=_clock_config(display_mode="digital"),
    )
    presentation = RetainedClockPresentation(
        host=host,
        model=model,
        geometry=OverlayWidgetGeometry(100.0, 80.0, 320.0, 140.0),
        display_bounds=OverlayWidgetGeometry(0.0, 0.0, 1920.0, 1080.0),
        display_identity="screen:a",
    )
    try:
        retained = host.presentation_for_model_identity(model.config.widget_id)
        assert retained is not None
        item_identity = id(presentation.item)
        model_identity = id(model)

        retained.apply_custom_layout_size_payload({"font_size": 72})
        qt_app.processEvents()

        assert model.config.font_size == 72
        assert model.fontSize == 72.0
        assert id(presentation.item) == item_identity
        assert id(presentation.model) == model_identity
    finally:
        host.retire_all()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        factory.deleteLater()
        owner.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_style_direction_and_mode_updates_mutate_existing_clock_in_place(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    context, root, host = _create_host(factory, owner)
    ticker = _FakeTicker()
    now_box = [datetime(2026, 8, 25, 13, 24, 30)]
    config = _clock_config(display_mode="analog")
    model = _model(now_box, ticker, config=config)
    presentation = RetainedClockPresentation(
        host=host,
        model=model,
        geometry=OverlayWidgetGeometry(100.0, 80.0, 420.0, 540.0),
        display_bounds=OverlayWidgetGeometry(0.0, 0.0, 1920.0, 1080.0),
        display_identity="screen:a",
    )
    try:
        presentation.activate(object())
        item = presentation.item
        engine = QQmlEngine.contextForObject(item).engine()
        static_face = item.findChild(QQuickItem, "clockAnalogueStaticFace")
        numeral = _find_visual_item(item, "clockAnalogueNumeral0")
        card = item.findChild(QQuickItem, "overlayWidgetCard")
        calendar = item.findChild(QQuickItem, "clockAnalogueCalendar")
        text_shadow = calendar.findChild(QQuickItem, "shadowedTextShadow")
        assert card is not None and text_shadow is not None

        presentation.apply_config(
            replace_config := ClockPresentationConfig.from_mapping(
                "clock",
                {
                    **{
                        "format": config.time_format,
                        "show_seconds": config.show_seconds,
                        "timezone": config.timezone_name,
                        "show_timezone": config.show_timezone,
                        "show_day_of_week": config.show_day_of_week,
                        "show_date": config.show_date,
                        "show_separator": config.show_separator,
                        "calendar_layout": config.calendar_layout,
                        "calendar_font_size": config.calendar_font_size,
                        "font_family": "Aptos",
                        "font_size": 54,
                        "color": config.text_color,
                        "show_background": config.show_background,
                        "bg_color": config.background_color,
                        "bg_opacity": config.background_opacity,
                        "border_color": config.border_color,
                        "border_opacity": config.border_opacity,
                        "display_mode": "analog",
                        "show_numerals": config.show_numerals,
                        "analog_face_shadow": config.analog_face_shadow,
                    }
                },
            ),
            _shadow_values(
                direction="NW",
                frame_extra_offset=2,
                text_extra_offset=1,
            ),
        )
        qt_app.processEvents()

        assert model.config == replace_config
        assert presentation.item is item
        assert QQmlEngine.contextForObject(item).engine() is engine
        assert item.findChild(QQuickItem, "clockAnalogueStaticFace") is static_face
        assert _find_visual_item(item, "clockAnalogueNumeral0") is numeral
        assert len(ticker.subscribers) == 1
        assert card.property("shadowOffsetX") == pytest.approx(-4.0)
        assert card.property("shadowOffsetY") == pytest.approx(-4.0)
        assert card.property("shadowExtendLeft") == pytest.approx(2.0)
        assert card.property("shadowExtendTop") == pytest.approx(2.0)
        assert text_shadow.x() == pytest.approx(-3.0)
        assert text_shadow.y() == pytest.approx(-3.0)
        assert model.analogRingOffsetX == pytest.approx(-3.0)
        assert model.analogHandOffsetY == pytest.approx(-4.0)
        assert model.fontFamily == "Aptos"
    finally:
        presentation.retire()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        factory.deleteLater()
        owner.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_clock_geometry_variants_round_trip_exactly_and_first_target_centers_once(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    context, root, host = _create_host(factory, owner)
    ticker = _FakeTicker()
    now_box = [datetime(2026, 8, 25, 13, 24, 30)]
    store = ClockGeometryVariantStore()
    digital = OverlayWidgetGeometry(140.0, 120.0, 320.0, 140.0)
    bounds = OverlayWidgetGeometry(0.0, 0.0, 800.0, 600.0)
    model = _model(now_box, ticker)
    presentation = RetainedClockPresentation(
        host=host,
        model=model,
        geometry=digital,
        display_bounds=bounds,
        display_identity="screen:a",
        geometry_store=store,
    )
    try:
        assert presentation.set_display_mode("analog") is True
        first_analog = presentation.geometry
        assert first_analog != digital
        assert first_analog.x + first_analog.width / 2.0 == pytest.approx(
            digital.x + digital.width / 2.0
        )
        assert first_analog.y >= bounds.y
        assert first_analog.y + first_analog.height <= bounds.y + bounds.height

        authored_analog = OverlayWidgetGeometry(20.0, 30.0, 500.0, 550.0)
        presentation.set_geometry(authored_analog)
        assert presentation.set_display_mode("digital") is True
        assert presentation.geometry == digital
        assert presentation.set_display_mode("analog") is True
        assert presentation.geometry == authored_analog
        assert presentation.set_display_mode("digital") is True
        assert presentation.geometry == digital
    finally:
        presentation.retire()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        factory.deleteLater()
        owner.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_quick_window_gives_clock_double_tap_first_refusal_before_next_fallback(
    qt_app,
) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=117,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    window.setGeometry(0, 0, 160, 160)
    input_controller = QuickInputController(
        screen_index=0,
        runtime_generation=117,
        interaction_mode_enabled=True,
    )
    window.bind_input_controller(input_controller)
    scene = QuickSceneController(window=window, factory=factory)
    ticker = _FakeTicker()
    now_box = [datetime(2026, 8, 25, 13, 24, 30)]
    model = _model(now_box, ticker)
    toggles: list[str] = []
    next_requests: list[bool] = []
    presentation = RetainedClockPresentation(
        host=scene.ordinary_widget_host,
        model=model,
        geometry=OverlayWidgetGeometry(10.0, 10.0, 100.0, 80.0),
        display_bounds=OverlayWidgetGeometry(0.0, 0.0, 160.0, 160.0),
        display_identity="screen:a",
        on_mode_toggle=lambda mode, _geometry, _size: toggles.append(mode),
    )
    input_controller.next_image_requested.connect(
        lambda: next_requests.append(True)
    )
    QTest.mouseDClick(
        window,
        Qt.MouseButton.LeftButton,
        pos=QPoint(145, 145),
    )
    qt_app.processEvents()
    assert next_requests == [True]

    QTest.mouseDClick(
        window,
        Qt.MouseButton.LeftButton,
        pos=QPoint(50, 50),
    )
    qt_app.processEvents()

    assert model.displayMode == "analog"
    assert toggles == ["analog"]
    assert next_requests == [True]

    presentation.retire()
    scene.quiesce_for_retirement()
    window.deleteLater()
    input_controller.deleteLater()
    factory.deleteLater()
    qt_app.processEvents()


@pytest.mark.qt
def test_analogue_feature_toggles_and_direction_mutate_retained_items_in_place(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    context, root, host = _create_host(factory, owner)
    ticker = _FakeTicker()
    now_box = [datetime(2026, 8, 25, 13, 24, 30)]
    config = _clock_config(display_mode="analog")
    model = _model(now_box, ticker, config=config)
    presentation = RetainedClockPresentation(
        host=host,
        model=model,
        geometry=OverlayWidgetGeometry(90.0, 70.0, 420.0, 520.0),
        display_bounds=OverlayWidgetGeometry(0.0, 0.0, 1920.0, 1080.0),
        display_identity="screen:a",
    )
    try:
        presentation.activate(object())
        item = presentation.item
        geometry = presentation.geometry
        ring_shadow = item.findChild(QQuickItem, "clockAnalogueRingShadow")
        numeral = _find_visual_item(item, "clockAnalogueNumeral0")
        numeral_shadow = _find_visual_item(item, "clockAnalogueNumeralMainShadow0")
        hour_hand = item.findChild(QQuickItem, "clockAnalogueHourHand")
        hand_shadow = hour_hand.findChild(QQuickItem, "clockHandShadow")
        assert ring_shadow is not None
        assert numeral is not None and numeral_shadow is not None
        assert hour_hand is not None and hand_shadow is not None
        assert ring_shadow.isVisible() is True
        assert numeral_shadow.isVisible() is True
        assert hand_shadow.isVisible() is True

        presentation.apply_config(
            replace(config, analog_face_shadow=False, show_numerals=False),
            _shadow_values(direction="E"),
        )
        qt_app.processEvents()

        assert presentation.item is item
        assert presentation.geometry == geometry
        assert model.displayMode == "analog"
        assert len(ticker.subscribers) == 1
        assert ring_shadow.isVisible() is False
        assert numeral.isVisible() is False
        assert numeral_shadow.isVisible() is False
        assert hand_shadow.isVisible() is False

        presentation.apply_config(
            replace(config, analog_face_shadow=True, show_numerals=True),
            _shadow_values(direction="N"),
        )
        qt_app.processEvents()
        assert presentation.item is item
        assert ring_shadow.isVisible() is True
        assert numeral.isVisible() is True
        assert hand_shadow.isVisible() is True
        assert model.analogRingOffsetX == pytest.approx(0.0)
        assert model.analogRingOffsetY == pytest.approx(-3.0)
        assert model.analogNumeralContactOffsetX == pytest.approx(0.0)
        assert model.analogNumeralContactOffsetY == pytest.approx(-1.0)
        assert model.analogHandOffsetX == pytest.approx(0.0)
        assert model.analogHandOffsetY == pytest.approx(-4.0)
    finally:
        presentation.retire()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        factory.deleteLater()
        owner.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_three_differently_configured_clocks_share_engine_and_ticker(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    context, root, host = _create_host(factory, owner)
    ticker = _FakeTicker()
    now_box = [datetime(2026, 8, 25, 13, 24, 30)]
    configs = (
        _clock_config(display_mode="digital", font_size=48),
        ClockPresentationConfig.from_mapping(
            "clock2",
            {
                "format": "12h",
                "show_seconds": False,
                "timezone": "UTC-5",
                "show_timezone": True,
                "font_size": 34,
                "color": [255, 220, 120, 230],
                "display_mode": "digital",
            },
        ),
        ClockPresentationConfig.from_mapping(
            "clock3",
            {
                "format": "24h",
                "show_seconds": True,
                "timezone": "UTC",
                "show_timezone": False,
                "show_day_of_week": True,
                "show_date": True,
                "font_size": 68,
                "show_background": True,
                "display_mode": "analog",
                "analog_face_shadow": False,
            },
        ),
    )
    presentations = []
    try:
        for index, config in enumerate(configs):
            model = _model(now_box, ticker, config=config)
            presentation = RetainedClockPresentation(
                host=host,
                model=model,
                geometry=OverlayWidgetGeometry(
                    40.0 + index * 360.0,
                    50.0,
                    330.0,
                    180.0 if config.display_mode == "digital" else 450.0,
                ),
                display_bounds=OverlayWidgetGeometry(0.0, 0.0, 1920.0, 1080.0),
                display_identity="screen:a",
            )
            presentation.activate(object())
            presentations.append(presentation)

        engine = QQmlEngine.contextForObject(root).engine()
        assert [presentation.model.config.widget_id for presentation in presentations] == [
            "clock",
            "clock2",
            "clock3",
        ]
        assert all(
            QQmlEngine.contextForObject(presentation.item).engine() is engine
            for presentation in presentations
        )
        assert len(ticker.subscribers) == 3
        assert presentations[0].model.timeText == "13:24:30"
        assert presentations[1].model.timeText == "1:24 PM"
        assert presentations[2].model.displayMode == "analog"
        assert presentations[2].model.analogFaceShadow is False
    finally:
        host.retire_all()
        assert ticker.subscribers == []
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        factory.deleteLater()
        owner.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_clock_family_caller_projects_settings_through_current_scene_host(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=11,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    ticker = _FakeTicker()
    now_box = [datetime(2026, 8, 25, 13, 24, 30)]
    display_signature = "display:test"
    widgets = {
        "clock": {
            "format": "24h",
            "show_seconds": True,
            "show_day_of_week": True,
            "show_date": True,
            "show_separator": True,
            "calendar_layout": "two_lines",
            "calendar_font_size": 27,
            "font_family": "Aptos",
            "font_size": 52,
            "color": [240, 245, 250, 230],
            "show_background": True,
            "bg_color": [20, 25, 30, 255],
            "bg_opacity": 0.4,
            "border_color": [255, 255, 255, 255],
            "border_opacity": 0.8,
            "display_mode": "digital",
            "show_numerals": True,
            "analog_face_shadow": True,
        },
        "clock2": {
            "timezone": "UTC-5",
            "display_mode_overrides": {display_signature: "analog"},
        },
        "clock3": {"timezone": "UTC", "show_seconds": False},
    }
    shadows = _shadow_values(
        direction="NW",
        frame_extra_offset=2,
        text_extra_offset=1,
    )
    toggles: list[tuple[str, str]] = []
    presentations: list[RetainedClockPresentation] = []
    try:
        host = controller.ordinary_widget_host
        for index, widget_id in enumerate(("clock", "clock2", "clock3")):
            config = ClockPresentationConfig.from_widgets_mapping(
                widget_id,
                widgets,
                display_signature=display_signature,
            )
            style = ClockPresentationStyle.project(config, shadows)
            model = ClockPresentationModel(
                config,
                style,
                now_provider=lambda _zone: now_box[0],
                ticker_provider=lambda: ticker,  # type: ignore[arg-type]
            )
            presentation = RetainedClockPresentation(
                host=host,
                model=model,
                geometry=OverlayWidgetGeometry(
                    20.0 + index * 260.0,
                    30.0,
                    240.0,
                    180.0 if config.display_mode == "digital" else 320.0,
                ),
                display_bounds=OverlayWidgetGeometry(0.0, 0.0, 1000.0, 700.0),
                display_identity=display_signature,
                on_mode_toggle=lambda mode, _geometry, _size, wid=widget_id: toggles.append((wid, mode)),
            )
            presentation.activate(object())
            presentations.append(presentation)

        engine = QQmlEngine.contextForObject(controller.scene_root).engine()
        assert [entry.model.config.widget_id for entry in presentations] == [
            "clock",
            "clock2",
            "clock3",
        ]
        assert all(
            QQmlEngine.contextForObject(entry.item).engine() is engine
            for entry in presentations
        )
        assert all(entry.item.parentItem() is not None for entry in presentations)
        assert len(ticker.subscribers) == 3
        assert presentations[1].model.config.timezone_name == "UTC-5"
        assert presentations[1].model.config.font_family == "Aptos"
        assert presentations[1].model.config.calendar_layout == "two_lines"
        assert presentations[1].model.config.display_mode == "analog"
        assert presentations[2].model.config.timezone_name == "UTC"
        assert presentations[2].model.config.show_seconds is True
        assert presentations[0].model.style.card_style.shadow_offset_x == pytest.approx(-4.0)
        assert presentations[0].model.style.card_style.shadow_extend_left == pytest.approx(2.0)
        assert presentations[0].model.style.card_style.shadow_extend_top == pytest.approx(2.0)
        assert presentations[0].model.textShadowOffsetY == pytest.approx(-3.0)

        item = presentations[0].item
        presentations[0].toggle_display_mode()
        assert presentations[0].item is item
        assert toggles == [("clock", "analog")]

        controller.quiesce_for_retirement()
        assert host.is_retired is True
        assert ticker.subscribers == []
    finally:
        controller.quiesce_for_retirement()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


def test_clock_qml_contract_has_retained_two_pass_analogue_shadows_and_no_effect_choreography() -> None:
    analogue = (QML_ROOT / "ClockAnalogueFace.qml").read_text(encoding="utf-8")
    digital = (QML_ROOT / "ClockDigitalFace.qml").read_text(encoding="utf-8")
    presentation = (QML_ROOT / "ClockPresentation.qml").read_text(encoding="utf-8")
    hand = (QML_ROOT / "ClockHand.qml").read_text(encoding="utf-8")
    combined = "\n".join((analogue, digital, presentation, hand))

    for banned in (
        "Timer",
        "FrameAnimation",
        "MultiEffect",
        "layer.enabled",
        "QGraphicsEffect",
        "SettingsManager",
        "QWidget",
    ):
        assert banned not in combined

    assert "clockAnalogueStaticFace" in analogue
    assert "clockAnalogueNumeralMainShadow" in analogue
    assert "clockAnalogueNumeralContactShadow" in analogue
    assert "clockAnalogueNumeralVisible" in analogue
    assert "Tertiary" not in analogue and "tertiary" not in analogue
    assert "analogFaceShadow" in analogue
    assert "clockAnalogueHourHand" in analogue
    assert "clockAnalogueMinuteHand" in analogue
    assert "clockAnalogueSecondHand" in analogue
    assert "width: separatorBand.width * 0.77" in digital
    assert "thickness: digitalFace.clockModel.separatorThickness" in digital
    assert "thickness: analogueFace.clockModel.separatorThickness" in analogue
    assert "height: visible ? 10.0 * analogueFace.fontResizeFactor : 0.0" in analogue
    assert "clockAnalogueSeparator" in analogue
    for source, prefix in ((digital, "digitalFace"), (analogue, "analogueFace")):
        assert f"shadowEnabled: {prefix}.clockModel.textShadowEnabled" in source
        assert f"shadowColor: {prefix}.clockModel.textShadowColor" in source
        assert f"shadowOffsetX: {prefix}.clockModel.textShadowOffsetX" in source
        assert f"shadowOffsetY: {prefix}.clockModel.textShadowOffsetY" in source
    separator = (ROOT / "rendering" / "quick" / "qml" / "Separator.qml").read_text(encoding="utf-8")
    assert 'objectName: "overlaySeparatorShadow"' in separator
    assert "MultiEffect {" not in separator

    clock_model = (ROOT / "rendering" / "quick" / "widgets" / "clock.py").read_text(encoding="utf-8")
    assert "color.alpha() * 0.80" in clock_model
    assert "color.alpha() * 0.45" not in clock_model



def test_static_registry_maps_clock_family_without_member_duplication() -> None:
    from rendering.quick.widgets.registry import ORDINARY_WIDGET_FAMILY_COMPONENTS

    clock_descriptors = [
        descriptor
        for descriptor in ORDINARY_WIDGET_FAMILY_COMPONENTS
        if descriptor.family_id == "clocks"
    ]
    assert len(clock_descriptors) == 1
    descriptor = clock_descriptors[0]
    assert descriptor.qml_filename == "ClockPresentation.qml"
    assert descriptor.presentation_model_kind == "ClockPresentationModel"
    registry_source = (
        ROOT / "rendering" / "quick" / "widgets" / "registry.py"
    ).read_text(encoding="utf-8")
    assert "clock2" not in registry_source
    assert "clock3" not in registry_source


@pytest.mark.qt
def test_clock_custom_font_resizes_footer_and_analogue_ink_proportionally(qt_app) -> None:
    """A parent wheel/corner payload must not leave the calendar/footer at its old size.

    All three Clock identities use this same retained family/model and distinct
    variant payloads. This checks actual QML scene dimensions, not source text.
    """
    for variant, base_size in (("digital", (450.0, 220.0)), ("analog", (420.0, 540.0))):
        owner = QObject()
        factory = QuickSceneFactory()
        context, root, host = _create_host(factory, owner)
        model = _model(
            [datetime(2026, 9, 19, 13, 24, 30)],
            _FakeTicker(),
            config=_clock_config(display_mode=variant),
        )
        presentation = RetainedClockPresentation(
            host=host,
            model=model,
            geometry=OverlayWidgetGeometry(100.0, 80.0, *base_size),
            display_bounds=OverlayWidgetGeometry(0.0, 0.0, 1920.0, 1080.0),
            display_identity="screen:a",
        )
        try:
            item = presentation.item
            qt_app.processEvents()
            calendar = _find_visual_item(
                item, "clockDigitalCalendar" if variant == "digital" else "clockAnalogueCalendar"
            )
            separator = _find_visual_item(
                item, "clockDigitalSeparatorBand" if variant == "digital" else "clockAnalogueSeparator"
            )
            assert calendar is not None and separator is not None
            base_font = float(calendar.property("font").pointSizeF())
            base_separator = float(separator.height())
            if variant == "analog":
                ring = _find_visual_item(item, "clockAnalogueRing")
                assert ring is not None
                base_ring = float(ring.width())
            assert model.fontResizeFactor == pytest.approx(1.0)

            # The existing clock_font owner scales only its variant-local font
            # payload. The QML family must project the same factor onto its
            # remaining authored content, without a second persisted font.
            retained = host.presentation_for_model_identity(model.config.widget_id)
            assert retained is not None
            retained.apply_custom_layout_size_payload({"font_size": 72})
            item.setWidth(base_size[0] * 1.5)
            item.setHeight(base_size[1] * 1.5)
            qt_app.processEvents()
            assert model.fontResizeFactor == pytest.approx(1.5)
            assert float(calendar.property("font").pointSizeF()) == pytest.approx(
                base_font * 1.5, abs=1.0
            )
            assert float(separator.height()) == pytest.approx(
                base_separator * 1.5, abs=1.5
            )
            if variant == "analog":
                # The analogue ring is derived from the painted face's
                # actual remaining footprint after its independently scaled
                # calendar/timezone footer is reserved. The `min(width,
                # height-footer)` transition can legitimately move its
                # ratio slightly without deforming the face. Require a near-
                # uniform ring and the exact calendar/separator ratios above.
                assert float(ring.width()) == pytest.approx(base_ring * 1.5, rel=0.025)
                assert float(ring.height()) == pytest.approx(float(ring.width()), abs=0.01)

            # A real Settings font edit rebases only the transient reference;
            # it does not manufacture another variant/persistence size owner.
            new_config = replace(model.config, font_size=60)
            presentation.apply_config(new_config, _shadow_values())
            qt_app.processEvents()
            assert model.fontResizeFactor == pytest.approx(1.0)
        finally:
            host.retire_all()
            root.setParentItem(None)
            root.setParent(None)
            root.deleteLater()
            context.deleteLater()
            factory.deleteLater()
            owner.deleteLater()
            qt_app.processEvents()


@pytest.mark.qt
@pytest.mark.parametrize("face_mode,role_targets", [
    ("digital", {
        "time_text": "clockDigitalTime",
        "separator": "clockDigitalSeparator",
        "calendar_text": "clockDigitalCalendar",
        "timezone_text": "clockDigitalTimezone",
    }),
    ("analog", {
        "clock_face": "clockAnalogueFaceCoreEditTarget",
        "separator": "clockAnalogueSeparator",
        "calendar_text": "clockAnalogueCalendar",
        "timezone_text": "clockAnalogueTimezone",
    }),
])
def test_clock_selected_edit_proxies_follow_actual_applied_transforms_in_both_faces(
    qt_app, face_mode: str, role_targets: dict[str, str],
) -> None:
    """Actual Clock QML + CUSTOM overlay, not a mock target or a source literal.

    Every mode-appropriate role must retain its QQuickItem and Edit delegate
    through independent live X/Y and scale changes. No transform-list reads or
    second owner are needed: each selected target exposes applied QML values.
    """
    from PySide6.QtCore import QRect, qInstallMessageHandler
    from PySide6.QtQuick import QQuickWindow

    from rendering.custom_child_geometry import CustomChildRoleDescriptor
    from rendering.custom_layout_session import (
        CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem,
    )
    from rendering.quick.custom_layout_overlay import RetainedCustomLayoutOverlay

    window = QQuickWindow()
    window.setGeometry(0, 0, 1100, 850)
    factory = QuickSceneFactory()
    context, root, host = _create_host(factory, window)
    root.setParent(window.contentItem())
    root.setParentItem(window.contentItem())
    root.setWidth(1100.0)
    root.setHeight(850.0)
    ticker = _FakeTicker()
    model = _model(
        [datetime(2026, 8, 25, 13, 24, 30)], ticker,
        config=_clock_config(display_mode=face_mode),
    )
    presentation = RetainedClockPresentation(
        host=host, model=model,
        geometry=OverlayWidgetGeometry(90.0, 65.0, 540.0, 560.0),
        display_bounds=OverlayWidgetGeometry(0.0, 0.0, 1100.0, 850.0),
        display_identity="display:clock-edit-mapping",
    )
    edit_root = _find_visual_item(root, "customLayoutOverlay")
    assert edit_root is not None
    overlay = RetainedCustomLayoutOverlay(edit_root)
    bounds = QRect(90, 65, 540, 560)
    session = CustomLayoutSession()
    session.add_item(CustomLayoutSessionItem(
        source_key=CustomLayoutKey("clock", "display:clock-edit-mapping"),
        model_identity="clock", baseline_global_rect=bounds,
        current_global_rect=bounds, baseline_size_payload={},
        current_size_payload={}, baseline_enabled=True, current_enabled=True,
        custom_child_roles=tuple(
            CustomChildRoleDescriptor(role, movable=role != "clock_face")
            for role in role_targets
        ),
    ))
    messages: list[str] = []

    def collect_warning(_level, _context, message):
        messages.append(str(message))

    previous_handler = qInstallMessageHandler(collect_warning)
    try:
        presentation.activate(object())
        overlay.bind_session(
            session, display_identity="display:clock-edit-mapping",
            display_origin=QPoint(0, 0),
            presentation_item_resolver=lambda _item: presentation.item,
        )
        window.show()
        assert overlay.model.selectItem(0)
        qt_app.processEvents()
        frame = _find_visual_item(edit_root, "customLayoutEditFrame-clock")
        assert frame is not None
        assert frame.setProperty("childEditingLocked", False)
        qt_app.processEvents()

        def verify_painted_role(role_id: str, role_item: QQuickItem, target: QQuickItem) -> None:
            assert _find_visual_item(edit_root, f"customLayoutChildRole-clock-{role_id}") is role_item
            assert role_item.property("targetItem") == target
            assert role_item.property("targetReady") is True, role_id
            def projected_bounds(item: QQuickItem):
                corners = [
                    item.mapToItem(frame, px, py)
                    for px, py in (
                        (0.0, 0.0), (item.width(), 0.0),
                        (0.0, item.height()), (item.width(), item.height()),
                    )
                ]
                xs = [point.x() for point in corners]
                ys = [point.y() for point in corners]
                return min(xs), min(ys), max(xs), max(ys)

            # Clock's real card is clipped. Check the visible painted footprint,
            # not the invisible part of a scaled/moved child outside the card.
            # These two faces use only positive axis-aligned transforms.
            x0, y0, x1, y1 = projected_bounds(target)
            ancestor = target
            while ancestor is not None:
                if ancestor.clip():
                    cx0, cy0, cx1, cy1 = projected_bounds(ancestor)
                    x0, y0 = max(x0, cx0), max(y0, cy0)
                    x1, y1 = min(x1, cx1), min(y1, cy1)
                ancestor = ancestor.parentItem()
            assert x1 > x0 and y1 > y0, role_id
            assert (
                role_item.x(), role_item.y(), role_item.width(), role_item.height()
            ) == pytest.approx((
                x0, y0, x1 - x0, y1 - y0,
            ), abs=0.02), role_id

        for role_id, painted_name in role_targets.items():
            target = _find_visual_item(presentation.item, painted_name)
            role_item = _find_visual_item(edit_root, f"customLayoutChildRole-clock-{role_id}")
            assert target is not None and role_item is not None, (face_mode, role_id)
            verify_painted_role(role_id, role_item, target)
            # The Clock model's existing variant-local child owner is the only
            # input; QML supplies actual Scale/Translate paint and the shared
            # selected-Edit mapper independently projects it.
            if role_id == "clock_face":
                samples = (
                    {"width_scale": 1.17, "height_scale": 1.17},
                    {"width_scale": 0.89, "height_scale": 0.89},
                )
            else:
                samples = (
                    {"width_scale": 1.17, "height_scale": 0.88,
                     "x_offset": 0.07, "y_offset": -0.06},
                    {"width_scale": 0.91, "height_scale": 1.11,
                     "x_offset": -0.04, "y_offset": 0.08},
                )
            for payload in samples:
                before = role_item.property("mappingDependency")
                assert model.set_custom_child_geometry({role_id: payload})
                qt_app.processEvents()
                assert role_item.property("mappingDependency") != before, role_id
                verify_painted_role(role_id, role_item, target)
            assert model.set_custom_child_geometry({})
            qt_app.processEvents()
            verify_painted_role(role_id, role_item, target)
        if face_mode == "digital":
            # Real-world compact-X/Y regression: the unwrapped time glyph used
            # to overflow its smaller assigned Text.width while the selected
            # Edit proxy stayed attached to that width. The card clipped the
            # glyph, and Reset/re-edit appeared to jump. Test actual painted
            # geometry through shrink, authored-size restore and re-shrink.
            time_target = _find_visual_item(presentation.item, "clockDigitalTime")
            column = _find_visual_item(presentation.item, "clockDigitalContent")
            face = _find_visual_item(presentation.item, "clockDigitalFace")
            time_role = _find_visual_item(edit_root, "customLayoutChildRole-clock-time_text")
            assert time_target is not None and column is not None
            assert face is not None and time_role is not None
            retained = host.presentation_for_model_identity("clock")
            assert retained is not None
            retained.apply_custom_layout_size_payload({"font_size": 78})
            qt_app.processEvents()
            assert _find_visual_item(
                edit_root, "customLayoutChildRole-clock-time_text"
            ) is time_role, "Clock role recreated by an intrinsic font-size update"
            for width, height in (
                (378.0, 168.0), (351.0, 456.0),
                (540.0, 560.0), (378.0, 168.0),
            ):
                presentation.set_geometry(OverlayWidgetGeometry(
                    90.0, 65.0, width, height,
                ))
                qt_app.processEvents()
                # Keep the intrinsic, unwrapped glyph within its true painted
                # item, rather than using a narrower Edit rect as a mask.
                assert float(time_target.property("implicitWidth")) <= (
                    time_target.width() + 0.02
                )
                # The whole authored content stack must fit the assigned card
                # before per-role offsets are applied. Its scale is only a
                # derived paint fit, not a second CUSTOM geometry authority.
                start = column.mapToItem(face, 0.0, 0.0)
                end = column.mapToItem(face, column.width(), column.height())
                # This checks visual containment of the Column's *layout box*,
                # not Edit-to-painted-target agreement. Qt's centering and
                # fractional font metrics can place that non-painted box less
                # than one device-independent pixel across an edge (-0.375px
                # on the accepted compact Windows run). Reject meaningful
                # overflow without treating subpixel raster rounding as a
                # geometry failure. The exact mapped target assertion below
                # deliberately retains its independent 0.02px tolerance.
                layout_edge_slack = 1.0
                assert start.x() >= -layout_edge_slack
                assert start.y() >= -layout_edge_slack
                assert end.x() <= face.width() + layout_edge_slack
                assert end.y() <= face.height() + layout_edge_slack
                verify_painted_role("time_text", time_role, time_target)
                assert _find_visual_item(
                    edit_root, "customLayoutChildRole-clock-time_text"
                ) is time_role, "Clock role recreated during an ordinary compact resize"
            assert model.set_custom_child_geometry({
                "time_text": {"x_offset": 0.01, "y_offset": 0.02}
            })
            qt_app.processEvents()
            assert model.set_custom_child_geometry({})  # Reset child state.
            presentation.set_geometry(OverlayWidgetGeometry(
                90.0, 65.0, 351.0, 456.0,
            ))
            qt_app.processEvents()
            verify_painted_role("time_text", time_role, time_target)
        # Closing Edit must retire its delegates. Subsequent normal Clock
        # model updates still paint, but cannot resurrect a selected mapper or
        # add a second observer to the existing one-second ticker.
        overlay.clear_session()
        qt_app.processEvents()
        for index in range(12):
            assert model.set_custom_child_geometry({
                "separator": {"x_offset": (index + 1) * 0.002}
            })
            qt_app.processEvents()
            assert _find_visual_item(
                edit_root, "customLayoutChildRole-clock-separator"
            ) is None
        assert len(ticker.subscribers) == 1
        assert not [
            msg for msg in messages
            if "CustomLayoutOverlay.qml" in msg
            and ("non-bindable" in msg or "Binding loop" in msg)
        ], (face_mode, messages[:5], len(messages))
    finally:
        qInstallMessageHandler(previous_handler)
        overlay.clear_session()
        presentation.retire()
        window.hide()
        host.retire_all()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        factory.deleteLater()
        window.deleteLater()
        qt_app.processEvents()
