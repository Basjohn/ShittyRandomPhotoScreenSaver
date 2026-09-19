"""Qt delivery-agent regression for the shared edit overlay's *actual* click routing.

Synthetic QMouseEvents enter a real QQuickWindow. Assertions inspect the shared
session and flip callback, not an inert childAt() or a source string. No timers,
settings, production instrumentation, or screenshots are needed.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtQuick import QQuickItem, QQuickWindow

from rendering.custom_child_geometry import CustomChildRoleDescriptor
from rendering.custom_layout_session import CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem
from rendering.quick.custom_layout_overlay import RetainedCustomLayoutOverlay
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.widgets.host import OrdinaryWidgetPresentationHost, OverlayWidgetGeometry


def _walk(root: QQuickItem):
    yield root
    for child in root.childItems():
        yield from _walk(child)


def _one(root: QQuickItem, name: str) -> QQuickItem:
    matches = [item for item in _walk(root) if item.objectName() == name]
    assert len(matches) == 1, (name, [item.objectName() for item in matches])
    return matches[0]


def _click(window: QQuickWindow, qt_app, x: float, y: float) -> None:
    """Deliver a real press/release through Qt Quick, not a direct slot call."""
    local = QPointF(x, y)
    global_pos = QPointF(window.mapToGlobal(QPoint(round(x), round(y))))
    for event_type, buttons in (
        (QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton),
        (QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton),
    ):
        event = QMouseEvent(
            event_type, local, global_pos, Qt.MouseButton.LeftButton,
            buttons, Qt.KeyboardModifier.NoModifier,
        )
        QCoreApplication.sendEvent(window, event)
        qt_app.processEvents()


@pytest.mark.qt
def test_edit_header_and_empty_top_rail_select_and_flip_without_moving(qt_app) -> None:
    factory = QuickSceneFactory()
    window = QQuickWindow()
    window.setGeometry(0, 0, 760, 480)
    context, root = factory.create_display_root(
        owner=window, screen_index=0, runtime_generation=1201,
    )
    root.setParent(window.contentItem())
    root.setParentItem(window.contentItem())
    root.setWidth(760.0)
    root.setHeight(480.0)
    host = OrdinaryWidgetPresentationHost(
        host_item=_one(root, "ordinaryWidgetHost"),
        shadow_host_item=_one(root, "ordinaryWidgetShadowHost"),
        context=context, create_overlay_item=factory.create_overlay_widget,
        create_shadow_item=factory.create_overlay_card_shadow,
    )
    presentation = host.create_widget(
        object_name="reddit", model_identity="reddit",
        geometry=OverlayWidgetGeometry(100.0, 80.0, 400.0, 220.0),
    )
    header = QQuickItem()
    header.setParentItem(presentation.item)
    header.setX(15.0)
    header.setY(12.0)
    header.setWidth(160.0)
    header.setHeight(34.0)
    assert presentation.item.setProperty("customEditableChildRoles", [{
        "roleId": "header", "target": header,
        "normalizationWidth": 400.0, "normalizationHeight": 220.0,
        "allowParentGrowth": False,
    }])
    rect = QRect(100, 80, 400, 220)
    item = CustomLayoutSessionItem(
        source_key=CustomLayoutKey("reddit", "display:pointer"),
        model_identity="reddit", baseline_global_rect=rect,
        current_global_rect=rect, baseline_size_payload={},
        current_size_payload={}, baseline_enabled=True, current_enabled=True,
        custom_child_roles=(CustomChildRoleDescriptor(
            "header", uniform_scale=True, movable=True, alignment_flip=True,
        ),),
    )
    session = CustomLayoutSession()
    session.add_item(item)
    edit_root = _one(root, "customLayoutOverlay")
    overlay = RetainedCustomLayoutOverlay(edit_root)
    flips: list[str] = []
    try:
        overlay.bind_session(
            session, display_identity="display:pointer", display_origin=QPoint(0, 0),
            presentation_item_resolver=lambda _item: presentation.item,
            child_alignment_flip_handler=lambda _item, role: flips.append(role) or True,
        )
        window.show()
        qt_app.processEvents()
        assert edit_root.isVisible()
        frame = _one(edit_root, "customLayoutEditFrame-reddit")
        move = _one(edit_root, "customLayoutParentMoveArea-reddit")
        assert move.y() == pytest.approx(0.0)
        assert move.height() == pytest.approx(frame.height())

        # These are the old 32px dead strip and the empty space beside a flipped
        # header, neither of which should demand a precise grab on the label.
        for x, y in ((140.0, 85.0), (330.0, 90.0), (220.0, 102.0)):
            session.select_item(None)
            qt_app.processEvents()
            _click(window, qt_app, x, y)
            assert session.selected_item() is item, (x, y)
            assert item.current_global_rect == rect

        overlay.model.requestToggleSelectedChildEditLock()
        qt_app.processEvents()
        assert frame.property("childEditingLocked") is False
        flip = _one(edit_root, "customLayoutChildAlignmentFlip-reddit-header")
        child_frame = _one(edit_root, "customLayoutChildRole-reddit-header")
        assert flip.isVisible() and flip.isEnabled()
        assert (flip.width(), flip.height()) == (30.0, 30.0)
        # Project from the *retained role* into the window to avoid assuming
        # frame/scale mapping or the position of an unflipped header.
        center = flip.mapToItem(root, flip.width() / 2.0, flip.height() / 2.0)
        for dx, dy in ((0.0, 0.0), (-9.0, 0.0), (8.0, 0.0)):
            _click(window, qt_app, center.x() + dx, center.y() + dy)
            assert len(flips) == ((0.0, 0.0), (-9.0, 0.0), (8.0, 0.0)).index((dx, dy)) + 1
            assert item.current_global_rect == rect, "flip press fell through to parent move"
        assert flips == ["header", "header", "header"]
        assert child_frame.isVisible()
    finally:
        overlay.clear_session()
        window.hide()
        host.retire_all()
        header.setParentItem(None)
        header.deleteLater()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        factory.deleteLater()
        window.deleteLater()
        qt_app.processEvents()
