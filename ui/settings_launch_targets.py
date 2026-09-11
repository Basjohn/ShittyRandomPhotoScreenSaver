"""Semantic runtime -> Settings launch targets.

Runtime widgets emit stable semantic target ids only.  This module resolves them
into Settings navigation intent without importing QWidget/PySide, so runtime
presentation code never knows tab indices or lazy-section implementation detail.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class SettingsLaunchTarget:
    """One stable Settings navigation target."""

    target_id: str
    tab_key: str
    view_state: Mapping[str, object]
    focus_attr: str = ""


_TARGETS = {
    "weather_location": SettingsLaunchTarget(
        target_id="weather_location",
        tab_key="widgets",
        view_state=MappingProxyType({"subtab_id": "weather"}),
        focus_attr="weather_location",
    ),
}


def resolve_settings_launch_target(target_id: object) -> SettingsLaunchTarget | None:
    """Resolve a stable semantic target id, or ``None`` when unknown/empty."""

    key = str(target_id or "").strip().lower()
    return _TARGETS.get(key)


__all__ = ["SettingsLaunchTarget", "resolve_settings_launch_target"]
