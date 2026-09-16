"""Canonical storage path resolver for SRPSS.

Single source of truth for all application data directories.
All modules that need persistent storage should import from here
instead of computing paths with ``tempfile.gettempdir()`` or
hard-coded ``%APPDATA%`` lookups.

Directory layout under the application data root::

    %APPDATA%/SRPSS/            (or SRPSS_MC for Media Center profile)
    ├── settings_v2.json
    ├── cache/
    │   ├── rss/
    │   └── weather.json
    ├── state/
    │   └── feed_health.json
    └── logs/
    └── steam/
        ├── credentials.bin
        ├── credential_meta.json
        └── cache/
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Profile → folder mapping (shared with json_store.determine_storage_path)
# ---------------------------------------------------------------------------
_CANONICAL_FOLDERS = {"Screensaver": "SRPSS", "Screensaver_MC": "SRPSS_MC"}
_DEFAULT_PROFILE = "Screensaver"

# Module-level cache so repeated calls don't re-resolve
_resolved_base: Optional[Path] = None
_resolved_profile: Optional[str] = None


def detect_current_profile(default: str = "Screensaver") -> str:
    """Return the current SRPSS profile name.

    Returns:
        "Screensaver" for the normal build.
        "Screensaver_MC" for Media Center / MC builds.

    This must be side-effect free. Do not instantiate SettingsManager here.
    """
    import sys

    try:
        argv0 = str(getattr(sys, "argv", [""])[0] or "").lower()
        main_mod = sys.modules.get("__main__")
        main_file = str(getattr(main_mod, "__file__", "") or "").lower() if main_mod is not None else ""

        probe = f"{argv0} {main_file}"

        if (
            "srpss mc" in probe
            or "srpss_mc" in probe
            or "srpss media center" in probe
            or "srpss_media_center" in probe
            or "main_mc.py" in probe
        ):
            return "Screensaver_MC"
    except Exception:
        pass

    return default


def _appdata_root() -> Path:
    """Return ``%APPDATA%`` or a platform-appropriate fallback."""
    from os import environ

    appdata = environ.get("APPDATA")
    if appdata:
        return Path(appdata)
    return (Path.home() / "AppData" / "Roaming").resolve()


def resolve_app_data_dir(profile: Optional[str] = None) -> Path:
    """Resolve the canonical application data path without touching disk."""

    global _resolved_base, _resolved_profile
    profile = profile or _DEFAULT_PROFILE
    if _resolved_base is not None and _resolved_profile == profile:
        return _resolved_base

    folder = _CANONICAL_FOLDERS.get(profile)
    if folder is None:
        folder = f"SRPSS_profiles/{profile}"
    return (_appdata_root() / folder).resolve()


def get_app_data_dir(profile: Optional[str] = None) -> Path:
    """Return and create the canonical application data directory."""

    global _resolved_base, _resolved_profile
    profile = profile or _DEFAULT_PROFILE
    result = resolve_app_data_dir(profile)
    result.mkdir(parents=True, exist_ok=True)
    _resolved_base = result
    _resolved_profile = profile
    return result


def get_cache_dir(profile: Optional[str] = None) -> Path:
    """Return ``<app_data>/cache/`` — parent for all cache subdirectories."""
    d = get_app_data_dir(profile) / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_rss_cache_dir(profile: Optional[str] = None) -> Path:
    """Return ``<app_data>/cache/rss/`` for RSS image caching."""
    d = get_cache_dir(profile) / "rss"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_weather_cache_file(profile: Optional[str] = None) -> Path:
    """Return ``<app_data>/cache/weather.json``."""
    return get_cache_dir(profile) / "weather.json"


def get_weather_widget_cache_file(profile: Optional[str] = None) -> Path:
    """Return ``<app_data>/cache/weather_widget_last.json``."""
    return get_cache_dir(profile) / "weather_widget_last.json"


def get_state_dir(profile: Optional[str] = None) -> Path:
    """Return ``<app_data>/state/`` for persistent runtime state files."""
    d = get_app_data_dir(profile) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_feed_health_file(profile: Optional[str] = None) -> Path:
    """Return ``<app_data>/state/feed_health.json``."""
    return get_state_dir(profile) / "feed_health.json"


def get_steam_dir(profile: Optional[str] = None) -> Path:
    """Return ``<app_data>/steam/`` for Steam credential/cache state."""
    d = get_app_data_dir(profile) / "steam"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_steam_credentials_file(profile: Optional[str] = None) -> Path:
    """Return the encrypted Steam credential payload path."""
    return get_steam_dir(profile) / "credentials.bin"


def get_steam_credential_meta_file(profile: Optional[str] = None) -> Path:
    """Return the non-secret Steam credential metadata path."""
    return get_steam_dir(profile) / "credential_meta.json"


def get_steam_cache_dir(profile: Optional[str] = None, profile_key: str | None = None) -> Path:
    """Return the Steam cache root or a hashed account-specific cache folder."""
    d = get_steam_dir(profile) / "cache"
    if profile_key:
        d = d / profile_key
    d.mkdir(parents=True, exist_ok=True)
    return d



def reset_module_cache() -> None:
    """Clear the module-level resolved path cache (for testing)."""
    global _resolved_base, _resolved_profile
    _resolved_base = None
    _resolved_profile = None
