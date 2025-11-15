"""
Settings manager implementation for screensaver.

Uses QSettings for persistent storage. Simplified from SPQDocker reusable modules.
"""
from typing import Any, Callable, Dict, List
import threading
from PySide6.QtCore import QSettings, QObject, Signal
from core.logging.logger import get_logger

logger = get_logger('SettingsManager')


class SettingsManager(QObject):
    """
    Centralized settings management for the screensaver.
    
    Uses QSettings for persistent storage with organization/application name.
    Thread-safe with change notifications.
    """
    
    # Signal emitted when settings change
    settings_changed = Signal(str, object)  # key, new_value
    
    def __init__(self, organization: str = "ShittyRandomPhotoScreenSaver", 
                 application: str = "Screensaver"):
        """
        Initialize the settings manager.
        
        Args:
            organization: Organization name for QSettings
            application: Application name for QSettings
        """
        super().__init__()
        
        self._settings = QSettings(organization, application)
        self._lock = threading.RLock()
        self._change_handlers: Dict[str, List[Callable]] = {}
        
        # Initialize defaults
        self._set_defaults()
        
        logger.info("SettingsManager initialized")
    
    def _set_defaults(self) -> None:
        """Set default values if not already present."""
        defaults = {
            # Sources
            'sources.folders': [],
            'sources.rss_feeds': [],
            'sources.mode': 'folders',  # 'folders' | 'rss' | 'both'
            
            # Display
            'display.mode': 'fill',  # 'fill' | 'fit' | 'shrink'
            'display.pan_scan_enabled': False,
            'display.pan_scan_speed': 1.0,
            'display.pan_scan_zoom': 1.3,
            'display.refresh_sync': True,
            'display.prefer_triple_buffer': True,
            'display.gl_depth_bits': 24,
            'display.gl_stencil_bits': 8,
            'display.render_backend_mode': 'opengl',
            
            # Transitions
            'transitions.type': 'crossfade',  # 'crossfade' | 'slide' | 'diffuse' | 'block_puzzle'
            'transitions.duration': 1.0,
            'transitions.block_puzzle_grid': (6, 6),
            'transitions.slide_direction': 'left',
            'transitions.diffuse_block_size': 10,
            
            # Timing
            'timing.image_duration': 5.0,
            
            # Widgets - Clock
            'widgets.clock_enabled': True,
            'widgets.clock_format': '24h',
            'widgets.clock_timezone': 'local',
            'widgets.clock_position': 'top-right',
            'widgets.clock_transparency': 0.8,
            'widgets.clock_multiple': False,
            'widgets.clock_timezones': [],
            
            # Widgets - Weather
            'widgets.weather_enabled': False,
            'widgets.weather_location': '',
            'widgets.weather_position': 'top-left',
            'widgets.weather_transparency': 0.8,
            
            # Multi-monitor
            'multi_monitor.mode': 'same',  # 'same' | 'different'
        }
        
        for key, value in defaults.items():
            if not self._settings.contains(key):
                self._settings.setValue(key, value)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value.
        
        Args:
            key: Setting key in dot notation (e.g., 'sources.mode')
            default: Default value if key not found
        
        Returns:
            Setting value or default
        """
        with self._lock:
            return self._settings.value(key, default)
    
    @staticmethod
    def to_bool(value: Any, default: bool = False) -> bool:
        """Normalize a stored setting value to bool.
        
        Accepts common string forms ("true", "1", "yes", "on") as True and
        ("false", "0", "no", "off") as False. Falls back to bool(value) or
        the provided default when the value cannot be interpreted.
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ("true", "1", "yes", "on"):
                return True
            if v in ("false", "0", "no", "off"):
                return False
            return default
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return bool(value)
        return bool(value)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Convenience wrapper around get() that normalizes to bool."""
        raw = self.get(key, default)
        return self.to_bool(raw, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a setting value.
        
        Args:
            key: Setting key in dot notation
            value: Value to set
        """
        with self._lock:
            old_value = self._settings.value(key)
            self._settings.setValue(key, value)
            
            # Emit change signal
            self.settings_changed.emit(key, value)
            
            # Call registered handlers
            if key in self._change_handlers:
                for handler in self._change_handlers[key]:
                    try:
                        handler(value, old_value)
                    except Exception as e:
                        logger.error(f"Error in change handler for {key}: {e}")
        
        logger.debug("Setting changed: %s: %r -> %r", key, old_value, value)
    
    def save(self) -> None:
        """Force save settings to persistent storage."""
        with self._lock:
            self._settings.sync()
        logger.debug("Settings saved")
    
    def load(self) -> None:
        """Load settings from persistent storage."""
        # QSettings loads automatically, but we can force sync
        with self._lock:
            self._settings.sync()
        logger.debug("Settings loaded")
    
    def on_changed(self, key: str, handler: Callable[[Any, Any], None]) -> None:
        """
        Register a handler for when a specific setting changes.
        
        Args:
            key: Setting key to watch
            handler: Callback function(new_value, old_value)
        """
        with self._lock:
            if key not in self._change_handlers:
                self._change_handlers[key] = []
            self._change_handlers[key].append(handler)
        
        logger.debug(f"Registered change handler for {key}")
    
    def reset_to_defaults(self) -> None:
        """Reset all settings to default values."""
        with self._lock:
            self._settings.clear()
            self._set_defaults()
            self._settings.sync()
        
        logger.info("Settings reset to defaults")
        self.settings_changed.emit('*', None)  # Signal that all changed
    
    def get_all_keys(self) -> List[str]:
        """Get all setting keys."""
        with self._lock:
            return self._settings.allKeys()
    
    def contains(self, key: str) -> bool:
        """Check if a setting key exists."""
        with self._lock:
            return self._settings.contains(key)
    
    def remove(self, key: str) -> None:
        """Remove a setting key."""
        with self._lock:
            self._settings.remove(key)
        logger.debug(f"Removed setting: {key}")
    
    def clear(self) -> None:
        """Clear all settings (use with caution)."""
        with self._lock:
            self._settings.clear()
        logger.warning("All settings cleared")
