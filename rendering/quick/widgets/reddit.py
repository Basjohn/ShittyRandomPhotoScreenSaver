"""Stable retained Reddit family presentation state.

Provider selection, fetching, cache persistence, cadence and rate limiting stay
Python-owned.  This module owns only the retained Reddit/Reddit2 view model and
semantic presentation actions.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
import re
import time
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QObject,
    Property,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor

from core.reddit_preparation import RedditPost, candidate_identity
from core.settings.shadow_direction import (
    resolve_directional_extensions,
    resolve_signed_offset,
)

from .host import (
    ORDINARY_CARD_SHADOW_BASE,
    ORDINARY_TEXT_SHADOW_BASE,
    OrdinaryWidgetPresentationHost,
    OverlayCardStyle,
    OverlayWidgetGeometry,
    RetainedOverlayWidget,
)


_REDDIT_LOGO = Path(__file__).resolve().parents[3] / "images" / "Reddit_Logo_C.png"
_STYLE_KEYS = frozenset(
    {
        "font_family",
        "font_size",
        "color",
        "show_background",
        "show_separators",
        "show_refresh_spiral",
        "margin",
        "header_logo_px_adjust",
        "bg_color",
        "background_color",
        "bg_opacity",
        "background_opacity",
        "border_color",
        "border_opacity",
    }
)


def _bounded_float(value: object, default: float, low: float, high: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(default)
    return max(low, min(high, parsed))


def _bounded_int(value: object, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(low, min(high, parsed))


def _as_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    if value is None:
        return default
    return bool(value)


def _rgba(value: object, default: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    if isinstance(value, QColor):
        color = QColor(value)
    elif isinstance(value, (tuple, list)) and len(value) in {3, 4}:
        channels = list(value)
        if len(channels) == 3:
            channels.append(255)
        try:
            color = QColor(*(max(0, min(255, int(channel))) for channel in channels))
        except (TypeError, ValueError):
            color = QColor(*default)
    else:
        color = QColor(str(value)) if value is not None else QColor()
    if not color.isValid():
        color = QColor(*default)
    return color.red(), color.green(), color.blue(), color.alpha()


def _with_alpha(rgba: tuple[int, int, int, int], scale: float) -> QColor:
    color = QColor(*rgba)
    color.setAlpha(max(0, min(255, int(round(color.alpha() * float(scale))))))
    return color


def _subreddit_slug(value: object) -> str:
    slug = str(value or "").strip().replace("\\", "/")
    lowered = slug.lower()
    if "/r/" in lowered:
        slug = slug[lowered.index("/r/") + 3 :].split("/", 1)[0]
    elif lowered.startswith("r/"):
        slug = slug[2:]
    return slug.strip("/ ")


def _display_title(value: object) -> str:
    text = str(value or "").strip()
    for separator in (" - ", " – "):
        index = text.find(separator)
        if index > 0:
            text = text[:index].rstrip()
            break
    result: list[str] = []
    for word in text.split():
        match = re.match(r"^([^\w]*)(.*?)([^\w]*)$", word)
        if match is None:
            result.append(word)
            continue
        leading, core, trailing = match.groups()
        if len(core) >= 2 and core.isupper() and core.isalpha():
            resolved = core
        elif core.casefold() == "i":
            resolved = "I"
        else:
            resolved = core[:1].upper() + core[1:]
        result.append(f"{leading}{resolved}{trailing}")
    return " ".join(result)


def _age_label(created_utc: float, now_ts: float) -> str:
    delta = max(0.0, float(now_ts) - float(created_utc or 0.0))
    minutes = max(1, int(delta // 60))
    hours = int(delta // 3600)
    days = int(delta // 86400)
    if hours < 1:
        return f"{minutes}M AGO"
    if days < 1:
        return f"{hours:02d}HR AGO"
    if days < 7:
        return f"{days:02d}D AGO"
    weeks = days // 7
    if weeks < 52:
        return f"{weeks}W AGO"
    return f"{days // 365}Y AGO"


@dataclass(frozen=True)
class RedditPresentationConfig:
    widget_id: str = "reddit"
    subreddit: str = "technology"
    limit: int = 10
    font_family: str = "Inter"
    font_size: int = 18
    text_color: tuple[int, int, int, int] = (255, 255, 255, 230)
    show_background: bool = True
    background_color: tuple[int, int, int, int] = (35, 35, 35, 255)
    background_opacity: float = 0.6
    border_color: tuple[int, int, int, int] = (255, 255, 255, 255)
    border_opacity: float = 1.0
    show_separators: bool = True
    show_refresh_spiral: bool = True
    header_logo_px_adjust: int = 0

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, object],
        *,
        widget_id: str = "reddit",
    ) -> "RedditPresentationConfig":
        return cls(
            widget_id=str(widget_id or "reddit"),
            subreddit=_subreddit_slug(values.get("subreddit", "technology")),
            limit=_bounded_int(values.get("limit"), 10, 1, 25),
            font_family=str(values.get("font_family", "Inter") or "Inter"),
            font_size=_bounded_int(values.get("font_size"), 18, 8, 96),
            text_color=_rgba(values.get("color"), (255, 255, 255, 230)),
            show_background=_as_bool(values.get("show_background"), True),
            background_color=_rgba(
                values.get("bg_color", values.get("background_color")),
                (35, 35, 35, 255),
            ),
            background_opacity=_bounded_float(
                values.get("bg_opacity", values.get("background_opacity")),
                0.6,
                0.0,
                1.0,
            ),
            border_color=_rgba(
                values.get("border_color"), (255, 255, 255, 255)
            ),
            border_opacity=_bounded_float(
                values.get("border_opacity"), 1.0, 0.0, 1.0
            ),
            show_separators=_as_bool(values.get("show_separators"), True),
            show_refresh_spiral=_as_bool(
                values.get("show_refresh_spiral"), True
            ),
            header_logo_px_adjust=_bounded_int(
                values.get("header_logo_px_adjust"), 0, -128, 128
            ),
        )

    @classmethod
    def from_widgets_mapping(
        cls,
        widgets: Mapping[str, object],
        *,
        widget_id: str = "reddit",
    ) -> "RedditPresentationConfig":
        """Project canonical member settings with Reddit2 style inheritance."""

        from core.settings.defaults import get_default_settings

        defaults = get_default_settings().get("widgets", {})
        default_member = defaults.get(widget_id, {}) if isinstance(defaults, Mapping) else {}
        member = widgets.get(widget_id, {}) if isinstance(widgets, Mapping) else {}
        if not isinstance(default_member, Mapping):
            default_member = {}
        if not isinstance(member, Mapping):
            member = {}
        merged = dict(default_member)
        merged.update(member)
        if widget_id == "reddit2":
            base_default = defaults.get("reddit", {}) if isinstance(defaults, Mapping) else {}
            base_member = widgets.get("reddit", {}) if isinstance(widgets, Mapping) else {}
            base = dict(base_default) if isinstance(base_default, Mapping) else {}
            if isinstance(base_member, Mapping):
                base.update(base_member)
            for key in _STYLE_KEYS:
                if key not in member and key in base:
                    merged[key] = base[key]
        return cls.from_mapping(merged, widget_id=widget_id)


@dataclass(frozen=True)
class RedditPresentationStyle:
    card_style: OverlayCardStyle
    text_shadow_enabled: bool
    text_shadow_color: QColor
    text_shadow_offset_x: float
    text_shadow_offset_y: float

    @classmethod
    def project(
        cls,
        config: RedditPresentationConfig,
        shadow_values: Mapping[str, object],
        *,
        border_width: float = 4.0,
    ) -> "RedditPresentationStyle":
        direction = shadow_values.get("direction", "SE")
        frame_extra = _bounded_float(
            shadow_values.get("frame_extra_offset"), 0.0, 0.0, 40.0
        )
        text_extra = _bounded_float(
            shadow_values.get("text_extra_offset"), 0.0, 0.0, 40.0
        )
        card_offset = resolve_signed_offset(direction, *ORDINARY_CARD_SHADOW_BASE)
        card_extensions = resolve_directional_extensions(direction, frame_extra)
        text_offset = resolve_signed_offset(
            direction,
            ORDINARY_TEXT_SHADOW_BASE[0] + text_extra,
            ORDINARY_TEXT_SHADOW_BASE[1] + text_extra,
        )
        shadow_rgba = _rgba(shadow_values.get("color"), (0, 0, 0, 255))
        return cls(
            card_style=OverlayCardStyle(
                shell_enabled=config.show_background,
                background_color=_with_alpha(
                    config.background_color, config.background_opacity
                ),
                border_color=_with_alpha(config.border_color, config.border_opacity),
                border_width=max(0.0, float(border_width)),
                corner_radius=8.0,
                padding=14.0,
                shadow_enabled=(
                    config.show_background
                    and _as_bool(shadow_values.get("enabled"), True)
                ),
                shadow_color=_with_alpha(
                    shadow_rgba,
                    _bounded_float(
                        shadow_values.get("frame_opacity"), 0.77, 0.0, 1.0
                    ),
                ),
                shadow_blur=_bounded_float(
                    shadow_values.get("blur_radius"), 18.0, 0.0, 80.0
                ),
                shadow_offset_x=card_offset[0],
                shadow_offset_y=card_offset[1],
                shadow_extend_left=card_extensions[0],
                shadow_extend_top=card_extensions[1],
                shadow_extend_right=card_extensions[2],
                shadow_extend_bottom=card_extensions[3],
            ),
            text_shadow_enabled=_as_bool(
                shadow_values.get("text_enabled"), True
            ),
            text_shadow_color=_with_alpha(
                shadow_rgba,
                _bounded_float(
                    shadow_values.get("text_opacity"), 0.33, 0.0, 1.0
                ),
            ),
            text_shadow_offset_x=text_offset[0],
            text_shadow_offset_y=text_offset[1],
        )


@dataclass(frozen=True)
class RedditPresentationRow:
    identity: str
    title: str
    age: str
    url: str


class RedditRowListModel(QAbstractListModel):
    """One stable list-model object; feed commits mutate rows in place."""

    IdentityRole = int(Qt.ItemDataRole.UserRole) + 1
    TitleRole = IdentityRole + 1
    AgeRole = IdentityRole + 2
    UrlRole = IdentityRole + 3

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: tuple[RedditPresentationRow, ...] = ()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        return {
            self.IdentityRole: row.identity,
            self.TitleRole: row.title,
            self.AgeRole: row.age,
            self.UrlRole: row.url,
            int(Qt.ItemDataRole.DisplayRole): row.title,
        }.get(int(role))

    def roleNames(self) -> dict[int, bytes]:  # noqa: N802
        return {
            self.IdentityRole: b"postIdentity",
            self.TitleRole: b"postTitle",
            self.AgeRole: b"postAge",
            self.UrlRole: b"postUrl",
        }

    @property
    def rows(self) -> tuple[RedditPresentationRow, ...]:
        return self._rows

    def replace_rows(self, rows: Iterable[RedditPresentationRow]) -> bool:
        resolved = tuple(rows)
        if resolved == self._rows:
            return False
        old_count = len(self._rows)
        new_count = len(resolved)
        common = min(old_count, new_count)
        previous = self._rows
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
            changed_indexes: list[int] = []
            for index in range(common):
                if mutable[index] != resolved[index]:
                    mutable[index] = resolved[index]
                    changed_indexes.append(index)
            self._rows = tuple(mutable)
            if changed_indexes:
                self.dataChanged.emit(
                    self.index(min(changed_indexes), 0),
                    self.index(max(changed_indexes), 0),
                    [
                        self.IdentityRole,
                        self.TitleRole,
                        self.AgeRole,
                        self.UrlRole,
                    ],
                )
        if new_count > common:
            self._rows = resolved
        return True


@dataclass(frozen=True)
class RedditPresentationSnapshot:
    config: RedditPresentationConfig
    style: RedditPresentationStyle
    view_state: str = "loading"
    error_text: str = ""
    from_cache: bool = False
    refreshing: bool = False
    interaction_enabled: bool = False


class RedditPresentationModel(QObject):
    """Stable coherent state for one Reddit or Reddit2 retained card."""

    stateChanged = Signal()

    def __init__(
        self,
        config: RedditPresentationConfig,
        style: RedditPresentationStyle,
        runtime_service: Any | None = None,
        *,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._row_model = RedditRowListModel(self)
        self._runtime_service = runtime_service
        self._snapshot = RedditPresentationSnapshot(
            config=config,
            style=style,
            view_state="loading" if config.subreddit else "missing",
        )
        self._active = False
        self._retired = False

    @property
    def config(self) -> RedditPresentationConfig:
        return self._snapshot.config

    @property
    def style(self) -> RedditPresentationStyle:
        return self._snapshot.style

    @property
    def row_model(self) -> RedditRowListModel:
        return self._row_model

    @property
    def is_active(self) -> bool:
        return self._active and not self._retired

    def set_runtime_service(self, runtime_service: Any) -> None:
        """Accept the neutral owner injected by ``WidgetRuntimeManager``."""

        if self._retired:
            raise RuntimeError("cannot inject a retired Reddit presentation model")
        if self._active and runtime_service is not self._runtime_service:
            raise RuntimeError("cannot replace the active Reddit runtime service")
        self._runtime_service = runtime_service

    def activate(self, thread_manager: Any | None = None) -> None:
        if self._retired:
            raise RuntimeError("cannot activate a retired Reddit model")
        if self._active:
            return
        self._active = True
        service = self._runtime_service
        if service is None:
            return
        if thread_manager is None:
            self._active = False
            raise RuntimeError("Reddit runtime activation requires ThreadManager")
        service.attach_consumer(self)
        service.set_thread_manager(thread_manager)
        if service.config.subreddit.casefold() != self.config.subreddit.casefold():
            service.set_subreddit(self.config.subreddit)
        if not service.start():
            self._active = False
            service.detach_consumer(self)
            raise RuntimeError("Reddit runtime service failed to start")

    def retire(self) -> None:
        if self._retired:
            return
        self._active = False
        service = self._runtime_service
        if service is not None:
            service.stop()
            service.detach_consumer(self)
        self._retired = True
        self._row_model.replace_rows(())

    def apply_config(self, config: RedditPresentationConfig) -> bool:
        if config == self.config:
            return False
        subreddit_changed = config.subreddit.casefold() != self.config.subreddit.casefold()
        self._snapshot = replace(self._snapshot, config=config)
        if subreddit_changed:
            self._row_model.replace_rows(())
            self._snapshot = replace(
                self._snapshot,
                view_state="loading" if config.subreddit else "missing",
                error_text="",
                from_cache=False,
            )
            if self._runtime_service is not None:
                self._runtime_service.set_subreddit(config.subreddit)
        elif len(self._row_model.rows) > config.limit:
            self._row_model.replace_rows(self._row_model.rows[: config.limit])
        self.stateChanged.emit()
        return True

    def apply_style(self, style: RedditPresentationStyle) -> bool:
        if style == self.style:
            return False
        self._replace_snapshot(replace(self._snapshot, style=style))
        return True

    def publish_posts(
        self,
        posts: Iterable[RedditPost],
        *,
        from_cache: bool = False,
        now_ts: float | None = None,
    ) -> bool:
        if self._retired:
            return False
        now = time.time() if now_ts is None else float(now_ts)
        rows = tuple(
            RedditPresentationRow(
                identity=candidate_identity(post),
                title=_display_title(post.title),
                age=_age_label(post.created_utc, now),
                url=str(post.url or ""),
            )
            for post in tuple(posts)[: self.config.limit]
            if str(post.title or "").strip() and str(post.url or "").strip()
        )
        rows_changed = self._row_model.replace_rows(rows)
        snapshot = replace(
            self._snapshot,
            view_state="ready" if rows else "empty",
            error_text="",
            from_cache=bool(from_cache),
            refreshing=False,
        )
        state_changed = snapshot != self._snapshot
        self._snapshot = snapshot
        if rows_changed or state_changed:
            self.stateChanged.emit()
        return rows_changed or state_changed

    def publish_error(self, error: str) -> None:
        if self._retired:
            return
        self._replace_snapshot(
            replace(
                self._snapshot,
                view_state="ready" if self._row_model.rows else "error",
                error_text=str(error or "Reddit unavailable"),
                refreshing=False,
            )
        )

    def is_reddit_consumer_alive(self) -> bool:
        return self.is_active

    def on_reddit_runtime_posts(
        self,
        posts: Iterable[RedditPost],
        *,
        from_cache: bool,
        source_id: str | None,
        attempted_sources: Iterable[str],
    ) -> None:
        del source_id, attempted_sources
        if self.is_reddit_consumer_alive():
            self.publish_posts(posts, from_cache=from_cache)

    def on_reddit_runtime_refreshing(self, refreshing: bool) -> None:
        if self.is_reddit_consumer_alive():
            self.set_refreshing(refreshing)

    def on_reddit_runtime_error(self, error: str) -> None:
        if self.is_reddit_consumer_alive():
            self.publish_error(error)

    def request_refresh(self) -> bool:
        if not self.is_active or self._runtime_service is None:
            return False
        return bool(self._runtime_service.request_refresh())

    def set_refreshing(self, refreshing: bool) -> bool:
        normalized = bool(refreshing)
        if normalized == self._snapshot.refreshing:
            return False
        self._replace_snapshot(replace(self._snapshot, refreshing=normalized))
        return True

    def set_interaction_enabled(self, enabled: bool) -> bool:
        normalized = bool(enabled)
        if normalized == self._snapshot.interaction_enabled:
            return False
        self._replace_snapshot(
            replace(self._snapshot, interaction_enabled=normalized)
        )
        return True

    def admit_url(self, url: object) -> bool:
        if not self.is_active or not self._snapshot.interaction_enabled:
            return False
        candidate = str(url or "").strip()
        if not candidate:
            return False
        if candidate == self.subredditUrl:
            return True
        return any(row.url == candidate for row in self._row_model.rows)

    def _replace_snapshot(self, snapshot: RedditPresentationSnapshot) -> None:
        if snapshot == self._snapshot:
            return
        self._snapshot = snapshot
        self.stateChanged.emit()

    @Property(QObject, constant=True)
    def rowModel(self) -> QObject:
        return self._row_model

    @Property(str, notify=stateChanged)
    def viewState(self) -> str:
        return self._snapshot.view_state

    @Property(str, notify=stateChanged)
    def errorText(self) -> str:
        return self._snapshot.error_text

    @Property(str, notify=stateChanged)
    def subredditText(self) -> str:
        slug = self.config.subreddit
        return f"r/{slug}" if slug else "r/<subreddit>"

    @Property(str, notify=stateChanged)
    def subredditUrl(self) -> str:
        slug = self.config.subreddit
        return f"https://www.reddit.com/r/{slug}" if slug else "https://www.reddit.com"

    @Property(str, constant=True)
    def logoSource(self) -> str:
        return _REDDIT_LOGO.resolve().as_uri() if _REDDIT_LOGO.is_file() else ""

    @Property(str, notify=stateChanged)
    def fontFamily(self) -> str:
        return self.config.font_family

    @Property(float, notify=stateChanged)
    def fontSize(self) -> float:
        return float(self.config.font_size)

    @Property(float, notify=stateChanged)
    def ageFontSize(self) -> float:
        return float(max(8, self.config.font_size - 5))

    @Property(float, notify=stateChanged)
    def headerLogoSize(self) -> float:
        return float(max(12, int(self.config.font_size * 1.3) + self.config.header_logo_px_adjust))

    @Property(QColor, notify=stateChanged)
    def textColor(self) -> QColor:
        return QColor(*self.config.text_color)

    @Property(QColor, notify=stateChanged)
    def ageColor(self) -> QColor:
        return QColor(200, 200, 200, 220)

    @Property(QColor, notify=stateChanged)
    def separatorColor(self) -> QColor:
        color = QColor(*self.config.border_color)
        if color.alpha() <= 0:
            color = QColor(*self.config.text_color)
            color.setAlpha(max(0, min(255, int(color.alpha() * 0.4))))
        return color

    @Property(bool, notify=stateChanged)
    def showSeparators(self) -> bool:
        return self.config.show_separators

    @Property(bool, notify=stateChanged)
    def showBackground(self) -> bool:
        return self.config.show_background

    @Property(bool, notify=stateChanged)
    def showRefreshSpiral(self) -> bool:
        return self.config.show_refresh_spiral

    @Property(bool, notify=stateChanged)
    def refreshing(self) -> bool:
        return self._snapshot.refreshing

    @Property(bool, notify=stateChanged)
    def interactionEnabled(self) -> bool:
        return self._snapshot.interaction_enabled

    @Property(bool, notify=stateChanged)
    def fromCache(self) -> bool:
        return self._snapshot.from_cache

    @Property(bool, notify=stateChanged)
    def textShadowEnabled(self) -> bool:
        return self.style.text_shadow_enabled

    @Property(QColor, notify=stateChanged)
    def textShadowColor(self) -> QColor:
        return QColor(self.style.text_shadow_color)

    @Property(float, notify=stateChanged)
    def textShadowOffsetX(self) -> float:
        return self.style.text_shadow_offset_x

    @Property(float, notify=stateChanged)
    def textShadowOffsetY(self) -> float:
        return self.style.text_shadow_offset_y


class RetainedRedditPresentation:
    """One retained family item for either Reddit member."""

    def __init__(
        self,
        *,
        host: OrdinaryWidgetPresentationHost,
        model: RedditPresentationModel,
        geometry: OverlayWidgetGeometry,
        fade_opacity: float = 1.0,
        on_open_requested: Callable[[str], Any] | None = None,
        on_refresh_requested: Callable[[], Any] | None = None,
    ) -> None:
        self._model = model
        self._on_open_requested = on_open_requested
        self._on_refresh_requested = on_refresh_requested
        self._retained: RetainedOverlayWidget = host.create_family_widget(
            "reddit",
            initial_properties={"redditModel": model},
            object_name=model.config.widget_id,
            model_identity=model.config.widget_id,
            geometry=geometry,
            fade_opacity=fade_opacity,
            card_style=model.style.card_style,
        )
        self._retained.add_retirement_callback(model.retire)
        self._retained.set_custom_layout_size_payload_handler(
            self._apply_custom_layout_size_payload
        )
        host.set_widget_input_state_handler(self._retained, self.apply_input_state)
        open_signal = getattr(self._retained.item, "openPostRequested", None)
        if open_signal is not None and hasattr(open_signal, "connect"):
            open_signal.connect(self._handle_open_requested)
        refresh_signal = getattr(self._retained.item, "refreshRequested", None)
        if refresh_signal is not None and hasattr(refresh_signal, "connect"):
            refresh_signal.connect(self._handle_refresh_requested)

    @property
    def item(self):
        return self._retained.item

    @property
    def model(self) -> RedditPresentationModel:
        return self._model

    def activate(self, thread_manager: Any | None = None) -> None:
        self._model.activate(thread_manager)

    def set_geometry(self, geometry: OverlayWidgetGeometry) -> None:
        self._retained.set_geometry(geometry)

    def _apply_custom_layout_size_payload(
        self,
        payload: Mapping[str, object],
    ) -> None:
        # H9: Reddit CUSTOM resize is one uniform retained-presentation scale
        # (``OverlayWidget.uniformScaleTransform``) derived from the outer rect,
        # so it carries no per-value size payload and never mutates the
        # Settings-owned font size. A stale scaled ``font_size`` from a
        # pre-H9 committed layout is intentionally ignored here so replay resolves
        # the correct uniform scale from geometry alone.
        del payload

    def set_fade_opacity(self, opacity: float) -> None:
        self._retained.set_fade_opacity(opacity)

    def set_interaction_enabled(self, enabled: bool) -> bool:
        return self._model.set_interaction_enabled(enabled)

    def apply_input_state(self, input_state: object) -> bool:
        """Resolve primitive display input facts into pointer admission."""

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

    def apply_config(
        self,
        config: RedditPresentationConfig,
        shadow_values: Mapping[str, object],
        *,
        border_width: float = 4.0,
    ) -> None:
        self._model.apply_config(config)
        style = RedditPresentationStyle.project(
            config, shadow_values, border_width=border_width
        )
        self._model.apply_style(style)
        self._retained.set_card_style(style.card_style)

    def _handle_open_requested(self, url: str) -> bool:
        if not self._model.admit_url(url) or self._on_open_requested is None:
            return False
        return bool(self._on_open_requested(str(url)))

    def _handle_refresh_requested(self) -> bool:
        if (
            not self._model.is_active
            or not self._model.interactionEnabled
        ):
            return False
        if self._on_refresh_requested is not None:
            return bool(self._on_refresh_requested())
        return self._model.request_refresh()

    def retire(self) -> bool:
        return self._retained.retire()


__all__ = [
    "RedditPresentationConfig",
    "RedditPresentationModel",
    "RedditPresentationRow",
    "RedditPresentationSnapshot",
    "RedditPresentationStyle",
    "RedditRowListModel",
    "RetainedRedditPresentation",
]
