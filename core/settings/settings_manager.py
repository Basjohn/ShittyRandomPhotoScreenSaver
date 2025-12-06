"""
Settings manager implementation for screensaver.

Uses QSettings for persistent storage. Simplified from SPQDocker reusable modules.
"""
from typing import Any, Callable, Dict, List, Mapping
import threading
import sys
import json
from pathlib import Path
from PySide6.QtCore import QSettings, QObject, Signal
from core.logging.logger import get_logger, is_verbose_logging

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

        app_name = application
        try:
            if application == "Screensaver":
                exe_name = str(getattr(sys, "argv", [""])[0]).lower()
                if (
                    "srpss mc" in exe_name
                    or "srpss_mc" in exe_name
                    or "main_mc.py" in exe_name
                ):
                    app_name = "Screensaver_MC"
        except Exception:
            pass

        self._settings = QSettings(organization, app_name)
        self._organization = organization
        self._application = app_name
        self._lock = threading.RLock()
        self._change_handlers: Dict[str, List[Callable]] = {}

        # Initialize defaults
        self._set_defaults()

        # Diagnostic snapshot so widget enable/monitor issues can be traced
        # without guessing what QSettings returned on this machine. The
        # full widgets map can be large, so we only dump it in verbose
        # mode; normal debug just logs the presence/absence of the key.
        try:
            widgets_snapshot = self._settings.value('widgets', None)
            if is_verbose_logging():
                logger.debug("Widgets snapshot on init: %r", widgets_snapshot)
            else:
                if widgets_snapshot is None:
                    logger.debug("Widgets snapshot on init: <missing>")
                elif isinstance(widgets_snapshot, dict):
                    logger.debug(
                        "Widgets snapshot on init: %d sections", len(widgets_snapshot)
                    )
                else:
                    logger.debug(
                        "Widgets snapshot on init: type=%s", type(widgets_snapshot).__name__
                    )
        except Exception:
            logger.debug("Failed to read widgets snapshot on init", exc_info=True)

        logger.info("SettingsManager initialized")
    
    def _set_defaults(self) -> None:
        """Set default values if not already present."""
        defaults = {
            # Sources
            'sources.folders': [
                'C:/Users/Basjohn/Documents/[4] WALLPAPERS/PERSONALSET',
            ],
            'sources.rss_feeds': [],
            'sources.mode': 'folders',  # 'folders' | 'rss' | 'both'
            # RSS/JSON background controls and save-to-disk behaviour.
            'sources.rss_save_to_disk': False,
            'sources.rss_save_directory': '',
            # Global background RSS queue cap and TTL/refresh configuration.
            'sources.rss_background_cap': 30,
            'sources.rss_refresh_minutes': 10,
            'sources.rss_stale_minutes': 30,
            
            # Display
            'display.mode': 'fill',  # 'fill' | 'fit' | 'shrink'
            'display.hw_accel': True,
            'display.refresh_sync': True,
            'display.prefer_triple_buffer': True,
            'display.gl_depth_bits': 24,
            'display.gl_stencil_bits': 8,
            'display.render_backend_mode': 'opengl',
            'display.sharpen_downscale': False,
            'display.same_image_all_monitors': False,
            # Main display selection – canonical key: ALL monitors by default.
            'display.show_on_monitors': 'ALL',

            # Timing / queue
            'timing.interval': 40,
            'queue.shuffle': True,

            # Input
            'input.hard_exit': False,

            # Transitions (canonical nested config)
            'transitions': {
                'type': 'Wipe',
                'duration_ms': 3000,
                'easing': 'Auto',
                'direction': 'Random',
                'random_always': False,
                'block_flip': {
                    'rows': 12,
                    'cols': 24,
                },
                'diffuse': {
                    'block_size': 18,
                    'shape': 'Diamond',
                },
                'slide': {
                    'direction': 'Random',
                },
                'wipe': {
                    'direction': 'Random',
                },
                'peel': {
                    'direction': 'Random',
                },
                'blockspin': {
                    # Optional multi-slab grid wave for 3D Block Spins. When
                    # disabled the effect renders a single full-frame slab.
                    'use_grid': False,
                    # Cardinal wave direction across the grid.
                    'direction': 'Left to Right',
                },
                # Per-transition pool membership for random/switch behaviour.
                # When a type is marked False it will not be selected by the
                # engine's random rotation logic nor by the C-key transition
                # cycling, but it remains available for explicit selection in
                # the UI dropdown.
                'pool': {
                    'Crossfade': True,
                    'Slide': True,
                    'Wipe': True,
                    'Peel': True,
                    'Diffuse': True,
                    'Block Puzzle Flip': True,
                    '3D Block Spins': True,
                    'Rain Drops': True,
                    'Warp Dissolve': True,
                    # Shuffle has been retired for v1.2 and is no longer
                    # part of the active random/switch pool.
                    'Blinds': True,
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
                    'show_timezone': True,
                    'font_family': 'Segoe UI',
                    'font_size': 48,
                    'margin': 20,
                    'show_background': True,
                    'bg_opacity': 0.7,
                    'bg_color': [35, 35, 35, 255],
                    'color': [255, 255, 255, 230],
                    'border_color': [255, 255, 255, 255],
                    'border_opacity': 1.0,
                    # Display mode: 'digital' (existing behaviour) or 'analog'.
                    'display_mode': 'analog',
                    # When in analogue mode, controls whether hour numerals
                    # (1–12) are rendered around the clock face.
                    'show_numerals': True,
                    # Enable analogue face shadow by default.
                    'analog_face_shadow': True,
                },
                'clock2': {
                    # Exception: Clock 2 disabled by default.
                    'enabled': False,
                    'monitor': 2,
                    'format': '24h',
                    'position': 'Bottom Right',
                    'show_seconds': False,
                    # Exception: default timezone = local.
                    'timezone': 'local',
                    'show_timezone': True,
                    'font_family': 'Segoe UI',
                    'font_size': 32,
                    'margin': 20,
                    'color': [255, 255, 255, 230],
                    'display_mode': 'digital',
                    'show_numerals': True,
                },
                'clock3': {
                    # Exception: Clock 3 disabled by default.
                    'enabled': False,
                    'monitor': 'ALL',
                    'format': '24h',
                    'position': 'Bottom Left',
                    'show_seconds': False,
                    # Exception: default timezone = local.
                    'timezone': 'local',
                    'show_timezone': True,
                    'font_family': 'Segoe UI',
                    'font_size': 32,
                    'margin': 20,
                    'color': [255, 255, 255, 230],
                    'display_mode': 'digital',
                    'show_numerals': True,
                },
                'weather': {
                    'enabled': True,
                    'monitor': 1,
                    'position': 'Top Left',
                    # Exception: default location = New York.
                    'location': 'New York',
                    'font_family': 'Segoe UI',
                    'font_size': 24,
                    'color': [255, 255, 255, 230],
                    'show_background': True,
                    'bg_opacity': 0.7,
                    'bg_color': [35, 35, 35, 255],
                    'border_color': [255, 255, 255, 255],
                    'border_opacity': 1.0,
                },
                # Media widget defaults intentionally mirror other overlay
                # widgets. It is disabled by default but configured with a
                # Bottom Left position and a visible background frame so that
                # enabling it in the UI immediately produces a clear overlay.
                'media': {
                    'enabled': True,
                    'monitor': 1,
                    'position': 'Bottom Left',
                    'font_family': 'Segoe UI',
                    'font_size': 20,
                    'margin': 20,
                    'color': [255, 255, 255, 230],
                    'show_background': True,
                    'bg_opacity': 0.7,
                    # Darker Spotify-style card background by default.
                    'bg_color': [35, 35, 35, 255],
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
                    # Optional Spotify-only vertical volume slider rendered
                    # alongside the media card. When enabled and Core Audio
                    # (pycaw) is available, a slim overlay widget appears to
                    # the side of the Spotify card and controls the Spotify
                    # session volume only.
                    'spotify_volume_enabled': True,
                },
                # Spotify Beat Visualizer – thin bar visualizer paired with
                # the Spotify media widget. This is Spotify-only by design and
                # is positioned relative to the media widget rather than via a
                # separate position control.
                'spotify_visualizer': {
                    'enabled': True,
                    'monitor': 'ALL',
                    # Number of vertical bars to render.
                    'bar_count': 16,
                    # Base fill colour for bars (RGBA).
                    'bar_fill_color': [24, 24, 24, 255],
                    # Bar border colour (RGBA) and independent opacity scaler.
                    'bar_border_color': [255, 255, 255, 255],
                    'bar_border_opacity': 1.0,
                    # Ghosting configuration: trailing bar effect above the
                    # current height, rendered by the GPU overlay.
                    'ghosting_enabled': True,
                    'ghost_alpha': 0.4,
                    'ghost_decay': 0.4,
                    # When True, the legacy QWidget-based software visualiser is
                    # allowed to render bars when OpenGL is unavailable or when
                    # the renderer backend is explicitly set to 'software'. This
                    # is disabled by default so the GPU overlay remains the
                    # primary path in OpenGL mode.
                    'software_visualizer_enabled': False,
                },
                'reddit': {
                    'enabled': True,
                    # Default to primary display only so the widget does not
                    # appear on all screens out of the box.
                    'monitor': 1,
                    'position': 'Bottom Right',
                    'subreddit': 'all',
                    'font_family': 'Segoe UI',
                    'font_size': 14,
                    'margin': 20,
                    'color': [255, 255, 255, 230],
                    'show_background': True,
                    'bg_opacity': 1.0,
                    'bg_color': [35, 35, 35, 255],
                    'border_color': [255, 255, 255, 255],
                    'border_opacity': 1.0,
                    # Default to visible separators between posts for the
                    # compact card layout.
                    'show_separators': True,
                    'limit': 10,
                    'exit_on_click': True,
                },
                # Global widget drop-shadow configuration shared by all
                # overlay widgets (clocks, weather, media). The Widgets tab
                # currently exposes only an enable/disable checkbox; other
                # parameters may be tweaked in future UI iterations.
                'shadows': {
                    'enabled': True,
                    # Base shadow colour; alpha is further scaled by the
                    # text/frame opacity fields below.
                    'color': [0, 0, 0, 255],
                    # Offset in logical pixels (dx, dy).
                    'offset': [4, 4],
                    # Blur radius in logical pixels.
                    'blur_radius': 18,
                    # Opacity multiplier for text-only widgets (no frame).
                    'text_opacity': 0.3,
                    # Opacity multiplier for widgets with active
                    # background/frames.
                    'frame_opacity': 0.7,
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

    def get_widget_defaults(self, section: str) -> Dict[str, Any]:
        """Return the canonical default config for a widget section.

        This helper mirrors the structures used in ``_set_defaults()`` for the
        ``widgets`` map but does not read from or modify QSettings, so it is
        safe for UI code to call when it needs a fresh baseline.
        """

        widgets_defaults: Dict[str, Any] = {
            'clock': {
                'enabled': True,
                'monitor': 1,
                'format': '24h',
                'position': 'Top Right',
                'show_seconds': True,
                'timezone': 'local',
                'show_timezone': True,
                'font_family': 'Segoe UI',
                'font_size': 48,
                'margin': 20,
                'show_background': True,
                'bg_opacity': 0.7,
                'bg_color': [35, 35, 35, 255],
                'color': [255, 255, 255, 230],
                'border_color': [255, 255, 255, 255],
                'border_opacity': 1.0,
                'display_mode': 'analog',
                'show_numerals': True,
                'analog_face_shadow': True,
            },
            'clock2': {
                'enabled': False,
                'monitor': 2,
                'format': '24h',
                'position': 'Bottom Right',
                'show_seconds': False,
                'timezone': 'local',
                'show_timezone': True,
                'font_family': 'Segoe UI',
                'font_size': 32,
                'margin': 20,
                'color': [255, 255, 255, 230],
                'display_mode': 'digital',
                'show_numerals': True,
            },
            'clock3': {
                'enabled': False,
                'monitor': 'ALL',
                'format': '24h',
                'position': 'Bottom Left',
                'show_seconds': False,
                'timezone': 'local',
                'show_timezone': True,
                'font_family': 'Segoe UI',
                'font_size': 32,
                'margin': 20,
                'color': [255, 255, 255, 230],
                'display_mode': 'digital',
                'show_numerals': True,
            },
            'weather': {
                'enabled': True,
                'monitor': 1,
                'position': 'Top Left',
                'location': 'New York',
                'font_family': 'Segoe UI',
                'font_size': 24,
                'color': [255, 255, 255, 230],
                'show_background': True,
                'bg_opacity': 0.7,
                'bg_color': [35, 35, 35, 255],
                'border_color': [255, 255, 255, 255],
                'border_opacity': 1.0,
            },
            'media': {
                'enabled': True,
                'monitor': 1,
                'position': 'Bottom Left',
                'font_family': 'Segoe UI',
                'font_size': 20,
                'margin': 20,
                'color': [255, 255, 255, 230],
                'show_background': True,
                'bg_opacity': 0.7,
                'bg_color': [35, 35, 35, 255],
                'border_color': [255, 255, 255, 255],
                'border_opacity': 1.0,
                'artwork_size': 200,
                'rounded_artwork_border': True,
                'show_controls': True,
                'show_header_frame': True,
                'spotify_volume_enabled': True,
            },
            'spotify_visualizer': {
                'enabled': True,
                'monitor': 'ALL',
                'bar_count': 16,
                'bar_fill_color': [24, 24, 24, 255],
                'bar_border_color': [255, 255, 255, 255],
                'bar_border_opacity': 1.0,
                'ghosting_enabled': True,
                'ghost_alpha': 0.4,
                'ghost_decay': 0.4,
                'software_visualizer_enabled': False,
            },
            'shadows': {
                'enabled': True,
                'color': [0, 0, 0, 255],
                'offset': [4, 4],
                'blur_radius': 18,
                'text_opacity': 0.3,
                'frame_opacity': 0.7,
            },
        }

        key = str(section) if section is not None else ''
        base = widgets_defaults.get(key, {})
        return dict(base) if isinstance(base, Mapping) else {}
                
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

    def get_application_name(self) -> str:
        """Return the QSettings application name for this manager."""
        try:
            return getattr(self, "_application", self._settings.applicationName())
        except Exception:
            return "Screensaver"

    def get_organization_name(self) -> str:
        """Return the QSettings organization name for this manager."""
        try:
            return getattr(self, "_organization", self._settings.organizationName())
        except Exception:
            return "ShittyRandomPhotoScreenSaver"

    def _coerce_import_value(self, key: str, value: Any) -> Any:
        """Best-effort type coercion for SST imports.

        This is intentionally conservative and only normalises a small set of
        critical bool/int keys. All other values are passed through as-is.
        """

        dotted = str(key) if key is not None else ""
        bool_keys = {
            "display.hw_accel",
            "display.refresh_sync",
            "display.sharpen_downscale",
            "display.pan_and_scan",
            "display.pan_auto_speed",
            "display.same_image_all_monitors",
            "sources.rss_save_to_disk",
            "input.hard_exit",
            "queue.shuffle",
        }
        int_keys = {
            "timing.interval",
            "sources.rss_background_cap",
            "sources.rss_refresh_minutes",
            "sources.rss_stale_minutes",
            "cache.prefetch_ahead",
            "cache.max_items",
            "cache.max_memory_mb",
            "cache.max_concurrent",
        }

        try:
            if dotted in bool_keys:
                return self.to_bool(value, default=False)
            if dotted in int_keys:
                if isinstance(value, bool):
                    # bool is a subclass of int; preserve intent.
                    return int(value)
                return int(value)
        except Exception:
            logger.debug("Failed to coerce SST value for %s=%r", dotted, value, exc_info=True)
            return value

        return value

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

        # Compact logging by default so large nested maps (e.g. 'widgets')
        # do not flood the log. When verbose logging is enabled we still
        # include the full before/after values for deep debugging.
        if is_verbose_logging():
            logger.debug("Setting changed: %s: %r -> %r", key, old_value, value)
        else:
            logger.debug("Setting changed: %s", key)
    
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
        """Reset all settings to default values, preserving user-specific data.
        
        Preserved settings (not reset):
        - sources.folders (user's image folders)
        - sources.rss_feeds (user's RSS feeds)  
        - widgets.weather.location (auto-detected or user-set)
        - widgets.weather.latitude (auto-detected)
        - widgets.weather.longitude (auto-detected)
        """
        from core.settings.defaults import get_default_settings
        
        with self._lock:
            # Preserve user-specific data before clearing
            preserved: dict = {}
            
            # Preserve source folders and feeds
            folders = self._settings.value('sources.folders')
            if folders:
                preserved['sources.folders'] = folders
            rss_feeds = self._settings.value('sources.rss_feeds')
            if rss_feeds:
                preserved['sources.rss_feeds'] = rss_feeds
            
            # Preserve weather location/geo data from widgets map
            widgets_raw = self._settings.value('widgets')
            if isinstance(widgets_raw, dict):
                weather = widgets_raw.get('weather', {})
                if isinstance(weather, dict):
                    for key in ('location', 'latitude', 'longitude'):
                        if key in weather:
                            preserved[f'widgets.weather.{key}'] = weather[key]
            
            # Clear and apply canonical defaults
            self._settings.clear()
            
            # Apply new defaults from defaults module
            defaults = get_default_settings()
            for section, value in defaults.items():
                self._settings.setValue(section, value)
            
            # Restore preserved user-specific data
            if 'sources.folders' in preserved:
                sources = self._settings.value('sources', {})
                if isinstance(sources, dict):
                    sources['folders'] = preserved['sources.folders']
                    self._settings.setValue('sources', sources)
            
            if 'sources.rss_feeds' in preserved:
                sources = self._settings.value('sources', {})
                if isinstance(sources, dict):
                    sources['rss_feeds'] = preserved['sources.rss_feeds']
                    self._settings.setValue('sources', sources)
            
            # Restore weather geo data
            widgets = self._settings.value('widgets', {})
            if isinstance(widgets, dict):
                weather = widgets.get('weather', {})
                if isinstance(weather, dict):
                    for key in ('location', 'latitude', 'longitude'):
                        pkey = f'widgets.weather.{key}'
                        if pkey in preserved:
                            weather[key] = preserved[pkey]
                    widgets['weather'] = weather
                    self._settings.setValue('widgets', widgets)
            
            self._settings.sync()
        
        logger.info("Settings reset to defaults (preserved: %s)", list(preserved.keys()))
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

    # ------------------------------------------------------------------
    # QoL helpers for structured access and SST-style snapshots
    # ------------------------------------------------------------------

    def get_section(self, section: str, default: Any = None) -> Any:
        """Return a whole section value (e.g. 'widgets', 'transitions').

        For mapping-backed sections, this normalises the result to a plain
        dict so callers can work with standard container types.
        """

        with self._lock:
            value = self._settings.value(section, default)

        if isinstance(value, Mapping):
            return dict(value)
        return value

    def set_section(self, section: str, value: Mapping[str, Any]) -> None:
        """Set a whole section value in one shot.

        This is primarily intended for mapping-backed sections like
        'widgets' and 'transitions' and keeps change notifications and
        logging behaviour consistent with set().
        """

        mapping = dict(value) if isinstance(value, Mapping) else value
        with self._lock:
            old_value = self._settings.value(section)
            self._settings.setValue(section, mapping)

        self.settings_changed.emit(section, mapping)
        if is_verbose_logging():
            logger.debug("Section changed: %s: %r -> %r", section, old_value, mapping)
        else:
            logger.debug("Section changed: %s", section)

    def get_widgets_map(self) -> Dict[str, Any]:
        """Return the full widgets map as a plain dict.

        Callers should prefer this over reading the raw 'widgets' key so
        any future migration or normalisation can be centralised here.
        """

        value = self.get_section('widgets', {})
        return dict(value) if isinstance(value, Mapping) else {}

    def set_widgets_map(self, widgets: Mapping[str, Any]) -> None:
        """Replace the widgets map with the given mapping.

        This is a thin wrapper around set_section('widgets', ...) to keep
        callers from hard-coding the 'widgets' key.
        """

        self.set_section('widgets', widgets)

    def export_to_sst(self, path: str) -> bool:
        """Export a human-readable SST snapshot of all settings to *path*.

        The snapshot is a JSON document with a simple nested structure that
        mirrors the canonical settings schema documented in Docs/SPEC.md.
        QSettings remains the runtime store; this is purely a convenience
        layer for humans (and tests) to inspect or move configurations
        between machines.
        """

        try:
            with self._lock:
                keys = list(self._settings.allKeys())
                snapshot: Dict[str, Any] = {}

                for key in keys:
                    value = self._settings.value(key)

                    # Widgets and transitions are already stored as nested
                    # mappings; keep them as top-level sections in the
                    # snapshot so they are easy to diff and re-import.
                    if key == 'widgets':
                        if isinstance(value, Mapping):
                            snapshot['widgets'] = dict(value)
                        else:
                            snapshot['widgets'] = value
                        continue
                    if key == 'transitions':
                        if isinstance(value, Mapping):
                            snapshot['transitions'] = dict(value)
                        else:
                            snapshot['transitions'] = value
                        continue

                    # Dotted keys (e.g. 'display.mode', 'input.hard_exit')
                    # become nested sections in the SST snapshot.
                    if '.' in key:
                        section, subkey = key.split('.', 1)
                        container = snapshot.get(section)
                        if not isinstance(container, dict):
                            container = {}
                            snapshot[section] = container
                        container[subkey] = value
                    else:
                        # Rare top-level scalars (if any) are kept as-is.
                        snapshot[key] = value

            app_name = None
            try:
                app_name = getattr(self, "_application", None) or self._settings.applicationName()
            except Exception:
                app_name = "Screensaver"

            payload: Dict[str, Any] = {
                'settings_version': 1,
                'application': app_name,
                'snapshot': snapshot,
            }

            target = Path(path)
            target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding='utf-8')
            logger.info("Exported settings snapshot to %s", target)
            return True
        except Exception:
            logger.exception("Failed to export settings snapshot to %s", path)
            return False

    def import_from_sst(self, path: str, merge: bool = True) -> bool:
        """Import settings from an SST snapshot at *path*.

        When *merge* is True (default), existing sections are overlaid with
        values from the snapshot instead of clearing the store first. This
        keeps the operation safer in the presence of new keys introduced
        after the snapshot was created.
        """

        try:
            raw = Path(path).read_text(encoding='utf-8')
            loaded = json.loads(raw)
        except Exception:
            logger.exception("Failed to read settings snapshot from %s", path)
            return False

        sst_version: Any = None
        sst_application: Any = None
        if isinstance(loaded, Mapping):
            sst_version = loaded.get('settings_version')
            sst_application = loaded.get('application')

        current_version = 1
        if isinstance(sst_version, int):
            if sst_version > current_version:
                logger.warning(
                    "Importing settings snapshot from newer settings_version=%s (current=%s)",
                    sst_version,
                    current_version,
                )
            elif sst_version < current_version:
                logger.info(
                    "Importing settings snapshot from older settings_version=%s (current=%s)",
                    sst_version,
                    current_version,
                )

        if isinstance(sst_application, str):
            try:
                current_app = self.get_application_name()
            except Exception:
                current_app = None
            if current_app and sst_application != current_app:
                logger.info(
                    "Importing settings snapshot for application '%s' into '%s'",
                    sst_application,
                    current_app,
                )

        root: Any
        if isinstance(loaded, Mapping) and 'snapshot' in loaded:
            root = loaded.get('snapshot', {})
        else:
            root = loaded

        if not isinstance(root, Mapping):
            logger.warning("Settings snapshot root is not a mapping: %r", type(root))
            return False

        try:
            with self._lock:
                for section_key, section_value in root.items():
                    # Widgets: treat as a single mapping-backed section.
                    if section_key == 'widgets':
                        widgets_map: Any = section_value
                        if not isinstance(widgets_map, Mapping):
                            continue
                        widgets_dict: Dict[str, Any] = dict(widgets_map)

                        if merge:
                            existing = self._settings.value('widgets', {})
                            if isinstance(existing, Mapping):
                                merged_widgets = dict(existing)
                                for name, cfg in widgets_dict.items():
                                    merged_widgets[name] = cfg
                                widgets_dict = merged_widgets

                        self._settings.setValue('widgets', widgets_dict)
                        continue

                    # Transitions: similar treatment to widgets.
                    if section_key == 'transitions':
                        transitions_map: Any = section_value
                        if not isinstance(transitions_map, Mapping):
                            continue
                        transitions_dict: Dict[str, Any] = dict(transitions_map)

                        if merge:
                            existing_t = self._settings.value('transitions', {})
                            if isinstance(existing_t, Mapping):
                                merged_t = dict(existing_t)
                                merged_t.update(transitions_dict)
                                transitions_dict = merged_t

                        self._settings.setValue('transitions', transitions_dict)
                        continue

                    # Known mapping-backed sections must be dict-like.
                    if section_key in {'display', 'timing', 'input', 'sources', 'cache'} and not isinstance(section_value, Mapping):
                        logger.warning(
                            "Skipping SST section '%s': expected mapping, got %s",
                            section_key,
                            type(section_value).__name__,
                        )
                        continue

                    # Generic nested sections (display, timing, input, cache, etc.).
                    if isinstance(section_value, Mapping):
                        flat: Mapping[str, Any] = section_value
                        for subkey, subval in flat.items():
                            dotted = f"{section_key}.{subkey}"
                            coerced = self._coerce_import_value(dotted, subval)
                            self._settings.setValue(dotted, coerced)
                    else:
                        # Top-level scalar from SST – write back directly.
                        coerced = self._coerce_import_value(section_key, section_value)
                        self._settings.setValue(section_key, coerced)

                self._settings.sync()

            # Wildcard signal so listeners that care about global changes can
            # refresh their view.
            self.settings_changed.emit('*', None)
            logger.info("Imported settings snapshot from %s", path)
            return True
        except Exception:
            logger.exception("Failed to apply settings snapshot from %s", path)
            return False

    def preview_import_from_sst(self, path: str, merge: bool = True) -> Dict[str, Any]:
        """Preview the effect of importing an SST snapshot without mutating settings.

        Returns a mapping of setting keys to ``(old_value, new_value)`` tuples for
        every key that would change if :meth:`import_from_sst` were invoked with
        the same arguments.
        """

        try:
            raw = Path(path).read_text(encoding='utf-8')
            loaded = json.loads(raw)
        except Exception:
            logger.exception("Failed to read settings snapshot for preview from %s", path)
            return {}

        root: Any
        if isinstance(loaded, Mapping) and 'snapshot' in loaded:
            root = loaded.get('snapshot', {})
        else:
            root = loaded

        if not isinstance(root, Mapping):
            logger.warning("Settings snapshot root is not a mapping for preview: %r", type(root))
            return {}

        diffs: Dict[str, Any] = {}

        try:
            with self._lock:
                for section_key, section_value in root.items():
                    if section_key == 'widgets':
                        widgets_map: Any = section_value
                        if not isinstance(widgets_map, Mapping):
                            continue
                        new_widgets: Dict[str, Any] = dict(widgets_map)

                        existing = self._settings.value('widgets', {})
                        if isinstance(existing, Mapping):
                            old_widgets = dict(existing)
                        else:
                            old_widgets = {}

                        if merge and isinstance(existing, Mapping):
                            merged_widgets = dict(existing)
                            for name, cfg in new_widgets.items():
                                merged_widgets[name] = cfg
                            new_widgets = merged_widgets

                        if old_widgets != new_widgets:
                            diffs['widgets'] = (old_widgets, new_widgets)
                        continue

                    if section_key == 'transitions':
                        transitions_map: Any = section_value
                        if not isinstance(transitions_map, Mapping):
                            continue
                        new_transitions: Dict[str, Any] = dict(transitions_map)

                        existing_t = self._settings.value('transitions', {})
                        if isinstance(existing_t, Mapping):
                            old_transitions = dict(existing_t)
                        else:
                            old_transitions = {}

                        if merge and isinstance(existing_t, Mapping):
                            merged_t = dict(existing_t)
                            merged_t.update(new_transitions)
                            new_transitions = merged_t

                        if old_transitions != new_transitions:
                            diffs['transitions'] = (old_transitions, new_transitions)
                        continue

                    if section_key in {'display', 'timing', 'input', 'sources', 'cache'} and not isinstance(section_value, Mapping):
                        logger.warning(
                            "Skipping SST section '%s' in preview: expected mapping, got %s",
                            section_key,
                            type(section_value).__name__,
                        )
                        continue

                    if isinstance(section_value, Mapping):
                        flat: Mapping[str, Any] = section_value
                        for subkey, subval in flat.items():
                            dotted = f"{section_key}.{subkey}"
                            new_val = self._coerce_import_value(dotted, subval)
                            old_val = self._settings.value(dotted)
                            if old_val != new_val:
                                diffs[dotted] = (old_val, new_val)
                    else:
                        new_val = self._coerce_import_value(section_key, section_value)
                        old_val = self._settings.value(section_key)
                        if old_val != new_val:
                            diffs[section_key] = (old_val, new_val)

            return diffs
        except Exception:
            logger.exception("Failed to compute settings snapshot preview from %s", path)
            return {}
