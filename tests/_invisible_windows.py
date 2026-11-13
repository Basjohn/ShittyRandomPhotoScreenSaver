"""Show real windows in tests without them ever appearing on screen.

pytest runs on the real Windows QPA (Quick tests need GL), so a shown window
would flash on the operator's desktop.  A window passed through
:func:`keep_off_screen` is still genuinely shown, exposed and GPU-rendered,
and still receives synthetic (QTest) input, so a test measures exactly what it
did before.  It is just fully transparent, click-through, and a tool window
(no taskbar button).  Pixel reads use ``grabWindow()`` / ``grab()``, which
render the scene itself rather than reading the screen, so opacity does not
affect them.  (The same idea as the invisible real-saver measurements.)
Wait for its exposure with ``qtbot.waitUntil(window.isExposed)``:
``QTest.qWaitForWindowExposed`` never returned for a zero-opacity window.

This module is the one place that says how a test may show a window;
``tests/test_no_visible_test_windows.py`` derives what it accepts from it:

- its public functions (the helpers below), applied to the window before it is shown;
- the inline copy of :func:`keep_off_screen` (its zero-opacity call on the window) for subprocess scripts that
  cannot import this module;
- ``Qt.WidgetAttribute.WA_DontShowOnScreen`` (:data:`NEVER_ON_SCREEN_ATTRIBUTE`) when the test needs a shown widget
  but no native window at all;
- a subprocess script that runs on the offscreen platform (:data:`OFFSCREEN_PLATFORM`);
- for Tk, whose top-levels are mapped the moment they are constructed: :func:`keep_tk_off_screen` on the new window.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QWindow

# Inline copy for subprocess scripts that cannot import this module:
#   window.setOpacity(0.0); window.setFlag(Qt.WindowType.WindowTransparentForInput, True)
#   window.setFlag(Qt.WindowType.Tool, True)

#: A widget shown with this attribute is laid out and "visible" to Qt but has no native window.
NEVER_ON_SCREEN_ATTRIBUTE = "WA_DontShowOnScreen"
#: ``QT_QPA_PLATFORM`` for a subprocess whose windows never reach a real screen.
OFFSCREEN_PLATFORM = "offscreen"
#: The alpha a Tk window keeps under :func:`keep_tk_off_screen` (a name, not a literal: the scanner reads zero-literal
#: calls in these helpers as Qt opacity routes, and ``attributes`` must not become one).
_TK_TRANSPARENT = 0.0


def keep_off_screen(window):
    """Make a QWindow/top-level QWidget invisible and click-through; returns it."""
    if isinstance(window, QWindow):
        window.setOpacity(0.0)
        window.setFlag(Qt.WindowType.WindowTransparentForInput, True)
        window.setFlag(Qt.WindowType.Tool, True)
    else:
        window.setWindowOpacity(0.0)
        window.setWindowFlag(Qt.WindowType.WindowTransparentForInput, True)
        window.setWindowFlag(Qt.WindowType.Tool, True)
    return window


def keep_tk_off_screen(window):
    """Make a Tk top-level (``tk.Tk()``/``tk.Toplevel()``) invisible for the rest of its life; returns it.

    Withdrawn now and fully transparent from then on: a later ``attributes("-alpha", x)`` from the code under test
    (the Build Foundry maps itself at alpha 0, then restores 1.0) is held at transparent, so mapping it shows no
    pixels. A test that maps the window also places it off every monitor (the Build Foundry clamps itself into its
    ``_work_area``, so the test translates that area past the virtual screen).
    """
    window.withdraw()
    set_attributes = window.attributes

    def attributes(*args):
        if len(args) >= 2 and args[0] == "-alpha":
            args = ("-alpha", _TK_TRANSPARENT, *args[2:])
        return set_attributes(*args)

    window.attributes = attributes
    window.wm_attributes = attributes
    window.attributes("-alpha", _TK_TRANSPARENT)
    return window


def keep_off_screen_unlayered(widget) -> int:
    """Windows only: no pixels, no clicks, never focused or topmost, and NOT a layered window.

    For a test whose subject is the native window state itself (layered or not, exposed or not), where the zero
    opacity of :func:`keep_off_screen` would make the window layered and change what is measured: an empty window
    region (set before the first show) on a tool window that does not accept focus. Returns the native handle.
    """
    import ctypes
    from ctypes import wintypes

    widget.setWindowFlags(widget.windowFlags() | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
    hwnd = int(widget.winId())
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32")
    gdi32.CreateRectRgn.restype = ctypes.c_void_p
    gdi32.CreateRectRgn.argtypes = [ctypes.c_int] * 4
    user32.SetWindowRgn.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.BOOL]
    assert user32.SetWindowRgn(hwnd, gdi32.CreateRectRgn(0, 0, 0, 0), False)
    return hwnd
