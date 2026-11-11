"""Native core P2 phase-boundary audit, L4: liveness of the engine worker's frame stream itself.

A worker whose message loop answers the supervisor's heartbeat while its session's cadence thread is blocked inside a
step (a lock, a native call) published nothing and was seen by nobody: the Visualizer stayed frozen on its last frame
for the run, with nothing in the main log. The session is asked at each heartbeat the worker already answers
(``EngineSession.watch_cadence_liveness``: no timer, thread or polling of its own) and fails closed after
``STALLED_HEARTBEATS_BEFORE_CLOSE`` spaced heartbeats without a step, which the owner sees as the session's end (its
wake pipe) and recovers from as from any failed session.

The unit tests drive the watch on a real ``VisualizerLogicalRuntime`` with the heartbeat times in the test's hands; the
owner test runs the REAL owner (the host binding's, on an unshown runtime; recorded PCM, no device, no window) against
the same ``VisualizerEngineWorker`` in this process behind the supervisor stand-in.
"""
from __future__ import annotations

import threading
import time
import types

import pytest

from tests.test_visualizer_owner_engine_worker import _InProcessSupervisor, _Log, _pump
from tools.visualizer_replay import owner_worker_gate as gate


class _Cadence:
    """A real logical runtime whose step the test can block (as a lock or a native call would) and release."""

    def __init__(self) -> None:
        from widgets.spotify_visualizer.logical_runtime import VisualizerLogicalRuntime

        self._free = threading.Event()
        self._free.set()
        self._blocked = threading.Event()
        self.runtime = VisualizerLogicalRuntime(step=self._step, interval_s=0.002, generation=1,
                                                name="test-engine-cadence")
        assert self.runtime.start()

    def _step(self, _now: float) -> None:
        if not self._free.is_set():
            self._blocked.set()
            self._free.wait(30.0)

    def block(self) -> None:
        """Block the next step, after one more finished step (so the blocked step is a new sighting for a watch that
        already observed this runtime)."""
        self.stepped()
        self._blocked.clear()
        self._free.clear()
        assert self._blocked.wait(5.0)

    def release(self) -> None:
        self._free.set()

    def stepped(self) -> None:
        """Wait for at least one more finished step."""
        before, deadline = self.runtime.steps, time.perf_counter() + 5.0
        while self.runtime.steps == before:
            assert time.perf_counter() < deadline
            time.sleep(0.002)

    def close(self) -> None:
        self._free.set()
        assert self.runtime.stop()


def _session(runtime, *, paced: bool = True):
    """An ``EngineSession`` holding only what the watch and ``_fail_closed`` read (the runtime, the wake pipe)."""
    from core.visualizer_engine.engine_worker import EngineSession

    session = EngineSession.__new__(EngineSession)
    session._paced = paced
    session._controller = types.SimpleNamespace(logical_runtime=runtime)
    closed: list = []
    session.mailbox = types.SimpleNamespace(close_wake_sender=lambda: closed.append(True))
    return session, closed


@pytest.fixture
def cadence():
    cadence = _Cadence()
    yield cadence
    cadence.close()


def _beats(session) -> tuple[float, float]:
    """A heartbeat interval well past the watch's minimum spacing, and a gap well inside it."""
    return 3.0 * session.STALL_OBSERVATION_MIN_S, 0.1 * session.STALL_OBSERVATION_MIN_S


def test_a_blocked_cadence_fails_the_session_closed_after_spaced_heartbeats_only(cadence):
    session, closed = _session(cadence.runtime)
    beat, close_gap = _beats(session)
    cadence.block()
    assert not session.watch_cadence_liveness(now=0.0)                 # the sighting: nothing to compare with yet
    # Heartbeats that queued behind a long control edge are handled together: however many, one observation.
    for n in range(1, 20):
        assert not session.watch_cadence_liveness(now=n * close_gap / 20.0)
    assert session.failed is None and not closed
    now, results = 0.0, []
    for _ in range(session.STALLED_HEARTBEATS_BEFORE_CLOSE):
        now += beat
        results.append(session.watch_cadence_liveness(now=now))
        assert not session.watch_cadence_liveness(now=now + close_gap)  # its queued twin adds nothing
    assert results == [False] * (session.STALLED_HEARTBEATS_BEFORE_CLOSE - 1) + [True], results
    assert session.failed is not None and "no step" in session.failed
    assert closed == [True] and cadence.runtime.park_requested          # the owner's event, and the cadence parks
    assert not session.watch_cadence_liveness(now=now + beat) and closed == [True]   # failed once


def test_a_cadence_that_steps_between_heartbeats_starts_the_count_again(cadence):
    session, closed = _session(cadence.runtime)
    beat, _gap = _beats(session)
    now = 0.0
    for _ in range(3 * session.STALLED_HEARTBEATS_BEFORE_CLOSE):        # free running: never a stalled observation
        cadence.stepped()
        now += beat
        assert not session.watch_cadence_liveness(now=now)
    cadence.block()
    assert not session.watch_cadence_liveness(now=now + beat)           # sighting of the blocked step
    for n in range(session.STALLED_HEARTBEATS_BEFORE_CLOSE - 1):        # one short of the limit
        assert not session.watch_cadence_liveness(now=now + (n + 2) * beat)
    cadence.release()                                                   # a slow step, not a dead one
    cadence.stepped()
    now += (session.STALLED_HEARTBEATS_BEFORE_CLOSE + 2) * beat
    assert not session.watch_cadence_liveness(now=now)
    assert session.failed is None and not closed
    cadence.block()
    assert not session.watch_cadence_liveness(now=now + beat)
    fired = [session.watch_cadence_liveness(now=now + (n + 2) * beat)
             for n in range(session.STALLED_HEARTBEATS_BEFORE_CLOSE)]
    assert fired[-1] and not any(fired[:-1]) and closed == [True]


def test_a_parked_or_stopped_cadence_and_an_input_paced_session_are_never_failed(cadence):
    session, closed = _session(cadence.runtime)
    beat, _gap = _beats(session)
    assert cadence.runtime.park()                                       # display power off: parked, no step by design
    for n in range(4 * session.STALLED_HEARTBEATS_BEFORE_CLOSE):
        assert not session.watch_cadence_liveness(now=n * beat)
    assert cadence.runtime.unpark()
    cadence.stepped()
    assert cadence.runtime.stop()                                       # an activation commit: stopped and joined
    for n in range(4 * session.STALLED_HEARTBEATS_BEFORE_CLOSE):
        assert not session.watch_cadence_liveness(now=100.0 + n * beat)
    assert cadence.runtime.start()
    cadence.block()
    input_paced, input_closed = _session(cadence.runtime, paced=False)  # one tick per input: no cadence of its own
    no_runtime, _closed = _session(None)
    for n in range(4 * session.STALLED_HEARTBEATS_BEFORE_CLOSE):
        assert not input_paced.watch_cadence_liveness(now=n * beat)
        assert not no_runtime.watch_cadence_liveness(now=n * beat)
    assert session.failed is None and input_paced.failed is None and not closed and not input_closed


def test_a_park_that_waits_behind_a_blocked_step_is_still_watched(cadence):
    # Display power goes off while the step is blocked: the park is requested and never reached. Parked-by-request is
    # not parked: the watch goes on, or a blocked session would hide behind every display-off edge.
    session, closed = _session(cadence.runtime)
    beat, _gap = _beats(session)
    cadence.block()
    cadence.runtime.request_park()
    assert not cadence.runtime.is_parked()
    fired = [session.watch_cadence_liveness(now=n * beat)
             for n in range(session.STALLED_HEARTBEATS_BEFORE_CLOSE + 1)]
    assert fired[-1] and not any(fired[:-1]) and closed == [True]


@pytest.fixture
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


@pytest.mark.qt
@pytest.mark.parametrize("watched", (True, False))
def test_a_blocked_cadence_thread_is_seen_at_the_workers_heartbeat_and_the_owner_recovers(
        qt_app, monkeypatch, _no_device_and_a_fresh_run, watched):
    # The worker's message loop answers every heartbeat while its cadence thread sits inside one step. With the watch
    # the session fails closed at the heartbeat, the owner sees the session end and reconfigures once, frames flow
    # again, and the main log carries the reason (the stop's reply: the worker's own log never reaches it). Negative
    # control (the heartbeat answered as every worker answers it, as before the fix): every heartbeat is acknowledged,
    # the session never fails and the owner stays on a session that publishes nothing.
    from core.process.types import MessageType, WorkerMessage
    from core.process.workers.base import BaseWorker
    from core.visualizer_engine.engine_worker import EngineSession, VisualizerEngineWorker
    from tools.visualizer_replay.live_engine_gate import paced_pcm
    from widgets.spotify_visualizer import engine_worker_link

    monkeypatch.setattr(EngineSession, "STALL_OBSERVATION_MIN_S", 0.05, raising=False)
    if not watched:
        monkeypatch.setattr(VisualizerEngineWorker, "_handle_heartbeat", BaseWorker._handle_heartbeat)
    log = _Log()
    monkeypatch.setattr(engine_worker_link, "diagnostic_logger", log)
    pcm = paced_pcm(3.0)
    stand_in = _InProcessSupervisor()
    rig = gate.OwnerRig("spectrum", worker=True, supervisor=stand_in, cadence="thread")
    release = threading.Event()
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
        _pump(rig, 0.6)
        first, session = owner._worker, stand_in.worker._session
        assert first is not None and session.mailbox.revision > 0
        acknowledged: list = []
        stand_in.worker._send_response = acknowledged.append
        entered = threading.Event()

        def blocked_step(_now: float) -> None:
            entered.set()
            release.wait(60.0)

        session._paced_step_body = blocked_step
        assert entered.wait(5.0)
        frozen_at = session.mailbox.revision
        beats = 6
        for n in range(beats):
            stand_in.worker._handle_heartbeat(WorkerMessage(msg_type=MessageType.HEARTBEAT, seq_no=n,
                                                            correlation_id=f"beat-{n}"))
            time.sleep(0.08)
        assert [ack.msg_type for ack in acknowledged] == [MessageType.HEARTBEAT_ACK] * beats
        assert session.mailbox.revision == frozen_at                    # the frame stream stood still throughout
        assert (session.failed is not None) is watched, session.failed
        if not watched:
            _pump(rig, 1.0)
            assert owner._worker is first and session.mailbox.revision == frozen_at
            return
        assert "no step" in session.failed
        _pump(rig, 30.0, until=lambda: owner._worker is not first and owner._worker is not None
              and owner._worker.configured and owner._mode_transition_phase == "idle")
        assert owner._worker is not None and owner._worker is not first
        assert not engine_worker_link.worker_disabled_for_run()
        presented = len(rig.published)
        _pump(rig, 1.0)
        assert len(rig.published) > presented + 20                      # the replacement session's frames
        reported = [message for level, message in log.records if level == "error" and "no step" in message]
        assert reported, log.records                                    # why, in the main process's log
    finally:
        release.set()
        rig.close()
        stand_in.close()
