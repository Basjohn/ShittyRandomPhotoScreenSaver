"""Shared caches for SettingsDialog heavy data loads."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtGui import QFontDatabase

from core.settings.defaults import get_default_settings
from core.settings.storage_paths import get_cache_dir


@dataclass
class SettingsDialogCacheData:
    """Snapshot of cached data for the settings dialog."""

    defaults_generation: float
    defaults: Dict[str, Any]
    widget_defaults: Dict[str, Any]
    font_families: List[str]
    last_refresh_ts: float


_cache: SettingsDialogCacheData | None = None
_CACHE_FILENAME = "settings_dialog_cache.json"


def _cache_file() -> Path:
    return get_cache_dir() / _CACHE_FILENAME


def _compute_defaults_generation() -> float:
    """Use defaults module mtimes as a cheap invalidation hook."""
    defaults_paths = [
        Path(__file__).resolve().parents[1]
        / "core"
        / "settings"
        / "defaults.py",
        Path(__file__).resolve().parents[1]
        / "core"
        / "settings"
        / "default_settings.py",
    ]
    mtimes = []
    for defaults_path in defaults_paths:
        try:
            mtimes.append(defaults_path.stat().st_mtime)
        except FileNotFoundError:
            mtimes.append(time.time())
    return max(mtimes)


def _load_persisted_cache() -> SettingsDialogCacheData | None:
    path = _cache_file()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return SettingsDialogCacheData(
            defaults_generation=float(data["defaults_generation"]),
            defaults=data["defaults"],
            widget_defaults=data.get("widget_defaults", {}),
            font_families=data.get("font_families", []),
            last_refresh_ts=float(data.get("last_refresh_ts", 0.0)),
        )
    except Exception:
        return None


def _persist_cache(cache: SettingsDialogCacheData) -> None:
    try:
        payload = asdict(cache)
        path = _cache_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    except Exception:
        pass


def get_settings_dialog_cache() -> SettingsDialogCacheData:
    """Return (and refresh) the dialog cache."""
    global _cache
    generation = _compute_defaults_generation()
    if _cache and _cache.defaults_generation == generation:
        return _cache

    persisted = _load_persisted_cache()
    if persisted and persisted.defaults_generation == generation:
        _cache = persisted
        return _cache

    defaults = get_default_settings()
    widget_defaults = defaults.get("widgets", {}) if isinstance(defaults, dict) else {}

    font_db = QFontDatabase()
    font_families = list(font_db.families())

    _cache = SettingsDialogCacheData(
        defaults_generation=generation,
        defaults=defaults,
        widget_defaults=widget_defaults,
        font_families=font_families,
        last_refresh_ts=time.time(),
    )
    _persist_cache(_cache)
    return _cache
