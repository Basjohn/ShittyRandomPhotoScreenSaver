"""Canonical eight-direction shadow orientation authority (Phase E4).

One presentation-neutral token owns shadow *orientation only*. Every shadow
class (card, text, header, control, icon, volume slider, ...) keeps its own
authored magnitude/blur/spread/opacity/color; direction applies signs to the
authored magnitude and zeroes the perpendicular axis for the four axis-only
directions.

```text
NW  N  NE
 W     E
SW  S  SE
```

For an authored magnitude ``(mx, my)``:

```text
NW -> (-mx, -my)   N -> ( 0, -my)   NE -> (+mx, -my)
 W -> (-mx,   0)                      E -> (+mx,   0)
SW -> (-mx, +my)   S -> ( 0, +my)   SE -> (+mx, +my)
```

Direction is resolved to signed offsets in Python **before** any QML consumes
them. QML never parses the token, queries settings, or maps the direction
itself. This is orientation-only: it is not a second magnitude authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum


class ShadowDirection(Enum):
    """One of eight canonical outer shadow directions. Center is not a mode."""

    NW = "NW"
    N = "N"
    NE = "NE"
    W = "W"
    E = "E"
    SW = "SW"
    S = "S"
    SE = "SE"


DEFAULT_SHADOW_DIRECTION = ShadowDirection.SE

SHADOW_DIRECTION_SETTING_KEY = "widgets.shadows.direction"

# Orientation signs applied to an authored (magnitude) pair. Axis-only
# directions carry a zero on the perpendicular axis.
_SIGN_TABLE: dict[ShadowDirection, tuple[int, int]] = {
    ShadowDirection.NW: (-1, -1),
    ShadowDirection.N: (0, -1),
    ShadowDirection.NE: (1, -1),
    ShadowDirection.W: (-1, 0),
    ShadowDirection.E: (1, 0),
    ShadowDirection.SW: (-1, 1),
    ShadowDirection.S: (0, 1),
    ShadowDirection.SE: (1, 1),
}


def resolve_shadow_direction(token: object) -> ShadowDirection:
    """Resolve any persisted/user token to a direction; default ``SE``.

    Deterministic policy: a :class:`ShadowDirection` passes through unchanged; a
    string matching a canonical token (case-insensitive, surrounding whitespace
    ignored) resolves to it; anything else — unknown text, wrong type, ``None``,
    empty — resolves to the canonical default ``SE``.
    """

    if isinstance(token, ShadowDirection):
        return token
    if isinstance(token, str):
        key = token.strip().upper()
        for direction in ShadowDirection:
            if direction.value == key:
                return direction
    return DEFAULT_SHADOW_DIRECTION


def shadow_direction_signs(direction: object) -> tuple[int, int]:
    """Return the ``(sign_x, sign_y)`` orientation for a direction/token."""

    return _SIGN_TABLE[resolve_shadow_direction(direction)]


def resolve_signed_offset(
    direction: object,
    magnitude_x: float,
    magnitude_y: float,
) -> tuple[float, float]:
    """Apply direction signs to an authored magnitude pair.

    The incoming magnitude is treated as a magnitude regardless of its own sign;
    direction owns orientation only. Axis-only directions zero the perpendicular
    axis so, e.g., ``N`` produces ``(0, -my)``.
    """

    sign_x, sign_y = shadow_direction_signs(direction)
    return (
        float(sign_x) * abs(float(magnitude_x)),
        float(sign_y) * abs(float(magnitude_y)),
    )


def resolve_shadow_offsets(
    direction: object,
    magnitudes: Mapping[str, tuple[float, float]],
) -> dict[str, tuple[float, float]]:
    """Resolve class-specific authored magnitudes to signed offsets.

    ``magnitudes`` maps a shadow-class name (``"card"``, ``"text"``,
    ``"header"``, ...) to its authored ``(mx, my)`` magnitude. The same resolved
    direction is applied to every class; per-class magnitude distinctions are
    preserved.
    """

    resolved = resolve_shadow_direction(direction)
    return {
        name: resolve_signed_offset(resolved, magnitude[0], magnitude[1])
        for name, magnitude in magnitudes.items()
    }


def get_shadow_direction(settings: object) -> ShadowDirection:
    """Read the canonical direction from a ``SettingsManager``-like object.

    Falls back to the canonical default when the object cannot be queried or the
    stored token is malformed. Presentation code should call this (or
    :func:`resolve_shadow_direction` on an already-loaded value) rather than
    parsing the token itself.
    """

    getter = getattr(settings, "get", None)
    if not callable(getter):
        return DEFAULT_SHADOW_DIRECTION
    return resolve_shadow_direction(
        getter(SHADOW_DIRECTION_SETTING_KEY, DEFAULT_SHADOW_DIRECTION.value)
    )
