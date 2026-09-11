"""Authored retained-layout policy for Achievement Pulse."""

from __future__ import annotations

import math

from PySide6.QtCore import QSizeF

from core.settings.default_contract import require_canonical_default
from PySide6.QtGui import QFont, QFontMetricsF, QGuiApplication


ACHIEVEMENT_PULSE_AUTHORED_SIZE = QSizeF(600.0, 290.0)
ACHIEVEMENT_PULSE_SQUARE_AUTHORED_SIZE = QSizeF(600.0, 318.0)
ACHIEVEMENT_PULSE_PORTRAIT_AUTHORED_SIZE = QSizeF(600.0, 334.0)
_ACHIEVEMENT_DEFAULTS = require_canonical_default("widgets.achievement_pulse")
if not isinstance(_ACHIEVEMENT_DEFAULTS, dict):
    raise TypeError("Canonical Achievement Pulse defaults must be a mapping")

ACHIEVEMENT_SQUARE_ARTWORK_MIN = 140
ACHIEVEMENT_SQUARE_ARTWORK_DEFAULT = int(_ACHIEVEMENT_DEFAULTS["square_artwork_size"])
ACHIEVEMENT_SQUARE_ARTWORK_MAX = 190
ACHIEVEMENT_PORTRAIT_ASPECT_RATIO = 1.4
ACHIEVEMENT_CAPSULE_FILL_RGBA = tuple(_ACHIEVEMENT_DEFAULTS["capsule_fill_color"])
ACHIEVEMENT_CAPSULE_BORDER_RGBA = tuple(_ACHIEVEMENT_DEFAULTS["capsule_border_color"])
ACHIEVEMENT_CAPSULE_FONT_SIZE_MIN = 8
ACHIEVEMENT_CAPSULE_FONT_SIZE_DEFAULT = int(_ACHIEVEMENT_DEFAULTS["capsule_font_size"])
ACHIEVEMENT_CAPSULE_FONT_SIZE_MAX = 32
ACHIEVEMENT_CAPSULE_BASE_HEIGHT = 26.0
ACHIEVEMENT_CAPSULE_BASE_GAP = 6.0


def normalize_achievement_square_artwork_size(value: object) -> int:
    """Clamp artwork width to the retained title/artwork envelope."""

    try:
        resolved = int(value)
    except (TypeError, ValueError):
        resolved = ACHIEVEMENT_SQUARE_ARTWORK_DEFAULT
    return max(
        ACHIEVEMENT_SQUARE_ARTWORK_MIN,
        min(ACHIEVEMENT_SQUARE_ARTWORK_MAX, resolved),
    )


def normalize_achievement_artwork_shape(value: object) -> str:
    """Normalize the three authored retained artwork modes."""

    shape = str(value or "").strip().lower()
    return shape if shape in {"wide", "square", "portrait"} else "portrait"


def normalize_achievement_capsule_font_size(value: object) -> int:
    """Clamp the independently authored supporting-capsule font size."""

    try:
        resolved = int(value)
    except (TypeError, ValueError):
        resolved = ACHIEVEMENT_CAPSULE_FONT_SIZE_DEFAULT
    return max(
        ACHIEVEMENT_CAPSULE_FONT_SIZE_MIN,
        min(ACHIEVEMENT_CAPSULE_FONT_SIZE_MAX, resolved),
    )


def _font_height(font: QFont) -> float:
    if isinstance(QGuiApplication.instance(), QGuiApplication):
        return QFontMetricsF(font).height()
    point_size = font.pointSizeF()
    return max(1.0, (point_size if point_size > 0 else 10.0) * 1.35)


def achievement_capsule_geometry(
    *,
    font_family: str,
    capsule_font_size: int,
) -> tuple[float, float]:
    """Return retained capsule height/gap that contains the chosen font."""

    resolved_size = normalize_achievement_capsule_font_size(capsule_font_size)
    text_height = _font_height(
        QFont(font_family, resolved_size, QFont.Weight.DemiBold)
    )
    return (
        max(
            ACHIEVEMENT_CAPSULE_BASE_HEIGHT,
            float(math.ceil(text_height + 8.0)),
        ),
        max(
            ACHIEVEMENT_CAPSULE_BASE_GAP,
            float(math.ceil(text_height * 0.25)),
        ),
    )


def achievement_field_rail_count(
    field_count: int,
    *,
    double_capsules: bool,
    columns: int = 3,
    shelf_style: bool = False,
) -> int:
    """Return whole-row rail occupancy for supporting fields.

    Progress Pulse reserves the left rail and therefore uses two supporting
    columns.  Shelf Style renders label/value on one ledger row and does not
    consume the second capsule rail.
    """

    resolved_columns = max(1, int(columns))
    compact_rows = max(1, (max(0, int(field_count)) + resolved_columns - 1) // resolved_columns)
    rail_stride = 1 if shelf_style else (2 if double_capsules else 1)
    return compact_rows * rail_stride


def achievement_pulse_authored_size(
    *,
    show_artwork: bool,
    artwork_shape: str,
    artwork_size: int = ACHIEVEMENT_SQUARE_ARTWORK_DEFAULT,
    field_rail_count: int = 2,
    capsule_height: float = ACHIEVEMENT_CAPSULE_BASE_HEIGHT,
    capsule_gap: float = ACHIEVEMENT_CAPSULE_BASE_GAP,
) -> QSizeF:
    """Return the retained canvas for the selected artwork/capsule mode."""

    rail_count = max(1, int(field_rail_count))
    field_height = max(ACHIEVEMENT_CAPSULE_BASE_HEIGHT, float(capsule_height))
    field_gap = max(ACHIEVEMENT_CAPSULE_BASE_GAP, float(capsule_gap))
    baseline_block_height = (
        2.0 * ACHIEVEMENT_CAPSULE_BASE_HEIGHT + ACHIEVEMENT_CAPSULE_BASE_GAP
    )
    required_block_height = (
        rail_count * field_height + max(0, rail_count - 1) * field_gap
    )
    extra_height = max(0.0, required_block_height - baseline_block_height)
    resolved_shape = normalize_achievement_artwork_shape(artwork_shape)
    if show_artwork and resolved_shape == "portrait":
        portrait_height = (
            normalize_achievement_square_artwork_size(artwork_size)
            * ACHIEVEMENT_PORTRAIT_ASPECT_RATIO
        )
        required_height = (
            14.0
            + portrait_height
            + 6.0
            + 28.0
            + 12.0
            + required_block_height
            + 16.0
        )
        return QSizeF(
            ACHIEVEMENT_PULSE_PORTRAIT_AUTHORED_SIZE.width(),
            max(
                ACHIEVEMENT_PULSE_PORTRAIT_AUTHORED_SIZE.height(),
                required_height,
            ),
        )
    if show_artwork and resolved_shape == "square":
        return QSizeF(
            ACHIEVEMENT_PULSE_SQUARE_AUTHORED_SIZE.width(),
            ACHIEVEMENT_PULSE_SQUARE_AUTHORED_SIZE.height() + extra_height,
        )
    return QSizeF(
        ACHIEVEMENT_PULSE_AUTHORED_SIZE.width(),
        ACHIEVEMENT_PULSE_AUTHORED_SIZE.height() + extra_height,
    )


__all__ = [
    "ACHIEVEMENT_CAPSULE_BORDER_RGBA",
    "ACHIEVEMENT_CAPSULE_FILL_RGBA",
    "ACHIEVEMENT_CAPSULE_FONT_SIZE_DEFAULT",
    "ACHIEVEMENT_CAPSULE_FONT_SIZE_MAX",
    "ACHIEVEMENT_CAPSULE_FONT_SIZE_MIN",
    "ACHIEVEMENT_PULSE_AUTHORED_SIZE",
    "ACHIEVEMENT_PULSE_PORTRAIT_AUTHORED_SIZE",
    "ACHIEVEMENT_PULSE_SQUARE_AUTHORED_SIZE",
    "ACHIEVEMENT_SQUARE_ARTWORK_DEFAULT",
    "ACHIEVEMENT_SQUARE_ARTWORK_MAX",
    "ACHIEVEMENT_SQUARE_ARTWORK_MIN",
    "achievement_capsule_geometry",
    "achievement_field_rail_count",
    "achievement_pulse_authored_size",
    "normalize_achievement_artwork_shape",
    "normalize_achievement_capsule_font_size",
    "normalize_achievement_square_artwork_size",
]
