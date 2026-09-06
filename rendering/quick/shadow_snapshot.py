"""Strict generation-scoped Quick projection of canonical widget shadows.

Settings/default repair belongs at the Settings model boundary.  Quick widget
consumers receive one complete resolved snapshot for the display generation and
must not invent a second set of product shadow defaults if a field is missing.
Numeric limits here are presentation constraints, not product defaults.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math

from core.settings.shadow_direction import ShadowDirection


def _required_bool(values: Mapping[str, object], key: str) -> bool:
    value = values[key]
    if not isinstance(value, bool):
        raise TypeError(f"resolved Quick shadow {key!r} must be bool, got {type(value).__name__}")
    return value


def _required_float(
    values: Mapping[str, object],
    key: str,
    *,
    minimum: float,
    maximum: float,
) -> float:
    try:
        value = float(values[key])
    except (TypeError, ValueError) as exc:
        raise TypeError(f"resolved Quick shadow {key!r} must be numeric") from exc
    if not math.isfinite(value):
        raise ValueError(f"resolved Quick shadow {key!r} must be finite")
    return max(float(minimum), min(float(maximum), value))


def _required_rgba(values: Mapping[str, object]) -> tuple[int, int, int, int]:
    raw = values["color"]
    if not isinstance(raw, (tuple, list)) or len(raw) != 4:
        raise TypeError("resolved Quick shadow 'color' must be four RGBA channels")
    try:
        channels = tuple(max(0, min(255, int(channel))) for channel in raw)
    except (TypeError, ValueError) as exc:
        raise TypeError("resolved Quick shadow 'color' channels must be integers") from exc
    return channels  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class QuickShadowSnapshot:
    """Complete resolved shadow contract consumed by retained Quick widgets."""

    enabled: bool
    text_enabled: bool
    header_enabled: bool
    color: tuple[int, int, int, int]
    blur_radius: float
    text_opacity: float
    frame_opacity: float
    direction: ShadowDirection
    frame_extra_offset: float
    text_extra_offset: float

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "QuickShadowSnapshot":
        if not isinstance(values, Mapping):
            raise TypeError("resolved Quick shadow snapshot must be a mapping")
        try:
            direction = ShadowDirection(str(values["direction"]).strip().upper())
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("resolved Quick shadow direction must be a canonical token") from exc
        return cls(
            enabled=_required_bool(values, "enabled"),
            text_enabled=_required_bool(values, "text_enabled"),
            header_enabled=_required_bool(values, "header_enabled"),
            color=_required_rgba(values),
            blur_radius=_required_float(values, "blur_radius", minimum=0.0, maximum=128.0),
            text_opacity=_required_float(values, "text_opacity", minimum=0.0, maximum=1.0),
            frame_opacity=_required_float(values, "frame_opacity", minimum=0.0, maximum=1.0),
            direction=direction,
            frame_extra_offset=_required_float(values, "frame_extra_offset", minimum=0.0, maximum=40.0),
            text_extra_offset=_required_float(values, "text_extra_offset", minimum=0.0, maximum=40.0),
        )
