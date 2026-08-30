"""Shared presentation-neutral system-mute ownership for Media (Phase E1).

The Windows endpoint object is acquired lazily on the UI/runtime thread.  One
owner per runtime generation coordinates availability, mute state, semantic
toggle/system-volume actions and the 30-second poll cadence.  Per-display
services are leases; the temporary QWidget only paints and supplies feedback.
"""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable
import weakref

from core.logging.logger import get_logger
from core.threading.manager import ThreadManager

logger = get_logger(__name__)


@dataclass(frozen=True)
class SystemMuteRuntimeSnapshot:
    """One coherent system-mute revision delivered to active presenters."""

    revision: int
    available: bool
    muted: bool
    source: str


SystemMuteBackendFactory = Callable[[], Any]


def _load_system_mute_backend() -> Any:
    # Import acquires the process-global endpoint. Keep that work behind actual
    # mute-widget admission and on the same UI thread that will call it.
    from core.media import system_mute

    return system_mute


_SHARED_SYSTEM_MUTE_OWNERS: dict[
    tuple[str, object], "_SharedSystemMuteRuntimeOwner"
] = {}


def _shared_owner_key(runtime_generation: Any, thread_manager: Any) -> tuple[str, object]:
    if runtime_generation is not None:
        return ("runtime", runtime_generation)
    return ("thread_manager", id(thread_manager))


def _drop_shared_owner(
    key: tuple[str, object], owner: "_SharedSystemMuteRuntimeOwner"
) -> None:
    if _SHARED_SYSTEM_MUTE_OWNERS.get(key) is owner:
        _SHARED_SYSTEM_MUTE_OWNERS.pop(key, None)


def shared_system_mute_owner_count() -> int:
    """Return the live shared-owner count for focused cardinality tests."""

    return len(_SHARED_SYSTEM_MUTE_OWNERS)


def reset_shared_system_mute_runtime_for_tests() -> None:
    """Retire all process-shared mute owners (test isolation only)."""

    for owner in list(_SHARED_SYSTEM_MUTE_OWNERS.values()):
        owner.retire()
    _SHARED_SYSTEM_MUTE_OWNERS.clear()


class _SharedSystemMuteRuntimeOwner:
    """One runtime-generation system-mute state/poll/action authority."""

    _POLL_INTERVAL_MS = 30_000
    _EXTERNAL_REFRESH_THROTTLE_SEC = 0.1

    def __init__(
        self,
        *,
        thread_manager: Any,
        runtime_generation: Any,
        backend: Any = None,
        backend_factory: SystemMuteBackendFactory = _load_system_mute_backend,
        registry_key: tuple[str, object] | None = None,
    ) -> None:
        self._thread_manager = thread_manager
        self._runtime_generation = runtime_generation
        self._registry_key = registry_key
        self._backend = backend
        if self._backend is None:
            try:
                self._backend = backend_factory()
            except Exception:
                logger.error(
                    "[SYSTEM_MUTE_RUNTIME] Backend construction failed closed",
                    exc_info=True,
                )
                self._backend = None

        self._leases: weakref.WeakSet[SystemMuteRuntimeService] = weakref.WeakSet()
        self._active_leases: weakref.WeakSet[SystemMuteRuntimeService] = weakref.WeakSet()
        self._running = False
        self._retired = False
        self._owner_generation = 0
        self._poll_token = 0
        self._last_refresh_ts = 0.0
        self._available = self._backend_is_available()
        self._muted = False
        self._revision = 1
        self._source = "initial"

    @property
    def owner_generation(self) -> int:
        return self._owner_generation

    @property
    def poll_token(self) -> int:
        return self._poll_token

    @property
    def backend(self) -> Any:
        """Read-only diagnostic for focused cardinality regressions."""

        return self._backend

    def is_running(self) -> bool:
        return self._running and not self._retired

    def is_retired(self) -> bool:
        return self._retired

    def active_consumer_count(self) -> int:
        return sum(1 for lease in list(self._active_leases) if lease._consumer_alive())

    def attached_consumer_count(self) -> int:
        return sum(1 for lease in list(self._leases) if lease._consumer_alive())

    def current_snapshot(self) -> SystemMuteRuntimeSnapshot:
        return SystemMuteRuntimeSnapshot(
            revision=self._revision,
            available=self._available,
            muted=self._muted,
            source=self._source,
        )

    def attach(self, lease: "SystemMuteRuntimeService") -> None:
        if self._retired:
            raise RuntimeError("cannot attach to a retired system-mute owner")
        if self._thread_manager is None and lease._thread_manager is not None:
            self._thread_manager = lease._thread_manager
        elif (
            lease._thread_manager is not None
            and self._thread_manager is not None
            and lease._thread_manager is not self._thread_manager
        ):
            raise RuntimeError("shared system-mute consumers must use one ThreadManager")
        if (
            self._runtime_generation is not None
            and lease.runtime_generation is not None
            and lease.runtime_generation != self._runtime_generation
        ):
            raise RuntimeError("shared system-mute runtime generation mismatch")
        self._leases.add(lease)

    def detach(self, lease: "SystemMuteRuntimeService") -> None:
        self.deactivate(lease)
        self._leases.discard(lease)
        if not list(self._leases):
            self.retire()

    def activate(self, lease: "SystemMuteRuntimeService") -> bool:
        if self._retired or lease not in self._leases:
            return False
        self._active_leases.add(lease)
        started_owner = False
        if not self._running:
            from core.media.media_native_trace import trace_media_native_stage

            trace_media_native_stage(
                component="mute_button",
                stage="owner_activate_begin",
                generation=self._runtime_generation,
                detail="available=%s" % self._available,
            )
            self._running = True
            self._owner_generation += 1
            self._poll_token += 1
            started_owner = True
            trace_media_native_stage(
                component="mute_button",
                stage="owner_activate_complete",
                generation=self._runtime_generation,
            )
        lease._deliver_snapshot(self.current_snapshot())
        if started_owner and self._available:
            self._schedule_next_poll(
                owner_generation=self._owner_generation,
                poll_token=self._poll_token,
            )
        return True

    def deactivate(self, lease: "SystemMuteRuntimeService") -> None:
        self._active_leases.discard(lease)
        if list(self._active_leases) or not self._running:
            return
        self._running = False
        self._owner_generation += 1
        self._poll_token += 1

    def request_refresh(self, *, force: bool = False, source: str = "refresh") -> bool:
        if self._retired or not self._running or not self._available:
            return False
        now = time.monotonic()
        if (
            not force
            and now - self._last_refresh_ts < self._EXTERNAL_REFRESH_THROTTLE_SEC
        ):
            return False
        self._last_refresh_ts = now
        backend = self._backend
        try:
            state = backend.get_mute() if backend is not None else None
        except Exception:
            logger.debug("[SYSTEM_MUTE_RUNTIME] get_mute failed", exc_info=True)
            state = None
        if not isinstance(state, bool):
            return False
        if state != self._muted:
            self._muted = state
            self._publish(source=source)
        return True

    def toggle_mute(self) -> bool:
        if self._retired or not self._running or not self._available:
            return False
        backend = self._backend
        try:
            result = backend.toggle_mute() if backend is not None else None
        except Exception:
            logger.debug("[SYSTEM_MUTE_RUNTIME] toggle_mute failed", exc_info=True)
            result = None
        # Preserve the prior input contract: an admitted click is consumed even
        # if the optional backend reports no result, so local feedback still runs.
        if isinstance(result, bool):
            self._muted = result
            self._publish(source="toggle")
        return True

    def step_system_volume(self, delta: float) -> float | None:
        if self._retired or not self._running or not self._available:
            return None
        backend = self._backend
        try:
            result = backend.step_volume(float(delta)) if backend is not None else None
        except Exception:
            logger.debug("[SYSTEM_MUTE_RUNTIME] step_volume failed", exc_info=True)
            result = None
        if not isinstance(result, (int, float)) or isinstance(result, bool):
            return None
        self.request_refresh(force=True, source="system_volume")
        return float(result)

    def retire(self) -> None:
        if self._retired:
            return
        self._running = False
        self._retired = True
        self._owner_generation += 1
        self._poll_token += 1
        self._active_leases.clear()
        self._leases.clear()
        self._thread_manager = None
        # The backend module owns one process-global endpoint. A display lease
        # never shuts it down or resets it.
        self._backend = None
        if self._registry_key is not None:
            _drop_shared_owner(self._registry_key, self)

    def _backend_is_available(self) -> bool:
        backend = self._backend
        if backend is None:
            return False
        try:
            return bool(backend.is_available())
        except Exception:
            return False

    def _schedule_next_poll(
        self,
        *,
        owner_generation: int,
        poll_token: int,
    ) -> None:
        if (
            self._retired
            or not self._running
            or not self._available
            or owner_generation != self._owner_generation
            or poll_token != self._poll_token
        ):
            return
        owner_ref = weakref.ref(self)

        def _poll() -> None:
            owner = owner_ref()
            if owner is not None:
                owner._poll_tick(
                    owner_generation=owner_generation,
                    poll_token=poll_token,
                )

        _poll._srpss_runtime_generation = self._runtime_generation
        try:
            ThreadManager.single_shot(self._POLL_INTERVAL_MS, _poll)
        except Exception:
            logger.error("[SYSTEM_MUTE_RUNTIME] Failed to schedule mute poll", exc_info=True)
            self._running = False
            self._owner_generation += 1
            self._poll_token += 1

    def _poll_tick(self, *, owner_generation: int, poll_token: int) -> None:
        if (
            self._retired
            or not self._running
            or owner_generation != self._owner_generation
            or poll_token != self._poll_token
        ):
            return
        self.request_refresh(force=True, source="poll")
        self._schedule_next_poll(
            owner_generation=owner_generation,
            poll_token=poll_token,
        )

    def _publish(self, *, source: str) -> None:
        self._revision += 1
        self._source = source
        snapshot = self.current_snapshot()
        for lease in list(self._active_leases):
            lease._deliver_snapshot(snapshot)


class SystemMuteRuntimeService:
    """Per-display lease/projection to the shared system-mute owner."""

    def __init__(
        self,
        *,
        shared: bool = True,
        backend: Any = None,
        backend_factory: SystemMuteBackendFactory = _load_system_mute_backend,
        runtime_generation: Any = None,
    ) -> None:
        if shared and backend is not None:
            raise ValueError("backend injection is isolated-standalone only")
        self._shared = bool(shared)
        self._backend = backend
        self._backend_factory = backend_factory
        self._runtime_generation = runtime_generation
        self._thread_manager: Any = None
        self._consumer_ref: weakref.ReferenceType | None = None
        self._owner: _SharedSystemMuteRuntimeOwner | None = None
        self._running = False
        self._retired = False

    @property
    def runtime_generation(self) -> Any:
        return self._runtime_generation

    @property
    def is_shared(self) -> bool:
        """Return whether this lease participates in runtime-generation sharing."""

        return self._shared

    @property
    def shared_owner(self) -> _SharedSystemMuteRuntimeOwner | None:
        return self._owner

    def current_snapshot(self) -> SystemMuteRuntimeSnapshot | None:
        return self._owner.current_snapshot() if self._owner is not None else None

    def is_running(self) -> bool:
        return bool(
            self._running
            and not self._retired
            and self._owner is not None
            and self._owner.is_running()
        )

    def is_retired(self) -> bool:
        return self._retired

    def set_thread_manager(self, thread_manager: Any) -> None:
        self._thread_manager = thread_manager
        owner = self._owner
        if owner is not None:
            if owner._thread_manager is None:
                owner._thread_manager = thread_manager
            elif thread_manager is not None and owner._thread_manager is not thread_manager:
                raise RuntimeError("shared system-mute lease cannot replace ThreadManager")

    def attach_consumer(self, consumer: Any) -> None:
        if self._retired:
            raise RuntimeError("cannot attach consumer to retired system-mute service")
        current = self._consumer()
        if current is not None and current is not consumer:
            raise RuntimeError("system-mute lease already belongs to another consumer")
        if self._owner is not None:
            if current is consumer:
                return
            raise RuntimeError("system-mute lease already has an owner")
        self._consumer_ref = weakref.ref(consumer)
        generation = getattr(consumer, "_runtime_generation", None)
        if generation is None:
            try:
                generation = getattr(consumer.parent(), "_runtime_generation", None)
            except Exception:
                generation = None
        if generation is not None:
            self._runtime_generation = generation
        if self._thread_manager is None:
            self._thread_manager = getattr(consumer, "_thread_manager", None)

        owner_created = False
        if self._shared:
            if self._runtime_generation is None and self._thread_manager is None:
                self._consumer_ref = None
                raise RuntimeError(
                    "shared system-mute lease requires runtime generation or ThreadManager"
                )
            key = _shared_owner_key(self._runtime_generation, self._thread_manager)
            owner = _SHARED_SYSTEM_MUTE_OWNERS.get(key)
            if owner is None or owner.is_retired():
                owner = _SharedSystemMuteRuntimeOwner(
                    thread_manager=self._thread_manager,
                    runtime_generation=self._runtime_generation,
                    backend_factory=self._backend_factory,
                    registry_key=key,
                )
                _SHARED_SYSTEM_MUTE_OWNERS[key] = owner
                owner_created = True
        else:
            owner = _SharedSystemMuteRuntimeOwner(
                thread_manager=self._thread_manager,
                runtime_generation=self._runtime_generation,
                backend=self._backend,
                backend_factory=self._backend_factory,
            )
            owner_created = True
        try:
            owner.attach(self)
        except Exception:
            self._consumer_ref = None
            if owner_created:
                owner.retire()
            raise
        self._owner = owner

    def detach_consumer(self, consumer: Any = None) -> None:
        current = self._consumer()
        if consumer is not None and current is not consumer:
            return
        owner = self._owner
        if owner is not None:
            owner.detach(self)
        self._owner = None
        self._consumer_ref = None
        self._running = False

    def _consumer(self) -> Any:
        return self._consumer_ref() if self._consumer_ref is not None else None

    def _consumer_alive(self) -> bool:
        consumer = self._consumer()
        if consumer is None:
            return False
        try:
            return bool(consumer.is_system_mute_consumer_alive())
        except Exception:
            return False

    def _deliver_snapshot(self, snapshot: SystemMuteRuntimeSnapshot) -> None:
        consumer = self._consumer()
        if not self._running or consumer is None or not self._consumer_alive():
            return
        try:
            consumer.on_system_mute_runtime_snapshot(snapshot)
        except Exception:
            logger.debug("[SYSTEM_MUTE_RUNTIME] Snapshot delivery failed", exc_info=True)

    def start(self) -> bool:
        if self._retired or self._owner is None:
            return False
        if self._running:
            return True
        self._running = True
        try:
            activated = self._owner.activate(self)
        except Exception:
            logger.error("[SYSTEM_MUTE_RUNTIME] Lease activation failed closed", exc_info=True)
            activated = False
        if not activated:
            self._running = False
            return False
        return True

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._owner is not None:
            self._owner.deactivate(self)

    def retire(self) -> None:
        if self._retired:
            return
        self._retired = True
        self.detach_consumer()
        self._thread_manager = None

    def request_refresh(self, *, force: bool = False, source: str = "refresh") -> bool:
        owner = self._owner
        return bool(
            owner is not None and owner.request_refresh(force=force, source=source)
        )

    def toggle_mute(self) -> bool:
        owner = self._owner
        return bool(owner is not None and owner.toggle_mute())

    def step_system_volume(self, delta: float) -> float | None:
        owner = self._owner
        return owner.step_system_volume(delta) if owner is not None else None
