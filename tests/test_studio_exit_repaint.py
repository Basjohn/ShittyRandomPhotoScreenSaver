"""Leaving a Studio must leave Settings *painting*, not merely visible (operator, 6 Nov: "frozen and unclickable").

Settings is a frameless ``WA_TranslucentBackground`` window, which Qt presents as a *layered* window
(``UpdateLayeredWindow``). Layered windows never receive ``WM_PAINT``; Qt announces their exposure itself, but only
from a show it initiated. ``WindowPresence`` conceals and reveals Settings natively (``ShowWindow``) to keep the modal
loop alive, so Qt sees the native hide (expose -> empty) and never sees the native show: the QWindow stays *not
exposed*, every later ``update()`` is dropped before it reaches the backing store, and the window keeps accepting input
while its picture never changes. The operator's log shows exactly this: saves from the Visualizers tab for 25 s after a
clean reveal (``qt visible=True enabled=True``) and no GUI-thread stall.

Mechanism-level on purpose. The real ``SettingsDialog`` is NOT driven here: shown with an empty profile it raises the
guided-setup / "No Image Sources" popups (visible, not region-clipped) and its ``closeEvent`` can ``sys.exit``. The window
under test is a bare dialog with Settings' exact window recipe (``Dialog | FramelessWindowHint`` +
``WA_TranslucentBackground``, pinned to ``SettingsDialog._setup_window`` by a source test) and, for the acrylic case,
the same AccentPolicy call Settings makes. Its theme (light or dark) does not change the layered state, only the
backdrop tint, so the acrylic backdrop is the only theme-dependent variable.

Display safety: every window gets an empty window region before its first show (no pixels, no clicks), is a tool
window that does not accept focus, and a guard asserts via ``EnumWindows`` that this process never owns a visible
top-level window with a non-empty region. The Studio is the hidden offscreen surface.
"""
from __future__ import annotations

import inspect
import sys
import time

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="native Windows window state")

from PySide6.QtCore import QCoreApplication, QEvent, Qt  # noqa: E402

from tests.test_studio_exit_every_mode import _click_close  # noqa: E402


def _pump(times: int = 12) -> None:
    for _ in range(times):
        QCoreApplication.processEvents()
        time.sleep(0.01)


def _pump_until(condition, seconds: float = 1.5) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if condition():
            return True
        time.sleep(0.01)
    return bool(condition())


def _win32():
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32")
    gdi32.CreateRectRgn.restype = ctypes.c_void_p
    gdi32.CreateRectRgn.argtypes = [ctypes.c_int] * 4
    user32.SetWindowRgn.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.BOOL]
    user32.GetWindowRgn.argtypes = [wintypes.HWND, ctypes.c_void_p]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    return user32, gdi32


def visible_pixel_windows() -> list[int]:
    """Top-level windows of this process that are visible AND have pixels (anything but an empty window region)."""
    import ctypes
    import os
    from ctypes import wintypes
    user32, gdi32 = _win32()
    found: list[int] = []
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def check(hwnd, _lparam):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == os.getpid() and user32.IsWindowVisible(hwnd):
            region = gdi32.CreateRectRgn(0, 0, 0, 0)
            empty = user32.GetWindowRgn(hwnd, region) == 1                      # NULLREGION
            gdi32.DeleteObject(ctypes.c_void_p(region))
            if not empty:
                found.append(int(hwnd))
        return True
    user32.EnumWindows(proc(check), 0)
    return found


def make_invisible(widget) -> int:
    """No pixels, no clicks, never focused or topmost: an empty region (set before the first show) on a tool window."""
    widget.setWindowFlags(widget.windowFlags() | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
    hwnd = int(widget.winId())
    user32, gdi32 = _win32()
    assert user32.SetWindowRgn(hwnd, gdi32.CreateRectRgn(0, 0, 0, 0), False)
    return hwnd


class Native:
    def __init__(self, hwnd: int) -> None:
        self.hwnd = hwnd
        self.user32, _ = _win32()

    @property
    def visible(self) -> bool:
        return bool(self.user32.IsWindowVisible(self.hwnd))

    @property
    def layered(self) -> bool:
        return bool(self.user32.GetWindowLongW(self.hwnd, -20) & 0x80000)       # WS_EX_LAYERED


class Probe:
    """A bare window with Settings' window recipe, hidden by region, counting its content paints."""

    def __init__(self, *, translucent: bool = True, acrylic: bool = False) -> None:
        from PySide6.QtGui import QColor, QPainter
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget
        probe = self

        class Body(QWidget):
            def paintEvent(self, _event):  # noqa: N802 - Qt override
                probe.paints += 1
                QPainter(self).fillRect(self.rect(), QColor(200, 0, 0, 160))

        self.paints = 0
        self.dialog = QDialog()
        self.dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        if translucent:
            self.dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        QVBoxLayout(self.dialog).addWidget(body := Body())
        self.body = body
        self.dialog.resize(320, 200)
        # Focus and z-order are not what is under test, and nothing here may touch the operator's focus.
        self.dialog.raise_ = lambda: None
        self.dialog.activateWindow = lambda: None
        self.native = Native(make_invisible(self.dialog))
        if acrylic:
            from core.windows.dwm_blur import enable_acrylic_blur
            enable_acrylic_blur(self.native.hwnd, tint_r=20, tint_g=30, tint_b=40, tint_alpha=120)
        self.dialog.show()
        assert _pump_until(lambda: self.window.isExposed()), "the probe window never became exposed"
        assert visible_pixel_windows() == [], "the probe window shows pixels"

    @property
    def window(self):
        return self.dialog.windowHandle()

    def painted_after_update(self) -> bool:
        """A later content change (a saved setting) reaches the paint path."""
        self.paints = 0
        self.body.update()
        return _pump_until(lambda: self.paints > 0)

    def dispose(self) -> None:
        self.dialog.close()
        self.dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture(autouse=True)
def _no_visible_window_and_no_focus_theft(qt_app, monkeypatch):
    from ui.studio import presence
    from ui.studio.controller import StudioController

    def restore_without_focus(widget):
        """``_native_restore`` minus ``BringWindowToTop`` / ``SetForegroundWindow``: a test never takes focus."""
        user32, _ = _win32()
        hwnd = int(widget.winId())
        user32.ShowWindow(hwnd, presence._SW_SHOW)
        if not user32.IsWindowEnabled(hwnd) and widget.isEnabled():
            user32.EnableWindow(hwnd, True)
        return bool(user32.IsWindowVisible(hwnd)), bool(user32.IsWindowEnabled(hwnd))
    monkeypatch.setattr(presence, "_native_restore", restore_without_focus)
    assert visible_pixel_windows() == []
    yield
    active = StudioController.active()
    if active is not None:
        active.close()
    assert visible_pixel_windows() == [], "a test left a visible window with pixels on the operator's screen"


@pytest.fixture
def probe():
    made = []

    def make(**kwargs):
        made.append(Probe(**kwargs))
        return made[-1]
    yield make
    for item in made:
        item.dispose()


def test_the_probe_recipe_is_settings_own_window_recipe():
    """The bare window stands in for Settings only while Settings is still frameless and translucent."""
    from ui.settings_dialog import SettingsDialog
    source = inspect.getsource(SettingsDialog._setup_window)
    assert "Qt.WindowType.Dialog" in source and "Qt.WindowType.FramelessWindowHint" in source
    assert "WA_TranslucentBackground" in source


# ------------------------------------------------------------------------- the presence mechanism on a layered window
def _conceal_reveal(window) -> None:
    from ui.studio.presence import WindowPresence
    presence = WindowPresence(window.dialog)
    presence.conceal()
    _pump()
    assert not window.native.visible and not window.window.isExposed()          # Qt saw the native hide
    presence.reveal()
    _pump()
    assert visible_pixel_windows() == [], "the revealed window shows pixels"


@pytest.mark.parametrize("acrylic", [False, True], ids=["plain", "acrylic"])
def test_a_layered_window_is_exposed_and_paints_after_a_native_conceal_and_reveal(probe, acrylic):
    window = probe(acrylic=acrylic)
    assert window.native.layered
    _conceal_reveal(window)
    assert window.native.visible and window.dialog.isVisible()
    assert window.window.isExposed(), "Qt still thinks the revealed window is hidden"
    assert window.painted_after_update(), "a content change never reached the paint path"


def test_a_layered_window_without_the_re_expose_never_paints_negative_control(probe, monkeypatch):
    """The operator's stall: visible, enabled, accepting input, never repainting."""
    from ui.studio import presence
    monkeypatch.setattr(presence, "_native_reexpose", lambda widget: None)
    window = probe(acrylic=True)
    _conceal_reveal(window)
    assert window.native.visible and window.dialog.isVisible() and window.dialog.isEnabled()
    assert not window.window.isExposed()
    window.paints = 0
    window.body.update()
    _pump(25)
    assert window.paints == 0


def test_an_opaque_window_needed_no_re_expose_control(probe, monkeypatch):
    """Ordinary windows get ``WM_PAINT`` from Windows, which is why only the translucent Settings stalls."""
    from ui.studio import presence
    monkeypatch.setattr(presence, "_native_reexpose", lambda widget: None)
    window = probe(translucent=False)
    assert not window.native.layered
    _conceal_reveal(window)
    assert window.window.isExposed()          # Windows re-exposed it by itself: no Qt-side help was needed


# ------------------------------------------------------- every exit path of a real Studio session, real presence
def _studio_session(window):
    from ui.studio.controller import StudioController
    from ui.studio.presence import WindowPresence
    from ui.studio.surface import OffscreenStudioSurface
    from tests.test_waveform_studio_second_mode import ToyAdapter, ToyStore
    surfaces = []

    def factory(controller):
        surfaces.append(OffscreenStudioSurface(controller, size=(900, 600), present_on_show=False))
        return surfaces[-1]
    controller = StudioController(ToyAdapter(), ToyStore(), WindowPresence(window.dialog), factory)
    assert controller.open()
    surfaces[0].pump(3)
    assert controller.state == "presented" and controller.presence.concealed
    assert not window.native.visible and not window.window.isExposed()
    assert StudioController.active() is controller
    return controller, surfaces[0]


def _leave(controller, surface, path: str) -> None:
    if path == "close button":
        _click_close(surface)
    elif path == "escape":
        controller.bridge.requestCloseFrom("escape")                  # what the shell's Esc handler asks for
        _pump(5)
    elif path == "window close":
        surface.closeRequested.emit()                                 # the window X / Alt+F4
        _pump(5)
    elif path == "close()":
        controller.close()
    else:
        raise AssertionError(path)
    assert controller.state == "closed" and not controller.presence.concealed


@pytest.mark.parametrize("acrylic", [False, True], ids=["plain", "acrylic"])
@pytest.mark.parametrize("path", ["close button", "escape", "window close", "close()"])
def test_every_studio_exit_leaves_settings_exposed_and_repainting(probe, path, acrylic):
    window = probe(acrylic=acrylic)
    controller, surface = _studio_session(window)
    _leave(controller, surface, path)
    assert window.native.visible and window.dialog.isVisible() and window.dialog.isEnabled()
    assert window.window.isExposed(), f"Qt still thinks Settings is hidden after leaving by {path}"
    assert window.painted_after_update(), f"a content change never painted after leaving by {path}"


def test_a_studio_exit_without_the_re_expose_leaves_settings_stalled_negative_control(probe, monkeypatch):
    from ui.studio import presence
    monkeypatch.setattr(presence, "_native_reexpose", lambda widget: None)
    window = probe(acrylic=True)
    controller, surface = _studio_session(window)
    _leave(controller, surface, "close button")
    assert window.native.visible and window.dialog.isVisible() and window.dialog.isEnabled()
    assert not window.window.isExposed()
    window.paints = 0
    window.body.update()
    _pump(25)
    assert window.paints == 0


def test_the_reveal_log_names_the_exposure(probe, caplog):
    """The next field log shows at once whether Qt considered the window exposed after a reveal."""
    import logging
    window = probe()
    with caplog.at_level(logging.INFO):
        _conceal_reveal(window)
    revealed = [r.getMessage() for r in caplog.records if "Settings revealed" in r.getMessage()]
    assert revealed and "exposed=True" in revealed[-1]


# ------------------------------------------- the one-shot record of input after a reveal (6 Nov 21:56 post-close freeze)
def test_a_studio_exit_arms_a_one_shot_input_record_that_ends_with_the_first_input_to_settings(probe, caplog):
    """The field log after a close names the Qt/native window state at the reveal and when the Studio window is
    destroyed, then the first input Qt delivers to Settings and its delay; after that nothing is installed."""
    import logging
    from PySide6.QtTest import QTest
    window = probe(acrylic=True)
    with caplog.at_level(logging.INFO):
        controller, surface = _studio_session(window)
        _leave(controller, surface, "close button")
        watch = controller.presence.watch
        assert watch is not None and watch.active
        centre = window.body.mapTo(window.dialog, window.body.rect().center())
        QTest.mouseClick(window.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centre)
        assert watch.active                                   # armed until Settings paints after that input
        window.dialog.update()
        _pump()
        assert not watch.active
        settled = len(watch.records)
        QTest.mouseClick(window.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centre)
        window.dialog.update()
        _pump()
        assert len(watch.records) == settled                              # disarmed: nothing runs at rest
    lines = [r.getMessage() for r in caplog.records if "after reveal" in r.getMessage()]
    assert lines[0].split(" ms ", 1)[1].startswith("armed qt_exposed=")
    assert any("studio window destroyed" in line for line in lines)
    assert any("first input delivered to Settings: MouseButtonPress" in line for line in lines)
    assert "first Paint after the first input" in lines[-1]
    assert "native_disabled=False" in lines[0] and "native_visible=True" in lines[0]


def test_the_first_input_line_reports_whether_settings_repainted_since_the_reveal(probe, caplog):
    """The 6 Nov re-expose fix was proven only on a bare window, and the freeze came back that night: the record must
    say whether Settings repainted between the reveal and the first input, so the field log tells "input reached a
    Settings that never repainted" apart from "input never reached Settings"."""
    import logging
    from PySide6.QtTest import QTest
    window = probe(acrylic=True)
    with caplog.at_level(logging.INFO):
        controller, surface = _studio_session(window)
        _leave(controller, surface, "close button")
        watch = controller.presence.watch
        window.dialog.update()
        _pump()
        centre = window.body.mapTo(window.dialog, window.body.rect().center())
        QTest.mouseClick(window.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centre)
        watch.disarm()
    lines = [r.getMessage() for r in caplog.records if "after reveal" in r.getMessage()]
    final = next(line for line in lines if "first input delivered to Settings" in line)
    assert "first input delivered to Settings: MouseButtonPress (repaint since reveal: " in final
    assert "repaint since reveal: none" not in final, final
    assert any("first UpdateRequest on Settings since the reveal" in line or "first Paint on Settings since the reveal"
               in line for line in lines)


def test_a_watch_that_saw_no_repaint_reports_none_negative_control(probe, caplog):
    """Input with no repaint since the arm is reported as such (the freeze signature), not silently."""
    import logging
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent
    from ui.studio.presence import RevealWatch
    window = probe()
    with caplog.at_level(logging.INFO):
        watch = RevealWatch(window.dialog)
        press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(5, 5), QPointF(5, 5), Qt.MouseButton.LeftButton,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        watch._qt_input(window.dialog, press)
    assert watch.active                                       # still waiting for Settings to paint after the input
    assert "repaint since reveal: none" in watch.records[-1]
    watch.disarm()


def _reveal_without_pumping(window):
    """Conceal natively, then reveal; the Paint count is read before any event processing after the reveal."""
    from ui.studio.presence import WindowPresence
    presence = WindowPresence(window.dialog)
    presence.conceal()
    _pump()
    presence.reveal()
    painted = presence.watch._surface_counts.get("Paint", 0)
    presence.watch.disarm()
    return painted


def test_a_reveal_paints_settings_before_it_returns(probe):
    """7 Nov field logs: after a native show Settings kept its pre-Studio picture until a click (no Expose,
    UpdateRequest or Paint for 853 ms and 1577 ms, even with an asynchronous ``update()`` requested), and a late repaint
    swapped the stale picture for the current one. The reveal now repaints synchronously: Settings has painted the
    current state by the time ``reveal()`` returns, with no event loop in between."""
    window = probe(acrylic=True)
    assert _reveal_without_pumping(window) >= 1


def test_a_reveal_without_the_synchronous_repaint_paints_nothing_by_return_negative_control(probe, monkeypatch):
    """Without the repaint (or with only an asynchronous ``update()``) nothing has painted when the reveal returns."""
    from ui.studio import presence as presence_module
    window = probe(acrylic=True)
    monkeypatch.setattr(presence_module.WindowPresence, "repaint_revealed",
                        lambda self: self._widget.update())
    assert _reveal_without_pumping(window) == 0


def test_input_elsewhere_does_not_end_the_record_negative_control(probe):
    """Only input that reaches Settings ends the record: a click on another window leaves it armed."""
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QWidget
    window = probe()
    controller, surface = _studio_session(window)
    _leave(controller, surface, "close()")
    watch = controller.presence.watch
    other = QWidget()                                                  # never shown
    QTest.mouseClick(other, Qt.MouseButton.LeftButton)
    assert watch.active
    watch.disarm()
    assert not watch.active
    other.deleteLater()


def test_the_record_never_filters_another_windows_events(probe, monkeypatch):
    """The Qt filter sits on Settings' own window, never the application: an application-wide Python filter is handed
    every Qt Quick item an event visits, and wrapping items PySide had not wrapped yet deleted a live Studio item in a
    later test (7 Nov: test_waveform_studio_framing after test_waveform_studio_editors)."""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QWindow
    from PySide6.QtTest import QTest
    window = probe()
    controller, surface = _studio_session(window)
    _leave(controller, surface, "close()")
    watch = controller.presence.watch
    seen = []
    original = watch._guarded
    monkeypatch.setattr(watch, "_guarded", lambda action, *args: (seen.append(action.__name__),
                                                                   original(action, *args)))
    other = QWindow()                                                  # never shown
    QTest.mouseClick(other, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(5, 5))
    assert [name for name in seen if name == "_qt_input"] == [] and watch.active
    watch.disarm()
    other.deleteLater()
