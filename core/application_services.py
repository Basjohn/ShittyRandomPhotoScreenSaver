"""The application-service tier: process-scoped services above display generations.

A display generation (one ``DisplayManager`` and everything it builds) and a Settings dialog generation are torn
down and rebuilt on every Settings visit, CUSTOM reload and monitor-topology change. Anything that must outlive them
(the SMP library repository, playback service, queue) is an *application service*: one ``ApplicationServices``
registry on the engine owns it, created in ``ScreensaverEngine.initialize`` and retired only by terminal shutdown
(``engine_lifecycle.cleanup`` / the terminal stop finalization). ``DisplayPowerAuthority`` is the model: a
process-scoped, engine-owned authority that every generation consults and none owns. There is no module-global
instance; the registry lives and dies with its engine.

**Generations never own a service; they lease it.** A generation is admitted by its owner before it is built
(``admit_generation``: the engine's display construction, the Settings dialog construction) and retired at the same
edge that cancels its delayed callbacks (``retire_generation``: ``teardown_display_runtime`` for a display
generation, the ``cancel_scheduled_single_shots`` edge for the Settings dialog). Retiring a generation revokes every
lease it took; the service itself is untouched. A revoked lease resolves to ``None`` (fail closed), and a generation
that is not admitted (never admitted, or already retired) cannot take a new lease, so a late callback from a retired
generation can never reach a service, even after ``ThreadManager`` has pruned that generation's cancellation record
(AC-13 note). Consumers resolve ``lease.service`` per command and never cache the instance.

**Nothing is created until a real consumer asks.** ``register`` stores only a factory. The first ``lease`` of a name
creates its instance, and only while its capability predicate answers True. A product that declares no service (or
whose descriptors are unavailable, e.g. Standard SRPSS without ``--smp``) registers nothing and creates nothing.

**Service rules.** A factory imports its implementation lazily (import dormancy). An instance exposes ``retire()``,
called exactly once, in reverse creation order at terminal shutdown. A service never tags its own delayed work with a
display or Settings generation (that would let a generation teardown cancel it); it uses
``service_owner_key(name)`` and cancels that key in its own ``retire()``.
"""

from __future__ import annotations

import threading
import weakref
from dataclasses import dataclass
from typing import Callable, Hashable

from core.logging.logger import get_logger

logger = get_logger(__name__)


def service_owner_key(name: str) -> str:
    """The ThreadManager owner key for a service's own delayed work (never a generation key)."""

    return f"app-service:{name}"


@dataclass(frozen=True)
class ApplicationServiceDescriptor:
    """One declared application service.

    ``available`` is the launch-time product gate (e.g. ``core.smp.is_smp_enabled``), checked once when the engine
    registers its catalog. ``capability`` is the live gate checked when a lease would create the instance (e.g. the
    owning family's activation). ``factory`` builds the instance and imports its implementation inside the call.
    """

    name: str
    available: Callable[[], bool]
    factory: Callable[[], object]
    capability: Callable[[], bool] | None = None


# Every application service the product declares. Empty until SMP M2 adds its LibraryRepository (behind --smp).
APPLICATION_SERVICE_CATALOG: tuple[ApplicationServiceDescriptor, ...] = ()


class ServiceLease:
    """One generation's revocable handle on one application service.

    Holds no reference to the service: ``service`` resolves through the registry on every call and answers ``None``
    once the lease is revoked (its generation retired, the service retired, or ``release()``).
    """

    __slots__ = ("_registry", "name", "generation", "_revoked", "__weakref__")

    def __init__(self, registry: "ApplicationServices", name: str, generation: Hashable) -> None:
        self._registry = registry
        self.name = name
        self.generation = generation
        self._revoked = False

    @property
    def is_live(self) -> bool:
        return self._registry._resolve(self) is not None

    @property
    def service(self) -> object | None:
        return self._registry._resolve(self)

    def release(self) -> None:
        """Give the lease back early (a pane hidden inside a live generation)."""

        self._registry._release(self)

    def __repr__(self) -> str:
        state = "revoked" if self._revoked else "live"
        return f"ServiceLease({self.name!r}, generation={self.generation!r}, {state})"


class ApplicationServices:
    """The engine's one application-service registry (see the module docstring for the contract)."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._factories: dict[str, tuple[Callable[[], object], Callable[[], bool] | None]] = {}
        self._instances: dict[str, object] = {}
        self._creation_order: list[str] = []
        self._admitted: set[Hashable] = set()
        self._leases: dict[Hashable, "weakref.WeakSet[ServiceLease]"] = {}
        self._closed = False

    # -- registration -------------------------------------------------------------------------------------------

    def register(
        self,
        name: str,
        factory: Callable[[], object],
        *,
        capability: Callable[[], bool] | None = None,
    ) -> None:
        """Declare one service by name. Creates nothing; the first lease does."""

        name = str(name)
        if not name:
            raise ValueError("An application service needs a name")
        if not callable(factory):
            raise TypeError(f"Application service {name!r} factory is not callable")
        with self._lock:
            if self._closed:
                raise RuntimeError(f"Application services are retired; cannot register {name!r}")
            if name in self._factories:
                raise ValueError(f"Application service {name!r} is already registered")
            self._factories[name] = (factory, capability)
        logger.info("[APP_SERVICES] Registered %s", name)

    def register_catalog(self, catalog: tuple[ApplicationServiceDescriptor, ...]) -> tuple[str, ...]:
        """Register every descriptor whose product gate is open; return the names registered."""

        registered: list[str] = []
        for descriptor in catalog:
            if not bool(descriptor.available()):
                continue
            self.register(descriptor.name, descriptor.factory, capability=descriptor.capability)
            registered.append(descriptor.name)
        return tuple(registered)

    def registered_names(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._factories)

    def get(self, name: str) -> object | None:
        """The live instance, or None. Never creates: generations lease, they do not get."""

        with self._lock:
            return self._instances.get(str(name))

    # -- generations and leases -----------------------------------------------------------------------------------

    def admit_generation(self, generation: Hashable) -> None:
        """Admit one display or Settings generation before it is built; it may lease until retired."""

        with self._lock:
            if self._closed:
                return
            self._admitted.add(generation)

    def retire_generation(self, generation: Hashable) -> int:
        """Revoke every lease the generation took and refuse it new ones. Services are untouched."""

        with self._lock:
            self._admitted.discard(generation)
            leases = self._leases.pop(generation, None)
            revoked = 0
            for lease in tuple(leases or ()):
                if not lease._revoked:
                    lease._revoked = True
                    revoked += 1
        if revoked:
            logger.info("[APP_SERVICES] Revoked %d lease(s) of retired generation=%s", revoked, generation)
        return revoked

    def lease(self, name: str, *, generation: Hashable) -> ServiceLease | None:
        """Lease ``name`` for an admitted generation, creating the service on first use if its capability is active.

        Returns None (and creates nothing) when the registry is retired, the generation is not admitted, the name is
        not registered or its capability is inactive.
        """

        name = str(name)
        with self._lock:
            if self._closed or generation not in self._admitted:
                logger.debug("[APP_SERVICES] Lease of %s refused for generation=%s", name, generation)
                return None
            entry = self._factories.get(name)
            if entry is None:
                return None
            if name not in self._instances:
                factory, capability = entry
                if capability is not None and not bool(capability()):
                    logger.debug("[APP_SERVICES] Lease of %s refused: capability inactive", name)
                    return None
                instance = factory()
                if not callable(getattr(instance, "retire", None)):
                    raise TypeError(f"Application service {name!r} has no retire()")
                self._instances[name] = instance
                self._creation_order.append(name)
                logger.info("[APP_SERVICES] Created %s on first lease generation=%s", name, generation)
            lease = ServiceLease(self, name, generation)
            self._leases.setdefault(generation, weakref.WeakSet()).add(lease)
            return lease

    def _resolve(self, lease: ServiceLease) -> object | None:
        with self._lock:
            if lease._revoked or self._closed:
                return None
            return self._instances.get(lease.name)

    def _release(self, lease: ServiceLease) -> None:
        with self._lock:
            lease._revoked = True
            leases = self._leases.get(lease.generation)
            if leases is not None:
                leases.discard(lease)

    # -- retirement -----------------------------------------------------------------------------------------------

    def retire(self, name: str) -> bool:
        """Retire one live service exactly once, revoking every lease of it. A later lease may create it again."""

        name = str(name)
        with self._lock:
            instance = self._instances.pop(name, None)
            if instance is None:
                return False
            self._creation_order.remove(name)
            for leases in self._leases.values():
                for lease in tuple(leases):
                    if lease.name == name:
                        lease._revoked = True
                        leases.discard(lease)
        try:
            instance.retire()
        except Exception:
            logger.warning("[APP_SERVICES] %s retirement failed", name, exc_info=True)
        logger.info("[APP_SERVICES] Retired %s", name)
        return True

    def retire_all(self, *, reason: str) -> int:
        """Terminal: close the registry and retire every live service in reverse creation order (idempotent)."""

        with self._lock:
            if self._closed:
                return 0
            self._closed = True
            names = list(reversed(self._creation_order))
        retired = sum(1 for name in names if self.retire(name))
        with self._lock:
            for leases in self._leases.values():
                for lease in tuple(leases):
                    lease._revoked = True
            self._leases.clear()
            self._admitted.clear()
            self._factories.clear()
        logger.info("[APP_SERVICES] Registry retired reason=%s services=%d", reason, retired)
        return retired

    @property
    def is_retired(self) -> bool:
        return self._closed

    def describe(self) -> dict[str, object]:
        with self._lock:
            return {
                "registered": tuple(self._factories),
                "live": tuple(self._creation_order),
                "admitted_generations": len(self._admitted),
                "live_leases": sum(
                    1 for leases in self._leases.values() for lease in tuple(leases) if not lease._revoked
                ),
                "retired": self._closed,
            }
