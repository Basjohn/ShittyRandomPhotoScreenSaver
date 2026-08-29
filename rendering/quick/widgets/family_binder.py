"""Thin per-display ordinary-family presentation binder (H keystone).

Presentation-neutral wiring that resolves the admitted ordinary-widget family
instances for one display generation and constructs their existing
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
owner or clock. Per-instance ``enabled`` state stays distinct from family
capability effectiveness, exactly as the neutral manager contract requires.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Optional, Protocol, runtime_checkable

from core.logging.logger import get_logger

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

    The default when an instance has no explicit ``enabled`` is the canonical
    default for that id, falling back to enabled only for the first candidate
    (the base instance) so unconfigured secondary instances stay off.
    """

    from core.settings.defaults import get_default_settings

    defaults = get_default_settings().get("widgets", {})
    enabled: list[str] = []
    for index, widget_id in enumerate(candidate_ids):
        values = widgets_config.get(widget_id, {})
        if not isinstance(values, Mapping):
            values = {}
        default_values = defaults.get(widget_id, {})
        default_enabled = bool(
            default_values.get("enabled", index == 0)
            if isinstance(default_values, Mapping)
            else index == 0
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
    QWidget-owned or serviceless fallback.
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
    """

    @property
    def family_id(self) -> str: ...

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]: ...

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

    def bind(self, widgets_config: Mapping[str, object] | None) -> tuple[str, ...]:
        """Build every admitted family instance once for this display generation.

        A family is admitted only while its capability is *effective* (activated
        and every required family activated); within an admitted family, only the
        per-instance ``enabled`` instances are built. Returns the built widget
        ids in build order.
        """

        if self._retired:
            raise RuntimeError("cannot bind a retired family presentation binder")
        if self._bound_once:
            raise RuntimeError("family presentation binder already bound this generation")
        self._bound_once = True

        config: Mapping[str, object] = (
            widgets_config if isinstance(widgets_config, Mapping) else {}
        )
        for adapter in self._adapters:
            family_id = adapter.family_id
            if not self._runtime_manager.is_family_effective(config, family_id):
                continue
            for widget_id in adapter.enabled_instance_ids(config):
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
                if self._thread_manager is not None:
                    activate = getattr(retained, "activate", None)
                    if callable(activate):
                        try:
                            activate(self._thread_manager)
                        except Exception:
                            logger.debug(
                                "[FAMILY_BINDER] Failed to activate %s",
                                widget_id,
                                exc_info=True,
                            )
                self._bound.append(retained)
                self._bound_widget_ids.append(widget_id)
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

    @property
    def family_id(self) -> str:
        return "clocks"

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]:
        return _enabled_from_candidates(
            widgets_config, ("clock", "clock2", "clock3")
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
        from .clock import (
            ClockPresentationConfig,
            ClockPresentationModel,
            ClockPresentationStyle,
            RetainedClockPresentation,
        )

        config = ClockPresentationConfig.from_widgets_mapping(
            widget_id,
            widgets_config,
            display_signature=display_identity,
        )
        style = ClockPresentationStyle.project(config, shadow_values)
        model = ClockPresentationModel(config, style)
        return RetainedClockPresentation(
            host=host,
            model=model,
            geometry=geometry,
            display_bounds=display_bounds,
            display_identity=display_identity,
        )


class WeatherFamilyAdapter:
    """Adapter for the single-instance Weather family."""

    @property
    def family_id(self) -> str:
        return "weather"

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]:
        return _enabled_from_candidates(widgets_config, ("weather",))

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
        from .weather import (
            RetainedWeatherPresentation,
            WeatherPresentationConfig,
            WeatherPresentationModel,
            WeatherPresentationStyle,
        )

        config = WeatherPresentationConfig.from_widgets_mapping(widgets_config)
        style = WeatherPresentationStyle.project(config, shadow_values)
        model = WeatherPresentationModel(config, style)
        if not _attach_runtime_service(
            runtime_manager, widget_id, model, widgets_config
        ):
            return None
        return RetainedWeatherPresentation(
            host=host, model=model, geometry=geometry
        )


class RedditFamilyAdapter:
    """Adapter for the Reddit family (reddit/reddit2)."""

    @property
    def family_id(self) -> str:
        return "reddit"

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]:
        return _enabled_from_candidates(widgets_config, ("reddit", "reddit2"))

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
        from .reddit import (
            RedditPresentationConfig,
            RedditPresentationModel,
            RedditPresentationStyle,
            RetainedRedditPresentation,
        )

        config = RedditPresentationConfig.from_widgets_mapping(
            widgets_config, widget_id=widget_id
        )
        style = RedditPresentationStyle.project(config, shadow_values)
        model = RedditPresentationModel(config, style)
        if not _attach_runtime_service(
            runtime_manager, widget_id, model, widgets_config
        ):
            return None
        return RetainedRedditPresentation(
            host=host, model=model, geometry=geometry
        )


class GmailFamilyAdapter:
    """Adapter for the single-instance Gmail family."""

    @property
    def family_id(self) -> str:
        return "gmail"

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]:
        return _enabled_from_candidates(widgets_config, ("gmail",))

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
        from .gmail import (
            GmailPresentationConfig,
            GmailPresentationModel,
            GmailPresentationStyle,
            RetainedGmailPresentation,
        )

        config = GmailPresentationConfig.from_widgets_mapping(widgets_config)
        style = GmailPresentationStyle.project(config, shadow_values)
        model = GmailPresentationModel(config, style)
        if not _attach_runtime_service(
            runtime_manager, widget_id, model, widgets_config
        ):
            return None
        return RetainedGmailPresentation(
            host=host, model=model, geometry=geometry
        )


class AchievementPulseFamilyAdapter:
    """Adapter for the Achievement Pulse card (Steam capability family)."""

    @property
    def family_id(self) -> str:
        return "steam"

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]:
        return _enabled_from_candidates(widgets_config, ("achievement_pulse",))

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
        from .achievement_pulse import (
            AchievementPulsePresentationConfig,
            AchievementPulsePresentationModel,
            AchievementPulsePresentationStyle,
            RetainedAchievementPulsePresentation,
        )

        config = AchievementPulsePresentationConfig.from_widgets_mapping(
            widgets_config
        )
        style = AchievementPulsePresentationStyle.project(config, shadow_values)
        model = AchievementPulsePresentationModel(config, style)
        if not _attach_runtime_service(
            runtime_manager, widget_id, model, widgets_config
        ):
            return None
        return RetainedAchievementPulsePresentation(
            host=host, model=model, geometry=geometry
        )


class AbandonmentIssuesFamilyAdapter:
    """Adapter for the Abandonment Issues card (Steam capability family)."""

    @property
    def family_id(self) -> str:
        return "steam"

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]:
        return _enabled_from_candidates(widgets_config, ("abandonment_issues",))

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
        from .abandonment_issues import (
            AbandonmentIssuesPresentationConfig,
            AbandonmentIssuesPresentationModel,
            AbandonmentIssuesPresentationStyle,
            RetainedAbandonmentIssuesPresentation,
        )

        config = AbandonmentIssuesPresentationConfig.from_widgets_mapping(
            widgets_config
        )
        style = AbandonmentIssuesPresentationStyle.project(config, shadow_values)
        model = AbandonmentIssuesPresentationModel(config, style)
        if not _attach_runtime_service(
            runtime_manager, widget_id, model, widgets_config
        ):
            return None
        return RetainedAbandonmentIssuesPresentation(
            host=host, model=model, geometry=geometry
        )


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

    def enabled_instance_ids(
        self, widgets_config: Mapping[str, object]
    ) -> tuple[str, ...]:
        return _enabled_from_candidates(widgets_config, ("media",))

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
        from rendering.quick.media_artwork import MediaArtworkImageProvider

        from .media import (
            MediaPresentationConfig,
            MediaPresentationModel,
            MediaPresentationStyle,
            RetainedMediaPresentation,
        )

        config = MediaPresentationConfig.from_widgets_mapping(widgets_config)
        style = MediaPresentationStyle.project(config, shadow_values)
        model = MediaPresentationModel(
            config,
            style,
            MediaArtworkImageProvider(),
            runtime_generation=runtime_generation,
        )
        # The one media card consumes three neutral leases, each injected into
        # the same model by its own service spec. All are required: a missing
        # lease fails the card closed rather than presenting a half-wired card.
        for lease_widget_id in ("media", "spotify_volume", "mute_button"):
            if not _attach_runtime_service(
                runtime_manager, lease_widget_id, model, widgets_config
            ):
                # Retire any leases already owned for this card before failing
                # closed, so a partial build never leaves an orphaned lease.
                for owned in ("media", "spotify_volume", "mute_button"):
                    runtime_manager.retire_widget_service(owned)
                return None
        return RetainedMediaPresentation(
            host=host, model=model, geometry=geometry
        )


def default_ordinary_family_adapters() -> tuple[OrdinaryFamilyAdapter, ...]:
    """Return the explicit ordered ordinary-family adapters currently wired.

    Order is the deterministic build order; it does not imply Z-order, which the
    host owns.
    """

    return (
        ClockFamilyAdapter(),
        WeatherFamilyAdapter(),
        MediaFamilyAdapter(),
        RedditFamilyAdapter(),
        GmailFamilyAdapter(),
        AchievementPulseFamilyAdapter(),
        AbandonmentIssuesFamilyAdapter(),
    )


__all__ = [
    "AbandonmentIssuesFamilyAdapter",
    "AchievementPulseFamilyAdapter",
    "BoundFamilyPresentation",
    "ClockFamilyAdapter",
    "GmailFamilyAdapter",
    "MediaFamilyAdapter",
    "OrdinaryFamilyAdapter",
    "OrdinaryFamilyPresentationBinder",
    "RedditFamilyAdapter",
    "WeatherFamilyAdapter",
    "default_ordinary_family_adapters",
]
