"""Native Qt regression: R39 normal-hover lock must unlock the child Edit layer.

Test the actual retained CUSTOM model and QML Repeater, with no live app, builds,
new timers or test environment variables. Unlike a source assertion, the model
signal must cause a real QQuickItem's childEditingLocked to change.
"""
import pytest
from PySide6.QtCore import QObject, QPoint, QRect
from PySide6.QtQuick import QQuickItem

from rendering.custom_layout_session import CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem
from rendering.quick.custom_layout_overlay import RetainedCustomLayoutOverlay
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.widgets.host import OrdinaryWidgetPresentationHost, OverlayWidgetGeometry


def walk(item):
    for child in item.childItems():
        yield child
        yield from walk(child)


def frame_for(root, widget_id):
    matches = [item for item in walk(root) if item.objectName() == f'customLayoutEditFrame-{widget_id}']
    assert len(matches) == 1, len(matches)
    return matches[0]


@pytest.mark.qt
def test_immediate_post_bind_lock_click_enters_child_edit_and_new_session_resets(qt_app):
    owner = QObject()
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(owner=owner, screen_index=0, runtime_generation=1400)
    root.setWidth(960.0)
    root.setHeight(720.0)
    host = OrdinaryWidgetPresentationHost(
        host_item=root.findChild(QQuickItem, 'ordinaryWidgetHost'),
        shadow_host_item=root.findChild(QQuickItem, 'ordinaryWidgetShadowHost'),
        context=context, create_overlay_item=factory.create_overlay_widget,
        create_shadow_item=factory.create_overlay_card_shadow,
    )
    presentation = host.create_widget(
        object_name='clock', model_identity='clock',
        geometry=OverlayWidgetGeometry(80.0, 80.0, 360.0, 240.0),
    )
    child = QQuickItem()
    child.setParentItem(presentation.item)
    child.setWidth(100.0)
    child.setHeight(24.0)
    assert presentation.item.setProperty('customEditableChildRoles', [{
        'roleId': 'time_text', 'target': child,
        'normalizationWidth': 360.0, 'normalizationHeight': 240.0,
        'allowParentGrowth': False,
    }])
    edit_root = root.findChild(QQuickItem, 'customLayoutOverlay')
    overlay = RetainedCustomLayoutOverlay(edit_root)
    try:
        for attempt in range(2):
            session = CustomLayoutSession()
            rect = QRect(80, 80, 360, 240)
            session.add_item(CustomLayoutSessionItem(
                source_key=CustomLayoutKey('clock', 'display:r40'), model_identity='clock',
                baseline_global_rect=rect, current_global_rect=rect,
                baseline_size_payload={}, current_size_payload={},
                baseline_enabled=True, current_enabled=True, is_duplicate=False,
                resize_capable=True, size_reset_capable=True,
            ))
            model = overlay.bind_session(
                session, display_identity='display:r40', display_origin=QPoint(0, 0),
                presentation_item_resolver=lambda _item: presentation.item,
            )
            assert model.selectItem(0)
            # Exactly the model method invoked by normal-mode Lock handoff,
            # deliberately BEFORE processEvents delegates have caught up.
            model.requestToggleChildEditLockForWidget('clock')
            qt_app.processEvents()
            frame = frame_for(edit_root, 'clock')
            assert frame.property('childEditingLocked') is False, f'failed on session {attempt}'
            model.requestToggleChildEditLockForWidget('clock')
            qt_app.processEvents()
            assert frame.property('childEditingLocked') is True
            overlay.clear_session()
            qt_app.processEvents()
    finally:
        overlay.clear_session()
        host.retire_all()
        child.setParentItem(None)
        child.deleteLater()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        factory.deleteLater()
        owner.deleteLater()
        qt_app.processEvents()
