"""Family-authored Abandonment layout policy shared during retained cutover."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QSizeF


ABANDONMENT_AUTHORED_SIZE = QSizeF(600.0, 300.0)
ABANDONMENT_ARTWORK_SIZE_MIN = 110
ABANDONMENT_ARTWORK_SIZE_DEFAULT = 140
ABANDONMENT_ARTWORK_SIZE_MAX = 180
ABANDONMENT_ACCENT_RGBA = (222, 157, 88, 225)
ABANDONMENT_FIELD_DEFAULTS: dict[str, bool] = {
    "playtime": True,
    "achievements": True,
    "last_unlock": True,
    "last_played": True,
    "archive_class": False,
    "queue": False,
    "source": False,
    "pinned": False,
}
ABANDONMENT_LEDGER_ROW_HEIGHT = 31.0


def normalize_abandonment_artwork_size(value: object) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        resolved = ABANDONMENT_ARTWORK_SIZE_DEFAULT
    return max(
        ABANDONMENT_ARTWORK_SIZE_MIN,
        min(ABANDONMENT_ARTWORK_SIZE_MAX, resolved),
    )


def normalize_abandonment_artwork_shape(value: object) -> str:
    """Use a descriptive token while accepting the legacy portrait alias."""

    shape = str(value or "").strip().lower()
    return "portrait" if shape in {"portrait", "square"} else "wide"


def abandonment_authored_size(
    *,
    show_artwork: bool,
    artwork_shape: str,
    artwork_size: int,
    field_count: int = 4,
) -> QSizeF:
    """Grow the canvas for portrait artwork and every enabled ledger row."""

    resolved_size = normalize_abandonment_artwork_size(artwork_size)
    field_rows = max(0, (max(0, int(field_count)) + 1) // 2)
    ledger_height = ABANDONMENT_AUTHORED_SIZE.height() + (
        max(0, field_rows - 2) * ABANDONMENT_LEDGER_ROW_HEIGHT
    )
    if (
        show_artwork
        and normalize_abandonment_artwork_shape(artwork_shape) == "portrait"
    ):
        required_height = 76.0 + resolved_size * 1.4 + 22.0
        return QSizeF(
            ABANDONMENT_AUTHORED_SIZE.width(),
            max(ledger_height, required_height),
        )
    return QSizeF(ABANDONMENT_AUTHORED_SIZE.width(), ledger_height)


def abandonment_field_slot_count(
    field_visibility: Mapping[str, bool] | None,
) -> int:
    """Return stable layout slots from settings, even before evidence is loaded."""

    visibility = field_visibility or {}
    return sum(
        1
        for field_id, default in ABANDONMENT_FIELD_DEFAULTS.items()
        if bool(visibility.get(field_id, default))
    )


def abandonment_artwork_dimensions(
    *,
    show_artwork: bool,
    artwork_shape: str,
    artwork_size: int,
) -> QSizeF:
    """Return the authored artwork target for layout and presentation tests."""

    if not show_artwork:
        return QSizeF()
    resolved_size = normalize_abandonment_artwork_size(artwork_size)
    if normalize_abandonment_artwork_shape(artwork_shape) == "portrait":
        return QSizeF(float(resolved_size), resolved_size * 1.4)
    return QSizeF(
        min(238.0, resolved_size * 1.45),
        max(78.0, resolved_size * 0.66),
    )


__all__ = [
    "ABANDONMENT_ACCENT_RGBA",
    "ABANDONMENT_ARTWORK_SIZE_DEFAULT",
    "ABANDONMENT_ARTWORK_SIZE_MAX",
    "ABANDONMENT_ARTWORK_SIZE_MIN",
    "ABANDONMENT_AUTHORED_SIZE",
    "ABANDONMENT_FIELD_DEFAULTS",
    "ABANDONMENT_LEDGER_ROW_HEIGHT",
    "abandonment_artwork_dimensions",
    "abandonment_authored_size",
    "abandonment_field_slot_count",
    "normalize_abandonment_artwork_shape",
    "normalize_abandonment_artwork_size",
]
