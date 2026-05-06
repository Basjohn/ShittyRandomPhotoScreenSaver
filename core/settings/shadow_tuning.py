"""Painted frame shadow tuning loader.

Loads visual shadow tuning values from ``shadowtuning.json`` located alongside
``settings_v2.json`` in the application data directory.  If the file is missing
or corrupt, hardcoded defaults are used and the file is regenerated.

Sections
--------
``card``
    Tuning for ``BaseOverlayWidget`` painted card shadows (media, visualizer,
    gmail, clock, weather, reddit).
``volume_slider``
    Tuning for ``SpotifyVolumeWidget`` painted shadow.
``text``
    Tuning for painter-drawn runtime text shadows.
``header``
    Tuning for painter-drawn runtime header-frame shadows.
``icon``
    Tuning for alpha-mask icon shadows.
``control``
    Tuning for rounded runtime control shadows.

The file is loaded once at import time.  Other modules import the resulting
dictionaries and treat them as read-only at runtime.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from core.logging.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Hardcoded defaults — used when the JSON file is missing or corrupt
# ---------------------------------------------------------------------------

_CARD_DEFAULTS: Dict[str, Any] = {
    "card_shrink_right": 11,
    "card_shrink_bottom": 11,
    "offset_x": 4,
    "offset_y": 6,
    "blur_steps": 50,
    "spread": 9,
    "max_alpha": 10,
    "radius_extra": 0,
}

_VOLUME_SLIDER_DEFAULTS: Dict[str, Any] = {
    "card_shrink_right": 6,
    "card_shrink_bottom": 6,
    "offset_x": 2,
    "offset_y": 3,
    "blur_steps": 30,
    "spread": 5,
    "max_alpha": 12,
    "radius_extra": 0,
}

_TEXT_DEFAULTS: Dict[str, Any] = {
    "offset_x": 1,
    "offset_y": 1,
    "alpha": 100,
    "min_font_size": 10,
    "small_font_min_scale": 0.3,
}

_TEXT_LARGE_DEFAULTS: Dict[str, Any] = {
    "offset_x": 2,
    "offset_y": 2,
    "alpha": 180,
    "min_font_size": 20,
    "small_font_min_scale": 0.3,
}

_HEADER_DEFAULTS: Dict[str, Any] = {
    "offset_x": 2,
    "offset_y": 2,
    "alpha": 80,
}

_ICON_DEFAULTS: Dict[str, Any] = {
    "offset_x": 3,
    "offset_y": 4,
    "alpha": 67,
    "scale": 1.0,
}

_CONTROL_DEFAULTS: Dict[str, Any] = {
    "offset_x": 3,
    "offset_y": 4,
    "alpha": 80,
    "spread": 8,
    "passes": 5,
}

_FULL_DEFAULTS: Dict[str, Any] = {
    "card": dict(_CARD_DEFAULTS),
    "volume_slider": dict(_VOLUME_SLIDER_DEFAULTS),
    "text": dict(_TEXT_DEFAULTS),
    "text_large": dict(_TEXT_LARGE_DEFAULTS),
    "header": dict(_HEADER_DEFAULTS),
    "icon": dict(_ICON_DEFAULTS),
    "control": dict(_CONTROL_DEFAULTS),
}


# ---------------------------------------------------------------------------
# File resolution
# ---------------------------------------------------------------------------

def _shadow_tuning_path() -> Path:
    """Return the path to ``shadowtuning.json`` next to ``settings_v2.json``."""
    from core.settings.storage_paths import get_app_data_dir

    return get_app_data_dir() / "shadowtuning.json"


def _write_defaults(path: Path) -> None:
    """Write the hardcoded defaults to *path* so the user has a template."""
    _write_payload(path, _FULL_DEFAULTS)


def _write_payload(path: Path, payload: Dict[str, Any]) -> None:
    """Write a complete tuning payload to *path*."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=4, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        logger.info("[SHADOW_TUNING] Wrote tuning to %s", path)
    except Exception:
        logger.debug("[SHADOW_TUNING] Failed to write tuning", exc_info=True)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _load_section(data: Dict[str, Any], key: str, defaults: Dict[str, Any]) -> Dict[str, Any]:
    """Return a section dict with missing keys filled from *defaults*."""
    section = data.get(key)
    if not isinstance(section, dict):
        return dict(defaults)
    merged = dict(defaults)
    for k, v in section.items():
        if k in merged:
            try:
                # Coerce to the type of the default value
                expected_type = type(merged[k])
                merged[k] = expected_type(v)
            except (TypeError, ValueError):
                logger.debug(
                    "[SHADOW_TUNING] Bad value for %s.%s=%r, keeping default %r",
                    key, k, v, merged[k],
                )
    return merged


def _canonicalized_tuning_payload(data: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
    """Return merged tuning payload and whether the on-disk file needs refresh."""

    canonical = {
        "card": _load_section(data, "card", _CARD_DEFAULTS),
        "volume_slider": _load_section(data, "volume_slider", _VOLUME_SLIDER_DEFAULTS),
        "text": _load_section(data, "text", _TEXT_DEFAULTS),
        "text_large": _load_section(data, "text_large", _TEXT_LARGE_DEFAULTS),
        "header": _load_section(data, "header", _HEADER_DEFAULTS),
        "icon": _load_section(data, "icon", _ICON_DEFAULTS),
        "control": _load_section(data, "control", _CONTROL_DEFAULTS),
    }
    needs_refresh = False
    for section_name, section_defaults in _FULL_DEFAULTS.items():
        existing = data.get(section_name)
        if not isinstance(existing, dict):
            needs_refresh = True
            continue
        for key in section_defaults:
            if key not in existing:
                needs_refresh = True
                break
    return canonical, needs_refresh


def load_shadow_tuning() -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Load shadow tuning and return all runtime tuning sections.

    Creates the file with defaults if it does not exist.
    """
    path = _shadow_tuning_path()

    if not path.is_file():
        _write_defaults(path)
        return dict(_CARD_DEFAULTS), dict(_VOLUME_SLIDER_DEFAULTS), dict(_TEXT_DEFAULTS), dict(_TEXT_LARGE_DEFAULTS), dict(_HEADER_DEFAULTS), dict(_ICON_DEFAULTS), dict(_CONTROL_DEFAULTS)

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("root is not a dict")
    except Exception:
        logger.warning(
            "[SHADOW_TUNING] Corrupt %s — regenerating from defaults",
            path,
            exc_info=True,
        )
        _write_defaults(path)
        return dict(_CARD_DEFAULTS), dict(_VOLUME_SLIDER_DEFAULTS), dict(_TEXT_DEFAULTS), dict(_TEXT_LARGE_DEFAULTS), dict(_HEADER_DEFAULTS), dict(_ICON_DEFAULTS), dict(_CONTROL_DEFAULTS)

    canonical, needs_refresh = _canonicalized_tuning_payload(data)
    if needs_refresh:
        _write_payload(path, canonical)

    logger.info("[SHADOW_TUNING] Loaded from %s", path)
    return (
        canonical["card"],
        canonical["volume_slider"],
        canonical["text"],
        canonical["text_large"],
        canonical["header"],
        canonical["icon"],
        canonical["control"],
    )


# ---------------------------------------------------------------------------
# Module-level singletons — imported by consumers
# ---------------------------------------------------------------------------

try:
    CARD_SHADOW_TUNING, VOLUME_SLIDER_SHADOW_TUNING, TEXT_SHADOW_TUNING, TEXT_LARGE_SHADOW_TUNING, HEADER_SHADOW_TUNING, ICON_SHADOW_TUNING, CONTROL_SHADOW_TUNING = load_shadow_tuning()
except Exception:
    logger.debug("[SHADOW_TUNING] Startup load failed, using hardcoded defaults", exc_info=True)
    CARD_SHADOW_TUNING = dict(_CARD_DEFAULTS)
    VOLUME_SLIDER_SHADOW_TUNING = dict(_VOLUME_SLIDER_DEFAULTS)
    TEXT_SHADOW_TUNING = dict(_TEXT_DEFAULTS)
    TEXT_LARGE_SHADOW_TUNING = dict(_TEXT_LARGE_DEFAULTS)
    HEADER_SHADOW_TUNING = dict(_HEADER_DEFAULTS)
    ICON_SHADOW_TUNING = dict(_ICON_DEFAULTS)
    CONTROL_SHADOW_TUNING = dict(_CONTROL_DEFAULTS)
