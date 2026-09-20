"""Retained Games You Follow presentation using one shared Steam news lease.

The model never owns credentials, provider work, a timer, or Settings writes.
The ordinary family adapter injects one neutral runtime lease after QML
construction and activates it only when a real display presenter is admitted.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from collections.abc import Callable
from pathlib import Path
from math import isfinite

from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, Property, Qt, Signal, QUrl
from PySide6.QtGui import QColor

from core.settings.default_contract import require_canonical_default
from core.steam.games_followed_projection import FollowedNewsDisplay, project_followed_news
from core.steam.games_followed_source import FollowedNewsSnapshot
from core.steam.links import news_article_target
from rendering.custom_child_geometry import (
    CustomChildSize, clamp_child_geometry, child_role_map,
)
from rendering.games_followed_child_roles import FOLLOWED_CHILD_ROLES
from widgets.steam_followed_layout import followed_news_layout
from .host import OrdinaryWidgetPresentationHost, OverlayCardStyle, OverlayWidgetGeometry, RetainedOverlayWidget
from .theme_projection import (
    resolve_card_surface_colors, resolve_header_colors, resolve_primary_text_color,
)
from .steam_common import (
    SteamSemanticPalette, SteamCardStyleProjection, project_steam_semantic_palette,
    project_steam_card_style, as_bool, bounded_float, rgba as steam_rgba,
)

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
    GameRole = SlotRole + 6
    PreviewRole = SlotRole + 7
    ArtworkRole = SlotRole + 8

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
            self.GameRole: b"storyGame",
            self.PreviewRole: b"storyPreview",
            self.ArtworkRole: b"storyArtwork",
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
            return bool(row is not None and row.action_enabled)
        if role == self.GameRole:
            return "" if row is None else row.game_label
        if role == self.PreviewRole:
            return "" if row is None else row.preview
        if role == self.ArtworkRole:
            return "" if row is None else row.local_artwork_source
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
                     self.FilledRole, self.ActionRole, self.GameRole,
                     self.PreviewRole, self.ArtworkRole],
                )
        return True


@dataclass(frozen=True)
class FollowedPresentationConfig:
    base_width: float = 520.0
    base_height: float = 360.0
    font_family: str = "Inter"
    font_size: int = 17
    story_cap: int = 8
    headline_chars: int = 180
    headline_alignment: str = "left"
    show_artwork: bool = True
    artwork_shape: str = "wide"
    show_refresh_frame: bool = False

    @classmethod
    def from_widgets_mapping(cls, widgets: Mapping[str, object]) -> "FollowedPresentationConfig":
        """Resolve authored values from the existing steam_progress default root."""
        defaults = require_canonical_default("widgets.steam_progress")
        values = widgets.get("steam_progress", {}) if isinstance(widgets, Mapping) else {}
        if not isinstance(values, Mapping):
            values = {}

        def dimension(name: str, lower: float, upper: float) -> float:
            try:
                result = float(values.get(name, defaults[name]))
            except (TypeError, ValueError):
                result = float(defaults[name])
            if not isfinite(result):
                result = float(defaults[name])
            return max(lower, min(upper, result))

        return cls(
            base_width=dimension("preferred_width", 180.0, 1600.0),
            base_height=dimension("preferred_height", 130.0, 2000.0),
            font_family=str(values.get("font_family") or defaults["font_family"]),
            font_size=int(dimension("font_size", 8, 40)),
            story_cap=int(dimension("story_cap", 1, 8)),
            headline_chars=int(dimension("headline_truncation_chars", 48, 300)),
            headline_alignment=(str(values.get("headline_alignment", defaults["headline_alignment"]))
                                if values.get("headline_alignment", defaults["headline_alignment"])
                                in {"left", "center", "right"} else "left"),
            show_artwork=as_bool(values.get("show_artwork"), defaults["show_artwork"]),
            show_refresh_frame=as_bool(values.get("show_refresh_frame"), defaults["show_refresh_frame"]),
            artwork_shape=(str(values.get("artwork_shape", defaults["artwork_shape"]))
                           if values.get("artwork_shape", defaults["artwork_shape"])
                           in {"wide", "square", "portrait"} else "wide"),
        )


def followed_visual_style(
    widgets: Mapping[str, object], shadow_values: Mapping[str, object] | None = None,
) -> SteamCardStyleProjection:
    """Project the same outer shell/shadow/text contract as other Steam cards."""
    defaults = require_canonical_default("widgets.steam_progress")
    values = widgets.get("steam_progress", {}) if isinstance(widgets, Mapping) else {}
    if not isinstance(values, Mapping):
        values = {}
    background, border = resolve_card_surface_colors(
        values=values, defaults=defaults,
        background_color=steam_rgba(values.get("bg_color"), tuple(defaults["bg_color"])),
        background_opacity=bounded_float(values.get("bg_opacity"), defaults["bg_opacity"], 0.0, 1.0),
        border_color=steam_rgba(values.get("border_color"), tuple(defaults["border_color"])),
        border_opacity=bounded_float(values.get("border_opacity"), defaults["border_opacity"], 0.0, 1.0),
    )
    global_values = widgets.get("global", {}) if isinstance(widgets, Mapping) else {}
    if not isinstance(global_values, Mapping):
        global_values = {}
    canonical_width = float(require_canonical_default("widgets.global.card_border_width_px"))
    width = bounded_float(global_values.get("card_border_width_px"), canonical_width, 0.0, 12.0)
    return project_steam_card_style(
        show_background=as_bool(values.get("show_background"), defaults["show_background"]),
        background_color=background, background_opacity=1.0,
        border_color=border, border_opacity=1.0,
        shadow_values=shadow_values if shadow_values is not None
        else require_canonical_default("widgets.shadows"),
        border_width=width,
    )


def followed_card_style(widgets: Mapping[str, object],
                        shadow_values: Mapping[str, object] | None = None) -> OverlayCardStyle:
    """Compatibility with the existing card-shell construction seam."""
    return followed_visual_style(widgets, shadow_values).card_style


class GamesYouFollowPresentationModel(QObject):
    """Display-only accepted projection and CUSTOM preview; no backend authority."""

    contentExtentChanged = Signal()
    customGeometryChanged = Signal()
    displayChanged = Signal()
    layoutChanged = Signal()

    def __init__(self, config: FollowedPresentationConfig | None = None,
                 *, runtime_generation: int | None = None,
                 visual_style: SteamCardStyleProjection | None = None,
                 widgets: Mapping[str, object] | None = None) -> None:
        super().__init__()
        self.config = config or FollowedPresentationConfig()
        self._visual_style = visual_style or followed_visual_style(widgets or {})
        defaults = require_canonical_default("widgets.steam_progress")
        card_values = (widgets or {}).get("steam_progress", {})
        if not isinstance(card_values, Mapping):
            card_values = {}
        self._header_fill, self._header_border, self._header_text = resolve_header_colors(
            "steam_progress", values=card_values, defaults=defaults,
            fill=steam_rgba(defaults["bg_color"], (35, 35, 35, 255)),
            border=steam_rgba(defaults["border_color"], (255, 255, 255, 255)),
            text=steam_rgba(defaults["color"], (255, 255, 255, 230)),
        )
        self._body_text = resolve_primary_text_color(
            values=card_values, defaults=defaults,
            text_color=steam_rgba(defaults["color"], (255, 255, 255, 230)),
        )
        self._runtime_generation = runtime_generation
        self._runtime_service: object | None = None
        self._active = False
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
        self._snapshot = FollowedNewsSnapshot("unavailable")
        self._article_action: Callable[[str, str], bool] | None = None

    @Property(QObject, constant=True)
    def storyRows(self) -> FollowedStoryRows:
        return self._rows

    @Property(str, notify=displayChanged)
    def statusLabel(self) -> str:
        return self._display.status_label

    @Property(bool, notify=displayChanged)
    def stale(self) -> bool:
        return self._display.stale

    @Property(int, constant=True)
    def headlineChars(self) -> int:
        return self.config.headline_chars

    @Property(str, constant=True)
    def headlineAlignment(self) -> str:
        return self.config.headline_alignment

    @Property(bool, constant=True)
    def showArtwork(self) -> bool:
        return self.config.show_artwork

    @Property(str, constant=True)
    def artworkShape(self) -> str:
        return self.config.artwork_shape

    @Property(int, notify=displayChanged)
    def selectedStoryCount(self) -> int:
        return len(self._display.rows)

    @Property(int, notify=displayChanged)
    def omittedBySetting(self) -> int:
        """Retained source rows deliberately hidden by the authored story cap."""
        return max(0, len(self._snapshot.stories) - len(self._display.rows))

    @Property(int, notify=displayChanged)
    def checkedCount(self) -> int:
        return self._display.checked_count

    @Property(int, notify=displayChanged)
    def coveredCount(self) -> int:
        return self._display.covered_count

    @Property(int, notify=displayChanged)
    def followedCount(self) -> int:
        return self._display.followed_count

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

    @Property(int, notify=layoutChanged)
    def layoutRows(self) -> int:
        return self._layout.rows

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
        return QColor(*self._body_text)

    @Property(QColor, constant=True)
    def accentColor(self) -> QColor:
        return QColor(*self._palette.info_border)

    @Property(QColor, constant=True)
    def tileColor(self) -> QColor:
        return QColor(*self._palette.info_surface)

    @Property(QColor, constant=True)
    def headerFillColor(self) -> QColor:
        return QColor(*self._header_fill)

    @Property(QColor, constant=True)
    def headerBorderColor(self) -> QColor:
        return QColor(*self._header_border)

    @Property(QColor, constant=True)
    def headerTextColor(self) -> QColor:
        return QColor(*self._header_text)

    @Property(float, constant=True)
    def headerBorderWidth(self) -> float:
        return max(1.0, self._visual_style.card_style.border_width - 3.0)

    @Property(bool, constant=True)
    def textShadowEnabled(self) -> bool:
        return self._visual_style.text_shadow_enabled

    @Property(QColor, constant=True)
    def textShadowColor(self) -> QColor:
        return QColor(self._visual_style.text_shadow_color)

    @Property(float, constant=True)
    def textShadowOffsetX(self) -> float:
        return self._visual_style.text_shadow_offset_x

    @Property(float, constant=True)
    def textShadowOffsetY(self) -> float:
        return self._visual_style.text_shadow_offset_y

    @Property(bool, constant=True)
    def showRefreshFrame(self) -> bool:
        return self.config.show_refresh_frame

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
            show_artwork=self.config.show_artwork,
        )
        if current != self._layout:
            self._layout = current
            self.layoutChanged.emit()

    def set_runtime_service(self, service: object) -> None:
        """Attach the neutral generation lease; source identity never enters QML."""
        if self._retired or self._runtime_service is not None:
            raise RuntimeError("Games You Follow service may be attached exactly once")
        service.attach_consumer(self)
        self._runtime_service = service

    def is_games_followed_consumer_alive(self) -> bool:
        return self._active and not self._retired

    def activate(self, thread_manager: object | None = None) -> bool:
        if self._retired or self._runtime_service is None:
            return False
        if self._active:
            return True
        service = self._runtime_service
        service.set_thread_manager(thread_manager, generation=self._runtime_generation)
        self._active = True
        try:
            accepted = bool(service.start())
        except Exception:
            self._active = False
            raise
        if not accepted:
            self._active = False
        return accepted

    def on_games_followed_runtime_snapshot(self, snapshot: FollowedNewsSnapshot) -> bool:
        if not self.is_games_followed_consumer_alive():
            return False
        return self.accept_snapshot(snapshot)

    def request_manual_refresh(self) -> bool:
        if not self.is_games_followed_consumer_alive() or self._runtime_service is None:
            return False
        return bool(self._runtime_service.request_refresh())

    def accept_snapshot(self, snapshot: FollowedNewsSnapshot) -> bool:
        """One GUI-thread admission from the neutral shared source; no QML IDs."""
        if self._retired:
            return False
        projected = project_followed_news(snapshot)
        projected = FollowedNewsDisplay(
            status=projected.status, status_label=projected.status_label,
            rows=projected.rows[:self.config.story_cap],
            remaining_followed_count=projected.remaining_followed_count,
            checked_count=projected.checked_count, stale=projected.stale,
            covered_count=projected.covered_count, followed_count=projected.followed_count,
            selected_story_count=min(projected.selected_story_count, self.config.story_cap),
        )
        prior_omitted = self.omittedBySetting
        self._snapshot = snapshot
        if projected == self._display and self.omittedBySetting == prior_omitted:
            return False
        self._display = projected
        self._rows.apply_display(projected)
        self.displayChanged.emit()
        self._update_layout()
        return True

    def set_article_action(self, callback: Callable[[str, str], bool] | None) -> None:
        self._article_action = callback

    def open_story(self, slot: object) -> bool:
        """Resolve an ordinal click against the currently accepted private revision."""
        if (not self.is_games_followed_consumer_alive() or type(slot) is not int
            or not 0 <= slot < len(self._display.rows)
            or slot >= len(self._snapshot.stories)
            or self._article_action is None):
            return False
        story = self._snapshot.stories[slot]
        shown = self._display.rows[slot]
        if not story.action_available or not shown.action_enabled:
            return False
        canonical = f"https://store.steampowered.com/news/app/{story.appid}/view/{story.gid}"
        target = news_article_target(story.appid, story.gid, canonical)
        if target is None:
            return False
        return bool(self._article_action("news_article", target.browser_url))

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
        if self._retired:
            return
        self._retired = True
        self._active = False
        self._article_action = None
        if self._runtime_service is not None:
            self._runtime_service.stop()
            self._runtime_service = None


class RetainedGamesYouFollowPresentation:
    """Host-owned card; all editing, placement and retirement remain shared."""

    def __init__(
        self, *, host: OrdinaryWidgetPresentationHost,
        model: GamesYouFollowPresentationModel,
        geometry: OverlayWidgetGeometry,
        card_style: OverlayCardStyle,
        on_steam_action_requested: Callable[[str, str], bool] | None = None,
    ) -> None:
        self._model = model
        model.set_article_action(on_steam_action_requested)
        self._retained: RetainedOverlayWidget = host.create_family_widget(
            "steam_progress", initial_properties={"followedModel": model},
            object_name="steam_progress", model_identity="steam_progress",
            geometry=geometry, card_style=card_style,
        )
        for name, handler in (("refreshRequested", model.request_manual_refresh),
                              ("articleRequested", model.open_story)):
            signal = getattr(self._retained.item, name, None)
            if signal is not None and hasattr(signal, "connect"):
                signal.connect(handler)
        self._retained.add_retirement_callback(model.retire)
        self._retained.set_custom_layout_size_payload_handler(
            model.apply_custom_layout_size_payload
        )

    @property
    def item(self):
        return self._retained.item

    @property
    def model(self) -> GamesYouFollowPresentationModel:
        return self._model

    def activate(self, thread_manager: object | None = None) -> bool:
        return self._model.activate(thread_manager)

    def set_geometry(self, geometry: OverlayWidgetGeometry) -> None:
        self._retained.set_geometry(geometry)

    def set_fade_opacity(self, opacity: float) -> None:
        self._retained.set_fade_opacity(opacity)

    def retire(self) -> bool:
        return self._retained.retire()


__all__ = [
    "FOLLOWED_CHILD_ROLES", "FollowedPresentationConfig",
    "FollowedStoryRows", "GamesYouFollowPresentationModel",
    "RetainedGamesYouFollowPresentation", "followed_card_style",
    "followed_visual_style",
]
