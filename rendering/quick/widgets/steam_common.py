"""Small retained-presentation primitives shared by Steam card families."""

from __future__ import annotations

from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, Qt
from PySide6.QtGui import QColor, QImage

from widgets.steam_card_models import SteamCardField
from core.settings.shadow_direction import resolve_signed_offset
from .host import (
    ORDINARY_CARD_SHADOW_BASE,
    ORDINARY_TEXT_SHADOW_BASE,
    OverlayCardStyle,
)


def bounded_int(value: object, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(low, min(high, parsed))


def bounded_float(value: object, default: float, low: float, high: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(default)
    return max(low, min(high, parsed))


def as_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return default if value is None else bool(value)


def rgba(
    value: object,
    default: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    if isinstance(value, QColor):
        color = QColor(value)
    elif isinstance(value, (tuple, list)) and len(value) in {3, 4}:
        channels = list(value)
        if len(channels) == 3:
            channels.append(255)
        try:
            color = QColor(
                *(max(0, min(255, int(channel))) for channel in channels)
            )
        except (TypeError, ValueError):
            color = QColor(*default)
    else:
        color = QColor(str(value)) if value is not None else QColor()
    if not color.isValid():
        color = QColor(*default)
    return color.red(), color.green(), color.blue(), color.alpha()


def with_alpha(
    color_channels: tuple[int, int, int, int],
    scale: float,
) -> QColor:
    color = QColor(*color_channels)
    color.setAlpha(max(0, min(255, int(round(color.alpha() * scale)))))
    return color


def optional_appid(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


@dataclass(frozen=True)
class SteamCardStyleProjection:
    """Shared ordinary-card shell/text shadow projection for Steam families."""

    card_style: OverlayCardStyle
    text_shadow_enabled: bool
    text_shadow_color: QColor
    text_shadow_offset_x: float
    text_shadow_offset_y: float


def project_steam_card_style(
    *,
    show_background: bool,
    background_color: tuple[int, int, int, int],
    background_opacity: float,
    border_color: tuple[int, int, int, int],
    border_opacity: float,
    shadow_values: Mapping[str, object],
    border_width: float,
) -> SteamCardStyleProjection:
    direction = shadow_values.get("direction", "SE")
    frame_extra = bounded_float(
        shadow_values.get("frame_extra_offset"), 0.0, 0.0, 40.0
    )
    text_extra = bounded_float(
        shadow_values.get("text_extra_offset"), 0.0, 0.0, 40.0
    )
    card_offset = resolve_signed_offset(
        direction,
        ORDINARY_CARD_SHADOW_BASE[0] + frame_extra,
        ORDINARY_CARD_SHADOW_BASE[1] + frame_extra,
    )
    text_offset = resolve_signed_offset(
        direction,
        ORDINARY_TEXT_SHADOW_BASE[0] + text_extra,
        ORDINARY_TEXT_SHADOW_BASE[1] + text_extra,
    )
    shadow_rgba = rgba(shadow_values.get("color"), (0, 0, 0, 255))
    return SteamCardStyleProjection(
        card_style=OverlayCardStyle(
            shell_enabled=show_background,
            background_color=with_alpha(background_color, background_opacity),
            border_color=with_alpha(border_color, border_opacity),
            border_width=max(0.0, float(border_width)),
            corner_radius=10.0,
            padding=0.0,
            shadow_enabled=(
                show_background and as_bool(shadow_values.get("enabled"), True)
            ),
            shadow_color=with_alpha(
                shadow_rgba,
                bounded_float(
                    shadow_values.get("frame_opacity"), 0.77, 0.0, 1.0
                ),
            ),
            shadow_blur=bounded_float(
                shadow_values.get("blur_radius"), 18.0, 0.0, 80.0
            ),
            shadow_offset_x=card_offset[0],
            shadow_offset_y=card_offset[1],
        ),
        text_shadow_enabled=as_bool(
            shadow_values.get("text_enabled"), True
        ),
        text_shadow_color=with_alpha(
            shadow_rgba,
            bounded_float(
                shadow_values.get("text_opacity"), 0.33, 0.0, 1.0
            ),
        ),
        text_shadow_offset_x=text_offset[0],
        text_shadow_offset_y=text_offset[1],
    )


def accepted_local_image_source(image: QImage, identity: object) -> str:
    """Project an accepted runtime image identity to a QML-safe local source."""

    normalized = str(identity or "").strip()
    if image.isNull() or not normalized:
        return ""
    if normalized.lower().startswith("file:"):
        return normalized
    return Path(normalized).resolve().as_uri()


class SteamCardFieldListModel(QAbstractListModel):
    """Stable enabled-field rows shared by retained Steam presentations."""

    FieldIdRole = int(Qt.ItemDataRole.UserRole) + 1
    LabelRole = FieldIdRole + 1
    ValueRole = FieldIdRole + 2

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: tuple[SteamCardField, ...] = ()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        return {
            self.FieldIdRole: row.field_id,
            self.LabelRole: row.label,
            self.ValueRole: row.value,
            int(Qt.ItemDataRole.DisplayRole): row.value,
        }.get(int(role))

    def roleNames(self) -> dict[int, bytes]:  # noqa: N802
        return {
            self.FieldIdRole: b"fieldId",
            self.LabelRole: b"fieldLabel",
            self.ValueRole: b"fieldValue",
        }

    @property
    def rows(self) -> tuple[SteamCardField, ...]:
        return self._rows

    def replace_rows(self, rows: Iterable[SteamCardField]) -> bool:
        resolved = tuple(row for row in rows if row.enabled)
        if resolved == self._rows:
            return False
        previous = self._rows
        old_count = len(previous)
        new_count = len(resolved)
        common = min(old_count, new_count)
        if new_count < old_count:
            self.beginRemoveRows(QModelIndex(), new_count, old_count - 1)
            self._rows = previous[:new_count]
            self.endRemoveRows()
        elif new_count > old_count:
            self.beginInsertRows(QModelIndex(), old_count, new_count - 1)
            self._rows = (*previous, *resolved[old_count:])
            self.endInsertRows()
        if common:
            mutable = list(self._rows)
            changed = []
            for index in range(common):
                if mutable[index] != resolved[index]:
                    mutable[index] = resolved[index]
                    changed.append(index)
            self._rows = tuple(mutable)
            if changed:
                self.dataChanged.emit(
                    self.index(min(changed), 0),
                    self.index(max(changed), 0),
                    [self.FieldIdRole, self.LabelRole, self.ValueRole],
                )
        if new_count > common:
            self._rows = resolved
        return True


__all__ = [
    "SteamCardFieldListModel",
    "SteamCardStyleProjection",
    "accepted_local_image_source",
    "as_bool",
    "bounded_float",
    "bounded_int",
    "optional_appid",
    "project_steam_card_style",
    "rgba",
    "with_alpha",
]
