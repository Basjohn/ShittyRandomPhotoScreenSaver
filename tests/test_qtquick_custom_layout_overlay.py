"""G2 gates for the retained, session-backed CUSTOM edit overlay."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QPoint, QRect
from PySide6.QtGui import QColor
from PySide6.QtQuick import QQuickItem

from rendering.custom_layout_session import (
    CustomLayoutKey,
    CustomLayoutSession,
    CustomLayoutSessionItem,
)
from rendering.quick.custom_layout_overlay import (
    CustomLayoutOverlayModel,
    RetainedCustomLayoutOverlay,
)
from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.widgets.host import OverlayWidgetGeometry
from rendering.quick.window import QuickDisplayWindow


ROOT = Path(__file__).resolve().parents[1]


def _quick_items_named(root: QQuickItem, object_name: str) -> list[QQuickItem]:
    matches: list[QQuickItem] = []
    for child in root.childItems():
        if child.objectName() == object_name:
            matches.append(child)
        matches.extend(_quick_items_named(child, object_name))
    return matches


def _item(
    widget_id: str,
    display_identity: str,
    rect: QRect,
    *,
    duplicate: bool = False,
) -> CustomLayoutSessionItem:
    return CustomLayoutSessionItem(
        source_key=CustomLayoutKey(widget_id, display_identity),
        model_identity=widget_id,
        baseline_global_rect=rect,
        current_global_rect=rect,
        baseline_size_payload={},
        current_size_payload={},
        baseline_enabled=True,
        current_enabled=True,
        is_duplicate=duplicate,
    )


def test_overlay_model_mutates_shared_session_items_without_copying_authority() -> None:
    session = CustomLayoutSession()
    singleton = _item("clock", "display:a", QRect(110, 220, 180, 80))
    duplicate = _item(
        "weather",
        "display:a",
        QRect(320, 240, 220, 100),
        duplicate=True,
    )
    foreign = _item("gmail", "display:b", QRect(900, 40, 400, 180))
    for item in (singleton, duplicate, foreign):
        session.add_item(item)

    model = CustomLayoutOverlayModel(
        session=session,
        display_identity="display:a",
        display_origin=QPoint(100, 200),
    )

    assert model.rowCount() == 2
    singleton_identity = id(singleton)
    model.moveItem(0, 36.0, 48.0)
    assert id(session.item(singleton.source_key)) == singleton_identity
    assert singleton.current_global_rect == QRect(136, 248, 180, 80)

    model.closeItem(0)
    assert singleton.current_enabled is False
    assert singleton.removed is False
    assert model.rowCount() == 1

    model.closeItem(0)
    assert duplicate.current_enabled is True
    assert duplicate.removed is True
    assert model.rowCount() == 0
    assert foreign.current_enabled is True
    assert foreign.removed is False


@pytest.mark.qt
def test_display_scene_has_one_retained_overlay_with_red_center_guides(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(
        owner=owner,
        screen_index=0,
        runtime_generation=71,
    )
    root.setWidth(800.0)
    root.setHeight(600.0)
    overlay_items = root.findChildren(QQuickItem, "customLayoutOverlay")
    assert len(overlay_items) == 1
    overlay_item = overlay_items[0]
    retained_identity = id(overlay_item)
    overlay = RetainedCustomLayoutOverlay(overlay_item)

    session = CustomLayoutSession()
    clock = _item("clock", "display:a", QRect(20, 30, 180, 80))
    session.add_item(clock)
    overlay.bind_session(session, display_identity="display:a")
    overlay.set_guides(
        vertical=((400, "display_center"), (260, "peer")),
        horizontal=((300, "peer_center"),),
    )
    qt_app.processEvents()

    assert overlay_item.property("editActive") is True
    assert overlay_item.isVisible() is True
    assert id(overlay.item) == retained_identity
    assert _quick_items_named(overlay_item, "customLayoutEditFrame-clock")

    vertical = _quick_items_named(overlay_item, "customLayoutVerticalGuide")
    horizontal = _quick_items_named(overlay_item, "customLayoutHorizontalGuide")
    assert {line.property("guideKind") for line in vertical} == {
        "display_center",
        "peer",
    }
    center_vertical = next(
        line for line in vertical if line.property("guideKind") == "display_center"
    )
    peer_vertical = next(
        line for line in vertical if line.property("guideKind") == "peer"
    )
    assert center_vertical.property("color") == QColor("#ff3b30")
    assert peer_vertical.property("color") == QColor(180, 110, 255, 235)
    assert horizontal[0].property("color") == QColor("#ff3b30")

    overlay.model.moveItem(0, 70.0, 90.0)
    qt_app.processEvents()
    assert clock.current_global_rect == QRect(70, 90, 180, 80)
    assert id(overlay.item) == retained_identity

    overlay.model.closeItem(0)
    qt_app.processEvents()
    assert clock.current_enabled is False
    assert clock.removed is False
    assert not _quick_items_named(overlay_item, "customLayoutEditFrame-clock")
    assert id(overlay.item) == retained_identity

    overlay.clear_session()
    assert overlay_item.property("editActive") is False
    assert id(overlay.item) == retained_identity

    root.deleteLater()
    context.deleteLater()
    factory.deleteLater()
    owner.deleteLater()
    qt_app.processEvents()


@pytest.mark.qt
def test_scene_controller_owns_overlay_for_exact_display_generation(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=83,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    overlay = controller.custom_layout_overlay
    item = overlay.item

    assert item.objectName() == "customLayoutOverlay"
    assert item.parentItem() is controller.scene_root

    controller.quiesce_for_retirement()
    assert controller.readiness.qml_objects_retired is True
    with pytest.raises(RuntimeError):
        _ = overlay.item
    with pytest.raises(RuntimeError):
        _ = controller.custom_layout_overlay

    window.deleteLater()
    factory.deleteLater()
    qt_app.processEvents()


@pytest.mark.qt
def test_scene_binding_moves_hides_and_restores_same_retained_family_item(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=97,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    presentation = controller.ordinary_widget_host.create_widget(
        object_name="clock",
        model_identity="clock",
        geometry=OverlayWidgetGeometry(4.0, 5.0, 180.0, 80.0),
        fade_opacity=0.35,
    )
    presentation_item = presentation.item
    retained_identity = id(presentation_item)

    session = CustomLayoutSession()
    clock = _item("clock", "display:a", QRect(130, 250, 200, 90))
    session.add_item(clock)
    model = controller.bind_custom_layout_session(
        session,
        display_identity="display:a",
        display_origin=QPoint(100, 200),
    )

    assert controller.ordinary_widget_host.presentation_for_model_identity("clock") is presentation
    assert (presentation_item.x(), presentation_item.y()) == (30.0, 50.0)
    assert (presentation_item.width(), presentation_item.height()) == (200.0, 90.0)
    assert presentation_item.property("workingVisible") is True
    assert presentation_item.opacity() == pytest.approx(0.35)

    model.moveItem(0, 70.0, 95.0)
    assert clock.current_global_rect == QRect(170, 295, 200, 90)
    assert (presentation_item.x(), presentation_item.y()) == (70.0, 95.0)
    assert id(presentation.item) == retained_identity

    model.closeItem(0)
    assert clock.current_enabled is False
    assert presentation_item.property("workingVisible") is False
    assert presentation_item.opacity() == pytest.approx(0.35)
    assert id(presentation.item) == retained_identity

    session.restore_baseline()
    controller.refresh_custom_layout_session()
    assert clock.current_enabled is True
    assert presentation_item.property("workingVisible") is True
    assert (presentation_item.x(), presentation_item.y()) == (30.0, 50.0)
    assert id(presentation.item) == retained_identity

    controller.clear_custom_layout_session()
    assert controller.custom_layout_overlay.item.property("editActive") is False
    assert presentation_item.property("workingVisible") is True
    assert id(presentation.item) == retained_identity

    controller.quiesce_for_retirement()
    window.deleteLater()
    factory.deleteLater()
    qt_app.processEvents()


def test_quick_custom_layout_overlay_is_presentation_only() -> None:
    source = (
        ROOT / "rendering" / "quick" / "custom_layout_overlay.py"
    ).read_text(encoding="utf-8")
    qml = (
        ROOT / "rendering" / "quick" / "qml" / "CustomLayoutOverlay.qml"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "QWidget",
        "QQuickWidget",
        "SettingsManager",
        "provider",
        "capability",
        "QQmlEngine(",
        "QQuickWindow(",
    ):
        assert forbidden not in source
    assert "CustomLayoutSessionItem" in source
    assert "item.apply_remove_action()" in source
    assert "drag.target" not in qml
    assert "sessionModel.moveItem(" in qml
    assert "sessionModel.closeItem(" in qml
