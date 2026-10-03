"""The 3D Detail tier that applies to one 3D transition or Visualizer: the one resolver.

Settings (the ``scene3d`` section, edited on the 3D Settings tab) hold one value per level and
nothing derived:

- ``detail``: the General tier for everything 3D. ``Auto`` picks by the GPU in use
  (``scene3d_auto_tier``).
- ``transitions_detail`` / ``visualizers_detail``: a family's tier, or ``General`` to follow it.
- ``<mode>_detail`` for each 3D Visualizer mode: that mode's tier, or ``Auto`` to follow its
  family. (A 3D transition's own quality choices, Anti-aliasing / Bloom / Motion Blur on its
  page, keep their "Auto follows the tier" contract in ``resolve_scene_quality``.)

``resolve_scene3d_tier`` is the only place the levels combine. A malformed stored value means
what its canonical default means (follow the level above). Import-safe: no Qt, no GL.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from core.settings.default_contract import require_canonical_default
from rendering.gl_programs.scene3d import SCENE3D_DETAIL_NAMES

SCENE3D_SECTION = "scene3d"
SCENE3D_GENERAL_CHOICES: tuple[str, ...] = ("Auto", *SCENE3D_DETAIL_NAMES)
SCENE3D_FAMILY_CHOICES: tuple[str, ...] = ("General", *SCENE3D_DETAIL_NAMES)
SCENE3D_ENTRY_CHOICES: tuple[str, ...] = ("Auto", *SCENE3D_DETAIL_NAMES)
SCENE3D_FAMILIES: dict[str, str] = {"transitions": "transitions_detail", "visualizers": "visualizers_detail"}

# Auto by GPU class: a discrete (or unidentified) GPU gets High, an integrated one Balanced, a
# software renderer Performance.
_AUTO_TIERS = {"discrete": "High", "integrated": "Balanced", "software": "Performance"}
_SOFTWARE_RENDERERS = ("llvmpipe", "softpipe", "swiftshader", "microsoft basic render", "gdi generic")


def classify_gpu(vendor: str, renderer: str) -> str:
    """``discrete``, ``integrated`` or ``software`` from the GL vendor and renderer strings."""
    vendor_text, renderer_text = str(vendor or "").lower(), str(renderer or "").lower()
    if any(name in renderer_text for name in _SOFTWARE_RENDERERS):
        return "software"
    if "intel" in vendor_text or "intel" in renderer_text:
        # Arc A/B-series cards are discrete; every other Intel GPU (Arc-branded ones included) shares memory.
        return "discrete" if re.search(r"arc\(tm\) [ab]\d", renderer_text) else "integrated"
    if ("amd" in vendor_text or "ati" in vendor_text or "radeon" in renderer_text) and (
            "radeon(tm) graphics" in renderer_text or "radeon graphics" in renderer_text
            or "vega 3" in renderer_text or "vega 8" in renderer_text or "vega 11" in renderer_text):
        return "integrated"
    return "discrete"


def scene3d_auto_tier(gpu: tuple[str, str] | None) -> str:
    """The tier ``Auto`` means on this GPU ((vendor, renderer), None while none is known)."""
    return "High" if gpu is None else _AUTO_TIERS[classify_gpu(*gpu)]


def _value(section: Mapping[str, Any] | None, key: str) -> Any:
    if isinstance(section, Mapping) and key in section:
        return section[key]
    return require_canonical_default(f"{SCENE3D_SECTION}.{key}")


def scene3d_entry_key(entry: str) -> str:
    """An entry's (a 3D Visualizer mode's) own setting under ``scene3d``."""
    return f"{entry}_detail"


def read_scene3d_section(get) -> dict[str, Any]:
    """The stored ``scene3d`` section through ``get(dotted_key, default)`` (a SettingsManager's)."""
    from core.settings.defaults import get_default_setting

    canonical = get_default_setting(SCENE3D_SECTION, missing=None)
    if not isinstance(canonical, Mapping):
        raise KeyError("canonical defaults missing the scene3d section")
    return {key: get(f"{SCENE3D_SECTION}.{key}", value) for key, value in canonical.items()}


def resolve_scene3d_tier(section: Mapping[str, Any] | None, family: str, entry: str | None = None, *,
                         gpu: tuple[str, str] | None = None) -> str:
    """The tier for ``family`` ("transitions" / "visualizers"), or one of its entries: the entry's
    own tier, else the family's, else the General one (``Auto``: by ``gpu``)."""
    if family not in SCENE3D_FAMILIES:
        raise ValueError(f"unknown 3D family: {family!r}")
    if entry is not None:
        value = _value(section, scene3d_entry_key(entry))
        if value in SCENE3D_DETAIL_NAMES:
            return str(value)
    value = _value(section, SCENE3D_FAMILIES[family])
    if value in SCENE3D_DETAIL_NAMES:
        return str(value)
    value = _value(section, "detail")
    if value in SCENE3D_DETAIL_NAMES:
        return str(value)
    return scene3d_auto_tier(gpu)


def resolve_visualizer_tier(section: Mapping[str, Any] | None, mode: str, *,
                            gpu: tuple[str, str] | None = None) -> str:
    """The tier a Visualizer mode draws with: its own entry when the canonical section has one
    (the 3D modes), else the 3D Visualizers family's."""
    from core.settings.defaults import get_default_setting

    canonical = get_default_setting(SCENE3D_SECTION, missing=None) or {}
    entry = mode if scene3d_entry_key(mode) in canonical else None
    return resolve_scene3d_tier(section, "visualizers", entry, gpu=gpu)


__all__ = [
    "SCENE3D_ENTRY_CHOICES",
    "SCENE3D_FAMILIES",
    "SCENE3D_FAMILY_CHOICES",
    "SCENE3D_GENERAL_CHOICES",
    "SCENE3D_SECTION",
    "classify_gpu",
    "read_scene3d_section",
    "resolve_scene3d_tier",
    "resolve_visualizer_tier",
    "scene3d_auto_tier",
    "scene3d_entry_key",
]
