"""Held-left routing without acquiring desktop capture or changing native focus."""
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPointF, QRectF, Qt, QUrl
from PySide6.QtGui import QMouseEvent
from PySide6.QtQml import QQmlComponent, QQmlEngine

from rendering.quick.input_controller import QuickInputController
from rendering.quick.window import QuickDisplayWindow
from rendering.quick.state import QuickWindowPolicy
from tests.test_framed_scene_input import card as production_card


@pytest.fixture
def orbit_card(qt_app, monkeypatch):
    window = QuickDisplayWindow(screen_index=0, runtime_generation=708, screen=qt_app.primaryScreen(),
                                policy=QuickWindowPolicy(always_on_top=False))
    window.resize(400, 300)
    controller = QuickInputController(screen_index=0, runtime_generation=708, interaction_mode_enabled=True)
    controller.set_view_orbit_enabled(True)
    controller.set_scene_transform_enabled(True, mode_id='extruded_bubble')
    window.bind_input_controller(controller)
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(b'''import QtQuick
Item {
    width: 300; height: 200; x: 20; y: 20
    property bool cardShellEnabled: true
    property bool presentationActive: true
    property int clicks: 0
    property int taps: 0
    MouseArea { objectName: "mouseControl"; x:10; y:10; width:50; height:50; onClicked: parent.clicks++ }
    Item { x:80; y:10; width:50; height:50
        TapHandler { onTapped: parent.parent.taps++ }
    }
}''', QUrl())
    card = component.create()
    assert card is not None, component.errors()
    card.setParentItem(window.contentItem())
    card.setParent(window)
    window.watch_plain_orbit_card(card)
    window.bind_plain_orbit_target(lambda p: card if card.isVisible() and card.property('cardShellEnabled')
                                   and card.contains(card.mapFromScene(p)) else None)
    capture = SimpleNamespace(acquisitions=[], releases=0)
    class Capture:
        def acquire(self, rect):
            capture.acquisitions.append(QRectF(rect))
        def release(self):
            capture.releases += 1
    monkeypatch.setattr(window, '_new_plain_orbit_capture', Capture)
    cursor = SimpleNamespace(tracks_pointer_motion=False, starts=0, ends=0)
    def begin():
        cursor.starts += 1
        return True
    def end():
        cursor.ends += 1
    cursor.begin_orbit_fade, cursor.end_orbit_fade = begin, end
    window.bind_cursor_controller(cursor)
    turns, finishes, exits = [], [], []
    controller.view_orbit_requested.connect(lambda *args: turns.append(args))
    controller.view_orbit_finished.connect(lambda: finishes.append(1))
    controller.exit_requested.connect(lambda: exits.append(1))
    def send(kind, x, y, *, button=Qt.MouseButton.NoButton, buttons=Qt.MouseButton.NoButton,
             modifiers=Qt.KeyboardModifier.NoModifier):
        event = QMouseEvent(kind, QPointF(x, y), QPointF(x, y), button, buttons, modifiers)
        QCoreApplication.sendEvent(window, event)
        return event
    data = SimpleNamespace(window=window, card=card, controller=controller, capture=capture,
                           cursor=cursor, turns=turns, finishes=finishes, exits=exits, send=send)
    yield data
    import shiboken6
    if shiboken6.isValid(window):
        window.cancel_plain_orbit()
    controller.close_input()
    if shiboken6.isValid(window):
        window.deleteLater()
    controller.deleteLater()
    engine.deleteLater()
    qt_app.processEvents()


def _press(card, x=200, y=130):
    return card.send(QEvent.Type.MouseButtonPress, x, y, button=Qt.MouseButton.LeftButton,
                     buttons=Qt.MouseButton.LeftButton)


def _move(card, x=240, y=150, buttons=Qt.MouseButton.LeftButton):
    return card.send(QEvent.Type.MouseMove, x, y, buttons=buttons)


def _release(card, x=240, y=150):
    return card.send(QEvent.Type.MouseButtonRelease, x, y, button=Qt.MouseButton.LeftButton)


def test_window_never_bridges_blocking_quick_event_delivery_through_python():
    """Guardrails: render-thread synchronization must execute outside Python/GIL."""
    import ast
    from pathlib import Path
    from rendering.quick import window
    tree = ast.parse(Path(window.__file__).read_text(encoding='utf-8'))
    owner = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                 and node.name == 'QuickDisplayWindow')
    assert not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and node.name == 'event' for node in owner.body)


@pytest.mark.qt
def test_unclaimed_press_promotes_once_and_reuses_orbit_scale(orbit_card):
    card = orbit_card
    _press(card)
    assert card.window._plain_orbit_pending is not None
    _move(card, 201, 131)
    assert not card.capture.acquisitions and not card.turns
    _move(card)
    assert len(card.capture.acquisitions) == 1
    assert card.window._plain_orbit_press_device is None
    assert card.capture.acquisitions[0] == QRectF(20, 20, 300, 200)
    assert card.turns == [card.controller.view_orbit_drag_steps(40, 20)]
    _move(card, 250, 155)
    assert card.turns[-1] == card.controller.view_orbit_drag_steps(10, 5)
    _release(card)
    card.window.cancel_plain_orbit()
    assert card.capture.releases == card.cursor.ends == len(card.finishes) == 1


@pytest.mark.qt
@pytest.mark.parametrize('position,counter', [((40, 40), 'clicks'), ((110, 40), 'taps')])
def test_real_retained_mouse_and_pointer_handlers_keep_their_press(orbit_card, position, counter):
    card = orbit_card
    _press(card, *position)
    assert card.window._plain_orbit_pending is None
    _release(card, *position)
    assert card.card.property(counter) == 1
    assert not card.capture.acquisitions and not card.turns
    # A new held movement must also respect the retained press, including the
    # passive grab owned by TapHandler (not merely MouseArea's exclusive grab).
    _press(card, *position)
    _move(card, position[0] + 20, position[1] + 15)
    assert not card.capture.acquisitions and not card.turns
    assert card.window._plain_orbit_press_device is None
    _release(card, position[0] + 20, position[1] + 15)


@pytest.mark.qt
@pytest.mark.parametrize('cancel', ['release', 'missing_button', 'menu', 'edit', 'mode', 'reset',
                                  'close', 'deactivate', 'hide', 'grab_loss', 'card_hidden', 'card_destroyed', 'borderless'])
def test_every_cancellation_unwinds_once(orbit_card, cancel):
    card = orbit_card
    _press(card)
    _move(card)
    assert len(card.capture.acquisitions) == 1
    if cancel == 'release':
        _release(card)
    elif cancel == 'missing_button':
        _move(card, buttons=Qt.MouseButton.NoButton)
    elif cancel == 'menu':
        card.controller.set_context_menu_active(True)
    elif cancel == 'edit':
        card.window.set_custom_layout_input_blocked(True)
    elif cancel == 'mode':
        card.controller.set_scene_transform_enabled(True, mode_id='neon_lake')
    elif cancel == 'reset':
        card.controller.cancel_view_orbit_for_camera_reset()
    elif cancel == 'close':
        card.controller.close_input()
    elif cancel == 'card_hidden':
        card.card.setVisible(False)
    elif cancel == 'card_destroyed':
        import shiboken6
        shiboken6.delete(card.card)
    elif cancel == 'borderless':
        card.card.setProperty('cardShellEnabled', False)
    else:
        event = {'deactivate': QEvent.Type.WindowDeactivate, 'hide': QEvent.Type.Hide,
                 'grab_loss': QEvent.Type.UngrabMouse}[cancel]
        QCoreApplication.sendEvent(card.window, QEvent(event))
    card.window.cancel_plain_orbit()
    assert card.capture.releases == card.cursor.ends == 1
    assert card.controller._view_orbit_drag is None
    if cancel == 'reset':
        assert card.finishes == []  # Reset owns the replacement pose; never save the obsolete drag.


@pytest.mark.qt
def test_click_doubleclick_borderless_and_noninteraction_preserve_semantics(orbit_card):
    card = orbit_card
    _press(card)
    _release(card, 200, 130)
    assert not card.capture.acquisitions and not card.turns
    _press(card)
    card.send(QEvent.Type.MouseButtonDblClick, 200, 130, button=Qt.MouseButton.LeftButton,
              buttons=Qt.MouseButton.LeftButton)
    assert card.window._plain_orbit_pending is None
    card.card.setProperty('cardShellEnabled', False)
    _press(card)
    _move(card)
    assert not card.capture.acquisitions
    card.controller.set_interaction_mode_enabled(False)
    _press(card)
    assert card.exits == [1]


@pytest.mark.qt
def test_ctrl_admission_and_release_use_cached_input_edges(orbit_card):
    card = orbit_card
    card.controller.set_interaction_mode_enabled(False)
    card.controller.set_shared_ctrl_held(True)
    _press(card)
    _move(card)
    assert len(card.capture.acquisitions) == 1 and not card.exits
    card.controller.set_shared_ctrl_held(False)
    assert card.capture.releases == 1 and card.controller._view_orbit_drag is None


@pytest.mark.qt
def test_older_card_geometry_and_destruction_do_not_cancel_current_gesture(orbit_card):
    import shiboken6
    engine = QQmlEngine.contextForObject(orbit_card.card).engine()
    component = QQmlComponent(engine)
    component.setData(b'''import QtQuick
Item { property bool cardShellEnabled:true; property bool presentationActive:true; width:100; height:100 }
''', QUrl())
    older = component.create()
    assert older is not None
    older.setParent(orbit_card.window)
    orbit_card.window.watch_plain_orbit_card(older)
    _press(orbit_card)
    _move(orbit_card)
    older.setWidth(120)
    shiboken6.delete(older)
    assert orbit_card.capture.releases == 0
    _release(orbit_card)
    assert orbit_card.capture.releases == 1


@pytest.mark.qt
def test_failed_native_acquisition_is_logged_and_unwinds_cursor(orbit_card, monkeypatch, caplog):
    class Failed:
        cleanup_pending = False
        def acquire(self, rect):
            raise OSError('controlled native capture refusal')
        def release(self):
            pass
    monkeypatch.setattr(orbit_card.window, '_new_plain_orbit_capture', Failed)
    _press(orbit_card)
    _move(orbit_card)
    assert 'capture/confinement failed' in caplog.text
    assert orbit_card.cursor.starts == orbit_card.cursor.ends == 1
    assert orbit_card.window._plain_orbit_capture is None
    assert orbit_card.window._plain_orbit_pending is None
    assert orbit_card.turns == []


def test_native_clip_maps_local_client_ratio_without_scaling_negative_desktop_origin():
    from rendering.quick.pointer_capture import physical_client_clip
    assert physical_client_clip(QRectF(20, 10, 100, 80), (400, 300), (600, 600), (-1920, -240)) == (
        -1890, -220, -1740, -60)
    assert physical_client_clip(QRectF(-10, -10, 30, 30), (100, 100), (150, 150), (7, 11)) == (7, 11, 37, 41)
    with pytest.raises(ValueError):
        physical_client_clip(QRectF(200, 200, 10, 10), (100, 100), (150, 150), (0, 0))


@pytest.mark.qt
def test_drag_cursor_reuses_one_timer_and_cached_frames_without_motion_revival(orbit_card, monkeypatch):
    from rendering.quick.cursor_controller import QuickCursorController, _CURSOR_FADE_STEPS
    from rendering.quick.auxiliary import QuickAuxiliaryState
    cursor = QuickCursorController(window=orbit_card.window, screen_index=0, runtime_generation=708)
    monkeypatch.setattr(cursor, '_pointer_is_inside_window', lambda: True)
    try:
        cursor.apply_auxiliary_state(QuickAuxiliaryState(screen_index=0, runtime_generation=708, halo_enabled=True))
        timer = cursor._timer
        assert cursor.begin_orbit_fade()
        assert cursor._orbit_fade == 'out'
        cache_size = len(cursor._cursor_cache)
        for index in range(100):
            assert not cursor.note_pointer_motion(index + 1)
        assert len(cursor._cursor_cache) == cache_size
        for _ in range(_CURSOR_FADE_STEPS):
            cursor._on_timer()
        assert cursor._orbit_fade == 'held' and not timer.isActive()
        assert orbit_card.window.cursor().shape() == Qt.CursorShape.BlankCursor
        warmed = len(cursor._cursor_cache)
        cursor.end_orbit_fade()
        for _ in range(_CURSOR_FADE_STEPS):
            cursor._on_timer()
        assert cursor._orbit_fade == '' and cursor._fade_step == 0
        assert cursor._timer is timer and timer.isActive()
        assert len(cursor._cursor_cache) == warmed
        # Reversal halfway through uses the same alpha step, no flash to full.
        cursor.begin_orbit_fade()
        cursor._on_timer()
        assert cursor._fade_step == 1
        cursor.end_orbit_fade()
        assert cursor._fade_step == 1
        cursor._on_timer()
        assert cursor._fade_step == 0
        cursor.close()
        assert not timer.isActive()
    finally:
        cursor.close()
        cursor.deleteLater()


@pytest.mark.qt
def test_stock_arrow_fade_is_explicitly_declined_without_style_substitution(orbit_card, caplog):
    from rendering.quick.cursor_controller import QuickCursorController
    from rendering.quick.auxiliary import QuickAuxiliaryState
    cursor = QuickCursorController(window=orbit_card.window, screen_index=0, runtime_generation=708)
    try:
        cursor.apply_auxiliary_state(QuickAuxiliaryState(screen_index=0, runtime_generation=708,
                                                       native_cursor_visible=True))
        assert not cursor.begin_orbit_fade()
        assert 'Native arrow alpha raster unavailable' in caplog.text
        assert orbit_card.window.cursor().shape() == Qt.CursorShape.ArrowCursor
        assert cursor._orbit_fade == '' and not cursor._timer.isActive()
    finally:
        cursor.close()
        cursor.deleteLater()


@pytest.fixture
def native_capture_stub():
    from rendering.quick.pointer_capture import NativeOrbitCapture
    class API:
        capture = 0
        foreground = 17
        desktop = (-1920, -240, 1920, 1080)
        clip = desktop
        fail_clip = False
        fail_query = False
        fail_ungrab = False
        queries = 0
        calls = []
        def GetForegroundWindow(self):
            return self.foreground
        def GetCapture(self):
            return self.capture
        def GetClientRect(self, hwnd, result):
            result._obj.left, result._obj.top, result._obj.right, result._obj.bottom = (0, 0, 600, 600)
            return 1
        def ClientToScreen(self, hwnd, result):
            result._obj.x, result._obj.y = -1920, -240
            return 1
        def GetClipCursor(self, result):
            self.queries += 1
            if self.fail_query:
                return 0
            result._obj.left, result._obj.top, result._obj.right, result._obj.bottom = self.clip
            return 1
        def ClipCursor(self, rect):
            if self.fail_clip:
                return 0
            self.clip = self.desktop if rect is None else NativeOrbitCapture._tuple(rect._obj)
            self.calls.append(self.clip)
            return 1
        def GetSystemMetrics(self, index):
            return {76: -1920, 77: -240, 78: 3840, 79: 1320}[index]
    api = API()
    api.calls = []
    window = SimpleNamespace(width=lambda: 400, height=lambda: 300)
    grabs = []
    def grab(enabled):
        grabs.append(enabled)
        if not enabled and api.fail_ungrab:
            return False
        api.capture = 17 if enabled else 0
        return True
    window.setMouseGrabEnabled = grab
    capture = NativeOrbitCapture.__new__(NativeOrbitCapture)
    capture.api, capture.window, capture.hwnd = api, window, 17
    capture.clip, capture.grabbed = None, False
    return capture, api, grabs


def test_native_capture_clip_is_exact_and_release_idempotent(native_capture_stub):
    capture, api, grabs = native_capture_stub
    capture.acquire(QRectF(20, 10, 100, 80))
    assert api.clip == (-1890, -220, -1740, -60)
    capture.release()
    capture.release()
    assert api.clip == api.desktop and grabs == [True, False]


def test_native_capture_does_not_release_replacement_owners(native_capture_stub):
    capture, api, grabs = native_capture_stub
    capture.acquire(QRectF(20, 10, 100, 80))
    api.clip, api.capture = (1, 2, 30, 40), 999
    capture.release()
    assert api.clip == (1, 2, 30, 40) and api.capture == 999
    assert grabs == [True]


def test_native_capture_failed_clip_unwinds_capture_and_refuses_foreign_state(native_capture_stub):
    capture, api, grabs = native_capture_stub
    api.fail_clip = True
    with pytest.raises(OSError):
        capture.acquire(QRectF(20, 10, 100, 80))
    assert api.capture == 0 and grabs == [True, False] and capture.clip is None
    api.fail_clip, api.clip = False, (1, 2, 30, 40)
    with pytest.raises(RuntimeError, match='already owned'):
        capture.acquire(QRectF(20, 10, 100, 80))
    assert grabs == [True, False]


@pytest.mark.parametrize('failure', ['fail_query', 'fail_clip'])
def test_failed_native_unclip_preserves_token_until_later_success(native_capture_stub, failure):
    capture, api, grabs = native_capture_stub
    capture.acquire(QRectF(20, 10, 100, 80))
    original = capture.clip
    setattr(api, failure, True)
    for _ in range(2):
        with pytest.raises(OSError):
            capture.release()
        assert capture.clip == api.clip == original and capture.cleanup_pending
        assert not capture.grabbed and api.capture == 0
    setattr(api, failure, False)
    capture.release()
    assert capture.clip is None and not capture.cleanup_pending and api.clip == api.desktop
    completed = list(api.calls), list(grabs)
    capture.release()
    assert (api.calls, grabs) == completed


def test_failed_native_ungrab_preserves_only_its_unresolved_token(native_capture_stub):
    capture, api, grabs = native_capture_stub
    capture.acquire(QRectF(20, 10, 100, 80))
    api.fail_ungrab = True
    with pytest.raises(RuntimeError, match='mouse release failed'):
        capture.release()
    assert capture.clip is None and api.clip == api.desktop
    assert capture.grabbed and api.capture == 17 and capture.cleanup_pending
    queries = api.queries
    api.fail_ungrab = False
    capture.release()
    assert not capture.cleanup_pending and api.capture == 0
    assert api.queries == queries  # Successfully released clip is never queried/released again.


@pytest.mark.parametrize('qt_result', [False, True])
def test_release_checks_actual_native_capture_after_qt_call(native_capture_stub, qt_result):
    capture, api, _ = native_capture_stub
    capture.acquire(QRectF(20, 10, 100, 80))
    def release(enabled):
        assert enabled is False
        api.capture = 0
        return qt_result
    capture.window.setMouseGrabEnabled = release
    capture.release()
    assert not capture.cleanup_pending and api.capture == 0


def test_successful_qt_return_cannot_hide_retained_native_capture(native_capture_stub):
    capture, api, _ = native_capture_stub
    capture.acquire(QRectF(20, 10, 100, 80))
    capture.window.setMouseGrabEnabled = lambda _enabled: True
    with pytest.raises(RuntimeError, match='native mouse release failed'):
        capture.release()
    assert capture.grabbed and api.capture == 17


def test_retry_after_failure_never_clears_replacement_foreign_clip(native_capture_stub):
    capture, api, grabs = native_capture_stub
    capture.acquire(QRectF(20, 10, 100, 80))
    api.fail_clip = True
    with pytest.raises(OSError):
        capture.release()
    api.fail_clip, api.clip, api.capture = False, (1, 2, 30, 40), 999
    successful_clips = list(api.calls)
    capture.release()
    assert api.clip == (1, 2, 30, 40) and api.calls == successful_clips
    assert api.capture == 999 and not capture.cleanup_pending


@pytest.mark.qt
def test_window_retains_failed_cleanup_inactive_and_retries_only_discrete_edges(
        orbit_card, native_capture_stub, monkeypatch):
    card = orbit_card
    capture, api, grabs = native_capture_stub
    monkeypatch.setattr(card.window, '_new_plain_orbit_capture', lambda: capture)
    _press(card)
    _move(card)
    api.fail_clip = True
    _release(card)
    assert card.window._plain_orbit_capture is capture and capture.cleanup_pending
    assert card.window._plain_orbit_card is None and card.controller._view_orbit_drag is None
    assert card.cursor.ends == len(card.finishes) == 1
    queries = api.queries
    turns = list(card.turns)
    for x in range(250, 270):
        _move(card, x, 155)
    assert api.queries == queries and card.turns == turns  # No motion polling/retry.
    card.window.cancel_plain_orbit()
    assert card.window._plain_orbit_capture is capture and card.cursor.ends == 1
    api.fail_clip = False
    QCoreApplication.sendEvent(card.window, QEvent(QEvent.Type.Close))
    assert card.window._plain_orbit_capture is None and api.clip == api.desktop
    card.window.cancel_plain_orbit()
    assert card.cursor.ends == len(card.finishes) == 1


@pytest.mark.qt
def test_partial_acquisition_failed_unwind_remains_window_owned(
        orbit_card, native_capture_stub, monkeypatch):
    card = orbit_card
    capture, api, grabs = native_capture_stub
    api.fail_clip = api.fail_ungrab = True
    monkeypatch.setattr(card.window, '_new_plain_orbit_capture', lambda: capture)
    _press(card)
    _move(card)
    assert grabs == [True, False]  # One immediate native unwind, no retry loop.
    assert capture.cleanup_pending and card.window._plain_orbit_capture is capture
    assert card.window._plain_orbit_card is None and card.controller._view_orbit_drag is None
    assert card.cursor.ends == 1 and card.turns == []
    api.fail_clip = api.fail_ungrab = False
    card.window.cancel_plain_orbit()
    assert card.window._plain_orbit_capture is None and not capture.cleanup_pending
    assert grabs == [True, False, False] and card.cursor.ends == 1


@pytest.mark.qt
@pytest.mark.parametrize('fail_release', [False, True])
def test_synchronous_acquisition_cancel_unwinds_without_promoting(
        orbit_card, monkeypatch, fail_release):
    card = orbit_card
    class Capture:
        cleanup_pending = False
        releases = 0
        def acquire(self, rect):
            self.cleanup_pending = True
            card.window.cancel_plain_orbit('reset')
            assert self.releases == 0  # Finish the native acquisition before unwind.
        def release(self):
            self.releases += 1
            if fail_release:
                raise RuntimeError('native cleanup unavailable')
            self.cleanup_pending = False
    capture = Capture()
    monkeypatch.setattr(card.window, '_new_plain_orbit_capture', lambda: capture)
    _press(card)
    _move(card)
    assert capture.releases == 1
    assert card.window._plain_orbit_card is None and card.window._plain_orbit_pending is None
    assert card.controller._view_orbit_drag is None and card.turns == card.finishes == []
    assert card.cursor.ends == 1
    assert (card.window._plain_orbit_capture is capture) is fail_release
    expected_releases = 2 if fail_release else 1
    fail_release = False
    card.window.cancel_plain_orbit()
    assert card.window._plain_orbit_capture is None and not capture.cleanup_pending
    assert capture.releases == expected_releases
    assert card.cursor.ends == 1


@pytest.mark.qt
def test_canonical_runtime_deletion_gate_keeps_cleanup_owner_until_discrete_retry(
        orbit_card, native_capture_stub, monkeypatch):
    import shiboken6
    card = orbit_card
    capture, api, _ = native_capture_stub
    monkeypatch.setattr(card.window, '_new_plain_orbit_capture', lambda: capture)
    _press(card)
    _move(card)
    api.fail_clip = True
    _release(card)
    from rendering.quick.runtime import QuickDisplayRuntime
    from rendering.quick.state import QuickRuntimePhase
    # Exercise the exact existing retirement gate without publishing a second
    # runtime/scene or creating a native visible window.
    scene = SimpleNamespace(finalize_retirement=lambda: None, describe_scene_state=lambda: {})
    owner = SimpleNamespace(_phase=QuickRuntimePhase.RETIRING, _close_meta_calls_queued=True,
        _window_delete_queued=False, _scene_readiness=SimpleNamespace(qml_objects_retired=True),
        _window=card.window, _scene=scene, _pacer=None, _input=None, _auxiliary=None,
        _cursor=None, _context_menu=None, _transition=None)
    retry_gate = lambda: QuickDisplayRuntime._maybe_queue_window_deletion(owner)
    card.window.orbit_cleanup_completed.connect(retry_gate)
    retry_gate()
    assert not owner._window_delete_queued and shiboken6.isValid(card.window)
    assert card.window._plain_orbit_capture is capture
    assert QuickDisplayRuntime.close_runtime(owner) is False
    assert card.window._plain_orbit_capture is capture and not owner._window_delete_queued
    api.fail_clip = False
    assert QuickDisplayRuntime.close_runtime(owner) is False
    assert owner._window_delete_queued
    QCoreApplication.sendPostedEvents(card.window, QEvent.Type.DeferredDelete)
    assert not shiboken6.isValid(card.window)
    assert not capture.cleanup_pending and api.clip == api.desktop


@pytest.mark.qt
def test_early_native_event_does_not_require_constructed_capture_field(orbit_card):
    import ctypes
    from ctypes import wintypes
    window = orbit_card.window
    del window._plain_orbit_capture
    try:
        message = wintypes.MSG()
        assert window.nativeEvent(b'windows_generic_MSG', ctypes.addressof(message)) == (False, 0)
    finally:
        window._plain_orbit_capture = None


@pytest.mark.qt
@pytest.mark.parametrize('z,expected', [(-1., True), (1., False)])
def test_overlapping_retained_passive_grab_uses_same_paint_owner_as_target(orbit_card, z, expected):
    from rendering.quick.scene_controller import QuickSceneController
    card = orbit_card
    engine = QQmlEngine.contextForObject(card.card).engine()
    component = QQmlComponent(engine)
    component.setData(b'''import QtQuick
Item { x:20; y:20; width:300; height:200; property int taps:0
    TapHandler { onTapped: parent.taps++ }
}''', QUrl())
    other = component.create()
    assert other is not None, component.errors()
    other.setParent(card.window)
    other.setParentItem(card.window.contentItem())
    other.setZ(z)
    scene = SimpleNamespace(_visualizer_root=card.card, _custom_layout_session=None,
        _ordinary_widget_host=SimpleNamespace(diagnostic_widget_at=lambda p: SimpleNamespace(item=other)))
    scene.visualizer_contains_scene_position = lambda p: QuickSceneController.visualizer_contains_scene_position(scene,p)
    card.window.bind_plain_orbit_target(lambda p: QuickSceneController._plain_orbit_target_at(scene,p),
        grabber_blocks=lambda grabber,root: QuickSceneController._plain_orbit_grabber_blocks(scene,grabber,root))
    _press(card)
    _move(card)
    assert (card.window._plain_orbit_card is card.card) is expected
    _release(card)
    assert card.window._plain_orbit_pending is None
    assert other.property('taps') == 0


@pytest.mark.qt
def test_retained_ordinary_overlap_uses_actual_parent_stacking(orbit_card):
    from PySide6.QtQuick import QQuickItem
    from rendering.quick.scene_controller import QuickSceneController
    card = orbit_card.card
    other = QQuickItem(orbit_card.window.contentItem())
    other.setX(20)
    other.setY(20)
    other.setWidth(300)
    other.setHeight(200)
    scene = SimpleNamespace(_visualizer_root=card, _custom_layout_session=None,
        _ordinary_widget_host=SimpleNamespace(diagnostic_widget_at=lambda p: SimpleNamespace(item=other)))
    scene.visualizer_contains_scene_position = lambda p: QuickSceneController.visualizer_contains_scene_position(scene, p)
    hit = lambda: QuickSceneController._plain_orbit_target_at(scene, QPointF(200, 130))
    other.setZ(1.)
    assert hit() is None
    other.setZ(-1.)
    assert hit() is card
    other.setZ(0.)
    assert hit() is None  # Later sibling wins equal Z.
    card.stackAfter(other)
    assert hit() is card
    scene._custom_layout_session = object()
    assert hit() is None


@pytest.mark.qt
def test_actual_framed_camera_route_keeps_layout_and_persists_once(production_card, monkeypatch):
    from tests.test_framed_scene_input import point, mouse, pose, NONE
    card = production_card
    class Capture:
        def acquire(self, rect):
            assert rect.width() == 480 and rect.height() == 210
        def release(self):
            pass
    monkeypatch.setattr(card.window, '_new_plain_orbit_capture', Capture)
    p = point(card)
    before = pose(card)
    presentation = card.scene.visualizer_item.presentation
    mouse(card, QEvent.Type.MouseButtonPress, p, Qt.MouseButton.LeftButton, NONE)
    assert card.window._plain_orbit_pending is not None
    mouse(card, QEvent.Type.MouseMove, p + QPointF(40, 20), Qt.MouseButton.LeftButton, NONE)
    assert pose(card) != before and card.writes == []
    mouse(card, QEvent.Type.MouseButtonRelease, p + QPointF(40, 20), Qt.MouseButton.LeftButton, NONE)
    assert len(card.writes) == 1
    assert card.scene.visualizer_item.presentation == presentation
    assert {key: card.settings.get('widgets.spotify_visualizer')[key] for key in pose(card)} == pytest.approx(pose(card))


@pytest.mark.qt
def test_actual_camera_reset_glyph_retains_press_before_plain_orbit(production_card):
    from tests.test_framed_scene_input import mouse, NONE
    card = production_card
    root = card.scene._visualizer_root
    root.setProperty('cameraResetAvailable', True)
    root.setProperty('alwaysShowGlyphs', True)
    root.setProperty('widgetGlowAdmitted', True)
    glyph = root.findChild(type(root), 'visualizerCameraResetGlyph')
    assert glyph is not None
    # Admit the glyph's completed hover presentation directly. Its animation
    # has separate native coverage; this hidden test owns press routing only.
    glyph.setProperty('opacity', .92)
    glyph.setEnabled(True)
    p = glyph.mapToScene(QPointF(glyph.width() / 2, glyph.height() / 2))
    assert glyph.isEnabled()
    requests = []
    root.cameraResetRequested.connect(lambda: requests.append(1))
    mouse(card, QEvent.Type.MouseButtonPress, p, Qt.MouseButton.LeftButton, NONE)
    assert card.window._plain_orbit_pending is None
    mouse(card, QEvent.Type.MouseButtonRelease, p, Qt.MouseButton.LeftButton, NONE)
    assert requests == [1]
