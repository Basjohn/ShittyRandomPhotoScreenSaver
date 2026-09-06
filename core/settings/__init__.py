"""Settings management for the screensaver application.

The package namespace stays intentionally lightweight so defaults/schema tooling can
import ``core.settings.*`` without pulling Qt/PySide into a headless process.
``SettingsManager`` remains available through a lazy compatibility export.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .settings_manager import SettingsManager as SettingsManager

__all__ = ["SettingsManager"]


def __getattr__(name: str) -> Any:
    if name == "SettingsManager":
        from .settings_manager import SettingsManager

        return SettingsManager
    raise AttributeError(name)
