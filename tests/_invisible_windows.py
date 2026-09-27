"""Show real windows in tests without them ever appearing on screen.

pytest runs on the real Windows QPA (Quick tests need GL), so a shown window
would flash on the operator's desktop.  A window passed through
:func:`keep_off_screen` is still genuinely shown, exposed and GPU-rendered,
and still receives synthetic (QTest) input, so a test measures exactly what it
did before.  It is just fully transparent, click-through, and a tool window
(no taskbar button).  Pixel reads use ``grabWindow()`` / ``grab()``, which
render the scene itself rather than reading the screen, so opacity does not
affect them.  (The same idea as the invisible real-saver measurements.)
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QWindow

# Inline copy for subprocess scripts that cannot import this module:
#   window.setOpacity(0.0); window.setFlag(Qt.WindowType.WindowTransparentForInput, True)
#   window.setFlag(Qt.WindowType.Tool, True)


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
