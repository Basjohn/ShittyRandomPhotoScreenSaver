"""JSON-backed settings storage for SRPSS.

Provides a thin API compatible with the subset of QSettings used by
core.settings.settings_manager.SettingsManager. Internally maintains a flat
mapping of keys → values (where keys match the dotted notation previously
stored in QSettings) while persisting a canonical nested snapshot to disk.
"""
from __future__ import annotations

import json
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Mapping, Optional, Tuple

from core.logging.logger import get_logger

logger = get_logger(__name__)


SNAPSHOT_VERSION = 2
_STRUCTURED_KEYS = {"widgets", "transitions", "ui"}


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
        self._lock = threading.RLock()
        self._dirty = False
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
        with self._lock:
            self._last_load_failure = False
            self._last_load_error = None
            if not self._path.exists():
                self._data.clear()
                self._dirty = False
                return

            try:
                payload = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                logger.exception("Failed to read settings JSON at %s", self._path)
                self._data.clear()
                self._dirty = False
                self._last_load_failure = True
                self._last_load_error = "json_decode"
                return

            snapshot = payload.get("snapshot") if isinstance(payload, dict) else None
            if not isinstance(snapshot, Mapping):
                self._data.clear()
                self._dirty = False
                self._last_load_failure = True
                self._last_load_error = "invalid_snapshot"
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
            self._dirty = False

    def sync(self) -> None:
        with self._lock:
            if not self._dirty:
                return
            self._save_locked()

    def _save_locked(self) -> None:
        snapshot: Dict[str, Any] = {}
        for key, value in self._data.items():
            if key in _STRUCTURED_KEYS and isinstance(value, Mapping):
                snapshot[key] = value
                continue
            if "." in key:
                section, subkey = key.split(".", 1)
                container = snapshot.setdefault(section, {})
                if isinstance(container, Mapping):
                    container[subkey] = value
                else:
                    snapshot[section] = {subkey: value}
            else:
                snapshot[key] = value

        payload = {
            "version": SNAPSHOT_VERSION,
            "profile": self._profile,
            "snapshot": snapshot,
            "metadata": self._meta,
        }

        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self._path)
        self._dirty = False

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
            self._dirty = True

    def contains(self, key: str) -> bool:
        with self._lock:
            return key in self._data

    def remove(self, key: str) -> None:
        with self._lock:
            if key in self._data:
                del self._data[key]
                self._dirty = True

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._dirty = True

    def allKeys(self) -> Iterable[str]:
        with self._lock:
            return list(self._data.keys())

    def setArray(self, key: str, value: Any) -> None:
        self.setValue(key, value)

    # Utility used by SettingsManager.reset_to_defaults to repopulate store
    def replace_all(self, items: Mapping[str, Any]) -> None:
        with self._lock:
            self._data = {k: deepcopy(v) for k, v in items.items()}
            self._dirty = True

    # Metadata helpers -------------------------------------------------
    def update_metadata(self, **entries: Any) -> None:
        with self._lock:
            self._meta.update(entries)
            self._dirty = True

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
