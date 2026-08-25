"""F1 production-shaped gates for the retained Quick Clock family."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from PySide6.QtCore import QObject
from PySide6.QtGui import QColor
from PySide6.QtQml import QQmlEngine
from PySide6.QtQuick import QQuickItem

from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.widgets import (
    ClockGeometryVariantStore,
    ClockPresentationConfig,
    ClockPresentationModel,
    ClockPresentationStyle,
    OrdinaryWidgetPresentationHost,
    OverlayWidgetGeometry,
    RetainedClockPresentation,
)
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
        "show_digital_separator": True,
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
                        "show_digital_separator": config.show_separator,
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
        assert card.property("shadowOffsetX") == pytest.approx(-6.0)
        assert card.property("shadowOffsetY") == pytest.approx(-6.0)
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
    assert "thickness: 2.0" in digital
    assert "clockAnalogueSeparator" in analogue


def test_static_registry_maps_clock_family_without_member_duplication() -> None:
    from rendering.quick.widgets.registry import ORDINARY_WIDGET_FAMILY_COMPONENTS

    assert [descriptor.family_id for descriptor in ORDINARY_WIDGET_FAMILY_COMPONENTS] == [
        "clocks"
    ]
    descriptor = ORDINARY_WIDGET_FAMILY_COMPONENTS[0]
    assert descriptor.qml_filename == "ClockPresentation.qml"
    assert descriptor.presentation_model_kind == "ClockPresentationModel"
    registry_source = (
        ROOT / "rendering" / "quick" / "widgets" / "registry.py"
    ).read_text(encoding="utf-8")
    assert "clock2" not in registry_source
    assert "clock3" not in registry_source
