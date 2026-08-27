"""E3 slice 1 gates: retained ordinary-widget host and shared shell primitives.

These cross the real Quick seam: the shared primitives are compiled through the
same package QML import/component path the production scene uses, and the
synthetic retained item is created under the production display host via the
exact ``QuickSceneController``/``QuickSceneFactory`` ownership the runtime uses.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QColor
from PySide6.QtCore import QObject
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem

from core.settings.shadow_direction import ShadowDirection, resolve_signed_offset
from rendering.quick.bootstrap import quick_qml_root
from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.widgets.host import (
    OrdinaryWidgetPresentationHost,
    OverlayCardStyle,
    OverlayWidgetGeometry,
    RetainedOverlayWidget,
)
from rendering.quick.window import QuickDisplayWindow


ROOT = Path(__file__).resolve().parents[1]
QML_ROOT = quick_qml_root()
PRIMITIVE_FILES = (
    "OverlayWidget.qml",
    "OverlayCard.qml",
    "ShadowedText.qml",
    "Separator.qml",
)


def _load_primitive(engine: QQmlEngine, filename: str) -> QQmlComponent:
    from PySide6.QtCore import QUrl

    component = QQmlComponent(engine, QUrl.fromLocalFile(str(QML_ROOT / filename)))
    return component


def _qml_code_without_comments(path: Path) -> str:
    """Return QML source with ``//`` line comments removed (code-only scan)."""

    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        marker = line.find("//")
        lines.append(line if marker < 0 else line[:marker])
    return "\n".join(lines)


@pytest.mark.qt
def test_all_shell_primitives_load_through_package_import_path(qt_app) -> None:
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    try:
        for filename in PRIMITIVE_FILES:
            component = _load_primitive(engine, filename)
            assert component.status() == QQmlComponent.Status.Ready, [
                error.toString() for error in component.errors()
            ]
            instance = component.create()
            assert isinstance(instance, QQuickItem)
            instance.deleteLater()
    finally:
        engine.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_host_creates_updates_and_retires_synthetic_item_without_new_engine_or_window(
    qt_app,
) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(
        owner=owner,
        screen_index=0,
        runtime_generation=41,
    )
    windows_before = len(qt_app.topLevelWindows())
    host_item = root.findChild(QQuickItem, "ordinaryWidgetHost")
    assert host_item is not None
    host = OrdinaryWidgetPresentationHost(
        host_item=host_item,
        context=context,
        create_overlay_item=factory.create_overlay_widget,
    )

    widget = host.create_widget(
        object_name="synthetic-widget-0",
        geometry=OverlayWidgetGeometry(120.0, 80.0, 300.0, 200.0),
        fade_opacity=1.0,
        card_style=OverlayCardStyle(),
    )
    assert isinstance(widget, RetainedOverlayWidget)
    assert host.live_count == 1
    item = widget.item
    assert item.parentItem() is host_item

    # Creating a retained item must reuse the display's engine/context, never a
    # second QQmlEngine or top-level runtime window.
    item_engine = QQmlEngine.contextForObject(item).engine()
    root_engine = QQmlEngine.contextForObject(root).engine()
    assert item_engine is root_engine
    assert len(qt_app.topLevelWindows()) == windows_before

    # Explicit geometry/style/fade updates land on the retained item.
    widget.set_geometry(OverlayWidgetGeometry(10.0, 20.0, 640.0, 360.0))
    widget.set_fade_opacity(0.4)
    widget.set_card_style(
        OverlayCardStyle(
            background_color=QColor(10, 20, 30, 120),
            border_color=QColor(200, 210, 220, 64),
            corner_radius=12.0,
        )
    )
    assert (item.x(), item.y(), item.width(), item.height()) == (
        10.0,
        20.0,
        640.0,
        360.0,
    )
    assert item.property("fadeOpacity") == pytest.approx(0.4)
    assert item.opacity() == pytest.approx(0.4)
    card = item.findChild(QQuickItem, "overlayWidgetCard")
    assert card is not None
    assert card.property("cornerRadius") == pytest.approx(12.0)
    background = item.findChild(QQuickItem, "overlayCardBackground")
    assert background.property("color").alpha() == 120
    assert background.property("color").alpha() != card.property("borderColor").alpha()

    projected_payloads: list[dict[str, object]] = []
    widget.set_custom_layout_size_payload_handler(
        lambda payload: projected_payloads.append(dict(payload))
    )
    widget.apply_custom_layout_size_payload({"font_size": 72})
    assert projected_payloads == [{"font_size": 72}]

    # Retire without retaining the display generation: the item detaches, the
    # host reports no live widgets, and the retained wrapper fails closed.
    assert host.retire_widget(widget) is True
    assert host.live_count == 0
    assert widget.is_retired is True
    with pytest.raises(RuntimeError):
        _ = widget.item

    factory.deleteLater()
    owner.deleteLater()
    qt_app.processEvents()


@pytest.mark.qt
def test_shell_never_clips_signed_negative_shadow_offsets(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(
        owner=owner,
        screen_index=0,
        runtime_generation=0,
    )
    host_item = root.findChild(QQuickItem, "ordinaryWidgetHost")
    host = OrdinaryWidgetPresentationHost(
        host_item=host_item,
        context=context,
        create_overlay_item=factory.create_overlay_widget,
    )
    widget = host.create_widget(
        geometry=OverlayWidgetGeometry(0.0, 0.0, 200.0, 120.0),
        card_style=OverlayCardStyle(
            shadow_enabled=True,
            shadow_blur=24.0,
            shadow_offset_x=-9.0,
            shadow_offset_y=-11.0,
        ),
    )
    item = widget.item
    card = item.findChild(QQuickItem, "overlayWidgetCard")
    content = item.findChild(QQuickItem, "overlayCardContent")
    shadow = item.findChild(QQuickItem, "overlayCardShadow")

    # No node in the card path may clip the shadow blur or its negative offsets.
    assert item.clip() is False
    assert card.clip() is False
    assert content.clip() is False
    assert host_item.clip() is False
    assert shadow is not None
    assert shadow.isVisible() is True
    offset = shadow.property("offset")
    assert offset.x() == pytest.approx(-9.0)
    assert offset.y() == pytest.approx(-11.0)

    host.retire_all()
    factory.deleteLater()
    owner.deleteLater()
    qt_app.processEvents()


@pytest.mark.qt
def test_shadowed_text_shadow_uses_signed_offset_and_stays_unclipped(qt_app) -> None:
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = _load_primitive(engine, "ShadowedText.qml")
    assert component.status() == QQmlComponent.Status.Ready
    item = component.createWithInitialProperties(
        {
            "text": "Synthetic",
            "shadowEnabled": True,
            "shadowOffsetX": -4.0,
            "shadowOffsetY": -6.0,
        }
    )
    try:
        assert isinstance(item, QQuickItem)
        assert item.clip() is False
        shadow = item.findChild(QQuickItem, "shadowedTextShadow")
        main = item.findChild(QQuickItem, "shadowedTextMain")
        assert shadow is not None and main is not None
        assert shadow.x() == pytest.approx(-4.0)
        assert shadow.y() == pytest.approx(-6.0)
    finally:
        item.deleteLater()
        engine.deleteLater()
        qt_app.processEvents()


def test_shell_primitives_carry_no_per_frame_or_business_logic() -> None:
    # Static retained widgets must not schedule per-frame work, and the shared
    # primitives must remain presentation-only (no providers/settings/QWidget).
    forbidden = (
        "Timer",
        "FrameAnimation",
        "NumberAnimation",
        "SequentialAnimation",
        "Qt.callLater",
        "SettingsManager",
        "import QtQuick.Controls",
    )
    for filename in PRIMITIVE_FILES:
        source = (QML_ROOT / filename).read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in source, f"{filename} must not contain {token!r}"
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("import "):
                assert stripped in {
                    "import QtQuick",
                    "import QtQuick.Effects",
                }, f"{filename} unexpected import: {stripped!r}"

    # E4: ordinary text shadow is the surviving offset-pass semantic only — no
    # MultiEffect, no layer capture, no blur property, no Effects import. Scan
    # code only so explanatory comments naming what is avoided do not trip it.
    shadowed_text_code = _qml_code_without_comments(QML_ROOT / "ShadowedText.qml")
    for banned in ("MultiEffect", "layer.effect", "layer.enabled", "shadowBlur", "QtQuick.Effects"):
        assert banned not in shadowed_text_code, banned
    # It keeps the retained duplicate shadow glyph at a signed offset.
    assert "shadowedTextShadow" in shadowed_text_code
    assert "shadowOffsetX" in shadowed_text_code and "shadowOffsetY" in shadowed_text_code


def test_host_module_is_presentation_only() -> None:
    # Prove presentation-only by imports, not prose: the host may only depend on
    # stdlib and PySide6, never on model/data/settings/QWidget subsystems. E1
    # closed that ownership boundary and E3 must not route it back through here.
    import ast

    source = (ROOT / "rendering" / "quick" / "widgets" / "host.py").read_text(
        encoding="utf-8"
    )
    allowed_from = {"__future__", "collections.abc", "dataclasses"}
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.startswith("PySide6"), alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert (
                module in allowed_from or module.startswith("PySide6")
            ), module


def test_scene_controller_owns_and_retires_ordinary_widget_host(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=0,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    try:
        host = controller.ordinary_widget_host
        widget = host.create_widget(
            geometry=OverlayWidgetGeometry(5.0, 5.0, 100.0, 60.0),
        )
        assert host.live_count == 1
        assert widget.is_retired is False

        controller.quiesce_for_retirement()
        assert controller.readiness.qml_objects_retired is True
        # The host is retired with the display generation and its item released.
        assert widget.is_retired is True
        with pytest.raises(RuntimeError):
            _ = controller.ordinary_widget_host
    finally:
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


# --------------------------------------------------------------------------- #
# E4 — global shadow direction + retained shadow normalization                #
# --------------------------------------------------------------------------- #


def _card_offsets(direction: ShadowDirection) -> tuple[float, float]:
    # Authored card magnitude (offset_x=4, offset_y=6) resolved to a signed
    # offset by the presentation-neutral resolver, before it reaches QML.
    return resolve_signed_offset(direction, 4.0, 6.0)


@pytest.mark.qt
def test_overlay_card_shadow_is_cached_by_default(qt_app) -> None:
    # E4.3: the shared card shadow caches by default so static cards and fades
    # never rebuild the blur.
    source = (QML_ROOT / "OverlayCard.qml").read_text(encoding="utf-8")
    assert "cached: true" in source
    assert "cached: false" not in source

    owner = QObject()
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(
        owner=owner, screen_index=0, runtime_generation=0
    )
    host_item = root.findChild(QQuickItem, "ordinaryWidgetHost")
    host = OrdinaryWidgetPresentationHost(
        host_item=host_item,
        context=context,
        create_overlay_item=factory.create_overlay_widget,
    )
    widget = host.create_widget(
        geometry=OverlayWidgetGeometry(0.0, 0.0, 200.0, 120.0),
        card_style=OverlayCardStyle(),
    )
    shadow = widget.item.findChild(QQuickItem, "overlayCardShadow")
    assert shadow is not None
    assert shadow.property("cached") is True

    host.retire_all()
    factory.deleteLater()
    owner.deleteLater()
    qt_app.processEvents()


@pytest.mark.qt
def test_direction_change_updates_retained_shadow_without_recreating_item(qt_app) -> None:
    # E4.6: a direction change resolves to new signed offsets and updates the
    # retained shadow properties in place — the same QQuickItem, no new engine
    # or window.
    owner = QObject()
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(
        owner=owner, screen_index=0, runtime_generation=0
    )
    windows_before = len(qt_app.topLevelWindows())
    host_item = root.findChild(QQuickItem, "ordinaryWidgetHost")
    host = OrdinaryWidgetPresentationHost(
        host_item=host_item,
        context=context,
        create_overlay_item=factory.create_overlay_widget,
    )

    se_x, se_y = _card_offsets(ShadowDirection.SE)
    widget = host.create_widget(
        geometry=OverlayWidgetGeometry(0.0, 0.0, 200.0, 120.0),
        card_style=OverlayCardStyle(shadow_offset_x=se_x, shadow_offset_y=se_y),
    )
    item = widget.item
    card = item.findChild(QQuickItem, "overlayWidgetCard")
    assert (card.property("shadowOffsetX"), card.property("shadowOffsetY")) == (4.0, 6.0)
    engine_before = QQmlEngine.contextForObject(item).engine()

    nw_x, nw_y = _card_offsets(ShadowDirection.NW)
    widget.set_card_style(OverlayCardStyle(shadow_offset_x=nw_x, shadow_offset_y=nw_y))

    # Same retained item, updated retained properties, no new engine/window.
    assert widget.item is item
    assert (card.property("shadowOffsetX"), card.property("shadowOffsetY")) == (-4.0, -6.0)
    assert QQmlEngine.contextForObject(item).engine() is engine_before
    assert len(qt_app.topLevelWindows()) == windows_before
    assert host.live_count == 1

    host.retire_all()
    factory.deleteLater()
    owner.deleteLater()
    qt_app.processEvents()


@pytest.mark.qt
def test_root_fade_does_not_rewrite_card_shadow_properties(qt_app) -> None:
    # E4.3/E4.5: whole-widget fade is root opacity only and must not touch the
    # card shadow's magnitude/blur/offset/color authorities.
    owner = QObject()
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(
        owner=owner, screen_index=0, runtime_generation=0
    )
    host_item = root.findChild(QQuickItem, "ordinaryWidgetHost")
    host = OrdinaryWidgetPresentationHost(
        host_item=host_item,
        context=context,
        create_overlay_item=factory.create_overlay_widget,
    )
    widget = host.create_widget(
        geometry=OverlayWidgetGeometry(0.0, 0.0, 200.0, 120.0),
        fade_opacity=1.0,
        card_style=OverlayCardStyle(shadow_blur=18.0, shadow_offset_x=4.0, shadow_offset_y=6.0),
    )
    shadow = widget.item.findChild(QQuickItem, "overlayCardShadow")
    before = (
        shadow.property("blur"),
        shadow.property("offset").x(),
        shadow.property("offset").y(),
        shadow.property("color").name(QColor.NameFormat.HexArgb),
    )

    widget.set_fade_opacity(0.3)

    after = (
        shadow.property("blur"),
        shadow.property("offset").x(),
        shadow.property("offset").y(),
        shadow.property("color").name(QColor.NameFormat.HexArgb),
    )
    assert widget.item.property("fadeOpacity") == pytest.approx(0.3)
    assert widget.item.opacity() == pytest.approx(0.3)
    assert after == before

    host.retire_all()
    factory.deleteLater()
    owner.deleteLater()
    qt_app.processEvents()
