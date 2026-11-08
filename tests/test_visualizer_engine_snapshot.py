"""Native core P2a live inputs: the lossless engine snapshot (core/visualizer_engine/engine_snapshot.py).

The gate: the main process steps its beat engine (production DSP on the clip's native PCM, ``ProductionLaneEngine``)
and captures a snapshot per tick; an engine session ticks from those snapshots through ``SnapshotBeatEngine``. Its
frames, read back through the frame packet ABI, equal the in-process tick on the same
engine for every mode; in a ``WorkerType.VISUALIZER`` process too."""
import pytest

from core.process.supervisor import ProcessSupervisor
from core.process.types import MessageType, WorkerType
from core.visualizer_engine.engine_snapshot import (
    CAPTURED_GETTERS, SPECIAL_READS, EngineSnapshotSource, SnapshotBeatEngine, SnapshotContractError,
)
from core.visualizer_engine.engine_worker import EngineSession, visualizer_worker_main
from core.visualizer_engine.packet_mailbox import PacketMailbox

GENERATION = 9001

from widgets.spotify_visualizer.feature_replay import REPLAY_SEED  # noqa: E402


def _modes():
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    return tuple(d.mode_id for d in iter_all_visualizer_mode_descriptors())


def _reference(frames, mode):
    """The in-process tick on production DSP (what the main process runs today)."""
    from tools.expanded_visualizer_evidence import frame_digest

    reader = PacketMailbox(role="reader")
    session = EngineSession(mapping=reader.mapping_name, mode=mode, runtime_generation=GENERATION, inputs="lanes")
    try:
        digests = []
        for feature in frames:
            session.tick(feature)
            digests.append(frame_digest(reader.take().state))
        return digests
    finally:
        session.close()
        reader.close()


class _MainSide:
    """The main process's half: its configured beat engine, stepped and captured once per tick."""

    def __init__(self, mode):
        from widgets.spotify_visualizer.feature_replay import ProductionLaneEngine, configure_offline_controller
        from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController

        self.engine = engine = ProductionLaneEngine(32)
        controller = VisualizerRuntimeController(runtime_generation=GENERATION, initial_mode=mode,
                                                 engine_factory=lambda _count: engine)
        controller.engine = engine
        configure_offline_controller(controller, mode)          # the engine's DSP config, as the widget applies it
        self.source = EngineSnapshotSource(engine, mode)

    def initial(self):
        return self.source.capture(0.0, playing=True, step=False)

    def step(self, feature, clock):
        clock[0] = feature.timestamp_us / 1_000_000.0
        self.engine.set_playback_state(feature.playing)
        if not self.engine.accept_feature_frame(feature):
            raise ValueError("the engine rejected a post-DSP input")
        return self.source.capture(clock[0], playing=feature.playing)


def _split_in_process(frames, mode):
    from tools.expanded_visualizer_evidence import frame_digest
    from widgets.spotify_visualizer.feature_replay import deterministic_clock

    with deterministic_clock():                                  # the main process's clock
        main = _MainSide(mode)
        reader = PacketMailbox(role="reader")
        session = EngineSession(mapping=reader.mapping_name, mode=mode, runtime_generation=GENERATION,
                                inputs="snapshot", initial_snapshot=main.initial(), seed=REPLAY_SEED)
        try:
            digests = []
            for feature in frames:
                session.tick_snapshot(main.step(feature, session.clock))
                digests.append(frame_digest(reader.take().state))
            return digests
        finally:
            session.close()
            reader.close()


@pytest.mark.qt
@pytest.mark.parametrize("mode", _modes())
def test_the_snapshot_path_ticks_the_in_process_frames(qt_app, mode):
    import tools.expanded_visualizer_evidence as evidence

    frames = evidence.shipped_clip(1.5).frames
    expected = _reference(frames, mode)
    assert len(expected) > 30 and _split_in_process(frames, mode) == expected, mode


@pytest.mark.qt
def test_the_worker_process_ticks_identical_frames_from_snapshots(qt_app):
    import tools.expanded_visualizer_evidence as evidence
    from widgets.spotify_visualizer.feature_replay import deterministic_clock

    frames = evidence.shipped_clip(1.0).frames
    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    assert supervisor.start(WorkerType.VISUALIZER)
    try:
        for mode in _modes():
            expected = _reference(frames, mode)
            reader = PacketMailbox(role="reader")
            try:
                with deterministic_clock() as clock:            # the main process keeps its own clock
                    main = _MainSide(mode)
                    configured = supervisor.send_request_and_await_response(
                        WorkerType.VISUALIZER, MessageType.VIS_CONFIGURE,
                        {"mapping": reader.mapping_name, "mode": mode, "runtime_generation": GENERATION,
                         "inputs": "snapshot", "initial_snapshot": main.initial(), "seed": REPLAY_SEED},
                        timeout_ms=60_000)
                    assert configured is not None and configured.success, (mode, configured and configured.error)
                    seen = []
                    for feature in frames:
                        response = supervisor.send_request_and_await_response(
                            WorkerType.VISUALIZER, MessageType.VIS_INPUT, {"snapshot": main.step(feature, clock)},
                            timeout_ms=30_000)
                        assert response is not None and response.success, (mode, response and response.error)
                        seen.append(evidence.frame_digest(reader.take().state))
                supervisor.send_request_and_await_response(WorkerType.VISUALIZER, MessageType.VIS_STOP, {},
                                                           timeout_ms=30_000)
            finally:
                reader.close()
            assert len(expected) > 20 and seen == expected, mode
    finally:
        supervisor.shutdown()


class _Scheduler:
    def __init__(self):
        self.ops = []

    def feed(self, event):
        self.ops.append(("feed", event))
        return True

    def reset(self):
        self.ops.append(("reset", None))


class _Engine:
    """A minimal engine: every captured getter answers its own name; records the main-side writes."""

    def __init__(self):
        self.scheduler = _Scheduler()
        self.writes = []

    def __getattr__(self, name):
        if name in CAPTURED_GETTERS:
            return lambda: [name]
        raise AttributeError(name)

    def tick(self):
        self.writes.append("tick")

    def get_event_scheduler(self):
        return self.scheduler

    def get_onset_events(self, after_serial=0):
        return ()

    def peek_pre_agc_analysis_spectrum(self):
        return (0.5,)

    def request_pre_agc_analysis_spectrum(self):
        self.writes.append("spectrum")

    def set_waveform_history_demand(self, demanded):
        self.writes.append(("history", demanded))

    def set_idle_waveform_demand(self, demanded):
        self.writes.append(("idle", demanded))


def test_scheduler_feeds_and_resets_replay_in_order_on_the_worker():
    from widgets.spotify_visualizer.transient_bus import OnsetEvent

    engine = _Engine()
    source = EngineSnapshotSource(engine, "bubble")
    worker = SnapshotBeatEngine(source.capture(0.0, playing=True, step=False))
    kick = OnsetEvent(timestamp=1.0, event_type="kick", strength=0.9)
    engine.scheduler.feed(kick)                       # the DSP's feed, through the tap
    engine.scheduler.reset()
    engine.scheduler.feed(OnsetEvent(timestamp=1.05, event_type="kick", strength=0.8))
    snapshot = source.capture(1.1, playing=True)
    assert [op for op, _event in snapshot.scheduler_ops] == ["feed", "reset", "feed"]
    worker.accept_snapshot(snapshot)
    # After the reset the debounce starts over, so the second kick (50 ms later) is accepted.
    event = worker.get_event_scheduler().consume_next("kick", max_age_s=1e9)
    assert event is not None and event.timestamp == 1.05
    assert worker.get_event_scheduler().consume_next("kick", max_age_s=1e9) is None


def test_the_main_side_declares_the_modes_waveform_demands_and_the_tick_must_agree():
    engine = _Engine()
    source = EngineSnapshotSource(engine, "oscilloscope")             # draws samples and reads the spectrum
    worker = SnapshotBeatEngine(source.capture(0.0, playing=True, step=False))
    worker.accept_snapshot(source.capture(0.01, playing=True))
    # Declared before stepping, as the tick does: no tick -> engine write travels back (audit H4).
    assert engine.writes == [("idle", True), ("history", True), "spectrum", "tick"]
    worker.set_idle_waveform_demand(True)
    worker.set_waveform_history_demand(True)
    assert worker.get_pre_agc_analysis_spectrum() == (0.5,)
    with pytest.raises(SnapshotContractError):
        worker.set_waveform_history_demand(False)                     # another mode's rule: never silently diverge


def test_a_read_outside_the_contract_cannot_be_swallowed():
    engine = _Engine()
    source = EngineSnapshotSource(engine, "spectrum")                 # reads no spectrum
    worker = SnapshotBeatEngine(source.capture(0.0, playing=True, step=False))
    assert worker.get_smoothed_bars() == ["get_smoothed_bars"]
    for read in (worker.get_pre_agc_analysis_spectrum, lambda: worker.get_not_captured()):
        try:
            try:
                read()
            except Exception:                                         # the tick's defensive blocks catch this much
                pytest.fail("a contract miss was swallowed by except Exception (audit H3)")
        except SnapshotContractError:
            pass
        else:
            pytest.fail("the read did not raise")


def test_every_engine_read_in_the_visualizer_package_is_captured():
    # Static read surface (audit H3): every beat-engine getter called anywhere in the Visualizer package outside the
    # engine itself is captured or answered by the snapshot engine. The fence's commit-sequence read was missing.
    import pathlib
    import re

    from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

    names = {n for n in dir(_SpotifyBeatEngine) if n.startswith(("get_", "is_", "peek_"))}
    root = pathlib.Path(__file__).resolve().parents[1] / "widgets" / "spotify_visualizer"
    read = set()
    for path in root.rglob("*.py"):
        if path.name in ("beat_engine.py", "audio_worker.py", "feature_replay.py"):
            continue
        text = path.read_text(encoding="utf-8")
        read |= {n for n in names if re.search(r"[.\"']" + n + r"\b", text)}
    assert len(read) > 20                                             # the scan finds the tick's reads
    assert read <= set(CAPTURED_GETTERS) | set(SPECIAL_READS), sorted(read - set(CAPTURED_GETTERS) - set(SPECIAL_READS))


def test_the_spectrum_rule_names_every_mode_whose_capture_reads_it():
    # The main process requests the spectrum from the mode rule; a mode whose tick read it without the rule would
    # raise in the worker. The gate below ticks every mode through the snapshot, so a missing entry fails there too.
    from widgets.spotify_visualizer.mode_capabilities import reads_analysis_spectrum

    assert all(reads_analysis_spectrum(mode) for mode in ("sphere", "oscilloscope", "shockwave_grid"))
    assert not reads_analysis_spectrum("spectrum")


@pytest.mark.qt
def test_a_tick_that_raises_closes_the_session(qt_app):
    # Fail closed (audit M2): a tick that raised left its controller half-updated, so the worker ends the session and
    # says so; the next input is refused instead of ticking on.
    import dataclasses

    import tools.expanded_visualizer_evidence as evidence
    from core.process.types import WorkerMessage
    from core.visualizer_engine.engine_worker import VisualizerEngineWorker
    from widgets.spotify_visualizer.feature_replay import deterministic_clock

    frames = evidence.shipped_clip(0.2).frames
    worker = VisualizerEngineWorker(None, None)
    reader = PacketMailbox(role="reader")
    try:
        with deterministic_clock() as clock:
            main = _MainSide("spectrum")

            def send(kind, payload, seq):
                return worker.handle_message(WorkerMessage(msg_type=kind, seq_no=seq, correlation_id=str(seq),
                                                           payload=payload))

            configured = send(MessageType.VIS_CONFIGURE, {"mapping": reader.mapping_name, "mode": "spectrum",
                                                          "runtime_generation": GENERATION, "inputs": "snapshot",
                                                          "initial_snapshot": main.initial()}, 1)
            assert configured.success, configured.error
            assert send(MessageType.VIS_INPUT, {"snapshot": main.step(frames[0], clock)}, 2).success
            # A snapshot from another mode's rule: the tick's declaration disagrees and raises mid-tick.
            wrong = dataclasses.replace(main.step(frames[1], clock), draws_samples=True)
            failed = send(MessageType.VIS_INPUT, {"snapshot": wrong}, 3)
            assert not failed.success and failed.payload.get("session_closed") is True
            after = send(MessageType.VIS_INPUT, {"snapshot": main.step(frames[2], clock)}, 4)
            assert not after.success and "no engine session" in after.error
    finally:
        worker._close_session()
        reader.close()
