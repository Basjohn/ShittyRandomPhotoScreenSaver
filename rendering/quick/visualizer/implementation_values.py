"""Small value helpers shared by Qt Quick visualizer implementations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def rgba(
    value: object,
    *,
    default: Sequence[object],
) -> tuple[float, float, float, float]:
    channels: Sequence[object]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        channels = value
    else:
        channels = default
    if len(channels) < 3:
        channels = default
    alpha = channels[3] if len(channels) > 3 else 255
    resolved = tuple(
        max(0.0, min(1.0, float(channel) / 255.0))
        for channel in (*channels[:3], alpha)
    )
    return resolved  # type: ignore[return-value]


def parameter(
    parameters: Mapping[str, object],
    name: str,
    default: object,
) -> object:
    try:
        return parameters[name]
    except KeyError:
        return default


def safe_hue(value: float) -> float:
    raw = float(value) % 1.0
    return (raw + 0.002) % 1.0 if raw < 0.001 else raw


__all__ = ["parameter", "rgba", "safe_hue"]
