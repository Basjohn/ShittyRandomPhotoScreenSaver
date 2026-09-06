"""Small value helpers shared by Qt Quick visualizer implementations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def rgba(value: object) -> tuple[float, float, float, float]:
    """Normalize one required resolved RGBA value.

    Renderer colours are part of the immutable resolved frame. Invalid or
    incomplete values are contract errors; this layer owns no replacement
    colour table.
    """

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"resolved RGBA value must be a channel sequence: {value!r}")
    if len(value) < 3:
        raise ValueError(f"resolved RGBA value needs at least three channels: {value!r}")
    alpha = value[3] if len(value) > 3 else 255
    resolved = tuple(
        max(0.0, min(1.0, float(channel) / 255.0))
        for channel in (*value[:3], alpha)
    )
    return resolved  # type: ignore[return-value]


def parameter(
    parameters: Mapping[str, object],
    name: str,
) -> object:
    """Return one required immutable-frame parameter.

    Renderer input is a resolved contract. Missing authored parameters are an
    ownership/configuration error and must never become renderer-local product
    defaults.
    """

    try:
        return parameters[name]
    except KeyError as exc:
        raise KeyError(f"immutable visualizer frame missing parameter: {name}") from exc


def safe_hue(value: float) -> float:
    raw = float(value) % 1.0
    return (raw + 0.002) % 1.0 if raw < 0.001 else raw


__all__ = ["parameter", "rgba", "safe_hue"]
