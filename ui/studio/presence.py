"""Conceal and reveal the originating Settings window without ending its lifetime.

Settings runs inside ``QDialog.exec()`` in the runtime. ``QDialog.hide()`` (any
``setVisible(False)``) exits that modal loop and so *closes* Settings. The window
is therefore concealed natively (``ShowWindow(SW_HIDE)``): Qt keeps the same
dialog object, page, scroll, preset slider and modal loop untouched, and
``reveal`` shows exactly that window again.

Off Windows there is no native hide that keeps Qt's modal loop (hiding the
QWindow also ends ``exec()``), so the window stays shown but invisible: zero
window opacity (every Wayland compositor and composited X11) plus a move off
screen (non-composited X11). ``reveal`` restores opacity and geometry.

A native show must also be followed by a native *re-expose*. Settings is a frameless translucent window, which Qt
presents as a layered window; a layered window never receives ``WM_PAINT``, and Qt announces its exposure only from
a show it initiated. Qt does see the native hide (the QWindow becomes not exposed) but not the native show, so without
the re-expose the QWindow stays unexposed, every ``update()`` is dropped and the window accepts input while its picture
never changes ("frozen and unclickable", 6 Nov). ``RedrawWindow(RDW_INVALIDATE | RDW_UPDATENOW)`` makes Windows send
the ``WM_PAINT`` that a layered window otherwise never gets, and Qt turns it into the missing expose and a full repaint.
"""
from __future__ import annotations

import sys
from typing import Callable

from core.logging.logger import get_logger

logger = get_logger(__name__)

_SW_HIDE = 0
_SW_SHOW = 5
_OFF_SCREEN = -30000
_RDW_INVALIDATE = 0x0001
_RDW_ALLCHILDREN = 0x0080
_RDW_UPDATENOW = 0x0100


def _native_show(widget, command: int) -> bool:
    if sys.platform != "win32":
        return False
    import ctypes
    hwnd = int(widget.winId())
    if not hwnd:
        return False
    ctypes.windll.user32.ShowWindow(hwnd, command)
    return True


def _native_restore(widget) -> tuple[bool, bool]:
    """Show, re-enable and bring the window forward natively; (visible, enabled) as Windows reports them.

    Re-enabling matters: Qt disables other top-level windows while an application-modal window is shown,
    and a modal window torn down out of order must never leave Settings disabled underneath."""
    import ctypes
    user32 = ctypes.windll.user32
    hwnd = int(widget.winId())
    if not hwnd:
        return False, False
    user32.ShowWindow(hwnd, _SW_SHOW)
    if not user32.IsWindowEnabled(hwnd) and widget.isEnabled():
        user32.EnableWindow(hwnd, True)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    return bool(user32.IsWindowVisible(hwnd)), bool(user32.IsWindowEnabled(hwnd))


def _native_reexpose(widget) -> None:
    """Make Qt expose (and so repaint) a window that was shown natively: see the module note on layered windows."""
    import ctypes
    from ctypes import wintypes
    hwnd = int(widget.winId())
    if not hwnd:
        return
    user32 = ctypes.windll.user32
    user32.RedrawWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
    user32.RedrawWindow.restype = wintypes.BOOL
    user32.RedrawWindow(hwnd, None, None, _RDW_INVALIDATE | _RDW_ALLCHILDREN | _RDW_UPDATENOW)


_WM_ACTIVATE = 0x0006
_WM_MOUSEACTIVATE = 0x0021
_WM_KEYDOWN = 0x0100
_WM_LBUTTONDOWN = 0x0201
_WM_RBUTTONDOWN = 0x0204
_WM_NCLBUTTONDOWN = 0x00A1
_WATCHED_MESSAGES = {_WM_ACTIVATE: "WM_ACTIVATE", _WM_MOUSEACTIVATE: "WM_MOUSEACTIVATE", _WM_KEYDOWN: "WM_KEYDOWN",
                     _WM_LBUTTONDOWN: "WM_LBUTTONDOWN", _WM_RBUTTONDOWN: "WM_RBUTTONDOWN",
                     _WM_NCLBUTTONDOWN: "WM_NCLBUTTONDOWN"}
_GWL_STYLE = -16
_WS_DISABLED = 0x08000000


def window_state(widget) -> str:
    """Qt's and Windows' view of ``widget``'s window: modality, activation, focus, enable and capture (one line)."""
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication, QWidget

    def name(window) -> str:
        if window is None:
            return "none"
        if widget is not None and window in (widget, widget.windowHandle()):
            return "settings"
        return type(window).__name__
    handle = widget.windowHandle() if widget is not None else None
    parts = [f"qt_exposed={handle.isExposed() if handle is not None else None}",
             f"qt_modal={name(QGuiApplication.modalWindow())}", f"qt_focus={name(QGuiApplication.focusWindow())}",
             f"qt_active={name(QApplication.activeWindow())}", f"qt_active_modal={name(QApplication.activeModalWidget())}",
             f"qt_popup={name(QApplication.activePopupWidget())}", f"qt_mouse_grab={name(QWidget.mouseGrabber())}",
             f"qt_override_cursor={QGuiApplication.overrideCursor() is not None}"]
    if sys.platform == "win32" and widget is not None:
        import ctypes
        user32 = ctypes.windll.user32
        user32.GetWindowLongW.restype = ctypes.c_long
        hwnd = int(widget.winId())

        def native(handle) -> str:
            return "none" if not handle else ("settings" if int(handle) == hwnd else f"0x{int(handle):x}")
        parts += [f"native_foreground={native(user32.GetForegroundWindow())}",
                  f"native_active={native(user32.GetActiveWindow())}", f"native_focus={native(user32.GetFocus())}",
                  f"native_capture={native(user32.GetCapture())}",
                  f"native_visible={bool(user32.IsWindowVisible(hwnd))}",
                  f"native_disabled={bool(user32.GetWindowLongW(hwnd, _GWL_STYLE) & _WS_DISABLED)}"]
    return " ".join(parts)


class RevealWatch:
    """One-shot record of what happens to input after a reveal (the 6 Nov 21:56 "frozen after closing the Studio",
    which recovered by itself after ~18 s while the process was idle).

    Armed on the reveal edge only and gone after the first input Qt delivers to Settings (or after ``limit_s``, checked
    on the next event): nothing runs at rest. While armed, it logs the first native button/key/activation messages
    (which window Windows sent them to, and Settings' native and Qt state at that moment) and the first input Qt
    delivers, with its delay since the reveal."""

    MAX_NATIVE_LINES = 12

    def __init__(self, widget, *, limit_s: float = 60.0) -> None:
        import time
        from PySide6.QtCore import QAbstractNativeEventFilter, QEvent, QObject
        from PySide6.QtWidgets import QApplication
        self._widget = widget
        self._armed_at = time.perf_counter()
        self._limit_s = float(limit_s)
        self._native_lines = 0
        self.records: list[str] = []
        self.active = True
        # Repaint since the reveal (the 6 Nov re-expose fix was proven only on a bare window): the first Expose,
        # UpdateRequest and Paint Settings receives are logged, and the first-input line reports their counts, so a
        # click into a Settings that never repainted is named outright.
        self._surface_counts: dict[str, int] = {}
        self._input_at_ms: float | None = None
        watch = self
        inputs = (QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress)
        surface_events = {QEvent.Type.Expose: "Expose", QEvent.Type.UpdateRequest: "UpdateRequest",
                          QEvent.Type.Paint: "Paint"}

        class _Qt(QObject):
            def eventFilter(self, obj, event):  # noqa: N802 - Qt override
                if watch.active:
                    kind = event.type()
                    if kind in inputs:
                        watch._guarded(watch._qt_input, obj, event)
                    elif kind in surface_events:
                        watch._guarded(watch._surface, surface_events[kind])
                return False

        class _Native(QAbstractNativeEventFilter):
            def nativeEventFilter(self, event_type, message):  # noqa: N802 - Qt override
                if watch.active:
                    watch._guarded(watch._native, event_type, message)
                return False, 0

        self._app = QApplication.instance()
        self._qt_filter = _Qt()
        self._native_filter = _Native()
        # On Settings' own window only, never the application: every input to Settings reaches its QWindow first,
        # and an application-wide Python filter is handed every Qt Quick item an event visits (wrapping items PySide
        # had not wrapped yet deleted a live Studio item in a later test, 7 Nov).
        self._window = widget.windowHandle()
        if self._window is not None:
            self._window.installEventFilter(self._qt_filter)
        widget.installEventFilter(self._qt_filter)       # Settings' own top level: its Paint and posted UpdateRequests
        if sys.platform == "win32":
            self._app.installNativeEventFilter(self._native_filter)
        widget.destroyed.connect(self.disarm)          # Settings gone: nothing left to watch
        self._log(f"armed {window_state(widget)}")

    def _guarded(self, action, *args) -> None:
        """A diagnostic never raises into Qt's event loop: any failure (Settings deleted mid-watch) disarms it."""
        try:
            import shiboken6
            if not shiboken6.isValid(self._widget):
                self.disarm()
                return
            action(*args)
        except Exception:
            self.disarm()

    def _elapsed_ms(self) -> float:
        import time
        return (time.perf_counter() - self._armed_at) * 1000.0

    def _log(self, text: str) -> None:
        line = f"[STUDIO] after reveal +{self._elapsed_ms():.0f} ms {text}"
        self.records.append(line)
        logger.info(line)

    def _expired(self) -> bool:
        if self._elapsed_ms() / 1000.0 <= self._limit_s:
            return False
        self._log("watch expired without input reaching Settings" if self._input_at_ms is None
                  else "watch expired: Settings never painted after the first input")
        self.disarm()
        return True

    def _surface(self, name: str) -> None:
        if self._expired():
            return
        count = self._surface_counts.get(name, 0) + 1
        self._surface_counts[name] = count
        if count == 1:
            self._log(f"first {name} on Settings since the reveal")
        if name == "Paint" and self._input_at_ms is not None:
            # The 7 Nov field log: a click reached a Settings that never repainted. This line is how long the
            # picture stayed stale after the user's first click; the record ends here.
            self._log(f"first Paint after the first input (+{self._elapsed_ms() - self._input_at_ms:.0f} ms after it)"
                      f" {window_state(self._widget)}")
            self.disarm()

    def _qt_input(self, obj, event) -> None:
        if self._expired() or self._input_at_ms is not None:
            return
        repaint = ", ".join(f"{name} x{count}" for name, count in sorted(self._surface_counts.items())) or "none"
        self._log(f"first input delivered to Settings: {event.type().name} (repaint since reveal: {repaint})")
        self._input_at_ms = self._elapsed_ms()          # armed until Settings paints after it (or the limit)

    def _native(self, event_type, message) -> None:
        if self._expired() or self._native_lines >= self.MAX_NATIVE_LINES:
            return
        if bytes(event_type) not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            return
        import ctypes
        from ctypes import wintypes
        msg = wintypes.MSG.from_address(int(message))
        name = _WATCHED_MESSAGES.get(int(msg.message))
        if name is None:
            return
        self._native_lines += 1
        hwnd = int(msg.hWnd or 0)
        target = "settings" if self._widget is not None and hwnd == int(self._widget.winId()) else f"0x{hwnd:x}"
        self._log(f"native {name} to {target} {window_state(self._widget)}")

    def note(self, text: str) -> None:
        """A teardown edge after the reveal (the Studio window's destruction): log the state there, while armed."""
        if self.active:
            self._guarded(lambda: self._expired() or self._log(f"{text} {window_state(self._widget)}"))

    def disarm(self, *_args) -> None:
        if not self.active:
            return
        self.active = False
        try:
            import shiboken6
            if self._window is not None and shiboken6.isValid(self._window):
                self._window.removeEventFilter(self._qt_filter)
            if self._widget is not None and shiboken6.isValid(self._widget):
                self._widget.removeEventFilter(self._qt_filter)
            if sys.platform == "win32":
                self._app.removeNativeEventFilter(self._native_filter)
        except RuntimeError:
            pass


class WindowPresence:
    """One concealment of one top-level widget, restored to the same instance."""

    def __init__(self, widget, *, capture_view: Callable[[], object] | None = None,
                 restore_view: Callable[[object], None] | None = None,
                 refresh: Callable[[], None] | None = None) -> None:
        self._widget = widget
        self._capture_view = capture_view
        self._restore_view = restore_view
        self._refresh = refresh
        self.concealed = False
        self._natively_hidden = False
        self._soft_hidden_opacity: float | None = None
        self._geometry = None
        self._view = None
        self.reveal_count = 0
        self.watch: RevealWatch | None = None     # the one-shot input record of the last reveal

    @property
    def widget(self):
        return self._widget

    def conceal(self) -> None:
        if self.concealed:
            return
        widget = self._widget
        self._geometry = widget.geometry()
        self._view = self._capture_view() if self._capture_view is not None else None
        self._natively_hidden = bool(widget.isVisible()) and _native_show(widget, _SW_HIDE)
        if widget.isVisible() and not self._natively_hidden and sys.platform != "win32":
            self._soft_hidden_opacity = float(widget.windowOpacity())
            widget.setWindowOpacity(0.0)
            widget.move(_OFF_SCREEN, _OFF_SCREEN)
        self.concealed = True
        logger.info("[STUDIO] Settings concealed (native=%s)", self._natively_hidden)

    def reveal(self) -> None:
        """Show the same window again, refreshed from canonical state, at its prior place and view.

        Idempotent; every step after the native show is best-effort, so a failing refresh or view restore
        can never keep Settings hidden."""
        if not self.concealed:
            return
        self.concealed = False
        widget = self._widget
        try:
            import shiboken6
            if not shiboken6.isValid(widget):
                logger.info("[STUDIO] Settings is gone; nothing to reveal")
                return
        except ImportError:
            pass
        try:
            if self._refresh is not None:
                self._refresh()
        except Exception:
            logger.exception("[STUDIO] Settings refresh after the Studio failed")
        native = None
        if self._natively_hidden:
            self._natively_hidden = False
            try:
                native = _native_restore(widget)
            except Exception:
                logger.exception("[STUDIO] Native Settings restore failed; falling back to ShowWindow")
                _native_show(widget, _SW_SHOW)
            try:
                _native_reexpose(widget)
            except Exception:
                logger.exception("[STUDIO] Settings re-expose after the native show failed")
        if self._soft_hidden_opacity is not None:
            widget.setWindowOpacity(self._soft_hidden_opacity)
            self._soft_hidden_opacity = None
        if self._geometry is not None and widget.geometry() != self._geometry:
            widget.setGeometry(self._geometry)
        if self._restore_view is not None:
            try:
                self._restore_view(self._view)
            except Exception:
                logger.exception("[STUDIO] Settings view restore failed")
        if not widget.isEnabled():
            widget.setEnabled(True)
        if widget.isVisible():
            widget.raise_()
            widget.activateWindow()
        self.reveal_count += 1
        window = widget.windowHandle()
        logger.info("[STUDIO] Settings revealed (qt visible=%s enabled=%s exposed=%s native=%s)",
                    widget.isVisible(), widget.isEnabled(), window.isExposed() if window is not None else None, native)
        try:
            self.watch = RevealWatch(widget)              # armed first, so it sees the reveal's own repaint
        except Exception:
            logger.exception("[STUDIO] Reveal input watch unavailable")
        self.repaint_revealed()

    def repaint_revealed(self) -> None:
        """Repaint the revealed window NOW (synchronously). The native show puts back Settings' last layered picture,
        from before the Studio; a layered window never receives WM_PAINT, and an asynchronous ``update()`` can be
        dropped after the native hide/show (7 Nov field logs: a click 853 ms and 1577 ms after a reveal with no Expose,
        UpdateRequest or Paint since, even with ``update()`` requested). Until something repainted, Settings showed the
        stale picture (the "freeze"); a late repaint swapped it for the current one (a visible jump). ``repaint()``
        paints and flushes the current state inside the reveal. Called at the reveal and when the Studio window is
        gone."""
        widget = self._widget
        try:
            import shiboken6
            if widget is not None and shiboken6.isValid(widget) and widget.isVisible():
                widget.repaint()
        except Exception:
            logger.exception("[STUDIO] Settings repaint failed")


__all__ = ["WindowPresence"]
