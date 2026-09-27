"""Thin per-display ordinary-family presentation binder (H keystone).

Presentation-neutral wiring that resolves the admitted ordinary-widget family
instances routed to one display generation and constructs their existing
``Retained*Presentation`` items into that display's
``OrdinaryWidgetPresentationHost``.

It invents no capability, cadence, settings, geometry or provider authority:

- capability effectiveness (activation + dependency satisfaction) and neutral
  runtime service lifetimes stay with the single injected
  :class:`~rendering.widget_runtime_manager.WidgetRuntimeManager`;
- per-family config/style/model/item construction stays in the existing family
  modules, reached through one small explicit per-family adapter each;
- geometry and global shadow values are resolved by the display/runtime-level
  caller and injected as plain seams.

The binder only *orders* admission, *builds* through the adapters, and *holds*
the resulting retained presentations so it can retire them exactly once with the
display generation. It is not a second family map, provider owner, lifecycle
owner or clock. Per-instance ``enabled`` state and effective monitor route stay
distinct from family capability effectiveness, exactly as the neutral manager
and descriptor contracts require.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Optional, Protocol, runtime_checkable

from core.logging.logger import get_logger
from core.settings.default_contract import require_canonical_default
from rendering.widget_descriptors import widget_route_admits_screen

from .host import OrdinaryWidgetPresentationHost, OverlayWidgetGeometry

logger = get_logger(__name__)


def _enabled_flag(value: object, default: bool) -> bool:
    """Coerce a canonical ``enabled`` value without importing family privates."""

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


def _enabled_from_candidates(
    widgets_config: Mapping[str, object],
    candidate_ids: Sequence[str],
) -> tuple[str, ...]:
    """Filter explicit candidate instance ids by canonical per-instance enabled.

    Missing instance state resolves only through the canonical Widget default
    for that id; adapter ordering is never allowed to imply product behavior.
    """

    enabled: list[str] = []
    for widget_id in candidate_ids:
        values = widgets_config.get(widget_id, {})
        if not isinstance(values, Mapping):
            values = {}
        default_enabled = bool(
            require_canonical_default(f"widgets.{widget_id}.enabled")
        )
        if _enabled_flag(values.get("enabled", default_enabled), default_enabled):
            enabled.append(widget_id)
    return tuple(enabled)


def _attach_runtime_service(
    runtime_manager: Any,
    widget_id: str,
    model: Any,
    widgets_config: Mapping[str, object],
) -> bool:
    """Own and inject the neutral runtime service for a model, or fail closed.

    A widget id with no registered service spec needs no service and passes. A
    widget id that requires a service must receive one: a ``None`` result is a
    hard build/injection failure and the instance must not present on a
    retired presenter-owned or serviceless fallback.
    """

    if not runtime_manager.has_runtime_service(widget_id):
        return True
    service = runtime_manager.ensure_widget_service(widget_id, model, widgets_config)
    return service is not None


@runtime_checkable
class BoundFamilyPresentation(Protocol):
    """Minimal structural contract the binder needs to hold and retire an item."""

    def retire(self) -> bool: ...


@runtime_checkable
class OrdinaryFamilyAdapter(Protocol):
    """One explicit presentation-neutral adapter per ordinary widget family.

    An adapter owns only the knowledge of how to enumerate a family's enabled
    instances and how to construct that family's existing ``Retained*Presentation``
    from already-resolved settings. It holds no runtime lifetime itself.

    ``presentation_model`` is the single model construction ``build`` uses. It
    is also the seam Settings Arrange measures preferred sizes through
    (``preferred_size_measurement``), so both read one size authority.
    """

    @property
    def family_id(self) -> str: ...

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]: ...

    def presentation_component(self, widget_id: str) -> str | None:
        """Registered QML component id presenting ``widget_id``, or None if foreign."""
        ...

    def presentation_model(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        shadow_values: Mapping[str, object],
        display_identity: str | None = None,
        runtime_generation: int | None = None,
    ) -> Any:
        """Build the family's detached presentation model (no service, no item)."""
        ...

    def presentation_card_style(self, model: Any) -> Any:
        """The ``OverlayCardStyle`` the family's retained card presents ``model`` with."""
        ...

    def build(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        host: OrdinaryWidgetPresentationHost,
        geometry: OverlayWidgetGeometry,
        display_bounds: OverlayWidgetGeometry,
        display_identity: str,
        shadow_values: Mapping[str, object],
        runtime_manager: Any,
        runtime_generation: int | None,
    ) -> BoundFamilyPresentation | None: ...


class OrdinaryFamilyPresentationBinder:
    """Resolve + build + hold the admitted family presentations for one display."""

    def __init__(
        self,
        *,
        host: OrdinaryWidgetPresentationHost,
        runtime_manager: Any,
        geometry_resolver: Callable[[str], Optional[OverlayWidgetGeometry]],
        display_bounds: OverlayWidgetGeometry,
        display_identity: str,
        screen_index: int,
        shadow_values: Mapping[str, object] | None = None,
        thread_manager: Any | None = None,
        runtime_generation: int | None = None,
        adapters: Sequence[OrdinaryFamilyAdapter] | None = None,
    ) -> None:
        self._host = host
        self._runtime_manager = runtime_manager
        self._geometry_resolver = geometry_resolver
        self._display_bounds = display_bounds
        self._display_identity = str(display_identity)
        self._screen_index = int(screen_index)
        self._shadow_values: dict[str, object] = dict(shadow_values or {})
        self._thread_manager = thread_manager
        self._runtime_generation = runtime_generation
        self._adapters: tuple[OrdinaryFamilyAdapter, ...] = (
            tuple(adapters)
            if adapters is not None
            else default_ordinary_family_adapters()
        )
        self._bound: list[BoundFamilyPresentation] = []
        self._bound_widget_ids: list[str] = []
        self._bound_once = False
        self._retired = False

    @property
    def is_retired(self) -> bool:
        return self._retired

    @property
    def bound_widget_ids(self) -> tuple[str, ...]:
        return tuple(self._bound_widget_ids)

    @property
    def live_count(self) -> int:
        return len(self._bound)

    def presentation_for_widget_id(
        self,
        widget_id: str,
    ) -> BoundFamilyPresentation | None:
        """Return the retained presentation already owned for ``widget_id``."""

        normalized = str(widget_id)
        for bound_id, presentation in zip(self._bound_widget_ids, self._bound):
            if bound_id == normalized:
                return presentation
        return None

    def transfer_presentation_to(self, widget_id: str, target: "OrdinaryFamilyPresentationBinder") -> None:
        """Move the same family and service retirement records after pixel transfer."""
        if self._retired or target._retired:
            raise RuntimeError("cannot transfer a retired family binder")
        if target.presentation_for_widget_id(widget_id) is not None:
            raise RuntimeError(f"target already owns family: {widget_id}")
        index = self._bound_widget_ids.index(widget_id)
        self._runtime_manager.transfer_widget_service_to(widget_id, target._runtime_manager)
        presentation = self._bound.pop(index)
        self._bound_widget_ids.pop(index)
        target._bound.append(presentation)
        target._bound_widget_ids.append(widget_id)

    def retire_widget(self, widget_id: str) -> bool:
        """Retire one owned ordinary presentation and its neutral services.

        This is the mid-generation counterpart to ``retire_all``. It exists for
        retained CUSTOM disable commits: removing one ordinary card must not
        require destroying the display/runtime generation. Family-specific
        multi-service ownership stays in ``widget_runtime_services``.
        """

        if self._retired:
            raise RuntimeError("cannot retire a widget from a retired family binder")
        identity = str(widget_id or "").strip()
        if identity not in self._bound_widget_ids:
            return False
        index = self._bound_widget_ids.index(identity)
        presentation = self._bound.pop(index)
        self._bound_widget_ids.pop(index)

        retired = False
        try:
            retired = bool(presentation.retire())
        finally:
            from rendering.widget_runtime_services import (
                get_runtime_service_ids_for_presentation,
            )

            for service_id in get_runtime_service_ids_for_presentation(identity):
                self._runtime_manager.retire_widget_service(service_id)
        if not retired:
            raise RuntimeError(
                f"retained family refused mid-generation retirement: {identity}"
            )
        return True

    def bind(self, widgets_config: Mapping[str, object] | None) -> tuple[str, ...]:
        """Build every admitted family instance once for this display generation.

        A family is admitted only while its capability is *effective* (activated
        and every required family activated); within an admitted family, only the
        per-instance ``enabled`` instances whose effective monitor route admits
        this destination are built. Returns the built widget ids in build order.
        """

        if self._retired:
            raise RuntimeError("cannot bind a retired family presentation binder")
        if self._bound_once:
            raise RuntimeError("family presentation binder already bound this generation")
        self._bound_once = True

        config: Mapping[str, object] = (
            widgets_config if isinstance(widgets_config, Mapping) else {}
        )
        # Two-phase display-family assembly. Phase 1 resolves/builds/owns every
        # admitted retained presentation in the stable adapter order WITHOUT
        # activating any of them. Phase 2 then activates each successfully built
        # presentation exactly once, in the same order.
        #
        # The previous single loop interleaved build with activation, so a built
        # family's provider/native/artwork work (submitted to I/O workers) could
        # begin while a *later* admitted family's QML component was still being
        # constructed on the GUI thread. That concurrency intermittently wedged
        # screen-1 replacement construction (H1: MainThread stuck deep in
        # QQmlComponent.createWithInitialProperties for a later family while an
        # I/O worker ran a decode for an already-activated earlier family).
        # Deferring all activation until construction has fully returned removes
        # that overlap without changing admission, ownership or retirement.
        for adapter in self._adapters:
            family_id = adapter.family_id
            if not self._runtime_manager.is_family_effective(config, family_id):
                continue
            for widget_id in adapter.enabled_instance_ids(config):
                if not widget_route_admits_screen(
                    widget_id,
                    config,
                    self._screen_index,
                ):
                    logger.debug(
                        "[FAMILY_BINDER] Monitor route excludes %s from screen %d",
                        widget_id,
                        self._screen_index,
                    )
                    continue
                geometry = self._geometry_resolver(widget_id)
                if geometry is None:
                    logger.debug(
                        "[FAMILY_BINDER] No geometry for %s; skipping admission",
                        widget_id,
                    )
                    continue
                try:
                    retained = adapter.build(
                        widget_id=widget_id,
                        widgets_config=config,
                        host=self._host,
                        geometry=geometry,
                        display_bounds=self._display_bounds,
                        display_identity=self._display_identity,
                        shadow_values=self._shadow_values,
                        runtime_manager=self._runtime_manager,
                        runtime_generation=self._runtime_generation,
                    )
                except Exception:
                    logger.debug(
                        "[FAMILY_BINDER] Failed to build %s for family %s",
                        widget_id,
                        family_id,
                        exc_info=True,
                    )
                    continue
                if retained is None:
                    continue
                # Own the built presentation now so retire_all() covers it even if
                # its later activation fails; activation itself is deferred.
                self._bound.append(retained)
                self._bound_widget_ids.append(widget_id)

        # Phase 2 — activate every successfully built presentation exactly once,
        # in build order, only after all admitted construction has returned. A
        # failed activation is contained and never unbinds the presentation.
        if self._thread_manager is not None:
            for widget_id, retained in zip(self._bound_widget_ids, self._bound):
                activate = getattr(retained, "activate", None)
                if not callable(activate):
                    continue
                try:
                    activate(self._thread_manager)
                except Exception:
                    # A built retained family whose activation failed otherwise
                    # appears present but stays in loading/inactive state. Report
                    # this once at the activation edge, never on frame/render or
                    # provider cadence; teardown still owns the built family.
                    logger.warning(
                        "[FAMILY_BINDER] Failed to activate %s in generation %s",
                        widget_id, self._runtime_generation,
                        exc_info=True,
                    )
        return tuple(self._bound_widget_ids)

    def retire_all(self) -> None:
        """Retire every held presentation exactly once (terminal for this owner)."""

        if self._retired:
            return
        self._retired = True
        bound = self._bound
        self._bound = []
        self._bound_widget_ids = []
        for retained in reversed(bound):
            try:
                retained.retire()
            except Exception:
                logger.debug(
                    "[FAMILY_BINDER] Failed to retire a bound family presentation",
                    exc_info=True,
                )


class ClockFamilyAdapter:
    """Adapter for the Clock family (clock/clock2/clock3)."""

    def __init__(
        self,
        *,
        on_mode_toggle: Callable[
            [str, str, str, OverlayWidgetGeometry, Mapping[str, object]], None
        ] | None = None,
    ) -> None:
        # Product persistence stays outside the retained presentation. The
        # adapter only binds one already-existing semantic callback into the
        # presentation for this display/widget identity.
        self._on_mode_toggle = on_mode_toggle

    @property
    def family_id(self) -> str:
        return "clocks"

    INSTANCE_IDS = ("clock", "clock2", "clock3")

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]:
        return _enabled_from_candidates(widgets_config, self.INSTANCE_IDS)

    def presentation_component(self, widget_id: str) -> str | None:
        return "clocks" if widget_id in self.INSTANCE_IDS else None

    def presentation_card_style(self, model: Any) -> Any:
        return model.style.card_style

    def presentation_model(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        shadow_values: Mapping[str, object],
        display_identity: str | None = None,
        runtime_generation: int | None = None,
    ) -> Any:
        from .clock import (
            ClockPresentationConfig,
            ClockPresentationModel,
            ClockPresentationStyle,
        )

        config = ClockPresentationConfig.from_widgets_mapping(
            widget_id,
            widgets_config,
            display_signature=display_identity,
        )
        style = ClockPresentationStyle.project(config, shadow_values)
        return ClockPresentationModel(config, style)

    def build(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        host: OrdinaryWidgetPresentationHost,
        geometry: OverlayWidgetGeometry,
        display_bounds: OverlayWidgetGeometry,
        display_identity: str,
        shadow_values: Mapping[str, object],
        runtime_manager: Any,
        runtime_generation: int | None = None,
    ) -> BoundFamilyPresentation | None:
        from .clock import RetainedClockPresentation

        model = self.presentation_model(
            widget_id=widget_id,
            widgets_config=widgets_config,
            shadow_values=shadow_values,
            display_identity=display_identity,
        )
        mode_callback = None
        if self._on_mode_toggle is not None:
            mode_callback = (
                lambda target_mode, geometry, size_payload, wid=widget_id: (
                    self._on_mode_toggle(
                        wid,
                        presentation_ref().display_identity,
                        str(target_mode),
                        geometry,
                        size_payload,
                    )
                )
            )
        presentation = RetainedClockPresentation(
            host=host,
            model=model,
            geometry=geometry,
            display_bounds=display_bounds,
            display_identity=display_identity,
            on_mode_toggle=mode_callback,
        )
        from weakref import ref
        presentation_ref = ref(presentation)
        return presentation


class WeatherFamilyAdapter:
    """Adapter for the single-instance Weather family."""

    def __init__(
        self,
        *,
        on_settings_requested: Callable[[str], bool] | None = None,
    ) -> None:
        self._on_settings_requested = on_settings_requested

    @property
    def family_id(self) -> str:
        return "weather"

    INSTANCE_IDS = ("weather",)

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]:
        return _enabled_from_candidates(widgets_config, self.INSTANCE_IDS)

    def presentation_component(self, widget_id: str) -> str | None:
        return "weather" if widget_id in self.INSTANCE_IDS else None

    def presentation_card_style(self, model: Any) -> Any:
        return model.style.card_style

    def presentation_model(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        shadow_values: Mapping[str, object],
        display_identity: str | None = None,
        runtime_generation: int | None = None,
    ) -> Any:
        from .weather import (
            WeatherPresentationConfig,
            WeatherPresentationModel,
            WeatherPresentationStyle,
        )

        config = WeatherPresentationConfig.from_widgets_mapping(widgets_config)
        style = WeatherPresentationStyle.project(config, shadow_values)
        return WeatherPresentationModel(config, style)

    def build(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        host: OrdinaryWidgetPresentationHost,
        geometry: OverlayWidgetGeometry,
        display_bounds: OverlayWidgetGeometry,
        display_identity: str,
        shadow_values: Mapping[str, object],
        runtime_manager: Any,
        runtime_generation: int | None = None,
    ) -> BoundFamilyPresentation | None:
        from .weather import RetainedWeatherPresentation

        model = self.presentation_model(
            widget_id=widget_id,
            widgets_config=widgets_config,
            shadow_values=shadow_values,
        )
        if not _attach_runtime_service(
            runtime_manager, widget_id, model, widgets_config
        ):
            return None
        return RetainedWeatherPresentation(
            host=host,
            model=model,
            geometry=geometry,
            on_settings_requested=self._on_settings_requested,
        )


class RedditFamilyAdapter:
    """Adapter for the Reddit family (reddit/reddit2)."""

    def __init__(
        self,
        *,
        on_open_requested: Callable[[str, str], bool] | None = None,
    ) -> None:
        self._on_open_requested = on_open_requested

    @property
    def family_id(self) -> str:
        return "reddit"

    INSTANCE_IDS = ("reddit", "reddit2")

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]:
        return _enabled_from_candidates(widgets_config, self.INSTANCE_IDS)

    def presentation_component(self, widget_id: str) -> str | None:
        return "reddit" if widget_id in self.INSTANCE_IDS else None

    def presentation_card_style(self, model: Any) -> Any:
        return model.style.card_style

    def presentation_model(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        shadow_values: Mapping[str, object],
        display_identity: str | None = None,
        runtime_generation: int | None = None,
    ) -> Any:
        from .reddit import (
            RedditPresentationConfig,
            RedditPresentationModel,
            RedditPresentationStyle,
        )

        config = RedditPresentationConfig.from_widgets_mapping(
            widgets_config, widget_id=widget_id
        )
        style = RedditPresentationStyle.project(config, shadow_values)
        return RedditPresentationModel(config, style)

    def build(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        host: OrdinaryWidgetPresentationHost,
        geometry: OverlayWidgetGeometry,
        display_bounds: OverlayWidgetGeometry,
        display_identity: str,
        shadow_values: Mapping[str, object],
        runtime_manager: Any,
        runtime_generation: int | None = None,
    ) -> BoundFamilyPresentation | None:
        from .reddit import RetainedRedditPresentation

        model = self.presentation_model(
            widget_id=widget_id,
            widgets_config=widgets_config,
            shadow_values=shadow_values,
        )
        if not _attach_runtime_service(
            runtime_manager, widget_id, model, widgets_config
        ):
            return None
        open_callback = None
        if self._on_open_requested is not None:
            open_callback = (
                lambda url, wid=widget_id: bool(
                    self._on_open_requested(wid, str(url))
                )
            )
        return RetainedRedditPresentation(
            host=host,
            model=model,
            geometry=geometry,
            on_open_requested=open_callback,
        )


class FeedFamilyAdapter:
    """Adapter for the bounded general Feeds family.

    Every CUSTOM slot and NEWS category runs through this one adapter and the
    same retained presentation; the shared Feed runtime owner deduplicates
    identical endpoints.
    """

    def __init__(
        self,
        *,
        on_open_requested: Callable[[str, str], bool] | None = None,
    ) -> None:
        self._on_open_requested = on_open_requested

    @property
    def family_id(self) -> str:
        return "feeds"

    def presentation_component(self, widget_id: str) -> str | None:
        from core.feeds.config import FEED_WIDGET_IDS

        return "feeds" if widget_id in FEED_WIDGET_IDS else None

    def presentation_card_style(self, model: Any) -> Any:
        return model.style.card_style

    def presentation_model(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        shadow_values: Mapping[str, object],
        display_identity: str | None = None,
        runtime_generation: int | None = None,
    ) -> Any:
        from .feeds import (
            FeedPresentationConfig,
            FeedPresentationModel,
            FeedPresentationStyle,
        )

        config = FeedPresentationConfig.from_widgets_mapping(
            widgets_config, widget_id=widget_id
        )
        style = FeedPresentationStyle.project(config, shadow_values)
        return FeedPresentationModel(
            config, style, runtime_generation=runtime_generation
        )

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]:
        from core.feeds.config import FEED_WIDGET_IDS, feed_widget_config

        admitted: list[str] = []
        for widget_id in FEED_WIDGET_IDS:
            values = widgets_config.get(widget_id, {})
            if not isinstance(values, Mapping):
                values = {}
            config = feed_widget_config(widget_id, values)
            # An enabled but unconfigured card (no URL, no provider) does not
            # present a dead card and does not instantiate any Feed runtime owner.
            if config.enabled and config.configured:
                admitted.append(widget_id)
        return tuple(admitted)

    def build(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        host: OrdinaryWidgetPresentationHost,
        geometry: OverlayWidgetGeometry,
        display_bounds: OverlayWidgetGeometry,
        display_identity: str,
        shadow_values: Mapping[str, object],
        runtime_manager: Any,
        runtime_generation: int | None = None,
    ) -> BoundFamilyPresentation | None:
        from .feeds import RetainedFeedPresentation

        model = self.presentation_model(
            widget_id=widget_id,
            widgets_config=widgets_config,
            shadow_values=shadow_values,
            runtime_generation=runtime_generation,
        )
        if not _attach_runtime_service(
            runtime_manager, widget_id, model, widgets_config
        ):
            return None
        open_callback = None
        if self._on_open_requested is not None:
            open_callback = (
                lambda url, wid=widget_id: bool(
                    self._on_open_requested(wid, str(url))
                )
            )
        return RetainedFeedPresentation(
            host=host,
            model=model,
            geometry=geometry,
            on_open_requested=open_callback,
        )


class GmailFamilyAdapter:
    """Adapter for the single-instance Gmail family."""

    def __init__(
        self,
        *,
        on_open_inbox_requested: Callable[[], bool] | None = None,
        on_browser_opened: Callable[[], object] | None = None,
        on_auth_requested: Callable[[], bool] | None = None,
    ) -> None:
        self._on_open_inbox_requested = on_open_inbox_requested
        self._on_browser_opened = on_browser_opened
        self._on_auth_requested = on_auth_requested

    @property
    def family_id(self) -> str:
        return "gmail"

    INSTANCE_IDS = ("gmail",)

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]:
        return _enabled_from_candidates(widgets_config, self.INSTANCE_IDS)

    def presentation_component(self, widget_id: str) -> str | None:
        return "gmail" if widget_id in self.INSTANCE_IDS else None

    def presentation_card_style(self, model: Any) -> Any:
        return model.style.card_style

    def presentation_model(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        shadow_values: Mapping[str, object],
        display_identity: str | None = None,
        runtime_generation: int | None = None,
    ) -> Any:
        from .gmail import (
            GmailPresentationConfig,
            GmailPresentationModel,
            GmailPresentationStyle,
        )

        config = GmailPresentationConfig.from_widgets_mapping(widgets_config)
        style = GmailPresentationStyle.project(config, shadow_values)
        return GmailPresentationModel(
            config, style, runtime_generation=runtime_generation
        )

    def build(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        host: OrdinaryWidgetPresentationHost,
        geometry: OverlayWidgetGeometry,
        display_bounds: OverlayWidgetGeometry,
        display_identity: str,
        shadow_values: Mapping[str, object],
        runtime_manager: Any,
        runtime_generation: int | None = None,
    ) -> BoundFamilyPresentation | None:
        from .gmail import RetainedGmailPresentation

        model = self.presentation_model(
            widget_id=widget_id,
            widgets_config=widgets_config,
            shadow_values=shadow_values,
            runtime_generation=runtime_generation,
        )
        if not _attach_runtime_service(
            runtime_manager, widget_id, model, widgets_config
        ):
            return None
        return RetainedGmailPresentation(
            host=host,
            model=model,
            geometry=geometry,
            on_open_inbox_requested=self._on_open_inbox_requested,
            on_browser_opened=self._on_browser_opened,
            on_auth_requested=self._on_auth_requested,
        )


class AchievementPulseFamilyAdapter:
    """Adapter for the Achievement Pulse card (Steam capability family)."""

    def __init__(
        self,
        *,
        on_steam_action_requested: Callable[[str, str, str], bool] | None = None,
    ) -> None:
        self._on_steam_action_requested = on_steam_action_requested

    @property
    def family_id(self) -> str:
        return "steam"

    INSTANCE_IDS = ("achievement_pulse",)

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]:
        return _enabled_from_candidates(widgets_config, self.INSTANCE_IDS)

    def presentation_component(self, widget_id: str) -> str | None:
        return "achievement_pulse" if widget_id in self.INSTANCE_IDS else None

    def presentation_card_style(self, model: Any) -> Any:
        return model.style.card_style

    def presentation_model(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        shadow_values: Mapping[str, object],
        display_identity: str | None = None,
        runtime_generation: int | None = None,
    ) -> Any:
        from .achievement_pulse import (
            AchievementPulsePresentationConfig,
            AchievementPulsePresentationModel,
            AchievementPulsePresentationStyle,
        )

        config = AchievementPulsePresentationConfig.from_widgets_mapping(
            widgets_config
        )
        style = AchievementPulsePresentationStyle.project(config, shadow_values)
        return AchievementPulsePresentationModel(config, style)

    def build(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        host: OrdinaryWidgetPresentationHost,
        geometry: OverlayWidgetGeometry,
        display_bounds: OverlayWidgetGeometry,
        display_identity: str,
        shadow_values: Mapping[str, object],
        runtime_manager: Any,
        runtime_generation: int | None = None,
    ) -> BoundFamilyPresentation | None:
        from .achievement_pulse import RetainedAchievementPulsePresentation

        model = self.presentation_model(
            widget_id=widget_id,
            widgets_config=widgets_config,
            shadow_values=shadow_values,
        )
        if not _attach_runtime_service(
            runtime_manager, widget_id, model, widgets_config
        ):
            return None
        action_callback = None
        if self._on_steam_action_requested is not None:
            action_callback = lambda kind, target, wid=widget_id: bool(
                self._on_steam_action_requested(wid, str(kind), str(target))
            )
        return RetainedAchievementPulsePresentation(
            host=host,
            model=model,
            geometry=geometry,
            on_steam_action_requested=action_callback,
        )


class GamesYouFollowFamilyAdapter:
    """One enabled Steam news card; its generation-shared source stays neutral."""

    def __init__(self, *, on_steam_action_requested: Callable[[str, str, str], bool] | None = None) -> None:
        self._on_steam_action_requested = on_steam_action_requested

    @property
    def family_id(self) -> str:
        return "steam"

    INSTANCE_IDS = ("steam_progress",)

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]:
        return _enabled_from_candidates(widgets_config, self.INSTANCE_IDS)

    def presentation_component(self, widget_id: str) -> str | None:
        return "steam_progress" if widget_id in self.INSTANCE_IDS else None

    def presentation_card_style(self, model: Any) -> Any:
        return model.card_style

    def presentation_model(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        shadow_values: Mapping[str, object],
        display_identity: str | None = None,
        runtime_generation: int | None = None,
    ) -> Any:
        from .games_you_follow import (
            FollowedPresentationConfig,
            GamesYouFollowPresentationModel,
            followed_visual_style,
        )

        return GamesYouFollowPresentationModel(
            FollowedPresentationConfig.from_widgets_mapping(widgets_config),
            runtime_generation=runtime_generation,
            visual_style=followed_visual_style(widgets_config, shadow_values),
            widgets=widgets_config,
        )

    def build(
        self, *, widget_id: str, widgets_config: Mapping[str, object],
        host: OrdinaryWidgetPresentationHost, geometry: OverlayWidgetGeometry,
        display_bounds: OverlayWidgetGeometry, display_identity: str,
        shadow_values: Mapping[str, object], runtime_manager: Any,
        runtime_generation: int | None = None,
    ) -> BoundFamilyPresentation | None:
        from .games_you_follow import RetainedGamesYouFollowPresentation

        model = self.presentation_model(
            widget_id=widget_id, widgets_config=widgets_config,
            shadow_values=shadow_values, runtime_generation=runtime_generation,
        )
        if not _attach_runtime_service(runtime_manager, widget_id, model, widgets_config):
            model.retire()
            return None
        try:
            return RetainedGamesYouFollowPresentation(
                host=host, model=model, geometry=geometry,
                card_style=self.presentation_card_style(model),
                on_steam_action_requested=(
                    (lambda kind, target, wid=widget_id: bool(
                        self._on_steam_action_requested(wid, kind, target)
                    )) if self._on_steam_action_requested is not None else None
                ),
            )
        except Exception:
            runtime_manager.retire_widget_service(widget_id)
            model.retire()
            raise


class AbandonmentIssuesFamilyAdapter:
    """Adapter for the Abandonment Issues card (Steam capability family)."""

    def __init__(
        self,
        *,
        on_steam_action_requested: Callable[[str, str, str], bool] | None = None,
    ) -> None:
        self._on_steam_action_requested = on_steam_action_requested

    @property
    def family_id(self) -> str:
        return "steam"

    INSTANCE_IDS = ("abandonment_issues",)

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]:
        return _enabled_from_candidates(widgets_config, self.INSTANCE_IDS)

    def presentation_component(self, widget_id: str) -> str | None:
        return "abandonment_issues" if widget_id in self.INSTANCE_IDS else None

    def presentation_card_style(self, model: Any) -> Any:
        return model.style.card_style

    def presentation_model(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        shadow_values: Mapping[str, object],
        display_identity: str | None = None,
        runtime_generation: int | None = None,
    ) -> Any:
        from .abandonment_issues import (
            AbandonmentIssuesPresentationConfig,
            AbandonmentIssuesPresentationModel,
            AbandonmentIssuesPresentationStyle,
        )

        config = AbandonmentIssuesPresentationConfig.from_widgets_mapping(
            widgets_config
        )
        style = AbandonmentIssuesPresentationStyle.project(config, shadow_values)
        return AbandonmentIssuesPresentationModel(config, style)

    def build(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        host: OrdinaryWidgetPresentationHost,
        geometry: OverlayWidgetGeometry,
        display_bounds: OverlayWidgetGeometry,
        display_identity: str,
        shadow_values: Mapping[str, object],
        runtime_manager: Any,
        runtime_generation: int | None = None,
    ) -> BoundFamilyPresentation | None:
        from .abandonment_issues import RetainedAbandonmentIssuesPresentation

        model = self.presentation_model(
            widget_id=widget_id,
            widgets_config=widgets_config,
            shadow_values=shadow_values,
        )
        if not _attach_runtime_service(
            runtime_manager, widget_id, model, widgets_config
        ):
            return None
        action_callback = None
        if self._on_steam_action_requested is not None:
            action_callback = lambda kind, target, wid=widget_id: bool(
                self._on_steam_action_requested(wid, str(kind), str(target))
            )
        return RetainedAbandonmentIssuesPresentation(
            host=host,
            model=model,
            geometry=geometry,
            on_steam_action_requested=action_callback,
        )


class FriendPulseFamilyAdapter:
    """Adapter for the normally available, shared-source Steam Friend Pulse card."""

    def __init__(
        self,
        *,
        on_steam_action_requested: Callable[[str, str, str], bool] | None = None,
    ) -> None:
        self._on_steam_action_requested = on_steam_action_requested

    @property
    def family_id(self) -> str:
        return "steam"

    INSTANCE_IDS = ("friend_pulse",)

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]:
        shared = widgets_config.get("steam", {})
        if not isinstance(shared, Mapping):
            shared = {}
        default_enabled = bool(require_canonical_default("widgets.steam.enabled"))
        if not _enabled_flag(shared.get("enabled", default_enabled), default_enabled):
            return ()
        return _enabled_from_candidates(widgets_config, self.INSTANCE_IDS)

    def presentation_component(self, widget_id: str) -> str | None:
        return "friend_pulse" if widget_id in self.INSTANCE_IDS else None

    def presentation_card_style(self, model: Any) -> Any:
        return model.style.card_style

    def presentation_model(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        shadow_values: Mapping[str, object],
        display_identity: str | None = None,
        runtime_generation: int | None = None,
    ) -> Any:
        from .friend_pulse import (
            FriendPulsePresentationConfig,
            FriendPulsePresentationModel,
            FriendPulsePresentationStyle,
        )

        config = FriendPulsePresentationConfig.from_widgets_mapping(widgets_config)
        style = FriendPulsePresentationStyle.project(config, shadow_values)
        return FriendPulsePresentationModel(
            config,
            style,
            runtime_generation=runtime_generation,
        )

    def build(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        host: OrdinaryWidgetPresentationHost,
        geometry: OverlayWidgetGeometry,
        display_bounds: OverlayWidgetGeometry,
        display_identity: str,
        shadow_values: Mapping[str, object],
        runtime_manager: Any,
        runtime_generation: int | None = None,
    ) -> BoundFamilyPresentation | None:
        from .friend_pulse import RetainedFriendPulsePresentation

        model = self.presentation_model(
            widget_id=widget_id,
            widgets_config=widgets_config,
            shadow_values=shadow_values,
            runtime_generation=runtime_generation,
        )
        if not _attach_runtime_service(
            runtime_manager, widget_id, model, widgets_config
        ):
            return None
        action_callback = None
        if self._on_steam_action_requested is not None:
            action_callback = lambda kind, target, wid=widget_id: bool(
                self._on_steam_action_requested(wid, str(kind), str(target))
            )
        try:
            return RetainedFriendPulsePresentation(
                host=host,
                model=model,
                geometry=geometry,
                on_steam_action_requested=action_callback,
            )
        except Exception:
            runtime_manager.retire_widget_service(widget_id)
            raise


class SystemStatsFamilyAdapter:
    """Adapter for the normally available whole-system System Stats card."""

    @property
    def family_id(self) -> str:
        return "system_stats"

    INSTANCE_IDS = ("system_stats",)

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]:
        return _enabled_from_candidates(widgets_config, self.INSTANCE_IDS)

    def presentation_component(self, widget_id: str) -> str | None:
        return "system_stats" if widget_id in self.INSTANCE_IDS else None

    def presentation_card_style(self, model: Any) -> Any:
        return model.style.card_style

    def presentation_model(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        shadow_values: Mapping[str, object],
        display_identity: str | None = None,
        runtime_generation: int | None = None,
    ) -> Any:
        from .system_stats import (
            SystemStatsPresentationConfig,
            SystemStatsPresentationModel,
            SystemStatsPresentationStyle,
        )

        config = SystemStatsPresentationConfig.from_widgets_mapping(widgets_config)
        style = SystemStatsPresentationStyle.project(config, shadow_values)
        return SystemStatsPresentationModel(
            config,
            style,
            runtime_generation=runtime_generation,
        )

    def build(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        host: OrdinaryWidgetPresentationHost,
        geometry: OverlayWidgetGeometry,
        display_bounds: OverlayWidgetGeometry,
        display_identity: str,
        shadow_values: Mapping[str, object],
        runtime_manager: Any,
        runtime_generation: int | None = None,
    ) -> BoundFamilyPresentation | None:
        from .system_stats import RetainedSystemStatsPresentation

        model = self.presentation_model(
            widget_id=widget_id,
            widgets_config=widgets_config,
            shadow_values=shadow_values,
            runtime_generation=runtime_generation,
        )
        if not _attach_runtime_service(
            runtime_manager, widget_id, model, widgets_config
        ):
            return None
        try:
            return RetainedSystemStatsPresentation(
                host=host,
                model=model,
                geometry=geometry,
            )
        except Exception:
            runtime_manager.retire_widget_service(widget_id)
            raise


class SystemAudioOSDFamilyAdapter:
    """Opt-in retained OSD consuming only the shared system-audio service."""

    @property
    def family_id(self) -> str:
        return "system_audio_osd"

    INSTANCE_IDS = ("system_audio_osd",)

    def enabled_instance_ids(self, widgets_config: Mapping[str, object]) -> tuple[str, ...]:
        return _enabled_from_candidates(widgets_config, self.INSTANCE_IDS)

    def presentation_component(self, widget_id: str) -> str | None:
        return "system_audio_osd" if widget_id in self.INSTANCE_IDS else None

    def presentation_card_style(self, model: Any) -> Any:
        return model.config.card_style

    def presentation_model(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        shadow_values: Mapping[str, object],
        display_identity: str | None = None,
        runtime_generation: int | None = None,
    ) -> Any:
        from .system_audio_osd import SystemAudioOSDConfig, SystemAudioOSDPresentationModel

        return SystemAudioOSDPresentationModel(
            SystemAudioOSDConfig.from_widgets_mapping(widgets_config),
            runtime_generation=runtime_generation,
        )

    def build(self, *, widget_id: str, widgets_config: Mapping[str, object],
              host: OrdinaryWidgetPresentationHost, geometry: OverlayWidgetGeometry,
              display_bounds: OverlayWidgetGeometry, display_identity: str,
              shadow_values: Mapping[str, object], runtime_manager: Any,
              runtime_generation: int | None = None) -> BoundFamilyPresentation | None:
        from .system_audio_osd import RetainedSystemAudioOSDPresentation
        model = self.presentation_model(
            widget_id=widget_id, widgets_config=widgets_config,
            shadow_values=shadow_values, runtime_generation=runtime_generation,
        )
        if not _attach_runtime_service(runtime_manager, widget_id, model, widgets_config):
            model.retire()
            return None
        try:
            return RetainedSystemAudioOSDPresentation(
                host=host, model=model, geometry=geometry)
        except Exception:
            runtime_manager.retire_widget_service(widget_id)
            model.retire()
            raise


class MediaFamilyAdapter:
    """Adapter for the single-card Media family (media + volume + mute leases).

    The Media family presents one card (``media``) that consumes three neutral
    runtime services owned by the single manager: the transport/artwork lease
    (``media``), the volume lease (``spotify_volume``) and the system-mute lease
    (``mute_button``). The card fails closed if any required lease cannot build.
    """

    @property
    def family_id(self) -> str:
        return "media"

    INSTANCE_IDS = ("media",)

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]:
        return _enabled_from_candidates(widgets_config, self.INSTANCE_IDS)

    def presentation_component(self, widget_id: str) -> str | None:
        return "media" if widget_id in self.INSTANCE_IDS else None

    def presentation_card_style(self, model: Any) -> Any:
        return model.style.card_style

    def presentation_model(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        shadow_values: Mapping[str, object],
        display_identity: str | None = None,
        runtime_generation: int | None = None,
        artwork_provider: Any = None,
    ) -> Any:
        """Artwork only resolves pixels; a detached model may measure without one."""

        from .media import (
            MediaPresentationConfig,
            MediaPresentationModel,
            MediaPresentationStyle,
        )

        config = MediaPresentationConfig.from_widgets_mapping(widgets_config)
        style = MediaPresentationStyle.project(config, shadow_values)
        return MediaPresentationModel(
            config,
            style,
            artwork_provider,
            runtime_generation=runtime_generation,
        )

    def build(
        self,
        *,
        widget_id: str,
        widgets_config: Mapping[str, object],
        host: OrdinaryWidgetPresentationHost,
        geometry: OverlayWidgetGeometry,
        display_bounds: OverlayWidgetGeometry,
        display_identity: str,
        shadow_values: Mapping[str, object],
        runtime_manager: Any,
        runtime_generation: int | None = None,
    ) -> BoundFamilyPresentation | None:
        from core.media.media_native_trace import trace_media_native_stage
        from rendering.quick.media_artwork import MediaArtworkImageProvider

        from .media import RetainedMediaPresentation

        # H1 diagnostic: bracket the screen's Media-family construction so the
        # replacement-generation native termination has a precise last-stage
        # timeline (generation + thread) at every native boundary below.
        trace_media_native_stage(
            component="media_family",
            stage="model_construct_begin",
            generation=runtime_generation,
            screen=display_identity,
        )
        # Publish decoded artwork into the SAME provider the scene factory
        # registered on this host's QML engine, so an emitted
        # image://mediaartwork/<id> URL resolves against the instance that owns
        # the image. A private per-card provider (the prior bug) decoded real
        # artwork the engine's registered provider never saw, so the artwork box
        # stayed empty. Fail the card closed if the engine provider is absent
        # rather than silently building an unresolvable card.
        artwork_provider = host.registered_image_provider(
            MediaArtworkImageProvider.provider_id
        )
        if not isinstance(artwork_provider, MediaArtworkImageProvider):
            logger.debug(
                "[FAMILY_BINDER] Engine-registered Media artwork provider "
                "unavailable; failing Media card closed",
            )
            return None
        model = self.presentation_model(
            widget_id=widget_id,
            widgets_config=widgets_config,
            shadow_values=shadow_values,
            runtime_generation=runtime_generation,
            artwork_provider=artwork_provider,
        )
        trace_media_native_stage(
            component="media_family",
            stage="model_construct_complete",
            generation=runtime_generation,
            screen=display_identity,
        )
        # The one media card consumes three neutral leases, each injected into
        # the same model by its own service spec. All are required: a missing
        # lease fails the card closed rather than presenting a half-wired card.
        for lease_widget_id in ("media", "spotify_volume", "mute_button"):
            trace_media_native_stage(
                component=lease_widget_id,
                stage="lease_attach_begin",
                generation=runtime_generation,
                screen=display_identity,
            )
            attached = _attach_runtime_service(
                runtime_manager, lease_widget_id, model, widgets_config
            )
            trace_media_native_stage(
                component=lease_widget_id,
                stage="lease_attach_complete",
                generation=runtime_generation,
                screen=display_identity,
                detail="ok=%s" % attached,
            )
            if not attached:
                # Retire any leases already owned for this card before failing
                # closed, so a partial build never leaves an orphaned lease.
                for owned in ("media", "spotify_volume", "mute_button"):
                    runtime_manager.retire_widget_service(owned)
                return None
        trace_media_native_stage(
            component="media_family",
            stage="retained_item_construct_begin",
            generation=runtime_generation,
            screen=display_identity,
        )
        retained = RetainedMediaPresentation(
            host=host, model=model, geometry=geometry
        )
        trace_media_native_stage(
            component="media_family",
            stage="retained_item_construct_complete",
            generation=runtime_generation,
            screen=display_identity,
        )
        return retained


def default_ordinary_family_adapters(
    *,
    clock_mode_toggle: Callable[
        [str, str, str, OverlayWidgetGeometry, Mapping[str, object]], None
    ] | None = None,
    reddit_open_requested: Callable[[str, str], bool] | None = None,
    feed_open_requested: Callable[[str, str], bool] | None = None,
    steam_open_requested: Callable[[str, str, str], bool] | None = None,
    gmail_open_inbox_requested: Callable[[], bool] | None = None,
    gmail_browser_opened: Callable[[], object] | None = None,
    settings_target_requested: Callable[[str], bool] | None = None,
) -> tuple[OrdinaryFamilyAdapter, ...]:
    """Return the explicit ordered ordinary-family adapters currently wired.

    Product semantic actions are injected only into the two families that need
    them. The adapters remain lifetime-neutral and hold no DisplayManager owner;
    production supplies weak callbacks. Order is deterministic build order and
    does not imply Z-order, which the host owns.
    """

    return (
        ClockFamilyAdapter(on_mode_toggle=clock_mode_toggle),
        WeatherFamilyAdapter(on_settings_requested=settings_target_requested),
        MediaFamilyAdapter(),
        RedditFamilyAdapter(on_open_requested=reddit_open_requested),
        FeedFamilyAdapter(on_open_requested=feed_open_requested),
        GmailFamilyAdapter(
            on_open_inbox_requested=gmail_open_inbox_requested,
            on_browser_opened=gmail_browser_opened,
            on_auth_requested=(
                (lambda: bool(settings_target_requested("gmail_authorization")))
                if settings_target_requested is not None else None
            ),
        ),
        GamesYouFollowFamilyAdapter(on_steam_action_requested=steam_open_requested),
        AchievementPulseFamilyAdapter(
            on_steam_action_requested=steam_open_requested
        ),
        AbandonmentIssuesFamilyAdapter(
            on_steam_action_requested=steam_open_requested
        ),
        FriendPulseFamilyAdapter(on_steam_action_requested=steam_open_requested),
        SystemStatsFamilyAdapter(),
        SystemAudioOSDFamilyAdapter(),
    )


__all__ = [
    "AbandonmentIssuesFamilyAdapter",
    "AchievementPulseFamilyAdapter",
    "BoundFamilyPresentation",
    "ClockFamilyAdapter",
    "FeedFamilyAdapter",
    "FriendPulseFamilyAdapter",
    "GamesYouFollowFamilyAdapter",
    "GmailFamilyAdapter",
    "MediaFamilyAdapter",
    "OrdinaryFamilyAdapter",
    "OrdinaryFamilyPresentationBinder",
    "RedditFamilyAdapter",
    "SystemStatsFamilyAdapter",
    "SystemAudioOSDFamilyAdapter",
    "WeatherFamilyAdapter",
    "default_ordinary_family_adapters",
]
