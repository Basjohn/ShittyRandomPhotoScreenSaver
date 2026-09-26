"""Retained presentation for the general Feeds family.

Acquisition/cache/cadence live in ``widgets.feed_runtime``. This module owns
only immutable settings projection, one retained row model, and semantic URL /
manual-refresh actions.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
import base64
import time
from typing import Any
from urllib.parse import urlsplit

from PySide6.QtCore import (
    QAbstractListModel, QBuffer, QIODevice, QModelIndex, QObject, QPointF, QRectF,
    Property, Qt, Signal, Slot,
)
from PySide6.QtGui import QColor, QImage, QPainter, QPen

from core.feeds.config import CustomFeedConfig
from core.feeds.models import FeedRefreshResult
from core.feeds.projection import FeedDisplay, FeedDisplayRow, project_feed
from core.settings.default_contract import require_canonical_default
from core.settings.shadow_direction import resolve_directional_extensions, resolve_signed_offset
from rendering.custom_child_geometry import CustomChildSize, child_role_map, clamp_child_geometry
from rendering.feed_child_roles import FEED_CONTENT_EXTENT_MINIMUM, FEED_CUSTOM_CHILD_ROLES
from rendering.quick.shadow_snapshot import QuickShadowSnapshot

from .host import (
    ORDINARY_CARD_SHADOW_BASE,
    ORDINARY_TEXT_SHADOW_BASE,
    OrdinaryWidgetPresentationHost,
    OverlayCardStyle,
    OverlayWidgetGeometry,
    RetainedOverlayWidget,
)
from .theme_projection import (
    resolve_card_surface_colors,
    resolve_header_colors,
    resolve_primary_text_color,
)


def _bounded_int(value: object, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(low, min(high, parsed))


def _coerce_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        return bool(default)
    if value is None:
        return bool(default)
    return bool(value)


def _bounded_float(value: object, default: float, low: float, high: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(default)
    return max(low, min(high, parsed))


def _rgba(value: object, fallback: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    if isinstance(value, (tuple, list)) and len(value) in {3, 4}:
        channels = list(value)
        if len(channels) == 3:
            channels.append(255)
        try:
            return tuple(max(0, min(255, int(channel))) for channel in channels)  # type: ignore[return-value]
        except (TypeError, ValueError):
            pass
    return tuple(fallback)


def _qcolor(value: tuple[int, int, int, int]) -> QColor:
    return QColor(*value)


def _with_alpha(value: tuple[int, int, int, int], scale: float) -> QColor:
    color = QColor(*value)
    color.setAlpha(max(0, min(255, int(round(color.alpha() * float(scale))))))
    return color




@lru_cache(maxsize=64)
def _vector_monogram_data_uri(
    glyph: str, rgba: tuple[int, int, int, int], ordinal: int = 0
) -> str:
    """Rasterize one retained wireframe monogram from vector segments.

    This deliberately follows the Settings retained-vector-icon approach:
    QPainter owns a small antialiased wireframe once, and QML receives only an
    immutable in-memory image URI.  The monogram does not depend on emoji or a
    runtime font glyph, and it creates no Canvas repaint, timer or file cache.
    """

    label = str(glyph or "F")[:1].upper() or "F"
    # 14-segment-ish alphabet. Coordinates live inside the rounded wireframe
    # and are intentionally simple/legible at the 25 px BrandedHeader size.
    points = {
        "a1": ((0.29, 0.20), (0.49, 0.20)),
        "a2": ((0.51, 0.20), (0.71, 0.20)),
        "b": ((0.74, 0.23), (0.74, 0.47)),
        "c": ((0.74, 0.53), (0.74, 0.77)),
        "d1": ((0.29, 0.80), (0.49, 0.80)),
        "d2": ((0.51, 0.80), (0.71, 0.80)),
        "e": ((0.26, 0.53), (0.26, 0.77)),
        "f": ((0.26, 0.23), (0.26, 0.47)),
        "g1": ((0.29, 0.50), (0.49, 0.50)),
        "g2": ((0.51, 0.50), (0.71, 0.50)),
        "h": ((0.29, 0.22), (0.48, 0.47)),
        "i": ((0.71, 0.22), (0.52, 0.47)),
        "j": ((0.29, 0.78), (0.48, 0.53)),
        "k": ((0.71, 0.78), (0.52, 0.53)),
        "l": ((0.50, 0.23), (0.50, 0.47)),
        "m": ((0.50, 0.53), (0.50, 0.77)),
    }
    glyph_segments = {
        "0": "a1 a2 b c d1 d2 e f",
        "1": "b c",
        "2": "a1 a2 b g1 g2 e d1 d2",
        "3": "a1 a2 b c g1 g2 d1 d2",
        "4": "f g1 g2 b c",
        "5": "a1 a2 f g1 g2 c d1 d2",
        "6": "a1 a2 f e g1 g2 c d1 d2",
        "7": "a1 a2 b c",
        "8": "a1 a2 b c d1 d2 e f g1 g2",
        "9": "a1 a2 b c d1 d2 f g1 g2",
        "A": "a1 a2 b c e f g1 g2",
        "B": "a1 a2 b c d1 d2 e f g1 g2",
        "C": "a1 a2 d1 d2 e f",
        "D": "b c d1 d2 e g1 g2 l m",
        "E": "a1 a2 d1 d2 e f g1 g2",
        "F": "a1 a2 e f g1 g2",
        "G": "a1 a2 c d1 d2 e f g2",
        "H": "b c e f g1 g2",
        "I": "a1 a2 d1 d2 l m",
        "J": "b c d1 d2 e",
        "K": "e f h j i k",
        "L": "d1 d2 e f",
        "M": "b c e f h i",
        "N": "b c e f h k",
        "O": "a1 a2 b c d1 d2 e f",
        "P": "a1 a2 b e f g1 g2",
        "Q": "a1 a2 b c d1 d2 e f k",
        "R": "a1 a2 b e f g1 g2 k",
        "S": "a1 a2 c d1 d2 f g1 g2",
        "T": "a1 a2 l m",
        "U": "b c d1 d2 e f",
        "V": "e f j k",
        "W": "b c e f j k",
        "X": "h i j k",
        "Y": "h i m",
        "Z": "a1 a2 i j d1 d2",
    }
    segments = glyph_segments.get(label, glyph_segments["F"]).split()

    color = QColor(*rgba)
    image = QImage(96, 96, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    frame_pen = QPen(color)
    frame_pen.setWidthF(4.0)
    frame_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    frame_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(frame_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(QRectF(6.0, 6.0, 84.0, 84.0), 14.0, 14.0)

    # Same-initial CUSTOM slots carry a small ordinal in the lower-right
    # corner; the letter shrinks toward the upper-left to make room. The
    # ordinal uses the same segment alphabet, so there is no second renderer.
    ordinal_label = str(int(ordinal)) if 1 <= int(ordinal) <= 9 else ""

    def draw(segment_names, *, width, origin, scale):
        pen = QPen(color)
        pen.setWidthF(width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        ox, oy = origin
        sx, sy = scale
        for segment in segment_names:
            (x1, y1), (x2, y2) = points[segment]
            painter.drawLine(
                QPointF((ox + (x1 - 0.26) * sx) * 96.0, (oy + (y1 - 0.20) * sy) * 96.0),
                QPointF((ox + (x2 - 0.26) * sx) * 96.0, (oy + (y2 - 0.20) * sy) * 96.0),
            )

    if ordinal_label:
        draw(segments, width=6.0, origin=(0.24, 0.18), scale=(0.80, 0.80))
        draw(glyph_segments[ordinal_label].split(), width=4.5,
             origin=(0.63, 0.58), scale=(0.36, 0.40))
    else:
        draw(segments, width=7.0, origin=(0.26, 0.20), scale=(1.0, 1.0))
    painter.end()

    buffer = QBuffer()
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        return ""
    if not image.save(buffer, "PNG"):
        return ""
    payload = base64.b64encode(bytes(buffer.data())).decode("ascii")
    return f"data:image/png;base64,{payload}"


def _browser_action_url(value: object) -> str:
    target = str(value or "").strip()
    try:
        scheme = urlsplit(target).scheme.casefold()
    except ValueError:
        return ""
    return target if scheme in {"http", "https"} else ""


def _age_label(timestamp: int | None, now_ts: float | None = None) -> str:
    if not timestamp:
        return ""
    now = time.time() if now_ts is None else float(now_ts)
    delta = max(0, int(now - int(timestamp)))
    if delta < 3600:
        return f"{max(1, delta // 60)}M AGO"
    if delta < 86400:
        return f"{delta // 3600}HR AGO"
    if delta < 7 * 86400:
        return f"{delta // 86400}D AGO"
    return f"{delta // (7 * 86400)}W AGO"


@dataclass(frozen=True)
class FeedPresentationConfig:
    custom: CustomFeedConfig
    font_family: str
    font_size: int
    text_color: tuple[int, int, int, int]
    show_background: bool
    background_color: tuple[int, int, int, int]
    background_opacity: float
    border_color: tuple[int, int, int, int]
    border_opacity: float
    header_fill_color: tuple[int, int, int, int]
    header_border_color: tuple[int, int, int, int]
    header_text_color: tuple[int, int, int, int]
    preferred_width: int
    preferred_height: int
    # 1-based rank among enabled, configured CUSTOM slots that share this
    # slot's monogram initial (slot order); 0 when the initial is unique.
    monogram_ordinal: int

    @classmethod
    def from_widgets_mapping(
        cls,
        widgets: Mapping[str, object],
        *,
        widget_id: str,
    ) -> "FeedPresentationConfig":
        canonical = require_canonical_default(f"widgets.{widget_id}")
        if not isinstance(canonical, Mapping):
            raise TypeError(f"Canonical widgets.{widget_id} defaults must be a mapping")
        values = widgets.get(widget_id, {}) if isinstance(widgets, Mapping) else {}
        if not isinstance(values, Mapping):
            values = {}
        custom = CustomFeedConfig.from_mapping(widget_id, values)
        text = resolve_primary_text_color(
            values=values,
            defaults=canonical,
            text_color=_rgba(canonical["color"], (255, 255, 255, 230)),
        )
        background, border = resolve_card_surface_colors(
            values=values,
            defaults=canonical,
            background_color=_rgba(canonical["bg_color"], (35, 35, 35, 255)),
            background_opacity=float(canonical["bg_opacity"]),
            border_color=_rgba(canonical["border_color"], (255, 255, 255, 255)),
            border_opacity=float(canonical["border_opacity"]),
        )
        header_fill, header_border, header_text = resolve_header_colors(
            widget_id,
            values=values,
            defaults=canonical,
            fill=background,
            border=border,
            text=text,
        )
        return cls(
            custom=custom,
            font_family=str(values.get("font_family") or canonical["font_family"]),
            font_size=_bounded_int(values.get("font_size"), int(canonical["font_size"]), 8, 48),
            text_color=text,
            show_background=_coerce_bool(
                values.get("show_background", canonical["show_background"]),
                bool(canonical["show_background"]),
            ),
            background_color=background,
            background_opacity=1.0,
            border_color=border,
            border_opacity=1.0,
            header_fill_color=header_fill,
            header_border_color=header_border,
            header_text_color=header_text,
            preferred_width=_bounded_int(values.get("preferred_width"), int(canonical["preferred_width"]), 320, 1600),
            preferred_height=_bounded_int(values.get("preferred_height"), int(canonical["preferred_height"]), 180, 1800),
            monogram_ordinal=_monogram_ordinal(widgets, widget_id),
        )


def feed_monogram_initial(name: str) -> str:
    """The configured name's first letter or digit, uppercased; ``F`` if none."""

    for ch in str(name or "").strip():
        if ch.isalnum():
            return ch.upper()
    return "F"


def _monogram_ordinal(widgets: Mapping[str, object], widget_id: str) -> int:
    """Deterministic collision ordinal across the live CUSTOM slots.

    Only enabled, configured slots present cards, so only they can collide.
    """
    from core.feeds.config import CUSTOM_FEED_WIDGET_IDS

    live: list[tuple[str, str]] = []
    for slot_id in CUSTOM_FEED_WIDGET_IDS:
        raw = widgets.get(slot_id, {}) if isinstance(widgets, Mapping) else {}
        config = CustomFeedConfig.from_mapping(slot_id, raw if isinstance(raw, Mapping) else {})
        if slot_id == widget_id or (config.enabled and config.configured):
            live.append((slot_id, feed_monogram_initial(config.name)))
    initial = next((value for slot_id, value in live if slot_id == widget_id), None)
    sharing = [slot_id for slot_id, value in live if value == initial]
    if len(sharing) < 2:
        return 0
    return sharing.index(widget_id) + 1


@dataclass(frozen=True)
class FeedPresentationStyle:
    card_style: OverlayCardStyle
    text_shadow_enabled: bool
    text_shadow_color: QColor
    text_shadow_offset_x: float
    text_shadow_offset_y: float

    @classmethod
    def project(
        cls,
        config: FeedPresentationConfig,
        shadow_values: Mapping[str, object],
        *,
        border_width: float = 4.0,
    ) -> "FeedPresentationStyle":
        shadow = QuickShadowSnapshot.from_mapping(shadow_values)
        card_offset = resolve_signed_offset(shadow.direction, *ORDINARY_CARD_SHADOW_BASE)
        card_extensions = resolve_directional_extensions(shadow.direction, shadow.frame_extra_offset)
        text_offset = resolve_signed_offset(
            shadow.direction,
            ORDINARY_TEXT_SHADOW_BASE[0] + shadow.text_extra_offset,
            ORDINARY_TEXT_SHADOW_BASE[1] + shadow.text_extra_offset,
        )
        return cls(
            card_style=OverlayCardStyle(
                shell_enabled=config.show_background,
                background_color=_with_alpha(config.background_color, config.background_opacity),
                border_color=_with_alpha(config.border_color, config.border_opacity),
                border_width=max(0.0, float(border_width)),
                corner_radius=8.0,
                padding=14.0,
                shadow_enabled=config.show_background and shadow.enabled,
                shadow_color=_with_alpha(shadow.color, shadow.frame_opacity),
                shadow_blur=min(80.0, shadow.blur_radius),
                shadow_offset_x=card_offset[0],
                shadow_offset_y=card_offset[1],
                shadow_extend_left=card_extensions[0],
                shadow_extend_top=card_extensions[1],
                shadow_extend_right=card_extensions[2],
                shadow_extend_bottom=card_extensions[3],
            ),
            text_shadow_enabled=shadow.text_enabled,
            text_shadow_color=_with_alpha(shadow.color, shadow.text_opacity),
            text_shadow_offset_x=text_offset[0],
            text_shadow_offset_y=text_offset[1],
        )


class FeedRowsModel(QAbstractListModel):
    IdentityRole = int(Qt.ItemDataRole.UserRole) + 1
    TitleRole = IdentityRole + 1
    SummaryRole = IdentityRole + 2
    AuthorRole = IdentityRole + 3
    AgeRole = IdentityRole + 4
    UrlRole = IdentityRole + 5
    ImageRole = IdentityRole + 6

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: tuple[FeedDisplayRow, ...] = ()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)) -> object:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        return {
            self.IdentityRole: row.item_id,
            self.TitleRole: row.title,
            self.SummaryRole: row.summary,
            self.AuthorRole: row.author,
            self.AgeRole: _age_label(row.published_at),
            self.UrlRole: _browser_action_url(row.action_url),
            self.ImageRole: row.image_source,
            int(Qt.ItemDataRole.DisplayRole): row.title,
        }.get(int(role))

    def roleNames(self) -> dict[int, bytes]:  # noqa: N802
        return {
            self.IdentityRole: b"feedItemId",
            self.TitleRole: b"feedTitle",
            self.SummaryRole: b"feedSummary",
            self.AuthorRole: b"feedAuthor",
            self.AgeRole: b"feedAge",
            self.UrlRole: b"feedUrl",
            self.ImageRole: b"feedImageSource",
        }

    @property
    def rows(self) -> tuple[FeedDisplayRow, ...]:
        return self._rows

    def replace_rows(self, rows: Iterable[FeedDisplayRow]) -> bool:
        resolved = tuple(rows)
        if resolved == self._rows:
            return False
        self.beginResetModel()
        self._rows = resolved
        self.endResetModel()
        return True


_CHILD_ROLE_MAP = child_role_map(FEED_CUSTOM_CHILD_ROLES)


class FeedPresentationModel(QObject):
    stateChanged = Signal()
    contentExtentChanged = Signal()
    customGeometryChanged = Signal()

    def __init__(
        self,
        config: FeedPresentationConfig,
        style: FeedPresentationStyle,
        *,
        runtime_generation: object | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.style = style
        self._runtime_generation = runtime_generation
        self._runtime_service: object | None = None
        self._rows = FeedRowsModel(self)
        self._display: FeedDisplay | None = None
        self._snapshot = None
        self._local_artwork_by_item: dict[str, str] = {}
        self._content_extent: tuple[float, float] | None = None
        self._custom: dict[str, CustomChildSize] = {}
        self._view_state = "loading" if config.custom.configured else "missing"
        self._status_text = ""
        self._refreshing = False
        self._interaction_enabled = False
        self._active = False
        self._retired = False

    def set_runtime_service(self, service: object) -> None:
        if self._retired or self._runtime_service is not None:
            raise RuntimeError("Feed runtime service may be injected only once")
        attach = getattr(service, "attach_consumer", None)
        if not callable(attach):
            raise AttributeError("Feed runtime service is not attachable")
        self._runtime_service = service
        attach(self)

    def activate(self, thread_manager: object) -> None:
        if self._retired or self._active or self._runtime_service is None:
            return
        if not self.config.custom.configured:
            self._view_state = "missing"
            self.stateChanged.emit()
            return
        setter = getattr(self._runtime_service, "set_thread_manager", None)
        if callable(setter):
            setter(thread_manager, generation=self._runtime_generation)
        self._active = True
        if not bool(self._runtime_service.start()):
            self._active = False
            self._view_state = "error"
            self._status_text = "FEED UNAVAILABLE"
            self.stateChanged.emit()

    def retire(self) -> None:
        if self._retired:
            return
        self._retired = True
        self._active = False
        service = self._runtime_service
        if service is not None:
            stop = getattr(service, "stop", None)
            detach = getattr(service, "detach_consumer", None)
            if callable(stop):
                stop()
            if callable(detach):
                detach(self)
        self._rows.replace_rows(())
        self._snapshot = None
        self._local_artwork_by_item.clear()

    def is_feed_consumer_alive(self) -> bool:
        return self._active and not self._retired

    def on_feed_runtime_result(self, result: FeedRefreshResult, *, from_cache: bool) -> None:
        if not self.is_feed_consumer_alive():
            return
        snapshot = result.snapshot
        if snapshot is not None:
            old_view_state = self._view_state
            old_status_text = self._status_text
            old_refreshing = self._refreshing
            self._snapshot = snapshot
            self._local_artwork_by_item = dict(result.local_artwork_by_item)
            display = self._project_accepted_snapshot()
            display_changed = display != self._display
            self._display = display
            rows_changed = self._rows.replace_rows(display.rows)
            self._view_state = "ready" if display.rows else "empty"
            stale = result.status in {"stale_cache", "backoff_cache"}
            if stale:
                self._status_text = "CACHED · SOURCE TEMPORARILY UNAVAILABLE"
            elif from_cache:
                self._status_text = "CACHED"
            else:
                self._status_text = ""
            self._refreshing = False
            if (
                display_changed
                or rows_changed
                or old_view_state != self._view_state
                or old_status_text != self._status_text
                or old_refreshing != self._refreshing
            ):
                self.stateChanged.emit()
            return
        self._refreshing = False
        self._view_state = "error"
        self._status_text = "FEED UNAVAILABLE"
        self.stateChanged.emit()

    def _project_accepted_snapshot(self) -> FeedDisplay:
        return project_feed(
            self._snapshot,
            view_mode=self.config.custom.view_mode,
            item_limit=self.config.custom.item_limit,
            show_images=self.config.custom.show_images,
            local_artwork_by_item=self._local_artwork_by_item,
        )

    def request_refresh(self) -> bool:
        if not self._active or self._runtime_service is None:
            return False
        self._refreshing = True
        self.stateChanged.emit()
        admitted = bool(self._runtime_service.request_refresh())
        if not admitted and self._refreshing:
            self._refreshing = False
            self.stateChanged.emit()
        return admitted

    def set_interaction_enabled(self, enabled: bool) -> bool:
        normalized = bool(enabled)
        if normalized == self._interaction_enabled:
            return False
        self._interaction_enabled = normalized
        self.stateChanged.emit()
        return True

    def admit_url(self, url: object) -> bool:
        if not self._active or not self._interaction_enabled:
            return False
        target = _browser_action_url(url)
        if not target:
            return False
        if self._display is not None and target == _browser_action_url(self._display.home_url):
            return True
        return any(
            _browser_action_url(row.action_url) == target
            for row in self._rows.rows
            if _browser_action_url(row.action_url)
        )


    def set_content_extent(self, width: object, height: object) -> bool:
        """Project CUSTOM x/y extent onto the retained layout, never source work."""
        if self._retired:
            return False
        if width is None or height is None:
            extent = None
        else:
            try:
                w, h = float(width), float(height)
            except (TypeError, ValueError):
                return False
            if not (w == w and h == h):
                return False
            min_w, min_h = FEED_CONTENT_EXTENT_MINIMUM
            extent = (max(min_w, min(1600.0, w)), max(min_h, min(1800.0, h)))
        if extent == self._content_extent:
            return False
        self._content_extent = extent
        self.contentExtentChanged.emit()
        return True

    def set_custom_child_geometry(self, values: object) -> bool:
        """Project only validated shared CUSTOM payloads; never rebuild rows or source."""
        if self._retired:
            return False
        raw = values if isinstance(values, Mapping) else {}
        next_geometry: dict[str, CustomChildSize] = {}
        for name, descriptor in _CHILD_ROLE_MAP.items():
            value = raw.get(name)
            if not isinstance(value, Mapping):
                continue
            size = clamp_child_geometry(
                descriptor, value.get("width_scale", 1.0),
                value.get("height_scale", 1.0), value.get("x_offset", 0.0),
                value.get("y_offset", 0.0), value.get("alignment"), value.get("anchor"),
            )
            if not size.is_authored:
                next_geometry[name] = size
        if next_geometry == self._custom:
            return False
        self._custom = next_geometry
        self.customGeometryChanged.emit()
        return True

    def apply_custom_layout_size_payload(self, payload: Mapping[str, object]) -> None:
        extent = payload.get("content_extent") if isinstance(payload, Mapping) else None
        if isinstance(extent, (tuple, list)) and len(extent) == 2:
            self.set_content_extent(extent[0], extent[1])
        else:
            self.set_content_extent(None, None)
        self.set_custom_child_geometry(payload.get("child_geometry") if isinstance(payload, Mapping) else None)

    @Property("QVariantMap", notify=customGeometryChanged)
    def customChildGeometry(self) -> dict[str, dict[str, object]]:
        return {name: size.to_mapping() for name, size in self._custom.items()}

    @Property(float, constant=True)
    def basePreferredWidth(self) -> float:
        return float(self.config.preferred_width)

    @Property(float, constant=True)
    def basePreferredHeight(self) -> float:
        return float(self.config.preferred_height)

    @Property(QObject, constant=True)
    def rowModel(self) -> QObject:
        return self._rows

    @Property(int, notify=stateChanged)
    def rowCount(self) -> int:
        return self._rows.rowCount()

    @Property(int, notify=stateChanged)
    def firstArtworkRowIndex(self) -> int:
        """First retained row with admitted local artwork, or -1.

        CUSTOM uses this only to place one stable representative artwork edit
        target over real paint.  It never changes row identity or acquisition.
        """
        for index, row in enumerate(self._rows.rows):
            if row.image_source:
                return index
        return -1

    @Property(str, notify=stateChanged)
    def displayName(self) -> str:
        return self.config.custom.name

    @Property(str, notify=stateChanged)
    def monogram(self) -> str:
        return feed_monogram_initial(self.config.custom.name)

    @Property(str, notify=stateChanged)
    def monogramSource(self) -> str:
        return _vector_monogram_data_uri(
            self.monogram, self.config.header_text_color, self.config.monogram_ordinal
        )

    @Property(str, notify=stateChanged)
    def feedTitle(self) -> str:
        return self._display.title if self._display is not None else ""

    @Property(str, notify=stateChanged)
    def homeUrl(self) -> str:
        return _browser_action_url(
            self._display.home_url if self._display is not None else ""
        )

    @Property(str, notify=stateChanged)
    def viewMode(self) -> str:
        return self.config.custom.view_mode

    @Property(bool, notify=stateChanged)
    def showImages(self) -> bool:
        return bool(self.config.custom.show_images)

    @Property(bool, constant=True)
    def showSubtitle(self) -> bool:
        return bool(self.config.custom.show_subtitle)

    @Property(str, notify=stateChanged)
    def viewState(self) -> str:
        return self._view_state

    @Property(str, notify=stateChanged)
    def statusText(self) -> str:
        return self._status_text

    @Property(bool, notify=stateChanged)
    def refreshing(self) -> bool:
        return self._refreshing

    @Property(bool, notify=stateChanged)
    def interactionEnabled(self) -> bool:
        return self._interaction_enabled

    @Property(str, constant=True)
    def fontFamily(self) -> str:
        return self.config.font_family

    @Property(float, constant=True)
    def fontSize(self) -> float:
        return float(self.config.font_size)

    @Property(QColor, constant=True)
    def textColor(self) -> QColor:
        return _qcolor(self.config.text_color)

    @Property(QColor, constant=True)
    def headerFillColor(self) -> QColor:
        return _qcolor(self.config.header_fill_color)

    @Property(QColor, constant=True)
    def headerBorderColor(self) -> QColor:
        return _qcolor(self.config.header_border_color)

    @Property(QColor, constant=True)
    def headerTextColor(self) -> QColor:
        return _qcolor(self.config.header_text_color)

    @Property(float, constant=True)
    def headerBorderWidth(self) -> float:
        return max(1.0, self.style.card_style.border_width - 3.0)

    @Property(bool, constant=True)
    def textShadowEnabled(self) -> bool:
        return self.style.text_shadow_enabled

    @Property(QColor, constant=True)
    def textShadowColor(self) -> QColor:
        return self.style.text_shadow_color

    @Property(float, constant=True)
    def textShadowOffsetX(self) -> float:
        return self.style.text_shadow_offset_x

    @Property(float, constant=True)
    def textShadowOffsetY(self) -> float:
        return self.style.text_shadow_offset_y

    @Property(float, notify=contentExtentChanged)
    def preferredWidth(self) -> float:
        return float(self._content_extent[0] if self._content_extent is not None else self.config.preferred_width)

    @Property(float, notify=contentExtentChanged)
    def preferredHeight(self) -> float:
        return float(self._content_extent[1] if self._content_extent is not None else self.config.preferred_height)

    @Property(float, notify=contentExtentChanged)
    def contentExtentWidth(self) -> float:
        return float(self._content_extent[0]) if self._content_extent is not None else 0.0

    @Property(float, notify=contentExtentChanged)
    def contentExtentHeight(self) -> float:
        return float(self._content_extent[1]) if self._content_extent is not None else 0.0


class RetainedFeedPresentation:
    def __init__(
        self,
        *,
        host: OrdinaryWidgetPresentationHost,
        model: FeedPresentationModel,
        geometry: OverlayWidgetGeometry,
        on_open_requested: Callable[[str], Any] | None = None,
    ) -> None:
        self._model = model
        self._on_open_requested = on_open_requested
        self._retained: RetainedOverlayWidget = host.create_family_widget(
            "feeds",
            initial_properties={"feedModel": model},
            object_name=model.config.custom.widget_id,
            model_identity=model.config.custom.widget_id,
            geometry=geometry,
            card_style=model.style.card_style,
        )
        self._retained.add_retirement_callback(model.retire)
        self._retained.set_custom_layout_size_payload_handler(model.apply_custom_layout_size_payload)
        host.set_widget_input_state_handler(self._retained, self.apply_input_state)
        open_signal = getattr(self._retained.item, "openItemRequested", None)
        if open_signal is not None and hasattr(open_signal, "connect"):
            open_signal.connect(self._handle_open_requested)
        refresh_signal = getattr(self._retained.item, "refreshRequested", None)
        if refresh_signal is not None and hasattr(refresh_signal, "connect"):
            refresh_signal.connect(self._handle_refresh_requested)

    @property
    def item(self):
        return self._retained.item

    @property
    def model(self) -> FeedPresentationModel:
        return self._model

    def activate(self, thread_manager: object | None = None) -> None:
        if thread_manager is not None:
            self._model.activate(thread_manager)

    def set_geometry(self, geometry: OverlayWidgetGeometry) -> None:
        self._retained.set_geometry(geometry)

    def set_fade_opacity(self, opacity: float) -> None:
        self._retained.set_fade_opacity(opacity)

    def apply_input_state(self, input_state: object) -> bool:
        if isinstance(input_state, Mapping):
            value = input_state.get
        else:
            def value(name, default):
                return getattr(input_state, name, default)
        enabled = (
            bool(value("admission_open", True))
            and not bool(value("exiting", False))
            and (
                bool(value("interaction_mode_enabled", False))
                or bool(value("ctrl_held", False))
            )
        )
        return self._model.set_interaction_enabled(enabled)

    def _handle_open_requested(self, url: str) -> bool:
        if not self._model.admit_url(url) or self._on_open_requested is None:
            return False
        return bool(self._on_open_requested(str(url)))

    def _handle_refresh_requested(self) -> bool:
        if not self._model.interactionEnabled:
            return False
        return self._model.request_refresh()

    def retire(self) -> bool:
        return self._retained.retire()


__all__ = [
    "FeedPresentationConfig",
    "FeedPresentationModel",
    "FeedPresentationStyle",
    "FeedRowsModel",
    "RetainedFeedPresentation",
]
