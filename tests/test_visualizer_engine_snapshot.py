"""Native core P2a live inputs: the lossless engine snapshot (core/visualizer_engine/engine_snapshot.py).

The gate: the main process steps its beat engine (production DSP on the clip's native PCM, ``ProductionLaneEngine``)
and captures a snapshot per tick; an engine session ticks from those snapshots through ``SnapshotBeatEngine`` and
returns the tick's demands. Its frames, read back through the frame packet ABI, equal the in-process tick on the same
engine for every mode; in a ``WorkerType.VISUALIZER`` process too."""
import pytest

from core.process.supervisor import ProcessSupervisor
from core.process.types import MessageType, WorkerType
from core.visualizer_engine.engine_snapshot import (
    CAPTURED_GETTERS, EngineDemands, EngineSnapshotSource, SnapshotBeatEngine,
)
from core.visualizer_engine.engine_worker import EngineSession, visualizer_worker_main
from core.visualizer_engine.packet_mailbox import PacketMailbox

GENERATION = 9001


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
                                inputs="snapshot", initial_snapshot=main.initial())
        try:
            digests = []
            for feature in frames:
                _revision, demands = session.tick_snapshot(main.step(feature, session.clock))
                main.source.apply_demands(demands)
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
                         "inputs": "snapshot", "initial_snapshot": main.initial()}, timeout_ms=60_000)
                    assert configured is not None and configured.success, (mode, configured and configured.error)
                    seen = []
                    for feature in frames:
                        response = supervisor.send_request_and_await_response(
                            WorkerType.VISUALIZER, MessageType.VIS_INPUT, {"snapshot": main.step(feature, clock)},
                            timeout_ms=30_000)
                        assert response is not None and response.success, (mode, response and response.error)
                        main.source.apply_demands(response.payload["demands"])
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
    source = EngineSnapshotSource(engine, "oscilloscope")             # a mode that draws samples
    worker = SnapshotBeatEngine(source.capture(0.0, playing=True, step=False))
    worker.accept_snapshot(source.capture(0.01, playing=True))
    assert engine.writes == [("idle", True), ("history", True), "tick"]   # declared before stepping, as the tick does
    worker.set_idle_waveform_demand(True)
    worker.set_waveform_history_demand(True)
    with pytest.raises(RuntimeError):
        worker.set_waveform_history_demand(False)                     # another mode's rule: never silently diverge


def test_the_ticks_spectrum_request_reaches_the_main_engine():
    engine = _Engine()
    source = EngineSnapshotSource(engine, "spectrum")
    worker = SnapshotBeatEngine(source.capture(0.0, playing=True, step=False))
    assert worker.get_smoothed_bars() == ["get_smoothed_bars"]
    assert worker.get_pre_agc_analysis_spectrum() == (0.5,)   # the peeked value; reading it requests the next
    demands = worker.take_demands()
    assert demands == EngineDemands(analysis_spectrum=True)
    source.apply_demands(demands)
    assert engine.writes == ["spectrum"]
    assert worker.take_demands() == EngineDemands()            # per tick: nothing read, nothing requested
    with pytest.raises(RuntimeError):
        worker.get_not_captured()                              # a read no snapshot carries fails loudly
