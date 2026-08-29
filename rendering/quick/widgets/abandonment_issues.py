"""Retained Abandonment Issues presentation state and runtime bridge.

Provider, cache, selection, refresh and rotation cadence remain owned by the
existing neutral Abandonment runtime. This module owns only accepted retained
state, semantic action admission and presentation-only configuration.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QColor

from core.steam.abandonment_issues import AbandonmentSelection, parse_appid_list
from widgets.steam_abandonment_preparation import (
    AbandonmentPreparedPresentation,
    AbandonmentRuntimeConfig,
)
from widgets.steam_abandonment_layout import (
    ABANDONMENT_ACCENT_RGBA,
    ABANDONMENT_ARTWORK_SIZE_DEFAULT,
    ABANDONMENT_FIELD_DEFAULTS,
    abandonment_authored_size,
    abandonment_field_slot_count,
    normalize_abandonment_artwork_shape,
    normalize_abandonment_artwork_size,
)
from widgets.steam_card_models import (
    SteamCardViewModel,
    build_steam_connect_required_view_model,
)

from .host import (
    OrdinaryWidgetPresentationHost,
    OverlayCardStyle,
    OverlayWidgetGeometry,
    RetainedOverlayWidget,
)
from .steam_common import (
    SteamCardFieldListModel,
    accepted_local_image_source,
    as_bool,
    bounded_float,
    bounded_int,
    optional_appid,
    project_steam_card_style,
    rgba,
)


_STEAM_LOGO = Path(__file__).resolve().parents[3] / "images" / "Steam_Logo.png"
_FIELD_DEFAULTS = tuple(ABANDONMENT_FIELD_DEFAULTS.items())


@dataclass(frozen=True)
class AbandonmentIssuesPresentationConfig:
    font_family: str = "Inter"
    font_size: int = 14
    text_color: tuple[int, int, int, int] = (255, 255, 255, 230)
    show_background: bool = True
    background_color: tuple[int, int, int, int] = (35, 35, 35, 255)
    background_opacity: float = 0.3
    border_color: tuple[int, int, int, int] = (255, 255, 255, 255)
    border_opacity: float = 1.0
    selection_mode: str = "smart_rotation"
    pinned_appid: int | None = None
    minimum_playtime_minutes: int = 15
    preferred_max_playtime_minutes: int = 120
    preferred_max_unlocked_achievements: int = 2
    minimum_inactivity_days: int = 84
    preferred_minimum_inactivity_days: int = 182
    never_show_appids: tuple[int, ...] = ()
    field_visibility: tuple[tuple[str, bool], ...] = _FIELD_DEFAULTS
    show_rediscovery_message: bool = True
    show_artwork: bool = True
    artwork_shape: str = "portrait"
    artwork_size: int = ABANDONMENT_ARTWORK_SIZE_DEFAULT
    accent_color: tuple[int, int, int, int] = ABANDONMENT_ACCENT_RGBA
    guilt_desaturater: bool = False
    guilt_desaturation_strength: int = 55
    refresh_minutes: int = 10
    show_connection_info_icon: bool = True

    @classmethod
    def from_widgets_mapping(
        cls,
        widgets: Mapping[str, object],
    ) -> "AbandonmentIssuesPresentationConfig":
        """Project canonical shared-Steam and Abandonment settings."""

        from core.settings.defaults import get_default_settings

        defaults = get_default_settings().get("widgets", {})
        default_shared = defaults.get("steam", {}) if isinstance(defaults, Mapping) else {}
        default_card = (
            defaults.get("abandonment_issues", {})
            if isinstance(defaults, Mapping)
            else {}
        )
        shared = widgets.get("steam", {}) if isinstance(widgets, Mapping) else {}
        card = (
            widgets.get("abandonment_issues", {})
            if isinstance(widgets, Mapping)
            else {}
        )
        merged_shared = dict(default_shared) if isinstance(default_shared, Mapping) else {}
        merged_card = dict(default_card) if isinstance(default_card, Mapping) else {}
        if isinstance(shared, Mapping):
            merged_shared.update(shared)
        if isinstance(card, Mapping):
            merged_card.update(card)

        field_visibility = tuple(
            (
                field_id,
                as_bool(merged_card.get(f"show_{field_id}"), default),
            )
            for field_id, default in _FIELD_DEFAULTS
        )
        return cls(
            font_family=str(merged_card.get("font_family", "Inter") or "Inter"),
            font_size=bounded_int(merged_card.get("font_size"), 14, 8, 96),
            text_color=rgba(
                merged_card.get("color"),
                (255, 255, 255, 230),
            ),
            show_background=as_bool(
                merged_card.get("show_background"), True
            ),
            background_color=rgba(
                merged_card.get("bg_color"),
                (35, 35, 35, 255),
            ),
            background_opacity=bounded_float(
                merged_card.get("bg_opacity"), 0.3, 0.0, 1.0
            ),
            border_color=rgba(
                merged_card.get("border_color"),
                (255, 255, 255, 255),
            ),
            border_opacity=bounded_float(
                merged_card.get("border_opacity"), 1.0, 0.0, 1.0
            ),
            selection_mode=str(
                merged_card.get("selection_mode", "smart_rotation")
                or "smart_rotation"
            ),
            pinned_appid=optional_appid(merged_card.get("pinned_appid")),
            minimum_playtime_minutes=bounded_int(
                merged_card.get("minimum_playtime_minutes"), 15, 0, 1_000_000
            ),
            preferred_max_playtime_minutes=bounded_int(
                merged_card.get("preferred_max_playtime_hours"), 2, 1, 100_000
            )
            * 60,
            preferred_max_unlocked_achievements=bounded_int(
                merged_card.get("preferred_max_unlocked_achievements"),
                2,
                0,
                100_000,
            ),
            minimum_inactivity_days=bounded_int(
                merged_card.get("minimum_inactivity_weeks"), 12, 0, 100_000
            )
            * 7,
            preferred_minimum_inactivity_days=bounded_int(
                merged_card.get("preferred_minimum_inactivity_weeks"),
                26,
                0,
                100_000,
            )
            * 7,
            never_show_appids=parse_appid_list(
                merged_card.get("never_show_appids", ())
            ),
            field_visibility=field_visibility,
            show_rediscovery_message=as_bool(
                merged_card.get("show_rediscovery_message"), True
            ),
            show_artwork=as_bool(merged_card.get("show_artwork"), True),
            artwork_shape=normalize_abandonment_artwork_shape(
                merged_card.get("artwork_shape", "portrait")
            ),
            artwork_size=normalize_abandonment_artwork_size(
                merged_card.get("artwork_size", ABANDONMENT_ARTWORK_SIZE_DEFAULT)
            ),
            accent_color=rgba(
                merged_card.get("accent_color"),
                ABANDONMENT_ACCENT_RGBA,
            ),
            guilt_desaturater=as_bool(
                merged_card.get("guilt_desaturater"), False
            ),
            guilt_desaturation_strength=bounded_int(
                merged_card.get("guilt_desaturation_strength"), 55, 0, 100
            ),
            refresh_minutes=bounded_int(
                merged_shared.get("refresh_minutes"), 10, 5, 1440
            ),
            show_connection_info_icon=as_bool(
                merged_shared.get("show_connection_info_icon"), True
            ),
        )

    @property
    def runtime_config(self) -> AbandonmentRuntimeConfig:
        return AbandonmentRuntimeConfig(
            selection=AbandonmentSelection(
                mode=self.selection_mode,
                pinned_appid=self.pinned_appid,
                minimum_playtime_minutes=self.minimum_playtime_minutes,
                preferred_max_playtime_minutes=self.preferred_max_playtime_minutes,
                preferred_max_unlocked_achievements=(
                    self.preferred_max_unlocked_achievements
                ),
                minimum_inactivity_days=self.minimum_inactivity_days,
                preferred_minimum_inactivity_days=(
                    self.preferred_minimum_inactivity_days
                ),
                never_show_appids=self.never_show_appids,
            ),
            field_visibility=dict(self.field_visibility),
            show_artwork=self.show_artwork,
            artwork_shape=self.artwork_shape,
            guilt_desaturater=self.guilt_desaturater,
            guilt_desaturation_strength=self.guilt_desaturation_strength,
            refresh_minutes=self.refresh_minutes,
            show_connection_info_icon=self.show_connection_info_icon,
            show_rediscovery_message=self.show_rediscovery_message,
        )

    @property
    def authored_size(self) -> tuple[float, float]:
        size = abandonment_authored_size(
            show_artwork=self.show_artwork,
            artwork_shape=self.artwork_shape,
            artwork_size=self.artwork_size,
            field_count=abandonment_field_slot_count(
                dict(self.field_visibility)
            ),
        )
        return float(size.width()), float(size.height())


@dataclass(frozen=True)
class AbandonmentIssuesPresentationStyle:
    card_style: OverlayCardStyle
    text_shadow_enabled: bool
    text_shadow_color: QColor
    text_shadow_offset_x: float
    text_shadow_offset_y: float

    @classmethod
    def project(
        cls,
        config: AbandonmentIssuesPresentationConfig,
        shadow_values: Mapping[str, object],
        *,
        border_width: float = 4.0,
    ) -> "AbandonmentIssuesPresentationStyle":
        projection = project_steam_card_style(
            show_background=config.show_background,
            background_color=config.background_color,
            background_opacity=config.background_opacity,
            border_color=config.border_color,
            border_opacity=config.border_opacity,
            shadow_values=shadow_values,
            border_width=border_width,
        )
        return cls(
            card_style=projection.card_style,
            text_shadow_enabled=projection.text_shadow_enabled,
            text_shadow_color=projection.text_shadow_color,
            text_shadow_offset_x=projection.text_shadow_offset_x,
            text_shadow_offset_y=projection.text_shadow_offset_y,
        )


@dataclass(frozen=True)
class AbandonmentIssuesPresentationSnapshot:
    config: AbandonmentIssuesPresentationConfig
    style: AbandonmentIssuesPresentationStyle
    card: SteamCardViewModel
    artwork_source: str = ""
    artwork_identity: str = ""
    desaturation_bucket: int = 0
    interaction_enabled: bool = False


class AbandonmentIssuesPresentationModel(QObject):
    """Stable retained state for one archival Abandonment card."""

    stateChanged = Signal()
    fadeRequested = Signal()
    contentTransitionRequested = Signal()

    def __init__(
        self,
        config: AbandonmentIssuesPresentationConfig,
        style: AbandonmentIssuesPresentationStyle,
        *,
        runtime_service: Any | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._snapshot = AbandonmentIssuesPresentationSnapshot(
            config=config,
            style=style,
            card=build_steam_connect_required_view_model("abandonment_issues"),
        )
        self._field_model = SteamCardFieldListModel(self)
        self._runtime_service = runtime_service
        self._runtime_attached = False
        self._active = False
        self._retired = False
        self._pending_presentation: AbandonmentPreparedPresentation | None = None
        self._pending_manual_refresh = False
        self._pending_rotation = False

    @property
    def config(self) -> AbandonmentIssuesPresentationConfig:
        return self._snapshot.config

    @property
    def style(self) -> AbandonmentIssuesPresentationStyle:
        return self._snapshot.style

    @property
    def card(self) -> SteamCardViewModel:
        return self._snapshot.card

    @property
    def field_model(self) -> SteamCardFieldListModel:
        return self._field_model

    @property
    def is_active(self) -> bool:
        return self._active and not self._retired

    @property
    def has_pending_transition(self) -> bool:
        return self._pending_presentation is not None

    def is_abandonment_consumer_alive(self) -> bool:
        return self.is_active

    def set_runtime_service(self, service: Any) -> None:
        if self._retired or self._active:
            raise RuntimeError(
                "cannot replace Abandonment runtime after activation"
            )
        if self._runtime_service is service:
            return
        if self._runtime_service is not None:
            raise RuntimeError(
                "Abandonment presentation already has a runtime service"
            )
        self._runtime_service = service

    def activate(self, thread_manager: Any | None = None) -> bool:
        if self._retired:
            raise RuntimeError("cannot activate a retired Abandonment model")
        if self._active:
            return True
        service = self._runtime_service
        if service is not None:
            if thread_manager is None:
                raise RuntimeError("Abandonment runtime activation requires ThreadManager")
            service.configure(self.config.runtime_config)
            service.set_thread_manager(thread_manager)
            service.attach_consumer(self)
            self._runtime_attached = True
        self._active = True
        if service is not None and not service.start(start_fade_after_load=True):
            self._active = False
            service.detach_consumer(self)
            self._runtime_attached = False
            self._runtime_service = None
            raise RuntimeError("Abandonment runtime service failed to start")
        return True

    def on_abandonment_presentation(
        self,
        presentation: AbandonmentPreparedPresentation,
        *,
        animate: bool,
    ) -> None:
        if (
            not self.is_active
            or presentation.model.card_id != "abandonment_issues"
        ):
            return
        if animate:
            self._pending_presentation = presentation
            self.contentTransitionRequested.emit()
            return
        self._pending_presentation = None
        self._commit_presentation(presentation)
        self._flush_deferred_actions()

    def _commit_presentation(
        self,
        presentation: AbandonmentPreparedPresentation,
    ) -> None:
        card = presentation.model
        rows_changed = self._field_model.replace_rows(card.fields)
        snapshot = replace(
            self._snapshot,
            card=card,
            artwork_source=accepted_local_image_source(
                presentation.artwork,
                presentation.artwork_identity,
            ),
            artwork_identity=str(presentation.artwork_identity or ""),
            desaturation_bucket=max(0, int(presentation.desaturation_bucket)),
        )
        state_changed = snapshot != self._snapshot
        self._snapshot = snapshot
        if rows_changed or state_changed:
            self.stateChanged.emit()

    @Slot(result=bool)
    def commitPendingPresentation(self) -> bool:  # noqa: N802
        presentation = self._pending_presentation
        if not self.is_active or presentation is None:
            return False
        self._pending_presentation = None
        self._commit_presentation(presentation)
        self._flush_deferred_actions()
        return True

    def request_abandonment_fade(self) -> None:
        if self.is_active:
            self.fadeRequested.emit()

    def request_manual_refresh(self) -> bool:
        if (
            not self.is_active
            or not self._snapshot.interaction_enabled
            or self._runtime_service is None
        ):
            return False
        if self.has_pending_transition:
            self._pending_manual_refresh = True
            return True
        return bool(self._runtime_service.request_manual_refresh())

    def on_abandonment_rotation_due(self) -> bool:
        if not self.is_active or self._runtime_service is None:
            return False
        if self.has_pending_transition:
            self._pending_rotation = True
            return True
        return bool(self._runtime_service.request_cache_rotation())

    def _flush_deferred_actions(self) -> None:
        service = self._runtime_service
        if service is None or not self.is_active:
            self._pending_manual_refresh = False
            self._pending_rotation = False
            return
        if self._pending_manual_refresh:
            self._pending_manual_refresh = False
            service.request_manual_refresh()
        if self._pending_rotation:
            self._pending_rotation = False
            service.request_cache_rotation()

    def notify_fade_complete(self) -> None:
        if self.is_active and self._runtime_service is not None:
            self._runtime_service.on_presentation_fade_complete()

    def set_interaction_enabled(self, enabled: bool) -> bool:
        normalized = bool(enabled)
        if normalized == self._snapshot.interaction_enabled:
            return False
        self._snapshot = replace(
            self._snapshot,
            interaction_enabled=normalized,
        )
        self.stateChanged.emit()
        return True

    def apply_custom_layout_config(
        self,
        config: AbandonmentIssuesPresentationConfig,
    ) -> bool:
        if self._retired or config == self.config:
            return False
        self._snapshot = replace(self._snapshot, config=config)
        self.stateChanged.emit()
        return True

    def apply_style(self, style: AbandonmentIssuesPresentationStyle) -> bool:
        if self._retired or style == self.style:
            return False
        self._snapshot = replace(self._snapshot, style=style)
        self.stateChanged.emit()
        return True

    def retire(self) -> None:
        if self._retired:
            return
        self._retired = True
        self._active = False
        self._pending_presentation = None
        self._pending_manual_refresh = False
        self._pending_rotation = False
        if self._runtime_service is not None and self._runtime_attached:
            self._runtime_service.stop()
            self._runtime_service.detach_consumer(self)
        self._runtime_attached = False
        self._runtime_service = None
        self._field_model.replace_rows(())

    @Property(QObject, constant=True)
    def fieldModel(self) -> QObject:
        return self._field_model

    @Property(str, notify=stateChanged)
    def headerText(self) -> str:
        return self.card.header

    @Property(str, notify=stateChanged)
    def title(self) -> str:
        return self.card.title

    @Property(str, notify=stateChanged)
    def subtitle(self) -> str:
        return self.card.subtitle

    @Property(str, notify=stateChanged)
    def metricLabel(self) -> str:
        return self.card.metric_label

    @Property(str, notify=stateChanged)
    def metricValue(self) -> str:
        return self.card.metric_value

    @Property(str, notify=stateChanged)
    def statusText(self) -> str:
        return self.card.status

    @Property(str, notify=stateChanged)
    def viewState(self) -> str:
        return self.card.state

    @Property(int, notify=stateChanged)
    def appid(self) -> int:
        return int(self.card.appid or 0)

    @Property(bool, notify=stateChanged)
    def interactionEnabled(self) -> bool:
        return self._snapshot.interaction_enabled

    @Property(bool, notify=stateChanged)
    def showConnectionInfo(self) -> bool:
        return self.card.show_connection_info

    @Property(str, notify=stateChanged)
    def connectionInfoTarget(self) -> str:
        return self.card.connection_info_target

    @Property(str, notify=stateChanged)
    def connectionInfoTooltip(self) -> str:
        return self.card.connection_info_tooltip

    @Property(str, notify=stateChanged)
    def settingsTarget(self) -> str:
        return self.card.settings_target

    @Property(str, notify=stateChanged)
    def actionText(self) -> str:
        return self.card.action_text

    @Property(str, notify=stateChanged)
    def actionLabel(self) -> str:
        return self.card.action_label

    @Property(QColor, notify=stateChanged)
    def accentColor(self) -> QColor:
        return QColor(*self.config.accent_color)

    @Property(str, constant=True)
    def logoSource(self) -> str:
        return _STEAM_LOGO.resolve().as_uri() if _STEAM_LOGO.is_file() else ""

    @Property(str, notify=stateChanged)
    def artworkSource(self) -> str:
        return self._snapshot.artwork_source

    @Property(str, notify=stateChanged)
    def artworkIdentity(self) -> str:
        return self._snapshot.artwork_identity

    @Property(int, notify=stateChanged)
    def desaturationBucket(self) -> int:
        return self._snapshot.desaturation_bucket

    @Property(bool, notify=stateChanged)
    def showArtwork(self) -> bool:
        return self.config.show_artwork

    @Property(str, notify=stateChanged)
    def artworkShape(self) -> str:
        return self.config.artwork_shape

    @Property(float, notify=stateChanged)
    def artworkSize(self) -> float:
        return float(self.config.artwork_size)

    @Property(str, notify=stateChanged)
    def fontFamily(self) -> str:
        return self.config.font_family

    @Property(float, notify=stateChanged)
    def fontSize(self) -> float:
        return float(self.config.font_size)

    @Property(QColor, notify=stateChanged)
    def textColor(self) -> QColor:
        return QColor(*self.config.text_color)

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

    @Property(float, notify=stateChanged)
    def authoredWidth(self) -> float:
        return self.config.authored_size[0]

    @Property(float, notify=stateChanged)
    def authoredHeight(self) -> float:
        return self.config.authored_size[1]


class RetainedAbandonmentIssuesPresentation:
    """One retained archive card with semantic action routing."""

    def __init__(
        self,
        *,
        host: OrdinaryWidgetPresentationHost,
        model: AbandonmentIssuesPresentationModel,
        geometry: OverlayWidgetGeometry,
        fade_opacity: float = 0.0,
        on_settings_requested: Callable[[str], Any] | None = None,
    ) -> None:
        self._host = host
        self._model = model
        self._on_settings_requested = on_settings_requested
        self._retained: RetainedOverlayWidget = host.create_family_widget(
            "abandonment_issues",
            initial_properties={"abandonmentModel": model},
            object_name="abandonment_issues",
            model_identity="abandonment_issues",
            geometry=geometry,
            fade_opacity=fade_opacity,
            card_style=model.style.card_style,
        )
        self._retained.add_retirement_callback(model.retire)
        self._retained.set_custom_layout_size_payload_handler(
            self._apply_custom_layout_size_payload
        )
        host.set_widget_input_state_handler(self._retained, self.apply_input_state)
        self._connect("refreshRequested", model.request_manual_refresh)
        self._connect("settingsRequested", self._handle_settings_requested)
        model.fadeRequested.connect(self._handle_fade_requested)

    def _connect(self, signal_name: str, callback: Callable[..., Any]) -> None:
        signal = getattr(self._retained.item, signal_name, None)
        if signal is not None and hasattr(signal, "connect"):
            signal.connect(callback)

    @property
    def item(self):
        return self._retained.item

    @property
    def model(self) -> AbandonmentIssuesPresentationModel:
        return self._model

    def activate(self, thread_manager: Any | None = None) -> bool:
        return self._model.activate(thread_manager)

    def set_geometry(self, geometry: OverlayWidgetGeometry) -> None:
        self._retained.set_geometry(geometry)

    def set_fade_opacity(self, opacity: float) -> None:
        self._retained.set_fade_opacity(opacity)

    def set_interaction_enabled(self, enabled: bool) -> bool:
        return self._model.set_interaction_enabled(enabled)

    def _apply_custom_layout_size_payload(
        self,
        payload: Mapping[str, Any],
    ) -> None:
        config = self._model.config
        self._model.apply_custom_layout_config(
            replace(
                config,
                font_size=int(payload.get("font_size", config.font_size)),
                artwork_size=int(payload.get("artwork_size", config.artwork_size)),
            )
        )

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

    def apply_style(
        self,
        shadow_values: Mapping[str, object],
        *,
        border_width: float = 4.0,
    ) -> None:
        style = AbandonmentIssuesPresentationStyle.project(
            self._model.config,
            shadow_values,
            border_width=border_width,
        )
        self._model.apply_style(style)
        self._retained.set_card_style(style.card_style)

    def _handle_settings_requested(self, target: str) -> bool:
        normalized = str(target or "").strip()
        if (
            not self._model.is_active
            or not self._model.interactionEnabled
            or not normalized
            or self._on_settings_requested is None
        ):
            return False
        return bool(self._on_settings_requested(normalized))

    def _handle_fade_requested(self) -> None:
        if not self._model.is_active:
            return
        self._retained.set_fade_opacity(1.0)
        self._model.notify_fade_complete()

    def retire(self) -> bool:
        return self._host.retire_widget(self._retained)


__all__ = [
    "AbandonmentIssuesPresentationConfig",
    "AbandonmentIssuesPresentationModel",
    "AbandonmentIssuesPresentationSnapshot",
    "AbandonmentIssuesPresentationStyle",
    "RetainedAbandonmentIssuesPresentation",
]
