"""Native pointer facts of a Quick display window: the orbit gesture's short-lived capture/confinement, and the
one native arrow a retiring window gives Windows (``show_native_arrow_for_retiring_window``)."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import math
import sys

from PySide6.QtCore import QRectF


def physical_client_clip(rect: QRectF, logical_size, client_size, origin) -> tuple[int, int, int, int]:
    """Map local logical edges, never desktop coordinates, into native pixels."""
    width, height = logical_size
    pixels_x, pixels_y = client_size
    if min(width, height, pixels_x, pixels_y) <= 0:
        raise ValueError('Orbit confinement requires a nonempty client')
    clipped = rect.intersected(QRectF(0., 0., width, height))
    sx, sy = pixels_x / width, pixels_y / height
    left = math.ceil(clipped.left() * sx)
    top = math.ceil(clipped.top() * sy)
    right = math.floor(clipped.right() * sx)
    bottom = math.floor(clipped.bottom() * sy)
    if clipped.isEmpty() or right <= left or bottom <= top:
        raise ValueError('Orbit confinement has no interior device pixels')
    return origin[0] + left, origin[1] + top, origin[0] + right, origin[1] + bottom


class NativeOrbitCapture:
    """Own exactly one successful clip and Qt mouse grab; no process-global manager."""
    def __init__(self, window):
        if sys.platform != 'win32':
            raise RuntimeError('Native orbit confinement is implemented only for Windows')
        self.window = window
        self.hwnd = int(window.winId())
        self.clip = None
        self.grabbed = False
        self.api = ctypes.WinDLL('user32', use_last_error=True)
        for name, args, result in (
            ('GetClientRect', [wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
            ('ClientToScreen', [wintypes.HWND, ctypes.POINTER(wintypes.POINT)], wintypes.BOOL),
            ('GetClipCursor', [ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
            ('ClipCursor', [ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
            ('GetCapture', [], wintypes.HWND), ('GetForegroundWindow', [], wintypes.HWND),
            ('GetSystemMetrics', [ctypes.c_int], ctypes.c_int),
        ):
            function = getattr(self.api, name)
            function.argtypes, function.restype = args, result

    @staticmethod
    def _tuple(rect):
        return rect.left, rect.top, rect.right, rect.bottom

    def _checked(self, result, action):
        if not result:
            raise OSError(ctypes.get_last_error(), 'Orbit ' + action)

    @property
    def cleanup_pending(self) -> bool:
        return self.clip is not None or self.grabbed

    def acquire(self, card: QRectF):
        client, previous, origin = wintypes.RECT(), wintypes.RECT(), wintypes.POINT(0, 0)
        if int(self.api.GetForegroundWindow() or 0) != self.hwnd:
            raise RuntimeError('Orbit capture requires the foreground display window')
        capture = int(self.api.GetCapture() or 0)
        if capture and capture != self.hwnd:
            raise RuntimeError('Orbit declines an already-owned native mouse capture')
        self._checked(self.api.GetClientRect(self.hwnd, ctypes.byref(client)), 'GetClientRect failed')
        self._checked(self.api.ClientToScreen(self.hwnd, ctypes.byref(origin)), 'ClientToScreen failed')
        self._checked(self.api.GetClipCursor(ctypes.byref(previous)), 'GetClipCursor failed')
        desktop = (self.api.GetSystemMetrics(76), self.api.GetSystemMetrics(77))
        desktop += (desktop[0] + self.api.GetSystemMetrics(78), desktop[1] + self.api.GetSystemMetrics(79))
        if self._tuple(previous) != desktop:
            raise RuntimeError('Orbit declines confinement already owned by another operation')
        clip = physical_client_clip(card, (self.window.width(), self.window.height()),
                                    (client.right - client.left, client.bottom - client.top), (origin.x, origin.y))
        try:
            if not self.window.setMouseGrabEnabled(True):
                raise RuntimeError('Orbit Qt mouse capture failed')
            self.grabbed = True
            if int(self.api.GetCapture() or 0) != self.hwnd:
                raise RuntimeError('Orbit native mouse capture was not acquired')
            native = wintypes.RECT(*clip)
            self._checked(self.api.ClipCursor(ctypes.byref(native)), 'ClipCursor failed')
            self.clip = clip
        except Exception:
            self.release()
            raise

    def release(self):
        error = None
        try:
            if self.clip is not None:
                current = wintypes.RECT()
                self._checked(self.api.GetClipCursor(ctypes.byref(current)), 'GetClipCursor release failed')
                # Another owner may have replaced our clip after deactivation.
                if self._tuple(current) == self.clip:
                    self._checked(self.api.ClipCursor(None), 'ClipCursor release failed')
                # Clear only after successful release or proof it is foreign.
                self.clip = None
        except Exception as exc:
            error = exc
        finally:
            if self.grabbed:
                try:
                    if int(self.api.GetCapture() or 0) == self.hwnd:
                        self.window.setMouseGrabEnabled(False)
                        # Verify native ownership after release. Qt's return
                        # value alone is not proof that capture remains held.
                        if int(self.api.GetCapture() or 0) == self.hwnd:
                            raise RuntimeError('Orbit native mouse release failed')
                    self.grabbed = False
                except Exception as exc:
                    if error is None:
                        error = exc
        if error is not None:
            raise error


class QtOrbitCapture:
    """Non-Windows orbit capture: the Qt mouse grab only, without cursor confinement.

    Native confinement (ClipCursor) is Windows-only and Wayland forbids clients
    from confining the pointer, so off Windows the gesture keeps receiving
    motion through Qt's grab but the cursor is not clipped to the card.
    """

    def __init__(self, window):
        self.window = window
        self.grabbed = False

    @property
    def cleanup_pending(self) -> bool:
        return self.grabbed

    def acquire(self, card: QRectF):
        del card
        if not self.window.setMouseGrabEnabled(True):
            raise RuntimeError('Orbit Qt mouse capture failed')
        self.grabbed = True

    def release(self):
        if self.grabbed:
            self.window.setMouseGrabEnabled(False)
            self.grabbed = False


_IDC_ARROW = 32512
_GA_ROOT = 2
_RETIRE_API = None


def _retire_api():
    global _RETIRE_API
    if _RETIRE_API is None:
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        for name, args, result in (
            ('GetCursorPos', [ctypes.POINTER(wintypes.POINT)], wintypes.BOOL),
            ('WindowFromPoint', [wintypes.POINT], wintypes.HWND),
            ('GetAncestor', [wintypes.HWND, wintypes.UINT], wintypes.HWND),
            ('GetWindowThreadProcessId', [wintypes.HWND, ctypes.c_void_p], wintypes.DWORD),
            ('LoadCursorW', [wintypes.HINSTANCE, ctypes.c_void_p], wintypes.HANDLE),
            ('SetCursor', [wintypes.HANDLE], wintypes.HANDLE),
        ):
            function = getattr(user32, name)
            function.argtypes, function.restype = args, result
        kernel32.GetCurrentThreadId.argtypes, kernel32.GetCurrentThreadId.restype = [], wintypes.DWORD
        _RETIRE_API = (user32, kernel32)
    return _RETIRE_API


def show_native_arrow_for_retiring_window(hwnd: int) -> bool:
    """Make Windows itself display the arrow for a retiring display window (Windows only; R-183).

    ``QWindow.setCursor`` reaches Windows only when Qt's own window-under-mouse is that window
    (qwindowswindow.cpp ``applyNewCursor``); otherwise Qt stores the shape and applies it at the next
    ``WM_SETCURSOR``. A retiring window gets no next ``WM_SETCURSOR``: Windows does not re-query a still
    pointer when the windows under it hide, close or their process ends, so the last shape this GUI thread
    gave Windows (a link's pointing hand, the Halo, the blank cursor) stays on screen until the next mouse
    input. This one ``SetCursor(IDC_ARROW)`` on the GUI thread, while the window still exists, is that missing
    native instruction. It is shown only while this thread owns the cursor (the pointer is over its windows,
    or a shape it set is still frozen on screen); otherwise Windows ignores it. It is skipped while the pointer
    is over ANOTHER window of this GUI thread, which owns its own cursor.

    Returns True when the arrow was set. Off Windows nothing is needed (the window system resets the
    pointer when a surface unmaps) and the caller does not call it.
    """
    if not hwnd:
        return False
    user32, kernel32 = _retire_api()
    point = wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(point)):
        return False
    under = user32.WindowFromPoint(point)
    root = int((user32.GetAncestor(under, _GA_ROOT) if under else None) or under or 0)
    if root and root != int(hwnd) and user32.GetWindowThreadProcessId(root, None) == kernel32.GetCurrentThreadId():
        return False
    arrow = user32.LoadCursorW(None, ctypes.c_void_p(_IDC_ARROW))
    if not arrow:
        return False
    user32.SetCursor(arrow)
    return True


_QT_ORBIT_ANNOUNCED = False


def new_orbit_capture(window):
    """Return the platform's orbit capture owner for one gesture."""
    from core import platform_paths

    if platform_paths.IS_WINDOWS:
        return NativeOrbitCapture(window)
    global _QT_ORBIT_ANNOUNCED
    if not _QT_ORBIT_ANNOUNCED:
        _QT_ORBIT_ANNOUNCED = True
        from core.logging.logger import get_logger

        get_logger(__name__).info(
            '[PLATFORM] Orbit cursor confinement is Windows-only; orbit uses a Qt mouse grab without confinement'
        )
    return QtOrbitCapture(window)
