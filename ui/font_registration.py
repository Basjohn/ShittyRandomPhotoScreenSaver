"""Application font registration without importing the QWidget settings stack."""
from __future__ import annotations

from PySide6.QtGui import QFontDatabase, QGuiApplication

# Register the compiled Qt resources without importing Settings/QWidget modules.
try:  # pragma: no cover - defensive resource import
    from ui.resources import assets_rc  # noqa: F401
except Exception:  # pragma: no cover
    assets_rc = None  # type: ignore


_JOST_FONT_PATHS = (
    ":/ui/assets/fonts/Jost-Regular.ttf",
    ":/ui/assets/fonts/Jost-SemiBold.ttf",
    ":/ui/assets/fonts/Jost-Bold.ttf",
)
_INTER_FONT_PATHS = (
    ":/ui/assets/fonts/Inter-VariableFont_opsz,wght.ttf",
    ":/ui/assets/fonts/Inter-Italic-VariableFont_opsz,wght.ttf",
)
_FONTS_REGISTERED = False


def ensure_custom_fonts() -> None:
    """Register bundled fonts once after a QGuiApplication exists."""

    global _FONTS_REGISTERED
    if _FONTS_REGISTERED or QGuiApplication.instance() is None:
        return
    for path in _JOST_FONT_PATHS:
        QFontDatabase.addApplicationFont(path)
    for path in _INTER_FONT_PATHS:
        QFontDatabase.addApplicationFont(path)
    _FONTS_REGISTERED = True


__all__ = ["ensure_custom_fonts"]
