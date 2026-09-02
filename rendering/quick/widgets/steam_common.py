"""Small retained-presentation primitives shared by Steam card families."""

from __future__ import annotations

from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, Qt
from PySide6.QtGui import QColor, QImage

from widgets.steam_card_models import SteamCardField
from core.settings.shadow_direction import (
    resolve_directional_extensions,
    resolve_signed_offset,
)
from .theme_projection import resolve_rgba_role
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


@dataclass(frozen=True)
class SteamSemanticPalette:
    """Presentation-ready semantic colours shared by retained Steam cards.

    Each family supplies its accepted current pixels as fallbacks. Optional Widget
    Theme roles can then unify panels/gradients/outlines without exposing another
    permanent row of per-family Settings swatches.
    """

    info_surface: tuple[int, int, int, int] = (240, 144, 45, 230)
    info_border: tuple[int, int, int, int] = (255, 230, 180, 220)
    info_text: tuple[int, int, int, int] = (255, 255, 255, 255)
    tooltip_surface: tuple[int, int, int, int] = (43, 43, 43, 255)
    tooltip_border: tuple[int, int, int, int] = (154, 154, 154, 200)
    tooltip_text: tuple[int, int, int, int] = (255, 255, 255, 255)
    artwork_surface: tuple[int, int, int, int] = (12, 15, 20, 230)
    artwork_border: tuple[int, int, int, int] = (255, 255, 255, 175)
    artwork_stripe: tuple[int, int, int, int] = (255, 255, 255, 38)
    artwork_gradient_start: tuple[int, int, int, int] = (105, 115, 124, 255)
    artwork_gradient_middle: tuple[int, int, int, int] = (105, 115, 124, 255)
    artwork_gradient_end: tuple[int, int, int, int] = (23, 27, 32, 255)
    metric_surface: tuple[int, int, int, int] = (199, 213, 224, 69)
    metric_border: tuple[int, int, int, int] = (199, 213, 224, 199)
    metric_inner_border: tuple[int, int, int, int] = (199, 213, 224, 99)
    metric_separator: tuple[int, int, int, int] = (199, 213, 224, 110)


def project_steam_semantic_palette(
    *,
    fallback: SteamSemanticPalette,
) -> SteamSemanticPalette:
    """Resolve sparse Steam roles over one family's accepted local defaults."""

    def resolved(role: str, local_role: str, value: tuple[int, int, int, int]):
        return resolve_rgba_role(
            role,
            local_roles={local_role: value},
            fallback=value,
        )

    return SteamSemanticPalette(
        info_surface=resolved("steam.info.surface", "local.surface.alt", fallback.info_surface),
        info_border=resolved("steam.info.border", "local.border", fallback.info_border),
        info_text=resolved("steam.info.text", "local.text", fallback.info_text),
        tooltip_surface=resolved("steam.tooltip.surface", "local.surface", fallback.tooltip_surface),
        tooltip_border=resolved("steam.tooltip.border", "local.border", fallback.tooltip_border),
        tooltip_text=resolved("steam.tooltip.text", "local.text", fallback.tooltip_text),
        artwork_surface=resolved("steam.artwork.surface", "local.surface.alt", fallback.artwork_surface),
        artwork_border=resolved("steam.artwork.border", "local.border", fallback.artwork_border),
        artwork_stripe=resolved("steam.artwork.stripe", "local.separator", fallback.artwork_stripe),
        artwork_gradient_start=resolved(
            "steam.artwork.gradient.start", "local.gradient.start", fallback.artwork_gradient_start
        ),
        artwork_gradient_middle=resolved(
            "steam.artwork.gradient.middle", "local.gradient.middle", fallback.artwork_gradient_middle
        ),
        artwork_gradient_end=resolved(
            "steam.artwork.gradient.end", "local.gradient.end", fallback.artwork_gradient_end
        ),
        metric_surface=resolved("steam.metric.surface", "local.surface.alt", fallback.metric_surface),
        metric_border=resolved("steam.metric.border", "local.border", fallback.metric_border),
        metric_inner_border=resolved(
            "steam.metric.inner_border", "local.border", fallback.metric_inner_border
        ),
        metric_separator=resolved(
            "steam.metric.separator", "local.separator", fallback.metric_separator
        ),
    )


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
    card_offset = resolve_signed_offset(direction, *ORDINARY_CARD_SHADOW_BASE)
    card_extensions = resolve_directional_extensions(direction, frame_extra)
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
            shadow_extend_left=card_extensions[0],
            shadow_extend_top=card_extensions[1],
            shadow_extend_right=card_extensions[2],
            shadow_extend_bottom=card_extensions[3],
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
    "SteamSemanticPalette",
    "accepted_local_image_source",
    "as_bool",
    "bounded_float",
    "bounded_int",
    "optional_appid",
    "project_steam_card_style",
    "project_steam_semantic_palette",
    "rgba",
    "with_alpha",
]
