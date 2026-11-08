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
    edges = [1.011, 1.022, 1.060, 1.071, 1.082, 1.120, 1.300]
    delivered = []
    for now in edges:
        delivered.extend(source.due(now, block, running=True))
    assert all(len(piece) == block for piece in delivered)
    assert len(delivered) == int((edges[-1] - 1.0) * rate // block)
    joined = np.concatenate(delivered)
    assert np.array_equal(joined, np.take(stream, np.arange(len(joined)), mode="wrap"))
    assert source.most_blocks >= int(0.18 * rate // block)          # the late 1.120 -> 1.300 edge catches up
    cursor = source.delivered_samples
    assert source.due(2.0, block, running=False) == []                # closed or paused: nothing, playhead held
    source.rebase()
    assert source.due(5.0, block, running=True) == []                 # reopened: the closed gap is not delivered
    after = source.due(5.011, block, running=True)
    assert np.array_equal(np.concatenate(after), np.take(stream, np.arange(cursor, cursor + len(after) * block),
                                                         mode="wrap"))


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
    assert verdict["torn_reads"] == 0 and not verdict["stranded"] and verdict["failure"] is None


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
    assert not verdict["paced_ok"] and verdict["published_hz"] < 0.6 * verdict["authored_hz"], verdict


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
def test_the_cadence_parks_with_the_display_and_resumes_without_an_audio_burst(qt_app, pcm):
    # Display power mid-run: the cadence parks (no frame published while parked), capture closes and reopens, and the
    # reopened source delivers nothing for the parked gap.
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
    assert verdict["failure"] is None and verdict["published"] > seen["parked_revision"]
    assert verdict["torn_reads"] == 0 and not verdict["stranded"]
    assert verdict["audio"]["paced_s"] <= verdict["seconds"] - 0.35          # the parked gap is not paced audio
    assert verdict["delivered_over_paced"] >= 0.97
    assert verdict["capture"][0] >= 2 or verdict["capture"][1] >= 1          # capture reopened after the park


@pytest.mark.qt
def test_a_mode_switch_restarts_the_cadence_on_the_new_activation(qt_app, pcm):
    seen = {}

    def switch(session):
        seen["before"] = session.mailbox.revision
        session.request_mode("bubble")
        seen["mode"] = session.mode

    verdict = gate.paced_in_process(*pcm, "spectrum", seconds=SECONDS, between=switch)
    assert seen["mode"] == "bubble" and verdict["failure"] is None
    assert verdict["published"] > seen["before"] and not verdict["stranded"] and verdict["torn_reads"] == 0


@pytest.mark.qt
def test_a_failing_step_closes_the_session_and_publishes_nothing_more(qt_app, pcm, monkeypatch):
    from widgets.spotify_visualizer import tick_pipeline

    tick, calls = tick_pipeline.logical_tick, [0]

    def failing(state):
        calls[0] += 1
        if calls[0] == 20:
            raise RuntimeError("injected tick failure")
        return tick(state)

    monkeypatch.setattr(tick_pipeline, "logical_tick", failing)
    verdict = gate.paced_in_process(*pcm, "spectrum", seconds=0.6)
    assert verdict["failure"] == "RuntimeError: injected tick failure" and not verdict["paced_ok"]
    assert verdict["published"] == 19 and calls[0] == 20                    # nothing ticked after the failure
    assert verdict["step_failures"] == 0 and not verdict["stranded"]


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
