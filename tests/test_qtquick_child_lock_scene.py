"""Rendered Qt gate for lock position, child hitbox isolation and parent chrome.

No production timer/service/Settings dependency; the existing session owns geometry.
This supplements the nine-family scene tests, not a claim of human visual acceptance.

The exposure gates at the end run real Clock and Media families (and a Reddit card for the column rails) in the production
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


@pytest.mark.qt
def test_a_lock_click_that_locks_an_unselected_frame_keeps_the_selection_and_its_held_gesture(display):
    """Checkpoint audit 11, A11-L7: the Clock was left unlocked and the Media card is selected (its child gesture held).
    Hovering the Clock and clicking its lock only locks it: the selection stays on the Media card, whose gesture is not
    cancelled, and the Clock's parent glyphs are not revealed by a selection. Only a click that opens a lock focuses
    its parent (the tests above). Negative control (selecting on every click): the selection moved to the Clock and
    the Media card's held gesture was cancelled."""
    _families(display)
    model = _bind(display, _session())
    assert model.selectItem(_row(model, "clock"))
    _run(display, 300)
    frame = _edit_item(display, "customLayoutEditFrame-clock")
    lock = _edit_item(display, "customLayoutChildEditLock-clock")
    assert frame is not None and lock is not None
    none = Qt.MouseButton.NoButton
    _send(display, QEvent.Type.MouseMove, _centre(frame), none, none)
    _settle(display, lambda: lock.isEnabled() and lock.opacity() > 0.5)
    _click_lock(display, lock)
    assert frame.property("childEditingLocked") is False             # left unlocked ...
    assert model.selectItem(_row(model, "media"))                     # ... while the Media card is edited
    _run(display, 300)
    media = _edit_item(display, "customLayoutEditFrame-media")
    assert media is not None and media.property("selectedForChildEdit") is True
    assert frame.property("selectedForChildEdit") is False and frame.property("childEditingLocked") is False
    cancelled = []
    model._child_gesture_cancel_handler = lambda item: cancelled.append(item.model_identity)

    _send(display, QEvent.Type.MouseMove, _centre(frame), none, none)
    _settle(display, lambda: lock.isEnabled() and lock.opacity() > 0.5)
    _click_lock(display, lock)
    _run(display, 50)
    assert frame.property("childEditingLocked") is True
    assert frame.property("selectedForChildEdit") is False, "a locking click moved the selection"
    assert media.property("selectedForChildEdit") is True
    assert "media" not in cancelled, "a locking click cancelled the selected frame's held child gesture"


# ---------------------------------------------------------------------------------------------------
# The column rails (Reddit/Gmail's three semantic column grips) follow the lock like the child layer:
# loaded for the selected parent locked or not, fading in on unlock and out on lock (fade, never vanish),
# their input off at the lock edge so a grip held while locking is cancelled and nothing is swapped.

REDDIT_RECT = QRect(120, 90, 620, 340)  # display-local


def _reddit(display):
    """A real retained Reddit card with published posts and no runtime service: nothing can fetch from Reddit."""
    from rendering.quick.widgets.host import OverlayWidgetGeometry
    from rendering.quick.widgets.reddit import RetainedRedditPresentation
    from tests.test_qtquick_reddit_presentation import _model as _reddit_model, _post

    model = _reddit_model(limit=3)
    model.publish_posts(tuple(_post(index) for index in (1, 2, 3)), now_ts=20_000.0)
    presentation = RetainedRedditPresentation(
        host=display.scene.ordinary_widget_host, model=model,
        geometry=OverlayWidgetGeometry(float(REDDIT_RECT.x()), float(REDDIT_RECT.y()),
                                       float(REDDIT_RECT.width()), float(REDDIT_RECT.height())))
    presentation.activate()
    _run(display, 200)
    return presentation


def _drag(display, start: QPointF, target: QPointF) -> None:
    """Hover, press and drag horizontally towards ``target`` (moves carry no button, only held buttons: a move
    with a button is a fresh press in Qt 6). The caller releases."""
    none, left = Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton
    _send(display, QEvent.Type.MouseMove, start, none, none)
    _send(display, QEvent.Type.MouseButtonPress, start, left, left)
    _send(display, QEvent.Type.MouseMove, QPointF(start.x() + 4.0, start.y()), none, left)
    _send(display, QEvent.Type.MouseMove, QPointF(target.x(), start.y()), none, left)


def _rail_specs(presentation) -> list:
    specs = presentation.item.property("customColumnRailSpecs")
    specs = specs.toVariant() if hasattr(specs, "toVariant") else specs
    return [str(spec["roleId"]) for spec in specs or ()]


@pytest.mark.qt
def test_the_column_rails_fade_with_the_lock_and_a_grip_held_at_the_lock_edge_swaps_nothing(display, monkeypatch):
    """Reddit's column rails fade in on unlock and out on lock (never popping), with input off at once. A grip held
    across the lock (the L route) is cancelled; its release swaps nothing and adds no Undo, while the same drag
    unlocked does swap."""
    import socket

    from rendering.custom_layout_session import CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem
    from rendering.quick.column_rails import COLUMN_RAIL_IDS
    from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner
    from rendering.widget_descriptors import get_widget_runtime_descriptor

    def _refuse(*_args, **_kwargs):
        raise AssertionError("the Reddit rail test must never open a network connection")

    monkeypatch.setattr(socket, "create_connection", _refuse)
    monkeypatch.setattr(socket.socket, "connect", _refuse)

    presentation = _reddit(display)
    session = CustomLayoutSession()
    item = CustomLayoutSessionItem(
        source_key=CustomLayoutKey("reddit", DISPLAY), model_identity="reddit",
        baseline_global_rect=REDDIT_RECT, current_global_rect=REDDIT_RECT, baseline_size_payload={},
        current_size_payload={}, baseline_enabled=True, current_enabled=True, is_duplicate=False,
        resize_capable=True, size_reset_capable=True,
        custom_child_roles=get_widget_runtime_descriptor("reddit").custom_child_roles,
    )
    session.add_item(item)
    # The production swap authority and its bounded Undo, without Settings or display bindings.
    owner = QuickCustomLayoutOwner(settings_manager=None, participants_provider=lambda: (),
                                   visualizer_provider=lambda: (None, None), reload_request=lambda _reason: None)
    owner._active, owner._session = True, session
    model = display.scene.bind_custom_layout_session(
        session, display_identity=DISPLAY, display_origin=QPoint(0, 0),
        column_rail_swap_handler=owner.swap_column_rail_roles)
    assert model.selectItem(_row(model, "reddit"))
    _run(display, 300)
    frame = _edit_item(display, "customLayoutEditFrame-reddit")
    lock = _edit_item(display, "customLayoutChildEditLock-reddit")
    assert frame is not None and lock is not None
    assert frame.property("childEditingLocked") is True
    rails = _rail_specs(presentation)
    assert sorted(rails) == sorted(COLUMN_RAIL_IDS["reddit"])
    idle = _edit_item(display, "customLayoutColumnRailLayer-reddit")
    assert idle is None or not idle.isVisible(), "the locked rails must paint nothing"
    none, left = Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton
    _send(display, QEvent.Type.MouseMove, _centre(frame), none, none)
    _settle(display, lambda: lock.isEnabled() and lock.opacity() > 0.5)

    # 1. Unlock with a real click: the rails fade in, input on.
    _click_lock(display, lock)
    assert frame.property("childEditingLocked") is False
    layer = _edit_item(display, "customLayoutColumnRailLayer-reddit")
    assert layer is not None and layer.isVisible() and layer.isEnabled()
    assert layer.opacity() < 1.0, "the column rails popped in instead of fading in"
    _settle(display, lambda: layer.opacity() >= 1.0)

    def grip(rail: str):
        return _edit_item(display, f"customLayoutColumnGrip-reddit-{rail}")

    grips = {rail: grip(rail) for rail in rails}
    assert all(g is not None and g.isVisible() and g.width() > 0.0 for g in grips.values()), grips

    # 2. Lock with a real click: input off at once, the paint fades out (never vanishes).
    _click_lock(display, lock)
    assert frame.property("childEditingLocked") is True
    assert not layer.isEnabled(), "locking must drop the rails' input at once"
    assert layer.isVisible() and layer.opacity() > 0.0, "the column rails vanished instead of fading out"
    _settle(display, lambda: not layer.isVisible())
    assert layer.opacity() == 0.0
    assert not any(g.isVisible() for g in grips.values())

    # 3. Lock while a grip is held mid-drag (a drag whose release would swap): cancelled, nothing committed.
    display.scene.toggle_selected_child_edit_lock()  # the runtime's L route
    assert frame.property("childEditingLocked") is False
    _settle(display, lambda: layer.opacity() >= 1.0)
    held, onto = rails[-1], rails[0]  # the last delegate is topmost: its grip owns its own centre
    rail = _edit_item(display, f"customLayoutColumnRail-reddit-{held}")
    start, target = _centre(grip(held)), _centre(grip(onto))
    assert abs(target.x() - start.x()) >= 9.0
    before = item.current_size_payload.get("column_rails")
    assert not owner._undo_history
    _drag(display, start, target)
    display.render()
    assert rail.property("previewOffsetX") != 0.0, "the grip drag did not start"
    display.scene.toggle_selected_child_edit_lock()
    assert frame.property("childEditingLocked") is True and not layer.isEnabled()
    assert rail.property("previewOffsetX") == 0.0, "the held grip was not cancelled at the lock edge"
    _send(display, QEvent.Type.MouseButtonRelease, QPointF(target.x(), start.y()), left, none)
    _settle(display, lambda: not layer.isVisible())
    assert item.current_size_payload.get("column_rails") == before, "a grip held across the lock swapped columns"
    assert owner.undo_last_change() is False, "Undo gained an entry from a cancelled grip"

    # Control: the same drag unlocked reaches the swap authority (the assertions above are not vacuous).
    display.scene.toggle_selected_child_edit_lock()
    _settle(display, lambda: layer.isEnabled() and layer.opacity() >= 1.0)
    start, target = _centre(grip(held)), _centre(grip(onto))
    _drag(display, start, target)
    _send(display, QEvent.Type.MouseButtonRelease, QPointF(target.x(), start.y()), left, none)
    display.render()
    swapped = list(rails)
    swapped[0], swapped[-1] = swapped[-1], swapped[0]
    assert item.current_size_payload.get("column_rails") == swapped
    assert len(owner._undo_history) == 1
