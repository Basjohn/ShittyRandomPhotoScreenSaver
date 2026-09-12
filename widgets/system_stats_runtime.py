"""Event-owned shared CPU/RAM sampler leases for the System Stats card.

One runtime-generation owner samples only while a retained consumer lease is
active; each display receives the same immutable snapshot. The product path
intentionally excludes GPU metrics until their source can meet the same bounded
cost and reliability contract.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable
import weakref

from core.system_stats.source import CpuRamSample, WholeSystemCpuRamSource
from core.threading.manager import TaskPriority, ThreadManager, ThreadPoolType


SAMPLE_INTERVAL_MS = 10_000


@dataclass(frozen=True)
class SystemStatsRuntimeSnapshot:
    revision: int
    accepted_monotonic: float
    sample: CpuRamSample


SystemStatsSourceFactory = Callable[[], WholeSystemCpuRamSource]
OneShotScheduler = Callable[[int, Callable[[], None]], None]
TaskSubmitter = Callable[[Callable[[], Any], Callable[[Any], None], str], str]
UiDispatcher = Callable[[Callable[[], None]], bool | None]


_SHARED_SYSTEM_STATS_OWNERS: dict[tuple[str, object], "_SharedSystemStatsOwner"] = {}


def _owner_key(runtime_generation: Any, thread_manager: Any) -> tuple[str, object]:
    return (
        ("runtime", runtime_generation)
        if runtime_generation is not None
        else ("thread_manager", id(thread_manager))
    )


def _drop_owner(key: tuple[str, object], owner: "_SharedSystemStatsOwner") -> None:
    if _SHARED_SYSTEM_STATS_OWNERS.get(key) is owner:
        _SHARED_SYSTEM_STATS_OWNERS.pop(key, None)


def shared_system_stats_owner_count() -> int:
    """Focused lifecycle-test diagnostic only."""

    return len(_SHARED_SYSTEM_STATS_OWNERS)


def reset_shared_system_stats_runtime_for_tests() -> None:
    """Terminally retire all shared owners; test isolation only."""

    for owner in list(_SHARED_SYSTEM_STATS_OWNERS.values()):
        owner.retire()
    _SHARED_SYSTEM_STATS_OWNERS.clear()


def _default_schedule(delay_ms: int, callback: Callable[[], None]) -> None:
    ThreadManager.single_shot(delay_ms, callback)


def _default_submit(
    thread_manager: Any,
) -> TaskSubmitter:
    def submit(
        work: Callable[[], Any], complete: Callable[[Any], None], task_id: str
    ) -> str:
        return thread_manager.submit_task(
            ThreadPoolType.IO,
            work,
            task_id=task_id,
            priority=TaskPriority.LOW,
            category="system_stats.sample",
            callback=complete,
        )

    return submit


def _default_ui_dispatch(callback: Callable[[], None]) -> bool:
    return ThreadManager.run_on_ui_thread(callback)


class _SharedSystemStatsOwner:
    """One runtime-generation sampling authority, shared by display leases."""

    def __init__(
        self,
        *,
        thread_manager: Any,
        runtime_generation: Any,
        source_factory: SystemStatsSourceFactory,
        schedule: OneShotScheduler,
        submit: TaskSubmitter,
        ui_dispatch: UiDispatcher,
        registry_key: tuple[str, object] | None = None,
    ) -> None:
        self._thread_manager = thread_manager
        self._runtime_generation = runtime_generation
        self._source_factory = source_factory
        self._schedule = schedule
        self._submit = submit
        self._ui_dispatch = ui_dispatch
        self._registry_key = registry_key
        self._leases: weakref.WeakSet[SystemStatsRuntimeService] = weakref.WeakSet()
        self._active_leases: weakref.WeakSet[SystemStatsRuntimeService] = (
            weakref.WeakSet()
        )
        self._source: WholeSystemCpuRamSource | None = None
        self._snapshot: SystemStatsRuntimeSnapshot | None = None
        self._running = False
        self._retired = False
        self._in_flight = False
        self._scheduled = False
        self._owner_generation = 0
        self._token = 0
        self._revision = 0
        self._sequence = 0
        self._skipped_edges = 0

    @property
    def shared_snapshot(self) -> SystemStatsRuntimeSnapshot | None:
        return self._snapshot

    @property
    def skipped_edges(self) -> int:
        return self._skipped_edges

    def cardinality(self) -> dict[str, int | bool]:
        return {
            "attached_leases": sum(
                1 for lease in list(self._leases) if lease._consumer_alive()
            ),
            "active_leases": self.active_consumer_count(),
            "source_live": self._source is not None,
            "in_flight": self._in_flight,
            "scheduled": self._scheduled,
        }

    def active_consumer_count(self) -> int:
        return sum(1 for lease in list(self._active_leases) if lease._consumer_alive())

    def is_running(self) -> bool:
        return self._running and not self._retired

    def is_retired(self) -> bool:
        return self._retired

    def attach(self, lease: "SystemStatsRuntimeService") -> None:
        if self._retired:
            raise RuntimeError("cannot attach to retired system-stats owner")
        if self._thread_manager is None and lease._thread_manager is not None:
            self._thread_manager = lease._thread_manager
        elif (
            lease._thread_manager is not None
            and self._thread_manager is not lease._thread_manager
        ):
            raise RuntimeError("shared System Stats leases require one ThreadManager")
        if (
            self._runtime_generation is not None
            and lease.runtime_generation is not None
            and lease.runtime_generation != self._runtime_generation
        ):
            raise RuntimeError("shared System Stats runtime generation mismatch")
        self._leases.add(lease)

    def detach(self, lease: "SystemStatsRuntimeService") -> None:
        self.deactivate(lease)
        self._leases.discard(lease)
        if not list(self._leases):
            self.retire()

    def activate(self, lease: "SystemStatsRuntimeService") -> bool:
        if self._retired or lease not in self._leases:
            return False
        self._active_leases.add(lease)
        if not self._running:
            try:
                self._source = self._source_factory()
            except Exception:
                self._source = None
                self._active_leases.discard(lease)
                return False
            if self._source is None:
                self._active_leases.discard(lease)
                return False
            self._running = True
            self._owner_generation += 1
            self._token += 1
            self._schedule_sample(0)
        snapshot = self._snapshot
        if snapshot is not None:
            lease._deliver_snapshot(snapshot)
        return True

    def deactivate(self, lease: "SystemStatsRuntimeService") -> None:
        self._active_leases.discard(lease)
        if self._active_leases or not self._running:
            return
        self._running = False
        self._owner_generation += 1
        self._token += 1
        self._in_flight = False
        # Existing one-shot callbacks remain harmlessly token-fenced, but no
        # longer count as this owner's live cadence after the final release.
        self._scheduled = False
        self._close_and_clear_source()
        # A future lease must warm a new source instead of replaying a value
        # captured by a prior consumer lifetime. Keep ``_revision`` monotonic
        # so an old completion can never look newer than fresh state.
        self._snapshot = None

    def retire(self) -> None:
        if self._retired:
            return
        self._running = False
        self._retired = True
        self._owner_generation += 1
        self._token += 1
        self._in_flight = False
        self._scheduled = False
        self._active_leases.clear()
        self._leases.clear()
        self._close_and_clear_source()
        self._snapshot = None
        self._thread_manager = None
        if self._registry_key is not None:
            _drop_owner(self._registry_key, self)

    def _close_and_clear_source(self) -> None:
        source, self._source = self._source, None
        if source is not None:
            close = getattr(source, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    def _schedule_sample(self, delay_ms: int) -> None:
        if self._retired or not self._running or self._scheduled:
            return
        owner_generation = self._owner_generation
        token = self._token
        self._scheduled = True
        owner_ref = weakref.ref(self)

        def scheduled() -> None:
            owner = owner_ref()
            if owner is not None:
                owner._scheduled = False
                owner._sample_edge(owner_generation, token)

        scheduled._srpss_runtime_generation = self._runtime_generation
        try:
            self._schedule(max(0, int(delay_ms)), scheduled)
        except Exception:
            self._scheduled = False
            self._running = False
            self._owner_generation += 1
            self._token += 1
            self._close_and_clear_source()

    def _sample_edge(self, owner_generation: int, token: int) -> None:
        if (
            self._retired
            or not self._running
            or owner_generation != self._owner_generation
            or token != self._token
        ):
            return
        if self._in_flight:
            self._skipped_edges += 1
            return
        source = self._source
        if source is None:
            return
        self._in_flight = True
        self._sequence += 1
        sequence = self._sequence

        def work() -> CpuRamSample:
            return source.sample()

        work._srpss_runtime_generation = self._runtime_generation

        def complete(result: Any) -> None:
            def deliver() -> None:
                self._complete_sample(result, owner_generation, token)

            deliver._srpss_runtime_generation = self._runtime_generation
            try:
                dispatched = self._ui_dispatch(deliver)
            except Exception:
                dispatched = False
            if dispatched is False:
                self._fail_closed_ui_dispatch(owner_generation, token)

        complete._srpss_runtime_generation = self._runtime_generation

        try:
            self._submit(
                work,
                complete,
                f"system_stats_sample_{id(self)}_{owner_generation}_{sequence}",
            )
        except Exception:
            self._in_flight = False
            if (
                self._running
                and owner_generation == self._owner_generation
                and token == self._token
            ):
                self._schedule_sample(SAMPLE_INTERVAL_MS)

    def _fail_closed_ui_dispatch(self, owner_generation: int, token: int) -> None:
        """Stop rather than strand a live sampler when UI delivery is rejected.

        Completion normally transitions state on the UI thread. If that queue
        rejects the delivery, scheduling another worker pulse would create work
        with no legal publication path. Fence the worker result and release the
        source instead; a later normal recreation can establish a fresh owner.
        """

        if (
            self._retired
            or not self._running
            or owner_generation != self._owner_generation
            or token != self._token
        ):
            return
        self._in_flight = False
        self._running = False
        self._owner_generation += 1
        self._token += 1
        self._scheduled = False
        self._close_and_clear_source()
        self._snapshot = None
        for lease in list(self._active_leases):
            lease._running = False

    def _complete_sample(self, result: Any, owner_generation: int, token: int) -> None:
        if (
            self._retired
            or not self._running
            or owner_generation != self._owner_generation
            or token != self._token
        ):
            return
        self._in_flight = False
        if not bool(getattr(result, "success", False)) or not isinstance(
            getattr(result, "result", None), CpuRamSample
        ):
            self._schedule_sample(SAMPLE_INTERVAL_MS)
            return
        self._revision += 1
        self._snapshot = SystemStatsRuntimeSnapshot(
            revision=self._revision,
            accepted_monotonic=time.monotonic(),
            sample=result.result,
        )
        for lease in list(self._active_leases):
            lease._deliver_snapshot(self._snapshot)
        # Fixed delay is measured from completion, so there is never a queued
        # telemetry pulse competing with an already-running collection.
        self._schedule_sample(SAMPLE_INTERVAL_MS)


class SystemStatsRuntimeService:
    """Per-display consumer lease for one shared runtime-generation owner."""

    def __init__(
        self,
        *,
        shared: bool = True,
        runtime_generation: Any = None,
        source_factory: SystemStatsSourceFactory = WholeSystemCpuRamSource,
        schedule: OneShotScheduler = _default_schedule,
        submit_factory: Callable[[Any], TaskSubmitter] = _default_submit,
        ui_dispatch: UiDispatcher = _default_ui_dispatch,
    ) -> None:
        self._shared = bool(shared)
        self._runtime_generation = runtime_generation
        self._source_factory = source_factory
        self._schedule = schedule
        self._submit_factory = submit_factory
        self._ui_dispatch = ui_dispatch
        self._thread_manager: Any = None
        self._consumer_ref: weakref.ReferenceType | None = None
        self._owner: _SharedSystemStatsOwner | None = None
        self._running = False
        self._retired = False

    @property
    def runtime_generation(self) -> Any:
        return self._runtime_generation

    @property
    def shared_owner(self) -> _SharedSystemStatsOwner | None:
        return self._owner

    def set_thread_manager(self, thread_manager: Any) -> None:
        self._thread_manager = thread_manager

    def attach_consumer(self, consumer: Any) -> None:
        if self._retired:
            raise RuntimeError("cannot attach to retired System Stats service")
        if self._consumer() is not None and self._consumer() is not consumer:
            raise RuntimeError("System Stats lease already belongs to another consumer")
        if self._owner is not None:
            return
        self._consumer_ref = weakref.ref(consumer)
        generation = getattr(consumer, "_runtime_generation", None)
        if generation is not None:
            self._runtime_generation = generation
        if self._thread_manager is None:
            self._thread_manager = getattr(consumer, "_thread_manager", None)
        if self._runtime_generation is None and self._thread_manager is None:
            self._consumer_ref = None
            raise RuntimeError(
                "shared System Stats lease requires runtime generation or ThreadManager"
            )
        key = _owner_key(self._runtime_generation, self._thread_manager)
        owner = _SHARED_SYSTEM_STATS_OWNERS.get(key) if self._shared else None
        if owner is None or owner.is_retired():
            owner = _SharedSystemStatsOwner(
                thread_manager=self._thread_manager,
                runtime_generation=self._runtime_generation,
                source_factory=self._source_factory,
                schedule=self._schedule,
                submit=self._submit_factory(self._thread_manager),
                ui_dispatch=self._ui_dispatch,
                registry_key=key if self._shared else None,
            )
            if self._shared:
                _SHARED_SYSTEM_STATS_OWNERS[key] = owner
        try:
            owner.attach(self)
        except Exception:
            self._consumer_ref = None
            if owner.is_retired() is False and self._shared and not list(owner._leases):
                owner.retire()
            raise
        self._owner = owner

    def detach_consumer(self, consumer: Any = None) -> None:
        if consumer is not None and self._consumer() is not consumer:
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
        probe = getattr(consumer, "is_system_stats_consumer_alive", None)
        try:
            return bool(probe()) if callable(probe) else False
        except Exception:
            return False

    def _deliver_snapshot(self, snapshot: SystemStatsRuntimeSnapshot) -> None:
        consumer = self._consumer()
        if not self._running or consumer is None or not self._consumer_alive():
            return
        receiver = getattr(consumer, "on_system_stats_runtime_snapshot", None)
        if callable(receiver):
            receiver(snapshot)

    def current_snapshot(self) -> SystemStatsRuntimeSnapshot | None:
        return self._owner.shared_snapshot if self._owner is not None else None

    def is_running(self) -> bool:
        return (
            self._running
            and self._owner is not None
            and self._owner.is_running()
            and not self._retired
        )

    def is_retired(self) -> bool:
        return self._retired

    def start(self) -> bool:
        if self._retired or self._owner is None:
            return False
        if self._running:
            return True
        self._running = True
        if not self._owner.activate(self):
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
