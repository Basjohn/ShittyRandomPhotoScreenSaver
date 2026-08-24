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
Steam cards remain unregistered; no generic/shared Steam service is implied.

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


_RUNTIME_SERVICE_SPECS: dict[str, RuntimeServiceSpec] = {
    "reddit": _REDDIT_SERVICE_SPEC,
    "reddit2": _REDDIT_SERVICE_SPEC,
    "weather": _WEATHER_SERVICE_SPEC,
    "abandonment_issues": _ABANDONMENT_SERVICE_SPEC,
}


def get_runtime_service_spec(widget_id: str) -> Optional[RuntimeServiceSpec]:
    """Return the runtime-service spec for a widget id, or None if it owns none."""
    if not isinstance(widget_id, str) or not widget_id:
        return None
    return _RUNTIME_SERVICE_SPECS.get(widget_id)
