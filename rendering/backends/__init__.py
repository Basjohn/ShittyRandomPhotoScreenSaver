"""Renderer backend factory and utilities."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, Optional, Type

from core.logging.logger import get_logger
from core.settings.settings_manager import SettingsManager
from core.events import EventSystem, EventType

from .base import RendererBackend
from .opengl.backend import OpenGLRendererBackend
from .software.backend import SoftwareRendererBackend

logger = get_logger(__name__)


class BackendRegistry:
    """Registry mapping backend keys to backend classes."""

    def __init__(self) -> None:
        self._registry: Dict[str, Type[RendererBackend]] = {}

    def register(self, key: str, backend_cls: Type[RendererBackend]) -> None:
        key_lower = key.lower()
        if key_lower in self._registry:
            logger.warning("Overwriting backend registration for %s", key_lower)
        self._registry[key_lower] = backend_cls

    def create(self, key: str) -> RendererBackend:
        key_lower = key.lower()
        backend_cls = self._registry.get(key_lower)
        if backend_cls is None:
            raise KeyError(f"Backend '{key}' is not registered")
        backend = backend_cls()
        backend.initialize()
        return backend

    def available(self) -> Dict[str, Type[RendererBackend]]:
        return dict(self._registry)


_registry = BackendRegistry()


@dataclass
class BackendDiagnostics:
    """Accumulates telemetry for backend selections and fallbacks."""

    selections: Counter
    fallbacks: Counter
    failures: Counter


@dataclass
class BackendSelectionResult:
    """Details of a backend selection attempt."""

    backend: RendererBackend
    requested_mode: str
    resolved_mode: str
    fallback_reason: Optional[str] = None

    @property
    def fallback_performed(self) -> bool:
        return self.fallback_reason is not None


_diagnostics = BackendDiagnostics(Counter(), Counter(), Counter())

# Register built-in backends
_registry.register("opengl", OpenGLRendererBackend)
_registry.register("software", SoftwareRendererBackend)


def get_registry() -> BackendRegistry:
    return _registry


def _normalize_bool(value) -> bool:
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _normalize_backend(value: Optional[str]) -> str:
    if not isinstance(value, str):
        return "opengl"

    lowered = value.lower().strip()
    if lowered in {"opengl", "software"}:
        return lowered

    if lowered:
        logger.info("Unknown renderer backend '%s'; defaulting to OpenGL", lowered)
    return "opengl"


def _determine_mode(settings: SettingsManager) -> str:
    """Return normalized backend mode ('opengl' or 'software')."""

    raw = settings.get("display.render_backend_mode", "opengl")
    normalized = _normalize_backend(raw)

    if isinstance(raw, str) and raw.lower().strip() != normalized:
        try:
            settings.set("display.render_backend_mode", normalized)
        except Exception:
            logger.debug("Failed to persist normalized backend mode", exc_info=True)

    return normalized


def _publish(event_system: Optional[EventSystem], event_type: str, **data) -> None:
    if event_system is None:
        return
    try:
        event_system.publish(event_type, data=data, source="rendering.backends")
    except Exception:  # pragma: no cover - diagnostics should not break init
        logger.exception("Failed to publish event %s", event_type)


def _record_selection(resolved: str) -> None:
    _diagnostics.selections[resolved] += 1


def _record_fallback(requested: str, resolved: str) -> None:
    _diagnostics.fallbacks[f"{requested}->{resolved}"] += 1


def _record_failure(requested: str) -> None:
    _diagnostics.failures[requested] += 1


def create_backend_from_settings(
    settings: SettingsManager,
    *,
    event_system: Optional[EventSystem] = None,
) -> BackendSelectionResult:
    resolved_mode = _determine_mode(settings)

    if resolved_mode == "software":
        backend = _registry.create("software")
        logger.info("Renderer backend 'software' initialized")
        _record_selection("software")
        _publish(
            event_system,
            EventType.RENDER_BACKEND_SELECTED,
            requested="software",
            resolved="software",
            fallback=False,
        )
        return BackendSelectionResult(backend=backend, requested_mode="software", resolved_mode="software")

    if resolved_mode == "opengl":
        try:
            backend = _registry.create("opengl")
            logger.info("Renderer backend 'opengl' initialized")
            _record_selection("opengl")
            _publish(
                event_system,
                EventType.RENDER_BACKEND_SELECTED,
                requested="opengl",
                resolved="opengl",
                fallback=False,
            )
            return BackendSelectionResult(backend=backend, requested_mode="opengl", resolved_mode="opengl")
        except Exception as exc:
            logger.exception("OpenGL backend initialization failed: %s", exc)
            logger.warning("Falling back to software renderer after OpenGL failure: %s", exc)
            backend = _registry.create("software")
            reason = str(exc)
            _record_selection("software")
            _record_fallback("opengl", "software")
            _publish(
                event_system,
                EventType.RENDER_BACKEND_FALLBACK,
                requested="opengl",
                resolved="software",
                reason=reason,
            )
            _publish(
                event_system,
                EventType.RENDER_BACKEND_SELECTED,
                requested="opengl",
                resolved="software",
                fallback=True,
            )
            return BackendSelectionResult(
                backend=backend,
                requested_mode="opengl",
                resolved_mode="software",
                fallback_reason=reason,
            )
    
    logger.info("Renderer backend '%s' unsupported – defaulting to OpenGL", resolved_mode)
    settings.set("display.render_backend_mode", "opengl")
    return create_backend_from_settings(settings, event_system=event_system)


def get_backend_diagnostics() -> BackendDiagnostics:
    """Return a snapshot of backend telemetry counters."""

    return BackendDiagnostics(
        selections=_diagnostics.selections.copy(),
        fallbacks=_diagnostics.fallbacks.copy(),
        failures=_diagnostics.failures.copy(),
    )


def reset_backend_diagnostics() -> None:
    """Clear backend telemetry counters (primarily for testing)."""

    _diagnostics.selections.clear()
    _diagnostics.fallbacks.clear()
    _diagnostics.failures.clear()
