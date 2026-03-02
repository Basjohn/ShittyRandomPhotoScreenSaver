"""UI module for screensaver configuration."""

# Ensure compiled Qt resources (assets_rc) are registered before any stylesheets load.
from .resources import assets_rc  # noqa: F401
from .settings_dialog import SettingsDialog

__all__ = ['SettingsDialog']
