"""Short-lived native mouse capture/confinement for the existing orbit gesture."""
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
