"""One owner for the Visualizer's activation and engine edges (native core P2b; checkpoint audit 4, A4-H1).

The production Quick owner and the engine worker's session run the same control edges on one controller and engine
(``widgets/spotify_visualizer/logical_edges.py``). The same edge script goes through the owner's methods
(``start``, ``set_playing``, ``set_display_power``, ``_activate_pending_mode``) and the session's (its first input,
play edges, ``set_display_power``, ``request_mode``) on two recording engines and controllers configured alike, and
the call logs must be identical: a change to the owner's sequence reaches the worker, and a hand copy on either side
that drifts fails here. Only the hosts' own parts are outside the comparison: the owner's cadence park, reader-side
mailbox clear, Edit profile and scene binding; the session's capture-lane completion edge.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.visualizer_engine.engine_worker import EngineSession
from widgets.spotify_visualizer.feature_replay import configure_offline_controller, offline_activation_request
from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner
from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController

#: The controller's own steps that belong to the shared logical sequence (not the hosts' runtime or presentation).
_CONTROLLER_STEPS = ("stop_logical_runtime", "set_mode", "record_resolved_activation", "resolve_logical_mode_state",
                     "begin_render_activation")
_THREAD_MANAGER = object()          # one stand-in both hosts hand the engine


class _Recorder:
    """Records every public call made on it (``prefix`` + name, arguments) into a shared log."""

    def __init__(self, log: list, prefix: str = "") -> None:
        self._log, self._prefix = log, prefix

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)

        def call(*args, **kwargs):
            self._log.append((self._prefix + name, args, kwargs))

        return call


class _RecordingEngine(_Recorder):
    """A production-shaped engine whose every call is logged; it holds a retained frame (a warm engine), so every
    fence arm takes the watermark path, and each activation transaction commits a new generation and activation."""

    def __init__(self, log: list) -> None:
        super().__init__(log)
        self._audio_worker = _Recorder(log, "audio_worker.")
        self._generation = self._activation = 1

    def _record(self, name, *args, **kwargs):
        self._log.append((name, args, kwargs))

    def end_activation_transaction(self, **kwargs):
        self._record("end_activation_transaction", **kwargs)
        self._generation += 1
        self._activation += 1

    def get_generation_id(self):
        self._record("get_generation_id")
        return self._generation

    def get_activation_id(self):
        self._record("get_activation_id")
        return self._activation

    def get_latest_authoritative_frame(self):
        self._record("get_latest_authoritative_frame")
        return 1.0, self._generation, self._activation

    def get_authoritative_frame_commit_seq(self):
        self._record("get_authoritative_frame_commit_seq")
        return 7


def _controller(mode: str):
    log: list = []
    engine = _RecordingEngine(log)
    controller = VisualizerRuntimeController(runtime_generation=3, initial_mode=mode,
                                             engine_factory=lambda _count: engine)
    controller.ensure_engine()
    configure_offline_controller(controller, mode)
    controller.thread_manager = _THREAD_MANAGER
    for name in _CONTROLLER_STEPS:
        original = getattr(controller, name)

        def step(*args, _name=name, _original=original, **kwargs):
            log.append(("controller." + _name, args, kwargs))
            return _original(*args, **kwargs)

        setattr(controller, name, step)
    log.clear()
    return controller, log


class _OwnerHost:
    """The production owner's methods on a recording controller (its scene, cadence and backdrop stubbed)."""

    def __init__(self, mode: str) -> None:
        self.controller, self.log = _controller(mode)
        owner = QuickDisplayVisualizerOwner.__new__(QuickDisplayVisualizerOwner)
        owner._controller = self.controller
        owner._retired, owner._started, owner._configured, owner._bound = False, False, True, True
        owner._display_power_on, owner._engine_acquired, owner._engine_released_for_display_power = True, False, False
        owner._transition_clock = lambda: 0.0
        owner._start_logical_runtime = lambda **_kwargs: None
        owner._refresh_backdrop = lambda: None
        owner._edit_layout_profile_activator = None
        owner._activate_committed_layout_profile = lambda _target: None
        owner._pending_mode_activation = None
        owner._runtime = SimpleNamespace(
            bind_visualizer_render_source=lambda controller, **identity: controller.begin_render_activation(**identity))
        self.owner = owner

    def start(self, playing: bool) -> None:
        self.controller.playing = bool(playing)        # Media's state at configure
        self.owner.start()

    def playing(self, active: bool) -> None:
        self.owner.set_playing(active)

    def display(self, on: bool) -> None:
        self.owner.set_display_power(on)

    def activate(self, mode: str, preset: int) -> None:
        kind = "preset" if mode == self.controller.mode_id else "mode"
        self.owner._pending_mode_activation = {"kind": kind, "mode": mode, **offline_activation_request(mode, preset)}
        self.owner._activate_pending_mode(0.0)


class _SessionHost:
    """The engine worker session's edge methods on a recording controller (its capture-lane wait stubbed)."""

    def __init__(self, mode: str) -> None:
        self.controller, self.log = _controller(mode)
        session = EngineSession.__new__(EngineSession)
        session._live, session._controller, session._engine, session.mode = True, self.controller, \
            self.controller.engine, mode
        session._live_started, session._engine_acquired, session._released_for_display_power = False, False, False
        session._display_on, session._pending_mode = True, None
        session._settle_capture = lambda: None
        self.session = session

    def start(self, playing: bool) -> None:
        self.session._start_playback(playing)

    def playing(self, active: bool) -> None:
        self.session._set_playing(active)

    def display(self, on: bool) -> None:
        self.session.set_display_power(on)

    def activate(self, mode: str, preset: int) -> None:
        self.session.request_mode(mode, preset=preset)
        self.session._apply_pending_mode()


_SCRIPTS = {
    # Start playing; pause/resume; a park and unpark while playing; a mode switch, a same-mode preset; a paused park
    # (no capture reopened) and the resume after it; a switch back to the first mode.
    "playing": [("start", True), ("playing", False), ("playing", True), ("display", False), ("display", True),
                ("activate", ("oscilloscope", 0)), ("activate", ("oscilloscope", 1)), ("playing", False),
                ("display", False), ("display", True), ("playing", True), ("activate", ("spectrum", 0))],
    # Parked before start (nothing held, nothing resumed), started paused, then the first play edge.
    "parked_cold": [("display", False), ("display", True), ("start", False), ("activate", ("sphere", 0)),
                    ("playing", True), ("display", False), ("playing", False), ("display", True)],
}


def _run(host, script):
    observed = []
    for edge, value in script:
        getattr(host, edge)(*(value if isinstance(value, tuple) else (value,)))
        state = host.controller.logical_tick_state
        observed.append((edge, host.controller.mode_id, host.controller.playing,
                         getattr(state, "_pending_engine_generation", None),
                         getattr(state, "_pending_engine_activation_id", None),
                         getattr(state, "_waiting_for_fresh_engine_frame", None),
                         getattr(state, "_pending_engine_frame_epoch", None)))
    return host.log, observed


@pytest.mark.parametrize("script", sorted(_SCRIPTS))
def test_the_owner_and_the_session_run_one_edge_sequence(script):
    owner_log, owner_state = _run(_OwnerHost("spectrum"), _SCRIPTS[script])
    session_log, session_state = _run(_SessionHost("spectrum"), _SCRIPTS[script])
    assert session_log == owner_log
    assert session_state == owner_state
    names = {entry[0] for entry in owner_log}
    # The script reached every edge's engine side (a vacuous log would pass the comparison).
    assert {"acquire", "release", "set_playback_state", "begin_activation_transaction", "end_activation_transaction",
            "cancel_pending_compute_tasks", "controller.stop_logical_runtime",
            "controller.begin_render_activation"} <= names
    assert "wake" in names and (script != "playing" or "ensure_started" in names)


def test_a_hand_copy_on_one_side_fails_the_parity(monkeypatch):
    # Negative control: the session's play edge as a hand copy that drifted from the owner's (no ``wake`` before the
    # playback state, A4-H1's failure scenario) is caught by the comparison.
    def drifted(session, active):
        controller = session._controller
        previous, controller.playing = bool(controller.playing), bool(active)
        controller.engine.set_playback_state(bool(active))
        if active and not previous:
            from widgets.spotify_visualizer.tick_pipeline import arm_reentry_fresh_frame_fence

            arm_reentry_fresh_frame_fence(controller.logical_tick_state, controller.engine)

    monkeypatch.setattr(EngineSession, "_set_playing", drifted)
    owner_log, _owner_state = _run(_OwnerHost("spectrum"), _SCRIPTS["playing"])
    session_log, _session_state = _run(_SessionHost("spectrum"), _SCRIPTS["playing"])
    assert session_log != owner_log
    assert [e for e in owner_log if e[0] != "wake"] == session_log
