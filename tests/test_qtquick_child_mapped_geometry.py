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


def _assert_axis_aligned_clipped_bounds(
    actual, item: QQuickItem, clip_item: QQuickItem, frame: QQuickItem,
) -> None:
    """Independent paint oracle for this fixture's axis-aligned clip space.

    A clip changes *visible* paint bounds: using the item's four full corners
    after narrowing its ancestor would falsely expect the invisible portion.
    The fixture has positive, axis-aligned Scale/Translate transforms; reject
    rotation/shear here rather than silently using a wrong bounding-box clip
    oracle for some future, non-axis-aligned scene.
    """
    assert clip_item.clip() is True
    corners = _mapped_corners(item, clip_item)
    assert corners[0].y() == pytest.approx(corners[1].y(), abs=0.02)
    assert corners[2].y() == pytest.approx(corners[3].y(), abs=0.02)
    assert corners[0].x() == pytest.approx(corners[2].x(), abs=0.02)
    assert corners[1].x() == pytest.approx(corners[3].x(), abs=0.02)
    x0 = max(0.0, min(point.x() for point in corners))
    y0 = max(0.0, min(point.y() for point in corners))
    x1 = min(clip_item.width(), max(point.x() for point in corners))
    y1 = min(clip_item.height(), max(point.y() for point in corners))
    assert x1 > x0 and y1 > y0  # The fixture expects partially visible paint.
    top_left = clip_item.mapToItem(frame, x0, y0)
    bottom_right = clip_item.mapToItem(frame, x1, y1)
    assert actual == pytest.approx((
        top_left.x(), top_left.y(),
        bottom_right.x() - top_left.x(),
        bottom_right.y() - top_left.y(),
    ), abs=0.02)


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

@pytest.mark.qt
def test_selected_mapper_tracks_nested_qml_scale_translate_clips_and_role_readiness(
    qt_app,
) -> None:
    """Retained QML transforms use explicit bindable source dependencies.

    Test genuine QML Scale/Translate objects (not only QQuickItem.setScale),
    inherited uniform-like scaling, clipped paint and a role that disappears
    visually then returns without its selected Edit delegate being destroyed.
    """
    from PySide6.QtCore import QUrl, qInstallMessageHandler
    from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression

    window = QQuickWindow()
    window.setGeometry(0, 0, 1000, 700)
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(
        owner=window, screen_index=0, runtime_generation=1936,
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
    component = QQmlComponent(context.engine(), window)
    component.setData(b'''import QtQuick
        Item {
            id: probe
            property alias paintedTarget: painted
            property alias clipTarget: clippingParent
            // Mutate actual retained QML transforms inside QML. Exposing a
            // QQuickTranslate* to Python's QObject.property requires a PySide
            // converter that does not exist; that is a fixture API error.
            function setAppliedTranslationX(ancestor, value) {
                if (ancestor)
                    outerTranslation.x = value
                else
                    innerTranslation.x = value
                return ancestor ? outerTranslation.x : innerTranslation.x
            }
            property real dx: 0.0
            property real dy: 0.0
            property real sx: 1.0
            property real sy: 1.0
            property real localScaleX: 1.0
            property real localOffsetX: 0.0
            property bool useClip: false
            property bool ready: true
            width: 340; height: 220
            Item {
                id: clippingParent
                x: 30; y: 44; width: 210; height: 130
                visible: probe.ready
                clip: probe.useClip
                // Read the APPLIED transform object values, not their source
                // inputs: probe.dx can notify before Translate.x has updated.
                readonly property string customEditMappingDependency: [
                    outerScale.xScale, outerScale.yScale,
                    outerTranslation.x, outerTranslation.y
                ].join("|")
                transform: [
                    Scale { id: outerScale; origin.x: 0; origin.y: 0;
                        xScale: probe.sx; yScale: probe.sy },
                    Translate { id: outerTranslation; x: probe.dx; y: probe.dy }
                ]
                Item {
                    id: painted
                    x: 145; y: 30; width: 110; height: 50
                    readonly property string customEditMappingDependency: [
                        innerScale.xScale, innerScale.yScale,
                        innerTranslation.x, innerTranslation.y
                    ].join("|")
                    transform: [
                        Scale { id: innerScale; origin.x: 0; origin.y: 0;
                            xScale: probe.localScaleX; yScale: 1.0 },
                        Translate { id: innerTranslation;
                            x: probe.localOffsetX; y: 0.0 }
                    ]
                }
            }
        }
    ''', QUrl())
    assert component.status() == QQmlComponent.Status.Ready, component.errors()
    probe = component.create(context)
    assert isinstance(probe, QQuickItem), component.errors()
    QQmlEngine.setObjectOwnership(probe, QQmlEngine.ObjectOwnership.CppOwnership)
    probe.setParent(presentation.item)
    probe.setParentItem(presentation.item)
    painted = probe.property("paintedTarget")
    clipping_parent = probe.property("clipTarget")
    assert isinstance(painted, QQuickItem)
    assert isinstance(clipping_parent, QQuickItem)
    assert presentation.item.setProperty("customEditableChildRoles", [{
        "roleId": "header", "target": painted,
        # No family-specific geometryDependencies needed. Both transformed
        # ancestors publish their existing bindable inputs, never transform[].
        "normalizationWidth": 620.0, "normalizationHeight": 380.0,
    }])
    rect = QRect(90, 65, 620, 380)
    session = CustomLayoutSession()
    session.add_item(CustomLayoutSessionItem(
        source_key=CustomLayoutKey("friend_pulse", "display:transform-chain"),
        model_identity="friend_pulse", baseline_global_rect=rect,
        current_global_rect=rect, baseline_size_payload={}, current_size_payload={},
        baseline_enabled=True, current_enabled=True,
        custom_child_roles=(CustomChildRoleDescriptor("header", movable=True),),
    ))
    edit_root = _one(root, "customLayoutOverlay")
    overlay = RetainedCustomLayoutOverlay(edit_root)
    role_name = "customLayoutChildRole-friend_pulse-header"
    qml_messages: list[str] = []

    def collect_qml(_level, _context, message):
        qml_messages.append(str(message))

    previous_qt_handler = qInstallMessageHandler(collect_qml)
    try:
        overlay.bind_session(
            session, display_identity="display:transform-chain",
            display_origin=QPoint(0, 0),
            presentation_item_resolver=lambda _item: presentation.item,
        )
        window.show()
        assert overlay.model.selectItem(0)
        qt_app.processEvents()
        frame = _one(edit_root, "customLayoutEditFrame-friend_pulse")
        assert frame.setProperty("childEditingLocked", False)
        qt_app.processEvents()
        role = _one(edit_root, role_name)
        assert role.property("targetReady") is True
        assert role.property("targetItem") == painted
        _assert_bounds((role.x(), role.y(), role.width(), role.height()), painted, frame)
        for property_name, value in (
            ("dx", 32.0), ("dy", -19.0),
            ("sx", 1.24), ("sy", 0.81),
            ("localOffsetX", -9.0), ("localScaleX", 1.13),
        ):
            before = role.property("mappingDependency")
            assert probe.setProperty(property_name, value)
            qt_app.processEvents()
            assert role.property("mappingDependency") != before, property_name
            assert _one(edit_root, role_name) == role
            _assert_bounds((role.x(), role.y(), role.width(), role.height()), painted, frame)

        # A parent's presentation state hides the target, never its role ID.
        assert probe.setProperty("ready", False)
        qt_app.processEvents()
        assert _one(edit_root, role_name) == role
        assert role.property("targetReady") is False
        assert not role.isVisible()
        assert probe.setProperty("ready", True)
        qt_app.processEvents()
        assert _one(edit_root, role_name) == role
        assert role.property("targetReady") is True
        _assert_bounds((role.x(), role.y(), role.width(), role.height()), painted, frame)

        # Clip in parent LOCAL space, then project the clipped paint rectangle.
        # Use a nonrotated positive scale so this independent expected box is
        # directly available from the two clipped local corners.
        assert probe.setProperty("localScaleX", 1.0)
        assert probe.setProperty("localOffsetX", 0.0)
        assert probe.setProperty("useClip", True)
        qt_app.processEvents()
        top_left = clipping_parent.mapToItem(frame, 145.0, 30.0)
        bottom_right = clipping_parent.mapToItem(frame, 210.0, 80.0)
        assert (role.x(), role.y(), role.width(), role.height()) == pytest.approx(
            (top_left.x(), top_left.y(), bottom_right.x() - top_left.x(),
             bottom_right.y() - top_left.y()), abs=0.02,
        )
        before = role.property("mappingDependency")
        clipping_parent.setWidth(175.0)
        qt_app.processEvents()
        assert role.property("mappingDependency") != before
        assert _one(edit_root, role_name) == role
        top_left = clipping_parent.mapToItem(frame, 145.0, 30.0)
        bottom_right = clipping_parent.mapToItem(frame, 175.0, 80.0)
        assert (role.x(), role.y(), role.width(), role.height()) == pytest.approx(
            (top_left.x(), top_left.y(), bottom_right.x() - top_left.x(),
             bottom_right.y() - top_left.y()), abs=0.02,
        )
        # The parent's clip is STILL ENABLED and narrowed to 175px. Exercise
        # repeated transforms against the actual *clipped* painted footprint;
        # the full-item four-corner oracle would incorrectly expect the hidden
        # 80px of the 110px child to remain inside its Edit rectangle.
        assert clipping_parent.clip() is True
        for i in range(24):
            assert probe.setProperty("dx", float(i % 7))
            assert probe.setProperty("dy", float(-(i % 5)))
            qt_app.processEvents()
            assert _one(edit_root, role_name) is role
            assert role.property("targetItem") == painted
            assert role.property("targetReady") is True
            _assert_axis_aligned_clipped_bounds(
                (role.x(), role.y(), role.width(), role.height()),
                painted, clipping_parent, frame,
            )
        # A direct change to a retained QML transform must also invalidate the
        # *clipped* rectangle, even when its model/source input does not change.
        def apply_qml_translation(ancestor: bool, value: float) -> None:
            # Execute on the retained QML object; never marshal QQuickTranslate*
            # through an unsupported Python wrapper, and never mutate probe.dx.
            call = QQmlExpression(
                context, probe,
                f"setAppliedTranslationX({'true' if ancestor else 'false'}, {value!r})",
            )
            result = call.evaluate()
            assert not call.hasError(), call.error()
            # PySide6 returns (value, isUndefined) on supported Qt builds.
            # Unlike the earlier QQuickTranslate* wrapper failure, this is a
            # supported primitive result; reject an undefined evaluation.
            if isinstance(result, tuple):
                assert len(result) == 2 and result[1] is False, result
                applied = result[0]
            else:
                applied = result
            assert applied == pytest.approx(value)

        before = role.property("mappingDependency")
        apply_qml_translation(False, -17.0)
        qt_app.processEvents()
        assert role.property("mappingDependency") != before
        assert _one(edit_root, role_name) is role
        _assert_axis_aligned_clipped_bounds(
            (role.x(), role.y(), role.width(), role.height()),
            painted, clipping_parent, frame,
        )
        # Clipping had deliberately shrunk the previous proxy; turn it off so
        # the independent four-corner oracle can compare the full painted quad.
        assert probe.setProperty("useClip", False)
        qt_app.processEvents()
        assert clipping_parent.clip() is False
        assert _one(edit_root, role_name) is role
        assert role.property("targetReady") is True
        _assert_bounds((role.x(), role.y(), role.width(), role.height()), painted, frame)
        # Also mutate an actual QML transform object, without changing a
        # model/source input.  Invalidation must follow paint, not probe.dx.
        for ancestor, x_value in ((True, 15.0), (False, -9.0)):
            before = role.property("mappingDependency")
            apply_qml_translation(ancestor, x_value)
            qt_app.processEvents()
            assert role.property("mappingDependency") != before
            assert _one(edit_root, role_name) == role
            _assert_bounds((role.x(), role.y(), role.width(), role.height()), painted, frame)

        assert not [message for message in qml_messages
                    if "CustomLayoutOverlay.qml" in message
                    and ("non-bindable" in message or "Binding loop" in message)], (
            qml_messages[:5], len(qml_messages)
        )
    finally:
        qInstallMessageHandler(previous_qt_handler)
        overlay.clear_session()
        window.hide()
        probe.setParentItem(None)
        probe.setParent(None)
        probe.deleteLater()
        host.retire_all()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        factory.deleteLater()
        window.deleteLater()
        qt_app.processEvents()

@pytest.mark.qt
def test_selected_roles_retain_identity_when_live_normalization_baselines_change(qt_app) -> None:
    """Live card/accessory normalization is delegate data, never a Repeater model.

    This scene uses three semantic roles against the same retained family object:
    one normal card role, one external accessory with a different X baseline,
    and a dense authored-family role with both named baseAuthored axes.
    Neither a dynamic size change nor a partial hide/show may retire the roles.
    No Settings, timers, recurring scene scans or production probes are needed.
    """
    from PySide6.QtCore import QUrl, qInstallMessageHandler
    from PySide6.QtQml import QQmlComponent, QQmlEngine

    window = QQuickWindow()
    window.setGeometry(0, 0, 1000, 700)
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(
        owner=window, screen_index=0, runtime_generation=1940,
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
        geometry=OverlayWidgetGeometry(80.0, 60.0, 640.0, 340.0),
    )
    component = QQmlComponent(context.engine(), window)
    component.setData(b'''import QtQuick
        Item {
            id: probe
            property real childNormalizationWidth: 540.0
            property real childNormalizationHeight: 280.0
            property real volumeChildNormalizationWidth: 588.0
            property real baseAuthoredWidth: 510.0
            property real baseAuthoredHeight: 250.0
            property alias densePaint: dense
            property alias cardPaint: card
            property alias accessoryPaint: accessory
            width: 620; height: 320
            Item { id: card; x: 20; y: 30; width: 150; height: 54 }
            Item { id: accessory; x: 420; y: 70; width: 84; height: 25 }
            Item { id: dense; x: 210; y: 140; width: 90; height: 36 }
        }
    ''', QUrl())
    assert component.status() == QQmlComponent.Status.Ready, component.errors()
    probe = component.create(context)
    assert isinstance(probe, QQuickItem), component.errors()
    QQmlEngine.setObjectOwnership(probe, QQmlEngine.ObjectOwnership.CppOwnership)
    probe.setParent(presentation.item)
    probe.setParentItem(presentation.item)
    card = probe.property("cardPaint")
    accessory = probe.property("accessoryPaint")
    dense = probe.property("densePaint")
    assert all(isinstance(item, QQuickItem) for item in (card, accessory, dense))
    assert presentation.item.setProperty("customEditableChildRoles", [
        {"roleId": "header", "target": card, "normalizationTarget": probe},
        {"roleId": "avatars", "target": accessory,
         "normalizationTarget": probe,
         "normalizationWidthProperty": "volumeChildNormalizationWidth"},
        {"roleId": "usernames", "target": dense, "normalizationTarget": probe,
         "normalizationWidthProperty": "baseAuthoredWidth",
         "normalizationHeightProperty": "baseAuthoredHeight"},
    ])
    rect = QRect(80, 60, 640, 340)
    session = CustomLayoutSession()
    session.add_item(CustomLayoutSessionItem(
        source_key=CustomLayoutKey("friend_pulse", "display:live-norm"),
        model_identity="friend_pulse", baseline_global_rect=rect,
        current_global_rect=rect, baseline_size_payload={}, current_size_payload={},
        baseline_enabled=True, current_enabled=True,
        custom_child_roles=(
            CustomChildRoleDescriptor("header", movable=True),
            CustomChildRoleDescriptor("avatars", movable=True),
            CustomChildRoleDescriptor("usernames", movable=True),
        ),
    ))
    edit_root = _one(root, "customLayoutOverlay")
    overlay = RetainedCustomLayoutOverlay(edit_root)
    qml_messages: list[str] = []

    def collect_qml(_level, _context, message):
        qml_messages.append(str(message))

    previous_handler = qInstallMessageHandler(collect_qml)
    try:
        overlay.bind_session(
            session, display_identity="display:live-norm",
            display_origin=QPoint(0, 0),
            presentation_item_resolver=lambda _item: presentation.item,
        )
        window.show()
        assert overlay.model.selectItem(0)
        qt_app.processEvents()
        frame = _one(edit_root, "customLayoutEditFrame-friend_pulse")
        assert frame.setProperty("childEditingLocked", False)
        qt_app.processEvents()
        card_role = _one(edit_root, "customLayoutChildRole-friend_pulse-header")
        accessory_role = _one(edit_root, "customLayoutChildRole-friend_pulse-avatars")
        dense_role = _one(edit_root, "customLayoutChildRole-friend_pulse-usernames")
        assert card_role.property("targetItem") == card
        assert accessory_role.property("targetItem") == accessory
        assert dense_role.property("targetItem") == dense
        for i in range(20):
            # Independent, changing normalization baselines, but no edit-role
            # model publication. This is the lifecycle/perf invariant.
            width = 540.0 + 4.0 * i
            height = 280.0 + 2.0 * i
            accessory_width = width + (48.0 if i % 2 else 0.0)
            assert probe.setProperty("childNormalizationWidth", width)
            assert probe.setProperty("childNormalizationHeight", height)
            assert probe.setProperty("volumeChildNormalizationWidth", accessory_width)
            assert probe.setProperty("baseAuthoredWidth", 510.0 + 3.0 * i)
            assert probe.setProperty("baseAuthoredHeight", 250.0 + 5.0 * i)
            qt_app.processEvents()
            assert _one(edit_root, "customLayoutChildRole-friend_pulse-header") is card_role
            assert _one(edit_root, "customLayoutChildRole-friend_pulse-avatars") is accessory_role
            assert _one(edit_root, "customLayoutChildRole-friend_pulse-usernames") is dense_role
            assert card_role.property("normalizationWidth") == pytest.approx(width)
            assert card_role.property("normalizationHeight") == pytest.approx(height)
            assert accessory_role.property("normalizationWidth") == pytest.approx(accessory_width)
            assert accessory_role.property("normalizationHeight") == pytest.approx(height)
            assert dense_role.property("normalizationWidth") == pytest.approx(510.0 + 3.0 * i)
            assert dense_role.property("normalizationHeight") == pytest.approx(250.0 + 5.0 * i)
            _assert_bounds((card_role.x(), card_role.y(), card_role.width(), card_role.height()), card, frame)
            _assert_bounds((accessory_role.x(), accessory_role.y(), accessory_role.width(), accessory_role.height()), accessory, frame)
            _assert_bounds((dense_role.x(), dense_role.y(), dense_role.width(), dense_role.height()), dense, frame)
        accessory.setVisible(False)
        qt_app.processEvents()
        assert _one(edit_root, "customLayoutChildRole-friend_pulse-avatars") is accessory_role
        assert accessory_role.property("targetReady") is False
        accessory.setVisible(True)
        qt_app.processEvents()
        assert accessory_role.property("targetReady") is True
        assert _one(edit_root, "customLayoutChildRole-friend_pulse-avatars") is accessory_role
        assert not [message for message in qml_messages if (
            "Unable to assign" in message or "non-bindable" in message
            or "ReferenceError" in message or "TypeError" in message
        )], qml_messages[:12]
        overlay.clear_session()
        qt_app.processEvents()
        assert not any(item.objectName().startswith("customLayoutChildRole-friend_pulse-")
                       for item in _walk(edit_root))
    finally:
        qInstallMessageHandler(previous_handler)
        overlay.clear_session()
        window.hide()
        # The probe is owned by the retained presentation in the Qt scene.
        # Unparent it before the host retires that presentation; dereferencing
        # the old Python wrapper afterwards is a use-after-destruction in the
        # test teardown, not a selected Edit delegate-lifetime failure.
        probe.setParentItem(None)
        probe.setParent(None)
        host.retire_all()
        probe.deleteLater()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        factory.deleteLater()
        window.deleteLater()
        qt_app.processEvents()

@pytest.mark.qt
def test_child_snap_guides_retain_one_item_per_axis_during_repeated_pointer_samples(
    qt_app,
) -> None:
    """Same-position and changing-position snaps must not recreate guide QQuickItems.

    This is a real selected Edit scene, not a string-only test. The guide
    samples are injected at the shared event-owned snap publisher so it checks
    its item lifetime and coordinates without synthesizing a fragile screen
    pointer path through per-family collision geometry.
    """
    from PySide6.QtQml import QQmlExpression

    owner = QObject()
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(
        owner=owner, screen_index=0, runtime_generation=1981,
    )
    root.setWidth(850.0)
    root.setHeight(580.0)
    host = OrdinaryWidgetPresentationHost(
        host_item=_one(root, "ordinaryWidgetHost"),
        shadow_host_item=_one(root, "ordinaryWidgetShadowHost"),
        context=context, create_overlay_item=factory.create_overlay_widget,
        create_shadow_item=factory.create_overlay_card_shadow,
    )
    presentation = host.create_widget(
        object_name="friend_pulse", model_identity="friend_pulse",
        geometry=OverlayWidgetGeometry(40.0, 35.0, 520.0, 310.0),
    )
    target = QQuickItem()
    target.setParentItem(presentation.item)
    target.setX(60.0)
    target.setY(40.0)
    target.setWidth(120.0)
    target.setHeight(60.0)
    assert presentation.item.setProperty("customEditableChildRoles", [{
        "roleId": "header", "target": target,
        "normalizationWidth": 520.0, "normalizationHeight": 310.0,
    }])
    rect = QRect(40, 35, 520, 310)
    session = CustomLayoutSession()
    session.add_item(CustomLayoutSessionItem(
        source_key=CustomLayoutKey("friend_pulse", "display:retained-guides"),
        model_identity="friend_pulse", baseline_global_rect=rect,
        current_global_rect=rect, baseline_size_payload={},
        current_size_payload={}, baseline_enabled=True, current_enabled=True,
        custom_child_roles=(CustomChildRoleDescriptor("header", movable=True),),
    ))
    edit_root = _one(root, "customLayoutOverlay")
    overlay = RetainedCustomLayoutOverlay(edit_root)
    try:
        overlay.bind_session(
            session, display_identity="display:retained-guides",
            display_origin=QPoint(0, 0),
            presentation_item_resolver=lambda _item: presentation.item,
        )
        assert overlay.model.selectItem(0)
        qt_app.processEvents()
        frame = _one(edit_root, "customLayoutEditFrame-friend_pulse")
        assert frame.setProperty("childEditingLocked", False)
        qt_app.processEvents()
        layer = _one(edit_root, "customLayoutChildRoleLayer-friend_pulse")
        vertical = _one(edit_root, "customLayoutChildVerticalGuide")
        horizontal = _one(edit_root, "customLayoutChildHorizontalGuide")
        role = _one(edit_root, "customLayoutChildRole-friend_pulse-header")
        assert not vertical.isVisible() and not horizontal.isVisible()

        def guide(horizontal_axis: bool, position: float | None, kind: str) -> None:
            point = "null" if position is None else repr(float(position))
            expression = QQmlExpression(
                context, layer,
                f"publishChildGuide({'true' if horizontal_axis else 'false'}, "
                f"{point}, {kind!r})",
            )
            expression.evaluate()
            assert not expression.hasError(), expression.error()
            qt_app.processEvents()

        # The first acquisition, 24 steady snap samples, movement to another
        # line, semantic styling, and a hide/reacquire must all use these two
        # exact retained items. The visible guides still track current points.
        for position, kind in ((92.0, "sibling-center"),
                               (121.0, "semantic-margin-start")):
            for _ in range(24):
                guide(False, position, kind)
                guide(True, position + 13.0, kind)
                assert _one(edit_root, "customLayoutChildVerticalGuide") is vertical
                assert _one(edit_root, "customLayoutChildHorizontalGuide") is horizontal
                assert _one(edit_root, "customLayoutChildRole-friend_pulse-header") is role
                assert vertical.isVisible() and horizontal.isVisible()
                assert vertical.x() == pytest.approx(position)
                assert horizontal.y() == pytest.approx(position + 13.0)
                assert vertical.width() == (3.0 if kind.startswith("semantic-") else 2.0)
        guide(False, None, "")
        guide(True, None, "")
        assert not vertical.isVisible() and not horizontal.isVisible()
        guide(False, 63.0, "parent-center")
        assert _one(edit_root, "customLayoutChildVerticalGuide") is vertical
        assert vertical.isVisible() and vertical.x() == pytest.approx(63.0)
        assert horizontal.isVisible() is False
        assert _one(edit_root, "customLayoutChildRole-friend_pulse-header") is role
    finally:
        overlay.clear_session()
        host.retire_all()
        target.setParentItem(None)
        target.deleteLater()
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        factory.deleteLater()
        owner.deleteLater()
        qt_app.processEvents()
