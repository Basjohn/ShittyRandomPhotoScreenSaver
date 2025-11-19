"""
Settings manager implementation for screensaver.

Uses QSettings for persistent storage. Simplified from SPQDocker reusable modules.
"""
from typing import Any, Callable, Dict, List, Mapping
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

        # Diagnostic snapshot so widget enable/monitor issues can be traced
        # without guessing what QSettings returned on this machine.
        try:
            widgets_snapshot = self._settings.value('widgets', None)
            logger.debug("Widgets snapshot on init: %r", widgets_snapshot)
        except Exception:
            logger.debug("Failed to read widgets snapshot on init", exc_info=True)

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
            'display.hw_accel': True,
            'display.refresh_sync': True,
            'display.prefer_triple_buffer': True,
            'display.gl_depth_bits': 24,
            'display.gl_stencil_bits': 8,
            'display.render_backend_mode': 'opengl',
            'display.pan_and_scan': False,
            'display.pan_auto_speed': True,
            'display.pan_speed': 3.0,
            'display.sharpen_downscale': False,
            'display.same_image_all_monitors': False,

            # Timing / queue
            'timing.interval': 10,
            'queue.shuffle': True,

            # Transitions (canonical nested config)
            'transitions': {
                'type': 'Wipe',
                'duration_ms': 1300,
                'easing': 'Auto',
                'direction': 'Random',
                'random_always': False,
                'block_flip': {
                    'rows': 4,
                    'cols': 6,
                },
                'diffuse': {
                    'block_size': 50,
                    'shape': 'Rectangle',
                },
                'slide': {
                    'direction': 'Random',
                },
                'wipe': {
                    'direction': 'Random',
                },
            },

            # Widgets (canonical nested config). The actual stored "widgets"
            # map is merged with these defaults in _set_defaults so that
            # missing keys are filled in without overwriting existing user
            # choices.
            'widgets': {
                'clock': {
                    'enabled': True,
                    'monitor': 1,
                    'format': '24h',
                    'position': 'Top Right',
                    'show_seconds': True,
                    'timezone': 'local',
                    'show_timezone': False,
                    'font_family': 'Segoe UI',
                    'font_size': 48,
                    'margin': 20,
                    'show_background': True,
                    'bg_opacity': 0.7,
                    'bg_color': [64, 64, 64, 255],
                    'color': [255, 255, 255, 230],
                    'border_color': [255, 255, 255, 255],
                    'border_opacity': 1.0,
                },
                'clock2': {
                    'enabled': False,
                    'monitor': 'ALL',
                    'format': '24h',
                    'position': 'Bottom Right',
                    'show_seconds': False,
                    'timezone': 'UTC',
                    'show_timezone': True,
                    'font_family': 'Segoe UI',
                    'font_size': 32,
                    'margin': 20,
                    'color': [255, 255, 255, 230],
                },
                'clock3': {
                    'enabled': False,
                    'monitor': 'ALL',
                    'format': '24h',
                    'position': 'Bottom Left',
                    'show_seconds': False,
                    'timezone': 'UTC+01:00',
                    'show_timezone': True,
                    'font_family': 'Segoe UI',
                    'font_size': 32,
                    'margin': 20,
                    'color': [255, 255, 255, 230],
                },
                'weather': {
                    'enabled': False,
                    'monitor': 'ALL',
                    'position': 'Bottom Left',
                    'location': 'London',
                    'font_family': 'Segoe UI',
                    'font_size': 24,
                    'color': [255, 255, 255, 230],
                    'show_background': True,
                    'bg_opacity': 0.7,
                    'bg_color': [64, 64, 64, 255],
                    'border_color': [255, 255, 255, 255],
                    'border_opacity': 1.0,
                    'show_icons': True,
                },
                # Media widget defaults intentionally mirror other overlay
                # widgets. It is disabled by default but configured with a
                # Bottom Left position and a visible background frame so that
                # enabling it in the UI immediately produces a clear overlay.
                'media': {
                    'enabled': False,
                    'monitor': 'ALL',
                    'position': 'Bottom Left',
                    'font_family': 'Segoe UI',
                    'font_size': 20,
                    'margin': 20,
                    'color': [255, 255, 255, 230],
                    'show_background': True,
                    'bg_opacity': 0.7,
                    'bg_color': [64, 64, 64, 255],
                    'border_color': [255, 255, 255, 255],
                    'border_opacity': 1.0,
                    # Artwork/controls behaviour
                    # Default artwork size is larger and can be tuned per-user.
                    'artwork_size': 200,
                    # Rounded artwork border for album art frame.
                    'rounded_artwork_border': True,
                    # When False the transport control row is hidden and
                    # the widget becomes a pure “now playing” block.
                    'show_controls': True,
                    # Optional header subcontainer frame around the logo +
                    # title row to mirror the Reddit widget styling.
                    'show_header_frame': True,
                },
            },
        }
        
        for key, value in defaults.items():
            if key == 'widgets':
                # Merge any existing widgets map with canonical defaults so
                # that legacy configs gain new sections (e.g. media) without
                # losing user customizations.
                self._ensure_widgets_defaults(value)
            else:
                if not self._settings.contains(key):
                    self._settings.setValue(key, value)

    def _ensure_widgets_defaults(self, default_widgets: Dict[str, Any]) -> None:
        """Ensure the canonical widgets map exists and is merged with defaults.

        This helper is similar in spirit to _ensure_media_defaults but operates
        on the entire widgets map in one place so that new widget sections and
        style keys are added without overwriting any existing user choices.
        """

        with self._lock:
            raw_widgets = self._settings.value('widgets', None)
            if isinstance(raw_widgets, dict):
                widgets: Dict[str, Any] = dict(raw_widgets)
            else:
                widgets = {}

            changed = False

            for section_name, section_defaults in default_widgets.items():
                existing_section = widgets.get(section_name)
                if isinstance(existing_section, Mapping):
                    # Fill in any missing keys for this section, preserving
                    # the user's existing values even when QSettings returns
                    # a mapping type that is not a plain dict.
                    section_dict = dict(existing_section)
                    for k, v in section_defaults.items():
                        if k not in section_dict:
                            section_dict[k] = v
                            changed = True
                    widgets[section_name] = section_dict
                else:
                    # Entire section missing or invalid – adopt defaults.
                    widgets[section_name] = dict(section_defaults)
                    changed = True

            if changed or not isinstance(raw_widgets, dict):
                self._settings.setValue('widgets', widgets)
                
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
