"""Presentation-neutral runtime capability/lifecycle owner (Phase E1).

``WidgetRuntimeManager`` is the Phase-E destination owner named in
``Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`` (§6.1) and
``Docs/QtQuick_Migration/07_Settings_Capability_Activation.md`` (§7). It owns
application-level widget-family capability **admission** (dependency-aware — the
single shared-consumer/dependency accounting authority) and presentation-neutral
runtime **lifecycle routing**.

It deliberately does **not** create or own QWidget/Quick instances or runtime
pixels. The host (currently ``WidgetManager``) still owns the widget registry;
this owner *admits* families, *routes* lifecycle/capability reactions, and owns
presentation-neutral runtime *service* (provider/model) lifetimes on behalf of
runtime widgets. At module top it imports no QWidget/Quick/provider/renderer
code — only the neutral capability/catalog authorities and logging; the
transitional E2.7 failover bridge and the family-specific runtime-service specs
are imported lazily at their call sites, so this owner never becomes a
provider/presenter switchboard.

E1 slice 1 established this owner by extracting admission + lifecycle routing out
of the ``WidgetManager`` god-object (a net reduction there); the host keeps thin
delegating wrappers so its public API and the E2.7 confirmed-retirement contract
(``cleanup_widget`` returning an explicit bool) are preserved. E1 slice 2 moves
the first real provider lifetime (the Reddit post provider) here: the owner
builds it from canonical settings via the neutral
``rendering.widget_runtime_services`` registry, injects it into the widget for
use, and retires it on teardown — so the provider is no longer owned merely
because a QWidget exists. Later E1 slices migrate further provider/model lifetimes
and hoist ownership above the host.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Tuple, TYPE_CHECKING

from core.logging.logger import get_logger
from core.settings.capability_activation import (
    is_widget_family_activated,
    is_widget_family_effective,
)
from core.settings.widget_family_catalog import get_family_id_for_widget

if TYPE_CHECKING:
    from rendering.widget_manager import WidgetManager
    from rendering.widget_runtime_services import RuntimeServiceSpec

logger = get_logger(__name__)


class WidgetRuntimeManager:
    """Presentation-neutral capability-admission, lifecycle and service owner."""

    def __init__(self, host: "WidgetManager") -> None:
        # Transitional package-internal coupling: the host still owns the widget
        # registry (``host._widgets``). This owner routes lifecycle/admission and
        # never creates or retains QWidget instances of its own. A later E1 slice
        # hoists registry ownership; keep this edge weak of intent, not identity.
        self._host = host
        # Presentation-neutral runtime services (provider/model lifetimes) owned
        # on behalf of runtime widgets, keyed by widget id. Each entry is the
        # (service, spec) pair so retirement uses the spec's retire hook exactly
        # once, independently of QWidget pixel ownership.
        self._services: Dict[str, Tuple[Any, "RuntimeServiceSpec"]] = {}

    # ------------------------------------------------------------------ #
    # Capability admission authority (dependency-aware; shared-consumer)  #
    # ------------------------------------------------------------------ #
    def family_for_widget(self, widget_id: str) -> Optional[str]:
        """Return the canonical family id owning a runtime widget id, if any.

        ``None`` means the widget is not governed by any capability family and is
        therefore always admitted by activation state.
        """
        return get_family_id_for_widget(widget_id)

    def is_family_activated(
        self, widgets_config: Optional[Mapping[str, Any]], family_id: str
    ) -> bool:
        """Return whether a family's own activation flag is on.

        Missing activation state resolves compatibly to activated (pre-Quick /
        current installs must not silently lose features). This mirrors the
        landed creation-admission gate exactly — relocating ownership, not
        changing behavior.
        """
        return is_widget_family_activated(widgets_config, family_id)

    def is_family_effective(
        self, widgets_config: Optional[Mapping[str, Any]], family_id: str
    ) -> bool:
        """Return whether a family is activated AND its required families are.

        This is the canonical **activation + dependency-satisfaction** query
        (e.g. ``visualizers`` requires ``media``): a family is only *effective*
        while every capability it depends on remains activated. It is **not** a
        shared-provider last-consumer counter; genuine shared-service lifetime
        must use explicit consumer/ownership accounting, not this query.
        """
        return is_widget_family_effective(widgets_config, family_id)

    def admits_widget_family(
        self, widget_id: str, widgets_config: Optional[Mapping[str, Any]]
    ) -> bool:
        """Return whether a widget id's family admits runtime creation.

        A widget with no governing family is always admitted; a governed widget
        is admitted only while its family is activated. This is the capability
        gate consumed by widget creation; per-instance ``enabled`` state remains a
        distinct, separate check owned by the creation path.
        """
        family_id = self.family_for_widget(widget_id)
        if family_id is None:
            return True
        return self.is_family_activated(widgets_config, family_id)

    # ------------------------------------------------------------------ #
    # Presentation-neutral runtime service (provider/model) ownership     #
    # ------------------------------------------------------------------ #
    def ensure_widget_service(
        self,
        widget_id: str,
        widget: Any,
        widgets_config: Optional[Mapping[str, Any]],
    ) -> Any:
        """Own the presentation-neutral runtime service for a created widget.

        If ``widget_id`` has a registered :class:`RuntimeServiceSpec`, build the
        service from canonical settings, take ownership of its lifetime, and
        inject it into the widget for consumption. Idempotent: an existing owned
        service for the same id is retired first so a re-admission never
        double-owns. Family-specific knowledge lives in the neutral
        ``widget_runtime_services`` registry, not here.
        """
        from rendering.widget_runtime_services import get_runtime_service_spec

        spec = get_runtime_service_spec(widget_id)
        if spec is None:
            return None
        # Retire any prior owned service for this id before re-owning.
        self.retire_widget_service(widget_id)
        try:
            service = spec.build(widget_id, widgets_config or {})
        except Exception:
            logger.debug(
                "[WIDGET_RUNTIME] Failed to build runtime service for %s",
                widget_id,
                exc_info=True,
            )
            return None
        if service is None:
            return None
        self._services[widget_id] = (service, spec)
        if widget is not None:
            try:
                spec.inject(widget, service)
            except Exception:
                logger.debug(
                    "[WIDGET_RUNTIME] Failed to inject runtime service for %s",
                    widget_id,
                    exc_info=True,
                )
        return service

    def get_widget_service(self, widget_id: str) -> Any:
        """Return the owned runtime service for a widget id, or None."""
        entry = self._services.get(widget_id)
        return entry[0] if entry is not None else None

    def retire_widget_service(self, widget_id: str) -> bool:
        """Retire and drop the owned runtime service for a widget id.

        Returns whether a service was retired. Calls the spec's retire hook
        exactly once; a spec with no retire hook simply drops the reference.
        """
        entry = self._services.pop(widget_id, None)
        if entry is None:
            return False
        service, spec = entry
        if spec.retire is not None:
            try:
                spec.retire(service)
            except Exception:
                logger.debug(
                    "[WIDGET_RUNTIME] Failed to retire runtime service for %s",
                    widget_id,
                    exc_info=True,
                )
        return True

    def retire_all_services(self) -> None:
        """Retire every owned runtime service (terminal teardown)."""
        for widget_id in list(self._services.keys()):
            self.retire_widget_service(widget_id)

    # ------------------------------------------------------------------ #
    # Capability-deactivation reaction dispatch                          #
    # ------------------------------------------------------------------ #
    def handle_capability_change(self, settings_manager: Any) -> None:
        """React to a capability-activation change at the owner boundary.

        Currently dispatches the E2.7 canonical Visualizer failover retirement:
        when Media or Visualizers becomes ineffective, a pending grace / live
        temporary fallback must be retired so it cannot stay stuck. This is the
        extensible seam through which future E1 slices register additional
        family-exclusive runtime retirements. Lazy import avoids a module-load
        cycle with ``widget_setup_all``.
        """
        try:
            from rendering.widget_setup_all import (
                retire_visualizer_failover_on_capability_change,
            )
            retire_visualizer_failover_on_capability_change(settings_manager)
        except Exception:
            logger.debug(
                "[WIDGET_RUNTIME] Visualizer failover deactivation retirement failed",
                exc_info=True,
            )

    # ------------------------------------------------------------------ #
    # Runtime lifecycle routing (presentation-neutral)                   #
    # ------------------------------------------------------------------ #
    def _registry(self) -> Dict[str, Any]:
        host = self._host
        if host is None:
            return {}
        return getattr(host, "_widgets", {}) or {}

    def initialize_widget(self, name: str) -> bool:
        """Initialize a widget using the lifecycle system."""
        widget = self._registry().get(name)
        if widget is None:
            return False
        try:
            if hasattr(widget, "initialize") and callable(widget.initialize):
                widget.initialize()
                logger.debug("[LIFECYCLE] Widget %s initialized via WidgetRuntimeManager", name)
                return True
        except Exception:
            logger.debug("[LIFECYCLE] Failed to initialize %s", name, exc_info=True)
        return False

    def activate_widget(self, name: str) -> bool:
        """Activate a widget using the lifecycle system."""
        widget = self._registry().get(name)
        if widget is None:
            return False
        try:
            if hasattr(widget, "activate") and callable(widget.activate):
                widget.activate()
                logger.debug("[LIFECYCLE] Widget %s activated via WidgetRuntimeManager", name)
                return True
        except Exception:
            logger.debug("[LIFECYCLE] Failed to activate %s", name, exc_info=True)
        return False

    def deactivate_widget(self, name: str) -> bool:
        """Deactivate a widget using the lifecycle system."""
        widget = self._registry().get(name)
        if widget is None:
            return False
        try:
            if hasattr(widget, "deactivate") and callable(widget.deactivate):
                widget.deactivate()
                logger.debug("[LIFECYCLE] Widget %s deactivated via WidgetRuntimeManager", name)
                return True
        except Exception:
            logger.debug("[LIFECYCLE] Failed to deactivate %s", name, exc_info=True)
        return False

    def cleanup_widget(self, name: str) -> bool:
        """Cleanup a widget using the lifecycle system.

        Returns an explicit success bool. The E2.7 confirmed-retirement contract
        depends on this: a caller may only discard a live-owner record when
        cleanup is confirmed.
        """
        widget = self._registry().get(name)
        if widget is None:
            return False
        try:
            if hasattr(widget, "cleanup") and callable(widget.cleanup):
                widget.cleanup()
                logger.debug("[LIFECYCLE] Widget %s cleaned up via WidgetRuntimeManager", name)
                return True
        except Exception:
            logger.debug("[LIFECYCLE] Failed to cleanup %s", name, exc_info=True)
        return False

    def initialize_all_widgets(self) -> int:
        """Initialize all managed widgets using the lifecycle system."""
        count = 0
        for name in list(self._registry().keys()):
            if self.initialize_widget(name):
                count += 1
        logger.debug("[LIFECYCLE] Initialized %d widgets", count)
        return count

    def activate_all_widgets(self) -> int:
        """Activate all managed widgets using the lifecycle system.

        DORMANT as of Jan 2026: the legacy start() system is used instead (see
        setup_all_widgets). Lifecycle methods exist in all widgets but are not
        called on this path; kept to reduce regression risk.
        """
        count = 0
        for name in list(self._registry().keys()):
            if self.activate_widget(name):
                count += 1
        logger.debug("[LIFECYCLE] Activated %d widgets", count)
        return count

    def deactivate_all_widgets(self) -> int:
        """Deactivate all managed widgets using the lifecycle system."""
        count = 0
        for name in list(self._registry().keys()):
            if self.deactivate_widget(name):
                count += 1
        logger.debug("[LIFECYCLE] Deactivated %d widgets", count)
        return count

    def get_widget_lifecycle_state(self, name: str) -> Optional[str]:
        """Return the lifecycle state name of a widget, or None."""
        widget = self._registry().get(name)
        if widget is None:
            return None
        try:
            if hasattr(widget, "_lifecycle_state"):
                state = widget._lifecycle_state
                if hasattr(state, "name"):
                    return state.name
                return str(state)
        except Exception as e:
            logger.debug("[WIDGET_RUNTIME] Exception suppressed: %s", e)
        return None

    def get_all_lifecycle_states(self) -> Dict[str, str]:
        """Return a dict mapping widget name to lifecycle state name."""
        states: Dict[str, str] = {}
        for name in self._registry().keys():
            state = self.get_widget_lifecycle_state(name)
            if state is not None:
                states[name] = state
        return states

    def cleanup(self) -> None:
        """Retire owned services and release the host edge; terminal."""
        self.retire_all_services()
        self._host = None
