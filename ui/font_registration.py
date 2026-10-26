"""Application font registration without importing the QWidget settings stack."""
from __future__ import annotations

from PySide6.QtGui import QFontDatabase, QGuiApplication

from ui.resources.registration import ensure_core_resources


_JOST_FONT_PATHS = (
    ":/srpss/fonts/Jost-Regular.ttf",
    ":/srpss/fonts/Jost-SemiBold.ttf",
    ":/srpss/fonts/Jost-Bold.ttf",
)
_INTER_FONT_PATHS = (
    ":/srpss/fonts/Inter-VariableFont_opsz,wght.ttf",
    ":/srpss/fonts/Inter-Italic-VariableFont_opsz,wght.ttf",
)
_FONTS_REGISTERED = False
READABILITY_JOST_FAMILY = "SRPSS Jost Variable"
_READABILITY_FONTS_REGISTERED = False


def ensure_readability_fonts() -> None:
    """Register private light-only variants without changing Jost matching."""
    global _READABILITY_FONTS_REGISTERED
    if _READABILITY_FONTS_REGISTERED or QGuiApplication.instance() is None:
        return
    ensure_core_resources()
    for path in (":/srpss/fonts/Jost-Readability-Variable.ttf",
                 ":/srpss/fonts/Jost-Readability-Italic-Variable.ttf"):
        if QFontDatabase.addApplicationFont(path) < 0:
            raise RuntimeError(f"Could not register readability font: {path}")
    _READABILITY_FONTS_REGISTERED = True


def ensure_custom_fonts() -> None:
    """Register bundled fonts once after a QGuiApplication exists."""

    global _FONTS_REGISTERED
    if _FONTS_REGISTERED or QGuiApplication.instance() is None:
        return
    ensure_core_resources()
    for path in _JOST_FONT_PATHS:
        QFontDatabase.addApplicationFont(path)
    for path in _INTER_FONT_PATHS:
        QFontDatabase.addApplicationFont(path)
    _FONTS_REGISTERED = True


__all__ = ["ensure_custom_fonts", "ensure_readability_fonts", "READABILITY_JOST_FAMILY"]
