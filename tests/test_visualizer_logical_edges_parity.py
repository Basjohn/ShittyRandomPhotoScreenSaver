"""One owner for the Visualizer's configuration, activation and engine edges (native core P2b; checkpoint audits 4
and 5, A4-H1, A5-M2, A5-L1).

The production Quick owner and the engine worker's session run the same control edges on one controller and engine
(``widgets/spotify_visualizer/logical_edges.py``). The same edge script goes through each host's own real path on two
recording engines and controllers: the construction (the owner: the host binding's own ``construct``, which resolves
the activation from the Settings section and runs the owner's ``configure`` with it, its bind, Media's ``set_playing``,
display power when built while the displays are off, then ``start``; the session: ``_configure``, display power, then
its start), play edges, display power and activations. Both hosts start the cadence through
``logical_edges.start_logical_cadence`` (the controller's ``start_logical_runtime`` is recorded, never a thread): the
owner's real ``_start_logical_runtime`` and a worker-paced session's ``_start_cadence`` (slice 5.1), at start and after
every activation (checkpoint audit 6, A6-L4). The call logs and the logical state must be identical: a change to the
owner's sequence reaches the worker, and a hand copy on either side that drifts fails here. Only the hosts' own parts
are outside the comparison (logged as ``owner.*`` and checked where they sit): the owner's reader-side mailbox clear,
Edit profile, backdrop and scene binding (its ``bind`` keeps only the render admission); the session's capture-lane
completion edge.

By construction the comparison cannot see a change inside ``logical_edges`` (both hosts follow it), so the sequences
that matter most are also pinned: the park order with a running logical runtime (the clocks rebase only while it is
parked) and the owner's activation failure stages.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.authored_clock import pinned_authored_clock
from core.visualizer_engine.engine_worker import EngineSession
from widgets.spotify_visualizer import logical_edges, quick_display_visualizer_owner, tick_pipeline
from widgets.spotify_visualizer.feature_replay import configure_offline_controller, offline_activation_request
from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner
from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
from widgets.spotify_visualizer.technical_config import resolve_technical_config

#: The controller's own steps that belong to the shared logical sequence (not the hosts' runtime or presentation).
_CONTROLLER_STEPS = ("stop_logical_runtime", "set_mode", "record_resolved_activation", "resolve_logical_mode_state",
                     "begin_render_activation", "set_logical_parked")
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
    """A production-shaped engine whose every call is logged; each activation transaction commits a new generation
    and activation. ``warm``: it holds a retained frame, so every fence arm takes the watermark path; a cold engine
    (no frame ever committed) leaves the fence unarmed."""

    def __init__(self, log: list, *, warm: bool = True) -> None:
        super().__init__(log)
        self._audio_worker = _Recorder(log, "audio_worker.")
        self._generation = self._activation = 1
        self._warm = warm
        self._raise_on: str | None = None

    def _record(self, name, *args, **kwargs):
        self._log.append((name, args, kwargs))
        if name == self._raise_on:
            raise RuntimeError(f"injected failure in {name}")

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        return lambda *args, **kwargs: self._record(name, *args, **kwargs)

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
        return (1.0 if self._warm else 0.0), self._generation, self._activation

    def get_authoritative_frame_commit_seq(self):
        self._record("get_authoritative_frame_commit_seq")
        return 7


class _RecordingRuntime:
    """A running logical runtime (no thread) whose park / unpark / stop are logged (A5-L1)."""

    def __init__(self, log: list) -> None:
        self._log, self._parked = log, False

    def is_running(self) -> bool:
        return True

    def is_parked(self) -> bool:
        return self._parked

    def park(self) -> bool:
        self._log.append(("runtime.park", (), {}))
        self._parked = True
        return True

    def unpark(self) -> bool:
        self._log.append(("runtime.unpark", (), {}))
        self._parked = False
        return True

    def stop(self) -> bool:
        self._log.append(("runtime.stop", (), {}))
        return True


def _controller(mode: str, *, warm: bool):
    log: list = []
    engine = _RecordingEngine(log, warm=warm)
    controller = VisualizerRuntimeController(runtime_generation=3, initial_mode=mode,
                                             engine_factory=lambda _count: engine)
    controller.ensure_engine()
    for name in _CONTROLLER_STEPS:
        original = getattr(controller, name)

        def step(*args, _name=name, _original=original, **kwargs):
            log.append(("controller." + _name, args, kwargs))
            return _original(*args, **kwargs)

        setattr(controller, name, step)

    def start_logical_runtime(*, step, interval_s):
        # The cadence start both hosts reach through ``start_logical_cadence`` (never a thread here).
        log.append(("controller.start_logical_runtime", (), {"interval_s": interval_s}))

    controller.start_logical_runtime = start_logical_runtime
    return controller, log


def _request(mode: str, preset: int) -> dict:
    return offline_activation_request(mode, preset)


class _OwnerHost:
    """The production owner's methods on a recording controller (its scene, bind and backdrop stubbed and logged as
    ``owner.*``), constructed by the host binding's own ``construct`` (A6-L4: never a hand copy of it)."""

    def __init__(self, mode: str, *, warm: bool = True) -> None:
        self.controller, self.log = _controller(mode, warm=warm)
        log = self.log
        owner = QuickDisplayVisualizerOwner.__new__(QuickDisplayVisualizerOwner)
        owner._controller = self.controller
        owner._retired, owner._started, owner._configured, owner._bound = False, False, False, False
        owner._display_power_on, owner._engine_acquired, owner._engine_released_for_display_power = True, False, False
        owner._transition_clock = lambda: 0.0
        owner._refresh_backdrop = lambda: log.append(("owner.refresh_backdrop", (), {}))
        owner._edit_layout_profile_activator = None
        owner._activate_committed_layout_profile = (
            lambda target: log.append(("owner.activate_committed_layout_profile", (target,), {})))
        owner._pending_mode_activation = None
        owner._runtime = SimpleNamespace(
            bind_visualizer_render_source=lambda controller, **identity: controller.begin_render_activation(**identity))
        owner._expanded_overlays_drawn = False
        bridge = self.controller.render_bridge
        discard = bridge.discard_pending
        bridge.discard_pending = lambda: (log.append(("owner.discard_pending", (), {})), discard())[1]
        clear = self.controller.logical_mailbox.clear
        self.controller.logical_mailbox.clear = lambda: (log.append(("owner.mailbox_clear", (), {})), clear())[1]

        def bind(*, engine_generation, activation_id):
            # The owner's bind: its render admission (shared) and its scene wiring (its own, not built here).
            log.append(("owner.bind", (), {}))
            owner._render_identity = owner._runtime.bind_visualizer_render_source(
                owner._controller, engine_generation=engine_generation, activation_id=activation_id)
            owner._bound = True
            return owner._render_identity

        owner.bind = bind
        owner.resolved_outer_size = lambda: (420.0, 280.0)
        owner.set_authored_outer_origin = lambda x, y: log.append(("owner.set_authored_outer_origin", (), {})) or True
        self.owner = owner

    def construct(self, mode: str, preset: int, playing: bool, display_on: bool) -> None:
        """The host binding's ``construct`` on a stub host, the Settings section naming ``mode`` and ``preset``:
        Media ``playing`` or paused, the displays on or off."""
        from dataclasses import asdict, replace
        from unittest import mock

        from tests.test_visualizer_host_binding import _Caller, _StubHost
        from widgets.spotify_visualizer.visualizer_host_binding import VisualizerHostBinding

        host = _StubHost(0)
        self.owner._presentation_runtime = host.runtime
        caller = _Caller([host])
        # The section the session's offline request resolves too (``offline_activation_request``: mode and preset).
        caller.widgets["spotify_visualizer"] = {"enabled": True, "visualizers_enabled": True, "mode": mode,
                                                f"preset_{mode}": preset}
        services = replace(
            caller.services(), thread_manager=lambda: _THREAD_MANAGER, display_power_on=lambda: display_on,
            presentation_kwargs=lambda model, _mode: asdict(model),
            media_model_for=lambda _unit: SimpleNamespace(playbackState="playing" if playing else "paused"))
        self.binding_inputs = {}
        configure = self.owner.configure

        def recorded_configure(**kwargs):
            self.binding_inputs.update(kwargs)
            return configure(**kwargs)

        self.owner.configure = recorded_configure
        with mock.patch.object(quick_display_visualizer_owner, "QuickDisplayVisualizerOwner",
                               lambda *_args, **_kwargs: self.owner):
            assert VisualizerHostBinding(services).construct(host) is True

    def playing(self, active: bool) -> None:
        self.owner.set_playing(active)

    def display(self, on: bool) -> None:
        self.owner.set_display_power(on)

    def activate(self, mode: str, preset: int) -> None:
        kind = "preset" if mode == self.controller.mode_id else "mode"
        self.owner._pending_mode_activation = {"kind": kind, "mode": mode, **_request(mode, preset)}
        self.owner._activate_pending_mode(0.0)

    def adopt_runtime(self) -> None:
        self.controller.adopt_logical_runtime(_RecordingRuntime(self.log))


class _SessionHost:
    """The engine worker session's edge methods on a recording controller (its capture-lane wait stubbed). ``paced``:
    a worker-paced session (slice 5.1), which starts its own cadence as the owner does; an input-paced one starts
    none."""

    def __init__(self, mode: str, *, warm: bool = True, paced: bool = True) -> None:
        self.controller, self.log = _controller(mode, warm=warm)
        session = EngineSession.__new__(EngineSession)
        session._live, session._controller, session._engine, session.mode = True, self.controller, \
            self.controller.engine, mode
        session._live_started, session._engine_acquired, session._released_for_display_power = False, False, False
        session._display_on, session._pending_mode, session._paced = True, None, paced
        session._interval_s, session._commits_at_start, session._cadence_started_ts = None, 0, 0.0
        session._settle_capture = lambda: None
        self.session = session

    def construct(self, _mode: str, preset: int, playing: bool, display_on: bool) -> None:
        # VIS_CONFIGURE, display power when the displays are off, VIS_START (the session's start).
        self.session._configure(preset, None, _THREAD_MANAGER)
        if not display_on:
            self.session.set_display_power(False)
        self.session._start_playback(playing)

    def playing(self, active: bool) -> None:
        self.session._set_playing(active)

    def display(self, on: bool) -> None:
        self.session.set_display_power(on)

    def activate(self, mode: str, preset: int) -> None:
        self.session.request_mode(mode, preset=preset)
        self.session._apply_pending_mode()

    def adopt_runtime(self) -> None:
        self.controller.adopt_logical_runtime(_RecordingRuntime(self.log))


_SCRIPTS = {
    # Constructed playing; pause/resume; a park and unpark while playing; a mode switch, a same-mode preset; a paused
    # park (no capture reopened) and the resume after it; a switch back to the first mode.
    "playing": [("construct", ("spectrum", 0, True, True)), ("playing", False), ("playing", True),
                ("display", False), ("display", True), ("activate", ("oscilloscope", 0)),
                ("activate", ("oscilloscope", 1)), ("playing", False), ("display", False), ("display", True),
                ("playing", True), ("activate", ("spectrum", 0))],
    # Constructed paused, a layout-profile change (Sphere), then the first play edge, a park while playing and a pause
    # while parked.
    "paused_cold": [("construct", ("spectrum", 0, False, True)), ("activate", ("sphere", 0)), ("playing", True),
                    ("display", False), ("playing", False), ("display", True)],
    # Constructed while the displays are off (A5-L1, the owner's ``start`` tail: the reference released again), the
    # displays back on, a pause and a switch.
    "started_parked": [("construct", ("spectrum", 1, True, False)), ("display", True), ("playing", False),
                       ("activate", ("bubble", 0))],
    # Constructed paused while the displays are off (the reference released, nothing admitted), a preset while
    # parked, then the displays on and playing.
    "parked_paused": [("construct", ("spectrum", 0, False, False)), ("activate", ("spectrum", 1)),
                      ("display", True), ("playing", True)],
}


def _state(controller) -> tuple:
    """The logical state a configure / edge leaves (primitive tick-state fields, the recorded inputs)."""
    state = controller.logical_tick_state
    primitives = tuple(sorted((key, repr(value)) for key, value in vars(state).items()
                              if isinstance(value, (bool, int, float, str, type(None)))))
    return (controller.mode_id, controller.playing, controller.settings_model, controller.technical_config_cache,
            repr(controller.resolved_activation), primitives)


def _run(host, script):
    observed = []
    with pinned_authored_clock(lambda: 100.0):
        for edge, value in script:
            getattr(host, edge)(*(value if isinstance(value, tuple) else (value,)))
            observed.append((edge, _state(host.controller)))
    return host.log, observed


def _shared(log, *, cadence: bool = True):
    """The shared sequence: no ``owner.*`` step (the hosts' own), no cadence start for an input-paced session. A park
    before the start (built while the displays are off) is a flag on the controller that nothing before the start
    reads: the binding raises it after Media's play edge, the session before its start, so it is compared by count
    (``_parks_before_start``), not position."""
    entries = [entry for entry in log if not entry[0].startswith("owner.")
               and (cadence or entry[0] != "controller.start_logical_runtime")]
    first_acquire = next((i for i, entry in enumerate(entries) if entry[0] == "acquire"), len(entries))
    return [entry for i, entry in enumerate(entries)
            if not (i < first_acquire and entry[:2] == ("controller.set_logical_parked", (True,)))]


def _parks_before_start(log) -> int:
    first_acquire = next((i for i, entry in enumerate(log) if entry[0] == "acquire"), len(log))
    return sum(entry[:2] == ("controller.set_logical_parked", (True,)) for entry in log[:first_acquire])


@pytest.mark.parametrize("paced", [True, False], ids=["paced", "input_paced"])
@pytest.mark.parametrize("warm", [True, False], ids=["warm", "cold"])
@pytest.mark.parametrize("script", sorted(_SCRIPTS))
def test_the_owner_and_the_session_run_one_edge_sequence(script, warm, paced):
    owner_log, owner_state = _run(_OwnerHost("spectrum", warm=warm), _SCRIPTS[script])
    session_log, session_state = _run(_SessionHost("spectrum", warm=warm, paced=paced), _SCRIPTS[script])
    assert _shared(session_log) == _shared(owner_log, cadence=paced)
    assert _parks_before_start(session_log) == _parks_before_start(owner_log) == (not _SCRIPTS[script][0][1][3])
    assert session_state == owner_state
    # The cadence starts (A6-L4, slice 5.1): the owner's at its start and after every committed activation; a
    # worker-paced session's at the same places, an input-paced session's never.
    starts = [i for i, entry in enumerate(owner_log) if entry[0] == "controller.start_logical_runtime"]
    activations = sum(edge == "activate" for edge, _value in _SCRIPTS[script])
    assert len(starts) == 1 + activations
    assert sum(entry[0] == "controller.start_logical_runtime" for entry in session_log) == (len(starts) if paced else 0)
    names = {entry[0] for entry in owner_log}
    # The script reached every edge's engine side (a vacuous log would pass the comparison).
    assert {"acquire", "release", "set_playback_state", "begin_activation_transaction", "end_activation_transaction",
            "cancel_pending_compute_tasks", "controller.stop_logical_runtime", "controller.begin_render_activation",
            "controller.record_resolved_activation", "controller.resolve_logical_mode_state",
            "controller.set_logical_parked", "get_latest_authoritative_frame"} <= names
    assert ("wake" in names) == (script != "started_parked")              # a play edge after start
    # Capture admitted at a start or an unpark while playing (the paused constructions reach neither).
    assert ("ensure_started" in names) == (script not in ("paused_cold", "parked_paused"))
    # A warm engine arms the watermark (reads the commit sequence); a cold one never does.
    assert ("get_authoritative_frame_commit_seq" in names) == warm
    # The owner's own steps sit where they belong: the backdrop inside every configure, the profile discard and
    # commit inside the transaction before the mode changes (planar -> 3D only), the reader clear after the park.
    owner_only = [entry[0] for entry in owner_log if entry[0].startswith("owner.")]
    assert "owner.refresh_backdrop" in owner_only and "owner.mailbox_clear" in owner_only
    assert owner_only.index("owner.refresh_backdrop") < owner_only.index("owner.bind")   # configure, then bind
    profile = [i for i, entry in enumerate(owner_log) if entry[0] == "owner.activate_committed_layout_profile"]
    assert bool(profile) == (script == "paused_cold")
    for index in profile:
        begin = max(i for i, entry in enumerate(owner_log[:index]) if entry[0] == "begin_activation_transaction")
        assert owner_log[index - 1][0] == "owner.discard_pending" and begin < index - 1
        assert owner_log[index + 1][0] == "controller.set_mode"


def test_the_session_configure_is_the_owners_not_the_replay_copy(monkeypatch):
    # A5-M2's negative control: the pre-change session configured with ``configure_offline_controller`` (no logical mode
    # state, no fence, playing forced on, no activation recorded for a preset); the comparison catches it at the
    # configure step.
    def replay_copy(session, preset, settings, thread_manager):
        controller = session._controller
        configure_offline_controller(controller, controller.mode_id, preset, None, settings)
        controller.thread_manager = thread_manager

    owner_log, owner_state = _run(_OwnerHost("spectrum"), _SCRIPTS["playing"][:1])
    monkeypatch.setattr(EngineSession, "_configure", replay_copy)
    session_log, session_state = _run(_SessionHost("spectrum"), _SCRIPTS["playing"][:1])
    assert _shared(session_log) != _shared(owner_log) and session_state != owner_state


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
    assert _shared(session_log) != _shared(owner_log)
    assert [e for e in _shared(owner_log) if e[0] != "wake"] == _shared(session_log)


# ------------------------------------------------------------------------------- pinned sequences (A5-L1)

_PARK_SCRIPT = [("construct", ("spectrum", 0, True, True)), ("adopt_runtime", ()), ("display", False),
                ("display", True)]
#: Park with a running runtime: the cadence parks first, then the reference goes; unpark: the reference and capture
#: come back, the clocks rebase while the cadence is still parked, then it unparks.
_PARK_ORDER = [("controller.set_logical_parked", (True,)), ("runtime.park", ()), ("release", ()), ("acquire", ()),
               ("ensure_started", ()), ("rebase", ()), ("controller.set_logical_parked", (False,)),
               ("runtime.unpark", ())]
_PARK_NAMES = {name for name, _args in _PARK_ORDER}


def _park_sequence(host_type, monkeypatch) -> list:
    host = host_type("spectrum")
    rebase = tick_pipeline.rebase_logical_clocks_after_park

    def recorded_rebase(*args, **kwargs):
        host.log.append(("rebase", (), {}))
        return rebase(*args, **kwargs)

    monkeypatch.setattr(tick_pipeline, "rebase_logical_clocks_after_park", recorded_rebase)
    log, _observed = _run(host, _PARK_SCRIPT)
    start = max(i for i, entry in enumerate(log) if entry[0] == "ensure_started"
                and not any(e[0] == "runtime.park" for e in log[:i]))
    return [(name, args) for name, args, _kwargs in log[start + 1:] if name in _PARK_NAMES]


@pytest.mark.parametrize("host_type", [_OwnerHost, _SessionHost], ids=["owner", "session"])
def test_a_running_runtime_parks_first_and_rebases_only_while_parked(host_type, monkeypatch):
    assert _park_sequence(host_type, monkeypatch) == _PARK_ORDER


def test_unparking_before_the_resume_fails_the_pinned_park_order(monkeypatch):
    # Negative control (A5-L1): the cadence unparked before the resume (inside the shared module, so both hosts follow
    # it and the parity comparison stays green): the resume finds it unparked and never rebases the clocks.
    def unpark_first(controller, *, started, released_for_display_power, on_reacquired):
        controller.set_logical_parked(False)
        return logical_edges.resume_engine_after_park(controller, started=started,
                                                      released_for_display_power=released_for_display_power,
                                                      on_reacquired=on_reacquired)

    monkeypatch.setattr(logical_edges, "unpark_logical_side", unpark_first)
    monkeypatch.setattr(quick_display_visualizer_owner, "unpark_logical_side", unpark_first)
    for host_type in (_OwnerHost, _SessionHost):
        sequence = _park_sequence(host_type, monkeypatch)
        assert sequence != _PARK_ORDER and ("rebase", ()) not in sequence


class _ExceptionLog:
    def __init__(self) -> None:
        self.steps: list[str] = []

    def exception(self, message, *args, **_kwargs):
        if "activation FAILED step=" in message:
            self.steps.append(str(args[1]))

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


@pytest.mark.parametrize("failing, step, restored", [
    ("owner.discard_pending", "begin_engine_transaction", True),          # A5-L5: the label before the refactor
    ("owner.activate_committed_layout_profile", "activate_committed_profile", True),
    ("controller.set_mode", "set_controller_mode", True),
    ("reset_floor_state", "configure_target", False),                   # past set_mode: no outgoing to restore
])
def test_the_owner_names_each_failed_activation_step_and_restores_the_outgoing_mode(monkeypatch, failing, step,
                                                                                     restored):
    # A5-L1/L5: a mode activation (planar -> 3D: the profile callback runs) failing at each stage of the transaction.
    # The owner's failure log names the step, ``recover`` restores the outgoing mode inside the transaction (its
    # runtime restarted before the transaction ends) and the transaction always ends.
    exceptions = _ExceptionLog()
    monkeypatch.setattr(quick_display_visualizer_owner, "logger", exceptions)
    host = _OwnerHost("spectrum")
    with pinned_authored_clock(lambda: 100.0):
        host.construct("spectrum", 0, True, True)
        if failing.startswith("owner."):
            name = failing.split(".", 1)[1]
            target = host.controller.render_bridge if name == "discard_pending" else host.owner
            attribute = "discard_pending" if name == "discard_pending" else "_activate_committed_layout_profile"

            def fail(*_args, _name=failing):
                host.log.append((_name, (), {}))
                raise RuntimeError(f"injected failure in {_name}")

            monkeypatch.setattr(target, attribute, fail)
        elif failing.startswith("controller."):
            def fail_mode(*_args, **_kwargs):
                host.log.append((failing, (), {}))
                raise RuntimeError("injected failure in set_mode")

            monkeypatch.setattr(host.controller, "set_mode", fail_mode)
        else:
            host.controller.engine._raise_on = failing
        mark = len(host.log)
        if restored:
            host.activate("sphere", 0)
        else:
            with pytest.raises(RuntimeError, match="injected"):
                host.activate("sphere", 0)
    assert exceptions.steps == [step]
    tail = [entry[0] for entry in host.log[mark:]]
    assert tail.index("begin_activation_transaction") < tail.index(failing) < tail.index("end_activation_transaction")
    if restored:
        assert host.controller.mode_id == "spectrum" and host.owner._mode_transition_phase == "idle"
        # The outgoing mode's cadence restarted inside the transaction (``_start_logical_runtime``).
        restart = "controller.start_logical_runtime"
        assert tail.index(failing) < tail.index(restart) < tail.index("end_activation_transaction")
    else:
        assert host.owner._mode_transition_phase == "failed" and "controller.start_logical_runtime" not in tail


@pytest.mark.parametrize("host_type", [_OwnerHost, _SessionHost], ids=["owner", "session"])
def test_a_failed_preset_activation_raises_after_ending_its_transaction_on_both_hosts(host_type):
    # A failure inside a same-mode preset's transaction is not recoverable (``recover`` restores mode switches only):
    # both hosts raise and the transaction still ends; the two logs are the same.
    logs = {}
    for each in (_OwnerHost, _SessionHost):
        host = each("spectrum")
        with pinned_authored_clock(lambda: 100.0):
            host.construct("spectrum", 0, True, True)
            host.controller.engine._raise_on = "reset_smoothing_state"
            mark = len(host.log)
            with pytest.raises(RuntimeError, match="injected"):
                host.activate("spectrum", 1)
        logs[each] = _shared(host.log[mark:])
        names = [entry[0] for entry in logs[each]]
        assert names.index("reset_smoothing_state") < names.index("end_activation_transaction")
        if each is _OwnerHost:
            assert host.owner._mode_transition_phase == "failed"
    assert logs[_OwnerHost] == logs[_SessionHost]


def test_an_unjoined_runtime_refuses_the_activation_before_its_transaction_on_both_hosts(monkeypatch):
    for host_type in (_OwnerHost, _SessionHost):
        host = host_type("spectrum")
        with pinned_authored_clock(lambda: 100.0):
            host.construct("spectrum", 0, True, True)
            monkeypatch.setattr(host.controller, "stop_logical_runtime", lambda: False)
            mark = len(host.log)
            with pytest.raises(logical_edges.LogicalRuntimeNotJoined):
                host.activate("oscilloscope", 0)
        assert "begin_activation_transaction" not in [entry[0] for entry in host.log[mark:]]
        assert host.controller.mode_id == "spectrum"
