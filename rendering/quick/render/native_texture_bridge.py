"""Adopt an existing OpenGL texture as a Qt scenegraph texture (PR-04).

The transition host has already uploaded the destination image to the GPU when a
transition ends. Wrapping that texture lets the retained background show it
without uploading the same pixels a second time.

PySide6 binds no native texture adoption API: ``QRhiTexture::createFrom`` and
``QNativeInterface::QSGOpenGLTexture::fromNative`` are absent from every
release (neither ``QRhiTexture::NativeTexture`` nor the Quick native interfaces
are in its typesystems). This module makes exactly that one call into the
``Qt6Quick`` module the process has already loaded -- found by module handle on
Windows and with ``RTLD_NOLOAD`` on Linux, so a second copy of Qt can never be
loaded -- and returns a non-owning Python wrapper. It owns no texture, cache, thread, timer or context.

Ownership contract (Qt 6): the returned ``QSGTexture`` wraps the GL name but
never deletes it; the caller keeps the GL allocation alive while the wrapper
can render and deletes it only after the wrapper is gone.
"""
from __future__ import annotations

import ctypes
import sys

from PySide6.QtGui import QOpenGLContext
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface, QSGTexture
import shiboken6

# public: static class QSGTexture * __cdecl QNativeInterface::QSGOpenGLTexture::fromNative(
#     unsigned int, class QQuickWindow *, class QSize const &,
#     class QFlags<enum QQuickWindow::CreateTextureOption>)   -- Qt 6.x, MSVC x64
_FROM_NATIVE = (
    "?fromNative@QSGOpenGLTexture@QNativeInterface@@SAPEAVQSGTexture@@"
    "IPEAVQQuickWindow@@AEBVQSize@@V?$QFlags@W4CreateTextureOption@QQuickWindow@@@@@Z"
)


# The same function as exported by libQt6Quick.so.6 (Itanium mangling). Its QFlags
# argument is a trivially copyable int wrapper, passed in a register like the c_int.
_FROM_NATIVE_LINUX = (
    "_ZN16QNativeInterface16QSGOpenGLTexture10fromNativeEjP12QQuickWindowRK5QSize"
    "6QFlagsINS1_19CreateTextureOptionEE"
)


class NativeTextureUnavailable(RuntimeError):
    """Adoption is not possible here; the caller uploads instead (attributed)."""


class _QSize(ctypes.Structure):
    _fields_ = [("wd", ctypes.c_int), ("ht", ctypes.c_int)]


_function = None
_unavailable: str | None = None


def _bind():
    global _function, _unavailable
    if _function is not None:
        return _function
    if _unavailable is not None:
        raise NativeTextureUnavailable(_unavailable)
    try:
        if sys.platform == "win32":
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetModuleHandleW.restype = ctypes.c_void_p
            kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
            handle = kernel32.GetModuleHandleW("Qt6Quick.dll")
            if not handle:
                raise NativeTextureUnavailable("Qt6Quick.dll is not loaded in this process")
            module = ctypes.WinDLL("Qt6Quick.dll", handle=handle)
            symbol = _FROM_NATIVE
        elif sys.platform.startswith("linux"):
            import os

            try:
                module = ctypes.CDLL("libQt6Quick.so.6", mode=os.RTLD_NOLOAD | os.RTLD_LAZY)
            except OSError as exc:
                raise NativeTextureUnavailable("libQt6Quick.so.6 is not loaded in this process") from exc
            symbol = _FROM_NATIVE_LINUX
        else:
            raise NativeTextureUnavailable(f"native texture adoption is not bound for {sys.platform}")
        try:
            function = getattr(module, symbol)
        except AttributeError as exc:
            raise NativeTextureUnavailable("QSGOpenGLTexture::fromNative is not exported") from exc
        function.restype = ctypes.c_void_p
        function.argtypes = [ctypes.c_uint, ctypes.c_void_p, ctypes.POINTER(_QSize), ctypes.c_int]
    except NativeTextureUnavailable as exc:
        _unavailable = str(exc)
        raise
    _function = function
    return function


def wrap_gl_texture(
    texture_id: int,
    window: QQuickWindow,
    pixel_size: tuple[int, int],
    *,
    options: QQuickWindow.CreateTextureOption = QQuickWindow.CreateTextureOption.TextureIsOpaque,
) -> QSGTexture:
    """Wrap ``texture_id`` (current context, RGBA8; opaque unless ``options`` says otherwise)
    for ``window``'s scenegraph.

    Must run on the window's render thread with its OpenGL context current
    (Quick's sync or render phase). Raises ``NativeTextureUnavailable``.
    """
    function = _bind()
    api = window.rendererInterface().graphicsApi()
    if api != QSGRendererInterface.GraphicsApi.OpenGL:
        raise NativeTextureUnavailable(f"scenegraph graphics API is {api.name}, not OpenGL")
    if QOpenGLContext.currentContext() is None:
        raise NativeTextureUnavailable("no current OpenGL context")
    width, height = (int(pixel_size[0]), int(pixel_size[1]))
    if texture_id <= 0 or width <= 0 or height <= 0:
        raise NativeTextureUnavailable("invalid texture name or size")
    size = _QSize(width, height)
    pointer = function(int(texture_id), shiboken6.getCppPointer(window)[0],
                       ctypes.byref(size), int(options.value))
    if not pointer:
        raise NativeTextureUnavailable("fromNative returned no texture")
    return shiboken6.wrapInstance(pointer, QSGTexture)


__all__ = ["NativeTextureUnavailable", "wrap_gl_texture"]
