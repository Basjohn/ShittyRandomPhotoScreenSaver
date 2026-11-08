"""Native core P2b, work order 5 slice 5.1: worker-paced ticks.

A ``cadence="worker"`` live session ticks on its own clock: the logical runtime's cadence (``VisualizerLogicalRuntime``,
started through ``logical_edges.start_logical_cadence``, the owner's own start), fed the shipped clip's PCM on the
audio clock at the cadence's edges (``recorded_capture.PacedPcmSource``: no thread, no timer, no poll), its frames
reaching the reader through the mailbox and the wake pipe. The reader takes on its wakes and stalls after each take (a
slow GUI): the worker keeps its cadence, the reader coalesces (latest wins), the newest frame is never stranded,
nothing is torn. Not frame identity (the commits race the tick, as live); the recorded-input gates keep their
deterministic input-driven mode."""
import numpy as np
import pytest

from core.visualizer_engine.engine_worker import EngineSession
from core.visualizer_engine.packet_mailbox import PacketMailbox
from core.visualizer_engine.recorded_capture import PacedPcmSource
from tools.visualizer_replay import live_engine_gate as gate

SECONDS = 1.5


def _modes():
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    return tuple(d.mode_id for d in iter_all_visualizer_mode_descriptors())


@pytest.fixture(autouse=True)
def _no_audio_device(monkeypatch):
    def _device(_config=None):
        raise AssertionError("the paced rig opened an audio device")

    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", _device)
    monkeypatch.setattr(EngineSession, "LIVE_EDGE_TIMEOUT_S", 10.0)


@pytest.fixture(scope="module")
def pcm():
    return gate.paced_pcm(3.0)


def test_the_paced_source_hands_over_the_audio_clock_in_device_blocks():
    # Edges at irregular times (a late edge catches up with several blocks): the blocks are the stream in order,
    # wrapping at its end, and their total is the audio clock's whole blocks (the remainder carried); a reopen
    # (rebase) and a closed or paused stretch deliver nothing for their gap and hold the playhead.
    rate, block = 48_000, 256
    stream = np.arange(10_000, dtype=np.float32)
    source = PacedPcmSource(stream, rate)
    assert source.due(1.0, block, running=True) == []                 # the first edge starts the clock
    edges = [1.011, 1.022, 1.060, 1.071, 1.082, 1.120, 1.200]
    delivered = []
    for now in edges:
        delivered.extend(source.due(now, block, running=True))
    assert all(len(piece) == block for piece in delivered)
    assert len(delivered) == int((edges[-1] - 1.0) * rate // block)
    joined = np.concatenate(delivered)
    assert np.array_equal(joined, np.take(stream, np.arange(len(joined)), mode="wrap"))
    assert source.most_blocks >= int(0.08 * rate // block)          # the late 1.120 -> 1.200 edge catches up
    assert source.dropped_samples == 0                              # within a device's buffer: nothing dropped
    cursor = source.delivered_samples
    assert source.due(2.0, block, running=False) == []                # closed or paused: nothing, playhead held
    source.rebase()
    assert source.due(5.0, block, running=True) == []                 # reopened: the closed gap is not delivered
    after = source.due(5.011, block, running=True)
    assert np.array_equal(np.concatenate(after), np.take(stream, np.arange(cursor, cursor + len(after) * block),
                                                         mode="wrap"))


def test_one_edge_never_delivers_more_than_a_devices_buffer():
    # A6-L1: a stream left open across a long gap (a minute's park with no reopen, the audit's probe) hands over at
    # most a device's buffer at the next edge; the older audio overflowed (dropped, the playhead moved past it), as a
    # device drops it. The pre-fix source handed over the whole gap in one edge (unbounded: an overnight park would
    # allocate gigabytes on the cadence thread).
    rate, block = 48_000, 256
    stream = np.arange(10_000, dtype=np.float32)
    source = PacedPcmSource(stream, rate)
    source.due(1.0, block, running=True)
    burst = source.due(61.0, block, running=True)
    assert 0 < len(burst) * block <= PacedPcmSource.MAX_BACKLOG_S * rate
    gap = 60 * rate
    assert source.dropped_samples + source.delivered_samples <= gap < source.dropped_samples + source.delivered_samples + 2 * block
    cursor = source.dropped_samples % len(stream)                   # the playhead moved past the overflowed audio
    assert np.array_equal(burst[0], np.take(stream, np.arange(cursor, cursor + block), mode="wrap"))


def test_a_capture_open_restarts_the_clock_before_its_stream_can_deliver():
    # A6-L1 (the audit's probe a): a cadence edge that lands anywhere inside ``RecordedCaptureBackend.start`` (an
    # unpark's capture reopen on its lane while the cadence already runs) after a long park delivers nothing for the
    # parked gap: the clock restarts before the callback is installed, so the edge sees a closed stream or the
    # restarted clock. Pre-fix the callback was installed first and an edge between the two took the whole gap.
    from core.visualizer_engine.recorded_capture import RecordedCaptureBackend
    from utils.audio_capture import AudioCaptureConfig

    rate, block = 48_000, 256
    source = PacedPcmSource(np.arange(10_000, dtype=np.float32), rate)
    source.due(1.0, block, running=True)
    source.due(1.011, block, running=True)                         # the clock runs on the pre-park edges
    before = source.delivered_samples
    landed = []

    def edge() -> None:                                              # a cadence step 60 s later, inside ``start``
        landed.extend(source.due(61.011 + 0.001 * len(landed), block, running=backend.is_running()))

    def on_started(_backend) -> None:
        edge()
        source.rebase()
        edge()

    backend = RecordedCaptureBackend(AudioCaptureConfig(sample_rate=rate, block_size=block), on_started=on_started)
    note = backend._note_capture_starting

    def starting() -> None:                                          # after the callback is installed
        edge()
        note()

    backend._note_capture_starting = starting
    assert backend.start(lambda _samples: None)
    assert landed == [] and source.delivered_samples == before and source.dropped_samples == 0


def test_a_worker_paced_session_is_validated_and_starts_only_explicitly(pcm):
    samples, rate = pcm
    reader = PacketMailbox(role="reader")
    try:
        for bad in ({"inputs": "feature", "order": "free"}, {"inputs": "live", "order": "production"}):
            with pytest.raises(ValueError):
                EngineSession(mapping=reader.mapping_name, mode="spectrum", runtime_generation=1, cadence="worker",
                              pcm=samples, pcm_rate=rate, **bad)
        with pytest.raises(ValueError):
            EngineSession(mapping=reader.mapping_name, mode="spectrum", runtime_generation=1, inputs="live",
                          order="free", pcm=samples, pcm_rate=rate)          # PCM without the worker cadence
    finally:
        reader.close()


@pytest.mark.qt
def test_a_worker_paced_session_ticks_on_its_own_cadence(qt_app, pcm):
    verdict = gate.paced_in_process(*pcm, "spectrum", seconds=SECONDS)
    assert verdict["paced_ok"], verdict
    assert verdict["published"] == verdict["steps"] and verdict["taken"] < verdict["published"]
    assert verdict["torn_reads"] == 0 and not verdict["stranded"] and verdict["step_failures"] == 0
    # A6-L6: the cadence within 5% of the authored rate; latest wins on every take after a stall.
    assert verdict["cadence_ok"] and verdict["latest_checks"] > 0 and not verdict["stale_takes"]
    # A6-M1: the audio reached the engine: every offered block published by the capture callback, analyses
    # committed, frames with energy.
    engine = verdict["engine"]
    assert engine["accepted_blocks"] == engine["offered_blocks"] > 0 and verdict["accepted_over_paced"] >= 0.97
    assert engine["analysis_commits"] >= gate.PACED_MIN_COMMITS_PER_STEP * verdict["steps"]
    assert verdict["energetic_share"] >= gate.PACED_MIN_ENERGETIC


@pytest.mark.qt
def test_a_writer_held_by_its_reader_fails_the_cadence_check(qt_app, pcm, monkeypatch):
    # Negative control: a writer that waits out the reader's stall at every publish (a reader that blocks the worker)
    # drops the cadence to the reader's rate and fails the gate.
    import threading

    publish = PacketMailbox.publish

    def held(self, state, **kwargs):
        if self._reader is None:                           # the session's writer side only
            threading.Event().wait(gate.PACED_STALL_S)
        return publish(self, state, **kwargs)

    monkeypatch.setattr(PacketMailbox, "publish", held)
    verdict = gate.paced_in_process(*pcm, "spectrum", seconds=SECONDS)
    assert not verdict["paced_ok"] and not verdict["cadence_ok"], verdict
    assert verdict["published_hz"] < 0.6 * verdict["authored_hz"], verdict


@pytest.mark.qt
def test_a_cadence_ten_percent_slow_fails_the_rate_check(qt_app, pcm, monkeypatch):
    # A6-L6's negative control: a cadence ~11% slow (every step takes 12% longer than the interval: ~80 Hz of 90)
    # passed the old 60% floor; the 5% tolerance fails it.
    import threading
    import time

    step = EngineSession._paced_step

    def slow(self, now):
        step(self, now)
        threading.Event().wait(max(0.0, 1.0 / 90.0 * 1.12 - (time.perf_counter() - now)))

    monkeypatch.setattr(EngineSession, "_paced_step", slow)
    verdict = gate.paced_in_process(*pcm, "spectrum", seconds=SECONDS)
    assert verdict["cadence_hz"] >= 0.6 * verdict["authored_hz"], verdict          # the old floor passes it
    assert not verdict["cadence_ok"] and not verdict["paced_ok"], verdict


@pytest.mark.qt
def test_a_reader_that_takes_the_oldest_unread_frame_fails_the_latest_wins_check(qt_app, pcm, monkeypatch):
    # A6-L6's negative control: a reader that takes the oldest frame it has not read (FIFO over the ABI's slots, not
    # the newest) still coalesces (taken < published) and is never stranded, but fails the latest-wins check.
    import math
    import struct

    from core.visualizer_engine import packet_abi as abi

    def oldest_unread(self):
        # ``read_latest``'s seqlock read, aimed at the oldest whole slot newer than the last accepted one.
        view, size_of = self._view, self._slot_bytes
        bases = [abi.HEADER_BYTES + slot * size_of for slot in range(abi.SLOT_COUNT)]
        unread = sorted((struct.unpack_from("<Q", view, base)[0], base) for base in bases)
        unread = [(sequence, base) for sequence, base in unread if sequence > self.accepted and sequence % 2 == 0]
        if not unread:
            return None
        target, base = unread[0]
        end = struct.unpack_from("<Q", view, base + size_of - 8)[0]
        head, size, schema, logical, source, flags, edges, *identity = abi._SLOT_HEAD.unpack_from(view, base)
        payload = bytes(view[base + abi.SLOT_PAYLOAD_OFFSET:
                             base + abi.SLOT_PAYLOAD_OFFSET + min(size, size_of - abi.SLOT_OVERHEAD)])
        if end != target or head != target or struct.unpack_from("<Q", view, base)[0] != target:
            self.torn_reads += 1
            return None
        self.accepted = target
        return abi.FramePacket(target, schema, logical, None if math.isnan(source) else source, flags, edges, payload,
                               *identity)

    monkeypatch.setattr(abi.FramePacketReader, "read_latest", oldest_unread)
    verdict = gate.paced_in_process(*pcm, "spectrum", seconds=SECONDS)
    assert verdict["taken"] < verdict["published"] and verdict["stale_takes"], verdict
    assert not verdict["paced_ok"], verdict


@pytest.mark.qt
def test_audio_paced_one_block_per_edge_fails_the_audio_clock_check(qt_app, pcm, monkeypatch):
    # Negative control: a source that hands over one block per cadence edge (paced by the tick, not the audio clock)
    # delivers less audio than the clock produced and fails the gate.
    due = PacedPcmSource.due

    def one_per_edge(self, now, block, *, running):
        blocks = due(self, now, block, running=running)
        self.delivered_samples -= max(0, len(blocks) - 1) * int(block)
        return blocks[:1]

    monkeypatch.setattr(PacedPcmSource, "due", one_per_edge)
    verdict = gate.paced_in_process(*pcm, "spectrum", seconds=SECONDS)
    assert not verdict["paced_ok"] and verdict["delivered_over_paced"] < 0.97, verdict


@pytest.mark.qt
def test_a_capture_callback_that_drops_every_block_fails_the_engine_audio_check(qt_app, pcm, monkeypatch):
    # A6-M1's negative control (the audit's probe b): ``offer`` replaced by a stub that reports every block delivered
    # but never calls the capture callback. The source's own arithmetic still says the audio was delivered on the
    # clock (the old check passed it); the engine never received it, and the gate now fails.
    from core.visualizer_engine.recorded_capture import RecordedCaptureBackend

    monkeypatch.setattr(RecordedCaptureBackend, "offer", lambda self, block: True)
    verdict = gate.paced_in_process(*pcm, "spectrum", seconds=SECONDS)
    assert verdict["delivered_over_paced"] >= 0.97, verdict                     # what the old gate read
    assert verdict["engine"]["accepted_blocks"] == 0 and verdict["accepted_over_paced"] == 0.0, verdict
    assert not verdict["audio_ok"] and not verdict["paced_ok"], verdict


@pytest.mark.qt
def test_the_cadence_parks_with_the_display_and_resumes_without_an_audio_burst(qt_app, pcm):
    # Display power mid-run: the cadence parks (no frame published while parked), capture closes and reopens, and the
    # reopened source delivers nothing for the parked gap; after the unpark the cadence runs at its rate (A6-L6).
    import threading

    seen = {}

    def park_for_a_while(session):
        assert session.set_display_power(False)
        seen["parked_revision"] = session.mailbox.revision
        threading.Event().wait(0.4)
        seen["still_parked_revision"] = session.mailbox.revision
        assert session.set_display_power(True)

    verdict = gate.paced_in_process(*pcm, "oscilloscope", seconds=SECONDS, between=park_for_a_while)
    assert seen["parked_revision"] == seen["still_parked_revision"]
    assert verdict["step_failures"] == 0 and verdict["published"] > seen["parked_revision"]
    assert verdict["torn_reads"] == 0 and not verdict["stranded"] and not verdict["stale_takes"]
    assert verdict["audio"]["paced_s"] <= verdict["seconds"] - 0.35          # the parked gap is not paced audio
    assert verdict["delivered_over_paced"] >= 0.97 and verdict["audio"]["dropped_s"] == 0.0
    assert verdict["capture"][0] >= 2 or verdict["capture"][1] >= 1          # capture reopened after the park
    assert verdict["cadence_ok"], verdict                                     # its rate over the unparked time


@pytest.mark.qt
def test_a_mode_switch_restarts_the_cadence_on_the_new_activation(qt_app, pcm):
    seen = {}

    def switch(session):
        seen["before"] = session.mailbox.revision
        session.request_mode("bubble")
        seen["mode"] = session.mode

    verdict = gate.paced_in_process(*pcm, "spectrum", seconds=SECONDS, between=switch)
    assert seen["mode"] == "bubble" and verdict["step_failures"] == 0
    assert verdict["published"] > seen["before"] and not verdict["stranded"] and verdict["torn_reads"] == 0
    # The restarted runtime (the new activation's) runs at the cadence (A6-L6), and capture fed the engine after it.
    assert verdict["cadence_ok"] and verdict["steps"] > 0, verdict
    assert verdict["engine"]["accepted_blocks"] == verdict["engine"]["offered_blocks"] > 0


def _fail_once(monkeypatch, at: int):
    """``logical_tick`` raising once, at its ``at``-th call (the cadence's step), then ticking again."""
    from widgets.spotify_visualizer import tick_pipeline

    tick, calls = tick_pipeline.logical_tick, [0]

    def failing(state):
        calls[0] += 1
        if calls[0] == at:
            raise RuntimeError("injected tick failure")
        return tick(state)

    monkeypatch.setattr(tick_pipeline, "logical_tick", failing)
    return calls


class _RuntimeLog:
    """``logical_runtime``'s logger, recording errors (the cadence owner's failure log)."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    def error(self, message, *args, **_kwargs):
        self.errors.append(message % args if args else message)

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


@pytest.mark.qt
def test_a_step_that_raises_once_is_logged_and_the_next_step_publishes_in_process_and_in_the_session(
        qt_app, pcm, monkeypatch):
    # A6-M3 (decided by the lead): a step failure behaves as in process. The owner's cadence
    # (``_start_logical_runtime``: ``start_logical_cadence`` with the default step) and the worker session's cadence
    # (its paced step) both leave the failure to ``VisualizerLogicalRuntime``: logged once, counted, and the next
    # step retries and publishes.
    import threading

    from widgets.spotify_visualizer import logical_runtime
    from widgets.spotify_visualizer.feature_replay import configure_offline_controller
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from tools.visualizer_replay.engine import ReplayBeatEngine

    log = _RuntimeLog()
    monkeypatch.setattr(logical_runtime, "logger", log)
    raised = "Logical step raised; cadence continues"

    # In process: the production owner's cadence start on an offline-configured controller.
    calls = _fail_once(monkeypatch, 5)
    engine = ReplayBeatEngine(32)
    controller = VisualizerRuntimeController(runtime_generation=1, initial_mode="spectrum",
                                             engine_factory=lambda _count: engine)
    controller.engine = engine
    configure_offline_controller(controller, "spectrum")
    owner = QuickDisplayVisualizerOwner.__new__(QuickDisplayVisualizerOwner)
    owner._controller = controller
    reached, revisions = threading.Event(), []

    def on_wake():
        publication = controller.logical_mailbox.take()
        if publication is not None:
            revisions.append(publication.revision)
            if publication.revision >= 12:
                reached.set()

    controller.logical_mailbox.set_wake_callback(on_wake)
    owner._start_logical_runtime()
    try:
        assert reached.wait(5.0)
    finally:
        runtime = controller.logical_runtime
        assert controller.stop_logical_runtime()
    in_process = runtime.describe()
    assert in_process["step_failures"] == 1 and calls[0] > 5 and max(revisions) >= 12
    assert sum(raised in message for message in log.errors) == 1

    # The worker session: the same, on its own cadence.
    log.errors.clear()
    calls = _fail_once(monkeypatch, 20)
    verdict = gate.paced_in_process(*pcm, "spectrum", seconds=0.6)
    assert verdict["step_failures"] == 1 and calls[0] > 21, verdict
    assert verdict["published"] == verdict["steps"] - 1 > 20 and not verdict["stranded"], verdict
    assert sum(raised in message for message in log.errors) == 1


@pytest.mark.qt
def test_the_pre_fix_catch_and_freeze_step_fails_the_retry_contract(qt_app, pcm, monkeypatch):
    # A6-M3's negative control: the 5.1 step that caught its own failure and froze the session (nothing logged,
    # ``step_failures`` 0, nothing published after it) fails the contract the test above pins.
    step, frozen = EngineSession._paced_step, {}

    def catch_and_freeze(self, now):
        if frozen.get(id(self)):
            return
        try:
            step(self, now)
        except Exception:
            frozen[id(self)] = True

    monkeypatch.setattr(EngineSession, "_paced_step", catch_and_freeze)
    calls = _fail_once(monkeypatch, 20)
    verdict = gate.paced_in_process(*pcm, "spectrum", seconds=0.6)
    assert calls[0] == 20 and verdict["step_failures"] == 0 and verdict["published"] == 19, verdict


def _paced_worker(reader, pcm):
    """A ``VisualizerEngineWorker`` (in this process) with a started worker-paced session on ``reader``."""
    from core.process.types import MessageType, WorkerMessage
    from core.visualizer_engine.engine_worker import VisualizerEngineWorker

    worker, serial = VisualizerEngineWorker(None, None), [0]

    def send(kind, **payload):
        serial[0] += 1
        return worker.handle_message(WorkerMessage(msg_type=kind, seq_no=serial[0], correlation_id=str(serial[0]),
                                                   payload=payload))

    samples, rate = pcm
    configured = send(MessageType.VIS_CONFIGURE, mapping=reader.mapping_name, mode="spectrum", runtime_generation=1,
                      inputs="live", order="free", cadence="worker", pcm=samples, pcm_rate=rate)
    assert configured.success, configured.error
    assert send(MessageType.VIS_START, playing=True).success
    return worker, send


def _close_left_open(worker, monkeypatch) -> None:
    """A session the code under test left open (pre-fix: its cadence thread still running) is closed here, so a
    failing test fails rather than hanging the run on a non-daemon thread."""
    if worker is not None and worker._session is not None:
        monkeypatch.undo()
        worker._close_session()


@pytest.mark.qt
def test_a_failed_paced_mode_switch_closes_the_session_and_releases_capture(qt_app, pcm, monkeypatch):
    # A6-M2: a worker-paced mode switch applies at once; one that raises after the runtime stopped (here inside the
    # activation commit) may have half-applied, so VIS_SET_MODE closes the session with ``session_closed`` (capture
    # released), as VIS_INPUT does. Negative control: a refused request (an unknown mode) leaves the session as it was.
    from core.process.types import MessageType
    from widgets.spotify_visualizer import logical_edges

    reader, worker = PacketMailbox(role="reader"), None
    try:
        worker, send = _paced_worker(reader, pcm)
        session = worker._session
        refused = send(MessageType.VIS_SET_MODE, mode="not_a_mode")
        assert not refused.success and not refused.payload.get("session_closed") and worker._session is session
        commit = logical_edges.commit_logical_activation

        def failing_commit(controller, **kwargs):
            assert controller.stop_logical_runtime()          # the runtime stopped: the switch has half-applied
            raise RuntimeError("injected activation failure")

        monkeypatch.setattr(logical_edges, "commit_logical_activation", failing_commit)
        backend = session._backend
        assert backend is not None and backend.is_running()
        failed = send(MessageType.VIS_SET_MODE, mode="bubble")
        assert not failed.success and failed.payload.get("session_closed") is True, failed
        assert "injected activation failure" in failed.error
        assert worker._session is None and not backend.is_running()            # capture released with the session
        assert not send(MessageType.VIS_START, playing=True).success            # nothing left to drive
        monkeypatch.setattr(logical_edges, "commit_logical_activation", commit)
    finally:
        _close_left_open(worker, monkeypatch)
        reader.close()


@pytest.mark.qt
def test_vis_stop_closes_the_session_even_when_finish_raises(qt_app, pcm, monkeypatch):
    # A6-L7: an unjoined cadence makes ``finish`` raise; VIS_STOP still closes the session (capture, compute lane and
    # mapping released) and says so.
    from core.process.types import MessageType

    reader, worker = PacketMailbox(role="reader"), None
    try:
        worker, send = _paced_worker(reader, pcm)
        session = worker._session
        backend, runtime = session._backend, session._controller.logical_runtime
        assert runtime is not None and runtime.is_running()
        stop, calls = EngineSession._stop_cadence, [0]

        def unjoined_once(self):
            calls[0] += 1
            if calls[0] == 1:
                raise RuntimeError("the session's cadence did not join")
            return stop(self)

        monkeypatch.setattr(EngineSession, "_stop_cadence", unjoined_once)
        stopped = send(MessageType.VIS_STOP)
        assert not stopped.success and stopped.payload.get("session_closed") is True, stopped
        assert "did not join" in stopped.error
        # The close unwound everything the session held: its cadence (the stack's own stop), capture, the mapping.
        assert worker._session is None and not backend.is_running() and calls[0] == 1
        assert not runtime.is_running()
    finally:
        _close_left_open(worker, monkeypatch)
        reader.close()


@pytest.mark.qt
def test_a_worker_paced_session_in_the_worker_process_for_every_mode(qt_app, pcm):
    # The gate across processes, every mode: the worker's own cadence, frames through the mapping and the wake pipe
    # to a stalling reader.
    from core.process.supervisor import ProcessSupervisor
    from core.process.types import WorkerType
    from core.visualizer_engine.engine_worker import visualizer_worker_main

    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    assert supervisor.start(WorkerType.VISUALIZER)
    try:
        failing = {}
        for mode in _modes():
            verdict = gate.paced_in_worker(supervisor, *pcm, mode, seconds=SECONDS)
            if not verdict["paced_ok"]:
                failing[mode] = verdict
        assert not failing, failing
    finally:
        supervisor.shutdown()
