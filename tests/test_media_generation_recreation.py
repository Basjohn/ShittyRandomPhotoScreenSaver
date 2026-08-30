"""Deterministic same-process Media replacement-generation recreation (H1).

Evidence: ``H_Post_Cutover_Runtime_Reality_Corrections.md`` §3 and
``Post_Cutover_Operator_Observation_Ledger_2026-08-30.md`` O-001/O-002 — leaving
Settings or CUSTOM on the dual-display source build tears down the old
two-display generation cleanly, then dies while screen 1's Media/native services
activate in the *replacement* generation.

Production replaces the whole ``DisplayManager`` with an incremented
``runtime_generation`` while reusing the one app-scoped ``ThreadManager``. The
three shared Media owners (``media`` transport, ``spotify_volume`` app-volume,
``mute_button`` system-mute) are keyed by ``("runtime", runtime_generation)`` and
retired by the destruction barrier before the replacement builds.

This regression proves the *deterministic* half of H1: that the generation-keyed
owner lifecycle is clean across a same-process replacement — old owners retire,
the replacement builds fresh owners under the new generation on the same
ThreadManager, no owner is reused across generations, and every shared registry
returns to zero after teardown. It deliberately does **not** exercise the native
COM/WinRT/pycaw path; a native access violation cannot be surfaced by fakes, so
that half is an operator runtime smoke (see the H doc). Keeping this bar GREEN
means any future regression here is a Python-lifecycle fault, which in turn keeps
the native bisect honestly scoped to native ownership.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from core.threading.manager import ThreadManager
from widgets.media_runtime import (
    MediaRuntimeService,
    reset_shared_media_runtime_for_tests,
    shared_media_owner_count,
)
from widgets.media_volume_runtime import (
    MediaVolumeRuntimeService,
    reset_shared_media_volume_runtime_for_tests,
    shared_media_volume_owner_count,
)
from widgets.system_mute_runtime import (
    SystemMuteRuntimeService,
    reset_shared_system_mute_runtime_for_tests,
    shared_system_mute_owner_count,
)


@dataclass
class _TaskResult:
    success: bool
    result: Any = None


class _Timer:
    def __init__(self, interval: int, callback) -> None:
        self.interval = int(interval)
        self.callback = callback
        self.active = True

    def isActive(self) -> bool:
        return self.active

    def setInterval(self, interval: int) -> None:
        self.interval = int(interval)

    def start(self) -> None:
        self.active = True

    def stop(self) -> None:
        self.active = False

    def deleteLater(self) -> None:
        self.active = False


class _ThreadManager:
    """One app-scoped fake ThreadManager reused across runtime generations."""

    def __init__(self) -> None:
        self.jobs: list[tuple[Any, Any]] = []
        self.timers: list[_Timer] = []

    def schedule_recurring(self, interval, callback, **_kwargs) -> _Timer:
        timer = _Timer(interval, callback)
        self.timers.append(timer)
        return timer

    def submit_io_task(self, worker, callback=None, **_kwargs) -> None:
        self.jobs.append((worker, callback))

    def drain(self) -> None:
        while self.jobs:
            worker, callback = self.jobs.pop(0)
            result = worker()
            if callback is not None:
                callback(_TaskResult(success=True, result=result))


class _MediaController:
    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.thread_manager = None
        self.runtime_generation = None
        self.retire_calls = 0

    def set_thread_manager(self, thread_manager) -> None:
        self.thread_manager = thread_manager

    def set_runtime_generation(self, runtime_generation) -> None:
        self.runtime_generation = runtime_generation

    def retire(self) -> None:
        self.retire_calls += 1

    def get_current_track_from_io_worker(self, fallback_providers=()):
        return None, None

    def is_app_process_running(self) -> bool:
        return False


class _MediaControllerFactory:
    def __init__(self) -> None:
        self.built: list[_MediaController] = []

    def __call__(self, *, thread_manager, app_filter):
        controller = _MediaController(str(app_filter))
        controller.set_thread_manager(thread_manager)
        self.built.append(controller)
        return controller


class _VolumeController:
    def __init__(self, provider: str) -> None:
        self.provider = provider

    def is_available(self) -> bool:
        return True

    def configure_volume_target(self, provider, source_app_user_model_id="") -> bool:
        self.provider = str(provider)
        return True

    def get_volume(self) -> float:
        return 0.5

    def set_volume(self, level: float) -> bool:
        return True


class _VolumeControllerFactory:
    def __init__(self) -> None:
        self.built: list[_VolumeController] = []

    def __call__(self, provider: str) -> _VolumeController:
        controller = _VolumeController(provider)
        self.built.append(controller)
        return controller


class _MuteBackend:
    def is_available(self) -> bool:
        return True

    def get_mute(self) -> bool:
        return False

    def toggle_mute(self):
        return True

    def step_volume(self, delta):
        return 0.5


class _MuteBackendFactory:
    def __init__(self) -> None:
        self.built: list[_MuteBackend] = []

    def __call__(self) -> _MuteBackend:
        backend = _MuteBackend()
        self.built.append(backend)
        return backend


class _MediaConsumer:
    def __init__(self, thread_manager, generation: int) -> None:
        self._thread_manager = thread_manager
        self._runtime_generation = generation
        self.alive = True

    def is_media_consumer_alive(self) -> bool:
        return self.alive

    def is_media_volume_consumer_alive(self) -> bool:
        return self.alive

    def is_system_mute_consumer_alive(self) -> bool:
        return self.alive

    # Presentation delivery seams (unused values, must not raise).
    def on_media_runtime_snapshot(self, *_a, **_k) -> None: ...
    def on_media_runtime_provider_changed(self, *_a, **_k) -> None: ...
    def on_media_runtime_volume_target(self, *_a, **_k) -> None: ...
    def on_media_volume_runtime_snapshot(self, *_a, **_k) -> None: ...
    def on_system_mute_runtime_snapshot(self, *_a, **_k) -> None: ...


@dataclass
class _MediaFamily:
    """The three neutral Media leases owned for one display in one generation."""

    consumer: _MediaConsumer
    media: MediaRuntimeService
    volume: MediaVolumeRuntimeService
    mute: SystemMuteRuntimeService

    def start(self) -> None:
        assert self.media.start() is True
        assert self.volume.start() is True
        assert self.mute.start() is True

    def owners(self) -> tuple[Any, Any, Any]:
        return (
            self.media.shared_owner,
            self.volume.shared_owner,
            self.mute.shared_owner,
        )

    def retire(self) -> None:
        # Mirrors WidgetRuntimeManager.retire_all_services on the destruction
        # barrier: every owned lease is retired exactly once.
        self.media.retire()
        self.volume.retire()
        self.mute.retire()


def _build_media_family(
    thread_manager: _ThreadManager,
    *,
    generation: int,
    media_factory: _MediaControllerFactory,
    volume_factory: _VolumeControllerFactory,
    mute_factory: _MuteBackendFactory,
) -> _MediaFamily:
    """Build one display's three Media leases for a runtime generation."""

    consumer = _MediaConsumer(thread_manager, generation)
    media = MediaRuntimeService(
        provider="spotify", shared=True, controller_factory=media_factory
    )
    media.set_thread_manager(thread_manager)
    media.attach_consumer(consumer)

    volume = MediaVolumeRuntimeService(
        provider="spotify", shared=True, controller_factory=volume_factory
    )
    volume.set_thread_manager(thread_manager)
    volume.attach_consumer(consumer)

    mute = SystemMuteRuntimeService(shared=True, backend_factory=mute_factory)
    mute.set_thread_manager(thread_manager)
    mute.attach_consumer(consumer)

    return _MediaFamily(consumer=consumer, media=media, volume=volume, mute=mute)


@pytest.fixture(autouse=True)
def _isolated_shared_owners(monkeypatch):
    from core.media.media_native_trace import reset_media_native_trace_for_tests

    reset_shared_media_runtime_for_tests()
    reset_shared_media_volume_runtime_for_tests()
    reset_shared_system_mute_runtime_for_tests()
    reset_media_native_trace_for_tests()
    monkeypatch.setattr(
        ThreadManager, "run_on_ui_thread", staticmethod(lambda fn: (fn(), True)[1])
    )
    monkeypatch.setattr(
        ThreadManager, "single_shot", staticmethod(lambda *a, **k: None)
    )
    yield
    reset_shared_media_runtime_for_tests()
    reset_shared_media_volume_runtime_for_tests()
    reset_shared_system_mute_runtime_for_tests()
    reset_media_native_trace_for_tests()


def test_replacement_generation_rebuilds_media_family_without_owner_reuse() -> None:
    tm = _ThreadManager()
    media_factory = _MediaControllerFactory()
    volume_factory = _VolumeControllerFactory()
    mute_factory = _MuteBackendFactory()

    # Generation 1: the display that carries Media (evidence's "screen 1").
    gen1 = _build_media_family(
        tm,
        generation=1,
        media_factory=media_factory,
        volume_factory=volume_factory,
        mute_factory=mute_factory,
    )
    assert shared_media_owner_count() == 1
    assert shared_media_volume_owner_count() == 1
    assert shared_system_mute_owner_count() == 1
    gen1.start()
    tm.drain()
    gen1_owners = gen1.owners()
    assert all(owner is not None for owner in gen1_owners)

    # Destruction barrier: the old generation retires before the replacement.
    gen1.retire()
    assert shared_media_owner_count() == 0
    assert shared_media_volume_owner_count() == 0
    assert shared_system_mute_owner_count() == 0

    # Generation 2: same process, same ThreadManager, incremented generation.
    gen2 = _build_media_family(
        tm,
        generation=2,
        media_factory=media_factory,
        volume_factory=volume_factory,
        mute_factory=mute_factory,
    )
    assert shared_media_owner_count() == 1
    assert shared_media_volume_owner_count() == 1
    assert shared_system_mute_owner_count() == 1
    gen2.start()
    tm.drain()
    gen2_owners = gen2.owners()

    # The replacement must own fresh owners under the new generation, never the
    # retired generation-1 owners (a reused owner would carry a dead generation's
    # native controller/thread across the boundary).
    for old, new in zip(gen1_owners, gen2_owners):
        assert new is not None
        assert new is not old
        assert old.is_retired() is True
        assert new.is_retired() is False

    # A fresh native controller/backend was constructed per generation.
    assert len(media_factory.built) == 2
    assert len(volume_factory.built) == 2
    assert len(mute_factory.built) == 2

    gen2.retire()
    assert shared_media_owner_count() == 0
    assert shared_media_volume_owner_count() == 0
    assert shared_system_mute_owner_count() == 0


def test_replacement_generation_reemits_native_stage_breadcrumbs(caplog) -> None:
    tm = _ThreadManager()
    media_factory = _MediaControllerFactory()
    volume_factory = _VolumeControllerFactory()
    mute_factory = _MuteBackendFactory()

    with caplog.at_level("INFO"):
        gen1 = _build_media_family(
            tm,
            generation=1,
            media_factory=media_factory,
            volume_factory=volume_factory,
            mute_factory=mute_factory,
        )
        gen1.start()
        tm.drain()
        gen1.retire()
        gen2 = _build_media_family(
            tm,
            generation=2,
            media_factory=media_factory,
            volume_factory=volume_factory,
            mute_factory=mute_factory,
        )
        gen2.start()
        tm.drain()

    native = [m for m in caplog.messages if "[MEDIA_NATIVE][H1]" in m]

    # Each generation re-emits its own activate timeline for all three owners, so
    # the operator's dual-display bisect can see exactly which component/thread
    # reaches which stage last in the failing replacement generation.
    for component in ("media", "spotify_volume", "mute_button"):
        for generation in (1, 2):
            begin = [
                m
                for m in native
                if ("component=%s" % component) in m
                and "stage=owner_activate_begin" in m
                and ("gen=%s" % generation) in m
            ]
            assert len(begin) == 1, (component, generation, begin)

    # One-shot de-dup holds within a generation: a repeated start must not
    # re-emit that generation's activate breadcrumb.
    before = len(
        [m for m in native if "component=media" in m and "stage=owner_activate_begin" in m]
    )
    gen2.media.start()
    after = [
        m
        for m in caplog.messages
        if "[MEDIA_NATIVE][H1]" in m
        and "component=media" in m
        and "stage=owner_activate_begin" in m
    ]
    assert len(after) == before

    gen2.retire()
