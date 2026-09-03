"""Lifetime safety regression for the Lead-B ``gc.freeze()`` GC policy.

`RuntimeGCPolicy.freeze_stable_generation()` moves the tracked startup set to the
permanent generation to end recurring Gen2 stalls. `gc.freeze()` excludes frozen
objects from *cyclic* collection until `gc.unfreeze()`, so these tests pin the
exact lifetime properties the fix relies on, and — critically — that a runtime
generation recreated *after* the freeze is still reclaimed (no accumulation
across recreations). If future work moves runtime-owned cyclic lifetime into the
pre-freeze permanent set, or breaks post-freeze collection, these fail.
"""
from __future__ import annotations

import gc
import weakref

import pytest

from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController


def _build_generation(generation: int) -> VisualizerRuntimeController:
    controller = VisualizerRuntimeController(
        runtime_generation=generation,
        bar_count=24,
        initial_mode="bubble",
        engine_factory=lambda _n: object(),
    )
    controller.enabled = True
    controller.logical_mailbox.publish("state", generation=generation, activation_id=0)
    return controller


@pytest.fixture(autouse=True)
def _restore_freeze_state():
    # Never leak freeze state to other tests, even on failure.
    yield
    gc.unfreeze()
    gc.collect()


# --- CPython semantics the fix depends on ---------------------------------

def test_frozen_object_is_still_destroyed_by_refcount():
    class _Held:
        pass

    gc.collect()
    obj = [_Held()]
    w = weakref.ref(obj[0])
    gc.freeze()
    obj.clear()  # refcount -> 0
    assert w() is None  # freed immediately despite being frozen


def test_frozen_cycle_is_pinned_until_unfreeze():
    gc.collect()

    class _N:
        pass

    a, b = _N(), _N()
    a.other = b
    b.other = a
    wa, wb = weakref.ref(a), weakref.ref(b)
    gc.freeze()
    del a, b
    gc.collect(2)
    assert wa() is not None and wb() is not None  # cyclic garbage pinned while frozen
    gc.unfreeze()
    gc.collect()
    assert wa() is None and wb() is None


def test_post_freeze_cycle_is_collected_normally():
    gc.collect()

    class _N:
        pass

    gc.freeze()
    a, b = _N(), _N()
    a.other = b
    b.other = a
    wa, wb = weakref.ref(a), weakref.ref(b)
    del a, b
    gc.collect()
    assert wa() is None and wb() is None  # allocated after freeze -> normal collection


# --- The runtime-generation invariant -------------------------------------

def test_post_freeze_runtime_generations_do_not_accumulate():
    """A runtime generation created AND retired after the freeze must be
    reclaimed. This is the anti-accumulation guarantee across recreations."""
    gc.collect()
    gc.freeze()
    survivors = []
    for generation in range(1, 6):
        controller = _build_generation(generation)
        ref = weakref.ref(controller)
        controller.stop_logical_runtime()
        del controller
        gc.collect()
        if ref() is not None:
            survivors.append(generation)
    assert survivors == [], (
        "post-freeze runtime generations were pinned "
        f"{survivors}; runtime-owned cyclic lifetime must not enter the frozen set"
    )


def test_pre_freeze_generation_is_a_bounded_pin_released_on_unfreeze():
    """The one generation live at freeze time is pinned (bounded), and is
    released once unfrozen — never a leak beyond RUN stop."""
    gc.collect()
    gen0 = _build_generation(0)
    ref = weakref.ref(gen0)
    gc.freeze()
    gen0.stop_logical_runtime()
    del gen0
    gc.collect(2)
    assert ref() is not None  # pinned while frozen (documents the bounded cost)
    gc.unfreeze()
    gc.collect(2)
    assert ref() is None  # fully released on unfreeze (stop)
