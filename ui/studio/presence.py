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


__all__ = ["WindowPresence"]
