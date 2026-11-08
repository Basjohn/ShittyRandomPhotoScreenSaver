"""Native core P2b slice 1: the live engine on recorded PCM, in process and in the worker.

``EngineSession(inputs="live")`` runs the production ``_SpotifyBeatEngine`` with its real ``SpotifyVisualizerAudioWorker``,
capture lane and compute pool (its own ``ThreadManager``), fed each recorded frame's native PCM through the worker's
capture callback by ``RecordedCaptureBackend`` (installed through the audio worker's one source seam; no device). Per
input the session pushes the new blocks, steps the engine (which submits the newest block to the compute lane) and
waits for the engine's analysis-settled edge before the tick, so the asynchronous commit path runs and the frames are
deterministic (``order="settled"``, the portability order; slice 2's off-steady-state gates use the production order,
``tests/test_visualizer_engine_live_off_steady.py``). The gate: the same frames in process and in a
``WorkerType.VISUALIZER`` process, for every mode."""
import numpy as np
import pytest

from core.process.supervisor import ProcessSupervisor
from core.process.types import MessageType, WorkerType
from core.visualizer_engine.engine_worker import EngineSession, visualizer_worker_main
from core.visualizer_engine.packet_mailbox import PacketMailbox
from core.visualizer_engine.recorded_capture import CaptureHistoryStream

GENERATION = 9001


def _modes():
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    return tuple(d.mode_id for d in iter_all_visualizer_mode_descriptors())


@pytest.fixture(autouse=True)
def _no_audio_device(monkeypatch):
    # The rig must never reach a device: the device factory raises, so a session that bypassed the recorded source
    # fails here (and fast) instead of opening the machine's loopback.
    def _device(_config=None):
        raise AssertionError("the live-engine rig opened an audio device")

    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", _device)
    monkeypatch.setattr(EngineSession, "LIVE_EDGE_TIMEOUT_S", 10.0)


def _live_session(reader, mode):
    from widgets.spotify_visualizer.feature_replay import REPLAY_SEED

    return EngineSession(mapping=reader.mapping_name, mode=mode, runtime_generation=GENERATION, inputs="live",
                         seed=REPLAY_SEED, order="settled")


def test_the_recorded_stream_rebuilds_every_capture_history_in_device_blocks():
    # Each new publication's samples, cut into device blocks (the newest block whole), concatenate back into a stream
    # whose tail is exactly every frame's recorded history.
    import tools.expanded_visualizer_evidence as evidence

    stream, pushed, block = CaptureHistoryStream(), [], 480
    for feature in evidence.shipped_clip(1.0).frames:
        blocks = stream.blocks(feature.capture_history, feature.timestamp_us, block)
        assert all(len(piece) <= block for piece in blocks)
        if len(blocks) > 1:
            assert len(blocks[-1]) == block
        pushed.extend(blocks)
        history = np.frombuffer(feature.capture_history.pcm_f32le, dtype="<f4")
        joined = np.concatenate(pushed)
        assert np.array_equal(joined[-len(history):], history)


@pytest.mark.qt
def test_recorded_pcm_reaches_the_live_engine_through_its_capture_callback(qt_app):
    # The audio worker opens the recorded backend through its source seam and the worker's own callback mixes the
    # blocks: Oscilloscope's capture history (kept by that callback) is the recording's, sample for sample.
    import tools.expanded_visualizer_evidence as evidence
    from core.visualizer_engine.recorded_capture import RecordedCaptureBackend

    reader = PacketMailbox(role="reader")
    session = _live_session(reader, "oscilloscope")
    try:
        for feature in evidence.shipped_clip(0.3).frames:
            session.tick(feature)
            reader.take()
            recorded = np.frombuffer(feature.capture_history.pcm_f32le, dtype="<f4")
            assert np.array_equal(session._engine.get_waveform_history(), recorded)
        assert isinstance(session._backend, RecordedCaptureBackend)
    finally:
        session.close()
        reader.close()


@pytest.mark.qt
def test_each_tick_reads_the_asynchronous_commit_of_its_own_block(qt_app, monkeypatch):
    # The compute lane commits on its own thread; the session waits for the engine's settled edge, so the tick entered
    # after the commit of the block it was fed: one more authoritative commit per new publication, stamped with this
    # input's clock (the lane read the authored clock while analysing it).
    import threading

    import tools.expanded_visualizer_evidence as evidence
    from widgets.spotify_visualizer import tick_pipeline

    seen = []
    original = tick_pipeline.logical_tick

    def spy(widget):
        engine = widget._engine
        seen.append((engine.get_authoritative_frame_commit_seq(), engine.get_latest_authoritative_frame()[0],
                     threading.current_thread() is threading.main_thread()))
        return original(widget)

    monkeypatch.setattr(tick_pipeline, "logical_tick", spy)
    reader = PacketMailbox(role="reader")
    session = _live_session(reader, "spectrum")
    expected, serial = [], None
    try:
        lanes = set()
        session._engine.set_analysis_settled_observer(
            lambda: (lanes.add(threading.current_thread().name), session._settled.set()))
        for feature in evidence.shipped_clip(0.5).frames:
            session.tick(feature)
            reader.take()
            if feature.capture_history.capture_serial != serial:
                serial = feature.capture_history.capture_serial
                expected.append(feature.timestamp_us / 1e6)
            assert seen[-1][:2] == (len(expected), expected[-1])
        assert all(on_main for _seq, _ts, on_main in seen)
        assert lanes and not any(name == threading.main_thread().name for name in lanes)   # committed off-thread
    finally:
        session.close()
        reader.close()


@pytest.mark.qt
def test_the_seed_reaches_bubble_and_a_process_rng_draw_in_the_tick_diverges(qt_app, monkeypatch):
    # Work order 5 slice 5.6 (checkpoint audit 2, A2-M2): the session's ``seed`` seeds Bubble's own generator through
    # its controller, never the process RNG, so two sessions with the seed tick identical frames, while a tick that
    # drew from the process RNG (here: Bubble's simulation handed the ``random`` module itself) is not seeded by any
    # session and the same comparison fails (with the old process-wide seed it passed).
    import random

    import tools.expanded_visualizer_evidence as evidence
    from widgets.spotify_visualizer import bubble_simulation

    frames = evidence.shipped_clip(0.6).frames

    def digests():
        reader = PacketMailbox(role="reader")
        session = _live_session(reader, "bubble")
        try:
            seen = []
            for feature in frames:
                session.tick(feature)
                seen.append(evidence.frame_digest(reader.take().state))
            return seen
        finally:
            session.close()
            reader.close()

    first = digests()
    assert len(first) > 40 and digests() == first
    real_init = bubble_simulation.BubbleSimulation.__init__

    def process_rng(self, seed=None):
        real_init(self, seed)
        self._rng = random                                    # the module: the process RNG's draws

    monkeypatch.setattr(bubble_simulation.BubbleSimulation, "__init__", process_rng)
    assert digests() != digests()


@pytest.mark.qt
def test_a_tick_that_raises_closes_the_live_session(qt_app, monkeypatch):
    # Fail closed (audit M2; ported from the deleted snapshot input's gate, work order 5 slice 5.6): a tick that raised
    # left its controller half-updated, so the worker ends the session and says so; the next input is refused instead
    # of ticking on.
    import tools.expanded_visualizer_evidence as evidence
    from core.process.types import WorkerMessage
    from core.visualizer_engine.engine_worker import VisualizerEngineWorker
    from widgets.spotify_visualizer import tick_pipeline
    from widgets.spotify_visualizer.feature_replay import REPLAY_SEED

    frames = evidence.shipped_clip(0.2).frames
    worker = VisualizerEngineWorker(None, None)
    reader = PacketMailbox(role="reader")

    def send(kind, payload, seq):
        return worker.handle_message(WorkerMessage(msg_type=kind, seq_no=seq, correlation_id=str(seq), payload=payload))

    try:
        configured = send(MessageType.VIS_CONFIGURE, {"mapping": reader.mapping_name, "mode": "spectrum",
                                                      "runtime_generation": GENERATION, "inputs": "live",
                                                      "seed": REPLAY_SEED, "order": "settled"}, 1)
        assert configured.success, configured.error
        assert send(MessageType.VIS_INPUT, {"frame": frames[0]}, 2).success
        real_tick = tick_pipeline.logical_tick

        def raising(state):
            real_tick(state)
            raise RuntimeError("injected mid-tick failure")

        monkeypatch.setattr(tick_pipeline, "logical_tick", raising)
        failed = send(MessageType.VIS_INPUT, {"frame": frames[1]}, 3)
        assert not failed.success and failed.payload.get("session_closed") is True, failed
        assert worker._session is None
        monkeypatch.setattr(tick_pipeline, "logical_tick", real_tick)
        after = send(MessageType.VIS_INPUT, {"frame": frames[2]}, 4)
        assert not after.success and "no engine session" in after.error
    finally:
        worker._close_session()
        reader.close()


@pytest.mark.qt
def test_the_worker_process_ticks_the_live_engines_frames_for_every_mode(qt_app):
    # The P2b identity gate: the live engine in process equals the live engine in a WorkerType.VISUALIZER process,
    # frame for frame, through the packet ABI.
    import tools.expanded_visualizer_evidence as evidence

    clip = evidence.shipped_clip(1.0)
    expected = {}
    for mode in _modes():
        reader = PacketMailbox(role="reader")
        session = _live_session(reader, mode)
        try:
            digests = []
            for feature in clip.frames:
                session.tick(feature)
                digests.append(evidence.frame_digest(reader.take().state))
        finally:
            session.close()
            reader.close()
        expected[mode] = digests
    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    assert supervisor.start(WorkerType.VISUALIZER)
    from widgets.spotify_visualizer.feature_replay import REPLAY_SEED

    try:
        for mode in _modes():
            reader = PacketMailbox(role="reader")
            try:
                configured = supervisor.send_request_and_await_response(
                    WorkerType.VISUALIZER, MessageType.VIS_CONFIGURE,
                    {"mapping": reader.mapping_name, "mode": mode, "runtime_generation": GENERATION, "inputs": "live",
                     "seed": REPLAY_SEED, "order": "settled"},
                    timeout_ms=60_000)
                assert configured is not None and configured.success, (mode, configured and configured.error)
                seen = []
                for feature in clip.frames:
                    response = supervisor.send_request_and_await_response(
                        WorkerType.VISUALIZER, MessageType.VIS_INPUT, {"frame": feature}, timeout_ms=30_000)
                    assert response is not None and response.success, (mode, response and response.error)
                    seen.append(evidence.frame_digest(reader.take().state))
                stopped = supervisor.send_request_and_await_response(
                    WorkerType.VISUALIZER, MessageType.VIS_STOP, {}, timeout_ms=30_000)
                assert stopped is not None and stopped.success
            finally:
                reader.close()
            assert len(seen) > 60 and seen == expected[mode], mode
    finally:
        supervisor.shutdown()
    assert not supervisor.is_running(WorkerType.VISUALIZER)
