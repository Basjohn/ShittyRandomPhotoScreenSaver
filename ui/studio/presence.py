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
"""
from __future__ import annotations

import sys
from typing import Callable

from core.logging.logger import get_logger

logger = get_logger(__name__)

_SW_HIDE = 0
_SW_SHOW = 5
_OFF_SCREEN = -30000


def _native_show(widget, command: int) -> bool:
    if sys.platform != "win32":
        return False
    import ctypes
    hwnd = int(widget.winId())
    if not hwnd:
        return False
    ctypes.windll.user32.ShowWindow(hwnd, command)
    return True


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

    def reveal(self) -> None:
        """Show the same window again, refreshed from canonical state, at its prior place and view."""
        if not self.concealed:
            return
        self.concealed = False
        widget = self._widget
        try:
            import shiboken6
            if not shiboken6.isValid(widget):
                return
        except ImportError:
            pass
        try:
            if self._refresh is not None:
                self._refresh()
        except Exception:
            logger.exception("[STUDIO] Settings refresh after the Studio failed")
        if self._natively_hidden:
            _native_show(widget, _SW_SHOW)
            self._natively_hidden = False
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
        if widget.isVisible():
            widget.raise_()
            widget.activateWindow()
        self.reveal_count += 1


__all__ = ["WindowPresence"]
