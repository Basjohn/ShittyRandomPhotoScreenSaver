"""
Implementation of the settings management system.

This module contains the core implementation of the settings manager,
handling loading, saving, and accessing application settings with
UI-thread-only mutations enforced via ThreadManager and lock-free reads.
"""

import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TypeVar, Union

from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal

from core.interfaces import ISettingsManager
from core.threading import ThreadManager
from core import logging as core_logging
from .types import SettingDefinition, SettingsCategory

def get_runtime_root():
    """Get the runtime root directory (where the executable or script is located)."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).parent.parent.parent

get_logger = core_logging.get_logger

# Type variables
T = TypeVar('T')


class _SettingsManagerImpl(ISettingsManager):
    """Internal implementation of the settings manager.
    
    This class handles the core settings logic without Qt dependencies,
    making it easier to test and maintain.
    """
    
    def __init__(self):
        """Initialize the settings manager with default values."""
        self._settings: Dict[str, Any] = {}
        self._settings_definitions: Dict[str, SettingDefinition] = {}
        self._logger = get_logger(__name__)
        self._load_defaults()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value.
        
        Args:
            key: Setting key in dot notation (e.g., 'app.theme.color')
            default: Default value to return if key is not found
            
        Returns:
            The setting value or default if not found
        """
        # Lock-free read: mutations are UI-thread-only
        return self._settings.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a setting value.
        
        Args:
            key: Setting key in dot notation
            value: Value to set
        """
        # Called only from UI thread by outer SettingsManager
        self._settings[key] = value
    
    def save(self, file_path: Optional[Union[str, Path]] = None) -> None:
        """Save settings to persistent storage.
        
        Args:
            file_path: Optional path to save settings file. If None, uses default location.
        """
        if file_path is None:
            if hasattr(self, '_settings_file') and self._settings_file is not None:
                file_path = self._settings_file
            else:
                settings_dir = Path.home() / '.spqmodular'
                settings_dir.mkdir(exist_ok=True)
                file_path = settings_dir / 'settings.json'
        else:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w') as f:
            json.dump(self._settings, f, indent=4)
    
    def load(self, file_path: Optional[Union[str, Path]] = None) -> None:
        """Load settings from persistent storage.
        
        Args:
            file_path: Optional path to load settings from. If None, uses default location.
        """
        if file_path is None:
            file_path = Path.home() / '.spqmodular' / 'settings.json'
        else:
            file_path = Path(file_path)
        
        if not file_path.exists():
            return
        
        try:
            with open(file_path, 'r') as f:
                loaded_settings = json.load(f)

            # Only update existing keys to preserve defaults for missing settings
            for key, value in loaded_settings.items():
                if key in self._settings_definitions:
                    self._settings[key] = value

        except (json.JSONDecodeError, OSError) as e:
            get_logger(__name__).error(f"Failed to load settings: {e}")
    
    def reset_to_defaults(self) -> None:
        """Reset all settings to their default values."""
        # Called only from UI thread by outer SettingsManager
        self._load_defaults()
    
    def get_setting_definition(self, key: str) -> Optional[SettingDefinition]:
        """Get the definition for a setting.
        
        Args:
            key: Setting key
            
        Returns:
            SettingDefinition if found, None otherwise
        """
        return self._settings_definitions.get(key)
    
    def _load_defaults(self) -> None:
        """Load default settings definitions and values."""
        self._settings_definitions = {
            # Appearance
            'theme': SettingDefinition(
                default='dark',
                setting_type=str,
                options=['light', 'dark'],
                description='Application color theme (canonical key)',
                category=SettingsCategory.APPEARANCE
            ),
            # Media control
            'media.volume_step': SettingDefinition(
                default=0.05,
                setting_type=float,
                validator=lambda x: isinstance(x, float) and 0.01 <= x <= 0.25,
                description='Per-step session volume delta (0.01-0.25)',
                category=SettingsCategory.BEHAVIOR
            ),
            'media.app_catalog': SettingDefinition(
                default={},
                setting_type=dict,
                description='User overrides for media app catalog entries',
                category=SettingsCategory.BEHAVIOR
            ),
            'media.wm_command_ids': SettingDefinition(
                default={},
                setting_type=dict,
                description='Per-app WM_COMMAND action IDs for MPC variants',
                category=SettingsCategory.BEHAVIOR
            ),
            # Input timing controls
            'input.volume_hold_initial_delay_ms': SettingDefinition(
                default=200,
                setting_type=int,
                validator=lambda x: isinstance(x, int) and 50 <= x <= 1000,
                description='Initial delay before continuous volume adjustment starts when holding volume keys (50-1000ms)',
                category=SettingsCategory.BEHAVIOR
            ),
            'input.volume_hold_interval_ms': SettingDefinition(
                default=50,
                setting_type=int,
                validator=lambda x: isinstance(x, int) and 10 <= x <= 200,
                description='Interval between continuous volume steps when holding volume keys (10-200ms)',
                category=SettingsCategory.BEHAVIOR
            ),
            'appearance.opacity': SettingDefinition(
                default=100,
                setting_type=int,
                validator=lambda x: 0 <= x <= 100,
                description='Opacity of the overlay windows (0-100%)',
                category=SettingsCategory.APPEARANCE
            ),
            # Overlay visual options
            'overlay.rounded_borders': SettingDefinition(
                default=True,
                setting_type=bool,
                description='Use rounded corners for overlay border rendering',
                category=SettingsCategory.APPEARANCE
            ),
            'overlay.larger_borders': SettingDefinition(
                default=False,
                setting_type=bool,
                description='Increase border thickness by 1px for better visibility',
                category=SettingsCategory.APPEARANCE
            ),
            # UI state persistence
            'ui.main_window_geometry': SettingDefinition(
                default={'x': 0, 'y': 0, 'width': 800, 'height': 500, 'maximized': False},
                setting_type=dict,
                validator=lambda g: isinstance(g, dict)
                    and isinstance(g.get('x', 0), int)
                    and isinstance(g.get('y', 0), int)
                    and isinstance(g.get('width', 0), int)
                    and isinstance(g.get('height', 0), int)
                    and isinstance(g.get('maximized', False), bool),
                description='Main window geometry and state',
                category=SettingsCategory.GENERAL
            ),
            'ui.badge_file': SettingDefinition(
                default='Badge19.png',
                setting_type=str,
                description='Selected badge image filename',
                category=SettingsCategory.GENERAL
            ),
            'ui.mode_button_state': SettingDefinition(
                default='window',
                setting_type=str,
                options=['window', 'monitor', 'docking'],
                description='Selected mode button state',
                category=SettingsCategory.GENERAL
            ),
            'ui.block_flash_min_interval_ms': SettingDefinition(
                default=250,
                setting_type=int,
                validator=lambda x: isinstance(x, int) and 0 <= x <= 2000,
                description='Minimum interval between keypassthrough block UI flash feedback (0-2000ms, throttles spam)',
                category=SettingsCategory.GENERAL
            ),
            # Overlay geometry persistence (standalone DWM and Docking main)
            'overlays.dwm.last_state': SettingDefinition(
                default={},
                setting_type=dict,
                description='Nearest-corner persisted state for standalone DWM overlay (corner,width,height,monitor_index)',
                category=SettingsCategory.GENERAL
            ),
            'docking.last_state': SettingDefinition(
                default={},
                setting_type=dict,
                description='Nearest-corner persisted state for Docking main overlay (corner,width,height,monitor_index)',
                category=SettingsCategory.GENERAL
            ),
            # Feature toggles
            'features.autoswitch_enabled': SettingDefinition(
                default=False,
                setting_type=bool,
                description='Enable Autoswitch controller',
                category=SettingsCategory.BEHAVIOR
            ),
            'features.keypassthrough_enabled': SettingDefinition(
                default=False,
                setting_type=bool,
                description='Enable key passthrough for overlays',
                category=SettingsCategory.BEHAVIOR
            ),
            'features.keypassthrough_blocklist_enabled': SettingDefinition(
                default=True,
                setting_type=bool,
                description='Enable keypassthrough blocklist feature',
                category=SettingsCategory.BEHAVIOR
            ),
            'features.display_locked_switching': SettingDefinition(
                default=False,
                setting_type=bool,
                description='Restrict window switching to same monitor as overlay source',
                category=SettingsCategory.BEHAVIOR
            ),
            'features.media_control_enabled': SettingDefinition(
                default=True,
                setting_type=bool,
                description='Enable media key routing and media controller features',
                category=SettingsCategory.BEHAVIOR
            ),
            # Docking mode settings
            'docking.enabled': SettingDefinition(
                default=False,
                setting_type=bool,
                description='Enable docking mode (3-overlay system)',
                category=SettingsCategory.BEHAVIOR
            ),
            'docking.mode': SettingDefinition(
                default='normal',
                setting_type=str,
                options=['normal', 'cycle'],
                description='Docking operation mode: normal (current behavior) or cycle (MRU-driven continuous cycling)',
                category=SettingsCategory.BEHAVIOR
            ),
            'docking.overlay_count': SettingDefinition(
                default=3,
                setting_type=int,
                validator=lambda x: isinstance(x, int) and 2 <= x <= 5,
                description='Number of overlays to create in docking mode (2-5)',
                category=SettingsCategory.BEHAVIOR
            ),
            'docking.size_ratios': SettingDefinition(
                default=[1.0, 0.7, 0.5],
                setting_type=list,
                validator=lambda x: isinstance(x, list) and len(x) == 3 and all(isinstance(r, (int, float)) and 0.1 <= r <= 1.0 for r in x),
                description='Size ratios for main and secondary overlays [100%, 70%, 50%]',
                category=SettingsCategory.BEHAVIOR
            ),
            'docking.spacing': SettingDefinition(
                default=2,
                setting_type=int,
                validator=lambda x: isinstance(x, int) and 0 <= x <= 20,
                description='Pixels between docking overlays (0-20)',
                category=SettingsCategory.BEHAVIOR
            ),
            'docking.positioning_mode': SettingDefinition(
                default='auto',
                setting_type=str,
                options=['auto', 'manual'],
                description='Positioning mode for secondary overlays',
                category=SettingsCategory.BEHAVIOR
            ),
            'docking.mru_capacity': SettingDefinition(
                default=12,
                setting_type=int,
                validator=lambda x: isinstance(x, int) and 3 <= x <= 20,
                description='MRU list capacity for docking mode (3-20)',
                category=SettingsCategory.BEHAVIOR
            ),
            # Debug/diagnostics (verbose logging controls)
            'debug.keypassthrough_verbose': SettingDefinition(
                default=False,
                setting_type=bool,
                description='Verbose logging for key passthrough routing decisions',
                category=SettingsCategory.GENERAL
            ),
            'debug.window_filter_verbose': SettingDefinition(
                default=False,
                setting_type=bool,
                description='Verbose logging for window filtering exclusions (WindowFilter)',
                category=SettingsCategory.GENERAL
            ),
            'debug.volume_osd_verbose': SettingDefinition(
                default=False,
                setting_type=bool,
                description='Verbose logging for Volume OSD widget visibility and updates',
                category=SettingsCategory.GENERAL
            ),
            'debug.docking_verbose': SettingDefinition(
                default=False,
                setting_type=bool,
                description='Verbose logging for docking manager sizing/fit/position calculations',
                category=SettingsCategory.GENERAL
            ),
            # Hotkeys
            'hotkeys.opacity_enabled': SettingDefinition(
                default=True,
                setting_type=bool,
                description='Enable opacity hotkeys',
                category=SettingsCategory.HOTKEYS
            ),
            'hotkeys.prefer_keyboard_fallback': SettingDefinition(
                default=False,
                setting_type=bool,
                description='Prefer keyboard library combo fallback when system hotkey registration fails',
                category=SettingsCategory.HOTKEYS
            ),
            'hotkeys.allow_single_digits': SettingDefinition(
                default=False,
                setting_type=bool,
                description='Allow single-digit keys as standalone hotkeys (keyboard backend only)',
                category=SettingsCategory.HOTKEYS
            ),
            'hotkeys.quickswitch_enabled': SettingDefinition(
                default=True,
                setting_type=bool,
                description='Enable QuickSwitch hotkey',
                category=SettingsCategory.HOTKEYS
            ),
            'hotkeys.hide_show_enabled': SettingDefinition(
                default=True,
                setting_type=bool,
                description='Enable Hide/Show All Overlays hotkey',
                category=SettingsCategory.HOTKEYS
            ),
            'hotkeys.hide_show_overlays': SettingDefinition(
                default='ctrl+shift+h',
                setting_type=str,
                description='Hide/Show all overlays hotkey combo (default: ctrl+shift+h)',
                category=SettingsCategory.HOTKEYS
            ),
            'hotkeys.opacity_decrease': SettingDefinition(
                default='-',
                setting_type=str,
                description='Opacity decrease key (single-key suppression backend)',
                category=SettingsCategory.HOTKEYS
            ),
            'hotkeys.opacity_increase': SettingDefinition(
                default='=',
                setting_type=str,
                description='Opacity increase key (single-key suppression backend)',
                category=SettingsCategory.HOTKEYS
            ),
            'hotkeys.opacity_quickswitch': SettingDefinition(
                default='ctrl+shift+x',
                setting_type=str,
                description='Quickswitch combo (default: ctrl+shift+x)',
                category=SettingsCategory.HOTKEYS
            ),
            # Graphics pipeline selection (feature flag)
            'graphics.pipeline': SettingDefinition(
                default='dxgi',
                setting_type=str,
                options=['dxgi'],
                description='Capture/renderer pipeline selection (dxgi only)',
                requires_restart=True,
                category=SettingsCategory.EXPERIMENTAL
            ),
            # Graphics presentation selection (renderer presentation path)
            'graphics.presentation': SettingDefinition(
                default='cpu-blit',
                setting_type=str,
                options=['cpu-blit', 'd3d11-swapchain'],
                description='Renderer presentation path: CPU QImage blit or D3D11 swapchain host',
                requires_restart=False,
                category=SettingsCategory.EXPERIMENTAL
            ),
            
            # Behavior
            'behavior.auto_switch': SettingDefinition(
                default=True,
                setting_type=bool,
                description='Automatically switch to the most recently used window',
                category=SettingsCategory.BEHAVIOR
            ),
            'behavior.click_through': SettingDefinition(
                default=False,
                setting_type=bool,
                description='Allow mouse clicks to pass through the overlay',
                category=SettingsCategory.BEHAVIOR
            ),
            
            # Performance
            'performance.cache_size': SettingDefinition(
                default=100,
                setting_type=int,
                validator=lambda x: x > 0,
                description='Maximum number of items to cache',
                category=SettingsCategory.PERFORMANCE
            ),
            'performance.threads': SettingDefinition(
                default=4,
                setting_type=int,
                validator=lambda x: 1 <= x <= 32,
                description='Number of worker threads to use',
                category=SettingsCategory.PERFORMANCE
            )
        }
        
        # Capture preferences
        self._settings_definitions['capture.fps'] = SettingDefinition(
            default=60,
            setting_type=int,
            validator=lambda x: isinstance(x, int) and 1 <= x <= 165,
            description='Target monitor capture frames per second (1-165)',
            category=SettingsCategory.PERFORMANCE
        )
        
        # Set default values
        for key, definition in self._settings_definitions.items():
            self._settings[key] = definition.default


class SettingsManager(QObject):
    """
    Qt-compatible settings manager with signals for setting changes.
    
    This class provides a Qt-compatible interface to the settings system,
    with support for change notifications via signals.
    """
    
    # Signal emitted when a setting changes
    setting_changed = Signal(str, object)
    
    _instance = None
    _initialized = False
    
    @classmethod
    def _reset_for_testing(cls):
        """Reset singleton state for testing purposes."""
        cls._instance = None
        cls._initialized = False
    
    def __new__(cls, *args, **kwargs):
        """Ensure singleton behavior."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, parent: Optional[QObject] = None, settings_file: Optional[Union[str, Path]] = None):
        """Initialize the settings manager."""
        if SettingsManager._initialized:
            # For testing: allow reinitializing with different settings file
            if settings_file is not None and hasattr(self, '_settings_file'):
                old_file = self._settings_file
                new_file = Path(settings_file)
                if old_file != new_file:
                    # Reset for new file path
                    self._settings_file = new_file
                    self._impl = _SettingsManagerImpl()
                    self._impl.load(self._settings_file)
            return
            
        super().__init__(parent)
        self._impl = _SettingsManagerImpl()
        self._logger = get_logger(__name__)
        self._handlers = {}
        # Coalesced save management (tag -> True when a save is pending)
        self._save_coalesce: Dict[str, bool] = {}
        # Resolve settings file path: honor explicit path, else prefer portable ./settings next to runtime root
        try:
            if settings_file is not None:
                self._settings_file = Path(settings_file)
            else:
                resolved_dir = self._resolve_settings_dir()
                self._settings_file = resolved_dir / 'settings.json'
        except Exception:
            # Best-effort fallback
            self._settings_file = Path.home() / '.spqmodular' / 'settings.json'
        # Ensure directory exists and log resolution
        try:
            self._settings_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self._logger.error(f"[SETTINGS] Failed to ensure settings directory {self._settings_file.parent}: {e}", exc_info=True)
        self._logger.info(f"[SETTINGS] Using settings file: {self._settings_file}")
        
        # Load saved settings
        if Path(self._settings_file).exists():
            self._logger.info(f"[SETTINGS] Loading settings from {self._settings_file}")
        else:
            self._logger.info(f"[SETTINGS] No existing settings at {self._settings_file}; defaults will be created")
        self._impl.load(self._settings_file)
        # Apply explicit migrations, then validate
        self._apply_migrations()
        
        # Register with ResourceManager for deterministic cleanup
        try:
            from utils.resource_manager import ResourceType, get_resource_manager
            self._resource_manager = get_resource_manager()
            self._resource_id = self._resource_manager.register(
                self,
                ResourceType.CUSTOM,
                "SettingsManager singleton",
                cleanup_handler=lambda obj: obj._cleanup()
            )
            self._logger.debug("Registered SettingsManager with ResourceManager")
        except Exception as e:
            self._logger.warning(f"Failed to register with ResourceManager: {e}")
            self._resource_manager = None
            self._resource_id = None
        self._validate_loaded_settings()

        # Ensure defaults are flushed to disk on first run
        try:
            self._ensure_settings_file_exists()
        except Exception as e:
            # Non-fatal: log and continue
            self._logger.error(f"Failed to create default settings file: {e}", exc_info=True)

        # Ensure keypassthrough blocklist exists alongside the settings file
        try:
            self._ensure_keypassthrough_blocklist_defaults()
        except Exception as e:
            # Non-fatal: log explicitly; creation is best-effort
            self._logger.error(f"[KEYPASS] Failed to ensure blocklist defaults: {e}", exc_info=True)
        
        SettingsManager._initialized = True
    
    def _cleanup(self):
        """Cleanup handler for ResourceManager."""
        try:
            # Save current settings before cleanup
            self.save()
            # Clear handlers
            self._handlers.clear()
            self._save_coalesce.clear()
            self._logger.debug("SettingsManager cleanup completed")
        except Exception as e:
            self._logger.error(f"Error during SettingsManager cleanup: {e}")
    
    def shutdown(self):
        """Explicit shutdown method."""
        if hasattr(self, '_resource_id') and self._resource_id and hasattr(self, '_resource_manager') and self._resource_manager:
            try:
                self._resource_manager.unregister(self._resource_id)
                self._resource_id = None
            except Exception as e:
                self._logger.warning(f"Failed to unregister from ResourceManager: {e}")
        self._cleanup()

    # --- UI-thread helpers -------------------------------------------------
    @staticmethod
    def _on_ui_thread() -> bool:
        try:
            app = QCoreApplication.instance()
            return bool(app and (QThread.currentThread() is app.thread()))
        except Exception:
            return False

    @staticmethod
    def _ensure_on_ui(func: Callable, *args, **kwargs) -> None:
        # If no Qt application exists (e.g., unit tests), execute inline
        app = QCoreApplication.instance()
        if app is None:
            func(*args, **(kwargs or {}))
            return
        if SettingsManager._on_ui_thread():
            func(*args, **(kwargs or {}))
        else:
            ThreadManager.run_on_ui_thread(func, *args, **(kwargs or {}))
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value with type conversion.
        
        Args:
            key: Setting key in dot notation (e.g., 'app.theme.color')
            default: Default value to return if key is not found
            
        Returns:
            The setting value, converted to the specified type if possible
        """
        return self._impl.get(key, default)
    
    def set(self, key: str, value: Any, save_immediately: bool = True, *, force: bool = False) -> bool:
        """Set a setting value.
        
        Args:
            key: Setting key in dot notation
            value: Value to set
            save_immediately: If True, save to disk immediately
            
        Returns:
            bool: True if the setting was updated, False otherwise
            
        Raises:
            ValueError: If the value is not valid for the setting
        """
        def _apply() -> bool:
            definition = self._impl.get_setting_definition(key)
            if definition is not None:
                # Validate the value
                nonlocal value
                if not isinstance(value, definition.setting_type):
                    try:
                        value = definition.setting_type(value)
                    except (ValueError, TypeError) as e:
                        raise ValueError(
                            f"Invalid value for setting {key}: {value}. "
                            f"Expected {definition.setting_type.__name__}"
                        ) from e

                if definition.validator and not definition.validator(value):
                    raise ValueError(f"Invalid value for setting {key}: {value}")

                if definition.options and value not in definition.options:
                    raise ValueError(
                        f"Invalid value for setting {key}. "
                        f"Must be one of: {', '.join(map(str, definition.options))}"
                    )

            # Update the setting without alias mirroring (canonical only)
            changed = False
            old_value = self._impl.get(key)
            if old_value != value:
                self._impl.set(key, value)
                changed = True

            # Emit on change or when explicitly forced
            if changed or force:
                # Notify listeners for the changed key
                try:
                    self.setting_changed.emit(key, value)
                except Exception:
                    pass

                # Call any registered handlers for the key
                handlers = list(self._handlers.get(key, ()))
                for handler in handlers:
                    try:
                        handler(key, value)
                    except Exception as e:
                        self._logger.error(
                            f"Error in setting change handler for {key}: {e}",
                            exc_info=True
                        )

                if changed and save_immediately:
                    self.save()

            return bool(changed or force)

        # Ensure mutation occurs on UI thread
        app = QCoreApplication.instance()
        if app is None or SettingsManager._on_ui_thread():
            # In tests (no Qt) or already on UI, execute synchronously
            return _apply()
        else:
            # Execute on UI and return best-effort boolean via side-effect container
            result_box = {'ok': False}
            def _apply_and_store():
                result_box['ok'] = _apply()
            ThreadManager.run_on_ui_thread(_apply_and_store)
            return bool(result_box['ok'])
    
    def save(self) -> None:
        """Save settings to persistent storage."""
        if hasattr(self, '_settings_file') and self._settings_file is not None:
            self._logger.debug(f"[SETTINGS] Saving settings to {self._settings_file}")
            self._impl.save(self._settings_file)
        else:
            self._impl.save()

    def request_save(self, tag: str, within_ms: int = 500) -> None:
        """Request a settings save coalesced by tag within a time window.

        Multiple calls with the same tag within the window result in a single save.

        Args:
            tag: Coalescing key for this save request (e.g., 'opacity', 'ui.geometry').
            within_ms: Window in milliseconds to coalesce saves for this tag.
        """
        if not tag:
            tag = "default"

        def _schedule():
            # Coalesce strictly on UI thread
            if self._save_coalesce.get(tag, False):
                return
            self._save_coalesce[tag] = True

            def _do_save():
                try:
                    self.save()
                except Exception as e:
                    try:
                        self._logger.error(f"[SETTINGS] Coalesced save failed for tag '{tag}': {e}")
                    except Exception:
                        pass
                finally:
                    self._save_coalesce[tag] = False

            # Guard against early calls before Qt app initialization
            from PySide6.QtCore import QCoreApplication
            if QCoreApplication.instance() is not None:
                ThreadManager.single_shot(max(0, int(within_ms)), _do_save)
            else:
                # No Qt app yet - perform immediate save
                _do_save()

        try:
            if SettingsManager._on_ui_thread():
                _schedule()
            else:
                ThreadManager.run_on_ui_thread(_schedule)
        except Exception as e:
            # Fallback: perform immediate save to avoid losing state
            try:
                self._logger.debug(f"[SETTINGS] request_save fallback immediate save for tag '{tag}': {e}")
            except Exception:
                pass
            self.save()
    
    def load(self) -> None:
        """Load settings from persistent storage."""
        self._impl.load()
        # After load, migrate, validate, then reconcile without emitting extra signals
        self._apply_migrations()
        self._validate_loaded_settings()
        # No alias reconciliation; only canonical 'theme' is recognized
    
    def get_settings_dir(self) -> Path:
        """Return the directory where settings and auxiliary files live.

        This is a public wrapper over the internal resolver used for colocating
        auxiliary files such as the key passthrough blocklist.
        """
        try:
            return self._resolve_settings_dir()
        except Exception:
            # Best-effort fallback
            from pathlib import Path as _P
            return _P.home() / '.spqmodular'
    
    def reset_to_defaults(self) -> None:
        """Reset all settings to their default values."""
        def _apply():
            self._impl.reset_to_defaults()
            # Notify listeners of all changes
            for key in self._impl._settings_definitions.keys():
                value = self._impl.get(key)
                self.setting_changed.emit(key, value)
            self.save()
        SettingsManager._ensure_on_ui(_apply)
    
    def register_change_handler(self, key: str, handler: Callable[[str, Any], None]) -> None:
        """Register a callback for when a setting changes.
        
        Args:
            key: Setting key to monitor
            handler: Callback function that takes (key, value) parameters
        """
        def _apply():
            if key not in self._handlers:
                self._handlers[key] = []
            # Deduplicate by identity
            if handler not in self._handlers[key]:
                self._handlers[key].append(handler)
        SettingsManager._ensure_on_ui(_apply)
    
    def unregister_change_handler(self, key: str, handler: Callable[[str, Any], None]) -> None:
        """Unregister a previously registered change handler.
        
        Args:
            key: Setting key
            handler: Callback function to remove
        """
        def _apply():
            if key in self._handlers and handler in self._handlers[key]:
                self._handlers[key].remove(handler)
                if not self._handlers[key]:
                    del self._handlers[key]
        SettingsManager._ensure_on_ui(_apply)
    
    def get_setting_definition(self, key: str) -> Optional[SettingDefinition]:
        """Get the definition for a setting.
        
        Args:
            key: Setting key
            
        Returns:
            SettingDefinition if found, None otherwise
        """
        return self._impl.get_setting_definition(key)
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary.
        
        Returns:
            Dictionary of all setting key-value pairs
        """
        return dict(self._impl._settings)
    
    def get_settings_by_category(self, category: SettingsCategory) -> Dict[str, Any]:
        """Get all settings in a specific category.
        
        Args:
            category: Settings category
            
        Returns:
            Dictionary of setting key-value pairs in the specified category
        """
        return {
            key: value for key, value in self._impl._settings.items()
            if (defn := self._impl.get_setting_definition(key)) and defn.category == category
        }

    # --- Internal helpers -------------------------------------------------
    def _apply_migrations(self) -> None:
        """Apply explicit, deterministic migrations to persisted settings.

        Current migrations:
        - Map legacy theme value 'system' to 'dark' for canonical 'theme'.
        - Map legacy graphics.pipeline value 'wgc-d3d11' to 'dxgi'.
        """
        migrated = False
        v = self._impl.get('theme')
        if v == 'system':
            self._logger.info("Migrating theme from 'system' to 'dark'")
            self._impl.set('theme', 'dark')
            migrated = True
        gp = self._impl.get('graphics.pipeline')
        if gp == 'wgc-d3d11':
            self._logger.info("Migrating graphics.pipeline from 'wgc-d3d11' to 'dxgi'")
            self._impl.set('graphics.pipeline', 'dxgi')
            migrated = True
        if migrated:
            # Do not emit signals here; reconciliation and save will follow
            pass
    def _validate_loaded_settings(self) -> None:
        """Validate persisted settings strictly against definitions.

        Raises:
            ValueError: If any persisted value violates type, validator, or options.
        """
        for k, v in list(self._impl._settings.items()):
            defn = self._impl.get_setting_definition(k)
            if not defn:
                continue
            # Enforce exact type, no silent coercion
            if not isinstance(v, defn.setting_type):
                raise ValueError(
                    f"Invalid type for setting {k}: {type(v).__name__}, expected {defn.setting_type.__name__}"
                )
            if defn.validator and not defn.validator(v):
                raise ValueError(f"Invalid value for setting {k}: {v}")
            if defn.options and v not in defn.options:
                opts = ', '.join(map(str, defn.options))
                raise ValueError(f"Invalid value for setting {k}. Must be one of: {opts}")



    # --- Blocklist defaults (KeyPassthrough) ---------------------------------
    def _ensure_settings_file_exists(self) -> None:
        """Create settings.json with defaults if it doesn't exist."""
        try:
            p = Path(self._settings_file) if hasattr(self, '_settings_file') else None
        except Exception:
            p = None
        if p is None:
            return
        if not p.exists():
            # Persist current in-memory defaults to disk
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            self._impl.save(p)
            self._logger.info(f"Created default settings at {p}")

    def _resolve_settings_dir(self) -> Path:
        """Resolve the directory where settings and auxiliary files live.

        Precedence:
        1) If an explicit settings file path was provided, use its parent directory.
        2) Primary: /settings folder next to runtime root
        3) Fallback: settings.json next to executable
        4) Last resort: user config directory (~/.spqmodular)
        """
        # 1) Explicit settings file path provided (for tests)
        try:
            if hasattr(self, '_settings_file') and self._settings_file and self._settings_file != Path():
                explicit_path = Path(self._settings_file)
                if explicit_path.is_absolute():
                    return explicit_path.parent
        except Exception:
            pass

        # 2) Primary: /settings folder next to runtime root
        try:
            runtime_root = get_runtime_root()
            settings_dir = runtime_root / 'settings'
            self._logger.debug(f"[SETTINGS] Primary location: {settings_dir}")
            return settings_dir
        except Exception as e:
            self._logger.warning(f"[SETTINGS] Failed to resolve runtime root: {e}")

        # 3) Fallback: settings.json next to executable
        try:
            if getattr(sys, 'frozen', False):
                exe_dir = Path(sys.executable).parent
                self._logger.debug(f"[SETTINGS] Fallback to exe directory: {exe_dir}")
                return exe_dir
        except Exception as e:
            self._logger.warning(f"[SETTINGS] Failed to resolve exe directory: {e}")

        # 4) Last resort: user config directory
        fallback = Path.home() / '.spqmodular'
        self._logger.debug(f"[SETTINGS] Last resort user config: {fallback}")
        return fallback

    def _ensure_keypassthrough_blocklist_defaults(self) -> None:
        """Create a default key passthrough blocklist file if it doesn't exist.

        - Location: same directory as settings.json (or ~/.spqmodular if not set)
        - Encoding: UTF-8
        - Content: documented header + ~24+ widely-used anti-cheat game executables
        """
        settings_dir = self._resolve_settings_dir()
        try:
            settings_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            # Directory creation failure will be surfaced when opening the file
            pass

        blocklist_path = settings_dir / 'keypassthrough_blocklist.txt'
        if blocklist_path.exists():
            self._logger.debug(f"[KEYPASS] Blocklist present at: {blocklist_path}")
            return

        header = (
            "# KeyPassthrough Blocklist\n"
            "#\n"
            "# How to use (one entry per line):\n"
            "# - You can write plain lines (no JSON) OR a JSON object per line.\n"
            "# - Plain line rules:\n"
            "#   * Ends with .exe  => match by process name (exe), case-insensitive\n"
            "#   * Otherwise       => match window title (contains); if multiple words, ALL must be present\n"
            "# - JSON object rules (advanced):\n"
            "#   {\"exe\": \"cs2.exe\"}\n"
            "#   {\"title_exact\": \"PUBERTY SIMULATOR\"}\n"
            "#   {\"title_contains\": \"genshin impact\"}\n"
            "# - Comments start with # and are ignored. Blank lines are OK. Trailing commas on a line are ignored.\n"
            "#\n"
            "# Default entries (popular online games with anti-cheat):\n"
        )

        # Keep entries conservative and process-name specific
        default_entries = [
            "cs2.exe",
            "VALORANT-Win64-Shipping.exe",
            "FortniteClient-Win64-Shipping.exe",
            "r5apex.exe",
            "TslGame.exe",
            "Overwatch.exe",
            "GenshinImpact.exe",
            "RustClient.exe",
            "DeadByDaylight-Win64-Shipping.exe",
            "EscapeFromTarkov.exe",
            "RainbowSix.exe",
            "Destiny2.exe",
            "FallGuys_client.exe",
            "BF2042.exe",
            "BFV.exe",
            "BF1.exe",
            "NewWorld.exe",
            "ELDENRING.exe",
            "Paladins.exe",
            "Warframe.x64.exe",
            "HaloInfinite.exe",
            "HuntGame.exe",
            "LOSTARK.exe",
            "Prospect-Win64-Shipping.exe",
        ]

        try:
            with open(blocklist_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(header)
                for entry in default_entries:
                    f.write(entry + "\n")
            self._logger.info(
                f"[KEYPASS] Created default key passthrough blocklist at {blocklist_path} with {len(default_entries)} entries"
            )
        except Exception as e:
            self._logger.error(f"[KEYPASS] Failed to write blocklist defaults to {blocklist_path}: {e}", exc_info=True)

