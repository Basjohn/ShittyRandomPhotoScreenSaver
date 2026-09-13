"""Account-private persistence for Friend Pulse pinned friends.

Only opaque friend fingerprints are stored.  The file is deliberately outside
Settings/defaults because pins are user/account state, not application defaults.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Collection

from core.settings.storage_paths import get_steam_cache_dir


PIN_SCHEMA_VERSION = 1
PIN_FILE_NAME = "friend_pulse_pins.json"


def pin_path_for_profile_key(profile_key: str, *, root: Path | None = None) -> Path:
    profile_key = str(profile_key or "").strip()
    if not profile_key.startswith("profile_"):
        raise ValueError("Friend Pulse pin profile key must be opaque/profile-derived")
    base = root or get_steam_cache_dir(profile_key=profile_key)
    return Path(base) / PIN_FILE_NAME


def load_friend_pulse_pins(
    profile_key: str,
    *,
    root: Path | None = None,
) -> frozenset[str]:
    path = pin_path_for_profile_key(profile_key, root=root)
    if not path.is_file():
        return frozenset()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("schema_version") != PIN_SCHEMA_VERSION:
            return frozenset()
        values = raw.get("pinned_fingerprints", ())
        if not isinstance(values, list):
            return frozenset()
        resolved = [
            str(value).strip()
            for value in values
            if isinstance(value, str) and str(value).strip()
        ]
        return frozenset(resolved)
    except Exception:
        return frozenset()


def save_friend_pulse_pins(
    profile_key: str,
    pins: Collection[str],
    *,
    root: Path | None = None,
) -> Path:
    path = pin_path_for_profile_key(profile_key, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = sorted(
        {
            str(value).strip()
            for value in pins
            if isinstance(value, str) and str(value).strip()
        }
    )
    payload = {
        "schema_version": PIN_SCHEMA_VERSION,
        "pinned_fingerprints": normalized,
    }
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
    return path