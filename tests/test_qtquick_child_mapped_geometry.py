"""Real retained-QML regression for edit-only mapped child bounds.

The *target* and the occupied paint may differ. Assertions use four independent
Qt-mapped corners, rather than mirroring the QML helper's implementation. No
production probes, render-loop timing, Settings writes, or provider data.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, QPoint, QRect
from PySide6.QtQuick import QQuickItem, QQuickWindow

from rendering.custom_child_geometry import CustomChildRoleDescriptor
from rendering.custom_layout_session import CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem
from rendering.quick.custom_layout_overlay import RetainedCustomLayoutOverlay
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.widgets.host import OrdinaryWidgetPresentationHost, OverlayWidgetGeometry


def _walk(item: QQuickItem):
    yield item
    for child in item.childItems():
        yield from _walk(child)


def _one(root: QQuickItem, name: str) -> QQuickItem:
    found = [child for child in _walk(root) if child.objectName() == name]
    assert len(found) == 1, (name, [i.objectName() for i in _walk(root)])
    return found[0]


def _mapped_corners(item: QQuickItem, frame: QQuickItem):
    return [
        item.mapToItem(frame, x, y)
        for x, y in ((0.0, 0.0), (item.width(), 0.0),
                     (0.0, item.height()), (item.width(), item.height()))
    ]


def _assert_bounds(actual, item: QQuickItem, frame: QQuickItem):
    corners = _mapped_corners(item, frame)
    x0 = min(point.x() for point in corners)
    y0 = min(point.y() for point in corners)
    x1 = max(point.x() for point in corners)
    y1 = max(point.y() for point in corners)
    assert actual == pytest.approx((x0, y0, x1 - x0, y1 - y0), abs=0.02)


@pytest.mark.qt
def test_live_window_reflow_with_cancelling_axes_keeps_selected_proxy_on_paint(qt_app) -> None:
    """An actual retained window must follow x/y and width/height compensation.

    The old additive mapping dependency lost the changed signal when opposite
    component deltas summed to zero. The edit delegate must survive unchanged.
    """
    factory = QuickSceneFactory()
    window = QQuickWindow()
    window.setGeometry(0, 0, 1000, 700)
    context, root = factory.create_display_root(
        owner=window, screen_index=0, runtime_generation=1935,
    )
    root.setParent(window.contentItem())
    root.setParentItem(window.contentItem())
    root.setWidth(1000.0)
    root.setHeight(700.0)
    host = OrdinaryWidgetPresentationHost(
        host_item=_one(root, "ordinaryWidgetHost"),
        shadow_host_item=_one(root, "ordinaryWidgetShadowHost"),
        context=context, create_overlay_item=factory.create_overlay_widget,
        create_shadow_item=factory.create_overlay_card_shadow,
    )
    presentation = host.create_widget(
        object_name="friend_pulse", model_identity="friend_pulse",
        geometry=OverlayWidgetGeometry(90.0, 65.0, 620.0, 380.0),
    )
    ancestor = QQuickItem()
    ancestor.setParentItem(presentation.item)
    ancestor.setX(35.0)
    ancestor.setY(42.0)
    ancestor.setWidth(310.0)
    ancestor.setHeight(180.0)
    ancestor.setRotation(22.0)
    target = QQuickItem()
    target.setParentItem(ancestor)
    target.setX(18.0)
    target.setY(32.0)
    target.setWidth(165.0)
    target.setHeight(48.0)
    assert presentation.item.setProperty("customEditableChildRoles", [{
        "roleId": "header", "target": target,
        "geometryDependencies": [ancestor],
        "normalizationWidth": 620.0, "normalizationHeight": 380.0,
        "allowParentGrowth": False,
    }])
    rect = QRect(90, 65, 620, 380)
    session = CustomLayoutSession()
    session.add_item(CustomLayoutSessionItem(
        source_key=CustomLayoutKey("friend_pulse", "display:mapped-live"),
        model_identity="friend_pulse", baseline_global_rect=rect,
        current_global_rect=rect, baseline_size_payload={}, current_size_payload={},
        baseline_enabled=True, current_enabled=True,
        custom_child_roles=(CustomChildRoleDescriptor("header", movable=True),),
    ))
    edit_root = _one(root, "customLayoutOverlay")
    overlay = RetainedCustomLayoutOverlay(edit_root)
    try:
        overlay.bind_session(
            session, display_identity="display:mapped-live",
            display_origin=QPoint(0, 0),
            presentation_item_resolver=lambda _item: presentation.item,
        )
        window.show()
        assert overlay.model.selectItem(0)
        qt_app.processEvents()
        frame = _one(edit_root, "customLayoutEditFrame-friend_pulse")
        assert frame.setProperty("childEditingLocked", False)
        qt_app.processEvents()
        role = _one(edit_root, "customLayoutChildRole-friend_pulse-header")
        assert role.property("targetReady") is True
        _assert_bounds((role.x(), role.y(), role.width(), role.height()), target, frame)
        for moving, first, second in (
            (ancestor, "x", "y"),
            (ancestor, "width", "height"),
            (target, "x", "y"),
        ):
            before = role.property("mappingDependency")
            getattr(moving, "set" + first.capitalize())(getattr(moving, first)() + 13.0)
            getattr(moving, "set" + second.capitalize())(getattr(moving, second)() - 13.0)
            qt_app.processEvents()
            assert role.property("mappingDependency") != before
            assert _one(edit_root, "customLayoutChildRole-friend_pulse-header") is role
            _assert_bounds((role.x(), role.y(), role.width(), role.height()), target, frame)
        overlay.clear_session()
        qt_app.processEvents()
        assert not any(item.objectName() == "customLayoutChildRole-friend_pulse-header"
                       for item in _walk(edit_root))
        assert target.isVisible()
    finally:
        overlay.clear_session()
        window.hide()
        host.retire_all()
        target.setParentItem(None)
        target.deleteLater()
        ancestor.setParentItem(None)
        ancestor.deleteLater()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        factory.deleteLater()
        window.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
@pytest.mark.parametrize("rotation,scale", [
    (0.0, 1.0), (45.0, 1.0), (90.0, 1.0), (180.0, 1.0),
    (45.0, -1.0), (90.0, -1.0),
])
def test_selected_child_target_and_distinct_occupied_use_four_mapped_corners(
    qt_app, rotation: float, scale: float,
) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(
        owner=owner, screen_index=0, runtime_generation=1911,
    )
    root.setWidth(1000.0)
    root.setHeight(700.0)
    host = OrdinaryWidgetPresentationHost(
        host_item=_one(root, "ordinaryWidgetHost"),
        shadow_host_item=_one(root, "ordinaryWidgetShadowHost"),
        context=context, create_overlay_item=factory.create_overlay_widget,
        create_shadow_item=factory.create_overlay_card_shadow,
    )
    presentation = host.create_widget(
        object_name="friend_pulse", model_identity="friend_pulse",
        geometry=OverlayWidgetGeometry(100.0, 70.0, 600.0, 350.0),
    )
    ancestor = QQuickItem()
    ancestor.setParentItem(presentation.item)
    ancestor.setX(70.0)
    ancestor.setY(60.0)
    ancestor.setWidth(300.0)
    ancestor.setHeight(150.0)
    ancestor.setScale(1.3)
    target = QQuickItem()
    target.setParentItem(ancestor)
    target.setX(40.0)
    target.setY(22.0)
    target.setWidth(130.0)
    target.setHeight(16.0)
    target.setRotation(rotation)
    target.setScale(scale)
    occupied = QQuickItem()
    occupied.setParentItem(ancestor)
    occupied.setX(27.0)
    occupied.setY(12.0)
    occupied.setWidth(150.0)
    occupied.setHeight(35.0)
    occupied.setRotation(-27.0)
    assert presentation.item.setProperty("customEditableChildRoles", [{
        "roleId": "separator", "target": target, "occupiedTarget": occupied,
        "geometryDependencies": [ancestor],
        "normalizationWidth": 600.0, "normalizationHeight": 350.0,
        "allowParentGrowth": False,
    }])
    rect = QRect(100, 70, 600, 350)
    session = CustomLayoutSession()
    session.add_item(CustomLayoutSessionItem(
        source_key=CustomLayoutKey("friend_pulse", "display:mapped"),
        model_identity="friend_pulse", baseline_global_rect=rect,
        current_global_rect=rect, baseline_size_payload={}, current_size_payload={},
        baseline_enabled=True, current_enabled=True,
        custom_child_roles=(CustomChildRoleDescriptor(
            "separator", movable=True, uniform_scale=True,
        ),),
    ))
    edit_root = _one(root, "customLayoutOverlay")
    overlay = RetainedCustomLayoutOverlay(edit_root)
    try:
        overlay.bind_session(
            session, display_identity="display:mapped", display_origin=QPoint(0, 0),
            presentation_item_resolver=lambda _item: presentation.item,
        )
        assert overlay.model.selectItem(0)
        qt_app.processEvents()
        frame = _one(edit_root, "customLayoutEditFrame-friend_pulse")
        assert frame.setProperty("childEditingLocked", False)
        qt_app.processEvents()
        role = _one(edit_root, "customLayoutChildRole-friend_pulse-separator")
        assert role.property("targetReady") is True
        assert role.isVisible()
        _assert_bounds((role.x(), role.y(), role.width(), role.height()), target, frame)
        _assert_bounds(tuple(float(role.property(k)) for k in (
            "occupiedX", "occupiedY", "occupiedWidth", "occupiedHeight"
        )), occupied, frame)
        # The old single-number dependency summed every x/y/width/height.
        # Equal-and-opposite changes therefore suppressed its changed signal,
        # leaving the actual painted child ahead of the retained Edit proxy.
        for moving, first, second in (
            (ancestor, "x", "y"),
            (target, "x", "y"),
            (occupied, "x", "y"),
            (ancestor, "width", "height"),
        ):
            previous_signature = role.property("mappingDependency")
            previous_first = getattr(moving, first)()
            previous_second = getattr(moving, second)()
            getattr(moving, "set" + first.capitalize())(previous_first + 9.0)
            getattr(moving, "set" + second.capitalize())(previous_second - 9.0)
            qt_app.processEvents()
            assert role.property("mappingDependency") != previous_signature
            assert _one(edit_root, "customLayoutChildRole-friend_pulse-separator") is role
            _assert_bounds((role.x(), role.y(), role.width(), role.height()), target, frame)
            _assert_bounds(tuple(float(role.property(k)) for k in (
                "occupiedX", "occupiedY", "occupiedWidth", "occupiedHeight"
            )), occupied, frame)
        # A retained ancestor edit must remap without replacing the role model.
        ancestor.setRotation(33.0)
        ancestor.setX(83.0)
        qt_app.processEvents()
        assert _one(edit_root, "customLayoutChildRole-friend_pulse-separator") is role
        _assert_bounds((role.x(), role.y(), role.width(), role.height()), target, frame)
        _assert_bounds(tuple(float(role.property(k)) for k in (
            "occupiedX", "occupiedY", "occupiedWidth", "occupiedHeight"
        )), occupied, frame)
    finally:
        overlay.clear_session()
        host.retire_all()
        for item in (target, occupied, ancestor):
            item.setParentItem(None)
            item.deleteLater()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        factory.deleteLater()
        owner.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_thin_positive_stroke_is_editable_but_hidden_or_zero_stroke_is_not(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(
        owner=owner, screen_index=0, runtime_generation=1912,
    )
    root.setWidth(900.0)
    root.setHeight(550.0)
    host = OrdinaryWidgetPresentationHost(
        host_item=_one(root, "ordinaryWidgetHost"),
        shadow_host_item=_one(root, "ordinaryWidgetShadowHost"),
        context=context, create_overlay_item=factory.create_overlay_widget,
        create_shadow_item=factory.create_overlay_card_shadow,
    )
    presentation = host.create_widget(
        object_name="friend_pulse", model_identity="friend_pulse",
        geometry=OverlayWidgetGeometry(80.0, 50.0, 550.0, 330.0),
    )
    target = QQuickItem()
    target.setParentItem(presentation.item)
    target.setX(35.0)
    target.setY(120.0)
    target.setWidth(450.0)
    target.setHeight(0.38)  # The old >1.0 *local* gate rejected this.
    target.setScale(4.0)
    assert presentation.item.setProperty("customEditableChildRoles", [{
        "roleId": "separator", "target": target,
        "normalizationWidth": 550.0, "normalizationHeight": 330.0,
        "allowParentGrowth": False,
    }])
    rect = QRect(80, 50, 550, 330)
    session = CustomLayoutSession()
    session.add_item(CustomLayoutSessionItem(
        source_key=CustomLayoutKey("friend_pulse", "display:thin"),
        model_identity="friend_pulse", baseline_global_rect=rect,
        current_global_rect=rect, baseline_size_payload={}, current_size_payload={},
        baseline_enabled=True, current_enabled=True,
        custom_child_roles=(CustomChildRoleDescriptor(
            "separator", movable=True, uniform_scale=True,
        ),),
    ))
    edit_root = _one(root, "customLayoutOverlay")
    overlay = RetainedCustomLayoutOverlay(edit_root)
    try:
        overlay.bind_session(
            session, display_identity="display:thin", display_origin=QPoint(0, 0),
            presentation_item_resolver=lambda _item: presentation.item,
        )
        assert overlay.model.selectItem(0)
        qt_app.processEvents()
        frame = _one(edit_root, "customLayoutEditFrame-friend_pulse")
        assert frame.setProperty("childEditingLocked", False)
        qt_app.processEvents()
        role = _one(edit_root, "customLayoutChildRole-friend_pulse-separator")
        assert role.property("targetReady") is True
        assert role.isVisible()
        _assert_bounds((role.x(), role.y(), role.width(), role.height()), target, frame)
        target.setScale(-4.0)
        qt_app.processEvents()
        assert role.property("targetReady") is True
        _assert_bounds((role.x(), role.y(), role.width(), role.height()), target, frame)
        target.setHeight(0.0)
        qt_app.processEvents()
        assert role.property("targetReady") is False
        assert role.isVisible() is False
        target.setHeight(0.38)
        target.setVisible(False)
        qt_app.processEvents()
        assert role.property("targetReady") is False
        target.setVisible(True)
        qt_app.processEvents()
        assert role.property("targetReady") is True
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
