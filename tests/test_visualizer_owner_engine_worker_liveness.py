"""Native core P2b, work order 5 slice 5.5 (failure and liveness) and checkpoint audit 7's failure items: the owner on
the engine worker never waits on it, sees a dead worker by an event, bounds its recovery, and fades, never vanishes.

The REAL owner built by the host binding on an unshown runtime (``tools/visualizer_replay/owner_worker_gate.py``'s rig;
no window is shown); no device is opened (recorded PCM through ``engine_worker_link.recorded_capture_for_testing``).
The liveness tests drive a real ``WorkerType.VISUALIZER`` process (a hung worker is a suspended process, a dead one a
killed process); the recovery and edge-order tests run the same ``VisualizerEngineWorker`` in this process behind the
supervisor stand-in, so the order is deterministic.
"""
from __future__ import annotations

import multiprocessing
import threading
import time

import pytest

from tests.test_visualizer_owner_engine_worker import _InProcessSupervisor, _Log, _pump
from tools.visualizer_replay import owner_worker_gate as gate

#: One frame at 60 Hz: the GUI-thread bound for any control edge (slice 5.5's gate).
FRAME_S = 1.0 / 60.0


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
def pcm():
    from tools.visualizer_replay.live_engine_gate import paced_pcm

    return paced_pcm(3.0)


def _fast_heartbeat_supervisor():
    """A real supervisor at the production heartbeat; ``_fast_heartbeat`` speeds it up only while a hung worker is
    being judged. A cold configure (the worker's imports and session build, run by its message loop between
    heartbeats) is judged as production judges it (5 misses at 3 s), never by the fast beat's 1.25 s, which a first or
    replacement configure can exceed on a cold or loaded machine since workers no longer preload `main.py`'s imports
    (checkpoint audit 10, A10-M1): the fast beat then retired healthy workers mid-configure and the owner fell back."""
    from core.process.supervisor import ProcessSupervisor
    from core.process.types import WorkerType
    from core.visualizer_engine.engine_worker import visualizer_worker_main

    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    assert supervisor.start(WorkerType.VISUALIZER)
    return supervisor


def _fast_heartbeat(supervisor) -> None:
    """Judge every 0.25 s (production: 3 s): a hung worker is retired after a few missed beats, in seconds."""
    supervisor._heartbeat_interval_s = 0.25


def _production_heartbeat(supervisor) -> None:
    """Back to the production interval once the hung worker is retired, before its replacement configures."""
    from core.process.types import HealthStatus

    supervisor._heartbeat_interval_s = HealthStatus.HEARTBEAT_INTERVAL_MS / 1000.0


def _timed(record: dict, name: str, call):
    start = time.perf_counter()
    try:
        return call()
    finally:
        record.setdefault(name, []).append(time.perf_counter() - start)


def _record_fades(rig, owner) -> list:
    """(content fade, the logical frame presented) for every presentation from now on (the steady route and the
    recovery's commit)."""
    fades: list = []
    commit = owner._apply_resolved_presentation

    def recording(presentation):
        fades.append((float(presentation.content_fade), rig.published[-1] if rig.published else None))
        commit(presentation)

    owner._apply_resolved_presentation = recording
    owner._sync.set_presentation_route(owner._resolve_current_presentation, recording)
    return fades


def _fail_session_behind_the_owners_back(stand_in) -> None:
    """The in-process worker closes its session: its wake writer closes, so the owner's listener sees the pipe end (as
    when the worker process dies)."""
    stand_in.worker._close_session()


# ------------------------------------------------------------------------------------------------ the wake pipe


def test_a_full_wake_pipe_never_blocks_the_worker_tick(monkeypatch):
    # A reader that stopped draining fills the wake pipe; the writer (the worker's cadence thread) drops the byte
    # instead of blocking (the reader has wakes pending and takes the newest frame per wake). Negative control: the
    # pre-5.5 blocking send never returns.
    from core.visualizer_engine import packet_mailbox
    from core.visualizer_engine.packet_mailbox import PacketMailbox

    def run(blocking: bool) -> tuple[bool, int, int]:
        reader = PacketMailbox(role="reader")
        receiver, sender = multiprocessing.Pipe(duplex=False)
        writer = PacketMailbox(role="writer", attach=reader.mapping_name, wake_sender=sender)
        send = (lambda conn: (conn.send_bytes(b"w"), True)[1]) if blocking else \
            packet_mailbox.send_wake_byte_without_blocking
        done = threading.Event()

        def publish_many() -> None:
            with monkeypatch.context() as patch:
                patch.setattr(packet_mailbox, "send_wake_byte_without_blocking", send)
                for _ in range(70_000):                # more wakes than a pipe holds (64 Ki one-byte messages)
                    writer._send_wake()
            done.set()

        threading.Thread(target=publish_many, daemon=True).start()
        finished = done.wait(3.0)
        dropped = writer.wakes_dropped
        drained = 0
        while not done.is_set() or receiver.poll(0):   # drain (this releases a blocked writer) until it is done
            if receiver.poll(0.05):
                receiver.recv_bytes()
                drained += 1
        writer.close()
        reader.close()
        receiver.close()
        return finished, dropped, drained

    finished, dropped, drained = run(blocking=False)
    assert finished and dropped > 0 and drained > 0, (finished, dropped, drained)
    finished, _dropped, _drained = run(blocking=True)
    assert not finished


# ------------------------------------------------------------------------------------- liveness (real process)


@pytest.mark.qt
def test_control_edges_never_wait_on_a_hung_worker_and_the_heartbeat_ends_it(qt_app, pcm):
    # A7-M4: a hung-but-alive worker (its process suspended) answers nothing; every edge returns within one frame
    # (sent, never awaited: Media's play edge, display power, a 30-step view drag, a mode request), and the
    # supervisor's heartbeat (bounded: a few missed beats, then the stop's bound and termination) ends the worker,
    # which fails the session by an event: the owner reconfigures once onto a fresh worker and recovers there.
    # Before 5.5 the first edge blocked the GUI for the edge timeout (measured: 21.9 s with the production heartbeat).
    import psutil

    from core.process.types import WorkerType
    from widgets.spotify_visualizer import engine_worker_link

    supervisor = _fast_heartbeat_supervisor()
    rig = gate.OwnerRig("spectrum", worker=True, supervisor=supervisor, cadence="thread",
                        extra_modes=("oscilloscope",))
    times: dict = {}
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
            _pump(rig, 1.0)
            hung = owner._worker
            process = psutil.Process(supervisor._workers[WorkerType.VISUALIZER].pid)
            _fast_heartbeat(supervisor)
            process.suspend()
            try:
                controller = owner.controller
                _timed(times, "set_playing", lambda: owner.set_playing(False))
                _timed(times, "set_display_power", lambda: owner.set_display_power(False))
                _timed(times, "set_display_power", lambda: owner.set_display_power(True))
                for step in range(30):
                    _timed(times, "view", lambda s=step: controller.set_custom_viewport_override(
                        (800.0 + s, 400.0), {"spectrum": 0}))
                    rig.app.processEvents()
                inputs = gate.activation_inputs(rig.widgets, "oscilloscope")
                _timed(times, "request_mode_change", lambda: owner.request_mode_change("oscilloscope", **inputs))
                started = time.perf_counter()
                _pump(rig, 20.0, until=lambda: owner._worker is not hung)
                detected_s = time.perf_counter() - started
                _production_heartbeat(supervisor)
            finally:
                try:
                    process.resume()
                except psutil.Error:
                    pass
            _pump(rig, 15.0, until=lambda: owner._worker is not None and not owner._worker.busy
                  and owner._mode_transition_phase == "idle")
            worst = {name: max(values) for name, values in times.items()}
            print("GUI stall per edge (s), hung worker:", worst, "failure detected after", round(detected_s, 2))
            assert all(value < FRAME_S for value in worst.values()), worst
            assert owner._worker is not hung and owner._worker is not None, detected_s
            assert owner._mode_transition_phase == "idle" and not engine_worker_link.worker_disabled_for_run()
    finally:
        rig.close()
        supervisor.shutdown()


@pytest.mark.qt
def test_a_killed_worker_is_seen_by_its_pipe_end_and_the_owner_recovers_on_a_fresh_worker(qt_app, pcm):
    # A dead worker is detected by an event (the session's wake pipe ends: the worker held its only writer end), not a
    # reply timeout; the edge sent into it returns at once; the replacement's configure reaches a restarted worker
    # (a configure queued to the dead process and cancelled by the supervisor's restart goes out again, once).
    import psutil

    from core.process.types import WorkerType
    from widgets.spotify_visualizer import engine_worker_link

    supervisor = _fast_heartbeat_supervisor()
    rig = gate.OwnerRig("spectrum", worker=True, supervisor=supervisor, cadence="thread")
    times: dict = {}
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
            _pump(rig, 1.0)
            first = owner._worker
            psutil.Process(supervisor._workers[WorkerType.VISUALIZER].pid).kill()
            _timed(times, "set_playing", lambda: owner.set_playing(False))
            _timed(times, "set_playing", lambda: owner.set_playing(True))
            _pump(rig, 20.0, until=lambda: owner._worker is not first and owner._worker is not None
                  and owner._worker.configured and owner._mode_transition_phase == "idle")
            worst = max(times["set_playing"])
            assert worst < FRAME_S, worst
            assert owner._worker is not None and owner._worker is not first, owner._worker
            assert owner._mode_transition_phase == "idle" and not engine_worker_link.worker_disabled_for_run()
            presented = len(rig.published)
            _pump(rig, 1.0)
            assert len(rig.published) > presented + 20             # the fresh worker's frames are presented
    finally:
        rig.close()
        supervisor.shutdown()


# ------------------------------------------------------------------------------ bounded recovery (A7-M3)


def _stand_in_rig(pcm, mode: str = "spectrum", **kwargs):
    from widgets.spotify_visualizer import engine_worker_link

    stand_in = _InProcessSupervisor()
    rig = gate.OwnerRig(mode, worker=True, supervisor=stand_in, cadence="thread", **kwargs)
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
    except BaseException:
        rig.close()
        stand_in.close()
        raise
    return stand_in, rig, owner


@pytest.mark.qt
@pytest.mark.parametrize("bounded", (True, False))
def test_a_replacement_that_never_publishes_is_bounded_by_the_recovery_deadline(qt_app, pcm, monkeypatch, bounded):
    # The first session fails; its replacement configures but never publishes (its cadence never starts), so nothing
    # paces the held frame's fade. The recovery's deadline falls back in process once (counted for the run): the
    # in-process runtime's publications pace the fade, then the in-process activation is revealed. Negative control
    # (no recovery deadline, the pre-5.5 owner): the frame stays frozen in "recovering" and Settings stays refused.
    from core.visualizer_engine.engine_worker import EngineSession
    from widgets.spotify_visualizer import engine_worker_link
    from widgets.spotify_visualizer import quick_display_visualizer_owner as owner_module

    monkeypatch.setattr(owner_module, "_ACTIVATION_TRANSACTION_DEADLINE_MS", 500)
    if not bounded:
        monkeypatch.setattr(owner_module.QuickDisplayVisualizerOwner, "_arm_recovery_deadline", lambda self: None)
    stand_in, rig, owner = _stand_in_rig(pcm)
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            _pump(rig, 1.6)                                          # past the activation fade-in
            fades = _record_fades(rig, owner)
            monkeypatch.setattr(EngineSession, "_start_cadence", lambda self: None)   # the replacement stays silent
            _fail_session_behind_the_owners_back(stand_in)
            _pump(rig, 0.4)
            assert owner._mode_transition_phase == "recovering" and owner._worker is not None
            frozen = len(fades)
            _pump(rig, 3.0, until=lambda: owner._mode_transition_phase == "idle")
        if not bounded:
            assert owner._mode_transition_phase == "recovering" and len(fades) == frozen
            return
        assert owner._worker is None and engine_worker_link.worker_disabled_for_run()
        assert owner._mode_transition_phase == "idle" and owner._mode_transition_fade == 1.0
        after = [fade for fade, _logical in fades[frozen:]]
        assert after and max(after) == 1.0 and min(after) == 0.0, after             # faded, then revealed
    finally:
        rig.close()
        stand_in.close()


@pytest.mark.qt
def test_a_fallback_that_raises_is_contained_and_escalates_once(qt_app, pcm, monkeypatch):
    # A7-M3 (iii): the second failure's in-process fallback raises; nothing escapes into the edge's caller (here
    # Media's play edge, which found the link closed), and the owner escalates once to the generation-fenced
    # reconstruction. Negative control: the unguarded fallback raises out of Media's handler.
    from widgets.spotify_visualizer import quick_display_visualizer_owner as owner_module

    def boom(*_args, **_kwargs):
        raise RuntimeError("the in-process configure failed")

    from widgets.spotify_visualizer import engine_worker_link

    for guarded in (True, False):
        engine_worker_link.reset_run_state_for_testing()
        stand_in, rig, owner = _stand_in_rig(pcm)
        try:
            _pump(rig, 0.3)
            failures: list = []
            owner._transition_failure_callback = failures.append
            owner._worker_failures = 1                                 # the next failure is the second
            if not guarded:
                monkeypatch.setattr(owner, "_fall_back_in_process", owner._fall_back_in_process_unguarded)
            with monkeypatch.context() as patch:
                patch.setattr(owner_module, "configure_logical_controller", boom)
                owner._worker.close()                                  # the session's link is gone
                if guarded:
                    owner.set_playing(False)                            # never raises
                    assert failures == ["engine_worker_fallback_failed"]
                    assert owner._mode_transition_phase == "failed"
                else:
                    with pytest.raises(RuntimeError, match="in-process configure failed"):
                        owner.set_playing(False)
        finally:
            owner._worker = None
            rig.close()
            stand_in.close()


@pytest.mark.qt
def test_a_crossfade_deadline_armed_before_a_failure_cannot_fire_into_its_recovery(qt_app, pcm):
    # A7-M3: a recovery bumps the request serial, so the crossfade's deadline (armed at the request, same serial
    # before) is inert during the recovery. Negative control: with the serial it was armed with, the same deadline
    # signals "deadline:recovering" (a full reconstruction).
    stand_in, rig, owner = _stand_in_rig(pcm, extra_modes=("oscilloscope",))
    try:
        _pump(rig, 1.6)
        failures: list = []
        owner._transition_failure_callback = failures.append
        assert owner.request_mode_change("oscilloscope", **gate.activation_inputs(rig.widgets, "oscilloscope"))
        armed = owner._transition_request_serial
        _fail_session_behind_the_owners_back(stand_in)
        _pump(rig, 2.0, until=lambda: owner._mode_transition_phase == "recovering")
        assert owner._mode_transition_phase == "recovering"
        owner._on_transition_deadline(armed)
        assert not failures and owner._mode_transition_phase == "recovering"
        owner._transition_request_serial = armed                       # the negative control: no fence
        owner._on_transition_deadline(armed)
        assert failures == ["deadline:recovering"]
    finally:
        rig.close()
        stand_in.close()


@pytest.mark.qt
@pytest.mark.parametrize("pre_fix", (False, True))
def test_a_slow_but_healthy_replacement_gets_its_own_reveal_deadline(qt_app, pcm, monkeypatch, pre_fix):
    # Checkpoint audit 8, A8-M1: the replacement's session build is slow (a cold spawn and build measured ~4 s) and its
    # first presentable frame comes 1 s after its reveal starts (a prepared reveal waiting for its warm frames):
    # healthy, but past the deadline armed at the failure. The reveal has its own deadline, so the replacement is
    # revealed on the worker. Negative control (the pre-fix reveal re-armed with the failure's serial): the failure's
    # shot fires into the reveal, the healthy replacement is retired and the worker is off for the run.
    from core.visualizer_engine.engine_worker import EngineSession
    from widgets.spotify_visualizer import engine_worker_link
    from widgets.spotify_visualizer import quick_display_visualizer_owner as owner_module

    owner_class = owner_module.QuickDisplayVisualizerOwner
    monkeypatch.setattr(owner_module, "_ACTIVATION_TRANSACTION_DEADLINE_MS", 1500)
    if pre_fix:
        def old_finish(self, now):
            recovery, self._worker_recovery = self._worker_recovery, None
            if recovery is None:
                return
            if recovery["reveal"]:
                self._bind_replacement(recovery["identity"], now, reveal=True)
                self._arm_recovery_deadline()                          # the failure's serial: its shot stays live
            else:
                self._bind_replacement(recovery["identity"], now, reveal=False)
                self._mode_transition_phase = "idle"
                self._recovery_stage = 0

        monkeypatch.setattr(owner_class, "_finish_worker_recovery", old_finish)
    stand_in, rig, owner = _stand_in_rig(pcm)
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            _pump(rig, 1.6)
            first = owner._worker
            build = EngineSession.__init__

            def slow_build(self, *args, **kwargs):
                time.sleep(0.5)
                build(self, *args, **kwargs)

            reveal: dict = {}
            waiting = owner_class._worker_waiting_for_fresh_frame

            def warm_frames_first(self):
                if self._worker is not first:
                    since = reveal.setdefault("since", time.perf_counter())
                    if time.perf_counter() - since < 1.0:
                        return True
                return waiting(self)

            monkeypatch.setattr(EngineSession, "__init__", slow_build)
            monkeypatch.setattr(owner_class, "_worker_waiting_for_fresh_frame", warm_frames_first)
            _fail_session_behind_the_owners_back(stand_in)
            _pump(rig, 6.0, until=lambda: "since" in reveal and owner._mode_transition_phase == "idle")
            assert owner._mode_transition_phase == "idle"
        if pre_fix:
            assert owner._worker is None and engine_worker_link.worker_disabled_for_run()
            return
        assert owner._worker is not None and owner._worker is not first
        assert not engine_worker_link.worker_disabled_for_run() and owner._mode_transition_fade == 1.0
    finally:
        rig.close()
        stand_in.close()


@pytest.mark.qt
@pytest.mark.parametrize("pre_fix", (False, True))
def test_a_recovery_that_never_reveals_escalates_to_the_reconstruction_as_in_process(qt_app, pcm, monkeypatch,
                                                                                    pre_fix):
    # Checkpoint audit 8, A8-M2: the replacement never reveals (its reveal never completes: a prepared reveal that
    # never finishes), so the first expiry falls back in process; the in-process activation never reveals either. The
    # second expiry escalates to the generation-fenced reconstruction, exactly as an in-process activation's
    # waiting_target deadline does ("deadline:waiting_target": the display's reload retires this owner, its hidden
    # runtime with it, and the rebuilt one fades in). Negative control (the pre-fix second expiry): the owner goes idle
    # at fade 0 while its in-process runtime keeps publishing invisible frames, and nothing brings it back.
    from widgets.spotify_visualizer import engine_worker_link
    from widgets.spotify_visualizer import quick_display_visualizer_owner as owner_module

    owner_class = owner_module.QuickDisplayVisualizerOwner
    monkeypatch.setattr(owner_module, "_ACTIVATION_TRANSACTION_DEADLINE_MS", 500)
    if pre_fix:
        expiry = owner_class._on_recovery_deadline

        def old_second_expiry(self, serial):
            if (not self._retired and serial == self._transition_request_serial and self._display_power_on
                    and self._recovery_stage and self._worker is None
                    and self._mode_transition_phase == "waiting_target"):
                self._recovery_stage = 0
                self._mode_transition_phase = "idle"
                self._mode_transition_fade = 0.0
                self._preparing_activation = None
                return
            expiry(self, serial)

        monkeypatch.setattr(owner_class, "_on_recovery_deadline", old_second_expiry)
    stand_in, rig, owner = _stand_in_rig(pcm)
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            _pump(rig, 1.6)
            failures: list = []
            owner._transition_failure_callback = failures.append
            monkeypatch.setattr(owner_class, "_target_renderer_preparing", lambda self, now: True)
            _fail_session_behind_the_owners_back(stand_in)
            _pump(rig, 5.0, until=lambda: failures or (owner._worker is None and owner._recovery_stage == 0
                                                       and owner._mode_transition_phase == "idle"))
            assert owner._worker is None and engine_worker_link.worker_disabled_for_run()   # the first expiry
            if pre_fix:
                assert not failures and owner._mode_transition_phase == "idle"
                assert owner._mode_transition_fade == 0.0
                presented = len(rig.published)
                _pump(rig, 0.5)
                assert len(rig.published) > presented + 10              # invisible frames, nothing brings it back
                return
            assert failures == ["deadline:waiting_target"] and owner._mode_transition_phase == "failed"
    finally:
        rig.close()
        stand_in.close()


# ----------------------------------------------------------------------------------------------- the lows


@pytest.mark.qt
@pytest.mark.parametrize("pre_fix", (False, True))
def test_a_failed_commit_never_flashes_the_outgoing_frame_back(qt_app, pcm, monkeypatch, pre_fix):
    # A7-L1: the hidden activation's commit fails after the outgoing frame faded out to 0; the recovery holds that
    # frame at the fade it was drawn at (0), so nothing flashes, then reveals the replacement from hidden. Negative
    # control (the pre-fix order: the fade reset to 1.0 before the hold): the faded-out frame is re-presented visible.
    from core.visualizer_engine.engine_worker import EngineSession
    from widgets.spotify_visualizer import quick_display_visualizer_owner as owner_module

    def refuse(self, *_args, **_kwargs):
        raise RuntimeError("the commit failed")

    monkeypatch.setattr(EngineSession, "request_mode", refuse)
    if pre_fix:
        abandon = owner_module.QuickDisplayVisualizerOwner._abandon_worker_commit

        def reset_first(self):
            # The pre-fix order: the failed commit restored full opacity before the failure path took its hold.
            if self._worker_commit is not None:
                self._mode_transition_fade = 1.0
            abandon(self)

        monkeypatch.setattr(owner_module.QuickDisplayVisualizerOwner, "_abandon_worker_commit", reset_first)
    stand_in, rig, owner = _stand_in_rig(pcm, extra_modes=("oscilloscope",))
    try:
        _pump(rig, 1.6)
        fades = _record_fades(rig, owner)
        first = owner._worker
        assert owner.request_mode_change("oscilloscope", **gate.activation_inputs(rig.widgets, "oscilloscope"))
        _pump(rig, 4.0, until=lambda: owner._worker not in (None, first) and owner._mode_transition_phase == "idle")
        # Recovered on the worker; its completed reveal started the failure count again (A10-L4).
        assert owner._worker not in (None, first) and owner._mode_transition_phase == "idle"
        assert owner._worker_failures == 0
        zero = next(index for index, (fade, _logical) in enumerate(fades) if fade == 0.0)
        # A re-presentation of a frame already shown (the recovery's held frame) at a visible fade is the flash.
        seen: set = set()
        again = []
        for index, (fade, logical) in enumerate(fades):
            if index > zero and id(logical) in seen:
                again.append(fade)
            seen.add(id(logical))
        flashed = any(fade > 0.0 for fade in again)
        assert again and flashed is pre_fix, again
    finally:
        rig.close()
        stand_in.close()


@pytest.mark.qt
def test_a_replacement_that_fails_before_it_starts_leaves_the_in_process_identity_bound(qt_app, pcm, monkeypatch):
    # A7-L2: the replacement's first edge fails (its VIS_SET_VIEW). The failure arrives as an event, never inside the
    # reconfigure, so the second failure's in-process fallback is what stays bound: its frames pass render admission
    # and are presented (the pre-fix re-entry bound the dead replacement's identity: hidden for good).
    from core.visualizer_engine.engine_worker import EngineSession

    stand_in, rig, owner = _stand_in_rig(pcm)
    try:
        _pump(rig, 1.6)
        set_view = EngineSession.set_view

        def refuse(self, **kwargs):
            raise RuntimeError("the view was refused")

        monkeypatch.setattr(EngineSession, "set_view", refuse)
        owner.controller.set_custom_viewport_override((640.0, 360.0), {"spectrum": 0})   # the replacement sends it
        monkeypatch.setattr(EngineSession, "set_view", set_view)
        owner.controller.set_custom_viewport_override(None)
        rig.settle()
        monkeypatch.setattr(EngineSession, "set_view", refuse)
        _fail_session_behind_the_owners_back(stand_in)
        _pump(rig, 4.0, until=lambda: owner._worker is None and owner._mode_transition_phase == "idle")
        assert owner._worker is None and owner._mode_transition_phase == "idle"
        engine = owner.controller.engine
        identity = owner.render_identity
        assert (identity.engine_generation, identity.activation_id) == (engine.get_generation_id(),
                                                                        engine.get_activation_id())
        presented = len(rig.published)
        _pump(rig, 0.5)
        assert len(rig.published) > presented + 10
    finally:
        rig.close()
        stand_in.close()


@pytest.mark.qt
@pytest.mark.parametrize("pre_fix", (False, True))
def test_a_failure_while_parked_presents_no_pre_park_frame_at_the_unpark(qt_app, pcm, monkeypatch, pre_fix):
    # A7-L3: the session fails while the displays are off; nothing pre-park is held, so at the unpark the replacement
    # reveals from hidden and the hours-old frame is never presented. Negative control (the pre-fix hold, which ignored
    # display power): the pre-park frame is presented again after the unpark.
    from widgets.spotify_visualizer import quick_display_visualizer_owner as owner_module

    if pre_fix:
        def old_hold(self, link):
            if self._worker_recovery is not None or self._recovery_held is not None:
                return
            held = link.mailbox.last_taken if link.mailbox is not None else None
            if held is not None:
                self._recovery_held = (held, float(self._mode_transition_fade))

        def old_begin(self):
            held = self._recovery_held
            begin(self)
            if held is not None and self._worker_recovery is not None:
                self._worker_recovery.update(held=held[0], revision=int(held[0].revision), fade_from=held[1],
                                             done=False)

        begin = owner_module.QuickDisplayVisualizerOwner._begin_worker_recovery
        monkeypatch.setattr(owner_module.QuickDisplayVisualizerOwner, "_hold_for_recovery", old_hold)
        monkeypatch.setattr(owner_module.QuickDisplayVisualizerOwner, "_begin_worker_recovery", old_begin)
        monkeypatch.setattr(owner_module.QuickDisplayVisualizerOwner, "_drop_recovery_hold", lambda self: None)
    stand_in, rig, owner = _stand_in_rig(pcm)
    try:
        _pump(rig, 1.6)
        owner.set_display_power(False)
        rig.settle()
        pre_park = owner._worker.mailbox.last_taken.state
        _fail_session_behind_the_owners_back(stand_in)
        _pump(rig, 0.5)
        mark = len(rig.published)
        owner.set_display_power(True)
        _pump(rig, 3.0, until=lambda: owner._mode_transition_phase == "idle" and owner._worker is not None)
        assert owner._mode_transition_phase == "idle"
        shown_again = any(logical is pre_park for logical in rig.published[mark:])
        assert shown_again is pre_fix
    finally:
        rig.close()
        stand_in.close()


@pytest.mark.qt
def test_the_worker_path_logs_playback_edges_and_logs_a_park_only_once_applied(qt_app, pcm, monkeypatch):
    # A7-L5: with the reactivity diagnostics on, Media's play edge on the worker path records its T1 (sent) and T2
    # (the worker's reply); "parked" is logged on the park's successful reply only, never for a failed edge.
    from core.visualizer_engine.engine_worker import EngineSession
    from widgets.spotify_visualizer import quick_display_visualizer_owner as owner_module

    log = _Log()
    monkeypatch.setattr(owner_module, "logger", log)
    monkeypatch.setattr(owner_module, "is_viz_diagnostics_enabled", lambda: True)
    stand_in, rig, owner = _stand_in_rig(pcm)
    try:
        _pump(rig, 0.3)
        owner.set_playing(False)
        rig.settle()
        stages = [message for _level, message in log.records if "[VIS_PLAYBACK_EDGE]" in message]
        assert any("stage=T1" in message for message in stages) and any("stage=T2" in message for message in stages)

        def refuse(self, on):
            raise RuntimeError("the park failed")

        monkeypatch.setattr(EngineSession, "set_display_power", refuse)
        owner.set_display_power(False)
        rig.settle()
        assert not any("Visualizer parked" in message for _level, message in log.records), log.records
    finally:
        rig.close()
        stand_in.close()


@pytest.mark.qt
@pytest.mark.parametrize("pre_fix", (False, True))
def test_a_park_reply_that_lands_after_the_unpark_never_clears_the_reader(qt_app, pcm, monkeypatch, pre_fix):
    # Checkpoint audit 8, A8-L3: OFF then ON are both sent before the OFF reply is handled (the GUI thread was busy),
    # so the worker may already have published post-unpark frames. Only the newest edge's reply acts: the reader is
    # never cleared while the displays are on. Negative control (the pre-fix reply, fenced by the link only): the OFF
    # reply clears the reader with the displays back on, dropping a fresh post-unpark frame.
    from widgets.spotify_visualizer import quick_display_visualizer_owner as owner_module

    if pre_fix:
        def old_edge(self, on):
            controller, link = self._controller, self._worker

            def applied(_reply, _link=link):
                if _link is not self._worker:
                    return
                if not on:
                    controller.logical_mailbox.clear()

            link.set_display_power(on, on_reply=applied)
            return True

        monkeypatch.setattr(owner_module.QuickDisplayVisualizerOwner, "_set_display_power_on_worker", old_edge)
    stand_in, rig, owner = _stand_in_rig(pcm)
    try:
        _pump(rig, 0.3)
        mailbox = owner.controller.logical_mailbox
        clear = mailbox.clear
        cleared_while_on: list = []

        def recording_clear():
            cleared_while_on.append(owner.display_power_on)
            clear()

        mailbox.clear = recording_clear
        assert owner.set_display_power(False) and owner.set_display_power(True)   # both sent before either reply
        rig.settle()
        assert cleared_while_on == ([True] if pre_fix else []), cleared_while_on
    finally:
        rig.close()
        stand_in.close()


class _ManualSupervisor:
    """The supervisor's asynchronous request surface with every reply in the test's hands (no worker). An abandoned
    correlation's callback stays with the test: a late emit from a listener already running it."""

    def __init__(self) -> None:
        self.callbacks: dict = {}
        self.sent: list = []
        self.payloads: list = []

    def register_worker_factory(self, *_args) -> None:
        return None

    def is_running(self, _worker_type) -> bool:
        return True

    def stop(self, _worker_type, timeout=None) -> bool:
        return True

    def start(self, _worker_type) -> bool:
        return True

    def register_response_callback(self, _worker_type, correlation_id, callback) -> bool:
        self.callbacks[correlation_id] = callback
        return True

    def send_message(self, _worker_type, msg_type, payload, correlation_id=None):
        self.sent.append((msg_type, correlation_id))
        self.payloads.append(payload)
        return correlation_id

    def abandon_response(self, _worker_type, correlation_id, *, reason="") -> int:
        return 0


@pytest.mark.qt
@pytest.mark.parametrize("pre_fix", (False, True))
def test_a_late_reply_for_an_abandoned_correlation_never_answers_its_resend(qt_app, monkeypatch, pre_fix):
    # Checkpoint audit 8, A8-L4: the supervisor retires the worker before the configure is answered; the link sends
    # the configure again under a new correlation. A late answer for the abandoned correlation (a listener already
    # running its callback when it was abandoned) is dropped: only the resend's reply configures the link. Negative
    # control (the pre-fix match by token): the stale answer configures it, and the resend's real reply is dropped.
    from core.process.types import MessageType, WorkerResponse
    from widgets.spotify_visualizer.engine_worker_link import ACTIVATION_KEYS, EngineWorkerLink

    if pre_fix:
        deliver = EngineWorkerLink._deliver_reply

        def by_token(self, token, correlation, response, **kwargs):
            entry = self._pending.get(token)
            return deliver(self, token, entry[2] if entry is not None else correlation, response, **kwargs)

        monkeypatch.setattr(EngineWorkerLink, "_deliver_reply", by_token)

    def reply(correlation: str, identity: tuple[int, int]) -> WorkerResponse:
        return WorkerResponse(msg_type=MessageType.VIS_CONFIGURE, seq_no=0, correlation_id=correlation, success=True,
                              payload={"engine_generation": identity[0], "activation_id": identity[1]})

    supervisor = _ManualSupervisor()
    configured: list = []
    link = EngineWorkerLink(supervisor, on_lost=lambda _link, _reason: None)
    try:
        link.configure(runtime_generation=1, mode="spectrum", bar_count=32,
                       activation={key: None for key in ACTIVATION_KEYS}, on_configured=configured.append)
        (_message, abandoned), = supervisor.sent
        late = supervisor.callbacks[abandoned]
        late(None)                                                # cancelled: the worker was retired
        gate._event_loop_for(qt_app, 5.0, until=lambda: len(supervisor.sent) == 2)
        (_message, resent) = supervisor.sent[1]
        assert resent != abandoned
        late(reply(abandoned, (7, 7)))                            # the abandoned correlation answers late
        qt_app.processEvents()
        supervisor.callbacks[resent](reply(resent, (8, 8)))
        gate._event_loop_for(qt_app, 5.0, until=lambda: bool(configured) and not link.busy)
        assert configured == ([(7, 7)] if pre_fix else [(8, 8)]), configured
    finally:
        link.close()


class _HungSupervisor(_InProcessSupervisor):
    """A worker that answers nothing from its first configure on (hung inside it: a device open, a stuck build; or
    a spawn task queued behind a busy IO pool)."""

    def send_message(self, worker_type, msg_type, payload, correlation_id=None):
        self.sent.append((msg_type, dict(payload)))
        return correlation_id


@pytest.mark.qt
@pytest.mark.parametrize("bounded", (True, False))
def test_a_first_configure_that_is_never_answered_is_bounded(qt_app, pcm, monkeypatch, bounded):
    # Checkpoint audit 8, A8-L5: the first configure has its own deadline (the recovery's one-shot): unanswered, the
    # activation runs in process (worker disabled for the run), its identity bound and its runtime running.
    # Negative control (no deadline: the pre-fix owner, which waited for the heartbeat, twice, or for ever): the owner
    # stays on the unanswering worker with its render binding deferred, nothing presented.
    from widgets.spotify_visualizer import engine_worker_link
    from widgets.spotify_visualizer import quick_display_visualizer_owner as owner_module

    monkeypatch.setattr(owner_module, "_ACTIVATION_TRANSACTION_DEADLINE_MS", 500)
    if not bounded:
        monkeypatch.setattr(owner_module.QuickDisplayVisualizerOwner, "_arm_first_configure_deadline",
                            lambda self, link: None)
    # The rig settles on the configure's reply; this worker never gives one, so it settles for a bounded 1.5 s.
    monkeypatch.setattr(gate.OwnerRig, "settle", lambda self: gate._event_loop_for(
        self.app, 1.5, until=lambda: self.owner is not None and self.owner._worker is None))
    stand_in = _HungSupervisor()
    rig = gate.OwnerRig("spectrum", worker=True, supervisor=stand_in, cadence="thread")
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            if bounded:
                with pytest.raises(RuntimeError, match="fell back in process"):
                    rig.build()
            else:
                rig.build()
        owner = rig.owner
        if not bounded:
            assert owner._worker is not None and not owner._worker.configured
            assert owner._bind_deferred and owner.render_identity is None
            return
        assert owner._worker is None and engine_worker_link.worker_disabled_for_run()
        engine = owner.controller.engine
        identity = owner.render_identity
        assert (identity.engine_generation, identity.activation_id) == (engine.get_generation_id(),
                                                                        engine.get_activation_id())
        assert owner.controller.logical_runtime is not None and owner.controller.logical_runtime.is_running()
    finally:
        rig.close()
        stand_in.close()


@pytest.mark.qt
@pytest.mark.parametrize("mode,target", (("oscilloscope", "bubble"), ("spectrum", "sphere")))
def test_a_paused_switch_on_the_worker_reveals_as_in_process(qt_app, mode, target):
    # A7-L6: a mode switch while Media is paused: the worker path's reveal predicate (the target's newest presentable
    # frame) and the in-process one (the tick state's fresh-frame fence) reveal on the same frame, and the frames
    # are identical. A non-Spectrum target reveals paused idle; a switch out of Spectrum into a 3D mode.
    import tools.expanded_visualizer_evidence as evidence
    from core.process.supervisor import ProcessSupervisor
    from core.process.types import WorkerType
    from core.visualizer_engine.engine_worker import visualizer_worker_main

    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    try:
        assert supervisor.start(WorkerType.VISUALIZER)
        script = gate.identity_script_paused_switch(evidence.shipped_clip(5.5).frames, target)
        worker = gate.identity_run(mode, script, worker=True, supervisor=supervisor)
        in_process = gate.identity_run(mode, script, worker=False, namespace=worker["namespace"])
    finally:
        supervisor.shutdown()
    reveal = [index for index, (phase, fade) in enumerate(worker["phases"]) if phase == "fading_in"]
    assert worker["final_mode"] == in_process["final_mode"] == target and worker["on_worker"]
    assert reveal and worker["phases"] == in_process["phases"], (reveal[:3], next(
        (i for i, (a, b) in enumerate(zip(worker["phases"], in_process["phases"])) if a != b), None))
    assert worker["digests"] == in_process["digests"]
