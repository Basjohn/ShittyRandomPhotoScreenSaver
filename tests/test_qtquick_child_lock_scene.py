"""Rendered Qt gate for lock position, child hitbox isolation and parent chrome.

No production timer/service/Settings dependency; the existing session owns geometry.
This supplements the nine-family scene tests, not a claim of human visual acceptance.

The exposure gates at the end run real Clock and Media families in the production
``DisplayScene.qml`` + ``QuickSceneController`` inside the hidden ``QQuickRenderControl``
host (polished and rendered, never shown), with real pointer events through its window.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from PySide6.QtCore import QElapsedTimer, QEvent, QObject, QPoint, QPointF, QRect, Qt
from PySide6.QtQuick import QQuickItem

from rendering.custom_layout_session import CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.custom_layout_overlay import RetainedCustomLayoutOverlay
from rendering.quick.widgets.host import OrdinaryWidgetPresentationHost, OverlayWidgetGeometry


def _pump_until(qt_app, done, timeout_ms: int = 3000) -> None:
    clock = QElapsedTimer()
    clock.start()
    while not done():
        qt_app.processEvents()
        assert clock.elapsed() < timeout_ms, "the edit chrome did not settle before the deadline"


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
        # This detached scene has no pointer/window. Scope the geometry test to
        # revealed chrome; actual hover and pointer delivery have native gates.
        assert frame.property('parentGlyphControlsOpacity') == 0.
        frame.setProperty('parentGlyphControlsOpacity', 1.)
        from PySide6.QtCore import QEventLoop, QTimer
        loop = QEventLoop()
        QTimer.singleShot(1300, loop.quit)
        loop.exec()
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
        # Locking drops child input at once and fades the paint out (never vanishes).
        assert role_layer.isEnabled() is False
        _pump_until(qt_app, lambda: not role_layer.isVisible())

        # Unlock only the edit chrome; keep the existing observer and model.
        assert frame.setProperty("childEditingLocked", False)
        qt_app.processEvents()
        assert role_layer.isVisible() is True and role_frame.isVisible() is True
        assert one("customLayoutChildRoleLayer-clock") is role_layer
        assert target.isVisible() is True
        assert frame.setProperty("childEditingLocked", True)
        qt_app.processEvents()
        _pump_until(qt_app, lambda: not role_layer.isVisible())
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


# ---------------------------------------------------------------------------------------------------
# Opening the lock exposes the children. Operator, 8 Nov: "clicking the child lock open does not
# expose the child widgets. You have to edit/move/adjust the parent widget afterwards until they
# are exposed." Only the selected parent loads its child layer, while the Edit frame's lock glyph is
# hover-revealed on every child-capable frame; its click must focus that parent itself.

WIDTH, HEIGHT = 1280, 720
DISPLAY = "display:lock-exposure"
RECTS = {"clock": QRect(60, 60, 420, 260), "media": QRect(560, 360, 650, 300)}  # display-local


@pytest.fixture
def display(qt_app):
    if qt_app.platformName().strip().lower() != "windows":
        pytest.skip("the hidden production scene needs the Windows QPA GL")
    from tools.expanded_visualizer_evidence import HiddenDisplayHost

    host = HiddenDisplayHost(WIDTH, HEIGHT, dpr=1.0)
    try:
        yield host
    finally:
        try:
            host.scene.clear_custom_layout_session()
        except RuntimeError:
            pass
        host.close()


def _run(display, ms: int) -> None:
    clock = QElapsedTimer()
    clock.start()
    while clock.elapsed() < ms:
        display.render()


def _settle(display, done, timeout_ms: int = 4000) -> None:
    clock = QElapsedTimer()
    clock.start()
    while not done():
        display.render()
        assert clock.elapsed() < timeout_ms, "the edit layer did not settle before the deadline"


def _visual_items(item) -> list:
    found, queue = [], list(item.childItems())
    while queue:
        child = queue.pop()
        found.append(child)
        queue.extend(child.childItems())
    return found


def _edit_item(display, name: str):
    layer = display.scene.custom_layout_overlay.item
    return next((item for item in _visual_items(layer) if item.objectName() == name), None)


def _send(display, kind, point: QPointF, button, buttons) -> None:
    """One real pointer event through the hidden scene's window (no render: the caller decides)."""
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QMouseEvent

    QCoreApplication.sendEvent(display.window, QMouseEvent(
        kind, point, point, point, button, buttons, Qt.KeyboardModifier.NoModifier))


def _centre(item) -> QPointF:
    return item.mapToScene(QPointF(item.width() / 2.0, item.height() / 2.0))


def _click_lock(display, lock) -> None:
    point = _centre(lock)
    left, none = Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton
    _send(display, QEvent.Type.MouseMove, point, none, none)
    _send(display, QEvent.Type.MouseButtonPress, point, left, left)
    _send(display, QEvent.Type.MouseButtonRelease, point, left, none)


def _families(display) -> dict:
    """Real Clock and Media families on the production scene's ordinary-widget host."""
    from rendering.quick.widgets.clock import RetainedClockPresentation
    from rendering.quick.widgets.host import OverlayWidgetGeometry
    from rendering.quick.widgets.media import RetainedMediaPresentation
    from tests.test_qtquick_clock_presentation import _FakeTicker, _clock_config
    from tests.test_qtquick_clock_presentation import _model as _clock_model
    from tests.test_qtquick_media_presentation import (
        _FakeMediaRuntime, _FakeMediaVolumeRuntime, _image, _snapshot)
    from tests.test_qtquick_media_presentation import _model as _media_model

    def geometry(rect: QRect) -> OverlayWidgetGeometry:
        return OverlayWidgetGeometry(float(rect.x()), float(rect.y()), float(rect.width()), float(rect.height()))

    host = display.scene.ordinary_widget_host
    clock = RetainedClockPresentation(
        host=host, model=_clock_model([datetime(2026, 8, 25, 13, 24, 30)], _FakeTicker(), config=_clock_config()),
        geometry=geometry(RECTS["clock"]), display_bounds=OverlayWidgetGeometry(0.0, 0.0, WIDTH, HEIGHT),
        display_identity=DISPLAY)
    clock.activate(object())
    runtime = _FakeMediaRuntime()
    media_model, _, _ = _media_model(display.factory.media_artwork_provider, runtime, _FakeMediaVolumeRuntime())
    media = RetainedMediaPresentation(host=host, model=media_model, geometry=geometry(RECTS["media"]))
    media.activate(object())
    runtime.publish(_snapshot(1, image=_image()))
    _run(display, 200)
    return {"clock": clock, "media": media}


def _session():
    from rendering.custom_layout_session import CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem
    from rendering.widget_descriptors import get_widget_runtime_descriptor

    session = CustomLayoutSession()
    for family, rect in RECTS.items():
        session.add_item(CustomLayoutSessionItem(
            source_key=CustomLayoutKey(family, DISPLAY), model_identity=family,
            baseline_global_rect=rect, current_global_rect=rect, baseline_size_payload={},
            current_size_payload={}, baseline_enabled=True, current_enabled=True, is_duplicate=False,
            resize_capable=True, size_reset_capable=True,
            custom_child_roles=get_widget_runtime_descriptor(family).custom_child_roles,
        ))
    return session


def _bind(display, session):
    return display.scene.bind_custom_layout_session(session, display_identity=DISPLAY, display_origin=QPoint(0, 0))


def _row(model, family: str) -> int:
    return next(index for index, item in enumerate(model._items) if item.model_identity == family)


def _shown_children(display, family: str, presentation) -> dict:
    """Each shown child frame's rectangle in its parent's Edit frame, by the family's own role ids."""
    roles = presentation.item.property("customEditableChildRoles")
    roles = roles.toVariant() if hasattr(roles, "toVariant") else roles
    shown = {}
    for role in roles:
        role_id = str(role["roleId"])
        frame = _edit_item(display, f"customLayoutChildRole-{family}-{role_id}")
        if frame is not None and frame.isVisible():
            shown[role_id] = (frame.x(), frame.y(), frame.width(), frame.height())
    return shown


def _after_parent_nudge(display, model, family: str, presentation) -> dict:
    """The operator's workaround: a parent edit with no net change (one pixel and back) re-derives every frame."""
    row, rect = _row(model, family), RECTS[family]
    model.moveItem(row, rect.x() + 1, rect.y(), rect.x() + 1, rect.y())
    _run(display, 40)
    model.moveItem(row, rect.x(), rect.y(), rect.x(), rect.y())
    model.finishMove()
    _run(display, 80)
    assert model._items[row].current_global_rect == rect
    return _shown_children(display, family, presentation)


def _assert_exposed(display, model, family: str, presentation) -> None:
    exposed = _shown_children(display, family, presentation)
    assert exposed, f"no {family} child frame is shown"
    for role_id, (_x, _y, width, height) in exposed.items():
        assert width > 0.0 and height > 0.0, (family, role_id)
    nudged = _after_parent_nudge(display, model, family, presentation)
    assert set(nudged) == set(exposed), family
    for role_id, rect in exposed.items():
        assert nudged[role_id] == pytest.approx(rect, abs=0.01), (family, role_id)


@pytest.mark.qt
@pytest.mark.parametrize("selected", ["other_widget", "this_widget"])
@pytest.mark.parametrize("family", ["clock", "media"])
def test_the_edit_frames_lock_exposes_the_children_at_once_without_a_parent_edit(display, family, selected):
    """Another widget (or this one) is selected; the pointer rests on this one until its Edit glyphs show and clicks
    its lock. Its children show at once, fading in (never popping in at full opacity, though a selected parent's
    layer was loaded while locked), at the geometry a parent edit would give them; the second click locks again,
    fading them out."""
    presentations = _families(display)
    model = _bind(display, _session())
    other = next(name for name in RECTS if name != family)
    assert model.selectItem(_row(model, other if selected == "other_widget" else family))
    _run(display, 300)
    frame = _edit_item(display, f"customLayoutEditFrame-{family}")
    lock = _edit_item(display, f"customLayoutChildEditLock-{family}")
    assert frame is not None and lock is not None
    assert frame.property("selectedForChildEdit") is (selected == "this_widget")
    assert frame.property("childEditingLocked") is True
    none = Qt.MouseButton.NoButton
    _send(display, QEvent.Type.MouseMove, _centre(frame), none, none)
    _settle(display, lambda: lock.isEnabled() and lock.opacity() > 0.5)

    _click_lock(display, lock)
    assert frame.property("childEditingLocked") is False
    assert frame.property("selectedForChildEdit") is True, "the lock click did not focus its parent"
    layer = _edit_item(display, f"customLayoutChildRoleLayer-{family}")
    assert layer is not None and layer.isVisible() and layer.isEnabled()
    assert layer.opacity() < 1.0, "the children popped in instead of fading in"
    _settle(display, lambda: layer.opacity() >= 1.0)
    assert _edit_item(display, f"customLayoutChildRoleLayer-{other}") is None
    _assert_exposed(display, model, family, presentations[family])

    _click_lock(display, lock)
    assert frame.property("childEditingLocked") is True
    assert layer.isVisible() and not layer.isEnabled(), "locking must drop input at once and fade, not vanish"
    _settle(display, lambda: not layer.isVisible())
    assert not _shown_children(display, family, presentations[family])


@pytest.mark.qt
@pytest.mark.parametrize("family", ["clock", "media"])
def test_the_hover_glyphs_lock_opens_edit_with_the_children_exposed(display, family):
    """The normal-mode hover glyph's route (the display manager after admission): Edit starts, the widget is selected
    and its lock request arrives before Qt has built the Edit frames. The children show without a parent edit."""
    presentations = _families(display)
    session = _session()
    session.select_item(next(item for item in session.items() if item.model_identity == family))
    model = _bind(display, session)
    model.requestToggleChildEditLockForWidget(family)
    _run(display, 1)
    frame = _edit_item(display, f"customLayoutEditFrame-{family}")
    layer = _edit_item(display, f"customLayoutChildRoleLayer-{family}")
    assert frame is not None and layer is not None
    assert frame.property("childEditingLocked") is False and frame.property("selectedForChildEdit") is True
    assert layer.isVisible() and layer.isEnabled()
    _settle(display, lambda: layer.opacity() >= 1.0)
    _assert_exposed(display, model, family, presentations[family])
