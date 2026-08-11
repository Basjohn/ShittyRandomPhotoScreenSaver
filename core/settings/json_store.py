"""JSON-backed settings storage for SRPSS.

Provides a thin API compatible with the subset of QSettings used by
core.settings.settings_manager.SettingsManager. Internally maintains a flat
mapping of keys → values (where keys match the dotted notation previously
stored in QSettings) while persisting a canonical nested snapshot to disk.
"""
from __future__ import annotations

import itertools
import json
import os
import threading
import weakref
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Mapping, Optional, Tuple

from core.logging.logger import get_logger
from core.settings.persistence import (
    PersistenceTicket,
    flush_settings_path,
    get_settings_persistence,
)

logger = get_logger(__name__)


SNAPSHOT_VERSION = 2
_STRUCTURED_KEYS = {"widgets", "transitions", "ui"}
_OWNER_KEY_COUNTER = itertools.count(1)
_OWNER_KEY_LOCK = threading.Lock()


class SettingsDurabilityError(RuntimeError):
    """Raised when a required persistence/load ordering boundary cannot pass."""


def _next_persistence_owner_key() -> int:
    with _OWNER_KEY_LOCK:
        return next(_OWNER_KEY_COUNTER)


class JsonSettingsStore:
    """File-backed replacement for the subset of QSettings we relied on."""

    def __init__(
        self,
        *,
        storage_path: Path,
        profile: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self._path = storage_path
        self._profile = profile
        self._meta: Dict[str, Any] = dict(metadata or {})
        self._data: Dict[str, Any] = {}
        self._manager_cache: Dict[str, Any] = {}
        self._manager_cache_lock = threading.RLock()
        self._lock = threading.RLock()
        self._dirty = False
        self._state_revision = 0
        self._durable_state_revision = 0
        self._last_requested_state_revision = -1
        self._last_ticket: PersistenceTicket | None = None
        self._last_persistence_error: Optional[str] = None
        self._persistence_owner_key = _next_persistence_owner_key()
        self._last_load_failure = False
        self._last_load_error: Optional[str] = None
        self.load()

    # ------------------------------------------------------------------
    # Basic file IO helpers
    # ------------------------------------------------------------------
    def exists(self) -> bool:
        with self._lock:
            return self._path.exists()

    def fileName(self) -> str:
        return str(self._path)

    def load(self) -> None:
        """Load snapshot from disk if the file exists."""
        # Flush, revision validation, and install form a retryable optimistic
        # barrier.  A mutation between observation and disk install changes the
        # revision (or leaves the store dirty), forcing another flush instead
        # of allowing old disk state to overwrite new in-memory authority.
        for _attempt in range(4):
            with self._lock:
                if self._dirty:
                    self.sync()
                observed_revision = self._state_revision

            if not flush_settings_path(self._path, timeout=5.0):
                raise SettingsDurabilityError(
                    f"settings path durability flush failed before load: {self._path}"
                )

            with self._lock:
                if self._dirty or self._state_revision != observed_revision:
                    continue
                self._load_from_disk_locked()
                return

        raise SettingsDurabilityError(
            f"settings changed continuously during load boundary: {self._path}"
        )

    def _load_from_disk_locked(self) -> None:
        self._last_load_failure = False
        self._last_load_error = None
        if not self._path.exists():
            self._data.clear()
            self._finish_load_locked()
            return

        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to read settings JSON at %s", self._path)
            self._data.clear()
            self._last_load_failure = True
            self._last_load_error = "json_decode"
            self._finish_load_locked()
            return

        snapshot = payload.get("snapshot") if isinstance(payload, dict) else None
        if not isinstance(snapshot, Mapping):
            self._data.clear()
            self._last_load_failure = True
            self._last_load_error = "invalid_snapshot"
            self._finish_load_locked()
            return

        flat: Dict[str, Any] = {}
        for key, value in snapshot.items():
            if key == "custom_preset_backup":
                # Legacy global preset payloads are intentionally retired.
                continue
            if key in _STRUCTURED_KEYS:
                flat[key] = value
                continue
            if isinstance(value, Mapping):
                for subkey, subval in _flatten_section(key, value):
                    flat[subkey] = subval
            else:
                flat[key] = value

        self._data = flat
        self._meta = {
            "version": payload.get("version", SNAPSHOT_VERSION),
            "profile": payload.get("profile", self._profile),
            **(
                payload.get("metadata")
                if isinstance(payload.get("metadata"), Mapping)
                else {}
            ),
        }
        self._finish_load_locked()

    def _finish_load_locked(self) -> None:
        # Re-loading is a new authoritative state, but owner revisions must
        # remain monotonic because the process writer fences out older state.
        self._state_revision += 1
        self._durable_state_revision = self._state_revision
        self._last_requested_state_revision = self._state_revision
        self._last_ticket = None
        self._last_persistence_error = None
        with self._manager_cache_lock:
            self._manager_cache.clear()
        self._dirty = False

    def manager_cache(self) -> Dict[str, Any]:
        """Return the cache shared by every manager for this store authority."""

        return self._manager_cache

    def manager_cache_lock(self) -> threading.RLock:
        """Return the lock protecting the shared manager read cache."""

        return self._manager_cache_lock

    def manager_operation_lock(self) -> threading.RLock:
        """Return the store-wide lock ordering manager reads and mutations."""

        return self._lock

    def sync(self, *, wait: bool = False, timeout: float = 5.0) -> bool:
        """Submit the current immutable revision to the ordered writer.

        Normal callers return after admission.  ``wait=True`` is the explicit
        durability boundary used by startup, Settings completion, reload, and
        process shutdown.
        """

        with self._lock:
            if not self._dirty:
                ticket = self._last_ticket
            elif (
                self._last_requested_state_revision == self._state_revision
                and self._last_ticket is not None
                and self._last_ticket.success is not False
            ):
                ticket = self._last_ticket
            else:
                # Snapshot and admission are one store-ordered transaction.
                # Holding only the store's ordinary data lock here cannot wait
                # on disk; controller.submit() performs bounded in-memory work.
                state_revision = self._state_revision
                controller = get_settings_persistence()
                ticket = controller.submit(
                    owner_key=self._persistence_owner_key,
                    path=self._path,
                    profile=self._profile,
                    snapshot_version=SNAPSHOT_VERSION,
                    state_revision=state_revision,
                    data=deepcopy(self._data),
                    metadata=deepcopy(self._meta),
                    callback=self._persistence_completed,
                )
                self._last_requested_state_revision = state_revision
                self._last_ticket = ticket

        if wait and ticket is not None:
            return get_settings_persistence().flush_ticket(ticket, timeout=timeout)
        return True

    def flush(self, *, timeout: float = 5.0) -> bool:
        """Wait until the current in-memory revision is durable."""

        return self.sync(wait=True, timeout=timeout)

    def persistence_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            ticket = self._last_ticket
            return {
                "state_revision": self._state_revision,
                "durable_state_revision": self._durable_state_revision,
                "last_requested_state_revision": self._last_requested_state_revision,
                "dirty": self._dirty,
                "last_ticket_revision": ticket.revision if ticket is not None else 0,
                "last_ticket_done": ticket.done if ticket is not None else True,
                "last_ticket_success": ticket.success if ticket is not None else True,
                "last_error": self._last_persistence_error,
            }

    def _persistence_completed(
        self,
        state_revision: int,
        _persistence_revision: int,
        success: bool,
        error: Optional[str],
    ) -> None:
        with self._lock:
            if success:
                self._durable_state_revision = max(
                    self._durable_state_revision,
                    int(state_revision),
                )
                if self._durable_state_revision >= self._state_revision:
                    self._dirty = False
                self._last_persistence_error = None
            else:
                self._dirty = True
                self._last_persistence_error = error

    def _mark_changed_locked(self) -> None:
        self._state_revision += 1
        self._dirty = True

    # ------------------------------------------------------------------
    # QSettings-like API surface
    # ------------------------------------------------------------------
    def value(self, key: str, default: Any = None) -> Any:
        with self._lock:
            if key in self._data:
                return deepcopy(self._data[key])
            return default

    def setValue(self, key: str, value: Any) -> None:
        with self._lock:
            current = self._data.get(key)
            if current == value:
                return
            self._data[key] = deepcopy(value)
            self._mark_changed_locked()

    def contains(self, key: str) -> bool:
        with self._lock:
            return key in self._data

    def remove(self, key: str) -> None:
        with self._lock:
            if key in self._data:
                del self._data[key]
                self._mark_changed_locked()

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._mark_changed_locked()

    def allKeys(self) -> Iterable[str]:
        with self._lock:
            return list(self._data.keys())

    def setArray(self, key: str, value: Any) -> None:
        self.setValue(key, value)

    # Utility used by SettingsManager.reset_to_defaults to repopulate store
    def replace_all(self, items: Mapping[str, Any]) -> None:
        with self._lock:
            self._data = {k: deepcopy(v) for k, v in items.items()}
            self._mark_changed_locked()

    # Metadata helpers -------------------------------------------------
    def update_metadata(self, **entries: Any) -> None:
        with self._lock:
            self._meta.update(entries)
            self._mark_changed_locked()

    def metadata(self) -> Mapping[str, Any]:
        with self._lock:
            return dict(self._meta)

    # Load failure helpers ----------------------------------------------
    def had_load_failure(self) -> bool:
        with self._lock:
            return self._last_load_failure

    def last_load_error(self) -> Optional[str]:
        with self._lock:
            return self._last_load_error

    def clear_load_failure_flag(self) -> None:
        with self._lock:
            self._last_load_failure = False
            self._last_load_error = None


def determine_storage_path(app_name: str, *, base_dir: Path | None = None) -> Path:
    """Compute the canonical storage path for the given application profile.

    Only the two canonical profiles ("Screensaver" and "Screensaver_MC") map to
    the well-known SRPSS / SRPSS_MC directories. Any other app_name (e.g. test
    UUIDs) is placed in an isolated subdirectory so it can never contaminate the
    production settings file.
    """
    if base_dir is None:
        base_dir = _default_appdata_dir()
    _CANONICAL = {"Screensaver": "SRPSS", "Screensaver_MC": "SRPSS_MC"}
    folder = _CANONICAL.get(app_name)
    if folder is None:
        # Non-production profile — isolate under SRPSS_profiles/<app_name>
        folder = f"SRPSS_profiles/{app_name}"
    return (base_dir / folder / "settings_v2.json").resolve()


_STORE_REGISTRY_LOCK = threading.RLock()
_STORE_REGISTRY: "weakref.WeakValueDictionary[str, JsonSettingsStore]" = (
    weakref.WeakValueDictionary()
)


def get_json_settings_store(
    *,
    storage_path: Path,
    profile: str,
    metadata: Mapping[str, Any] | None = None,
) -> JsonSettingsStore:
    """Return the one live in-process mutable store for a resolved path."""

    resolved = storage_path.resolve()
    registry_key = os.path.normcase(str(resolved))
    with _STORE_REGISTRY_LOCK:
        existing = _STORE_REGISTRY.get(registry_key)
        if existing is not None:
            return existing
        store = JsonSettingsStore(
            storage_path=resolved,
            profile=profile,
            metadata=metadata,
        )
        _STORE_REGISTRY[registry_key] = store
        return store


def _default_appdata_dir() -> Path:
    from os import environ

    appdata = environ.get("APPDATA")
    if appdata:
        return Path(appdata)
    # Fallback to %USERPROFILE%\AppData\Roaming
    home = Path.home()
    return (home / "AppData" / "Roaming").resolve()


def _flatten_section(prefix: str, mapping: Mapping[str, Any]) -> Iterator[Tuple[str, Any]]:
    for key, value in mapping.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping) and prefix not in _STRUCTURED_KEYS:
            yield from _flatten_section(dotted, value)
        else:
            yield dotted, value
