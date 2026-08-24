"""Neutral registry of presentation-neutral runtime services per widget id (E1).

This is the family-specific knowledge boundary for E1 provider/model lifetime
ownership. ``WidgetRuntimeManager`` stays generic — it never contains a
``if widget_id == ...`` provider/presenter switchboard. Instead each widget id
that owns a presentation-neutral runtime service (provider/model/etc.) registers
a small :class:`RuntimeServiceSpec` here describing how to build, inject and
retire that service. The owner drives those specs generically.

E1 slice 2 introduced the first entry: the branded Reddit widget's post
*provider* (``core.reddit_post_provider``), which was previously constructed and
owned by the ``RedditWidget``/factory (i.e. owned merely because a QWidget
existed). Its lifetime now belongs to the neutral owner, which creates it from
canonical settings, injects it into the widget for use, and retires it on runtime
teardown independently of QWidget pixel ownership.

E1 slice 3 adds the per-instance Weather runtime-data service. It owns provider
fetch/cache/refresh/retry/request-generation lifetime while the legacy
``WeatherWidget`` remains only a prepared-state presentation consumer.

E1 slice 4 adds a separate per-card/display Abandonment runtime/model service.
It owns that Steam card's cache/source/rotation cadence and prepared state while
preserving the existing neutral ``core.steam`` cache/backend authorities. Other
Steam cards remain separate; no generic/shared Steam service is implied.

E1 slice 5 adds the distinct per-card/display Achievement Pulse runtime/model/
artwork service. Progress and Friend Pulse remain unregistered and source-inert.

E1 slice 6 adds one Media lease per display. Leases in the same runtime
generation join one family-shared owner for controller/provider, polling,
accepted state and source-resolution artwork decode; QWidget presenters retain
only their per-display projection and QPixmap/DPR work.

E1 slice 7 adds one Gmail lease per display. Leases in the same runtime
generation join one Gmail-specific shared owner for backend bootstrap
coordination, cache-first startup, polling/fetch, accepted raw-email state,
notification decisions and serialized actions. ``GmailBackend.instance()``
remains the unchanged process singleton.

E1 slice 8 adds a separate Media app-volume lease per participating display.
Those leases share one controller/target/read-write/debounce owner per runtime
generation. A second, distinct system-mute lease shares one UI-thread endpoint
state/poll/action owner. The primary Media owner remains intentionally separate.

Heavy provider implementation is imported lazily inside the build callable so a
process that never activates/creates the family does not resolve it merely
because this registry is imported.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from core.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class RuntimeServiceSpec:
    """How to build/inject/retire one widget id's presentation-neutral service.

    - ``build(widget_id, widgets_config) -> service | None`` constructs the
      service from canonical settings (no QWidget required);
    - ``inject(widget, service) -> None`` hands the built service to the runtime
      widget for consumption (the widget renders/uses it but no longer owns its
      lifetime);
    - ``retire(service) -> None`` releases the service; ``None`` when the service
      holds no releasable resources (e.g. a stateless source object);
    - ``reuse_is_valid(widget, service) -> bool`` validates that an existing
      presentation still consumes a live compatible owner before setup reuses
      it across reconciliation.
    """

    build: Callable[[str, Mapping[str, Any]], Any]
    inject: Callable[[Any, Any], None]
    retire: Optional[Callable[[Any], None]] = None
    reuse_is_valid: Optional[Callable[[Any, Any], bool]] = None


def _widget_is_active(widget: Any) -> bool:
    getter = getattr(widget, "is_lifecycle_active", None)
    if not callable(getter):
        return False
    try:
        return bool(getter())
    except Exception:
        # Reuse validation is a fail-closed boundary.  An unresolvable
        # lifecycle state must not make a stopped owner look safely inactive.
        return True


def _service_is_retired(service: Any) -> bool:
    getter = getattr(service, "is_retired", None)
    if not callable(getter):
        return False
    try:
        return bool(getter())
    except Exception:
        return True


def _service_is_running(service: Any) -> bool:
    getter = getattr(service, "is_running", None)
    if not callable(getter):
        return False
    try:
        return bool(getter())
    except Exception:
        return False


def _resolve_reddit_provider_id(
    widget_id: str, widgets_config: Mapping[str, Any]
) -> Any:
    """Resolve the configured provider id, honoring reddit2 family inheritance.

    Mirrors the previous factory resolution: a member's own ``provider`` wins;
    ``reddit2`` otherwise inherits the ``reddit`` family provider; absence
    normalizes to the RSS default inside ``build_reddit_post_provider``.
    """
    cfg = widgets_config.get(widget_id, {}) if isinstance(widgets_config, Mapping) else {}
    provider_id = cfg.get("provider") if isinstance(cfg, Mapping) else None
    if provider_id is None and widget_id == "reddit2":
        base = widgets_config.get("reddit", {}) if isinstance(widgets_config, Mapping) else {}
        if isinstance(base, Mapping):
            provider_id = base.get("provider")
    return provider_id


def _build_reddit_service(widget_id: str, widgets_config: Mapping[str, Any]) -> Any:
    from core.reddit_post_provider import build_reddit_post_provider

    provider_id = _resolve_reddit_provider_id(widget_id, widgets_config)
    return build_reddit_post_provider(provider_id)


def _inject_reddit_service(widget: Any, service: Any) -> None:
    setter = getattr(widget, "set_post_provider", None)
    if not callable(setter):
        # A required service could not be handed to the widget. Raise so the owner
        # fails closed rather than leaving a runtime-managed widget with no
        # neutral provider (or on a QWidget-owned default).
        raise AttributeError(
            "runtime widget cannot accept post provider (missing set_post_provider)"
        )
    setter(service)


def _reddit_service_reuse_is_valid(widget: Any, service: Any) -> bool:
    return getattr(widget, "_post_provider", None) is service


_REDDIT_SERVICE_SPEC = RuntimeServiceSpec(
    build=_build_reddit_service,
    inject=_inject_reddit_service,
    retire=None,  # RedditPostProvider holds no releasable resources.
    reuse_is_valid=_reddit_service_reuse_is_valid,
)


def _build_weather_service(widget_id: str, widgets_config: Mapping[str, Any]) -> Any:
    # Lazy import preserves deactivated-family import dormancy. Construction is
    # provider/network/filesystem inert; the service starts work only after
    # injection and the normal widget start boundary.
    from widgets.weather_runtime import WeatherRuntimeService

    return WeatherRuntimeService()


def _inject_weather_service(widget: Any, service: Any) -> None:
    setter = getattr(widget, "set_runtime_service", None)
    if not callable(setter):
        raise AttributeError(
            "runtime widget cannot accept Weather service (missing set_runtime_service)"
        )
    setter(service)


def _retire_weather_service(service: Any) -> None:
    retire = getattr(service, "retire", None)
    if not callable(retire):
        raise AttributeError("Weather runtime service has no retire method")
    retire()


def _weather_service_reuse_is_valid(widget: Any, service: Any) -> bool:
    if getattr(widget, "_runtime_service", None) is not service:
        return False
    if _service_is_retired(service):
        return False
    # Missing-location Weather is intentionally active with a stopped service.
    has_location = bool(str(getattr(widget, "_location", "") or "").strip())
    return not (_widget_is_active(widget) and has_location) or _service_is_running(
        service
    )


_WEATHER_SERVICE_SPEC = RuntimeServiceSpec(
    build=_build_weather_service,
    inject=_inject_weather_service,
    retire=_retire_weather_service,
    reuse_is_valid=_weather_service_reuse_is_valid,
)


def _build_abandonment_service(
    widget_id: str, widgets_config: Mapping[str, Any]
) -> Any:
    # Construction is provider/network/filesystem inert. Configuration is
    # synchronized by the presentation consumer during injection so the factory's
    # canonical normalization remains the single settings interpretation.
    from widgets.steam_abandonment_runtime import AbandonmentRuntimeService

    return AbandonmentRuntimeService()


def _inject_abandonment_service(widget: Any, service: Any) -> None:
    setter = getattr(widget, "set_runtime_service", None)
    if not callable(setter):
        raise AttributeError(
            "runtime widget cannot accept Abandonment service "
            "(missing set_runtime_service)"
        )
    setter(service)


def _retire_abandonment_service(service: Any) -> None:
    retire = getattr(service, "retire", None)
    if not callable(retire):
        raise AttributeError("Abandonment runtime service has no retire method")
    retire()


def _abandonment_service_reuse_is_valid(widget: Any, service: Any) -> bool:
    if getattr(widget, "_runtime_service", None) is not service:
        return False
    if _service_is_retired(service):
        return False
    return not _widget_is_active(widget) or _service_is_running(service)


_ABANDONMENT_SERVICE_SPEC = RuntimeServiceSpec(
    build=_build_abandonment_service,
    inject=_inject_abandonment_service,
    retire=_retire_abandonment_service,
    reuse_is_valid=_abandonment_service_reuse_is_valid,
)


def _build_achievement_service(
    widget_id: str, widgets_config: Mapping[str, Any]
) -> Any:
    # Construction is provider/network/filesystem inert. The temporary
    # presenter synchronizes already-normalized factory configuration during
    # injection; start remains the first work-admission boundary.
    from widgets.steam_achievement_runtime import AchievementPulseRuntimeService

    return AchievementPulseRuntimeService()


def _inject_achievement_service(widget: Any, service: Any) -> None:
    setter = getattr(widget, "set_achievement_runtime_service", None)
    if not callable(setter):
        raise AttributeError(
            "runtime widget cannot accept Achievement Pulse service "
            "(missing set_achievement_runtime_service)"
        )
    setter(service)


def _retire_achievement_service(service: Any) -> None:
    retire = getattr(service, "retire", None)
    if not callable(retire):
        raise AttributeError("Achievement Pulse runtime service has no retire method")
    retire()


def _achievement_service_reuse_is_valid(widget: Any, service: Any) -> bool:
    if getattr(widget, "_achievement_runtime_service", None) is not service:
        return False
    if _service_is_retired(service):
        return False
    return not _widget_is_active(widget) or _service_is_running(service)


_ACHIEVEMENT_SERVICE_SPEC = RuntimeServiceSpec(
    build=_build_achievement_service,
    inject=_inject_achievement_service,
    retire=_retire_achievement_service,
    reuse_is_valid=_achievement_service_reuse_is_valid,
)


def _build_media_service(widget_id: str, widgets_config: Mapping[str, Any]) -> Any:
    from core.settings.models import MediaWidgetSettings
    from widgets.media_runtime import MediaRuntimeService

    config = (
        widgets_config.get(widget_id, {})
        if isinstance(widgets_config, Mapping)
        else {}
    )
    model = MediaWidgetSettings.from_mapping(
        config if isinstance(config, Mapping) else {}
    )
    return MediaRuntimeService(provider=model.provider, shared=True)


def _inject_media_service(widget: Any, service: Any) -> None:
    setter = getattr(widget, "set_runtime_service", None)
    if not callable(setter):
        raise AttributeError(
            "runtime widget cannot accept Media service (missing set_runtime_service)"
        )
    setter(service)


def _retire_media_service(service: Any) -> None:
    retire = getattr(service, "retire", None)
    if not callable(retire):
        raise AttributeError("Media runtime service has no retire method")
    retire()


def _media_service_reuse_is_valid(widget: Any, service: Any) -> bool:
    if getattr(widget, "_runtime_service", None) is not service:
        return False
    if _service_is_retired(service):
        return False
    return not _widget_is_active(widget) or _service_is_running(service)


_MEDIA_SERVICE_SPEC = RuntimeServiceSpec(
    build=_build_media_service,
    inject=_inject_media_service,
    retire=_retire_media_service,
    reuse_is_valid=_media_service_reuse_is_valid,
)


def _build_gmail_service(widget_id: str, widgets_config: Mapping[str, Any]) -> Any:
    from widgets.gmail_runtime import GmailRuntimeConfig, GmailRuntimeService

    config = (
        widgets_config.get(widget_id, {})
        if isinstance(widgets_config, Mapping)
        else {}
    )
    model = GmailRuntimeConfig.from_mapping(
        config if isinstance(config, Mapping) else {}
    )
    return GmailRuntimeService(config=model, shared=True)


def _inject_gmail_service(widget: Any, service: Any) -> None:
    setter = getattr(widget, "set_runtime_service", None)
    if not callable(setter):
        raise AttributeError(
            "runtime widget cannot accept Gmail service (missing set_runtime_service)"
        )
    setter(service)


def _retire_gmail_service(service: Any) -> None:
    retire = getattr(service, "retire", None)
    if not callable(retire):
        raise AttributeError("Gmail runtime service has no retire method")
    retire()


def _gmail_service_reuse_is_valid(widget: Any, service: Any) -> bool:
    if getattr(widget, "_runtime_service", None) is not service:
        return False
    if _service_is_retired(service):
        return False
    if getattr(service, "shared_owner", None) is None:
        return False
    return not _widget_is_active(widget) or _service_is_running(service)


_GMAIL_SERVICE_SPEC = RuntimeServiceSpec(
    build=_build_gmail_service,
    inject=_inject_gmail_service,
    retire=_retire_gmail_service,
    reuse_is_valid=_gmail_service_reuse_is_valid,
)


def _build_media_volume_service(
    widget_id: str, widgets_config: Mapping[str, Any]
) -> Any:
    from core.settings.models import MediaWidgetSettings
    from widgets.media_volume_runtime import MediaVolumeRuntimeService

    config = (
        widgets_config.get("media", {})
        if isinstance(widgets_config, Mapping)
        else {}
    )
    model = MediaWidgetSettings.from_mapping(
        config if isinstance(config, Mapping) else {}
    )
    return MediaVolumeRuntimeService(provider=model.provider, shared=True)


def _inject_media_volume_service(widget: Any, service: Any) -> None:
    setter = getattr(widget, "set_runtime_service", None)
    if not callable(setter):
        raise AttributeError(
            "runtime widget cannot accept Media volume service "
            "(missing set_runtime_service)"
        )
    setter(service)


def _retire_media_volume_service(service: Any) -> None:
    retire = getattr(service, "retire", None)
    if not callable(retire):
        raise AttributeError("Media volume runtime service has no retire method")
    retire()


def _media_volume_service_reuse_is_valid(widget: Any, service: Any) -> bool:
    if getattr(widget, "_runtime_service", None) is not service:
        return False
    if _service_is_retired(service):
        return False
    if getattr(service, "shared_owner", None) is None:
        return False
    return not _widget_is_active(widget) or _service_is_running(service)


_MEDIA_VOLUME_SERVICE_SPEC = RuntimeServiceSpec(
    build=_build_media_volume_service,
    inject=_inject_media_volume_service,
    retire=_retire_media_volume_service,
    reuse_is_valid=_media_volume_service_reuse_is_valid,
)


def _build_system_mute_service(
    widget_id: str, widgets_config: Mapping[str, Any]
) -> Any:
    from widgets.system_mute_runtime import SystemMuteRuntimeService

    return SystemMuteRuntimeService(shared=True)


def _inject_system_mute_service(widget: Any, service: Any) -> None:
    setter = getattr(widget, "set_runtime_service", None)
    if not callable(setter):
        raise AttributeError(
            "runtime widget cannot accept system-mute service "
            "(missing set_runtime_service)"
        )
    setter(service)


def _retire_system_mute_service(service: Any) -> None:
    retire = getattr(service, "retire", None)
    if not callable(retire):
        raise AttributeError("system-mute runtime service has no retire method")
    retire()


def _system_mute_service_reuse_is_valid(widget: Any, service: Any) -> bool:
    if getattr(widget, "_runtime_service", None) is not service:
        return False
    if _service_is_retired(service):
        return False
    if getattr(service, "shared_owner", None) is None:
        return False
    return not _widget_is_active(widget) or _service_is_running(service)


_SYSTEM_MUTE_SERVICE_SPEC = RuntimeServiceSpec(
    build=_build_system_mute_service,
    inject=_inject_system_mute_service,
    retire=_retire_system_mute_service,
    reuse_is_valid=_system_mute_service_reuse_is_valid,
)


_RUNTIME_SERVICE_SPECS: dict[str, RuntimeServiceSpec] = {
    "reddit": _REDDIT_SERVICE_SPEC,
    "reddit2": _REDDIT_SERVICE_SPEC,
    "weather": _WEATHER_SERVICE_SPEC,
    "media": _MEDIA_SERVICE_SPEC,
    "spotify_volume": _MEDIA_VOLUME_SERVICE_SPEC,
    "mute_button": _SYSTEM_MUTE_SERVICE_SPEC,
    "gmail": _GMAIL_SERVICE_SPEC,
    "abandonment_issues": _ABANDONMENT_SERVICE_SPEC,
    "achievement_pulse": _ACHIEVEMENT_SERVICE_SPEC,
}


def get_runtime_service_spec(widget_id: str) -> Optional[RuntimeServiceSpec]:
    """Return the runtime-service spec for a widget id, or None if it owns none."""
    if not isinstance(widget_id, str) or not widget_id:
        return None
    return _RUNTIME_SERVICE_SPECS.get(widget_id)
