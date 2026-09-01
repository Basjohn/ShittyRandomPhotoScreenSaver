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
        interaction_mode_provider=lambda: True,
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
    assert "height: visible ? 10.0 : 0.0" in analogue
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


def test_clock_separator_legacy_key_is_read_only_compatibility_input() -> None:
    legacy = ClockPresentationConfig.from_mapping(
        "clock",
        {"show_digital_separator": True, "separator_thickness": 3},
    )
    current = ClockPresentationConfig.from_mapping(
        "clock",
        {"show_separator": False, "show_digital_separator": True, "separator_thickness": 5},
    )
    assert legacy.show_separator is True
    assert legacy.separator_thickness == pytest.approx(3.0)
    assert current.show_separator is False
    assert current.separator_thickness == pytest.approx(5.0)


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
