"""Semantic runtime -> Settings launch targets.

Runtime widgets emit stable semantic target ids only.  This module resolves them
into Settings navigation intent without importing QWidget/PySide, so runtime
presentation code never knows tab indices or lazy-section implementation detail.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import base64
import json
import math
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class SettingsLaunchTarget:
    """One stable Settings navigation target."""

    target_id: str
    tab_key: str
    view_state: Mapping[str, object]
    focus_attr: str = ""
    studio_mode: str = ""
    studio_pose: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))


_TARGETS = {
    "weather_location": SettingsLaunchTarget(
        target_id="weather_location",
        tab_key="widgets",
        view_state=MappingProxyType({"subtab_id": "weather"}),
        focus_attr="weather_location",
    ),
    "gmail_authorization": SettingsLaunchTarget(
        target_id="gmail_authorization",
        tab_key="widgets",
        view_state=MappingProxyType({"subtab_id": "gmail"}),
        focus_attr="gmail_authorize_btn",
    ),
}


def _studio_pose(mode: str, values: Mapping[str, object]) -> dict[str, object]:
    """Restrict runtime handoff to finite, current-mode camera values. No persistence."""
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
    from core.settings.framed_camera import spec_for_mode

    descriptor = get_visualizer_mode_descriptor(mode)
    valid = set(descriptor.view_orbit_settings) | set(descriptor.scene_transform_settings)
    spec = spec_for_mode(mode)
    if spec is not None:
        valid.update(spec.input_keys)
    pose = {}
    for key, value in values.items():
        if key not in valid:
            continue
        if spec is not None and key == spec.key("camera_position"):
            if not isinstance(value, (list, tuple)) or len(value) != 3:
                continue
            try:
                xyz = [float(component) for component in value]
            except (TypeError, ValueError):
                continue
            if all(math.isfinite(component) for component in xyz):
                pose[key] = xyz
        else:
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(number):
                pose[key] = number
    return pose


def make_studio_launch_target(mode: str, values: Mapping[str, object]) -> str:
    """Primitive-only, generation-local Settings handoff; no widget or worker imports."""
    from ui.studio.registry import has_studio
    if not has_studio(mode):
        raise ValueError(f"No Studio for {mode!r}")
    encoded = json.dumps(_studio_pose(mode, values), separators=(",", ":"), allow_nan=False).encode("utf8")
    return f"studio:{mode}:{base64.urlsafe_b64encode(encoded).decode('ascii').rstrip('=')}"


def resolve_settings_launch_target(target_id: object) -> SettingsLaunchTarget | None:
    """Resolve a stable semantic target id, or ``None`` when unknown/empty."""

    key = str(target_id or "").strip()
    if key.startswith("studio:") and len(key) < 4096:
        parts = key.split(":", 2)
        if len(parts) != 3 or not parts[1]:
            return None
        mode, encoded = parts[1], parts[2]
        from ui.studio.registry import has_studio
        if not has_studio(mode):
            return None
        try:
            raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            pose = json.loads(raw)
            if not isinstance(pose, dict):
                return None
            clean = _studio_pose(mode, pose)
        except (ValueError, TypeError, UnicodeError, KeyError, OverflowError):
            return None
        return SettingsLaunchTarget(
            target_id=f"studio:{mode}", tab_key="visualizers",
            view_state=MappingProxyType({"page": "mode", "mode_id": mode}),
            studio_mode=mode, studio_pose=MappingProxyType(clean),
        )
    return _TARGETS.get(key.lower())


__all__ = ["SettingsLaunchTarget", "make_studio_launch_target", "resolve_settings_launch_target"]
