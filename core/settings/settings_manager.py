"""Settings manager implementation for screensaver."""
from typing import Any, Callable, Dict, List, Mapping, Optional
from copy import deepcopy
import math
import threading
import json
import weakref
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QSettings, QObject, Signal
from core.logging.logger import get_logger, is_verbose_logging
from core.settings.default_contract import (
    get_canonical_default,
    require_canonical_default,
)
from core.settings.json_store import (
    SettingsDurabilityError,
    determine_storage_path,
    get_json_settings_store,
)
from core.settings.models import SpotifyVisualizerSettings
from core.settings.structured_roots import STRUCTURED_SETTINGS_ROOTS
from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping
from core.settings.visualizer_retired_modes import strip_retired_visualizer_settings
from core.settings.visualizer_settings_contract import (
    strip_legacy_global_technical_keys,
    strip_legacy_global_visual_keys,
)

_WIDGET_DEFAULT_MERGE_SKIP_KEYS: dict[str, frozenset[str]] = {
    # Migration authorities/version markers must only be written when a section
    # has been normalized from real persisted data. Injecting them during
    # default-merges hides legacy state before its one-time migration runs.
    "spotify_visualizer": frozenset({
        "bubble_gradient_semantics_version",
    }),
}

logger = get_logger('SettingsManager')
_MANAGER_REGISTRY_LOCK = threading.RLock()
_MANAGERS_BY_STORE: "weakref.WeakKeyDictionary[object, weakref.WeakSet[SettingsManager]]" = (
    weakref.WeakKeyDictionary()
)
_NO_EXPLICIT_DEFAULT = object()


class SettingsManager(QObject):
    """Centralized settings management backed by a JSON snapshot."""
    
    # Signal emitted when settings change
    settings_changed = Signal(str, object)  # key, new_value
    _STRUCTURED_ROOTS = STRUCTURED_SETTINGS_ROOTS
    _VISUALIZER_SCHEMA_METADATA_KEY = "visualizer_schema_version"
    _VISUALIZER_SCHEMA_VERSION = 5
    _LEGACY_GLOBAL_PRESET_KEYS = frozenset({"preset", "custom_preset_backup"})
    _RETIRED_WIDGET_SHADOW_KEYS = frozenset({
        "intense_shadow",
        "analog_shadow_intense",
        "digital_shadow_intense",
    })
    _RETIRED_WIDGET_SHADOW_DOTTED_KEYS = frozenset({
        "widgets.clock.analog_shadow_intense",
        "widgets.clock.digital_shadow_intense",
        "widgets.weather.intense_shadow",
        "widgets.media.intense_shadow",
        "widgets.reddit.intense_shadow",
        "widgets.reddit2.intense_shadow",
        "widgets.imgur.intense_shadow",
        "widgets.gmail.intense_shadow",
        # F0.5: the old global magnitude pair is retired; direction + per-bucket
        # Extra Offset replace it. It is dropped on load, never migrated.
        "widgets.shadows.offset",
    })
    _LEGACY_KEY_ALIASES = {
        "input.hard_exit": "input.interaction_mode",
    }
    _MISSING = object()
    _MANUAL_FLOOR_MIN = 0.0
    _MANUAL_FLOOR_MAX = 1.0
    
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
            if application == "Screensaver" and storage_base_dir is None:
                from core.settings.storage_paths import detect_current_profile
                app_name = detect_current_profile(default="Screensaver")
        except Exception as exc:
            logger.debug("[SETTINGS] Exception suppressed: %s", exc, exc_info=True)

        storage_path = determine_storage_path(app_name, base_dir=storage_base_dir)
        self._settings = get_json_settings_store(
            storage_path=storage_path,
            profile=app_name,
        )
        self._organization = organization
        self._application = app_name
        self._storage_path = storage_path
        self._storage_base_dir = storage_base_dir
        # Managers sharing one profile path also share the store operation
        # lock.  A cache miss therefore cannot read an old store value and
        # repopulate the shared cache after a peer mutation invalidates it.
        self._lock = self._settings.manager_operation_lock()
        self._change_handlers: Dict[str, List[Callable]] = {}
        
        # In-memory cache for frequently accessed settings (P2 optimization)
        self._cache = self._settings.manager_cache()
        self._cache_lock = self._settings.manager_cache_lock()
        self._cache_enabled = True
        with _MANAGER_REGISTRY_LOCK:
            managers = _MANAGERS_BY_STORE.get(self._settings)
            if managers is None:
                managers = weakref.WeakSet()
                _MANAGERS_BY_STORE[self._settings] = managers
            managers.add(self)

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

        try:
            self._migrate_legacy_setting_aliases()
        except Exception:
            logger.debug("Legacy settings alias migration failed", exc_info=True)

        try:
            self._normalize_structured_root_storage()
        except Exception:
            logger.debug("Structured settings-root normalization failed", exc_info=True)

        # Initialize defaults
        self._set_defaults()

        # Repair invalid persisted widget-family capability dependencies (e.g.
        # media=False must force visualizers=False) durably, after defaults are
        # merged so a missing dependent key is resolved before normalization.
        try:
            self._normalize_persisted_widget_capability_state()
        except Exception:
            logger.debug("Widget capability dependency normalization failed", exc_info=True)

        try:
            self._run_persisted_visualizer_schema_migrations()
        except Exception:
            logger.debug("Persisted visualizer schema migration failed", exc_info=True)

        try:
            self.validate_and_repair()
        except Exception:
            logger.debug("Settings validation failed", exc_info=True)

        # Clean up obsolete settings for hygiene
        try:
            self.cleanup_obsolete_settings()
        except Exception:
            logger.debug("Settings cleanup failed", exc_info=True)
        try:
            self.cleanup_legacy_global_preset_state()
        except Exception:
            logger.debug("Legacy global preset cleanup failed", exc_info=True)

        # Startup is the first explicit durability boundary.  Runtime changes
        # are admitted to the ordered writer without holding the GUI thread;
        # construction finishes only after migrations/default repair are on
        # disk so a second manager for the same profile cannot start stale.
        if not self._settings.flush(timeout=5.0):
            logger.warning(
                "[SETTINGS_PERSIST] Startup durability flush failed for %s",
                storage_path,
            )

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
        # User-specific sources must remain empty by default so new installs
        # never inherit local paths. Detection of Pictures folders now happens
        # only when the user explicitly selects sources.
        return []

    @classmethod
    def _canonicalize_key(cls, key: str) -> str:
        """Return the canonical dotted key for a possibly legacy alias."""
        return cls._LEGACY_KEY_ALIASES.get(str(key), str(key))

    def _migrate_legacy_setting_aliases(self) -> None:
        """Forward-migrate retired dotted keys to their canonical names."""
        migrated: list[tuple[str, str]] = []
        with self._lock:
            for legacy_key, canonical_key in self._LEGACY_KEY_ALIASES.items():
                if not self._settings.contains(legacy_key):
                    continue
                legacy_value = self._settings.value(legacy_key)
                if not self._settings.contains(canonical_key):
                    self._settings.setValue(canonical_key, legacy_value)
                    migrated.append((legacy_key, canonical_key))
                self._settings.remove(legacy_key)

            if migrated:
                self._settings.sync()
                self._clear_cache_locked()

        if migrated:
            logger.info("Migrated legacy setting aliases: %s", migrated)

    @staticmethod
    def _assign_nested_if_missing(
        target: Dict[str, Any],
        parts: List[str],
        value: Any,
    ) -> bool:
        """Assign one dotted compatibility value without overriding canonical shape."""

        if not parts:
            return False
        current: Dict[str, Any] = target
        for part in parts[:-1]:
            existing = current.get(part, SettingsManager._MISSING)
            if existing is SettingsManager._MISSING:
                child: Dict[str, Any] = {}
                current[part] = child
                current = child
                continue
            if not isinstance(existing, Mapping):
                return False
            child = dict(existing)
            current[part] = child
            current = child
        leaf = parts[-1]
        if leaf in current:
            return False
        current[leaf] = deepcopy(value)
        return True

    @classmethod
    def _normalize_structured_mapping_shape(
        cls,
        mapping: Mapping[str, Any],
    ) -> tuple[Dict[str, Any], bool]:
        """Expand dotted compatibility members inside one structured mapping.

        Older reset/SST paths could serialize ``ui`` as e.g.
        ``{"dialog_geometry.width": 1389}`` even though ``ui`` is explicitly a
        structured root.  Nested members are authoritative when both forms are
        present; dotted members only fill missing paths and are then retired.
        """

        normalized: Dict[str, Any] = {}
        dotted_members: list[tuple[str, Any]] = []
        changed = False
        for key, value in mapping.items():
            key_text = str(key)
            if "." in key_text:
                dotted_members.append((key_text, value))
                changed = True
                continue
            # Only the root's member names are a persistence-shape concern.
            # Nested mappings can legitimately contain semantic dotted keys
            # (for example Widget Theme colour-role names such as
            # ``card.background``), so never reinterpret them here.
            normalized[key_text] = deepcopy(value)

        for dotted, value in dotted_members:
            cls._assign_nested_if_missing(
                normalized,
                [part for part in dotted.split(".") if part],
                value,
            )
        return normalized, changed

    def _normalize_structured_root_storage(self) -> None:
        """Repair structured roots that were flattened by older persistence paths."""

        repaired_roots: list[str] = []
        with self._lock:
            all_keys = list(self._settings.allKeys())
            # Normalize every declared structured root. Older QSettings/reset/SST
            # paths could leave either a root mapping containing dotted members
            # or separate ``root.member`` store keys. Nested values win; flat
            # compatibility members only fill missing paths and are then retired.
            for root in sorted(self._STRUCTURED_ROOTS):
                raw_root = self._settings.value(root, self._MISSING)
                if isinstance(raw_root, Mapping):
                    normalized, changed = self._normalize_structured_mapping_shape(raw_root)
                else:
                    normalized = {}
                    changed = False

                prefix = f"{root}."
                flat_keys = [key for key in all_keys if str(key).startswith(prefix)]
                for flat_key in flat_keys:
                    tail = str(flat_key)[len(prefix):]
                    self._assign_nested_if_missing(
                        normalized,
                        [part for part in tail.split(".") if part],
                        self._settings.value(flat_key),
                    )
                    self._settings.remove(flat_key)
                    changed = True

                if changed:
                    self._settings.setValue(root, normalized)
                    repaired_roots.append(root)

            if repaired_roots:
                self._settings.sync()
                self._clear_cache_locked()

        if repaired_roots:
            logger.info(
                "Normalized flattened structured settings roots: %s",
                repaired_roots,
            )
    
    def _set_defaults(self) -> None:
        """Merge every canonical product default without overwriting user state.

        The runtime store projection from :func:`get_flat_defaults` is the one
        serialization authority shared with Reset and tooling.  Do not maintain
        another top-level section allow-list or local flattening algorithm here.
        """
        from core.settings.defaults import get_flat_defaults

        canonical_store = get_flat_defaults(self._application)

        for key, value in canonical_store.items():
            if key in self._LEGACY_GLOBAL_PRESET_KEYS:
                continue

            if key == 'widgets' and isinstance(value, Mapping):
                # Widget merging has additional visualizer migration rules.
                self._ensure_widgets_defaults(dict(value))
                continue
            if key == 'transitions' and isinstance(value, Mapping):
                self._ensure_transitions_defaults(dict(value))
                continue
            if key in self._STRUCTURED_ROOTS and isinstance(value, Mapping):
                self._ensure_structured_root_defaults(key, value)
                continue

            if not self._settings.contains(key):
                self._settings.setValue(key, deepcopy(value))

    @staticmethod
    def _merge_missing_mapping_defaults(
        existing: Mapping[str, Any],
        defaults: Mapping[str, Any],
    ) -> tuple[Dict[str, Any], bool]:
        """Deep-fill missing mapping leaves while preserving existing values."""

        merged: Dict[str, Any] = deepcopy(dict(existing))
        changed = False
        for key, default_value in defaults.items():
            if key not in merged:
                merged[key] = deepcopy(default_value)
                changed = True
                continue
            existing_value = merged[key]
            if isinstance(existing_value, Mapping) and isinstance(default_value, Mapping):
                child, child_changed = SettingsManager._merge_missing_mapping_defaults(
                    existing_value,
                    default_value,
                )
                if child_changed:
                    merged[key] = child
                    changed = True
        return merged, changed

    def _ensure_structured_root_defaults(
        self,
        root: str,
        defaults: Mapping[str, Any],
    ) -> None:
        """Seed/merge one declared structured root without flattening it."""

        with self._lock:
            raw = self._settings.value(root, self._MISSING)
            if raw is self._MISSING or not isinstance(raw, Mapping):
                self._settings.setValue(root, deepcopy(dict(defaults)))
                return
            merged, changed = self._merge_missing_mapping_defaults(raw, defaults)
            if changed:
                self._settings.setValue(root, merged)

    @staticmethod
    def _normalize_widgets_mapping(value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        widgets = dict(value)
        vis_section = widgets.get("spotify_visualizer")
        if isinstance(vis_section, Mapping):
            widgets["spotify_visualizer"] = normalize_visualizer_section_mapping(
                vis_section,
                apply_preset_overlay=False,
            )
        return widgets

    def _store_widgets_root_locked(self, value: Any) -> Dict[str, Any]:
        """Persist the canonical widgets root under the current lock."""
        normalized = self._normalize_widgets_mapping(value)
        widgets_dict = dict(normalized) if isinstance(normalized, Mapping) else {}
        self._settings.setValue('widgets', widgets_dict)
        return widgets_dict

    def _store_transitions_root_locked(self, value: Any) -> Dict[str, Any]:
        """Persist the canonical transitions root under the current lock."""
        transitions_dict = dict(value) if isinstance(value, Mapping) else {}
        self._settings.setValue('transitions', transitions_dict)
        return transitions_dict

    def _visualizer_schema_version(self) -> int:
        """Return the persisted visualizer schema version from metadata."""
        try:
            raw = self._settings.metadata().get(self._VISUALIZER_SCHEMA_METADATA_KEY, 0)
            return int(raw)
        except Exception:
            return 0

    def _mark_visualizer_schema_current_locked(self) -> None:
        """Record that persisted visualizer settings match the current schema."""
        if self._visualizer_schema_version() >= self._VISUALIZER_SCHEMA_VERSION:
            return
        self._settings.update_metadata(
            **{self._VISUALIZER_SCHEMA_METADATA_KEY: self._VISUALIZER_SCHEMA_VERSION}
        )

    def _normalize_persisted_widget_capability_state(self) -> None:
        """Durably repair invalid persisted widget-family capability deps at load.

        A persisted/migrated state that violates a family dependency — most
        importantly ``media=False`` with ``visualizers`` still activated (or its
        activation key missing, which resolves to activated) — must not remain
        latent, or a later Media reactivation would silently re-enable
        Visualizers. This runs the ONE canonical dependency authority
        (``capability_activation.normalize_widget_capability_state``) over the
        current widgets root after defaults have been merged, and persists any
        repair through the low-level store (no ``settings_changed`` emission, so
        no signal/save recursion even if a Settings dialog is later open). It
        never introduces a second dependency rule and never auto-activates a
        dependency (Media is never turned back on to satisfy Visualizers).
        """
        import copy as _copy
        from core.settings.capability_activation import (
            normalize_widget_capability_state,
        )

        with self._lock:
            widgets = self._settings.value('widgets', {})
            if not isinstance(widgets, Mapping):
                return
            widgets_copy = _copy.deepcopy(dict(widgets))
            if not normalize_widget_capability_state(widgets_copy):
                return
            self._store_widgets_root_locked(widgets_copy)
            self._settings.sync()
            self._clear_cache_locked()
            logger.info(
                "Repaired persisted widget capability dependency state "
                "(e.g. media=False forces visualizers=False)"
            )

    def _run_persisted_visualizer_schema_migrations(self) -> None:
        """Normalize persisted visualizer settings only when schema advances."""
        with self._lock:
            schema_version = self._visualizer_schema_version()
            if schema_version >= self._VISUALIZER_SCHEMA_VERSION:
                return

            widgets = self._settings.value('widgets', {})
            if isinstance(widgets, Mapping):
                widgets_dict = dict(widgets)
                vis_section = widgets_dict.get('spotify_visualizer')
                if isinstance(vis_section, Mapping):
                    normalized_vis = normalize_visualizer_section_mapping(
                        vis_section,
                        apply_preset_overlay=False,
                    )
                    if dict(vis_section) != normalized_vis:
                        widgets_dict['spotify_visualizer'] = normalized_vis
                        self._store_widgets_root_locked(widgets_dict)

            if schema_version < 5:
                from core.settings.visualizer_presets import (
                    normalize_visualizer_custom_snapshot_cache,
                )

                raw_cache = self._settings.value('visualizer_custom_presets', None)
                if raw_cache is not None:
                    try:
                        normalized_cache = normalize_visualizer_custom_snapshot_cache(
                            raw_cache
                        )
                    except (TypeError, ValueError):
                        logger.warning(
                            "[VIS_PRESETS] Refusing malformed Custom-cache migration",
                            exc_info=True,
                        )
                        raise
                    if dict(raw_cache) != normalized_cache:
                        self._settings.setValue(
                            'visualizer_custom_presets',
                            normalized_cache,
                        )

            self._mark_visualizer_schema_current_locked()
            self._settings.sync()

    def _ensure_transitions_defaults(self, default_transitions: Dict[str, Any]) -> None:
        with self._lock:
            raw_transitions = self._settings.value('transitions', None)
            if isinstance(raw_transitions, Mapping):
                transitions: Dict[str, Any] = dict(raw_transitions)
            else:
                transitions = {}

            changed = False
            block_flip = transitions.get('block_flip')
            if isinstance(block_flip, Mapping) and 'columns' in block_flip:
                normalized_block_flip = dict(block_flip)
                normalized_block_flip['cols'] = normalized_block_flip.pop(
                    'columns'
                )
                transitions['block_flip'] = normalized_block_flip
                changed = True

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

            changed = merge(transitions, default_transitions) or changed
            if changed or not isinstance(raw_transitions, Mapping):
                self._store_transitions_root_locked(transitions)
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
                    skip_keys = _WIDGET_DEFAULT_MERGE_SKIP_KEYS.get(section_name, frozenset())
                    for k, v in section_defaults.items():
                        if k in skip_keys and k not in section_dict:
                            continue
                        if k not in section_dict:
                            section_dict[k] = v
                            changed = True
                    widgets[section_name] = section_dict
                else:
                    # Entire section missing or invalid – adopt defaults.
                    section_dict = dict(section_defaults)
                    if section_name == 'spotify_visualizer':
                        section_dict = normalize_visualizer_section_mapping(
                            section_dict,
                            apply_preset_overlay=False,
                            resolve_preset_indices=False,
                        )
                    widgets[section_name] = section_dict
                    changed = True

            if not isinstance(raw_widgets, Mapping):
                self._store_widgets_root_locked(widgets)
                self._settings.sync()
            elif changed:
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
        defaults = get_default_settings(self._application)
        widgets_defaults = defaults['widgets']

        key = str(section) if section is not None else ''
        base = widgets_defaults.get(key, {})
        return dict(base) if isinstance(base, Mapping) else {}
                
    def get(self, key: str, default: Any = _NO_EXPLICIT_DEFAULT) -> Any:
        """Get a setting value through the canonical product-default authority.

        For a persisted product key present in the canonical defaults/profile
        overlay, that canonical value is *always* the missing-value default. Any
        historical call-site literal passed as ``default`` is deliberately ignored
        for canonical product keys so it cannot become a shadow authority.

        Explicit defaults remain meaningful only for intentionally non-product
        runtime/session keys that have no canonical default.
        """
        def to_plain(obj: Any) -> Any:
            if isinstance(obj, Mapping):
                return {k: to_plain(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [to_plain(v) for v in obj]
            return obj

        key = self._canonicalize_key(key)
        default_was_explicit = default is not _NO_EXPLICIT_DEFAULT
        canonical_default = get_canonical_default(
            key,
            self._application,
            missing=self._MISSING,
        )
        canonical_key = canonical_default is not self._MISSING
        if canonical_key:
            default = canonical_default
        elif not default_was_explicit:
            default = None

        with self._lock:
            # Canonical product keys have one stable cache identity regardless of
            # obsolete caller literals. Transient/session keys retain the caller's
            # explicit-default identity.
            cache_default_key = "canonical" if canonical_key else id(default)
            cache_key = f"{key}:{cache_default_key}"
            if self._cache_enabled:
                with self._cache_lock:
                    cached = self._cache.get(cache_key, self._MISSING)
                if cached is not self._MISSING:
                    return cached

            structured_value = self._get_structured_value_locked(key)
            if structured_value is not self._MISSING:
                value = structured_value
            else:
                value = self._settings.value(key, default)

            if isinstance(value, Mapping):
                return to_plain(value)

            # Some QSettings backends (notably on Windows) round-trip
            # QVariantList items as strings. Normalize critical list-valued
            # settings before publishing them to the shared cache.
            dotted = str(key) if key is not None else ""
            if dotted == "display.show_on_monitors" and isinstance(value, list):
                coerced: list[Any] = []
                for item in value:
                    try:
                        coerced.append(int(item))
                    except Exception as exc:
                        logger.debug(
                            "[SETTINGS] Exception suppressed: %s",
                            exc,
                            exc_info=True,
                        )
                        coerced.append(item)
                if self._cache_enabled:
                    with self._cache_lock:
                        self._cache[cache_key] = coerced
                return coerced

            # Cache the result before releasing the shared store operation
            # lock so a peer mutation cannot invalidate and then be followed
            # by this older read repopulating the cache.
            if self._cache_enabled:
                with self._cache_lock:
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
        """Return a bool using the canonical product default when one exists.

        The explicit *default* remains available for transient/session keys only;
        persisted product booleans cannot acquire a second fallback authority here.
        """
        canonical = get_canonical_default(
            self._canonicalize_key(key),
            self._application,
            missing=self._MISSING,
        )
        bool_default = canonical if isinstance(canonical, bool) else bool(default)
        # For persisted product booleans, the canonical value must also be the
        # storage-read default. Otherwise a missing canonical-True key first
        # becomes the method signature's False before coercion can repair it.
        read_default = bool_default if isinstance(canonical, bool) else bool(default)
        raw = self.get(key, read_default)
        return self.to_bool(raw, bool_default)

    def get_application_name(self) -> str:
        """Return the resolved application profile owned by this manager."""
        return self._application

    def get_storage_path(self) -> Path:
        """Return the active JSON settings file path."""
        return self._storage_path

    def get_settings_dir(self) -> Path:
        """Return the directory containing the active settings profile."""
        return self._storage_path.parent

    def get_organization_name(self) -> str:
        """Return the organization identity owned by this manager."""
        return self._organization

    @staticmethod
    def _to_plain_value(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {k: SettingsManager._to_plain_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [SettingsManager._to_plain_value(v) for v in value]
        return value

    def _coerce_import_value(self, key: str, value: Any) -> Any:
        """Coerce one imported leaf from its canonical schema value.

        Type policy comes from the canonical defaults/profile overlay rather than a
        hand-maintained key list. Unknown/session keys remain transport-transparent.
        Invalid canonical product values fall back to the canonical value.
        """

        dotted = self._canonicalize_key(str(key) if key is not None else "")
        canonical = get_canonical_default(
            dotted,
            self._application,
            missing=self._MISSING,
        )
        if canonical is self._MISSING:
            return self._to_plain_value(value)

        try:
            if isinstance(canonical, bool):
                return self.to_bool(value, default=canonical)
            if isinstance(canonical, int) and not isinstance(canonical, bool):
                return int(value)
            if isinstance(canonical, float):
                return float(value)
            if isinstance(canonical, str):
                return canonical if value is None else str(value)
            if isinstance(canonical, list):
                if isinstance(value, (list, tuple)):
                    return [self._to_plain_value(item) for item in value]
                return deepcopy(canonical)
            if isinstance(canonical, Mapping):
                if isinstance(value, Mapping):
                    return self._to_plain_value(value)
                return deepcopy(canonical)
            # ``None`` deliberately means the canonical schema does not constrain
            # the payload type (for example Use Theme / optional values).
            if canonical is None:
                return self._to_plain_value(value)
        except (TypeError, ValueError, OverflowError):
            logger.debug(
                "Failed to coerce SST value for %s=%r; using canonical default",
                dotted,
                value,
                exc_info=True,
            )
            return deepcopy(canonical)

        return self._to_plain_value(value)

    def set(self, key: str, value: Any) -> None:
        """
        Set a setting value.
        
        Args:
            key: Setting key in dot notation
            value: Value to set
        """
        key = self._canonicalize_key(key)
        with self._lock:
            handled, old_value = self._set_structured_value_locked(key, value)
            if not handled:
                if key == "widgets" and isinstance(value, Mapping):
                    old_value = self._settings.value(key)
                    value = self._store_widgets_root_locked(dict(value))
                    self._mark_visualizer_schema_current_locked()
                elif key == "transitions" and isinstance(value, Mapping):
                    old_value = self._settings.value(key)
                    value = self._store_transitions_root_locked(dict(value))
                else:
                    old_value = self._settings.value(key)
                    self._settings.setValue(key, value)

            # Invalidate cache entries for this key/root (P2 optimization)
            self._invalidate_cache_for_key_locked(key)

            # Every semantic mutation enters the process-owned ordered writer.
            # Complete pending snapshots from this same store may coalesce;
            # in-memory visibility, cache invalidation, and notification do not.
            self._settings.sync()

        self._publish_store_change(key, value, old_value)

        # Compact logging by default so large nested maps (e.g. 'widgets')
        # do not flood the log. When verbose logging is enabled we still
        # include the full before/after values for deep debugging.
        if is_verbose_logging():
            logger.debug("Setting changed: %s: %r -> %r", key, old_value, value)
        else:
            logger.debug("Setting changed: %s", key)

    def replace_visualizer_runtime_preset_state(
        self,
        visualizer_section: Mapping[str, Any],
        custom_presets: Mapping[str, Any],
    ) -> None:
        """Atomically persist one runtime preset result and its Custom cache.

        H8 must replace only the ``spotify_visualizer`` child while preserving
        Media and every other widget sibling.  The dedicated Custom-cache root
        is the sole companion write.  Both mappings enter the ordered writer in
        one store revision so a restart cannot observe half of the preset move.
        """

        if not isinstance(visualizer_section, Mapping):
            raise TypeError("visualizer_section must be a mapping")
        if not isinstance(custom_presets, Mapping):
            raise TypeError("custom_presets must be a mapping")

        from core.settings.visualizer_presets import (
            normalize_visualizer_custom_snapshot_cache,
        )

        normalized_section = normalize_visualizer_section_mapping(
            dict(visualizer_section),
            apply_preset_overlay=False,
            resolve_preset_indices=False,
        )
        normalized_cache = normalize_visualizer_custom_snapshot_cache(
            custom_presets
        )

        with self._lock:
            raw_widgets = self._settings.value('widgets', {})
            widgets = dict(raw_widgets) if isinstance(raw_widgets, Mapping) else {}
            old_section = deepcopy(widgets.get('spotify_visualizer'))
            old_cache = self._settings.value('visualizer_custom_presets', {})
            widgets['spotify_visualizer'] = deepcopy(normalized_section)
            self._store_widgets_root_locked(widgets)
            self._settings.setValue(
                'visualizer_custom_presets',
                deepcopy(normalized_cache),
            )
            self._mark_visualizer_schema_current_locked()
            self._invalidate_cache_for_key_locked('widgets.spotify_visualizer')
            self._invalidate_cache_for_key_locked('visualizer_custom_presets')
            self._settings.sync()

        self._publish_store_change(
            'widgets.spotify_visualizer',
            deepcopy(normalized_section),
            old_section,
        )
        if old_cache != normalized_cache:
            self._publish_store_change(
                'visualizer_custom_presets',
                deepcopy(normalized_cache),
                old_cache,
            )
        logger.info(
            "[VIS_PRESETS] Persisted runtime visualizer child and Custom cache"
        )

    def _invalidate_cache_for_key_locked(self, key: str) -> None:
        """Invalidate cached values tied to *key* (and descendants)."""
        if not self._cache_enabled:
            return
        key_text = str(key or "")
        with self._cache_lock:
            if not key_text or key_text == "*":
                self._cache.clear()
                return
            key_root = key_text.split(".", 1)[0]
            keys_to_remove: list[str] = []
            for cache_key in list(self._cache.keys()):
                cache_name = cache_key.split(":", 1)[0]
                if not cache_name:
                    keys_to_remove.append(cache_key)
                    continue
                if (
                    cache_name == key_text
                    or cache_name.startswith(f"{key_text}.")
                    or cache_name == key_root
                    or cache_name.startswith(f"{key_root}.")
                ):
                    keys_to_remove.append(cache_key)
            for cache_key in keys_to_remove:
                self._cache.pop(cache_key, None)

    def _clear_cache_locked(self) -> None:
        """Clear the in-memory settings cache after bulk store mutations."""
        if not self._cache_enabled:
            return
        with self._cache_lock:
            self._cache.clear()

    def _publish_store_change(self, key: str, value: Any, old_value: Any) -> None:
        """Synchronously notify every live manager sharing this store."""

        with _MANAGER_REGISTRY_LOCK:
            registered = list(_MANAGERS_BY_STORE.get(self._settings, ()))
        managers = [self, *(manager for manager in registered if manager is not self)]
        for manager in managers:
            try:
                with manager._lock:
                    manager._invalidate_cache_for_key_locked(key)
                    handlers = list(manager._change_handlers.get(key, ()))
                manager.settings_changed.emit(key, value)
                for handler in handlers:
                    try:
                        handler(value, old_value)
                    except Exception:
                        logger.error(
                            "Error in change handler for %s",
                            key,
                            exc_info=True,
                        )
            except RuntimeError:
                # A weakly-held QObject wrapper may be in final destruction.
                continue

    def set_many(self, values: Mapping[str, Any]) -> None:
        """Set multiple settings in one call."""
        for k, v in values.items():
            self.set(k, v)

    # Typed helpers -----------------------------------------------------
    def get_spotify_visualizer_settings(self) -> SpotifyVisualizerSettings:
        """Return typed settings for the Spotify visualizer widget."""
        return SpotifyVisualizerSettings.from_settings(self)

    def set_spotify_visualizer_settings(self, model: SpotifyVisualizerSettings) -> None:
        """Persist one typed visualizer snapshot as an atomic widgets-root write.

        Build the complete section first, then normalize and persist it through
        one widgets-root transaction while preserving every sibling widget.
        """
        prefix = "widgets.spotify_visualizer."
        visualizer_section = {
            key[len(prefix):]: value
            for key, value in model.to_dict().items()
            if key.startswith(prefix)
        }

        with self._lock:
            stored_widgets = self._settings.value("widgets", {})
            widgets = dict(stored_widgets) if isinstance(stored_widgets, Mapping) else {}
            widgets["spotify_visualizer"] = visualizer_section
            widgets = self._store_widgets_root_locked(widgets)
            self._invalidate_cache_for_key_locked("widgets")
            self._settings.sync()

        self._publish_store_change("widgets", widgets, stored_widgets)
        logger.debug("Spotify visualizer settings persisted as one normalized widgets root")

    def reset_visualizers_to_defaults(self) -> None:
        """Reset only the spotify visualizer settings to canonical defaults."""
        from core.settings.defaults import get_default_settings

        defaults = get_default_settings(self._application)
        widgets_defaults = defaults['widgets']
        vis_defaults = widgets_defaults.get('spotify_visualizer', {})
        if not isinstance(vis_defaults, Mapping):
            logger.debug("No spotify_visualizer defaults found during reset request")
            return

        normalized_defaults = normalize_visualizer_section_mapping(
            vis_defaults,
            apply_preset_overlay=False,
        )
        widgets = self.get('widgets')
        if isinstance(widgets, Mapping):
            widgets_dict = dict(widgets)
        else:
            widgets_dict = {}
        widgets_dict['spotify_visualizer'] = normalized_defaults
        self.set('widgets', widgets_dict)

    def save(self) -> None:
        """Request ordered persistence of the current in-memory revision."""
        with self._lock:
            self._settings.sync()
        logger.debug("Settings persistence requested")

    def flush(self, timeout: float = 5.0) -> bool:
        """Wait for the current revision to reach durable storage."""

        # JsonSettingsStore releases its operation lock before waiting for the
        # writer acknowledgement.  Do not hold the same shared lock here: the
        # writer callback needs it to publish the durable revision.
        success = self._settings.flush(timeout=timeout)
        if success:
            logger.debug("Settings persistence flush complete")
        else:
            logger.warning("[SETTINGS_PERSIST] Settings flush failed or timed out")
        return success

    def persistence_snapshot(self) -> Dict[str, Any]:
        """Return passive ordered-persistence state for diagnostics/tests."""

        return self._settings.persistence_snapshot()

    def load(self) -> None:
        """Load settings from persistent storage."""
        try:
            if not self._settings.flush(timeout=5.0):
                logger.error(
                    "[SETTINGS_PERSIST] Refusing reload after durability flush failure"
                )
                return
            # JsonSettingsStore owns the cross-manager revision barrier.  Do
            # not hold this manager's lock while it waits, or a peer mutation's
            # synchronous signal fanout could deadlock on this manager.
            self._settings.load()
            with self._lock:
                self._clear_cache_locked()
        except SettingsDurabilityError as exc:
            logger.error(
                "[SETTINGS_PERSIST] Refusing reload across failed boundary: %s",
                exc,
            )
            return
        except Exception as exc:
            logger.error("Failed to load settings: %s", exc, exc_info=True)
            # Non-durability load failures retain the historical repair path.
            try:
                self.reset_to_defaults()
            except Exception:
                logger.exception("Failed to reset settings after load failure")
            return
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
                    self._settings.setValue('sources.folders', require_canonical_default('sources.folders', self._application))
                repairs['sources.folders'] = f"Invalid type: {type(folders).__name__}"
            
            # Validate sources.rss_feeds - must be list
            rss_feeds = self._settings.value('sources.rss_feeds')
            if rss_feeds is not None and not isinstance(rss_feeds, list):
                logger.warning(f"Repairing sources.rss_feeds: was {type(rss_feeds).__name__}, expected list")
                if isinstance(rss_feeds, str):
                    self._settings.setValue('sources.rss_feeds', [rss_feeds] if rss_feeds else [])
                else:
                    self._settings.setValue('sources.rss_feeds', require_canonical_default('sources.rss_feeds', self._application))
                repairs['sources.rss_feeds'] = f"Invalid type: {type(rss_feeds).__name__}"
            
            # Validate timing.interval - must be positive number
            interval = self._settings.value('timing.interval')
            if interval is not None:
                try:
                    interval_val = int(interval)
                    if interval_val < 1:
                        logger.warning(f"Repairing timing.interval: {interval_val} < 1")
                        self._settings.setValue(
                            'timing.interval',
                            require_canonical_default('timing.interval', self._application),
                        )
                        repairs['timing.interval'] = f"Out of range: {interval_val}"
                    elif interval_val > 3600:
                        logger.warning(f"Repairing timing.interval: {interval_val} > 3600")
                        self._settings.setValue(
                            'timing.interval',
                            require_canonical_default('timing.interval', self._application),
                        )
                        repairs['timing.interval'] = f"Out of range: {interval_val}"
                except (ValueError, TypeError):
                    logger.warning(f"Repairing timing.interval: invalid value {interval!r}")
                    self._settings.setValue(
                        'timing.interval',
                        require_canonical_default('timing.interval', self._application),
                    )
                    repairs['timing.interval'] = f"Invalid value: {interval!r}"
            
            # Validate display.mode - must be valid enum
            display_mode = self._settings.value('display.mode')
            valid_modes = {'fill', 'fit', 'shrink', 'stretch', 'center'}
            if display_mode is not None and display_mode not in valid_modes:
                logger.warning(f"Repairing display.mode: {display_mode!r} not in {valid_modes}")
                self._settings.setValue(
                    'display.mode',
                    require_canonical_default('display.mode', self._application),
                )
                repairs['display.mode'] = f"Invalid value: {display_mode!r}"

            # Validate display.render_backend_mode - must be valid enum
            backend_mode = self._settings.value('display.render_backend_mode')
            valid_backends = {'opengl', 'software'}
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
                    self._settings.setValue(
                        'display.render_backend_mode',
                        require_canonical_default('display.render_backend_mode', self._application),
                    )
                    repairs['display.render_backend_mode'] = f"Invalid value: {backend_mode!r}"

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

            # Validate widgets - must be dict
            widgets = self._settings.value('widgets')
            if widgets is not None and not isinstance(widgets, Mapping):
                logger.warning(f"Repairing widgets: was {type(widgets).__name__}, expected mapping")
                from core.settings.defaults import get_default_settings
                canonical_widgets = get_default_settings(self._application).get('widgets')
                if not isinstance(canonical_widgets, Mapping):
                    raise RuntimeError("Canonical defaults are missing the widgets root")
                self._store_widgets_root_locked(dict(canonical_widgets))
                repairs['widgets'] = f"Invalid type: {type(widgets).__name__}"
            elif isinstance(widgets, Mapping):
                vis_section = widgets.get('spotify_visualizer')  # type: ignore[index]
                if isinstance(vis_section, Mapping):
                    repaired_vis = strip_retired_visualizer_settings(vis_section)
                    repaired_vis = strip_legacy_global_technical_keys(repaired_vis)
                    repaired_vis = strip_legacy_global_visual_keys(repaired_vis)
                    if dict(vis_section) != repaired_vis:
                        for key, old_value in dict(vis_section).items():
                            if key in repaired_vis:
                                continue
                            repairs[f'widgets.spotify_visualizer.{key}'] = (
                                "Removed retired visualizer key"
                            )
                        widgets_copy = dict(widgets)
                        widgets_copy['spotify_visualizer'] = repaired_vis
                        self._store_widgets_root_locked(widgets_copy)
                        widgets = widgets_copy
                        repairs['widgets.spotify_visualizer'] = "Normalized retired visualizer keys"
                clamp_repairs = self._clamp_visualizer_manual_floors(widgets)
                if clamp_repairs:
                    repairs.update(clamp_repairs)

            # Validate transitions - must be dict
            transitions = self._settings.value('transitions')
            if transitions is not None and not isinstance(transitions, Mapping):
                logger.warning(f"Repairing transitions: was {type(transitions).__name__}, expected mapping")
                from core.settings.defaults import get_default_settings
                canonical_transitions = get_default_settings(self._application).get('transitions')
                if not isinstance(canonical_transitions, Mapping):
                    raise RuntimeError("Canonical defaults are missing the transitions root")
                self._store_transitions_root_locked(dict(canonical_transitions))
                repairs['transitions'] = f"Invalid type: {type(transitions).__name__}"
            
            if repairs:
                self._clear_cache_locked()
                self._settings.sync()
                logger.info(f"Settings validation repaired {len(repairs)} issues: {list(repairs.keys())}")
            else:
                logger.debug("Settings validation passed - no repairs needed")
        
        return repairs

    def _clamp_visualizer_manual_floors(self, widgets_map: Mapping[str, Any]) -> Dict[str, str]:
        """Clamp spotify visualizer manual floor values within the supported range."""

        vis_section = widgets_map.get('spotify_visualizer')  # type: ignore[index]
        if not isinstance(vis_section, Mapping):
            return {}

        vis_config = dict(vis_section)
        widgets_copy = dict(widgets_map)
        repairs: Dict[str, str] = {}
        changed = False

        for key, value in list(vis_config.items()):
            if not key.endswith('manual_floor'):
                continue

            needs_cast = not isinstance(value, (int, float))
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                canonical_floor = require_canonical_default(
                    f"widgets.spotify_visualizer.{key}",
                    self._application,
                )
                numeric_value = float(canonical_floor)
                needs_cast = True

            clamped = min(max(numeric_value, self._MANUAL_FLOOR_MIN), self._MANUAL_FLOOR_MAX)
            requires_update = needs_cast or not math.isclose(numeric_value, clamped, rel_tol=1e-9, abs_tol=1e-9)

            if requires_update:
                vis_config[key] = clamped
                changed = True
                repairs[f"widgets.spotify_visualizer.{key}"] = (
                    f"Manual floor normalized to {clamped:.2f} (range {self._MANUAL_FLOOR_MIN:.2f}-{self._MANUAL_FLOOR_MAX:.2f})"
                )

        if changed:
            widgets_copy['spotify_visualizer'] = vis_config
            self._store_widgets_root_locked(widgets_copy)

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
        """Reset all settings to default values, preserving configured user data."""
        from core.settings.defaults import PRESERVE_ON_RESET
        
        with self._lock:
            # Preserve user-specific data before clearing
            preserved: dict[str, Any] = {}
            for key in sorted(PRESERVE_ON_RESET):
                structured_present = self._contains_structured_key_locked(key)
                if structured_present is None and not self._settings.contains(key):
                    continue
                if structured_present is False:
                    continue
                value = self.get(key, self._MISSING)
                if value is self._MISSING:
                    continue
                preserved[key] = deepcopy(value)
            
            # Replace the store from the same canonical runtime-shape projection
            # used by fresh-profile seeding. There is no Reset-only section list
            # or flattening algorithm.
            from core.settings.defaults import get_flat_defaults
            self._settings.replace_all(get_flat_defaults(self._application))
            
            # Restore preserved values using the same structured-key contract.
            for key, value in preserved.items():
                handled, _old = self._set_structured_value_locked(key, deepcopy(value))
                if not handled:
                    self._settings.setValue(key, deepcopy(value))

            # Keep normalized visualizer defaults after any weather/widget restore.
            widgets = self._settings.value('widgets', {})
            if isinstance(widgets, Mapping):
                widgets_dict = dict(widgets)
                vis_defaults = widgets_dict.get('spotify_visualizer')
                if isinstance(vis_defaults, Mapping):
                    widgets_dict['spotify_visualizer'] = normalize_visualizer_section_mapping(
                        vis_defaults,
                        apply_preset_overlay=False,
                    )
                    self._store_widgets_root_locked(widgets_dict)
            self._mark_visualizer_schema_current_locked()
            self._settings.sync()
            self._clear_cache_locked()

        logger.info("Settings reset to defaults (preserved: %s)", list(preserved.keys()))
        self._publish_store_change('*', None, self._MISSING)
    
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
        key = self._canonicalize_key(key)
        with self._lock:
            structured = self._contains_structured_key_locked(key)
            if structured is not None:
                return structured
            return self._settings.contains(key)
    
    def remove(self, key: str) -> None:
        """Remove a setting key."""
        key = self._canonicalize_key(key)
        with self._lock:
            removed = self._remove_structured_key_locked(key)
            if not removed:
                self._settings.remove(key)
            self._invalidate_cache_for_key_locked(str(key))
            self._settings.sync()

        self._publish_store_change(key, None, self._MISSING)

        logger.debug(f"Removed setting: {key}")
    
    def clear(self) -> None:
        """Clear all settings (use with caution)."""
        with self._lock:
            self._settings.clear()
            self._clear_cache_locked()
            self._settings.sync()
        self._publish_store_change('*', None, self._MISSING)
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

        if root == "widgets":
            mapping = self._store_widgets_root_locked(mapping)
        elif root == "transitions":
            mapping = self._store_transitions_root_locked(mapping)
        else:
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

    def set_section(self, section: str, value: Mapping[str, Any], *, emit_change: bool = True) -> None:
        """Set a whole section value in one shot.

        This is primarily intended for mapping-backed sections like
        'widgets' and 'transitions' and keeps change notifications and
        logging behaviour consistent with set().
        """

        mapping = dict(value) if isinstance(value, Mapping) else value
        with self._lock:
            old_value = self._settings.value(section)
            if section == "widgets":
                mapping = self._store_widgets_root_locked(mapping)
            elif section == "transitions":
                mapping = self._store_transitions_root_locked(mapping)
            else:
                self._settings.setValue(section, mapping)
            self._invalidate_cache_for_key_locked(section)

            self._settings.sync()

        if emit_change:
            self._publish_store_change(section, mapping, old_value)
        if is_verbose_logging():
            logger.debug("Section changed%s: %s: %r -> %r", "" if emit_change else " (silent)", section, old_value, mapping)
        else:
            logger.debug("Section changed%s: %s", "" if emit_change else " (silent)", section)

    def get_widgets_map(self) -> Dict[str, Any]:
        """Return the full widgets map as a plain dict.

        Callers should prefer this over reading the raw 'widgets' key so
        any future migration or normalisation can be centralised here.
        """

        value = self.get_section('widgets', {})
        return dict(value) if isinstance(value, Mapping) else {}

    def set_widgets_map(self, widgets: Mapping[str, Any], *, emit_change: bool = True) -> None:
        """Replace the widgets map with the given mapping.

        This is a thin wrapper around set_section('widgets', ...) to keep
        callers from hard-coding the 'widgets' key. Use emit_change=False only
        for owner-local repair/rebuild paths that also refresh their runtime
        state explicitly; silent writes still sync and invalidate dotted caches.
        """

        self.set_section('widgets', widgets, emit_change=emit_change)

    def export_to_sst(self, path: str) -> bool:
        """Delegates to core.settings.sst_io."""
        from core.settings.sst_io import export_to_sst
        return export_to_sst(self, path)

    def import_from_sst(self, path: str, merge: bool = True) -> bool:
        """Delegates to core.settings.sst_io."""
        from core.settings.sst_io import import_from_sst
        return import_from_sst(self, path, merge)

    def preview_import_from_sst(self, path: str, merge: bool = True) -> Dict[str, Any]:
        """Delegates to core.settings.sst_io."""
        from core.settings.sst_io import preview_import_from_sst
        return preview_import_from_sst(self, path, merge)

    def _normalize_sst_snapshot(self, snapshot: Mapping[str, Any]) -> Dict[str, Any]:
        """Delegates to core.settings.sst_io."""
        from core.settings.sst_io import normalize_sst_snapshot
        return normalize_sst_snapshot(snapshot)
