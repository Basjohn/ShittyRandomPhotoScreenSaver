"""Shared presentation-neutral app-volume ownership for Media (Phase E1).

``MediaVolumeRuntimeService`` is a per-display lease.  Production leases in
one runtime generation join a single owner for the Core Audio controller,
accepted provider/process target, read/write generations, optimistic level and
write debounce. Retained Quick remains the presentation/input consumer.
"""
from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any, Callable
import weakref

from core.logging.logger import get_logger, is_verbose_logging
from core.media.provider_registry import (
    get_provider_process_exe_name_for_source,
    preserve_provider_setting,
    provider_supports_app_volume,
)
from core.threading.manager import ThreadManager

logger = get_logger(__name__)


@dataclass(frozen=True)
class MediaVolumeRuntimeSnapshot:
    """One coherent app-volume revision projected to active presenters."""

    revision: int
    provider: str
    browser_process: str | None
    supported: bool
    available: bool
    level: float
    source: str


VolumeControllerFactory = Callable[[str], Any]


def _create_volume_controller(provider: str) -> Any:
    # Keep pycaw/controller implementation dormant until this service is built.
    from core.media.spotify_volume import SpotifyVolumeController

    return SpotifyVolumeController(provider=provider)


_SHARED_MEDIA_VOLUME_OWNERS: dict[
    tuple[str, object], "_SharedMediaVolumeRuntimeOwner"
] = {}


def _shared_owner_key(runtime_generation: Any, thread_manager: Any) -> tuple[str, object]:
    if runtime_generation is not None:
        return ("runtime", runtime_generation)
    return ("thread_manager", id(thread_manager))


def _drop_shared_owner(
    key: tuple[str, object], owner: "_SharedMediaVolumeRuntimeOwner"
) -> None:
    if _SHARED_MEDIA_VOLUME_OWNERS.get(key) is owner:
        _SHARED_MEDIA_VOLUME_OWNERS.pop(key, None)


def shared_media_volume_owner_count() -> int:
    """Return the live shared-owner count for focused cardinality tests."""

    return len(_SHARED_MEDIA_VOLUME_OWNERS)


def reset_shared_media_volume_runtime_for_tests() -> None:
    """Retire all process-shared app-volume owners (test isolation only)."""

    for owner in list(_SHARED_MEDIA_VOLUME_OWNERS.values()):
        owner.retire()
    _SHARED_MEDIA_VOLUME_OWNERS.clear()


class _SharedMediaVolumeRuntimeOwner:
    """One runtime-generation app-volume controller and state authority."""

    _READ_THROTTLE_SEC = 1.25
    _WRITE_DEBOUNCE_MS = 80

    def __init__(
        self,
        *,
        provider: str,
        thread_manager: Any,
        runtime_generation: Any,
        controller: Any = None,
        controller_factory: VolumeControllerFactory = _create_volume_controller,
        registry_key: tuple[str, object] | None = None,
        allow_direct_calls: bool = False,
    ) -> None:
        self._provider = preserve_provider_setting(provider)
        self._thread_manager = thread_manager
        self._runtime_generation = runtime_generation
        self._registry_key = registry_key
        self._allow_direct_calls = bool(allow_direct_calls)
        self._controller_lock = threading.Lock()
        self._controller = controller
        if self._controller is None:
            try:
                self._controller = controller_factory(self._provider)
            except Exception:
                logger.error(
                    "[MEDIA_VOLUME_RUNTIME] Controller construction failed closed",
                    exc_info=True,
                )
                self._controller = None

        self._leases: weakref.WeakSet[MediaVolumeRuntimeService] = weakref.WeakSet()
        self._active_leases: weakref.WeakSet[MediaVolumeRuntimeService] = weakref.WeakSet()
        self._running = False
        self._retired = False
        self._owner_generation = 0
        self._target_generation = 0
        self._read_request_id = 0
        self._read_in_flight_request = 0
        self._last_read_request_ts = 0.0
        self._debounce_token = 0
        self._pending_volume: float | None = None
        self._write_request_id = 0

        self._browser_process: str | None = None
        self._supported = False
        self._available = self._controller_is_available()
        self._level = 1.0
        self._revision = 0
        self._source = "initial"
        self._configure_target(self._provider, "")
        self._publish(source="initial", notify=False)

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def controller(self) -> Any:
        """Read-only diagnostic for focused owner-cardinality tests."""

        return self._controller

    @property
    def owner_generation(self) -> int:
        return self._owner_generation

    @property
    def target_generation(self) -> int:
        return self._target_generation

    @property
    def read_request_id(self) -> int:
        return self._read_request_id

    @property
    def write_request_id(self) -> int:
        return self._write_request_id

    @property
    def pending_volume(self) -> float | None:
        return self._pending_volume

    def is_running(self) -> bool:
        return self._running and not self._retired

    def is_retired(self) -> bool:
        return self._retired

    def active_consumer_count(self) -> int:
        return sum(1 for lease in list(self._active_leases) if lease._consumer_alive())

    def attached_consumer_count(self) -> int:
        return sum(1 for lease in list(self._leases) if lease._consumer_alive())

    def current_snapshot(self) -> MediaVolumeRuntimeSnapshot:
        return MediaVolumeRuntimeSnapshot(
            revision=self._revision,
            provider=self._provider,
            browser_process=self._browser_process,
            supported=self._supported,
            available=self._available,
            level=self._level,
            source=self._source,
        )

    def attach(self, lease: "MediaVolumeRuntimeService") -> None:
        if self._retired:
            raise RuntimeError("cannot attach to a retired Media volume owner")
        if self._thread_manager is None and lease._thread_manager is not None:
            self._thread_manager = lease._thread_manager
        elif (
            lease._thread_manager is not None
            and self._thread_manager is not None
            and lease._thread_manager is not self._thread_manager
        ):
            raise RuntimeError("shared Media volume consumers must use one ThreadManager")
        if (
            self._runtime_generation is not None
            and lease.runtime_generation is not None
            and lease.runtime_generation != self._runtime_generation
        ):
            raise RuntimeError("shared Media volume runtime generation mismatch")
        if lease.configured_provider != self._provider:
            logger.warning(
                "[MEDIA_VOLUME_RUNTIME] Joining canonical provider %s with stale %s",
                self._provider,
                lease.configured_provider,
            )
        self._leases.add(lease)

    def detach(self, lease: "MediaVolumeRuntimeService") -> None:
        self.deactivate(lease)
        self._leases.discard(lease)
        if not list(self._leases):
            self.retire()

    def activate(self, lease: "MediaVolumeRuntimeService") -> bool:
        if self._retired or lease not in self._leases:
            return False
        if self._thread_manager is None and not self._allow_direct_calls:
            logger.error("[MEDIA_VOLUME_RUNTIME] Cannot start shared owner without ThreadManager")
            return False
        self._active_leases.add(lease)
        started_owner = False
        if not self._running:
            from core.media.media_native_trace import trace_media_native_stage

            trace_media_native_stage(
                component="spotify_volume",
                stage="owner_activate_begin",
                generation=self._runtime_generation,
            )
            self._running = True
            self._owner_generation += 1
            started_owner = True
            trace_media_native_stage(
                component="spotify_volume",
                stage="owner_activate_complete",
                generation=self._runtime_generation,
            )
        lease._deliver_snapshot(self.current_snapshot())
        if started_owner:
            self.request_sync(force=True)
        return True

    def deactivate(self, lease: "MediaVolumeRuntimeService") -> None:
        self._active_leases.discard(lease)
        if list(self._active_leases) or not self._running:
            return
        self._running = False
        self._owner_generation += 1
        self._invalidate_pending_work()

    def set_provider(self, provider: object) -> bool:
        normalized = preserve_provider_setting(provider)
        if normalized == self._provider:
            return False
        self._provider = normalized
        self._browser_process = None
        self._invalidate_target()
        self._configure_target(normalized, "")
        self._publish(source="provider")
        if self._running:
            self.request_sync(force=True)
        return True

    def set_runtime_source(
        self, provider: object, source_app_user_model_id: object
    ) -> bool:
        normalized = preserve_provider_setting(provider)
        if normalized != self._provider or normalized != "spotify_browser":
            return False
        browser_process = get_provider_process_exe_name_for_source(
            normalized, source_app_user_model_id
        )
        if (
            browser_process == self._browser_process
            and self._supported == (browser_process is not None)
        ):
            return False
        self._invalidate_target()
        configured = self._configure_target(normalized, source_app_user_model_id)
        self._browser_process = browser_process if configured else None
        self._publish(source="runtime_target")
        if self._running and self._supported:
            self.request_sync(force=True)
        return True

    def request_sync(self, *, force: bool = False) -> bool:
        if not self._running or not self._supported or not self._available:
            return False
        now = time.monotonic()
        if not force and now - self._last_read_request_ts < self._READ_THROTTLE_SEC:
            return False
        self._last_read_request_ts = now
        self._read_request_id += 1
        request_id = self._read_request_id
        self._read_in_flight_request = request_id
        owner_generation = self._owner_generation
        target_generation = self._target_generation

        if self._thread_manager is None:
            if not self._allow_direct_calls:
                return False
            logger.warning(
                "[MEDIA_VOLUME_RUNTIME][COMPAT] Direct standalone volume read without ThreadManager"
            )
            value = self._read_volume_for_target(target_generation)
            self._accept_read(value, owner_generation, target_generation, request_id)
            return True

        owner_ref = weakref.ref(self)

        def _read() -> float | None:
            owner = owner_ref()
            if owner is None:
                return None
            return owner._read_volume_for_target(target_generation)

        _read._srpss_runtime_generation = self._runtime_generation

        def _result(task_result: Any) -> None:
            value = None
            try:
                if getattr(task_result, "success", False):
                    value = getattr(task_result, "result", None)
            except Exception:
                value = None

            def _apply() -> None:
                owner = owner_ref()
                if owner is not None:
                    owner._accept_read(
                        value, owner_generation, target_generation, request_id
                    )

            _apply._srpss_runtime_generation = self._runtime_generation
            if not ThreadManager.run_on_ui_thread(_apply):
                owner = owner_ref()
                if owner is not None and owner._read_in_flight_request == request_id:
                    owner._read_in_flight_request = 0

        _result._srpss_runtime_generation = self._runtime_generation
        try:
            self._thread_manager.submit_io_task(_read, callback=_result)
        except Exception:
            if self._read_in_flight_request == request_id:
                self._read_in_flight_request = 0
            logger.error("[MEDIA_VOLUME_RUNTIME] Failed to schedule volume read", exc_info=True)
            return False
        return True

    def set_volume_optimistic(self, level: float) -> bool:
        if not self._running or not self._supported or not self._available:
            return False
        clamped = float(max(0.0, min(1.0, level)))
        self._level = clamped
        self._publish(source="optimistic")
        self._pending_volume = clamped
        self._debounce_token += 1
        token = self._debounce_token
        owner_generation = self._owner_generation
        target_generation = self._target_generation
        owner_ref = weakref.ref(self)

        def _flush() -> None:
            owner = owner_ref()
            if owner is not None:
                owner._flush_pending(
                    token=token,
                    owner_generation=owner_generation,
                    target_generation=target_generation,
                )

        _flush._srpss_runtime_generation = self._runtime_generation
        ThreadManager.single_shot(self._WRITE_DEBOUNCE_MS, _flush)
        return True

    def retire(self) -> None:
        if self._retired:
            return
        self._running = False
        self._retired = True
        self._owner_generation += 1
        self._invalidate_pending_work()
        self._active_leases.clear()
        self._leases.clear()
        self._controller = None
        self._thread_manager = None
        if self._registry_key is not None:
            _drop_shared_owner(self._registry_key, self)

    def _controller_is_available(self) -> bool:
        controller = self._controller
        if controller is None:
            return False
        try:
            return bool(controller.is_available())
        except Exception:
            return False

    def _configure_target(self, provider: str, source_id: object) -> bool:
        controller = self._controller
        configured = False
        if controller is not None:
            try:
                with self._controller_lock:
                    configured = bool(
                        controller.configure_volume_target(provider, source_id)
                    )
            except Exception:
                logger.debug(
                    "[MEDIA_VOLUME_RUNTIME] Target configuration failed",
                    exc_info=True,
                )
        if provider == "spotify_browser" and get_provider_process_exe_name_for_source(
            provider, source_id
        ) is None:
            configured = False
        self._available = self._controller_is_available()
        self._supported = bool(
            configured
            and (
                provider_supports_app_volume(provider)
                or provider == "spotify_browser"
            )
        )
        return configured

    def _invalidate_target(self) -> None:
        self._target_generation += 1
        self._invalidate_pending_work()

    def _invalidate_pending_work(self) -> None:
        self._read_request_id += 1
        self._read_in_flight_request = 0
        self._debounce_token += 1
        self._pending_volume = None

    def _read_volume_for_target(self, target_generation: int) -> float | None:
        controller = self._controller
        if controller is None:
            return None
        try:
            with self._controller_lock:
                if (
                    self._retired
                    or not self._running
                    or target_generation != self._target_generation
                ):
                    return None
                # H1 diagnostic: the pycaw/Core Audio enumeration runs on an IO
                # worker; record that thread once per owner because the evidence
                # ends on "comtypes/Core Audio release" during replacement.
                from core.media.media_native_trace import trace_media_native_stage

                trace_media_native_stage(
                    component="spotify_volume",
                    stage="core_audio_enumerate",
                    generation=self._runtime_generation,
                )
                return controller.get_volume()
        except Exception:
            logger.debug("[MEDIA_VOLUME_RUNTIME] Volume read failed", exc_info=True)
            return None

    def _accept_read(
        self,
        value: Any,
        owner_generation: int,
        target_generation: int,
        request_id: int,
    ) -> None:
        if self._read_in_flight_request == request_id:
            self._read_in_flight_request = 0
        if (
            self._retired
            or not self._running
            or owner_generation != self._owner_generation
            or target_generation != self._target_generation
            or request_id != self._read_request_id
            or not isinstance(value, float)
        ):
            return
        self._level = float(max(0.0, min(1.0, value)))
        self._publish(source="read")

    def _flush_pending(
        self,
        *,
        token: int,
        owner_generation: int,
        target_generation: int,
    ) -> None:
        if (
            self._retired
            or not self._running
            or owner_generation != self._owner_generation
            or target_generation != self._target_generation
            or token != self._debounce_token
        ):
            return
        level = self._pending_volume
        self._pending_volume = None
        if level is None:
            return
        self._write_request_id += 1
        request_id = self._write_request_id

        if self._thread_manager is None:
            if not self._allow_direct_calls:
                return
            logger.warning(
                "[MEDIA_VOLUME_RUNTIME][COMPAT] Direct standalone volume write without ThreadManager"
            )
            self._write_volume_for_target(
                level,
                owner_generation,
                target_generation,
                request_id,
            )
            return

        owner_ref = weakref.ref(self)

        def _write() -> bool:
            owner = owner_ref()
            if owner is None:
                return False
            return owner._write_volume_for_target(
                level,
                owner_generation,
                target_generation,
                request_id,
            )

        _write._srpss_runtime_generation = self._runtime_generation
        try:
            self._thread_manager.submit_io_task(_write)
        except Exception:
            logger.error("[MEDIA_VOLUME_RUNTIME] Failed to schedule volume write", exc_info=True)

    def _write_volume_for_target(
        self,
        level: float,
        owner_generation: int,
        target_generation: int,
        request_id: int,
    ) -> bool:
        controller = self._controller
        if controller is None:
            return False
        try:
            with self._controller_lock:
                if (
                    self._retired
                    or not self._running
                    or owner_generation != self._owner_generation
                    or target_generation != self._target_generation
                    or request_id != self._write_request_id
                ):
                    return False
                result = bool(controller.set_volume(level))
                if is_verbose_logging():
                    logger.debug(
                        "[MEDIA_VOLUME_RUNTIME] set_volume %.2f -> %s", level, result
                    )
                return result
        except Exception:
            logger.debug("[MEDIA_VOLUME_RUNTIME] Volume write failed", exc_info=True)
            return False

    def _publish(self, *, source: str, notify: bool = True) -> None:
        self._revision += 1
        self._source = source
        if not notify:
            return
        snapshot = self.current_snapshot()
        for lease in list(self._active_leases):
            lease._deliver_snapshot(snapshot)


class MediaVolumeRuntimeService:
    """Per-display lease/projection to the shared app-volume owner."""

    def __init__(
        self,
        *,
        provider: str = "spotify",
        shared: bool = True,
        controller: Any = None,
        controller_factory: VolumeControllerFactory = _create_volume_controller,
        runtime_generation: Any = None,
    ) -> None:
        if shared and controller is not None:
            raise ValueError("controller injection is isolated-standalone only")
        self._configured_provider = preserve_provider_setting(provider)
        self._shared = bool(shared)
        self._controller = controller
        self._controller_factory = controller_factory
        self._runtime_generation = runtime_generation
        self._thread_manager: Any = None
        self._consumer_ref: weakref.ReferenceType | None = None
        self._owner: _SharedMediaVolumeRuntimeOwner | None = None
        self._running = False
        self._retired = False

    @property
    def configured_provider(self) -> str:
        return self._configured_provider

    @property
    def runtime_generation(self) -> Any:
        return self._runtime_generation

    @property
    def shared_owner(self) -> _SharedMediaVolumeRuntimeOwner | None:
        return self._owner

    def current_snapshot(self) -> MediaVolumeRuntimeSnapshot | None:
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
                raise RuntimeError("shared Media volume lease cannot replace ThreadManager")

    def attach_consumer(self, consumer: Any) -> None:
        if self._retired:
            raise RuntimeError("cannot attach consumer to retired Media volume service")
        current = self._consumer()
        if current is not None and current is not consumer:
            raise RuntimeError("Media volume lease already belongs to another consumer")
        if self._owner is not None:
            if current is consumer:
                return
            raise RuntimeError("Media volume lease already has an owner")
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
                    "shared Media volume lease requires runtime generation or ThreadManager"
                )
            key = _shared_owner_key(self._runtime_generation, self._thread_manager)
            owner = _SHARED_MEDIA_VOLUME_OWNERS.get(key)
            if owner is None or owner.is_retired():
                owner = _SharedMediaVolumeRuntimeOwner(
                    provider=self._configured_provider,
                    thread_manager=self._thread_manager,
                    runtime_generation=self._runtime_generation,
                    controller_factory=self._controller_factory,
                    registry_key=key,
                )
                _SHARED_MEDIA_VOLUME_OWNERS[key] = owner
                owner_created = True
        else:
            owner = _SharedMediaVolumeRuntimeOwner(
                provider=self._configured_provider,
                thread_manager=self._thread_manager,
                runtime_generation=self._runtime_generation,
                controller=self._controller,
                controller_factory=self._controller_factory,
                allow_direct_calls=True,
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
            return bool(consumer.is_media_volume_consumer_alive())
        except Exception:
            return False

    def _deliver_snapshot(self, snapshot: MediaVolumeRuntimeSnapshot) -> None:
        consumer = self._consumer()
        if not self._running or consumer is None or not self._consumer_alive():
            return
        try:
            consumer.on_media_volume_runtime_snapshot(snapshot)
        except Exception:
            logger.debug("[MEDIA_VOLUME_RUNTIME] Snapshot delivery failed", exc_info=True)

    def start(self) -> bool:
        if self._retired or self._owner is None:
            return False
        if self._running:
            return True
        self._running = True
        try:
            activated = self._owner.activate(self)
        except Exception:
            logger.error("[MEDIA_VOLUME_RUNTIME] Lease activation failed closed", exc_info=True)
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

    def set_provider_runtime(self, provider: object) -> bool:
        owner = self._owner
        if owner is None:
            normalized = preserve_provider_setting(provider)
            changed = normalized != self._configured_provider
            self._configured_provider = normalized
            return changed
        changed = owner.set_provider(provider)
        self._configured_provider = owner.provider
        return changed

    def set_runtime_volume_source(
        self, provider: object, source_app_user_model_id: object
    ) -> bool:
        owner = self._owner
        return bool(
            owner is not None
            and owner.set_runtime_source(provider, source_app_user_model_id)
        )

    def request_sync(self, *, force: bool = False) -> bool:
        owner = self._owner
        return bool(owner is not None and owner.request_sync(force=force))

    def set_volume_optimistic(self, level: float) -> bool:
        owner = self._owner
        return bool(owner is not None and owner.set_volume_optimistic(level))
