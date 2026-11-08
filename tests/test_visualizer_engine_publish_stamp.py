"""Native core P2 gate 3 preparation: the engine worker's publish time reaches the main process's frame trace.

Each frame slot carries ``publish_ns`` (ABI 2, slot bytes 56-63: appended into the zero padding before the payload,
no field moved), the writer's ``time.perf_counter_ns()`` at publish. ``perf_counter`` is the clock every process
shares (QueryPerformanceCounter on Windows, no per-process origin), so a stamp made in a spawned process lies between
two readings the parent takes around it. The worker stamps only while the main process's ``--frame-trace`` is
admitted; the main side records the trace's ``LOGICAL_PUBLISH`` at the stamp when it takes the frame, and the live
check reads the same age chain (publish -> sync -> render -> swap) on both paths."""
from __future__ import annotations

import multiprocessing as mp
import struct
import time
import uuid

import pytest

from core.performance.frame_trace import FrameTraceEvent, FrameTraceSink
from core.visualizer_engine import packet_abi as abi
from core.visualizer_engine.packet_mailbox import PacketMailbox

SLOT = 256


def _fresh():
    buffer = bytearray(abi.mapping_bytes(SLOT))
    abi.initialise(buffer, slot_bytes=SLOT, runtime_generation=3, engine_generation=5, activation_id=7, mode_code=2)
    return buffer, abi.FramePacketWriter(buffer), abi.FramePacketReader(buffer)


def _slot_base(buffer, sequence):
    return next(abi.HEADER_BYTES + slot * SLOT for slot in range(abi.SLOT_COUNT)
                if struct.unpack_from("<Q", buffer, abi.HEADER_BYTES + slot * SLOT)[0] == sequence)


class _Recorder:
    """A frame-trace sink stand-in: every record, as its keyword arguments."""

    def __init__(self) -> None:
        self.records: list[tuple[int, dict]] = []

    def record(self, event, **kwargs) -> bool:
        self.records.append((int(event), kwargs))
        return True

    def publishes(self) -> list[dict]:
        return [kwargs for event, kwargs in self.records if event == FrameTraceEvent.LOGICAL_PUBLISH]


# -------------------------------------------------------------------------------------------- the ABI field


def test_the_publish_stamp_is_slot_bytes_56_to_63_and_nothing_moved():
    buffer, writer, reader = _fresh()
    sequence = writer.publish(b"payload", payload_schema=1, logical_timestamp=2.5, runtime_generation=11,
                              engine_generation=-1, activation_id=4, mode_code=abi.MODE_CODES["sphere"],
                              publish_ns=123_456_789_012)
    packet = reader.read_latest()
    assert packet.publish_ns == 123_456_789_012 and packet.payload == b"payload"
    base = _slot_base(buffer, sequence)
    assert struct.unpack_from("<Q", buffer, base + 56)[0] == 123_456_789_012
    # Append-only: the identity stays at 40, the payload at 64, the version 2.
    assert struct.unpack_from("<IIII", buffer, base + 40) == (11, 0xFFFFFFFF, 4, abi.MODE_CODES["sphere"])
    assert bytes(buffer[base + abi.SLOT_PAYLOAD_OFFSET:base + abi.SLOT_PAYLOAD_OFFSET + 7]) == b"payload"
    assert abi.SLOT_PAYLOAD_OFFSET == 64 and abi.ABI_VERSION == 2 and abi._SLOT_HEAD.size == 64


def test_an_unstamped_frame_carries_zero_and_a_stamp_that_does_not_fit_is_refused():
    buffer, writer, reader = _fresh()
    writer.publish(b"a", payload_schema=1, logical_timestamp=1.0, publish_ns=99)
    reader.read_latest()
    sequence = writer.publish(b"b", payload_schema=1, logical_timestamp=1.0)       # a writer that does not stamp
    assert reader.read_latest().publish_ns == 0                                    # 0: not stamped, never stale
    assert struct.unpack_from("<Q", buffer, _slot_base(buffer, sequence) + 56)[0] == 0
    for bad in (-1, 1 << 64):
        with pytest.raises(ValueError):
            writer.publish(b"c", payload_schema=1, logical_timestamp=1.0, publish_ns=bad)
    assert reader.read_latest() is None                                            # nothing of a refused frame


def test_a_torn_stamp_is_never_accepted():
    # The stamp is part of the slot head, under the seqlock: a slot whose begin is odd is refused whole.
    buffer, writer, reader = _fresh()
    sequence = writer.publish(b"x", payload_schema=1, logical_timestamp=1.0, publish_ns=7)
    struct.pack_into("<Q", buffer, _slot_base(buffer, sequence), sequence - 1)      # a writer mid-fill
    assert reader.read_latest() is None and reader.torn_reads == 1


# -------------------------------------------------------------------------------------- the shared clock


def _stamp_in_child(name, ready, go, clock):
    """Spawned: wait for ``go``, then publish one frame through the engine worker's writer (``clock`` "stamp": the
    production stamp; "process_time": a per-process clock in the field, the negative control)."""
    from multiprocessing.shared_memory import SharedMemory

    if clock == "stamp":
        box = PacketMailbox(role="writer", attach=name, publish_stamps=True)
        ready.set()
        go.wait(30)
        box.publish(None, generation=1, activation_id=1)
        box.close()
        return
    memory = SharedMemory(name=name)
    writer = abi.FramePacketWriter(memory.buf)
    ready.set()
    go.wait(30)
    writer.publish(b"x", payload_schema=1, logical_timestamp=1.0, publish_ns=time.process_time_ns())
    writer.release()
    memory.close()


def _bracketed_stamp(clock):
    context = mp.get_context("spawn")
    reader = PacketMailbox(role="reader")
    try:
        ready, go = context.Event(), context.Event()
        child = context.Process(target=_stamp_in_child, args=(reader.mapping_name, ready, go, clock))
        child.start()
        assert ready.wait(60)
        before = time.perf_counter_ns()
        go.set()
        child.join(60)
        after = time.perf_counter_ns()
        assert child.exitcode == 0
        packet = reader._reader.read_latest()
        return before, packet.publish_ns, after
    finally:
        reader.close()


def test_a_stamp_made_in_another_process_lies_on_this_processes_perf_counter():
    before, stamp, after = _bracketed_stamp("stamp")
    assert before <= stamp <= after, (before, stamp, after)


def test_negative_control_a_per_process_clock_falls_outside_the_bracket():
    # The bracket discriminates: a clock with a per-process origin (CPU time since the child's start) is far from it.
    before, stamp, after = _bracketed_stamp("process_time")
    assert stamp and not before <= stamp <= after


# ------------------------------------------------------------------------- the main side's trace record


def _loop(*, stamps: bool, traced: bool):
    reader = PacketMailbox(role="reader")
    recorder = _Recorder() if traced else None
    reader._frame_trace = recorder                     # as ``current_frame_trace()`` gives it at construction
    writer = PacketMailbox(role="writer", attach=reader.mapping_name, publish_stamps=stamps)
    return reader, writer, recorder


def test_the_reader_records_the_publish_at_the_writers_stamp_when_it_takes_the_frame():
    reader, writer, recorder = _loop(stamps=True, traced=True)
    try:
        assert reader.traces_publications
        writer.publish(None, generation=4, activation_id=2, now_ts=10.25)
        before_take = time.perf_counter_ns()
        assert reader.peek() is not None and recorder.publishes() == []          # a peek records nothing
        taken = reader.take()
        stamp = reader._peeked_publish_ns
        assert 0 < stamp <= before_take
        assert recorder.publishes() == [{"screen_index": -1, "revision": taken.revision, "auxiliary": 4,
                                         "logical_timestamp_ns": 0, "timestamp_ns": stamp}]
        assert reader.take() is None and len(recorder.publishes()) == 1           # once per frame
        # Superseded frames the reader never took are never recorded; the revision is the worker's publication count.
        for _ in range(3):
            writer.publish(None, generation=4, activation_id=2)
        newest = reader.take()
        assert newest.revision == taken.revision + 3
        assert [row["revision"] for row in recorder.publishes()] == [taken.revision, newest.revision]
        assert recorder.publishes()[1]["timestamp_ns"] > stamp
    finally:
        writer.close()
        reader.close()


def test_negative_controls_no_stamp_or_no_trace_records_nothing():
    # A writer that does not stamp (the trace not admitted on the main side): the frame is taken, nothing recorded.
    reader, writer, recorder = _loop(stamps=False, traced=True)
    try:
        writer.publish(None, generation=1, activation_id=1)
        assert reader.take() is not None and recorder.publishes() == [] and reader._peeked_publish_ns == 0
    finally:
        writer.close()
        reader.close()
    # No trace in the reader's process: nothing asks for stamps.
    reader, writer, _ = _loop(stamps=True, traced=False)
    try:
        assert not reader.traces_publications
        writer.publish(None, generation=1, activation_id=1)
        assert reader.take() is not None
    finally:
        writer.close()
        reader.close()


def test_the_unstamped_writer_never_reads_a_clock(monkeypatch):
    # Zero cost at rest: with stamps off the writer's publish reads no perf_counter_ns at all.
    import core.visualizer_engine.packet_mailbox as module

    reads = []
    monkeypatch.setattr(module.time, "perf_counter_ns", lambda: reads.append(1) or 1)
    reader, writer, _ = _loop(stamps=False, traced=False)
    try:
        writer.publish(None, generation=1, activation_id=1)
        assert reads == []
        stamped = PacketMailbox(role="writer", attach=reader.mapping_name, publish_stamps=True)
        try:
            stamped.publish(None, generation=1, activation_id=1)
            assert reads == [1]                         # control: the stamping writer reads it once per publish
        finally:
            stamped.close()
    finally:
        writer.close()
        reader.close()


def test_the_link_asks_for_stamps_only_while_the_trace_is_admitted(monkeypatch):
    # The configure's ``publish_stamps`` follows the reader's trace admission (read once at construction).
    from core.performance import frame_trace

    monkeypatch.setattr(frame_trace, "_active_sink", _Recorder())
    traced = PacketMailbox(role="reader")
    monkeypatch.setattr(frame_trace, "_active_sink", None)
    plain = PacketMailbox(role="reader")
    try:
        assert traced.traces_publications and not plain.traces_publications
    finally:
        traced.close()
        plain.close()


@pytest.mark.qt
def test_on_the_engine_worker_the_main_trace_records_the_workers_publishes(qt_app, monkeypatch):
    # End to end: the production owner on a spawned engine worker with the trace admitted in this process. The
    # worker stamps its slots, the main side records each frame it takes at the worker's stamp, and every stamp lies on
    # this process's perf_counter (between the test's start and the record). Control: the configure asked for stamps.
    from core.performance import frame_trace
    from core.process.supervisor import ProcessSupervisor
    from core.process.types import MessageType, WorkerType
    from core.visualizer_engine.engine_worker import EngineSession, visualizer_worker_main
    from tools.visualizer_replay import owner_worker_gate as gate
    from tools.visualizer_replay.live_engine_gate import paced_pcm
    from widgets.spotify_visualizer import engine_worker_link

    def _device(_config=None):
        raise AssertionError("a test opened an audio device")

    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", _device)
    monkeypatch.setattr(EngineSession, "LIVE_EDGE_TIMEOUT_S", 10.0)
    engine_worker_link.reset_run_state_for_testing()
    recorder = _Recorder()
    monkeypatch.setattr(frame_trace, "_active_sink", recorder)
    sent = []
    send = ProcessSupervisor.send_message

    def watched(self, worker_type, msg_type, payload, correlation_id=None):
        sent.append((msg_type, dict(payload)))
        return send(self, worker_type, msg_type, payload, correlation_id=correlation_id)

    monkeypatch.setattr(ProcessSupervisor, "send_message", watched)
    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    assert supervisor.start(WorkerType.VISUALIZER)
    began = time.perf_counter_ns()
    pcm, rate = paced_pcm(3.0)
    rig = gate.OwnerRig("spectrum", worker=True, supervisor=supervisor, cadence="thread")
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm, pcm_rate=rate):
            owner = rig.build()
        gate._event_loop_for(rig.app, 15.0, until=lambda: len(recorder.publishes()) > 30)
        ended = time.perf_counter_ns()
        configure = [payload for message, payload in sent if message == MessageType.VIS_CONFIGURE]
        assert configure and configure[0]["publish_stamps"] is True
        assert owner._worker is not None and owner.controller.logical_runtime is None    # no tick in main
        publishes = recorder.publishes()
        assert len(publishes) > 30
        stamps = [row["timestamp_ns"] for row in publishes]
        assert all(began < stamp < ended for stamp in stamps), (began, stamps[:3], ended)
        revisions = [row["revision"] for row in publishes]
        assert revisions == sorted(revisions) and len(set(revisions)) == len(revisions)
        # The tick's own time, as the live check reads it: logical timestamp (the worker's authored now) -> publish.
        ticks = [(row["timestamp_ns"] - row["logical_timestamp_ns"]) / 1e6 for row in publishes
                 if row["logical_timestamp_ns"] > 0]
        assert ticks and all(0.0 <= tick < 1000.0 for tick in ticks)
    finally:
        rig.close()
        supervisor.shutdown()
        engine_worker_link.reset_run_state_for_testing()
