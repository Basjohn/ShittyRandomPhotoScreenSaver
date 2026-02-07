"""Settings manager implementation for screensaver."""
from typing import Any, Callable, Dict, List, Mapping, Optional
from copy import deepcopy
import threading
import sys
import json
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QSettings, QObject, Signal
from core.logging.logger import get_logger, is_verbose_logging
from core.settings.json_store import JsonSettingsStore, determine_storage_path, SNAPSHOT_VERSION
from core.settings.models import SpotifyVisualizerSettings

logger = get_logger('SettingsManager')


class SettingsManager(QObject):
    """Centralized settings management backed by a JSON snapshot."""
    
    # Signal emitted when settings change
    settings_changed = Signal(str, object)  # key, new_value
    _STRUCTURED_ROOTS = frozenset({"widgets", "transitions", "ui"})
    _MISSING = object()
    
    def __init__(
        self,
        organization: str = "ShittyRandomPhotoScreenSaver",
        application: str = "Screensaver",
        *,
        storage_base_dir: Optional[Path] = None,
    ):
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
                    or "srpss media center" in exe_name
                    or "srpss_media_center" in exe_name
                    or "main_mc.py" in exe_name
                ):
                    app_name = "Screensaver_MC"
        except Exception as exc:
            logger.debug("[SETTINGS] Exception suppressed: %s", exc, exc_info=True)

        storage_path = determine_storage_path(app_name, base_dir=storage_base_dir)
        self._settings = JsonSettingsStore(storage_path=storage_path, profile=app_name)
        self._organization = organization
        self._application = app_name
        self._storage_path = storage_path
        self._storage_base_dir = storage_base_dir
        self._lock = threading.RLock()
        self._change_handlers: Dict[str, List[Callable]] = {}
        
        # In-memory cache for frequently accessed settings (P2 optimization)
        self._cache: Dict[str, Any] = {}
        self._cache_enabled = True

        if not self._settings.exists():
            self._run_initial_migration(organization, app_name, storage_path)
        elif self._settings.had_load_failure():
            error_code = self._settings.last_load_error()
            logger.warning(
                "Settings JSON load failure (code=%s) at %s – regenerating defaults",
                error_code,
                storage_path,
            )
            self.reset_to_defaults()
            self._settings.clear_load_failure_flag()

        # Initialize defaults
        self._set_defaults()

        try:
            self.validate_and_repair()
        except Exception:
            logger.debug("Settings validation failed", exc_info=True)

        # Clean up obsolete settings for hygiene
        try:
            self.cleanup_obsolete_settings()
        except Exception:
            logger.debug("Settings cleanup failed", exc_info=True)

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

    # ------------------------------------------------------------------
    # Legacy QSettings migration
    # ------------------------------------------------------------------

    def _run_initial_migration(self, organization: str, app_name: str, storage_path: Path) -> None:
        """Perform first-run migration + logging."""

        try:
            migrated = self._migrate_from_qsettings(organization, app_name)
            if migrated:
                logger.info(
                    "Migrated legacy QSettings profile '%s/%s' into %s",
                    organization,
                    app_name,
                    storage_path,
                )
            else:
                logger.info(
                    "No legacy QSettings data detected for '%s/%s'; starting fresh JSON store",
                    organization,
                    app_name,
                )
            self._settings.update_metadata(last_migration_completed=datetime.utcnow().isoformat() + "Z")
            self._settings.sync()
        except Exception:
            logger.exception("Failed to migrate legacy QSettings; falling back to defaults")
            self._settings.clear()
            self._settings.sync()

    def _migrate_from_qsettings(self, organization: str, app_name: str) -> bool:
        """Import legacy QSettings data into the JSON store.

        Returns True when data was migrated.
        """

        legacy = QSettings(organization, app_name)
        try:
            keys = list(legacy.allKeys())
            has_data = bool(keys)
            if not has_data:
                has_data = bool(getattr(legacy, "childGroups", lambda: [])())
            if not has_data:
                return False
        except Exception:
            logger.exception("Failed to probe legacy QSettings for migration")
            return False

        flat: Dict[str, Any] = {}
        for key in keys:
            try:
                flat[str(key)] = self._to_plain_value(legacy.value(key))
            except Exception:
                logger.debug("[MIGRATE] Failed to read legacy key %s", key, exc_info=True)

        self._settings.replace_all(flat)
        self._settings.update_metadata(
            migrated_from="qsettings",
            migrated_at=datetime.utcnow().isoformat() + "Z",
            legacy_profile=app_name,
        )
        self._settings.sync()
        self._write_migration_backup(flat)
        return True

    def _write_migration_backup(self, data: Mapping[str, Any]) -> None:
        try:
            backup_dir = (self._storage_path.parent / "backups").resolve()
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"qsettings_snapshot_{timestamp}.json"
            backup_payload = {
                "profile": self._application,
                "organization": self._organization,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "data": data,
            }
            backup_path.write_text(json.dumps(backup_payload, indent=2, sort_keys=True), encoding="utf-8")
        except Exception:
            logger.debug("Failed to write migration backup", exc_info=True)

    def _get_default_image_folders(self) -> List[str]:
        """Get default image folders based on system.
        
        Returns user's Pictures folder if available, otherwise empty list.
        This replaces the previous hardcoded path.
        """
        folders = []
        try:
            # Try to get user's Pictures folder
            from PySide6.QtCore import QStandardPaths
            pictures = QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)
            if pictures and Path(pictures).exists():
                folders.append(pictures)
        except Exception as exc:
            logger.debug("[SETTINGS] Exception suppressed: %s", exc, exc_info=True)

        # Fallback: try common Windows paths
        if not folders:
            try:
                import os
                user_profile = os.environ.get('USERPROFILE', '')
                if user_profile:
                    pictures_path = Path(user_profile) / 'Pictures'
                    if pictures_path.exists():
                        folders.append(str(pictures_path))
            except Exception as exc:
                logger.debug("[SETTINGS] Exception suppressed: %s", exc, exc_info=True)
        
        return folders
    
    def _set_defaults(self) -> None:
        """Set default values if not already present."""
        from core.settings.defaults import get_default_settings
        canonical = get_default_settings()

        defaults: Dict[str, Any] = {
            # User-specific sources should remain dynamic on first run.
            'sources.folders': self._get_default_image_folders(),
            'sources.rss_feeds': [],
        }

        for section in ('display', 'input', 'queue', 'sources', 'timing'):
            section_value = canonical.get(section)
            if not isinstance(section_value, Mapping):
                continue
            for subkey, subval in section_value.items():
                dotted = f"{section}.{subkey}"
                # Even if a future defaults schema includes these, keep them
                # dynamic here.
                if dotted in {'sources.folders', 'sources.rss_feeds'}:
                    continue
                defaults[dotted] = subval

        canonical_transitions = canonical.get('transitions')
        if isinstance(canonical_transitions, Mapping):
            defaults['transitions'] = dict(canonical_transitions)

        canonical_widgets = canonical.get('widgets')
        if isinstance(canonical_widgets, Mapping):
            defaults['widgets'] = dict(canonical_widgets)
        
        for key, value in defaults.items():
            if key == 'widgets':
                # Merge any existing widgets map with canonical defaults so
                # that legacy configs gain new sections (e.g. media) without
                # losing user customizations.
                self._ensure_widgets_defaults(value)
            elif key == 'transitions':
                self._ensure_transitions_defaults(value)
            else:
                if not self._settings.contains(key):
                    self._settings.setValue(key, value)

    def _ensure_transitions_defaults(self, default_transitions: Dict[str, Any]) -> None:
        with self._lock:
            raw_transitions = self._settings.value('transitions', None)
            if isinstance(raw_transitions, Mapping):
                transitions: Dict[str, Any] = dict(raw_transitions)
            else:
                transitions = {}

            def merge(existing: Dict[str, Any], defaults_map: Mapping[str, Any]) -> bool:
                changed = False
                for k, v in defaults_map.items():
                    if k not in existing:
                        existing[k] = deepcopy(v)
                        changed = True
                        continue
                    if isinstance(v, Mapping) and isinstance(existing.get(k), Mapping):
                        child = dict(existing[k])
                        if merge(child, v):
                            existing[k] = child
                            changed = True
                return changed

            changed = merge(transitions, default_transitions)
            if changed or not isinstance(raw_transitions, Mapping):
                self._settings.setValue('transitions', transitions)
                self._settings.sync()

    def _ensure_widgets_defaults(self, default_widgets: Dict[str, Any]) -> None:
        """Ensure the canonical widgets map exists and is merged with defaults.

        This helper is similar in spirit to _ensure_media_defaults but operates
        on the entire widgets map in one place so that new widget sections and
        style keys are added without overwriting any existing user choices.
        """

        with self._lock:
            raw_widgets = self._settings.value('widgets', None)
            if isinstance(raw_widgets, Mapping):
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

            if changed or not isinstance(raw_widgets, Mapping):
                self._settings.setValue('widgets', widgets)
                self._settings.sync()

    def get_widget_defaults(self, section: str) -> Dict[str, Any]:
        """Return the canonical default config for a widget section.

        This helper mirrors the structures used in ``_set_defaults()`` for the
        ``widgets`` map but does not read from or modify QSettings, so it is
        safe for UI code to call when it needs a fresh baseline.
        """

        # Import canonical defaults to ensure consistency
        from core.settings.defaults import get_default_settings
        defaults = get_default_settings()
        widgets_defaults = defaults.get('widgets', {})

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
            # Check cache first (P2 optimization from architectural audit)
            cache_key = f"{key}:{id(default)}"
            if self._cache_enabled and cache_key in self._cache:
                return self._cache[cache_key]

            structured_value = self._get_structured_value_locked(key)
            if structured_value is not self._MISSING:
                value = structured_value
            else:
                value = self._settings.value(key, default)

        def to_plain(obj: Any) -> Any:
            if isinstance(obj, Mapping):
                return {k: to_plain(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [to_plain(v) for v in obj]
            return obj

        if isinstance(value, Mapping):
            return to_plain(value)

        # Some QSettings backends (notably on Windows) round-trip QVariantList
        # items as strings. Normalize critical list-valued settings.
        dotted = str(key) if key is not None else ""
        if dotted == "display.show_on_monitors" and isinstance(value, list):
            coerced: list[Any] = []
            for item in value:
                try:
                    coerced.append(int(item))
                except Exception as exc:
                    logger.debug("[SETTINGS] Exception suppressed: %s", exc, exc_info=True)
                    coerced.append(item)
            # Cache the coerced value
            if self._cache_enabled:
                with self._lock:
                    self._cache[cache_key] = coerced
            return coerced

        # Cache the result for future lookups
        if self._cache_enabled:
            with self._lock:
                self._cache[cache_key] = value
        return value
    
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
        """Return the application profile name for this manager."""
        return getattr(self, "_application", "Screensaver")

    def get_organization_name(self) -> str:
        """Return the organization name for this manager."""
        return getattr(self, "_organization", "ShittyRandomPhotoScreenSaver")

    @staticmethod
    def _to_plain_value(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {k: SettingsManager._to_plain_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [SettingsManager._to_plain_value(v) for v in value]
        return value

    def _coerce_import_value(self, key: str, value: Any) -> Any:
        """Best-effort type coercion for SST imports.

        This is intentionally conservative and only normalises a small set of
        critical bool/int keys. All other values are passed through as-is.
        """

        dotted = str(key) if key is not None else ""
        bool_keys = {
            "display.hw_accel",
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

    # Obsolete settings that should be removed from JSON for hygiene
    _OBSOLETE_KEYS = frozenset({
        'display.vsync_enabled',
        'display.fps_cap',
    })

    def cleanup_obsolete_settings(self) -> List[str]:
        """Remove obsolete/invalid settings from the JSON store.
        
        This is basic settings hygiene - removes keys that are no longer
        part of the architecture to prevent stale settings from persisting.
        
        Returns:
            List of removed keys
        """
        removed = []
        with self._lock:
            for key in self._OBSOLETE_KEYS:
                if self._settings.contains(key):
                    self._settings.remove(key)
                    removed.append(key)
                    logger.debug("Removed obsolete setting: %s", key)
            if removed:
                self._settings.sync()
                logger.info("Cleaned up %d obsolete settings: %s", len(removed), removed)
        return removed

    # Keys that require immediate sync to prevent data loss on crash/exit
    _CRITICAL_KEYS = frozenset({
        'transitions',
        'widgets',
        'sources.folders',
        'sources.rss_feeds',
        'display',
    })

    def set(self, key: str, value: Any) -> None:
        """
        Set a setting value.
        
        Args:
            key: Setting key in dot notation
            value: Value to set
        """
        with self._lock:
            handled, old_value = self._set_structured_value_locked(key, value)
            if not handled:
                old_value = self._settings.value(key)
                self._settings.setValue(key, value)

            # Invalidate cache entries for this key (P2 optimization)
            if self._cache_enabled:
                prefixes = {key}
                root_key = key.split('.')[0] if '.' in key else key
                prefixes.add(root_key)
                keys_to_remove = [
                    cache_k for cache_k in self._cache
                    if any(cache_k.startswith(f"{prefix}:") for prefix in prefixes)
                ]
                for cache_k in keys_to_remove:
                    del self._cache[cache_k]

            # Immediate sync for critical settings to prevent data loss
            root_key = key.split('.')[0] if '.' in key else key
            if root_key in self._CRITICAL_KEYS or key in self._CRITICAL_KEYS:
                self._settings.sync()

            # Emit change signal
            self.settings_changed.emit(key, value)

            # Call registered handlers
            if key in self._change_handlers:
                for handler in self._change_handlers[key]:
                    try:
                        handler(value, old_value)
                    except Exception:
                        logger.error("Error in change handler for %s", key, exc_info=True)

        # Compact logging by default so large nested maps (e.g. 'widgets')
        # do not flood the log. When verbose logging is enabled we still
        # include the full before/after values for deep debugging.
        if is_verbose_logging():
            logger.debug("Setting changed: %s: %r -> %r", key, old_value, value)
        else:
            logger.debug("Setting changed: %s", key)

    def set_many(self, values: Mapping[str, Any]) -> None:
        """Set multiple settings in one call."""
        for k, v in values.items():
            self.set(k, v)

    # Typed helpers -----------------------------------------------------
    def get_spotify_visualizer_settings(self) -> SpotifyVisualizerSettings:
        """Return typed settings for the Spotify visualizer widget."""
        return SpotifyVisualizerSettings.from_settings(self)

    def set_spotify_visualizer_settings(self, model: SpotifyVisualizerSettings) -> None:
        """Persist Spotify visualizer settings from a typed model."""
        self.set_many(model.to_dict())
    
    def save(self) -> None:
        """Force save settings to persistent storage."""
        with self._lock:
            self._settings.sync()
        logger.debug("Settings saved")
    
        """Load settings from persistent storage."""
        with self._lock:
            try:
                self._settings.load()
                self._cache.clear()
            except Exception as exc:
                logger.error("Failed to load settings: %s", exc, exc_info=True)
                # Reset to defaults if loading fails
                self.reset_to_defaults()
        logger.debug("Settings loaded")

    def validate_and_repair(self) -> Dict[str, str]:
        """Validate settings and repair corrupted values.
        
        Checks for:
        - Invalid types (e.g., string where list expected)
        - Out-of-range values
        - Missing required keys
        
        Returns:
            Dict of repaired keys and their issues
        """
        repairs = {}
        
        with self._lock:
            # Validate sources.folders - must be list
            folders = self._settings.value('sources.folders')
            if folders is not None and not isinstance(folders, list):
                logger.warning(f"Repairing sources.folders: was {type(folders).__name__}, expected list")
                if isinstance(folders, str):
                    self._settings.setValue('sources.folders', [folders] if folders else [])
                else:
                    self._settings.setValue('sources.folders', [])
                repairs['sources.folders'] = f"Invalid type: {type(folders).__name__}"
            
            # Validate sources.rss_feeds - must be list
            rss_feeds = self._settings.value('sources.rss_feeds')
            if rss_feeds is not None and not isinstance(rss_feeds, list):
                logger.warning(f"Repairing sources.rss_feeds: was {type(rss_feeds).__name__}, expected list")
                if isinstance(rss_feeds, str):
                    self._settings.setValue('sources.rss_feeds', [rss_feeds] if rss_feeds else [])
                else:
                    self._settings.setValue('sources.rss_feeds', [])
                repairs['sources.rss_feeds'] = f"Invalid type: {type(rss_feeds).__name__}"
            
            # Validate timing.interval - must be positive number
            interval = self._settings.value('timing.interval')
            if interval is not None:
                try:
                    interval_val = int(interval)
                    if interval_val < 1:
                        logger.warning(f"Repairing timing.interval: {interval_val} < 1")
                        self._settings.setValue('timing.interval', 10)
                        repairs['timing.interval'] = f"Out of range: {interval_val}"
                    elif interval_val > 3600:
                        logger.warning(f"Repairing timing.interval: {interval_val} > 3600")
                        self._settings.setValue('timing.interval', 60)
                        repairs['timing.interval'] = f"Out of range: {interval_val}"
                except (ValueError, TypeError):
                    logger.warning(f"Repairing timing.interval: invalid value {interval!r}")
                    self._settings.setValue('timing.interval', 10)
                    repairs['timing.interval'] = f"Invalid value: {interval!r}"
            
            # Validate display.mode - must be valid enum
            display_mode = self._settings.value('display.mode')
            valid_modes = {'fill', 'fit', 'shrink', 'stretch', 'center'}
            if display_mode is not None and display_mode not in valid_modes:
                logger.warning(f"Repairing display.mode: {display_mode!r} not in {valid_modes}")
                self._settings.setValue('display.mode', 'fill')
                repairs['display.mode'] = f"Invalid value: {display_mode!r}"

            # Validate display.render_backend_mode - must be valid enum
            backend_mode = self._settings.value('display.render_backend_mode')
            valid_backends = {'opengl', 'software', 'd3d11'}
            if backend_mode is not None:
                normalized = None
                if isinstance(backend_mode, str):
                    normalized = backend_mode.lower().strip()
                if not isinstance(normalized, str) or normalized not in valid_backends:
                    logger.warning(
                        "Repairing display.render_backend_mode: %r not in %s",
                        backend_mode,
                        valid_backends,
                    )
                    self._settings.setValue('display.render_backend_mode', 'opengl')
                    repairs['display.render_backend_mode'] = f"Invalid value: {backend_mode!r}"
                elif normalized == 'd3d11':
                    logger.info("Normalizing legacy display.render_backend_mode=d3d11 to opengl")
                    self._settings.setValue('display.render_backend_mode', 'opengl')
                    repairs['display.render_backend_mode'] = "Legacy value: d3d11"

            # Validate display.hw_accel - keep in sync with backend mode
            hw_accel = self._settings.value('display.hw_accel')
            backend_mode_final = self._settings.value('display.render_backend_mode')
            backend_is_opengl = False
            if isinstance(backend_mode_final, str) and backend_mode_final.lower().strip() == 'opengl':
                backend_is_opengl = True
            expected_hw = bool(backend_is_opengl)
            if hw_accel is not None:
                if isinstance(hw_accel, bool):
                    hw_val = hw_accel
                elif isinstance(hw_accel, str):
                    hw_val = hw_accel.lower().strip() in {'1', 'true', 'yes', 'on'}
                else:
                    hw_val = bool(hw_accel)
                if hw_val != expected_hw:
                    logger.info(
                        "Repairing display.hw_accel: %r -> %r (backend=%r)",
                        hw_accel,
                        expected_hw,
                        backend_mode_final,
                    )
                    self._settings.setValue('display.hw_accel', expected_hw)
                    repairs['display.hw_accel'] = f"Mismatch with backend: {backend_mode_final!r}"
            else:
                # Missing key: populate to avoid ambiguous startup paths.
                self._settings.setValue('display.hw_accel', expected_hw)
                repairs['display.hw_accel'] = "Missing key"
            
            # Validate spotify visualizer sensitivity - must be in valid range (0.25-2.5)
            # Fix for corrupted sensitivity values that cause poor visualizer performance
            vis_sensitivity = self._settings.value('widgets.spotify_visualizer.sensitivity')
            if vis_sensitivity is not None:
                try:
                    sens_val = float(vis_sensitivity)
                    # If sensitivity is below 0.5, it's likely corrupted - reset to default 1.0
                    if sens_val < 0.5:
                        logger.warning(f"Repairing widgets.spotify_visualizer.sensitivity: {sens_val} < 0.5 (likely corrupted)")
                        self._settings.setValue('widgets.spotify_visualizer.sensitivity', 1.0)
                        repairs['widgets.spotify_visualizer.sensitivity'] = f"Out of range: {sens_val}"
                    elif sens_val > 2.5:
                        logger.warning(f"Repairing widgets.spotify_visualizer.sensitivity: {sens_val} > 2.5")
                        self._settings.setValue('widgets.spotify_visualizer.sensitivity', 1.0)
                        repairs['widgets.spotify_visualizer.sensitivity'] = f"Out of range: {sens_val}"
                except (ValueError, TypeError):
                    logger.warning(f"Repairing widgets.spotify_visualizer.sensitivity: invalid value {vis_sensitivity!r}")
                    self._settings.setValue('widgets.spotify_visualizer.sensitivity', 1.0)
                    repairs['widgets.spotify_visualizer.sensitivity'] = f"Invalid value: {vis_sensitivity!r}"

            # Validate widgets - must be dict
            widgets = self._settings.value('widgets')
            if widgets is not None and not isinstance(widgets, Mapping):
                logger.warning(f"Repairing widgets: was {type(widgets).__name__}, expected mapping")
                try:
                    from core.settings.defaults import get_default_settings
                    canonical_widgets = get_default_settings().get('widgets', {})
                    if isinstance(canonical_widgets, Mapping):
                        self._settings.setValue('widgets', dict(canonical_widgets))
                    else:
                        self._settings.setValue('widgets', {})
                except Exception as exc:
                    logger.debug("[SETTINGS] Exception suppressed: %s", exc, exc_info=True)
                    self._settings.setValue('widgets', {})
                repairs['widgets'] = f"Invalid type: {type(widgets).__name__}"
            
            # Validate transitions - must be dict
            transitions = self._settings.value('transitions')
            if transitions is not None and not isinstance(transitions, Mapping):
                logger.warning(f"Repairing transitions: was {type(transitions).__name__}, expected mapping")
                try:
                    from core.settings.defaults import get_default_settings
                    canonical_transitions = get_default_settings().get('transitions', {})
                    if isinstance(canonical_transitions, Mapping):
                        self._settings.setValue('transitions', dict(canonical_transitions))
                    else:
                        self._settings.setValue('transitions', {})
                except Exception as exc:
                    logger.debug("[SETTINGS] Exception suppressed: %s", exc, exc_info=True)
                    self._settings.setValue('transitions', {})
                repairs['transitions'] = f"Invalid type: {type(transitions).__name__}"
            
            if repairs:
                self._settings.sync()
                logger.info(f"Settings validation repaired {len(repairs)} issues: {list(repairs.keys())}")
            else:
                logger.debug("Settings validation passed - no repairs needed")
        
        return repairs
    
    def backup_settings(self, backup_path: Optional[Path] = None) -> Optional[Path]:
        """Create a backup of current settings.
        
        Args:
            backup_path: Optional path for backup file. If None, uses default location.
            
        Returns:
            Path to backup file, or None if backup failed
        """
        try:
            if backup_path is None:
                # Default to settings directory with timestamp
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                settings_dir = Path(self._settings.fileName()).parent
                backup_path = settings_dir / f"settings_backup_{timestamp}.json"
            
            # Export all settings to JSON
            settings_dict = {}
            with self._lock:
                for key in self._settings.allKeys():
                    settings_dict[key] = self._settings.value(key)
            
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(settings_dict, f, indent=2, default=str)
            
            logger.info(f"Settings backed up to: {backup_path}")
            return backup_path
            
        except Exception:
            logger.error("Failed to backup settings", exc_info=True)
            return None
    
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
            if isinstance(widgets_raw, Mapping):
                widgets_map = dict(widgets_raw)
                weather = widgets_map.get('weather', {})
                if isinstance(weather, Mapping):
                    for key in ('location', 'latitude', 'longitude'):
                        if key in weather:
                            preserved[f'widgets.weather.{key}'] = weather[key]
            
            # Clear and apply canonical defaults
            self._settings.clear()
            
            # Apply new defaults from defaults module
            # Some sections (widgets, transitions) are stored as nested dicts,
            # while others use flat dot-notation keys for QSettings compatibility
            defaults = get_default_settings()
            
            # Sections that should be stored as nested dicts (not flattened)
            nested_sections = {'widgets', 'transitions'}
            
            def flatten_dict(d: dict, parent_key: str = '') -> dict:
                """Flatten nested dict to dot-notation keys."""
                items = {}
                for k, v in d.items():
                    new_key = f"{parent_key}.{k}" if parent_key else k
                    if isinstance(v, dict):
                        items.update(flatten_dict(v, new_key))
                    else:
                        items[new_key] = v
                return items
            
            for section, value in defaults.items():
                if section in nested_sections:
                    # Store as nested dict
                    self._settings.setValue(section, value)
                elif isinstance(value, dict):
                    # Flatten to dot-notation keys
                    flat = flatten_dict(value, section)
                    for key, val in flat.items():
                        self._settings.setValue(key, val)
                else:
                    self._settings.setValue(section, value)
            
            # Restore preserved user-specific data using flat dot-notation keys
            if 'sources.folders' in preserved:
                self._settings.setValue('sources.folders', preserved['sources.folders'])
            
            if 'sources.rss_feeds' in preserved:
                self._settings.setValue('sources.rss_feeds', preserved['sources.rss_feeds'])
            
            # Restore weather geo data into the nested widgets dict
            widgets = self._settings.value('widgets', {})
            if isinstance(widgets, Mapping):
                widgets_dict = dict(widgets)
                weather = widgets_dict.get('weather', {})
                if isinstance(weather, Mapping):
                    weather_dict = dict(weather)
                    for key in ('location', 'latitude', 'longitude'):
                        pkey = f'widgets.weather.{key}'
                        if pkey in preserved:
                            weather_dict[key] = preserved[pkey]
                    widgets_dict['weather'] = weather_dict
                    self._settings.setValue('widgets', widgets_dict)
            
            self._settings.sync()
            self._cache.clear()

        logger.info("Settings reset to defaults (preserved: %s)", list(preserved.keys()))
        self.settings_changed.emit('*', None)  # Signal that all changed
    
    def get_all_keys(self) -> List[str]:
        """Get all setting keys."""
        with self._lock:
            base_keys = list(self._settings.allKeys())
            seen = set(base_keys)
            for root in self._STRUCTURED_ROOTS:
                root_value = self._get_structured_root_locked(root)
                if not root_value:
                    continue
                for dotted in self._iter_structured_keys(root, root_value):
                    if dotted not in seen:
                        base_keys.append(dotted)
                        seen.add(dotted)
            return base_keys
    
    def contains(self, key: str) -> bool:
        """Check if a setting key exists."""
        with self._lock:
            structured = self._contains_structured_key_locked(key)
            if structured is not None:
                return structured
            return self._settings.contains(key)
    
    def remove(self, key: str) -> None:
        """Remove a setting key."""
        with self._lock:
            removed = self._remove_structured_key_locked(key)
            if not removed:
                self._settings.remove(key)

            if self._cache_enabled:
                prefixes = {key}
                root_key = key.split('.')[0] if isinstance(key, str) and '.' in key else key
                if root_key:
                    prefixes.add(root_key)
                keys_to_remove = [
                    cache_k for cache_k in self._cache
                    if any(cache_k.startswith(f"{prefix}:") for prefix in prefixes if prefix)
                ]
                for cache_k in keys_to_remove:
                    del self._cache[cache_k]

        logger.debug(f"Removed setting: {key}")
    
    def clear(self) -> None:
        """Clear all settings (use with caution)."""
        with self._lock:
            self._settings.clear()
        logger.warning("All settings cleared")

    # ------------------------------------------------------------------
    # QoL helpers for structured access and SST-style snapshots
    # ------------------------------------------------------------------

    def _get_structured_root_locked(self, root: str) -> Mapping[str, Any] | None:
        if root not in self._STRUCTURED_ROOTS:
            return None
        value = self._settings.value(root)
        return value if isinstance(value, Mapping) else None

    def _split_structured_key(self, key: str) -> tuple[str, List[str]] | None:
        if not isinstance(key, str) or '.' not in key:
            return None
        root, tail = key.split('.', 1)
        if root not in self._STRUCTURED_ROOTS:
            return None
        parts = [segment for segment in tail.split('.') if segment]
        if not parts:
            return None
        return root, parts

    def _traverse_structured(self, mapping: Mapping[str, Any], parts: List[str]) -> Any:
        current: Any = mapping
        for part in parts:
            if not isinstance(current, Mapping):
                return self._MISSING
            current = current.get(part, self._MISSING)
            if current is self._MISSING:
                return self._MISSING
        return current

    def _get_structured_value_locked(self, key: str) -> Any:
        split = self._split_structured_key(key)
        if split is None:
            return self._MISSING
        root, parts = split
        mapping = self._get_structured_root_locked(root)
        if mapping is None:
            return self._MISSING
        return self._traverse_structured(mapping, parts)

    def _set_structured_value_locked(self, key: str, value: Any) -> tuple[bool, Any]:
        split = self._split_structured_key(key)
        if split is None:
            return False, self._MISSING
        root, parts = split
        mapping = self._get_structured_root_locked(root)
        if mapping is None:
            mapping = {}
        else:
            mapping = dict(mapping)

        current = mapping
        for part in parts[:-1]:
            node = current.get(part)
            if not isinstance(node, Mapping):
                node = {}
                current[part] = node
            else:
                node = dict(node)
                current[part] = node
            current = node
        old_value = current.get(parts[-1]) if isinstance(current, Mapping) else self._MISSING
        if isinstance(current, Mapping):
            current[parts[-1]] = value
        else:
            return False, self._MISSING

        self._settings.setValue(root, mapping)
        return True, old_value

    def _contains_structured_key_locked(self, key: str) -> Optional[bool]:
        split = self._split_structured_key(key)
        if split is None:
            return None
        root, parts = split
        mapping = self._get_structured_root_locked(root)
        if mapping is None:
            return False
        result = self._traverse_structured(mapping, parts)
        return result is not self._MISSING

    def _remove_structured_key_locked(self, key: str) -> bool:
        split = self._split_structured_key(key)
        if split is None:
            return False
        root, parts = split
        mapping = self._get_structured_root_locked(root)
        if mapping is None:
            return False
        mapping = dict(mapping)
        stack: List[tuple[Mapping[str, Any], str]] = []
        current: Any = mapping
        for part in parts[:-1]:
            if not isinstance(current, Mapping) or part not in current:
                return False
            next_node = current[part]
            if not isinstance(next_node, Mapping):
                return False
            stack.append((current, part))
            next_node = dict(next_node)
            current[part] = next_node
            current = next_node

        if not isinstance(current, Mapping) or parts[-1] not in current:
            return False
        del current[parts[-1]]

        # Clean up empty dictionaries
        while stack:
            parent, part = stack.pop()
            child = parent[part]
            if isinstance(child, Mapping) and child:
                break
            del parent[part]
        self._settings.setValue(root, mapping)
        return True

    def _iter_structured_keys(self, prefix: str, mapping: Mapping[str, Any]) -> List[str]:
        dotted_keys: List[str] = []
        for key, value in mapping.items():
            dotted = f"{prefix}.{key}" if prefix else key
            dotted_keys.append(dotted)
            if isinstance(value, Mapping):
                dotted_keys.extend(self._iter_structured_keys(dotted, value))
        return dotted_keys

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

            root_key = section.split('.')[0] if '.' in section else section
            if root_key in self._CRITICAL_KEYS or section in self._CRITICAL_KEYS:
                self._settings.sync()

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
                    if key == 'custom_preset_backup':
                        if isinstance(value, Mapping):
                            snapshot['custom_preset_backup'] = dict(value)
                        else:
                            snapshot['custom_preset_backup'] = value
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

            app_name = getattr(self, "_application", "Screensaver")

            payload: Dict[str, Any] = {
                'settings_version': 2,
                'application': app_name,
                'profile': app_name,
                'snapshot_version': SNAPSHOT_VERSION,
                'metadata': self._settings.metadata(),
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
            current_app = self.get_application_name()
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

        normalized_root = self._normalize_sst_snapshot(root)

        try:
            with self._lock:
                for section_key, section_value in normalized_root.items():
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

                    if section_key == 'custom_preset_backup':
                        cpb_map: Any = section_value
                        if isinstance(cpb_map, Mapping):
                            self._settings.setValue('custom_preset_backup', dict(cpb_map))
                        else:
                            self._settings.setValue('custom_preset_backup', cpb_map)
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
                            if dotted in {
                                "display.refresh_sync",
                                "display.refresh_adaptive",
                                "display.render_backend_mode",
                                "display.hw_accel",
                            }:
                                logger.info(
                                    "Skipping legacy display key from SST import: %s",
                                    dotted,
                                )
                                continue
                            coerced = self._coerce_import_value(dotted, subval)
                            self._settings.setValue(dotted, coerced)
                    else:
                        # Top-level scalar from SST – write back directly.
                        coerced = self._coerce_import_value(section_key, section_value)
                        self._settings.setValue(section_key, coerced)

                self._settings.sync()
                self._cache.clear()

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

        normalized_root = self._normalize_sst_snapshot(root)

        diffs: Dict[str, Any] = {}

        try:
            with self._lock:
                for section_key, section_value in normalized_root.items():
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

    def _normalize_sst_snapshot(self, snapshot: Mapping[str, Any]) -> Dict[str, Any]:
        """Coerce legacy flat SST snapshots into the canonical nested form."""

        normalized: Dict[str, Any] = {}

        def assign(section: str, subkey: str, value: Any) -> None:
            container = normalized.get(section)
            if not isinstance(container, dict):
                container = {}
                normalized[section] = container
            container[subkey] = value

        for key, value in snapshot.items():
            if key in {'widgets', 'transitions', 'custom_preset_backup'}:
                if isinstance(value, Mapping):
                    normalized[key] = dict(value)
                else:
                    normalized[key] = value
                continue

            if '.' in key:
                section, subkey = key.split('.', 1)
                assign(section, subkey, value)
            else:
                normalized[key] = value

        return normalized
