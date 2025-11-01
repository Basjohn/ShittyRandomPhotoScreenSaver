"""
Core settings management for the application.

This module provides centralized configuration management with support for:
- Type-safe settings with default values
- Persistent storage
- Change notifications
- Thread-safe access
"""

from .settings_manager import SettingsManager
from .types import SettingsCategory, SettingDefinition
from typing import Optional
from pathlib import Path

# Global singleton instance
_settings_manager: Optional[SettingsManager] = None

def get_settings_manager(settings_file: Optional[Path] = None) -> SettingsManager:
    """Get the global SettingsManager instance."""
    global _settings_manager
    if _settings_manager is None:
        if settings_file is None:
            # Use default settings file location
            settings_file = Path(__file__).parent.parent.parent / 'settings' / 'settings.json'
        _settings_manager = SettingsManager(settings_file=settings_file)
    return _settings_manager

# Public API
__all__ = ['SettingsManager', 'SettingsCategory', 'SettingDefinition', 'get_settings_manager']
