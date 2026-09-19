"""Rendered Qt gate for lock position, child hitbox isolation and parent chrome.

No production timer/service/Settings dependency; the existing session owns geometry.
This supplements the nine-family scene tests, not a claim of human visual acceptance.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, QPoint, QRect
from PySide6.QtQuick import QQuickItem

from rendering.custom_layout_session import CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.custom_layout_overlay import RetainedCustomLayoutOverlay
from rendering.quick.widgets.host import OrdinaryWidgetPresentationHost, OverlayWidgetGeometry


@pytest.mark.qt
def test_child_lock_is_reset_adjacent_default_locked_and_does_not_retire_geometry(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(owner=owner, screen_index=0, runtime_generation=901)
    root.setWidth(1200.0)
    root.setHeight(800.0)
    host_item = root.findChild(QQuickItem, "ordinaryWidgetHost")
    shadow_host_item = root.findChild(QQuickItem, "ordinaryWidgetShadowHost")
    host = OrdinaryWidgetPresentationHost(
        host_item=host_item, shadow_host_item=shadow_host_item, context=context,
        create_overlay_item=factory.create_overlay_widget,
        create_shadow_item=factory.create_overlay_card_shadow,
    )
    presentation = host.create_widget(
        object_name="clock", model_identity="clock",
        geometry=OverlayWidgetGeometry(100.0, 90.0, 400.0, 240.0),
    )
    target = QQuickItem()
    target.setParentItem(presentation.item)
    target.setX(38.0)
    target.setY(210.0)  # Deliberately overlaps the reset-adjacent lock.
    target.setWidth(80.0)
    target.setHeight(22.0)
    # Use the same QML role projection as the production clock, without a ticker.
    assert presentation.item.setProperty("customEditableChildRoles", [{
        "roleId": "time_text", "target": target,
        "normalizationWidth": 400.0, "normalizationHeight": 240.0,
        "allowParentGrowth": False,
    }])
    rect = QRect(100, 90, 400, 240)
    session = CustomLayoutSession()
    session.add_item(CustomLayoutSessionItem(
        source_key=CustomLayoutKey("clock", "display:lock"),
        model_identity="clock", baseline_global_rect=rect,
        current_global_rect=rect, baseline_size_payload={}, current_size_payload={},
        baseline_enabled=True, current_enabled=True, is_duplicate=False,
        resize_capable=True, size_reset_capable=True,
    ))
    edit_root = root.findChild(QQuickItem, "customLayoutOverlay")
    overlay = RetainedCustomLayoutOverlay(edit_root)
    try:
        overlay.bind_session(session, display_identity="display:lock", display_origin=QPoint(0, 0),
                             presentation_item_resolver=lambda _item: presentation.item)
        edit_root.setProperty("editActive", True)
        assert overlay.model.selectItem(0)
        qt_app.processEvents()

        # Repeater delegates have visual parentage rather than QObject ownership.
        # Both the role lookup and the corner-loader assertion need this walker.
        def walk(parent: QQuickItem):
            for child in parent.childItems():
                yield child
                yield from walk(child)

        def one(name: str) -> QQuickItem:
            items = [i for i in walk(edit_root) if i.objectName() == name]
            assert len(items) == 1, (name, [i.objectName() for i in walk(edit_root)])
            return items[0]

        frame = one("customLayoutEditFrame-clock")
        reset = one("customLayoutRestoreSize-clock")
        lock = one("customLayoutChildEditLock-clock")
        close = one("customLayoutClose-clock")
        mark = one("customLayoutChildEditLockMark-clock")
        role_layer = one("customLayoutChildRoleLayer-clock")
        role_frame = one("customLayoutChildRole-clock-time_text")
        parent_corner = one("customLayoutResize-clock-bottom_left")
        assert frame.property("childEditingLocked") is True
        assert (lock.width(), lock.height()) == (22.0, 22.0)
        assert mark.scale() == pytest.approx(0.9)
        assert lock.x() == pytest.approx(reset.x() + reset.width() + 6.0)
        assert lock.y() == pytest.approx(reset.y())
        assert min(close.z(), reset.z(), lock.z()) > max(role_layer.z(), parent_corner.z())
        # QQuickItem.childAt returns an enclosing full-frame Loader here;
        # it is not a pointer-delivery/hit-test oracle. The Loader is a
        # transparent parent for only the corner MouseAreas and must stay
        # below all actionable parent chrome. Actual pointer acceptance is
        # covered by the Windows scene-interaction gate, not childAt alone.
        corner_loader = one("contentCornerLoader") if any(
            i.objectName() == "contentCornerLoader"
            for i in walk(edit_root)
        ) else None
        if corner_loader is not None:
            assert corner_loader.z() < min(close.z(), reset.z(), lock.z())
        for control in (close, reset, lock):
            assert control.isVisible() and control.isEnabled()
            assert control.width() == 22.0 and control.height() == 22.0
        assert role_layer.isVisible() is False and role_frame.isVisible() is False
        assert target.isVisible() is True
        assert (target.x(), target.y(), target.width(), target.height()) == (38.0, 210.0, 80.0, 22.0)

        # The L shortcut raises the same model event consumed by the existing
        # glyph; it must not create a second lock state or touch geometry.
        overlay.model.requestToggleSelectedChildEditLock()
        qt_app.processEvents()
        assert frame.property("childEditingLocked") is False
        assert role_layer.isVisible() is True
        overlay.model.requestToggleSelectedChildEditLock()
        qt_app.processEvents()
        assert frame.property("childEditingLocked") is True
        assert role_layer.isVisible() is False

        # Unlock only the edit chrome; keep the existing observer and model.
        assert frame.setProperty("childEditingLocked", False)
        qt_app.processEvents()
        assert role_layer.isVisible() is True and role_frame.isVisible() is True
        assert one("customLayoutChildRoleLayer-clock") is role_layer
        assert target.isVisible() is True
        assert frame.setProperty("childEditingLocked", True)
        qt_app.processEvents()
        assert role_layer.isVisible() is False
        assert one("customLayoutChildRoleLayer-clock") is role_layer
        assert (frame.x(), frame.y(), frame.width(), frame.height()) == (100.0, 90.0, 400.0, 240.0)
    finally:
        overlay.clear_session()
        host.retire_all()
        target.setParentItem(None)
        target.deleteLater()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        factory.deleteLater()
        owner.deleteLater()
        qt_app.processEvents()
