"""Retained Games You Follow presentation contract (G2 staging).

Deliberately NOT admitted by the family registry until the shared Steam owner,
real Qt, cache/security, and dormant lease gates have passed. The first admitted
component will reuse this same model/QML; this module performs no source/network
work, import-time access, polling, or Settings writes.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from math import isfinite

from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, Property, Qt, Signal, QUrl
from PySide6.QtGui import QColor

from core.steam.games_followed_projection import FollowedNewsDisplay, project_followed_news
from core.steam.games_followed_source import FollowedNewsSnapshot
from rendering.custom_child_geometry import (
    CustomChildSize, clamp_child_geometry, child_role_map,
)
from rendering.games_followed_child_roles import FOLLOWED_CHILD_ROLES
from widgets.steam_followed_layout import followed_news_layout
from .steam_common import SteamSemanticPalette, project_steam_semantic_palette

_STEAM_LOGO = Path(__file__).resolve().parents[3] / "images" / "Steam_Logo_Cropped.png"

_CHILD_ROLE_MAP = child_role_map(FOLLOWED_CHILD_ROLES)
_MAX_ROWS = 8


class FollowedStoryRows(QAbstractListModel):
    """Exactly eight retained ordinal slots; refresh/resize never resets the model."""

    SlotRole = int(Qt.ItemDataRole.UserRole) + 1
    TitleRole = SlotRole + 1
    SourceRole = SlotRole + 2
    PublishedRole = SlotRole + 3
    FilledRole = SlotRole + 4
    ActionRole = SlotRole + 5

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: tuple[object | None, ...] = (None,) * _MAX_ROWS

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else _MAX_ROWS

    def roleNames(self) -> dict[int, bytes]:  # noqa: N802
        return {
            self.SlotRole: b"storySlot",
            self.TitleRole: b"storyTitle",
            self.SourceRole: b"storySource",
            self.PublishedRole: b"storyPublished",
            self.FilledRole: b"storyFilled",
            self.ActionRole: b"storyActionEnabled",
        }

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)) -> object:
        if not index.isValid() or not 0 <= index.row() < _MAX_ROWS:
            return None
        slot = index.row()
        row = self._rows[slot]
        if role == self.SlotRole:
            return slot
        if role == self.FilledRole:
            return row is not None
        if role == self.ActionRole:
            return False  # No click permission until secure-helper/redirect admission.
        if role == self.TitleRole:
            return "" if row is None else row.title
        if role == self.SourceRole:
            return "" if row is None else row.source_label
        if role == self.PublishedRole:
            return "" if row is None else row.published_label
        return None

    def apply_display(self, display: FollowedNewsDisplay) -> bool:
        next_rows: tuple[object | None, ...] = tuple(display.rows[:_MAX_ROWS]) + (
            (None,) * (_MAX_ROWS - min(_MAX_ROWS, len(display.rows)))
        )
        if next_rows == self._rows:
            return False
        old = self._rows
        self._rows = next_rows
        for slot in range(_MAX_ROWS):
            if old[slot] != next_rows[slot]:
                self.dataChanged.emit(
                    self.index(slot, 0), self.index(slot, 0),
                    [self.TitleRole, self.SourceRole, self.PublishedRole,
                     self.FilledRole, self.ActionRole],
                )
        return True


@dataclass(frozen=True)
class FollowedPresentationConfig:
    base_width: float = 520.0
    base_height: float = 360.0
    font_family: str = "Inter"
    font_size: int = 17


class GamesYouFollowPresentationModel(QObject):
    """Display-only accepted projection and CUSTOM preview; no backend authority."""

    contentExtentChanged = Signal()
    customGeometryChanged = Signal()
    displayChanged = Signal()
    layoutChanged = Signal()

    def __init__(self, config: FollowedPresentationConfig | None = None) -> None:
        super().__init__()
        self.config = config or FollowedPresentationConfig()
        self._rows = FollowedStoryRows(self)
        # Inherit existing Steam semantic theme roles rather than create new
        # per-card colour authority; the eventual family adapter projects
        # Settings/style changes through this same model's theme edge.
        self._palette = project_steam_semantic_palette(fallback=SteamSemanticPalette(
            info_surface=(38, 51, 69, 230),
            info_border=(102, 192, 244, 230),
            info_text=(237, 246, 252, 245),
        ))
        self._display = project_followed_news(FollowedNewsSnapshot("unavailable"))
        self._extent: tuple[float, float] | None = None
        self._custom: dict[str, CustomChildSize] = {}
        self._layout = followed_news_layout(
            self.config.base_width, self.config.base_height, 0,
        )
        self._retired = False

    @Property(QObject, constant=True)
    def storyRows(self) -> FollowedStoryRows:
        return self._rows

    @Property(str, notify=displayChanged)
    def statusLabel(self) -> str:
        return self._display.status_label

    @Property(bool, notify=displayChanged)
    def stale(self) -> bool:
        return self._display.stale

    @Property(int, notify=displayChanged)
    def selectedStoryCount(self) -> int:
        return len(self._display.rows)

    @Property(int, notify=displayChanged)
    def remainingFollowedCount(self) -> int:
        return self._display.remaining_followed_count

    @Property(int, notify=layoutChanged)
    def visibleStoryCount(self) -> int:
        return self._layout.visible_count

    @Property(int, notify=layoutChanged)
    def overflowStoryCount(self) -> int:
        return self._layout.overflow_count

    @Property(int, notify=layoutChanged)
    def layoutColumns(self) -> int:
        return max(1, self._layout.columns)

    @Property(str, notify=layoutChanged)
    def layoutArrangement(self) -> str:
        return self._layout.arrangement

    @Property(float, notify=contentExtentChanged)
    def authoredWidth(self) -> float:
        return self._extent[0] if self._extent else self.config.base_width

    @Property(float, notify=contentExtentChanged)
    def authoredHeight(self) -> float:
        return self._extent[1] if self._extent else self.config.base_height

    @Property(float, constant=True)
    def baseAuthoredWidth(self) -> float:
        return self.config.base_width

    @Property(float, constant=True)
    def baseAuthoredHeight(self) -> float:
        return self.config.base_height

    @Property(str, constant=True)
    def fontFamily(self) -> str:
        return self.config.font_family

    @Property(int, constant=True)
    def fontSize(self) -> int:
        return self.config.font_size

    @Property(QColor, constant=True)
    def primaryColor(self) -> QColor:
        return QColor(*self._palette.info_text)

    @Property(QColor, constant=True)
    def accentColor(self) -> QColor:
        return QColor(*self._palette.info_border)

    @Property(QColor, constant=True)
    def tileColor(self) -> QColor:
        return QColor(*self._palette.info_surface)

    @Property(QUrl, constant=True)
    def steamLogo(self) -> QUrl:
        return QUrl.fromLocalFile(str(_STEAM_LOGO))

    @Property("QVariantMap", notify=customGeometryChanged)
    def customChildGeometry(self) -> dict[str, dict[str, object]]:
        return {role: value.to_mapping() for role, value in self._custom.items()}

    def _update_layout(self) -> None:
        current = followed_news_layout(
            self.authoredWidth, self.authoredHeight, len(self._display.rows),
            previous_arrangement=self._layout.arrangement,
        )
        if current != self._layout:
            self._layout = current
            self.layoutChanged.emit()

    def accept_snapshot(self, snapshot: FollowedNewsSnapshot) -> bool:
        """Only the future admitted owner calls this on the GUI thread."""
        if self._retired:
            return False
        projected = project_followed_news(snapshot)
        if projected == self._display:
            return False
        self._display = projected
        self._rows.apply_display(projected)
        self.displayChanged.emit()
        self._update_layout()
        return True

    def set_content_extent(self, width: object, height: object) -> bool:
        if self._retired:
            return False
        if width is None or height is None:
            extent = None
        else:
            try:
                w, h = float(width), float(height)
            except (TypeError, ValueError):
                return False
            if not isfinite(w) or not isfinite(h):
                return False
            extent = (max(180.0, min(1600.0, w)), max(130.0, min(2000.0, h)))
        if self._extent == extent:
            return False
        self._extent = extent
        self.contentExtentChanged.emit()
        self._update_layout()
        return True

    def set_custom_child_geometry(self, values: object) -> bool:
        if self._retired:
            return False
        source = values if isinstance(values, Mapping) else {}
        next_geometry: dict[str, CustomChildSize] = {}
        for name, descriptor in _CHILD_ROLE_MAP.items():
            value = source.get(name)
            if not isinstance(value, Mapping):
                continue
            normalized = clamp_child_geometry(
                descriptor, value.get("width_scale", 1.0),
                value.get("height_scale", 1.0), value.get("x_offset", 0.0),
                value.get("y_offset", 0.0), value.get("alignment"), value.get("anchor"),
            )
            if not normalized.is_authored:
                next_geometry[name] = normalized
        if next_geometry == self._custom:
            return False
        self._custom = next_geometry
        self.customGeometryChanged.emit()
        return True

    def apply_custom_layout_size_payload(self, payload: Mapping[str, object]) -> None:
        extent = payload.get("content_extent")
        if isinstance(extent, (tuple, list)) and len(extent) == 2:
            self.set_content_extent(extent[0], extent[1])
        else:
            self.set_content_extent(None, None)
        self.set_custom_child_geometry(payload.get("child_geometry"))

    def retire(self) -> None:
        self._retired = True


__all__ = [
    "FOLLOWED_CHILD_ROLES", "FollowedPresentationConfig",
    "FollowedStoryRows", "GamesYouFollowPresentationModel",
]
