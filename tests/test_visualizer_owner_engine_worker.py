"""Native core P2b, work order 5 slice 5.2 (and the core of 5.3): the production owner on the engine worker.

The REAL owner, built by the host binding's own ``construct`` on an unshown runtime (``tools/visualizer_replay/
owner_worker_gate.py``'s rig: no window is shown), admitted onto the engine worker by the code-level admission
(``experiment_flags.visualizer_engine_worker_admitted``: the default on Windows; every rig states its path). No test
opens a device: worker sessions take the shipped
clip's PCM through the link's test-only control (``engine_worker_link.recorded_capture_for_testing``; the session
refuses the device for its life), and the device-path tests run the session in process with the device constructor
replaced. Most tests drive a real ``WorkerType.VISUALIZER`` process; the edge-order tests (the park's reader clear, a
preset change) run the same ``VisualizerEngineWorker`` in this process behind a supervisor stand-in, so the order is
deterministic.
"""
from __future__ import annotations

import dataclasses
import sys
import threading

import pytest

from tools.visualizer_replay import owner_worker_gate as gate


def _modes():
    return gate.modes()


@pytest.fixture(autouse=True)
def _no_device_and_a_fresh_run(monkeypatch):
    from core.visualizer_engine.engine_worker import EngineSession
    from widgets.spotify_visualizer import engine_worker_link

    def _device(_config=None):
        raise AssertionError("a test opened an audio device")

    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", _device)
    monkeypatch.setattr(EngineSession, "LIVE_EDGE_TIMEOUT_S", 10.0)
    engine_worker_link.reset_run_state_for_testing()
    yield
    engine_worker_link.reset_run_state_for_testing()


@pytest.fixture(scope="module")
def supervisor():
    from core.process.supervisor import ProcessSupervisor
    from core.process.types import WorkerType
    from core.visualizer_engine.engine_worker import visualizer_worker_main

    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    assert supervisor.start(WorkerType.VISUALIZER)
    yield supervisor
    supervisor.shutdown()


@pytest.fixture(scope="module")
def pcm():
    from tools.visualizer_replay.live_engine_gate import paced_pcm

    return paced_pcm(3.0)


class _InProcessSupervisor:
    """The supervisor's request surface over a ``VisualizerEngineWorker`` in this process (deterministic order). The
    wake pipe's writer end is duplicated as the real queue's pickling would, so the link closing its copy leaves the
    session's open."""

    def __init__(self) -> None:
        from core.visualizer_engine.engine_worker import VisualizerEngineWorker

        self.worker = VisualizerEngineWorker(None, None)
        self.sent: list = []
        self._serial = 0

    def register_worker_factory(self, *_args) -> None:
        return None

    def is_running(self, _worker_type) -> bool:
        return True

    def start(self, _worker_type) -> bool:
        return True

    @staticmethod
    def _duplicate(conn):
        from multiprocessing import reduction

        if sys.platform == "win32":
            return type(conn)(reduction.duplicate(conn.fileno(), inheritable=False), readable=False, writable=True)
        import os

        return type(conn)(os.dup(conn.fileno()), readable=False, writable=True)

    def send_request_and_await_response(self, _worker_type, msg_type, payload, *, timeout_ms=0):
        from core.process.types import WorkerMessage

        payload = dict(payload)
        if "wake" in payload:
            payload["wake"] = self._duplicate(payload["wake"])
        self.sent.append((msg_type, payload))
        self._serial += 1
        return self.worker.handle_message(WorkerMessage(msg_type=msg_type, seq_no=self._serial,
                                                        correlation_id=str(self._serial), payload=payload))

    # The asynchronous surface (slice 5.5): the request is handled at once (deterministic order); its reply reaches
    # the registered callback, which the link turns into a queued event like the real listener's.
    def register_response_callback(self, _worker_type, correlation_id, callback) -> bool:
        self.callbacks = getattr(self, "callbacks", {})
        self.callbacks[correlation_id] = callback
        return True

    def send_message(self, worker_type, msg_type, payload, correlation_id=None):
        response = self.send_request_and_await_response(worker_type, msg_type, payload)
        callback = self.callbacks.pop(correlation_id, None)
        if callback is not None:
            callback(response)
        return correlation_id

    def abandon_response(self, _worker_type, correlation_id, *, reason="") -> int:
        getattr(self, "callbacks", {}).pop(correlation_id, None)
        return 0

    def close(self) -> None:
        self.worker._close_session()


def _pump(rig, seconds: float, until=None) -> None:
    gate._event_loop_for(rig.app, seconds, until=until)


# ------------------------------------------------------------------------------------------------ the admission


def test_the_path_follows_the_platform_unless_argv_chooses_it():
    # No token: the platform default (the engine worker on Windows: tests/test_platform_selection.py; in process on
    # Linux: tests/test_linux_runtime_branches.py). --viz-engine-worker / --viz-in-process choose; in process wins.
    from core.diagnostics import experiment_flags as ef

    assert ef.parse_experiment_flags(["main.py", "/s"]).visualizer_engine_worker is None
    worker = ef.parse_experiment_flags(["main.py", "--viz-engine-worker", "/s"])
    in_process = ef.parse_experiment_flags(["main.py", "--viz-in-process", "/s"])
    assert worker.visualizer_engine_worker is True and in_process.visualizer_engine_worker is False
    assert ef.parse_experiment_flags(["--viz-in-process", "--viz-engine-worker"]).visualizer_engine_worker is False
    for token in ("--viz-engine-worker", "--viz-in-process"):
        assert ef.experiment_flag_tokens(["main.py", token, "/s"]) == (token,)
    saved = ef.active_experiment_flags()
    try:
        ef.override_active_flags_for_testing(None)
        assert ef.visualizer_engine_worker_admitted() is ef.visualizer_engine_worker_platform_default()
        ef.activate_experiment_flags(worker)
        assert ef.visualizer_engine_worker_admitted() is True
        ef.activate_experiment_flags(in_process)
        assert ef.visualizer_engine_worker_admitted() is False
    finally:
        ef.override_active_flags_for_testing(saved)


@pytest.mark.qt
def test_the_in_process_path_builds_the_in_process_owner_and_never_reaches_the_worker(qt_app, monkeypatch):
    # In process (stated): no link is built, the supervisor is never asked for the worker, the controller holds its
    # engine.
    from widgets.spotify_visualizer import engine_worker_link

    asked = []

    class _Supervisor:
        def __getattr__(self, name):
            asked.append(name)
            raise AssertionError(f"the in-process owner asked the supervisor for {name}")

    def _no_link(*_args, **_kwargs):
        raise AssertionError("the in-process owner built an engine-worker link")

    monkeypatch.setattr(engine_worker_link.EngineWorkerLink, "__init__", _no_link)
    rig = gate.OwnerRig("spectrum", worker=False, supervisor=_Supervisor(), clock=[0.0])
    try:
        owner = rig.build()
        assert owner._worker is None and owner._engine_worker_admitted is False
        assert owner.controller.engine is rig.engines[-1] and not asked
    finally:
        rig.close()


# ------------------------------------------------------------------------------------------- on the worker


@pytest.mark.qt
def test_on_the_worker_the_main_process_keeps_no_engine_and_runs_no_tick(qt_app, supervisor, pcm, monkeypatch):
    from widgets.spotify_visualizer import engine_worker_link, tick_pipeline

    ticks = []
    tick = tick_pipeline.logical_tick

    def counting(state):
        ticks.append(state)
        return tick(state)

    monkeypatch.setattr(tick_pipeline, "logical_tick", counting)
    rig = gate.OwnerRig("bubble", worker=True, supervisor=supervisor, cadence="thread")
    presented = []
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
        controller = owner.controller
        sync = owner._publication_wake._callback
        owner._publication_wake._callback = lambda: presented.append(sync())
        # Until the owner presented a run of the worker's frames (bounded): a long suite can leave the GUI's event
        # queue busy with earlier tests' teardown, which this test does not time.
        _pump(rig, 15.0, until=lambda: sum(bool(p) for p in presented) > 30)
        ticks = [state for state in ticks if state is controller.logical_tick_state]   # this owner's only
        assert owner._worker is not None and controller.engine is None and controller.logical_runtime is None
        assert not ticks and sum(bool(p) for p in presented) > 30, (
            len(presented), gate._newest_published(owner._worker.mailbox), owner._mode_transition_phase,
            owner._worker_identity, controller.render_identity, owner._publication_wake.pending,
            owner._publication_wake._closed)
        assert rig.engines == []                       # the controller's engine factory was never asked
        assert owner.render_identity == controller.render_identity
        assert controller.logical_mailbox is owner._worker.mailbox and owner._worker.label_namespace >= 1
    finally:
        rig.close()


@pytest.mark.qt
@pytest.mark.parametrize("mode", _modes())
def test_the_owner_on_the_worker_presents_the_in_process_owners_frames(qt_app, supervisor, mode):
    # Gate (slice 5.2): the real owner + binding on the worker, fed the shipped clip's PCM, publishes to its render
    # bridge the frames the same owner publishes in process on the same PCM through the live engine (production read
    # order), through configure and start, play, a warm pause and resume, a park and unpark and a mode switch through
    # the owner's crossfade; and it stays on the worker throughout.
    import tools.expanded_visualizer_evidence as evidence

    verdict = gate.identity_gate(mode, evidence.shipped_clip(5.5).frames, supervisor)
    assert verdict["identical"], verdict


@pytest.mark.qt
def test_a_one_tick_drift_on_one_side_fails_the_identity_gate(qt_app, supervisor, monkeypatch):
    # Negative control: the in-process side's Media edge one input late (the worker's lands where the owner sends it).
    import tools.expanded_visualizer_evidence as evidence

    frames = evidence.shipped_clip(5.5).frames
    script = gate.identity_script(frames, "oscilloscope")
    late = []
    for kind, value in script:
        late.append((kind, value))
    index = next(i for i, (kind, value) in enumerate(late) if kind == "input" and not value.playing)
    kind, value = late[index]
    late[index] = (kind, dataclasses.replace(value, playing=True))     # the pause reaches it one tick late
    worker = gate.identity_run("oscilloscope", script, worker=True, supervisor=supervisor)
    in_process = gate.identity_run("oscilloscope", late, worker=False, namespace=worker["namespace"])
    assert worker["digests"] != in_process["digests"]


@pytest.mark.qt
@pytest.mark.parametrize("mode", ("spectrum", "extruded_bubble"))
def test_the_worker_paced_owner_keeps_its_cadence_against_a_slow_gui(qt_app, supervisor, pcm, mode):
    # Real time: the worker paces itself; its frames reach sync_present through the listener and the queued wake on
    # the GUI event loop, the GUI stalling 40 ms after each: the cadence holds, the GUI coalesces (latest wins), the
    # newest frame is presented after the stop, nothing is torn, the audio reached the engine.
    verdict = gate.live_run(mode, worker=True, supervisor=supervisor, pcm=pcm, seconds=2.0, stall_s=gate.STALL_S)
    assert verdict["realtime_ok"], verdict
    assert verdict["presented"] < verdict["published"] and verdict["latest_checks"] > 0


@pytest.mark.qt
def test_the_wake_listener_drains_while_the_gui_thread_is_blocked(qt_app, supervisor, pcm):
    # A6-L8's wake obligation: the wake callback never blocks and a stalled GUI leaves the listener draining, so the
    # worker's wake pipe never fills and the cadence never waits on the GUI.
    from widgets.spotify_visualizer import engine_worker_link

    rig = gate.OwnerRig("spectrum", worker=True, supervisor=supervisor, cadence="thread")
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
        mailbox = owner._worker.mailbox
        _pump(rig, 0.3)
        before = gate._newest_published(mailbox)
        threading.Event().wait(1.0)                    # the GUI thread blocked: no event is processed
        during = gate._newest_published(mailbox) - before
        assert during >= 80, during                    # ~90 Hz went on (the pipe drained by the listener)
        assert owner._publication_wake.pending        # one queued wake, coalesced, waiting for the GUI
        report = owner._worker.stop()
        assert report["cadence"]["skipped_deadlines"] <= 2 and report["cadence"]["step_failures"] == 0
    finally:
        rig.close()


# --------------------------------------------------------------------------------------- edge order (in process)


@pytest.mark.qt
def test_the_park_clears_the_reader_after_the_park_reply_never_before(qt_app, pcm, monkeypatch):
    # A6-L8: the worker's last pre-park publish lands before the park reply (here forced: one more tick inside the
    # park edge); the owner clears its reader after the reply, so that frame is dropped and nothing pre-park is
    # presented later. Negative controls: clearing before the edge leaves it; never clearing leaves it.
    from core.visualizer_engine.engine_worker import EngineSession
    from widgets.spotify_visualizer import engine_worker_link
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner
    from widgets.spotify_visualizer.tick_pipeline import logical_tick

    park = EngineSession.set_display_power

    def park_then_one_more_publish(self, on):
        changed = park(self, on)
        if not on:
            # A frame the worker publishes before its park reply (the cadence is parked here, so no step races it).
            logical_tick(self._controller.logical_tick_state)
        return changed

    monkeypatch.setattr(EngineSession, "set_display_power", park_then_one_more_publish)
    original = QuickDisplayVisualizerOwner._set_display_power_on_worker

    def clear_before(self, on):
        if not on:
            self._controller.logical_mailbox.clear()
        self._worker.set_display_power(on)
        return True

    def never_clear(self, on):
        self._worker.set_display_power(on)
        return True

    unread = {}
    for name, variant in (("after", original), ("before", clear_before), ("never", never_clear)):
        monkeypatch.setattr(QuickDisplayVisualizerOwner, "_set_display_power_on_worker", variant)
        stand_in = _InProcessSupervisor()
        rig = gate.OwnerRig("spectrum", worker=True, supervisor=stand_in, cadence="thread")
        try:
            with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
                owner = rig.build()
            # No presentation while the reply is awaited (it would take the frame and hide what each variant left).
            owner.controller.logical_mailbox.set_wake_callback(None)
            assert owner.set_display_power(False)
            rig.settle()                                 # the park's reply (an event: the owner never waits)
            unread[name] = owner.controller.logical_mailbox.peek()
        finally:
            rig.close()
            stand_in.close()
    assert unread["after"] is None, unread
    assert unread["before"] is not None and unread["never"] is not None, unread


@pytest.mark.qt
def test_a_preset_change_on_the_worker_reactivates_the_session_with_the_binding_inputs(qt_app, pcm):
    # Settings (interim, slice 5.4 replaces it with a delta at a tick boundary): a same-mode preset change is the
    # owner's preset activation committed in the session (VIS_SET_MODE for the current mode, with the owner's own
    # resolved inputs), which rebinds the render identity to the committed activation.
    from core.process.types import MessageType
    from widgets.spotify_visualizer import engine_worker_link

    stand_in = _InProcessSupervisor()
    clock = [0.0]
    rig = gate.OwnerRig("bubble", worker=True, supervisor=stand_in, cadence="thread", clock=clock)
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
            before = owner.render_identity
            inputs = gate.activation_inputs(rig.widgets, "bubble")
            assert owner.request_preset_change("bubble", **inputs)
            for step in range(200):
                clock[0] = 0.02 * (step + 1)
                _pump(rig, 0.02)
                if owner._mode_transition_phase in ("waiting_target", "fading_in", "idle") and \
                        owner.render_identity != before:
                    break
        modes = [(msg, payload) for msg, payload in stand_in.sent if msg == MessageType.VIS_SET_MODE]
        assert len(modes) == 1 and modes[0][1]["mode"] == "bubble" and modes[0][1]["at_once"] is True
        sent = modes[0][1]["activation"]
        assert sent["settings_model"] == inputs["settings_model"]
        assert sent["presentation_kwargs"] == inputs["presentation_kwargs"]
        assert owner.render_identity.activation_id > before.activation_id
        assert owner._worker is not None
    finally:
        rig.close()
        stand_in.close()


@pytest.mark.qt
def test_the_framed_view_the_worker_tick_reads_follows_the_owners_controller(qt_app, pcm):
    # The tick reads the controller's layout metrics; on the worker path the owner forwards them (VIS_SET_VIEW) when
    # they change: a CUSTOM working override and its retirement, a committed rotation map. Negative control: with the
    # forwarding disabled the session's controller keeps the old metrics.
    from widgets.spotify_visualizer import engine_worker_link

    def run(forward: bool):
        stand_in = _InProcessSupervisor()
        rig = gate.OwnerRig("spectrum", worker=True, supervisor=stand_in, cadence="thread")
        try:
            with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
                owner = rig.build()
            main, session = owner.controller, stand_in.worker._session._controller
            if not forward:
                main.set_layout_metrics_observer(None)
            seen = []
            main.set_custom_viewport_override((800.0, 400.0), {"spectrum": 1})
            rig.settle()                                 # sent at the end of the GUI turn, never awaited
            seen.append(session.layout_metrics_snapshot == main.layout_metrics_snapshot)
            seen.append(session.presentation_viewport_extent == main.presentation_viewport_extent == (400.0, 800.0))
            main.set_custom_viewport_override(None)
            main.commit_content_rotation_map({"spectrum": 2})
            rig.settle()
            seen.append(session.layout_metrics_snapshot == main.layout_metrics_snapshot)
            return seen
        finally:
            rig.close()
            stand_in.close()

    assert run(True) == [True, True, True]
    assert run(False) == [False, False, False]


@pytest.mark.qt
def test_a_retired_owner_leaves_no_callback_of_its_own_on_its_controller(qt_app, pcm):
    # Gate 4 (8 Nov, R-178): the destruction barrier judges a retiring generation's Python owners by reference
    # counting. On the worker path the owner installs its layout-metrics observer (a bound method) on its controller,
    # so owner -> controller -> observer -> owner is a cycle only a deep collection frees: with the admission on,
    # every Settings round trip timed the barrier out and the saver exited. Retirement leaves the controller holding
    # nothing of the owner (it keeps the controller for post-retirement diagnostics).
    import types

    from widgets.spotify_visualizer import engine_worker_link

    stand_in = _InProcessSupervisor()
    rig = gate.OwnerRig("spectrum", worker=True, supervisor=stand_in, cadence="thread")
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
        controller = owner.controller
        assert owner._worker is not None
        installed = [name for name, value in vars(controller).items()
                     if isinstance(value, types.MethodType) and value.__self__ is owner]
        assert installed, "the worker path no longer installs an owner callback: this test checks nothing"
        assert owner.retire()
        held = [name for name, value in vars(controller).items()
                if isinstance(value, types.MethodType) and value.__self__ is owner]
        assert held == [], f"the retired owner is still referenced by its controller through {held}"
    finally:
        rig.close()
        stand_in.close()


@pytest.mark.qt
def test_the_session_is_configured_with_the_bindings_own_activation(qt_app, pcm):
    # A6-L4: the worker receives the activation the host binding resolved and its presentation kwargs (with the
    # resolved 3D Detail tier), never an offline request; its controller records the same inputs as the owner's.
    from core.process.types import MessageType
    from widgets.spotify_visualizer import engine_worker_link

    stand_in = _InProcessSupervisor()
    rig = gate.OwnerRig("sphere", worker=True, supervisor=stand_in, cadence="thread")
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
        configure = [payload for msg, payload in stand_in.sent if msg == MessageType.VIS_CONFIGURE]
        assert len(configure) == 1
        sent = configure[0]["activation"]
        assert "scene3d_detail" in sent["presentation_kwargs"]
        main, session = owner.controller, stand_in.worker._session._controller
        assert sent["settings_model"] == main.settings_model == session.settings_model
        assert repr(session.resolved_activation) == repr(main.resolved_activation)
        assert session.technical_config_cache == main.technical_config_cache
    finally:
        rig.close()
        stand_in.close()


def test_every_configure_takes_a_fresh_label_namespace_from_one_counter():
    from widgets.spotify_visualizer import engine_worker_link

    taken = [engine_worker_link.next_label_namespace() for _ in range(5)]
    assert all(value >= 1 for value in taken) and taken == sorted(set(taken))


# ------------------------------------------------------------------------------------------------ failures


class _Log:
    def __init__(self) -> None:
        self.records: list[tuple[str, str]] = []

    def _record(self, level):
        def log(message, *args, **_kwargs):
            self.records.append((level, message % args if args else message))
        return log

    def __getattr__(self, name):
        if name in ("warning", "error", "info", "exception", "debug"):
            return self._record(name)
        raise AttributeError(name)


@pytest.mark.qt
def test_a_worker_that_cannot_configure_leaves_the_activation_in_process(qt_app, monkeypatch):
    # No supervisor (the worker cannot start): the activation runs in process, logged once; the run is not disabled.
    from widgets.spotify_visualizer import engine_worker_link, quick_display_visualizer_owner

    log = _Log()
    monkeypatch.setattr(quick_display_visualizer_owner, "logger", log)
    rig = gate.OwnerRig("spectrum", worker=True, supervisor=None, clock=[0.0])
    rig.worker = True
    try:
        with pytest.raises(RuntimeError, match="fell back in process"):
            rig.build()
        owner = rig.owner
        assert owner._worker is None and owner.controller.engine is not None
        assert sum("Configure failed" in message for _level, message in log.records) == 1
        assert not engine_worker_link.worker_disabled_for_run()
    finally:
        rig.close()


@pytest.mark.qt
def test_a_worker_that_cannot_start_leaves_the_activation_in_process(qt_app, supervisor, pcm, monkeypatch):
    from widgets.spotify_visualizer import engine_worker_link

    def _refuse(self, playing):
        raise engine_worker_link.EngineWorkerFailure("vis_start: injected", session_closed=True)

    monkeypatch.setattr(engine_worker_link.EngineWorkerLink, "start", _refuse)
    rig = gate.OwnerRig("spectrum", worker=True, supervisor=supervisor, cadence="thread")
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            with pytest.raises(RuntimeError, match="fell back in process"):
                rig.build()
        owner = rig.owner
        assert owner._worker is None and owner.is_started and owner.controller.engine is not None
        assert owner.controller.logical_runtime is not None and owner.controller.logical_runtime.is_running()
        assert not engine_worker_link.worker_disabled_for_run()
    finally:
        rig.close()


@pytest.mark.qt
def test_a_lost_session_fades_the_held_frame_out_reconfigures_and_a_loss_before_the_reveal_stays_in_process(
        qt_app, supervisor, pcm, monkeypatch):
    # The session ends under the owner (stopped behind its back: its wake pipe ends, as when the worker dies, its
    # device fails to open or its steps keep failing). First: the held frame is re-presented fading out on the
    # replacement's publications (never vanishing), then the replacement (a fresh session and namespace) is revealed
    # from hidden. The completed reveal starts the failure count again (checkpoint audit 10, A10-L4), so a later loss
    # recovers the same way. A loss while a recovery's replacement is not yet revealed is the second strike: the owner
    # runs in process for the run. Negative control (no reset, the pre-A10-L4 owner): the second loss, after a
    # completed recovery, already left the worker for the run.
    from core.process.types import MessageType, WorkerType
    from widgets.spotify_visualizer import engine_worker_link

    # Three recoveries are begun below (the run's recovery limit is the other test's, A11-M1).
    assert engine_worker_link.MAX_RECOVERIES_PER_RUN >= 3
    rig = gate.OwnerRig("spectrum", worker=True, supervisor=supervisor, cadence="thread", paced=None)
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
            _pump(rig, 1.6)                              # past the activation fade-in
            first = owner._worker
            assert first.mailbox.last_taken is not None
            fades = []
            commit = owner._apply_resolved_presentation

            def recording(presentation):
                fades.append((float(presentation.content_fade), id(rig.published[-1]) if rig.published else None))
                commit(presentation)

            owner._apply_resolved_presentation = recording           # the steady route and the recovery's commit
            owner._sync.set_presentation_route(owner._resolve_current_presentation, recording)
            stopped = supervisor.send_request_and_await_response(WorkerType.VISUALIZER, MessageType.VIS_STOP, {},
                                                                 timeout_ms=10_000)
            assert stopped is not None and stopped.success
            _pump(rig, 1.5, until=lambda: owner._worker is not first and owner._mode_transition_phase == "idle")
            _pump(rig, 1.0)
            second = owner._worker
            assert second is not None and second is not first
            assert second.label_namespace > first.label_namespace
            # The held frame: one logical frame presented again and again, its fade falling (never a jump to 0).
            runs, start = [], 0
            for index in range(1, len(fades) + 1):
                if index == len(fades) or fades[index][1] != fades[start][1]:
                    runs.append((start, index))
                    start = index
            held_start, held_end = max(runs, key=lambda run: run[1] - run[0])
            held_fades = [fade for fade, _logical in fades[held_start:held_end]]
            assert len(held_fades) >= 3 and held_fades == sorted(held_fades, reverse=True), held_fades
            assert held_fades[0] > 0.5 and held_fades[-1] < 0.5, held_fades
            after = [fade for fade, _logical in fades[held_end:]]
            assert after and after[0] == 0.0 and max(after) == 1.0                  # revealed from hidden
            assert owner._mode_transition_phase == "idle" and not engine_worker_link.worker_disabled_for_run()
            assert owner._worker_failures == 0                         # A10-L4: the completed reveal reset the count
            # A later loss, after a completed recovery, recovers the same way.
            stopped = supervisor.send_request_and_await_response(WorkerType.VISUALIZER, MessageType.VIS_STOP, {},
                                                                 timeout_ms=10_000)
            assert stopped is not None and stopped.success
            _pump(rig, 3.0, until=lambda: owner._worker not in (None, second)
                  and owner._mode_transition_phase == "idle")
            third = owner._worker
            assert third is not None and third is not second and third.label_namespace > second.label_namespace
            assert not engine_worker_link.worker_disabled_for_run() and owner._worker_failures == 0
            # A loss before a recovery's reveal completed: the replacement is held back from revealing (it waits for
            # a fresh frame), so the next loss lands while the count still holds the first strike.
            waiting = owner._worker_waiting_for_fresh_frame
            monkeypatch.setattr(owner, "_worker_waiting_for_fresh_frame",
                                lambda: owner._worker is not third or waiting())
            stopped = supervisor.send_request_and_await_response(WorkerType.VISUALIZER, MessageType.VIS_STOP, {},
                                                                 timeout_ms=10_000)
            assert stopped is not None and stopped.success
            _pump(rig, 3.0, until=lambda: owner._worker not in (None, third) and owner._worker.configured
                  and owner._mode_transition_phase == "waiting_target")
            assert owner._worker not in (None, third) and owner._mode_transition_phase == "waiting_target"
            assert owner._worker_failures == 1
            presented = len(rig.published)
            stopped = supervisor.send_request_and_await_response(WorkerType.VISUALIZER, MessageType.VIS_STOP, {},
                                                                 timeout_ms=10_000)
            assert stopped is not None and stopped.success
            _pump(rig, 1.0, until=lambda: owner._worker is None)
            _pump(rig, 1.5)
            assert owner._worker is None and engine_worker_link.worker_disabled_for_run()
            assert str(engine_worker_link._run_disabled_reason).startswith("second failure")   # not the deadline
            assert owner.controller.engine is not None and owner.controller.logical_runtime.is_running()
            assert len(rig.published) > presented + 20                               # in process, presenting
    finally:
        rig.close()


@pytest.mark.qt
def test_a_failure_that_recurs_after_every_completed_recovery_ends_in_process_at_the_runs_recovery_limit(
        qt_app, supervisor, pcm):
    # Checkpoint audit 11, A11-M1: the session fails again after every completed recovery (stopped behind the owner's
    # back once each replacement is revealed). Each genuinely recovered session still starts the failure count again
    # (A10-L4), but every recovery takes one of the run's ``MAX_RECOVERIES_PER_RUN``; the failure after the last one
    # leaves the worker for the run (held frame faded, the in-process activation revealed and presenting) instead of
    # cycling fade-out / rebuild / fade-in for the whole run. Negative control (no limit, the A10-L4 owner): that
    # failure recovers on the worker once more.
    from core.process.types import MessageType, WorkerType
    from widgets.spotify_visualizer import engine_worker_link

    def end_the_session():
        stopped = supervisor.send_request_and_await_response(WorkerType.VISUALIZER, MessageType.VIS_STOP, {},
                                                             timeout_ms=10_000)
        assert stopped is not None and stopped.success

    rig = gate.OwnerRig("spectrum", worker=True, supervisor=supervisor, cadence="thread", paced=None)
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
            _pump(rig, 1.6)                              # past the activation fade-in
            for _recovery in range(engine_worker_link.MAX_RECOVERIES_PER_RUN):
                failed = owner._worker
                assert failed is not None
                end_the_session()
                _pump(rig, 3.0, until=lambda: owner._worker not in (None, failed)
                      and owner._mode_transition_phase == "idle")
                assert owner._worker not in (None, failed) and owner._mode_transition_phase == "idle"
                assert owner._worker_failures == 0 and not engine_worker_link.worker_disabled_for_run()
            end_the_session()
            _pump(rig, 1.0, until=lambda: owner._worker is None)
            presented = len(rig.published)
            _pump(rig, 1.5)
            _pump(rig, 2.0, until=lambda: owner._mode_transition_phase == "idle")
            assert owner._worker is None and engine_worker_link.worker_disabled_for_run()
            assert str(engine_worker_link._run_disabled_reason).startswith("recovery limit")
            assert owner.controller.engine is not None and owner.controller.logical_runtime.is_running()
            assert len(rig.published) > presented + 20                               # in process, presenting
            assert owner._mode_transition_phase == "idle" and owner._mode_transition_fade == 1.0   # revealed
    finally:
        rig.close()


# --------------------------------------------------------------------------------- the device (slice 5.3 core)


def _device_session(monkeypatch, device):
    """A production session (worker-paced, no recorded PCM) in this process, with the device constructor replaced."""
    import multiprocessing

    from core.visualizer_engine.engine_worker import EngineSession
    from core.visualizer_engine.packet_mailbox import PacketMailbox

    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", device)
    reader = PacketMailbox(role="reader")
    receiver, sender = multiprocessing.Pipe(duplex=False)
    ended = threading.Event()
    reader.listen_for_wakes(receiver, on_closed=ended.set)
    session = EngineSession(mapping=reader.mapping_name, mode="spectrum", runtime_generation=1, inputs="live",
                            order="free", cadence="worker", wake=_InProcessSupervisor._duplicate(sender))
    sender.close()
    return session, reader, ended


@pytest.mark.qt
def test_the_production_session_opens_the_device_through_the_normal_capture_path_on_its_lane(qt_app, monkeypatch):
    from core.visualizer_engine.recorded_capture import RecordedCaptureBackend

    opened = []

    def device(config=None):
        opened.append(threading.current_thread().name)
        return RecordedCaptureBackend(config)

    session, reader, ended = _device_session(monkeypatch, device)
    try:
        engine = session._engine
        assert not session.device_refused and engine._audio_worker._capture_backend_factory is None
        session.start(True)
        done = threading.Event()
        assert engine.fence_capture_transactions(done.set) and done.wait(10.0)
        assert opened == ["affinity_io_lane:audio_capture"] and engine.is_capture_running()
        done.clear()
        assert engine.fence_capture_transactions(done.set) and done.wait(10.0)     # the session's check ran
        assert not session.capture_failed and not ended.is_set()
    finally:
        session.close()
        reader.close()


@pytest.mark.qt
def test_a_device_that_does_not_open_keeps_the_session_and_is_retried_at_the_next_capture_edge(qt_app, monkeypatch):
    # A7-L4: a device failure is not a worker failure. The session keeps running (its wake pipe stays open: no
    # session end for the owner, no fade, nothing counted towards ending the worker for the run), reports the failure
    # in its replies and retries the device at the next edge that opens capture (here Media's pause and play).
    # Negative control (the pre-fix report): the wake pipe closed, so the owner saw the session end.
    from core.process.types import MessageType, WorkerMessage
    from core.visualizer_engine.engine_worker import VisualizerEngineWorker
    from core.visualizer_engine.recorded_capture import RecordedCaptureBackend

    attempts = []

    def device(config=None):
        attempts.append(config)
        if len(attempts) == 1:
            raise OSError("no loopback device")
        return RecordedCaptureBackend(config)

    session, reader, ended = _device_session(monkeypatch, device)
    worker = VisualizerEngineWorker(None, None)
    worker._session = session
    try:
        engine = session._engine
        session.start(True)                        # never waits on the device (as in process)
        for _check in range(2):                    # the open, then the session's check behind it
            done = threading.Event()
            assert engine.fence_capture_transactions(done.set) and done.wait(10.0)
        assert session.capture_failed and not ended.is_set() and not engine.is_capture_running()
        reply = worker.handle_message(WorkerMessage(msg_type=MessageType.VIS_SET_VIEW, seq_no=1, correlation_id="1",
                                                    payload={"extent": (400.0, 300.0), "rotations": {}}))
        assert reply.success and reply.payload["capture_failed"] is True
        session.set_playing(False)
        session.set_playing(True)                  # the next capture edge retries the device
        for _check in range(2):
            done = threading.Event()
            assert engine.fence_capture_transactions(done.set) and done.wait(10.0)
        assert len(attempts) == 2 and engine.is_capture_running() and not session.capture_failed
        assert not ended.wait(0.2)                 # the session never ended for its owner
    finally:
        worker._session = None
        session.close()
        reader.close()
