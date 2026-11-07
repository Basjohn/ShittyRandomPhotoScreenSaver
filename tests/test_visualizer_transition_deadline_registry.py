"""AC-10: the Visualizer owner's mode-transition deadline is a generation-owned ``ThreadManager.single_shot``.

A mode switch arms one bounded deadline. Retiring the owner's display generation
(``ThreadManager.cancel_scheduled_single_shots``, the teardown edge) must cancel it, so it never runs; a live
generation's deadline still fires (control). Until AC-10 the deadline was a raw ``QTimer.singleShot`` the registry
could not see.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from core.threading.manager import ThreadManager
from widgets.spotify_visualizer import quick_display_visualizer_owner as owner_module
from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner


def _owner(generation: str, reported: list) -> QuickDisplayVisualizerOwner:
    owner = QuickDisplayVisualizerOwner.__new__(QuickDisplayVisualizerOwner)
    owner._runtime = SimpleNamespace(runtime_generation=generation)
    owner._retired = False
    owner._started = True
    owner._controller = SimpleNamespace(mode_id="bubble")
    owner._mode_transition_phase = "idle"
    owner._mode_transition_started_at = 0.0
    owner._mode_transition_fade = 1.0
    owner._pending_mode_activation = None
    owner._transition_request_serial = 0
    owner._transition_recovery_issued = False
    owner._transition_clock = lambda: 1.0
    owner._transition_failure_callback = reported.append
    return owner


def _switch_mode(owner: QuickDisplayVisualizerOwner) -> None:
    assert owner.request_mode_change(
        "spectrum", settings_model=None, resolved_activation=None, technical_cache={},
        logical_kwargs={}, presentation_kwargs={},
    )
    assert owner._mode_transition_phase == "fading_out"


@pytest.mark.qt
def test_retiring_the_generation_cancels_a_pending_mode_transition_deadline(monkeypatch, qt_app, qtbot):
    monkeypatch.setattr(owner_module, "_ACTIVATION_TRANSACTION_DEADLINE_MS", 40)
    # The deadline's fading_out branch restores the outgoing scene; record that it ran.
    retired_reported: list = []
    live_reported: list = []
    retired_generation = f"ac10-retired-{uuid.uuid4().hex}"
    retired = _owner(retired_generation, retired_reported)
    live = _owner(f"ac10-live-{uuid.uuid4().hex}", live_reported)
    restored: list = []
    for owner, name in ((retired, "retired"), (live, "live")):
        owner._resolve_current_presentation = lambda: "outgoing_stage"
        owner._apply_resolved_presentation = lambda _stage, name=name: restored.append(name)
        owner._request_retained_present = lambda: None

    _switch_mode(retired)
    _switch_mode(live)
    cancelled = ThreadManager.cancel_scheduled_single_shots(retired_generation)   # the generation's teardown edge

    qtbot.waitUntil(lambda: "live" in restored, timeout=3000)   # control: the live generation's deadline fires
    qtbot.wait(150)
    assert restored == ["live"], "the retired generation's transition deadline ran after its cancellation"
    assert retired._mode_transition_phase == "fading_out"
    assert cancelled == 1
    assert live._mode_transition_phase == "idle"
    assert retired_reported == [] and live_reported == []


def test_the_deadline_holds_its_owner_weakly_and_is_tagged_with_the_display_generation(monkeypatch):
    scheduled: list = []
    monkeypatch.setattr(
        ThreadManager, "single_shot", staticmethod(lambda ms, func, *args: scheduled.append((ms, func, args))),
    )
    owner = _owner("ac10-tag", [])
    _switch_mode(owner)

    (ms, func, args), = scheduled
    assert ms == owner_module._ACTIVATION_TRANSACTION_DEADLINE_MS
    # A bound method: ThreadManager keeps a WeakMethod and reads the generation from its owner.
    assert func.__self__ is owner and func.__func__ is QuickDisplayVisualizerOwner._on_transition_deadline
    assert args == (owner._transition_request_serial,)
    assert owner._runtime_generation == "ac10-tag"
