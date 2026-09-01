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
    "OverlayCardShadow.qml",
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
    shadow_host_item = root.findChild(QQuickItem, "ordinaryWidgetShadowHost")
    assert host_item is not None
    assert shadow_host_item is not None
    host = OrdinaryWidgetPresentationHost(
        host_item=host_item,
        shadow_host_item=shadow_host_item,
        context=context,
        create_overlay_item=factory.create_overlay_widget,
        create_shadow_item=factory.create_overlay_card_shadow,
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
    shadow_underlay = widget.shadow_item
    assert item.parentItem() is host_item
    assert shadow_underlay is not None
    assert shadow_underlay.parentItem() is shadow_host_item
    assert item.property("externalCardShadow") is True

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

    input_states: list[object] = []
    initial_input_state = {"ctrl_held": False}

    def _project_input_state(state: object) -> bool:
        input_states.append(state)
        return True

    assert host.apply_input_state(initial_input_state) is False
    host.set_widget_input_state_handler(
        widget,
        _project_input_state,
    )
    assert input_states == [initial_input_state]
    next_input_state = {"ctrl_held": True}
    assert host.apply_input_state(next_input_state) is True
    assert input_states == [initial_input_state, next_input_state]

    # Retire without retaining the display generation: the item detaches, the
    # host reports no live widgets, and the retained wrapper fails closed.
    assert host.retire_widget(widget) is True
    assert host.live_count == 0
    assert widget.is_retired is True
    with pytest.raises(RuntimeError):
        _ = widget.item
    assert host.apply_input_state({"ctrl_held": False}) is False

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

    # No node in the card path may clip the shadow blur or its directional
    # extrusion. Card shadows never use Qt effect translation: negative signed
    # direction grows the surface left/up while the actual effect offset stays 0.
    assert item.clip() is False
    assert card.clip() is False
    assert content.clip() is False
    assert host_item.clip() is False
    assert shadow is not None
    assert shadow.isVisible() is True
    offset = shadow.property("offset")
    assert offset.x() == pytest.approx(0.0)
    assert offset.y() == pytest.approx(0.0)
    background = item.findChild(QQuickItem, "overlayCardBackground")
    assert background is not None
    assert shadow.x() == pytest.approx(background.x() - 9.0)
    assert shadow.y() == pytest.approx(background.y() - 11.0)
    assert shadow.width() == pytest.approx(background.width() + 9.0)
    assert shadow.height() == pytest.approx(background.height() + 11.0)

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


def test_production_ordinary_shadows_use_one_display_underlay_below_all_cards() -> None:
    display = (QML_ROOT / "DisplayScene.qml").read_text(encoding="utf-8")
    overlay = (QML_ROOT / "OverlayWidget.qml").read_text(encoding="utf-8")
    underlay = (QML_ROOT / "OverlayCardShadow.qml").read_text(encoding="utf-8")
    host = (ROOT / "rendering" / "quick" / "widgets" / "host.py").read_text(encoding="utf-8")
    scene = (ROOT / "rendering" / "quick" / "scene_controller.py").read_text(encoding="utf-8")

    assert 'objectName: "ordinaryWidgetShadowHost"' in display
    assert 'objectName: "ordinaryWidgetHost"' in display
    shadow_pos = display.index('objectName: "ordinaryWidgetShadowHost"')
    card_pos = display.index('objectName: "ordinaryWidgetHost"')
    assert shadow_pos < card_pos
    assert "z: 0" in display[shadow_pos:card_pos]
    assert "z: 10" in display[card_pos:]
    assert "property bool externalCardShadow: false" in overlay
    assert "shadowEnabled: overlayWidget.cardShadowEnabled && !overlayWidget.externalCardShadow" in overlay
    assert 'objectName: "overlayCardShadowUnderlay"' in underlay
    assert "sourceWidget.cardShadowVisualWidth" in underlay
    assert "sourceWidget.opacity" in underlay
    assert "offset: Qt.vector2d(0.0, 0.0)" in underlay
    assert 'item.setProperty("externalCardShadow", True)' in host
    assert "create_overlay_card_shadow" in scene


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
def test_startup_gate_is_independent_inherited_and_prevents_punch_through(qt_app) -> None:
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

    # Prime the host before a family root exists. A late-created root must enter
    # the scene already closed; it may never spend a frame at QML's default 1.0.
    assert host.set_startup_reveal_opacity(0.0) == ()
    widget = host.create_widget(
        model_identity="late-family",
        geometry=OverlayWidgetGeometry(0.0, 0.0, 200.0, 120.0),
        fade_opacity=1.0,
    )
    assert widget.item.property("startupRevealOpacity") == pytest.approx(0.0)
    assert widget.item.opacity() == pytest.approx(0.0)

    # A family-local publication may freely drive its authored fade back to one;
    # it still cannot become visible before the generation startup gate opens.
    widget.set_fade_opacity(1.0)
    assert widget.item.property("fadeOpacity") == pytest.approx(1.0)
    assert widget.item.opacity() == pytest.approx(0.0)

    assert host.set_startup_reveal_opacity(0.5) == ("late-family",)
    assert widget.item.opacity() == pytest.approx(0.5)
    widget.set_fade_opacity(0.4)
    assert widget.item.opacity() == pytest.approx(0.2)

    # A second root created mid-reveal inherits the current scalar synchronously.
    second = host.create_widget(
        model_identity="mid-reveal-family",
        geometry=OverlayWidgetGeometry(220.0, 0.0, 200.0, 120.0),
        fade_opacity=1.0,
    )
    assert second.item.property("startupRevealOpacity") == pytest.approx(0.5)
    assert second.item.opacity() == pytest.approx(0.5)

    # Steam-style roots authored to begin hidden must enter the scene with BOTH
    # gates already closed/current; the host must not parent at QML's default
    # fadeOpacity=1 and correct it afterwards.
    hidden = host.create_widget(
        model_identity="initially-hidden-family",
        geometry=OverlayWidgetGeometry(440.0, 0.0, 200.0, 120.0),
        fade_opacity=0.0,
    )
    assert hidden.item.property("startupRevealOpacity") == pytest.approx(0.5)
    assert hidden.item.property("fadeOpacity") == pytest.approx(0.0)
    assert hidden.item.opacity() == pytest.approx(0.0)

    host_source = (ROOT / "rendering" / "quick" / "widgets" / "host.py").read_text(
        encoding="utf-8"
    )
    adopt_start = host_source.index("    def _adopt_item(")
    adopt_end = host_source.index("    def registered_image_provider", adopt_start)
    adopt = host_source[adopt_start:adopt_end]
    assert adopt.index('item.setProperty("fadeOpacity", initial_fade)') < adopt.index(
        "item.setParentItem(host_item)"
    )

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


@pytest.mark.qt
def test_overlay_card_frame_extra_offset_is_directional_growth_not_full_translation(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(
        owner=owner, screen_index=0, runtime_generation=0
    )
    host_item = root.findChild(QQuickItem, "ordinaryWidgetHost")
    shadow_host_item = root.findChild(QQuickItem, "ordinaryWidgetShadowHost")
    assert host_item is not None
    assert shadow_host_item is not None
    host = OrdinaryWidgetPresentationHost(
        host_item=host_item,
        shadow_host_item=shadow_host_item,
        context=context,
        create_overlay_item=factory.create_overlay_widget,
        create_shadow_item=factory.create_overlay_card_shadow,
    )

    widget = host.create_widget(
        geometry=OverlayWidgetGeometry(0.0, 0.0, 200.0, 120.0),
        card_style=OverlayCardStyle(
            shadow_offset_x=4.0,
            shadow_offset_y=4.0,
            shadow_extend_right=20.0,
            shadow_extend_bottom=20.0,
        ),
    )
    qt_app.processEvents()

    card = widget.item.findChild(QQuickItem, "overlayWidgetCard")
    shadow_underlay = widget.shadow_item
    shadow = None if shadow_underlay is None else shadow_underlay.findChild(
        QQuickItem, "overlayCardShadow"
    )
    background = widget.item.findChild(QQuickItem, "overlayCardBackground")
    assert card is not None
    assert shadow_underlay is not None
    assert shadow_underlay.parentItem() is shadow_host_item
    assert widget.item.property("externalCardShadow") is True
    assert shadow is not None
    assert background is not None

    # The host writes the extension values on OverlayWidget and the card binds
    # them locally while the display-level shadow underlay consumes the same
    # root properties. No inert dynamic QObject properties are permitted.
    assert card.property("shadowExtendLeft") == pytest.approx(0.0)
    assert card.property("shadowExtendTop") == pytest.approx(0.0)
    assert card.property("shadowExtendRight") == pytest.approx(20.0)
    assert card.property("shadowExtendBottom") == pytest.approx(20.0)

    # Both the authored 4px base direction and Extra Offset are asymmetric
    # geometry. The Qt shadow effect itself must remain untranslated, so SE +20
    # grows right/bottom by 24px while top/left coordinates remain invariant.
    assert shadow.property("offset").x() == pytest.approx(0.0)
    assert shadow.property("offset").y() == pytest.approx(0.0)
    assert shadow.x() == pytest.approx(background.x())
    assert shadow.y() == pytest.approx(background.y())
    assert shadow.width() == pytest.approx(background.width() + 24.0)
    assert shadow.height() == pytest.approx(background.height() + 24.0)

    # Reorienting to NW mirrors only the extrusion edge. The opposite right/
    # bottom boundary remains exactly at the background boundary.
    widget.set_card_style(
        OverlayCardStyle(
            shadow_offset_x=-4.0,
            shadow_offset_y=-4.0,
            shadow_extend_left=20.0,
            shadow_extend_top=20.0,
        )
    )
    qt_app.processEvents()
    assert card.property("shadowExtendLeft") == pytest.approx(20.0)
    assert card.property("shadowExtendTop") == pytest.approx(20.0)
    assert card.property("shadowExtendRight") == pytest.approx(0.0)
    assert card.property("shadowExtendBottom") == pytest.approx(0.0)
    assert shadow.property("offset").x() == pytest.approx(0.0)
    assert shadow.property("offset").y() == pytest.approx(0.0)
    assert shadow.x() == pytest.approx(background.x() - 24.0)
    assert shadow.y() == pytest.approx(background.y() - 24.0)
    assert shadow.width() == pytest.approx(background.width() + 24.0)
    assert shadow.height() == pytest.approx(background.height() + 24.0)
    assert shadow.x() + shadow.width() == pytest.approx(
        background.x() + background.width()
    )
    assert shadow.y() + shadow.height() == pytest.approx(
        background.y() + background.height()
    )

    host.retire_all()
    factory.deleteLater()
    owner.deleteLater()
    qt_app.processEvents()
