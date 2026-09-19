"""Test-only lifecycle gate for the selected child's Edit-only QML layer.

Twenty select/retire/rebind transitions, no production instrumentation or
runtime geometry mutations. The next active session must have exactly one role
and one frame; Edit OFF must have no retained role delegates.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, QPoint, QRect
from PySide6.QtQuick import QQuickItem

from rendering.custom_child_geometry import CustomChildRoleDescriptor
from rendering.custom_layout_session import CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem
from rendering.quick.custom_layout_overlay import RetainedCustomLayoutOverlay
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.widgets.host import OrdinaryWidgetPresentationHost, OverlayWidgetGeometry


def _named(item: QQuickItem, name: str) -> list[QQuickItem]:
    matches = [item] if item.objectName() == name else []
    for child in item.childItems():
        matches.extend(_named(child, name))
    return matches


@pytest.mark.qt
def test_selected_role_edit_layer_retires_and_rebinds_without_stale_delegates(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(
        owner=owner, screen_index=0, runtime_generation=1913,
    )
    root.setWidth(900.0)
    root.setHeight(650.0)
    host = OrdinaryWidgetPresentationHost(
        host_item=_named(root, "ordinaryWidgetHost")[0],
        shadow_host_item=_named(root, "ordinaryWidgetShadowHost")[0],
        context=context, create_overlay_item=factory.create_overlay_widget,
        create_shadow_item=factory.create_overlay_card_shadow,
    )
    presentation = host.create_widget(
        object_name="friend_pulse", model_identity="friend_pulse",
        geometry=OverlayWidgetGeometry(100.0, 70.0, 540.0, 290.0),
    )
    target = QQuickItem()
    target.setParentItem(presentation.item)
    target.setX(20.0)
    target.setY(100.0)
    target.setWidth(400.0)
    target.setHeight(0.4)
    target.setScale(3.0)
    assert presentation.item.setProperty("customEditableChildRoles", [{
        "roleId": "separator", "target": target,
        "normalizationWidth": 540.0, "normalizationHeight": 290.0,
        "allowParentGrowth": False,
    }])
    rect = QRect(100, 70, 540, 290)
    overlay = RetainedCustomLayoutOverlay(_named(root, "customLayoutOverlay")[0])
    edit_root = overlay.item
    role_name = "customLayoutChildRole-friend_pulse-separator"
    frame_name = "customLayoutEditFrame-friend_pulse"
    try:
        for cycle in range(20):
            session = CustomLayoutSession()
            session.add_item(CustomLayoutSessionItem(
                source_key=CustomLayoutKey("friend_pulse", "display:cycle"),
                model_identity="friend_pulse", baseline_global_rect=rect,
                current_global_rect=rect,
                baseline_size_payload={}, current_size_payload={},
                baseline_enabled=True, current_enabled=True,
                custom_child_roles=(CustomChildRoleDescriptor(
                    "separator", movable=True, uniform_scale=True,
                ),),
            ))
            overlay.bind_session(
                session, display_identity="display:cycle", display_origin=QPoint(0, 0),
                presentation_item_resolver=lambda _item: presentation.item,
            )
            assert overlay.model.selectItem(0)
            qt_app.processEvents()
            assert len(_named(edit_root, frame_name)) == 1, cycle
            frame = _named(edit_root, frame_name)[0]
            assert frame.setProperty("childEditingLocked", False)
            qt_app.processEvents()
            roles = _named(edit_root, role_name)
            assert len(roles) == 1, (cycle, len(roles))
            assert roles[0].property("targetReady") is True
            # Switching to parent-only editing must unload the child role even
            # when the QML edit root/session itself remains alive.
            session.select_item(None)
            qt_app.processEvents()
            assert not _named(edit_root, role_name), cycle
            # A queued Edit requirement from the previous selection cannot
            # resurrect its child layer after the session has been cleared.
            overlay.clear_session()
            qt_app.processEvents()
            qt_app.processEvents()
            assert edit_root.property("editActive") is False
            assert not _named(edit_root, frame_name), cycle
            assert not _named(edit_root, role_name), cycle
        assert target.isVisible() is True
        assert (target.x(), target.y(), target.width(), target.height()) == pytest.approx(
            (20.0, 100.0, 400.0, 0.4), abs=0.001
        )
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
