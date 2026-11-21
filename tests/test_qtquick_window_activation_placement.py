"""Clicking into the saver must not resize its placed display window (the focus-click black flicker).

Every application activation edge (``DisplayManager._on_application_state_changed``) revalidates each Quick window's
bound-screen geometry. That re-applied Qt's logical R-63 rect, which at a fractional DPR rounds to a different device
rect than the device-exact one the window was placed at (3840 x 2162 instead of 2163 at 150 %), so every click into
the saver resized the native window twice (Qt's rect, then the device-exact fix) and the swap chain showed a black
frame. A placed window is now left alone; a displaced one (the resume edge the revalidation exists for) is placed again.

The window's own methods run against a simulated native layer that rounds the way Qt's Windows platform does
(measured on a hidden window, evidence ``display/focus_flicker/20261121_activation_double_resize``); no window is
created or shown.
"""
from __future__ import annotations

import ctypes
import sys

import pytest
from PySide6.QtCore import QRect

from rendering.quick.device_geometry import compat_native_rect
from rendering.quick.window import QuickDisplayWindow

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="the native placement path is Windows-only")


def _qt_round(value: float) -> int:
    # Qt 6's qRound: half away from zero.
    return int(value + 0.5) if value >= 0 else -int(-value + 0.5)


class _Screen:
    """A 3840 x 2160 monitor at 150 % to the right of a 2560 x 1440 one at 150 % (the operator's Display 1)."""

    logical_origin = (2560, 0)
    device_origin = (2560, 0)
    dpr = 1.5

    def geometry(self) -> QRect:
        return QRect(2560, 0, 2560, 1440)

    def virtualGeometry(self) -> QRect:  # noqa: N802 (Qt name)
        return QRect(0, 0, 5120, 1440)

    def devicePixelRatio(self) -> float:  # noqa: N802 (Qt name)
        return self.dpr


_MONITOR = (2560, 0, 6400, 2160)
_VIRTUAL = (0, 0, 6400, 2160)

_BORROWED = (
    "revalidate_bound_screen_geometry",
    "_on_screen_metrics_changed",
    "_apply_screen_geometry",
    "_apply_native_compat_geometry",
    "_native_rects_expected",
    "_fullscreen_compat_geometry",
)
_OPTIONAL = ("_placement_is_current",)


def _window_class() -> type:
    namespace = {name: QuickDisplayWindow.__dict__[name] for name in _BORROWED}
    namespace.update({name: QuickDisplayWindow.__dict__[name] for name in _OPTIONAL if name in QuickDisplayWindow.__dict__})
    return type("_SimulatedDisplayWindow", (_NativeLayer,), namespace)


class _NativeLayer:
    """The Qt and Win32 facts the placement methods read and write, with Qt's Windows rounding."""

    def __init__(self) -> None:
        self._screen = _Screen()
        self._bound_screen = self._screen
        self._binding_loss = None
        self._close_queued = False
        self._screen_index = 1
        self._runtime_generation = 3
        self._compat_logical_rects: set[tuple[int, int, int, int]] = set()
        self.visible = False
        self.native = (0, 0, 0, 0)
        self.native_sizes: list[tuple[int, int]] = []  # every WM_SIZE the window would get

    # Qt ---------------------------------------------------------------
    def screen(self):
        return self._screen

    def isVisible(self) -> bool:  # noqa: N802 (Qt name)
        return self.visible

    def effectiveDevicePixelRatio(self) -> float:  # noqa: N802 (Qt name)
        return self._screen.dpr

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802 (Qt name)
        if rect.getRect() == self.geometry().getRect():
            return  # QWindow::setGeometry returns early on an unchanged rect
        (lx, ly), (dx, dy), dpr = self._screen.logical_origin, self._screen.device_origin, self._screen.dpr
        left = dx + _qt_round((rect.x() - lx) * dpr)
        top = dy + _qt_round((rect.y() - ly) * dpr)
        self._set_native((left, top, left + _qt_round(rect.width() * dpr), top + _qt_round(rect.height() * dpr)))

    def geometry(self) -> QRect:
        (lx, ly), (dx, dy), dpr = self._screen.logical_origin, self._screen.device_origin, self._screen.dpr
        left, top, right, bottom = self.native
        return QRect(
            lx + _qt_round((left - dx) / dpr),
            ly + _qt_round((top - dy) / dpr),
            _qt_round((right - left) / dpr),
            _qt_round((bottom - top) / dpr),
        )

    def cancel_plain_orbit(self) -> None:
        pass

    def refresh_display_identity(self):
        return None

    def _refresh_scene_rect(self, *_args) -> None:
        pass

    # Win32 -------------------------------------------------------------
    def _native_rects(self):
        return (1, self.native, _MONITOR, _VIRTUAL)

    def _set_native(self, rect: tuple[int, int, int, int]) -> None:
        old = self.native
        self.native = rect
        if (old[2] - old[0], old[3] - old[1]) != (rect[2] - rect[0], rect[3] - rect[1]):
            self.native_sizes.append((rect[2] - rect[0], rect[3] - rect[1]))


@pytest.fixture
def window(monkeypatch):
    shown = _window_class()()

    def set_window_pos(_hwnd, _after, x, y, cx, cy, _flags):
        shown._set_native((x, y, x + cx, y + cy))
        return True

    monkeypatch.setattr(ctypes.windll.user32, "SetWindowPos", set_window_pos)
    # The show path: placed while hidden, then the visible edge sets the device-exact rect.
    shown._apply_screen_geometry(shown._screen)
    shown.visible = True
    shown._apply_native_compat_geometry()
    assert shown.native == compat_native_rect(_MONITOR, _VIRTUAL, _Screen.dpr)
    shown.native_sizes.clear()
    return shown


def test_an_activation_edge_leaves_a_placed_window_unresized(window):
    placed = window.native
    window.revalidate_bound_screen_geometry()  # what every click into the saver runs
    assert window.native_sizes == []
    assert window.native == placed


def test_a_work_area_edge_leaves_a_placed_window_unresized(window):
    placed = window.native
    window._on_screen_metrics_changed()  # availableGeometryChanged (a taskbar edge)
    assert window.native_sizes == []
    assert window.native == placed


def test_a_displaced_window_is_placed_again(window):
    """The resume repair the revalidation exists for still runs."""
    window._set_native((2560, 0, 6400, 2160))  # Windows moved it to exact cover while asleep
    window.revalidate_bound_screen_geometry()
    assert window.native == compat_native_rect(_MONITOR, _VIRTUAL, _Screen.dpr)
