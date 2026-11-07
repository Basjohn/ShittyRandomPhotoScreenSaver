"""Every display generation is frozen at its coordinated reveal and thawed before it retires (gen2 stalls, 7 Nov 2026).

Until 7 Nov the RUN froze its heap once, from a 45 s timer, and the first Settings visit (or any runtime retirement)
thawed it for the rest of the RUN: every later gen2 collection scanned the whole long-lived heap again (the 86-161 ms
logical-thread stalls). Now the engine's coordinated reveal (the generation's warm-up end) freezes the generation it
revealed, and every display teardown thaws it before its destruction barrier, so the next generation is frozen at its
own reveal. Structural only: these tests drive the real reveal handler and the real teardown with stand-in
collaborators and check what the collector can scan, never a timing.
"""
from __future__ import annotations

import gc
import weakref

import pytest

from core.performance.gc_policy import RuntimeGCPolicy
from engine import engine_lifecycle
from engine.screensaver_engine import EngineState, ScreensaverEngine


class _Engine:
    """The reveal handler's and the teardown's collaborators, nothing else (the methods under test are the real ones)."""

    _runtime_lifecycle_event = "test"
    _on_startup_reveal_completed = ScreensaverEngine._on_startup_reveal_completed
    _freeze_revealed_generation = ScreensaverEngine.__dict__.get("_freeze_revealed_generation", lambda self: None)

    def __init__(self, policy, state=EngineState.RUNNING):
        self._gc_policy = policy
        self._state = state
        self.display_manager = _Manager()

    def _get_state(self):
        return self._state

    def _is_runtime_identity_current(self, *_args):
        return True

    def _end_replacement_watchdog(self, _reason):
        pass

    def _prepare_next_transition(self):
        pass

    def _record_stale_runtime_callback(self, *_args):
        pass

    def reveal(self):
        self._on_startup_reveal_completed(1, self.display_manager, 1)

    def teardown(self):
        engine_lifecycle.teardown_display_runtime(self, reason="topology_change")
        self.display_manager = _Manager()


class _Manager:
    """A retiring display generation's Python heap, released by reference counting (the barrier's standard)."""

    def __init__(self):
        self.graph = [{"payload": [object() for _ in range(50)]} for _ in range(40)]

    def get_display_count(self):
        return 0

    def cleanup(self):
        pass

    def retire_runtime(self):
        pass


@pytest.fixture
def policy():
    policy = RuntimeGCPolicy()
    policy.start()
    yield policy
    policy.stop()
    gc.unfreeze()


def _scanned(obj) -> bool:
    """Whether the collector's generations (what a gen2 collection scans) hold ``obj``; frozen objects are not."""
    return any(candidate is obj for candidate in gc.get_objects())


def test_the_coordinated_reveal_freezes_the_generation_it_revealed(policy):
    engine = _Engine(policy)
    witness = engine.display_manager.graph[0]
    assert _scanned(witness)
    engine.reveal()
    assert policy.frozen and gc.get_freeze_count() > 0
    assert not _scanned(witness)            # the revealed generation's heap left every gen2 scan


def test_a_paused_engine_never_freezes_at_a_reveal(policy):
    _Engine(policy, state=EngineState.STOPPED).reveal()
    assert not policy.frozen and gc.get_freeze_count() == 0


def test_every_teardown_thaws_the_generation_before_its_barrier(policy):
    engine = _Engine(policy)
    engine.reveal()
    assert policy.frozen
    engine.teardown()                       # a topology replacement: does not go through stop()
    assert not policy.frozen and gc.get_freeze_count() == 0


def test_generation_swaps_refreeze_each_generation_and_never_pin_a_retired_one(policy):
    """25 reveal/teardown swaps: each generation is frozen while live and freed at its teardown; the frozen set
    never accumulates retired generations (the frozen count returns to zero at every teardown)."""
    engine = _Engine(policy)
    retired = []
    for _swap in range(25):
        engine.reveal()
        assert policy.frozen and not _scanned(engine.display_manager.graph[0])
        frozen_live = gc.get_freeze_count()
        retired.append(weakref.ref(engine.display_manager))
        engine.teardown()
        assert retired[-1]() is None                     # released at its teardown by refcount: nothing pinned
        assert gc.get_freeze_count() == 0 and frozen_live > 0
    assert all(ref() is None for ref in retired)
