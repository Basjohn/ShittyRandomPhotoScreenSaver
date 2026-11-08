"""Native core P2b slice 2: the live engine off its steady state, in process and in the worker (audit H3, 4b).

The live-engine rig (``EngineSession(inputs="live")``) in production commit order (checkpoint audit 3, A3-H1: the
tick's own step submits the newest block and the tick reads the previous commit, held deterministic at the compute
lane's admission gate) through pause/resume (warm and cold capture), the warm re-entry fence (resume and display
power), and in-session mode switches (``VIS_SET_MODE``), identical in a ``WorkerType.VISUALIZER`` process; the
per-slot identity and flags a native reader validates with plain ``struct`` (audits H5, A3-M4); the spectrum demand at
activation (A3-M1); the device refusal in any process (A3-L1), per engine (A4-L3, A3-L5); and the warm resume's capture
restart (A3-L2). Checkpoint audit 4: a same-mode request is the owner's preset activation (A4-M3); an admission failure
publishes nothing of its tick (A4-L6)."""
import dataclasses
import struct

import pytest

from core.process.supervisor import ProcessSupervisor
from core.process.types import MessageType, WorkerType
from core.visualizer_engine import packet_abi as abi
from core.visualizer_engine.engine_worker import EngineSession, visualizer_worker_main
from core.visualizer_engine.packet_mailbox import PacketMailbox
from core.visualizer_engine.recorded_capture import synthesise_pause
from tools.visualizer_replay import live_engine_gate as gate

GENERATION = gate.GENERATION
U32_NONE = 0xFFFFFFFF


@pytest.fixture(autouse=True)
def _short_edges(monkeypatch):
    monkeypatch.setattr(EngineSession, "LIVE_EDGE_TIMEOUT_S", 10.0)


@pytest.fixture
def supervisor():
    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    assert supervisor.start(WorkerType.VISUALIZER)
    yield supervisor
    supervisor.shutdown()
    assert not supervisor.is_running(WorkerType.VISUALIZER)


def _clip(seconds=4.0):
    import tools.expanded_visualizer_evidence as evidence
    return evidence.shipped_clip(seconds).frames


def _session(reader, mode, **kwargs):
    from widgets.spotify_visualizer.feature_replay import REPLAY_SEED

    return EngineSession(mapping=reader.mapping_name, mode=mode, runtime_generation=GENERATION, inputs="live",
                         seed=REPLAY_SEED, **kwargs)


def _drive(mode, script, *, order="production", observe=None):
    """In process; ``observe(session, frame_state, feature)`` after every tick."""
    reader = PacketMailbox(role="reader")
    session = _session(reader, mode, order=order)
    try:
        for kind, value in script:
            if kind == "input":
                session.tick(value)
                state = reader.take().state
                if observe is not None:
                    observe(session, state, value)
            elif kind == "mode":
                session.request_mode(value)
            else:
                session.set_display_power(value)
    finally:
        session.close()
        reader.close()


@pytest.mark.qt
def test_production_order_ticks_read_the_previous_commit(qt_app, monkeypatch):
    # Live, the tick's own engine step submits the newest block's analysis and the tick reads what is committed then:
    # the previous block's. The rig holds that analysis at the admission gate until the tick returns, so the tick
    # reads exactly the previous commit, every time (A3-H1); ``settled`` order (slice 1) reads its own block's.
    # Adversarial schedule: after each step that submitted an analysis, the tick gives it up to 50 ms to commit
    # before reading (the race the gate exists for; without the gate the analysis wins it).
    from widgets.spotify_visualizer import tick_pipeline
    from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

    original_step = _SpotifyBeatEngine.tick

    def slow_step(engine):
        result = original_step(engine)
        if engine.has_analysis_in_flight():
            engine._analysis_settled_observer.__self__.wait(0.05)   # the session's settled Event
        return result

    monkeypatch.setattr(_SpotifyBeatEngine, "tick", slow_step)

    def run(order):
        seen, publications, serial = [], [], None
        original = tick_pipeline.consume_engine_bars

        def spy(widget, now_ts):
            result = original(widget, now_ts)
            seen.append(widget._engine.get_authoritative_frame_commit_seq())
            return result

        tick_pipeline.consume_engine_bars = spy
        try:
            def observe(_session, _state, feature):
                nonlocal serial
                if feature.capture_history.capture_serial != serial:
                    serial = feature.capture_history.capture_serial
                publications.append(serial)
            _drive("spectrum", gate.steps("steady", _clip(0.5), "spectrum"), order=order, observe=observe)
        finally:
            tick_pipeline.consume_engine_bars = original
        new = [index for index, s in enumerate(publications) if index == 0 or s != publications[index - 1]]
        return seen, new

    seen, new = run("production")
    for count, index in enumerate(new):
        assert seen[index] == count, (index, seen[index], count)        # this block's commit is not read yet
    settled, new = run("settled")
    assert [settled[index] for index in new] == list(range(1, len(new) + 1))   # control: the other order


@pytest.mark.qt
@pytest.mark.parametrize("scenario", ["pause_warm", "pause_cold", "reentry"])
def test_pause_resume_and_reentry_tick_identical_frames_in_the_worker(qt_app, supervisor, scenario):
    # The paused tick path (idle waveform/bars, the warm-capture grace and, cold, its expiry), the resume (wake, ramp,
    # capture reopening on its lane, the fence) and display power re-entry: the worker's frames and slot heads equal
    # the in-process ones, for a sample-drawing mode, a bar mode and the 3D simulation.
    for mode in ("oscilloscope", "spectrum", "extruded_bubble"):
        script = gate.steps(scenario, _clip(), mode)
        local = gate.run_in_process(script, mode)
        worker = gate.run_in_worker(supervisor, script, mode)
        assert len(local["digests"]) > 250
        assert worker["digests"] == local["digests"], (scenario, mode)
        assert worker["heads"] == local["heads"], (scenario, mode)


@pytest.mark.qt
def test_a_cold_pause_stops_capture_and_the_resume_reopens_it(qt_app):
    # Past the warm grace the paused tick stops capture (the authored clock decides it); the resume reopens it on its
    # lane before the next block (the session waits on the lane's completion edge) and restarts the ramp.
    frames = synthesise_pause(_clip(3.0), at_s=1.0, pause_s=7.0)
    states = []

    def observe(session, state, feature):
        backend = session._backend
        states.append((feature.playing, backend is not None and backend.is_running(), session.capture_counts[0],
                       session._engine.is_reactivity_play_ramping()))

    _drive("spectrum", [("input", f) for f in frames], observe=observe)
    paused = [s for s in states if not s[0]]
    resumed = [s for s in states[len(states) - len(paused):] if s[0]]
    assert paused[0][1] and not paused[-1][1]              # warm at first, stopped once the grace expired
    assert resumed and resumed[0][1] and resumed[0][2] == 2  # reopened: a second recorded source
    assert resumed[0][3]                                   # a cold resume restarts the reactivity ramp


@pytest.mark.qt
@pytest.mark.parametrize("scenario", ["pause_warm", "reentry"])
def test_the_fence_never_admits_the_retained_frame_on_reentry(qt_app, monkeypatch, scenario):
    # Resume and display power re-entry arm the fence on the engine's commit sequence (the owner's set_playing /
    # set_display_power): the ticks before a post-re-entry commit present nothing from the retained frame, the first
    # tick after one does. Control: with the arm disabled the retained frame is presented at once.
    from widgets.spotify_visualizer import tick_pipeline

    def resume_rows():
        rows, armed = [], []

        def observe(session, state, feature):
            fence = session._controller.logical_tick_state
            rows.append((feature.playing, state.present_frame, fence._waiting_for_fresh_engine_frame,
                         session._engine.get_authoritative_frame_commit_seq()))
            armed.append(fence._pending_engine_frame_epoch)

        script = gate.steps(scenario, _clip(), "spectrum")
        _drive("spectrum", script, observe=observe)
        if scenario == "pause_warm":
            start = next(i for i, row in enumerate(rows) if not row[0])
            start = next(i for i in range(start, len(rows)) if rows[i][0])
        else:                                              # the inputs ticked before the park
            start = sum(1 for kind, _v in script[:[k for k, _ in script].index("display")] if kind == "input")
        return rows[start:start + 4], armed[start:start + 4], rows[start - 1][3]

    rows, armed, retained_seq = resume_rows()
    # The two re-entry ticks carry no new capture: held, the watermark is the retained frame's commit sequence.
    assert [row[1] for row in rows[:2]] == [False, False] and all(row[2] for row in rows[:2])
    assert armed[0] == retained_seq
    # The first tick that reads a commit made after re-entry is presented and clears the fence.
    # (Production order: a tick's commit lands after it, so the tick after the first post-re-entry commit reads it.)
    first = next(i for i, row in enumerate(rows) if row[3] > retained_seq)
    assert rows[first + 1][1] and not rows[first + 1][2]

    def never_armed(state, _engine):
        # The arm disabled: every engine treated as cold (the helper's own cold path). The session's configure runs
        # it too (the owner's configure, A5-M2), so a stub that left the state untouched would also skip that clear.
        state._waiting_for_fresh_engine_frame = False
        state._pending_engine_frame_epoch = -1
        return False

    monkeypatch.setattr(tick_pipeline, "arm_reentry_fresh_frame_fence", never_armed)
    rows, _armed, _seq = resume_rows()
    assert rows[0][1] and not rows[0][2]                  # control: the retained frame is admitted at once


@pytest.mark.qt
@pytest.mark.parametrize("pair", [("spectrum", "extruded_bubble"), ("extruded_bubble", "spectrum"),
                                  ("oscilloscope", "bubble")])
def test_an_in_session_mode_switch_ticks_identical_frames_in_the_worker(qt_app, supervisor, pair):
    # VIS_SET_MODE applied at the next tick boundary on the existing session (playing, then paused with a switch
    # back, then resumed): identical frames and slot heads in process and in the worker.
    mode, partner = pair
    script = gate.steps("switch", _clip(), mode, partner)
    local = gate.run_in_process(script, mode)
    worker = gate.run_in_worker(supervisor, script, mode)
    assert worker["digests"] == local["digests"] and worker["heads"] == local["heads"]
    codes = {head[4] for head in local["heads"]}
    assert codes == {abi.MODE_CODES[mode], abi.MODE_CODES[partner]}


@pytest.mark.qt
def test_a_mode_switch_is_applied_in_place_never_a_rebuild(qt_app):
    # The engine, its capture source, the mailbox and the runtime generation stay; the engine commits one new
    # generation and activation; the newest request before a tick wins; a mode the ABI cannot name is refused at
    # request time and leaves the session intact.
    frames = _clip(1.0)
    reader = PacketMailbox(role="reader")
    session = _session(reader, "spectrum")
    try:
        for feature in frames[:20]:
            session.tick(feature)
        engine, mailbox = session._engine, session.mailbox
        generation, activation = engine.get_generation_id(), engine.get_activation_id()
        session.request_mode("bubble")
        session.request_mode("extruded_bubble")           # latest wins
        with pytest.raises(KeyError):
            session.request_mode("not_a_mode")
        session.tick(frames[20])
        state = reader.take().state
        assert state.mode_id == "extruded_bubble" and session._engine is engine and session.mailbox is mailbox
        assert (engine.get_generation_id(), engine.get_activation_id()) == (generation + 1, activation + 1)
        assert state.runtime_generation == GENERATION and session.capture_counts[0] == 1
    finally:
        session.close()
        reader.close()


@pytest.mark.qt
def test_a_same_mode_request_is_the_owners_preset_activation_never_dropped(qt_app):
    # A4-M3: VIS_SET_MODE for the current mode carries a preset (or settings); it is applied as the owner's same-mode
    # preset activation (new settings, a new engine activation, frames under it), never acknowledged and dropped.
    from widgets.spotify_visualizer.feature_replay import offline_activation_request

    frames = _clip(1.0)
    reader = PacketMailbox(role="reader")
    session = _session(reader, "spectrum")
    try:
        for feature in frames[:10]:
            session.tick(feature)
            reader.take()
        engine, controller = session._engine, session._controller
        activation = engine.get_activation_id()
        session.request_mode("spectrum", preset=1)
        session.tick(frames[10])
        state = reader.take().state
        assert engine.get_activation_id() == activation + 1 and state.activation_id == activation + 1
        assert state.mode_id == "spectrum" and session.mode == "spectrum"
        assert controller.settings_model == offline_activation_request("spectrum", 1)["settings_model"]
    finally:
        session.close()
        reader.close()


@pytest.mark.qt
def test_an_admission_failure_publishes_nothing_of_that_tick(qt_app, monkeypatch):
    # A4-L6: an analysis that outwaits the admission gate (production order) fails the session before that tick's
    # frame reaches the mapping, not after. The failure is recorded while the tick runs (as the compute lane would).
    from widgets.spotify_visualizer import tick_pipeline

    frames = _clip(0.5)
    reader = PacketMailbox(role="reader")
    session = _session(reader, "spectrum")
    try:
        for feature in frames[:5]:
            session.tick(feature)
            reader.take()
        original = tick_pipeline.consume_engine_bars

        def failed_admission(widget, now_ts):
            session._admission_failed = True
            return original(widget, now_ts)

        monkeypatch.setattr(tick_pipeline, "consume_engine_bars", failed_admission)
        revision = session.mailbox.revision
        with pytest.raises(RuntimeError, match="admission gate"):
            session.tick(frames[5])
        assert reader.take() is None and session.mailbox.revision == revision
    finally:
        session.close()
        reader.close()


@pytest.mark.qt
def test_each_slot_carries_the_identity_and_flags_a_native_reader_validates(qt_app):
    # Plain struct at the ABI's offsets, no codec: the header's configure-time identity; every slot's own identity
    # (runtime/engine generation, activation, mode code) and flags under its seqlock, equal to the frame it holds,
    # changing with the frame across an in-place switch (A3-M4).
    from multiprocessing.shared_memory import SharedMemory

    reader = PacketMailbox(role="reader")
    tap = SharedMemory(name=reader.mapping_name)
    session = _session(reader, "spectrum")
    frames = synthesise_pause(_clip(1.5), at_s=0.5, pause_s=0.3)
    seen_codes, seen_flags = set(), set()
    try:
        engine = session._engine
        assert struct.unpack_from("<4sH", tap.buf, 0) == (b"SRVZ", abi.ABI_VERSION) and abi.ABI_VERSION == 2
        assert struct.unpack_from("<IIII", tap.buf, 8)[:3] == (GENERATION, engine.get_generation_id(),
                                                              engine.get_activation_id())
        assert struct.unpack_from("<I", tap.buf, 28)[0] == abi.MODE_CODES["spectrum"]
        for index, feature in enumerate(frames):
            if index == 60:
                session.request_mode("oscilloscope")
            session.tick(feature)
            state = reader.take().state
            flags, *identity = gate.newest_slot_head(tap.buf)
            expected = ((abi.FLAG_CHANGED if state.changed else 0) | (abi.FLAG_PRESENT_FRAME if state.present_frame else 0)
                        | (abi.FLAG_MODE_REVEAL_READY if state.mode_reveal_ready else 0)
                        | (abi.FLAG_PLAYING if state.playing else 0))
            assert flags == expected, index
            assert identity == [state.runtime_generation, state.engine_generation & U32_NONE,
                                state.activation_id & U32_NONE, abi.MODE_CODES[state.mode_id]], index
            seen_codes.add(identity[3])
            seen_flags.add(flags)
        assert seen_codes == {abi.MODE_CODES["spectrum"], abi.MODE_CODES["oscilloscope"]}
        assert any(not f & abi.FLAG_PLAYING for f in seen_flags) and any(f & abi.FLAG_PLAYING for f in seen_flags)
        # The header stays the configure-time identity (never relabelled in place).
        assert struct.unpack_from("<I", tap.buf, 28)[0] == abi.MODE_CODES["spectrum"]
    finally:
        session.close()
        tap.close()
        reader.close()


@pytest.mark.qt
def test_a_recorded_session_refuses_an_audio_device_in_any_process(qt_app, supervisor):
    # A3-L1: a test's monkeypatch reaches only its own process; the session itself refuses a device for its life,
    # in process and in the worker (the configure reply reports it). A4-L3: per engine, never a process-wide swap:
    # two sessions closing out of order (A opened first, closed first) never touch the module's device factory, each
    # session's engine refuses the device path (its own factory removed, capture fails closed), and an engine that is
    # not a session's keeps the device path while sessions are open.
    from widgets.spotify_visualizer import audio_worker

    device = audio_worker.create_audio_capture
    first_reader, second_reader = PacketMailbox(role="reader"), PacketMailbox(role="reader")
    first = _session(first_reader, "spectrum")
    second = None
    try:
        second = _session(second_reader, "oscilloscope")
        assert first.device_refused and second.device_refused
        assert audio_worker.create_audio_capture is device
        production = audio_worker.SpotifyVisualizerAudioWorker()
        assert production._capture_factory() is device and not production.devices_refused
        for session in (first, second):
            worker = session._engine._audio_worker
            assert worker._capture_factory() == session._open_capture   # the recorded source seam
            worker._capture_backend_factory = None                       # without it, the device path refuses
            with pytest.raises(RuntimeError, match="never opens an audio device"):
                worker._capture_factory()(None)
            worker._capture_backend_factory = session._open_capture
        first.close()
        assert audio_worker.create_audio_capture is device and second.device_refused
    finally:
        first.close()
        if second is not None:
            second.close()
        first_reader.close()
        second_reader.close()
    assert audio_worker.create_audio_capture is device
    worker_reader = PacketMailbox(role="reader")
    try:
        configured = gate.configure_worker(supervisor, worker_reader, "spectrum")
        assert configured.payload["device_refused"] is True
    finally:
        worker_reader.close()


@pytest.mark.qt
def test_an_installed_capture_source_is_used_whatever_its_truth_value(qt_app):
    # A3-L5: the device is the source only when no factory is installed (``is None``), never when an installed one is
    # falsy (a source object with ``__len__`` or ``__bool__``). Control: the former ``factory or device`` lookup sends
    # such a source to the device.
    from widgets.spotify_visualizer import audio_worker

    class EmptySource:
        def __len__(self):
            return 0

        def __call__(self, config):
            return None

    source = EmptySource()
    worker = audio_worker.SpotifyVisualizerAudioWorker()
    worker.set_capture_backend_factory(source)
    with worker._capture_lock:
        assert worker._capture_factory() is source
    assert (source or audio_worker.create_audio_capture) is audio_worker.create_audio_capture


@pytest.mark.qt
def test_the_warm_resume_capture_restart_is_frame_neutral(qt_app, monkeypatch):
    # A3-L2: ``wake`` restarts a capture that went quiet, judged on the wall clock (0.5 s), so whether a warm resume in
    # the rig restarts depends on how long the rig took. Forced both ways on the history-drawing mode: the restart
    # runs on the capture lane before the next block and the frames are identical.
    from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker

    script = gate.steps("pause_warm", _clip(3.0), "oscilloscope")
    runs = {}
    for stale in (True, False):
        monkeypatch.setattr(SpotifyVisualizerAudioWorker, "is_capture_stale", lambda self, _s=stale: _s)
        runs[stale] = gate.run_in_process(script, "oscilloscope")
    assert runs[True]["restarts"] == 1 and runs[False]["restarts"] == 0
    assert runs[True]["digests"] == runs[False]["digests"]


@pytest.mark.qt
def test_a_free_running_worker_never_strands_or_tears_a_frame(qt_app, supervisor):
    # Not an identity check: the worker in ``free`` order (commits race the tick) with the reader taking frames on its
    # own wake thread; no exception, revisions only advance, the last frame is taken, nothing torn.
    result = gate.stress_in_worker(supervisor, _clip(1.0), "spectrum")
    assert result["ok"] and result["taken"] > 0 and result["torn_reads"] == 0, result


@pytest.mark.qt
def test_a_paused_input_with_a_new_capture_publication_fails_closed(qt_app):
    # The recorder records no new publication while paused; an input that carries one is outside the rig's contract.
    frames = _clip(0.2)
    reader = PacketMailbox(role="reader")
    session = _session(reader, "spectrum")
    try:
        session.tick(frames[0])
        with pytest.raises(ValueError):
            session.tick(dataclasses.replace(frames[3], playing=False))
    finally:
        session.close()
        reader.close()
